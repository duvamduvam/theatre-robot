# didier_perception — ce que Didier sait du monde, publié

Premier habitant : le **tableau des objets** (lots O0-O1, 18/11 ; étude
[`etude-objets-vus-et-carte.md`](../../docs/etudes/etude-objets-vus-et-carte.md) §6). Les pistes
de personnes du lot A2 le rejoindront (un nœud par sujet, contrat dans `theatre_contrats`).

**Un tableau, un écrivain, quatre lecteurs.** `objets_node` est le SEUL à calculer « où est le
banc » : il publie `scene/objets` (latché, contrat `theatre_contrats/objets.py`) ; la bouche
(`chat_node`), la réflexion, le sélecteur de jeu et la régie le lisent et désignent un objet par
son `id`. Panne d'origine : séance du 15/11, Didier à x = 14 m dit « le banc est là » et roule
22 m — trois composants, trois représentations, aucun identifiant commun.

| Module | Rôle |
|---|---|
| `tableau.py` | logique PURE de l'écrivain : fusion carte ↔ vu, noms uniques (« banc », « banc 2 »), péremption des objets vus, géométrie vue de Didier (distance, azimut, côté, dans le champ ±30° et à 15 m au plus), règle `atteignable` (repère monde/odom, σ ≤ 1 m, ≤ 10 m, carte ou vu il y a < 10 s) |
| `objets_node.py` | entrées/sorties ROS : `rehearsal/objects` (carte, latché) + `ground_truth/odom` (pose, SIM) → `scene/objets` (latché, republié à 1 Hz et à chaque changement de carte) |

Sources aujourd'hui (O1) : la **carte** de la régie (sim, lieu préparé ; position = CENTRE de
l'objet quand la géométrie de collision est connue, sinon l'ancre du POI) et la **pose vérité
terrain** de Gazebo. En rue (pas de carte, pas de pose), le tableau est vide : la caméra y entre
au lot O2 (inventaire, désignation recoupée), sans changement de contrat.

**Le chemin roues ne passe pas ici** : le tableau fournit une CIBLE ; vitesses, deadman,
`twist_mux`, arrêt d'urgence et bornes de `goto.py` sont ailleurs et intouchés.

Tests (hôte, sans ROS) : `cd packages/didier_perception && ../../.venv/bin/python -m pytest -q -o addopts=`
— dont la séance du 15/11 rejouée sur la VRAIE carte (« banc » à x = 14 → pas ici, 22 m).
