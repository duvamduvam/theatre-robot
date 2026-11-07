#!/usr/bin/env python3
"""Node `gaze_follower` : le robot suit une personne DU REGARD (cou seulement).

SÉCURITÉ (cf. CLAUDE.md) :
 - Ce node ne publie QUE sur le cou (`neck` en mode robot, `neck/position` en
   mode sim). Il ne touche JAMAIS wheels/cmd_vel*/e_stop — aucun de ces topics
   n'apparaît ici. Le regard ne déplace pas les 50 kg du robot.
 - Il démarre DÉSACTIVÉ (enabled=False) : télécommande > autonome, toujours.
   Activation en direct via le topic `gaze` ("on"/"off") — un bouton télécommande
   pourra s'y brancher plus tard.

NON AJOUTÉ au launch de prod (didier_bringup) POUR L'INSTANT : tant que le sens du
cou (direction_sign) n'a pas été validé au protocole caméra, ce node se lance À LA
MAIN. Voir le rapport de validation sim et « reste à valider sur le vrai robot ».

Node volontairement FIN (I/O seulement) : toute la logique est dans la classe pure
robot.move.gaze_control.GazeControl (testée hors ROS). On n'importe PAS robot_config
ni robot.actions.* : le node reste autonome et tourne tel quel dans le conteneur de
simulation (qui n'embarque pas les dépendances matérielles du Pi).

ARBITRAGE (2026-07-12, lot B de docs/etude-arbitrage-actionneurs.md) : le regard
autonome n'a pas la même légitimité qu'une séquence de spectacle scriptée. Le node
s'abonne donc à `animation_state` (topic latché publié par animations_node) et se
TAIT (les deux GazeControl passent en enabled=False) tant qu'une animation a la
main sur le cou/les yeux. Deux drapeaux distincts pilotent l'état effectif :
`_user_enabled` (toggle topic `gaze` on/off) et `_animation_active` (une séquence
joue) ; l'activation réelle est leur ET logique (cf. _apply_enabled).

« REGARDER » (lot M2, docs/spec-aller-voir.md §7.1) : topic `look`, StringTime
JSON {"angle_deg": 30, "hold_ms": 4000} (+ = gauche ; compat {"dir": "gauche"|
"droite"|"devant"}), publié par chat_node. Cou (et yeux en mode robot) à
l'angle — saturé à la course utile du cou, journalisé —, tenue hold_ms (bornée
1000-8000 ms dans gaze_control) en ignorant les personnes, puis
retour lent au centre — interrompu par la première détection si le suivi est ON
(reprise du suivi). Fonctionne suivi ON comme OFF : c'est un geste demandé, pas
du suivi. ARBITRAGE INCHANGÉ : ordre ignoré tant qu'une animation a la main, et
geste coupé net quand une séquence démarre. Aucun réglage d'amorti/gain touché :
même mapping, même slew que le suivi. Cou et yeux seulement — pas de roues.
Revue M2 : « gaze off » explicite coupe aussi le geste (télécommande > autonome) ;
au plus 3 réarmements de suite sans retour au suivi, au-delà tenue coupée et
`look` ignoré 4 s ; un payload hostile est refusé, jamais fatal ; gain <= 0
refusé au démarrage.
"""

import json
import time

import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy
from std_msgs.msg import Float64
from robot_interfaces.msg import StringTime
from theatre_contrats import stringtime, topics

from robot.move.gaze_control import GazeControl, LookGovernor, consigne_to_radians, look_course_deg, parse_look

# Contrats de topics (ne pas dévier — interfaces existantes).
# PointStamped : x=azimut, y=élévation, z=confiance. Nom RELATIF depuis le lot
# L1a (theatre_contrats.topics) : sans namespace il se résout en /vision/person.
VISION_TOPIC = topics.VISION_PERSON
GAZE_CMD_TOPIC = "gaze"             # StringTime "on"/"off" : activation en direct
# StringTime JSON {"angle_deg", "hold_ms"} : « regarder » (lot M2). Littéral gravé des
# deux côtés (LOOK_TOPIC de chat_node, dépôt vision).
LOOK_TOPIC = "look"
NECK_TOPIC_ROBOT = "neck"          # StringTime : consigne 0-99 (vrai robot)
# Float64 en radians (JointPositionController gz). RELATIF depuis le lot L1b :
# /<robot>/neck/position côté ROS, relayé vers le topic gz /neck/position par le bridge.
NECK_TOPIC_SIM = "neck/position"
LEFT_EYE_TOPIC = "left_eye"        # StringTime : consigne 0-99 (servo œil gauche)
RIGHT_EYE_TOPIC = "right_eye"      # StringTime : consigne 0-99 (servo œil droit)
# StringTime latché : json.dumps(nom séquence) ou "" (contrat animations_node,
# cf. docs/etude-arbitrage-actionneurs.md lot B). Constante LITTÉRALE (et non
# importée de dadou_utils_ros.utils_static.ANIMATION_STATE) : ce node reste
# VOLONTAIREMENT autonome (cf. docstring de module) pour tourner tel quel dans
# le conteneur de simulation, qui n'a pas la dépendance dadou_utils_ros.
ANIMATION_STATE_TOPIC = "animation_state"
# Marge (ms) ajoutée au temps restant annoncé (msg.time) pour armer la
# PÉREMPTION locale de l'état animation : la fin de séquence normale arrive
# par un "" sur animation_state, mais si animations_node meurt en pleine
# séquence ce "" ne vient jamais — sans péremption le gaze resterait muet
# pour toujours (panne silencieuse). Déclinaison du deadman maison (servos,
# roues). animations_node RE-publie l'état à chaque (re)démarrage de séquence
# (même nom compris) précisément pour que cette échéance soit réarmée.
STATE_EXPIRY_MARGIN_MS = 2000


def _now_ms():
    """Horloge MONOTONE en millisecondes. On n'utilise PAS le temps ROS/sim : le
    suivi du regard n'est pas lié au temps de simulation (contrairement au chemin
    roues), et une horloge monotone évite tout saut d'horloge sur les timeouts."""
    return int(time.monotonic() * 1000)


class GazeFollowerNode(Node):
    def __init__(self):
        super().__init__("gaze_follower")

        # --- Paramètres ROS déclarés (réglables au lancement) ---
        self.declare_parameter("enabled", False)          # DÉSACTIVÉ par défaut
        self.declare_parameter("output_mode", "robot")    # 'robot' | 'sim'
        self.declare_parameter("gain", 20.0)
        # direction_sign=+1 VALIDÉ au protocole caméra réel du 2026-07-12.
        # ⚠️ CORRECTION 2026-09-14 : la justification écrite ici était FAUSSE.
        # Elle invoquait une « boucle fermée auto-validante, la caméra est sur
        # la tête ». David a établi que la caméra est FIXE SUR LE BUSTE (support
        # devant la bouche) et ne tourne PAS avec le cou. Donc le gaze est en
        # BOUCLE OUVERTE : rien ne rattrape une erreur de signe ou de gain.
        # Le signe +1 reste bon — mais il est validé par ce que David a VU en
        # scène le 12/07, pas par une convergence. Ne pas le retoucher sans
        # repasser un protocole visuel. Voir aussi l'avertissement sur `gain`
        # dans robot/move/gaze_control.py : en boucle ouverte, le gain est un
        # ÉTALONNAGE, pas un réglage de confort.
        self.declare_parameter("direction_sign", 1)
        self.declare_parameter("center", 50)
        self.declare_parameter("confidence_min", 0.4)
        # ema_alpha=0.15 / slew_max=1.5 : amortissement VALIDÉ au protocole du
        # 2026-07-12 — avec les valeurs initiales (0.4 / 3.0) la boucle
        # oscillait (cou 53<->61 en va-et-vient : trop de retard de phase
        # cumulé EMA perception + EMA locale + slew + rampe physique du servo
        # pour ce gain). Suivi doux et stable avec ces valeurs.
        self.declare_parameter("ema_alpha", 0.15)
        self.declare_parameter("slew_max", 1.5)
        self.declare_parameter("slew_return", 1.0)
        self.declare_parameter("timeout_ms", 1500)
        self.declare_parameter("tick_hz", 10.0)
        # --- Yeux (2026-07-12) : les servos left_eye/right_eye suivent AUSSI
        # l'azimut. MÊME logique pure (deuxième instance de GazeControl) avec
        # leur propre réglage : gain plus fort et slew plus vif — les yeux
        # dardent, le cou suit, c'est le comportement naturel d'un regard.
        # Consigne IDENTIQUE aux deux yeux (les séquences artistiques leur
        # donnent la même plage 15-90 ; si le montage réel s'avère miroir,
        # ajouter un eye_right_sign — à trancher au protocole visuel).
        # eye_gain=49 (plein débattement 1-99, les séquences artistiques
        # utilisent déjà 0-99 : mécanique éprouvée) et eye_direction_sign=-1 :
        # VALIDÉS visuellement au protocole du 2026-07-12 (le montage des
        # yeux est bien MIROIR du cou — avec +1 le regard fuyait la personne,
        # amplitude jugée trop faible à gain 25 puis 35).
        self.declare_parameter("eyes_enabled", True)
        self.declare_parameter("eye_gain", 49.0)
        self.declare_parameter("eye_center", 50)
        self.declare_parameter("eye_direction_sign", -1)
        self.declare_parameter("eye_slew_max", 8.0)
        self.declare_parameter("eye_slew_return", 3.0)

        enabled = self.get_parameter("enabled").value
        self.output_mode = self.get_parameter("output_mode").value
        tick_hz = self.get_parameter("tick_hz").value

        # Deux drapeaux d'activation distincts (lot B arbitrage, cf. docstring
        # de module) : l'utilisateur (toggle topic `gaze`) et l'arbitrage
        # amont (une séquence a la main). L'état EFFECTIF des GazeControl est
        # leur ET logique, calculé uniquement par _apply_enabled() (source
        # unique de vérité — jamais de set_enabled direct ailleurs).
        self._user_enabled = bool(enabled)
        self._animation_active = False
        self._animation_expiry_ms = 0  # échéance de péremption (cf. STATE_EXPIRY_MARGIN_MS)

        # gain <= 0 : refus EXPLICITE au démarrage (revue M2) — c'est l'échelle
        # du `look` (division par la course du cou) et l'étalonnage du suivi.
        if not self.get_parameter("gain").value > 0:
            raise ValueError("gaze_follower : paramètre gain > 0 attendu, reçu {!r}".format(
                self.get_parameter("gain").value))
        # Limiteur des réarmements de `look`, commun cou + yeux (revue M2).
        self.look_governor = LookGovernor()

        # Logique pure : instanciée DÉSACTIVÉE, l'état effectif est posé juste
        # après par _apply_enabled() (évite de dupliquer le calcul ET ici).
        self.gaze = GazeControl(
            center=self.get_parameter("center").value,
            gain=self.get_parameter("gain").value,
            direction_sign=self.get_parameter("direction_sign").value,
            confidence_min=self.get_parameter("confidence_min").value,
            ema_alpha=self.get_parameter("ema_alpha").value,
            slew_max=self.get_parameter("slew_max").value,
            slew_return=self.get_parameter("slew_return").value,
            timeout_ms=self.get_parameter("timeout_ms").value,
            enabled=False,
        )

        # --- Yeux : deuxième GazeControl, mêmes filtres d'entrée (confiance,
        # timeout), réglages propres. ZÉRO logique nouvelle : la classe pure
        # déjà testée fait tout (EMA, slew, LOST->retour centre, anti-spam).
        self.eyes_enabled = bool(self.get_parameter("eyes_enabled").value)
        self.eyes = GazeControl(
            center=self.get_parameter("eye_center").value,
            gain=self.get_parameter("eye_gain").value,
            direction_sign=self.get_parameter("eye_direction_sign").value,
            confidence_min=self.get_parameter("confidence_min").value,
            ema_alpha=self.get_parameter("ema_alpha").value,
            slew_max=self.get_parameter("eye_slew_max").value,
            slew_return=self.get_parameter("eye_slew_return").value,
            timeout_ms=self.get_parameter("timeout_ms").value,
            enabled=False,
        )

        # --- Sortie : publishers selon le mode (pas de topic inutile) ---
        if self.output_mode == "sim":
            self.pub = self.create_publisher(Float64, NECK_TOPIC_SIM, 10)
            # Yeux non câblés en sim pour l'instant (pas de joint gz dédié
            # exposé) : le suivi des yeux est validé visuellement en réel.
            self.eye_pubs = []
        else:
            self.pub = self.create_publisher(StringTime, NECK_TOPIC_ROBOT, 10)
            self.eye_pubs = [
                self.create_publisher(StringTime, LEFT_EYE_TOPIC, 10),
                self.create_publisher(StringTime, RIGHT_EYE_TOPIC, 10),
            ] if self.eyes_enabled else []

        # --- Entrées ---
        self.create_subscription(PointStamped, VISION_TOPIC, self._on_person, 10)
        self.create_subscription(StringTime, GAZE_CMD_TOPIC, self._on_gaze_cmd, 10)
        # VOLATILE (défaut) : un « regarde à droite » ancien rejoué à la
        # connexion n'a plus de sens scénique.
        self.create_subscription(StringTime, LOOK_TOPIC, self._on_look, 10)
        # Arbitrage amont : abonnement latché. PIÈGE QoS : la durabilité doit
        # être TRANSIENT_LOCAL DES DEUX CÔTÉS — un abonné VOLATILE (défaut)
        # resterait compatible mais ne recevrait PAS le dernier état à la
        # connexion ; ce node, lancé À LA MAIN en cours de spectacle, raterait
        # justement l'information que le latch devait lui garantir.
        self.create_subscription(
            StringTime, ANIMATION_STATE_TOPIC, self._on_animation_state,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))

        # Timer de tick à cadence fixe.
        self.create_timer(1.0 / tick_hz, self._on_tick)

        # Source unique de vérité pour l'état effectif des deux GazeControl
        # (posés désactivés ci-dessus) : applique _user_enabled AND NOT
        # _animation_active dès le démarrage.
        self._apply_enabled()

        self.get_logger().info(
            "gaze_follower démarré : output_mode={} enabled={} (télécommande > autonome)".format(
                self.output_mode, bool(enabled)))

    def _apply_enabled(self):
        # Calcule l'activation EFFECTIVE = utilisateur ET PAS d'animation en
        # cours (yeux en plus soumis à eyes_enabled). PIÈGE : set_enabled(False)
        # fait un _reset() complet côté GazeControl (voulu -- à la reprise, le
        # gaze repart d'un état neutre et RÉ-ÉMET sa première consigne car
        # last_published redevient None ; sans ce reset, l'anti-spam croirait
        # la consigne déjà publiée alors que l'animation a bougé le cou
        # entre-temps).
        effective = self._user_enabled and not self._animation_active
        self.gaze.set_enabled(effective)
        self.eyes.set_enabled(effective and self.eyes_enabled)

    def _on_animation_state(self, ros_msg):
        # Payload = json.dumps(nom) ou json.dumps("") (contrat animations_node).
        # Tolérant comme _on_gaze_cmd : json ou brut, tout ce qui n'est pas une
        # chaîne devient "" (repos) par prudence (producteur qui divague).
        raw = ros_msg.msg
        value = stringtime.decode_or_raw(raw, ANIMATION_STATE_TOPIC)
        name = value if isinstance(value, str) else ""

        was_active = self._animation_active
        self._animation_active = bool(name)
        if self._animation_active:
            # La séquence a la main : un « regarder » en vol tombe (sinon il
            # irait au bout, set_enabled(False) le laissant finir exprès).
            self.gaze.cancel_look()
            self.eyes.cancel_look()
            # ros_msg.time = remaining_ms au (re)démarrage (contrat
            # animations_node). time <= 0 (producteur hors contrat) : seule la
            # marge protège — 2 s de pause au pire, jamais muet pour toujours.
            self._animation_expiry_ms = _now_ms() + max(int(ros_msg.time), 0) + STATE_EXPIRY_MARGIN_MS

        # Log UNIQUEMENT sur transition : ce topic peut recevoir un message à
        # chaque changement de séquence, pas la peine de logger si l'état ne
        # bouge pas (ex. re-publication du même repos).
        if self._animation_active and not was_active:
            self.get_logger().info("gaze en pause : séquence '{}' a la main".format(name))
        elif was_active and not self._animation_active:
            self.get_logger().info("gaze reprend : plus de séquence en cours")

        self._apply_enabled()

    def _on_person(self, msg):
        # x=azimut [-1..1], y=élévation [-1..1] (ignorée), z=confiance [0..1].
        now = _now_ms()
        self.gaze.update(msg.point.x, msg.point.y, msg.point.z, now)
        self.eyes.update(msg.point.x, msg.point.y, msg.point.z, now)

    def _on_gaze_cmd(self, ros_msg):
        # Le fil StringTime porte "on"/"off" (json ou brut, on tolère les deux).
        raw = ros_msg.msg
        value = stringtime.decode_or_raw(raw, GAZE_CMD_TOPIC)
        if value in ("on", True, 1, "1"):
            self._user_enabled = True
            self._apply_enabled()
            self.get_logger().info("gaze ON : suivi du regard activé (cou{}){}".format(
                " + yeux" if self.eyes_enabled else "",
                # L'utilisateur demande ON pendant qu'une séquence a la main :
                # l'intention est retenue, l'effet attendra la fin de séquence.
                " — en pause tant que la séquence en cours a la main" if self._animation_active else ""))
        elif value in ("off", False, 0, "0"):
            self._user_enabled = False
            # « gaze off » EXPLICITE : la télécommande prime, un « regarder » en
            # vol tombe aussi (revue M2). set_enabled, lui, le laisse finir —
            # exprès, pour les republications d'animation_state.
            self.gaze.cancel_look()
            self.eyes.cancel_look()
            self._apply_enabled()  # set_enabled(False) -> reset complet de l'état
            self.get_logger().info("gaze OFF : suivi désactivé, état réinitialisé")
        else:
            self.get_logger().warn("commande gaze inconnue : {!r}".format(raw))

    def _on_look(self, ros_msg):
        # Un callback qui lève tue le node de PROD (revue M2) : jamais ici.
        try:
            self._look(ros_msg)
        except Exception as e:
            self.get_logger().error("look {!r} : {!r}".format(ros_msg.msg, e))

    def _look(self, ros_msg):
        # Contrat : JSON {"angle_deg", "hold_ms"} (compat "dir") ; décodage
        # tolérant, angle saturé et tenue bornée dans parse_look (pur, testé).
        # Échelle = course du COU (cf. LOOK_DIR_AZIMUTH dans gaze_control).
        order = parse_look(ros_msg.msg, look_course_deg(self.gaze.gain))
        if order is None:
            self.get_logger().warn("look : ordre illisible, ignoré : {!r}".format(ros_msg.msg))
            return
        if self._animation_active:
            # Arbitrage : une séquence scriptée a la main sur cou/yeux.
            self.get_logger().info("look ignoré : une séquence a la main")
            return
        now = _now_ms()
        verdict = self.look_governor.decide(self.gaze.looking, now)
        if verdict == "limit":
            # Flux de look : la tenue en cours est coupée, le suivi reprend.
            self.gaze.end_hold()
            self.eyes.end_hold()
            self.get_logger().warn("look ignoré : trop de réarmements de suite, retour au suivi")
            return
        if verdict == "locked":
            self.get_logger().info("look ignoré : verrou anti-flux en cours")
            return
        if order.saturated:
            self.get_logger().warn("look : angle au-delà de la course du cou (±{:.0f}°), saturé : {!r}".format(
                look_course_deg(self.gaze.gain), ros_msg.msg))
        self.gaze.look(order.azimuth, order.hold_ms, now)
        if self.eyes_enabled:
            self.eyes.look(order.azimuth, order.hold_ms, now)
        self.get_logger().info("look : azimut {:+.2f} pendant {} ms, puis {}".format(
            order.azimuth, order.hold_ms, "reprise du suivi" if self._user_enabled else "retour au centre"))

    def _on_tick(self):
        now = _now_ms()

        # Péremption de l'état animation (garde-fou façon deadman, cf.
        # STATE_EXPIRY_MARGIN_MS) : la fin de séquence normale arrive par un
        # "" sur animation_state — si animations_node est mort en pleine
        # séquence, on reprend la main plutôt que de rester muet pour toujours.
        if self._animation_active and now > self._animation_expiry_ms:
            self._animation_active = False
            self.get_logger().warn(
                "état animation périmé (animations_node muet ?) : reprise du gaze")
            self._apply_enabled()

        consigne = self.gaze.tick(now)
        if consigne is not None:
            if self.output_mode == "sim":
                self.pub.publish(Float64(data=consigne_to_radians(consigne)))
            else:
                # Contrat vrai robot : msg = json.dumps(valeur 0-99), time = 0.
                self.pub.publish(StringTime(msg=json.dumps(consigne), time=0))

        # Yeux : même consigne aux deux servos (cf. déclaration des paramètres),
        # anti-spam porté par l'instance GazeControl dédiée.
        eye_consigne = self.eyes.tick(now)
        if eye_consigne is not None:
            for pub in self.eye_pubs:
                pub.publish(StringTime(msg=json.dumps(eye_consigne), time=0))


def main(args=None):
    rclpy.init(args=args)
    node = GazeFollowerNode()
    try:
        rclpy.spin(node)
    except Exception as e:
        node.get_logger().error(str(e))
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    main()
