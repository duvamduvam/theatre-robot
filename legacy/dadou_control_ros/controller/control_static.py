"""Constantes statiques mono-consommateur de la télécommande (dadou_control_ros).

Rapatriement (2026-07) : ces ~98 constantes n'étaient utilisées QUE par ce
dépôt mais vivaient dans dadou_utils_ros.utils_static — le contrat partagé
entre télécommande/robot/vision. Les y laisser créait un couplage inutile :
toute modification ici (renommage, suppression) touchait potentiellement les
trois dépôts alors qu'aucun autre ne les consommait. Cf. le bug MODE du
commit c08eb82 de la lib partagée (une valeur changée là-bas a cassé le mode
random des animations bras/yeux côté robot, sans lien avec la télécommande) :
la leçon retenue est que la lib partagée ne doit porter QUE le contrat
inter-machines, pas les détails internes de chacun.

Valeurs copiées VERBATIM depuis utils_static au moment du rapatriement — ne
pas les faire dériver sans vérifier qu'aucun autre dépôt ne s'y attend (JSON
de séquences, configs sauvegardées, etc. qui embarqueraient la valeur brute).

Règle de migration inverse : si une constante d'ici devient nécessaire dans
dadou_robot_ros ou dadou_vision_ros, la déplacer vers utils_static.py (lib
partagée) et supprimer sa définition ici — jamais la dupliquer dans les deux
sens à la fois, sous peine de désynchronisation silencieuse.
"""

LAPTOP_TYPE = 'x86_64'
L1 = "L1"
L2 = "L2"
R1 = "R1"
R2 = "R2"
LX = "LX"
LY = "LY"
RX = "RX"
RY = "RY"
START = 'START'
SELECT = "SELECT"
BL = "BL"
BR = "BR"
ALL = "all"
ARMS = 'arms'
AUDIO_NAME = 'audio_name'
AUDIO_PATH = 'audio_path'
BASE = 'base'
BAUD_RATE = 'baud rate'
BORDEAUX = 'bordeaux'
BUTTON = 'button'
BUTTON_GRID = 'button grid'
CHOOSE = 'choose'
CELL = "cell"
CLEAN = 'clean'
COLORS = 'colors'
CONNECTED = 'connected'
CMD = 'cmd'
CONFIG = 'config'
COORD = "coord"
CONTROL = 'controller'
CYAN = 'cyan'
DATAS = 'datas'
DEVICE = 'device'
DIDIER = "didier"
DOCKER_LOGGING_CONFIG_FILE = 'docker-arm64 logging config file'
EYE = 'eye'
EYES = 'eyes'
# --- Topics de perception/autonomie pilotés depuis la télécommande (2026-09-14)
# Déclarés ICI et non dans la lib partagée dadou_utils_ros : les deux
# consommateurs (person_tracker côté vision, person_follower côté robot)
# déclarent déjà leur nom de topic en dur de leur côté. Passer par la lib
# partagée, qui n'a pas de versionnage, ferait porter un risque à trois dépôts
# pour deux chaînes de caractères.
DESIGNATE = 'designate'   # "on" = « c'est moi » : verrouille le suivi sur la
                          # personne la plus CENTRÉE dans l'image ; "off" relâche.
FOLLOW = 'follow'         # "on"/"off" : suivi de personne AUX ROUES.
ROUTE_SPEED = 'route_speed'  # nombre 0..1 : vitesse du CHEMINEMENT de Didier en
                             # salle de répétition simulée (contrat ROUTE_SPEED_TOPIC de
                             # dadou_robot_ros/conf/ros2_dependencies/robot_rehearsal/
                             # robot_rehearsal/contracts.py). Sim-only : personne ne
                             # l'écoute sur le vrai robot, il y est inoffensif.
# Clé de config : profil de décodage du boîtier de faders (controller/input/
# sliders_mapping.py). Valeur = nom de profil ; choisie par la variable
# d'environnement SLIDERS_PROFILE du compose (défaut "default" = comportement
# historique, octet pour octet).
SLIDERS_PROFILE = 'sliders_profile'
FONT1 = 'font1'
FONT2 = 'font2'
FONT12 = 'font12'
FONT22 = 'font22'
FONT3 = 'font3'
GAMEPAD = "gamepad"
GLOVE = "glove"
GLOVE_LEFT = 'glove left'
GLOVE_RIGHT = 'glove right'
HOST_NAME = 'host name'
ICON = 'icon'
ICONS = 'icons'
IMAGE = 'image'
IN_CELL = "in cell"
INPUT_KEY = "input_key"
JSON_LIGHTS_METHODS = 'json lights methods'
JSON_SPEECHS = 'json speechs'
KEYBOARD = "keyboard"
LAPTOP_LOGGING_CONFIG_FILE = 'laptop logging config file'
LENGTH = 'length'
LOG_FILE = 'log file'
LONG = "long"
LORA = 'lora'
MSG = 'msg'
NECKS = 'necks'
NEXT = 'next'
OUT_CELL = "out_cell"
PATH = 'path'
PATHS = 'paths'
PAUSE = 'pause'
PLAY = 'play'
PLAYLIST = 'playlist'
PLAYLISTS = 'playlists'
PLAYLIST_LIST = 'playlists_list'
PLAYLIST_PATH = 'playlists path'
PLAYLIST_PLAY = 'playlist play'
PLAYLIST_STOP = 'playlist stop'
PROJECT_LIGHTS_DIRECTORY = 'project light directory'
PURPLE = 'purple'
RANDOM_ANIMATION = 'random animation'
RANDOM_COLOR = 'random color'
RESTART = 'restart'
ROBOT = 'robot'
RPI_LOGGING_CONFIG_FILE = 'rpi logging config file'
SEQUENCE = 'sequence'
SHORT = "short"
SLIDE = 'slide'
SLIDERS = 'sliders'
STATE = 'state'
VISUALS = 'visuals'
WINDOW = "window"
WS_CLIENT = 'ws client'
WS_CLIENTS = 'ws client'
WS_PORT = 'ws port'
XBOX = "xbox"
X1 = "x1"
X2 = "x2"
Y1 = "y1"
Y2 = "y2"
YELLOW = 'yellow'
