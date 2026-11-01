import copy
import logging
import os
import socket

from dadou_utils_ros.misc import Misc

from dadou_utils_ros.utils_static import (
    AUDIOS_DIRECTORY, RPI_TYPE, NAME, SERIAL_ID, MSG_SIZE, TYPE, SEQUENCES, MOUTH, BASE_PATH, JSON_EXPRESSIONS,
    JSON_LIGHTS, JSON_DIRECTORY, SEQUENCES_DIRECTORY, DEVICES, LOGGING_CONFIG_FILE, JSON_CONFIG, JSON_LIGHTS_BASE,
    ORANGE, SYSTEM, LOGGING_FILE_NAME, UP, WHEELS, FORWARD, DOWN, BACKWARD, LEFT, RIGHT, ANIMATION, A, B, X, Y,
    LEFT_ARM, RIGHT_ARM, NECK, RIGHT_EYE, LEFT_EYE, JOYSTICK, MEDIAS_DIRECTORY, PROJECT_DIRECTORY, SRC_DIRECTORY,
    VISUAL_DIRECTORY, LOGGING_DIRECTORY, CONFIG_DIRECTORY, AUDIO, FACE, ROBOT_LIGHTS, RELAY, WHEEL_LEFT,
    WHEEL_RIGHT, LOGGING_CONFIG_TEST_FILE, LOGGING_TEST_FILE_NAME,
)
from controller.control_static import (
    BUTTON_GRID, EYES, LAPTOP_TYPE, PATH, VISUALS, WS_CLIENT, AUDIO_NAME, AUDIO_PATH, PATHS, JSON_SPEECHS,
    PLAYLIST_PATH, GLOVE_LEFT, GLOVE_RIGHT, PROJECT_LIGHTS_DIRECTORY, PLAYLIST_PLAY, PLAYLIST_STOP, PURPLE,
    BORDEAUX, YELLOW, CYAN, FONT1, FONT2, FONT3, RPI_LOGGING_CONFIG_FILE, LAPTOP_LOGGING_CONFIG_FILE,
    JSON_LIGHTS_METHODS, WS_CLIENTS, WS_PORT, BAUD_RATE, ICONS, CONFIG, LOG_FILE, HOST_NAME, BUTTON, MSG, BL, BR,
    START, SELECT, ALL, INPUT_KEY, DOCKER_LOGGING_CONFIG_FILE, FONT22, PLAYLIST_LIST, FONT12, RANDOM_ANIMATION,
    DESIGNATE, FOLLOW, ROUTE_SPEED, SLIDERS_PROFILE,
)

config = {}

DUAL_GLOVE_9DOF_LEFT, DUAL_GLOVE_9DOF_RIGHT, DUAL_GLOVE_LEFT, DUAL_GLOVE_RIGHT, SINGLE_GLOVE_9DOF, SINGLE_GLOVE, DUAL_GLOVE, CONFIG = \
    "2 GL 9", "2 GR 9", "2 GL", "2 GR", "1 G 9", "1 G", "2 G", CONFIG
IHL, IML, IBL, MHL, MML, MBL, AHL, AML, ABL, OHL, OML, OBL, IHR, IMR, IBR, MHR, MMR, MBR, AHR, AMR, ABR, OHR, OMR, OBR =1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24
#IH, IM, IB, MH, MM, MB, AH, AM, AB, OH, OM, OB = 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12

config[BASE_PATH] = os.getcwd()
config[HOST_NAME] = socket.gethostname()

config[WS_PORT] = 4421
#config[WS_CLIENTS] = {'controller': '192.168.1.200', 'sceno': '192.168.1.220', 'harddrive': '192.168.1.230'}
config[WS_CLIENTS] = {ALL: {'controller': 'didier.local', 'sceno': 'sceno.local', 'harddrive': 'disk.local'}, "gamepad": {'controller': 'didier.local'}}
#config[WS_CLIENT] = {'sceno': 'ws://192.168.1.220:4421', 'sceno': 'ws://192.168.1.220:4421'}
############## JSON FILES ##############



config[JSON_CONFIG] = 'control_config.json'
config[JSON_EXPRESSIONS] = 'expressions.json'
config[JSON_LIGHTS] = 'lights_base.json'
config[JSON_LIGHTS_BASE] = 'lights_base.json'
config[JSON_LIGHTS_METHODS] = 'lights_methods.json'
config[JSON_SPEECHS] = 'speechs.json'

config[PLAYLIST_LIST] = ["didier20_bis", "grandlieu", "eternel-short"]

############### PATHS ###############

#config[BASE_PATH] = os.path.dirname(__file__)

config[SYSTEM] = Misc.get_system_type()

if Misc.is_raspberrypi():
    #TODO FIX RPI PATH
    config[BASE_PATH] = "/home/ros2_ws/"
elif Misc.is_docker():
    config[BASE_PATH] = "/home/ros2_ws/"
else:
    config[BASE_PATH] = "/home/ros2_ws/"

# ⚠️ PUBLISHER_LIST est le FILTRE de publication : Ros2TkinterApp.publish()
# ignore silencieusement toute clé de commande absente de cette liste. Un bouton
# dont la commande n'est pas listée ici ne fait donc RIEN, sans erreur — c'est ce
# qui rendait `follow` inatteignable depuis la télécommande jusqu'au 14/09.
PUBLISHER_LIST = [RANDOM_ANIMATION, ANIMATION, AUDIO, FACE, ROBOT_LIGHTS, RELAY, NECK ,LEFT_EYE,
                  RIGHT_EYE, LEFT_ARM, RIGHT_ARM, WHEELS, WHEEL_LEFT, WHEEL_RIGHT,
                  DESIGNATE, FOLLOW, ROUTE_SPEED]

# Profil du boîtier de faders : variable d'environnement SLIDERS_PROFILE (passée
# par les compose arm/x86), défaut "default" (comportement historique). Validé
# au démarrage par SerialInputs (refus explicite d'un nom inconnu).
config[SLIDERS_PROFILE] = os.environ.get("SLIDERS_PROFILE", "default")

config[SRC_DIRECTORY] = config[BASE_PATH] + "src/"
config[PROJECT_DIRECTORY] = config[SRC_DIRECTORY] + 'controller/'

config[AUDIOS_DIRECTORY] = config[PROJECT_DIRECTORY] + 'audios/'
config[MEDIAS_DIRECTORY] = config[PROJECT_DIRECTORY] + 'medias/'
config[CONFIG_DIRECTORY] = config[PROJECT_DIRECTORY] + 'conf/'
config[JSON_DIRECTORY] = config[PROJECT_DIRECTORY] + 'json/'

config[PLAYLIST_PATH] = config[JSON_DIRECTORY] + 'playlists/'
config[SEQUENCES_DIRECTORY] = config[JSON_DIRECTORY] + 'sequences/'
config[PROJECT_LIGHTS_DIRECTORY] = config[JSON_DIRECTORY] + 'projects_lights/'

config[VISUAL_DIRECTORY] = config[MEDIAS_DIRECTORY] + 'visuals/'

config[LOGGING_DIRECTORY] = config[CONFIG_DIRECTORY] + "logging/"
config[LOGGING_CONFIG_TEST_FILE] = config[LOGGING_DIRECTORY] + 'logging-test.conf'
#config[LOGGING_CONFIG_FILE] = config[LOGGING_DIRECTORY] + 'logging.conf'

config[LOGGING_DIRECTORY] = config[CONFIG_DIRECTORY] + 'logging/'
config[RPI_LOGGING_CONFIG_FILE] = config[LOGGING_DIRECTORY] + 'logging-pi.conf'


config[LAPTOP_LOGGING_CONFIG_FILE] = config[LOGGING_DIRECTORY] + 'logging-laptop.conf'
config[DOCKER_LOGGING_CONFIG_FILE] = config[LOGGING_DIRECTORY] + 'logging-docker-arm64.conf'
config[DOCKER_LOGGING_CONFIG_FILE] = config[LOGGING_DIRECTORY] + 'logging-docker-arm64.conf'

if Misc.is_raspberrypi():
    config[LOGGING_TEST_FILE_NAME] = '/home/pi/test/logs/robot-test.log'
else:
    config[LOGGING_TEST_FILE_NAME] = '/home/dadou/Nextcloud/dev/didier/python/dadou_control_ros/test_logs/control-test.log'

if Misc.is_raspberrypi():
    #config[LOGGING_CONFIG_FILE] = config[RPI_LOGGING_CONFIG_FILE]
    config[LOGGING_FILE_NAME] = "/home/ros2_ws/log/controller.log"
    config[LOGGING_TEST_FILE_NAME] = "/home/pi/test/logs/controller-test.log"
elif Misc.is_docker():
    #config[LOGGING_CONFIG_FILE] = config[DOCKER_LOGGING_CONFIG_FILE]
    config[LOGGING_FILE_NAME] = "/home/ros2_ws/log/controller.log"
else:
    #config[LOGGING_CONFIG_FILE] = config[LAPTOP_LOGGING_CONFIG_FILE]
     config[LOGGING_FILE_NAME] = "/home/ros2_ws/log/controller.log"
    # Write test logs inside the repository to avoid permission issues
# try:
#        cwd = os.getcwd()
#    except Exception:
#        cwd = "."
#    config[LOGGING_TEST_FILE_NAME] = os.path.join(cwd, "test_logs", "controller-test.log")

config[PATHS] = {
        VISUALS: config[VISUAL_DIRECTORY] + "visuals/",
        EYES: config[VISUAL_DIRECTORY] + "eye/",
        MOUTH: config[VISUAL_DIRECTORY] + "mouth/",
        SEQUENCES: config[VISUAL_DIRECTORY] + "sequences/",
        ICONS: config[VISUAL_DIRECTORY] + "icons/"
    }


############# COLORS ###############
#https://coolors.co/palettes/trending

config[PURPLE] = '#5f0f40'
config[BORDEAUX] = '#9a031e'
config[YELLOW] = '#fb8b24'
config[ORANGE] = '#e36414'
config[CYAN] = '#0f4c5c'

############ FONTS #################

config[FONT1] = "Helvetica 30 italic bold" #None tkfont.Font(family='Helvetica', size=18, weight="bold", slant="italic")
config[FONT2] = "Helvetica 17 italic bold" #None tkfont.Font(family='Helvetica', size=15, weight="bold", slant="italic")
config[FONT3] = "Helvetica 15 italic bold" #None tkfont.Font(family='Helvetica', size=12, weight="bold", slant="italic")

config[FONT12] = "Helvetica 12 italic bold"
config[FONT22] = "Helvetica 22 italic bold" #None tkfont.Font(family='Helvetica', size=18, weight="bold", slant="italic")

FONT_DROPDOWN = "Helvetica 34 italic bold"
FONT_BUTTON = "Helvetica 34 italic bold"

config[BUTTON_GRID] = "Helvetica 31 italic bold" #None tkfont.Font(family='Helvetica', size=18, weight="bold", slant="italic")

########### GAMEPAD ###############
HE, AR, EY, AN = "HE", "AR", "EY", "AN"
SELECT_MODE = [HE, AR, EY, AN]


BUTTONS_MAPPING = {HE: {UP: {RIGHT_ARM: DOWN}, DOWN: {RIGHT_ARM: UP}, LEFT: {NECK: UP}, RIGHT: {NECK: DOWN},
                        A: {RIGHT_EYE: UP}, B: {RIGHT_EYE: DOWN}, X: {LEFT_EYE: UP},
                        Y: {LEFT_EYE: DOWN}, BL: {BL: None}, BR: {BR: None},
                        'by': {WHEELS: FORWARD}, 'bw': {WHEELS: LEFT}, 'br': {WHEELS: RIGHT}, 'bg': {WHEELS: BACKWARD},
                        'bb': {ANIMATION: 'random button'}, START: {}, SELECT: {SELECT: None}}}
BUTTONS_MAPPING[AR] = copy.copy(BUTTONS_MAPPING[HE])
#BUTTONS_MAPPING[AR][A] = {LEFT_ARM: UP}
#BUTTONS_MAPPING[AR][B] = {LEFT_ARM: DOWN}

BUTTONS_MAPPING[EY] = copy.copy(BUTTONS_MAPPING[HE])
BUTTONS_MAPPING[AN] = copy.copy(BUTTONS_MAPPING[HE])

config[PLAYLIST_PLAY] = ['c', 'D']
config[PLAYLIST_STOP] = ['j', 'H']
RESTART_APP = ['I']

################## USB DEVICES ################
config[DEVICES] = [
        {
            NAME: 'bouton rouge',
            SERIAL_ID: 'usb-Raspberry_Pi_Pico_E66250758B6A3721-if00',
            MSG: "br",
            MSG_SIZE: 0,
            TYPE: INPUT_KEY,
            BAUD_RATE: 115200
        },
        {
            NAME: 'bouton blanc',
            SERIAL_ID: 'usb-Raspberry_Pi_Pico_E4683818DF310B23-if00',
            MSG: "bw",
            MSG_SIZE: 0,
            TYPE: BUTTON,
            BAUD_RATE: 115200
        },
        {
            NAME: 'bouton blue',
            SERIAL_ID: 'usb-Raspberry_Pi_Pico_E66250758B474521-if00',
            MSG: "bb",
            MSG_SIZE: 0,
            TYPE: BUTTON,
            BAUD_RATE: 115200
        },
        {
            NAME: 'bouton jaune',
            SERIAL_ID: 'usb-Raspberry_Pi_Pico_DE61B868C74A4E36-if00',
            MSG: "by",
            MSG_SIZE: 0,
            TYPE: BUTTON,
            BAUD_RATE: 115200
        },
        {
            NAME: 'bouton vert',
            SERIAL_ID: 'usb-Raspberry_Pi_Pico_E66250758B90892A-if00',
            MSG: "bg",
            MSG_SIZE: 0,
            TYPE: BUTTON,
            BAUD_RATE: 115200
        },
        {
            NAME: 'buttons',
            SERIAL_ID: 'usb-1a86_USB_Serial-if00-port0',
            MSG_SIZE: 0,
            TYPE: INPUT_KEY,
            BAUD_RATE: 115200
        },
        {
            NAME: GLOVE_LEFT,
            SERIAL_ID: 'usb-Raspberry_Pi_Pico_E462785763442E33-if00',
            MSG_SIZE: 0,
            TYPE: INPUT_KEY,
            BAUD_RATE: 115200
        },
        {
            NAME: "glove_right",
            SERIAL_ID: "usb-Raspberry_Pi_Pico_E4624881D32D1B30-if00",
            "msg_size": 0,
            TYPE: INPUT_KEY,
            BAUD_RATE: 115200
        },
        {
            NAME: JOYSTICK,
            SERIAL_ID: "usb-Waveshare_Electronics_RP2040-Zero_DE6250B407486D23-if00",
            "msg_size": 6,
            TYPE: JOYSTICK,
            BAUD_RATE: 115200
        },
        {
            NAME: "sliders",
            SERIAL_ID: "usb-Waveshare_Electronics_RP2040-Zero_E66138935F269628-if00",
            "msg_size": 6,
            TYPE: "sliders",
            BAUD_RATE: 9600
        }
    ]



#else:
#    logging.error("can't find system type {}".format(config[SYSTEM]))
