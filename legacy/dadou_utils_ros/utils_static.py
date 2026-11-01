"""Contrat inter-machines du parc Didier (robot / télécommande / vision).

RÈGLE (chantier 2026-07-11, après le bug MODE c08eb82) : ce fichier ne contient
QUE ce qui est partagé entre au moins deux dépôts — noms de topics StringTime,
clés des payloads JSON échangés sur le réseau, conventions de nommage communes —
plus quelques constantes des modules internes de cette lib. Les constantes
propres à un seul dépôt vivent CHEZ LUI (robot/robot_static.py,
controller/control_static.py). Toute valeur modifiée ici doit l'être de façon
coordonnée : les tests de contrat des consommateurs (test_contrat_utils.py côté
robot, test_utils_static_contract.py côté control) figent ces valeurs et
rougissent à la moindre dérive.
"""

# ---------------------------------------------------------------- TOPICS StringTime (noms des canaux ROS entre machines)
ANIMATION = 'animation'
# État d'activité des animations (arbitrage amont, étude 2026-07-12 côté robot :
# docs/etude-arbitrage-actionneurs.md). Publié LATCHÉ par animations_node :
# msg = json.dumps(nom de la séquence en cours) ou json.dumps("") au repos.
# Consommé par les comportements autonomes (gaze côté robot, chat côté vision)
# qui se taisent tant qu'une séquence a la main sur visage + tête.
ANIMATION_STATE = 'animation_state'
AUDIO = 'audio'
EXPRESSION = 'expression'
FACE = 'face'
LEFT_ARM = 'left_arm'
LEFT_EYE = 'left_eye'
LIGHTS = 'lights'
NECK = 'neck'
RELAY = 'relay'
RIGHT_ARM = 'right_arm'
RIGHT_EYE = 'right_eye'
ROBOT_LIGHTS = 'robot_lights'
SPEAK = 'speak'
SYSTEM = 'system'
WHEELS = 'wheels'

# ---------------------------------------------------------------- CLÉS des payloads JSON (contenu des messages)
A = 'A'
ANGLO = 'anglo'
AUDIOS = 'audios'
B = 'B'
BACKWARD = 'backward'
BRIGHTNESS = 'brightness'
COLOR = 'color'
DEFAULT = 'default'
DEVICES = 'devices'
DOWN = 'down'
DURATION = 'duration'
FACES = 'faces'
FILES = 'files'
FORWARD = 'forward'
INCLINO = "inclino"
JOYSTICK = 'self.gamepad'
KEY = 'key'
KEYS = 'keys'
LOOP = 'loop'
METHOD = 'method'
# 'mode' MINUSCULE : c'est la clé des keyframes servo des séquences JSON
# ({"mode": "random", ...}). Passée à 'MODE' par c08eb82 (2025-09-27) → le mode
# random ne s'armait plus jamais depuis les animations (bras/yeux inertes).
MODE = 'mode'
MOUTH = 'mouth'
NAME = 'name'
NORMAL = 'normal'
RANDOM = 'random'
SEQUENCES = 'sequences'
SPEED = 'speed'
STOP = 'stop'
TYPE = 'type'
UP = "UP"
WHEEL_LEFT = 'wheel_left'
WHEEL_RIGHT = 'wheel_right'
X = 'X'
Y = 'Y'

# ---------------------------------------------------------------- FICHIERS JSON et RÉPERTOIRES partagés par convention
AUDIOS_DIRECTORY = 'audios directory'
BASE_PATH = 'base path'
CONFIG_DIRECTORY = 'config directory'
JSON_AUDIOS = 'json audios'
JSON_CONFIG = 'json config'
JSON_DIRECTORY = 'json directory'
JSON_EXPRESSIONS = 'json expressions'
JSON_LIGHTS = 'json lights'
JSON_LIGHTS_BASE = 'json lights base'
LOGGING_DIRECTORY = "logging directory"
MEDIAS_DIRECTORY = "medias_directory"
PROJECT_DIRECTORY = 'project directory'
SEQUENCES_DIRECTORY = 'sequences directory'
SRC_DIRECTORY = 'src directory'
VISUAL_DIRECTORY = 'src path'

# ---------------------------------------------------------------- PLATEFORME / LOGGING
LOGGING_CONFIG_FILE = 'logging config file'
LOGGING_CONFIG_TEST_FILE = 'logging test config file'
LOGGING_FILE_NAME = 'logging file name'
LOGGING_TEST_FILE_NAME = 'logging test file name'
MSG_SIZE = "msg_size"
RPI_TYPE = ['armv7l', 'aarch64']
SERIAL_ID = 'serial_id'

# ---------------------------------------------------------------- INTERNES à dadou_utils_ros (utilisées par misc/sound/inputs — pas un contrat)
BAUD_RATE = 'baud rate'
BUTTON = 'button'
DEVICE_MSG_SIZE = 'msg_size'
DIGITAL_CHANNELS_ENABLED = "digitail channels enabled"
ERROR = "error"
EYE = 'eye'
EYE_VISUALS_PATH = 'eye visuals path'
I2C_ENABLED = 'i2c_enabled'
IP = "ip"
JSON_NOTES = 'notes'
LORA = 'lora'
MOUTH_VISUALS_PATH = 'mouth visuals path'
MSG = 'msg'
NOTE = 'note'
PAUSE = 'pause'
PLAY = 'play'
RESTART_PIN = 'restart pin'
SHUTDOWN_PIN = 'shutdown pin'
STATUS_LED_PIN = 'status pin'

# ---------------------------------------------------------------- DIVERS (contrat, à re-classer à l'occasion)
LEFT = 'left'
ORANGE = 'orange'
RIGHT = 'right'
