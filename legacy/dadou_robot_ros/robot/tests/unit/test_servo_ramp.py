"""Tests de la rampe linéaire, de l'anti-spam I2C, du fix random_duration et du
deadman servo (robot/actions/servo.py).

Contexte matériel (voir servo.py) : les servos (cou, 2 yeux, 2 bras) sont
pilotés par un PCA9685 via adafruit_servokit. Avant ce chantier, Servo écrivait
la consigne d'un coup (saut sec), réécrivait l'I2C même à valeur inchangée, et
n'avait AUCUN deadman (un mode random tournait pour toujours si animations_node
mourait). Ces tests exercent le MÊME code que la prod, avec un canal PCA9685
factice et une horloge monkeypatchée (jamais de sleep : déterministe).

adafruit_servokit est une lib matériel absente de l'hôte/CI ; robot.actions.servo
fait `from adafruit_servokit import ServoKit` au niveau module. On stube le module
AVANT le premier import (même pattern que test_servo_random_mode.py).
"""
import json
import os
import sys
import types

import pytest

_fake_adafruit_servokit = types.ModuleType("adafruit_servokit")
_fake_adafruit_servokit.ServoKit = object  # jamais instancié : Servo construit via object.__new__
sys.modules.setdefault("adafruit_servokit", _fake_adafruit_servokit)

from dadou_utils_ros.utils.time_utils import TimeUtils
from dadou_utils_ros.utils_static import NECK, NORMAL, RANDOM, MODE, UP, DOWN, STOP, ANIMATION, \
    DURATION
from robot.robot_static import RANDOM_MOVE_MIN, RANDOM_MOVE_MAX, RANDOM_TIME_MIN, \
    RANDOM_TIME_MAX, RANDOM_DURATION
from robot.actions.servo import Servo, STEP, INPUT_MAX  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PARLE_JSON = os.path.join(REPO_ROOT, "json", "sequences", "didier", "parle.json")


class RecordingChannel:
    """Canal PCA9685 factice : enregistre chaque écriture de .angle (lecture OK)."""

    def __init__(self):
        self.writes = []
        self._angle = None

    @property
    def angle(self):
        return self._angle

    @angle.setter
    def angle(self, value):
        self._angle = value
        self.writes.append(value)


class NoReadChannel:
    """Canal factice qui LÈVE si on lit .angle : garantit qu'UP/DOWN ne fait plus
    de transaction de lecture I2C (le suivi interne current_pos remplace la
    lecture de pwm_channel.angle)."""

    def __init__(self):
        self.writes = []

    @property
    def angle(self):
        raise AssertionError("lecture I2C interdite : .angle ne doit pas être lu")

    @angle.setter
    def angle(self, value):
        self.writes.append(value)


class Clock:
    """Horloge ms injectable (monkeypatch de TimeUtils.current_milli_time)."""

    def __init__(self, t=1000):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, ms):
        self.t += ms


def make_servo(channel, clock, default_pos=50, servo_max=99, start_pos=None):
    """Construit un Servo sans passer par __init__ (qui parle au vrai ServoKit).
    servo_max=99 par défaut => l'angle physique écrit == int(current_pos)
    (mapping 0-99 -> 0-99 quasi identité), ce qui rend la rampe lisible.
    On pose TOUS les attributs qu'update()/process() lisent réellement."""
    servo = object.__new__(Servo)
    servo.enabled = True
    servo.mode = NORMAL
    servo.servo_type = NECK
    servo.pwm_channel = channel
    servo.default_pos = default_pos
    servo.servo_max = servo_max
    servo.current_pos = default_pos if start_pos is None else start_pos
    servo.target_pos = servo.current_pos
    servo._last_written_angle = None
    servo._last_process_time = clock()
    servo.animation_deadline = 0
    # État random sur ses défauts (écrasé par update en mode random).
    servo.random_start_time = 0
    servo.random_duration = 0
    servo.random_last_time = 0
    servo.random_next_time = 0
    servo.random_move_min = 0
    servo.random_move_max = 0
    servo.random_time_min = 0
    servo.random_time_max = 0
    return servo


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    # current_milli_time est une staticmethod ; on la remplace par l'horloge
    # injectée -> TimeUtils.is_time() (utilisé par le random/deadman) ET les
    # appels directs de servo.py tapent tous dans la même horloge déterministe.
    monkeypatch.setattr(TimeUtils, "current_milli_time", c)
    return c


def tick(servo, clock, dt_ms=50):
    """Un tick de node : avance l'horloge de dt_ms puis appelle process()."""
    clock.advance(dt_ms)
    servo.process()


# --- 1) Rampe : cible éloignée atteinte par étapes croissantes, vitesse OK ---

def test_ramp_reaches_distant_target_by_increasing_steps(clock):
    channel = RecordingChannel()
    servo = make_servo(channel, clock, start_pos=0)

    servo.update({NECK: 99})  # cible éloignée (course quasi pleine)
    assert servo.target_pos == 99

    # 30 ticks de 50 ms suffisent largement (RAMP_SPEED=160/s => ~0,6 s).
    for _ in range(30):
        tick(servo, clock)

    writes = channel.writes
    # Plusieurs écritures intermédiaires (pas un saut direct à 99).
    assert len(writes) >= 5
    # Strictement croissantes jusqu'à la cible.
    assert writes == sorted(writes)
    assert writes[-1] == 99
    # Vitesse respectée : chaque pas ~ RAMP_SPEED*dt = 160*0.05 = 8 unités,
    # à ±1 près (l'angle écrit est un entier). Le dernier pas peut être plus
    # court (clamp sur la cible) : on l'exclut.
    intermediate = writes[:-1]
    diffs = [b - a for a, b in zip(intermediate, intermediate[1:])]
    assert diffs, "au moins deux écritures intermédiaires attendues"
    assert all(7 <= d <= 9 for d in diffs), diffs


# --- 2) Anti-spam : aucune écriture une fois la cible atteinte ---

def test_no_write_once_target_reached(clock):
    channel = RecordingChannel()
    servo = make_servo(channel, clock, start_pos=0)

    servo.update({NECK: 40})
    for _ in range(30):
        tick(servo, clock)
    assert servo.current_pos == 40
    reached = len(channel.writes)

    # Cible atteinte : 20 ticks de plus ne doivent RIEN réécrire (anti-spam).
    for _ in range(20):
        tick(servo, clock)
    assert len(channel.writes) == reached


# --- 3) Deux updates vers la même valeur => pas de double écriture ---

def test_same_target_twice_no_double_write(clock):
    channel = RecordingChannel()
    servo = make_servo(channel, clock, start_pos=0)

    servo.update({NECK: 30})
    for _ in range(30):
        tick(servo, clock)
    settled = len(channel.writes)
    assert servo.current_pos == 30

    servo.update({NECK: 30})  # même valeur : ne doit rien changer
    for _ in range(10):
        tick(servo, clock)
    assert len(channel.writes) == settled


# --- 4) FIX random_duration : clé au niveau servo_type => sortie auto ---

def test_random_duration_key_at_servo_level_triggers_exit(clock):
    channel = RecordingChannel()
    servo = make_servo(channel, clock)

    servo.update({NECK: {MODE: RANDOM, RANDOM_DURATION: 2000,
                         RANDOM_MOVE_MIN: 35, RANDOM_MOVE_MAX: 75,
                         RANDOM_TIME_MIN: 500, RANDOM_TIME_MAX: 3000}})
    assert servo.mode == RANDOM
    # La clé a bien été lue DANS le dict du servo (bug historique : lue au
    # niveau top-level, donc jamais).
    assert servo.random_duration == 2000
    assert servo.random_start_time != 0

    # Avant l'échéance : reste en random.
    clock.advance(1000)
    servo.process()
    assert servo.mode == RANDOM

    # Après l'échéance : sortie auto -> NORMAL (position laissée où elle est).
    clock.advance(1500)
    servo.process()
    assert servo.mode == NORMAL


# --- 5) Deadman servo : ANIMATION+DURATION armé, échéance dépassée -> default ---

def test_deadman_returns_to_default_after_deadline(clock):
    channel = RecordingChannel()
    servo = make_servo(channel, clock, default_pos=50, start_pos=80)

    # Keyframe d'animation : anim=True + temps restant (4000 ms).
    servo.update({NECK: {MODE: RANDOM, RANDOM_MOVE_MIN: 35, RANDOM_MOVE_MAX: 75,
                         RANDOM_TIME_MIN: 500, RANDOM_TIME_MAX: 3000},
                  ANIMATION: True, DURATION: 4000})
    assert servo.mode == RANDOM
    # Échéance = now + DURATION + marge (ANIMATION_STOP_MARGIN=2000).
    assert servo.animation_deadline == clock() + 4000 + Servo.ANIMATION_STOP_MARGIN

    # Horloge poussée au-delà de l'échéance : deadman -> retour au repos.
    clock.advance(4000 + Servo.ANIMATION_STOP_MARGIN + 100)
    servo.process()
    assert servo.mode == NORMAL
    assert servo.target_pos == 50  # cible = default_pos
    assert servo.animation_deadline == 0  # désarmé


def test_stop_disarms_deadman(clock):
    channel = RecordingChannel()
    servo = make_servo(channel, clock)

    servo.update({NECK: {MODE: RANDOM, RANDOM_MOVE_MIN: 35, RANDOM_MOVE_MAX: 75,
                         RANDOM_TIME_MIN: 500, RANDOM_TIME_MAX: 3000},
                  ANIMATION: True, DURATION: 4000})
    assert servo.animation_deadline != 0

    servo.update({NECK: STOP, ANIMATION: False})
    assert servo.animation_deadline == 0
    assert servo.mode == NORMAL
    assert servo.target_pos == servo.default_pos


# --- 6) UP/DOWN : modifie la cible SANS lecture I2C ---

def test_up_down_change_target_without_i2c_read(clock):
    # NoReadChannel lève si .angle est LU : garantit qu'UP/DOWN s'appuie sur
    # current_pos et ne fait plus de transaction de lecture.
    channel = NoReadChannel()
    servo = make_servo(channel, clock, start_pos=50)

    servo.update({NECK: UP})
    assert servo.target_pos == 50 + STEP
    # Aucune écriture non plus pendant l'update (le matériel bouge via process).
    assert channel.writes == []

    servo.update({NECK: DOWN})
    # current_pos vaut toujours 50 (process non appelé) -> 50 - STEP.
    assert servo.target_pos == 50 - STEP
    assert channel.writes == []


def test_up_respects_upper_bound(clock):
    channel = NoReadChannel()
    servo = make_servo(channel, clock, start_pos=INPUT_MAX - 1)
    # Trop proche du plafond (INPUT_MAX - STEP) : UP ne bouge pas la cible.
    servo.update({NECK: UP})
    assert servo.target_pos == INPUT_MAX - 1


# --- Anti-régression : les vraies keyframes de parle.json arment le random ---

def test_real_parle_keyframes_still_arm_random(clock):
    with open(PARLE_JSON) as f:
        sequence = json.load(f)

    channel = RecordingChannel()
    servo = make_servo(channel, clock)

    _t, neck_keyframe = sequence["neck"][0]
    servo.update({NECK: neck_keyframe})

    assert servo.mode == RANDOM
    # Bornes exactes de json/sequences/didier/parle.json (piste "neck") : si
    # elles changent dans le JSON, ce test doit être mis à jour -- c'est voulu.
    assert servo.random_move_min == 35
    assert servo.random_move_max == 80
