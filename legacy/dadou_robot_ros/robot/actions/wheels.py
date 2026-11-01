import logging

from dadou_utils_ros.misc import Misc
from dadou_utils_ros.utils.time_utils import TimeUtils
from robot.robot_static import CMD_FORWARD, CMD_BACKWARD, CMD_LEFT, CMD_RIGHT, I2C_ENABLED, \
    PWM_CHANNELS_ENABLED, WHEEL_LEFT_PWM, WHEEL_RIGHT_PWM, WHEEL_LEFT_DIR, WHEEL_RIGHT_DIR, \
    STRAIGHT, DIGITAL_CHANNELS_ENABLED
from dadou_utils_ros.utils_static import ANGLO, WHEEL_RIGHT, WHEEL_LEFT, WHEELS, KEY, ANIMATION, \
    STOP, FORWARD, BACKWARD, LEFT, RIGHT, INCLINO, SPEED, JOYSTICK, X, Y, DURATION
from robot_drive.diff_drive import DiffDrive
from robot_drive.joystick_mixer import translate
from robot.robot_config import MAX_PWM_L, MAX_PWM_R
from robot.actions.action import Action


class Wheels(Action):
    left = 0
    right = 0
    mode = None

    # TODO check steps
    PWM_STEP = 5
    TIME_STEP = 50
    move_time = 0
    MOVE_TIMEOUT = 400
    # Pendant une animation le deadman 400ms est remplacé par une échéance absolue :
    # temps restant annoncé par animations_node + marge. Si aucun temps restant n'est
    # reçu, un plafond de secours borne quand même le mouvement.
    ANIMATION_STOP_MARGIN = 2000
    ANIMATION_FALLBACK_TIMEOUT = 30000
    animation_deadline = 0
    MIN_PWM = 5000
    MAX_DIR = 65530
    FREQUENCY = 500

    # Cinématique différentielle du mode /cmd_vel : mêmes défauts que le
    # wheels_bridge (robot_drive) pour que sim et vrai robot partagent la même
    # conversion Twist -> paire roues.
    WHEEL_SEPARATION = 0.58
    MAX_WHEEL_SPEED = 1.0

    starting_angle_x = 0
    target_pos_x = 0
    half_turn = False
    front_pos = 0

    front_pos_margin = 3
    angle_margin = 5

    sensor = None

    animation_ongoing = False

    test_speed = 0
    test_direction = 0
    last_move = 0

    def __init__(self, config, pca9685=None):

        self.config = config

        self.max_pwm_l = MAX_PWM_L
        self.max_pwm_r = MAX_PWM_R

        # Convertisseur Twist -> paire roues du mode /cmd_vel (voir apply_twist).
        # Pur (stdlib), créé même si le PWM est désactivé : inoffensif hors mode.
        self.cmd_vel_diff_drive = DiffDrive(
            wheel_separation=self.WHEEL_SEPARATION,
            max_wheel_speed=self.MAX_WHEEL_SPEED,
        )

        # Un pca9685 injecté (faux matériel en test, futur hardware_interface
        # ros2_control) court-circuite la détection Raspberry Pi.
        self.enabled = pca9685 is not None or \
            ((self.config[I2C_ENABLED] or self.config[DIGITAL_CHANNELS_ENABLED]) and Misc.is_raspberrypi())
        logging.info("init  {} wheels i2c enabled {}".format(type, Misc.is_raspberrypi()))
        if not self.enabled:
            logging.warning("i2c pwm disabled")
            return

        if pca9685 is None:
            # Les libs Adafruit ne sont importables que sur le Pi.
            import adafruit_pca9685
            import board
            import busio
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                pca9685 = adafruit_pca9685.PCA9685(i2c)
                pca9685.frequency = 60
            except ValueError:
                logging.error("can't connect to to i2c")
                self.enabled = False
                return

        self.left_pwm = pca9685.channels[self.config[WHEEL_LEFT_PWM]]
        self.right_pwm = pca9685.channels[self.config[WHEEL_RIGHT_PWM]]
        self.dir_left = pca9685.channels[self.config[WHEEL_LEFT_DIR]]
        self.dir_right = pca9685.channels[self.config[WHEEL_RIGHT_DIR]]

    def set_9dof(self, sensor):
        self.sensor = sensor

    def update(self, msg):
        if not self.enabled or not msg:
            return msg

        if ANIMATION in msg:
            self.animation_ongoing = msg[ANIMATION]
            if self.animation_ongoing:
                remaining = msg[DURATION] if DURATION in msg else self.ANIMATION_FALLBACK_TIMEOUT
                self.animation_deadline = TimeUtils.current_milli_time() + remaining + self.ANIMATION_STOP_MARGIN

        if KEY in msg and (msg[KEY] == self.config[FORWARD] or msg[KEY] == self.config[BACKWARD] or msg[KEY] == self.config[LEFT] or msg[KEY] == self.config[RIGHT]):
            if msg[KEY] == self.config[CMD_FORWARD]:
                self.update_cmd(50, 50)
            elif msg[KEY] == self.config[CMD_BACKWARD]:
                self.update_cmd(-50, -50)
            elif msg[KEY] == self.config[CMD_LEFT]:
                self.update_cmd(-50, 50)
            elif msg[KEY] == self.config[CMD_RIGHT]:
                self.update_cmd(50, -50)

        if INCLINO in msg:
            left, right = translate(turn=msg[ANGLO][X], forward=msg[ANGLO][Y])
            self.update_cmd(left, right)
        if JOYSTICK in msg:
            left, right = translate(turn=msg[JOYSTICK][X], forward=msg[JOYSTICK][Y])
            self.update_cmd(left, right)
        if WHEELS in msg:
            logging.info(" wheels input {}".format(msg[WHEELS]))
            if msg[WHEELS] == STOP:
                self.stop()
                return msg
            if SPEED in msg[WHEELS]:
                max_speed = int((self.MAX_DIR / 100) * int(msg[WHEELS][SPEED]))
                logging.info("update max speed to {}".format(max_speed))
                self.max_pwm_r = max_speed
                self.max_pwm_l = max_speed
                return msg
            if LEFT in msg[WHEELS] and RIGHT in msg[WHEELS]:
                self.update_cmd(msg[WHEELS][LEFT], msg[WHEELS][RIGHT])
                return msg
            if (hasattr(msg[WHEELS], "__len__") and len(msg[WHEELS]) == 2 and
                    0 <= msg[WHEELS][0] <= 1 and 0 <= msg[WHEELS][1] <= 1):
                self.update_cmd(int(msg[WHEELS][0]*100), int(msg[WHEELS][1]*100))
                return msg
            try:
                if msg[WHEELS] == FORWARD:
                    self.update_cmd(50, 50)
                elif msg[WHEELS] == BACKWARD:
                    self.update_cmd(-50, -50)
                elif msg[WHEELS] == LEFT:
                    self.update_cmd(-50, 50)
                elif msg[WHEELS] == RIGHT:
                    self.update_cmd(50, -50)
                else:
                    self.update_cmd(int(msg[WHEELS][0]*100), int(msg[WHEELS][1]*100))
            except TypeError:
                logging.error("can't process {}".format(msg[WHEELS]))

        return msg

    def update_cmd(self, left_wheel, right_wheel):
        self.left = left_wheel
        self.right = right_wheel

        self.left_pwm.duty_cycle = Misc.mapping(abs(left_wheel), 0, 100, self.MIN_PWM, self.max_pwm_l)
        self.right_pwm.duty_cycle = Misc.mapping(abs(right_wheel), 0, 100, self.MIN_PWM, self.max_pwm_r)

        self.set_direction(left_wheel, self.dir_left)
        self.set_direction(right_wheel, self.dir_right)

        self.move_time = TimeUtils.current_milli_time()
        logging.info("cmd left {} duty cycle {} direction {} // cmd right {} duty cycle {} direction {}".
                        format(left_wheel, self.left_pwm.duty_cycle, self.dir_left.duty_cycle, right_wheel, self.right_pwm.duty_cycle, self.dir_right.duty_cycle))


    def apply_twist(self, linear_x, angular_z):
        """Consomme un Twist /cmd_vel (mode WHEELS_CMD_VEL_ENABLED) : cinématique
        différentielle -> paire roues [-1, 1] -> PWM (update_cmd attend des pourcents).

        Le deadman check_stop() 400 ms reste ACTIF ici : c'est le dernier rempart
        local si toute la chaîne ROS amont (twist_mux + twist_deadman) meurt (plus
        de Twist -> coupure PWM locale). La logique animation_deadline ne s'active
        pas dans ce mode : animation_ongoing reste False (le mux + le deadman amont
        arbitrent déjà remote/animation), donc check_stop applique le deadman 400 ms.
        """
        if not self.enabled:
            return

        left, right = self.cmd_vel_diff_drive.twist_to_wheels(linear_x, angular_z)
        left_pct = int(left * 100)
        right_pct = int(right * 100)

        # Twist nul -> coupure franche : update_cmd(0, 0) remonterait le PWM à
        # MIN_PWM (les roues avanceraient au ralenti), il faut donc passer par stop().
        # Mais UNE seule fois : au repos, le twist_deadman amont inonde /cmd_vel de
        # zéros à 20 Hz — marteler stop() noierait robot.log (constaté au protocole
        # caméra du 2026-07-04 : une ligne "wheels stopped" toutes les 50 ms).
        if left_pct == 0 and right_pct == 0:
            if self.left_pwm.duty_cycle != 0 or self.right_pwm.duty_cycle != 0:
                self.stop()
            return

        self.update_cmd(left_pct, right_pct)

    def set_direction(self, cmd_dir, pwm_dir):
        if cmd_dir >= 0:
            pwm_dir.duty_cycle = 0
        else:
            pwm_dir.duty_cycle = self.MAX_DIR

    def test(self):
        self.dir_left = False
        self.dir_right = False
        self.left_pwm.duty_cycle = 10000
        self.right_pwm.duty_cycle = 10000

    def stop(self):
        self.left_pwm.duty_cycle = 0
        self.right_pwm.duty_cycle = 0
        logging.info("wheels stopped")

    def check_stop(self):

        if not self.enabled:
            return

        if self.left_pwm.duty_cycle == 0 and self.right_pwm.duty_cycle == 0:
            return

        if self.animation_ongoing:
            if TimeUtils.current_milli_time() > self.animation_deadline:
                logging.warning("wheels deadman: animation deadline exceeded, stopping wheels")
                self.stop()
                self.animation_ongoing = False
        elif TimeUtils.is_time(last_time=self.move_time, time_out=self.MOVE_TIMEOUT):
            self.stop()

    def process(self):

        if not self.enabled:
            return

        if self.mode == STRAIGHT:
            self.move_straight()

        self.check_stop()

    def move_straight(self):
        if self.starting_angle_x != -1 and self.sensor:
            if self.starting_angle_x > self.sensor.euler[0]:
                self.update_cmd(self.left+1, self.right-1)
            else:
                self.update_cmd(self.left-1, self.right+1)

    def start_circle(self, left, right):
        if self.sensor:
            self.half_turn = False
            self.starting_angle_x = self.sensor.euler[0]
            self.update_cmd(left, right)
        else:
            logging.error("9dof not set")

    def move_circle(self):
        if self.starting_angle_x != -1 and self.sensor:
            if self.half_turn and abs(self.starting_angle_x - self.sensor.euler[0]) <= self.angle_margin:
                return True
            if not self.half_turn and abs(self.starting_angle_x - self.sensor.euler[0]) > 180:
                self.half_turn = True
        return False

    def set_front_pos(self):
        if self.sensor:
            self.front_pos = self.sensor.euler[0]
        else:
            logging.error("9dof not set")

    def get_back_front(self):
        if self.sensor:
            if abs(self.sensor.euler[0] - self.front_pos) < self.front_pos_margin:
                logging.info("front position reached")
            else:
                if self.sensor.euler[0] - self.front_pos:
                    self.update_cmd(self.left - 1, self.right + 1)

        else:
            logging.error("9dof not set")
        return False

