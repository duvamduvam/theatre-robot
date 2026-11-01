# Constantes internes au robot, rapatriées de dadou_utils_ros.utils_static.
#
# Pourquoi ce fichier : dadou_utils_ros/utils_static.py est la lib PARTAGÉE avec
# ../dadou_control_ros (télécommande) et ../dadou_vision_ros. Il ne doit contenir que
# le CONTRAT inter-machines (topics StringTime, clés de payload échangées, directions,
# couleurs communes, etc.). Les ~85 constantes ci-dessous n'ont jamais qu'un seul
# consommateur : ce repo. Les y laisser mélangées au contrat rendait invisible qui
# dépend de quoi — c'est exactement ce qui a permis au bug MODE (commit c08eb82,
# 2025-09-27) de passer inaperçu : une constante partagée modifiée unilatéralement
# a cassé le mode random des animations (bras/yeux inertes) sans qu'aucun import
# ne signale la rupture de contrat.
#
# Règle pour la suite : une constante utilisée par un autre repo (dadou_control_ros,
# dadou_vision_ros) doit MIGRER vers dadou_utils_ros.utils_static — jamais l'inverse
# silencieusement. Si un jour une constante d'ici devient partagée, elle sort de ce
# fichier et rejoint le contrat, avec le test de non-régression associé
# (robot/tests/unit/test_contrat_utils.py).
#
# Valeurs copiées VERBATIM depuis dadou_utils_ros/utils_static.py au moment du
# rapatriement — ne pas les modifier ici sans vérifier qu'aucun autre repo ne les
# utilise (grep sur ../dadou_control_ros et ../dadou_vision_ros).

############### IA / audio ###############

AI = "ai"
AUDIOS_DB = 'audios_db'
AUDIO_DEVICE_ID = 'audio device id'
DEFAULT_VOLUME_LEVEL = 'default volume level'
DEVICES_LIST = 'device list'

############### Visages : yeux / bouche ###############

BACKGROUND = 'background'
EYE_VISUALS_PATH = 'eye visuals path'
LEFT_EYES = "left_eyes"
LEFT_EYE_NB = "left eye nb"
LEYE = 'leye'
MOUTHS = 'mouths'
MOUTH_VISUALS_PATH = 'mouth visuals path'
REYE = 'reye'
RIGHT_EYES = 'right_eyes'
RIGHT_EYE_NB = "right eye nb"

############### Couleurs ###############

BLUE = 'blue'
RED = 'red'

############### Calibration / positions servos ###############

CALIBRATION = 'calibration'
DEFAULT_POS = 'default_pos'
MAX_POS = 'max_pos'
SERVO = "servo"
SERVOS = "servos"
SERVO_MIN = 'servo_min'
LEFT_ARM_NB = 'left arm nb'
RIGHT_ARM_NB = 'right arm nb'
HEAD_PWM_NB = 'head pwm nb'
STRAIGHT = 'straight'

############### Roues : commandes legacy StringTime ###############

CMD_BACKWARD = 'cmd_backward'
CMD_FORWARD = 'cmd_forward'
CMD_LEFT = 'cmd_left'
CMD_RIGHT = 'cmd_right'
WHEEL_LEFT_DIR = 'wheel left dir'
WHEEL_LEFT_PWM = 'wheel left pwm'
WHEEL_RIGHT_DIR = 'wheel right dir'
WHEEL_RIGHT_PWM = 'wheel right pwm'

############### Répertoires ###############

DB_DIRECTORY = 'db directory'

############### Clés JSON (séquences, config, mapping) ###############

JSON_AUDIOS_DATAS = "json audios datas"
JSON_AUDIO_SEQUENCE = 'json audio sequence'
JSON_COLORS = 'json colors'
JSON_FACE_SEQUENCE = 'json face sequence'
JSON_LIGHTS_SEQUENCE = 'json lights sequence'
JSON_MAPPINGS = 'json mapping'
JSON_NOTES = 'notes'
JSON_RELAYS = 'json relays'
JSON_VISUALS = 'json visuals'
SEQUENCES_DB = 'sequences db'

############### Activation matériel (drapeaux GPIO/PWM/I2C) ###############

DIGITAL_CHANNELS_ENABLED = "digitail channels enabled"
I2C_ENABLED = 'i2c_enabled'
PWM_CHANNELS_ENABLED = 'pmw channels enabled'
SINGLE_THREAD = 'single_thread'

############### Bornes d'entrée génériques ###############

INPUT_MAX = "input_max"
INPUT_MIN = "input_min"

############### LEDs / relais ###############

LIGHTS_END_LED = 'lights end led'
LIGHTS_LED_COUNT = 'lights led count'
LIGHTS_PIN = 'lights pin'
LIGHTS_START_LED = 'lights start led'
RELAYS = 'relays'

############### Pins GPIO divers ###############

RESTART_PIN = 'restart pin'
SHUTDOWN_PIN = 'shutdown pin'
STATUS_LED_PIN = 'status pin'

############### LoRa ###############

LORA_CS_PIN = 'lora cs pin'
LORA_MISO_PIN = 'lora miso pin'
LORA_MOSI_PIN = 'lora mosi pin'
LORA_RESET_PIN = 'lora reset pin'
LORA_SCK_PIN = 'lora sck pin'

############### Cadence des nodes ###############

# 20 Hz — le tick global des nodes. Le driver LED (fast_neopixel vendorisé)
# bloque ~31 ms par show() : attente de fin de trame INDISPENSABLE (sa
# suppression corrompait les trames, incident 2026-07-13). lights_node
# s'auto-limite de fait, les autres nodes (servos…) tiennent la cadence.
# NE PAS appliquer à la chaîne roues (wheels_node / robot_drive : gelée).
TICK_PERIOD_S = 0.05

############### Boucle principale / logging ###############

LITTLE_MOVE = "little move"
LOGGING = 'logging'
LOOP_DURATION = 'loop duration'
MAIN_LOOP_SLEEP = 'main loop sleep'
PROFILER = 'profiler'
STOP_ANIMATION_KEYS = 'stop animation key'
STOP_KEY = 'stop key'
TIME = 'time'

############### Animation aléatoire ###############

RANDOM_ANIMATION_HIGH = 'random animation high'
RANDOM_ANIMATION_LOW = 'random animation low'
RANDOM_DURATION = 'random duration'
RANDOM_MOVE_MAX = 'random move max'
RANDOM_MOVE_MIN = 'random move min'
RANDOM_TIME_MAX = 'random time max'
RANDOM_TIME_MIN = 'random time min'
RANDOM_TYPE = 'random type'

############### Divers ###############

NONE = 'none'
NOTE = 'note'
OFF = "off"
TYPES = 'types'
