# opti_avancee_projet
c'est le projet d'opti avancée tu connais

## Installation

**Pré-requis** : avoir [uv sur sa machine](https://docs.astral.sh/uv/getting-started/installation/)

* Cloner le dépôt
```bash
git clone --recurse-submodules https://github.com/theocimino/opti_avancee_projet.git
```

* Installer l'environnement virtuel avec uv

```bash
uv python install 3.9
uv python pin 3.9
uv venv --python 3.9
uv pip sync -r ./lib/AMON/requirements.txt -c constraints.txt
```

