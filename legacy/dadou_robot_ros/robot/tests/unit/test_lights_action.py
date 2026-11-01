"""Tests de caractérisation de Lights : figent le routage update()/process()
ACTUEL avant le refactoring prévu des pistes de keyframes.

On exerce le VRAI code de prod (vrais json/robot_lights.json + lights_base.json
+ colors.json, vraie classe Track) ; seules les briques matérielles sont
doublées : le ruban LED (FakeGlobalStrip) et la pile d'animations Adafruit
(FakeLightsAnimations, pour ne PAS dépendre d'adafruit_led_animation, absente
hors Pi). Lights est construit via object.__new__ (comme bare_manager /
bare_servo ailleurs) pour éviter PixelSubset (matériel) dans __init__, tout en
chargeant les vraies séquences via AbstractJsonActions.__init__.
"""

import pytest

from dadou_utils_ros.utils.time_utils import TimeUtils
from dadou_utils_ros.utils_static import (
    BRIGHTNESS, DEFAULT, METHOD, ROBOT_LIGHTS, SEQUENCES, STOP,
)
from robot.robot_static import JSON_COLORS
from dadou_utils_ros.utils_static import JSON_LIGHTS, JSON_LIGHTS_BASE
from robot.robot_config import config
from robot.files.robot_json_manager import RobotJsonManager
from robot.actions.abstract_json_actions import AbstractJsonActions
from robot.actions.lights import Lights
from robot.sequences.track import Track


class FakeGlobalStrip:
    """Ruban LED global factice : Lights n'y touche que brightness (message
    brightness) et, via les animations, __setitem__/show()."""

    def __init__(self, size=1000):
        self.pixels = [None] * size
        self.brightness = 0.05
        self.show_calls = 0

    def __setitem__(self, index, value):
        self.pixels[index] = value

    def __len__(self):
        return len(self.pixels)

    def show(self):
        self.show_calls += 1


class FakeAnimation:
    """Animation Adafruit factice : seule animate() est appelée par Lights."""

    def __init__(self, params):
        self.params = params
        self.animate_calls = 0

    def animate(self):
        self.animate_calls += 1


class FakeLightsAnimations:
    """Remplace LightsAnimations : chaque nom de méthode (solid, chase,
    color_cycle, ...) est une fabrique qui rend une FakeAnimation. hasattr()
    est donc toujours vrai (Lights.load_light_method le vérifie)."""

    def __init__(self):
        self.built = []

    def __getattr__(self, name):
        def factory(params):
            anim = FakeAnimation(params)
            self.built.append((name, anim))
            return anim
        return factory


@pytest.fixture(scope="module")
def json_manager():
    return RobotJsonManager(config)


@pytest.fixture
def clock(monkeypatch):
    state = {"now": 1_000_000}
    monkeypatch.setattr(TimeUtils, "current_milli_time", staticmethod(lambda: state["now"]))
    return state


@pytest.fixture
def make_lights(json_manager):
    def _make(strip=None):
        strip = strip or FakeGlobalStrip()
        lights = object.__new__(Lights)
        # Charge les vraies séquences robot_lights.json (get_sequence réel).
        AbstractJsonActions.__init__(
            lights, config=config, json_manager=json_manager,
            json_file=config[JSON_LIGHTS], action_type=ROBOT_LIGHTS,
        )
        lights.light_type = ROBOT_LIGHTS
        lights.global_strip = strip
        lights.colors = json_manager.get_json_file(config[JSON_COLORS])
        lights.lights_base = lights.load_light_base(config, json_manager)
        lights.animations_methods = FakeLightsAnimations()
        lights.default = DEFAULT
        lights.sequence = {}
        lights.current_animation = {}
        lights.duration = 0
        lights.loop = True
        lights.start_time = 0
        lights.strip = strip
        return lights, strip
    return _make


def default_brick_name(json_manager):
    """Nom de la 1re brique de la séquence lumière 'default' du dépôt."""
    lights_json = json_manager.get_json_file(config[JSON_LIGHTS])
    default_seq = next(s for s in lights_json.values() if s.get(DEFAULT))
    return next(iter(default_seq[SEQUENCES]))


# --- routage update() ---

def test_brightness_message_sets_global_strip_and_returns(make_lights):
    lights, strip = make_lights()

    result = lights.update({ROBOT_LIGHTS: {BRIGHTNESS: 0.42}})

    assert strip.brightness == 0.42
    assert result is None                 # court-circuit : return sans séquence
    assert lights.sequence == {}          # aucune séquence chargée


def test_known_sequence_builds_sequence_and_loads_method(make_lights):
    lights, _ = make_lights()

    lights.update({ROBOT_LIGHTS: "trip"})  # 5 briques, 1re = "sea colorcycle"

    assert isinstance(lights.sequence, Track)
    # load_light_method a construit l'animation de la 1re brique (method color_cycle).
    assert isinstance(lights.current_animation, FakeAnimation)
    assert lights.current_animation.params[METHOD] == "color_cycle"


def test_stop_returns_to_default_sequence(make_lights, json_manager):
    lights, _ = make_lights()

    lights.update({ROBOT_LIGHTS: STOP})

    assert isinstance(lights.sequence, Track)
    assert lights.sequence.last_value.method == default_brick_name(json_manager)


# --- process() : bascule de brique dans le temps ---

def test_process_switches_brick_and_animates(make_lights, clock):
    lights, _ = make_lights()

    lights.update({ROBOT_LIGHTS: "trip"})  # loop, duration 50000, 1re brique à 0.2
    first_method = lights.sequence.last_value.method
    first_anim = lights.current_animation

    lights.process()  # pas encore l'heure de basculer -> animate() de la 1re brique
    assert first_anim.animate_calls >= 1
    assert lights.sequence.last_value.method == first_method

    # au-delà de int(0.2 * 50000) = 10000 ms : time_to_switch -> next()
    clock["now"] += 10001
    lights.process()

    assert lights.sequence.last_value.method != first_method  # brique suivante
    assert isinstance(lights.current_animation, FakeAnimation)
