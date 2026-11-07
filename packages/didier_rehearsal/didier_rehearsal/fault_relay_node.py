#!/usr/bin/env python3
"""Node `fault_relay` : un point de relais générique (SIM-ONLY), passant par
défaut, piloté par le régisseur (rehearsal/relay_cmd) et protégé par son
battement (rehearsal/heartbeat) : sans battement > 1 s, retour en passant.

Toute la décision est dans didier_rehearsal.fault_relay (pure, testée) ; ici
seulement l'I/O : abonnement amont, publication aval, traduction du sentinel
ZERO en message nul du bon type. Paramètre `relay` = clé de contracts.RELAYS.
"""
import logging
import os
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from robot_interfaces.msg import StringTime
from theatre_contrats import stringtime

from didier_rehearsal.contracts import HEARTBEAT_TOPIC, RELAYS, RELAY_CMD_TOPIC, check_domain
from didier_rehearsal.fault_relay import ZERO, FaultRelay

TYPES = {"twist": Twist, "string_time": StringTime}


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


class FaultRelayNode(Node):
    def __init__(self):
        check_domain(os.environ)   # refus hors domaine 43
        super().__init__("fault_relay")
        self.declare_parameter("relay", "")
        self.declare_parameter("seed", 0)
        name = str(self.get_parameter("relay").value)
        if name not in RELAYS:
            raise RuntimeError(f"relay « {name} » inconnu ; attendu parmi {sorted(RELAYS)}")
        upstream, downstream, typ = RELAYS[name]
        self.msg_type = TYPES[typ]
        self.relay = FaultRelay(name, seed=int(self.get_parameter("seed").value))
        # QoS profondeur 1 : une consigne périmée ne vaut rien (étude §11.1).
        self.pub = self.create_publisher(self.msg_type, downstream, 1)
        self.create_subscription(self.msg_type, upstream, self._on_msg, 1)
        self.create_subscription(StringTime, RELAY_CMD_TOPIC, self._on_cmd, 10)
        self.create_subscription(StringTime, HEARTBEAT_TOPIC, self._on_heartbeat, 10)
        self.create_timer(0.05, self._tick)   # 20 Hz : relâche des retards + chien de garde
        self._last_op = "pass"
        # Le nom est le même que le node pour pouvoir en lancer plusieurs.
        self.get_logger().info(f"relais « {name} » : {upstream} -> {downstream} ({typ}), passant")

    def _emit(self, items):
        for m in items:
            self.pub.publish(self.msg_type() if m is ZERO else m)
        if self.relay.op != self._last_op:
            self.get_logger().info(f"relais « {self.relay.name} » : {self._last_op} -> {self.relay.op}")
            self._last_op = self.relay.op

    def _on_msg(self, msg):
        self._emit(self.relay.process(msg, _now_ms()))

    def _tick(self):
        self._emit(self.relay.tick(_now_ms()))

    def _on_heartbeat(self, _msg):
        self.relay.heartbeat(_now_ms())

    def _on_cmd(self, msg: StringTime):
        try:
            # `loads` (et non decode) : ce node a son propre refus (warning +
            # return) et n'attrape QUE ValueError — gardé tel quel (lot L1a).
            cmd = stringtime.loads(msg.msg)
        except ValueError:
            self.get_logger().warning(f"relay_cmd illisible : {msg.msg!r}")
            return
        if not isinstance(cmd, dict) or cmd.get("relay") != self.relay.name:
            return   # pas pour moi
        now = _now_ms()
        until = cmd.get("until_ms")
        try:
            self.relay.set_op(str(cmd.get("op")), cmd.get("params") or {}, now,
                              None if until is None else now + int(until))
        except ValueError as e:
            self.get_logger().warning(str(e))
            return
        self._emit([])


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = FaultRelayNode()
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
