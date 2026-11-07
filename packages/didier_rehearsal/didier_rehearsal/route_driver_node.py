#!/usr/bin/env python3
"""Node `route_driver` : Didier CHEMINE SEUL dans la rue simulée (SIM-ONLY).

SÉCURITÉ (cf. CLAUDE.md — ce node publie une consigne roues) :
 - Sortie UNIQUE : Twist sur `cmd_vel_follow`, créneau PRIORITÉ 20 du
   twist_mux — structurellement SOUS la télécommande (100) et le web (50) ;
   le twist_deadman (400 ms) reste derrière. Jamais e_stop/wheels/cmd_vel.
 - Démarre DÉSACTIVÉ ; activation à chaud par le topic `route` ("on"/"off").
 - Publie, latchés, l'ÉTAT de la route (`route_state`) et sa CAUSE
   (`route_state_cause` : "boot" au démarrage, "cmd" à chaque extinction par
   commande) : le régisseur ne relance à la voix qu'une route éteinte par un
   REBOOT, jamais par David (revue adversariale I1, 22/10).
 - Zéro FRANC dès qu'une condition manque (désactivé, odométrie périmée,
   arrivé), puis silence : le mux retombe sur les autres entrées.
 - Le suivi de personne (person_follower) doit être OFF pendant la route :
   même créneau du mux. Rien ici ne le force — c'est une règle de séance,
   écrite dans le README et l'étude §12.
 - Ce package n'est JAMAIS dans didier_bringup (test anti-fuite). La pose
   consommée ici (/ground_truth/odom, vérité terrain gz) n'existe que dans
   Gazebo : sur le vrai robot, ce node n'aurait aucune pose et resterait à zéro.
 - Lot M1 « aller voir » (spec-aller-voir.md) : un ordre `route_goto` du
   régisseur SUSPEND le suivi (zéro franc) et lance une manœuvre bornée
   (didier_rehearsal.goto) sur la MÊME sortie unique. État "goto" puis
   "arrived" (ou "off" si abandonnée). `cancel`, `route off`, `route on`
   l'abandonnent avec un zéro franc IMMÉDIAT (publié dans le callback, sans
   attendre le tick). Ceinture : un ordre est refusé ici aussi tant que la
   route est OFF par David (dernière commande `route` = off). Après une
   manœuvre, la reprise (`route on`) vise le waypoint le plus proche DEVANT
   (RouteFollower.rejoin).
 - Lot M2 (spec-aller-voir.md §7.2-§7.3) : MÊME canal, gestes chiffrés
   {"turn_rad"} (pivot seul) et {"forward_m"} (ligne droite sur le cap,
   jamais de recul), validés et bornés dans goto.parse_order / GotoManeuver
   (délais propres, croisière, fader, calage) ; mêmes abandons, même état
   "goto" -> "arrived".
 - Lot M3 (spec-aller-voir.md §8.4) : MÊME canal, {"name", "orbit_x", "orbit_y",
   "orbit_r", "orbit_dir"} -> approche du cercle, un tour complet, arrêt face
   au centre (goto.OrbitOrder) ; abandon « off_track » hors du cercle. Le
   MÊME tour redemandé (même centre, rayon, sens) est ignoré, comme le même
   objet d'« aller voir » ; un tour dans l'autre sens est un nouvel ordre.

Node volontairement FIN : I/O seulement, toute la logique est dans
didier_rehearsal.route et didier_rehearsal.goto (pures, testées sans ROS).
"""

import json
import logging
import os
import time

import rclpy
import yaml
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from theatre_interfaces.msg import StringTime
from theatre_contrats import stringtime

from didier_rehearsal.contracts import (CMD_VEL_TOPIC, ODOM_TOPIC, POI_EVENT_TOPIC,
                                       ROUTE_CMD_TOPIC, ROUTE_GOTO_CANCEL, ROUTE_GOTO_RESULT_TOPIC,
                                       ROUTE_GOTO_TOPIC,
                                       ROUTE_SPEED_TOPIC, ROUTE_STATE_CAUSE_TOPIC,
                                       ROUTE_STATE_TOPIC, check_domain)
from didier_rehearsal.goto import (ARRIVED, ForwardOrder, GotoConfig, GotoError, GotoManeuver, GotoOrder,
                                   OrbitOrder, TurnOrder, parse_order)

# Latché : un abonné arrivé après coup (régisseur relancé) reçoit l'état courant.
LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
from didier_rehearsal.route import (PoiWatcher, RouteConfig, RouteError, RouteFollower,
                                   load_route, yaw_from_quaternion)


def _now_ms() -> int:
    """Horloge MONOTONE (même choix que person_follower) : la péremption de
    l'odométrie ne dépend pas du temps ROS — sim en pause = odom périmée =
    zéro, ce qui est exactement le comportement voulu."""
    return int(time.monotonic() * 1000)


def _decode(raw: str):
    """Payload StringTime : JSON si possible, brut sinon (contrat commun
    follow/gaze/chat) — theatre_contrats.stringtime.decode_or_raw."""
    return stringtime.decode_or_raw(raw)


class RouteDriverNode(Node):
    def __init__(self):
        check_domain(os.environ)   # refus hors domaine 43 (revue du 08/10)
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
        # Manœuvre « aller voir » (lot M1) : None = suivi d'itinéraire seul.
        self.goto = None
        self._arrived = None        # nom de l'objet devant lequel Didier est arrêté
        self._goto_dirty = False    # une manœuvre a déplacé Didier : rejoin() au prochain `on`
        self._off_by_david = False  # dernière commande `route` = off (ceinture du régisseur)
        self._last_pose = None      # (x, y, yaw, ms) : amorce la manœuvre sans attendre /odom

        self.cmd_pub = self.create_publisher(Twist, CMD_VEL_TOPIC, 10)
        self.poi_pub = self.create_publisher(StringTime, POI_EVENT_TOPIC, 10)
        self.state_pub = self.create_publisher(StringTime, ROUTE_STATE_TOPIC, LATCHED)
        self.cause_pub = self.create_publisher(StringTime, ROUTE_STATE_CAUSE_TOPIC, LATCHED)
        self.goto_result_pub = self.create_publisher(StringTime, ROUTE_GOTO_RESULT_TOPIC, 10)
        # Manœuvre : jamais plus vite que la croisière CONFIGURÉE du suivi
        # (max_lin / max_ang du node), en plus de ses propres plafonds.
        goto_defaults = GotoConfig()
        self.goto_config = GotoConfig(**{**goto_defaults.__dict__,
                                         "max_lin": min(goto_defaults.max_lin, self.follower.config.max_lin),
                                         "max_ang": min(goto_defaults.max_ang, self.follower.config.max_ang)})
        self.create_subscription(Odometry, ODOM_TOPIC, self._on_odom, 10)
        self.create_subscription(StringTime, ROUTE_CMD_TOPIC, self._on_route_cmd, 10)
        self.create_subscription(StringTime, ROUTE_SPEED_TOPIC, self._on_speed, 10)
        # VOLATILE : un ordre ancien rejoué au démarrage ferait partir Didier.
        self.create_subscription(StringTime, ROUTE_GOTO_TOPIC, self._on_goto, 10)

        # Cause AVANT l'état : un abonné qui lit l'état « off » doit déjà
        # trouver sa cause. "boot" même si enabled=True (la cause ne sert
        # qu'à qualifier un état OFF).
        self._publish_cause("boot")
        self._publish_state()
        tick_hz = float(self.get_parameter("tick_hz").value)
        self.create_timer(1.0 / tick_hz, self._tick)
        self.get_logger().info(
            f"route_driver prêt : itinéraire « {route.name} », {len(route.waypoints)} points, "
            f"{len(route.pois)} POI, enabled={self.follower.enabled}, speed={self.follower.speed:g} "
            f"-> {CMD_VEL_TOPIC} (mux prio 20)"
        )

    def _state(self) -> str:
        if self.goto is not None:
            return "goto"
        if self._arrived is not None:
            return "arrived"
        return "on" if self.follower.enabled else "off"

    def _publish_state(self):
        self.state_pub.publish(StringTime(msg=self._state(), time=0, anim=False))

    def _publish_cause(self, cause: str):
        self.cause_pub.publish(StringTime(msg=json.dumps(cause), time=0, anim=False))

    def _on_odom(self, msg: Odometry):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw, now = yaw_from_quaternion(q.x, q.y, q.z, q.w), _now_ms()
        self.follower.update_pose(p.x, p.y, yaw, now)
        if self.goto is not None:
            self.goto.update_pose(p.x, p.y, yaw, now)
        self._last_pose = (p.x, p.y, yaw, now)
        # Les POI sont dans le repère MONDE : la vérité terrain l'est aussi.
        for ev in self.pois.update(p.x, p.y):
            payload = {"poi": ev.poi, "event": ev.event, "distance": round(ev.distance, 2)}
            self.poi_pub.publish(StringTime(msg=json.dumps(payload), time=0, anim=False))
            self.get_logger().info(f"POI {ev.event} : {ev.poi} ({ev.distance:.1f} m)")

    def _on_route_cmd(self, msg: StringTime):
        value = _decode(msg.msg)
        if value in ("on", True, 1, "1"):
            # Route ON pendant une manœuvre : David reprend la main, elle tombe.
            self._abandon_goto("route_on")
            self._arrived = None
            self._off_by_david = False
            if self._goto_dirty:
                # Didier a quitté le chemin (aller voir) : reprise vers le
                # waypoint le plus proche DEVANT, pas l'ancien index.
                self.follower.rejoin()
                self._goto_dirty = False
                self.get_logger().info(f"route : reprise au waypoint {self.follower.waypoint_index}")
            self.follower.set_enabled(True)
            self._publish_state()
            self.get_logger().info("route ON : cheminement activé")
        elif value in ("off", False, 0, "0"):
            self._abandon_goto("route_off")
            self._arrived = None
            self._off_by_david = True
            self.follower.set_enabled(False)
            # À CHAQUE extinction par commande, quel que soit son format : c'est
            # ce qui interdit au régisseur de relancer à la voix contre David.
            self._publish_cause("cmd")
            self._publish_state()
            self.get_logger().info("route OFF : cheminement désactivé (zéro publié)")
        elif value == "restart":
            self.follower.restart()
            self.get_logger().info("route RESTART : itinéraire repris au début")
        else:
            self.get_logger().warning(f"route : commande ignorée {msg.msg!r}")

    def _halt(self, reason: str):
        """Zéro franc IMMÉDIAT (dans le callback, pas au tick suivant) si une
        consigne non nulle était en cours ; le tick reste ensuite silencieux."""
        if self._last_reason == "ok":
            self.cmd_pub.publish(Twist())
        if reason != self._last_reason:
            self.get_logger().info(f"route : {reason}")
            self._last_reason = reason

    def _goto_result(self, result: str, reason: str):
        """Issue de la manœuvre courante : log + route_goto_result (journal du régisseur)."""
        payload = {"name": self.goto.order.name, "result": result, "reason": reason,
                   "travelled": round(self.goto.travelled, 2)}
        text = json.dumps(payload)
        if result == "arrived":
            self.get_logger().info(f"goto_arrived {text}")
        else:
            self.get_logger().warning(f"goto_abort {text}")
        self.goto_result_pub.publish(StringTime(msg=text, time=0, anim=False))

    def _abandon_goto(self, by: str) -> bool:
        """Abandonne la manœuvre en cours (stop, cancel, route on/off) :
        zéro franc immédiat. -> True s'il y en avait une. L'appelant publie l'état."""
        if self.goto is None:
            return False
        self.goto.cancel()
        self._goto_result("aborted", by)
        self.goto = None
        self._halt("cancelled")
        return True

    def _on_goto(self, msg: StringTime):
        """Ordre du régisseur : JSON {name, x, y, standoff} (M1), {turn_rad} /
        {forward_m} (M2), {name, orbit_*} (M3) ou "cancel"."""
        value = _decode(msg.msg)
        if value == ROUTE_GOTO_CANCEL:
            if self._abandon_goto("cancel"):
                self._publish_state()
            return
        if self._off_by_david:
            # Ceinture du refus du régisseur : jamais de mouvement contre un `off` de David.
            self.get_logger().warning(f"route_goto refusé (route OFF par David) : {msg.msg!r}")
            return
        try:
            order = parse_order(value)
        except GotoError as e:
            self.get_logger().warning(f"route_goto refusé : {e}")
            return
        if self.goto is not None and (
                (isinstance(order, GotoOrder) and self.goto.order.name == order.name)
                # Tour : même cercle ET même sens (le LLM redit « fais le tour »
                # au tour suivant : ni arrêt, ni angle balayé ni délai remis à zéro).
                or (isinstance(order, OrbitOrder) and self.goto.order == order)):
            # MÊME objet redemandé (le LLM le redit au tour suivant) : rien —
            # ni arrêt franc, ni délai remis à zéro (la borne de 60 s tient).
            # Un GESTE (pivot, ligne droite) redemandé, lui, est un NOUVEL
            # ordre (revue M2, choix le plus simple et sûr) : « tourne à
            # gauche, encore » = encore 90°, comptés depuis la pose courante ;
            # l'ancien tombe avec un zéro franc (abandon « goto_suivant »),
            # chaque ordre garde ses propres bornes. Pas de cumul : un cumul
            # demanderait de rebudgéter délai et translation à la volée.
            self.get_logger().info(f"route_goto : « {order.name} » déjà en cours, ignoré")
            return
        self._abandon_goto("goto_suivant")
        # Le suivi s'efface (zéro franc) : UNE seule consigne sur la sortie.
        was_on = self.follower.enabled
        self.follower.set_enabled(False)
        if was_on:
            self._halt("goto")
        now = _now_ms()
        self.goto = GotoManeuver(order, now, self.goto_config)
        if self._last_pose is not None:
            # Dernière pose connue, avec SON horodatage : périmée, elle le reste.
            self.goto.update_pose(*self._last_pose)
        self._arrived = None
        self._goto_dirty = True
        self._publish_state()
        if isinstance(order, TurnOrder):
            what = f"{order.turn_rad:+.4f} rad, sur place"
        elif isinstance(order, ForwardOrder):
            what = "ligne droite sur le cap courant"
        elif isinstance(order, OrbitOrder):
            what = (f"autour de ({order.cx:.2f}, {order.cy:.2f}), rayon {order.radius:g} m, "
                    f"{'gauche' if order.direction > 0 else 'droite'}")
        else:
            what = f"vers ({order.x:.2f}, {order.y:.2f}), arrêt à {order.standoff:g} m"
        self.get_logger().info(f"route_goto : « {order.name} » {what}")

    def _on_speed(self, msg: StringTime):
        before = self.follower.speed
        self.follower.set_speed(_decode(msg.msg))
        if self.follower.speed != before:
            self.get_logger().info(f"route_speed = {self.follower.speed:.2f}")

    def _tick(self):
        if self.goto is not None:
            out = self.goto.tick(_now_ms(), self.follower.speed)
            if self.goto.finished:
                arrived = self.goto.phase == ARRIVED
                self._goto_result("arrived" if arrived else "aborted", out.reason)
                if arrived:
                    self._arrived = self.goto.order.name
                self.goto = None
                self._publish_state()
        else:
            out = self.follower.tick(_now_ms())
        if out.reason in ("ok", "held"):
            # "held" (facteur 0) : zéro PUBLIÉ à chaque tick — le créneau 20 du
            # mux reste tenu (une lubie stop n'ouvre pas les roues à l'animation).
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
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error(e, exc_info=True)
    finally:
        if node is not None:
            node.destroy_node()
        # SIGTERM (kill du régisseur, arrêt du launch) a souvent DÉJÀ fermé le
        # contexte : un second shutdown lève et sort en code 1 (vécu 08/10).
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
