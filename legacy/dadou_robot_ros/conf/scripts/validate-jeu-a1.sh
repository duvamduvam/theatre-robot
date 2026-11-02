#!/bin/bash
# A1 — porte de sortie REJOUABLE du sélecteur de jeu (spec theatre-robot/docs/
# spec-A1-selecteur-de-jeu.md §6), DANS le conteneur sim : monde `chantiers`,
# chaîne roues + rehearsal.launch.py route:=chantiers scenario:=jeu-a1 jeu:=true
# + gaze_follower + didier_jeu (jeu_node) déjà lancés, route OFF.
# Durée ≈ 16 min (15 min de jeu + mise en route).
#
# La PERCEPTION EST SCRIPTÉE PAR CE SCRIPT (pilote rclpy longue durée, PAS de
# `ros2 topic pub` : le CLI se fait découvrir en retard sur le PC de dev, cf.
# operations.md §Séance « Chantiers ») : personne A approche à t=60 s, reste
# 30 s, s'éloigne ; personne B passe vite à t=300 s ; silence ensuite.
# Console jouée par le script : ignore pendant l'approche de A, va_la vers un
# objet devant (t=150 s) puis reviens, go+stop (t=262/270 s) puis go (330 s),
# « stop » de la BOUCHE (t=420 s) puis « go » (430 s). Route ON, séance startée.
#
# T1 zéro oscillation : jamais deux décisions DIFFÉRENTES à < 2 s (journal)
# T2 fréquences      : initiatives spontanées >= 8 s ; <= 1 arrêt de Didier / 120 s ;
#                      chaque arrêt précédé d'une intention publiée >= 3 s avant le stop
# T3 réaction        : chaque naissance de piste -> décision ou maintien en <= 1 s
# T4 console         : ignore -> rien vers la piste 30 s ; va_la -> aller_voir accepté
#                      (journal du régisseur + route_goto_result) ; stop -> arrêt < 1 s
#                      et aucune initiative de déplacement jusqu'au go
# T5 arrêt vocal     : stop de la bouche relayé en < 200 ms, journal relais_stop
# T6 lisibilité      : jeu/intention jamais muette > 1 s ; chaque ligne a un pourquoi
# T7 domaine         : jeu_node refuse de démarrer hors 43 (le garde-fou de
#                      robot_rehearsal, testé aussi sur l'hôte : test_contrat_node.py)
source /opt/ros/${ROS_DISTRO}/setup.sh
source /home/ros2_ws/install/setup.bash
CAP=/tmp/vja1; rm -rf $CAP; mkdir -p $CAP
JDIR=/home/ros2_ws/log/jeu
RDIR=/home/ros2_ws/log/rehearsal
DUREE=${DUREE:-900}
ok=0; ko=0
verdict() { if [ "$1" = 1 ]; then echo "  ✅ $2"; ok=$((ok+1)); else echo "  ❌ $2"; ko=$((ko+1)); fi; }
# Salves idempotentes, comme V-R3 (le CLI ros2 part souvent avant d'être découvert).
P() { timeout 20 ros2 topic pub -t 10 -r 2 "$1" robot_interfaces/msg/StringTime "{msg: \"$2\"}" >/dev/null 2>&1; }
ROUTE() { for i in 1 2; do P route "$1"; st=$(timeout 6 ros2 topic echo --once route_state --field msg --qos-durability transient_local 2>/dev/null | head -1); [ "$st" = "$1" ] && return 0; done; echo "  ⚠️ route_state ≠ $1 après 2 salves (dernier : ${st:-aucun})"; return 1; }

# --- PRÉCONDITIONS -----------------------------------------------------------
for proc in jeu_node route_driver fault_relay director twist_deadman animations_node gaze_follower servos_sim_node; do
  pgrep -f "/$proc\$|/$proc " >/dev/null || { echo "PRÉCONDITION : processus « $proc » absent (ANIMATIONS=true ? gaze_follower ? chaîne roues ? rehearsal.launch.py jeu:=true ? ros2 run didier_jeu jeu_node ?)"; exit 2; }
done
pgrep -af "/director " | grep -q "rehearsal/chat_move:=jeu/chat_move" || { echo "PRÉCONDITION : le régisseur n'est pas remappé sur jeu/chat_move (rehearsal.launch.py jeu:=true)"; exit 2; }
timeout 10 gz model --list 2>/dev/null | grep -q titan_grise || { echo "PRÉCONDITION : modèle titan_grise absent (WORLD=chantiers ?)"; exit 2; }
JJ=$(ls -t $JDIR/*_jeu.jsonl 2>/dev/null | head -1)
jpid=$(basename "$JJ" 2>/dev/null | cut -d_ -f2)
[ -n "$jpid" ] && kill -0 "$jpid" 2>/dev/null || { echo "PRÉCONDITION : aucun jeu_node vivant avec journal dans $JDIR"; exit 2; }
RJ=$(ls -t $RDIR/*_jeu-a1.jsonl 2>/dev/null | head -1)
rpid=$(basename "$RJ" 2>/dev/null | cut -d_ -f3)
[ -n "$rpid" ] && kill -0 "$rpid" 2>/dev/null || { echo "PRÉCONDITION : aucun régisseur vivant avec le scénario jeu-a1 (scenario:=jeu-a1 ?)"; exit 2; }
echo "  journal du jeu : $JJ"
echo "  journal du régisseur : $RJ"

echo "=== T7 domaine : jeu_node refuse hors 43 $(date +%T) ==="
# Refus AVANT rclpy.init : rien n'est créé sur le domaine 42 (gravé en test).
out7=$(ROS_DOMAIN_ID=42 timeout 30 ros2 run didier_jeu jeu_node 2>&1); rc7=$?
echo "  code de sortie : $rc7 ; $(echo "$out7" | grep -o 'refuse de démarrer[^(]*' | head -1)"
verdict "$([ $rc7 != 0 ] && [ $rc7 != 124 ] && echo "$out7" | grep -q "ROS_DOMAIN_ID='42'" && echo 1 || echo 0)" "ROS_DOMAIN_ID=42 : refus au démarrage (code ≠ 0, message du garde-fou)"

echo "=== mise en route : téléportation, séance START, route ON $(date +%T) ==="
ROUTE off; P route restart
timeout 10 gz service -s /world/stage/set_pose --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 3000 \
  --req 'name: "dadou_robot", position: {x: 0, y: 0, z: 0.3}, orientation: {w: 1}' >/dev/null 2>&1
# START AVANT route on (un « go » de Didier hors séance serait ignoré par le régisseur).
sleep 2; P route_speed 1.0; P rehearsal/cmd start; ROUTE on

echo "=== jeu de $DUREE s, perception et console scriptées $(date +%T) ==="
python3 - "$CAP/capture.json" "$DUREE" <<'EOF'
import json, math, sys, time
import rclpy
from geometry_msgs.msg import PointStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from robot_interfaces.msg import StringTime

SORTIE, DUREE = sys.argv[1], float(sys.argv[2])
LATCHE = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)


class Pilote(Node):
    def __init__(self):
        super().__init__("validate_jeu_a1")
        self.cap = {"intention": [], "jeu_chat_move": [], "cmd_vel": [], "goto_result": [], "console": [],
                    "bouche": [], "evenements": {}, "objets": [], "pose": []}
        self.pub_box = self.create_publisher(PointStamped, "vision/person_box", 10)
        self.pub_console = self.create_publisher(StringTime, "jeu/console", 10)
        self.pub_bouche = self.create_publisher(StringTime, "rehearsal/chat_move", 10)
        self.create_subscription(StringTime, "jeu/intention", self._intention, LATCHE)
        self.create_subscription(StringTime, "jeu/chat_move", self._move, 10)
        self.create_subscription(StringTime, "jeu/journal", self._journal, 10)
        self.create_subscription(Twist, "cmd_vel_follow", self._cmd, 10)
        self.create_subscription(StringTime, "route_goto_result", self._goto, 10)
        self.create_subscription(StringTime, "rehearsal/objects", self._objets, LATCHE)
        self.create_subscription(Odometry, "/ground_truth/odom", self._odom, 10)
        self.pose = None
        self.pistes = []          # (id, t) des naissances vues sur jeu/journal
        self.t0 = None
        self.faits = set()
        self.create_timer(0.0625, self._box)        # 16 Hz, comme la vision
        self.create_timer(0.5, self._presence)      # battement 2 Hz
        self.create_timer(0.1, self._scenario)

    # --- captures (horloge MONOTONE : la même que t_mono_ms des journaux) --------
    def _intention(self, m):
        self.cap["intention"].append((time.monotonic(), json.loads(m.msg)))

    def _move(self, m):
        self.cap["jeu_chat_move"].append((time.monotonic(), json.loads(m.msg)))

    def _journal(self, m):
        ev = json.loads(m.msg)
        if ev.get("type") == "naissance_piste":
            self.pistes.append((ev["payload"]["piste"], time.monotonic()))

    def _cmd(self, m):
        self.cap["cmd_vel"].append((time.monotonic(), m.linear.x, m.angular.z))

    def _goto(self, m):
        self.cap["goto_result"].append((time.monotonic(), json.loads(m.msg)))

    def _objets(self, m):
        self.cap["objets"] = json.loads(m.msg)

    def _odom(self, m):
        p, q = m.pose.pose.position, m.pose.pose.orientation
        self.pose = (p.x, p.y, math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y ** 2 + q.z ** 2)))

    # --- sorties ---------------------------------------------------------------
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

    def _presence(self):
        if self.t0 is not None:
            self.pub_console.publish(StringTime(msg=json.dumps({"presence": True}), time=0, anim=False))

    def _box(self):
        t = self.t()
        if t < 0:
            return
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

    def _une_fois(self, nom, cond=True):
        if nom in self.faits or not cond:
            return False
        self.faits.add(nom)
        return True

    def _scenario(self):
        if self.t0 is None:
            # Départ quand le jeu est DÉCOUVERT (intention latchée reçue) : les
            # premiers messages d'un publieur neuf partent sinon dans le vide.
            if self.cap["intention"]:
                self.t0 = time.monotonic()
                self.ev("depart")
            return
        t = self.t()
        a = next((p for p in self.pistes if p[1] >= self.t0 + 59.0), None)
        if a and self._une_fois("ignore", time.monotonic() >= a[1] + 1.5):
            self.console({"cmd": "ignore", "cible": a[0]}); self.ev("ignore", cible=a[0])
        if self._une_fois("va_la", t >= 150.0):
            cible = self._objet_devant()
            if cible:
                self.console({"cmd": "va_la", "cible": cible}); self.ev("va_la", cible=cible)
            else:
                self.ev("va_la_impossible", pose=self.pose)
        va = self.cap["evenements"].get("va_la")
        res = [r for r in self.cap["goto_result"] if va and r[0] > va["t"]]
        if self._une_fois("reviens", (res and time.monotonic() > res[0][0] + 2.0) or t >= 240.0):
            self.console({"cmd": "reviens"}); self.ev("reviens")
        if self._une_fois("go_avant_stop", t >= 262.0):
            self.console({"cmd": "go"}); self.ev("go_avant_stop")
        if self._une_fois("stop_console", t >= 270.0):
            self.console({"cmd": "stop"}); self.ev("stop_console")
        if self._une_fois("go_console", t >= 330.0):
            self.console({"cmd": "go"}); self.ev("go_console")
        if self._une_fois("stop_bouche", t >= 420.0):
            self.bouche("stop"); self.ev("stop_bouche")
        if self._une_fois("go_bouche", t >= 430.0):
            self.bouche("go"); self.ev("go_bouche")
        if t >= DUREE:
            self.ev("fin")
            raise SystemExit

    def _objet_devant(self):
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


rclpy.init()
n = Pilote()
try:
    rclpy.spin(n)
except SystemExit:
    pass
n.cap["pistes"] = n.pistes
json.dump(n.cap, open(SORTIE, "w"))
n.destroy_node()
rclpy.shutdown()
EOF

echo "=== verdicts (journal du jeu + captures) $(date +%T) ==="
python3 - "$JJ" "$RJ" "$CAP/capture.json" > $CAP/verdicts.txt <<'EOF'
import json, sys
jj, rj, capf = sys.argv[1:]
cap = json.load(open(capf))
ev = cap["evenements"]
t0 = ev["depart"]["t"]; tfin = ev["fin"]["t"]
J = [json.loads(l) for l in open(jj, encoding="utf-8") if l.strip()]
J = [e for e in J if t0 * 1000 - 5000 <= e["t_mono_ms"] <= tfin * 1000]
R = [json.loads(l) for l in open(rj, encoding="utf-8") if l.strip()]
def ts(e): return e["t_mono_ms"] / 1000.0
def typ(t): return [e for e in J if e["type"] == t]
def V(okb, texte): print(("1" if okb else "0") + "\t" + texte)

# T1 : décisions DIFFÉRENTES successives à >= 2 s (le maintien n'est pas un changement).
dec = typ("decision")
pires = [(round(ts(b) - ts(a), 3), a["payload"]["action"], b["payload"]["action"]) for a, b in zip(dec, dec[1:])
         if (a["payload"]["action"], a["payload"]["cible"]) != (b["payload"]["action"], b["payload"]["cible"])]
mini = min((p[0] for p in pires), default=None)
print(f"#  décisions : {len(dec)} ; écart minimal entre deux changements : {mini} s")
V(all(p[0] >= 1.999 for p in pires) and len(dec) >= 5, f"T1 zéro oscillation ({len(pires)} changements, aucun < 2 s)")

# T2 : fréquences.
sp = [ts(e) for e in dec if e["payload"]["spontanee"]]
gaps = [round(b - a, 2) for a, b in zip(sp, sp[1:])]
print(f"#  initiatives spontanées : {len(sp)} ; écart minimal : {min(gaps) if gaps else None} s")
V(len(sp) >= 2 and all(g >= 7.999 for g in gaps), "T2 initiatives spontanées espacées d'au moins 8 s")
arrets = typ("arret_didier")
ta = [ts(e) for e in arrets]
print(f"#  arrêts de Didier : {len(ta)} à " + ", ".join(f"{t - t0:.0f} s" for t in ta))
V(len(ta) >= 1 and all(b - a >= 119.999 for a, b in zip(ta, ta[1:])), "T2 au plus un arrêt de Didier par 120 s (au moins un arrêt joué)")
stops = [t for t, m in cap["jeu_chat_move"] if m == "stop"]
inten = [(t, i) for t, i in cap["intention"] if i.get("action") == "lubie"]
ok_pre = True
for e in arrets:
    t_stop = min((t for t in stops if t >= ts(e) - 0.5), default=None)
    t_int = min((t for t, i in inten if i.get("cible") == e["payload"]["cible"] and t <= (t_stop or 0)
                 and t >= (t_stop or 0) - 10.0), default=None)
    d = None if t_stop is None or t_int is None else round(t_stop - t_int, 2)
    print(f"#    arrêt {e['payload']['cible']} : intention reçue {d} s avant le stop")
    ok_pre = ok_pre and d is not None and d >= 2.9
V(ok_pre and arrets, "T2 chaque arrêt précédé de son intention publiée >= 3 s avant le stop (tolérance de réception 0,1 s)")

# T3 : réaction <= 1 s à chaque naissance de piste.
nee = typ("naissance_piste")
rep = [e for e in J if e["type"] in ("decision", "maintien") and e["payload"].get("reaction_a")]
ok3 = True
for n in nee:
    r = [ts(e) - ts(n) for e in rep if e["payload"]["reaction_a"] == n["payload"]["piste"] and ts(e) >= ts(n)]
    d = round(min(r), 2) if r else None
    print(f"#  piste {n['payload']['piste']} née à {ts(n) - t0:.1f} s : ligne de décision après {d} s")
    ok3 = ok3 and d is not None and d <= 1.0
V(ok3 and len(nee) >= 2, f"T3 réaction <= 1 s pour chaque naissance de piste ({len(nee)} pistes)")

# T4 ignore.
ig = ev.get("ignore")
if ig:
    vers = [round(ts(e) - ig["t"], 1) for e in dec if e["payload"]["cible"] == ig["cible"]
            and ig["t"] <= ts(e) < ig["t"] + 30.0]
    print(f"#  ignore {ig['cible']} : décisions vers elle dans les 30 s : {vers}")
V(bool(ig) and not vers, "T4 ignore : aucune action vers la piste pendant 30 s")
# T4 va_la.
va = ev.get("va_la")
acc = [e for e in R if e.get("type") == "aller_voir" and va and e["t_mono_ms"] / 1000.0 >= va["t"]
       and e["payload"].get("name") == va["cible"]]
res = [r for t, r in cap["goto_result"] if va and t >= va["t"] and r.get("name") == va["cible"]]
print(f"#  va_la {va and va.get('cible')} : régisseur {[e['payload'].get('effect') for e in acc]} ; résultat {[r.get('result') for r in res]}")
V(bool(acc) and acc[0]["payload"].get("effect") == "accepted" and bool(res),
  "T4 va_la : aller_voir accepté par le régisseur (journal) et route_goto_result reçu")
# T4 stop console.
st, go = ev.get("stop_console"), ev.get("go_console")
relais = min((t for t, m in cap["jeu_chat_move"] if m == "stop" and st and t >= st["t"]), default=None)
avant = [abs(l) for t, l, a in cap["cmd_vel"] if st and st["t"] - 1.0 <= t < st["t"]]
zero = min((t for t, l, a in cap["cmd_vel"] if st and t >= st["t"] and abs(l) < 0.02 and abs(a) < 0.05), default=None)
pendant = [abs(l) for t, l, a in cap["cmd_vel"] if st and go and st["t"] + 1.0 <= t < go["t"]]
moves = [m for t, m in cap["jeu_chat_move"] if st and go and st["t"] + 0.5 <= t < go["t"]]
dep = [e["payload"]["action"] for e in dec if st and go and st["t"] <= ts(e) < go["t"] and e["payload"]["deplacement"]]
print(f"#  stop console : relayé en {None if relais is None else round((relais - st['t']) * 1000)} ms ; "
      f"vitesse avant {max(avant) if avant else None} ; à zéro après {None if zero is None else round(zero - st['t'], 2)} s ; "
      f"max pendant le verrou {max(pendant) if pendant else None} ; chat_move pendant : {moves} ; déplacements décidés : {dep}")
V(zero is not None and zero - st["t"] < 1.0 and relais is not None, "T4 stop : Didier à l'arrêt en < 1 s")
V(bool(pendant) and max(pendant) < 0.02 and not moves and not dep, "T4 stop : aucune initiative de déplacement jusqu'au go")
# T5 arrêt vocal.
sb = ev.get("stop_bouche")
rel = min((t for t, m in cap["jeu_chat_move"] if m == "stop" and sb and t >= sb["t"]), default=None)
jr = [e for e in typ("relais_stop") if e["payload"]["source"] == "bouche" and sb and ts(e) >= sb["t"] - 0.1]
lat = None if rel is None else round((rel - sb["t"]) * 1000)
print(f"#  stop de la bouche relayé en {lat} ms ; journal relais_stop : {len(jr)}")
V(lat is not None and lat < 200 and bool(jr), "T5 stop de la bouche relayé en < 200 ms, sans score (relais_stop)")
# T6 lisibilité.
ti = [t for t, i in cap["intention"] if t0 <= t <= tfin and i.get("action")]
trous = max((b - a for a, b in zip(ti, ti[1:])), default=99.0)
vides = [i for t, i in cap["intention"] if not i.get("action")]
sans = [e["type"] for e in J if not str(e["payload"].get("pourquoi", "")).strip()]
print(f"#  intentions reçues : {len(ti)} ; plus long silence : {trous:.2f} s ; vides : {len(vides)} ; lignes sans pourquoi : {len(sans)} / {len(J)}")
V(trous <= 1.0 and not vides, "T6 jeu/intention jamais muette ni vide plus de 1 s")
V(not sans and len(J) > 0, "T6 chaque ligne du journal porte un pourquoi non vide")
EOF
grep '^#' $CAP/verdicts.txt | sed 's/^#/ /'
while IFS=$'\t' read -r v txt; do verdict "$v" "$txt"; done < <(grep -v '^#' $CAP/verdicts.txt)
echo "  journal du jeu : $JJ"
echo "=== A1 : $ok OK, $ko KO $(date +%T) ==="
[ "$ko" = 0 ]
