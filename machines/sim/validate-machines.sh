#!/bin/bash
# L2b — preuve REJOUABLE que les machines de Didier sont toutes là et se parlent, dans la sim
# multi-conteneurs (spec docs/spec-L2-sim-multi-conteneurs.md, décision 21), DANS le conteneur
# `monde` (domaine 43) : le graphe est vu d'ICI, pas depuis chaque conteneur.
#   M1 les noeuds_attendus du robot (machines/robot/machine.yml, monté en lecture seule) sont
#      dans le graphe ;
#   M2 idem vision (machines/vision/machine.yml) ;
#   M3 /<robot>/controller_node (télécommande actuelle) est dans le graphe ;
#   M4 vision/status : au moins 2 messages en 15 s ;
#   M6 controller_node a un éditeur sur `animation` (get_publishers_info_by_topic).
# L2c ajoutera M5 (l'image traverse monde -> vision -> robot) et M7-M10 (états du matériel simulé).
# rclpy seulement, jamais `ros2 topic echo` (la CLI perd des messages sur ce PC, operations.md).
# Ligne finale : « === validate-machines : N OK, K KO ». Sortie 0 = OK ; 1 = KO ; 2 = banc faux.
# Ne lance rien, n'écrit rien. Refus hors domaine 43.
source /opt/ros/${ROS_DISTRO}/setup.sh
source /home/ros2_ws/install/setup.bash
NS="/${ROBOT_NAME:-didier}"
export NS
MACHINES=${MACHINES:-/home/ros2_ws/machines}
export MACHINES
[ "${ROS_DOMAIN_ID:-}" = 43 ] || { echo "REFUS : ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-absent}, ce script ne tourne qu'en simulation (43)"; exit 2; }
for m in robot vision; do
  [ -r "$MACHINES/$m/machine.yml" ] || { echo "PRÉCONDITION : $MACHINES/$m/machine.yml illisible (machines/ monté dans monde ?)"; exit 2; }
done

echo "=== machines de la sim sous $NS/ $(date +%T) ==="
python3 - <<'PY'
import os, sys, time
import rclpy
import yaml
from std_msgs.msg import String

NS = os.environ["NS"]
MACHINES = os.environ["MACHINES"]
# Découverte : ≥ 5 s (3 s comptent trop peu de nœuds, vu en L2a), puis jusqu'à 30 s si incomplet.
DECOUVERTE_MIN_S, DECOUVERTE_MAX_S = 5.0, 30.0
STATUS_FENETRE_S, STATUS_MIN = 15.0, 2

ok = ko = 0
def verdict(bon, texte):
    global ok, ko
    print(("  ✅ " if bon else "  ❌ ") + texte, flush=True)
    if bon:
        ok += 1
    else:
        ko += 1

def attendus(machine):
    with open(os.path.join(MACHINES, machine, "machine.yml"), encoding="utf-8") as f:
        return list(yaml.safe_load(f)["noeuds_attendus"])

rclpy.init()
node = rclpy.create_node("validate_machines", namespace=NS)

def graphe():
    return {(ns.rstrip("/") + "/" + nom) for nom, ns in node.get_node_names_and_namespaces()}

robot, vision = attendus("robot"), attendus("vision")
telecommande = NS + "/controller_node"
voulus = set(robot) | set(vision) | {telecommande}
debut = time.monotonic()
while True:
    rclpy.spin_once(node, timeout_sec=0.2)
    vus = graphe()
    ecoule = time.monotonic() - debut
    if ecoule >= DECOUVERTE_MAX_S or (ecoule >= DECOUVERTE_MIN_S and voulus <= vus):
        break
print("  %d nœuds vus en %.0f s" % (len(vus), ecoule), flush=True)

manque = sorted(set(robot) - vus)
verdict(not manque, "M1 robot : %d nœuds attendus (machines/robot/machine.yml)%s"
        % (len(robot), " — manquent : " + " ".join(manque) if manque else ""))
manque = sorted(set(vision) - vus)
verdict(not manque, "M2 vision : %d nœud(s) attendu(s) (machines/vision/machine.yml)%s"
        % (len(vision), " — manquent : " + " ".join(manque) if manque else ""))
verdict(telecommande in vus, "M3 télécommande : %s %s" % (telecommande, "présent" if telecommande in vus else "ABSENT"))

recus = []
node.create_subscription(String, "vision/status", lambda m: recus.append(m.data), 10)
fin = time.monotonic() + STATUS_FENETRE_S
while time.monotonic() < fin:
    rclpy.spin_once(node, timeout_sec=0.2)
verdict(len(recus) >= STATUS_MIN, "M4 %s/vision/status : %d message(s) en %.0f s (≥ %d)"
        % (NS, len(recus), STATUS_FENETRE_S, STATUS_MIN))

editeurs = node.get_publishers_info_by_topic(NS + "/animation")
noms = sorted("%s/%s" % (i.node_namespace.rstrip("/"), i.node_name) for i in editeurs)
verdict(telecommande in noms, "M6 %s/animation : éditeurs %s (attendu : %s)" % (NS, noms or "aucun", telecommande))

node.destroy_node()
rclpy.shutdown()
print("=== validate-machines : %d OK, %d KO %s ===" % (ok, ko, time.strftime("%H:%M:%S")), flush=True)
sys.exit(0 if ko == 0 else 1)
PY
