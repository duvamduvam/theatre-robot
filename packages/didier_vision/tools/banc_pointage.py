#!/usr/bin/env python3
"""Banc de POINTAGE : un modèle de vision sait-il montrer l'objet dont Didier parle ?

POURQUOI (étude docs/etudes/etude-objets-vus-et-carte.md, 17/11) : la tête parle
de ce qu'elle voit, la régie déplace vers un nom de la carte — deux sources de
vérité. La voie (b) de l'étude demande à un modèle de vision le POINT (ou la
boîte) de l'objet nommé, puis le projette au sol par la pose de la caméra.
Ce banc mesure cette voie sur la caméra Gazebo du monde `chantiers`, où la
vérité est connue (géométrie du SDF + pose ground_truth) : taux de bonne
désignation, erreur d'azimut, erreur de projection au sol, latence, coût.

Quatre étapes, quatre sous-commandes (les résultats bruts vont HORS dépôt,
défaut ~/tmp/banc-pointage/) :

  preparer   (PC, stdlib + yaml)  poses + vérité des objets -> plan.json
  capturer   (conteneur didier-sim-monde, rclpy + cv2 + gz) téléporte le robot
             à chaque pose, prend l'image de camera/image_raw et la pose vraie
  interroger (PC, stdlib)  une question par (image, objet, modèle, variante),
             via OpenRouter ; clé lue dans la variable OPENROUTER_API_KEY,
             jamais affichée ni écrite ; plafond de dépense dur (--budget-usd)
  mesurer    (PC, stdlib)  projection au sol, comparaison à la vérité, tableau

    python3 tools/banc_pointage.py preparer --depot <racine du dépôt>
    docker exec -i didier-sim-monde python3 - capturer --plan /home/ros2_ws/log/banc/plan.json \
        --sortie /home/ros2_ws/log/banc < tools/banc_pointage.py
    OPENROUTER_API_KEY=… python3 tools/banc_pointage.py interroger
    python3 tools/banc_pointage.py mesurer

SIM-ONLY, outil d'atelier : rien ici ne publie sur un topic de mouvement (la
capture téléporte le modèle par le service gz `set_pose`, chaîne roues absente).

Géométrie (caméra du buste, dadou_robot_gz.urdf.xacro) : axe optique HORIZONTAL
quand le robot est à plat, hauteur CAM_HEIGHT_M, champ horizontal CAM_HFOV_RAD,
image 640×480, 15,5 cm en avant de l'origine du modèle. Robot à plat, un pixel
(u, v) sous l'horizon touche le sol à
    avant = h·f / (v − cy)     gauche = avant·(cx − u) / f
— la distance n'existe que SOUS l'horizon, et son erreur croît comme d²
(d²/(h·f) mètres par pixel : 4 cm à 5 m, 17 cm à 10 m, 68 cm à 20 m). Le code
projette avec la pose 3D complète de la caméra (roulis, tangage, hauteur) : un
tangage ignoré de 1,6° fausse la distance de 5 m à 20 m (vécu le 17/11).
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import pathlib
import re
import statistics
import sys
import time

# -- Caméra du buste en sim (dadou_robot_gz.urdf.xacro, lue le 17/11) ----------
CAM_WIDTH, CAM_HEIGHT = 640, 480
CAM_HFOV_RAD = 1.047
BASE_Z_M = 0.23          # origine du modèle au-dessus du sol (wheel_radius 0,13 + base_height/2)
CAM_UP_M = 0.83          # base_height/2 0,10 + torso_height 0,70 + 0,03 (lu : gz model -l camera_link)
CAM_FORWARD_M = 0.155    # torso_length/2 + 0,015, en avant de l'origine du modèle
CAM_HEIGHT_M = BASE_Z_M + CAM_UP_M   # 1,06 m, robot à plat
FOCAL_PX = (CAM_WIDTH / 2) / math.tan(CAM_HFOV_RAD / 2)
CX, CY = CAM_WIDTH / 2, CAM_HEIGHT / 2

# -- Plan du banc --------------------------------------------------------------
# Poses (x, y, cap °) le long de l'itinéraire `chantiers` : caps variés pour
# que les objets ne soient pas toujours au même endroit de l'image.
POSES = [
    # vues « en marche », le long du Mail puis du quai (objets de 6 à 25 m)
    (12.0, 0.5, 10), (20.0, 0.0, 15), (22.0, 0.0, -10), (26.0, 0.0, 0), (31.0, 0.0, 10),
    (38.0, 0.0, 0), (52.0, 0.0, 0), (66.0, 0.0, 20), (90.0, 14.0, 35), (96.0, 19.0, 40),
    (118.0, 33.0, 30),
    # vues « tourné vers l'objet », à 4-5 m (le cas « le banc à gauche » après un pivot)
    (14.0, 0.0, 25), (23.5, 0.0, 45), (28.0, 0.0, -40), (32.5, 0.0, 25), (55.0, 0.0, 40),
    (60.0, -0.5, -20), (69.0, 2.0, 30), (88.5, 15.0, 45), (94.5, 14.5, 20),
]
# Un objet est une CIBLE s'il est dans le champ avec marge, ni trop près (sa
# base sort de l'image sous 2,45 m) ni trop loin, et pas un bâtiment.
TARGET_MAX_BEARING_DEG = 25.0
TARGET_MIN_M, TARGET_MAX_M = 2.6, 25.0
TARGET_MAX_RADIUS_M = 4.0
TARGETS_PER_IMAGE = 3     # le plus proche, le médian, le plus lointain du champ
# Objets À PLAT au sol : ils ne masquent rien.
FLAT_OBJECTS = frozenset({"flaque", "rails", "loire", "pelouse"})
# Question PIÈGE (la panne du 15/11 : « le banc est là, bien en vue », il était
# à 22 m) : un objet de la carte qui n'est PAS dans l'image (hors champ, loin).
ABSENT_MIN_M = 12.0
ABSENT_MIN_BEARING_DEG = 50.0   # le champ s'arrête à ±30°

MODEL_NAME = "dadou_robot"      # modèle Gazebo du robot
# Capture refusée si le robot n'est pas À PLAT (hauteur et inclinaison du modèle).
LEVEL_TOL_M, LEVEL_TOL_DEG = 0.005, 0.2

MODELS = ["google/gemini-3.7-flash", "google/gemini-3.5-flash", "qwen/qwen3-vl-30b-a3b-instruct"]
VARIANTS = ("pied", "boite")
# Modèles qui rendent [x, y] malgré la consigne [y, x] : mesurés DEUX fois (tel
# que demandé, puis relus dans leur ordre) — l'écart est un résultat du banc.
XY_NATIVE_MODELS = frozenset({"qwen/qwen3-vl-30b-a3b-instruct"})
XY_SUFFIX = " (relu en [x, y])"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_ENV = "OPENROUTER_API_KEY"
REQUEST_TIMEOUT_S = 40.0
MAX_TOKENS = 400

PROMPTS = {
    "pied": (
        "Voici l'image de la caméra d'un robot (640×480). Objet cherché : « {desc} ».\n"
        "S'il est visible, donne le point où il TOUCHE LE SOL (le milieu de sa base), en "
        "[y, x] normalisé de 0 à 1000 (y = 0 en haut de l'image, x = 0 à gauche).\n"
        "Réponds UNIQUEMENT par un objet JSON, sans texte autour : "
        "{{\"visible\": true, \"point\": [y, x]}} ou {{\"visible\": false}} s'il n'est pas dans l'image."),
    "boite": (
        "Voici l'image de la caméra d'un robot (640×480). Objet cherché : « {desc} ».\n"
        "S'il est visible, donne sa boîte englobante en [ymin, xmin, ymax, xmax] normalisé de 0 à "
        "1000 (y = 0 en haut de l'image, x = 0 à gauche).\n"
        "Réponds UNIQUEMENT par un objet JSON, sans texte autour : "
        "{{\"visible\": true, \"box_2d\": [ymin, xmin, ymax, xmax]}} ou {{\"visible\": false}} "
        "s'il n'est pas dans l'image."),
}

# Question OUVERTE (ajoutée après la série A du 17/11 : interrogé sur un objet
# ABSENT, un modèle désigne volontiers un sosie — la flaque pour « table très
# basse », le plot pour « bagues géantes »). Ici on ne suggère aucun nom : une
# question par image, le modèle dit ce qu'il voit.
INVENTORY = "inventaire"
INVENTORY_OBJECT = "*"
INVENTORY_MAX_TOKENS = 900
INVENTORY_PROMPT = (
    "Voici l'image de la caméra d'un robot (640×480), dans une rue piétonne.\n"
    "Liste les objets distincts visibles (mobilier, objets posés au sol, véhicules, animaux ; PAS les "
    "bâtiments, ni le sol, ni le ciel), 8 au plus, du plus proche au plus lointain.\n"
    "Réponds UNIQUEMENT par un tableau JSON, sans texte autour : "
    "[{\"nom\": \"<2 à 4 mots en français>\", \"box_2d\": [ymin, xmin, ymax, xmax]}] "
    "avec des coordonnées normalisées de 0 à 1000 (y = 0 en haut, x = 0 à gauche).")

# Désignation « bonne » : l'azimut du point tombe dans l'emprise angulaire de
# l'objet, à cette tolérance près.
BEARING_TOLERANCE_DEG = 3.0
# Rayon plongeant de moins de ça sous l'horizontale : pas de distance (division par ~0).
HORIZON_MARGIN_DEG = 0.3
DISTANCE_BINS = ((0.0, 6.0), (6.0, 12.0), (12.0, 99.0))

DEFAULT_DIR = pathlib.Path.home() / "tmp" / "banc-pointage"


# == Géométrie PURE ============================================================

def wrap_deg(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


def rotation(roll: float, pitch: float, yaw: float):
    """Matrice Rz(yaw)·Ry(pitch)·Rx(roll) (REP 103 : tangage + = le nez plonge)."""
    cr, sr, cp, sp, cy, sy = (math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch),
                              math.cos(yaw), math.sin(yaw))
    return ((cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
            (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
            (-sp, cp * sr, cp * cr))


def camera_from_base(base):
    """Pose du modèle (x, y, z, roulis, tangage, lacet) -> pose de la CAMÉRA
    (même forme), par le décalage fixe du link (CAM_FORWARD_M, 0, CAM_UP_M)."""
    x, y, z, roll, pitch, yaw = base
    R = rotation(roll, pitch, yaw)
    off = (CAM_FORWARD_M, 0.0, CAM_UP_M)
    return (x + sum(R[0][k] * off[k] for k in range(3)), y + sum(R[1][k] * off[k] for k in range(3)),
            z + sum(R[2][k] * off[k] for k in range(3)), roll, pitch, yaw)


def nominal_camera(pose):
    """Pose 2D (x, y, lacet rad) d'un robot À PLAT -> pose de la caméra."""
    return camera_from_base((pose[0], pose[1], BASE_Z_M, 0.0, 0.0, pose[2]))


def relative(cam, xy):
    """(distance au sol m, azimut ° + = gauche) d'un point du monde vu de la caméra."""
    dx, dy = xy[0] - cam[0], xy[1] - cam[1]
    return math.hypot(dx, dy), wrap_deg(math.degrees(math.atan2(dy, dx) - cam[5]))


def pixel_ray(cam, u: float, v: float):
    """Rayon du pixel (u, v) dans le repère MONDE (non normé)."""
    R = rotation(cam[3], cam[4], cam[5])
    ray = (1.0, (CX - u) / FOCAL_PX, -(v - CY) / FOCAL_PX)   # avant, gauche, haut
    return tuple(sum(R[i][k] * ray[k] for k in range(3)) for i in range(3))


def pixel_bearing_deg(cam, u: float, v: float) -> float:
    """Azimut (° + = gauche, relatif au cap de la caméra) du pixel."""
    ray = pixel_ray(cam, u, v)
    return wrap_deg(math.degrees(math.atan2(ray[1], ray[0]) - cam[5]))


def pixel_to_ground(cam, u: float, v: float):
    """Pixel -> point (x, y) du SOL (z = 0) dans le monde, ou None si le rayon
    ne plonge pas d'au moins HORIZON_MARGIN_DEG sous l'horizontale."""
    ray = pixel_ray(cam, u, v)
    horizontal = math.hypot(ray[0], ray[1])
    if ray[2] >= -math.tan(math.radians(HORIZON_MARGIN_DEG)) * horizontal:
        return None
    t = -cam[2] / ray[2]
    return cam[0] + t * ray[0], cam[1] + t * ray[1]


def ground_to_pixel(cam, xy):
    """Point du sol (monde) -> pixel (u, v), ou None s'il est derrière la caméra."""
    R = rotation(cam[3], cam[4], cam[5])
    d = (xy[0] - cam[0], xy[1] - cam[1], -cam[2])
    c = tuple(sum(R[k][i] * d[k] for k in range(3)) for i in range(3))   # R transposée
    if c[0] <= 0.05:
        return None
    return CX - FOCAL_PX * c[1] / c[0], CY - FOCAL_PX * c[2] / c[0]


def norm_to_pixel(y: float, x: float):
    """[y, x] normalisé 0-1000 -> (u, v) pixels."""
    return x / 1000.0 * CAM_WIDTH, y / 1000.0 * CAM_HEIGHT


# == preparer : poses + vérité =================================================

def load_objects(depot: pathlib.Path) -> dict:
    """{nom: {x, y, r, desc}} : centre et rayon d'emprise depuis la géométrie
    du monde (collisions, à défaut visuels : flaque, rails), comme
    compute_tours.py ; `desc` = ce qu'on VOIT (itinéraire)."""
    import xml.etree.ElementTree as ET

    import yaml
    sys.path.insert(0, str(depot / "packages" / "didier_rehearsal" / "tools"))
    import compute_tours as ct

    world = ET.parse(str(depot / "packages/didier_sim/worlds/chantiers.sdf")).getroot().find("world")
    identity = ([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], (0.0, 0.0, 0.0))
    discs = {}
    for model in world.findall("model"):
        m = ct._compose(identity, model)
        for kind in ("collision", "visual"):
            found = []
            for link in model.findall("link"):
                lk = ct._compose(m, link)
                for el in link.findall(kind):
                    R, t = ct._compose(lk, el)
                    found.append((t[0], t[1], ct._extent(el.find("geometry"), R)))
            if found:
                discs[model.get("name")] = found
                break
    route = yaml.safe_load((depot / "packages/didier_rehearsal/config/chantiers.yaml").read_text())
    objects = {}
    for poi in route["pois"]:
        own = discs.get(poi["name"])
        if not own:
            continue
        x0, x1, y0, y1 = ct._bbox(own)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        objects[poi["name"]] = {
            "x": round(cx, 3), "y": round(cy, 3),
            "r": round(max(math.hypot(x - cx, y - cy) + e for x, y, e in own), 3),
            "desc": poi.get("desc", poi["name"])}
    return objects


def plan_queries(objects: dict) -> list:
    """Pour chaque pose : les cibles (la plus proche, la médiane et la plus
    lointaine du champ, non masquées par un objet plus proche) et une question
    piège (objet de la carte hors de l'image, tiré à tour de rôle)."""
    images = []
    for i, (x, y, yaw_deg) in enumerate(POSES):
        pose = nominal_camera((x, y, math.radians(yaw_deg)))
        seen = []
        for name, o in objects.items():
            d, b = relative(pose, (o["x"], o["y"]))
            half = math.degrees(math.atan2(o["r"], max(d, 0.1)))
            seen.append({"name": name, "d": d, "b": b, "half": half, "r": o["r"]})
        candidates = []
        for s in seen:
            if not (TARGET_MIN_M <= s["d"] - s["r"] and s["d"] <= TARGET_MAX_M
                    and abs(s["b"]) <= TARGET_MAX_BEARING_DEG and s["r"] <= TARGET_MAX_RADIUS_M):
                continue
            masked = any(o is not s and o["d"] < s["d"] and o["r"] <= TARGET_MAX_RADIUS_M
                         and o["name"] not in FLAT_OBJECTS
                         and abs(wrap_deg(o["b"] - s["b"])) < o["half"] + s["half"] for o in seen)
            if not masked:
                candidates.append(s)
        candidates.sort(key=lambda s: s["d"])
        picks = sorted({0, len(candidates) // 2, len(candidates) - 1}) if candidates else []
        targets = [candidates[k] for k in picks]
        far = sorted((s for s in seen if s["d"] >= ABSENT_MIN_M and abs(s["b"]) >= ABSENT_MIN_BEARING_DEG
                      and s["r"] <= TARGET_MAX_RADIUS_M), key=lambda s: s["name"])
        absent = far[(7 * i) % len(far)]["name"] if far else None
        images.append({
            "image": f"pose{i:02d}", "pose": [x, y, yaw_deg],
            "targets": [{"name": t["name"], "distance_m": round(t["d"], 2), "bearing_deg": round(t["b"], 2),
                         "half_deg": round(t["half"], 2)} for t in targets[:TARGETS_PER_IMAGE]],
            "absent": absent})
    return images


def cmd_preparer(args) -> int:
    depot = pathlib.Path(args.depot).resolve() if args.depot else pathlib.Path(__file__).resolve().parents[3]
    objects = load_objects(depot)
    plan = {"camera": {"width": CAM_WIDTH, "height": CAM_HEIGHT, "hfov_rad": CAM_HFOV_RAD,
                       "up_m": CAM_UP_M, "forward_m": CAM_FORWARD_M, "base_z_m": BASE_Z_M},
            "objects": objects, "images": plan_queries(objects)}
    out = pathlib.Path(args.dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    n_pos = sum(len(i["targets"]) for i in plan["images"])
    n_neg = sum(1 for i in plan["images"] if i["absent"])
    print(f"plan : {len(plan['images'])} images, {n_pos} cibles, {n_neg} pièges "
          f"-> {(n_pos + n_neg) * len(MODELS) * len(VARIANTS)} appels prévus")
    return 0


# == capturer : dans le conteneur didier-sim-monde ==============================

def cmd_capturer(args) -> int:
    import subprocess

    import cv2
    import numpy as np
    import rclpy
    from nav_msgs.msg import Odometry
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Image

    plan = json.loads(pathlib.Path(args.plan).read_text())
    out = pathlib.Path(args.sortie)
    out.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    # Namespace du robot (lot L1b) : topics RELATIFS, comme tout le dépôt.
    node = rclpy.create_node("banc_pointage_capture", namespace=args.robot)
    last = {"image": None, "odom": None, "n_image": 0}

    def on_image(msg):
        last["image"], last["n_image"] = msg, last["n_image"] + 1

    def on_odom(msg):
        last["odom"] = msg

    node.create_subscription(Image, "camera/image_raw", on_image, qos_profile_sensor_data)
    node.create_subscription(Odometry, "ground_truth/odom", on_odom, 10)

    def spin(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.05)

    def model_pose():
        """Pose 3D VRAIE du modèle, lue dans Gazebo : (x, y, z, roulis, tangage,
        lacet). Pas ground_truth/odom : il est publié en 2D (z = 0, lacet seul) —
        le 17/11, une première capture téléportée à ce z = 0 a enfoncé le robot
        dans le sol ; il en est ressorti cabré de 1,6°, et les distances projetées
        à 20 m étaient fausses de 5 m."""
        text = subprocess.run(["gz", "model", "-m", MODEL_NAME, "-p"], check=True,
                              capture_output=True, text=True).stdout
        numbers = re.findall(r"\[([-0-9.e ]+)\]", text)
        xyz, rpy = ([float(n) for n in group.split()] for group in numbers[-2:])
        return (*xyz, *rpy)

    spin(3.0)
    if last["odom"] is None or last["image"] is None:
        print("capture : pas d'image ou pas de vérité terrain — la sim tourne-t-elle ?")
        return 1
    done = []
    for item in plan["images"]:
        x, y, yaw_deg = item["pose"]
        yaw = math.radians(yaw_deg)
        req = (f'name: "{MODEL_NAME}", position: {{x: {x}, y: {y}, z: {BASE_Z_M}}}, '
               f'orientation: {{z: {math.sin(yaw / 2)}, w: {math.cos(yaw / 2)}}}')
        subprocess.run(["gz", "service", "-s", "/world/stage/set_pose", "--reqtype", "gz.msgs.Pose",
                        "--reptype", "gz.msgs.Boolean", "--timeout", "3000", "--req", req],
                       check=True, capture_output=True)
        spin(2.5)                      # le robot se pose, le rendu rattrape
        seen = last["n_image"]
        while last["n_image"] < seen + 2:   # une image rendue APRÈS la stabilisation
            spin(0.2)
        msg, base = last["image"], model_pose()
        if abs(base[2] - BASE_Z_M) > LEVEL_TOL_M or max(abs(base[3]), abs(base[4])) > math.radians(LEVEL_TOL_DEG):
            print(f"{item['image']} : robot PAS à plat {base} — capture refusée")
            return 1
        channels = len(msg.data) // (msg.width * msg.height)
        frame = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(msg.height, msg.width, channels)
        if msg.encoding.startswith("rgb"):
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(out / f"{item['image']}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        done.append({"image": item["image"], "asked": item["pose"], "base": [round(c, 5) for c in base],
                     "camera": [round(c, 5) for c in camera_from_base(base)],
                     "size": [msg.width, msg.height]})
        print(f"{item['image']} : demandé {item['pose']} -> vrai ({base[0]:.2f}, {base[1]:.2f}, z {base[2]:.3f}, "
              f"tangage {math.degrees(base[4]):+.2f}°, cap {math.degrees(base[5]):.1f}°)")
    (out / "captures.json").write_text(json.dumps(done, indent=1))
    node.destroy_node()
    rclpy.shutdown()
    return 0


# == interroger : OpenRouter ===================================================

def parse_answer(text: str):
    """Réponse du modèle -> dict JSON ou None (tolère les clôtures ```json)."""
    if not isinstance(text, str):
        return None
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def ask(model: str, prompt: str, jpeg: bytes, key: str, max_tokens: int = MAX_TOKENS) -> dict:
    """Un appel non streamé. Rend {text, latency_s, cost_usd, tokens, error}."""
    import urllib.error
    import urllib.request
    body = {
        "model": model, "max_tokens": max_tokens, "temperature": 0,
        "usage": {"include": True},
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}}]}]}
    if model.startswith("google/"):
        body["reasoning"] = {"effort": "minimal"}   # la réflexion ne sert pas à pointer, elle coûte
    request = urllib.request.Request(
        OPENROUTER_URL, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}: {exc.read()[:300].decode(errors='replace')}",
                "latency_s": time.monotonic() - start, "cost_usd": 0.0}
    except Exception as exc:  # réseau, délai, JSON : une ligne d'erreur, le banc continue
        return {"error": f"{type(exc).__name__}: {exc}", "latency_s": time.monotonic() - start, "cost_usd": 0.0}
    latency = time.monotonic() - start
    if "error" in payload:
        return {"error": json.dumps(payload["error"])[:300], "latency_s": latency, "cost_usd": 0.0}
    usage = payload.get("usage") or {}
    return {"text": payload["choices"][0]["message"].get("content"), "latency_s": latency,
            "cost_usd": float(usage.get("cost") or 0.0),
            "tokens": [usage.get("prompt_tokens"), usage.get("completion_tokens")]}


def cmd_interroger(args) -> int:
    key = os.environ.get(KEY_ENV)
    if not key:
        print(f"interroger : variable {KEY_ENV} absente (jamais en argument, jamais affichée)")
        return 2
    folder = pathlib.Path(args.dir)
    plan = json.loads((folder / "plan.json").read_text())
    results_path = folder / "reponses.jsonl"
    known, spent = set(), 0.0
    if results_path.exists():      # reprise : un appel déjà payé n'est jamais refait
        for line in results_path.read_text().splitlines():
            row = json.loads(line)
            spent += row.get("cost_usd", 0.0)
            if not row.get("error"):
                known.add((row["image"], row["object"], row["model"], row["variant"]))
    models = args.models.split(",") if args.models else MODELS
    calls = 0
    with results_path.open("a") as out:
        for item in plan["images"]:
            jpeg = (folder / f"{item['image']}.jpg").read_bytes()
            asks = [(t["name"], True, VARIANTS) for t in item["targets"]]
            if item["absent"]:
                asks.append((item["absent"], False, VARIANTS))
            asks.append((INVENTORY_OBJECT, True, (INVENTORY,)))
            for name, present, variants in asks:
                for model in models:
                    for variant in variants:
                        if (item["image"], name, model, variant) in known:
                            continue
                        if spent >= args.budget_usd:
                            print(f"BUDGET atteint ({spent:.3f} $) : arrêt après {calls} appels")
                            return 3
                        if args.limit and calls >= args.limit:
                            print(f"limite de {args.limit} appels atteinte ({spent:.4f} $)")
                            return 0
                        if variant == INVENTORY:
                            answer = ask(model, INVENTORY_PROMPT, jpeg, key, INVENTORY_MAX_TOKENS)
                        else:
                            answer = ask(model, PROMPTS[variant].format(desc=plan["objects"][name]["desc"]),
                                         jpeg, key)
                        calls += 1
                        spent += answer.get("cost_usd", 0.0)
                        row = {"image": item["image"], "object": name, "present": present,
                               "model": model, "variant": variant, **answer}
                        out.write(json.dumps(row, ensure_ascii=False) + "\n")
                        out.flush()
                        shown = answer.get("error") or (answer.get("text") or "").strip().replace("\n", " ")[:70]
                        print(f"{item['image']} {name:16s} {model.split('/')[-1]:28s} {variant:5s} "
                              f"{answer['latency_s']:.2f}s {shown}")
    print(f"{calls} appels, dépense cumulée du banc : {spent:.4f} $")
    return 0


# == mesurer ===================================================================

def answer_pixel(variant: str, value: dict, xy_order: bool = False):
    """Réponse analysée -> (u, v) du point au SOL revendiqué, ou None.
    `xy_order` : lire la réponse dans l'ordre [x, y] / [xmin, ymin, xmax, ymax]
    (celui que Qwen rend malgré la consigne, constaté le 17/11)."""
    try:
        if variant == "pied":
            y, x = value["point"][::-1] if xy_order else value["point"]
        else:
            box = value["box_2d"]
            _ymin, xmin, ymax, xmax = (box[1], box[0], box[3], box[2]) if xy_order else box
            y, x = ymax, (xmin + xmax) / 2.0     # milieu du bord BAS de la boîte
        y, x = float(y), float(x)
    except (KeyError, TypeError, ValueError):
        return None
    if not (0.0 <= y <= 1000.0 and 0.0 <= x <= 1000.0):
        return None
    return norm_to_pixel(y, x)


def measure_row(row: dict, plan: dict, poses: dict, xy_order: bool = False):
    """Une réponse -> mesures (dict) ; None si l'appel a échoué."""
    if row.get("error"):
        return None
    value = parse_answer(row.get("text"))
    out = {"present": row["present"], "latency_s": row["latency_s"], "cost_usd": row.get("cost_usd", 0.0),
           "parsed": value is not None, "said_visible": bool(value and value.get("visible") is True)}
    if not row["present"] or not out["said_visible"]:
        return out
    pixel = answer_pixel(row["variant"], value, xy_order)
    if pixel is None:
        out["said_visible"], out["parsed"] = False, False
        return out
    cam = tuple(poses[row["image"]])
    obj = plan["objects"][row["object"]]
    d, bearing = relative(cam, (obj["x"], obj["y"]))
    half = math.degrees(math.atan2(obj["r"], d))
    err_b = wrap_deg(pixel_bearing_deg(cam, *pixel) - bearing)
    out.update(distance_m=d, bearing_err_deg=err_b,
               designated=abs(err_b) <= half + BEARING_TOLERANCE_DEG)
    ground = pixel_to_ground(cam, *pixel)
    if ground is not None:
        err = math.hypot(ground[0] - obj["x"], ground[1] - obj["y"])
        out.update(ground_err_m=err, ground_err_beyond_m=max(0.0, err - obj["r"]),
                   range_err_m=math.hypot(ground[0] - cam[0], ground[1] - cam[1]) - d)
    return out


def parse_inventory(text):
    """Réponse d'inventaire -> liste de (nom, [ymin, xmin, ymax, xmax]) valides."""
    if not isinstance(text, str):
        return []
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return []
    try:
        value = json.loads(match.group(0))
    except ValueError:
        return []
    items = []
    for entry in value if isinstance(value, list) else []:
        box = entry.get("box_2d") if isinstance(entry, dict) else None
        if isinstance(box, list) and len(box) == 4 and all(isinstance(c, (int, float)) for c in box):
            items.append((str(entry.get("nom", "")), [float(c) for c in box]))
    return items


def measure_inventory(row: dict, plan: dict, poses: dict, xy_order: bool = False) -> dict:
    """Inventaire d'une image -> pour chaque CIBLE du plan : retrouvée (une
    boîte dont le milieu tombe dans son emprise angulaire) ? sous quel nom ?
    à quelle erreur au sol (milieu du bord bas de la boîte) ?"""
    cam = tuple(poses[row["image"]])
    items = parse_inventory(row.get("text"))
    targets = next(i["targets"] for i in plan["images"] if i["image"] == row["image"])
    found = []
    for target in targets:
        obj = plan["objects"][target["name"]]
        d, bearing = relative(cam, (obj["x"], obj["y"]))
        half = math.degrees(math.atan2(obj["r"], d))
        best = None
        for name, box in items:
            pixel = answer_pixel("boite", {"box_2d": box}, xy_order)
            if pixel is None:
                continue
            err_b = abs(wrap_deg(pixel_bearing_deg(cam, *pixel) - bearing))
            if err_b <= half + BEARING_TOLERANCE_DEG and (best is None or err_b < best[0]):
                ground = pixel_to_ground(cam, *pixel)
                err = math.hypot(ground[0] - obj["x"], ground[1] - obj["y"]) if ground else None
                best = (err_b, name, err)
        found.append({"target": target["name"], "distance_m": d, "found": best is not None,
                      "label": best[1] if best else None, "ground_err_m": best[2] if best else None})
    return {"n_items": len(items), "targets": found, "latency_s": row["latency_s"],
            "cost_usd": row.get("cost_usd", 0.0)}


def report_inventory(rows_by_model: dict, summary: list) -> None:
    for model, rows in sorted(rows_by_model.items()):
        targets = [t for r in rows for t in r["targets"]]
        found = [t for t in targets if t["found"]]
        ground = [t["ground_err_m"] for t in found if t["ground_err_m"] is not None]
        near = [t for t in targets if t["distance_m"] < 12.0]
        lat = [r["latency_s"] for r in rows]
        line = {"model": model, "variant": INVENTORY, "calls": len(rows),
                "items_med": statistics.median(r["n_items"] for r in rows),
                "targets": len(targets), "found": len(found),
                "targets_near": len(near), "found_near": sum(1 for t in near if t["found"]),
                "ground_err_med_m": statistics.median(ground) if ground else None,
                "latency_med_s": statistics.median(lat), "latency_p90_s": _p90(lat),
                "cost_per_call_usd": sum(r["cost_usd"] for r in rows) / len(rows),
                "labels": sorted({f"{t['target']} -> {t['label']}" for t in found})}
        summary.append(line)
        print(f"\n{model} [{INVENTORY}] — {len(rows)} images, {line['items_med']:g} objets listés (médiane)")
        print(f"  cibles du plan retrouvées : {len(found)}/{len(targets)} ({_pct(len(found), len(targets))}) ; "
              f"à moins de 12 m : {line['found_near']}/{len(near)} ({_pct(line['found_near'], len(near))}) ; "
              f"erreur au sol médiane {_med(ground)} m")
        print(f"  latence médiane {line['latency_med_s']:.2f} s, p90 {line['latency_p90_s']:.2f} s ; "
              f"coût {line['cost_per_call_usd'] * 1000:.3f} m$ / appel")
        print("  noms donnés : " + " ; ".join(line["labels"]))


def _pct(part, whole) -> str:
    return f"{100.0 * part / whole:.0f} %" if whole else "—"


def _med(values) -> str:
    return f"{statistics.median(values):.2f}" if values else "—"


def _p90(values) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(math.ceil(0.9 * len(ordered))) - 1)]


def cmd_mesurer(args) -> int:
    folder = pathlib.Path(args.dir)
    plan = json.loads((folder / "plan.json").read_text())
    poses = {c["image"]: c["camera"] for c in json.loads((folder / "captures.json").read_text())}
    groups, errors, total_cost, total_calls, inventories = {}, {}, 0.0, 0, {}
    for line in (folder / "reponses.jsonl").read_text().splitlines():
        row = json.loads(line)
        key = (row["model"], row["variant"])
        total_calls += 1
        total_cost += row.get("cost_usd", 0.0)
        if row["variant"] == INVENTORY:
            if row.get("error"):
                errors[key] = errors.get(key, 0) + 1
                continue
            inventories.setdefault(row["model"], []).append(measure_inventory(row, plan, poses))
            if row["model"] in XY_NATIVE_MODELS:
                inventories.setdefault(row["model"] + XY_SUFFIX, []).append(
                    measure_inventory(row, plan, poses, xy_order=True))
            continue
        measured = measure_row(row, plan, poses)
        if measured is None:
            errors[key] = errors.get(key, 0) + 1
            continue
        groups.setdefault(key, []).append(measured)
        if row["model"] in XY_NATIVE_MODELS:     # seconde lecture, dans SON ordre
            groups.setdefault((row["model"] + XY_SUFFIX, row["variant"]), []).append(
                measure_row(row, plan, poses, xy_order=True))
    summary = []
    for (model, variant), rows in sorted(groups.items()):
        pos = [r for r in rows if r["present"]]
        neg = [r for r in rows if not r["present"]]
        found = [r for r in pos if r["said_visible"] and "bearing_err_deg" in r]
        good = [r for r in found if r["designated"]]
        ground = [r for r in good if "ground_err_m" in r]
        lat = [r["latency_s"] for r in rows]
        line = {
            "model": model, "variant": variant, "calls": len(rows), "errors": errors.get((model, variant), 0),
            "positives": len(pos), "designated": len(good), "said_visible": len(found),
            "negatives": len(neg), "false_seen": sum(1 for r in neg if r["said_visible"]),
            "bearing_abs_med_deg": statistics.median(abs(r["bearing_err_deg"]) for r in good) if good else None,
            "projectable": len(ground),
            "ground_err_med_m": statistics.median(r["ground_err_m"] for r in ground) if ground else None,
            "ground_beyond_med_m": statistics.median(r["ground_err_beyond_m"] for r in ground) if ground else None,
            "bins": {}, "latency_med_s": statistics.median(lat), "latency_p90_s": _p90(lat),
            "cost_per_call_usd": sum(r["cost_usd"] for r in rows) / len(rows)}
        for lo, hi in DISTANCE_BINS:
            inside = [r for r in ground if lo <= r["distance_m"] < hi]
            asked = [r for r in good if lo <= r["distance_m"] < hi]
            line["bins"][f"{lo:g}-{hi:g}"] = {
                "n": len(inside), "designated": len(asked),
                "ground_err_med_m": statistics.median(r["ground_err_m"] for r in inside) if inside else None,
                "range_err_med_m": statistics.median(r["range_err_m"] for r in inside) if inside else None}
        summary.append(line)
        print(f"\n{model} [{variant}] — {len(rows)} réponses, {line['errors']} erreurs d'appel")
        print(f"  bonne désignation : {len(good)}/{len(pos)} ({_pct(len(good), len(pos))}) ; "
              f"dit visible : {len(found)}/{len(pos)} ; piège (objet absent dit visible) : "
              f"{line['false_seen']}/{len(neg)}")
        print(f"  azimut |erreur| médiane : {_med([abs(r['bearing_err_deg']) for r in good])}° ; "
              f"projetables au sol : {len(ground)}/{len(good)}")
        print(f"  erreur au sol médiane : {_med([r['ground_err_m'] for r in ground])} m "
              f"(hors emprise : {_med([r['ground_err_beyond_m'] for r in ground])} m)")
        for name, b in line["bins"].items():
            if b["n"]:
                print(f"    {name:>6} m : n={b['n']:2d}  erreur sol médiane {b['ground_err_med_m']:.2f} m, "
                      f"erreur de distance médiane {b['range_err_med_m']:+.2f} m")
        print(f"  latence médiane {line['latency_med_s']:.2f} s, p90 {line['latency_p90_s']:.2f} s ; "
              f"coût {line['cost_per_call_usd'] * 1000:.3f} m$ / appel")
    report_inventory(inventories, summary)
    print(f"\nTOTAL : {total_calls} appels, {total_cost:.4f} $")
    (folder / "resume.json").write_text(json.dumps(
        {"total_calls": total_calls, "total_cost_usd": total_cost, "lines": summary}, indent=1))
    return 0


def main(argv) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preparer")
    p.add_argument("--depot", default="", help="racine du mono-dépôt (défaut : celle de ce fichier)")
    p.add_argument("--dir", default=str(DEFAULT_DIR))
    p = sub.add_parser("capturer")
    p.add_argument("--plan", required=True)
    p.add_argument("--sortie", required=True)
    p.add_argument("--robot", default=os.environ.get("ROBOT_NAME", "didier"), help="namespace ROS du robot")
    p = sub.add_parser("interroger")
    p.add_argument("--dir", default=str(DEFAULT_DIR))
    p.add_argument("--models", default="")
    p.add_argument("--budget-usd", type=float, default=1.8)
    p.add_argument("--limit", type=int, default=0, help="nombre max d'appels de cette passe (0 = tous)")
    p = sub.add_parser("mesurer")
    p.add_argument("--dir", default=str(DEFAULT_DIR))
    args = parser.parse_args(argv)
    return {"preparer": cmd_preparer, "capturer": cmd_capturer,
            "interroger": cmd_interroger, "mesurer": cmd_mesurer}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
