# Imports matériels différés (pattern wheels.py) : le module doit s'importer sans les libs Pi.
import logging.config

from dadou_utils_ros.utils.time_utils import TimeUtils
from robot.robot_static import JSON_COLORS
from dadou_utils_ros.utils_static import METHOD, DEFAULT, DURATION, SEQUENCES, LOOP, COLOR, \
    NAME, JSON_LIGHTS_BASE, BRIGHTNESS, STOP
from robot.actions.abstract_json_actions import AbstractJsonActions
from robot.sequences.track import Track
from robot.visual.lights_animations import LightsAnimations

"""
          "method": "sparkle_pulse",
          "color": "AMBER"
          "method": "chase",
          "color": "RED"
          "method": "blink",
          "color": "BLUE"
          "method": "color_cycle"
          "method": "pulse",
          "color": "BLUE"
          "method": "rainbow_chase"
          "method": "rainbow_comet"
          "method": "color_cycle"
          "method": "comet"
"""


class Lights(AbstractJsonActions):
    # Le nombre de LED et les bornes de la zone « corps » viennent du config
    # (LIGHTS_LED_COUNT / LIGHTS_START_LED / LIGHTS_END_LED), passés à __init__.
    # Ne PAS recoder de constantes de longueur ici : le ruban physique peut changer.

    # TODO check examples : https://www.digikey.fr/en/maker/projects/circuitpython-led-animations/d15c769c6f6d411297657c35f0166958

    def __init__(self, config, start, end, json_manager, global_strip, light_type, json_light):
        # État par instance (était au niveau classe = partagé entre l'éclairage
        # corps et le visage, piège Python).
        self.sequence = {}
        self.current_animation = {}
        self.animations_methods = {}
        self.default = DEFAULT
        self.duration = 0
        self.start_time = 0

        self.light_type = light_type
        super().__init__(config=config, json_manager=json_manager, action_type=self.light_type, json_file=json_light)

        logging.info("starting lights")

        self.global_strip = global_strip
        # PixelSubset vient d'adafruit_led_animation (lib Pi) : import différé.
        from adafruit_led_animation.helper import PixelSubset
        self.strip = PixelSubset(global_strip, start, end)
        self.colors = json_manager.get_json_file(config[JSON_COLORS])
        self.lights_base = self.load_light_base(config, json_manager)
        self.animations_methods = LightsAnimations(end - start, self.strip)
        self.update({light_type: DEFAULT})

    def load_light_base(self, config, json_manager):
        lights_base = json_manager.get_json_file(config[JSON_LIGHTS_BASE])
        for light_name in lights_base:
            if COLOR in lights_base[light_name]:
                lights_base[light_name][COLOR] = self.get_color(lights_base[light_name][COLOR])

        return lights_base

    def update(self, msg):

        if msg[self.light_type] == STOP:
            self.update({self.light_type: self.default})

        if BRIGHTNESS in msg[self.light_type]:
            logging.info("update brightness to {}".format(msg[self.light_type][BRIGHTNESS]))
            self.global_strip.brightness = float(msg[self.light_type][BRIGHTNESS])
            return

        json_seq = self.get_sequence(msg, True)
        if not json_seq:
            return

        if DURATION in msg and msg[DURATION] != 0:
            self.duration = msg[DURATION]
        else:
            self.duration = json_seq[DURATION]
        self.loop = json_seq[LOOP]

        if DEFAULT in json_seq:
            self.default = json_seq[NAME]

        # Chaque entrée de séquence = {nom_de_brique: position_relative_0..1}.
        # La couleur n'est PAS portée à ce niveau : elle vient de lights_base.json,
        # résolue en RGB par load_light_base() puis appliquée à l'animation Adafruit
        # dans load_light_method(). L'ancienne branche de « surcharge couleur » a été
        # retirée : son test (COLOR dans une liste [position, LightAnimation]) était
        # toujours faux et l'indexation animation[COLOR] aurait levé une TypeError.
        sequences = []
        for brick_name, position in json_seq[SEQUENCES].items():
            sequences.append([position, LightAnimation(brick_name, position)])
        self.start_time = TimeUtils.current_milli_time()
        # Lights « affiche jusqu'à t » : brique i active jusqu'à t_i*duration.
        # Un poll immédiat charge la 1re brique juste après (activation à 0).
        self.sequence = Track.frames(sequences, json_seq[DURATION], json_seq[LOOP], self.start_time)
        first = self.sequence.poll(self.start_time)
        if first:
            self.load_light_method(first.method)
        logging.info("update lights {} sequences to {}".format(self.light_type, json_seq[NAME]))

    def load_light_method(self, light_name):

        if light_name not in self.lights_base:
            logging.error("{} not in lights base".format(light_name))
            return
        light = self.lights_base[light_name]
        if not hasattr(self.animations_methods, light[METHOD]):
            logging.error('{} not in lights base'.format(light[METHOD]))
            return
        self.current_animation = getattr(self.animations_methods, light[METHOD])(
            light)

    def get_color(self, color_name):
        if color_name in self.colors:
            return self.colors[color_name][0], self.colors[color_name][1], self.colors[color_name][2]
        else:
            logging.error("color {} not defined".format(color_name))

    def process(self):
        if not self.loop and TimeUtils.is_time(self.start_time, self.duration):
            self.update({self.light_type: self.default})

        # poll : la brique suivante sort quand son instant est atteint (une par
        # tick). Rien à changer tant que poll rend None (on rejoue l'animation
        # Adafruit courante). Boucle gérée par Track.
        value = self.sequence.poll(TimeUtils.current_milli_time())
        if value:
            self.load_light_method(value.method)

        self.current_animation.animate()


class LightAnimation:

    def __init__(self, method, duration: int):
        logging.debug("add animation method : " + method + " duration : " + str(duration))
        self.method = method
        self.duration = duration
        # Était évalué À L'IMPORT du module (attribut de classe) : figé à l'instance.
        self.start_time = TimeUtils.current_milli_time()
