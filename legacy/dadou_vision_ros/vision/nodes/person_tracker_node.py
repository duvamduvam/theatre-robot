#!/usr/bin/env python3
"""Node 'person_tracker' : webcam -> détection -> /vision/person (V1).

QUOI : node FIN (I/O seulement) — ouvre la caméra (open_camera de detector.py,
       PAS de duplication), lit une frame par tour de timer, détecte les
       personnes (MediaPipeDetector), choisit/lisse la cible (TargetPicker),
       publie geometry_msgs/PointStamped sur /vision/person si une cible est
       retenue. Toute la LOGIQUE vit ailleurs et est testée sans ROS :
       vision/tracking/detector.py (backend) et vision/tracking/target_picker.py
       (choix de cible + lissage, testé par vision/tests/unit/test_target_picker.py).
POURQUOI la cadence n'est pas fixée par le timer : la webcam Jieli plafonne à
       16,7 fps et l'inférence MediaPipe domine le budget de frame (mesuré au
       bench : ~24% CPU pour 16,7 Hz) — un timer à période courte (voir
       TIMER_PERIOD_SECONDS) ne fait que déclencher le tour suivant dès que le
       précédent est fini ; la cadence RÉELLE est bornée par cap.read()+detect(),
       pas par le timer. C'est le même principe que la boucle de mesure du bench
       (bench_detection.run_bench), volontairement gardé identique.
CONTRAT (ARCHITECTURE.md, ne pas dévier) : silence = personne perdue — on ne
       publie RIEN quand TargetPicker.update() renvoie None (pas de message
       "vide"), le consommateur (gaze_follower côté robot) gère son timeout,
       comme cmd_vel/twist_deadman.
"""
import json
import os
import time

import cv2
import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from robot_interfaces.msg import StringTime
from sensor_msgs.msg import CompressedImage, Image
from theatre_contrats import topics

from vision.tracking.detector import MediaPipeDetector, open_camera
from vision.tracking.camera_source import (
    SOURCE_GAZEBO, SOURCE_WEBCAM, available_sources, decode_camera_source,
    image_to_bgr, resolve_source)
from vision.tracking.camera_switch import CAMERA_OFF, CAMERA_ON, decode_camera_enable
from vision.tracking.target_picker import TargetPicker

# Modèle téléchargé DANS L'IMAGE Docker (Dockerfile-arm, curl au build) : pas
# de dépendance réseau au démarrage du node. Chemin par défaut du paramètre
# ROS model_path — modifiable pour du dev PC hors conteneur.
DEFAULT_MODEL_PATH = "/home/ros2_ws/models/efficientdet_lite0.tflite"

# Bornée par la caméra/l'inférence (cf. docstring module) : ce n'est PAS la
# cadence réelle de publication, juste un plafond haut pour ne pas monopoliser
# le thread ROS en cas de lecture caméra anormalement rapide.
TIMER_PERIOD_SECONDS = 1.0 / 30.0

# Résolution de capture : identique au bench qui a validé le couple
# webcam/MJPG/CPU (640x480/30fps demandés, 16,7 fps réels côté Jieli).
CAPTURE_WIDTH = 640
CAPTURE_HEIGHT = 480
CAPTURE_FPS = 30

# frame_id du contrat ARCHITECTURE.md (topic /vision/person).
CAMERA_FRAME_ID = "camera"

# Retour vidéo (console de régie, cf. dadou_robot_ros docs/etude-interface-web.md
# W2 « MJPEG embarqué ») : la webcam étant tenue en EXCLUSIF par ce node, il est
# la seule source d'images possible — il republie donc ses trames en JPEG
# compressé (sensor_msgs/CompressedImage), throttlées et à qualité modérée :
# ~25 Ko/trame à 5 i/s ≈ 125 Ko/s sur le réseau, compatible WiFi/4G, là où du
# sensor_msgs/Image brut (640x480 BGR) ferait 4,6 Mo/s au même débit. Le
# web_bridge (Pi robot) sert ces octets TELS QUELS en MJPEG (camera_compressed).
VIDEO_TOPIC = "camera/image_raw/compressed"
VIDEO_FPS_DEFAULT = 5.0        # 0 = publication désactivée
VIDEO_JPEG_QUALITY = 70        # même qualité que _encode_jpeg côté web_bridge

# Désignation par bouton (2026-09-14, cf. dadou_robot_ros docs/
# etude-identification-acteur.md) : David se place devant le robot et appuie
# sur le gant -> ce topic bascule TargetPicker en cible verrouillée (voir
# TargetPicker.designate/release). Même contrat StringTime que `chat`/`gaze`
# côté robot : payload JSON "on"/true ou "off"/false, topic de COMMANDE (pas
# latché — contrairement à animation_state, personne n'a besoin de connaître
# l'état de désignation au démarrage tardif d'un abonné).
DESIGNATE_TOPIC = "designate"

# Coupe-webcam (vie privée de l'acteur au PC + arrêter que Didier s'adresse à
# lui) : commande `camera_enable` ("on"/"off"), état `camera_state` LATCHÉ.
# "off" = le périphérique est réellement LIBÉRÉ (la LED de la webcam s'éteint)
# et plus rien n'est publié (/vision/person, /vision/person_box, vidéo).
CAMERA_ENABLE_TOPIC = "camera_enable"
CAMERA_STATE_TOPIC = "camera_state"
# Cadence du log de réessai quand la réouverture échoue (le timer tourne à 30 Hz).
CAMERA_RETRY_LOG_S = 5.0

# Source d'images à chaud (répétition simulée) : commande `camera_source`
# ("webcam" | "gazebo"), état EFFECTIF `camera_source_state` latché, et
# `camera_sources` latché = JSON des sources disponibles (["webcam"] ou
# ["webcam","gazebo"]). « gazebo » n'existe que si le paramètre
# sim_camera_topic est non vide (banc PC x86 seulement, jamais sur le Pi).
CAMERA_SOURCE_TOPIC = "camera_source"
CAMERA_SOURCE_STATE_TOPIC = "camera_source_state"
CAMERA_SOURCES_TOPIC = "camera_sources"
# Cadence du warning « encoding refusé » (une frame Gazebo toutes les ~30 ms).
SIM_IMAGE_LOG_S = 5.0


class PersonTrackerStartupError(RuntimeError):
    """Levée quand le node ne peut pas démarrer proprement (modèle ou caméra
    manquants/invalides). Différencie un échec de démarrage EXPLICITE (déjà
    loggé via self.get_logger().error(...) avant d'être levée) d'un crash
    Python générique — main() l'attrape spécifiquement pour sortir proprement
    plutôt que de laisser une trace de crash-loop silencieuse."""


class PersonTrackerNode(Node):
    def __init__(self):
        super().__init__("person_tracker")

        # Paramètres ROS déclarés avec défauts (mission V1) : modifiables par
        # YAML/CLI sans toucher au code, ex. `ros2 run vision person_tracker
        # --ros-args -p camera_device:=/dev/video2`.
        self.declare_parameter("camera_device", "/dev/video0")
        self.declare_parameter("model_path", DEFAULT_MODEL_PATH)
        self.declare_parameter("score_threshold", 0.4)
        self.declare_parameter("ema_alpha", 0.4)
        self.declare_parameter("video_fps", VIDEO_FPS_DEFAULT)
        # "" = option Gazebo INDISPONIBLE (cas du robot réel).
        self.declare_parameter("sim_camera_topic", "")

        camera_device = self.get_parameter("camera_device").value
        model_path = self.get_parameter("model_path").value
        score_threshold = float(self.get_parameter("score_threshold").value)
        ema_alpha = float(self.get_parameter("ema_alpha").value)
        self._video_fps = float(self.get_parameter("video_fps").value)
        self._sim_camera_topic = str(self.get_parameter("sim_camera_topic").value or "").strip()

        # Échec explicite et propre si le modèle est absent : mieux vaut un
        # message clair au démarrage ("chemin X introuvable, vérifier le
        # montage/le build Docker") qu'une exception mediapipe opaque plus
        # loin, ou pire, une crash-loop silencieuse du conteneur.
        if not os.path.isfile(model_path):
            # PIÈGE (trouvé au déploiement Pi 5, 2026-07-04) : RcutilsLogger
            # (rclpy) n'est PAS le module `logging` stdlib — .error()/.info()
            # ne prennent qu'UNE chaîne déjà formatée, pas de style printf
            # %s/args variadiques (ça lève un TypeError "takes 2 positional
            # arguments but N were given"). On formate donc avec des f-strings.
            self.get_logger().error(
                f"Modèle MediaPipe introuvable : {model_path} — le "
                "Dockerfile-arm est censé le télécharger au build (curl vers "
                "ce chemin). Vérifiez le paramètre model_path et l'image Docker."
            )
            raise PersonTrackerStartupError(f"modèle introuvable : {model_path}")

        try:
            self._detector = MediaPipeDetector(model_path, score_threshold=score_threshold)
        except Exception as exc:  # noqa: BLE001 - on veut un log explicite avant de propager
            self.get_logger().error(
                f"Échec d'initialisation MediaPipe (modèle={model_path}) : {exc}"
            )
            raise PersonTrackerStartupError("échec init MediaPipe") from exc

        try:
            self._cap = open_camera(
                camera_device, width=CAPTURE_WIDTH, height=CAPTURE_HEIGHT, fps=CAPTURE_FPS,
            )
        except RuntimeError as exc:
            self.get_logger().error(
                f"Caméra indisponible ({camera_device}) : {exc} — vérifiez que "
                "le périphérique existe (v4l2-ctl --list-devices) et que /dev "
                "est bien monté dans le conteneur."
            )
            raise PersonTrackerStartupError("caméra indisponible") from exc

        self._camera_device = camera_device
        # Coupe-webcam : _camera_wanted est la CONSIGNE (écrite par le callback
        # de commande), _cap l'ÉTAT réel. Seul _on_timer ouvre/ferme la capture
        # (une seule main sur le périphérique, jamais depuis le callback ;
        # rclpy.spin = exécuteur mono-thread, le drapeau n'a pas de course).
        self._camera_wanted = True
        self._camera_state_sent = None
        self._last_retry_log_s = 0.0
        # Source d'images : _source_wanted = CONSIGNE (callback), _source_active
        # = ce que le timer a réellement mis en place. Frame Gazebo : le
        # callback ne fait que ranger le dernier message, le timer le consomme
        # (conversion + détection dans le MÊME tick que la webcam) puis le met
        # à None : une frame déjà traitée n'est jamais retraitée.
        self._source_wanted = SOURCE_WEBCAM
        self._source_active = SOURCE_WEBCAM
        self._source_state_sent = None
        self._sim_sub = None
        self._sim_msg = None
        self._last_sim_log_s = 0.0
        self._picker = TargetPicker(ema_alpha=ema_alpha)
        # Noms RELATIFS (theatre_contrats.topics, lot L1a) : sans namespace ils
        # se résolvent en /vision/person et /vision/person_box comme avant.
        self._publisher = self.create_publisher(PointStamped, topics.VISION_PERSON, 10)
        # Suivi roues (2026-07-11) : même cible, contrat ÉTENDU sur un topic
        # SÉPARÉ — /vision/person reste gelé (x=azimut, y=élévation,
        # z=confiance, consommé par gaze_follower), /vision/person_box porte
        # x=azimut, y=HAUTEUR de silhouette [0..1] (proxy de distance,
        # cf. target_picker), z=confiance. Consommé par person_follower
        # (dadou_robot_ros). Mêmes règles : silence = personne perdue.
        self._box_publisher = self.create_publisher(PointStamped, topics.VISION_PERSON_BOX, 10)

        # Désignation par bouton (cf. constante DESIGNATE_TOPIC) : bascule le
        # TargetPicker entre régime historique et cible verrouillée. QoS par
        # défaut (depth=10, VOLATILE) : c'est une commande, pas un état à
        # rattraper par un abonné tardif.
        self.create_subscription(StringTime, DESIGNATE_TOPIC, self._on_designate, 10)

        # Coupe-webcam : commande VOLATILE, état LATCHÉ (TRANSIENT_LOCAL,
        # depth 1) des DEUX côtés côté abonné — sinon la page ouverte après
        # le démarrage ne saurait jamais si la webcam est coupée.
        self.create_subscription(StringTime, CAMERA_ENABLE_TOPIC, self._on_camera_enable, 10)
        self._camera_state_pub = self.create_publisher(
            StringTime, CAMERA_STATE_TOPIC,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self._publish_camera_state(CAMERA_ON)  # défaut : la capture est ouverte ci-dessus

        # Source d'images : commande volatile, états latchés (même raison).
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(StringTime, CAMERA_SOURCE_TOPIC, self._on_camera_source, 10)
        self._source_state_pub = self.create_publisher(
            StringTime, CAMERA_SOURCE_STATE_TOPIC, latched)
        sources_pub = self.create_publisher(StringTime, CAMERA_SOURCES_TOPIC, latched)
        sources_pub.publish(StringTime(
            msg=json.dumps(available_sources(self._sim_camera_topic)), time=0, anim=False))
        self._publish_source_state(SOURCE_WEBCAM)  # défaut : webcam, ouverte plus haut

        # Retour vidéo (cf. constantes VIDEO_*) : publisher créé SEULEMENT si
        # video_fps > 0 — même garantie structurelle que drive_enabled côté
        # web_bridge (aucune ligne de code ne PEUT publier d'image sinon).
        self._video_pub = None
        self._last_video_s = 0.0
        if self._video_fps > 0:
            self._video_pub = self.create_publisher(CompressedImage, VIDEO_TOPIC, 10)

        self._timer = self.create_timer(TIMER_PERIOD_SECONDS, self._on_timer)

        self.get_logger().info(
            f"person_tracker démarré (camera={camera_device}, model={model_path}, "
            f"score_threshold={score_threshold:.2f}, ema_alpha={ema_alpha:.2f}, "
            f"video_fps={self._video_fps:g}) -> /vision/person"
            + (f" + {VIDEO_TOPIC}" if self._video_pub is not None else "")
        )

    def _on_designate(self, ros_msg) -> None:
        """Active/désactive la désignation par bouton — même contrat que
        chat_node._on_chat_cmd (dadou_vision_ros/vision/nodes/chat_node.py) :
        "on"/"off", JSON ou brut. PIÈGE ÉVITÉ : le décodage StringTime commun
        du dépôt frère (dadou_robot_ros/robot/nodes/payload.py::decode) n'est
        PAS réutilisable ici — il importe robot.robot_static, un paquet ROS
        que vision n'a et ne doit PAS dépendre (dépôts frères indépendants).
        Ce dépôt n'a pas d'équivalent factorisé pour ses topics de commande
        (chat/persona) : on suit donc le même motif dupliqué, pas de perte
        silencieuse — toute valeur non reconnue est logguée en warning."""
        raw = ros_msg.msg
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            value = raw
        if value in ("on", True, 1, "1"):
            self._picker.designate()
            self.get_logger().info("désignation ON : verrouillage sur la prochaine personne centrée")
        elif value in ("off", False, 0, "0"):
            self._picker.release()
            self.get_logger().info("désignation OFF : retour au choix historique (score * aire)")
        else:
            self.get_logger().warning(f"commande designate inconnue : {raw!r}")

    def _on_camera_enable(self, ros_msg) -> None:
        """Pose la CONSIGNE caméra ; l'ouverture/fermeture réelle se fait dans
        _on_timer. Valeur inconnue : warning, rien ne change."""
        wanted = decode_camera_enable(ros_msg.msg)
        if wanted is None:
            self.get_logger().warning(f"commande camera_enable inconnue : {ros_msg.msg!r}")
            return
        self._camera_wanted = wanted

    def _on_camera_source(self, ros_msg) -> None:
        """Pose la CONSIGNE de source ; l'abonnement/la libération réels se
        font dans _sync_camera (jamais ici). Inconnue ou « gazebo » sans
        sim_camera_topic : warning, rien ne change."""
        requested = decode_camera_source(ros_msg.msg)
        if requested is None:
            self.get_logger().warning(f"commande camera_source inconnue : {ros_msg.msg!r}")
            return
        adopted = resolve_source(self._source_wanted, requested, self._sim_camera_topic)
        if adopted != requested:
            self.get_logger().warning(
                f"camera_source {requested!r} refusée : sim_camera_topic non configuré "
                "(source gazebo indisponible sur cette machine)")
            return
        self._source_wanted = adopted

    def _on_sim_image(self, msg) -> None:
        """Range la dernière frame Gazebo (le timer la consomme)."""
        self._sim_msg = msg

    def _publish_source_state(self, source: str) -> None:
        """Publie la source EFFECTIVE, seulement sur changement."""
        if source == self._source_state_sent:
            return
        self._source_state_sent = source
        self._source_state_pub.publish(StringTime(msg=source, time=0, anim=False))
        self.get_logger().info(f"source d'images : {source}")

    def _release_inputs(self) -> None:
        """Ferme TOUT ce qui alimente la perception : périphérique (LED éteinte)
        et abonnement Gazebo."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        if self._sim_sub is not None:
            self.destroy_subscription(self._sim_sub)
            self._sim_sub = None
        self._sim_msg = None

    def _publish_camera_state(self, state: str) -> None:
        """Publie l'état EFFECTIF (pas la consigne), seulement sur changement."""
        if state == self._camera_state_sent:
            return
        self._camera_state_sent = state
        self._camera_state_pub.publish(StringTime(msg=state, time=0, anim=False))
        self.get_logger().info(f"caméra {state}")

    def _sync_camera(self) -> bool:
        """Met les entrées en accord avec les consignes (marche/arrêt ET source).
        Renvoie True si une frame peut être lue ce tour-ci."""
        if self._source_active != self._source_wanted:
            # Changement de source (même caméra coupée : la source choisie
            # s'appliquera à la reprise). On ferme l'ancienne entrée, et comme
            # pour la coupure : désignation relâchée + lissage effacé, pas de
            # cible fantôme d'une source à l'autre.
            self._release_inputs()
            self._picker.release()
            self._picker.reset()
            self._source_active = self._source_wanted
            self._publish_source_state(self._source_active)
        if not self._camera_wanted:
            if self._cap is not None or self._sim_sub is not None:
                self._release_inputs()  # libère /dev/video0 : la LED s'éteint
                # Désignation relâchée ET lissage effacé : à la reprise, pas de
                # cible fantôme ni de verrouillage hérité d'avant la coupure.
                self._picker.release()
                self._picker.reset()
            self._publish_camera_state(CAMERA_OFF)
            return False
        if self._source_active == SOURCE_GAZEBO:
            if self._sim_sub is None:
                # BEST_EFFORT depth 1 : seule la dernière frame compte.
                self._sim_sub = self.create_subscription(
                    Image, self._sim_camera_topic, self._on_sim_image,
                    QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))
            self._publish_camera_state(CAMERA_ON)
            return True
        if self._cap is None:
            try:
                self._cap = open_camera(
                    self._camera_device, width=CAPTURE_WIDTH,
                    height=CAPTURE_HEIGHT, fps=CAPTURE_FPS,
                )
            except RuntimeError as exc:
                # Consigne « on » conservée : on réessaie à chaque tour (log
                # throttlé). L'état publié reste « off » tant que ça échoue.
                now = time.monotonic()
                if now - self._last_retry_log_s >= CAMERA_RETRY_LOG_S:
                    self._last_retry_log_s = now
                    self.get_logger().error(f"Réouverture caméra échouée : {exc} (nouvel essai)")
                return False
        self._publish_camera_state(CAMERA_ON)
        return True

    def _read_frame(self):
        """Une frame BGR de la source active, ou None (rien de neuf / refusée)."""
        if self._source_active == SOURCE_GAZEBO:
            msg, self._sim_msg = self._sim_msg, None  # consommée : jamais retraitée
            if msg is None:
                return None
            try:
                return image_to_bgr(msg.encoding, msg.width, msg.height, msg.step, msg.data)
            except ValueError as exc:
                now = time.monotonic()
                if now - self._last_sim_log_s >= SIM_IMAGE_LOG_S:
                    self._last_sim_log_s = now
                    self.get_logger().warning(f"Image {self._sim_camera_topic} refusée : {exc}")
                return None
        ok, frame = self._cap.read()
        if not ok:
            # Échec de lecture PONCTUEL (pas au démarrage) : on log et on
            # attend le prochain tour plutôt que de crasher le node — une
            # webcam USB peut avoir un hoquet transitoire sans être hors service.
            self.get_logger().warning("Échec de lecture caméra (frame ignorée)")
            return None
        return frame

    def _publish_video(self, frame) -> None:
        """Republie la trame courante en JPEG compressé, throttlée à video_fps.
        Publiée QUE quelqu'un regarde ou non (DDS ne transmet rien sans
        abonné : le coût réseau est nul sans console ouverte ; le coût CPU de
        l'encodage — ~2-3 ms à 5 i/s sur Pi 5 — est assumé en continu plutôt
        que de complexifier avec une détection d'abonnés)."""
        now = time.monotonic()
        if now - self._last_video_s < 1.0 / self._video_fps:
            return  # trame excédentaire : jetée AVANT tout encodage
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, VIDEO_JPEG_QUALITY])
        if not ok:
            return  # échec d'encodage ponctuel : on retentera à la prochaine trame
        self._last_video_s = now
        msg = CompressedImage()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = CAMERA_FRAME_ID
        msg.format = "jpeg"
        msg.data = jpeg.tobytes()
        self._video_pub.publish(msg)

    def _on_timer(self) -> None:
        if not self._sync_camera():
            return  # coupée (ou en cours de réouverture) : AUCUNE publication
        frame = self._read_frame()
        if frame is None:
            return

        # Retour vidéo AVANT la détection : la vidéo vit même si MediaPipe
        # échoue ou ne voit personne (deux services indépendants).
        if self._video_pub is not None:
            self._publish_video(frame)

        height, width = frame.shape[:2]
        detections = self._detector.detect(frame)
        result = self._picker.update(detections, width, height)

        if result is None:
            # Silence = personne perdue (contrat ARCHITECTURE.md) : ne rien publier.
            return

        stamp = self.get_clock().now().to_msg()

        msg = PointStamped()
        msg.header.stamp = stamp
        msg.header.frame_id = CAMERA_FRAME_ID
        msg.point.x = result.azimuth
        msg.point.y = result.elevation
        msg.point.z = result.confidence
        self._publisher.publish(msg)

        # Contrat étendu pour le suivi roues (cf. création du publisher) :
        # y = hauteur de silhouette, PAS l'élévation.
        box_msg = PointStamped()
        box_msg.header.stamp = stamp
        box_msg.header.frame_id = CAMERA_FRAME_ID
        box_msg.point.x = result.azimuth
        box_msg.point.y = result.height
        box_msg.point.z = result.confidence
        self._box_publisher.publish(box_msg)

    def destroy_node(self):
        # Libère la caméra même si le node est détruit après une erreur avant
        # que self._cap n'existe (cas modèle manquant : on sort avant cap).
        cap = getattr(self, "_cap", None)
        if cap is not None:
            cap.release()
            self._cap = None
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    try:
        node = PersonTrackerNode()
    except PersonTrackerStartupError:
        # Déjà loggé en détail dans __init__ (get_logger().error avant la
        # levée) : ici on se contente de sortir proprement, contexte ROS
        # fermé, code de retour non nul pour que systemd/docker sachent que
        # ça n'a pas tourné (mais SANS boucle de crash bruyante : un seul
        # message clair, pas une pile d'exception).
        rclpy.try_shutdown()
        raise SystemExit(1)

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        # SIGINT ou arrêt du contexte par rclpy : chemin d'arrêt NORMAL (fin
        # de spectacle, docker stop), pas une erreur à tracer.
        pass
    finally:
        node.destroy_node()
        # try_shutdown (PAS shutdown) : le handler SIGINT de rclpy (Jazzy) a
        # souvent DÉJÀ fermé le contexte — shutdown() lèverait
        # « rcl_shutdown already called » (cf. chat_node.main, 2026-07-11).
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
