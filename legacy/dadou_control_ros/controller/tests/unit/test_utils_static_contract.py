"""Garde-fou anti-régression du contrat partagé dadou_utils_ros.utils_static.

Rapatriement (2026-07) : les constantes utilisées par un seul dépôt (télécommande,
robot ou vision) ont été déplacées hors de utils_static vers un module local à
chacun (côté télécommande : controller/control_static.py). Il ne reste dans
utils_static QUE le contrat inter-machines : les ~74 constantes ci-dessous, dont
la VALEUR (pas seulement le nom) doit rester identique entre dadou_control_ros,
dadou_robot_ros et dadou_vision_ros — ce sont les clés des messages StringTime
échangés sur le réseau (ex. WHEELS, NECK, ANIMATION...) et des chemins/JSON
partagés par convention de nommage entre dépôts.

Rappel du risque (cf. commit c08eb82 de la lib partagée, voir le commentaire dans
utils_static.py à côté de MODE) : une valeur changée ici SANS coordination entre
les dépôts frères casse silencieusement le dépôt qui n'a pas été mis à jour — pas
d'erreur à l'import, juste un comportement muet côté récepteur (ex. clé de
message qui ne matche plus rien). Ce test échoue immédiatement si une valeur
dérive, AVANT que le symptôme silencieux n'apparaisse en usage réel.

Si ce test échoue : soit la valeur a changé par erreur (revert), soit c'est un
changement voulu et coordonné avec les dépôts frères — dans ce cas, mettre à
jour CE test en même temps que utils_static.py.
"""

from dadou_utils_ros.utils_static import (
    RPI_TYPE, A, B, X, Y, UP, DOWN, LEFT, RIGHT, ANGLO, ANIMATION, AUDIO, AUDIOS, AUDIOS_DIRECTORY, BACKWARD,
    BASE_PATH, BRIGHTNESS, COLOR, CONFIG_DIRECTORY, DEFAULT, DEVICES, DURATION, EXPRESSION, FACE, FACES, FILES,
    FORWARD, INCLINO, JOYSTICK, JSON_AUDIOS, JSON_CONFIG, JSON_DIRECTORY, JSON_EXPRESSIONS, JSON_LIGHTS,
    JSON_LIGHTS_BASE, KEY, KEYS, LEFT_ARM, LEFT_EYE, LIGHTS, LOGGING_CONFIG_FILE, LOGGING_CONFIG_TEST_FILE,
    LOGGING_DIRECTORY, LOGGING_FILE_NAME, LOGGING_TEST_FILE_NAME, LOOP, MEDIAS_DIRECTORY, METHOD, MODE, MOUTH,
    MSG_SIZE, NAME, NECK, NORMAL, ORANGE, PROJECT_DIRECTORY, RANDOM, RELAY, RIGHT_ARM, RIGHT_EYE, SEQUENCES,
    SEQUENCES_DIRECTORY, SERIAL_ID, SPEAK, SPEED, SYSTEM, SRC_DIRECTORY, VISUAL_DIRECTORY, STOP, ROBOT_LIGHTS, TYPE,
    WHEELS, WHEEL_LEFT, WHEEL_RIGHT,
)


def test_shared_contract_values_are_unchanged():
    assert RPI_TYPE == ['armv7l', 'aarch64']
    assert A == 'A'
    assert B == 'B'
    assert X == 'X'
    assert Y == 'Y'
    assert UP == "UP"
    assert DOWN == 'down'
    assert LEFT == 'left'
    assert RIGHT == 'right'
    assert ANGLO == 'anglo'
    assert ANIMATION == 'animation'
    assert AUDIO == 'audio'
    assert AUDIOS == 'audios'
    assert AUDIOS_DIRECTORY == 'audios directory'
    assert BACKWARD == 'backward'
    assert BASE_PATH == 'base path'
    assert BRIGHTNESS == 'brightness'
    assert COLOR == 'color'
    assert CONFIG_DIRECTORY == 'config directory'
    assert DEFAULT == 'default'
    assert DEVICES == 'devices'
    assert DURATION == 'duration'
    assert EXPRESSION == 'expression'
    assert FACE == 'face'
    assert FACES == 'faces'
    assert FILES == 'files'
    assert FORWARD == 'forward'
    assert INCLINO == "inclino"
    assert JOYSTICK == 'self.gamepad'
    assert JSON_AUDIOS == 'json audios'
    assert JSON_CONFIG == 'json config'
    assert JSON_DIRECTORY == 'json directory'
    assert JSON_EXPRESSIONS == 'json expressions'
    assert JSON_LIGHTS == 'json lights'
    assert JSON_LIGHTS_BASE == 'json lights base'
    assert KEY == 'key'
    assert KEYS == 'keys'
    assert LEFT_ARM == 'left_arm'
    assert LEFT_EYE == 'left_eye'
    assert LIGHTS == 'lights'
    assert LOGGING_CONFIG_FILE == 'logging config file'
    assert LOGGING_CONFIG_TEST_FILE == 'logging test config file'
    assert LOGGING_DIRECTORY == "logging directory"
    assert LOGGING_FILE_NAME == 'logging file name'
    assert LOGGING_TEST_FILE_NAME == 'logging test file name'
    assert LOOP == 'loop'
    assert MEDIAS_DIRECTORY == "medias_directory"
    assert METHOD == 'method'
    assert MODE == 'mode'
    assert MOUTH == 'mouth'
    assert MSG_SIZE == "msg_size"
    assert NAME == 'name'
    assert NECK == 'neck'
    assert NORMAL == 'normal'
    assert ORANGE == 'orange'
    assert PROJECT_DIRECTORY == 'project directory'
    assert RANDOM == 'random'
    assert RELAY == 'relay'
    assert RIGHT_ARM == 'right_arm'
    assert RIGHT_EYE == 'right_eye'
    assert SEQUENCES == 'sequences'
    assert SEQUENCES_DIRECTORY == 'sequences directory'
    assert SERIAL_ID == 'serial_id'
    assert SPEAK == 'speak'
    assert SPEED == 'speed'
    assert SYSTEM == 'system'
    assert SRC_DIRECTORY == 'src directory'
    assert VISUAL_DIRECTORY == 'src path'
    assert STOP == 'stop'
    assert ROBOT_LIGHTS == 'robot_lights'
    assert TYPE == 'type'
    assert WHEELS == 'wheels'
    assert WHEEL_LEFT == 'wheel_left'
    assert WHEEL_RIGHT == 'wheel_right'
