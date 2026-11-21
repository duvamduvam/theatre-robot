#!/bin/bash
# CS — épreuves du CORPS SÛR (lot A0-4, spec docs/spec-A0-corps-sur.md §8.5), DANS le conteneur
# `monde` : monde `stage` (plateau nu, obstacle et passant scriptés d'A0-2), vrai bringup du robot
# (drive.launch.py : corps_sur devant twist_mux, configuration machines/sim/robot/corps_sur.yaml).
# Pilote rclpy en HORLOGE SIMULÉE (use_sim_time) : tous les temps sont des temps simulés. `T0`
# d'une apparition = horodatage du DERNIER message de vérité terrain (sim/obstacle_pose, 100 Hz)
# qui montre l'obstacle encore à l'ancienne place (erreur ≤ 10 ms, comptée contre nous). Les
# réceptions du pilote (cmd_vel, …) sont horodatées à SON horloge : un retard de sa boucle compte
# aussi contre nous. Graine fixe 20261118. Téléportations par gz-transport (service set_pose).
#
# 25 verdicts (ATTENDU_CORPS_SUR=25 dans fumee.sh) :
#   CS1  démarrage (3)   a. scan à 10 Hz ± 10 %, 500 rayons (échelon 1 retenu en A0-2)
#                        b. nœud relancé : ARME moins de 5 s après son premier état (1er balayage)
#                        c. `vue` publié conforme à la pose A : avant seul
#   CS2  porte de l'étude (4) : cmd_vel_follow 0,3 m/s, obstacle posé à 0,5 m de la caisse, 20
#                        relèvements tirés dans la région vue (l'AVANT : bord avant et coins
#                        jusqu'à 60°) ; a. 20/20 premier zéro sur cmd_vel < 200 ms après T0 à 20 Hz ;
#                        b. distance parcourue après T0 ≤ 0,15 m (40 essais) ; c. aucune distance
#                        vraie caisse-obstacle sous 0,30 m (40 essais) ; d. les 20 mêmes à 5 Hz :
#                        20/20 < 200 ms (le zéro anticipé) ; max et médiane au journal
#   CS3  reprise (1)     obstacle retiré, source active : cmd_vel non nul entre 0,2 et 1,0 s après
#                        (borne basse 0,2 et non 0,3 : voir la note « CS3 » plus bas)
#   CS4  trois canaux (2) a. cmd_vel_web (publié ici) ; b. cmd_vel_anim par le VRAI chemin
#                        (little-move3 jouée par animations_node, obstacle posé dès sa phase avant)
#   CS5  moon-walk (1)   arrière non vu : jamais de linear.x < 0 sur cmd_vel alors que cmd_vel_anim
#                        en porte, motif recul_aveugle publié (diagnostics). La seconde moitié de la
#                        spec (« ARRIERE vue ») n'est pas jouable avec la pose A : voir la note « CS5 »
#   CS6  ralenti (1)     obstacle à 0,9 m : cmd_vel = 0,15 ± 0,01 pour 0,3 ; à 1,5 m : 0,30
#   CS7  télécommande non filtrée (1) obstacle à 0,3 m devant, cmd_vel_remote 0,2 pendant 1 s :
#                        cmd_vel = 0,2 ; cmd_vel_follow simultané ne passe pas
#   CS8  capteur perdu en marche (3) SIGSTOP de pont_lidar : a. zéro < 0,45 s après le dernier
#                        balayage, VERROU capteur_perdu ; b. SIGCONT : toujours zéro 3 s après ;
#                        c. rearmer : repart en moins de 2 s
#   CS9  capteur absent au démarrage (2) nœud relancé, pont_lidar figé : a. 5 s de cmd_vel_follow,
#                        aucune sortie non nulle, DEMARRAGE capteur_absent ; b. SIGCONT : ARME en
#                        moins de 3 s sans réarmement
#   CS10 mort du filtre (2) a. kill -9 en marche : zéro < 500 ms, la télécommande conduit toujours ;
#                        b. relancé, SIGSTOP du nœud en marche : zéro < 500 ms
#   CS11 arrêt d'urgence (1) e_stop vrai : zéro en moins de 0,5 s, VERROU e_stop ; faux : la télécommande conduit,
#                        l'autonome reste à zéro ; rearmer : repart
#   CS12 configuration du ROBOT en sim (3) machines/robot/corps_sur.yaml, pose et masques de la sim
#                        substitués (ici identiques), tout le reste intact ; a. superviseur : non
#                        exigé dans le fichier → ARME sans battement ; exigé (variante « avant la
#                        rue ») → DEMARRAGE superviseur_absent, battement 5 Hz → ARME, coupé →
#                        zéro < 1,1 s et VERROU superviseur_perdu ; b. mouvement continu coupé à
#                        4,0 ± 0,1 s, repris après 1 s d'entrées nulles ; c. vitesse plafonnée à 0,25
#   CS13 passant (1)     6 passages en travers (0,5 ; 1,0 ; 1,5 m/s, deux sens), Didier à 0,3 m/s
#                        demandés, trajet recalé pour que la surface du passant approche à 0,5 ±
#                        0,05 m de la caisse (3 rejeux au plus) : distance vraie ≥ 0,30 m à tout
#                        instant ; reprise moins de 1 s après la sortie de zone
# Après chaque épreuve qui relance le nœud, la configuration de la SIM est remise et vérifiée (ARME,
# terrain sim) ; en fin d'épreuve le nœud relancé par ce script reste en marche (la fumée arrête
# la sim de toute façon).
#
# Notes de spec (points ouverts, README de didier_corps_sur) :
#   CS3 : avec balayages_de_sortie = 3 à 10 Hz, la sortie d'ARRET tombe au 3e balayage dégagé,
#         soit 0,2 à 0,3 s après le retrait (le 1er balayage dégagé peut suivre le retrait de
#         quelques ms). La borne basse « 0,3 s » de la spec rougirait une fois sur deux sans
#         défaut : gravée à 0,2 s (= deux périodes), ce qui prouve encore l'hystérésis.
#   CS5 : la pose A (face avant, décision du 18/11) ne voit pas l'arrière ; « ARRIERE vue, obstacle
#         derrière pendant le recul » est éprouvé au niveau du moteur
#         (test_moteur.py::test_arriere_vu_obstacle_derriere_pendant_le_recul), pas en sim.
#   Banc (20/11) : un essai d'obstacle où Didier n'est pas en marche à T0 vu du pilote est rejoué
#         deux fois au plus ; un VERROU capteur_perdu trouvé en tête d'essai (nœud figé > 0,30 s
#         par la charge du PC) est compté, dit et réarmé, deux au plus par passe, sinon rouge.
#         Latence, distance et état attendu ne se rejouent jamais. Les attentes partent du premier
#         /clock (avant lui l'horloge simulée vaut 0).
#
# Variables (essais) : CS_SEULEMENT="CS1,CS2" (sous-ensemble ; le compte final n'est alors pas
# celui de la fumée) ; CS_NOEUD_PYTHONPATH (préfixé au PYTHONPATH du nœud RELANCÉ : contrôle par
# mutation du zéro anticipé, mutant 12 de la spec §6.3).
source /opt/ros/${ROS_DISTRO}/setup.sh
source /home/ros2_ws/install/setup.bash
NS="/${ROBOT_NAME:-didier}"
source /home/ros2_ws/captures.sh

# --- PRÉCONDITIONS (banc faux = code 2, jamais un verdict) ------------------------------------
[ "${ROS_DOMAIN_ID:-}" = 43 ] || { echo "PRÉCONDITION : ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-absent}, 43 exigé"; exit 2; }
for motif in "lib/didier_corps_sur/corps_sur_node" "__node:=pont_lidar" "/twist_deadman" "/twist_mux" \
             "passant_sim_node" "animations_node"; do
  pgrep -f "$motif" >/dev/null || { echo "PRÉCONDITION : processus « $motif » absent (vrai bringup ? monde stage ?)"; exit 2; }
done
MODELES=$(timeout 10 gz model --list 2>/dev/null)
grep -q obstacle <<<"$MODELES" && grep -q passant <<<"$MODELES" \
  || { echo "PRÉCONDITION : modèles obstacle/passant absents (WORLD=stage ?)"; exit 2; }
[ -x /home/ros2_ws/install/didier_corps_sur/lib/didier_corps_sur/corps_sur_node ] \
  || { echo "PRÉCONDITION : didier_corps_sur non construit dans monde"; exit 2; }

# Journal de secours (survit à l'épreuve) : ce que voit l'enregistreur, à l'horloge murale.
capture_demarrer corps-sur \
  --journal $NS/cmd_vel=geometry_msgs/msg/Twist \
  --journal $NS/cmd_vel_follow_sur=geometry_msgs/msg/Twist \
  --journal $NS/cmd_vel_anim_sur=geometry_msgs/msg/Twist \
  --journal $NS/cmd_vel_web_sur=geometry_msgs/msg/Twist \
  --journal $NS/corps_sur/etat=theatre_interfaces/msg/StringTime,latche \
  --dernier $NS/sim/obstacle_pose=geometry_msgs/msg/PoseStamped \
  --dernier $NS/ground_truth/odom=nav_msgs/msg/Odometry

echo "=== CS : corps sûr, pilote en horloge simulée $(date +%T) ==="
python3 - "$NS" <<'EOF'
import json, math, os, random, signal, statistics, subprocess, sys, time
import yaml
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, Empty
from diagnostic_msgs.msg import DiagnosticArray
from theatre_interfaces.msg import StringTime
from gz.msgs10.boolean_pb2 import Boolean
from gz.msgs10.pose_pb2 import Pose as GzPose
from gz.transport13 import Node as NoeudGz
from didier_corps_sur.geometrie import Caisse, distance_caisse

NS = sys.argv[1]
SEULEMENT = {s.strip() for s in os.environ.get("CS_SEULEMENT", "").split(",") if s.strip()}
GRAINE = 20261118
VERROUS_SPONTANES_MAX = 2               # voir Pilote.armer_zone_libre
CAISSE = Caisse()                       # défauts §4.1 = ceux de la sim (gravé)
R_OBSTACLE, R_PASSANT = 0.15, 0.20
X_LIDAR = 0.33
NOEUD_EXE = "/home/ros2_ws/install/didier_corps_sur/lib/didier_corps_sur/corps_sur_node"
CONF_SIM = "/home/ros2_ws/machines/sim/robot/corps_sur.yaml"
CONF_ROBOT = "/home/ros2_ws/machines/robot/corps_sur.yaml"
JOURNAL_NOEUD = "/home/ros2_ws/log/corps-sur-cs.log"
LOIN = (50.0, 0.0)                      # place de l'obstacle hors champ (stage.sdf)
LOIN_PASSANT = (55.0, 0.0)
ORIGINE = (0.0, 0.0, 0.0)               # plateau 10 × 8 m centré : Didier y repart à chaque essai
ZERO = 1e-6
ARC_MAX = math.radians(60)

ok = ko = 0


def verdict(bon, texte):
    global ok, ko
    print(("  ✅ " if bon else "  ❌ ") + texte, flush=True)
    ok, ko = ok + bool(bon), ko + (not bon)


def journal(texte):
    print("#  " + texte, flush=True)


def ms(d):
    return "—" if d is None or not math.isfinite(d) else f"{d * 1000:.0f} ms"


def valeurs(serie):
    return sorted({round(v, 3) for v in serie})


class Echec(Exception):
    pass


def vers_robot(pose, x, y):
    """Point monde → repère de Didier (x devant, y à gauche)."""
    xr, yr, lacet = pose
    dx, dy = x - xr, y - yr
    c, s = math.cos(lacet), math.sin(lacet)
    return c * dx + s * dy, -s * dx + c * dy


def vers_monde(pose, x, y):
    xr, yr, lacet = pose
    c, s = math.cos(lacet), math.sin(lacet)
    return xr + c * x - s * y, yr + s * x + c * y


def pres(serie, t):
    """Échantillon (t, …) le plus proche de t dans une série horodatée croissante."""
    if not serie:
        return None
    lo, hi = 0, len(serie) - 1
    while lo < hi:
        m = (lo + hi) // 2
        if serie[m][0] < t:
            lo = m + 1
        else:
            hi = m
    if lo > 0 and abs(serie[lo - 1][0] - t) < abs(serie[lo][0] - t):
        lo -= 1
    return serie[lo]


def centre_a(d_surface, s, rayon=R_OBSTACLE):
    """Centre (repère de Didier) d'un cylindre dont la SURFACE est à d_surface de la caisse, dans
    la région AVANT : s ∈ [−1, 1] le long du bord avant (|y| ≤ demi_largeur) puis des coins
    arrondis jusqu'à 60° (relèvement vu du lidar ≤ 75°, loin du masque [90, 270])."""
    rc = d_surface + rayon
    demi = CAISSE.demi_largeur
    u = s * (demi + rc * ARC_MAX)
    if abs(u) <= demi:
        return CAISSE.x_avant + rc, u
    a = (abs(u) - demi) / rc
    return CAISSE.x_avant + rc * math.cos(a), math.copysign(demi + rc * math.sin(a), u)


class Pilote(Node):
    def __init__(self):
        super().__init__("validate_corps_sur", namespace=NS,
                         parameter_overrides=[Parameter("use_sim_time", value=True)])
        self.gz = NoeudGz()
        fiable = QoSProfile(depth=100)
        latche = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                            reliability=ReliabilityPolicy.RELIABLE)
        rapide = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.cmd, self.anim_brut, self.scans, self.etats = [], [], [], []
        self.sur = {"anim": [], "follow": [], "web": []}
        self.odom, self.obstacle, self.passant = [], [], []
        self.diag = {}
        self.create_subscription(Twist, "cmd_vel", lambda m: self.cmd.append((self.t(), m.linear.x, m.angular.z)), fiable)
        self.create_subscription(Twist, "cmd_vel_anim",
                                 lambda m: self.anim_brut.append((self.t(), m.linear.x, m.angular.z)), fiable)
        for canal in self.sur:
            self.create_subscription(Twist, f"cmd_vel_{canal}_sur",
                                     lambda m, c=canal: self.sur[c].append((self.t(), m.linear.x, m.angular.z)), fiable)
        self.create_subscription(LaserScan, "scan", self._scan, rapide)
        self.create_subscription(StringTime, "corps_sur/etat", self._etat, latche)
        self.create_subscription(DiagnosticArray, "diagnostics", self._diag, fiable)
        self.create_subscription(Odometry, "ground_truth/odom", self._odom, fiable)
        self.create_subscription(PoseStamped, "sim/obstacle_pose", lambda m: self.obstacle.append(self._pose(m)), fiable)
        self.create_subscription(PoseStamped, "sim/passant_pose", lambda m: self.passant.append(self._pose(m)), fiable)
        self.pubs = {nom: self.create_publisher(Twist, nom, 10)
                     for nom in ("cmd_vel_follow", "cmd_vel_web", "cmd_vel_remote")}
        self.e_stop_pub = self.create_publisher(Bool, "e_stop", 10)
        self.battement_pub = self.create_publisher(Empty, "superviseur/battement", 10)
        self.rearmer_pub = self.create_publisher(Empty, "corps_sur/rearmer", 10)
        self.animation_pub = self.create_publisher(StringTime, "animation", 10)
        self.passant_pub = self.create_publisher(StringTime, "sim/passant", 10)
        # Sources périodiques en horloge simulée : nom -> [v, w, période, prochaine échéance].
        self.sources = {}
        self.battement_periode = None
        self.battement_dernier = None
        self.create_timer(0.005, self._sources)
        self.noeud = None               # Popen du nœud relancé par ce script
        self.verrous_spontanes = 0      # VERROU capteur_perdu trouvés en tête d'essai (banc chargé)

    # --- horloge, réceptions -----------------------------------------------------------------
    def t(self):
        return self.get_clock().now().nanoseconds * 1e-9

    @staticmethod
    def _pose(m):
        return (m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, m.pose.position.x, m.pose.position.y)

    def _scan(self, m):
        self.scans.append((self.t(), m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, len(m.ranges)))

    def _etat(self, m):
        try:
            self.etats.append((self.t(), json.loads(m.msg)))
        except ValueError:
            pass

    def _diag(self, m):
        for s in m.status:
            if s.name.endswith("/corps_sur"):
                self.diag = {kv.key: kv.value for kv in s.values}

    def _odom(self, m):
        q = m.pose.pose.orientation
        lacet = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        self.odom.append((t, m.pose.pose.position.x, m.pose.pose.position.y, lacet))

    def _sources(self):
        t = self.t()
        for nom, s in list(self.sources.items()):
            if t >= s[3]:
                tw = Twist()
                tw.linear.x, tw.angular.z = float(s[0]), float(s[1])
                self.pubs[nom].publish(tw)
                s[3] = max(s[3] + s[2], t)
        if self.battement_periode and (self.battement_dernier is None
                                       or t - self.battement_dernier >= self.battement_periode):
            self.battement_pub.publish(Empty())
            self.battement_dernier = t

    # --- actions -------------------------------------------------------------------------------
    def source(self, nom, v=None, w=0.0, hz=20.0):
        """Source périodique ; v None = muette."""
        if v is None:
            self.sources.pop(nom, None)
        else:
            self.sources[nom] = [v, w, 1.0 / hz, self.t()]

    def silence(self):
        self.sources.clear()

    def dormir(self, s):
        """Attend s secondes SIMULÉES (garde murale : horloge figée 60 s = échec du banc)."""
        self.horloge_recue()
        fin = self.t() + s
        mur, dernier = time.monotonic(), self.t()
        while self.t() < fin:
            rclpy.spin_once(self, timeout_sec=0.005)
            if self.t() != dernier:
                mur, dernier = time.monotonic(), self.t()
            elif time.monotonic() - mur > 60:
                raise Echec("horloge simulée figée depuis 60 s (Gazebo en pause ?)")

    def horloge_recue(self, delai_mur=60.0):
        """Attend le premier /clock : avant lui, l'horloge simulée vaut 0 et toute échéance
        « t() + délai » serait dépassée d'un coup au premier message (vécu le 20/11 : sim lancée
        depuis plus de 30 s simulées, attente initiale « échouée » en 0 s)."""
        fin = time.monotonic() + delai_mur
        while self.t() <= 0.0:
            rclpy.spin_once(self, timeout_sec=0.01)
            if time.monotonic() > fin:
                raise Echec(f"aucun /clock en {delai_mur:g} s murales (Gazebo absent ?)")

    def attendre(self, cond, delai, quoi):
        self.horloge_recue()
        fin = self.t() + delai
        while True:
            if cond():
                return self.t()
            if self.t() >= fin:
                raise Echec(f"{quoi} : pas en {delai:g} s simulées")
            self.dormir(0.01)

    def pose(self):
        if not self.odom:
            raise Echec("aucune vérité terrain (ground_truth/odom)")
        return self.odom[-1][1:]

    def etat(self):
        return self.etats[-1][1] if self.etats else {}

    def poser(self, modele, x, y, z, lacet=0.0):
        req = GzPose()
        req.name = modele
        req.position.x, req.position.y, req.position.z = x, y, z
        req.orientation.z, req.orientation.w = math.sin(lacet / 2), math.cos(lacet / 2)
        for _ in range(3):
            fait, rep = self.gz.request("/world/stage/set_pose", req, GzPose, Boolean, 1000)
            if fait and rep.data:
                return
        raise Echec(f"set_pose {modele} refusé")

    def placer_didier(self, x=ORIGINE[0], y=ORIGINE[1], lacet=ORIGINE[2]):
        self.silence()
        self.dormir(0.8)                 # le deadman a remis zéro, Didier est arrêté
        self.poser("dadou_robot", x, y, 0.24, lacet)
        self.attendre(lambda: math.hypot(self.pose()[0] - x, self.pose()[1] - y) < 0.05, 5, "Didier replacé")
        self.dormir(0.8)

    def poser_obstacle_monde(self, wx, wy):
        """Pose l'obstacle en (wx, wy) monde → T0 (dernier message à l'ancienne place)."""
        n0 = len(self.obstacle)
        ancien = self.obstacle[-1][1:] if self.obstacle else LOIN
        self.poser("obstacle", wx, wy, 0.5)
        self.attendre(lambda: any(math.hypot(o[1] - wx, o[2] - wy) < 0.02 for o in self.obstacle[n0:]), 3,
                      "obstacle posé (vérité terrain)")
        i = next(k for k in range(n0, len(self.obstacle))
                 if math.hypot(self.obstacle[k][1] - wx, self.obstacle[k][2] - wy) < 0.02)
        avant = [o for o in self.obstacle[:i] if math.hypot(o[1] - ancien[0], o[2] - ancien[1]) < 0.02]
        return avant[-1][0] if avant else self.obstacle[i][0] - 0.01

    def poser_obstacle(self, cx, cy):
        """Obstacle dont le CENTRE est en (cx, cy) dans le repère de Didier à cet instant → T0."""
        return self.poser_obstacle_monde(*vers_monde(self.pose(), cx, cy))

    def obstacle_loin(self):
        if not self.obstacle or math.hypot(self.obstacle[-1][1] - LOIN[0], self.obstacle[-1][2] - LOIN[1]) > 0.05:
            return self.poser_obstacle_monde(*LOIN)
        return None

    def armer_zone_libre(self, delai=5):
        """En tête d'essai : ARME et zone LIBRE. Un VERROU capteur_perdu trouvé ICI n'a été provoqué
        par aucune épreuve (celles qui en provoquent réarment ou relancent avant) : c'est le banc —
        un processus figé plus de 0,30 s par la charge du PC (la minuterie de rclpy passe avant le
        balayage en attente). Le nœud a fait son travail (zéro et verrou) ; on le compte, on le dit
        et on réarme. Au-delà de VERROUS_SPONTANES_MAX, la passe est rouge (banc trop chargé)."""
        e = self.etat()
        if (e.get("etat"), e.get("cause")) == ("VERROU", "capteur_perdu"):
            self.verrous_spontanes += 1
            journal(f"VERROU capteur_perdu SPONTANÉ n° {self.verrous_spontanes} (banc chargé) : réarmement")
            if self.verrous_spontanes > VERROUS_SPONTANES_MAX:
                raise Echec(f"plus de {VERROUS_SPONTANES_MAX} verrous capteur_perdu spontanés : banc trop chargé")
            self.dormir(1.2)              # capteur sain depuis 1 s, exigé par le réarmement
            self.rearmer()
        self.attendre(lambda: self.etat().get("etat") == "ARME" and self.etat().get("zone") == "LIBRE", delai,
                      "corps sûr ARME et zone LIBRE")

    def lancer(self, nom="cmd_vel_follow", v=0.3, hz=20.0):
        self.source(nom, v, 0.0, hz)
        self.attendre(lambda: self.cmd and abs(self.cmd[-1][1] - v) < 0.02, 3, f"Didier lancé ({nom} {v})")

    def rearmer(self):
        self.rearmer_pub.publish(Empty())

    # --- nœud ---------------------------------------------------------------------------------
    def pids_noeud(self):
        r = subprocess.run(["pgrep", "-f", "lib/didier_corps_sur/corps_sur_node"], capture_output=True, text=True)
        return [int(p) for p in r.stdout.split()]

    def tuer_noeud(self, sig=signal.SIGTERM):
        for pid in self.pids_noeud():
            os.kill(pid, sig)
        fin = time.monotonic() + 10
        while time.monotonic() < fin:
            if self.noeud is not None:
                self.noeud.poll()       # ramasse le zombie de notre enfant
            if not self.pids_noeud():
                break
            rclpy.spin_once(self, timeout_sec=0.05)
        if self.pids_noeud():
            raise Echec("le nœud corps_sur ne meurt pas")
        self.noeud = None

    def lancer_noeud(self, config):
        env = dict(os.environ)
        if os.environ.get("CS_NOEUD_PYTHONPATH"):
            env["PYTHONPATH"] = os.environ["CS_NOEUD_PYTHONPATH"] + ":" + env.get("PYTHONPATH", "")
        n0 = len(self.etats)
        self.noeud = subprocess.Popen(
            [NOEUD_EXE, "--ros-args", "-r", f"__ns:={NS}", "-r", "__node:=corps_sur",
             "-p", "use_sim_time:=true", "-p", f"config:={config}"],
            stdout=open(JOURNAL_NOEUD, "a"), stderr=subprocess.STDOUT, env=env, start_new_session=True)
        self.attendre(lambda: len(self.etats) > n0, 20, f"premier état du nœud relancé ({config})")
        return self.etats[n0][0]

    def relancer(self, config):
        self.tuer_noeud()
        return self.lancer_noeud(config)

    def remettre_sim(self):
        """Configuration de la SIM remise et vérifiée (spec §8.5)."""
        if self.etat().get("terrain") != "sim" or not self.pids_noeud():
            self.relancer(CONF_SIM)
        self.attendre(lambda: self.etat().get("etat") == "ARME" and self.etat().get("terrain") == "sim", 8,
                      "configuration de la sim remise (ARME, terrain sim)")

    def signaler(self, motif, sig):
        r = subprocess.run(["pgrep", "-f", motif], capture_output=True, text=True)
        pids = [int(p) for p in r.stdout.split()]
        if not pids:
            raise Echec(f"processus « {motif} » introuvable")
        for pid in pids:
            os.kill(pid, sig)
        return self.t()

    # --- mesures -------------------------------------------------------------------------------
    def premier_zero(self, apres, serie=None):
        return next((t for t, v, w in (self.cmd if serie is None else serie)
                     if t > apres and abs(v) < ZERO and abs(w) < ZERO), None)

    def premier_non_nul(self, apres, serie=None):
        return next((t for t, v, w in (self.cmd if serie is None else serie)
                     if t > apres and (abs(v) > ZERO or abs(w) > ZERO)), None)

    def distances_vraies(self, de, a, serie, rayon):
        """[(t, distance VRAIE surface-caisse)] entre de et a (poses horodatées sim)."""
        res = []
        for t, x, y, lacet in self.odom:
            if de <= t <= a:
                o = pres(serie, t)
                if o is not None and abs(o[0] - t) < 0.05:
                    cx, cy = vers_robot((x, y, lacet), o[1], o[2])
                    res.append((t, distance_caisse(CAISSE, cx, cy) - rayon))
        return res

    def dmin_vraie(self, de, a, serie, rayon):
        return min((d for _, d in self.distances_vraies(de, a, serie, rayon)), default=math.inf)

    def deplacement(self, t0, a):
        p0 = pres(self.odom, t0)
        return max((math.hypot(x - p0[1], y - p0[2]) for t, x, y, _ in self.odom if t0 <= t <= a), default=0.0)


def essai_obstacle(n, nom_source, hz, cx, cy, v=0.3, rejeux=2):
    """Didier en marche (v), obstacle posé en (cx, cy) → latence du zéro, déplacement, d_min.

    PRÉCONDITION « en marche à T0 » non tenue (le pilote, à court de CPU, a pris du retard sur ses
    réceptions : ses horodatages et la pose qui place l'obstacle sont alors périmés — vécu le 20/11,
    CS4a, d_min 0,40 m pour 0,5 visé) : l'essai est REJOUÉ, deux fois au plus, et dit au journal.
    Seule cette précondition du banc se rejoue ; latence, déplacement et d_min jamais."""
    for essai in range(rejeux + 1):
        r = _essai_obstacle(n, nom_source, hz, cx, cy, v)
        if r["marche"] or essai == rejeux:
            return r
        print(f"#  {nom_source} : pas en marche à T0 vu du pilote (banc en retard), essai rejoué", flush=True)
    return r


def _essai_obstacle(n, nom_source, hz, cx, cy, v):
    n.obstacle_loin()
    n.placer_didier()
    n.armer_zone_libre()
    n.lancer(nom_source, v, hz)
    n.dormir(0.5)
    t0 = n.poser_obstacle(cx, cy)
    marche = any(abs(c[1]) > 0.05 for c in n.cmd if t0 - 0.3 <= c[0] <= t0)
    n.dormir(1.2)
    n.silence()
    zero = n.premier_zero(t0)
    return {"latence": (zero - t0) if zero is not None else math.inf, "deplacement": n.deplacement(t0, t0 + 1.2),
            "dmin": n.dmin_vraie(t0, t0 + 1.2, n.obstacle, R_OBSTACLE), "t0": t0, "marche": marche}


def faire(nom):
    return not SEULEMENT or nom in SEULEMENT


rclpy.init()
n = Pilote()
rng = random.Random(GRAINE)
try:
    try:
        n.attendre(lambda: n.odom and n.obstacle and n.scans and n.etats, 30, "odom, obstacle, scan et état reçus")
    except Echec as e:
        raise Echec(f"{e} (reçus : odom {len(n.odom)}, obstacle {len(n.obstacle)}, scan {len(n.scans)}, "
                    f"état {len(n.etats)})") from None
    n.obstacle_loin()
    n.poser("passant", LOIN_PASSANT[0], LOIN_PASSANT[1], 0.85)

    # ================================================================ CS1 démarrage
    if faire("CS1"):
        print(f"--- CS1 démarrage {time.strftime('%T')}", flush=True)
        n.dormir(5.0)
        fen = [s for s in n.scans if s[0] >= n.t() - 5.0]
        freq = (len(fen) - 1) / (fen[-1][0] - fen[0][0]) if len(fen) > 1 and fen[-1][0] > fen[0][0] else 0.0
        rayons = sorted({s[2] for s in fen})
        verdict(9.0 <= freq <= 11.0 and rayons == [500],
                f"CS1a scan {freq:.2f} Hz en temps simulé (10 ± 10 %), rayons {rayons} (500 attendus)")
        t_premier = n.relancer(CONF_SIM)
        try:
            t_arme = n.attendre(lambda: n.etat().get("etat") == "ARME", 5, "ARME")
        except Echec:
            t_arme = math.inf
        verdict(t_arme - t_premier < 5.0,
                f"CS1b nœud relancé : ARME {t_arme - t_premier:.2f} s après son premier état (< 5 s)")
        e = n.etat()
        verdict(e.get("vue") == {"avant": True, "arriere": False, "flanc_g": False, "flanc_d": False}
                and e.get("terrain") == "sim",
                f"CS1c vue publiée {e.get('vue')} (pose A : avant seul), terrain {e.get('terrain')}")
    n.remettre_sim()

    # ================================================================ CS2 porte de l'étude
    if faire("CS2"):
        print(f"--- CS2 porte de l'étude {time.strftime('%T')}", flush=True)
        tirages = [rng.uniform(-1.0, 1.0) for _ in range(20)]
        resultats = {}
        for hz in (20.0, 5.0):
            res = []
            for k, s in enumerate(tirages):
                cx, cy = centre_a(0.5, s)
                r = essai_obstacle(n, "cmd_vel_follow", hz, cx, cy)   # rejoué si pas en marche à T0
                res.append(r)
                journal(f"{hz:g} Hz essai {k + 1:2d} centre ({cx:.3f} ; {cy:+.3f}) relèvement "
                        f"{math.degrees(math.atan2(cy, cx - X_LIDAR)):+.1f}° : zéro {ms(r['latence'])}, "
                        f"{r['deplacement']:.3f} m après T0, d_min vraie {r['dmin']:.3f} m, en marche {r['marche']}")
            resultats[hz] = res
            lats = [r["latence"] for r in res]
            journal(f"{hz:g} Hz : latence max {ms(max(lats))}, médiane {ms(statistics.median(lats))}")
        r20, r5 = resultats[20.0], resultats[5.0]
        bons20 = sum(r["marche"] and r["latence"] < 0.200 for r in r20)
        bons5 = sum(r["marche"] and r["latence"] < 0.200 for r in r5)
        tous = r20 + r5
        verdict(bons20 == 20, f"CS2a 20 Hz : {bons20}/20 zéros sur cmd_vel < 200 ms après T0 "
                              f"(max {ms(max(r['latence'] for r in r20))}, médiane "
                              f"{ms(statistics.median(r['latence'] for r in r20))})")
        verdict(all(r["deplacement"] <= 0.15 for r in tous),
                f"CS2b distance parcourue après T0 ≤ 0,15 m : max {max(r['deplacement'] for r in tous):.3f} m (40 essais)")
        verdict(all(r["dmin"] >= 0.30 for r in tous),
                f"CS2c distance vraie caisse-obstacle ≥ 0,30 m : min {min(r['dmin'] for r in tous):.3f} m (40 essais)")
        verdict(bons5 == 20, f"CS2d 5 Hz : {bons5}/20 zéros < 200 ms (max {ms(max(r['latence'] for r in r5))}, "
                             f"médiane {ms(statistics.median(r['latence'] for r in r5))})")

    # ================================================================ CS3 reprise
    if faire("CS3"):
        print(f"--- CS3 reprise {time.strftime('%T')}", flush=True)
        n.obstacle_loin()
        n.placer_didier()
        n.armer_zone_libre()
        n.lancer()
        n.poser_obstacle(*centre_a(0.5, 0.0))
        n.dormir(1.0)
        arrete = n.etat().get("zone") == "ARRET"
        t_retrait = n.poser_obstacle_monde(*LOIN)
        n.dormir(1.5)
        n.silence()
        repart = n.premier_non_nul(t_retrait)
        d = (repart - t_retrait) if repart is not None else math.inf
        verdict(arrete and 0.2 <= d <= 1.0, f"CS3 obstacle retiré : cmd_vel non nul {d:.3f} s après (0,2 à 1,0 s), "
                                           f"arrêt avant le retrait : {arrete}")

    # ================================================================ CS4 les trois canaux
    if faire("CS4"):
        print(f"--- CS4 trois canaux {time.strftime('%T')}", flush=True)
        r = essai_obstacle(n, "cmd_vel_web", 20.0, *centre_a(0.5, 0.0))
        verdict(r["marche"] and r["latence"] < 0.200 and r["dmin"] >= 0.30,
                f"CS4a cmd_vel_web : zéro {ms(r['latence'])} après T0, d_min vraie {r['dmin']:.3f} m")
        n.obstacle_loin()
        n.placer_didier()
        n.armer_zone_libre()
        n0, s0 = len(n.anim_brut), len(n.sur["anim"])
        n.animation_pub.publish(StringTime(msg=json.dumps("little-move3"), time=0, anim=False))
        n.attendre(lambda: any(v > 0.05 for _, v, _ in n.anim_brut[n0:]), 10,
                   "phase avant de little-move3 sur cmd_vel_anim")
        # t_avant = horodatage de RÉCEPTION de la demande, pas l'heure du sondage : wheels_bridge
        # ne publie qu'UNE fois par clé roues, et le cmd_vel qui la suit arrive dans la même
        # milliseconde — le sondage (10 ms) le laissait avant t_avant (CS4b rouge du 20/11 matin).
        t_avant = next(t for t, v, _ in n.anim_brut[n0:] if v > 0.05)
        n.attendre(lambda: any(v > 0.05 for t, v, _ in n.cmd if t >= t_avant), 1, "phase avant sur cmd_vel")
        # 0,1 s de marche avant l'obstacle : posé dans la même milliseconde que l'unique consigne, il
        # la précédait parfois à la vérité terrain (« en marche à T0 » faux). La consigne tient
        # 0,4 s (deadman) : T0 ≈ +0,1 s, un zéro venu du deadman et non du corps sûr tomberait à
        # ≈ 0,3 s de T0, au-delà des 200 ms, donc l'épreuve le distingue toujours.
        n.dormir(0.1)
        t0 = n.poser_obstacle(*centre_a(0.5, 0.0))
        n.dormir(1.0)
        # En marche À T0 : le DERNIER cmd_vel avant T0 porte la phase avant (pas seulement « un
        # cmd_vel non nul quelque part avant ») — sinon le zéro du deadman (400 ms après l'unique
        # message de la clé) passerait pour celui du corps sûr.
        avant_t0 = [v for t, v, _ in n.cmd if t_avant <= t <= t0]
        marche = bool(avant_t0) and avant_t0[-1] > 0.05
        zero = n.premier_zero(t0)
        zero_sur = n.premier_zero(t0, serie=n.sur["anim"][s0:])
        lat = (zero - t0) if zero is not None else math.inf
        lat_sur = (zero_sur - t0) if zero_sur is not None else math.inf
        verdict(marche and lat < 0.200 and lat_sur < 0.200,
                f"CS4b cmd_vel_anim (little-move3 par animations_node) : en marche à T0 {marche}, zéro sur cmd_vel "
                f"{ms(lat)} après T0, zéro du corps sûr sur cmd_vel_anim_sur {ms(lat_sur)}")
        n.dormir(4.0)                    # fin de la séquence (5 s)
        n.obstacle_loin()

    # ================================================================ CS5 moon-walk
    if faire("CS5"):
        print(f"--- CS5 moon-walk {time.strftime('%T')}", flush=True)
        n.placer_didier()
        n.armer_zone_libre()
        n0, c0 = len(n.anim_brut), len(n.cmd)
        debut = n.t()
        n.animation_pub.publish(StringTime(msg=json.dumps("moon-walk"), time=0, anim=False))
        t_recul = n.attendre(lambda: any(v < -0.05 for _, v, _ in n.anim_brut[n0:]), 25,
                             "recul de moon-walk sur cmd_vel_anim")
        n.dormir(2.5)                    # les diagnostics (1 Hz) portent le dernier refus
        motif = n.diag.get("refus_anim")
        n.attendre(lambda: n.t() > debut + 31.5, 20, "fin de moon-walk")
        recul_vu = [v for t, v, _ in n.cmd[c0:] if v < -ZERO]
        verdict(not recul_vu and motif == "recul_aveugle",
                f"CS5 moon-walk, arrière non vu : recul demandé à +{t_recul - debut:.1f} s, "
                f"{len(recul_vu)} linear.x < 0 sur cmd_vel, motif publié « {motif} »")

    # ================================================================ CS6 ralenti
    if faire("CS6"):
        print(f"--- CS6 ralenti {time.strftime('%T')}", flush=True)
        mesures = {}
        for d_surface, de, a in ((0.9, 0.4, 0.8), (1.5, 0.2, 0.6)):
            n.obstacle_loin()
            n.placer_didier()
            n.armer_zone_libre()
            n.lancer()
            n.dormir(0.3)
            t0 = n.poser_obstacle(*centre_a(d_surface, 0.0))
            n.dormir(a + 0.1)
            n.silence()
            vals = [v for t, v, _ in n.cmd if t0 + de <= t <= t0 + a]
            mesures[d_surface] = statistics.median(vals) if vals else math.nan
            journal(f"obstacle à {d_surface} m : cmd_vel {valeurs(vals)}")
        verdict(abs(mesures[0.9] - 0.15) <= 0.01 and abs(mesures[1.5] - 0.30) <= 0.01,
                f"CS6 ralenti : à 0,9 m cmd_vel {mesures[0.9]:.3f} (0,15 ± 0,01), à 1,5 m {mesures[1.5]:.3f} (0,30)")
        n.obstacle_loin()

    # ================================================================ CS7 télécommande non filtrée
    if faire("CS7"):
        print(f"--- CS7 télécommande {time.strftime('%T')}", flush=True)
        n.obstacle_loin()
        n.placer_didier()
        n.poser_obstacle(*centre_a(0.3, 0.0))
        n.attendre(lambda: n.etat().get("zone") == "ARRET", 2, "zone ARRET")
        s0 = len(n.sur["follow"])
        n.source("cmd_vel_follow", 0.3, 0.0, 20.0)
        n.dormir(0.5)
        t_r = n.t()
        n.source("cmd_vel_remote", 0.2, 0.0, 20.0)
        n.dormir(1.0)
        n.source("cmd_vel_remote", None)
        t_fin = n.t()
        n.dormir(1.0)
        n.silence()
        pendant = [v for t, v, _ in n.cmd if t_r + 0.3 <= t <= t_fin]
        apres = [v for t, v, _ in n.cmd if t_fin + 0.7 <= t <= t_fin + 1.0]
        follow_sur = [v for _, v, _ in n.sur["follow"][s0:]]
        bon = (pendant and all(abs(v - 0.2) < 0.005 for v in pendant) and apres and all(abs(v) < ZERO for v in apres)
               and follow_sur and all(abs(v) < ZERO for v in follow_sur))
        verdict(bon, f"CS7 obstacle à 0,3 m : télécommande → cmd_vel {valeurs(pendant)} ; après elle "
                     f"{valeurs(apres)} ; cmd_vel_follow_sur {valeurs(follow_sur)} ({len(follow_sur)} msgs)")
        n.obstacle_loin()

    # ================================================================ CS8 capteur perdu en marche
    if faire("CS8"):
        print(f"--- CS8 capteur perdu {time.strftime('%T')}", flush=True)
        n.placer_didier()
        n.armer_zone_libre()
        n.lancer()
        n.dormir(0.5)
        t_stop = n.signaler("__node:=pont_lidar", signal.SIGSTOP)
        try:
            n.dormir(1.0)
            dernier = max(s[0] for s in n.scans if s[0] <= t_stop + 0.2)
            zero = n.premier_zero(dernier)
            e = n.etat()
            d = (zero - dernier) if zero is not None else math.inf
            verdict(d < 0.45 and (e.get("etat"), e.get("cause")) == ("VERROU", "capteur_perdu"),
                    f"CS8a pont_lidar figé : zéro {d:.3f} s après le dernier balayage (< 0,45), état "
                    f"{e.get('etat')} {e.get('cause')}")
        finally:
            t_cont = n.signaler("__node:=pont_lidar", signal.SIGCONT)
        n.dormir(3.0)
        non_nuls = [v for t, v, _ in n.cmd if t_cont < t <= t_cont + 3.0 and abs(v) > ZERO]
        verdict(not non_nuls and n.etat().get("etat") == "VERROU",
                f"CS8b SIGCONT : {len(non_nuls)} consigne(s) non nulle(s) en 3 s, état {n.etat().get('etat')}")
        t_re = n.t()
        n.rearmer()
        try:
            t_repart = n.attendre(lambda: n.premier_non_nul(t_re) is not None, 2.0, "reprise")
        except Echec:
            t_repart = math.inf
        verdict(t_repart - t_re < 2.0, f"CS8c rearmer : repart {t_repart - t_re:.2f} s après (< 2 s)")
        n.silence()

    # ================================================================ CS9 capteur absent au démarrage
    if faire("CS9"):
        print(f"--- CS9 capteur absent au démarrage {time.strftime('%T')}", flush=True)
        n.placer_didier()
        n.tuer_noeud()
        n.signaler("__node:=pont_lidar", signal.SIGSTOP)
        try:
            n.lancer_noeud(CONF_SIM)
            s0 = len(n.sur["follow"])
            t_d = n.t()
            n.source("cmd_vel_follow", 0.3, 0.0, 20.0)
            n.dormir(5.0)
            n.silence()
            sorties = [v for _, v, _ in n.sur["follow"][s0:]]
            non_nuls = [v for t, v, _ in n.cmd if t > t_d and abs(v) > ZERO]
            e = n.etat()
            verdict(sorties and all(abs(v) < ZERO for v in sorties) and not non_nuls
                    and (e.get("etat"), e.get("cause")) == ("DEMARRAGE", "capteur_absent"),
                    f"CS9a lidar figé au lancement : {len(sorties)} sorties toutes nulles, {len(non_nuls)} non nulle(s) "
                    f"sur cmd_vel, état {e.get('etat')} {e.get('cause')}")
        finally:
            t_cont = n.signaler("__node:=pont_lidar", signal.SIGCONT)
        try:
            t_arme = n.attendre(lambda: n.etat().get("etat") == "ARME", 3.0, "ARME")
        except Echec:
            t_arme = math.inf
        verdict(t_arme - t_cont < 3.0, f"CS9b SIGCONT : ARME {t_arme - t_cont:.2f} s après, sans réarmement (< 3 s)")

    # ================================================================ CS10 mort du filtre
    if faire("CS10"):
        print(f"--- CS10 mort du filtre {time.strftime('%T')}", flush=True)
        n.remettre_sim()
        n.placer_didier()
        n.armer_zone_libre()
        n.lancer()
        n.dormir(0.5)
        t_k = n.t()
        n.tuer_noeud(signal.SIGKILL)
        n.dormir(1.0)
        zero = n.premier_zero(t_k)
        d = (zero - t_k) if zero is not None else math.inf
        t_r = n.t()
        n.source("cmd_vel_remote", 0.2, 0.0, 20.0)
        n.dormir(1.0)
        n.silence()
        conduit = [v for t, v, _ in n.cmd if t_r + 0.3 <= t <= t_r + 1.0]
        verdict(d < 0.5 and conduit and all(abs(v - 0.2) < 0.005 for v in conduit),
                f"CS10a kill -9 en marche : zéro {d:.3f} s après (< 0,5) ; télécommande → cmd_vel {valeurs(conduit)}")
        n.lancer_noeud(CONF_SIM)
        n.placer_didier()
        n.armer_zone_libre()
        n.lancer()
        n.dormir(0.5)
        t_s = n.signaler("lib/didier_corps_sur/corps_sur_node", signal.SIGSTOP)
        try:
            n.dormir(1.0)
            zero = n.premier_zero(t_s)
            d = (zero - t_s) if zero is not None else math.inf
            verdict(d < 0.5, f"CS10b SIGSTOP du nœud en marche : zéro {d:.3f} s après (< 0,5)")
        finally:
            n.silence()
            n.signaler("lib/didier_corps_sur/corps_sur_node", signal.SIGCONT)
        n.relancer(CONF_SIM)
        n.remettre_sim()

    # ================================================================ CS11 arrêt d'urgence
    if faire("CS11"):
        print(f"--- CS11 arrêt d'urgence {time.strftime('%T')}", flush=True)
        n.placer_didier()
        n.armer_zone_libre()
        n.lancer()
        n.dormir(0.5)
        t_e = n.t()
        for _ in range(3):
            n.e_stop_pub.publish(Bool(data=True))
            n.dormir(0.1)
        n.dormir(0.7)
        zero = n.premier_zero(t_e)
        e = n.etat()
        # Le verrou du mux bloque aussi la sortie du corps sûr : le zéro vient du mux ou, au pire,
        # du deadman (400 ms + un tic) — d'où 0,5 s.
        coupe = zero is not None and zero - t_e < 0.5 and (e.get("etat"), e.get("cause")) == ("VERROU", "e_stop")
        for _ in range(3):
            n.e_stop_pub.publish(Bool(data=False))
            n.dormir(0.1)
        n.dormir(0.5)
        t_r = n.t()
        n.source("cmd_vel_remote", 0.2, 0.0, 20.0)
        n.dormir(1.0)
        n.source("cmd_vel_remote", None)
        t_f = n.t()
        n.dormir(1.0)
        conduit = [v for t, v, _ in n.cmd if t_r + 0.3 <= t <= t_f]
        autonome = [v for t, v, _ in n.cmd if t_f + 0.7 <= t <= t_f + 1.0]
        t_re = n.t()
        n.rearmer()
        try:
            t_rep = n.attendre(lambda: n.premier_non_nul(t_re) is not None, 2.0, "reprise")
        except Echec:
            t_rep = math.inf
        n.silence()
        verdict(coupe and conduit and all(abs(v - 0.2) < 0.005 for v in conduit)
                and autonome and all(abs(v) < ZERO for v in autonome) and t_rep - t_re < 2.0,
                f"CS11 e_stop : zéro {ms(None if zero is None else zero - t_e)}, état {e.get('etat')} {e.get('cause')} ; "
                f"relâché : télécommande {valeurs(conduit)}, autonome {valeurs(autonome)} ; rearmer : repart "
                f"{t_rep - t_re:.2f} s après")

    # ================================================================ CS12 configuration du robot en sim
    if faire("CS12"):
        print(f"--- CS12 configuration du robot en sim {time.strftime('%T')}", flush=True)
        with open(CONF_SIM, encoding="utf-8") as f:
            sim = yaml.safe_load(f)
        with open(CONF_ROBOT, encoding="utf-8") as f:
            robot = yaml.safe_load(f)
        for cle in ("x", "y", "lacet_rad", "masques_deg"):
            robot["lidar"][cle] = sim["lidar"][cle]
        tel_quel, exige = "/tmp/cs12-robot.yaml", "/tmp/cs12-robot-superviseur-exige.yaml"
        with open(tel_quel, "w", encoding="utf-8") as f:
            yaml.safe_dump(robot, f)
        robot_exige = json.loads(json.dumps(robot))
        robot_exige["superviseur"]["exige"] = True
        with open(exige, "w", encoding="utf-8") as f:
            yaml.safe_dump(robot_exige, f)
        journal(f"fichier du robot : superviseur exigé {robot['superviseur']['exige']}, durée "
                f"{robot['duree']['duree_max_mouvement_s']} s, follow v_max {robot['canaux']['follow']['v_max']}")
        n.placer_didier()
        # a. superviseur
        n.relancer(tel_quel)
        try:
            n.attendre(lambda: n.etat().get("etat") == "ARME", 4, "ARME (robot, superviseur tel que le fichier)")
            sans = n.etat().get("superviseur") == "non_exige" and not robot["superviseur"]["exige"]
        except Echec:
            sans = False
        n.relancer(exige)
        n.dormir(2.0)
        e_abs = n.etat()
        absent = (e_abs.get("etat"), e_abs.get("cause")) == ("DEMARRAGE", "superviseur_absent")
        d, coupe, e = math.inf, False, {}
        try:
            n.battement_periode = 0.2
            n.attendre(lambda: n.etat().get("etat") == "ARME", 3, "ARME avec battement")
            n.lancer("cmd_vel_follow", 0.2)
            n.dormir(0.5)
            n.battement_periode = None
            dernier_b = n.battement_dernier
            n.dormir(1.6)
            zero = n.premier_zero(dernier_b)
            d = (zero - dernier_b) if zero is not None else math.inf
            e = n.etat()
            coupe = d < 1.1 and (e.get("etat"), e.get("cause")) == ("VERROU", "superviseur_perdu")
        except Echec as ex:
            journal(f"CS12a : {ex}")
        n.battement_periode = None
        n.silence()
        verdict(sans and absent and coupe,
                f"CS12a superviseur : fichier tel quel → ARME sans battement ({sans}) ; exigé → {e_abs.get('etat')} "
                f"{e_abs.get('cause')}, battement 5 Hz coupé → zéro {d:.2f} s après (< 1,1), "
                f"{e.get('etat')} {e.get('cause')}")
        # c. plafond, puis b. durée bornée (fichier tel quel)
        n.relancer(tel_quel)
        n.placer_didier(-3.0, 0.0, 0.0)
        n.attendre(lambda: n.etat().get("etat") == "ARME", 4, "ARME (robot)")
        t_p = n.t()
        n.source("cmd_vel_follow", 0.4, 0.0, 20.0)
        n.dormir(1.0)
        n.source("cmd_vel_follow", 0.0, 0.0, 20.0)
        n.dormir(1.5)
        plafond = [v for t, v, _ in n.cmd if t_p + 0.3 <= t <= t_p + 1.0]
        c0 = len(n.cmd)
        n.source("cmd_vel_follow", 0.2, 0.0, 20.0)
        n.dormir(5.0)
        t1 = next((t for t, v, _ in n.cmd[c0:] if abs(v) > ZERO), None)
        t2 = n.premier_zero(t1) if t1 is not None else None
        duree = (t2 - t1) if t2 is not None else math.inf
        n.source("cmd_vel_follow", 0.0, 0.0, 20.0)
        n.dormir(1.1)
        t_z = n.t()
        n.source("cmd_vel_follow", 0.2, 0.0, 20.0)
        n.dormir(0.6)
        n.silence()
        reprise = n.premier_non_nul(t_z)
        verdict(abs(duree - 4.0) <= 0.1 and reprise is not None and reprise - t_z < 0.5,
                f"CS12b mouvement continu coupé après {duree:.2f} s (4,0 ± 0,1), repris "
                f"{ms(None if reprise is None else reprise - t_z)} après 1,1 s d'entrées nulles")
        verdict(plafond and all(abs(v - 0.25) < 0.005 for v in plafond),
                f"CS12c follow 0,4 demandé → cmd_vel {valeurs(plafond)} (plafond du fichier : 0,25)")
        n.relancer(CONF_SIM)
        n.remettre_sim()

    # ================================================================ CS13 passant
    if faire("CS13"):
        print(f"--- CS13 passant {time.strftime('%T')}", flush=True)
        n.remettre_sim()
        bons, details = 0, []
        Y0 = 2.5
        for vitesse in (0.5, 1.0, 1.5):
            for sens in (1, -1):
                ligne = 0.5 + 0.3 * (Y0 - 1.2) / vitesse     # avance estimée de Didier, recalée ensuite
                for essai in range(4):
                    n.obstacle_loin()
                    n.poser("passant", LOIN_PASSANT[0], LOIN_PASSANT[1], 0.85)
                    n.placer_didier(-2.0, 0.0, 0.0)   # du recul : le plateau finit à x = 5
                    n.armer_zone_libre()
                    n.lancer()
                    xc = CAISSE.x_avant + R_PASSANT + ligne
                    p0 = len(n.passant)
                    t_dep = n.t()
                    n.passant_pub.publish(StringTime(msg=json.dumps({"de": [xc, -sens * Y0], "a": [xc, sens * Y0],
                                                                     "vitesse": vitesse, "repere": "didier"}),
                                                     time=0, anim=False))
                    n.dormir(2 * Y0 / vitesse + 1.5)
                    n.silence()
                    serie = n.passant[p0:]
                    dist = n.distances_vraies(t_dep, n.t(), serie, R_PASSANT)
                    dmin = min((d for _, d in dist), default=math.inf)
                    dans = [t for t, d in dist if d < 0.6]
                    t_sortie = max(dans) if dans else None
                    repart = n.premier_non_nul(t_sortie) if t_sortie is not None else None
                    reprise = (repart - t_sortie) if repart is not None else math.inf
                    if abs(dmin - 0.5) <= 0.05 or essai == 3:
                        break
                    journal(f"passant {vitesse} m/s sens {sens:+d} : d_min {dmin:.3f} hors 0,5 ± 0,05, ligne recalée")
                    ligne += 0.5 - (dmin if math.isfinite(dmin) else 1.0)
                bon = dmin >= 0.30 and t_sortie is not None and reprise < 1.0
                bons += bon
                details.append(f"{vitesse} m/s {'→' if sens > 0 else '←'} d_min {dmin:.3f}, reprise {reprise:.2f} s")
                journal(f"passant {vitesse} m/s sens {sens:+d} (essai {essai + 1}) : d_min vraie {dmin:.3f} m, "
                        f"reprise {reprise:.2f} s après la sortie de zone — {'bon' if bon else 'MAUVAIS'}")
        n.poser("passant", LOIN_PASSANT[0], LOIN_PASSANT[1], 0.85)
        verdict(bons == 6, f"CS13 passant : {bons}/6 (distance vraie ≥ 0,30 m, reprise < 1 s) — " + " ; ".join(details))

    n.remettre_sim()
    journal(f"fin : état {n.etat()}")
except Echec as e:
    print(f"  ❌ ÉCHEC du déroulé : {e}", flush=True)
    ko += 1
    # De quoi juger sans rejouer : dernier état, santé du capteur vue par le nœud, retard du pilote.
    journal(f"état au moment de l'échec : {n.etat()}")
    journal("diagnostics : " + ", ".join(f"{k}={n.diag.get(k)}" for k in
                                          ("age_dernier_balayage_s", "points_valides", "motifs_balayage",
                                           "duree_rappel_scan_max_ms")))
    if n.odom:
        journal(f"retard du pilote sur la vérité terrain : {n.t() - n.odom[-1][0]:.3f} s")
finally:
    n.silence()
    for _ in range(5):
        rclpy.spin_once(n, timeout_sec=0.05)
    if n.noeud is not None:
        # Le nœud relancé ici reste en marche, détaché (configuration de la sim remise).
        journal(f"nœud corps_sur relancé par l'épreuve laissé en marche (pid {n.noeud.pid})")

print(f"#  verrous capteur_perdu spontanés (banc chargé, réarmés) : {n.verrous_spontanes}", flush=True)
print(f"=== CS corps sûr : {ok} OK, {ko} KO ===", flush=True)
os._exit(0 if ko == 0 else 1)
EOF
rc=$?
capture_arreter || echo "  ⚠️ enregistreur de secours mort : les verdicts ci-dessus restent ceux du pilote"
exit $rc
