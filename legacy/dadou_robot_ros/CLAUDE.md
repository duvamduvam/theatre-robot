# Didier — robot de théâtre (dadou_robot_ros)

Code embarqué (Raspberry Pi 4, Docker, ROS 2 **Jazzy**) du robot de théâtre Didier (~50 kg).
Dépôts frères : `../dadou_control_ros` (télécommande), `../dadou_utils_ros` (lib partagée
par symlink + système de déploiement Ansible), `../dadou_vision_ros` (gelé).
Objectif long terme : robot autonome qui suit l'acteur, parle, simule des émotions.

## RÈGLES DE SÉCURITÉ (non négociables — des incidents roues ont déjà eu lieu)

- Toute fonctionnalité mouvement DOIT traiter son cas d'arrêt (deadman, e-stop, perte de liaison).
- Toute modification du chemin roues → validation en **simulation** d'abord, puis **protocole
  caméra** sur le vrai robot (roues hors sol, webcam USB, captures ffmpeg) AVANT usage au sol.
- `ROS_DOMAIN_ID=42` = vrai robot, `43` = simulation. Ne jamais mélanger : une commande de
  test ne doit jamais pouvoir atteindre le vrai Didier.
- Commiter un instantané AVANT tout refactoring.
- `WHEELS_CMD_VEL_ENABLED=True` est la config officielle depuis la bascule validée du
  2026-07-04 ; tout retour en arrière ou nouvelle bascule repasse par le protocole caméra.
- **Namespace par robot (lot L1b, 04/11, validé en SIM seulement)** : tous les nœuds sous
  `/<ROBOT_NAME>/` (défaut `/didier/`) — les topics roues deviennent `/didier/cmd_vel`,
  `/didier/wheels`, `/didier/e_stop`. **Pas de déploiement sur le robot avant le protocole
  caméra** (`validate-cmdvel-protocol.sh`, déjà préfixé). Robot, vision et télécommande
  d'un même Didier doivent avoir le même `ROBOT_NAME` (posé par les docker-compose).

## État Phase 2 (2026-07-04) — migration mouvement vers les standards ROS

FAIT et validé en sim (tout est commité/poussé, CI verte, 123 tests unitaires) :
- **Simulation Gazebo Harmonic** : `conf/docker/sim/` (conteneur dédié x86),
  packages `robot_description` (URDF xacro + plugins gz) et `robot_sim` (monde, bridge, launch).
- **Chaîne cmd_vel** (`packages/robot_drive` (racine du mono-dépôt ; L1e-1 du 06/11 : `conf/ros2_dependencies/` n'existe plus, les 6 packages ament vivent dans `packages/`, la liste poussée vers chaque Pi = variable `packages` de l'hôte dans `ansible/hosts`), package AUTONOME — aucun import
  dadou_utils_ros ni robot.*) : `wheels_bridge` (StringTime→Twist ; le fil ne porte que la
  VALEUR de la clé wheels) → `twist_mux` (remote 100 > anim 10, verrou `e_stop` latché,
  `use_stamped: false` obligatoire en Jazzy) → `twist_deadman` (zéros à 20 Hz si silence
  > 400 ms) → `/cmd_vel`.
- **wheels_node bi-mode** : legacy StringTime ou `/cmd_vel` selon le drapeau.
  En mode cmd_vel : deadman local 400 ms conservé (ultime rempart), twist nul → `stop()`
  franc (le plancher MIN_PWM d'`update_cmd(0,0)` ferait ramper les roues), appelé une
  seule fois par arrêt (le twist_deadman inonde de zéros à 20 Hz au repos → spam log sinon).
- **BASCULE FAITE ET VALIDÉE sur le robot le 2026-07-04** : `WHEELS_CMD_VEL_ENABLED=True`
  est la config officielle. Protocole caméra 4/4 (roues hors sol) : forward 50 %,
  slider vitesse 50 %→25 %, e-stop étanche, kill de la chaîne en plein mouvement →
  arrêt local en 440 ms. Protocole rejouable : `conf/scripts/validate-cmdvel-protocol.sh`
  (à exécuter dans le conteneur robot). Rollback : drapeau à False + sentinelle + restart.

## État du 2026-07-11 — visage calibré, architecture assainie, temps réel

- **Câblage LED du visage ÉTABLI physiquement** (mires lues par l'humain — la webcam ne
  résout pas les motifs) et GRAVÉ dans `robot/visual/image_mapping.py` +
  `test_image_mapping.py` : bouche en serpentin entrant en bas-droite, rangée basse et
  yeux montés tête-bêche, œil droit 384-447 / gauche 448-511 (contigu, sans trous).
  Ne JAMAIS « corriger » ces tests sans repasser les mires (`calib`, `calib-couleurs`,
  `calib-bords` — voir docs/operations.md).
- **Chantier architecture fait** : code mort purgé, décodage StringTime commun (payload
  JSON invalide = refus loggué, plus de perte silencieuse), classe `Track` unique pour
  les pistes de keyframes (fix au passage : les frames du visage étaient décalées d'un
  cran), contrat `Action` (ABC), contrats de données testés (chaque visuel/audio/brique
  référencé doit exister). **601 tests** (`.venv/bin/pytest`, chiffre relevé le
  2026-09-14 ; il en disait 443, figés au 11/07), CI verte.
- **Temps réel fait** : tick global 20 Hz (`TICK_PERIOD_S`, chaîne roues non touchée),
  servos en rampe linéaire (`RAMP_SPEED=160`, à caler sur scène) + anti-spam I2C +
  deadman façon roues + fix `random_duration` (le réel suit enfin la sim).
  ⚠️ `FastNeoPixel` conservé mais SLEEP DE FIN DE TRAME RÉTABLI le 2026-07-13 : sa
  suppression corrompait le visage (« deux signaux »), et le neopixel stock est
  cassé dans le conteneur (ruban noir silencieux) — post-mortem
  `docs/incidents/2026-07-13-glitch-visage-driver-led.md`.
- ⚠️ **`e_stop` n'a AUCUNE source** (verrou twist_mux déclaré, personne ne publie —
  vérifié robot + télécommande). Le deadman 400 ms est l'arrêt d'urgence effectif.
  À câbler côté télécommande, avec protocole roues.
- ⚠️ **`chat_node` coupé** sur le Pi vision depuis le 11/07 (il écrase `face` au moindre
  bruit). Relance : `ssh pi@192.168.1.151 'sudo docker restart dadou-vision-container'`.

## Commandes

```bash
.venv/bin/pytest -q                 # tests unitaires (host, sans ROS ni matériel)

# ⚠️ Namespace (L1b) : la CLI ne suit PAS le namespace des nœuds — un nom relatif tapé
# dans `ros2 topic pub/echo` se résout à la RACINE. Toujours préfixer (/didier/…) et
# lancer les `ros2 run` avec `--ros-args -r __ns:=/didier`. Sim : ROBOT_NAME=<nom> au compose.

# Simulation (GUI ; HEADLESS=true pour serveur seul ; ANIMATIONS=true = animations_node en sim) :
cd conf/docker/sim && ANIMATIONS=true docker compose -f docker-compose-sim.yml up -d
# Jouer une animation en sim (bras/yeux/cou via servos_sim_node — validé 2026-07-11) :
docker exec dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 topic pub --once /didier/animation robot_interfaces/msg/StringTime "{msg: \"\\\"parle\\\"\", time: 45000, anim: false}"'
# Arrêt d'animation : msg: "false" (booléen JSON — PAS "stop", qui serait cherché comme nom de séquence).
# Chaîne roues dans la sim :
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 launch robot_drive drive.launch.py use_sim_time:=true'
# Conduite clavier (publie /didier/cmd_vel_remote via remap, prioritaire) :
docker exec -it dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r __ns:=/didier -r cmd_vel:=cmd_vel_remote'
# Suivi de personne en sim (chaîne roues requise ; toggle topic `follow` on/off, OFF par défaut) :
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 run robot person_follower --ros-args -r __ns:=/didier'
# Perception scriptée pour le tester (personne à droite, loin, sûre) :
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && ros2 topic pub -r 16 /didier/vision/person_box geometry_msgs/msg/PointStamped "{point: {x: 0.5, y: 0.2, z: 0.9}}"'

# Salle de répétition (Didier chemine seul, SIM-ONLY) : WORLD=rue (60 m, V-R1/V-R2) ou
# WORLD=chantiers (Nefs → Titan grise, 20 bugs + 30 lubies, page scène http://localhost:8765/scene).
# Séance complète (sim + régisseur + tête vision + page) : docs/operations.md §Séance « Chantiers ».
# Vérif rejouable : docker exec dadou-sim-container bash /home/ros2_ws/validate-rehearsal-chantiers.sh
# Vérif du namespace (L1b ; sim démarrée avec ROBOT_NAME=didier2 puis sans) :
# docker exec dadou-sim-container bash /home/ros2_ws/validate-namespace.sh

# Déploiement robot : Ansible dans ../dadou_utils_ros (rsync du checkout local, PAS de git sur le Pi).
# ssh alias `r` = pi@robot. Logs applicatifs : /home/ros2_ws/log/robot.log DANS le conteneur (pas stdout docker).
# Sentinelle de build : créer le fichier robot/change déclenche colcon build au (re)démarrage.
```

## État et priorités

**Tableau de bord des chantiers : `docs/chantiers.md`** — statut, prochaine
action et verrous de CHAQUE chantier (web, télédiagnostic, suivi de personne,
gaze/arbitrage, pistes en veille). C'est LÀ que l'état se met à jour à chaque
lot — ce fichier-ci ne garde que les règles, les commandes et la tête de liste.
Le détail des décisions vit dans les `docs/etude-*.md` de chaque chantier.

Priorités de tête (l'ordre compte) :
0. **Protocole physique chat_node V2** — conversation complète sur le vrai
   matériel (le code est prêt et validé sim, jamais testé en réel).
1. **Refonte électrique** (`docs/hardware/plan-refonte-electrique.md`) — décidée le 05/11 AVANT tout roulage au sol : elle installe l'arrêt matériel.
2. **Test scénique au sol** — première fois que cmd_vel roule au sol,
   télécommande en main. C'est LE verrou des roues web réelles et du suivi
   de personne réel.

En parallèle (sans bousculer 0-1) : interface web (suite = W1 e_stop),
télédiagnostic (suite = étape 2 boîte noire + bouton START).

## Méthode de travail

- **Commenter chaque action en travaillant** (le quoi ET le pourquoi) : narration des
  étapes dans la conversation, commentaires français dans code/scripts/configs
  (les contraintes et pièges, pas la paraphrase), commits détaillés, découvertes
  consignées immédiatement. Raison : le projet doit pouvoir continuer avec un autre
  modèle (Opus) à tout moment — une action non expliquée est un fil perdu.
- Découpage modèles : conception/revue = modèle fort ; implémentation sur spec fermée =
  Agent Sonnet ; code sécurité = Agent Opus minimum ; mécanique = Haiku.
- Niveau d'effort en session Fable : **medium par défaut** (architecture, specs, revues,
  orchestration — le volume de raisonnement utile est modeste sur ce projet). Monter en
  **high** ponctuellement pour : conception d'un sous-système neuf (ros2_control,
  exécutif py_trees), débogage vraiment retors, revue finale d'un changement du chemin
  roues. `low` n'a pas d'intérêt : si la tâche est simple, autant basculer la session
  en Opus (moins cher que Fable bridé).
- La vérification doit exécuter le MÊME code que la prod (pas de reproduction approximative).
- CI GitHub Actions minimale (le repo est public : jamais de secrets, historique déjà purgé).
- Mémoire de session détaillée dans ~/.claude/projects/.../memory/ (chargée automatiquement).
