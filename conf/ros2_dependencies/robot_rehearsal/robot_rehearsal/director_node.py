#!/usr/bin/env python3
"""Node `director` : le RÉGISSEUR de pannes (SIM-ONLY, canal technique).

Charge un scénario YAML (validé, expansé avec sa graine), attend « start »
sur rehearsal/cmd (autostart false par défaut), puis exécute la timeline :
  relay       -> ordre au relais (rehearsal/relay_cmd), révoqué à la fin ;
  pause       -> SIGSTOP du processus (liste blanche), SIGCONT à la fin ;
  kill        -> SIGTERM de route_driver (le launch le respawne), puis
                 « route on » après reenable_delay_s si demandé ;
  speed       -> route_speed = value, puis la vitesse EN VIGUEUR à la fin
                 (dernière consigne externe, sinon paramètre `speed`, sinon
                 restore du scénario) ;
  instruction -> publie le texte sur chat_instruction (canal joué, consommé
                 par chat_node) ; si durée > 0, "" à la fin (consigne levée) ;
  lubie       -> consigne sur chat_instruction (texte du scénario, sinon champ
                 `lubie` du POI dans l'itinéraire `route_file`) + route_speed 0
                 si stop ; à la fin "" + vitesse en vigueur. FERMÉE AU FADER :
                 une consigne route_speed externe qui s'écarte de plus de
                 EXTERNAL_SPEED_DELTA de la vitesse d'avant la lubie la termine
                 sur-le-champ, SANS rendre de vitesse (David vient de la fixer) ;
  chat        -> panne de conversation sur rehearsal/chat_fault, « pass » à la
                 fin (sauf phantom, ponctuel : rien à lever) ;
et JOURNALISE tout (robot.diagnostic.journal, JSONL) : la frise du débrief.
Les éléments `t: poi` partent sur l'« enter » du POI (rehearsal/poi_event) ;
un « enter » hors séance (avant START, après la fin) est journalisé
`poi_enter_ignored` et PAS mémorisé : START doit précéder `route on`.
« start » après la fin REJOUE la séance (même timeline, `scenario_reset`).
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
from collections import deque
from datetime import datetime

import rclpy
import yaml
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from robot_interfaces.msg import StringTime

from robot.diagnostic.journal import JournalWriter, make_event
from robot_rehearsal.contracts import (CHAT_FAULT_TOPIC, DIRECTOR_CMD_TOPIC,
                                       HEARTBEAT_TOPIC, INSTRUCTION_TOPIC, POI_EVENT_TOPIC,
                                       RELAY_CMD_TOPIC, ROUTE_CMD_TOPIC, ROUTE_SPEED_TOPIC,
                                       ROUTE_STATE_TOPIC, check_domain)
from robot_rehearsal.director import (MESSAGE_TYPES, Director, ReenablePolicy, fader_moved, messages,
                                      speed_factor, speed_in_effect)
from robot_rehearsal.process_faults import ProcessFaultError, apply, find_pids, pause_bounded
from robot_rehearsal.route import RouteError, load_route
from robot_rehearsal.scenario import ScenarioError, load_scenario


def _mono_ms() -> int:
    return int(time.monotonic() * 1000)


class DirectorNode(Node):
    def __init__(self):
        check_domain(os.environ)   # refus hors domaine 43, AVANT tout effet
        super().__init__("director")
        self.declare_parameter("scenario_file", "")
        # MÊME itinéraire que route_driver : les noms de POI des déclencheurs
        # et le texte des lubies sans `text` y sont lus. Vide = aucun POI connu
        # (un scénario qui en référence est alors refusé au démarrage).
        self.declare_parameter("route_file", "")
        self.declare_parameter("seed", -1)           # -1 = graine du fichier
        # MÊME vitesse initiale que route_driver (même substitution du launch) :
        # la vitesse en vigueur tant qu'aucune consigne externe n'a été vue.
        self.declare_parameter("speed", 0.5)
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
        route_file = str(self.get_parameter("route_file").value)
        self._poi_lubie = {}   # nom de POI -> champ lubie de l'itinéraire
        if route_file:
            with open(route_file, encoding="utf-8") as f:
                try:
                    route = load_route(yaml.safe_load(f))
                except RouteError as e:
                    raise RuntimeError(f"itinéraire invalide ({route_file}) : {e}") from e
            self._poi_lubie = {p.name: p.lubie for p in route.pois}
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        seed = int(self.get_parameter("seed").value)
        try:
            # Refus AU DÉMARRAGE d'un POI inconnu ou d'une lubie sans texte —
            # pour tous les éléments, tirés ou non (sinon refus selon la graine).
            self.scenario = load_scenario(data, seed=None if seed < 0 else seed, pois=self._poi_lubie)
        except ScenarioError as e:
            raise RuntimeError(f"scénario invalide ({path}, itinéraire {route_file or 'aucun'}) : {e}") from e
        self.director = Director(self.scenario)
        self.reenable = ReenablePolicy(
            min_delay_s=float(self.get_parameter("reenable_min_delay_s").value),
            max_delay_s=float(self.get_parameter("reenable_max_delay_s").value))
        self._paused = {}   # process -> pids gelés (pour l'abort / le finally)
        # Vitesse de cheminement (route_speed), vue du régisseur :
        #  - _own_speed : textes que NOUS venons de publier ; un node reçoit ses
        #    propres publications, leur écho ne doit pas passer pour le fader.
        #    Bornée : un écho perdu ne laisse pas une file grossir sans fin ;
        #  - _external_speed : dernière consigne EXTERNE (fader, page), None
        #    tant qu'aucune n'a été vue ;
        #  - _speed_before_lubie : vitesse en vigueur au start d'une lubie
        #    stop=true (référence de la fermeture au fader), None hors lubie.
        self._initial_speed = speed_factor(self.get_parameter("speed").value)
        self._own_speed = deque(maxlen=16)
        self._external_speed = None
        self._speed_before_lubie = None

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
        self.pub_chat_fault = self.create_publisher(StringTime, CHAT_FAULT_TOPIC, 10)
        self.create_subscription(StringTime, DIRECTOR_CMD_TOPIC, self._on_cmd, 10)
        self.create_subscription(StringTime, POI_EVENT_TOPIC, self._on_poi_event, 10)
        # On ÉCOUTE le topic route (y compris nos propres ordres) : c'est ce qui
        # permet de ne jamais relancer la route contre un `off` de David.
        self.create_subscription(StringTime, ROUTE_CMD_TOPIC, self._on_route_cmd, 10)
        # On ÉCOUTE route_speed : la vitesse en vigueur (rendue à la fin d'un
        # speed / d'une lubie) et le geste de David qui ferme une lubie.
        self.create_subscription(StringTime, ROUTE_SPEED_TOPIC, self._on_route_speed, 10)
        # État LATCHÉ publié par route_driver : la source de vérité pour armer
        # une relance (QoS TRANSIENT_LOCAL des DEUX côtés, sinon pas de latch).
        self.create_subscription(StringTime, ROUTE_STATE_TOPIC, self._on_route_state,
                                 QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_timer(0.2, lambda: self.pub_heartbeat.publish(StringTime(msg="1", time=0, anim=False)))
        self.create_timer(1.0 / float(self.get_parameter("tick_hz").value), self._tick)

        # Les déclencheurs POI ont été tirés au CHARGEMENT (load_scenario) : le
        # journal dit ce qui a été tiré (timeline) et ce qui ne l'a pas été.
        self.log("scenario_loaded", {"name": self.scenario.name, "seed": self.scenario.seed,
                                     "duration_s": self.scenario.duration_s,
                                     "timeline": [{"id": f.id, "type": f.type, "t_s": f.t_s,
                                                   "trigger_poi": f.trigger_poi, "p": f.draw_p,
                                                   "duration_s": f.duration_s, "params": f.params}
                                                  for f in self.scenario.faults],
                                     "undrawn": list(self.scenario.undrawn)})
        self.get_logger().info(f"régisseur prêt : « {self.scenario.name} », graine {self.scenario.seed}, "
                               f"{len(self.scenario.faults)} pannes ({len(self.scenario.undrawn)} écartées "
                               f"au tirage), journal {self.journal_path}")
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
        if self.director.started and not self.director.ended:
            self.get_logger().warning("scénario déjà démarré")
            return
        if self.director.ended:
            # Séance finie (durée, stop, abort) : « start » la REJOUE — même
            # timeline (graine et tirages du chargement), ordonnanceur neuf.
            # Avant : ignoré avec un simple warning, le START semblait perdu.
            self.director = Director(self.scenario)
            self.log("scenario_reset", {"reason": "restart"})
        self.director.start(time.monotonic())
        self.log("scenario_start", {"name": self.scenario.name, "seed": self.scenario.seed})

    def _on_route_state(self, msg: StringTime):
        confirmed = self.reenable.note_state(msg.msg.strip().strip('"'), time.monotonic())
        if confirmed:
            # Journalisé SEULEMENT sur confirmation par l'état latché.
            self.log("route_reenable", {"after_kill": confirmed})

    def _on_route_cmd(self, msg: StringTime):
        self.reenable.note_route_cmd(msg.msg.strip().strip('"'))

    def _on_route_speed(self, msg: StringTime):
        """route_speed vu sur le topic. NOS publications (speed, lubie) sont
        reconnues à leur texte exact et ignorées — limite : une source externe
        qui publierait le MÊME texte pendant que notre écho est en vol serait
        prise pour lui. Les consignes EXTERNES (fader du boîtier, page scène)
        donnent la vitesse en vigueur et peuvent FERMER une lubie : le boîtier
        peut ré-émettre en continu sa position (jitter d'ADC compris), la page
        n'envoie qu'au changement — seul un écart > EXTERNAL_SPEED_DELTA de la
        vitesse d'avant la lubie est un geste de David."""
        if msg.msg in self._own_speed:
            self._own_speed.remove(msg.msg)
            return
        value = speed_factor(msg.msg)
        if value is None:
            return   # illisible : route_driver l'ignore aussi
        self._external_speed = value
        if self._speed_before_lubie is None or not fader_moved(value, self._speed_before_lubie):
            return
        try:
            self._execute(self.director.close_active("speed", time.monotonic(), only_type="lubie"),
                          closed_by="fader")
        except Exception as e:   # un callback qui lève tue le node : jamais ici
            self.get_logger().error(f"fermeture au fader : {e!r}")

    def _on_poi_event(self, msg: StringTime):
        """Contrat route_driver : JSON {"poi", "event": enter|exit, "distance"}.
        Tout est journalisé (la frise du débrief) ; seul « enter » déclenche."""
        try:
            ev = json.loads(msg.msg)
            poi, kind = str(ev["poi"]), ev["event"]
        except (ValueError, TypeError, KeyError) as e:
            self.get_logger().warning(f"poi_event illisible : {msg.msg!r} ({e!r})")
            return
        payload = {"poi": poi, "distance": ev.get("distance")}
        if kind == "enter":
            if not self.director.started or self.director.ended:
                # Hors séance, Director.trigger ne déclenche rien — et on ne
                # MÉMORISE pas l'enter (c'est au script / à la page d'envoyer
                # START avant `route on`). Mais le journal le DIT : sinon le
                # débrief ne saurait pas pourquoi la lubie n'est jamais partie.
                reason = "ended" if self.director.ended else "before_start"
                self.log("poi_enter_ignored", {"poi": poi, "reason": reason})
                return
            self.log("poi_enter", payload)
            try:
                self._execute(self.director.trigger(poi, time.monotonic()))
            except Exception as e:   # un callback qui lève tue le node : jamais ici
                self.get_logger().error(f"trigger {poi} : {e!r}")
        elif kind == "exit":
            self.log("poi_exit", payload)
        else:
            self.get_logger().warning(f"poi_event : événement inconnu {kind!r}")

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
    def _execute(self, actions, closed_by=None):
        """`closed_by` ("fader") : les stops viennent d'une fermeture par
        David — journalisés avec, et la vitesse n'est PAS rendue."""
        for a in actions:
            if a.kind == "end":
                self.log("scenario_end", {"status": self.director.status()})
                continue
            f = a.fault
            payload = {"id": f.id, "type": f.type, "params": f.params}
            if f.type == "lubie":
                # La consigne RÉSOLUE (params.text vaut null quand elle vient de l'itinéraire).
                payload["text"] = self._lubie_text(f)
            if a.kind == "skip":
                self.log("fault_skip", payload)
                continue
            if a.kind == "stop" and closed_by is not None:
                payload["closed_by"] = closed_by
            try:
                self._apply(a.kind, f, closed_by)
                self.log(f"fault_{a.kind}", payload)
            except Exception as e:   # ProcessFaultError, RuntimeError, OSError (pgrep absent, PID…)
                self.log("fault_error", dict(payload, error=repr(e)))
                if a.kind == "start":
                    # Jamais de fault_stop pour une panne jamais appliquée.
                    self.director.cancel(f.id, time.monotonic())

    def _apply(self, kind: str, f, closed_by=None):
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
            # Fin : la vitesse EN VIGUEUR (le fader de David), pas le restore figé.
            value = p["value"] if kind == "start" else self._speed_in_effect(p["restore"])
            self._publish(ROUTE_SPEED_TOPIC, json.dumps(value))
        elif f.type in MESSAGE_TYPES:
            # instruction / lubie / chat : messages calculés par la logique pure
            # (director.messages, gravée par test) — ici on publie, rien d'autre.
            text = self._lubie_text(f) if f.type == "lubie" else ""
            restore = in_effect = None
            if f.type == "lubie":
                # Vitesse en vigueur : rendue au stop, sauf fermeture AU FADER
                # (David vient de la fixer : la lui rendre l'écraserait).
                in_effect = self._speed_in_effect(p["restore"])
                restore = None if closed_by == "fader" else in_effect
            for topic, payload in messages(f, kind, text, restore_value=restore):
                self._publish(topic, payload)
            if f.type == "lubie" and p["stop"]:
                # Référence de la fermeture au fader : la vitesse d'AVANT notre
                # « 0 » ; posée APRÈS publication (un échec = pas de lubie active).
                self._speed_before_lubie = in_effect if kind == "start" else None

    def _publish(self, topic: str, payload: str) -> None:
        """Publie sur le publisher de SON topic ; route_speed est noté dans
        _own_speed AVANT publication (son écho revient par notre abonnement)."""
        pubs = {INSTRUCTION_TOPIC: self.pub_instruction, ROUTE_SPEED_TOPIC: self.pub_speed,
                CHAT_FAULT_TOPIC: self.pub_chat_fault}
        if topic == ROUTE_SPEED_TOPIC:
            self._own_speed.append(payload)
        pubs[topic].publish(StringTime(msg=payload, time=0, anim=False))

    def _speed_in_effect(self, fallback: float) -> float:
        return speed_in_effect(self._external_speed, self._initial_speed, fallback)

    def _lubie_text(self, f) -> str:
        """Texte du scénario, sinon champ `lubie` du POI (existence vérifiée au chargement)."""
        return f.params["text"] if f.params["text"] is not None else self._poi_lubie[f.params["poi"]]


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
