# machines/sim

Le PC de David : les bancs de simulation et leurs épreuves (lot L1e-4c, 11/11 ; ex partie sim de
`legacy/dadou_robot_ros/conf/` et banc x86 de la vision). Rien d'ici ne part sur un Pi. Domaine
ROS **43** (le vrai robot est sur 42). En L2, un compose lancera un conteneur par machine.

| Chemin | Rôle |
|---|---|
| `banc-robot/docker-compose-sim.yml`, `Dockerfile-sim` | la sim Gazebo (`cd machines/sim/banc-robot && HEADLESS=true docker compose -f docker-compose-sim.yml up -d`) ; `GZ_IP=127.0.0.1` obligatoire (A1 intermittent, 11/11) |
| `banc-robot/docker-compose-x86.yml`, `Dockerfile-x86` | ancien banc de bureau du robot (conf en contexte nommé `conf` = `../../robot`) |
| `banc-vision/` | perception + parole réelles sur le PC (`./build-x86.sh`, puis `CHAT=true docker compose -f docker-compose-x86.yml up -d`), `audio_banc.py` |
| `launch-sim-in-docker.sh` | entrée du conteneur sim (copiée dans l'image et montée) |
| `validate-{namespace,catalogue,rehearsal-*,jeu-a1}.sh`, `pub.sh` | épreuves rejouables, montées dans `/home/ros2_ws/` du conteneur sim |
| `fumee.sh`, `fumee_page.py`, `coeurs_reserves.py` | fumée nocturne (lot F) : rejoue tout sur main, pages `docs/fumee/` |
| `didier-fumee.{service,timer}`, `installer-fumee.sh` | minuterie systemd utilisateur ; **relancer `installer-fumee.sh` depuis le checkout de main** après un déménagement |

Mode d'emploi : `legacy/dadou_robot_ros/docs/operations.md` (sections Sim, Séance « Chantiers »,
Fumée automatique).
