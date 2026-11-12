"""Valide data/json/lights_base.json (briques) et robot_lights.json (séquences qui les
enchaînent) — par le contrat unique theatre_contrats.donnees (lot L1d, 12/11).

Piège du format "sequences" d'une lumière : un DICT ORDONNÉ {brique: fraction}, pas une liste
de keyframes ; c'est l'ordre du fichier qui doit être croissant (Lights.update itère .items()).

La méthode d'une brique doit appartenir à donnees.METHODES_LUMIERE ; le contrat ne peut pas
importer LightsAnimations (didier_core) : l'égalité des deux listes est gravée ICI.
LightsAnimations n'est pas instanciée (son __init__ importe adafruit, absent de l'hôte) : on
lit ses méthodes sur la CLASSE.
"""
import inspect
import os

import pytest

from didier_core.visual.lights_animations import LightsAnimations
from theatre_contrats import donnees

# data/ du mono-dépôt (données du robot, L1e-4b) ; le test vit dans packages/didier_core/test/unit.
DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))), "data")
REFERENCES = donnees.charger_references(DATA_ROOT)
LIGHTS_BASE = REFERENCES["lights_base"]
ROBOT_LIGHTS = REFERENCES["robot_lights"]


def test_lights_base_file_exists():
    assert len(LIGHTS_BASE) >= 10, "briques introuvables sous {}".format(DATA_ROOT)


def test_robot_lights_file_exists():
    assert len(ROBOT_LIGHTS) >= 5, "séquences lights introuvables sous {}".format(DATA_ROOT)


def test_methodes_lumiere_egales_a_lights_animations():
    # Méthode de brique = méthode publique de la classe dont la signature est (self, params) :
    # c'est ainsi que Lights.load_light_method l'appelle (getattr(...)(light)).
    methodes = sorted(
        nom for nom, f in vars(LightsAnimations).items()
        if inspect.isfunction(f) and not nom.startswith("_")
        and list(inspect.signature(f).parameters) == ["self", "params"])
    assert tuple(methodes) == donnees.METHODES_LUMIERE


@pytest.mark.parametrize("name", sorted(LIGHTS_BASE))
def test_light_base_brick(name):
    assert donnees.verifier_brique(name, LIGHTS_BASE[name], REFERENCES) == []


@pytest.mark.parametrize("name", sorted(ROBOT_LIGHTS))
def test_robot_lights_sequence(name):
    assert donnees.verifier_lumiere(name, ROBOT_LIGHTS[name], REFERENCES) == []
