"""SHIM de transition (lot L1a, 2026-11-02) — ce fichier DISPARAÎT au lot L5.

Le CONTRAT inter-machines (noms de topics, clés de payload, organes) vit
désormais dans le package `theatre_contrats` (packages/theatre_contrats du
mono-dépôt theatre-robot) ; il est ré-exporté ici pour que les 129 imports
existants `from dadou_utils_ros.utils_static import X` continuent de marcher
sans réécriture. Pour un code NEUF : importer theatre_contrats directement.

CONSÉQUENCE : tout environnement qui importe cette lib doit avoir
theatre_contrats sur son chemin — colcon (package dans src/ du workspace) dans
les conteneurs, conftest.py (sys.path) pour les tests hôte. Sans lui, TOUS les
nodes tombent à l'import, wheels_node compris.

Restent DÉFINIES ici (pas un contrat, jusqu'à L5) : chemins/répertoires,
logging, plateforme, couleurs, constantes internes à dadou_utils_ros.
Supprimées au lot L1a car importées par personne (tools/inventaire.py) :
JSON_NOTES, NOTE, FILES. IP n'est plus utilisée que par com/ws_server.py et
com/ws_com.py, modules eux-mêmes morts : à supprimer ensemble en L5.

Les tests de contrat des consommateurs (test_contrat_utils.py côté robot,
test_utils_static_contract.py côté control) figent les valeurs à travers ce
shim et rougissent à la moindre dérive.
"""

# ---------------------------------------------------------------- CONTRAT (ré-exporté de theatre_contrats)
from theatre_contrats.organs import *  # noqa: F401,F403
from theatre_contrats.topics import *  # noqa: F401,F403
from theatre_contrats.keys import *  # noqa: F401,F403

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
LORA = 'lora'
MOUTH_VISUALS_PATH = 'mouth visuals path'
MSG = 'msg'
PAUSE = 'pause'
PLAY = 'play'
RESTART_PIN = 'restart pin'
SHUTDOWN_PIN = 'shutdown pin'
STATUS_LED_PIN = 'status pin'

# ---------------------------------------------------------------- COULEURS (clé de config de la télécommande)
ORANGE = 'orange'
