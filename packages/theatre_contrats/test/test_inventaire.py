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
# Nouveaux au lot A1 (sélecteur de jeu, didier_jeu) : PAS repris de utils_static.
TOPICS_JEU = {
    "JEU_CONSOLE": "jeu/console", "JEU_INTENTION": "jeu/intention",
    "JEU_CHAT_MOVE": "jeu/chat_move", "JEU_JOURNAL": "jeu/journal",
}
# Nouveaux au lot L1c (le robot publie catalogue + sha) : PAS repris de utils_static.
TOPICS_CATALOGUE = {"CATALOGUE": "catalogue", "DEPLOY_SHA": "deploy_sha"}
# Nouveaux au lot L1d (édition à travers le robot) : PAS repris de utils_static.
TOPICS_EDITION = {"DATA_EDIT": "data_edit", "DATA_EDIT_RESULT": "data_edit_result"}
# Nouveaux au lot L1d-2 (porte sim) : PAS repris de utils_static.
TOPICS_PORTE_SIM = {"VALIDATION_SIM": "validation_sim", "VALIDATION_SIM_DEMANDE": "validation_sim_demande",
                    "ROUES_REFUSEES": "roues_refusees"}
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
    assert _constantes(topics) == {**ORGANES, **TOPICS_HORS_ORGANES, **TOPICS_PERCEPTION, **TOPICS_JEU,
                                         **TOPICS_CATALOGUE, **TOPICS_EDITION, **TOPICS_PORTE_SIM}


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
