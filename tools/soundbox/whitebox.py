import pickle
import z3
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
import pandas as pd
import numpy as np


expression = dict()

def is_linear_expr(expr):
    #if is_bv_var(expr) or is_bv_const(expr):
        #return True
    if z3.is_bv(expr) and len(expr.children()) < 1:
        return True
    # Check if the expression is a multiplication
    elif expr.decl().name() == "*":
        # Check if the left-hand side is a constant
        lhs = expr.arg(0)
        if z3.is_bv_const(lhs):
            return is_linear_expr(expr.arg(1))
        # Check if the right-hand side is a constant
        rhs = expr.arg(1)
        if z3.is_bv_const(rhs):
            return is_linear_expr(expr.arg(0))
    # Check if the expression is an addition or subtraction
    elif expr.decl().name() in ["bvadd", "bvsub"]:
        return all([is_linear_expr(arg) for arg in expr.children()])
    # Check if the expression is a negation
    elif expr.decl().name() == "bvneg":
        return is_linear_expr(expr.arg(0))
    return False


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

tups = newtups

if len(sys.argv) > 1:
    assert int(sys.argv[1]) < len(tups)
    tups = [tups[int(sys.argv[1])]]
    log_file = 'exps_concolic/%s.log' % (tups[0][1])
    log_csv = 'exps_concolic/%s.csv' % (tups[0][1])
else:
    log_file = 'exps_concolic/regional1.log'
    log_csv = 'exps_concolic/regional1.csv'

subprocess.run("mkdir -p exps_concolic", shell=True)

total = 0
cnt = 0
logger = logging.getLogger("top")
coloredlogs.install(level='DEBUG', fmt='%(asctime)s %(name)s %(pathname)s:%(lineno)d %(levelname)s %(message)s', logger=logger)
logging.basicConfig(filename=log_file,
                    filemode='w',
                    format='%(asctime)s %(name)s %(pathname)s:%(lineno)d %(levelname)s %(message)s',
                    level='DEBUG')
logger.info("Running %s tups", tups)
states = []
for tup in tups:
    unpatched_program = 'magma/symcc_analysis_unpatched/%s' % (tup[1])
    patched_program = 'magma/symcc_analysis_patched_%s/%s' % (tup[0].lower(), tup[1])
    f = 'pocs/%s' % (tup[0].lower())
    oracle_unpatched_program = 'magmaclean/magma/unpatched/%s_repo/afl/%s' % (tup[1], tup[-1])
    oracle_patched_program = 'magmaclean/magma/singlepatched/%s_repo/afl/%s' % (tup[0].lower(), tup[-1])
    prog = tup[-1]
    total += 1
    if 1:
        try:
            p1, p2, input_file = unpatched_program, patched_program, f
            start_time = time.time()
            formulasizes = []
            formulavars = []
            formulagentimes = []
            formulas = []
            hit_rates = []
            totaltimes = []
            haslinear = []
            circuit_sizes = []
            circuit_sizes_bds = []
            pickled_inputs_f = []
            formula_f = []
            z3_varcnt = []
            for p in [p1, p2]:
                logger.info("Running %s %s %s", p1, p2, input_file)

                cmd = 'docker run --rm -v $(pwd):/external -e POC=%s -e PROG=%s --entrypoint=/external/runner.sh %s' % (tup[0].lower(), tup[2], p)
                logger.info("Running %s", cmd)

                s = time.time()
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, shell=True)
                stderr = res.stderr.decode('utf-8', errors='ignore')
                formulagentimes.append(int(time.time()-s))
                if "Final input:" in stderr and 'Final formula' in stderr:
                    formula, soln = stderr.split("Now Final formula:")[-1].split("Final input")
                    variables = {}
                    if "Infeasible" in soln:
                        infeasible = 1
                    elif len(soln.strip()) == 0 or len(formula.strip()) == 0:
                        infeasible = 2
                    else:
                        for var in soln.split("\n"):
                            if '->' in var:
                                byte_idx = int(var.split("->")[0].replace("stdin", "").strip())
                                byte_val = int(var.split("->")[1].replace("#", "0").strip(), 16)
                                assert(byte_idx not in variables.keys())
                                variables[byte_idx] = byte_val
                        infeasible = 0

                    if len(formula.strip()):
                        formula_invalid = 0
                        formula_vars = len(variables)
                        res = z3.parse_smt2_string(formula.strip())
                        solver = z3.Solver()
                        solver.add(res)
                        formula_obj = solver.to_smt2()
                        formula_size = len(solver.assertions())
                        try:
                            circuit_size = int(stderr.split('unique')[0].split('total, ')[-1].strip())
                            circuit_size_bd = int(stderr.split('total')[0].split('Final formula:')[-1].strip())
                        except:
                            circuit_size = -1
                            circuit_size_bd = -1
                        has_linear = 0
                        if 1:
                            for item in solver.assertions():
                                if is_linear(item):
                                    has_linear += 1
                                    logger.warning("Linear %s", str(item))
                        if infeasible == 0:
                            rect = None
                            if 1:
                                rect = {}
                                for i in range(2):
                                    for idx, val in variables.items():
                                        o = z3.Optimize()
                                        o.add(res)
                                        if i == 0:
                                            obj = o.maximize(z3.BitVec('stdin%s' % (idx), 8))
                                            o.check()
                                            upper_value = o.upper(obj)
                                            rect[idx] = {'upp': int(str(upper_value)), 'idx': idx, 'origval': val}
                                        else:
                                            obj = o.minimize(z3.BitVec('stdin%s' % (idx), 8))
                                            o.check()
                                            lower_value = o.lower(obj)
                                            rect[idx]['low'] = int(str(lower_value))
                        else:
                            rect = None

                    else:
                        has_linear = 0
                        formula_invalid = 2
                        formula_size = 0
                        circuit_size = 0
                        circuit_size_bd = 0
                        formula_vars = 0
                        rect = None
                        formula_obj = None
                else:
                    infeasible = -1
                    formula_invalid = -1
                    formula_size = -1
                    formula_vars = -1
                    has_linear = -1
                    circuit_size = -1
                    circuit_size_bd = -1
                    formula_obj = None
                    rect = None
                formulasizes.append(formula_size)
                formulavars.append(formula_vars)
                hit_rates.append(infeasible)
                formulas.append(formula_invalid)
                totaltimes.append(int(time.time()-s))
                haslinear.append(has_linear)
                circuit_sizes.append(circuit_size)
                circuit_sizes_bds.append(circuit_size_bd)
            states.append({'p1_path_divergence': hit_rates[0], 'p1_time': totaltimes[0], 'p1_formula_invalid': formulas[0], 'p1_formulagen_time': formulagentimes[0], 'p1_formula_size': formulasizes[0], 'p1_formula_vars': formulavars[0], 'p1_has_linear': haslinear[0], 'p1_pickled_inputs_f': pickled_inputs_f[0], 'p1_formula_f': formula_f[0], 'p1_z3_var_cnt': z3_varcnt[0],'p1_circuit_size_uniq': circuit_sizes[0],'p1_circuit_size_total': circuit_sizes_bds[0],
                'p2_path_divergence': hit_rates[1], 'p2_time': totaltimes[1], 'p2_formula_invalid': formulas[1], 'p2_formulagen_time': formulagentimes[1], 'p2_formula_size': formulasizes[1], 'p2_formula_vars': formulavars[1], 'p2_has_linear': haslinear[1], 'p2_pickled_inputs_f': pickled_inputs_f[1], 'p2_formula_f': formula_f[1], 'p2_z3_var_cnt': z3_varcnt[1],'p2_circuit_size_uniq': circuit_sizes[1],'p2_circuit_size_total': circuit_sizes_bds[1],
                'p1_unpatched': p1, 'p2_patched': p2, 'f': input_file, 'totaltime': int(time.time()-start_time)})
            df = pd.DataFrame(states)
            df.to_csv(log_csv)
            cnt += 1

        except:
            logger.fatal("%s", traceback.format_exc())
            logger.fatal("[-] FAILURE %s %s %s %s", tup, p1, p2, input_file)

logger.fatal(" count %d total %d, len(tups): %d", cnt,  total, len(tups))
