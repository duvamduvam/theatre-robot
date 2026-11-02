#!/usr/bin/env python3
"""Node `jeu_node` — le sélecteur de jeu de Didier (lot A1), I/O ROS SEULEMENT.

SIM-ONLY : refuse de démarrer hors ROS_DOMAIN_ID=43 (garde-fou de
robot_rehearsal, IMPORTÉ — son message dit « robot_rehearsal refuse de
démarrer », c'est connu et assumé : une seule définition du garde-fou).
Le refus a lieu AVANT rclpy.init : rien n'est jamais créé sur le domaine 42.

Lit   : vision/person_box (perception scriptée en A1), rehearsal/poi_event,
        rehearsal/chat_move (la BOUCHE : ses demandes deviennent des intentions,
        son « stop » est relayé sans arbitrage), jeu/console (page scène),
        chat_situation, chat_transcript (parole entendue), mission_state (latché), route_state et route_state_cause (latchés),
        route_goto_result, animation_state (latché), rehearsal/objects (latché),
        /ground_truth/odom (SIM-ONLY : orienter le regard d'une lubie vers
        l'objet ; A2 le remplacera par la perception).
Écrit : jeu/chat_move (-> régisseur, remappé par rehearsal.launch.py jeu:=true),
        animation (nom de séquence), look (« regarder », gaze_follower),
        jeu/intention (latché, republié toutes les 0,5 s), jeu/journal (+ JSONL).

SÉCURITÉ : AUCUN éditeur de Twist ici (gravé par test_contrat_node.py). Les
roues ne bougent que par le régisseur, qui arbitre, puis route_driver.
Lancement : par rehearsal.launch.py jeu:=true (respawn), jamais à part : le remap
de la bouche n'y est actif QUE s'il lance aussi ce node (revue A1, bloquant 2).
Répertoire ou réglages illisibles -> MODE DÉGRADÉ (relais.RelaisSeul) : relais
stop/go seul, journal `degrade`.
"""
import json
import math
import os
import time

# Garde-fou AVANT tout import rclpy à effet : check_domain est pur.
from robot_rehearsal.contracts import (CHAT_MOVE_TOPIC, OBJECTS_TOPIC, ODOM_TOPIC, POI_EVENT_TOPIC,
                                       ROUTE_GOTO_RESULT_TOPIC, ROUTE_STATE_CAUSE_TOPIC, ROUTE_STATE_TOPIC,
                                       check_domain)
from theatre_contrats import stringtime, topics

from didier_jeu.journal import Journal, marquer_sans_pourquoi
from didier_jeu.reglages import charger_reglages
from didier_jeu.repertoire import candidates, charger_deplacements, par_emploi
from didier_jeu.relais import RelaisSeul
from didier_jeu.selecteur import Selecteur

# « regarder » (lot M2) : littéral gravé avec gaze_follower_node.LOOK_TOPIC
# (test_contrat_node.py le relit dans le vrai fichier).
LOOK_TOPIC = "look"
# Boucle de réflexion (dépôt vision, vision/ai/reflection_contract.py) :
# SITUATION_TOPIC / MISSION_STATE_TOPIC, littéraux gravés en test.
SITUATION_TOPIC = "chat_situation"
MISSION_STATE_TOPIC = "mission_state"
# Ce que Didier a COMPRIS (chat_node, « Flow », docs/interfaces.md) : JSON
# {"role": "david"|"didier", "text", "t_ms"} ; rôle david = parole entendue.
# Littéral gravé avec CHAT_TRANSCRIPT_TOPIC de chat_node (test_contrat_node.py).
TRANSCRIPT_TOPIC = "chat_transcript"
# Republication de l'intention latchée (porte T6 : jamais muette plus de 1 s).
# 0,5 s et pas 1 s : le tick (0,1 s) ferait des écarts de 1,0 à 1,1 s, plus le
# transport DDS — la porte se mesure côté abonné.
INTENTION_PERIODE_S = 0.5


def _share(*parts):
    from ament_index_python.packages import get_package_share_directory
    return os.path.join(get_package_share_directory("didier_jeu"), *parts)


def main(args=None):
    check_domain(os.environ)   # refus hors domaine 43, AVANT rclpy.init

    import rclpy
    from geometry_msgs.msg import PointStamped
    from nav_msgs.msg import Odometry
    from rclpy.node import Node
    from robot_interfaces.msg import StringTime
    from theatre_contrats import qos

    class JeuNode(Node):
        def __init__(self):
            super().__init__("jeu_node")
            self.declare_parameter("reglages_file", _share("config", "reglages.yaml"))
            self.declare_parameter("deplacements_file", _share("config", "deplacements.yaml"))
            self.declare_parameter("sequences_dir", "/home/ros2_ws/json/sequences")
            self.declare_parameter("journal_dir", "/home/ros2_ws/log/jeu")
            p = lambda n: self.get_parameter(n).value  # noqa: E731
            self.journal = None
            self._compteur = {"sans_pourquoi": 0}   # lignes sans pourquoi (bugs), comptées
            try:
                self.journal = Journal(p("journal_dir"))
                self.get_logger().info(f"journal : {self.journal.chemin}")
            except OSError as e:   # sans journal, le jeu (et surtout le relais) vit quand même
                self.get_logger().error(f"journal impossible : {e!r}")
            tick_s = 0.1
            try:
                self.reglages = charger_reglages(p("reglages_file"))
                tick_s = self.reglages.get("tick_s")
                pools, sans_emploi, doublons = par_emploi(candidates(p("sequences_dir")),
                                                          self.reglages.get("emplois"))
                self.sel = Selecteur(self.reglages, pools, charger_deplacements(p("deplacements_file")))
                demarrage = {"pourquoi": "le sélecteur de jeu démarre (simulation seulement, domaine 43)",
                             "repertoire": {k: [s.nom for s in v] for k, v in pools.items()},
                             "sans_emploi": sans_emploi, "doublons_sans_emploi": doublons,
                             "superviseur": self.reglages.get("superviseur.mode")}
            except Exception as e:  # noqa: BLE001 — répertoire, réglages, vocabulaire illisibles
                # MODE DÉGRADÉ (revue A1, bloquant 2) : avec jeu:=true le régisseur
                # n'écoute plus la bouche ; sans ce relais, son « stop » serait perdu.
                self.get_logger().error(f"MODE DÉGRADÉ, relais stop/go seul : {e!r}")
                self.sel = RelaisSeul(repr(e))
                demarrage = None

            self.pub_move = self.create_publisher(StringTime, topics.JEU_CHAT_MOVE, 10)
            self.pub_anim = self.create_publisher(StringTime, topics.ANIMATION, 10)
            self.pub_look = self.create_publisher(StringTime, LOOK_TOPIC, 10)
            self.pub_intention = self.create_publisher(StringTime, topics.JEU_INTENTION, qos.latched())
            self.pub_journal = self.create_publisher(StringTime, topics.JEU_JOURNAL, 10)

            if demarrage is not None:
                self._journaliser("demarrage", demarrage)

            self.create_subscription(PointStamped, topics.VISION_PERSON_BOX, self._on_box, 10)
            self.create_subscription(StringTime, POI_EVENT_TOPIC, self._json(self.sel.sur_poi_event), 10)
            self.create_subscription(StringTime, CHAT_MOVE_TOPIC, self._json(self.sel.sur_chat_move_bouche), 10)
            self.create_subscription(StringTime, topics.JEU_CONSOLE, self._json(self.sel.sur_console), 10)
            self.create_subscription(StringTime, SITUATION_TOPIC, self._on_situation, 10)
            self.create_subscription(StringTime, TRANSCRIPT_TOPIC, self._on_transcript, 10)
            self.create_subscription(StringTime, MISSION_STATE_TOPIC, self._json(self.sel.sur_mission),
                                     qos.latched())
            self.create_subscription(StringTime, ROUTE_STATE_TOPIC, self._on_route_state, qos.latched())
            # Cause latchée de l'état de route : « cmd » = Route OFF par David.
            self.create_subscription(StringTime, ROUTE_STATE_CAUSE_TOPIC, self._json(self.sel.sur_route_cause),
                                     qos.latched())
            self.create_subscription(StringTime, ROUTE_GOTO_RESULT_TOPIC, self._json(self.sel.sur_goto_result), 10)
            self.create_subscription(StringTime, topics.ANIMATION_STATE, self._json(self.sel.sur_animation_state),
                                     qos.latched())
            self.create_subscription(StringTime, OBJECTS_TOPIC, self._on_objects, qos.latched())
            self.create_subscription(Odometry, ODOM_TOPIC, self._on_odom, 10)
            self._t_intention = 0.0
            self.create_timer(tick_s, self._tick)
            self._vider()

        # --- entrées ------------------------------------------------------
        def _json(self, handler):
            """Callback StringTime -> handler(valeur JSON ou brute, now). Un
            callback qui lève tuerait le node : jamais ici."""
            def cb(msg):
                try:
                    handler(stringtime.decode_or_raw(msg.msg.strip()), time.monotonic())
                except Exception as e:  # noqa: BLE001
                    self.get_logger().error(f"{handler.__name__} {msg.msg!r} : {e!r}")
                self._vider()
            return cb

        def _on_box(self, msg):
            p = msg.point
            try:
                if all(math.isfinite(v) for v in (p.x, p.y, p.z)):
                    self.sel.sur_person_box(p.x, p.y, p.z, time.monotonic())
            except Exception as e:  # noqa: BLE001
                self.get_logger().error(f"person_box : {e!r}")
            self._vider()

        def _on_situation(self, msg):
            v = stringtime.decode_or_raw(msg.msg)
            texte = v.get("text") if isinstance(v, dict) else None
            self.sel.sur_situation(texte, time.monotonic())

        def _on_transcript(self, msg):
            v = stringtime.decode_or_raw(msg.msg)
            if isinstance(v, dict) and v.get("role") == "david":
                self.sel.sur_parole(v.get("text", ""), time.monotonic())
                self._vider()

        def _on_route_state(self, msg):
            # Contrat route_driver : payload BRUT (on/off/goto/arrived), JSON toléré.
            v = stringtime.decode_or_raw(msg.msg.strip())
            self.sel.sur_route_state(v if isinstance(v, str) else msg.msg.strip(), time.monotonic())

        def _on_objects(self, msg):
            try:
                self.sel.sur_objets(json.loads(msg.msg))
            except (ValueError, TypeError) as e:
                self.get_logger().warning(f"rehearsal/objects illisible : {e!r}")

        def _on_odom(self, msg):
            pose = msg.pose.pose
            q = pose.orientation
            cap = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            self.sel.sur_pose(pose.position.x, pose.position.y, cap)

        # --- tick et sorties ----------------------------------------------
        def _tick(self):
            now = time.monotonic()
            try:
                self.sel.tick(now)
            except Exception as e:  # noqa: BLE001
                self.get_logger().error(f"tick : {e!r}")
            if now - self._t_intention >= INTENTION_PERIODE_S:
                self.sel.sorties.append(("intention", self.sel.intention(now)))
            self._vider()

        def _vider(self):
            for sortie in self.sel.vider_sorties():
                kind = sortie[0]
                if kind == "chat_move":
                    self.pub_move.publish(StringTime(msg=json.dumps(sortie[1]), time=0, anim=False))
                elif kind == "animation":
                    self.pub_anim.publish(StringTime(msg=json.dumps(sortie[1]), time=0, anim=False))
                elif kind == "look":
                    self.pub_look.publish(StringTime(msg=json.dumps(sortie[1]), time=0, anim=False))
                elif kind == "intention":
                    self._t_intention = time.monotonic()
                    self.pub_intention.publish(StringTime(msg=json.dumps(sortie[1], ensure_ascii=False),
                                                          time=0, anim=False))
                elif kind == "journal":
                    self._journaliser(sortie[1], sortie[2])

        def _journaliser(self, type_, payload):
            payload = marquer_sans_pourquoi(payload, self._compteur)
            if self.journal is None:
                self.get_logger().info(f"{type_} {str(payload.get('pourquoi', ''))[:120]}")
                return
            try:
                ligne = self.journal.ecrire(int(time.monotonic() * 1000), type_, payload)
            except (OSError, ValueError) as e:
                # Disque plein : le journal est perdu, PAS le jeu.
                self.get_logger().error(f"journal : {e!r}")
                return
            self.get_logger().info(f"{type_} {payload.get('pourquoi', '')[:120]}")
            self.pub_journal.publish(StringTime(msg=ligne, time=0, anim=False))

    rclpy.init(args=args)
    node = JeuNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.journal is not None:
            node.journal.fermer()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
