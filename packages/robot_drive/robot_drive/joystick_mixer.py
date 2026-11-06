"""Mixage joystick / inclinomètre -> paire moteurs, indépendant de ROS (stdlib).

Déplacé depuis robot/move/anglo_meter_translator.py pour que robot_drive reste
100% autonome : le conteneur de simulation n'embarque ni dadou_utils_ros ni
robot.*. La sémantique est identique à l'original :

    translate(forward, turn) -> (gauche, droite) en POURCENTS -100..100

Le mapping linéaire de dadou_utils_ros.misc.Misc.mapping est réimplémenté
localement (_mapping) pour reproduire les valeurs dorées à l'identique (division
entière plancher + écrêtage aux bornes d'entrée). L'import MAX_PWM_R de l'ancien
module était mort (jamais utilisé) et n'est volontairement pas repris.
"""

import math

MIN_JOYSTICK = -99
MAX_JOYSTICK = 99


def _mapping(v, in_min, in_max, out_min, out_max):
    """Réimplémentation pure de Misc.mapping : écrêtage aux bornes d'entrée
    puis interpolation linéaire en division entière plancher (//)."""
    if v < in_min:
        v = in_min
    if v > in_max:
        v = in_max
    return (v - in_min) * (out_max - out_min) // (in_max - in_min) + out_min


def translate(forward, turn):
    """(forward, turn) -> (gauche, droite) en pourcents -100..100."""
    return calculate_diff(turn, forward)


def calculate_diff(x, y):
    """x = turn, y = forward. Mixage différentiel (angle/coefficient de virage)
    identique à l'ancien AngloMeterTranslator.calculate_diff."""

    # Angle du vecteur (x, y) : mesure la part de virage.
    z = math.sqrt(x * x + y * y)

    # Angle en radians (garde-fou NaN si z == 0).
    rad = math.acos(abs(x) / z) if z != 0 else 0

    # ... puis en degrés.
    angle = rad * 180 / math.pi

    # Coefficient de virage : -1 à 0°, 0 à 45°, 1 à 90°.
    tcoeff = -1 + (angle / 90) * 2
    turn = tcoeff * abs(abs(y) - abs(x))
    turn = round(turn * 100) / 100

    # Le mouvement est le max de |y| ou |x|.
    mov = max(abs(y), abs(x))

    # Premier et troisième quadrant.
    if (x >= 0 and y >= 0) or (x < 0 and y < 0):
        left = mov
        right = turn
    else:
        right = mov
        left = turn

    # Inversion de polarité en marche arrière.
    if y < 0:
        left = 0 - left
        right = 0 - right

    # Mapping sur la plage définie (pourcents -100..100).
    left_motor_output = int(_mapping(left, MIN_JOYSTICK, MAX_JOYSTICK, -100, 100))
    right_motor_output = int(_mapping(right, MIN_JOYSTICK, MAX_JOYSTICK, -100, 100))

    return left_motor_output, right_motor_output
