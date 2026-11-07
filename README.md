# theatre-robot — le système Didier en un seul dépôt

Mono-dépôt du robot de théâtre Didier et de ses appareils (télécommande, vision, sono,
lumières, gants) — décidé le 2026-11-01 (`legacy/dadou_robot_ros/docs/etude-architecture-globale.md`).

## Lire la carte en deux dossiers

| Dossier | Ce qu'on y trouve |
|---|---|
| `packages/` | **QUOI** : un package ROS 2 par fonction, à plat. Noms : `didier_*` (le robot), `telecommande_*` / `sono_*` / `lights_*` (les appareils), `theatre_*` (le commun : contrats, sim, gabarit) |
| `machines/<hôte>/` | **OÙ** : ce qui tourne sur chaque machine — packages déployés, compose, launch, variables Ansible. `machines/sim/` = la séance de simulation, un conteneur par machine |
| `data/` | les JSON (séquences, visuels, audios, relais, lumières) — **vérité unique**, servie par le robot, éditée à travers lui |
| `deploy/` | Ansible (toutes les machines) |
| `docker/` | Dockerfiles communs (base ARM / x86) |
| `docs/` | documentation **vivante** (architecture, opérations, contrats, chantiers, incidents, matériel) ; `docs/etudes/` = les études, avec leur statut en tête |
| `atelier/` | essais, PCB, scripts d'atelier — jamais déployé |
| `legacy/` | **TRANSITOIRE (lot L0)** : les quatre anciens dépôts importés avec tout leur historique, côte à côte, tels qu'ils tournaient le 2026-11-02. La sim et les compose y fonctionnent sans changement. Chaque lot vide un peu `legacy/` vers les dossiers ci-dessus ; il disparaît au lot L5 |

## État de la migration (mis à jour à chaque lot)

| Lot | Statut |
|---|---|
| L0 sauvegardes + squelette | **FAIT le 02/11** : 6 dépôts sauvegardés et poussés, secrets purgés, squelette posé et **validé sur pièce par David**, 4 historiques importés (1 628 commits), **V-R3 rejoué depuis `legacy/` : 21 OK / 0 KO**, tests du cœur verts, Ansible pointe sur `legacy/` |
| L1 contrats + données | **en cours** — **L1a FAIT et VALIDÉ le 02/11** : `packages/theatre_contrats` + `packages/robot_interfaces` (copie unique), `utils_static.py` réduit à un shim, codec StringTime commun, topics de la vision relatifs, V-R3 21/21 ; ⚠️ **Verrous de déploiement de L1a (revue du 02/11)** : (a) Ansible corrigé le 02/11 (synchro de `conf/ros2_dependencies/` conditionnelle, `packages/` rsyncé vers `ros2_ws/src/`) ; (b) le nouveau code n'entre en service sur un Pi qu'après un `colcon build` complet — poser la sentinelle au déploiement, sinon l'ancien code tourne en silence ; (c) aucune image ni `colcon build` ARM exécuté : `robot_interfaces` (numpy facultatif) et les `COPY --from=` ARM se vérifient au premier déploiement, robot d'abord). Suite : L1b namespace `didier/`, L1c catalogue publié, L1d édition via le robot, L1e renommages `didier_*` (spec `docs/spec-L1-contrats-donnees.md`). **L1b + L1c faits en sim sur la branche `l1-namespace-catalogue` (déployés hors robot le 04/11, non fusionnés : protocole caméra d'abord). L1e-1 FAIT le 06/11 sur la même branche** : les 6 packages ROS du robot sont dans `packages/` (noms inchangés), Ansible pousse une liste de packages par machine, tests hôte et sim verts. **L1e-2 FAIT le 07/11** : les 6 renommés `didier_*` (bringup, description, drive, rehearsal, sim, web), Ansible efface des Pi les anciens noms (`packages_retires`), V-R3 21/21 et A1 14/14 (détail dans `docs/spec-L1-contrats-donnees.md` §L1e) |
| L2 sim multi-conteneurs | à venir |
| L3 gabarit + sono | à venir |
| L4 télécommande neuve | à venir |
| L5 ménage | à venir |

Pendant la transition, **la source de vérité du code reste `legacy/`** ; les dossiers cibles
contiennent des README qui disent ce qui doit y arriver et d'où.
