"""Solvers d'optimisation de layout éolien (blackbox AMON)."""

import ast
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

import data as amon_data
import windfarm_eval
import windfarm_setting as amon_wf


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


def naive_solver(param, x0, n_steps=1, step=None):
    """Descente de gradient naïve sur une pénalité EAP + contraintes.

    `N` (nombre d'éoliennes) est lu dans le fichier `param` et n'est pas optimisé.
    On minimise

    ```text
    f(x) = (E_max - EAP(x)) / E_max + s(x) / s_max + p(x) / p_max
    ```

    Chaque terme vaut entre 0 et 1, donc `f(x)` vaut entre 0 et 3.
    `f/3` a le même minimiseur : on garde la somme, plus simple à lire.

    Une évaluation de blackbox dure plusieurs secondes. Un pas de gradient
    coûte `2N + 1` évaluations (différences finies, puis le nouveau point).

    Args:
        param: Fichier param (absolu, relatif au repo, ou relatif à `lib/AMON`).
        x0: Layout initial — chemin fichier **ou** liste
            `[x0, y0, ..., x_{N-1}, y_{N-1}]`.
        n_steps: Nombre de pas de descente. `0` = on évalue seulement `x0`.
        step: Longueur du pas, en mètres. Par défaut : le diamètre `D`.

    Returns:
        EAP (GWh) du layout visité qui a le plus petit `f`.
    """
    param = resolve_path(param)

    # --- Lire N, D, et la boîte du terrain ---------------------------------
    # N est fixé par DIMENSION : on ne change pas le nombre d'éoliennes.
    # D est le diamètre. Deux turbines doivent être à au moins 2D.
    # On s'en sert aussi comme longueur de pas (un pas = un diamètre).
    nb_wt, diameter, _hub, scale_factor, _pc, boundary_file, *_rest = (
        amon_data.read_param_file(param)
    )
    # "na" : on ne charge pas les zones d'exclusion. Il nous faut seulement
    # le rectangle englobant (bbox), déjà mis à l'échelle par AMON.
    lb, ub, *_terrain = amon_wf.terrain_setting(
        boundary_file, "na", scale_factor=scale_factor
    )
    lb = np.asarray(lb, dtype=float)  # [x_min, y_min]
    ub = np.asarray(ub, dtype=float)  # [x_max, y_max]

    # --- Mettre x0 sous forme de vecteur de taille 2N ----------------------
    # Fichier : une ligne du type [x0, y0, x1, y1, ...], comme AMON.
    if not isinstance(x0, list):
        with open(resolve_path(x0), "r") as f:
            x0 = ast.literal_eval(f.read().splitlines()[0])
    x = np.asarray(x0, dtype=float).copy()
    if x.size != 2 * nb_wt:
        raise ValueError(
            f"x0 a {x.size} coordonnées, il en faut {2 * nb_wt} (2 par éolienne)"
        )

    # Projection sur la bbox : x pair = abscisse, x impair = ordonnée.
    # Après ça, chaque éolienne est dans le rectangle du terrain.
    def project(z):
        z = np.asarray(z, dtype=float).copy()
        z[0::2] = np.clip(z[0::2], lb[0], ub[0])
        z[1::2] = np.clip(z[1::2], lb[1], ub[1])
        return z

    x = project(x)

    # n_steps = 0 : pas d'optimisation, juste l'EAP du point de départ.
    if n_steps <= 0:
        print("[naive] n_steps=0, évaluation de x0 seulement", flush=True)
        eap, *_c = windfarm_eval.windfarm_eval(param, x.tolist())
        print(f"[naive] EAP={float(eap):.4f}", flush=True)
        return float(eap)

    # --- Trois plafonds, pour que chaque terme de f soit dans [0, 1] -------
    #
    # E_max : N fois l'EAP d'UNE turbine isolée (pas de sillage entre elles).
    # Les sillages ne font que baisser la production, donc c'est un plafond.
    center = [0.5 * (lb[0] + ub[0]), 0.5 * (lb[1] + ub[1])]
    print("[naive] EAP d'une turbine isolée (pour E_max) …", flush=True)
    eap_one, *_c = windfarm_eval.windfarm_eval(param, center)
    eap_max = float(nb_wt) * float(eap_one)

    # s_max : pire espacement = toutes les turbines au même point.
    # Il y a N(N-1)/2 paires, chacune dépasse la distance 2D de exactement 2D,
    # et spacing_constraint_min renvoie la somme de ces dépassements.
    # Donc s_max = N(N-1)/2 * 2D = N(N-1) D.
    s_max = float(nb_wt * (nb_wt - 1) * diameter)

    # p_max : pire placement dans la bbox.
    # Une turbine dans le rectangle est au plus à une diagonale du polygone,
    # et on somme N turbines.
    diagonal = float(np.hypot(ub[0] - lb[0], ub[1] - lb[1]))
    p_max = float(nb_wt) * diagonal

    print(
        f"[naive] E_max={eap_max:.4f}  s_max={s_max:.1f}  p_max={p_max:.1f}",
        flush=True,
    )

    # f = terme énergie + terme espacement + terme placement.
    # Si un plafond est nul (N=1, ou bbox vide), ce terme vaut 0.
    def penalty(eap, s_d, sum_dist):
        t_eap = (eap_max - eap) / eap_max if eap_max > 0.0 else 0.0
        t_s = s_d / s_max if s_max > 0.0 else 0.0
        t_p = sum_dist / p_max if p_max > 0.0 else 0.0
        return t_eap + t_s + t_p

    # Un appel blackbox + la valeur de f. On renvoie aussi le point projeté.
    def evaluate(z):
        z = project(z)
        eap, s_d, sum_dist = windfarm_eval.windfarm_eval(param, z.tolist())
        eap = float(eap)
        return z, eap, penalty(eap, s_d, sum_dist)

    # Pas de différence finie et pas de descente : de l'ordre du diamètre.
    # ε trop petit → le quotient (f(x+ε)-f(x))/ε noie le signal dans le bruit.
    eps = float(diameter) if diameter > 0 else 1.0
    step_len = eps if step is None else float(step)

    # Meilleur point vu (y compris les petits décalages du gradient).
    x, eap, f_cur = evaluate(x)
    best_x, best_eap, best_f = x.copy(), eap, f_cur
    print(f"[naive] step 0/{n_steps}  f={f_cur:.4f}  EAP={eap:.4f}", flush=True)

    def remember(z, eap_z, f_z):
        nonlocal best_x, best_eap, best_f
        if f_z < best_f:
            best_x, best_eap, best_f = z.copy(), eap_z, f_z

    for k in range(n_steps):
        # Gradient avant : g_i = ( f(x + δ e_i) - f(x) ) / δ
        # δ = +ε, ou −ε si +ε sort de la bbox (sinon le point ne bouge pas
        # et le quotient vaudrait 0 sans raison).
        g = np.zeros(x.size)
        for i in range(x.size):
            z_try = x.copy()
            z_try[i] = x[i] + eps
            z_try = project(z_try)
            if z_try[i] == x[i]:
                z_try = x.copy()
                z_try[i] = x[i] - eps
                z_try = project(z_try)
            delta = z_try[i] - x[i]
            if delta == 0.0:
                g[i] = 0.0
                continue
            z_try, eap_try, f_try = evaluate(z_try)
            g[i] = (f_try - f_cur) / delta
            remember(z_try, eap_try, f_try)

        # Direction normalisée : on avance de `step_len` mètres, pas de
        # ||g|| mètres (g est en 1/mètre, un pas α g serait tout petit).
        # x ← proj( x - t g / ||g|| )
        g_norm = float(np.linalg.norm(g))
        if g_norm == 0.0:
            print(f"[naive] gradient nul au pas {k + 1}, arrêt", flush=True)
            break
        x = project(x - step_len * g / g_norm)
        x, eap, f_cur = evaluate(x)
        remember(x, eap, f_cur)
        print(
            f"[naive] step {k + 1}/{n_steps}  f={f_cur:.4f}  EAP={eap:.4f}"
            f"  best_f={best_f:.4f}  best_EAP={best_eap:.4f}",
            flush=True,
        )

    return float(best_eap)


if __name__ == "__main__":
    # n=2 pour un smoke test rapide (~3 évals × ~10 s)
    print("Best EAP =", mc_solver("bb_example/param.txt", "bb_example/x0_instance.txt", n=2), "GWh")
