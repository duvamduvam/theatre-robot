# Imports matériels différés (pattern wheels.py) : le module doit s'importer sans les libs Pi.
import logging
import random

from dadou_utils_ros.misc import Misc
from dadou_utils_ros.utils.time_utils import TimeUtils
from robot.robot_static import RANDOM_MOVE_MAX, RANDOM_MOVE_MIN, RANDOM_TIME_MAX, \
    RANDOM_TIME_MIN, RANDOM_DURATION
from dadou_utils_ros.utils_static import NORMAL, RANDOM, MODE, ANIMATION, UP, DOWN, STOP, DEFAULT, \
    DURATION
from robot.actions.action import Action

INPUT_MIN = 0
INPUT_MAX = 99

SERVO_MIN = 0
STEP = 5


class Servo(Action):
    # --- Rampe ---
    # Vitesse de rampe, en unités de consigne (échelle 0-99) par SECONDE.
    # 160 => ~0,6 s pour la pleine course (99 unités) : assez vif pour le jeu
    # scénique, assez lent pour gommer les à-coups ; à caler sur scène.
    # Avant, Servo écrivait la consigne d'un seul coup (saut sec) sur l'I2C ;
    # désormais update() ne fixe QUE la cible et process() (20 Hz) fait avancer
    # la position réelle vers elle à cette vitesse.
    RAMP_SPEED = 160

    # --- Deadman servo (motif roues, cf. Wheels.ANIMATION_STOP_MARGIN) ---
    # Marge ajoutée au temps restant annoncé par animations_node avant de
    # présumer le node mort et de ramener le servo au repos. MÊME valeur que les
    # roues : les deux chaînes partagent la même sémantique d'arrêt de secours.
    ANIMATION_STOP_MARGIN = 2000

    random_time_min = 0
    random_time_max = 0
    random_move_min = 0
    random_move_max = 0
    random_last_time = 0
    random_next_time = 0
    random_start_time = 0
    random_duration = 0

    # Échéance absolue (ms) du deadman servo ; 0 = désarmé.
    animation_deadline = 0

    def __init__(self, servo_type, pwm_channel_nb, default_pos, servo_max, i2c_enabled, pwm_channels_enabled):

        self.enabled = (i2c_enabled or pwm_channels_enabled) and Misc.is_raspberrypi()
        logging.info("init  {} servo i2c enabled {}".format(servo_type, Misc.is_raspberrypi()))

        if not self.enabled:
            return

        # ServoKit vient d'adafruit_servokit (I2C PCA9685), lib Pi : import différé.
        from adafruit_servokit import ServoKit
        try:
            self.self_pwm_channels = ServoKit(channels=16)
            self.pwm_channel = self.self_pwm_channels.servo[pwm_channel_nb]

        except ValueError as err:
            logging.error("{} : can't connect to i2c".format(servo_type))
            self.enabled = False
            return

        self.servo_type = servo_type
        self.mode = NORMAL
        self.servo_max = servo_max
        self.default_pos = default_pos

        # État de la rampe (échelle 0-99, celle des messages) :
        #  - current_pos suit la position réelle du servo. Initialisé à
        #    default_pos car on amène PHYSIQUEMENT le servo au repos au démarrage
        #    (comportement conservé de l'ancien set_angle(default_pos) en fin
        #    d'__init__) : le suivi interne doit refléter cette position de départ.
        #  - target_pos est la consigne que la rampe cherche à atteindre.
        self.current_pos = default_pos
        self.target_pos = default_pos
        # Dernier angle ENTIER réellement écrit sur l'I2C (anti-spam, cf.
        # _write_hardware). None = rien d'écrit encore.
        self._last_written_angle = None
        # Horodatage du dernier process() pour mesurer le dt RÉEL de la rampe
        # (jamais supposé 50 ms : un tick peut arriver en retard).
        self._last_process_time = TimeUtils.current_milli_time()
        self.animation_deadline = 0

        # Amène physiquement le servo au repos au démarrage (écriture directe).
        self._write_hardware()

    def update(self, msg):

        if not self.enabled:
            return msg

        logging.info("{} servo update with {}".format(self.servo_type, msg))

        # --- Deadman servo (motif roues, cf. Wheels.update) ---
        # Une keyframe d'animation (anim=True) annonce le temps RESTANT de la
        # séquence dans DURATION (rempli par animations_node = remaining_ms()).
        # On arme une échéance absolue : si animations_node meurt en pleine
        # animation, un mode random tournerait POUR TOUJOURS (aucun deadman
        # n'existait avant). process() ramène alors le servo au repos passé
        # cette échéance. Un nouveau message d'animation la réarme ; un STOP la
        # désarme (voir plus bas).
        if msg.get(ANIMATION) and msg.get(DURATION, 0) > 0:
            self.animation_deadline = TimeUtils.current_milli_time() + msg[DURATION] + self.ANIMATION_STOP_MARGIN

        if msg[self.servo_type] == STOP:
            logging.info("update {} servo with default pos {}".format(self.servo_type, self.default_pos))
            self.set_target(self.default_pos)
            self.mode = NORMAL
            self.animation_deadline = 0  # STOP désarme le deadman

        #parameter default angle
        if msg and self.servo_type in msg and isinstance(msg[self.servo_type], dict) and DEFAULT in msg[self.servo_type]:
            default_angle = float(msg[self.servo_type][DEFAULT])
            logging.info("{} servo default {}".format(self.servo_type, default_angle))
            self.default_pos = default_angle
            self.set_target(default_angle)

        if msg and self.servo_type in msg:
            if msg[self.servo_type] == UP:
                # ±STEP sur la CIBLE, à partir du suivi interne current_pos (et
                # NON plus d'une LECTURE de pwm_channel.angle : une transaction
                # I2C de moins par clic). La rampe fait le reste.
                if self.current_pos < INPUT_MAX - STEP:
                    self.target_pos = self.current_pos + STEP
            elif msg[self.servo_type] == DOWN:
                if self.current_pos > STEP:
                    self.target_pos = self.current_pos - STEP
            elif isinstance(msg[self.servo_type], (int, float)) and not isinstance(msg[self.servo_type], bool):
                self.set_target(msg[self.servo_type])
                self.mode = NORMAL
            else:
                if isinstance(msg[self.servo_type], dict) and MODE in msg[self.servo_type]:
                    #let the last instruction finish
                    if self.mode == RANDOM:
                        return
                    self.mode = msg[self.servo_type][MODE]
                    if self.mode == RANDOM:
                        if RANDOM_MOVE_MAX in msg[self.servo_type] and RANDOM_MOVE_MIN in msg[self.servo_type]\
                                and RANDOM_TIME_MAX in msg[self.servo_type] and RANDOM_TIME_MIN in msg[self.servo_type]:
                            self.random_time_min = msg[self.servo_type][RANDOM_TIME_MIN]
                            self.random_time_max = msg[self.servo_type][RANDOM_TIME_MAX]
                            self.random_move_min = msg[self.servo_type][RANDOM_MOVE_MIN]
                            self.random_move_max = msg[self.servo_type][RANDOM_MOVE_MAX]
                            # FIX random_duration : la clé se lit au niveau
                            # msg[servo_type] (DANS le dict du servo), comme le
                            # font les vraies séquences JSON et la sim (ServoSim,
                            # référence de sémantique). L'ancien code testait
                            # `RANDOM_DURATION in msg` (le dict TOP-LEVEL, qui ne
                            # porte que servo_type et parfois DURATION) : toujours
                            # faux -> le random ne se terminait jamais tout seul.
                            # Divergence documentée dans servos_logic.py : résolue.
                            self.random_duration = msg[self.servo_type].get(RANDOM_DURATION, 0)
                            self.random_start_time = TimeUtils.current_milli_time() if self.random_duration else 0
                            self.random_last_time = TimeUtils.current_milli_time()
                            self.random_next_time = random.randint(self.random_time_min, self.random_time_max)
                        else:
                            logging.error("missing parameter in random instruction {}".format(msg[self.servo_type]))
                            self.mode = RANDOM

        return msg

    def set_target(self, value):
        """Fixe la CIBLE de la rampe (échelle 0-99). Ne touche PAS le matériel :
        c'est process() qui fait avancer current_pos vers la cible et écrit
        l'I2C. Conserve le quirk historique de set_angle : une valeur dans ]0,1]
        est interprétée comme une fraction et ramenée sur 0-99 (*100)."""
        if 0 < value <= 1:
            value = value * 100
        self.target_pos = max(INPUT_MIN, min(INPUT_MAX, value))
        logging.debug("update servo {} target {}".format(self.servo_type, self.target_pos))

    def _write_hardware(self):
        """Convertit current_pos (0-99) en angle physique (0-servo_max) et
        l'écrit sur l'I2C UNIQUEMENT si l'angle ENTIER à écrire change.

        Anti-spam : aligne le vrai robot sur le garde _dirty de la sim. Avant,
        Servo réécrivait pwm_channel.angle à chaque appel même à valeur
        inchangée (bus PCA9685 martelé à 20 Hz, servo qui vibre sur des
        micro-variations sous le degré). On ne réécrit désormais qu'un vrai
        changement d'angle entier."""
        angle = int(Misc.mapping(self.current_pos, INPUT_MIN, INPUT_MAX, SERVO_MIN, self.servo_max))
        if angle != self._last_written_angle:
            self.pwm_channel.angle = angle
            self._last_written_angle = angle

    def _advance_ramp(self, now):
        """Avance current_pos vers target_pos à RAMP_SPEED, avec le dt RÉEL
        écoulé depuis le dernier process() (et non 50 ms supposés)."""
        dt = (now - self._last_process_time) / 1000.0
        if dt <= 0:
            return
        step = self.RAMP_SPEED * dt
        delta = self.target_pos - self.current_pos
        if abs(delta) <= step:
            self.current_pos = self.target_pos  # évite le dépassement (overshoot)
        else:
            self.current_pos += step if delta > 0 else -step

    def process(self):
        if not self.enabled:
            return

        now = TimeUtils.current_milli_time()

        # Deadman servo : échéance dépassée -> retour au repos et arrêt du random.
        if self.animation_deadline and now > self.animation_deadline:
            logging.info("deadman servo {} : retour au repos".format(self.servo_type))
            self.target_pos = self.default_pos
            self.mode = NORMAL
            self.animation_deadline = 0

        if self.mode == RANDOM:
            # Sortie du random à échéance : on suit la sim (ServoSim.tick) ->
            # retour NORMAL, la position reste où le dernier tirage l'a laissée
            # (seul "stop" recentre au default).
            if self.random_start_time != 0 and TimeUtils.is_time(self.random_start_time, self.random_duration):
                self.mode = NORMAL
            elif TimeUtils.is_time(self.random_last_time, self.random_next_time):
                # Le random tire une nouvelle CIBLE ; la rampe l'atteint
                # progressivement (avant : saut sec via set_angle).
                self.target_pos = random.randint(self.random_move_min, self.random_move_max)
                self.random_last_time = now
                self.random_next_time = random.randint(self.random_time_min, self.random_time_max)

        self._advance_ramp(now)
        self._last_process_time = now
        self._write_hardware()
