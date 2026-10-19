"""Solvers d'optimisation de layout éolien (blackbox AMON)."""

import itertools
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
AMON = ROOT / "lib" / "AMON"

# Sorties AMON (bb_result.txt, WindRose.png) → <repo>/results/
os.environ["AMON_RESULTS_DIR"] = str(ROOT / "results")

os.chdir(AMON)
sys.path.insert(0, str(AMON))

import windfarm_eval


def resolve_path(path):
    """Résout un chemin fichier : absolu, puis racine du repo, puis `lib/AMON`.

    Ordre de recherche :
    1. chemin absolu (ou déjà existant tel quel) ;
    2. relatif à la racine du projet (`ROOT`, à côté de `solvers.py`) ;
    3. relatif à AMON (`lib/AMON`, chemins style instances / bb_example).

    Args:
        path: Chemin fichier (`str` ou `Path`).

    Returns:
        Chemin absolu (`str`).

    Raises:
        FileNotFoundError: si le fichier n'existe dans aucun des emplacements.
    """
    p = Path(path)
    if p.is_file():
        return str(p.resolve())
    for base in (ROOT, AMON):
        cand = base / p
        if cand.is_file():
            return str(cand.resolve())
    raise FileNotFoundError(
        f"{path!r} introuvable (cherché en absolu, sous {ROOT}, sous {AMON})"
    )


def mc_solver(param, x0, n=10):
    """Baseline Monte Carlo naïve pour maximiser l'EAP (énergie annuelle).

    Évalue `x0`, puis tire `n` layouts complètement aléatoires dans une
    boîte fixe et garde celui qui donne le meilleur EAP.

    Formulation équivalente (polycopié / NOMAD, minimisation) :

    ```text
    min  f(x) = -EAP(x)   ⇔   max  EAP(x)
    ```

    Layout AMON (coordonnées intercalées) :

    ```text
    x = [x0, y0, x1, y1, ..., x_{NT-1}, y_{NT-1}]
    ```

    ### Chemins `param` / `x0`

    Fichiers résolus via `resolve_path` : racine du repo **ou** `lib/AMON`
    (ex. `"bb_example/param.txt"` ou `"instances/1/x0.txt"`).
    Si `x0` est une `list`, elle est passée telle quelle à la blackbox.

    ### Exemple

    ```python
    # chemins AMON
    best = mc_solver("bb_example/param.txt", "bb_example/x0_instance.txt", n=10)
    # ou fichiers posés à la racine du repo : "mon_param.txt", "mon_x0.txt"
    ```

    Args:
        param: Fichier param (absolu, relatif au repo, ou relatif à `lib/AMON`).
        x0: Layout initial — chemin fichier (même résolution) **ou** liste
            `[x0, y0, ..., x_{n-1}, y_{n-1}]`.
        n: Nombre de tirages aléatoires après l'évaluation de `x0`.

    Returns:
        Meilleur EAP observé, en GWh (`float`).
    """
    param = resolve_path(param)
    if not isinstance(x0, list):
        x0 = resolve_path(x0)

    # Point de référence uniquement (ensuite : tirages i.i.d., pas autour de x0)
    print(f"[mc] eval 0/{n} (x0) …", flush=True)
    eap, *_ = windfarm_eval.windfarm_eval(param, x0)
    best = eap
    print(f"[mc] EAP={eap:.4f}  best={best:.4f}", flush=True)

    for i in range(n):
        
        # 30 = DIMENSION du bb_example ; bornes = bbox du terrain (hardcodées)
        xs = np.random.uniform(52274.51767349267, 53803.380417069864, 30)
        ys = np.random.uniform(521785.03108614404, 522850.77981024975, 30)
        
        # Format AMON : [x0, y0, x1, y1, ...]
        layout = list(itertools.chain(*zip(xs, ys)))
        
        print(f"[mc] eval {i + 1}/{n} …", flush=True)
        eap, *_ = windfarm_eval.windfarm_eval(param, layout)  # *_ = contraintes ignorées
        
        if eap > best:  # max EAP ⇔ min (-EAP)
            best = eap
        
        print(f"[mc] EAP={eap:.4f}  best={best:.4f}", flush=True)

    return best


if __name__ == "__main__":
    # n=2 pour un smoke test rapide (~3 évals × ~10 s)
    print("Best EAP =", mc_solver("bb_example/param.txt", "bb_example/x0_instance.txt", n=2), "GWh")
