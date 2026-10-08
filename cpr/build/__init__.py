"""Build a PR in a sandbox, run selected unit tests with JaCoCo, and save status.json.

`cpr build <N>` writes `<work>/build-runs/<N>/<head>/status.json`; `cpr review` only reads it.
"""

import json
import os

CONFIG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "build.json")


def load_config(path=CONFIG):
    with open(path) as f:
        return json.load(f)


def runs_dir(work_dir, number):
    return os.path.join(work_dir, "build-runs", str(number))


def run_dir(work_dir, number, head):
    return os.path.join(runs_dir(work_dir, number), head)
