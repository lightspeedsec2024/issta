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
from pathlib import Path
from typing import Union, List
import json

import z3

PathLike = Union[Path, str]

class CNFFormula:
    """
    Class the represent a CNF formula in DIMACS format.
    It can either be populated by a CNF file or by an SMT2
    file. In this later case Z3 is used to parse the file
    and to extract the CNF representation.
    """
    def __init__(self):
        """
        Class construction. A formula is meant to be instanciated
        via the static methods from_z3, from_smt2_file, from_dimacs_string
        and from_dimacs_file.
        """
        self.goal = z3.Goal()
        self.tactics = z3.Then('simplify', 'bit-blast', 'tseitin-cnf')
        self.subgoal = None  # keep it in case of
        # Goal is a collection of constraints we want to find a solution or show to be unsatisfiable (infeasible).
        # Goals are processed using Tactics. A Tactic transforms a goal into a set of subgoals.
        # A goal has a solution if one of its subgoals has a solution.
        # A goal is unsatisfiable if all subgoals are unsatisfiable.

        self.variables_num = None
        self.clauses_num = None
        self.clauses = []

    def _apply_tactics(self) -> None:
        """
        Apply the Z3 tactics to generate the goals.

        :return: None
        """
        self.subgoal = self.tactics(self.goal)
        if len(self.subgoal) > 1:
            print("warning: multiple subgoal for the formula")

    @staticmethod
    def from_z3(smt_formula) -> 'CNFFormula':
        """
        Convert a Z3 expression to a CNF formula.

        :param smt_formula: Z3 expression (all types that can be fed to a Goal instance)
        :return: a CNF Formula instance
        """
        f = CNFFormula()
        f.goal.add(smt_formula)
        f._apply_tactics()
        f._fill_from_dimacs_string(f.subgoal[0].dimacs())
        return f

    @staticmethod
    def from_smt2_file(smt_file: PathLike) -> 'CNFFormula':
        """"
        Load a CNFFormula from an SMT2 file. It uses Z3 to parse
        the SMT2 and to apply the different tactics generating the
        goals in CNF.

        :param smt_file: SMT2 file
        :return: a CNF Formula instance
        """
        p = Path(smt_file)
        if not p.exists():
            raise FileNotFoundError('SMT2 file not found: {}'.format(p))
        x = z3.parse_smt2_file(p.as_posix())
        return CNFFormula.from_z3(x)

    def _fill_from_dimacs_string(self, s: str) -> None:
        """
        Parse the CNF file as a string and fill the
        appropriate attributes of the object.

        :param s: CNF file string
        :return: None
        """
        lines = [x for x in s.split("\n") if x]
        for i in range(len(lines)):
            l = lines[i]
            if l[0] == "c":  # comment
                pass
            elif l[0] == "p":  # problem line
                p, cnf, var_num, clause_num = l.split(" ")
                self.variables_num, self.clauses_num = var_num, clause_num
                if cnf != "cnf":
                    raise Exception("Problem line FORMAT should be 'cnf'")
            else:
                # This parsing force each clause to be on a different line
                terms = l.split(" ")
                if terms[-1] != "0":
                    if i != (len(lines)-1):
                        raise Exception("DIMACS clause expected to end by '0'")
                    else:
                        terms = [int(x) for x in terms]
                else:
                    terms = [int(x) for x in terms[:-1]]
                self.clauses.append([int(x) for x in terms])

    @staticmethod
    def from_dimacs_string(s: str) -> 'CNFFormula':
        """
        Create a CNFFormula instance from the given
        string which represent a DIMACS file.s

        :param s: DIMACS file as a string
        :return: a CNFFormula instance
        """
        f = CNFFormula()
        f._fill_from_dimacs_string(s)
        return f

    @staticmethod
    def from_dimacs_file(in_file: PathLike) -> 'CNFFormula':
        """
        Create a CNF Formula from a dimacs file.

        :param in_file: input DIMACS file
        :return: a CNFFormula instance
        """
        p = Path(in_file)
        if not p.exists():
            raise FileNotFoundError("DIMACS file {} not found".format(p))
        return CNFFormula.from_dimacs_string(p.read_text())

    @staticmethod
    def __int_clauses_to_z3(clauses: List[List[int]]) -> z3.z3.BoolRef:
        z3_clauses = []
        vars = {}
        for clause in clauses:
            conds = []
            for t in clause:
                a = abs(t)
                if a in vars:
                    b = vars[a]
                else:
                    b = z3.Bool("k!{}".format(a))
                    vars[a] = b
                b = z3.Not(b) if t < 0 else b
                conds.append(b)
            z3_clauses.append(z3.Or(*conds))
        return z3.And(*z3_clauses)

    def to_graph_file(self, output_file: PathLike, with_layout=False, dim=2, iter=50) -> None:
        """
        Convert the formula to a graph representation (using networkx) and
        export it as JSON.

        :param output_file: JSON output file
        :param with_layout: if True compute the layout
        :param dim: dimension of the layout (2 or 3)
        :param iter: number of iteration for the layout computation
        :return: None
        """
        g = self.to_networkx(with_layout, dim, iter)
        json_data = networkx.readwrite.json_graph.node_link_data(g)
        with open(output_file, "w") as f:
            json.dump(json_data, f)

    def to_dimacs_file(self, output_file: PathLike) -> None:
        """
        Write the CNFFormula to a DIMACS file. If it was instanciated
        from z3 just call .dimacs() otherwise dump all the clauses.

        :param output_file: DIMACS output file
        :return: None
        """
        with open(output_file, "w") as f:
            if self.subgoal:
                f.write(self.subgoal[0].dimacs())
            else:
                f.write("p cnf {} {}\n".format(self.variables_num, self.clauses_num))
                for c in self.clauses:
                    f.write("{} 0\n".format(" ".join(str(x) for x in c)))




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
log_csv = 'spur.csv'

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
                            dicts1.append({'smt2sat_time': -1,'formula_bytes': -1, "samples": -1, "num_solutions": -1, "num_vars": -1, "num_clauses":  -1, "time": -1})
                            hit_rates.append(-1.0)
                            data_f.append('-1.0')
                            logger.info("skipping %s", p)
                            continue
                        var_cnt = df[df['f'] == f]['p1_formula_vars'].unique()[0]
                    else:
                        pickled_file = df[df['f'] == f]['p2_formula_f'].unique()[0]
                        if df[df['f'] == f]['p2_formula_vars'].unique()[0] <= 0:
                            dicts1.append({'smt2sat_time': -1,'formula_bytes': -1, "samples": -1, "num_solutions": -1, "num_vars": -1, "num_clauses":  -1, "time": -1})
                            data_f.append('-1.0')
                            hit_rates.append(-1.0)
                            logger.info("skipping %s", p)
                            continue
                        var_cnt = df[df['f'] == f]['p2_formula_vars'].unique()[0]

                    cmd = 'python bitblast1.py %s' % (pickled_file)
                    logger.info("Running %s", cmd)
                    local_time = time.time()
                    res = subprocess.run(cmd, stdout=subprocess.PIPE,  stderr=subprocess.PIPE, check=False, shell=True)
                    dict1={'formula_bytes': os.path.getsize('formula1.cnf'), 'smt2sat_time': time.time()-local_time}
                    if res.returncode != 0:
                        stdout = res.stdout.decode('utf-8')
                        print(stdout)
                        stderr = res.stderr.decode('utf-8')
                        print(stderr)
                        dicts1.append({'smt2sat_time': -3,'formula_bytes': -3, "samples": -3, "num_solutions": -3, "num_vars": -3, "num_clauses":  -3, "time": -3})
                        data_f.append('-1.0')
                        hit_rates.append(-1.0)
                        logger.info("Failure %s", pickled_file)
                        continue
                    
                    cmd = '../spur/build/Release/spur -s 1000 -cnf formula1.cnf -no-sample-write'
                    logger.info("Running %s", cmd)
                    res = subprocess.run(cmd, stdout=subprocess.PIPE,  stderr=subprocess.PIPE, check=False, shell=True)
                    stdout = res.stdout.decode('utf-8')
                    final_output = stdout.split("#START_HEADER")[-1]
                    if 'samples' in final_output:
                        for line in final_output.split("\n"):
                            if 'num_samples' in line:
                                dict1['samples'] = line.split('num_samples,')[-1]
                            elif 'tot_num_models' in line:
                                dict1['num_solutions'] = line.split('tot_num_models,')[-1]
                            elif 'num_vars' in line:
                                dict1['var_cnt'] = line.split('num_vars,')[-1]
                            elif 'num_clauses' in line:
                                dict1['clause_cnt'] = line.split('num_clauses,')[-1]
                            elif 'execution_time' in line:
                                dict1['time'] = line.split('execution_time,')[-1]
                            else:
                                continue
                        dicts1.append(dict1.copy())
                    else:
                        dicts1.append({'smt2sat_time': -2, 'formula_bytes': -2, "samples": -2, "num_solutions": -2, "num_vars": -2, "num_clauses":  -2, "time": -2})
                    data_f.append(-2.0)

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
            logger.fatal("%s", traceback.format_exc())
            logger.fatal("[-] FAILURE %s %s %s %s", tup, p1, p2, input_file)

logger.fatal(" count %d total %d, len(tups): %d", cnt,  total, len(newtups))
