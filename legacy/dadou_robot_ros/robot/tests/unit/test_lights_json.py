"""Valide le contrat de données de lights_base.json et robot_lights.json
(consommés par robot/actions/lights.py).

Deux fichiers, deux rôles bien distincts (voir Lights.update/load_light_method) :
 - lights_base.json : les « briques » élémentaires -> une méthode d'animation
   Adafruit (LightsAnimations.<method>) + une couleur optionnelle (résolue
   dans colors.json par Lights.get_color) ;
 - robot_lights.json : des séquences qui ENCHAÎNENT des briques de
   lights_base.json dans le temps (champ "sequences" = {nom_de_brique: t}).

Piège du format "sequences" : ce n'est PAS une liste [t, valeur] comme les
pistes de séquences d'animation (json/sequences/**), mais un DICT
{brique: position}. L'ordre d'itération d'un dict JSON chargé par json.load
est l'ordre d'insertion du fichier (garanti dict Python >= 3.7) : c'est cet
ordre qui doit être croissant, exactement comme Track.frames l'attend
(robot/actions/lights.py : `for brick_name, position in json_seq[SEQUENCES].items()`).

LightsAnimations n'est PAS instanciée ici : son __init__ importe
adafruit_led_animation (lib Pi absente du host de dev/CI, voir l'en-tête du
module). On vérifie la présence de la méthode par hasattr sur la CLASSE
elle-même (les méthodes sont des attributs de classe, hasattr fonctionne
sans construire d'objet).
"""

import json
import os

import pytest

from robot.visual.lights_animations import LightsAnimations

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LIGHTS_BASE_FILE = os.path.join(REPO_ROOT, "json", "lights_base.json")
ROBOT_LIGHTS_FILE = os.path.join(REPO_ROOT, "json", "robot_lights.json")
COLORS_FILE = os.path.join(REPO_ROOT, "json", "colors.json")

# Références mortes préexistantes, à trancher : AUCUNE connue à ce jour
# (exploration du 2026-07-11 : toutes les briques/couleurs/méthodes existent).
EXCEPTIONS = []

with open(LIGHTS_BASE_FILE) as f:
    LIGHTS_BASE = json.load(f)
with open(ROBOT_LIGHTS_FILE) as f:
    ROBOT_LIGHTS = json.load(f)
with open(COLORS_FILE) as f:
    COLORS = json.load(f)

BRICK_NAMES = sorted(LIGHTS_BASE.keys())
ROBOT_LIGHTS_NAMES = sorted(ROBOT_LIGHTS.keys())


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def test_lights_base_file_exists():
    assert len(LIGHTS_BASE) >= 10, "briques introuvables sous {}".format(LIGHTS_BASE_FILE)


def test_robot_lights_file_exists():
    assert len(ROBOT_LIGHTS) >= 5, "séquences lights introuvables sous {}".format(ROBOT_LIGHTS_FILE)


@pytest.mark.parametrize("name", BRICK_NAMES)
def test_light_base_brick(name):
    brick = LIGHTS_BASE[name]

    assert "method" in brick, "brique '{}' : champ 'method' obligatoire".format(name)
    method = brick["method"]
    assert isinstance(method, str), "brique '{}' : 'method' doit être une chaîne".format(name)
    assert hasattr(LightsAnimations, method), \
        "brique '{}' : méthode '{}' absente de LightsAnimations (robot/visual/lights_animations.py)".format(
            name, method)

    if "color" in brick and (name, "color") not in EXCEPTIONS:
        color = brick["color"]
        assert color in COLORS, \
            "brique '{}' : couleur '{}' absente de {}".format(name, color, COLORS_FILE)


@pytest.mark.parametrize("name", ROBOT_LIGHTS_NAMES)
def test_robot_lights_sequence(name):
    sequence = ROBOT_LIGHTS[name]

    assert is_number(sequence.get("duration")) and sequence["duration"] > 0, \
        "séquence lights '{}' : champ 'duration' (nombre > 0) obligatoire".format(name)
    assert isinstance(sequence.get("loop"), bool), \
        "séquence lights '{}' : champ 'loop' (bool) obligatoire".format(name)
    assert isinstance(sequence.get("sequences"), dict), \
        "séquence lights '{}' : champ 'sequences' (dict {{brique: t}}) obligatoire".format(name)

    previous_t = -1
    for brick_name, t in sequence["sequences"].items():
        where = "séquence lights '{}' -> brique '{}'".format(name, brick_name)

        if (name, brick_name) not in EXCEPTIONS:
            assert brick_name in LIGHTS_BASE, \
                "{} : brique inconnue de {}".format(where, LIGHTS_BASE_FILE)

        assert is_number(t) and 0 <= t <= 1, "{} : t hors [0,1] : {!r}".format(where, t)
        assert t >= previous_t, "{} : briques non triées (t={} après t={})".format(where, t, previous_t)
        previous_t = t
