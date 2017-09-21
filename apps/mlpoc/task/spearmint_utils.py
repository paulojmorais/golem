# based on braninpy from https://github.com/JasperSnoek/spearmint/blob/master/spearmint-lite/braninpy/braninrunner.py  # noqa

import json
import math
import os
import shutil
from collections import OrderedDict
from typing import Tuple, List, Optional, Dict, Callable

import time

RESULT_FILE = "results.dat"
CONFIG = "config.json"
DEFAULT_EVAL_TIME = 1  # spearmint takes into consideration evalutaion times, but we are not going to bother with that now

UPDATE_PERIOD = 0.1  # when waiting for results from spearmint, loop will wait this much between checking if results arrived

# dirty-state hyperparams configurations
# eg these which were already send to provider, but there is still no answer
dirties = set()


def process_lines(directory: str, f: Callable[[str, str, Tuple[str], str], None]) -> None:
    """
    A helper function to do processing of RESULT_FILE
    :param directory: spearmint_directory
    :param f: function to apply to every line (every tuple) of the file
    :return: None
    """

    with open(os.path.join(directory, RESULT_FILE), 'r') as resfile:
        for line in resfile.readlines():
            values = line.split()
            if len(values) < 3:
                continue
            y = values.pop(0)
            dur = values.pop(0)
            x = tuple(values)
            f(y, dur, x, line)


def run_one_evaluation(directory: str, params: Dict[str, List[str]]) -> None:
    """
    This function is called by MLPOCTask.__update_spearmint_state with new results from provider
    It then simply saves the results to RESULT_FILE file (replaces old line with these hyperparams
    and without score with new one, containing score and DEFAULT_EVAL_TIME
    :param directory: spearmint directory
    :param params: dict of score -> hyperparameters, but since we need the reverse dict, we are reversing it here
    :return: None
    """

    params = {tuple(x for x in v): k for k, v in sorted(params.items())}
    print("Evaluation...")
    newlines = []

    def f(y, dur, x, line):
        if dur == 'P' and tuple(x) in params:
            val = params[tuple(x)]
            newlines.append("{} {} {}\n".format(val, DEFAULT_EVAL_TIME, " ".join(p for p in x)))
        else:
            newlines.append(line)

    process_lines(directory, f)
    with open(os.path.join(directory, RESULT_FILE), 'w') as outfile:
        outfile.writelines(newlines)


def create_conf(directory: str):
    conf = OrderedDict([("HIDDEN_LAYER_SIZE", {"name": "HIDDEN_LAYER_SIZE",
                              "type": "int",
                              "min": 1,
                              "max": 10**5,
                              "size": 1
                              })])
    with open(os.path.join(directory, CONFIG), "w+") as f:
        json.dump(conf, f)


def clean_res(directory):
    global dirties
    dirties = set()
    for f in os.listdir(directory):
        shutil.rmtree(os.path.join(f, directory), ignore_errors=True)


def extract_results(directory: str) -> Tuple[List[str], List[List[str]]]:
    """
    Extracts results from RESULT_FILE, in the form of
    :param directory: spearmint_directory
    :return: [list of results], [list of hyperparameters]
    """
    xs = []
    ys = []

    def f(y, dur, x, _):
        if dur == 'P':
            return
        else:
            xs.append(x)
            ys.append(y)

    process_lines(directory, f)
    return xs, ys


def get_next_configuration(directory: str) -> Optional[List[str]]:
    xs = None

    def f(y, dur, x, _):
        nonlocal xs
        if dur == 'P' and x not in dirties:
            if not xs:
                # we only need to return one new hyperparams configuration
                dirties.add(x)
                xs = x

    process_lines(directory, f)
    return xs

def generate_new_suggestions(file):
    open(file, "w").close()  # create signal file
    while os.path.exists(file):
        time.sleep(UPDATE_PERIOD)