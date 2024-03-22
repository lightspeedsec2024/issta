import pickle
import time
import tempfile
import math
import pandas as pd
import sys
import traceback
import logging
import subprocess
import collections
import glob
import os

newtups = [
    ('PNG001', 'libpng', 'libpng_read_fuzzer'), # libpng_read_fuzzer
    ('PNG003', 'libpng', 'libpng_read_fuzzer'),
    ('PNG006', 'libpng', 'libpng_read_fuzzer'),
    ('PNG007', 'libpng', 'libpng_read_fuzzer'),
    ('PHP004', 'php', 'exif'), # exif
    ('PHP009', 'php', 'exif'),
    ('PHP011', 'php', 'exif'),
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
log_csv = '/external/src/smtsampler.csv'

subprocess.run("mkdir -p exps", shell=True)
subprocess.run("mkdir -p bad_inputs", shell=True)
total = 0
cnt = 0
logging.basicConfig(format='%(asctime)s %(message)s',level=logging.INFO)
logger = logging.getLogger("top")
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
            start_time = time.time()
            hs = []
            hit_rates = []
            dicts1 = []
            data_f = []
            times = []
            if 1:
                for p in [p1, p2]:
                    if p == p1:
                        pickled_file = df[df['f'] == f]['p1_formula_f'].unique()[0]
                        if df[df['f'] == f]['p1_formula_vars'].unique()[0] <= 0:
                            dicts1.append({"Samples": -1, "Valid samples": -1, "Unique valid samples": -1, "Total time":  -1, "Solver time": -1, 'formula_vars': -1, 'myformulavars': -1})
                            hit_rates.append(-1.0)
                            data_f.append('-1.0')
                            logger.info("skipping %s", p)
                            continue
                        var_cnt = df[df['f'] == f]['p1_formula_vars'].unique()[0]
                    else:
                        pickled_file = df[df['f'] == f]['p2_formula_f'].unique()[0]
                        if df[df['f'] == f]['p2_formula_vars'].unique()[0] <= 0:
                            dicts1.append({"Samples": -1, "Valid samples": -1, "Unique valid samples": -1, "Total time":  -1, "Solver time": -1, 'formula_vars': -1, 'myformulavars': -1})
                            data_f.append('-1.0')
                            hit_rates.append(-1.0)
                            logger.info("skipping %s", p)
                            continue
                        var_cnt = df[df['f'] == f]['p2_formula_vars'].unique()[0]
                    cmd = './smtsampler -n 1000 -t 300.0 %s' % (pickled_file.replace("/data/poisson/", "/external/"))
                    logger.info("Running %s", cmd)
                    res = subprocess.run(cmd, stdout=subprocess.PIPE,  stderr=subprocess.PIPE, check=False, shell=True)
                    stdout = res.stdout.decode('utf-8')
                    final_output = stdout.split("Stopping")[-1]
                    if 'Samples' in final_output:
                        dict1={'formula_vars': var_cnt}
                        for line in final_output.split("\n"):
                            if 'Samples' in line:
                                dict1['Samples'] = line.split('Samples')[-1].replace(":", "").strip()
                            elif 'Valid samples' in line:
                                dict1['Valid samples'] = line.split('Valid samples')[-1].replace(":", "").strip()
                            elif 'Unique valid samples' in line:
                                dict1['Unique valid samples'] = line.split('Unique valid samples')[-1].replace(":", "").strip()
                            elif 'Total time' in line:
                                dict1['Total time'] = line.split('Total time')[-1].replace(":", "").strip()
                            elif 'Solver time' in line:
                                dict1['Solver time'] = line.split('Solver time')[-1].replace(":", "").strip()
                            else:
                                continue
                        dicts1.append(dict1.copy())
                    else:
                        dicts1.append({"Samples": -2, "Valid samples": -2, "Unique valid samples": -2, "Total time":  -2, "Solver time": -2, 'formula_vars': -1, 'myformulavars': -1})
                    stderr = res.stderr.decode('utf-8')
                    if 'begin' in stderr:
                        xs = []
                        for inp in stderr.split("------------ begin ---------")[1:]:
                            var = [(elem.split('()')[0].strip(), int(elem.split('#x')[-1].split(')')[0], 16)) for elem in inp.split('define-fun ')[1:]]
                            dict2 = {}
                            for item in var:
                                dict2[int(item[0].replace("stdin",  ""))] = item[1]
                            dicts1[-1]['myformulavars'] = len(dict2)
                            x = [ 10 if i not in dict2 else dict2[i] for i in range(os.path.getsize('/external/src/' + f))]
                            xs.append(x)

                        with tempfile.NamedTemporaryFile(delete=False, dir='/external/src/exps_concolic', suffix='.%s.%s.smtsampler.pickle' % (p.replace("/","_"), f.replace("/", "_"))) as tmp:
                            pickle.dump((xs, None), tmp, protocol=pickle.HIGHEST_PROTOCOL)
                            data_f.append(tmp.name)
                    else:
                        dicts1[-1]['myformulavars'] = -1
                        data_f.append('invalid')

            state = {'p1_unpatched': p1, 'p2_patched': p2, 'f': input_file, 
                    'time': int(time.time()-start_time), 'p1_pickled_inputs_f': data_f[0], 'p2_pickled_inputs_f': data_f[1]
                    }
            for item in dicts1[0]:
                state['p1_'+item.replace(" ", "_").lower()] = dicts1[0][item]
            for item in dicts1[1]:
                state['p2_'+item.replace(" ", "_").lower()] = dicts1[1][item]
            states.append(state)
            print(pd.DataFrame(states))
            pd.DataFrame(states).to_csv(log_csv)
            cnt += 1

        except:
            import pdb; pdb.set_trace()
            logger.fatal("%s", traceback.format_exc())
            logger.fatal("[-] FAILURE %s %s %s %s", tup, p1, p2, input_file)

logger.fatal(" count %d total %d, len(tups): %d", cnt,  total, len(newtups))
