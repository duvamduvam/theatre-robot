#!/bin/bash
# OBJ — épreuves du TABLEAU DES OBJETS (lot O1, 18/11 ; étude docs/etudes/etude-objets-vus-et-carte.md
# §10, épreuves 1, 2 et 4), DANS le conteneur `monde` : monde `chantiers`, vrai bringup du robot,
# rehearsal.launch.py route:=chantiers scenario:=jeu-a1 jeu:=true (régisseur + sélecteur de jeu),
# objets_node dans le conteneur `vision` (vision.launch.py). ZÉRO jeton : pas de tête ; le pilote
# joue la BOUCHE en publiant sur rehearsal/chat_move ce que chat_node publierait : le geste passe
# par LA garde de la bouche, theatre_contrats.objets.garde_geste — le code même qu'appelle
# chat_node (ConversationEngine._local_refusal), pas une copie (revue O1, 19/11) — sur le tableau
# capturé ; l'id résolu est joint comme le fait chat_node. Séance NON
# démarrée, route jamais coupée par commande (cause « boot ») : le régisseur accepte les gestes,
# et le « go » de reprise du sélecteur est ignoré hors séance — Didier ne repart pas seul.
#
# E1 « montre-moi le banc », il est là : Didier à (32,5 ; 0), cap 25° ; aller_voir banc
#   E1a le tableau dit le banc ICI, atteignable, à 4,5 m (± 0,3)
#   E1b la garde de la bouche le laisse passer ; l'ordre du sélecteur (jeu/chat_move) et la réponse
#       du régisseur portent l'id « carte/banc », accepté ; route_goto vise la position du TABLEAU
#       (36,2 ; 2,496), standoff 2,5 = emprise du banc 1,1 + garde du corps sûr 0,90 + marge 0,5
#       (A0-4, 22/11 : hors de la bande ARRET ; revue O1 : 2,1 = 1,1 + Didier 0,5 + 0,5)
#   E1c arrivée (route_goto_result « arrived » du même ordre) en ≤ 60 s
#   E1d arrêt à 2,5 m ± 0,3 du centre (36,2 ; 2,496) ET SANS CONTACT : au moins 0,2 m de jeu entre
#       l'emprise du banc (1,1) et le rayon balayé de Didier (0,5), soit ≥ 1,8 m du centre — à
#       1,6 m ils se touchent, KO (revue O1 : l'ancienne borne, 1,2 m, acceptait un contact).
#       Pose FINALE : goto.py ne recule jamais et finit par un pivot sur place (FACE) — le centre
#       de Didier n'est jamais plus près de l'objet qu'à l'arrêt.
#   E1e face à lui (± 10°)
# E2 « le banc », il n'est pas là (la séance du 15/11) : Didier à (14 ; 0), cap 0 ; la demande part
#    quand même sur rehearsal/chat_move (une bouche dont la garde aurait sauté : on éprouve la
#    SECONDE ligne, le sélecteur ; la garde du chat est éprouvée par les tests unitaires de
#    didier_vision, test_aller_voir_le_banc_a_22_m_jamais_publie_et_dit_ou_il_est)
#   E2a le tableau dit le banc PAS ICI, 22,3 m (± 0,3) devant, ni en vue ni atteignable
#   E2b réponse du sélecteur : dropped / pas_ici, distance_m 22,3 (± 0,3), côté devant, en ≤ 1 s
#   E2c zéro ordre : rien sur jeu/chat_move ni route_goto pour ce geste
#   E2d zéro roue : cmd_vel_follow nul et moins de 0,05 m parcourus en 8 s
#   E2e la GARDE de la bouche (garde_geste, le code de chat_node), sur le tableau de la sim, refuse
#       « le banc » : dropped / pas_ici, 22,3 m devant — la PREMIÈRE ligne, celle qu'on contourne
#       ensuite pour éprouver la seconde
# E4 une seule vérité, 10 gestes (aller_voir et tour_de, noms et alias), Didier replacé à (14 ; 0)
#    avant chacun, un geste toutes les 12 s (lot S1 : un geste de la bouche est un ordre, sans
#    réfractaire ; l'écart de 12 s est gardé)
#   E4a les 10 gestes acceptés par le régisseur
#   E4b même id dans la demande de la bouche, l'ordre du sélecteur (jeu/chat_move) et la réponse du
#       régisseur, pour les 10
#   E4c même id dans le journal du sélecteur (ordre, lot S1 ; « offre » avant) et celui du régisseur
#       (aller_voir / tour_de)
source /opt/ros/${ROS_DISTRO}/setup.sh
source /home/ros2_ws/install/setup.bash
NS="/${ROBOT_NAME:-didier}"
source /home/ros2_ws/captures.sh
RDIR=/home/ros2_ws/log/rehearsal

# --- PRÉCONDITIONS (banc faux = code 2, jamais un verdict) ------------------------------------
for proc in jeu_node route_driver director twist_deadman objets_node; do
  pgrep -f "/$proc\$|/$proc " >/dev/null || { echo "PRÉCONDITION : processus « $proc » absent (rehearsal.launch.py jeu:=true ? vision.launch.py ?)"; exit 2; }
done
pgrep -af "lib/didier_rehearsal/[d]irector" | grep -q "rehearsal/chat_move:=jeu/chat_move" || { echo "PRÉCONDITION : le régisseur n'est pas remappé sur jeu/chat_move (rehearsal.launch.py jeu:=true)"; exit 2; }
timeout 10 gz model --list 2>/dev/null | grep -q titan_grise || { echo "PRÉCONDITION : modèle titan_grise absent (WORLD=chantiers ?)"; exit 2; }
RJ=$(ls -t $RDIR/*_jeu-a1.jsonl 2>/dev/null | head -1)
rpid=$(basename "$RJ" 2>/dev/null | cut -d_ -f3)
[ -n "$rpid" ] && kill -0 "$rpid" 2>/dev/null || { echo "PRÉCONDITION : aucun régisseur vivant avec le scénario jeu-a1"; exit 2; }

capture_demarrer objets \
  --journal $NS/jeu/chat_move=theatre_interfaces/msg/StringTime \
  --journal $NS/rehearsal/chat_move_reply=theatre_interfaces/msg/StringTime \
  --journal $NS/route_goto=theatre_interfaces/msg/StringTime \
  --journal $NS/route_goto_result=theatre_interfaces/msg/StringTime \
  --journal $NS/jeu/journal=theatre_interfaces/msg/StringTime \
  --journal $NS/cmd_vel_follow=geometry_msgs/msg/Twist \
  --dernier $NS/scene/objets=theatre_interfaces/msg/StringTime,latche \
  --dernier $NS/route_state=theatre_interfaces/msg/StringTime,latche \
  --dernier $NS/ground_truth/odom=nav_msgs/msg/Odometry

echo "=== OBJ : pilote (E1, E2, E4) $(date +%T) ==="
python3 - "$CAP" "$NS" <<'EOF'
"""Pilote : AGIT seulement (téléporte, publie comme la bouche) ; il lit les captures de
l'enregistreur pour décider QUAND agir, jamais par une souscription à lui."""
import json, math, subprocess, sys, time
from pathlib import Path
import rclpy
from rclpy.node import Node
from theatre_interfaces.msg import StringTime
from theatre_contrats import objets

CAP, NS = Path(sys.argv[1]), sys.argv[2]
ESPACEMENT_S = 12.0          # > refractaire_s.deplacement (10 s) du sélecteur
# 10 gestes vus de (14 ; 0) cap 0 : objets à portée (carrousel 2,2 m, table_basse 4,3, elephant 5,6,
# poster_bizarre 8,8 ; tours : table_basse, poster_bizarre), noms ET alias de chantiers.yaml.
GESTES = [("aller_voir", "carrousel", None), ("aller_voir", "la table basse", None),
          ("tour_de", "table_basse", "gauche"), ("aller_voir", "éléphant", None),
          ("aller_voir", "poster", None), ("tour_de", "poster_bizarre", "droite"),
          ("aller_voir", "manège", None), ("aller_voir", "petite table", None),
          ("aller_voir", "affiche", None), ("tour_de", "la table basse", "droite")]
marques = {"gestes": []}


class Echec(Exception):
    pass


def dernier(topic):
    try:
        return json.loads((CAP / "dernier" / (NS + "/" + topic).strip("/").replace("/", "__")
                           ).with_suffix(".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def pose():
    d = dernier("ground_truth/odom")
    if d is None:
        return None
    p = d["payload"]["pose"]["pose"]
    q = p["orientation"]
    cap = math.atan2(2.0 * (q["w"] * q["z"] + q["x"] * q["y"]), 1.0 - 2.0 * (q["y"] ** 2 + q["z"] ** 2))
    return p["position"]["x"], p["position"]["y"], math.degrees(cap)


def tableau():
    d = dernier("scene/objets")
    return objets.decoder(d["payload"]["msg"]) if d else None


class Pilote(Node):
    def __init__(self):
        super().__init__("validate_objets", namespace=NS)
        self.pub = self.create_publisher(StringTime, "rehearsal/chat_move", 10)
        self.pret = False

    def dormir(self, s):
        fin = time.monotonic() + s
        while time.monotonic() < fin:
            rclpy.spin_once(self, timeout_sec=min(0.1, max(0.0, fin - time.monotonic())))

    def attendre(self, cond, delai, quoi):
        fin = time.monotonic() + delai
        while time.monotonic() < fin:
            if cond():
                return
            self.dormir(0.2)
        raise Echec(f"{quoi} : pas dans les {delai:g} s")

    def bouche(self, intent):
        """UN message sur rehearsal/chat_move (comme chat_node), après appariement du sélecteur."""
        if not self.pret:
            self.attendre(lambda: self.pub.get_subscription_count() >= 1, 10, f"abonné de {NS}/rehearsal/chat_move")
            self.dormir(1.0)    # découverte DDS asymétrique : 1 s de grâce au premier usage
            self.pret = True
        self.pub.publish(StringTime(msg=json.dumps(intent, ensure_ascii=False), time=0, anim=False))
        return time.time()

    def placer(self, x, y, cap_deg):
        """Téléporte Didier puis attend que la pose ET le tableau l'aient vu (≤ 10 s)."""
        yaw = math.radians(cap_deg)
        req = (f'name: "dadou_robot", position: {{x: {x}, y: {y}, z: 0.3}}, '
               f'orientation: {{z: {math.sin(yaw / 2)}, w: {math.cos(yaw / 2)}}}')
        subprocess.run(["timeout", "10", "gz", "service", "-s", "/world/stage/set_pose", "--reqtype", "gz.msgs.Pose",
                        "--reptype", "gz.msgs.Boolean", "--timeout", "3000", "--req", req], capture_output=True)

        def vu():
            p, t = pose(), tableau()
            return (p is not None and math.hypot(p[0] - x, p[1] - y) < 0.3 and t is not None and t.pose is not None
                    and math.hypot(t.pose.x - x, t.pose.y - y) < 0.3)
        self.attendre(vu, 10, f"Didier placé en ({x} ; {y}) et vu par le tableau")
        self.dormir(1.5)        # le tableau republie (1 Hz) une pose posée


def resolu(texte, cmd, sens=None):
    """LA garde de la bouche (objets.garde_geste, appelée telle quelle par chat_node) sur le
    tableau capturé ; l'id est joint si elle laisse passer — exactement ce que publie chat_node."""
    t = tableau()
    intent = {"cmd": cmd, "objet": texte}
    if sens:
        intent["sens"] = sens
    garde = objets.garde_geste(t, intent)
    o = garde.objet
    if garde.effect is None:
        intent["id"] = o.id
    return intent, {"statut": t.resoudre(texte).statut, "garde": [garde.effect, garde.reason],
                    "id": o and o.id, "distance_m": o and o.distance_m, "cote": o and o.cote,
                    "en_vue": o and o.en_vue, "atteignable": o and o.atteignable, "tour": o and o.tour,
                    "emprise_m": o and o.emprise_m}


rclpy.init()
n = Pilote()
try:
    n.attendre(lambda: tableau() is not None and len(tableau().objets) >= 20, 30, "tableau des objets (carte reçue)")
    # E1 — le banc est là.
    n.placer(32.5, 0.0, 25.0)
    intent, vu = resolu("banc", "aller_voir")
    marques["e1_tableau"] = vu
    if "id" not in intent:
        raise Echec(f"E1 « banc » : la garde de la bouche le refuse ({vu})")
    marques["e1"] = n.bouche(intent)
    marques["e1_intent"] = intent
    print(f"  {time.strftime('%T')} E1 aller_voir banc publié ({vu})", flush=True)
    n.attendre(lambda: dernier("route_state") and dernier("route_state")["payload"]["msg"].strip('"') == "arrived",
               70, "arrivée devant le banc")
    n.dormir(2.0)
    marques["e1_pose"] = pose()
    marques["e1_fin"] = time.time()

    # E2 — le banc n'est pas là (x = 14).
    n.dormir(max(0.0, ESPACEMENT_S - (time.time() - marques["e1"])))
    n.placer(14.0, 0.0, 0.0)
    _intent, vu = resolu("le banc", "aller_voir")
    marques["e2_tableau"] = vu
    marques["e2_p0"] = pose()
    marques["e2"] = n.bouche({"cmd": "aller_voir", "objet": "le banc", "id": "carte/banc"})
    print(f"  {time.strftime('%T')} E2 aller_voir le banc publié depuis x = 14 ({vu})", flush=True)
    n.dormir(8.0)
    marques["e2_p8"] = pose()
    marques["e2_fin"] = time.time()

    # E4 — dix gestes, une seule vérité.
    for cmd, texte, sens in GESTES:
        n.placer(14.0, 0.0, 0.0)
        intent, vu = resolu(texte, cmd, sens)
        if "id" not in intent:
            raise Echec(f"E4 « {texte} » : la garde de la bouche le refuse ({vu})")
        t = n.bouche(intent)
        marques["gestes"].append({"t": t, "intent": intent})
        print(f"  {time.strftime('%T')} E4 {cmd} « {texte} » -> {intent['id']}", flush=True)
        n.dormir(max(0.0, ESPACEMENT_S - (time.time() - t)))
    n.dormir(4.0)
    marques["fin"] = time.time()
except Echec as e:
    marques["echec"] = str(e)
    print(f"  ⚠️ pilote : {e}", flush=True)
finally:
    (CAP / "pilote.json").write_text(json.dumps(marques, indent=1, ensure_ascii=False), encoding="utf-8")
    n.destroy_node()
    rclpy.try_shutdown()
EOF

capture_arreter || { echo "=== OBJ : mesure invalide (enregistreur mort), aucun verdict $(date +%T) ==="; exit 2; }

echo "=== OBJ : verdicts (relus sur les captures) $(date +%T) ==="
python3 - "$CAP" "$NS" "$RJ" <<'EOF'
import json, math, sys
from pathlib import Path

CAP, NS, RJ = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
BANC = (36.2, 2.496)          # centre du banc (chantiers_tours.yaml), position du TABLEAU
EMPRISE_BANC = 1.1            # orbite 2,1 − dégagement 1,0 (majorant de la collision)
RAYON_DIDIER = 0.5            # contracts.GOTO_DIDIER_RAYON_M (roulette arrière à 0,45 m)
# A0-4 (22/11) : EMPRISE_BANC + garde du corps sûr (x_avant 0,30 + bande ARRET 0,60, lus par le
# régisseur dans machines/sim/robot/corps_sur.yaml) + GOTO_MARGE_M (0,5) — gravé ; O1 : 2,1.
STANDOFF_BANC = 2.5
JEU_MIN = 0.2                 # jeu minimal Didier ↔ banc à l'arrêt (m)
m = json.loads((CAP / "pilote.json").read_text(encoding="utf-8"))
lignes = [json.loads(l) for l in open(CAP / "journal.jsonl", encoding="utf-8")]
regie = []
for l in open(RJ, encoding="utf-8"):
    try:
        regie.append(json.loads(l))
    except ValueError:
        pass
ok = ko = 0


def verdict(bon, texte):
    global ok, ko
    print(("  ✅ " if bon else "  ❌ ") + texte, flush=True)
    ok, ko = ok + bool(bon), ko + (not bon)


def msgs(topic, de=0.0, a=math.inf):
    out = []
    for l in lignes:
        if l["topic"] == NS + "/" + topic and de <= l["stamp"] < a:
            p = l["payload"]
            if "msg" in p:
                try:
                    p = json.loads(p["msg"])
                except ValueError:
                    p = p["msg"]
            out.append((l["stamp"], p))
    return out


def proche(v, cible, tol):
    return isinstance(v, (int, float)) and abs(v - cible) <= tol


if "echec" in m:
    print(f"  pilote interrompu : {m['echec']}")

# --- E1 -------------------------------------------------------------------------------------
t1, f1 = m.get("e1", math.inf), m.get("e1_fin", math.inf)
v1 = m.get("e1_tableau") or {}
verdict(v1.get("statut") == "ici" and v1.get("atteignable") and proche(v1.get("distance_m"), 4.5, 0.3)
        and v1.get("emprise_m") == EMPRISE_BANC,
        f"E1a le tableau dit le banc ici et atteignable : {v1}")
ordre_jeu = next((v for _, v in msgs("jeu/chat_move", t1, f1) if isinstance(v, dict) and v.get("cmd") == "aller_voir"), None)
rep1 = next((v for _, v in msgs("rehearsal/chat_move_reply", t1, f1)
             if isinstance(v, dict) and v.get("source") == "director"), None)
goto1 = next((v for _, v in msgs("route_goto", t1, f1) if isinstance(v, dict)), None)
verdict(v1.get("garde") == [None, None] and ordre_jeu is not None and ordre_jeu.get("id") == "carte/banc"
        and rep1 is not None
        and rep1.get("effect") == "accepted" and (rep1.get("demande") or {}).get("id") == "carte/banc"
        and goto1 is not None and goto1.get("name") == "banc" and proche(goto1.get("x"), BANC[0], 0.01)
        and proche(goto1.get("y"), BANC[1], 0.01) and goto1.get("standoff") == STANDOFF_BANC,
        f"E1b garde de la bouche {v1.get('garde')}, id porté par le sélecteur ({ordre_jeu}) et le régisseur ({rep1 and rep1.get('effect')}), "
        f"ordre à la position du tableau ({goto1})")
arr = next(((t, v) for t, v in msgs("route_goto_result", t1, f1) if isinstance(v, dict) and v.get("name") == "banc"),
           None)
verdict(arr is not None and arr[1].get("result") == "arrived" and arr[0] - t1 <= 60,
        f"E1c arrivée : {arr and arr[1]} en {('%.1f s' % (arr[0] - t1)) if arr else '—'} (≤ 60 s)")
p = m.get("e1_pose")
d = math.dist(p[:2], BANC) if p else math.nan
jeu = d - (EMPRISE_BANC + RAYON_DIDIER)
verdict(p is not None and proche(d, STANDOFF_BANC, 0.3) and jeu >= JEU_MIN,
        f"E1d arrêt à {d:.2f} m du centre du banc ({STANDOFF_BANC:g} ± 0,3), jeu {jeu:.2f} m "
        f"(≥ {JEU_MIN:g}){' — CONTACT' if jeu <= 0 else ''}")
ecart = abs((math.degrees(math.atan2(BANC[1] - p[1], BANC[0] - p[0])) - p[2] + 180) % 360 - 180) if p else math.nan
verdict(p is not None and ecart <= 10.0, f"E1e face au banc : écart de cap {ecart:.1f}° (≤ 10)")

# --- E2 -------------------------------------------------------------------------------------
t2, f2 = m.get("e2", math.inf), m.get("e2_fin", math.inf)
v2 = m.get("e2_tableau") or {}
verdict(v2.get("statut") == "pas_ici" and proche(v2.get("distance_m"), 22.3, 0.3) and v2.get("cote") == "devant"
        and not v2.get("en_vue") and not v2.get("atteignable"),
        f"E2a le tableau dit le banc connu, pas ici : {v2}")
rep2 = next(((t, v) for t, v in msgs("rehearsal/chat_move_reply", t2, f2) if isinstance(v, dict)), None)
verdict(rep2 is not None and rep2[1].get("source") == "jeu" and rep2[1].get("effect") == "dropped"
        and rep2[1].get("reason") == "pas_ici" and proche(rep2[1].get("distance_m"), 22.3, 0.3)
        and rep2[1].get("cote") == "devant" and rep2[0] - t2 <= 1.0,
        f"E2b réponse « connu, pas ici » du sélecteur : {rep2 and rep2[1]} "
        f"({('%.2f s' % (rep2[0] - t2)) if rep2 else '—'}, ≤ 1 s)")
# Ordres de GESTE seulement : le « go » de reprise du sélecteur (10 s après l'arrivée d'E1) peut
# tomber ici ; hors séance le régisseur l'ignore (E2d le prouve : aucune roue ne tourne).
ordres2 = [v for _, v in msgs("jeu/chat_move", t2, f2) if isinstance(v, dict)] + \
          [v for _, v in msgs("route_goto", t2, f2) if isinstance(v, dict)]
verdict(not ordres2, f"E2c zéro ordre de geste parti (jeu/chat_move, route_goto) : {ordres2 or 'aucun'}")
vit = [max(abs(v["linear"]["x"]), abs(v["angular"]["z"])) for _, v in msgs("cmd_vel_follow", t2, f2)]
p0, p8 = m.get("e2_p0"), m.get("e2_p8")
derive = math.dist(p0[:2], p8[:2]) if p0 and p8 else math.inf
verdict(max(vit, default=0.0) < 0.01 and derive < 0.05,
        f"E2d zéro roue : cmd_vel_follow max {max(vit, default=0.0):.3f} ({len(vit)} msgs, < 0,01), "
        f"{derive:.3f} m parcourus en 8 s (< 0,05)")
verdict(v2.get("garde") == ["dropped", "pas_ici"] and v2.get("id") == "carte/banc"
        and proche(v2.get("distance_m"), 22.3, 0.3) and v2.get("cote") == "devant",
        f"E2e la garde de la bouche (garde_geste, le code de chat_node) refuse « le banc » : {v2.get('garde')}")

# --- E4 -------------------------------------------------------------------------------------
gestes = m.get("gestes", [])
bornes = [g["t"] for g in gestes] + [m.get("fin", math.inf)]
acceptes = verites = journaux = 0
for i, g in enumerate(gestes):
    de, a, intent = bornes[i], bornes[i + 1], g["intent"]
    id_ = intent["id"]
    jeu = next((v for _, v in msgs("jeu/chat_move", de, a) if isinstance(v, dict) and v.get("cmd") == intent["cmd"]),
               None)
    rep = next((v for _, v in msgs("rehearsal/chat_move_reply", de, a)
                if isinstance(v, dict) and v.get("source") == "director"), None)
    # Lot S1 : le geste de la bouche est journalisé « ordre » (exécuté tout de suite, sans score).
    offre = next((v for _, v in msgs("jeu/journal", de, a) if isinstance(v, dict) and v.get("type") == "ordre"
                  and isinstance((v.get("payload") or v).get("demande"), dict)), None)
    offre_id = ((offre.get("payload") or offre).get("demande") or {}).get("id") if offre else None
    reg = [e for e in regie if e.get("type") == intent["cmd"] and (e.get("payload") or {}).get("id") == id_]
    acceptes += bool(rep and rep.get("effect") == "accepted")
    verites += bool(jeu and rep and jeu.get("id") == id_ and (rep.get("demande") or {}).get("id") == id_)
    journaux += bool(offre_id == id_ and reg)
    print(f"#  {intent['cmd']} « {intent['objet']} » {id_} : jeu {jeu and jeu.get('id')} ; régisseur "
          f"{rep and rep.get('effect')} {rep and (rep.get('demande') or {}).get('id')} ; journal jeu {offre_id} ; "
          f"journal régisseur {len(reg)} ligne(s)")
verdict(len(gestes) == 10 and acceptes == 10, f"E4a {acceptes}/10 gestes acceptés par le régisseur")
verdict(len(gestes) == 10 and verites == 10, f"E4b {verites}/10 : même id bouche, sélecteur, régisseur")
verdict(len(gestes) == 10 and journaux == 10, f"E4c {journaux}/10 : même id au journal du sélecteur et du régisseur")

print(f"=== OBJ tableau des objets : {ok} OK, {ko} KO ===")
sys.exit(0 if ko == 0 else 1)
EOF
