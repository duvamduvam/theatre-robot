#!/usr/bin/env python3
"""Node `person_follower` : le robot suit une personne AUX ROUES.

SÉCURITÉ (cf. CLAUDE.md — ce node commande les 50 kg du robot) :
 - Sortie UNIQUE : Twist sur `cmd_vel_follow`, entrée du twist_mux à
   priorité 20 — STRUCTURELLEMENT sous la télécommande (100) et le web (50) :
   reprendre la main physique écrase toujours le suivi. Il ne touche JAMAIS
   e_stop/wheels/neck — aucun de ces topics n'apparaît ici.
 - Démarre DÉSACTIVÉ (enabled=False) : télécommande > autonome, toujours.
   Activation en direct via le topic `follow` ("on"/"off" — même contrat que
   `gaze` et `chat`).
 - Personne perdue / désactivation -> zéro franc puis silence (le twist_mux
   retombe sur les autres entrées ; le twist_deadman aval reste l'ultime
   rempart). Toute la logique de décision (deadzones, plafonds durs, slew,
   timeout) vit dans robot.move.follow_control.FollowControl (pure, testée).

NON AJOUTÉ au launch de prod (robot_bringup) : usage au sol conditionné au
test scénique (feuille de route priorité 1) PUIS à un protocole caméra roues
hors sol (direction_sign azimut->rotation inconnu, comme le gaze). D'ici là :
validation en SIMULATION uniquement, node lancé À LA MAIN.

Node volontairement FIN (I/O seulement), même pattern que gaze_follower_node :
pas d'import robot_config ni robot.actions.* — il tourne tel quel dans le
conteneur de simulation.
"""

import json
import time

import rclpy
from geometry_msgs.msg import PointStamped, Twist
from rclpy.node import Node
from robot_interfaces.msg import StringTime

from robot.move.follow_control import FollowConfig, FollowControl

# Contrats de topics (ne pas dévier — interfaces existantes).
VISION_BOX_TOPIC = "/vision/person_box"  # PointStamped : x=azimut, y=HAUTEUR silhouette, z=confiance
FOLLOW_CMD_TOPIC = "follow"              # StringTime "on"/"off" : activation en direct
CMD_VEL_TOPIC = "cmd_vel_follow"         # Twist -> twist_mux priorité 20


def _now_ms():
    """Horloge MONOTONE en millisecondes (même choix que gaze_follower : les
    timeouts de cible ne dépendent pas du temps ROS/sim, et une horloge
    monotone est insensible aux sauts d'horloge)."""
    return int(time.monotonic() * 1000)


class PersonFollowerNode(Node):
    def __init__(self):
        super().__init__("person_follower")

        # --- Paramètres ROS déclarés (défauts = FollowConfig, jamais dupliqués
        # en dur ici — la dataclass est la source unique de vérité) ---
        defaults = FollowConfig()
        self.declare_parameter("enabled", False)  # DÉSACTIVÉ par défaut
        self.declare_parameter("direction_sign", defaults.direction_sign)
        self.declare_parameter("confidence_min", defaults.confidence_min)
        self.declare_parameter("az_deadzone", defaults.az_deadzone)
        self.declare_parameter("ang_gain", defaults.ang_gain)
        self.declare_parameter("max_ang", defaults.max_ang)
        self.declare_parameter("target_height", defaults.target_height)
        self.declare_parameter("height_deadzone", defaults.height_deadzone)
        self.declare_parameter("lin_gain", defaults.lin_gain)
        self.declare_parameter("max_lin", defaults.max_lin)
        self.declare_parameter("allow_reverse", defaults.allow_reverse)
        self.declare_parameter("timeout_ms", defaults.timeout_ms)
        self.declare_parameter("tick_hz", 10.0)

        config = FollowConfig(
            direction_sign=int(self.get_parameter("direction_sign").value),
            confidence_min=float(self.get_parameter("confidence_min").value),
            az_deadzone=float(self.get_parameter("az_deadzone").value),
            ang_gain=float(self.get_parameter("ang_gain").value),
            max_ang=float(self.get_parameter("max_ang").value),
            target_height=float(self.get_parameter("target_height").value),
            height_deadzone=float(self.get_parameter("height_deadzone").value),
            lin_gain=float(self.get_parameter("lin_gain").value),
            max_lin=float(self.get_parameter("max_lin").value),
            allow_reverse=bool(self.get_parameter("allow_reverse").value),
            timeout_ms=int(self.get_parameter("timeout_ms").value),
        )
        enabled = bool(self.get_parameter("enabled").value)
        tick_hz = float(self.get_parameter("tick_hz").value)

        self.follow = FollowControl(config, enabled=enabled)

        # --- Sortie : Twist vers le mux (sim et réel : même topic, c'est le
        # twist_mux qui arbitre partout) ---
        self.pub = self.create_publisher(Twist, CMD_VEL_TOPIC, 10)

        # --- Entrées ---
        self.create_subscription(PointStamped, VISION_BOX_TOPIC, self._on_person_box, 10)
        self.create_subscription(StringTime, FOLLOW_CMD_TOPIC, self._on_follow_cmd, 10)

        self.create_timer(1.0 / tick_hz, self._on_tick)

        self.get_logger().info(
            "person_follower démarré : enabled={} direction_sign={} max_lin={} max_ang={}"
            " -> {} (mux prio 20, télécommande > web > suivi)".format(
                enabled, config.direction_sign, self.follow.max_lin,
                self.follow.max_ang, CMD_VEL_TOPIC))

    def _on_person_box(self, msg):
        # x=azimut [-1..1], y=hauteur de silhouette [0..1], z=confiance [0..1]
        # (contrat /vision/person_box, cf. dadou_vision_ros target_picker.py).
        self.follow.update(msg.point.x, msg.point.y, msg.point.z, _now_ms())

    def _on_follow_cmd(self, ros_msg):
        # Même contrat que gaze/chat : "on"/"off", json ou brut tolérés.
        raw = ros_msg.msg
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            value = raw
        if value in ("on", True, 1, "1"):
            self.follow.set_enabled(True)
            self.get_logger().info("follow ON : suivi aux roues activé")
        elif value in ("off", False, 0, "0"):
            self.follow.set_enabled(False)  # zéro franc au prochain tick
            self.get_logger().info("follow OFF : suivi désactivé (zéro publié)")
        else:
            self.get_logger().warning(f"commande follow inconnue : {raw!r}")

    def _on_tick(self):
        command = self.follow.tick(_now_ms())
        if command is None:
            return  # IDLE/désactivé : silence total (le mux retombe ailleurs)
        lin, ang = command
        twist = Twist()
        twist.linear.x = lin
        twist.angular.z = ang
        self.pub.publish(twist)


def main(args=None):
    rclpy.init(args=args)
    node = PersonFollowerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass  # arrêt normal (Ctrl-C / SIGINT), pas une erreur à tracer
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
