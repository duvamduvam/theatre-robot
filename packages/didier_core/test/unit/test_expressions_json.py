"""Valide data/json/expressions.json (consommé par didier_core.actions.face) — par le contrat
unique theatre_contrats.donnees.verifier_expression (lot L1d, 12/11).

Règles (dans donnees.py, plus ici) : duration > 0, loop bool, trois pistes mouths/left_eyes/
right_eyes de keyframes [t, fichier], fichier présent sous medias/visuals/{mouth,eye}, bouche
24x16 et œil 8x8 lus dans l'EN-TÊTE PNG (plus d'imageio comme juge : ImageMapping refuse en
silence une image de mauvaise taille, d'où l'intérêt de l'attraper à la donnée). Le champ
« name » est optionnel (le chargeur l'injecte) mais doit égaler la clé s'il est présent.
"""
import os

import pytest

from theatre_contrats import donnees

# data/ du mono-dépôt (données du robot, L1e-4b) ; le test vit dans packages/didier_core/test/unit.
DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))), "data")
REFERENCES = donnees.charger_references(DATA_ROOT)
EXPRESSIONS = REFERENCES["expressions"]


def test_expressions_file_exists():
    assert len(EXPRESSIONS) >= 30, "expressions introuvables sous {}".format(DATA_ROOT)


@pytest.mark.parametrize("name", sorted(EXPRESSIONS))
def test_expression_format(name):
    assert donnees.verifier_expression(name, EXPRESSIONS[name], REFERENCES) == []
