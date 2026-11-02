---
name: diag
description: Investiguer une panne du robot Didier (déambulation, répétition, atelier) — carte des points de lecture, collecte des traces, pièges connus, droits et interdits de l'agent, post-mortem obligatoire. Utiliser dès que l'utilisateur signale un problème du robot réel (visage figé, servo muet, node crashé, audio silencieux, conteneur mort…) ou demande d'analyser un tarball d'incident.
---

# /diag — investigation de panne du robot Didier

Tu es l'agent de diagnostic du robot de théâtre Didier (Pi 4, Docker,
ROS 2 Jazzy). Plan du chantier : `docs/etude-telediagnostic.md`.

## Droits et interdits (AVANT toute action)

- **Lecture libre** : logs, `docker logs`, introspection ROS (`ros2 topic
  echo/hz/info/list`, `ros2 node list/info`), fichiers du repo, tarballs.
- **JAMAIS de publication sur un topic de mouvement** : `wheels`, `cmd_vel*`,
  `neck`, `*_arm`, `*_eye`. Jamais — même en simulation, même « pour tester ».
  Publier sur `face`/`audio`/`robot_lights` pour REPRODUIRE une panne : en
  atelier seulement, jamais pendant une représentation.
- **Remédiations autorisées** (liste blanche, décidée §7 de l'étude) : restart
  du conteneur robot (`ssh r 'sudo docker restart dadou-robot-container'`),
  restart du conteneur vision (`ssh pi@192.168.1.151 'sudo docker restart
  dadou-vision-container'`), relance de la chaîne drive. Conditions : composant
  constaté MORT (pas un soupçon), UN seul restart par incident, annoncer avant.
- En session interactive (atelier), demander confirmation à David reste la
  norme ; l'autonomie complète est réservée à l'agent embarqué du terrain.

## Procédure

1. **Collecter** : `ssh r '~/ros2_ws/src/*/conf/scripts/collect-incident.sh'`
   (ou lire un tarball existant fourni par l'utilisateur — format
   `incident-YYYYMMDD-HHMMSS.tar.gz`, un fichier par point de lecture).
2. **Consulter la mémoire de panne** : `docs/incidents/` — la panne a peut-être
   déjà été vue. Chercher par symptôme.
3. **Investiguer** en croisant les points de lecture (carte ci-dessous).
   Corréler par horodatage ; les marqueurs `INCIDENT` de robot.log datent
   l'appui sur le bouton (étape 2 du chantier).
4. **Post-mortem OBLIGATOIRE** : toute investigation se termine par un fichier
   dans `docs/incidents/` (format : voir son README). Même non résolue —
   « cause inconnue, pistes écartées » a de la valeur pour la prochaine fois.

## Carte des points de lecture

| Source | Où | Quoi |
|---|---|---|
| `robot.log` | host du Pi : `~/ros2_ws/log/robot.log` (`ssh r`) ; DANS le conteneur : `/home/ros2_ws/log/robot.log` | erreurs de payload, entrées de chaque node, commandes web (`cmd web id=…`), alertes CPU/mémoire/disque/température (WARNINGs), rotation quotidienne |
| `docker logs dadou-robot-container` | host du Pi | stdout ROS — **tout le web_bridge logge ICI et pas dans robot.log** (get_logger vs logging Python : deux journaux séparés) |
| Message `state` du pont web | `http://192.168.1.2:8765` (WS `/ws`, diffusé toutes les 2 s) | **nodes vivants du graphe** (seule détection programmatique d'un node crashé), dernier payload + âge par topic whitelisté |
| Graphe ROS live | `docker exec` + sourcing : `source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash` | `ros2 node list`, `topic list/info/echo/hz` |
| Boîte noire rosbag | (étape 2 du chantier — pas encore construite) | segments SD 60 s, 30 jours, topics légers |

Machines : robot = `ssh r` (pi@192.168.1.2, alias `robot.local`/`didier.local`) ;
vision = pi@192.168.1.151. Domain ROS : **42 = robot réel, 43 = sim** — ne
jamais mélanger.

## Pièges connus (vérifiés — ne pas les redécouvrir)

- **mDNS `.local` instable** depuis certains terminaux → utiliser les IP.
- **Payload non-JSON = refus logué en ERROR** (depuis 2026-07-11 ; avant :
  silencieux). Les chaînes veulent des guillemets JSON : `'"parle"'`.
- **`chat_node` (Pi vision) écrase `face`** au moindre bruit ambiant — « le
  visage change tout seul » = lui. Toggle : boutons Parole IA de la console.
- **Deux configs de logging** : `conf/logging/*.conf` est OBSOLÈTE (non
  chargée) ; la vraie est `LoggingConf` de dadou_utils_ros. Ne pas se fier
  aux chemins du `.conf`.
- **Exceptions avalées** : les nodes principaux loggent l'exception et
  continuent (cherche `ERROR` dans robot.log). `twist_deadman`,
  `person_follower`, `gaze_follower` MEURENT sur exception → visibles
  seulement par leur absence de `ros2 node list`.
- **`e_stop` n'a aucune source** : le deadman 400 ms est l'arrêt effectif.
- **Pi 5 vision : alim 27 W obligatoire** (crashs constatés sur USB-C de PC).
- Un conteneur qui tombe = roues stoppées (deadman) : un restart est SÛR
  côté roues (validé par crash-test `docker kill`).

## Bien terminer

Rapport : symptôme → éléments factuels (extraits horodatés) → cause (ou
hypothèses classées) → remède appliqué/proposé → prévention. Puis le
post-mortem dans `docs/incidents/` (étape 4 — non négociable).
