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
| L0 sauvegardes + squelette | **en cours** (02/11) : squelette posé, historiques importés, sim à vérifier depuis `legacy/` |
| L1 contrats + données | à venir |
| L2 sim multi-conteneurs | à venir |
| L3 gabarit + sono | à venir |
| L4 télécommande neuve | à venir |
| L5 ménage | à venir |

Pendant la transition, **la source de vérité du code reste `legacy/`** ; les dossiers cibles
contiennent des README qui disent ce qui doit y arriver et d'où.
