#!/bin/bash
# A1 — porte de sortie REJOUABLE du sélecteur de jeu (spec theatre-robot/docs/
# spec-A1-selecteur-de-jeu.md §6), DANS le conteneur sim : monde `chantiers`,
# chaîne roues + rehearsal.launch.py route:=chantiers scenario:=jeu-a1 jeu:=true
# (qui lance AUSSI jeu_node) + gaze_follower déjà lancés.
# Durée ≈ 16 min (15 min de jeu + mise en route).
#
# UN SEUL pilote rclpy LONGUE DURÉE fait tout (pas de `ros2 topic pub/echo` :
# le CLI se fait découvrir en retard sur le PC de dev, operations.md §Séance
# « Chantiers ») et ÉCOUTE AVANT la mise en route — aucune épreuve n'a de trou
# de capture (revue A1 du 02/11) :
#   mise en route : route off (confirmé par route_state LU, sinon échec), restart,
#     téléportation, vitesse 1, séance START, route on (confirmé, sinon échec) ;
#   perception SCRIPTÉE : A approche à t=60 s, reste 30 s, s'éloigne ; B passe
#     vite à t=300 s ; silence ensuite ;
#   console : ignore A à sa naissance + 1,5 s ; va_la vers A (piste) à 104 s
#     (approcher : se tourner puis avancer 1 m) ; va_la vers l'objet devant à
#     150 s puis reviens ; dès 262 s « go » toutes les 5 s tant qu'il est arrêté
#     puis STOP dès qu'il roule, GO 60 s après ; bouche : stop à 420 s, go à 430 s.
#
# T1 zéro oscillation : deux décisions successives jamais à < 2 s (spontanée ->
#                      spontanée comprise) ; aucun retour A -> B -> A en < 5 s
# T2 fréquences      : initiatives spontanées >= 8 s ; tout arrêt de Didier (lubie,
#                      approche, bouche) >= 120 s ; chaque arrêt-lubie : regard
#                      (look) ET intention publiés >= 3 s avant le stop
# T3 réaction        : chaque offre née (personne OU objet) -> choix ou maintien <= 1 s
# T4 console         : ignore -> rien vers la piste 30 s ; va_la piste -> avancer
#                      accepté par le régisseur ; va_la objet -> aller_voir accepté +
#                      route_goto_result ; stop sur un Didier qui ROULE -> arrêt < 1 s,
#                      puis aucune vitesse, aucune demande, aucun déplacement décidé
#                      jusqu'au go (fenêtres : dès le stop / dès l'arrêt constaté)
# T5 arrêt vocal     : stop de la bouche relayé en < 200 ms, journal relais_stop
# T6 lisibilité      : jeu/intention jamais muette > 1 s ; chaque ligne du TOPIC
#                      jeu/journal a un pourquoi non vide et jamais « (absent — bug) »
# T7 domaine         : le vrai main() de jeu_node refuse hors 43 AVANT d'importer
#                      rclpy (sous-processus sans rclpy ; aucun node lancé hors 43)
source /opt/ros/${ROS_DISTRO}/setup.sh
source /home/ros2_ws/install/setup.bash
CAP=/tmp/vja1; rm -rf $CAP; mkdir -p $CAP
JDIR=/home/ros2_ws/log/jeu
RDIR=/home/ros2_ws/log/rehearsal
DUREE=${DUREE:-900}
ok=0; ko=0
verdict() { if [ "$1" = 1 ]; then echo "  ✅ $2"; ok=$((ok+1)); else echo "  ❌ $2"; ko=$((ko+1)); fi; }

# --- PRÉCONDITIONS -----------------------------------------------------------
for proc in jeu_node route_driver fault_relay director twist_deadman animations_node gaze_follower servos_sim_node; do
  pgrep -f "/$proc\$|/$proc " >/dev/null || { echo "PRÉCONDITION : processus « $proc » absent (ANIMATIONS=true ? gaze_follower ? chaîne roues ? rehearsal.launch.py jeu:=true ?)"; exit 2; }
done
pgrep -af "lib/robot_rehearsal/[d]irector" | grep -q "rehearsal/chat_move:=jeu/chat_move" || { echo "PRÉCONDITION : le régisseur n'est pas remappé sur jeu/chat_move (rehearsal.launch.py jeu:=true)"; exit 2; }
timeout 10 gz model --list 2>/dev/null | grep -q titan_grise || { echo "PRÉCONDITION : modèle titan_grise absent (WORLD=chantiers ?)"; exit 2; }
JJ=$(ls -t $JDIR/*_jeu.jsonl 2>/dev/null | head -1)
jpid=$(basename "$JJ" 2>/dev/null | cut -d_ -f2)
[ -n "$jpid" ] && kill -0 "$jpid" 2>/dev/null || { echo "PRÉCONDITION : aucun jeu_node vivant avec journal dans $JDIR"; exit 2; }
grep -q '"type": "degrade"' "$JJ" && { echo "PRÉCONDITION : jeu_node est en MODE DÉGRADÉ (voir $JJ)"; exit 2; }
RJ=$(ls -t $RDIR/*_jeu-a1.jsonl 2>/dev/null | head -1)
rpid=$(basename "$RJ" 2>/dev/null | cut -d_ -f3)
[ -n "$rpid" ] && kill -0 "$rpid" 2>/dev/null || { echo "PRÉCONDITION : aucun régisseur vivant avec le scénario jeu-a1 (scenario:=jeu-a1 ?)"; exit 2; }
echo "  journal du jeu : $JJ"
echo "  journal du régisseur : $RJ"

echo "=== T7 domaine : le garde-fou refuse hors 43, AVANT rclpy $(date +%T) ==="
# Revue A1 (bloquant 5) : on ne lance JAMAIS un vrai node sur un autre domaine
# (conteneur en network_mode host). Le VRAI main() de jeu_node est appelé dans
# un python où rclpy est INTERDIT d'import : le refus doit venir de check_domain
# (RuntimeError) AVANT tout import rclpy (sinon ImportError = régression).
# Domaines essayés : 0 (défaut ROS) et absent. Test hôte : test_contrat_node.py.
t7=1
for dom in 0 absent; do
  if [ "$dom" = absent ]; then envd="env -u ROS_DOMAIN_ID"; else envd="env ROS_DOMAIN_ID=$dom"; fi
  out7=$($envd python3 -c "
import sys
sys.modules['rclpy'] = None   # tout import de rclpy lèverait ImportError
from didier_jeu.jeu_node import main
try:
    main()
except RuntimeError as e:
    print('REFUS', e); sys.exit(0)
except ImportError as e:
    print('ATTEINT RCLPY', e); sys.exit(1)
print('DÉMARRÉ'); sys.exit(1)
" 2>&1); rc=$?
  echo "  domaine $dom : $(echo "$out7" | tail -1 | cut -c1-110)"
  [ $rc = 0 ] && echo "$out7" | grep -q "^REFUS" || t7=0
done
verdict "$t7" "T7 jeu_node refuse hors domaine 43 (domaine 0 et absent), avant tout import rclpy"

echo "=== mise en route puis $DUREE s de jeu (un seul pilote rclpy) $(date +%T) ==="
python3 - "$CAP/capture.json" "$DUREE" <<'EOF'
import json, math, subprocess, sys, time
import rclpy
from geometry_msgs.msg import PointStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from robot_interfaces.msg import StringTime

SORTIE, DUREE = sys.argv[1], float(sys.argv[2])
LATCHE = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
TELEPORT = ["timeout", "10", "gz", "service", "-s", "/world/stage/set_pose", "--reqtype", "gz.msgs.Pose",
            "--reptype", "gz.msgs.Boolean", "--timeout", "3000", "--req",
            'name: "dadou_robot", position: {x: 0, y: 0, z: 0.3}, orientation: {w: 1}']


class Echec(Exception):
    pass


class Pilote(Node):
    def __init__(self):
        super().__init__("validate_jeu_a1")
        self.cap = {"intention": [], "jeu_chat_move": [], "cmd_vel": [], "goto_result": [], "console": [],
                    "bouche": [], "evenements": {}, "objets": [], "journal": [], "look": [], "route_state": []}
        self.pub_box = self.create_publisher(PointStamped, "vision/person_box", 10)
        self.pub_console = self.create_publisher(StringTime, "jeu/console", 10)
        self.pub_bouche = self.create_publisher(StringTime, "rehearsal/chat_move", 10)
        self.pub_route = self.create_publisher(StringTime, "route", 10)
        self.pub_speed = self.create_publisher(StringTime, "route_speed", 10)
        self.pub_seance = self.create_publisher(StringTime, "rehearsal/cmd", 10)
        self.create_subscription(StringTime, "jeu/intention", self._intention, LATCHE)
        self.create_subscription(StringTime, "jeu/chat_move", self._move, 10)
        self.create_subscription(StringTime, "jeu/journal", self._journal, 10)
        self.create_subscription(StringTime, "look", self._look, 10)
        self.create_subscription(StringTime, "route_state", self._route_state, LATCHE)
        self.create_subscription(Twist, "cmd_vel_follow", self._cmd, 10)
        self.create_subscription(StringTime, "route_goto_result", self._goto, 10)
        self.create_subscription(StringTime, "rehearsal/objects", self._objets, LATCHE)
        self.create_subscription(Odometry, "/ground_truth/odom", self._odom, 10)
        self.pose = None
        self.dernier_go = 0.0
        self.pistes = []          # (id, t) des naissances vues sur jeu/journal
        self.t0 = None
        self.faits = set()

    # --- captures (horloge MONOTONE : la même que t_mono_ms des journaux) --------
    def _intention(self, m):
        self.cap["intention"].append((time.monotonic(), json.loads(m.msg)))

    def _move(self, m):
        self.cap["jeu_chat_move"].append((time.monotonic(), json.loads(m.msg)))

    def _journal(self, m):
        ev = json.loads(m.msg)
        self.cap["journal"].append(ev)
        if ev.get("type") == "naissance_piste":
            self.pistes.append((ev["payload"]["piste"], time.monotonic()))

    def _look(self, m):
        self.cap["look"].append((time.monotonic(), json.loads(m.msg)))

    def _route_state(self, m):
        self.cap["route_state"].append((time.monotonic(), m.msg.strip().strip('"')))

    def _cmd(self, m):
        self.cap["cmd_vel"].append((time.monotonic(), m.linear.x, m.angular.z))

    def _goto(self, m):
        self.cap["goto_result"].append((time.monotonic(), json.loads(m.msg)))

    def _objets(self, m):
        self.cap["objets"] = json.loads(m.msg)

    def _odom(self, m):
        p, q = m.pose.pose.position, m.pose.pose.orientation
        self.pose = (p.x, p.y, math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y ** 2 + q.z ** 2)))

    # --- utilitaires -------------------------------------------------------------
    def attendre(self, cond, delai, quoi):
        fin = time.monotonic() + delai
        while time.monotonic() < fin:
            rclpy.spin_once(self, timeout_sec=0.05)
            if cond():
                return
        raise Echec(f"{quoi} : pas obtenu en {delai:g} s")

    def dormir(self, d):
        fin = time.monotonic() + d
        while time.monotonic() < fin:
            rclpy.spin_once(self, timeout_sec=0.05)

    def etat_route(self):
        return self.cap["route_state"][-1][1] if self.cap["route_state"] else None

    def publier(self, pub, valeur, n=1):
        for _ in range(n):
            pub.publish(StringTime(msg=json.dumps(valeur), time=0, anim=False))
            self.dormir(0.2)

    def route(self, etat):
        """Commande de route en boucle fermée : renvoyée chaque seconde jusqu'à
        ce que route_state (latché) la CONFIRME ; sinon échec de la mise en route."""
        fin = time.monotonic() + 15.0
        while time.monotonic() < fin:
            self.pub_route.publish(StringTime(msg=json.dumps(etat), time=0, anim=False))
            self.dormir(1.0)
            if self.etat_route() == etat:
                print(f"  route_state lu : {etat}", flush=True)
                return
        raise Echec(f"route_state ≠ {etat} après 15 s (dernier lu : {self.etat_route()})")

    def console(self, ordre):
        ordre = dict(ordre, presence=True)
        self.pub_console.publish(StringTime(msg=json.dumps(ordre), time=0, anim=False))
        self.cap["console"].append((time.monotonic(), ordre))

    def bouche(self, valeur):
        self.pub_bouche.publish(StringTime(msg=json.dumps(valeur), time=0, anim=False))
        self.cap["bouche"].append((time.monotonic(), valeur))

    def ev(self, nom, **infos):
        self.cap["evenements"][nom] = dict(infos, t=time.monotonic())
        print(f"  [{self.t():6.1f} s] {nom} {infos if infos else ''}", flush=True)

    def t(self):
        return time.monotonic() - self.t0 if self.t0 else -1.0

    def roule(self):
        """Didier avance : consigne cmd_vel_follow > 0,05 m/s dans la dernière 0,5 s."""
        now = time.monotonic()
        return any(abs(l) > 0.05 for t, l, a in self.cap["cmd_vel"][-40:] if t >= now - 0.5)

    def _une_fois(self, nom, cond=True):
        if nom in self.faits or not cond:
            return False
        self.faits.add(nom)
        return True

    # --- mise en route -------------------------------------------------------------
    def mise_en_route(self):
        self.cap["evenements"]["ecoute"] = {"t": time.monotonic()}
        self.attendre(lambda: bool(self.cap["intention"]), 30.0, "intention latchée du sélecteur (découverte)")
        self.attendre(lambda: bool(self.cap["route_state"]), 30.0, "route_state latché (découverte)")
        self.route("off")
        self.publier(self.pub_route, "restart", 3)
        r = subprocess.run(TELEPORT, capture_output=True, text=True)
        print(f"  téléportation à l'origine : code {r.returncode}", flush=True)
        self.dormir(2.0)
        self.publier(self.pub_speed, 1.0, 3)
        self.publier(self.pub_seance, "start", 3)
        self.route("on")
        self.t0 = time.monotonic()
        self.ev("depart")

    # --- le jeu ----------------------------------------------------------------------
    def boite(self):
        t = self.t()
        box = None
        if 60.0 <= t < 110.0:                       # personne A
            if t < 70.0:
                k = (t - 60.0) / 10.0; box = (0.3 - 0.2 * k, 0.2 + 0.4 * k)
            elif t < 100.0:
                box = (0.1, 0.6)
            else:
                k = (t - 100.0) / 10.0; box = (0.1 + 0.4 * k, 0.6 - 0.45 * k)
        elif 300.0 <= t < 303.0:                    # personne B, passe vite
            box = (-0.9 + 0.6 * (t - 300.0), 0.3)
        if box is None:
            return
        m = PointStamped()
        m.header.stamp = self.get_clock().now().to_msg()
        m.point.x, m.point.y, m.point.z = box[0], box[1], 0.9
        self.pub_box.publish(m)

    def scenario(self):
        t = self.t()
        a = next((p for p in self.pistes if p[1] >= self.t0 + 59.0), None)
        if a and self._une_fois("ignore", time.monotonic() >= a[1] + 1.5):
            self.console({"cmd": "ignore", "cible": a[0]}); self.ev("ignore", cible=a[0])
        if a and self._une_fois("va_la_piste", t >= 104.0):
            # A s'éloigne (hauteur ≈ 0,47 < 0,55) : se tourner vers elle puis avancer 1 m.
            self.console({"cmd": "va_la", "cible": a[0]}); self.ev("va_la_piste", cible=a[0])
        if self._une_fois("va_la", t >= 150.0):
            cible = self.objet_devant()
            if cible:
                self.console({"cmd": "va_la", "cible": cible}); self.ev("va_la", cible=cible)
            else:
                self.ev("va_la_impossible", pose=self.pose)
        va = self.cap["evenements"].get("va_la")
        res = [r for r in self.cap["goto_result"] if va and r[0] > va["t"]]
        if self._une_fois("reviens", (res and time.monotonic() > res[0][0] + 2.0) or t >= 240.0):
            self.console({"cmd": "reviens"}); self.ev("reviens")
        # « stop » de David : l'épreuve n'a de sens que si Didier ROULE.
        if "stop_console" not in self.faits and t >= 262.0:
            if self.roule() and t >= 270.0 or t >= 320.0:
                self._une_fois("stop_console")
                self.console({"cmd": "stop"}); self.ev("stop_console", roule=self.roule())
            elif time.monotonic() - self.dernier_go >= 5.0:
                self.dernier_go = time.monotonic()
                self.console({"cmd": "go"}); self.ev("go_avant_stop")
        st = self.cap["evenements"].get("stop_console")
        if st and self._une_fois("go_console", time.monotonic() >= st["t"] + 60.0):
            self.console({"cmd": "go"}); self.ev("go_console")
        if self._une_fois("stop_bouche", t >= 420.0):
            self.bouche("stop"); self.ev("stop_bouche")
        if self._une_fois("go_bouche", t >= 430.0):
            self.bouche("go"); self.ev("go_bouche")

    def objet_devant(self):
        """Objet de rehearsal/objects devant Didier, entre 5 et 35 m (le
        régisseur refuse au-delà de 40 m) : le plus proche."""
        if self.pose is None:
            return None
        x, y, cap = self.pose
        cands = []
        for o in self.cap["objets"]:
            dx, dy = o["x"] - x, o["y"] - y
            d = math.hypot(dx, dy)
            if 5.0 <= d <= 35.0 and dx * math.cos(cap) + dy * math.sin(cap) > 0:
                cands.append((d, o["name"]))
        return min(cands)[1] if cands else None

    def jouer(self):
        prochaine_boite = prochaine_presence = time.monotonic()
        while self.t() < DUREE:
            rclpy.spin_once(self, timeout_sec=0.02)
            now = time.monotonic()
            if now >= prochaine_boite:
                prochaine_boite = now + 0.0625      # 16 Hz, comme la vision
                self.boite()
            if now >= prochaine_presence:
                prochaine_presence = now + 0.5      # battement 2 Hz
                self.pub_console.publish(StringTime(msg=json.dumps({"presence": True}), time=0, anim=False))
            self.scenario()
        self.ev("fin")


rclpy.init()
n = Pilote()
code = 0
try:
    n.mise_en_route()
    n.jouer()
except Echec as e:
    print(f"  MISE EN ROUTE ÉCHOUÉE : {e}", flush=True)
    code = 3
n.cap["pistes"] = n.pistes
json.dump(n.cap, open(SORTIE, "w"))
n.destroy_node()
rclpy.shutdown()
sys.exit(code)
EOF
rc=$?
[ $rc = 0 ] || { echo "=== A1 : mise en route échouée (code $rc) — aucune épreuve jouée $(date +%T) ==="; exit 2; }

echo "=== verdicts (journal du jeu + captures du pilote) $(date +%T) ==="
python3 - "$JJ" "$RJ" "$CAP/capture.json" > $CAP/verdicts.txt <<'EOF'
import json, sys
jj, rj, capf = sys.argv[1:]
cap = json.load(open(capf))
ev = cap["evenements"]
t_ecoute, t0, tfin = ev["ecoute"]["t"], ev["depart"]["t"], ev["fin"]["t"]
# Journal du jeu depuis que le pilote ÉCOUTE (avant la mise en route : aucun trou).
J = [json.loads(l) for l in open(jj, encoding="utf-8") if l.strip()]
J = [e for e in J if t_ecoute * 1000 <= e["t_mono_ms"] <= tfin * 1000]
R = [json.loads(l) for l in open(rj, encoding="utf-8") if l.strip()]
def ts(e): return e["t_mono_ms"] / 1000.0
def typ(t): return [e for e in J if e["type"] == t]
def V(okb, texte): print(("1" if okb else "0") + "\t" + texte)
def cle(e):
    p = e["payload"]; return (p["action"], p.get("cible"), p.get("sequence"))

# T1 : TOUTE paire de décisions successives (spontanée -> spontanée comprise) à >= 2 s
# (t_mono_ms tronqué à la ms : 1 999 ms = 2,000 s) ; aucun retour A -> B -> A en < 5 s.
dec = typ("decision")
ecarts = [round(ts(b) - ts(a), 3) for a, b in zip(dec, dec[1:])]
retours = [(cle(a)[0], cle(b)[0], round(ts(c) - ts(a), 2)) for a, b, c in zip(dec, dec[1:], dec[2:])
           if cle(a) == cle(c) and cle(a) != cle(b) and ts(c) - ts(a) < 5.0]
print(f"#  décisions : {len(dec)} ; écart minimal entre deux : {min(ecarts) if ecarts else None} s ; "
      f"retours A->B->A en < 5 s : {retours}")
V(len(dec) >= 5 and all(e >= 1.999 for e in ecarts) and not retours,
  "T1 zéro oscillation (toute décision >= 2 s après la précédente, aucun retour en < 5 s)")

# T2 : fréquences.
sp = [ts(e) for e in dec if e["payload"]["spontanee"]]
gaps = [round(b - a, 2) for a, b in zip(sp, sp[1:])]
print(f"#  initiatives spontanées : {len(sp)} ; écart minimal : {min(gaps) if gaps else None} s")
V(len(sp) >= 2 and all(g >= 7.999 for g in gaps), "T2 initiatives spontanées espacées d'au moins 8 s")
arrets = typ("arret_didier")
ta = [ts(e) for e in arrets]
print("#  arrêts de Didier : " + ", ".join(f"{e['payload'].get('kind')} à {ts(e) - t0:.0f} s" for e in arrets))
V(len(ta) >= 1 and all(b - a >= 119.999 for a, b in zip(ta, ta[1:])),
  "T2 au plus un arrêt de Didier (lubie, approche, bouche) par 120 s, au moins un joué")
stops = [t for t, m in cap["jeu_chat_move"] if m == "stop"]
inten = [(t, i) for t, i in cap["intention"] if i.get("action") == "lubie"]
ok_pre, n_lubie = True, 0
for e in arrets:
    if e["payload"].get("kind") != "lubie":
        continue
    n_lubie += 1
    cible = e["payload"]["cible"]
    t_stop = min((t for t in stops if t >= ts(e) - 0.2), default=None)
    t_int = min((t for t, i in inten if i.get("cible") == cible and t_stop and t_stop - 10.0 <= t <= t_stop),
                default=None)
    t_look = max((t for t, l in cap["look"] if t_stop and t_stop - 10.0 <= t <= t_stop), default=None)
    di = None if t_stop is None or t_int is None else round(t_stop - t_int, 2)
    dl = None if t_stop is None or t_look is None else round(t_stop - t_look, 2)
    print(f"#    arrêt-lubie {cible} : intention {di} s et regard {dl} s avant le stop (regard={e['payload'].get('regard')})")
    # Capture = réception : 0,1 s de transport toléré ; pas de capture = KO (plus de « hors fenêtre »).
    ok_pre = ok_pre and di is not None and di >= 2.9 and dl is not None and dl >= 2.9
V(ok_pre and n_lubie >= 1, "T2 chaque arrêt-lubie : regard ET intention publiés >= 3 s avant le stop")

# T3 : chaque offre née (personne OU objet) -> ligne de décision (choix ou maintien) <= 1 s.
nees = [(ts(e), e["payload"]["piste"], "personne") for e in typ("naissance_piste")] + \
       [(ts(e), e["payload"]["piste"], "objet") for e in typ("offre") if e["payload"].get("kind") == "objet"]
rep = [e for e in J if e["type"] in ("decision", "maintien") and e["payload"].get("reaction_a")]
pires, ok3 = [], True
for t_n, cible, kind in nees:
    r = [ts(e) - t_n for e in rep if cible in e["payload"]["reaction_a"] and ts(e) >= t_n - 0.001]
    d = round(min(r), 2) if r else None
    pires.append((d if d is not None else 99.0, kind, cible))
    ok3 = ok3 and d is not None and d <= 1.0
pires.sort(reverse=True)
print(f"#  offres nées : {sum(1 for x in nees if x[2] == 'personne')} personnes, "
      f"{sum(1 for x in nees if x[2] == 'objet')} objets ; plus lentes réponses : {pires[:3]}")
V(ok3 and any(k == "personne" for _, _, k in nees) and any(k == "objet" for _, _, k in nees),
  "T3 réaction <= 1 s à chaque offre née (personnes et objets)")

# T4 ignore.
ig = ev.get("ignore")
vers = [round(ts(e) - ig["t"], 1) for e in dec if ig and e["payload"]["cible"] == ig["cible"]
        and ig["t"] <= ts(e) < ig["t"] + 30.0] if ig else None
print(f"#  ignore {ig and ig['cible']} : décisions vers elle dans les 30 s : {vers}")
V(bool(ig) and not vers, "T4 ignore : aucune action vers la piste pendant 30 s")
# T4 va_la vers une PISTE (approcher).
vp = ev.get("va_la_piste")
av = [m for t, m in cap["jeu_chat_move"] if vp and t >= vp["t"] and isinstance(m, dict) and m.get("cmd") == "avancer"]
acc_av = [e["payload"].get("effect") for e in R if vp and e.get("type") == "avancer" and e["t_mono_ms"] / 1000.0 >= vp["t"]]
tou = [m for t, m in cap["jeu_chat_move"] if vp and vp["t"] <= t <= vp["t"] + 20 and isinstance(m, dict)
       and m.get("cmd") == "tourner"]
print(f"#  va_la {vp and vp['cible']} : tourner {tou} ; avancer {av[:1]} ; régisseur avancer {acc_av[:1]}")
V(bool(av) and av[0] == {"cmd": "avancer", "metres": 1.0} and acc_av[:1] == ["accepted"],
  "T4 va_la vers une piste : s'approcher (avancer 1 m) accepté par le régisseur")
# T4 va_la vers un objet.
va = ev.get("va_la")
acc = [e for e in R if e.get("type") == "aller_voir" and va and e["t_mono_ms"] / 1000.0 >= va["t"]
       and e["payload"].get("name") == va["cible"]]
res = [r for t, r in cap["goto_result"] if va and t >= va["t"] and r.get("name") == va["cible"]]
print(f"#  va_la {va and va.get('cible')} : régisseur {[e['payload'].get('effect') for e in acc]} ; résultat {[r.get('result') for r in res]}")
V(bool(acc) and acc[0]["payload"].get("effect") == "accepted" and bool(res),
  "T4 va_la vers un objet : aller_voir accepté par le régisseur et route_goto_result reçu")
# T4 stop console : fenêtres SANS marge (revue A1) — demandes dès le stop, vitesse dès l'arrêt constaté.
st, go = ev.get("stop_console"), ev.get("go_console")
relais = min((t for t, m in cap["jeu_chat_move"] if m == "stop" and st and t >= st["t"]), default=None)
avant = [abs(l) for t, l, a in cap["cmd_vel"] if st and st["t"] - 1.0 <= t < st["t"]]
zero = min((t for t, l, a in cap["cmd_vel"] if st and t >= st["t"] and abs(l) < 0.02 and abs(a) < 0.05), default=None)
pendant = [abs(l) for t, l, a in cap["cmd_vel"] if zero and go and zero <= t < go["t"]]
moves = [m for t, m in cap["jeu_chat_move"] if st and go and st["t"] <= t < go["t"] and m != "stop"]
dep = [e["payload"]["action"] for e in dec if st and go and st["t"] <= ts(e) < go["t"] and e["payload"]["deplacement"]]
print(f"#  stop console : relayé en {None if relais is None else round((relais - st['t']) * 1000)} ms ; "
      f"vitesse avant {round(max(avant), 3) if avant else None} ; à zéro après {None if zero is None else round(zero - st['t'], 2)} s ; "
      f"max ensuite {max(pendant) if pendant else None} ; demandes : {moves} ; déplacements décidés : {dep}")
V(bool(avant) and max(avant) > 0.05 and zero is not None and zero - st["t"] < 1.0 and relais is not None,
  "T4 stop : Didier qui ROULAIT est à l'arrêt en < 1 s")
V(bool(pendant) and max(pendant) < 0.02 and not moves and not dep,
  "T4 stop : aucune vitesse, aucune demande, aucun déplacement décidé jusqu'au go")
# T5 arrêt vocal.
sb = ev.get("stop_bouche")
rel = min((t for t, m in cap["jeu_chat_move"] if m == "stop" and sb and t >= sb["t"]), default=None)
jr = [e for e in typ("relais_stop") if e["payload"]["source"] == "bouche" and sb and ts(e) >= sb["t"] - 0.1]
lat = None if rel is None else round((rel - sb["t"]) * 1000)
print(f"#  stop de la bouche relayé en {lat} ms ; journal relais_stop : {len(jr)}")
V(lat is not None and lat < 200 and bool(jr), "T5 stop de la bouche relayé en < 200 ms, sans score (relais_stop)")
# T6 lisibilité, sur ce que la page REÇOIT (topic jeu/journal, pas le fichier).
ti = [t for t, i in cap["intention"] if t0 <= t <= tfin and i.get("action")]
trous = max((b - a for a, b in zip(ti, ti[1:])), default=99.0)
vides = [i for t, i in cap["intention"] if not i.get("action")]
lignes = cap["journal"]
muettes = [e["type"] for e in lignes if not str(e["payload"].get("pourquoi", "")).strip()
           or e["payload"].get("pourquoi") == "(absent — bug)" or "bug_sans_pourquoi" in e["payload"]]
print(f"#  intentions reçues : {len(ti)} ; plus long silence : {trous:.2f} s ; vides : {len(vides)} ; "
      f"lignes du topic jeu/journal : {len(lignes)} dont sans pourquoi : {len(muettes)}")
V(trous <= 1.0 and not vides, "T6 jeu/intention jamais muette ni vide plus de 1 s")
V(not muettes and len(lignes) > 0, "T6 chaque ligne du topic jeu/journal porte un pourquoi (jamais « absent — bug »)")
EOF
grep '^#' $CAP/verdicts.txt | sed 's/^#/ /'
while IFS=$'\t' read -r v txt; do verdict "$v" "$txt"; done < <(grep -v '^#' $CAP/verdicts.txt)
echo "  journal du jeu : $JJ"
echo "=== A1 : $ok OK, $ko KO $(date +%T) ==="
[ "$ko" = 0 ]
