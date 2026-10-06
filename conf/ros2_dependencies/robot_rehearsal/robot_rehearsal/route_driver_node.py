#!/usr/bin/env python3
"""Node `route_driver` : Didier CHEMINE SEUL dans la rue simulée (SIM-ONLY).

SÉCURITÉ (cf. CLAUDE.md — ce node publie une consigne roues) :
 - Sortie UNIQUE : Twist sur `cmd_vel_follow`, créneau PRIORITÉ 20 du
   twist_mux — structurellement SOUS la télécommande (100) et le web (50) ;
   le twist_deadman (400 ms) reste derrière. Jamais e_stop/wheels/cmd_vel.
 - Démarre DÉSACTIVÉ ; activation à chaud par le topic `route` ("on"/"off").
 - Zéro FRANC dès qu'une condition manque (désactivé, odométrie périmée,
   arrivé), puis silence : le mux retombe sur les autres entrées.
 - Le suivi de personne (person_follower) doit être OFF pendant la route :
   même créneau du mux. Rien ici ne le force — c'est une règle de séance,
   écrite dans le README et l'étude §12.
 - Ce package n'est JAMAIS dans robot_bringup (test anti-fuite). La pose
   consommée ici (/ground_truth/odom, vérité terrain gz) n'existe que dans
   Gazebo : sur le vrai robot, ce node n'aurait aucune pose et resterait à zéro.

Node volontairement FIN : I/O seulement, toute la logique est dans
robot_rehearsal.route (pure, testée sans ROS).
"""

import json
import logging
import time

import rclpy
import yaml
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from robot_interfaces.msg import StringTime

from robot_rehearsal.contracts import (CMD_VEL_TOPIC, ODOM_TOPIC, POI_EVENT_TOPIC,
                                       ROUTE_CMD_TOPIC, ROUTE_SPEED_TOPIC)
from robot_rehearsal.route import (PoiWatcher, RouteConfig, RouteError, RouteFollower,
                                   load_route, yaw_from_quaternion)


def _now_ms() -> int:
    """Horloge MONOTONE (même choix que person_follower) : la péremption de
    l'odométrie ne dépend pas du temps ROS — sim en pause = odom périmée =
    zéro, ce qui est exactement le comportement voulu."""
    return int(time.monotonic() * 1000)


def _decode(raw: str):
    """Payload StringTime : JSON si possible, brut sinon (contrat commun
    follow/gaze/chat)."""
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


class RouteDriverNode(Node):
    def __init__(self):
        super().__init__("route_driver")

        defaults = RouteConfig()
        self.declare_parameter("route_file", "")          # YAML obligatoire
        self.declare_parameter("enabled", False)          # DÉSACTIVÉ par défaut
        self.declare_parameter("speed", 0.5)              # facteur 0..1 (le fader)
        self.declare_parameter("max_lin", defaults.max_lin)
        self.declare_parameter("max_ang", defaults.max_ang)
        self.declare_parameter("ang_gain", defaults.ang_gain)
        self.declare_parameter("arrive_radius_m", defaults.arrive_radius_m)
        self.declare_parameter("heading_slow_rad", defaults.heading_slow_rad)
        self.declare_parameter("odom_timeout_ms", defaults.odom_timeout_ms)
        self.declare_parameter("tick_hz", 10.0)

        route_file = str(self.get_parameter("route_file").value)
        if not route_file:
            raise RuntimeError("route_file manquant : chemin du YAML d'itinéraire requis")
        with open(route_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        try:
            route = load_route(data)
        except RouteError as e:
            # Refus EXPLICITE au démarrage : un itinéraire faux ne roule pas.
            raise RuntimeError(f"itinéraire invalide ({route_file}) : {e}") from e

        config = RouteConfig(
            max_lin=float(self.get_parameter("max_lin").value),
            max_ang=float(self.get_parameter("max_ang").value),
            ang_gain=float(self.get_parameter("ang_gain").value),
            arrive_radius_m=float(self.get_parameter("arrive_radius_m").value),
            heading_slow_rad=float(self.get_parameter("heading_slow_rad").value),
            lin_slew=defaults.lin_slew,
            ang_slew=defaults.ang_slew,
            odom_timeout_ms=int(self.get_parameter("odom_timeout_ms").value),
        )
        self.follower = RouteFollower(
            route, config,
            enabled=bool(self.get_parameter("enabled").value),
            speed=float(self.get_parameter("speed").value),
        )
        self.pois = PoiWatcher(route.pois)
        self._last_reason = None

        self.cmd_pub = self.create_publisher(Twist, CMD_VEL_TOPIC, 10)
        self.poi_pub = self.create_publisher(StringTime, POI_EVENT_TOPIC, 10)
        self.create_subscription(Odometry, ODOM_TOPIC, self._on_odom, 10)
        self.create_subscription(StringTime, ROUTE_CMD_TOPIC, self._on_route_cmd, 10)
        self.create_subscription(StringTime, ROUTE_SPEED_TOPIC, self._on_speed, 10)

        tick_hz = float(self.get_parameter("tick_hz").value)
        self.create_timer(1.0 / tick_hz, self._tick)
        self.get_logger().info(
            f"route_driver prêt : itinéraire « {route.name} », {len(route.waypoints)} points, "
            f"{len(route.pois)} POI, enabled={self.follower.enabled}, speed={self.follower.speed:g} "
            f"-> {CMD_VEL_TOPIC} (mux prio 20)"
        )

    def _on_odom(self, msg: Odometry):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        self.follower.update_pose(p.x, p.y, yaw_from_quaternion(q.x, q.y, q.z, q.w), _now_ms())
        # Les POI sont dans le repère MONDE : la vérité terrain l'est aussi.
        for ev in self.pois.update(p.x, p.y):
            payload = {"poi": ev.poi, "event": ev.event, "distance": round(ev.distance, 2)}
            self.poi_pub.publish(StringTime(msg=json.dumps(payload), time=0, anim=False))
            self.get_logger().info(f"POI {ev.event} : {ev.poi} ({ev.distance:.1f} m)")

    def _on_route_cmd(self, msg: StringTime):
        value = _decode(msg.msg)
        if value in ("on", True, 1, "1"):
            self.follower.set_enabled(True)
            self.get_logger().info("route ON : cheminement activé")
        elif value in ("off", False, 0, "0"):
            self.follower.set_enabled(False)
            self.get_logger().info("route OFF : cheminement désactivé (zéro publié)")
        elif value == "restart":
            self.follower.restart()
            self.get_logger().info("route RESTART : itinéraire repris au début")
        else:
            self.get_logger().warning(f"route : commande ignorée {msg.msg!r}")

    def _on_speed(self, msg: StringTime):
        before = self.follower.speed
        self.follower.set_speed(_decode(msg.msg))
        if self.follower.speed != before:
            self.get_logger().info(f"route_speed = {self.follower.speed:.2f}")

    def _tick(self):
        out = self.follower.tick(_now_ms())
        if out.reason == "ok":
            self.cmd_pub.publish(Twist(linear=_v3(out.lin), angular=_v3z(out.ang)))
        elif self._last_reason == "ok":
            # Transition ok -> arrêt : UN zéro franc, puis silence (le mux
            # retombe sur les autres entrées, le deadman fait le reste).
            self.cmd_pub.publish(Twist())
        if out.reason != self._last_reason:
            self.get_logger().info(f"route : {out.reason}")
            self._last_reason = out.reason


def _v3(x: float):
    from geometry_msgs.msg import Vector3
    return Vector3(x=float(x), y=0.0, z=0.0)


def _v3z(z: float):
    from geometry_msgs.msg import Vector3
    return Vector3(x=0.0, y=0.0, z=float(z))


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = RouteDriverNode()
        rclpy.spin(node)
    except Exception as e:
        logging.error(e, exc_info=True)
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
