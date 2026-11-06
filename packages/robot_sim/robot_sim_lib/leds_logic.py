"""Logique pure de la visualisation LED simulée (aucune dépendance ROS/Gazebo).

AVERTISSEMENT (à ne pas perdre en cours de route) : ceci est une VISUALISATION
en sim, PAS une réplique du rendu Adafruit LED Animation du vrai robot
(robot/actions/lights.py + robot/visual/lights_animations.py). Les effets
(blink, pulse, sparkle, rainbow...) sont approximés par de simples fonctions
du temps — largement suffisant pour donner un repère visuel (le robot « vit »
en sim) mais ça ne valide RIEN sur le rendu réel du ruban physique.

Le temps est TOUJOURS pris en paramètre (ms), jamais lu via time.time() ni
via un random.* non seedé : ça permet de tester toute la logique de façon
déterministe (voir robot/tests/unit/test_leds_logic.py) et respecte l'usage
sim_time (horloge Gazebo, pas l'horloge murale) côté leds_sim_node.
"""
import colorsys
import math
import random

STOP = "stop"
BRIGHTNESS_KEY = "brightness"

# Méthodes dont le rendu change à chaque tick par nature : le node ne doit PAS
# leur appliquer l'anti-spam "publie seulement si la couleur a changé" (cf.
# gz_bridge.yaml / commande UserCommands MaterialColor, pas un flux vidéo).
ANIMATED_METHODS = {
    "blink", "pulse", "sparkle_pulse", "sparkle",
    "rainbow", "rainbow_comet", "rainbow_chase", "rainbow_sparkle", "color_cycle",
}

BLACK = (0, 0, 0)


def is_animated_method(method):
    """True si la brique change de couleur à chaque tick (cf. ANIMATED_METHODS)."""
    return method in ANIMATED_METHODS


# ======================================================================
# Résolution couleur (colors.json / lights_base.json)
# ======================================================================

def rgb_from_color_name(color_name, colors):
    """colors : dict nom -> [r,g,b] (json/colors.json). KeyError si couleur inconnue
    (propagée telle quelle : le node loggue et ignore plutôt que planter)."""
    r, g, b = colors[color_name]
    return (int(r), int(g), int(b))


def brick_base_color(brick, colors):
    """Couleur statique d'une brique lights_base.json. (0,0,0) si la brique n'en
    déclare pas (rainbow/color_cycle génèrent leur couleur, ils n'en ont pas de
    fixe dans le JSON)."""
    color_name = brick.get("color")
    if color_name is None:
        return BLACK
    return rgb_from_color_name(color_name, colors)


def scale_color(color, factor):
    """Multiplie chaque canal par factor (borné 0..1), arrondi entier 0..255."""
    factor = max(0.0, min(1.0, factor))
    return tuple(max(0, min(255, round(c * factor))) for c in color)


# ======================================================================
# Timeline séquence -> brique active (json/robot_lights.json, champ "sequences")
# ======================================================================

def build_timeline(sequence_bricks, duration_ms):
    """sequence_bricks : dict ORDONNÉ {nom_de_brique: position_relative_fin (0..1)}.
    Retourne [(nom_brique, debut_ms, fin_ms), ...] : chaque brique joue depuis la
    fin de la précédente jusqu'à sa propre position * duration_ms (la première
    brique commence à 0).

    NB divergence assumée avec le vrai Lights (robot/actions/lights.py, classe
    Sequence) : son calcul de durée du PREMIER élément utilise les positions
    [1] et [0] au lieu de 0 et [0], un détail qui ressemble à un artefact de
    son code plutôt qu'un choix voulu. Ici on prend l'interprétation naturelle
    des données (positions cumulatives croissantes depuis 0) : plus simple à
    tester, et c'est une visualisation, pas une réplique.
    """
    timeline = []
    previous_end = 0.0
    for brick_name, position in sequence_bricks.items():
        end_ms = position * duration_ms
        timeline.append((brick_name, previous_end, end_ms))
        previous_end = end_ms
    return timeline


def active_brick_at(timeline, loop, duration_ms, elapsed_ms):
    """Brique active à l'instant elapsed_ms depuis le démarrage de la séquence.
    None si la séquence non-loop est terminée (elapsed_ms >= duration_ms) :
    le node doit alors éteindre.
    """
    if not timeline:
        return None
    if loop and duration_ms > 0:
        elapsed_ms = elapsed_ms % duration_ms
    elif elapsed_ms >= duration_ms:
        return None
    for brick_name, start_ms, end_ms in timeline:
        if start_ms <= elapsed_ms < end_ms:
            return brick_name
    # Bornes flottantes (fin exacte de la dernière brique) ou brique unique à
    # position 0 (durée nulle par construction, ex. json/robot_lights.json
    # "devil": {"solid red": 0}) : on reste sur la dernière brique tant qu'on
    # est dans la fenêtre de la séquence.
    return timeline[-1][0]


# ======================================================================
# Effets par méthode de brique (lights_base.json -> "method")
# ======================================================================

def compute_effect_color(brick, elapsed_ms, colors):
    """Couleur RGB (0..255) rendue par une brique à l'instant elapsed_ms
    (temps écoulé depuis le début de LA BRIQUE, pas de la séquence)."""
    method = brick.get("method", "solid")
    base = brick_base_color(brick, colors)
    t_sec = elapsed_ms / 1000.0

    if method in ("solid", "chase", "comet"):
        # chase/comet balaient le ruban physiquement : en visu globale (une
        # seule boîte), on ne rend que la couleur de base, constante.
        return base

    if method == "blink":
        # créneau ~1 Hz : moitié du temps allumé, moitié éteint.
        return base if (t_sec % 1.0) < 0.5 else BLACK

    if method in ("pulse", "sparkle_pulse"):
        # respiration sinusoïdale ~0.5 Hz (période 2 s).
        intensity = 0.5 + 0.5 * math.sin(2 * math.pi * 0.5 * t_sec)
        return scale_color(base, intensity)

    if method == "sparkle":
        return _sparkle_color(base, elapsed_ms)

    if method.startswith("rainbow") or method == "color_cycle":
        return _rainbow_color(elapsed_ms)

    # Méthode inconnue : dégradation propre sur la couleur de base plutôt que planter.
    return base


def _sparkle_color(base, elapsed_ms, step_ms=80):
    """Scintillement pseudo-aléatoire déterministe : une nouvelle valeur toutes
    les step_ms, tirée d'un RNG seedé par le pas de temps (reproductible en test,
    pas un vrai bruit temps réel)."""
    step = int(elapsed_ms // step_ms)
    rng = random.Random(step)
    factor = rng.uniform(0.3, 1.0)
    return scale_color(base, factor)


def _rainbow_color(elapsed_ms, tours_per_sec=0.2):
    """Teinte HSV qui cycle à tours_per_sec tours/seconde (saturation/valeur max)."""
    hue = (elapsed_ms / 1000.0 * tours_per_sec) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
    return (round(r * 255), round(g * 255), round(b * 255))


# ======================================================================
# État "robot_lights" : séquence en cours + brightness globale
# ======================================================================

class LedsSimState:
    """Reproduit le comportement observable du topic robot_lights, en version
    simplifiée : pas de notion de "séquence par défaut" à laquelle revenir sur
    stop/fin (le vrai Lights.update() le fait) -- ici stop/fin => éteint tout
    court. Assumé : c'est une visualisation V1, pas une réplique."""

    def __init__(self, robot_lights_json):
        self.robot_lights_json = robot_lights_json
        self.brightness = 1.0
        self._sequence_name = None
        self._timeline = []
        self._loop = False
        self._duration_ms = 0
        self._start_ms = 0

    def update(self, payload, now_ms, override_duration_ms=None):
        """payload : nom de séquence (str), STOP, ou {"brightness": x}."""
        if isinstance(payload, dict):
            if BRIGHTNESS_KEY in payload:
                self.set_brightness(payload[BRIGHTNESS_KEY])
            return
        if payload == STOP:
            self.stop()
            return
        self.start_sequence(payload, now_ms, override_duration_ms)

    def start_sequence(self, name, now_ms, override_duration_ms=None):
        """KeyError si `name` n'existe pas dans robot_lights.json (le node
        loggue et ignore plutôt que planter, comme le vrai lights_node)."""
        json_seq = self.robot_lights_json[name]
        duration_ms = override_duration_ms if override_duration_ms else json_seq["duration"]
        self._sequence_name = name
        self._loop = bool(json_seq["loop"])
        self._duration_ms = duration_ms
        self._timeline = build_timeline(json_seq["sequences"], duration_ms)
        self._start_ms = now_ms

    def stop(self):
        self._sequence_name = None
        self._timeline = []

    def set_brightness(self, value):
        self.brightness = max(0.0, min(1.0, float(value)))

    @property
    def sequence_name(self):
        return self._sequence_name

    def current_color_and_method(self, now_ms, lights_base, colors):
        """Retourne (rgb_ou_None, method_ou_None). rgb=None => éteint (émissif
        noir). Une séquence non-loop arrivée à échéance s'éteint d'elle-même
        (retour à éteint à la fin, comme demandé par la spec)."""
        if self._sequence_name is None:
            return None, None
        elapsed_ms = now_ms - self._start_ms
        brick_name = active_brick_at(self._timeline, self._loop, self._duration_ms, elapsed_ms)
        if brick_name is None:
            self.stop()  # séquence non-loop terminée : retour à éteint
            return None, None
        brick = lights_base[brick_name]
        # Le temps de l'effet est relatif à la BRIQUE (démarrage de la séquence
        # à défaut de suivre le début exact de chaque segment : suffisant pour
        # une visu, évite de retracker un start_time par brique).
        color = compute_effect_color(brick, elapsed_ms, colors)
        color = scale_color(color, self.brightness)
        return color, brick.get("method")


# ======================================================================
# "face" : approximation V1 (expressions = bitmaps, pas des couleurs)
# ======================================================================

def face_colors(expression, colors):
    """Approximation V1 assumée : les expressions du vrai robot sont des
    bitmaps sur une matrice de LED (pas des couleurs), donc il n'y a pas de
    mapping "juste" vers une couleur. On se contente d'un signal visuel
    minimal : toute expression non-stop allume bouche (GOLD) + yeux (AQUA) ;
    "stop" (ou aucune expression connue) éteint les trois."""
    if expression is None or expression == STOP:
        return {"mouth": BLACK, "left_eye": BLACK, "right_eye": BLACK}
    gold = rgb_from_color_name("GOLD", colors)
    aqua = rgb_from_color_name("AQUA", colors)
    return {"mouth": gold, "left_eye": aqua, "right_eye": aqua}
