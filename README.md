# opti_avancee_projet

c'est le projet d'opti avancée tu connais

## Installation

**Pré-requis** : avoir [uv sur sa machine](https://docs.astral.sh/uv/getting-started/installation/)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

* Cloner le dépôt

```bash
git clone --recurse-submodules https://github.com/theocimino/opti_avancee_projet.git
cd opti_avancee_projet
```

* Installer l'environnement virtuel avec uv

```bash
uv python install 3.9
uv python pin 3.9
uv venv --python 3.9          # crée .venv/ à la racine (ou: uv venv ../envpy39 --python 3.9)
source .venv/bin/activate
uv pip install -r ./lib/AMON/requirements.txt -c constraints.txt
uv pip install 'setuptools<82'   # requis : py_wake importe pkg_resources (fourni par setuptools)
```

> `constraints.txt` ne fait que borner `setuptools<82` ; il ne l'installe pas. Sans l'install explicite ci-dessus → `ModuleNotFoundError: No module named 'pkg_resources'`.

* (Optionnel) `.env` avec `PYTHONPATH=.../lib/AMON` — utile pour `main.py`.  
`solvers.py` gère déjà le path AMON tout seul (`sys.path` + `chdir`). Voir [.env-exemple](.env-exemple).

## Patch AMON (obligatoire pour rediriger les outputs)

AMON écrit par défaut dans `./results/` **relatif au CWD** (donc `lib/AMON/results/` si on lance depuis AMON).  
On a patché `lib/AMON/windfarm_eval.py` pour lire la variable d'env `AMON_RESULTS_DIR` (process-local, disparaît à la fin du script).

Fichier : [`lib/AMON/windfarm_eval.py`](lib/AMON/windfarm_eval.py)

1. **Après** `import ast` (~L13–14) — ajouter :

```python
import os
```

2. **Après les imports, avant** `memoize` (~L22–26) — ajouter :

```python
def results_dir():
    """Output directory (default: ./results). Override with env AMON_RESULTS_DIR."""
    d = os.environ.get("AMON_RESULTS_DIR", "results")
    os.makedirs(d, exist_ok=True)
    return d
```

3. **Dans** `settings()` (~L78) — remplacer :

```python
# avant
wf.site_setting(..., "results")
# après
wf.site_setting(..., results_dir())
```

4. **Dans** `windfarm_eval()`, écriture du log (~L137) — remplacer :

```python
# avant
file = open('results/bb_result.txt', 'a+')
# après
file = open(os.path.join(results_dir(), 'bb_result.txt'), 'a+')
```

Sans ce patch, `solvers.py` écrit encore dans `lib/AMON/results/`.  
Avec le patch + `AMON_RESULTS_DIR` (posé par `solvers.py`), les sorties vont dans `./results/` à la racine du repo (`bb_result.txt`, `WindRose.png`).

## Lancer un solver

Depuis la racine du repo, env activé :

```bash
source .venv/bin/activate  
python solvers.py
```

Ou bien dans un script python :

```python
from solvers import mc_solver
best = mc_solver("bb_example/param.txt", "bb_example/x0_instance.txt", n=10)
```

## Créer un .txt de paramétrisation des éoliennes

todo
