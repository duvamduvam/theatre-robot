# theatre-robot — le système Didier en un seul dépôt

Mono-dépôt du robot de théâtre Didier et de ses appareils (télécommande, vision, sono,
lumières, gants) — décidé le 2026-11-01 (`docs/etude-architecture-globale.md`).

## Lire la carte en deux dossiers

| Dossier | Ce qu'on y trouve |
|---|---|
| `packages/` | **QUOI** : un package ROS 2 par fonction, à plat. Noms : `didier_*` (le robot), `telecommande_*` / `sono_*` / `lights_*` (les appareils), `theatre_*` (le commun : contrats, sim, gabarit) |
| `machines/<machine>/` | **OÙ** : ce qui tourne sur chaque machine — **en place depuis L1e-4c (11/11)** : `machine.yml` (packages déployés, launch, nœuds attendus, secrets, fichiers système ; lu par Ansible) + la conf copiée dans `src/<robot\|vision>/conf/` du Pi (compose ARM, scripts, systemd). `machines/sim/` = bancs PC (`banc-robot/` = la sim Gazebo, `banc-vision/`), scripts de vérification et fumée ; un conteneur par machine en L2. Convention : [`machines/README.md`](machines/README.md) |
| `data/` | le contenu du robot : `json/` (séquences, expressions, lumières, relais), `medias/` (audios, visuels du visage), `db/` — **en place depuis L1e-4b (08/11)**, copié par Ansible dans `src/robot/` du Pi ; vérité unique servie par le robot (catalogue), éditée à travers lui à L1d |
| `deploy/` | Ansible (toutes les machines) — **en place depuis L1e-4a (08/11)** : `cd deploy && ansible-playbook -i hosts deploy-pios.yml -e target_group=robot\|vision`, puis `./ecart-pi.sh <groupe>` |
| `docker/` | Dockerfiles communs (base ARM / x86) |
| `docs/` | documentation **vivante** (architecture, opérations, contrats, chantiers, incidents, matériel) ; `docs/etudes/` = les études, avec leur statut en tête |
| `atelier/` | essais, firmwares des microcontrôleurs, scripts d'atelier — jamais déployé |
| `legacy/` | **TRANSITOIRE (lot L0)** : les quatre anciens dépôts importés avec tout leur historique. Depuis L1e-4e (11/11) il ne reste que la télécommande (`dadou_control_ros`, → L4) et des bandeaux d'archive (dont `dadou_robot_ros/CLAUDE.md`, règles de sécurité roues) ; il disparaît au lot L5 |

## État de la migration (mis à jour à chaque lot)

| Lot | Statut |
|---|---|
| L0 sauvegardes + squelette | **FAIT le 02/11** : 6 dépôts sauvegardés et poussés, secrets purgés, squelette posé et **validé sur pièce par David**, 4 historiques importés (1 628 commits), **V-R3 rejoué depuis `legacy/` : 21 OK / 0 KO**, tests du cœur verts, Ansible pointe sur `legacy/` |
| L1 contrats + données | **en cours** — FAITS, fusionnés et déployés hors robot (07/11) : L1a contrats, L1b namespace `/didier/`, L1c catalogue + sha publiés, L1e-1/2 packages `didier_*` dans `packages/`, L1e-3a lib `dadou_utils_ros`, L1e-3b messages `theatre_interfaces` ; L1e-3c cœur `didier_core` et L1e-3d vision `didier_vision` (08/11) ; L1e-4a `deploy/`, L1e-4b `data/` (11/11) ; L1e-4c `machines/` (11/11) ; L1e-4e ménage (11/11, branche : doc dans `docs/`, essais et firmwares dans `atelier/`, venvs racine). ⛔ Protocole caméra dû avant tout usage au sol. Reste : L1d édition via le robot (conception fermée le 12/11 ; L1d-1 fait sur la branche `l1d` : contrat des données avec bornes roues, écrivain désactivé par défaut, rechargement à chaud ; L1d-2 à L1d-5 à venir). Détail : [tableau de bord](docs/chantiers.md), [spec L1](docs/spec-L1-contrats-donnees.md) |
| L2 sim multi-conteneurs | **spec fermée écrite le 13/11**, rien de codé — [`docs/spec-L2-sim-multi-conteneurs.md`](docs/spec-L2-sim-multi-conteneurs.md) (5 sous-étapes L2a à L2e) |
| L3 gabarit + sono | à venir |
| L4 télécommande neuve | à venir |
| L5 ménage | à venir |

Pendant la transition, le code vit dans `packages/`, Ansible dans `deploy/`, les données du
robot dans `data/` et la conf des machines dans `machines/` ; la doc dans `docs/` (L1e-4e). Les dossiers cibles encore vides contiennent des
README qui disent ce qui doit y arriver et d'où.
