# docs/

Documentation vivante du mono-dépôt (arrivée de `legacy/dadou_robot_ros/docs/` au lot L1e-4e, 2026-11-11). Un test (`packages/didier_core/test/unit/test_liens_markdown.py`) échoue sur tout lien Markdown relatif mort du dépôt.

## Par où commencer

- [`chantiers.md`](chantiers.md) : **tableau de bord** — état, prochaine action et blocages de chaque chantier. Commencer ici.
- [`architecture.md`](architecture.md) : le logiciel du robot, ses couches et son lien avec le contrôleur et les utilitaires.
- [`interfaces.md`](interfaces.md) : topics ROS et configuration exposés/consommés par le robot.
- [`operations.md`](operations.md) : commandes de test, déploiement, calibration, fumée, répétitions.
- [`software/overview.md`](software/overview.md) : nœuds ROS 2, gestionnaires d'actions, comment étendre.
- [`hardware/overview.md`](hardware/overview.md) : sous-systèmes physiques, capteurs, puissance.
- [`ansible-ecarts.md`](ansible-ecarts.md) : ce que les Pi portent hors Ansible et le plan pour qu'une réinstallation soit rapide et complète (relevé du 2026-11-07, à compléter à chaque reflash).

## Études et specs

- `etude-*.md` (à plat dans ce dossier) : études de chantier — globale (`etude-architecture-globale.md`), actionneurs, arbitrage, autonomie, danse, conversation, odométrie, torse, voix, interface web, télédiagnostic, télécommande USB, etc.
- [`spec-L1-contrats-donnees.md`](spec-L1-contrats-donnees.md), [`spec-A1-selecteur-de-jeu.md`](spec-A1-selecteur-de-jeu.md), [`spec-aller-voir.md`](spec-aller-voir.md), [`spec-metteur-en-scene.md`](spec-metteur-en-scene.md) : specs fermées.
- [`etudes/`](etudes/) : études plus récentes — [`etude-standards-robotique.md`](etudes/etude-standards-robotique.md) (ROS et standards, **décidé le 2026-11-11**, état des actions au §7), [`etude-banc-temoin.md`](etudes/etude-banc-temoin.md).

## Dossiers

- `incidents/` : fiches d'incident (index `incidents/README.md`), lues par le skill `/diag`.
- `seances/` : comptes rendus de séances sur le terrain.
- `outils/` : utilitaires d'atelier (feuille millimétrée imprimable, schémas du tronc) — voir `outils/README.md`.
- `pictures/` : photos et schémas cités par les pages.
- `veille/` : veille robotique hebdomadaire (une page HTML par semaine, sommaire `veille/index.html`, méthode `veille/README.md`). Créée le 2026-11-02.
- `fumee/` : fumée nocturne de la sim (une page HTML par fumée, sommaire `fumee/index.html`, journaux copiés hors conteneur dans `fumee/journaux/`). Écrit et commité par `machines/sim/fumee.sh` — **ne pas éditer à la main** ; mode d'emploi : `operations.md`, section « Fumée automatique ». Créé le 2026-11-07 (lot F).
- `architecture-ui-telecommande.html` : schémas de l'UI de la télécommande sans X11.

Voir aussi : [`../README.md`](../README.md) (carte du dépôt) et [`../CLAUDE.md`](../CLAUDE.md) (règles de travail).
