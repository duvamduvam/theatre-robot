#!/usr/bin/env python3
"""Node `director` : le RÉGISSEUR de pannes (SIM-ONLY, canal technique).

Charge un scénario YAML (validé, expansé avec sa graine), attend « start »
sur rehearsal/cmd (autostart false par défaut), puis exécute la timeline :
  relay       -> ordre au relais (rehearsal/relay_cmd), révoqué à la fin ;
  pause       -> SIGSTOP du processus (liste blanche), SIGCONT à la fin ;
  kill        -> SIGTERM de route_driver (le launch le respawne), puis
                 « route on » après reenable_delay_s si demandé ;
  speed       -> route_speed = value, puis restore à la fin ;
  instruction -> publie le texte sur rehearsal/instruction (canal joué —
                 consommateur au lot R3) ;
et JOURNALISE tout (robot.diagnostic.journal, JSONL) : la frise du débrief.
Bat à 5 Hz sur rehearsal/heartbeat : s'il meurt, les relais retombent seuls
en passant (chien de garde côté relais, pas ici).

SÉCURITÉ : ce node ne publie JAMAIS de Twist. Ses seuls effets sur le
mouvement passent par le relais de cmd_vel_follow (sous la télécommande, au-
dessus du deadman) et par route/route_speed (le cheminement). Il n'est jamais
dans le bringup du robot.
"""
import json
import logging
import os
import time
from datetime import datetime

import rclpy
import yaml
from rclpy.node import Node
from robot_interfaces.msg import StringTime

from robot.diagnostic.journal import make_event
from robot_rehearsal.contracts import (DIRECTOR_CMD_TOPIC, HEARTBEAT_TOPIC, INSTRUCTION_TOPIC,
                                       RELAY_CMD_TOPIC, ROUTE_CMD_TOPIC, ROUTE_SPEED_TOPIC)
from robot_rehearsal.director import Director
from robot_rehearsal.process_faults import ProcessFaultError, apply
from robot_rehearsal.scenario import ScenarioError, load_scenario


def _mono_ms() -> int:
    return int(time.monotonic() * 1000)


class DirectorNode(Node):
    def __init__(self):
        super().__init__("director")
        self.declare_parameter("scenario_file", "")
        self.declare_parameter("seed", -1)           # -1 = graine du fichier
        self.declare_parameter("autostart", False)
        self.declare_parameter("tick_hz", 10.0)
        self.declare_parameter("journal_dir", "/home/ros2_ws/log/rehearsal")
        self.declare_parameter("reenable_delay_s", 8.0)   # > respawn_delay du launch (5 s)

        path = str(self.get_parameter("scenario_file").value)
        if not path:
            raise RuntimeError("scenario_file manquant")
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        seed = int(self.get_parameter("seed").value)
        try:
            self.scenario = load_scenario(data, seed=None if seed < 0 else seed)
        except ScenarioError as e:
            raise RuntimeError(f"scénario invalide ({path}) : {e}") from e
        self.director = Director(self.scenario)
        self.reenable_delay_s = float(self.get_parameter("reenable_delay_s").value)

        journal_dir = str(self.get_parameter("journal_dir").value)
        os.makedirs(journal_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.journal_path = os.path.join(journal_dir, f"{stamp}_{self.scenario.name}.jsonl")
        self._journal = open(self.journal_path, "a", encoding="utf-8")

        self.pub_heartbeat = self.create_publisher(StringTime, HEARTBEAT_TOPIC, 10)
        self.pub_relay = self.create_publisher(StringTime, RELAY_CMD_TOPIC, 10)
        self.pub_instruction = self.create_publisher(StringTime, INSTRUCTION_TOPIC, 10)
        self.pub_route = self.create_publisher(StringTime, ROUTE_CMD_TOPIC, 10)
        self.pub_speed = self.create_publisher(StringTime, ROUTE_SPEED_TOPIC, 10)
        self.create_subscription(StringTime, DIRECTOR_CMD_TOPIC, self._on_cmd, 10)
        self.create_timer(0.2, lambda: self.pub_heartbeat.publish(StringTime(msg="1", time=0, anim=False)))
        self.create_timer(1.0 / float(self.get_parameter("tick_hz").value), self._tick)
        self._pending_reenable = []   # [(échéance_mono_s, fault_id)]

        self.log("scenario_loaded", {"name": self.scenario.name, "seed": self.scenario.seed,
                                     "duration_s": self.scenario.duration_s,
                                     "timeline": [{"id": f.id, "type": f.type, "t_s": f.t_s,
                                                   "duration_s": f.duration_s, "params": f.params}
                                                  for f in self.scenario.faults]})
        self.get_logger().info(f"régisseur prêt : « {self.scenario.name} », graine {self.scenario.seed}, "
                               f"{len(self.scenario.faults)} pannes, journal {self.journal_path}")
        if bool(self.get_parameter("autostart").value):
            self._start()

    # --- journal ------------------------------------------------------------
    def log(self, type_: str, payload: dict) -> None:
        ev = make_event(_mono_ms(), "director", type_, payload)
        self._journal.write(ev.to_line() + "\n")
        self._journal.flush()
        self.get_logger().info(f"{type_} {json.dumps(payload, ensure_ascii=False)[:160]}")

    # --- commandes ----------------------------------------------------------
    def _on_cmd(self, msg: StringTime):
        cmd = msg.msg.strip().strip('"')
        if cmd == "start":
            self._start()
        elif cmd in ("stop", "abort"):
            self._execute(self.director.abort(time.monotonic()))
            self.log("scenario_abort", {"cmd": cmd})
        else:
            self.get_logger().warning(f"rehearsal/cmd ignoré : {msg.msg!r}")

    def _start(self):
        if self.director.started:
            self.get_logger().warning("scénario déjà démarré")
            return
        self.director.start(time.monotonic())
        self.log("scenario_start", {"name": self.scenario.name, "seed": self.scenario.seed})

    def _tick(self):
        now = time.monotonic()
        self._execute(self.director.tick(now))
        due = [fid for (t, fid) in self._pending_reenable if now >= t]
        if due:
            self._pending_reenable = [(t, f) for (t, f) in self._pending_reenable if now < t]
            self.pub_route.publish(StringTime(msg="on", time=0, anim=False))
            self.log("route_reenable", {"after_kill": due})

    # --- exécution des actions ---------------------------------------------
    def _execute(self, actions):
        for a in actions:
            if a.kind == "end":
                self.log("scenario_end", {"status": self.director.status()})
                continue
            f = a.fault
            payload = {"id": f.id, "type": f.type, "params": f.params}
            if a.kind == "skip":
                self.log("fault_skip", payload)
                continue
            try:
                self._apply(a.kind, f)
                self.log(f"fault_{a.kind}", payload)
            except (ProcessFaultError, RuntimeError) as e:
                self.log("fault_error", dict(payload, error=str(e)))
                if a.kind == "start":
                    # Jamais de fault_stop pour une panne jamais appliquée.
                    self.director.cancel(f.id, time.monotonic())

    def _apply(self, kind: str, f):
        p = f.params
        if f.type == "relay":
            if kind == "start":
                until_ms = int(f.duration_s * 1000)
                cmd = {"relay": p["relay"], "op": p["op"],
                       "params": {k: v for k, v in p.items() if k not in ("relay", "op")},
                       "until_ms": until_ms}
            else:
                cmd = {"relay": p["relay"], "op": "pass", "params": {}, "until_ms": None}
            self.pub_relay.publish(StringTime(msg=json.dumps(cmd), time=0, anim=False))
        elif f.type == "pause":
            pids = apply("pause" if kind == "start" else "resume", p["process"])
            if kind == "start" and not pids:
                raise RuntimeError(f"aucun processus « {p['process']} » à mettre en pause")
        elif f.type == "kill":
            if kind == "start":
                pids = apply("kill", p["process"])
                if not pids:
                    raise RuntimeError(f"aucun processus « {p['process']} » à tuer")
                if p.get("reenable", True):
                    self._pending_reenable.append((time.monotonic() + self.reenable_delay_s, f.id))
        elif f.type == "speed":
            value = p["value"] if kind == "start" else p["restore"]
            self.pub_speed.publish(StringTime(msg=json.dumps(value), time=0, anim=False))
        elif f.type == "instruction":
            if kind == "start":
                self.pub_instruction.publish(StringTime(msg=json.dumps(p["text"], ensure_ascii=False),
                                                        time=0, anim=False))


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = DirectorNode()
        rclpy.spin(node)
    except Exception as e:
        logging.error(e, exc_info=True)
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
