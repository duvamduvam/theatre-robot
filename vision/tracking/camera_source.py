"""Choix de la SOURCE d'images de la perception (topic `camera_source`) — SANS
ROS, testé par vision/tests/unit/test_camera_source.py.

POURQUOI : en répétition simulée, on veut choisir à chaud entre la webcam du PC
(défaut, comportement historique) et la caméra du robot simulé dans Gazebo
(sensor_msgs/Image sur `sim_camera_topic`). Le node reste fin (I/O seulement) ;
ici vivent les décisions et la conversion de pixels, gravées par des tests.
cv_bridge n'est PAS installé dans le conteneur vision : conversion à la main."""
import json
from typing import Optional

import numpy as np

SOURCE_WEBCAM = "webcam"
SOURCE_GAZEBO = "gazebo"


def decode_camera_source(raw) -> Optional[str]:
    """Payload StringTime de `camera_source` -> "webcam" | "gazebo" | None
    (inconnu : le node logge un warning et RIEN ne change). Tolérant comme
    `camera_enable` : brut ou JSON, casse et espaces ignorés. Aucune valeur
    inconnue ne retombe sur un défaut (changer de source par erreur coupe la
    perception ou rallume la webcam)."""
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        value = raw
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    return value if value in (SOURCE_WEBCAM, SOURCE_GAZEBO) else None


def available_sources(sim_camera_topic: str) -> list:
    """Sources proposables : Gazebo seulement si un topic est configuré (banc PC)."""
    sources = [SOURCE_WEBCAM]
    if (sim_camera_topic or "").strip():
        sources.append(SOURCE_GAZEBO)
    return sources


def resolve_source(current: str, requested: str, sim_camera_topic: str) -> str:
    """Source à adopter : `requested` si disponible, sinon `current` inchangée
    (« gazebo » sans sim_camera_topic = refus, la webcam n'est pas touchée)."""
    if requested in available_sources(sim_camera_topic):
        return requested
    return current


def image_to_bgr(encoding: str, width: int, height: int, step: int, data) -> np.ndarray:
    """sensor_msgs/Image `rgb8` -> tableau (height, width, 3) uint8 BGR,
    contigu, comme ce que renvoie cv2.VideoCapture.read(). `step` = octets par
    ligne, peut dépasser width*3 (remplissage de fin de ligne, à jeter).
    ValueError pour tout autre encoding ou des dimensions incohérentes : le
    node refuse proprement plutôt que d'alimenter la détection en bruit."""
    if encoding != "rgb8":
        raise ValueError(f"encoding {encoding!r} non géré (rgb8 seulement)")
    if width <= 0 or height <= 0 or step < width * 3:
        raise ValueError(f"dimensions invalides : {width}x{height}, step={step}")
    buffer = np.frombuffer(data, dtype=np.uint8)
    if buffer.size < step * height:
        raise ValueError(f"données trop courtes : {buffer.size} < {step * height}")
    rows = buffer[:step * height].reshape(height, step)
    rgb = rows[:, :width * 3].reshape(height, width, 3)
    return np.ascontiguousarray(rgb[:, :, ::-1])


def camera_is_partner_effective(base_flag: bool, source: str) -> bool:
    """Le drapeau « la caméra filme le partenaire » (banc sim + partenaire connu)
    exige AUSSI la webcam du PC : la caméra Gazebo filme le décor simulé, pas
    la personne devant l'écran."""
    return bool(base_flag) and source == SOURCE_WEBCAM
