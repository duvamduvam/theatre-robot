# machines/

**OÙ** tourne quoi : un dossier par machine du parc (lot L1e-4c, 11/11). Le **QUOI** (le code)
est dans `packages/`, le contenu du robot dans `data/`, Ansible dans `deploy/`.

| Dossier | Machine | État |
|---|---|---|
| `robot/` | Pi 4 du robot (hôte `r`) | conf complète (ex `legacy/dadou_robot_ros/conf/` sans la sim) |
| `vision/` | Pi 5 de la tête (hôte `ai`) | conf complète (ex `legacy/dadou_vision_ros/{conf,mediamtx}`) |
| `sim/` | le PC de David (pas un hôte Ansible) | sim multi-conteneurs depuis L2b (`docker-compose.yml` : `monde`, `robot`, `vision`, `telecommande`, mêmes Dockerfiles que les Pi), surcouche banc vision, épreuves, fumée et sa minuterie |
| `telecommande/`, `gant-gauche/`, `gant-droit/` | console de pilotage, gants | `machine.yml` seul : le code et la conf sont encore dans `legacy/dadou_control_ros/` (lot L4) |
| `lights/` | — | pas encore d'hôte : à créer avec `nouvel_appareil.py` (gabarit d'appareil, L3a) |

## La convention `machine.yml`

`deploy/hosts` ne dit que **où** est une machine : groupe, IP, utilisateur, clé — et
`machine: <dossier>`. Tout ce qui dit **ce qui y tourne** est dans `machines/<machine>/machine.yml`,
chargé par Ansible (`include_vars`, en tête de `deploy-pios.yml` et `install-pios-lite.yml`) :

| Variable | Rôle |
|---|---|
| `project_ros_dir`, `project_name` | dossier `~/ros2_ws/src/<project_ros_dir>/` du Pi, nom du conteneur et du service |
| `conf_machine_dir` | la conf de la machine sur le PC : `{{ machines_dir }}/<machine>` (copiée dans `src/<projet>/conf/`), ou `legacy/<projet>/conf` pour une machine pas encore déménagée |
| `local_project_dir` | SEULEMENT les machines restées dans `legacy/` : leur projet entier part par la copie « projet » |
| `packages` | packages de `packages/` copiés dans `ros2_ws/src/` (défaut : `packages_default` de `deploy/vars/main.yml`) |
| `donnees_dir` | robot seul : `data/` → `src/robot/{json,medias,db}` ; avec lui, les audios privés (hors dépôt, `medias_prives_dir` de `deploy/vars/main.yml`) → `src/robot/medias/audios/`, sha vérifiés (`ecart-pi.sh`, volet d) |
| `edition_donnees` | robot seul (L1d) : variable `DATA_EDIT` du conteneur, `false` dans le dépôt — l'activer est une décision de David |
| `launch_cmd`, `sentinelle_build`, `noeuds_attendus` | lancement, build colcon au démarrage, contrôle de fin de déploiement |
| `paquets_hote`, `unites_systemd`, `fichiers_etc`, `telechargements_hote`, `dossiers_montes`, `secrets_hote` | système de l'hôte, voix, points de montage, secrets (depuis `~/.config/didier/` du PC, jamais du dépôt) |

Une variable de contenu dans `hosts`, un hôte sans `machine:` ou une machine sans `machine.yml`
font rougir `packages/didier_core/test/unit/test_arborescence.py`.

## Ajouter une machine (ou en remettre une retirée)

**Un appareil du spectacle** (sono, lumières…) se crée avec le gabarit : `python3
packages/theatre_gabarit/tools/nouvel_appareil.py <nom>`, puis les gestes numérotés de
[`packages/theatre_gabarit/README.md`](../packages/theatre_gabarit/README.md) — les tests rouges
du nouvel appareil (`test_gabarit.py`) disent ce qui manque, `deploy/hosts` et
`HOTES_MACHINES` de `test_arborescence.py` compris (geste G8). C'est la seule procédure écrite
(lot L3a, 28/11). Le 11/11, les hôtes `d` (disque), `s` (sono) et `test` avaient été retirés de
`deploy/hosts` avec leurs dossiers ; la sono revient par le gabarit au lot L3b.

## Ce qui part sur un Pi

`machines/<machine>/` est copié tel quel dans `~/ros2_ws/src/<project_ros_dir>/conf/` (rôle
`synchronise`), **sauf** `machine.yml`, `README.md` et `secret`. Les chemins sur les Pi et dans les
conteneurs n'ont pas bougé (`src/robot/conf/docker/arm/docker-compose-arm.yml`…) : les compose ARM
gardent donc des chemins relatifs à la disposition du Pi (`../../..` = `src/<projet>/`), pas à
celle du dépôt. `machines/sim/` ne part sur aucun Pi. Renommer les chemins Pi est le travail de L2.

## Les images Docker (L2a, 14/11)

**Un Dockerfile par machine, `<machine>/docker/Dockerfile`, le même pour le Pi (ARM) et le PC
(x86)**, construit en natif des deux côtés (aucune émulation). Son contexte principal est son
dossier `docker/` et rien n'en est copié : tout arrive par **contextes nommés** — `conf` (la conf
de la machine), `data` (robot seul) et un par package de la liste `packages` du `machine.yml`. Le
compose ARM (`docker/arm/docker-compose-arm.yml`) donne les chemins du Pi ; le compose du PC (banc
vision aujourd'hui, sim en L2b) ceux du dépôt. Même liste partout — lignes `COPY --from=<package>`,
`packages`, contextes des compose, montages de sources : gravé par `test_arborescence.py`.
Pas d'image de base commune (`docker/` à la racine est supprimé).

Les images ARM sont **publiées sur le Hub** (dépôts publics), d'où deux règles :
- **secret de la vision** : `conf/secret` n'y entre jamais — (a) `vision/.dockerignore` à la racine
  du contexte `conf` (il part sur le Pi avec la conf), (b) `COPY --from=conf --exclude=secret` dans
  le Dockerfile, (c) le rôle `conteneur` vérifie l'image construite pour chaque `secrets_hote` et
  fait échouer le déploiement si le fichier y est ;
- **audios privés** (robot) : sur le Pi, `medias/audios/` est rempli par Ansible ; le Dockerfile
  copie `medias/` avec `--exclude=audios/*` (le dossier reste, vide : point de montage).

Republier une image : `docs/ansible-ecarts.md` (ligne « Images sur le Hub »).
