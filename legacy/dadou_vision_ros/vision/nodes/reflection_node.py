#!/usr/bin/env python3
"""Node 'reflection' : le metteur en scène intérieur de Didier (boucle 2).

QUOI : node FIN (I/O seulement). Écoute la conversation, la caméra, la
       perception, la route et les consignes ; décide (ReflectionScheduler)
       quand interroger un LLM AVEC réflexion ; en tire un tableau de
       situation (SITUATION_TOPIC, relu par chat_node à chaque réplique), un
       état de mission latché et, parfois, un tour de parole spontané
       (PROMPT_TOPIC). Toute la logique vit dans vision/ai/{mission,
       situation,reflection,reflection_policy}.py (testée sans ROS).
POURQUOI un node SÉPARÉ de chat_node (cf. dadou_robot_ros/docs/etude-niveaux-
       reflexion.md) : la parole (< 1 s au premier mot) ne doit JAMAIS
       attendre la réflexion (3-7 s) ; les deux ne se parlent que par des
       topics asynchrones (vision/ai/reflection_contract.py).
SÉCURITÉ : ce node ne publie JAMAIS sur cmd_vel* ni sur un topic de
       mouvement. Réflexion morte = Didier parle moins bien (le tableau expire
       côté parole en SITUATION_TTL_S), rien de plus.
THREADS : les appels LLM tournent dans UN thread de travail unique, jamais
       dans un callback rclpy (ils bloqueraient les abonnements 5-7 s). L'état
       partagé (tableau, mission, ordonnanceur, transcript) est protégé par
       self._lock ; aucun appel réseau ni publication ne s'exécute sous verrou.
"""
import collections
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from robot_interfaces.msg import StringTime
from sensor_msgs.msg import CompressedImage

from vision.ai import reflection, reflection_contract as contract
from vision.ai.mission import MissionState
from vision.ai.reflection_policy import DeepRequests, Flights, ReflectionScheduler, SpontaneousPolicy
from vision.ai.situation import (SituationBoard, decode_poi_event, decode_speed,
                                 decode_transcript_line, persona_changed)
from vision.ai.stage import decode_text_payload
from vision.tracking.camera_source import (
    SOURCE_WEBCAM, camera_is_partner_effective, decode_camera_source)
from vision.vision_config import camera_is_partner_from_env, chat_env_overrides, config

# Topics consommés. Les noms `chat_*`, `rehearsal/poi_event`, `route_state`,
# `route_speed`, `/vision/person_box` et la vidéo sont des CONTRATS d'autres
# nodes (chat_node, régisseur, route_driver, person_tracker) : ne pas les
# renommer ici.
TRANSCRIPT_TOPIC = "chat_transcript"
POI_EVENT_TOPIC = "rehearsal/poi_event"
ROUTE_STATE_TOPIC = "route_state"
# Facteur de vitesse 0..1 (json.dumps(float)), publié en VOLATILE par le
# régisseur (dadou_robot_ros robot_rehearsal) : un node démarré après la
# dernière consigne ne connaît pas la vitesse — inconnue = considéré à
# l'arrêt (cf. SituationBoard.moving).
ROUTE_SPEED_TOPIC = "route_speed"
# COMMANDE de route (dadou_robot_ros robot_rehearsal, ROUTE_CMD_TOPIC) : lue
# SEULEMENT, pour son "restart" (nouvelle traversée) qui remet à neuf la
# mémoire des objets commentés en marche. Ce node n'y publie JAMAIS.
ROUTE_CMD_TOPIC = "route"
PERSON_BOX_TOPIC = "/vision/person_box"
VIDEO_TOPIC = "camera/image_raw/compressed"
INSTRUCTION_TOPIC = "chat_instruction"
CHAT_STATE_TOPIC = "chat_state"
# Personnalité ACTIVE de Didier, publiée par chat_node en TRANSIENT_LOCAL (msg
# brut) : l'abonnement DOIT être latché lui aussi, sinon rien n'arrive.
PERSONA_STATE_TOPIC = "persona_state"
# Source d'images de la perception (person_tracker, TRANSIENT_LOCAL) : la caméra
# Gazebo ne filme pas le partenaire devant l'écran.
CAMERA_SOURCE_STATE_TOPIC = "camera_source_state"

TICK_PERIOD_S = 0.5
TRANSCRIPT_KEEP = 30
PERSON_REAPPEAR_S = 5.0     # absence minimale pour parler de « réapparition »
IMAGE_MAX_AGE_S = 3.0       # au-delà, la trame est trop vieille pour être jointe

LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)


class ReflectionStartupError(RuntimeError):
    """Démarrage impossible (déjà loggé) ; main() sort proprement, code 1."""


class ReflectionNode(Node):
    def __init__(self):
        super().__init__("reflection")

        # Même lecture que chat_node : le partenaire vient de CHAT_PARTENAIRE
        # via chat_env_overrides (valeur invalide = échec explicite).
        try:
            overrides, _ = chat_env_overrides()
        except ValueError as exc:
            self.get_logger().error(f"Variable d'environnement invalide : {exc}")
            raise ReflectionStartupError("variable d'environnement invalide") from exc
        config.update(overrides)

        self.declare_parameter("destination", config["reflection_destination"])
        # Un paramètre ROS ne peut pas valoir None : "" = pas de partenaire connu.
        self.declare_parameter("partner", config["chat_partner"] or "")
        self._destination = self.get_parameter("destination").value
        self._partner = self.get_parameter("partner").value or None
        # Calculé UNE fois : la sim (domaine 43) filme le partenaire, pas un passant.
        self._camera_is_partner = camera_is_partner_from_env(os.environ, self._partner)
        # Source courante : « webcam » tant que rien n'est reçu (défaut du tracker).
        self._camera_source = SOURCE_WEBCAM

        self._lock = threading.Lock()
        self._board = SituationBoard()
        self._mission = MissionState(self._destination)
        self._scheduler = ReflectionScheduler()
        self._policy = SpontaneousPolicy()
        self._transcript = collections.deque(maxlen=TRANSCRIPT_KEEP)
        self._instruction = None
        self._deep = DeepRequests()    # demande "reflechir" + son nouvel essai unique
        self._persona = None           # inconnue tant que persona_state n'est pas reçu
        self._chat_state = ""          # inconnu tant que chat_node n'a rien publié
        self._image = None             # (octets JPEG, heure d'arrivée)
        self._last_person_s = None
        self._last_transcript_s = None
        self._last_spontaneous_s = None
        self._pending_pois = []        # objets ENTRÉS depuis le dernier job, dans l'ordre
        # Au plus un ordinaire + un profond en vol (cf. reflection_policy.Flights).
        self._flights = Flights()
        self._last_published = None    # (texte, heure) du dernier tableau publié

        self._reflector = reflection.Reflector(
            model=config["reflection_model"], base_url=config["chat_llm_base_url"],
            extra_body=config["reflection_extra_body"],
            max_tokens=config["reflection_max_tokens"])
        # 2 fils : une demande profonde part pendant un ordinaire en vol (01/11).
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="reflection")

        self._situation_pub = self.create_publisher(StringTime, contract.SITUATION_TOPIC, 10)
        self._prompt_pub = self.create_publisher(StringTime, contract.PROMPT_TOPIC, 10)
        self._mission_pub = self.create_publisher(StringTime, contract.MISSION_STATE_TOPIC, LATCHED)

        self.create_subscription(StringTime, TRANSCRIPT_TOPIC, self._on_transcript, 10)
        self.create_subscription(StringTime, POI_EVENT_TOPIC, self._on_poi_event, 10)
        self.create_subscription(StringTime, ROUTE_STATE_TOPIC, self._on_route_state, LATCHED)
        self.create_subscription(StringTime, ROUTE_SPEED_TOPIC, self._on_route_speed, 10)
        self.create_subscription(StringTime, ROUTE_CMD_TOPIC, self._on_route_cmd, 10)
        self.create_subscription(PointStamped, PERSON_BOX_TOPIC, self._on_person_box, 10)
        # BEST_EFFORT : compatible avec un éditeur fiable ou non, et une trame
        # perdue n'a aucune importance (on ne garde que la dernière).
        self.create_subscription(
            CompressedImage, VIDEO_TOPIC, self._on_image,
            QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))
        self.create_subscription(StringTime, INSTRUCTION_TOPIC, self._on_instruction, 10)
        self.create_subscription(StringTime, CHAT_STATE_TOPIC, self._on_chat_state, LATCHED)
        self.create_subscription(StringTime, PERSONA_STATE_TOPIC, self._on_persona_state, LATCHED)
        self.create_subscription(
            StringTime, CAMERA_SOURCE_STATE_TOPIC, self._on_camera_source_state, LATCHED)
        self.create_subscription(StringTime, contract.REFLECT_TOPIC, self._on_reflect, 10)

        self._publish_mission()
        self.create_timer(TICK_PERIOD_S, self._tick)
        self.get_logger().info(
            f"reflection prêt : destination={self._destination!r}, partenaire={self._partner!r}, "
            f"caméra=partenaire:{self._camera_is_partner}, "
            f"modèle={config['reflection_model']}, images={config['reflection_use_image']}")

    # -- abonnements (rapides : aucun appel réseau) ---------------------------

    def _on_transcript(self, msg):
        line = decode_transcript_line(msg.msg)
        if line is None:
            self.get_logger().warning(f"chat_transcript refusé : {msg.msg!r}")
            return
        now = time.monotonic()
        with self._lock:
            self._transcript.append(line)
            self._last_transcript_s = now
            self._scheduler.notify(line["role"], now)

    def _on_poi_event(self, msg):
        decoded = decode_poi_event(msg.msg)
        if decoded is None:
            self.get_logger().warning(f"poi_event refusé : {msg.msg!r}")
            return
        poi, event = decoded
        now = time.monotonic()
        with self._lock:
            self._board.set_poi(poi, event, now)
            # Seul l'« enter » est un événement de scène ; l'« exit » met le
            # tableau à jour sans payer un appel.
            if event == "enter":
                self._scheduler.notify("poi", now)
                self._pending_pois.append(poi)

    def _on_route_cmd(self, msg):
        # Même tolérance que route_driver._decode (JSON ou brut) ; "on"/"off"
        # passent par route_state, seul "restart" intéresse la réflexion.
        if decode_text_payload(msg.msg) != "restart":
            return
        with self._lock:
            self._policy.reset_remarks()
        self.get_logger().info("route restart : objets commentés en marche oubliés")

    def _on_route_state(self, msg):
        with self._lock:
            self._board.set_route(decode_text_payload(msg.msg))

    def _on_route_speed(self, msg):
        speed = decode_speed(msg.msg)
        if speed is None:
            # Même règle que route_driver : payload illisible ignoré, la
            # vitesse connue reste en vigueur.
            self.get_logger().warning(f"route_speed refusé : {msg.msg!r}")
            return
        with self._lock:
            self._board.set_speed(speed)

    def _on_person_box(self, msg):
        now = time.monotonic()
        with self._lock:
            self._board.update_person(msg.point.x, msg.point.y, msg.point.z, now)
            if self._last_person_s is None or now - self._last_person_s >= PERSON_REAPPEAR_S:
                self._scheduler.notify("person_appeared", now)
            self._last_person_s = now
            self._scheduler.person_seen(now)

    def _on_image(self, msg):
        with self._lock:
            self._image = (bytes(msg.data), time.monotonic())

    def _on_instruction(self, msg):
        text = decode_text_payload(msg.msg)
        with self._lock:
            self._instruction = text or None   # "" = consigne levée
            if text:
                self._scheduler.notify("instruction", time.monotonic())

    def _on_chat_state(self, msg):
        with self._lock:
            # chat_node publie l'état BRUT ("listening"), mais un `ros2 topic
            # pub` de débogage envoie souvent du JSON ("\"listening\"") : même
            # tolérance que partout ailleurs (piège vécu au banc du 23/10).
            self._chat_state = decode_text_payload(msg.msg)

    def _on_camera_source_state(self, msg):
        source = decode_camera_source(msg.msg)
        if source is None:
            self.get_logger().warning(f"camera_source_state inconnu : {msg.msg!r}")
            return
        self._camera_source = source  # affectation atomique, lue par le thread de travail

    def _on_persona_state(self, msg):
        """Changement de personnage : l'ancien transcript et ce que la
        réflexion en avait tiré (« compris », direction) sont réinjectés à
        chaque réplique -- sans purge, le nouveau personnage joue dans le
        sillage de l'ancien (vécu en sim le 2026-10-31). Le PREMIER message
        (latché reçu au démarrage) n'est pas un changement : on l'adopte sans
        rien vider. Perception, mission et consigne du régisseur ne dépendent
        pas du personnage : conservées."""
        name = decode_text_payload(msg.msg)
        with self._lock:
            changed = persona_changed(self._persona, name)
            if name:
                previous, self._persona = self._persona, name
            if changed:
                self._transcript.clear()
                self._board.reset_understanding()
        if changed:
            self.get_logger().info(
                f"persona {previous!r} -> {name!r} : transcript et direction de jeu effacés")

    def _on_reflect(self, msg):
        demande = contract.decode_reflect(msg.msg)
        if demande is None:
            self.get_logger().warning(f"demande de réflexion refusée : {msg.msg!r}")
            return
        with self._lock:
            self._deep.submit(demande)
            self._scheduler.notify("reflect", time.monotonic())
        self.get_logger().info(f"demande de réflexion reçue : {demande!r}")

    # -- cadence ---------------------------------------------------------------

    def _tick(self):
        now = time.monotonic()
        job = inputs = None
        with self._lock:
            job = self._scheduler.next_job(now, self._flights.any, self._flights.deep)
            if job is not None:
                token = self._flights.start(job)
                inputs = self._snapshot(now, job)
                inputs["flight_token"] = token
            text = self._board.compose(now, self._mission.summary())
            last = self._last_published
            due = (last is None and text != "") or (
                last is not None and (text != last[0] or now - last[1] >= contract.SITUATION_REPUBLISH_S))
            if due:
                self._last_published = (text, now)
        if due:
            self._situation_pub.publish(StringTime(
                msg=contract.encode_situation(text, int(time.time() * 1000)), time=0, anim=False))
        if job is not None:
            self._executor.submit(self._run_job, job, inputs)

    def _snapshot(self, now, job):
        """Entrées de l'appel LLM, copiées SOUS verrou (appelé verrou pris)."""
        image = None
        used_image = False
        if config["reflection_use_image"] and self._image is not None \
                and now - self._image[1] <= IMAGE_MAX_AGE_S:
            image, used_image = self._image[0], True
        demande, demande_retry = self._deep.take() if job.deep else (None, False)
        # Remarque en marche (décision de David du 31/10) : l'objet le plus
        # récemment ENTRÉ et jamais commenté, si Didier roule. Le job consomme
        # tous les POI en attente, comme l'ordonnanceur consomme ses
        # événements (il voit la perception entière). Profond : sans objet,
        # il répond à une demande.
        pois, self._pending_pois = self._pending_pois, []
        passing_poi = None
        if not job.deep and self._board.moving():
            passing_poi = next(
                (p for p in reversed(pois) if not self._policy.already_remarked(p)), None)
        return dict(
            transcript=list(self._transcript), perception=self._board.perception_text(now),
            mission_summary=self._mission.summary(), instruction=self._instruction,
            demande=demande, demande_retry=demande_retry, image=image, used_image=used_image,
            persona=self._persona, passing_poi=passing_poi)

    # -- thread de travail -----------------------------------------------------

    def _run_job(self, job, inputs):
        started = time.monotonic()
        try:
            messages = reflection.build_messages(
                inputs["transcript"], inputs["perception"], inputs["mission_summary"],
                inputs["instruction"], inputs["demande"], inputs["image"],
                partner=self._partner, destination=self._destination,
                persona=inputs["persona"], passing_poi=inputs["passing_poi"],
                camera_is_partner=camera_is_partner_effective(
                    self._camera_is_partner, self._camera_source))
            if job.deep:
                result = self._reflector.reflect(
                    messages, model=config["reflection_deep_model"],
                    extra_body=config["reflection_deep_extra_body"])
            else:
                result = self._reflector.reflect(messages)
            duration = time.monotonic() - started
            if result is None:
                self.get_logger().warning(
                    f"réflexion sans résultat ({job.reason}, {duration:.1f} s)")
                self._deep_failed(job, inputs)
                return
            self._apply_result(job, inputs, result, duration)
        except Exception as exc:  # noqa: BLE001 - le spectacle continue quoi qu'il arrive
            self.get_logger().error(f"réflexion en échec ({job.reason}) : {exc!r}")
            self._deep_failed(job, inputs)
        finally:
            with self._lock:
                self._flights.finish(job)

    def _deep_failed(self, job, inputs):
        """Job profond en échec (exception ou résultat None) : demande remise
        en attente UNE fois (revue adversariale du 23/10, I5 — Didier a promis
        de revenir avec la réponse, cf. DeepRequests), puis abandonnée."""
        demande = inputs["demande"]
        if not job.deep or demande is None:
            return
        with self._lock:
            requeued = self._deep.failed(demande, inputs["demande_retry"])
            if requeued:
                self._scheduler.notify("reflect", time.monotonic())
        if requeued:
            self.get_logger().warning(f"demande de réflexion remise en attente : {demande!r}")
        else:
            self.get_logger().warning(f"demande de réflexion abandonnée : {demande!r}")

    def _apply_result(self, job, inputs, result, duration):
        now = time.monotonic()
        with self._lock:
            superseded = self._flights.superseded(job, inputs["flight_token"])
        if superseded:
            self.get_logger().info(
                f"réflexion ({job.reason}) devancée par une demande profonde : "
                f"résultat jeté ({duration:.1f} s)")
            return
        with self._lock:
            # Appel parti sous l'ANCIENNE persona et revenu après le changement :
            # son « compris »/sa direction décrivent l'ancien personnage, on les jette.
            if inputs["persona"] == self._persona:
                self._board.set_reflection(result.situation, result.direction, now)
            changes = self._mission.apply(result.mission_update)
            text = result.direction or result.situation
            # `text` D'ABORD : allow() consomme l'objet croisé quand il accorde
            # un tour en marche — un résultat sans texte ne doit pas le brûler.
            speak = bool(text) and self._policy.allow(
                result.parler, job.deep, self._chat_state, now,
                self._last_transcript_s, self._last_spontaneous_s,
                moving=self._board.moving(), passing_poi=inputs["passing_poi"])
            if speak:
                self._last_spontaneous_s = now
        for change in changes:
            self.get_logger().info(f"mission : {change}")
        if changes:
            self._publish_mission()
        self.get_logger().info(
            f"réflexion ({job.reason}) : {'profonde' if job.deep else 'ordinaire'}, "
            f"{duration:.1f} s, image={'oui' if inputs['used_image'] else 'non'}, "
            f"objet croisé={inputs['passing_poi']!r}, "
            f"direction={result.direction!r}, parler={result.parler} "
            f"(envoyé={speak}, raison={result.raison!r})")
        if speak:
            self._prompt_pub.publish(StringTime(
                msg=contract.encode_prompt(text, result.raison), time=0, anim=False))

    def _publish_mission(self):
        with self._lock:
            payload = json.dumps(self._mission.to_dict(), ensure_ascii=False)
        self._mission_pub.publish(StringTime(msg=payload, time=0, anim=False))

    def destroy_node(self):
        # Pas d'attente de l'appel LLM en vol (jusqu'à REQUEST_TIMEOUT_S) :
        # le process s'arrête, le thread est abandonné.
        self._executor.shutdown(wait=False, cancel_futures=True)
        super().destroy_node()


def main(args=None):
    # Même doctrine que chat_node.main : les modules purs journalisent via
    # logging stdlib, invisible sans handler.
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )
    logging.getLogger("vision").setLevel(logging.INFO)

    rclpy.init(args=args)
    try:
        node = ReflectionNode()
    except ReflectionStartupError:
        rclpy.try_shutdown()
        raise SystemExit(1)

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
