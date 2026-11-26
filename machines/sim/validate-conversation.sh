#!/bin/bash
# CONV — épreuve de CONVERSATION SCRIPTÉE de bout en bout (16/11, décision de David), DANS le
# conteneur `monde` : monde `chantiers`, vrai bringup du robot, rehearsal.launch.py
# route:=chantiers scenario:=jeu-a1 jeu:=true (régisseur + sélecteur de jeu, scénario calme : ni
# bug ni lubie du régisseur) + gaze_follower, ET la tête (surcouche docker-compose.tete.yml :
# chat_node SANS micro ni son, mouvement à la voix, clé Anthropic). Durée ≈ 3-5 min ; coût ≈ 5 à
# 8 appels Claude Haiku 5.5 (≈ 0,002 $ au tarif lu le 16/11 : 0,10 $/M jetons d'entrée).
#
# Le texte remplace le micro (topic `chat_text`, le clavier de la page scène), publié UNE fois par
# phrase (jamais en salve : chaque message est un tour de conversation). Les contrôles portent sur
# des FAITS observables (topics, journal du jeu), jamais sur un jugement du LLM ; seuils gravés.
#
# P1 fournisseur  : la chaîne d'écoute (chat_audio_chain, latchée) annonce Anthropic en direct
# T0 départ       : route on, Didier est parti (x > 0,3 m)
# A  « fais le tour de l'éléphant » (l'éléphant n'a PAS de tour : collé à la Loire)
#   A1 Didier répond (≥ 1 réplique sur chat_transcript en ≤ 40 s)
#   A2 AUCUN ordre tour_de publié (bouche -> jeu, ni jeu -> régisseur) jusqu'à la phrase B
#   A3 aucune réplique ne prétend l'avoir fait (motifs gravés MOTIFS_PRETENTION)
# B  « va voir la table basse » (objet à < 10 m : la phrase part quand Didier en est à moins de
#    DIST_B_M, en marche depuis ≥ 11 s — période réfractaire « déplacement » du jeu = 10 s ; « en
#    marche » = route on ET route_speed > 0 : le hold d'une lubie n'en est pas un, fumée du 19/11)
#   B1 ordre aller_voir publié par la bouche, objet = la table basse, en ≤ 20 s
#   B2 accepté par le RÉGISSEUR (chat_move_reply source director, effect accepted) en ≤ 30 s
#   B3 arrivée : route_goto_result « arrived » du même ordre en ≤ 90 s
#   B4 reprise seule (lot S1, une seule reprise) : « go » du jeu d'origine « didier » à l'instant
#      tiré (journal « reprise_armee », delai_s dans [10, 40] s, ± 1 s), journal du jeu « reprise »
#   B5 Didier repart : route_state on après la reprise et x gagne ≥ 0,3 m en ≤ 15 s
# C  « stop » (Didier en marche et à l'écoute)
#   C1 « stop » publié par la bouche en ≤ 2 s (arrêt d'urgence, AVANT le LLM), d'origine « david »
#      (un mot d'arrêt est un ORDRE, lot S1)
#   C2 relayé par le jeu au régisseur en ≤ 0,5 s, origine « david » gardée
#   C3 arrêt : le régisseur pose route_speed 0 (« hold » : l'arrêt vocal ne coupe PAS la route,
#      route_state reste on — vu à l'essai 1 du 16/11) en ≤ 1 s après le stop de la bouche,
#      cmd_vel_follow nul de +2 à +9 s, et moins de 0,05 m parcourus de +4 à +9 s
# D  « Il y a une lettre sur le banc, tu pourrais regarder ? » (lot « texte raccord », séance du
#    18/11 21:35 rejouée : le banc est à plus de 10 m, la lettre est imaginaire). Après C, « go »
#    console, Didier en marche depuis ≥ EN_MARCHE_D_S, banc à > DIST_D_MIN_M
#   D1 Didier répond (≥ 1 réplique sur chat_transcript en ≤ 40 s)
#   D2 la bouche demande une PAUSE (rehearsal/chat_move "pause") en ≤ 20 s, et AUCUN aller_voir ni
#      tour_de n'est transmis au régisseur (jeu/chat_move) jusqu'à la fin
#   D3 arrêt : « stop » relayé par le jeu ≤ 0,5 s après la pause, route_speed 0 ≤ 1 s après
#   D4 regard : un message sur `look` dans les 1,5 s qui suivent la pause
#   D5 reprise seule (lot S1) : « go » du jeu d'origine « didier » à l'instant tiré (journal
#      « reprise_armee », [10, 40] s, ± 1 s), journal du jeu « pause_regard » puis « reprise », et x
#      gagne ≥ 0,3 m dans les 10 s qui suivent
#   D6 raccord : aucune réplique de D ne prétend être allée au banc ni avoir touché la lettre ; après
#      un geste REFUSÉ (chat_move_reply non accepté), aucune ne prétend non plus l'avoir vue
source /opt/ros/${ROS_DISTRO}/setup.sh
source /home/ros2_ws/install/setup.bash
NS="/${ROBOT_NAME:-didier}"
source /home/ros2_ws/captures.sh
JDIR=/home/ros2_ws/log/jeu
RDIR=/home/ros2_ws/log/rehearsal

# --- PRÉCONDITIONS (banc faux = code 2, jamais un verdict) ------------------------------------
for proc in jeu_node route_driver director twist_deadman animations_node gaze_follower "didier_vision/chat"; do
  pgrep -f "/$proc\$|/$proc " >/dev/null || { echo "PRÉCONDITION : processus « $proc » absent (surcouche docker-compose.tete.yml ? rehearsal.launch.py jeu:=true ? gaze_follower ?)"; exit 2; }
done
pgrep -af "lib/didier_rehearsal/[d]irector" | grep -q "rehearsal/chat_move:=jeu/chat_move" || { echo "PRÉCONDITION : le régisseur n'est pas remappé sur jeu/chat_move (rehearsal.launch.py jeu:=true)"; exit 2; }
timeout 10 gz model --list 2>/dev/null | grep -q titan_grise || { echo "PRÉCONDITION : modèle titan_grise absent (WORLD=chantiers ?)"; exit 2; }
JJ=$(ls -t $JDIR/*_jeu.jsonl 2>/dev/null | head -1)
grep -q '"type": "degrade"' "$JJ" 2>/dev/null && { echo "PRÉCONDITION : jeu_node est en MODE DÉGRADÉ ($JJ)"; exit 2; }
RJ=$(ls -t $RDIR/*_jeu-a1.jsonl 2>/dev/null | head -1)
rpid=$(basename "$RJ" 2>/dev/null | cut -d_ -f3)
[ -n "$rpid" ] && kill -0 "$rpid" 2>/dev/null || { echo "PRÉCONDITION : aucun régisseur vivant avec le scénario jeu-a1"; exit 2; }

# Enregistreur PRÊT (chaque abonnement apparié) avant le moindre geste : chat_node, jeu_node,
# régisseur et route_driver sont donc bien là et se font entendre.
capture_demarrer conversation \
  --journal $NS/rehearsal/chat_move=theatre_interfaces/msg/StringTime \
  --journal $NS/jeu/chat_move=theatre_interfaces/msg/StringTime \
  --journal $NS/rehearsal/chat_move_reply=theatre_interfaces/msg/StringTime \
  --journal $NS/route_goto_result=theatre_interfaces/msg/StringTime \
  --journal $NS/chat_transcript=theatre_interfaces/msg/StringTime \
  --journal $NS/jeu/journal=theatre_interfaces/msg/StringTime \
  --journal $NS/route_state=theatre_interfaces/msg/StringTime,latche \
  --journal $NS/chat_state=theatre_interfaces/msg/StringTime,latche \
  --journal $NS/route_speed=theatre_interfaces/msg/StringTime \
  --journal $NS/cmd_vel_follow=geometry_msgs/msg/Twist \
  --journal $NS/look=theatre_interfaces/msg/StringTime \
  --dernier $NS/chat_audio_chain=theatre_interfaces/msg/StringTime,latche \
  --dernier $NS/ground_truth/odom=nav_msgs/msg/Odometry

echo "=== CONV : pilote (route, phrases A B C) $(date +%T) ==="
python3 - "$CAP" "$NS" <<'EOF'
"""Pilote : AGIT seulement (publie) ; il lit les captures de l'enregistreur pour décider QUAND
agir (état de route, pose, état du chat), jamais par une souscription à lui."""
import json, math, subprocess, sys, time
from pathlib import Path
import rclpy
from rclpy.node import Node
from theatre_interfaces.msg import StringTime

CAP, NS = Path(sys.argv[1]), sys.argv[2]
TABLE = (17.8, 1.4)          # ancre du POI table_basse (didier_rehearsal/config/chantiers.yaml)
DIST_B_M = 9.0               # < PORTEE_M (10 m, « atteignable » du tableau des objets), marge 1 m
BANC = (36.2, 1.4)           # ancre du POI banc (didier_rehearsal/config/chantiers.yaml)
DIST_D_MIN_M = 11.0          # > PORTEE_M : le banc n'est pas atteignable (la séance du 18/11 : 20 m)
EN_MARCHE_D_S = 3.0
# > refractaire_s.deplacement (10 s) du sélecteur — plus exigé depuis le lot S1 (un geste de la
# bouche est un ordre, sans réfractaire), gardé : la scène B reste la même.
EN_MARCHE_S = 11.0
TELEPORT = ["timeout", "10", "gz", "service", "-s", "/world/stage/set_pose", "--reqtype", "gz.msgs.Pose",
            "--reptype", "gz.msgs.Boolean", "--timeout", "3000", "--req",
            'name: "dadou_robot", position: {x: 0, y: 0, z: 0.3}, orientation: {w: 1}']
marques = {}


class Echec(Exception):
    pass


def journal(topic=None, depuis=0.0):
    lignes = []
    try:
        with open(CAP / "journal.jsonl", encoding="utf-8") as f:
            for l in f:
                try:
                    d = json.loads(l)
                except ValueError:
                    continue
                if d["stamp"] >= depuis and (topic is None or d["topic"] == NS + "/" + topic):
                    lignes.append(d)
    except OSError:
        pass
    return lignes


def dernier(topic):
    try:
        return json.loads((CAP / "dernier" / (NS + "/" + topic).strip("/").replace("/", "__")
                           ).with_suffix(".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def etat(topic):
    l = journal(topic)
    return l[-1]["payload"]["msg"] if l else None


def cmd(l):
    """`cmd` d'une ligne de chat_move (lot S1 : {"cmd", "origine"} ; ancienne forme : la chaîne)."""
    v = json.loads(l["payload"]["msg"])
    return v.get("cmd") if isinstance(v, dict) else v


def pose():
    d = dernier("ground_truth/odom")
    if d is None:
        return None
    p = d["payload"]["pose"]["pose"]["position"]
    return p["x"], p["y"]


def en_marche(route_state, route_speed):
    """Didier ROULE : route « on » ET vitesse de route non nulle. route_state seul ne suffit pas :
    l'arrêt d'une lubie du sélecteur est un « hold » (route_speed 0, route_state reste on). Fumée
    du 19/11 08:36 : hold de 98 s compté comme « en marche », phrase B publiée 3 s après le
    « repartir » du jeu (réfractaire déplacement 10 s) → refusée « trop_tot », B2-C3 en cascade.
    Vitesse inconnue (jamais publiée) = pas en marche : le pilote la pose lui-même au départ."""
    if route_state != "on":
        return False
    try:
        return float(route_speed) > 0.0
    except (TypeError, ValueError):
        return False


class Pilote(Node):
    def __init__(self):
        super().__init__("validate_conversation", namespace=NS)
        self.pubs = {t: self.create_publisher(StringTime, t, 10)
                     for t in ("route", "route_speed", "rehearsal/cmd", "chat", "chat_text", "jeu/console")}
        self.apparies = set()

    def dormir(self, s):
        fin = time.monotonic() + s
        while time.monotonic() < fin:
            rclpy.spin_once(self, timeout_sec=min(0.1, max(0.0, fin - time.monotonic())))

    def publier_une_fois(self, topic, valeur):
        """UN message (jamais une salve), après appariement de l'abonné (≤ 10 s)."""
        pub, fin = self.pubs[topic], time.monotonic() + 10.0
        while pub.get_subscription_count() < 1:
            if time.monotonic() > fin:
                raise Echec(f"personne n'écoute {NS}/{topic} après 10 s")
            self.dormir(0.1)
        if topic not in self.apparies:
            # L'appariement vu d'ICI peut précéder celui vu par l'abonné (découverte DDS
            # asymétrique) : 1 s de grâce au premier usage, sinon un message unique se perd.
            self.apparies.add(topic)
            self.dormir(1.0)
        pub.publish(StringTime(msg=json.dumps(valeur), time=0, anim=False))
        return time.time()

    def idempotent(self, topic, valeur, confirme, delai=15.0):
        """Commande idempotente renvoyée chaque seconde jusqu'à `confirme()` (boucle fermée)."""
        fin = time.monotonic() + delai
        while time.monotonic() < fin:
            self.publier_une_fois(topic, valeur)
            self.dormir(1.0)
            if confirme():
                return
        raise Echec(f"{topic} := {valeur!r} non confirmé après {delai:g} s")

    def console(self, cmd):
        self.publier_une_fois("jeu/console", {"cmd": cmd, "presence": True})

    def attendre(self, cond, delai, quoi):
        fin = time.monotonic() + delai
        while time.monotonic() < fin:
            if cond():
                return
            self.dormir(0.2)
        raise Echec(f"{quoi} : pas dans les {delai:g} s")

    def ecoute(self):
        return etat("chat_state") == "listening"

    def dire(self, cle, texte):
        """Une phrase de David, Didier À L'ÉCOUTE (sinon elle attendrait la fin de sa réplique)."""
        self.attendre(self.ecoute, 60, f"chat_state=listening avant « {texte} »")
        marques[cle] = self.publier_une_fois("chat_text", texte)
        print(f"  {time.strftime('%T')} « {texte} » publié", flush=True)

    def faire_marcher(self, delai=150.0):
        """Didier EN MARCHE (en_marche : route on ET route_speed > 0) depuis ≥ EN_MARCHE_S, à
        < DIST_B_M de la table. Un arrêt du sélecteur (lubie : hold, route_speed 0) ou de la route
        (off) est levé à la CONSOLE (« go » de David) ; le compte des EN_MARCHE_S repart de la
        reprise effective (un « repartir » du jeu ouvre sa période réfractaire déplacement)."""
        fin, depuis_on, gos = time.monotonic() + delai, None, 0
        hors_route_depuis = None
        while time.monotonic() < fin:
            st, p = etat("route_state"), pose()
            if en_marche(st, etat("route_speed")):
                hors_route_depuis = None
                depuis_on = depuis_on or time.monotonic()
            else:
                depuis_on = None
                hors_route_depuis = hors_route_depuis or time.monotonic()
                if st in ("off", "on") and time.monotonic() - hors_route_depuis > 5 and gos < 3:
                    quoi = st if st == "off" else "on, vitesse 0"
                    print(f"  {time.strftime('%T')} Didier arrêté ({quoi}) : « go » console", flush=True)
                    self.console("go"); gos += 1; hors_route_depuis = None
            if p is not None and p[0] > TABLE[0]:
                raise Echec(f"Didier a dépassé la table basse (x = {p[0]:.1f}) avant la phrase B")
            if (depuis_on and time.monotonic() - depuis_on >= EN_MARCHE_S and p is not None
                    and math.dist(p, TABLE) < DIST_B_M):
                marques["dist_b"] = round(math.dist(p, TABLE), 2)
                return
            self.dormir(0.2)
        raise Echec(f"Didier n'est pas arrivé en marche à < {DIST_B_M} m de la table basse en {delai:g} s")


rclpy.init()
n = Pilote()
try:
    # Mise en route (comme V-R3/A1) : route off confirmée, restart, origine, vitesse 1, séance, on.
    n.idempotent("route", "off", lambda: etat("route_state") == "off")
    n.publier_une_fois("route", "restart")
    subprocess.run(TELEPORT, capture_output=True)
    n.dormir(2.0)
    n.idempotent("route_speed", 1.0, lambda: True, delai=2.0)
    n.idempotent("rehearsal/cmd", "start", lambda: True, delai=2.0)
    n.idempotent("chat", "on", n.ecoute, delai=20.0)
    marques["route_on"] = time.time()
    n.idempotent("route", "on", lambda: etat("route_state") == "on")
    n.dormir(8.0)
    marques["x_depart"] = (pose() or (math.nan,))[0]

    # A — la demande impossible, au tout début du trajet.
    n.dire("a", "Fais le tour de l'éléphant.")
    n.attendre(lambda: any(json.loads(l["payload"]["msg"]).get("role") == "didier"
                           for l in journal("chat_transcript", marques["a"])), 40, "réplique à A")
    n.dormir(8.0)     # une éventuelle continuation (geste refusé dit en personnage)
    n.attendre(n.ecoute, 40, "fin des répliques de A")

    # B — l'objet proche : Didier en marche, à < DIST_B_M de la table basse.
    n.faire_marcher()
    n.dire("b", "Va voir la table basse.")
    n.attendre(lambda: any(json.loads(l["payload"]["msg"]).get("result") == "arrived"
                           for l in journal("route_goto_result", marques["b"])), 120, "arrivée de B")
    arrivee = next(l["stamp"] for l in journal("route_goto_result", marques["b"])
                   if json.loads(l["payload"]["msg"]).get("result") == "arrived")
    # Reprise seule (lot S1 : silence tiré dans [10, 40] s) : le « go » du jeu, puis 15 s de marche
    # (B5). La pose est relevée ICI (l'odométrie n'est enregistrée qu'en dernière valeur).
    n.attendre(lambda: any(cmd(l) == "go" for l in journal("jeu/chat_move", arrivee)), 50,
               "« go » de reprise de B")
    marques["x_go"] = (pose() or (math.nan,))[0]
    n.dormir(15.0)
    marques["x_go15"] = (pose() or (math.nan,))[0]

    # C — l'arrêt, Didier en marche et à l'écoute.
    n.attendre(lambda: etat("route_state") == "on" and n.ecoute(), 60, "Didier en marche et à l'écoute avant C")
    n.dire("c", "Stop.")
    n.dormir(4.0)
    marques["p_c4"] = pose()
    n.dormir(5.0)
    marques["p_c9"] = pose()

    # D — « regarde » : la lettre (imaginaire) sur le banc (lointain). C a posé le stop de la
    # bouche : « go » de David à la console, puis Didier en marche quelques secondes.
    n.attendre(n.ecoute, 60, "Didier à l'écoute après C")
    n.console("go")
    fin, depuis = time.monotonic() + 30.0, None
    while True:
        if en_marche(etat("route_state"), etat("route_speed")):
            depuis = depuis or time.monotonic()
            if time.monotonic() - depuis >= EN_MARCHE_D_S:
                break
        else:
            depuis = None
        if time.monotonic() > fin:
            raise Echec("Didier n'est pas reparti après le « go » console de D")
        n.dormir(0.2)
    p = pose()
    if p is None or math.dist(p, BANC) <= DIST_D_MIN_M:
        raise Echec(f"banc trop proche pour D ({p}) : il serait atteignable")
    marques["dist_d"] = round(math.dist(p, BANC), 2)
    n.dire("d", "Il y a une lettre sur le banc, tu pourrais regarder ?")
    # La pause et sa reprise (lot S1 : silence tiré, ≤ 40 s) : la pose est relevée au « go » du jeu
    # puis 10 s après (D5).
    try:
        n.attendre(lambda: any(cmd(l) == "pause" for l in journal("rehearsal/chat_move", marques["d"])),
                   30, "pause de D")
        tp = next(l["stamp"] for l in journal("rehearsal/chat_move", marques["d"]) if cmd(l) == "pause")
        n.attendre(lambda: any(cmd(l) == "go" for l in journal("jeu/chat_move", tp)), 50,
                   "« go » de reprise de D")
        marques["x_d_go"] = (pose() or (math.nan,))[0]
        n.dormir(10.0)
        marques["x_d_go10"] = (pose() or (math.nan,))[0]
    except Echec as e:
        print(f"  ⚠️ pilote D : {e}", flush=True)     # les verdicts D diront lesquels manquent
    n.attendre(n.ecoute, 40, "fin des répliques de D")
    marques["fin"] = time.time()
except Echec as e:
    marques["echec"] = str(e)
    print(f"  ⚠️ pilote : {e}", flush=True)
finally:
    (CAP / "pilote.json").write_text(json.dumps(marques, indent=1), encoding="utf-8")
    n.destroy_node()
    rclpy.try_shutdown()
EOF

capture_arreter || { echo "=== CONV : mesure invalide (enregistreur mort), aucun verdict $(date +%T) ==="; exit 2; }

echo "=== CONV : verdicts (relus sur les captures) $(date +%T) ==="
python3 - "$CAP" "$NS" <<'EOF'
import json, math, re, sys
from pathlib import Path

CAP, NS = Path(sys.argv[1]), sys.argv[2]
TABLE = (17.8, 1.4)
# D6 — être allé au banc, ou avoir touché la lettre : motifs GRAVÉS (réplique en minuscules, sans
# accents, apostrophes droites). Et après un geste REFUSÉ, l'avoir vue (la séance du 18/11 : « je vois
# bien une enveloppe posée dessus »). Juge INDÉPENDANT du code de la bouche (didier_vision.ai.raccord).
MOTIFS_ALLE = [r"\bj'y suis\b", r"\bme (voila|voici)\b", r"\bje suis (arrive|alle|devant|a cote)",
               r"\bj'ai (ouvert|pris|ramasse|attrape|lu)\b", r"\bje (lis|ouvre|ramasse|decachette)\b"]
MOTIFS_VU = [r"\bje (la |le |l')?(vois|apercois|distingue)\b", r"\bj'ai (vu|trouve)\b", r"\by a bien\b"]
NOMS_TABLE = {"table_basse", "table basse", "table", "petite table"}
# Prétendre avoir fait (ou faire) le tour : motifs GRAVÉS, sur la réplique en minuscules,
# apostrophes typographiques ramenées à « ' ».
MOTIFS_PRETENTION = [
    # Passé : « j'ai fait le tour », « voilà, tour terminé », « le tour est fait ».
    r"\b(j'ai|on a|voil[aà]|c'est)\b[^.!?]{0,40}\b(fait|termin[ée]|fini|boucl[ée])\b[^.!?]{0,30}\btour\b",
    r"\btour\b[^.!?]{0,20}\b(est |c'est )?(fait|termin[ée]|fini|boucl[ée])\b",
    # Annonce (vue le 16/11, essai 1 : « Je vais lui faire le tour, tu verras ») ; « je ne vais pas
    # faire le tour » et « impossible de faire le tour » ne s'y prennent pas.
    r"\bje (vais|m'en vais) (lui |leur |en )?faire le tour\b",
    r"\bje (fais|refais) (le|son|leur) tour\b",
]
m = json.loads((CAP / "pilote.json").read_text(encoding="utf-8"))
lignes = [json.loads(l) for l in open(CAP / "journal.jsonl", encoding="utf-8")]
ok = ko = 0


def verdict(bon, texte):
    global ok, ko
    print(("  ✅ " if bon else "  ❌ ") + texte, flush=True)
    ok, ko = ok + bool(bon), ko + (not bon)


def msgs(topic, de=0.0, a=math.inf):
    """(stamp, valeur décodée) des messages d'un topic dans [de, a)."""
    out = []
    for l in lignes:
        if l["topic"] == NS + "/" + topic and de <= l["stamp"] < a:
            brut = l["payload"]["msg"]
            try:
                out.append((l["stamp"], json.loads(brut)))
            except ValueError:
                out.append((l["stamp"], brut))
    return out


def norm(s):
    return " ".join(str(s or "").lower().replace("_", " ").split())


# Lot S1 : la marche porte son origine ({"cmd", "origine"}) ; ancienne forme chaîne = « david ».
def marche(v, quoi, origine=None):
    c, o = (v.get("cmd"), v.get("origine", "david")) if isinstance(v, dict) else (v, "david")
    return c == quoi and (origine is None or o == origine)


def tirage(de, a):
    """(instant, delai_s) de la première reprise armée par le jeu dans [de, a)."""
    return next(((t, v["payload"].get("delai_s")) for t, v in msgs("jeu/journal", de, a)
                 if isinstance(v, dict) and v.get("type") == "reprise_armee"), (None, None))


chaine = None
try:
    chaine = json.loads(json.loads((CAP / "dernier" / (NS.strip("/") + "__chat_audio_chain.json"))
                                   .read_text())["payload"]["msg"]).get("reponse", "")
except (OSError, ValueError, AttributeError):
    pass
verdict(chaine is not None and "(Anthropic, secours OpenRouter)" in chaine,
        f"P1 la bouche parle à Anthropic en direct (chaîne : {chaine!r})")
x0 = m.get("x_depart", math.nan)
verdict(isinstance(x0, float) and x0 > 0.3, f"T0 route on : Didier est parti (x = {x0} m après 8 s)")
if "echec" in m:
    print(f"  pilote interrompu : {m['echec']}")

ta, tb, tc = m.get("a"), m.get("b"), m.get("c")
fin_a = tb or m.get("fin") or math.inf
# --- A -------------------------------------------------------------------------------------
dits_a = [v.get("text", "") for _, v in msgs("chat_transcript", ta or math.inf, fin_a)
          if isinstance(v, dict) and v.get("role") == "didier"]
premier_a = next((s for s, v in msgs("chat_transcript", ta or math.inf, fin_a)
                  if isinstance(v, dict) and v.get("role") == "didier"), None)
verdict(premier_a is not None and premier_a - ta <= 40,
        f"A1 Didier répond à « fais le tour de l'éléphant » ({len(dits_a)} réplique(s))")
tours = [(t, v) for topic in ("rehearsal/chat_move", "jeu/chat_move")
         for t, v in msgs(topic, ta or 0, fin_a) if isinstance(v, dict) and v.get("cmd") == "tour_de"]
verdict(ta is not None and not tours, f"A2 aucun ordre tour_de publié vers le régisseur ({tours or 'aucun'})")
texte_a = " / ".join(dits_a).lower().replace("’", "'")
pretend = [p for p in MOTIFS_PRETENTION if re.search(p, texte_a)]
verdict(ta is not None and dits_a and not pretend,
        f"A3 aucune réplique ne prétend avoir fait le tour (« {texte_a[:160]} »)")

# --- B -------------------------------------------------------------------------------------
fin_b = tc or m.get("fin") or math.inf
ordres = [(t, v) for t, v in msgs("rehearsal/chat_move", tb or math.inf, fin_b)
          if isinstance(v, dict) and v.get("cmd") == "aller_voir"]
o = ordres[0] if ordres else None
verdict(o is not None and norm(o[1].get("objet")) in NOMS_TABLE and o[0] - tb <= 20,
        f"B1 la bouche demande aller_voir table basse (à {m.get('dist_b')} m) : {o[1] if o else 'rien'}")
rep = next(((t, v) for t, v in msgs("rehearsal/chat_move_reply", tb or math.inf, fin_b)
            if isinstance(v, dict) and o and v.get("demande") == o[1]), None)
verdict(rep is not None and rep[1].get("source") == "director" and rep[1].get("effect") == "accepted"
        and rep[0] - tb <= 30, f"B2 accepté par le régisseur : {rep[1] if rep else 'aucune réponse'}")
arr = next(((t, v) for t, v in msgs("route_goto_result", tb or math.inf, fin_b)
            if isinstance(v, dict) and rep and v.get("name") == rep[1].get("name")), None)
verdict(arr is not None and arr[1].get("result") == "arrived" and arr[0] - tb <= 90,
        f"B3 arrivée à la table basse : {arr[1] if arr else 'aucune issue'}")
ta_arr = arr[0] if arr else math.inf
go = next((t for t, v in msgs("jeu/chat_move", ta_arr, fin_b) if marche(v, "go", "didier")), None)
reprise = [v for _, v in msgs("jeu/journal", ta_arr, fin_b) if isinstance(v, dict) and v.get("type") == "reprise"]
t_tir, delai_b = tirage(ta_arr - 1.0, fin_b)
verdict(go is not None and delai_b is not None and 10.0 <= delai_b <= 40.0 and abs(go - t_tir - delai_b) <= 1.0
        and reprise,
        f"B4 reprise seule de la route {('%.1f s' % (go - ta_arr)) if go else '—'} après l'arrivée "
        f"(tirage {delai_b} s, ± 1 s ; journal du jeu « reprise » : {len(reprise)})")
on_apres = next((t for t, v in msgs("route_state", go or math.inf, fin_b) if v == "on"), None)
gain = m.get("x_go15", math.nan) - m.get("x_go", math.nan)
verdict(on_apres is not None and gain >= 0.3,
        f"B5 Didier repart : route_state on après la reprise, x gagne {gain:.2f} m en 15 s (≥ 0,3)")

# --- C -------------------------------------------------------------------------------------
stop = next((t for t, v in msgs("rehearsal/chat_move", tc or math.inf) if marche(v, "stop")), None)
stop_v = next((v for t, v in msgs("rehearsal/chat_move", tc or math.inf) if marche(v, "stop")), None)
verdict(stop is not None and stop - tc <= 2.0 and marche(stop_v, "stop", "david"),
        f"C1 « stop » publié par la bouche {('%.2f s' % (stop - tc)) if stop else '—'} après la phrase (≤ 2 s), "
        f"d'origine david : {stop_v}")
relais = next((t for t, v in msgs("jeu/chat_move", stop or math.inf) if marche(v, "stop", "david")), None)
verdict(relais is not None and relais - stop <= 0.5,
        f"C2 relayé par le jeu au régisseur {('%.3f s' % (relais - stop)) if relais else '—'} après (≤ 0,5 s)")
hold = next((t for t, v in msgs("route_speed", stop or math.inf) if v in (0, 0.0, "0")), None)
vitesses = [l["payload"]["linear"]["x"] for l in lignes
            if l["topic"] == NS + "/cmd_vel_follow" and tc and tc + 2 <= l["stamp"] <= tc + 9]
p4, p9 = m.get("p_c4"), m.get("p_c9")
derive = math.dist(p4, p9) if p4 and p9 else math.inf
verdict(hold is not None and hold - stop <= 1.0 and vitesses and max(abs(v) for v in vitesses) < 0.01
        and derive < 0.05,
        f"C3 arrêt : route_speed 0 {('%.2f s' % (hold - stop)) if hold else '—'} après le stop (≤ 1 s), "
        f"cmd_vel_follow max {max((abs(v) for v in vitesses), default=float('nan')):.3f} m/s de +2 à +9 s "
        f"({len(vitesses)} msgs, < 0,01), {derive:.3f} m parcourus de +4 à +9 s (< 0,05)")

# --- D -------------------------------------------------------------------------------------
import unicodedata


def plat(s):
    s = str(s or "").lower().replace("’", "'")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


td, fin_d = m.get("d"), m.get("fin") or math.inf
dits_d = [(t, v.get("text", "")) for t, v in msgs("chat_transcript", td or math.inf, fin_d)
          if isinstance(v, dict) and v.get("role") == "didier"]
verdict(td is not None and dits_d and dits_d[0][0] - td <= 40,
        f"D1 Didier répond à « une lettre sur le banc, tu pourrais regarder » (à {m.get('dist_d')} m du "
        f"banc, {len(dits_d)} réplique(s))")
pause = next((t for t, v in msgs("rehearsal/chat_move", td or math.inf, fin_d) if marche(v, "pause")), None)
partis = [v for t, v in msgs("jeu/chat_move", td or math.inf, fin_d)
          if isinstance(v, dict) and v.get("cmd") in ("aller_voir", "tour_de")]
verdict(pause is not None and pause - td <= 20 and not partis,
        f"D2 la bouche demande une pause {('%.1f s' % (pause - td)) if pause else '—'} après la phrase "
        f"(≤ 20 s), aucun aller_voir/tour_de transmis au régisseur ({partis or 'aucun'})")
# Fenêtres ouvertes 0,1 s AVANT la pause (fumée 2026-11-24-1421) : le jeu publie le « stop »,
# la pause et `pause_regard` dans la même milliseconde, sur des topics différents ; l'enregistreur
# a daté le stop 2 ms avant la pause et D3/D5 l'ont manqué (Didier, lui, s'était bien arrêté puis
# était reparti 6,0 s après). Même marge que T5 d'A1 (relais_stop, −0,1 s).
avant = (pause or math.inf) - 0.1
stop_d = next((t for t, v in msgs("jeu/chat_move", avant, fin_d) if marche(v, "stop")), None)
hold_d = next((t for t, v in msgs("route_speed", stop_d or math.inf, fin_d) if v in (0, 0.0, "0")), None)
verdict(stop_d is not None and abs(stop_d - pause) <= 0.5 and hold_d is not None and hold_d - stop_d <= 1.0,
        f"D3 arrêt : « stop » du jeu {('%.3f s' % (stop_d - pause)) if stop_d else '—'} après la pause "
        f"(≤ 0,5 s), route_speed 0 {('%.2f s' % (hold_d - stop_d)) if hold_d else '—'} après (≤ 1 s)")
regard = [v for t, v in msgs("look", (pause or math.inf) - 0.5, (pause or math.inf) + 1.5)]
verdict(bool(regard), f"D4 regard : {regard[0] if regard else 'aucun message look'} autour de la pause")
go_d = next((t for t, v in msgs("jeu/chat_move", stop_d or math.inf, fin_d) if marche(v, "go", "didier")), None)
types_d = [v.get("type") for _, v in msgs("jeu/journal", avant, fin_d) if isinstance(v, dict)]
gain_d = m.get("x_d_go10", math.nan) - m.get("x_d_go", math.nan)
t_tir_d, delai_d = tirage(avant, fin_d)
verdict(go_d is not None and delai_d is not None and 10.0 <= delai_d <= 40.0
        and abs(go_d - t_tir_d - delai_d) <= 1.0 and "pause_regard" in types_d and "reprise" in types_d
        and gain_d >= 0.3,
        f"D5 reprise seule {('%.1f s' % (go_d - pause)) if go_d else '—'} après la pause (tirage {delai_d} s, "
        f"± 1 s ; journal "
        f"pause_regard {'pause_regard' in types_d}, reprise {'reprise' in types_d}), x gagne {gain_d:.2f} m "
        f"en 10 s (≥ 0,3)")
refus_d = next((t for t, v in msgs("rehearsal/chat_move_reply", td or math.inf, fin_d)
                if isinstance(v, dict) and v.get("effect") != "accepted"), None)
fautes = [(round(t - td, 1), x) for t, x in dits_d
          if any(re.search(p, plat(x)) for p in MOTIFS_ALLE)
          or (refus_d is not None and t > refus_d and any(re.search(p, plat(x)) for p in MOTIFS_VU))]
verdict(td is not None and dits_d and not fautes,
        f"D6 raccord : aucune réplique ne prétend être allée au banc{' ni, après le refus, avoir vu' if refus_d else ''}"
        f" ({fautes or ' / '.join(x for _, x in dits_d)[:200]})")

print(f"=== CONV conversation scriptée : {ok} OK, {ko} KO ===")
sys.exit(0 if ko == 0 else 1)
EOF
