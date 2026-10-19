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

## Méthode naïve (`naive_solver`)

`N` est fixé par `DIMENSION` dans le fichier paramètre : on optimise seulement les positions. Le vecteur de décision est

$$
x = (x_1, y_1, \ldots, x_N, y_N) \in \mathbb{R}^{2N}.
$$

Trois objets géométriques, à ne pas confondre :

- **boundary zone** : le polygone du terrain, lu dans `BOUNDARY_FILE`.
- **buildable zone** : ce polygone, moins les zones d'exclusion. C'est là que les turbines ont le droit d'être. La contrainte de placement mesure la distance à cette zone.
- **bbox** : le plus petit rectangle aligné aux axes qui contient la boundary zone. AMON le lit dans le shapefile (`Boundaries.bbox`) et en fait les bornes `lb` et `ub`, soit [x_min, x_max] pour les abscisses et [y_min, y_max] pour les ordonnées. La projection et le plafond de placement utilisent ce rectangle, pas le polygone.

La blackbox renvoie trois nombres :

- l'énergie annuelle, en GWh (à maximiser)

$$
EAP(x)
$$

- la contrainte d'espacement, en mètres, nulle si les turbines sont à au moins deux diamètres l'une de l'autre

$$
s(x) = 0
$$

- la contrainte de placement, en mètres, nulle si toutes les turbines sont dans la buildable zone

$$
p(x) = 0
$$

On **minimise** la somme de trois termes déjà ramenés entre 0 et 1 :

$$
f(x) = \frac{E_{\max} - \mathrm{EAP}(x)}{E_{\max}} + \frac{s(x)}{s_{\max}} + \frac{p(x)}{p_{\max}}.
$$

Donc f vaut entre 0 et 3. Diviser par 3 donnerait une fonction entre 0 et 1, avec **le même minimiseur** ; le code garde la somme.

Les trois plafonds :

$$
E_{\max} = N \cdot \mathrm{EAP}_1,
\qquad
s_{\max} = N(N-1)\, D,
\qquad
p_{\max} = N \sqrt{(x_{\max}-x_{\min})^2 + (y_{\max}-y_{\min})^2}.
$$

- Le premier plafond est l'énergie d'**une** turbine isolée (un appel blackbox au centre de la bbox), multipliée par N. Les sillages ne font que diminuer l'EAP.
- Le deuxième est le cas où toutes les turbines sont au même point : N(N−1)/2 paires, et chaque paire contribue un déficit de 2D.
- Le troisième utilise la diagonale de la bbox : dans ce rectangle, une turbine ne peut pas être plus loin que ça de la buildable zone.

Le gradient n'est pas fourni par la blackbox. On le calcule par **différences finies avant**. Le décalage vaut un diamètre ; s'il sort de la bbox, on prend l'opposé.

$$
g_i = \frac{f(x + \delta e_i) - f(x)}{\delta}.
$$

Puis on fait un pas de descente de gradient. Le vecteur g monte f, donc on suit −g. Le pas α est un nombre positif (dans le code, le déplacement fait un diamètre) :

$$
x \leftarrow x - \alpha g.
$$

Si ce nouveau point sort de la bbox, on le ramène sur le bord. C'est la projection Π : chaque abscisse est recollée dans [x_min, x_max], chaque ordonnée dans [y_min, y_max]. Une coordonnée trop petite prend la borne min, une coordonnée trop grande prend la borne max. Un point déjà dans la bbox ne bouge pas. Π ne connaît pas la buildable zone : une turbine peut être dans la bbox et quand même hors du polygone, et c'est alors p(x) qui le voit.

$$
x \leftarrow \Pi(x - \alpha g).
$$

On répète ça `n_steps` fois et on garde le point visité (y compris les décalages) qui a le plus petit f. La fonction renvoie l'EAP de ce point.

Nombre d'évaluations :

$$
2 + n_{\text{steps}}(2N + 1).
$$

Pour N = 30 et un seul pas, cela fait 63 appels, soit de l'ordre de 10 minutes.

```python
from solvers import naive_solver
eap = naive_solver("bb_example/param.txt", "bb_example/x0_instance.txt", n_steps=1)
```

## Créer un .txt de paramétrisation des éoliennes

todo
