"""Décision pure du coupe-webcam (topic `camera_enable`) — SANS ROS, testée par
test/unit/test_camera_switch.py.

POURQUOI un module à part : le node est fin (I/O seulement) ; la seule logique
du coupe-webcam est « que veut dire ce payload ? », et elle doit être gravée
par des tests sans cv2 ni rclpy."""
import json
from typing import Optional

# Valeurs de l'état publié sur `camera_state` (et de la commande reconnue).
CAMERA_ON = "on"
CAMERA_OFF = "off"


def decode_camera_enable(raw) -> Optional[bool]:
    """Payload StringTime de `camera_enable` -> True (allumer), False (couper),
    None (valeur inconnue : le node logge un warning et RIEN ne change).

    Tolérant comme `designate` : "on"/"off" bruts, JSON "\\"on\\"", true/false,
    1/0, "1"/"0". Casse et espaces ignorés pour les chaînes. Une valeur
    inconnue ne doit JAMAIS retomber sur un défaut : couper la webcam par
    erreur ou, pire, la rallumer par erreur (vie privée), est un vrai défaut."""
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        value = raw
    if isinstance(value, str):
        value = value.strip().lower()
    # `True == 1` en Python : les tuples couvrent bool et entiers JSON.
    # Les flottants (1.0) sont refusés exprès (pas un vrai booléen).
    if isinstance(value, float):
        return None
    if value in ("on", True, 1, "1"):
        return True
    if value in ("off", False, 0, "0"):
        return False
    return None
