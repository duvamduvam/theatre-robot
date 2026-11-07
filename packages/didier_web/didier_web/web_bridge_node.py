#!/usr/bin/env python3
"""Node rclpy + serveur aiohttp (HTTP + WebSocket) du pont web : supervision,
contenus (animation/face/audio/robot_lights), panneau technique, retour vidéo
MJPEG (/video) et pilotage roues W3 SIM-ONLY (message "drive" -> Twist sur
cmd_vel_web, UNIQUEMENT si drive_enabled=true -- défaut false, publisher non
créé sinon). Toujours AUCUN verrou e_stop (W1). La whitelist des contenus vit
dans web_protocol.py (import unique de vérité, testé en isolation) ; le drive
est un canal séparé, hors whitelist, avec plafond dur drive_to_twist.
Page « scène » (/scene) : mêmes WebSocket et sessions que la console ; ses
topics de répétition (route...) n'existent que si rehearsal_enabled (SIM-ONLY).

PIÈGE DEUX BOUCLES D'ÉVÉNEMENTS : rclpy.spin() est une boucle bloquante propre
à rclpy ; aiohttp a besoin de SA PROPRE boucle asyncio pour servir les
WebSockets. On ne les mélange PAS dans le même thread (rclpy.spin() ne rend
jamais la main à un event loop asyncio, et inversement) :
 - rclpy.spin(node) tourne dans un thread dédié (daemon, démarré dans main()) ;
 - aiohttp (web.run_app, boucle asyncio) tourne dans le thread principal.
Les deux communiquent par trois canaux, chacun protégé pour son usage :
 - `publisher.publish()` est thread-safe côté rclpy (documenté) : les
   handlers WebSocket (thread asyncio) appellent directement
   WebBridgeNode.publish_cmd(), aucune synchronisation nécessaire ;
 - `self.last_topics` (dernier payload par topic, pour la supervision) est
   ÉCRIT par les callbacks d'abonnement (thread spin) et LU par le timer
   asyncio qui construit le message "state" (thread aiohttp) : protégé par
   `self.lock` (threading.Lock, PAS asyncio.Lock -- les deux accès ne sont
   pas dans la même boucle d'événements).
 - les messages "feed" (TOPICS_FLUX, ex. chat_transcript) font le chemin
   INVERSE : reçus par un callback d'abonnement (thread spin), ils doivent être
   diffusés aux WebSockets (thread asyncio) IMMÉDIATEMENT et dans l'ordre. On
   n'y touche JAMAIS app["clients"] depuis le thread spin (dict muté par les
   handlers asyncio) : le callback ne fait que `loop.call_soon_threadsafe` vers
   une file asyncio, qu'un consommateur UNIQUE (_feed_loop) vide et diffuse.
   Une file + un consommateur plutôt qu'une tâche par message : c'est ce qui
   garantit l'ORDRE des répliques d'une conversation.
`SessionManager`, lui, n'est touché QUE depuis le thread asyncio (tous les
handlers WS + le timer de diffusion y tournent) : pas besoin de le protéger.
"""

import asyncio
import io
import json
import logging
import os
import pathlib
import threading
import time
import uuid

import rclpy
from aiohttp import web, WSMsgType
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import Twist
from PIL import Image as PILImage
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage, Image

from theatre_interfaces.msg import StringTime
# Codec StringTime commun (lot L1a) : `loads` et non decode_or_raw — le pont
# n'attrape que TypeError/JSONDecodeError (pas tout ValueError) et sa
# sémantique générique est gardée à l'identique.
from theatre_contrats import stringtime
from didier_web.web_catalog import build_catalog
from didier_web.web_protocol import (
    DRIVE_TIMEOUT_S, TOPICS_FLUX, TOPICS_LECTURE, WRITE_TIMEOUT_S, DriveFlow,
    ProtocolError, SessionManager, build_ack, build_err, build_feed,
    build_hb_ack, build_hello, build_state, drive_to_twist,
    effective_whitelist, parse_client_message, rehearsal_allowed,
    snapshot_visible, stop_all_commands,
)

STATE_PERIOD_S = 2.0  # cadence de diffusion du message "state" à tous les clients
NODES_REFRESH_PERIOD_S = 5.0  # get_node_names_and_namespaces() : évite de le refaire à 2 Hz
# Boucle de zéro pilotage : 20 Hz, comme le twist_deadman des roues -- assez
# fin pour publier l'arrêt franc peu après DRIVE_TIMEOUT_S (0.3 s) de silence.
DRIVE_TICK_S = 0.05
# Une frame vidéo plus vieille que ce délai = "flux tari" : l'endpoint /video
# répond 503 (l'UI affiche "pas de vidéo") au lieu de servir une image figée.
VIDEO_STALE_S = 2.0
# Profondeur de la file de flux (thread spin -> boucle asyncio). Une conversation
# produit quelques messages par minute : 256 ne sature que si la boucle asyncio
# est bloquée ; on jette alors (avec un WARNING) plutôt que de grossir sans fin.
FEED_QUEUE_MAX = 256
# Raison de refus commune aux messages qui exigent l'écriture (cmd/drive/stop) :
# l'UI s'en sert telle quelle dans son journal d'erreurs.
ERR_LECTURE_SEULE = "écriture non détenue"


class WebBridgeNode(Node):

    def __init__(self):
        super().__init__("web_bridge_node")

        # 8765 et pas 8088 : 8088 est le port par défaut de Superset, collision
        # RÉELLE constatée sur le PC de dev (réseau host, bind refusé au premier
        # lancement). Surchargable via le paramètre (WEB_PORT côté compose sim).
        self.declare_parameter("web_port", 8765)
        self.declare_parameter("token", "")
        self.declare_parameter("json_dir", "/home/ros2_ws/json")
        # SÉCURITÉ (SIM-ONLY) : le pilotage roues est derrière ce drapeau, FALSE
        # par défaut. Sans lui, le publisher cmd_vel_web n'est même pas créé --
        # aucune ligne de code ne PEUT publier de mouvement (même garantie
        # structurelle que la whitelist pour les topics de contenu).
        self.declare_parameter("drive_enabled", False)
        # Plafonds DURS appliqués côté serveur (drive_to_twist) : un navigateur
        # bugué/compromis ne peut pas les outrepasser. Valeurs prudentes par
        # défaut ; à caler après calibration max_wheel_speed (feuille de route §3).
        self.declare_parameter("max_linear", 0.5)
        self.declare_parameter("max_angular", 1.0)
        # Retour vidéo (caméra embarquée) : topic sensor_msgs/Image et cadence
        # max d'encodage JPEG (le Pi ne doit pas encoder plus vite que servi).
        self.declare_parameter("camera_topic", "camera/image_raw")
        self.declare_parameter("video_fps", 10)
        # true = le topic caméra porte du sensor_msgs/CompressedImage DÉJÀ en
        # JPEG (vrai robot : person_tracker du Pi vision publie
        # camera/image_raw/compressed, ~125 Ko/s — cf. dadou_vision_ros) :
        # les octets sont servis TELS QUELS en MJPEG, zéro ré-encodage.
        # false (défaut) = sensor_msgs/Image brut à encoder ici (sim : caméra gz).
        self.declare_parameter("camera_compressed", False)
        # Second flux vidéo, LECTURE SEULE : ce que la perception de Didier (person_tracker
        # du conteneur vision) voit et republie en CompressedImage JPEG -- en sim, la
        # webcam du PC, alors que camera_topic est la caméra Gazebo. Vide (défaut) =
        # désactivé : aucun abonnement, /perception répond 404, hello.perception=false
        # (rien ne change sur le vrai robot). Jamais inscriptible : ce topic n'est
        # pas dans la whitelist, le pont n'y publie rien.
        self.declare_parameter("perception_topic", "")
        # Troisième flux, LECTURE SEULE : « Didier vu de l'extérieur » (caméra de
        # poursuite Gazebo, SIM-ONLY, sensor_msgs/Image BRUT encodé ici comme
        # camera_topic). Vide (défaut) = désactivé : aucun abonnement, /exterior
        # répond 404, hello.exterior=false (le vrai robot n'a pas cette caméra).
        # Hors whitelist : le pont n'y publie rien.
        self.declare_parameter("exterior_topic", "")
        # SÉCURITÉ (SIM-ONLY) : topics de répétition simulée (route, route_speed,
        # rehearsal/cmd) de la page « scène ». FALSE par défaut ; même true, ignoré
        # hors domaine 43 (cf. plus bas) -- le vrai robot n'a jamais ces topics.
        self.declare_parameter("rehearsal_enabled", False)

        self.web_port = self.get_parameter("web_port").value
        self.json_dir = self.get_parameter("json_dir").value
        token = self.get_parameter("token").value or None
        self.drive_enabled = bool(self.get_parameter("drive_enabled").value)
        self.max_linear = float(self.get_parameter("max_linear").value)
        self.max_angular = float(self.get_parameter("max_angular").value)
        self.camera_topic = self.get_parameter("camera_topic").value
        self.video_fps = max(1, int(self.get_parameter("video_fps").value))
        self.camera_compressed = bool(self.get_parameter("camera_compressed").value)
        self.perception_topic = str(self.get_parameter("perception_topic").value or "")
        self.exterior_topic = str(self.get_parameter("exterior_topic").value or "")

        # ROS_DOMAIN_ID n'est pas exposé comme paramètre de node par rclpy :
        # c'est une variable d'environnement du PROCESSUS, lue une fois au
        # démarrage (elle ne change jamais en cours de vie du node).
        try:
            self.domain_id = int(os.environ.get("ROS_DOMAIN_ID", "-1"))
        except ValueError:
            self.domain_id = -1

        # Répétition : demandée ET domaine 43. Demandée sur un autre domaine = refus
        # LOGGUÉ en ERROR (jamais silencieux : l'opérateur croirait avoir les
        # boutons), et le node continue sans eux.
        rehearsal_demandee = bool(self.get_parameter("rehearsal_enabled").value)
        self.rehearsal_enabled = rehearsal_demandee and rehearsal_allowed(self.domain_id)
        if rehearsal_demandee and not self.rehearsal_enabled:
            self.get_logger().error(
                "rehearsal_enabled IGNORÉ : domain_id={} n'est pas la simulation (43)"
                " -- topics de répétition désactivés.".format(self.domain_id))
        # Whitelist EFFECTIVE : source unique pour les publishers ET pour le
        # parseur des cmd (handle_client_message).
        self.whitelist = effective_whitelist(self.rehearsal_enabled)

        self.sessions = SessionManager(token)

        # last_topics : topic -> {"msg": <valeur brute décodée>, "at_s": horloge monotone}.
        self.lock = threading.Lock()
        self.last_topics = {}
        self.node_names_cache = []

        # Un publisher/subscriber par topic whitelisté : IMPOSSIBLE de publier
        # ailleurs (pas de create_publisher générique côté handlers WS).
        self.publishers_by_topic = {
            topic: self.create_publisher(StringTime, topic, 10) for topic in sorted(self.whitelist)
        }
        for topic in sorted(self.whitelist):
            self.create_subscription(StringTime, topic, self._make_listener(topic), 10)

        # Topics d'ÉTAT en lecture seule (surbrillance des options actives,
        # 2026-07-13) : publiés LATCHÉS par chat_node (Pi vision) — l'abonné
        # DOIT être TRANSIENT_LOCAL lui aussi, sinon un pont démarré après le
        # chat ne verrait l'état qu'à la PROCHAINE transition (piège déjà vécu
        # sur animation_state). Aucun publisher créé : impossibles à publier
        # depuis le web (hors WHITELIST, cf. web_protocol.TOPICS_LECTURE).
        for topic in sorted(TOPICS_LECTURE):
            self.create_subscription(
                StringTime, topic, self._make_listener(topic),
                QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))

        # Topics de FLUX (chat_transcript) : chaque message est diffusé tel quel
        # à tous les clients, sans passer par last_topics (qui n'en garde que le
        # dernier, lu à 2 Hz). QoS par défaut VOLATILE depth 10 : compatible avec
        # un publieur volatile comme avec un latché ; on ne rejoue PAS l'historique
        # (une page rechargée repart d'une conversation vide -- voulu, un
        # transcript périmé n'est pas un état). Aucun publisher : hors WHITELIST.
        # feed_sink : posé par la boucle asyncio quand elle démarre (voir
        # _background_loops_ctx) ; None avant, donc les messages d'avant sont
        # jetés -- personne n'est connecté pour les recevoir.
        self.feed_sink = None
        for topic in sorted(TOPICS_FLUX):
            self.create_subscription(StringTime, topic, self._make_feed_listener(topic), 10)

        # --- Pilotage roues (SIM-ONLY, W3) --------------------------------------
        # Le publisher cmd_vel_web N'EXISTE que si drive_enabled : quand il vaut
        # None, publish_twist() est un no-op -- aucun mouvement possible, quoi
        # que fasse un client. DriveFlow décide quand publier l'arrêt franc.
        self.twist_pub = self.create_publisher(Twist, "cmd_vel_web", 10) \
            if self.drive_enabled else None
        self.drive_flow = DriveFlow()
        self._drive_active = False  # salve en cours ? (log INFO début/fin une seule fois)

        # --- Retour vidéo (caméra embarquée + perception) ------------------------
        # Une DerniereFrameJpeg par flux (écrite par le callback thread spin, lue par
        # l'endpoint HTTP thread asyncio) ; le throttle y est fait AVANT encodage.
        self.flux_camera = DerniereFrameJpeg(self.video_fps)
        if self.camera_compressed:
            self.create_subscription(
                CompressedImage, self.camera_topic, self._on_camera_compressed, 10)
        else:
            self.create_subscription(Image, self.camera_topic, self._on_camera, 10)

        self.flux_perception = DerniereFrameJpeg(self.video_fps)
        if self.perception_topic:
            # Best effort depth 1 : compatible avec un éditeur capteur (best effort)
            # comme fiable ; on ne garde que la dernière frame de toute façon.
            self.create_subscription(
                CompressedImage, self.perception_topic, self._on_perception,
                QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))

        self.flux_exterieur = DerniereFrameJpeg(self.video_fps)
        if self.exterior_topic:
            # Même QoS que perception (best effort depth 1 : seule la dernière
            # frame compte) ; le capteur gz publie du brut, donc encodage ici.
            self.create_subscription(
                Image, self.exterior_topic, self._on_exterior,
                QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))

        self.get_logger().info(
            "web_bridge_node prêt : port={} domain_id={} token_required={} json_dir={}"
            " drive_enabled={} max_linear={} max_angular={} camera_topic={}"
            " camera_compressed={} video_fps={} rehearsal_enabled={} perception_topic={!r}"
            " exterior_topic={!r}".format(
                self.web_port, self.domain_id, self.sessions.token_required, self.json_dir,
                self.drive_enabled, self.max_linear, self.max_angular,
                self.camera_topic, self.camera_compressed, self.video_fps,
                self.rehearsal_enabled, self.perception_topic, self.exterior_topic))
        if self.drive_enabled:
            # Trace explicite au démarrage : le pilotage roues est ACTIF (sim).
            self.get_logger().warning(
                "PILOTAGE ROUES WEB ACTIF (drive_enabled=true) -- cmd_vel_web publié,"
                " plafonds lin={} m/s ang={} rad/s. SIM-ONLY : protocole caméra requis"
                " avant tout usage sur le vrai robot.".format(self.max_linear, self.max_angular))

    def _make_listener(self, topic):
        """Une closure par topic : le callback doit savoir sous quelle clé
        ranger la valeur reçue dans last_topics."""
        def _on_message(msg):
            try:
                value = stringtime.loads(msg.msg)
            except (TypeError, json.JSONDecodeError):
                # Payload non-JSON (ne devrait pas arriver, cf. décodage StringTime
                # commun côté nodes robot) : republié tel quel, la supervision ne
                # doit jamais planter sur un topic externe au bridge.
                value = msg.msg
            with self.lock:
                self.last_topics[topic] = {"msg": value, "at_s": time.monotonic()}
        return _on_message

    def _make_feed_listener(self, topic):
        """Callback d'un topic de flux (thread SPIN). Décode comme _make_listener
        (JSON, sinon chaîne brute), puis confie le message à feed_sink -- qui
        traverse vers le thread asyncio. Surtout PAS de send direct ici : les
        WebSockets appartiennent à la boucle asyncio, pas au thread rclpy."""
        def _on_feed(msg):
            sink = self.feed_sink  # une seule lecture : l'attribut peut passer à None en arrêt
            if sink is None:
                return
            try:
                value = stringtime.loads(msg.msg)
            except (TypeError, json.JSONDecodeError):
                value = msg.msg
            sink(build_feed(topic, value))
        return _on_feed

    def publish_cmd(self, topic: str, value, time_ms: int = 0) -> None:
        """Publie une commande web. Sérialisation EXACTEMENT comme la
        télécommande (main_no_gui) : msg.msg = json.dumps(valeur nue) --
        "joie" -> '"joie"', False -> 'false' -- pas de ré-emballage {topic: valeur}
        sur le fil (voir docs/interfaces.md)."""
        ros_msg = StringTime()
        ros_msg.msg = json.dumps(value)
        ros_msg.time = time_ms
        ros_msg.anim = False
        self.publishers_by_topic[topic].publish(ros_msg)

    # --- Pilotage roues (SIM-ONLY) ------------------------------------------

    def publish_twist(self, lin_x: float, ang_z: float) -> None:
        """Publie un Twist sur cmd_vel_web. No-op si le publisher n'existe pas
        (drive_enabled=false) : garantie structurelle qu'aucun mouvement ne
        peut partir tant que le pilotage n'est pas explicitement activé."""
        if self.twist_pub is None:
            return
        msg = Twist()
        msg.linear.x = float(lin_x)
        msg.angular.z = float(ang_z)
        self.twist_pub.publish(msg)

    def on_drive_received(self, x: float, z: float, now_s: float) -> None:
        """Applique une consigne de drive : plafonne (drive_to_twist), publie,
        et arme le zéro. Log INFO SEULEMENT au premier drive d'une salve (15 Hz
        de messages -> pas de log par message, motif anti-spam wheels_node)."""
        lin, ang = drive_to_twist(x, z, self.max_linear, self.max_angular)
        self.publish_twist(lin, ang)
        if not self._drive_active:
            self._drive_active = True
            self.get_logger().info("pilotage web : début de mouvement")
        self.drive_flow.on_drive(now_s)

    def publish_drive_zero(self) -> None:
        """Publie UN Twist nul (arrêt franc) et clôt la salve. Idempotent :
        appelé par la boucle 20 Hz (fin de salve) ET par les chemins d'arrêt
        immédiat (déconnexion/perte d'écriture/take_control/STOP). Le log de fin
        et le reset ne se produisent qu'une fois par salve."""
        self.publish_twist(0.0, 0.0)
        self.drive_flow.reset()
        if self._drive_active:
            self._drive_active = False
            self.get_logger().info("pilotage web : fin de mouvement")

    # --- Retour vidéo (caméra embarquée) ------------------------------------

    def _on_camera(self, msg: Image) -> None:
        """Callback abonnement caméra (thread spin). Throttle AVANT encodage :
        le Pi ne doit pas encoder de JPEG pour des frames qui seront jetées
        (au plus video_fps encodages/s). Garde la dernière frame JPEG sous lock."""
        self._encoder_et_garder(self.flux_camera, msg)

    def _on_exterior(self, msg: Image) -> None:
        """Callback du flux « vu de l'extérieur » (thread spin) : même chemin
        que la caméra embarquée (throttle puis encodage), lecture seule."""
        self._encoder_et_garder(self.flux_exterieur, msg)

    @staticmethod
    def _encoder_et_garder(flux: "DerniereFrameJpeg", msg: Image) -> None:
        now = time.monotonic()
        if not flux.admettre(now):
            return  # frame excédentaire : jetée AVANT tout encodage
        jpeg = _encode_jpeg(msg)
        if jpeg is None:
            return
        flux.poser(jpeg, now)

    def _on_camera_compressed(self, msg: CompressedImage) -> None:
        """Callback abonnement caméra en mode camera_compressed (thread spin) :
        le payload est DÉJÀ du JPEG (person_tracker du Pi vision, format
        "jpeg") — on le stocke tel quel, aucun décodage/ré-encodage."""
        self._garder_jpeg(self.flux_camera, msg)

    def _on_perception(self, msg: CompressedImage) -> None:
        """Callback du flux perception (thread spin) : même traitement que la
        caméra compressée -- JPEG servi tel quel, lecture seule."""
        self._garder_jpeg(self.flux_perception, msg)

    @staticmethod
    def _garder_jpeg(flux: "DerniereFrameJpeg", msg: CompressedImage) -> None:
        if "jpeg" not in (msg.format or "").lower():
            return  # format inattendu : on ignore (l'UI affichera "pas de vidéo")
        now = time.monotonic()
        if flux.admettre(now):
            flux.poser(bytes(msg.data), now)

    def snapshot_jpeg(self) -> tuple:
        """(bytes JPEG | None, horodatage monotone) de la dernière frame caméra."""
        return self.flux_camera.snapshot()

    def snapshot_topics(self) -> dict:
        """Copie protégée de last_topics, âge recalculé à l'instant présent."""
        now = time.monotonic()
        with self.lock:
            items = dict(self.last_topics)
        # Topics masqués (lubies, vitesse) retirés AVANT diffusion : cf.
        # web_protocol.TOPICS_MASQUES -- David ne doit pas voir le tirage.
        return {
            topic: {"msg": info["msg"], "age_s": round(now - info["at_s"], 1)}
            for topic, info in snapshot_visible(items).items()
        }

    def refresh_node_names(self) -> None:
        self.node_names_cache = sorted(
            name for name, _namespace in self.get_node_names_and_namespaces())

    def hello_message(self, client_id: str) -> dict:
        return self._hello(writer=self.sessions.is_writer(client_id))

    def hello_readonly(self) -> dict:
        """hello forcé en lecture seule -- pour notifier un client qui vient de
        PERDRE l'écriture (ancien writer supplanté, ou libéré par timeout)."""
        return self._hello(writer=False)

    def _hello(self, writer: bool) -> dict:
        return build_hello(self.domain_id, writer=writer,
                           token_required=self.sessions.token_required,
                           drive_enabled=self.drive_enabled,
                           max_linear=self.max_linear, max_angular=self.max_angular,
                           rehearsal=self.rehearsal_enabled,
                           perception=bool(self.perception_topic),
                           exterior=bool(self.exterior_topic))


# --- Encodage vidéo (JPEG) : fonction pure, hors du node -------------------

class DerniereFrameJpeg:
    """Dernière frame JPEG d'un flux + horodatage monotone, sous lock (écrite
    par le callback ROS, lue par l'endpoint MJPEG). `admettre` est le throttle :
    à appeler AVANT tout encodage, pour ne rien encoder qui serait jeté."""

    def __init__(self, fps: int):
        self._intervalle_s = 1.0 / fps
        self._lock = threading.Lock()
        self._jpeg = None
        self._at_s = 0.0
        self._dernier_admis_s = 0.0

    def admettre(self, now_s: float) -> bool:
        if now_s - self._dernier_admis_s < self._intervalle_s:
            return False
        self._dernier_admis_s = now_s
        return True

    def poser(self, jpeg: bytes, now_s: float) -> None:
        with self._lock:
            self._jpeg = jpeg
            self._at_s = now_s

    def snapshot(self) -> tuple:
        with self._lock:
            return self._jpeg, self._at_s


def _encode_jpeg(msg: Image) -> bytes | None:
    """sensor_msgs/Image (rgb8 ou bgr8) -> bytes JPEG qualité 70, ou None si
    l'encodage échoue (encodage non géré, taille incohérente...) -- l'endpoint
    /video répond alors 503, l'UI affiche "pas de vidéo", rien ne plante.

    bgr8 : on s'appuie sur le décodeur brut de PIL avec le rawmode "BGR"
    (frombytes(..., "raw", "BGR")) -- il lit des octets ordonnés B,G,R dans une
    image RGB, c'est la voie la plus simple ET correcte (pas de recopie octet à
    octet). On suppose des lignes JOINTIVES (step == width*3), ce que fournit la
    caméra gz ; sinon la taille ne correspondrait pas et on renvoie None."""
    if msg.encoding == "rgb8":
        rawmode = "RGB"
    elif msg.encoding == "bgr8":
        rawmode = "BGR"
    else:
        return None
    if len(msg.data) < msg.width * msg.height * 3:
        return None
    try:
        img = PILImage.frombytes("RGB", (msg.width, msg.height),
                                 bytes(msg.data), "raw", rawmode)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return buf.getvalue()
    except (ValueError, OSError):
        return None


# --- Serveur HTTP / WebSocket (thread asyncio) ------------------------------

async def _send_json_safe(ws: web.WebSocketResponse, payload: dict) -> None:
    """Best-effort : un client qui a fermé sa socket entre-temps ne doit pas
    faire planter le diffuseur d'état ni un handler de commande."""
    if ws.closed:
        return
    try:
        await ws.send_json(payload)
    except ConnectionResetError:
        pass


async def catalog_handler(request: web.Request) -> web.Response:
    node = request.app["node"]
    # CORS ouvert : la console est UNE page (souvent servie par le pont de la
    # sim sur le PC) qui peut viser un AUTRE pont via son sélecteur de cible --
    # le fetch du catalogue est alors cross-origin. Les WebSocket et <img>
    # n'y sont pas soumis ; seul ce fetch l'exige. Pas de donnée sensible ici
    # (liste de noms), l'écriture reste protégée par la session WS.
    return web.json_response(build_catalog(node.json_dir),
                             headers={"Access-Control-Allow-Origin": "*"})


async def _handle_auth(node, app, client_id, ws, msg):
    if not node.sessions.authenticate(client_id, msg["token"], time.monotonic()):
        node.get_logger().warning("auth web refusée id={} (mauvais token)".format(client_id))
        await _send_json_safe(ws, build_err("token invalide"))
        return
    node.get_logger().info("auth web acceptée id={} writer={}".format(
        client_id, node.sessions.is_writer(client_id)))
    await _send_json_safe(ws, node.hello_message(client_id))


async def _handle_hb(node, app, client_id, ws, msg):
    node.sessions.heartbeat(client_id, time.monotonic())
    await _send_json_safe(ws, build_hb_ack(msg["t"]))


async def _handle_take_control(node, app, client_id, ws, msg):
    previous_writer = node.sessions.writer_id
    if not node.sessions.take_control(client_id, time.monotonic()):
        await _send_json_safe(ws, build_err("non authentifié"))
        return
    node.get_logger().info("prise de main écriture id={}".format(client_id))
    # Passation d'écriture = perte d'écriture pour l'ancien writer : on coupe
    # tout mouvement web en cours par prudence (cf. spec §3, "zéro immédiat").
    node.publish_drive_zero()
    await _send_json_safe(ws, node.hello_message(client_id))
    # L'ancien writer (autre onglet/opérateur) doit voir son bandeau repasser
    # en lecture seule sans attendre le prochain "state".
    if previous_writer and previous_writer != client_id and previous_writer in app["clients"]:
        await _send_json_safe(app["clients"][previous_writer], node.hello_readonly())


async def _handle_stop_all(node, app, client_id, ws, msg):
    if not node.sessions.is_writer(client_id):
        node.get_logger().warning("stop_all refusé (lecture seule) id={}".format(client_id))
        await _send_json_safe(ws, build_err(ERR_LECTURE_SEULE))
        return
    # Répétition activée : STOP coupe aussi la route et termine la séance
    # (cf. stop_all_commands) -- les topics existent alors dans la whitelist.
    for topic, value in stop_all_commands(node.rehearsal_enabled):
        node.publish_cmd(topic, value)
    # STOP CONTENUS coupe aussi le mouvement web (le Twist nul, en plus des
    # StringTime de stop_all_commands qui ne touchent QUE les contenus).
    node.publish_drive_zero()
    node.get_logger().info("STOP CONTENUS déclenché id={}".format(client_id))
    await _send_json_safe(ws, build_ack("stop_all"))


async def _handle_cmd(node, app, client_id, ws, msg):
    if not node.sessions.is_writer(client_id):
        node.get_logger().warning("cmd web refusée (lecture seule) id={} topic={}".format(
            client_id, msg["topic"]))
        await _send_json_safe(ws, build_err(ERR_LECTURE_SEULE))
        return
    node.publish_cmd(msg["topic"], msg["value"], msg["time"])
    node.get_logger().info("cmd web id={} topic={} payload={!r}".format(
        client_id, msg["topic"], msg["value"]))
    await _send_json_safe(ws, build_ack(msg["topic"]))


async def _handle_drive(node, app, client_id, ws, msg):
    """Consigne de pilotage roues (SIM-ONLY). Refusée si non-writer (WARNING) ou
    si le pilotage est désactivé (err "pilotage désactivé"). PAS d'ack ni de log
    par message : 15 Hz de drive spammeraient le journal ET la WebSocket -- le
    node log seulement début/fin de salve (on_drive_received/publish_drive_zero),
    et l'UI affiche localement la consigne qu'elle envoie."""
    if not node.sessions.is_writer(client_id):
        node.get_logger().warning("drive web refusé (lecture seule) id={}".format(client_id))
        await _send_json_safe(ws, build_err(ERR_LECTURE_SEULE))
        return
    if not node.drive_enabled:
        await _send_json_safe(ws, build_err("pilotage désactivé"))
        return
    node.on_drive_received(msg["x"], msg["z"], time.monotonic())


# Dispatch par type : chaque handler applique et répond son propre message.
# Table plutôt qu'une cascade if/elif -- garde handle_client_message sous le
# seuil de complexité et isole chaque règle (motif de web_protocol._PARSERS).
_HANDLERS = {
    "auth": _handle_auth,
    "hb": _handle_hb,
    "take_control": _handle_take_control,
    "stop_all": _handle_stop_all,
    "cmd": _handle_cmd,
    "drive": _handle_drive,
}


async def handle_client_message(node: WebBridgeNode, app: web.Application,
                                 client_id: str, ws: web.WebSocketResponse, raw: str) -> None:
    """Décode puis applique un message client. Refus de parsing loggué en
    WARNING + err renvoyé (connexion JAMAIS fermée -- motif du décodage
    StringTime commun) ; l'application est déléguée au handler du type."""
    try:
        msg = parse_client_message(raw, node.whitelist)
    except ProtocolError as e:
        node.get_logger().warning("message web rejeté id={} : {}".format(client_id, e.raison))
        await _send_json_safe(ws, build_err(e.raison))
        return
    await _HANDLERS[msg["type"]](node, app, client_id, ws, msg)


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    node = request.app["node"]
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    client_id = str(uuid.uuid4())
    request.app["clients"][client_id] = ws
    node.get_logger().info("client web connecté id={}".format(client_id))

    # hello immédiat, AVANT toute auth : le bandeau (mode SIMULATION/ROBOT RÉEL/
    # INCONNU) doit s'afficher même pendant que l'opérateur choisit son token.
    await _send_json_safe(ws, node.hello_message(client_id))

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                await handle_client_message(node, request.app, client_id, ws, msg.data)
            elif msg.type == WSMsgType.ERROR:
                node.get_logger().warning("erreur WebSocket id={} : {}".format(
                    client_id, ws.exception()))
    finally:
        released = node.sessions.remove_client(client_id)
        request.app["clients"].pop(client_id, None)
        # Déconnexion du writer -> arrêt franc immédiat du mouvement web (ne pas
        # attendre le zéro par timeout DriveFlow : le lien est déjà rompu).
        if released:
            node.publish_drive_zero()
        node.get_logger().info("client web déconnecté id={} (écriture libérée: {})".format(
            client_id, released))

    return ws


async def _broadcast(app: web.Application, payload: dict) -> None:
    # list() volontaire (pas une scorie) : chaque send est un point d'await où
    # un client peut se (dé)connecter et muter app["clients"] -- itérer le
    # dict vivant lèverait RuntimeError, on fige donc un instantané.
    for ws in list(app["clients"].values()):
        await _send_json_safe(ws, payload)


async def _state_loop(app: web.Application) -> None:
    """Boucle de fond (une par process, démarrée par cleanup_ctx) : toutes les
    STATE_PERIOD_S, vérifie le timeout heartbeat puis diffuse l'état à tous
    les clients connectés."""
    node = app["node"]
    last_nodes_refresh = 0.0
    while True:
        await asyncio.sleep(STATE_PERIOD_S)

        now_s = time.monotonic()
        released_id = node.sessions.check_timeouts(now_s)
        if released_id is not None:
            node.get_logger().warning(
                "écriture libérée par timeout heartbeat (> {:.1f}s) id={}".format(
                    WRITE_TIMEOUT_S, released_id))
            # Perte d'écriture (heartbeat mort) -> arrêt franc du mouvement web.
            node.publish_drive_zero()
            if released_id in app["clients"]:
                await _send_json_safe(app["clients"][released_id], node.hello_readonly())

        if now_s - last_nodes_refresh > NODES_REFRESH_PERIOD_S:
            node.refresh_node_names()
            last_nodes_refresh = now_s

        await _broadcast(app, build_state(
            topics=node.snapshot_topics(),
            nodes=node.node_names_cache,
            clients=len(app["clients"]),
            writer_present=node.sessions.writer_present(),
        ))


async def _drive_zero_loop(app: web.Application) -> None:
    """Boucle 20 Hz (SIM-ONLY) : publie l'arrêt franc quand une salve de drive
    se tait au-delà de DRIVE_TIMEOUT_S. Distincte de _state_loop (2 Hz, bien
    trop lente pour un arrêt roues) mais même motif cleanup_ctx. No-op tant
    qu'aucun drive n'a été reçu (should_zero renvoie False)."""
    node = app["node"]
    while True:
        await asyncio.sleep(DRIVE_TICK_S)
        if node.drive_flow.should_zero(time.monotonic()):
            node.publish_drive_zero()


def _enqueue_feed(node: WebBridgeNode, queue: asyncio.Queue, payload: dict) -> None:
    """Dépose un message de flux dans la file. Tourne DANS la boucle asyncio
    (appelé via call_soon_threadsafe) : la file n'est donc jamais touchée
    depuis deux threads. File pleine = boucle asyncio bloquée : on jette."""
    try:
        queue.put_nowait(payload)
    except asyncio.QueueFull:
        node.get_logger().warning("flux web saturé : message {} jeté".format(payload["topic"]))


def _make_feed_sink(node: WebBridgeNode, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue):
    """Puits thread-safe appelé par les callbacks d'abonnement (thread SPIN).
    PIÈGE : asyncio.Queue n'est PAS thread-safe -- put_nowait depuis le thread
    rclpy ne réveillerait pas la boucle (et corromprait la file). Seul
    loop.call_soon_threadsafe passe d'un thread à l'autre : il planifie
    _enqueue_feed dans la boucle ET la réveille, d'où une diffusion immédiate."""
    def _sink(payload: dict) -> None:
        try:
            loop.call_soon_threadsafe(_enqueue_feed, node, queue, payload)
        except RuntimeError:
            pass  # boucle déjà fermée (arrêt du process) : plus personne à servir
    return _sink


async def _feed_loop(app: web.Application, queue: asyncio.Queue) -> None:
    """Consommateur UNIQUE de la file de flux : diffuse chaque message à tous
    les clients, dans l'ordre d'arrivée. Une erreur d'envoi ne doit pas tuer la
    boucle (les répliques suivantes seraient perdues en silence) : loggée, puis
    on continue."""
    node = app["node"]
    while True:
        payload = await queue.get()
        try:
            await _broadcast(app, payload)
        except Exception as e:  # noqa: BLE001 -- la boucle de flux doit survivre
            node.get_logger().warning("diffusion du flux {} échouée : {}".format(
                payload["topic"], e))


async def _background_loops_ctx(app: web.Application):
    """cleanup_ctx aiohttp : démarre les boucles de fond au premier `up`, les
    coupe proprement au `cleanup` (sinon les tasks fuient au redémarrage)."""
    node = app["node"]
    feed_queue = asyncio.Queue(maxsize=FEED_QUEUE_MAX)
    tasks = [asyncio.ensure_future(_state_loop(app)),
             asyncio.ensure_future(_drive_zero_loop(app)),
             asyncio.ensure_future(_feed_loop(app, feed_queue))]
    # Branché APRÈS la création de la file et de son consommateur : le thread
    # spin ne peut pas déposer dans une file sans lecteur.
    node.feed_sink = _make_feed_sink(node, asyncio.get_running_loop(), feed_queue)
    yield
    node.feed_sink = None  # d'abord couper l'alimentation, puis les consommateurs
    for task in tasks:
        task.cancel()


async def _servir_mjpeg(request: web.Request, flux: DerniereFrameJpeg) -> web.StreamResponse:
    """Flux MJPEG (multipart/x-mixed-replace) de la dernière frame
    du flux donné, servi à video_fps. Aucune frame fraîche (ou flux tari > VIDEO_STALE_S)
    -> 503, l'UI affiche "pas de vidéo". Chaque client a son propre rythme
    d'envoi ; l'encodage, lui, est mutualisé (fait une seule fois par frame dans
    le callback ROS, cf. _on_camera). Partagé par /video, /perception et /exterior."""
    node = request.app["node"]
    interval = 1.0 / node.video_fps

    jpeg, at_s = flux.snapshot()
    if jpeg is None or (time.monotonic() - at_s) > VIDEO_STALE_S:
        return web.Response(status=503, text="pas de vidéo")

    resp = web.StreamResponse(status=200, headers={
        "Content-Type": "multipart/x-mixed-replace; boundary=frame",
        "Cache-Control": "no-cache",
    })
    await resp.prepare(request)
    try:
        while True:
            jpeg, at_s = flux.snapshot()
            if jpeg is None or (time.monotonic() - at_s) > VIDEO_STALE_S:
                break  # flux tari : on ferme, le client réessaiera (bouton ⟳)
            await resp.write(
                b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
            await asyncio.sleep(interval)
    except (ConnectionResetError, asyncio.CancelledError):
        pass  # client parti en cours de flux : normal, rien à logger
    return resp


async def video_handler(request: web.Request) -> web.StreamResponse:
    """GET /video : caméra embarquée (Gazebo en sim, Pi vision sur le robot)."""
    return await _servir_mjpeg(request, request.app["node"].flux_camera)


async def perception_handler(request: web.Request) -> web.StreamResponse:
    """GET /perception : ce que voit la perception, LECTURE SEULE. 404 si le
    paramètre perception_topic est vide (flux désactivé)."""
    node = request.app["node"]
    if not node.perception_topic:
        return web.Response(status=404, text="flux perception désactivé")
    return await _servir_mjpeg(request, node.flux_perception)


async def exterior_handler(request: web.Request) -> web.StreamResponse:
    """GET /exterior : Didier vu de l'extérieur (caméra de poursuite, SIM-ONLY),
    LECTURE SEULE. 404 si exterior_topic est vide (flux désactivé)."""
    node = request.app["node"]
    if not node.exterior_topic:
        return web.Response(status=404, text="flux extérieur désactivé")
    return await _servir_mjpeg(request, node.flux_exterieur)


def build_app(node: WebBridgeNode) -> web.Application:
    app = web.Application()
    app["node"] = node
    app["clients"] = {}  # client_id -> WebSocketResponse, pour le broadcast d'état

    static_dir = pathlib.Path(get_package_share_directory("didier_web")) / "static"

    async def index_handler(_request):
        return web.FileResponse(static_dir / "index.html")

    async def scene_handler(_request):
        # Page « scène » : servie à TOUT instant, même sans répétition -- ses
        # boutons de route/séance sont masqués par hello.rehearsal côté page, et
        # refusés côté serveur par la whitelist effective. Parole/persona/texte
        # marchent aussi sur le vrai robot.
        return web.FileResponse(static_dir / "scene.html")

    app.router.add_get("/", index_handler)
    app.router.add_get("/scene", scene_handler)
    app.router.add_get("/api/catalog", catalog_handler)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_get("/video", video_handler)
    app.router.add_get("/perception", perception_handler)
    app.router.add_get("/exterior", exterior_handler)
    app.router.add_static("/static/", static_dir)

    app.cleanup_ctx.append(_background_loops_ctx)
    return app


def main(args=None):
    rclpy.init(args=args)
    node = WebBridgeNode()
    try:
        # rclpy.spin dans un thread daemon : voir le pourquoi en tête de fichier.
        # daemon=True -> pas besoin de join() explicite, le thread meurt avec
        # le process (web.run_app est la boucle principale, bloquante).
        spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
        spin_thread.start()
        web.run_app(build_app(node), host="0.0.0.0", port=node.web_port)
    except Exception as e:
        logging.error(e, exc_info=True)
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
