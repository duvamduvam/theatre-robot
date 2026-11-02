"""Liste GRAVÉE de ce que theatre_contrats reprend de dadou_utils_ros/utils_static.py.

Ajouter ou retirer un nom du contrat exige de toucher CE test (et de vérifier
les trois consommateurs : robot, télécommande, vision). Recompter les imports
réels : tools/inventaire.py (AST — un grep rate les imports multi-lignes).
"""
from theatre_contrats import keys, organs, topics

ORGANES = {
    "AUDIO": "audio", "FACE": "face", "LEFT_ARM": "left_arm", "LEFT_EYE": "left_eye",
    "NECK": "neck", "RELAY": "relay", "RIGHT_ARM": "right_arm", "RIGHT_EYE": "right_eye",
    "ROBOT_LIGHTS": "robot_lights", "WHEELS": "wheels",
}
TOPICS_HORS_ORGANES = {
    "ANIMATION": "animation", "ANIMATION_STATE": "animation_state",
    "EXPRESSION": "expression", "LIGHTS": "lights", "SPEAK": "speak", "SYSTEM": "system",
}
# Nouveaux au lot L1a (anciens littéraux absolus de la vision) : PAS repris de utils_static.
TOPICS_PERCEPTION = {
    "VISION_PERSON": "vision/person", "VISION_PERSON_BOX": "vision/person_box",
    "VISION_STATUS": "vision/status",
}
CLES = {
    "A": "A", "ANGLO": "anglo", "AUDIOS": "audios", "B": "B", "BACKWARD": "backward",
    "BRIGHTNESS": "brightness", "COLOR": "color", "DEFAULT": "default", "DEVICES": "devices",
    "DOWN": "down", "DURATION": "duration", "FACES": "faces", "FORWARD": "forward",
    "INCLINO": "inclino", "JOYSTICK": "self.gamepad", "KEY": "key", "KEYS": "keys",
    "LEFT": "left", "LOOP": "loop", "METHOD": "method", "MODE": "mode", "MOUTH": "mouth",
    "NAME": "name", "NORMAL": "normal", "RANDOM": "random", "RIGHT": "right",
    "SEQUENCES": "sequences", "SPEED": "speed", "STOP": "stop", "TYPE": "type", "UP": "UP",
    "WHEEL_LEFT": "wheel_left", "WHEEL_RIGHT": "wheel_right", "X": "X", "Y": "Y",
}


def _constantes(module):
    return {n: v for n, v in vars(module).items() if n.isupper() and isinstance(v, str)}


def test_organes():
    assert _constantes(organs) == ORGANES
    assert organs.ORGANS == tuple(ORGANES[n] for n in sorted(ORGANES))


def test_topics():
    assert _constantes(topics) == {**ORGANES, **TOPICS_HORS_ORGANES, **TOPICS_PERCEPTION}


def test_cles():
    assert _constantes(keys) == CLES


def test_nombre_de_constantes_reprises():
    # 51 noms repris de utils_static le 2026-11-02 (sur 74 importés par du code :
    # les 23 autres — chemins, logging, plateforme, ORANGE — restent dans la lib).
    assert len(ORGANES) + len(TOPICS_HORS_ORGANES) + len(CLES) == 51


def test_un_nom_une_definition():
    # Un nom défini dans deux modules finirait par diverger.
    assert not set(ORGANES) & set(CLES)
    assert not set(TOPICS_HORS_ORGANES) & set(CLES)
