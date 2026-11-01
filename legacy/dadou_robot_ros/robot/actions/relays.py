# Imports matériels différés (pattern wheels.py) : le module doit s'importer sans les libs Pi.
import logging

from dadou_utils_ros.misc import Misc
from dadou_utils_ros.utils.time_utils import TimeUtils
from robot.robot_static import I2C_ENABLED, DIGITAL_CHANNELS_ENABLED, JSON_RELAYS, OFF
from dadou_utils_ros.utils_static import RELAY, NAME
from robot.actions.abstract_json_actions import AbstractJsonActions



class RelaysManager(AbstractJsonActions):

    SWITCH = "switch"
    KLAXON = "klaxon"
    HF_RECEIVER = "hf_receiver"
    EFFECT = "effect_on"
    VOICE_OUT = "voice_out"

    NORMAL_VOICE = "normal_voice"
    PITCHED_VOICE = "pitched_voice"

    def __init__(self, config, json_manager):
        super().__init__(config=config, json_manager=json_manager, json_file=config[JSON_RELAYS], action_type=RELAY)
        self.config = config

        self.i2c_enabled = (self.config[I2C_ENABLED] or self.config[DIGITAL_CHANNELS_ENABLED]) and Misc.is_raspberrypi()
        logging.info("init  {} relays i2c enabled {}".format(type, Misc.is_raspberrypi()))

        if not self.i2c_enabled:
            logging.warning("i2c digital disabled")
            return

        self.json_manager = json_manager

        # Les libs Adafruit ne sont importables que sur le Pi (I2C présent).
        import adafruit_pcf8574
        import board

        i2c = board.I2C()  # uses board.SCL and board.SDA
        pcf = adafruit_pcf8574.PCF8574(i2c, address=0x21)

        self.power_hf = pcf.get_pin(3)
        self.power_hf.value = True
        self.klaxon = pcf.get_pin(2)
        self.klaxon.value = True
        self.effect = pcf.get_pin(1)
        self.effect.value = True
        self.voice_out = pcf.get_pin(0)
        self.voice_out.value = True

        self.manual_switch = False

        self.last_effect_time = 0
        self.effect_timeout = 2000

        self.last_klaxon_time = 0
        self.klaxon_timeout = 1000

        #self.last_input_msg_time = 0
        #self.input_msg_timeout = 300

    def update(self, msg):

        #if not TimeUtils.is_time(self.last_input_msg_time, self.input_msg_timeout):
        #    return
        #self.last_input_msg_time = TimeUtils.current_milli_time()

        if not self.i2c_enabled:
            return msg

        relay = self.get_sequence(msg, True)

        if relay:
            if relay[NAME] == self.PITCHED_VOICE:
                self.pitched_voice()

            if relay[NAME] == self.NORMAL_VOICE:
                self.normal_voice()

            if relay[NAME] == self.KLAXON:
                self.klaxon.value = False
                self.last_klaxon_time = TimeUtils.current_milli_time()
                logging.info("klaxon {}".format(self.klaxon.value))

            if relay[NAME] == self.HF_RECEIVER:
                self.power_hf.value = not self.power_hf.value
                logging.info("switch hf receiver {}".format(self.power_hf.value))

            if relay[NAME] == self.EFFECT:
                #self.effect.value = True
                self.voice_out.value = False
                self.last_effect_time = TimeUtils.current_milli_time()
                logging.info("switch effect on")

            if relay[NAME] == OFF:
                    #self.manual_switch = False
                    self.last_effect_time = 0
                    logging.info("manual switch off")
                    #msg.update({ANIMATION: SPEAK})
                    #self.global_receiver.write_msg_plus_time({ANIMATION: False})

        return msg

    def pitched_voice(self):
        self.voice_out.value = False
        self.effect.value = True
        self.last_effect_time = TimeUtils.current_milli_time()
        logging.info("switch effect on")

    def normal_voice(self):
        self.voice_out.value = False
        self.effect.value = False
        self.last_effect_time = TimeUtils.current_milli_time()
        logging.info("switch effect on")

    def process(self):

        if not self.i2c_enabled:
            return

        if not self.voice_out.value and TimeUtils.is_time(self.last_effect_time, self.effect_timeout):
            #self.effect.value = False
            self.voice_out.value = True
            logging.info("effect off")

        if not self.klaxon.value and TimeUtils.is_time(self.last_klaxon_time, self.klaxon_timeout):
            self.klaxon.value = True
            logging.info("klaxon off")
