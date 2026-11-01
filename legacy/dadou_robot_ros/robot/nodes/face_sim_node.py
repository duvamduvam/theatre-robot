#!/usr/bin/env python3
"""Node face_sim : aperçu web du visage LED de Didier EN SIMULATION.

Exécute le VRAI code de rendu (robot.actions.face.Face + les tables
ImageMapping, réutilisés TELS QUELS -- rien n'est réimplémenté) sur un strip
factice (PreviewStrip, robot.visual.face_preview) au lieu du driver matériel
FastNeoPixel : aucune divergence possible entre ce que montre l'aperçu et ce
que ferait le vrai robot. Seul le "câblage" change -- PreviewStrip encode
chaque show() en JPEG au lieu de piloter un ruban LED réel.

Aucune lib matérielle importée (contrairement à lights_node) : ce node tourne
sur x86 comme sur le Pi. En pratique il n'est lancé QUE par sim.launch.py
(argument face:=true, défaut false, même prudence que animations/web) --
jamais dans le bringup du vrai robot.

PIÈGE DEUX BOUCLES D'ÉVÉNEMENTS : même architecture que
robot_web/web_bridge_node.py (rclpy.spin dans un thread daemon, aiohttp dans
le thread principal) -- rclpy.spin() est bloquant et ne rend jamais la main à
une boucle asyncio, on ne les mélange donc pas dans le même thread. Les deux
communiquent par self.last_jpeg (écrit par _on_show, thread spin ; lu par
l'endpoint /stream, thread aiohttp), protégé par self.jpeg_lock
(threading.Lock, PAS asyncio.Lock -- les deux accès ne sont pas dans la même
boucle d'événements).
"""

import asyncio
import io
import logging
import logging.config
import threading

import rclpy
from aiohttp import web
from PIL import Image as PILImage
from rclpy.node import Node
from robot_interfaces.msg import StringTime

from dadou_utils_ros.logging_conf import LoggingConf
from dadou_utils_ros.utils_static import DURATION, FACE, LOGGING_FILE_NAME
from robot.actions.face import Face
from robot.files.robot_json_manager import RobotJsonManager
from robot.nodes.payload import decode
from robot.robot_config import config
from robot.robot_static import LIGHTS_PIN, TICK_PERIOD_S
from robot.visual.face_preview import PreviewStrip, render_face_rgb

# Cadence du flux MJPEG (spec) : un visage fait de blocs de LED n'a aucun
# besoin de coller au tick 20 Hz du strip (TICK_PERIOD_S) -- 10 i/s suffit
# largement à percevoir les animations (clignements, bouche qui parle...).
STREAM_FPS = 10
# Upscale nearest (cf. render_face_rgb) : chaque "LED" doit rester un carré
# net à l'écran, pas un flou d'interpolation JPEG sur une image minuscule.
RENDER_SCALE = 16

_INDEX_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Visage de Didier — aperçu sim</title>
<style>
  body { background: #111; color: #ccc; font-family: sans-serif;
         display: flex; flex-direction: column; align-items: center; }
  img { image-rendering: pixelated; margin-top: 2em; border: 1px solid #333; }
</style>
</head>
<body>
<h1>Visage de Didier — aperçu sim</h1>
<img src="/stream" alt="aperçu du visage de Didier">
</body>
</html>
"""


class FaceSimNode(Node):

    def __init__(self):
        node_name = "face_sim_node"
        logging.config.dictConfig(LoggingConf.get(config[LOGGING_FILE_NAME], node_name))
        super().__init__(node_name)

        self.declare_parameter("face_port", 8766)
        self.face_port = self.get_parameter("face_port").value

        # LIGHTS_PIN n'existe que sur le Pi (robot_config.py : board.D18,
        # importé seulement si Misc.is_raspberrypi()) -- Face.__init__ le lit
        # dans un log debug, valeur neutre nécessaire pour construire hors
        # matériel (même contournement que robot/tests/unit/test_face.py).
        config.setdefault(LIGHTS_PIN, None)

        self.jpeg_lock = threading.Lock()
        self.last_jpeg = None

        # Le strip factice encode CHAQUE show() en JPEG (thread spin, seul
        # appelant possible : callbacks topic et tick sont sérialisés par
        # rclpy.spin_once/spin) ; _on_show range le résultat sous jpeg_lock
        # pour le thread aiohttp qui sert /stream.
        self.strip = PreviewStrip(on_show=self._on_show)

        robot_json_manager = RobotJsonManager(config)
        try:
            self.face = Face(config=config, json_manager=robot_json_manager, strip=self.strip)
        except OSError as e:
            # Cas concret attendu : medias/visuals/{mouth,eye} pas montés dans
            # le conteneur sim (docker-compose-sim.yml) -- FilesUtils.get_folder_files
            # fait un listdir() qui lève FileNotFoundError (sous-classe
            # d'OSError) sur un dossier absent. Message ACTIONNABLE avant de
            # laisser planter le node : sans lui, seule une trace OSError
            # générique apparaîtrait dans les logs, sans piste de résolution.
            logging.error(
                "impossible de charger les visuels du visage (%s) -- le volume"
                " medias/ est-il monté dans le conteneur sim ? voir"
                " conf/docker/sim/docker-compose-sim.yml", e)
            raise

        self.face_subscription = self.create_subscription(
            StringTime, FACE, self.face_callback, 10)
        self.timer = self.create_timer(TICK_PERIOD_S, self.timer_callback)

        logging.info("face_sim_node prêt : aperçu sur http://localhost:%s", self.face_port)

    def _on_show(self, pixels):
        """Callback de PreviewStrip.show() : rend la frame courante et
        l'encode en JPEG. Une erreur ici (image de visuel corrompue, etc.) ne
        doit JAMAIS remonter jusqu'à Face -- seule la frame de l'aperçu est
        perdue (l'ancienne reste servie), le visage réel n'en sait rien."""
        try:
            image = render_face_rgb(pixels, scale=RENDER_SCALE)
            buf = io.BytesIO()
            PILImage.fromarray(image, "RGB").save(buf, format="JPEG", quality=85)
        except Exception as e:
            logging.error("échec encodage JPEG de l'aperçu visage : %s", e, exc_info=True)
            return
        with self.jpeg_lock:
            self.last_jpeg = buf.getvalue()

    def snapshot_jpeg(self):
        with self.jpeg_lock:
            return self.last_jpeg

    def face_callback(self, ros_msg):
        msg = decode(ros_msg, FACE)
        if msg is None:
            return
        logging.info('Face (sim): "%s"', msg)
        self.face.update({FACE: msg, DURATION: ros_msg.time})

    def timer_callback(self):
        try:
            self.face.process()
        except Exception as e:
            logging.error(e, exc_info=True)


# --- Serveur HTTP (thread principal, boucle asyncio d'aiohttp) -------------

async def index_handler(_request: web.Request) -> web.Response:
    return web.Response(text=_INDEX_HTML, content_type="text/html")


async def stream_handler(request: web.Request) -> web.StreamResponse:
    """GET /stream : MJPEG (multipart/x-mixed-replace), même motif que
    /video dans robot_web/web_bridge_node.py -- une frame à la fois, servie à
    STREAM_FPS, chaque client indépendant. Rien à servir tant qu'aucun
    show() n'est encore passé : ne devrait pas arriver, Face affiche sa
    séquence "default" dès la construction (show_first_frames)."""
    node = request.app["node"]
    interval = 1.0 / STREAM_FPS

    resp = web.StreamResponse(status=200, headers={
        "Content-Type": "multipart/x-mixed-replace; boundary=frame",
        "Cache-Control": "no-cache",
    })
    await resp.prepare(request)
    try:
        while True:
            jpeg = node.snapshot_jpeg()
            if jpeg is not None:
                await resp.write(
                    b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                    + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
            await asyncio.sleep(interval)
    except (ConnectionResetError, asyncio.CancelledError):
        pass  # client parti en cours de flux : normal, rien à logger
    return resp


def build_app(node: FaceSimNode) -> web.Application:
    app = web.Application()
    app["node"] = node
    app.router.add_get("/", index_handler)
    app.router.add_get("/stream", stream_handler)
    return app


def main(args=None):
    rclpy.init(args=args)
    node = FaceSimNode()
    try:
        # rclpy.spin dans un thread daemon : voir le pourquoi en tête de
        # fichier. daemon=True -> pas besoin de join() explicite, le thread
        # meurt avec le process (web.run_app est la boucle principale,
        # bloquante).
        spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
        spin_thread.start()
        web.run_app(build_app(node), host="0.0.0.0", port=node.face_port)
    except Exception as e:
        logging.error(e, exc_info=True)
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    main()
