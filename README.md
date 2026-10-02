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

* Avoir un méchant .env avec une variable d'env qui est la suivante (avec le chemin adapté à votre arborescence)
`PYTHONPATH=/home/theo_wsl/Work/mam5/opti_avancee/opti_avancee_projet/lib/AMON`    
Si pas compris, se baser le [.env-exemple](.env-exemple)

## Lancer la simu

Depuis la racine du repo :
* Activer l'env virtuel si ce n'est pas fait : 
```bash
source .venv/bin/activate
```
* Lancer le super script python (paramétré avec les bonnes entrées à tester !) 
```bash
python main.py
```

## Créer un .txt de paramétrisation des éoliennes
todo