"""Garde-fou anti-régression du contrat inter-machines dadou_utils_ros.utils_static.

Pourquoi ce test : utils_static.py est importé par TROIS repos (dadou_robot_ros,
../dadou_control_ros, ../dadou_vision_ros) qui ne se recompilent pas ensemble — un
changement de valeur y est silencieux jusqu'à ce qu'un message ne matche plus côté
récepteur. C'est exactement ce qui s'est produit avec le bug MODE (commit c08eb82,
2025-09-27) : une constante partagée modifiée d'un côté a cassé le mode random des
animations (bras/yeux inertes) sans qu'aucun test ne rougisse.

Ce fichier fige donc, constante par constante, la valeur LITTÉRALE de chaque nom du
contrat partagé (topics StringTime, clés de payload JSON, directions, couleurs,
chemins...). Si ce test rougit, c'est qu'une valeur du contrat a changé : il faut
vérifier AVANT de committer que ../dadou_control_ros et ../dadou_vision_ros suivent,
sinon on recrée le bug MODE.

Périmètre : uniquement les constantes utilisées par au moins deux repos (catégories
"control+robot" et "control+robot+vision" de la classification utils_classification).
Les constantes mono-consommateur robot ont été rapatriées dans robot/robot_static.py
(voir son en-tête) et n'ont pas leur place ici : ce test protège le CONTRAT, pas
l'implémentation interne du robot.
"""

from dadou_utils_ros.utils_static import (
    A, B, X, Y, UP, DOWN, LEFT, RIGHT,
    FORWARD, BACKWARD, STOP,
    ANGLO, AUDIO, AUDIOS, AUDIOS_DIRECTORY,
    ANIMATION, ANIMATION_STATE, FACE, FACES,
    WHEELS, WHEEL_LEFT, WHEEL_RIGHT,
    LIGHTS, ROBOT_LIGHTS,
    NECK, LEFT_ARM, RIGHT_ARM, LEFT_EYE, RIGHT_EYE, MOUTH,
    SYSTEM, SPEAK, RELAY,
    KEY, KEYS, NAME, TYPE, MODE, METHOD, COLOR, BRIGHTNESS,
    DURATION, LOOP, SPEED, EXPRESSION, SEQUENCES, DEVICES, FILES, INCLINO, JOYSTICK,
    DEFAULT, NORMAL, RANDOM, ORANGE, MSG_SIZE, SERIAL_ID,
    JSON_AUDIOS, JSON_CONFIG, JSON_DIRECTORY, JSON_EXPRESSIONS,
    JSON_LIGHTS, JSON_LIGHTS_BASE,
    BASE_PATH, CONFIG_DIRECTORY, LOGGING_CONFIG_FILE, LOGGING_CONFIG_TEST_FILE,
    LOGGING_DIRECTORY, LOGGING_FILE_NAME, LOGGING_TEST_FILE_NAME,
    MEDIAS_DIRECTORY, PROJECT_DIRECTORY, SEQUENCES_DIRECTORY, SRC_DIRECTORY,
    VISUAL_DIRECTORY,
    RPI_TYPE,
)


class TestContratGamepadEtDirections:
    """Boutons/axes manette + directions de déplacement.

    Découverte lors de ce chantier : DOWN, LEFT et RIGHT sont chacun assignés
    DEUX FOIS dans utils_static.py (une fois comme libellé de bouton manette
    en MAJUSCULES, une fois comme direction de déplacement en minuscules) —
    Python ne garde que la dernière assignation, donc la valeur EFFECTIVEMENT
    importée est la direction en minuscules. UP, lui, n'a qu'une seule
    assignation et reste 'UP' en majuscules. C'est une incohérence pré-existante
    du contrat (pas touchée par ce lot, qui n'a pas mandat pour modifier
    utils_static.py) — ce test fige la valeur RÉELLEMENT active pour que toute
    correction future de cette incohérence fasse rougir ce test au lieu de
    casser silencieusement un des trois repos.
    """

    def test_gamepad_buttons(self):
        assert A == 'A'
        assert B == 'B'
        assert X == 'X'
        assert Y == 'Y'

    def test_directions(self):
        assert UP == "UP"
        assert DOWN == 'down'
        assert LEFT == 'left'
        assert RIGHT == 'right'
        assert FORWARD == 'forward'
        assert BACKWARD == 'backward'
        assert STOP == 'stop'


class TestContratTopicsStringTime:
    """Noms de topics StringTime (parties du robot pilotées à distance)."""

    def test_topics(self):
        assert WHEELS == 'wheels'
        assert WHEEL_LEFT == 'wheel_left'
        assert WHEEL_RIGHT == 'wheel_right'
        assert LIGHTS == 'lights'
        assert ROBOT_LIGHTS == 'robot_lights'
        assert NECK == 'neck'
        assert LEFT_ARM == 'left_arm'
        assert RIGHT_ARM == 'right_arm'
        assert LEFT_EYE == 'left_eye'
        assert RIGHT_EYE == 'right_eye'
        assert MOUTH == 'mouth'
        assert FACE == 'face'
        assert FACES == 'faces'
        assert SYSTEM == 'system'
        assert SPEAK == 'speak'
        assert RELAY == 'relay'
        assert AUDIO == 'audio'
        assert AUDIOS == 'audios'
        assert ANIMATION == 'animation'
        # animation_state (lot B arbitrage actionneurs, 2026-07-12) : topic
        # latché publié par animations_node, consommé par gaze_follower_node
        # (robot) ET chat_node (vision) -> contrat inter-repos comme les autres
        # constantes de cette classe.
        assert ANIMATION_STATE == 'animation_state'


class TestContratClesPayload:
    """Clés génériques utilisées dans les payloads JSON échangés entre repos."""

    def test_cles_payload(self):
        assert KEY == 'key'
        assert KEYS == 'keys'
        assert NAME == 'name'
        assert TYPE == 'type'
        # 'mode' minuscule : clé des keyframes servo des séquences JSON. Ne pas
        # confondre avec un éventuel MODE majuscule — cf. bug c08eb82 (2025-09-27).
        assert MODE == 'mode'
        assert METHOD == 'method'
        assert COLOR == 'color'
        assert BRIGHTNESS == 'brightness'
        assert DURATION == 'duration'
        assert LOOP == 'loop'
        assert SPEED == 'speed'
        assert EXPRESSION == 'expression'
        assert SEQUENCES == 'sequences'
        assert DEVICES == 'devices'
        assert FILES == 'files'
        assert INCLINO == "inclino"
        assert JOYSTICK == 'self.gamepad'
        assert DEFAULT == 'default'
        assert NORMAL == 'normal'
        assert RANDOM == 'random'
        assert ORANGE == 'orange'
        assert MSG_SIZE == "msg_size"
        assert SERIAL_ID == 'serial_id'
        assert ANGLO == 'anglo'


class TestContratClesFichiersJson:
    """Clés désignant les fichiers JSON de configuration partagés."""

    def test_cles_json(self):
        assert JSON_AUDIOS == 'json audios'
        assert JSON_CONFIG == 'json config'
        assert JSON_DIRECTORY == 'json directory'
        assert JSON_EXPRESSIONS == 'json expressions'
        assert JSON_LIGHTS == 'json lights'
        assert JSON_LIGHTS_BASE == 'json lights base'


class TestContratCheminsEtRepertoires:
    """Chemins/répertoires du contrat (identiques sur les machines concernées)."""

    def test_chemins(self):
        assert AUDIOS_DIRECTORY == 'audios directory'
        assert BASE_PATH == 'base path'
        assert CONFIG_DIRECTORY == 'config directory'
        assert LOGGING_CONFIG_FILE == 'logging config file'
        assert LOGGING_CONFIG_TEST_FILE == 'logging test config file'
        assert LOGGING_DIRECTORY == "logging directory"
        assert LOGGING_FILE_NAME == 'logging file name'
        assert LOGGING_TEST_FILE_NAME == 'logging test file name'
        assert MEDIAS_DIRECTORY == "medias_directory"
        assert PROJECT_DIRECTORY == 'project directory'
        assert SEQUENCES_DIRECTORY == 'sequences directory'
        assert SRC_DIRECTORY == 'src directory'
        # Valeur surprenante mais réelle : VISUAL_DIRECTORY vaut 'src path', pas
        # un chemin visuel. Figé tel quel, ce n'est pas le rôle de ce test de
        # corriger le contrat, seulement de détecter s'il bouge sans le vouloir.
        assert VISUAL_DIRECTORY == 'src path'


class TestContratPlateforme:
    """Identification de plateforme (Raspberry Pi vs laptop de dev)."""

    def test_rpi_type(self):
        assert RPI_TYPE == ['armv7l', 'aarch64']
