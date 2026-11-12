#!/bin/bash
# L1d-2 — porte sim, PAR LOT, sans page (spec docs/spec-L1-contrats-donnees.md, « L1d »,
# décision 7 bis) : rejoue en simulation tout ce que `donnees.a_rejouer(data/)` rend (séquences,
# expressions, lumières modifiées depuis leur dernier tampon), un élément à la fois, et affiche
# OK / KO puis ce qui reste à valider à l'œil (pistes roues : bouton « Valider les roues pour
# le robot » de la page scène).
#
# AUCUNE logique propre : c'est l'observateur validation_sim_node (lancé par sim.launch.py) qui
# décide et écrit le registre data/json/validations-sim.json ; ce script ne fait que jouer et
# attendre son verdict sur `validation_sim`.
#
#   machines/sim/rejouer-modifiees.sh            # depuis le PC, n'importe quel dossier
#
# - Sim absente : démarrée sans écran DEPUIS CET ARBRE (domaine 43, ANIMATIONS=true FACE=true
#   WEB=true), et LAISSÉE EN MARCHE à la fin (la page sert à valider les roues). Arrêt :
#   cd machines/sim/banc-robot && docker compose -f docker-compose-sim.yml down
# - Sim présente : utilisée seulement si elle monte le data/ de CET arbre, en domaine 43, avec
#   ANIMATIONS=true et FACE=true ; sinon refus (code 2), rien n'est joué.
# - La chaîne roues (drive.launch.py) est lancée si elle manque (le critère roues est « cmd_vel
#   nul 1 s après la fin »), et arrêtée en sortant si c'est nous qui l'avons lancée.
# - Avant chaque élément, un verdict de rechargement est publié sur data_edit_result (même forme
#   que celui de data_edit_node : il ne porte aucun contenu, il fait relire le fichier) : une
#   retouche faite à la main pendant que la sim tourne est bien celle qui est jouée.
# Sortie : 0 = tout rejoué (reste éventuellement des roues à valider, affichées) ; 1 = au moins
# un KO ; 2 = banc faux. Rien ici ne peut atteindre le vrai robot : domaine 43 exigé.
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPOT="$(cd "$ICI/../.." && pwd)"
DOCKER_DIR="$ICI/banc-robot"
CONTENEUR=dadou-sim-container
DRIVE_PID_FICHIER=/tmp/rejouer-modifiees-drive.pid

dit() { echo "[rejouer $(date +%T)] $*"; }
ros_dans() { docker exec "$CONTENEUR" bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && '"$1"; }

non_validees() { PYTHONPATH="$DEPOT/packages/theatre_contrats" python3 -m theatre_contrats.donnees non-validees "$DEPOT/data" || true; }

# --- 0. rien à faire ? (lu sur le PC, même module que la garde de déploiement ; il sort en 1
# quand la liste n'est pas vide, d'où la capture plutôt qu'un tube sous pipefail)
etat="$(non_validees)"
if ! grep -q "^à rejouer en sim" <<<"$etat"; then
  dit "rien à rejouer en sim."
  echo "$etat"
  exit 0
fi

# --- 1. la sim : celle de cet arbre, en domaine 43, ou démarrée ici
env_de() { docker inspect "$CONTENEUR" --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n "s/^$1=//p"; }
if docker ps --format '{{.Names}}' | grep -qx "$CONTENEUR"; then
  monte="$(docker inspect "$CONTENEUR" --format '{{range .Mounts}}{{if eq .Destination "/home/ros2_ws/src/robot/json"}}{{.Source}}{{end}}{{end}}')"
  if [ "$monte" != "$DEPOT/data/json" ]; then
    echo "REFUS : la sim qui tourne monte $monte, pas $DEPOT/data/json (autre arbre)."; exit 2
  fi
  for v in ROS_DOMAIN_ID=43 ANIMATIONS=true FACE=true; do
    [ "$(env_de "${v%%=*}")" = "${v#*=}" ] || { echo "REFUS : sim lancée sans $v (relancer avec ANIMATIONS=true FACE=true)"; exit 2; }
  done
  dit "sim présente (cet arbre, domaine 43)"
else
  dit "démarrage de la sim sans écran (domaine 43, colcon ≈ 1 min)"
  # ROS_DOMAIN_ID forcé ICI : le compose le lirait dans l'environnement de l'appelant.
  (cd "$DOCKER_DIR" && env ROS_DOMAIN_ID=43 ROBOT_NAME=didier HEADLESS=true ANIMATIONS=true FACE=true \
      WEB=true DATA_EDIT=false REHEARSAL=false WEB_DRIVE=false \
      docker compose -f docker-compose-sim.yml up -d) >/tmp/rejouer-modifiees-demarrage.log 2>&1 \
    || { echo "démarrage de la sim impossible : /tmp/rejouer-modifiees-demarrage.log"; exit 2; }
  [ "$(docker exec "$CONTENEUR" printenv ROS_DOMAIN_ID)" = 43 ] || { echo "REFUS : domaine ≠ 43 dans le conteneur"; exit 2; }
  t0=$SECONDS
  until docker exec "$CONTENEUR" pgrep -f parameter_bridge >/dev/null 2>&1; do
    if docker logs "$CONTENEUR" 2>&1 | grep -qE 'Failed +<<<|packages? failed'; then echo "colcon build a échoué (docker logs $CONTENEUR)"; exit 2; fi
    [ $((SECONDS - t0)) -lt 360 ] || { echo "sim pas prête après 360 s (docker logs $CONTENEUR)"; exit 2; }
    sleep 3
  done
  sleep 15   # le monde se charge
  dit "sim prête en $((SECONDS - t0)) s (laissée en marche à la fin)"
fi
[ "$(docker exec "$CONTENEUR" printenv ROS_DOMAIN_ID)" = 43 ] || { echo "REFUS : domaine ≠ 43"; exit 2; }

# --- 2. la chaîne roues, si elle manque (arrêtée en sortant si c'est nous)
DRIVE_A_NOUS=0
arreter_drive() {
  [ "$DRIVE_A_NOUS" = 1 ] || return 0
  # Groupe de processus lancé par setsid, tué par son PID noté (jamais par motif).
  docker exec "$CONTENEUR" bash -c 'p=$(cat '"$DRIVE_PID_FICHIER"' 2>/dev/null) && kill -INT -- -$p 2>/dev/null; sleep 3; kill -KILL -- -$p 2>/dev/null; rm -f '"$DRIVE_PID_FICHIER"'; true'
  dit "chaîne roues arrêtée"
}
trap arreter_drive EXIT
if ! docker exec "$CONTENEUR" pgrep -f "/twist_deadman( |$)" >/dev/null 2>&1; then
  ros_dans 'setsid ros2 launch didier_drive drive.launch.py use_sim_time:=true >/tmp/rejouer-modifiees-drive.log 2>&1 & echo $! >'"$DRIVE_PID_FICHIER"
  DRIVE_A_NOUS=1
  dit "chaîne roues lancée (journal /tmp/rejouer-modifiees-drive.log dans le conteneur)"
  sleep 5
fi

# --- 3. rejeu, un élément à la fois ; l'observateur juge
code=0
docker exec -i -e NS="/didier" "$CONTENEUR" bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && python3 -' <<'PY' || code=$?
import json, os, sys, time
import rclpy
from theatre_interfaces.msg import StringTime
from theatre_contrats import donnees, qos, topics

DATA = "/home/ros2_ws/src/robot"
NS = os.environ["NS"]
ATTENTE_NOEUDS = ("animation_node", "face_sim_node", "leds_sim_node", "validation_sim_node", "twist_deadman")

rclpy.init()
node = rclpy.create_node("rejouer_modifiees", namespace=NS)
verdicts = []
node.create_subscription(StringTime, topics.VALIDATION_SIM, lambda m: verdicts.append(json.loads(m.msg)),
                         qos.volatile(10))
pub = {t: node.create_publisher(StringTime, t, 10) for t in (topics.ANIMATION, topics.FACE, topics.ROBOT_LIGHTS)}
pub_recharge = node.create_publisher(StringTime, topics.DATA_EDIT_RESULT, qos.volatile(10))

def tourner(secondes, condition=lambda: False):
    fin = time.monotonic() + secondes
    while time.monotonic() < fin:
        rclpy.spin_once(node, timeout_sec=0.05)
        if condition():
            return True
    return condition()

def noeuds():
    return {n for n, ns in node.get_node_names_and_namespaces() if ns == NS}

if not tourner(60, lambda: set(ATTENTE_NOEUDS) <= noeuds()):
    print("PRÉCONDITION : nœuds absents : {}".format(sorted(set(ATTENTE_NOEUDS) - noeuds())), flush=True)
    sys.exit(2)
tourner(10, lambda: all(p.get_subscription_count() > 0 for p in [pub_recharge, *pub.values()]))

compteur = [0]
def recharger(kind, name):
    compteur[0] += 1
    v = {"id": "rejouer-{}-{}".format(os.getpid(), compteur[0]), "ok": True, "code": "ok",
         "detail": ["rechargement demandé par rejouer-modifiees.sh"], "kind": kind, "name": name,
         "mode": "replace", "sha256": None, "sauvegarde": None, "avertissements": []}
    pub_recharge.publish(StringTime(msg=json.dumps(v), time=0, anim=False))

def lire(relatif):
    with open(os.path.join(DATA, relatif), encoding="utf-8") as f:
        return json.load(f)

a_rejouer = donnees.a_rejouer(DATA)
print("{} élément(s) à rejouer, durée de jeu ≈ {:.0f} s".format(len(a_rejouer), sum(
    lire("json/sequences/{}.json".format(n)).get("duration", 0) / 1000 if k == "sequence" else 10
    for k, n in a_rejouer)), flush=True)
ok = ko = 0
t_debut = time.monotonic()
for i, (kind, name) in enumerate(a_rejouer, 1):
    if kind == "sequence":
        duree = lire("json/sequences/{}.json".format(name)).get("duration", 0)
        topic, valeur, attente = topics.ANIMATION, name.split("/")[-1], duree / 1000 + 20
        recharger("sequence", name)
    else:
        entree = lire(donnees.FICHIERS_A_ENTREES[kind])[name]
        attente = min(entree.get("duration", 10000), 10000) / 1000 + 10
        topic, valeur = (topics.FACE, name) if kind == "expression" else (topics.ROBOT_LIGHTS, name)
        recharger(kind, name)
        if kind == "expression":
            for piste, zone in donnees.PISTES_VISAGE.items():
                for k in entree.get(piste) or []:
                    image = "{}/{}".format(zone, str(k[1]).rsplit(".png", 1)[0])
                    if donnees.nom_valide("image", image):
                        recharger("image", image)
    tourner(1.5)   # rechargement fait, et une commande précédente bien finie
    vus = len(verdicts)
    attendu = name if kind != "sequence" else None
    def le_notre(v):
        if v.get("kind") != kind or "id" in v:
            return False
        return v.get("name") in (name, valeur) if kind == "sequence" else v.get("name") == attendu
    pub[topic].publish(StringTime(msg=json.dumps(valeur), time=0, anim=False))
    tourner(attente, lambda: any(le_notre(v) for v in verdicts[vus:]))
    v = next((v for v in verdicts[vus:] if le_notre(v)), None)
    if v is None:
        ko += 1
        print("  [{}/{}] KO {} {} : pas de verdict de l'observateur en {:.0f} s".format(i, len(a_rejouer), kind, name, attente), flush=True)
    elif v["ok"]:
        ok += 1
        print("  [{}/{}] OK {} {} ({})".format(i, len(a_rejouer), kind, name, v["code"]), flush=True)
    else:
        ko += 1
        print("  [{}/{}] KO {} {} : {} {}".format(i, len(a_rejouer), kind, name, v["code"], v["detail"][:3]), flush=True)
    if kind == "sequence" and v is not None and v["code"] in ("homonyme", "absente"):
        tourner(duree / 1000 + 1)   # jugée dès le départ : on laisse la séquence finir avant la suivante
    if kind != "sequence":
        # Une expression ou une lumière en boucle resterait affichée : on rend la main.
        pub[topic].publish(StringTime(msg=json.dumps("stop"), time=0, anim=False))

node.destroy_node()
rclpy.shutdown()
print("=== rejouer-modifiees : {} OK, {} KO en {:.0f} s ===".format(ok, ko, time.monotonic() - t_debut), flush=True)
sys.exit(0 if ko == 0 else 1)
PY
echo
dit "reste à valider (lu dans data/ du PC) :"
non_validees
echo "Pistes roues : page scène (http://localhost:8765/scene), « Valider les roues pour le robot »."
exit $code
