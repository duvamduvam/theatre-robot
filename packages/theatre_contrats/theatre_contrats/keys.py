"""Clés et valeurs conventionnelles des payloads JSON échangés sur le réseau.

Valeurs reprises À L'IDENTIQUE de dadou_utils_ros/utils_static.py (y compris
les incohérences historiques : UP vaut "UP" en majuscules, JOYSTICK vaut
'self.gamepad') — ce sont des valeurs DE FIL, les « corriger » casserait la
télécommande ou les séquences JSON déjà écrites.

Les noms d'organes (organs.py) servent AUSSI de clés de payload ; ils ne sont
pas redéfinis ici (un nom = une définition).
"""

A = 'A'
ANGLO = 'anglo'
AUDIOS = 'audios'
B = 'B'
BACKWARD = 'backward'
BRIGHTNESS = 'brightness'
COLOR = 'color'
DEFAULT = 'default'
DEVICES = 'devices'
DOWN = 'down'
DURATION = 'duration'
FACES = 'faces'
FORWARD = 'forward'
INCLINO = "inclino"
JOYSTICK = 'self.gamepad'
KEY = 'key'
KEYS = 'keys'
LEFT = 'left'
LOOP = 'loop'
METHOD = 'method'
# 'mode' MINUSCULE : c'est la clé des keyframes servo des séquences JSON
# ({"mode": "random", ...}). Passée à 'MODE' par c08eb82 (2025-09-27) → le mode
# random ne s'armait plus jamais depuis les animations (bras/yeux inertes).
MODE = 'mode'
MOUTH = 'mouth'
NAME = 'name'
NORMAL = 'normal'
RANDOM = 'random'
RIGHT = 'right'
SEQUENCES = 'sequences'
SPEED = 'speed'
STOP = 'stop'
TYPE = 'type'
UP = "UP"
WHEEL_LEFT = 'wheel_left'
WHEEL_RIGHT = 'wheel_right'
X = 'X'
Y = 'Y'
