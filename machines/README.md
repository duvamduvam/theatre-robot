# machines/

**OÙ** tourne quoi : un dossier par machine du parc (lot L1e-4c, 11/11). Le **QUOI** (le code)
est dans `packages/`, le contenu du robot dans `data/`, Ansible dans `deploy/`.

| Dossier | Machine | État |
|---|---|---|
| `robot/` | Pi 4 du robot (hôte `r`) | conf complète (ex `legacy/dadou_robot_ros/conf/` sans la sim) |
| `vision/` | Pi 5 de la tête (hôte `ai`) | conf complète (ex `legacy/dadou_vision_ros/{conf,mediamtx}`) |
| `sim/` | le PC de David (bancs, pas un hôte Ansible) | `banc-robot/` (sim Gazebo), `banc-vision/`, scripts de vérification, fumée et sa minuterie |
| `telecommande/`, `gant-gauche/`, `gant-droit/` | console de pilotage, gants | `machine.yml` seul : le code et la conf sont encore dans `legacy/dadou_control_ros/` (lot L4) |
| `lights/` | — | vide (pas encore d'hôte) |

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

Le 11/11, les hôtes `d` (disque), `s` (sono) et `test` ont été retirés de `deploy/hosts`, avec
`machines/disque/` et `machines/sono/` : leurs projets n'étaient pas dans le dépôt, le déploiement
ne pouvait pas marcher (l'ancien contenu reste dans l'historique git, commit de retrait du 11/11).
Pour en (re)mettre une — la sono reviendra ainsi au lot L3 :

1. `machines/<machine>/machine.yml` : partir de `machines/robot/machine.yml` ou
   `machines/vision/machine.yml` et ne garder que ce qui tourne sur l'hôte (tableau ci-dessus) ;
   un `README.md` d'une ligne (rôle de la machine).
2. `deploy/hosts` : un groupe, l'hôte avec `ansible_host: <IP>` et `machine: <machine>` — RIEN
   d'autre (utilisateur et clé au niveau d'un groupe parent, comme `didier_pi`).
3. `packages/didier_core/test/unit/test_arborescence.py` : ajouter l'hôte à `HOTES_MACHINES`.
4. Vérifier : `ansible-playbook -i hosts deploy-pios.yml --syntax-check`, les tests, puis
   `ansible-playbook -i hosts deploy-pios.yml -e target_group=<groupe>` et graver l'inventaire
   attendu (`attendu/<groupe>.txt`, voir `docs/ansible-ecarts.md`) pour que `./ecart-pi.sh <groupe>`
   ait une référence.

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
