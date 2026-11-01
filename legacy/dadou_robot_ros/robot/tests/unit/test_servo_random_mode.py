"""Test anti-régression du bug MODE (c08eb82, 2025-09-27) : la constante Python
MODE valait 'MODE' (majuscule) au lieu de 'mode', alors que la clé réelle des
keyframes servo dans les séquences JSON est 'mode' (minuscule, cf.
utils_static.MODE). Résultat : `msg[self.servo_type][MODE]` dans Servo.update()
ne matchait plus jamais rien -- le mode random ne s'armait plus, bras/yeux/cou
restaient inertes pendant les animations. Corrigé côté dadou_utils_ros.

Pour rester un vrai garde-fou, ce test passe par la VRAIE keyframe JSON d'une
séquence jouée en spectacle (pas une constante recopiée à la main qui aurait pu
être « corrigée » en même temps que le bug) : si le format de séquence dérive
ou si la clé JSON change, le test doit casser lui aussi.
"""

import json
import os
import sys
import types

import pytest

# adafruit_servokit est une lib matériel (I2C PCA9685) absente de l'hôte de dev
# et de la CI. robot.actions.servo fait `from adafruit_servokit import ServoKit`
# au niveau module : sans stub, la seule collecte du test lève
# ModuleNotFoundError avant même d'atteindre object.__new__(Servo). Le stub doit
# donc être posé AVANT le premier import de robot.actions.servo.
_fake_adafruit_servokit = types.ModuleType("adafruit_servokit")
_fake_adafruit_servokit.ServoKit = object  # jamais instancié : Servo est construit via object.__new__
sys.modules.setdefault("adafruit_servokit", _fake_adafruit_servokit)

from dadou_utils_ros.utils_static import MODE, NECK, NORMAL, RANDOM
from robot.actions.servo import Servo  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SPEAK_JSON = os.path.join(REPO_ROOT, "json", "sequences", "eternel-show", "speak.json")


class FakePwmChannel:
    """Canal PCA9685 factice : seul .angle est lu/écrit par Servo (set_angle/UP/DOWN)."""

    def __init__(self):
        self.angle = 0


@pytest.fixture
def bare_servo():
    # object.__new__ contourne __init__ (qui parle au vrai ServoKit i2c) --
    # même pattern que bare_manager dans test_animation_manager.py. On ne pose
    # que les attributs que update()/process() lisent réellement (les compteurs
    # random_* restent sur leurs défauts de classe, écrasés par update()).
    servo = object.__new__(Servo)
    servo.enabled = True
    servo.mode = NORMAL
    servo.servo_type = NECK
    servo.pwm_channel = FakePwmChannel()
    servo.default_pos = 50
    servo.servo_max = 100
    return servo


def load_neck_keyframe():
    """Charge la vraie piste neck de speak.json (séquence jouée en spectacle) :
    premier keyframe [t, valeur], on ne garde que la valeur (le dict de mode)."""
    with open(SPEAK_JSON) as f:
        sequence = json.load(f)
    _t, keyframe = sequence["neck"][0]
    return keyframe


def test_update_arms_random_mode_from_real_keyframe(bare_servo):
    keyframe = load_neck_keyframe()

    bare_servo.update({NECK: keyframe})

    assert bare_servo.mode == RANDOM
    # Bornes exactes de speak.json (json/sequences/eternel-show/speak.json,
    # piste "neck") : si elles changent dans le JSON, ce test doit être mis à
    # jour en même temps -- c'est voulu, il garantit l'alignement code/JSON.
    assert bare_servo.random_move_min == 40
    assert bare_servo.random_move_max == 70


def test_mode_constant_matches_json_key():
    # Contrat constante <-> JSON : les séquences écrivent {"mode": "random", ...}
    # (minuscule). Régression c08eb82 : MODE valait 'MODE' -- la comparaison
    # `msg[self.servo_type][MODE]` dans Servo.update() ne trouvait plus jamais
    # cette clé, le mode random ne s'armait plus (bras/yeux/cou inertes).
    assert MODE == "mode"
