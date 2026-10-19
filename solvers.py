import itertools
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
AMON = ROOT / "lib" / "AMON"
os.environ["AMON_RESULTS_DIR"] = str(ROOT / "results")
os.chdir(AMON)
sys.path.insert(0, str(AMON))

import windfarm_eval


def mc_solver(param, x0, n=10):
    """Monte Carlo : tire n layouts aléatoires, garde le meilleur EAP."""
    eap, *_ = windfarm_eval.windfarm_eval(param, x0)
    best = eap
    for _ in range(n):
        xs = np.random.uniform(52274.51767349267, 53803.380417069864, 30)
        ys = np.random.uniform(521785.03108614404, 522850.77981024975, 30)
        eap, *_ = windfarm_eval.windfarm_eval(param, list(itertools.chain(*zip(xs, ys))))
        if eap > best:
            best = eap
    return best


if __name__ == "__main__":
    print("Best EAP =", mc_solver("bb_example/param.txt", "bb_example/x0_instance.txt"), "GWh")
