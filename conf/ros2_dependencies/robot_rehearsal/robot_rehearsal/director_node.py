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
from rclpy.qos import DurabilityPolicy, QoSProfile
from robot_interfaces.msg import StringTime

from robot.diagnostic.journal import JournalWriter, make_event
from robot_rehearsal.contracts import (DIRECTOR_CMD_TOPIC, HEARTBEAT_TOPIC, INSTRUCTION_TOPIC,
                                       RELAY_CMD_TOPIC, ROUTE_CMD_TOPIC, ROUTE_SPEED_TOPIC,
                                       ROUTE_STATE_TOPIC, check_domain)
from robot_rehearsal.director import Director, ReenablePolicy
from robot_rehearsal.process_faults import ProcessFaultError, apply, find_pids, pause_bounded
from robot_rehearsal.scenario import ScenarioError, load_scenario


def _mono_ms() -> int:
    return int(time.monotonic() * 1000)


class DirectorNode(Node):
    def __init__(self):
        check_domain(os.environ)   # refus hors domaine 43, AVANT tout effet
        super().__init__("director")
        self.declare_parameter("scenario_file", "")
        self.declare_parameter("seed", -1)           # -1 = graine du fichier
        self.declare_parameter("autostart", False)
        self.declare_parameter("tick_hz", 10.0)
        self.declare_parameter("journal_dir", "/home/ros2_ws/log/rehearsal")
        # Relance après kill : au plus tôt min (> respawn_delay du launch, 5 s),
        # au plus tard max — ensuite la relance EXPIRE et le journal le dit.
        self.declare_parameter("reenable_min_delay_s", 6.0)
        self.declare_parameter("reenable_max_delay_s", 30.0)

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
        self.reenable = ReenablePolicy(
            min_delay_s=float(self.get_parameter("reenable_min_delay_s").value),
            max_delay_s=float(self.get_parameter("reenable_max_delay_s").value))
        self._paused = {}   # process -> pids gelés (pour l'abort / le finally)

        journal_dir = str(self.get_parameter("journal_dir").value)
        os.makedirs(journal_dir, exist_ok=True)
        # Un fichier par démarrage, horodatage à la ms + PID : aucun autre
        # écrivain ne peut s'y entrelacer (contrat JournalWriter).
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")[:-3]
        self.journal_path = os.path.join(journal_dir, f"{stamp}_{os.getpid()}_{self.scenario.name}.jsonl")
        self._journal_file = open(self.journal_path, "x", encoding="utf-8")
        self._journal = JournalWriter(self._journal_file)

        self.pub_heartbeat = self.create_publisher(StringTime, HEARTBEAT_TOPIC, 10)
        self.pub_relay = self.create_publisher(StringTime, RELAY_CMD_TOPIC, 10)
        self.pub_instruction = self.create_publisher(StringTime, INSTRUCTION_TOPIC, 10)
        self.pub_route = self.create_publisher(StringTime, ROUTE_CMD_TOPIC, 10)
        self.pub_speed = self.create_publisher(StringTime, ROUTE_SPEED_TOPIC, 10)
        self.create_subscription(StringTime, DIRECTOR_CMD_TOPIC, self._on_cmd, 10)
        # On ÉCOUTE le topic route (y compris nos propres ordres) : c'est ce qui
        # permet de ne jamais relancer la route contre un `off` de David.
        self.create_subscription(StringTime, ROUTE_CMD_TOPIC, self._on_route_cmd, 10)
        # État LATCHÉ publié par route_driver : la source de vérité pour armer
        # une relance (QoS TRANSIENT_LOCAL des DEUX côtés, sinon pas de latch).
        self.create_subscription(StringTime, ROUTE_STATE_TOPIC, self._on_route_state,
                                 QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_timer(0.2, lambda: self.pub_heartbeat.publish(StringTime(msg="1", time=0, anim=False)))
        self.create_timer(1.0 / float(self.get_parameter("tick_hz").value), self._tick)

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
        self.get_logger().info(f"{type_} {json.dumps(payload, ensure_ascii=False)[:160]}")
        try:
            self._journal.append(make_event(_mono_ms(), "director", type_, payload))
        except OSError as e:
            # Disque plein, fichier disparu : le journal est perdu, PAS le
            # régisseur (il doit rester vivant pour révoquer ses pannes).
            self.get_logger().error(f"journal inécrivable : {e}")

    # --- commandes ----------------------------------------------------------
    def _on_cmd(self, msg: StringTime):
        cmd = msg.msg.strip().strip('"')
        if cmd == "start":
            self._start()
        elif cmd in ("stop", "abort"):
            self._abort(cmd)
        else:
            self.get_logger().warning(f"rehearsal/cmd ignoré : {msg.msg!r}")

    def _start(self):
        if self.director.started:
            self.get_logger().warning("scénario déjà démarré")
            return
        self.director.start(time.monotonic())
        self.log("scenario_start", {"name": self.scenario.name, "seed": self.scenario.seed})

    def _on_route_state(self, msg: StringTime):
        confirmed = self.reenable.note_state(msg.msg.strip().strip('"'), time.monotonic())
        if confirmed:
            # Journalisé SEULEMENT sur confirmation par l'état latché.
            self.log("route_reenable", {"after_kill": confirmed})

    def _on_route_cmd(self, msg: StringTime):
        self.reenable.note_route_cmd(msg.msg.strip().strip('"'))

    def _abort(self, reason: str):
        """Tout révoquer, en une fois : pannes actives, relances armées,
        processus gelés (ceinture : le gardien détaché fera aussi SIGCONT)."""
        self._execute(self.director.abort(time.monotonic()))
        dropped = self.reenable.abort()
        for proc in list(self._paused):
            self._resume(proc)
        self.log("scenario_abort", {"cmd": reason, "reenable_dropped": dropped})

    def _resume(self, proc: str):
        try:
            apply("resume", proc)
        except (ProcessFaultError, OSError) as e:
            self.get_logger().error(f"resume {proc} : {e}")
        self._paused.pop(proc, None)

    def _tick(self):
        now = time.monotonic()
        try:
            self._execute(self.director.tick(now))
        except Exception as e:   # un timer qui lève tue le node : jamais ici
            self.get_logger().error(f"tick : {e!r}")
        # Relance après kill : seulement quand route_driver est REVENU et ABONNÉ
        # à `route` (sinon le « on » partirait dans le vide, et le journal mentirait).
        ready = self.pub_route.get_subscription_count() > 0 and bool(find_pids("route_driver"))
        send, expired = self.reenable.due(now, ready)
        if send:
            # Ré-envoyé chaque retry_s jusqu'à confirmation par route_state.
            self.pub_route.publish(StringTime(msg="on", time=0, anim=False))
            self.get_logger().info(f"relance route : « on » envoyé {self.reenable.pending()}")
        if expired:
            self.log("route_reenable_expired", {"after_kill": expired})

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
            except Exception as e:   # ProcessFaultError, RuntimeError, OSError (pgrep absent, PID…)
                self.log("fault_error", dict(payload, error=repr(e)))
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
            if kind == "start":
                # Gardien détaché : SIGCONT après la durée même si le régisseur meurt.
                pids = pause_bounded(p["process"], f.duration_s)
                if not pids:
                    raise RuntimeError(f"aucun processus « {p['process']} » à mettre en pause")
                self._paused[p["process"]] = pids
            else:
                self._resume(p["process"])
        elif f.type == "kill":
            if kind == "start":
                pids = apply("kill", p["process"])
                if not pids:
                    raise RuntimeError(f"aucun processus « {p['process']} » à tuer")
                if p.get("reenable", True) and not self.reenable.arm(f.id, time.monotonic()):
                    self.log("route_reenable_skipped", {"after_kill": f.id, "reason": "route était OFF"})
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
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error(e, exc_info=True)
    finally:
        if node is not None:
            # Ctrl-C ou crash : on révoque tout avant de partir (ceinture ; le
            # gardien détaché et les chiens de garde des relais sont les bretelles).
            try:
                node._abort("shutdown")
            except Exception as e:
                logging.error(e, exc_info=True)
            node.destroy_node()
        # SIGTERM (kill du régisseur, arrêt du launch) a souvent DÉJÀ fermé le
        # contexte : un second shutdown lève et sort en code 1 (vécu 08/10).
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
