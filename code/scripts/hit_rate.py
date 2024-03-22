import pickle
import time
import tempfile
import math
import pandas as pd
import sys
import traceback
import logging
import coloredlogs
import subprocess
import collections
import glob
import os
import numpy as np
np.random.seed(17)

newtups = [
    ('PNG001', 'libpng', 'libpng_read_fuzzer'), # libpng_read_fuzzer
    ('PNG003', 'libpng', 'libpng_read_fuzzer'),
    ('PNG006', 'libpng', 'libpng_read_fuzzer'),
    ('PNG007', 'libpng', 'libpng_read_fuzzer'),
    ('SND024', 'libsndfile', 'sndfile_fuzzer'), # sndfile_fuzzer
    ('SND007', 'libsndfile', 'sndfile_fuzzer'),
    ('SND006', 'libsndfile', 'sndfile_fuzzer'),
    ('SND005', 'libsndfile', 'sndfile_fuzzer'),
    ('SND017', 'libsndfile', 'sndfile_fuzzer'),
    ('SND020', 'libsndfile', 'sndfile_fuzzer'),
    ('XML001', 'libxml2', 'libxml2_xml_read_memory_fuzzer'),# libxml2_read_memory_fuzzer
    ('XML003', 'libxml2', 'libxml2_xml_read_memory_fuzzer'),
    ('XML009', 'libxml2', 'libxml2_xml_read_memory_fuzzer'),
    ('XML017', 'libxml2', 'libxml2_xml_read_memory_fuzzer'),
    ('SSL001', 'openssl', 'asn1'), # asn1
    ('SSL002', 'openssl', 'server'), # server
    ('SSL003', 'openssl', 'asn1'), # asn1
    ('SSL009', 'openssl', 'x509'), # x509
    ('SSL020', 'openssl', 'server'), # server
    ('TIF001', 'libtiff', 'tiff_read_rgba_fuzzer'), # tiff_read_rgba_fuzzer
    ('TIF002', 'libtiff', 'tiff_read_rgba_fuzzer'), # tiff_read_rgba_fuzzer
    ('TIF005', 'libtiff', 'tiffcp'), # tiffcp
    ('TIF006', 'libtiff', 'tiffcp'),
    ('TIF007', 'libtiff', 'tiffcp'),
    ('TIF009', 'libtiff', 'tiffcp'),
    ('TIF012', 'libtiff', 'tiffcp'),
    ('TIF014', 'libtiff', 'tiffcp'),
    ('PDF009', 'poppler', 'pdf_fuzzer'), # pdf_fuzzer
    ('PDF012', 'poppler', 'pdf_fuzzer'), # pdf_fuzzer
    ('PDF019', 'poppler', 'pdf_fuzzer'), # pdf_fuzzer
    ('SQL002', 'sqlite3', 'sqlite3_fuzz'), # sqlite_fuzz
    ('SQL018', 'sqlite3', 'sqlite3_fuzz'),  
    ('SND001', 'libsndfile', 'sndfile_fuzzer'),
    ('PDF001', 'poppler', 'pdf_fuzzer'), # pdf_fuzzer
    ('PDF003', 'poppler', 'pdfimages'), # pdfimages
    ('PDF008', 'poppler', 'pdfimages'), # pdfimages
    ('PDF010', 'poppler', 'pdf_fuzzer'), # pdf_fuzzer
    ('PDF011', 'poppler', 'pdfimages'), # pdfimages
    ('PDF016', 'poppler', 'pdf_fuzzer'), # pdf_fuzzer
    ('PDF018', 'poppler', 'pdftoppm'), # pdftoppm
    ('PDF021', 'poppler', 'pdf_fuzzer'), # pdf_fuzzer
]
    
df = pd.read_csv(sys.argv[1])
log_csv = 'hit_rate.csv'

subprocess.run("mkdir -p exps", shell=True)
subprocess.run("mkdir -p bad_inputs", shell=True)
total = 0
cnt = 0
logger = logging.getLogger("top")
coloredlogs.install(level='DEBUG', fmt='%(asctime)s %(name)s %(pathname)s:%(lineno)d %(levelname)s %(message)s', logger=logger)
states = []
for tup in newtups:
    unpatched_program = 'magmaclean/magma/unpatched/%s_repo/afl/%s' % (tup[1], tup[-1])
    patched_program = 'magmaclean/magma/singlepatched/%s_repo/afl/%s' % (tup[0].lower(), tup[-1])
    f = 'pocs/%s' % (tup[0].lower())
    prog = tup[-1]
    total += 1
    if 1:
        try:
            if f not in df['f'].unique():
                continue
            assert len(df[df['f'] == f]) == 1
            p1, p2, input_file = unpatched_program, patched_program, f
            assert os.path.exists(p1)
            assert os.path.exists(p2)
            assert os.path.exists(input_file)
            start_time = time.time()
            hs = []
            hit_rates = []
            crashes=[]
            num_inputs = []
            num_unique_inputs = []
            times = []
            if 1:
                for p in [p1, p2]:
                    if p == p1:
                        pickled_file = df[df['f'] == f]['p1_pickled_inputs_f'].unique()[0]
                        if df[df['f'] == f]['p1_formula_vars'].unique()[0] <= 0:
                            crashes.append(-1.0)
                            hit_rates.append(-1.0)
                            num_inputs.append(-1.0)
                            num_unique_inputs.append(-1.0)
                            logger.info("skipping %s", p)
                            continue
                    else:
                        pickled_file = df[df['f'] == f]['p2_pickled_inputs_f'].unique()[0]
                        if df[df['f'] == f]['p2_formula_vars'].unique()[0] <= 0:
                            crashes.append(-1.0)
                            hit_rates.append(-1.0)
                            num_inputs.append(-1.0)
                            num_unique_inputs.append(-1.0)
                            logger.info("skipping %s", p)
                            continue
                    logger.info("Using file %s", pickled_file)
                    with open(pickled_file.split('src/')[-1], 'rb') as handle:
                        xs, _ = pickle.load(handle)
                    subprocess.run("rm -rf exps/diff_inputs", shell=True)
                    subprocess.run("mkdir -p exps/diff_inputs", shell=True)
                    num_inputs.append(len(xs))
                    num_unique_inputs.append(len(set([tuple(x) for x in xs])))

                    for x in xs:
                        with tempfile.NamedTemporaryFile(delete=False, dir='exps/diff_inputs', suffix='.input') as tmp:
                            with open(tmp.name, "wb") as f1:
                                f1.write(bytearray(x))
                            if 0:
                                if p == p1:
                                    if prog == 'tiffcp':
                                        logger.warning("%s -M %s tmp.out", p, tmp.name )
                                        logger.warning("%s -M %s tmp.out", p, f)
                                    elif prog == 'xmllint':
                                        logger.warning("%s --valid --oldxml10 --push --memory %s", p, tmp.name )
                                        logger.warning("%s --valid --oldxml10 --push --memory %s", p, f)
                                    elif prog == 'pdfimages':
                                        logger.warning("%s %s /tmp/end", p, tmp.name )
                                        logger.warning("%s %s /tmp/end", p, f)
                                    elif prog == 'pdftoppm':
                                        logger.warning("%s -mono -cropbox %s", p, tmp.name )
                                        logger.warning("%s -mono -cropbox %s", p, f)
                                    else:
                                        logger.warning("%s %s", p, tmp.name )
                                        logger.warning("%s %s", p, f)
                                    assert (os.path.getsize(f) == os.path.getsize(tmp.name))
                                    import ipdb; ipdb.set_trace()
                                    break
                    subprocess.run("rm -rf exps/inputs%s exps/output_poisson%s" % (prog, prog), shell=True)
                    subprocess.run("mkdir -p exps/inputs%s exps/output_poisson%s" % (prog, prog), shell=True)
                    subprocess.run("cp %s exps/inputs%s/" % (input_file, prog), shell=True)

                    if prog == 'tiffcp':
                        cmd = ['AFLplusplus-4.05c/afl-fuzz', '-i', 'exps/inputs%s/' % (prog), '-o', 'exps/output_poisson%s' % (prog), p, '-M', '@@', 'tmp.out']
                    elif prog == 'xmllint':
                        cmd = ['AFLplusplus-4.05c/afl-fuzz', '-i', 'exps/inputs%s/' % (prog), '-o', 'exps/output_poisson%s' % (prog), p, '--valid', '--oldxml10', '--push', '--memory', '@@']
                    elif prog == 'pdfimages':
                        cmd = ['AFLplusplus-4.05c/afl-fuzz', '-i', 'exps/inputs%s/' % (prog), '-o', 'exps/output_poisson%s' % (prog), p, '@@', '/tmp/end']
                    elif prog == 'pdftoppm':
                        cmd = ['AFLplusplus-4.05c/afl-fuzz', '-i', 'exps/inputs%s/' % (prog), '-o', 'exps/output_poisson%s' % (prog), p, '-mono', '-cropbox', '@@']
                    else:
                        cmd = ['AFLplusplus-4.05c/afl-fuzz', '-i', 'exps/inputs%s/' % (prog), '-o', 'exps/output_poisson%s' % (prog), p, '@@']


                    env = os.environ.copy()
                    string = ''
                    lst = ['AFL_NO_UI', 'AFL_NO_AUTODICT', 'AFL_DISABLE_TRIM', 'AFL_CUSTOM_MUTATOR_LIBRARY', 'AFL_CUSTOM_MUTATOR_ONLY', 'DIRECTORY']
                    if prog == 'pdfimages' or prog == 'pdftoppm':
                        lst.append('AFL_DRIVER_DONT_DEFER')
                    for i in lst:
                        if i == 'AFL_CUSTOM_MUTATOR_LIBRARY':
                            val = 'AFLplusplus-4.05c/custom_mutators/examples/libpoissonmutator.so'
                        elif i == 'DIRECTORY':
                            val = 'exps/diff_inputs'
                        else:
                            val = '1'
                        env[i] = val
                        string += "%s=%s " % (i, env[i])


                    string += 'gdb --args ' + ' '.join(cmd)
                    logger.info("Running %s %s %s", p1, p2, input_file)
                    logger.info("Running %s", string)

                    res = subprocess.run(cmd, stdout=subprocess.PIPE, env=env, stderr=subprocess.PIPE, check=False)
                    stdout = res.stdout.decode('utf-8')
                    stderr = res.stderr.decode('utf-8')
                    print(stderr)
                    my_df = pd.read_csv("exps/diff_inputs/results.csv")
                    hit_rates.append(len(my_df[my_df.match == 1])/len(my_df))
                    crashes.append(len(my_df[my_df.crash==1]))
                    my_df.to_csv("%s_test.csv" % (input_file))
            states.append({'p1_hit_rate': hit_rates[0], 'p2_hit_rate': hit_rates[1], 'p1_inputs': num_inputs[0], 'p1_uniq_inputs': num_unique_inputs[0], 'p1_crashes': crashes[0], 'p2_crashes': crashes[1],
                'p2_inputs': num_inputs[1], 'p2_uniq_inputs': num_unique_inputs[1],
                'p1_unpatched': p1, 'p2_patched': p2, 'f': input_file, 'time': int(time.time()-start_time)})
            pd.DataFrame(states).to_csv(log_csv)
            cnt += 1

        except:
            import ipdb; ipdb.set_trace()
            logger.fatal("%s", traceback.format_exc())
            logger.fatal("[-] FAILURE %s %s %s %s", tup, p1, p2, input_file)

logger.fatal(" count %d total %d, len(tups): %d", cnt,  total, len(newtups))
