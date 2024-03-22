import random
import polytope
from dingo import PolytopeSampler
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
    ('SND024', 'libsndfile', 'sndfile_fuzzer'), # sndfile_fuzzer
    ('SND007', 'libsndfile', 'sndfile_fuzzer'),
    ('SND006', 'libsndfile', 'sndfile_fuzzer'),
    ('SND005', 'libsndfile', 'sndfile_fuzzer'),
    ('SND017', 'libsndfile', 'sndfile_fuzzer'),
    ('SND020', 'libsndfile', 'sndfile_fuzzer'),
    ('XML001', 'libxml2', 'libxml2_xml_read_memory_fuzzer'),# libxml2_read_memory_fuzzer
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
    ('SND001', 'libsndfile', 'sndfile_fuzzer'),
    ('PDF001', 'poppler', 'pdf_fuzzer'), # pdf_fuzzer
    ('PDF003', 'poppler', 'pdfimages'), # pdfimages
    ('PDF008', 'poppler', 'pdfimages'), # pdfimages
    ('PDF010', 'poppler', 'pdf_fuzzer'), # pdf_fuzzer
    ('PDF011', 'poppler', 'pdfimages'), # pdfimages
    ('PDF016', 'poppler', 'pdf_fuzzer'), # pdf_fuzzer
    ('PDF018', 'poppler', 'pdftoppm'), # pdftoppm
    ('PDF021', 'poppler', 'pdf_fuzzer'), # pdf_fuzzer
    ('XML003', 'libxml2', 'libxml2_xml_read_memory_fuzzer'), 
    ('SQL018', 'sqlite3', 'sqlite3_fuzz'),  
]
    
df = pd.read_csv(sys.argv[1])
log_csv = '/external/src/polytopesampler.csv'

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
                print('Skipping', f)
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
                        pickled_file = df[df['f'] == f]['p1_pickled_inputs_f'].unique()[0]
                        if df[df['f'] == f]['p1_formula_vars'].unique()[0] <= 0:
                            dicts1.append({"Total time":  -1, 'formula_vars': -1, 'polytope_size': -1})
                            hit_rates.append(-1.0)
                            data_f.append('-1.0')
                            logger.info("skipping %s", p)
                            continue
                        var_cnt = df[df['f'] == f]['p1_formula_vars'].unique()[0]
                    else:
                        pickled_file = df[df['f'] == f]['p2_pickled_inputs_f'].unique()[0]
                        if df[df['f'] == f]['p2_formula_vars'].unique()[0] <= 0:
                            dicts1.append({"Total time":  -1, 'formula_vars': -1, 'polytope_size': -1})
                            data_f.append('-1.0')
                            hit_rates.append(-1.0)
                            logger.info("skipping %s", p)
                            continue
                        var_cnt = df[df['f'] == f]['p2_formula_vars'].unique()[0]

                    dict1 = {'formula_vars': var_cnt}
                    with open('/external/src/'+pickled_file.split('src/')[-1], 'rb') as handle:
                        _, rect = pickle.load(handle)
                    if 0:
                        sides = [ [0, 255] if i not in rect else [rect[i]['low'], rect[i]['upp']] for i in range(os.path.getsize('/external/src/' + f))]
                        dict1['polytope_size'] = len(rect)
                    else:
                        idxtobyte = [ i for i in sorted(list(rect.keys())) if rect[i]['low'] != rect[i]['upp'] ]
                        dict1['polytope_size'] = len(idxtobyte)
                        sides = [ [rect[i]['low'], rect[i]['upp']] for i in idxtobyte ]
                    if len(sides) == 0:
                        for m in ['billiard_walk', 'cdhr', 'rdhr', 'ball_walk', 'dikin_walk', 'john_walk', 'vaidya_walk']:
                            dict1['Total time'+m] = -1
                        dict1['Total time'] = -1
                    else:
                        poly = polytope.box2poly(sides)
                        A = poly.A
                        b = poly.b

                        logger.info("Sampling  %s %s", p, f)
                        for m in ['billiard_walk', 'cdhr', 'rdhr', 'ball_walk', 'dikin_walk', 'john_walk', 'vaidya_walk']:
                            s1 = time.time()
                            print("starting", m)
                            # from https://github.com/GeomScale/dingo/blob/d9bdef9507849edd863763ca854d8d35ad3f0dc8/tests/rounding.py#L44
                            res = PolytopeSampler.sample_from_polytope_no_multiphase(A, b, n=1000, burn_in=10, method=m)
                            dict1['Total time'+m] = time.time() - s1
                            print(dict1)

                        s1 = time.time()
                        res = PolytopeSampler.sample_from_polytope_no_multiphase(A, b, burn_in=10, n=1000)# method='dikin_walk')
                        dict1['Total time'] = time.time() - s1
                    xs = []
                    for r in res:
                        if 0:
                            xs.append([int(ele) for ele in r])
                        else:
                            x = []
                            for i in range(os.path.getsize('/external/src/' + f)):
                                if i in rect:
                                    if rect[i]['low'] == rect[i]['upp']:
                                        x.append(rect[i]['low'])
                                    else:
                                        if 0:
                                            bytetoidx = idxtobyte.index(i)
                                            x.append(int(r[bytetoidx]))
                                        else:
                                            bytetoidx = idxtobyte.index(i)
                                            val = r[bytetoidx]
                                            bias = abs(val-int(val))
                                            if random.random() < bias:
                                                roundedval = int(val) + 1
                                            else:
                                                roundedval = int(val)
                                            x.append(roundedval)
                                else:
                                    x.append(10)
                            xs.append(x)

                    dicts1.append(dict1)
                    with tempfile.NamedTemporaryFile(delete=False, dir='/external/src/exps_concolic', suffix='.%s.%s.polytopesampler.pickle' % (p.replace("/","_"), f.replace("/", "_"))) as tmp:
                        pickle.dump((xs, None), tmp, protocol=pickle.HIGHEST_PROTOCOL)
                        data_f.append(tmp.name)

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
            import ipdb; ipdb.set_trace()
            logger.fatal("%s", traceback.format_exc())
            logger.fatal("[-] FAILURE %s %s %s %s", tup, p1, p2, input_file)

logger.fatal(" count %d total %d, len(tups): %d", cnt,  total, len(newtups))
