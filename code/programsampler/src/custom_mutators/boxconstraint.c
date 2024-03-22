/*
*/

// You need to use -I /path/to/AFLplusplus/include
#include "afl-fuzz.h"
#include "custom_mutator_helpers.h"

#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

typedef struct {
  uint8_t low;
  uint8_t high;
} Interval;

typedef struct {
  uint64_t size;
  Interval *interval;
} Boxconstraint;

typedef struct {
  Boxconstraint* h;
  u64 id;
} constraint_g;

typedef struct {
    int dimension;
    int count;
} DimensionCount;


static uint64_t executions = 0;
typedef struct my_mutator {

  afl_state_t *afl;

  // any additional data here!
  size_t trim_size_current;
  int    trimmming_steps;
  int    cur_step;
  constraint_g constraints[1000];
  uint16_t last_idx;

  // Reused buffers:
  BUF_VAR(u8, fuzz);
  BUF_VAR(u8, data);
  BUF_VAR(u8, havoc);
  BUF_VAR(u8, trim);
  BUF_VAR(u8, post_process);

} my_mutator_t;

void print_boxconstraint(Boxconstraint *h) {
    for (uint64_t i = 0; i < h->size; i++) {
        fprintf(stderr,"%lu: [%d, %d] \n", i, h->interval[i].low, h->interval[i].high);
    }
    fprintf(stderr,"\n");
}

/**
 * Initialize this custom mutator
 *
 * @param[in] afl a pointer to the internal state object. Can be ignored for
 * now.
 * @param[in] seed A seed for this mutator - the same seed should always mutate
 * in the same way.
 * @return Pointer to the data object this custom mutator instance should use.
 *         There may be multiple instances of this mutator in one afl-fuzz run!
 *         Return NULL on error.
 */
my_mutator_t *afl_custom_init(afl_state_t *afl, unsigned int seed) {

  my_mutator_t *data = calloc(1, sizeof(my_mutator_t));
  if (!data) {

    perror("afl_custom_init alloc");
    return NULL;

  }

  data->afl = afl;

  return data;

}

static void dump(char *txt, u8 *buf, u32 len) {

  u32 i;
  fprintf(stderr, "DUMP %s %016llx ", txt, hash64(buf, len, HASH_CONST));
  for (i = 0; i < len; i++)
    fprintf(stderr, "(%d, %d) \n", i, (int) buf[i]);
  fprintf(stderr, "\n");

}

static u8 get_exec_checksum(afl_state_t *afl, u8 *buf, u32 len, u64 *cksum) {

  if (unlikely(common_fuzz_stuff(afl, buf, len))) { return 1; }

  *cksum = hash64(afl->fsrv.trace_bits, afl->fsrv.map_size, HASH_CONST);
  executions++;

  return 0;

}

uint64_t montecarlo_count(Boxconstraint* h, uint64_t trials, my_mutator_t *data, uint8_t *buf, size_t buf_size, u64 exec_cksum) {
  uint64_t success = 0;
  for (uint64_t i = 0; i < trials; i++) {
	for (uint64_t i = 0; i < h->size; i++) {
	  buf[i] = rand() % (h->interval[i].high - h->interval[i].low + 1) +
			h->interval[i].low;
	}
    u64 cksum = 0;
    u64 old_crashes = data->afl->total_crashes;
    u64 old_timeouts = data->afl->total_tmouts;
    if (unlikely(get_exec_checksum(data->afl, buf, buf_size, &cksum))) {
        perror("error in get_exec_checksum\n");
    }
    u64 new_crashes = data->afl->total_crashes;
    u64 new_timeouts = data->afl->total_tmouts;
    if (cksum == exec_cksum) {
      success += 1;
	}
    if (new_timeouts == old_timeouts && new_crashes == old_crashes) {
    } else {
        char bad_input_filename[256];
        time_t t = time(NULL);
        snprintf(bad_input_filename, sizeof(bad_input_filename), "bad_inputs/%ld", (long) t);
        FILE *file = fopen(bad_input_filename, "w");
        if (file == NULL) {
            FATAL("Error: opening file.\n");
            exit(1);
        }
        fwrite(buf, sizeof(char), buf_size, file);
        fclose(file);
    }
  }
  return success;
}
/**
 * This method is called at the start of each trimming operation and receives
 * the initial buffer. It should return the amount of iteration steps possible
 * on this input (e.g. if your input has n elements and you want to remove
 * them one by one, return n, if you do a binary search, return log(n),
 * and so on...).
 *
 * If your trimming algorithm doesn't allow you to determine the amount of
 * (remaining) steps easily (esp. while running), then you can alternatively
 * return 1 here and always return 0 in post_trim until you are finished and
 * no steps remain. In that case, returning 1 in post_trim will end the
 * trimming routine. The whole current index/max iterations stuff is only used
 * to show progress.
 *
 * (Optional)
 *
 * @param data pointer returned in afl_custom_init for this fuzz case
 * @param buf Buffer containing the test case
 * @param buf_size Size of the test case
 * @return The amount of possible iteration steps to trim the input.
 *        negative on error.
 */
int32_t afl_custom_init_trim(my_mutator_t *data, uint8_t *buf,
                             size_t buf_size) {

  // We simply trim once
  data->trimmming_steps = 1;

  data->cur_step = 0;

  if (!maybe_grow(BUF_PARAMS(data, trim), buf_size)) {

    perror("init_trim grow");
    return -1;

  }

  memcpy(data->trim_buf, buf, buf_size);

  data->trim_size_current = buf_size;

  return data->trimmming_steps;

}

/**
 * This method is called for each trimming operation. It doesn't have any
 * arguments because we already have the initial buffer from init_trim and we
 * can memorize the current state in *data. This can also save
 * reparsing steps for each iteration. It should return the trimmed input
 * buffer, where the returned data must not exceed the initial input data in
 * length. Returning anything that is larger than the original data (passed
 * to init_trim) will result in a fatal abort of AFLFuzz.
 *
 * (Optional)
 *
 * @param[in] data pointer returned in afl_custom_init for this fuzz case
 * @param[out] out_buf Pointer to the buffer containing the trimmed test case.
 *     External library should allocate memory for out_buf.
 *     AFL++ will not release the memory after saving the test case.
 *     Keep a ref in *data.
 *     *out_buf = NULL is treated as error.
 * @return Pointer to the size of the trimmed test case
 */
size_t afl_custom_trim(my_mutator_t *data, uint8_t **out_buf) {

  *out_buf = data->trim_buf;

  // Remove the last byte of the trimming input
  return data->trim_size_current - 1;

}

/**
 * This method is called after each trim operation to inform you if your
 * trimming step was successful or not (in terms of coverage). If you receive
 * a failure here, you should reset your input to the last known good state.
 *
 * (Optional)
 *
 * @param[in] data pointer returned in afl_custom_init for this fuzz case
 * @param success Indicates if the last trim operation was successful.
 * @return The next trim iteration index (from 0 to the maximum amount of
 *     steps returned in init_trim). negative ret on failure.
 */
int32_t afl_custom_post_trim(my_mutator_t *data, int success) {

  if (success) {

    ++data->cur_step;
    return data->cur_step;

  }

  return data->trimmming_steps;

}

/**
 * Perform a single custom mutation on a given input.
 * This mutation is stacked with the other muatations in havoc.
 *
 * (Optional)
 *
 * @param[in] data pointer returned in afl_custom_init for this fuzz case
 * @param[in] buf Pointer to the input data to be mutated and the mutated
 *     output
 * @param[in] buf_size Size of input data
 * @param[out] out_buf The output buffer. buf can be reused, if the content
 * fits. *out_buf = NULL is treated as error.
 * @param[in] max_size Maximum size of the mutated output. The mutation must
 *     not produce data larger than max_size.
 * @return Size of the mutated output.
 */
size_t afl_custom_havoc_mutation(my_mutator_t *data, u8 *buf, size_t buf_size,
                                 u8 **out_buf, size_t max_size) {

  assert(0);
  if (buf_size == 0) {

    *out_buf = maybe_grow(BUF_PARAMS(data, havoc), 1);
    if (!*out_buf) {

      perror("custom havoc: maybe_grow");
      return 0;

    }

    **out_buf = rand() % 256;
    buf_size = 1;

  } else {

    // We reuse buf here. It's legal and faster.
    *out_buf = buf;

  }

  size_t victim = rand() % buf_size;
  (*out_buf)[victim] += rand() % 10;

  return buf_size;

}

/**
 * Return the probability (in percentage) that afl_custom_havoc_mutation
 * is called in havoc. By default it is 6 %.
 *
 * (Optional)
 *
 * @param[in] data pointer returned in afl_custom_init for this fuzz case
 * @return The probability (0-100).
 */
uint8_t afl_custom_havoc_mutation_probability(my_mutator_t *data) {

  return 5;  // 5 %

}

/**
 * Determine whether the fuzzer should fuzz the queue entry or not.
 *
 * (Optional)
 *
 * @param[in] data pointer returned in afl_custom_init for this fuzz case
 * @param filename File name of the test case in the queue entry
 * @return Return True(1) if the fuzzer will fuzz the queue entry, and
 *     False(0) otherwise.
 */
uint8_t afl_custom_queue_get(my_mutator_t *data, const uint8_t *filename) {

  return 1;

}

/**
 * Allow for additional analysis (e.g. calling a different tool that does a
 * different kind of coverage and saves this for the custom mutator).
 *
 * (Optional)
 *
 * @param data pointer returned in afl_custom_init for this fuzz case
 * @param filename_new_queue File name of the new queue entry
 * @param filename_orig_queue File name of the original queue entry
 * @return if the file contents was modified return 1 (True), 0 (False)
 *         otherwise
 */
uint8_t afl_custom_queue_new_entry(my_mutator_t  *data,
                                   const uint8_t *filename_new_queue,
                                   const uint8_t *filename_orig_queue) {

  return 0;

}

/**
 * Deinitialize everything
 *
 * @param data The data ptr from afl_custom_init
 */
void afl_custom_deinit(my_mutator_t *data) {

  free(data->post_process_buf);
  free(data->havoc_buf);
  free(data->data_buf);
  free(data->fuzz_buf);
  free(data->trim_buf);
  free(data);

}



/**
 * Perform custom mutations on a given input
 *
 * (Optional for now. Required in the future)
 *
 * @param[in] data pointer returned in afl_custom_init for this fuzz case
 * @param[in] buf Pointer to input data to be mutated
 * @param[in] buf_size Size of input data
 * @param[out] out_buf the buffer we will work on. we can reuse *buf. NULL on
 * error.
 * @param[in] add_buf Buffer containing the additional test case
 * @param[in] add_buf_size Size of the additional test case
 * @param[in] max_size Maximum size of the mutated output. The mutation must not
 *     produce data larger than max_size.
 * @return Size of the mutated output.
 */
size_t afl_custom_fuzz(my_mutator_t *data, uint8_t *buf, size_t buf_size,
                       u8 **out_buf, uint8_t *add_buf,
                       size_t add_buf_size,  // add_buf can be NULL
                       size_t max_size) {

  // maybe_grow is optimized to be quick for reused buffers.
  u8 * mutated_out = maybe_grow(BUF_PARAMS(data, fuzz), buf_size);
  if (!mutated_out) {

    * out_buf = NULL;
    perror("custom mutator allocation (maybe_grow)");
    return 0; /* afl-fuzz will very likely error out after this. */

  }
  memcpy(mutated_out, buf, buf_size);
  u64 exec_cksum;
  if (unlikely(get_exec_checksum(data -> afl, buf, buf_size, & exec_cksum))) {
    perror("error in get_exec_checksum\n");
  }

  data -> constraints[0].h = malloc(sizeof(Boxconstraint));
  data -> constraints[0].h -> size = buf_size;
  data -> constraints[0].h -> interval = malloc(sizeof(Interval) * (data -> constraints[0].h -> size + 1));
  data -> constraints[1].h = malloc(sizeof(Boxconstraint));
  data -> constraints[1].h -> size = buf_size;
  data -> constraints[1].h -> interval = malloc(sizeof(Interval) * (data -> constraints[1].h -> size + 1));
  data -> constraints[2].h = malloc(sizeof(Boxconstraint));
  data -> constraints[2].h -> size = buf_size;
  data -> constraints[2].h -> interval = malloc(sizeof(Interval) * (data -> constraints[1].h -> size + 1));

  assert(buf_size <= 1024 * 1024);
  double target_rate = 0.5;
  if (getenv("HITRATE")) {
    target_rate = (double) 1.0 / atoll(getenv("HITRATE"));
  }
  double * step = (double * ) malloc(1024 * 1024 * sizeof(double));
  double * old_step = (double * ) malloc(1024 * 1024 * sizeof(double));
  DimensionCount * counts = (DimensionCount * ) malloc(1024 * 1024 * sizeof(DimensionCount));
  for (int i = 0; i < 1024 * 1024; i++) {
    step[i] = 0.0;
    old_step[i] = 0.0;
    counts[i].dimension = i;
    counts[i].count = 0;
  }
  for (int idx = 0; idx < buf_size; ++idx) {
    data -> constraints[0].h -> interval[idx].low = buf[idx];
    data -> constraints[0].h -> interval[idx].high = buf[idx];
  }
  fprintf(stderr, "exec cnt: %ld\n", executions);
  uint64_t coordinate_idx = rand() % buf_size;
  int iteration = 0;
  double best_error = 1.0;
  uint64_t NUMTRIALS = 10;
  double EPS = 0.05;
  if (getenv("NUMTRIALS")) {
    NUMTRIALS = atoll(getenv("NUMTRIALS"));
  }
  if (getenv("EPS")) {
    EPS = (double) 1.0 / atoll(getenv("EPS"));
  }
  while (1) {
    iteration += 1;
    for (int idx = 0; idx < buf_size; ++idx) {
      int64_t low = data -> constraints[0].h -> interval[idx].low;
      int64_t high = data -> constraints[0].h -> interval[idx].high;
      if (low <= 0) {
        low = 0;
      }
      if (high >= 255) {
        high = 255;
      }
      assert(low <= 255 && low >= 0);
      assert(high <= 255 && high >= 0);
      data -> constraints[0].h -> interval[idx].low = (u8) low;
      data -> constraints[0].h -> interval[idx].high = (u8) high;
    }
    uint64_t trials = NUMTRIALS;
    uint64_t success = montecarlo_count(data -> constraints[0].h, trials, data, buf, buf_size, exec_cksum);

    double rate = (double) success / trials;
    double error = fabs(target_rate - rate);
    double eps = EPS;
    if (error <= eps) {

      fprintf(stderr, "terminated at iteration %d!\n", iteration);
      break;
    }
    if (iteration > 100) {

      fprintf(stderr, "maxed out iterations at iteration %d!\n", iteration);
      memcpy(data -> constraints[0].h -> interval, data -> constraints[2].h -> interval, sizeof(Interval) * (data -> constraints[1].h -> size + 1));
      break;
    }
    fprintf(stderr, "Coordinate descent on idx %d, dim %d\n", coordinate_idx, counts[coordinate_idx].dimension);
    memcpy(data -> constraints[1].h -> interval, data -> constraints[0].h -> interval, sizeof(Interval) * (data -> constraints[1].h -> size + 1));
    int64_t low = data -> constraints[0].h -> interval[counts[coordinate_idx].dimension].low - 1;
    int64_t high = data -> constraints[0].h -> interval[counts[coordinate_idx].dimension].high + 1;
    if (low <= 0) {
      low = 0;
    }
    if (high >= 255) {
      high = 255;
    }
    assert(low <= 255 && low >= 0);
    assert(high <= 255 && high >= 0);
    data -> constraints[0].h -> interval[counts[coordinate_idx].dimension].low = (u8) low;
    data -> constraints[0].h -> interval[counts[coordinate_idx].dimension].high = (u8) high;
    uint64_t local_trials = NUMTRIALS;
    uint64_t local_success = montecarlo_count(data -> constraints[0].h, trials, data, buf, buf_size, exec_cksum);
    double local_rate = (double) local_success / local_trials;
    double local_error = fabs(target_rate - local_rate);
    memcpy(data -> constraints[0].h -> interval, data -> constraints[1].h -> interval, sizeof(Interval) * (data -> constraints[1].h -> size + 1));

    int maxed_out = 0;
    if (local_error <= error + eps) {
      if (data -> constraints[0].h -> interval[counts[coordinate_idx].dimension].low > 0) {
        data -> constraints[0].h -> interval[counts[coordinate_idx].dimension].low -= 1;
      }
      if (data -> constraints[0].h -> interval[counts[coordinate_idx].dimension].high < 255) {
        data -> constraints[0].h -> interval[counts[coordinate_idx].dimension].high += 1;
      }
      if (local_error < best_error) {
        best_error = local_error;
        memcpy(data -> constraints[2].h -> interval, data -> constraints[0].h -> interval, sizeof(Interval) * (data -> constraints[1].h -> size + 1));
      }
    }
    coordinate_idx = rand() % buf_size;

  }
  print_boxconstraint(data -> constraints[0].h);
  Boxconstraint * h = data -> constraints[0].h;
  uint64_t success = 0;
  uint64_t trials = 100;
  for (uint64_t i = 0; i < trials; i++) {
    for (uint64_t i = 0; i < h -> size; i++) {
      buf[i] = rand() % (h -> interval[i].high - h -> interval[i].low + 1) +
        h -> interval[i].low;
    }
    u64 cksum = 0;
    if (unlikely(get_exec_checksum(data -> afl, buf, buf_size, & cksum))) {
      perror("error in get_exec_checksum\n");
    }
    if (cksum == exec_cksum) {
      success += 1;
    }
  }
  fprintf(stderr, "total exec cnt: %ld\n", executions);
  FATAL("\nSUCCESS %ld/%ld\n", success, trials);
  exit(0);

  * out_buf = mutated_out;
  return buf_size;

}
}

