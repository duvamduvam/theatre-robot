"""Les images du visage de data/medias/visuals/{mouth,eye}/ passent le contrat d'image
STRICT de theatre_contrats.donnees.verifier_image (lot L1d, 12/11) : celui qui juge toute
image qui ENTRE par le topic data_edit (PNG, CRC justes, 24x16 ou 8x8, RVB 8 bits non
entrelacé, données de la bonne longueur).

Exceptions GRAVÉES par nom : héritées, pas jugées ici. Leur rendu réel sur la matrice n'a
jamais été relevé ; les convertir ou non est une décision à part, hors L1d. Une image ajoutée
ou retouchée n'y entre pas : elle passe le contrat.
"""
import glob
import os

import pytest

from theatre_contrats import donnees

# data/ du mono-dépôt (données du robot, L1e-4b) ; le test vit dans packages/didier_core/test/unit.
DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))), "data")
VISUELS = os.path.join(DATA_ROOT, "medias", "visuals")

# 20 bouches en RVB 16 bits (15 référencées par une expression) et une en RVBA (relevé du 12/11).
EXCEPTIONS_16_BITS = (
    "mouth/bouche-style2.png", "mouth/bouche-style22.png", "mouth/brain.png", "mouth/brain2.png",
    "mouth/internet.png", "mouth/scooby-doo.png", "mouth/scooby-doo2.png", "mouth/upgrade3.png",
    "mouth/upgrade4.png", "mouth/upgrade5.png", "mouth/upgrade6.png", "mouth/upgrade7.png",
    "mouth/upgrade8.png", "mouth/upgrade9.png", "mouth/warning1.png", "mouth/warning2.png",
    "mouth/woman-close.png", "mouth/woman-ouvert1.png", "mouth/woman-ouvert2.png",
    "mouth/woman-ouvert3.png",
)
EXCEPTIONS_RVBA = ("mouth/persos/scooby-doo.png",)
EXCEPTIONS = EXCEPTIONS_16_BITS + EXCEPTIONS_RVBA

IMAGES = sorted(os.path.relpath(p, VISUELS) for zone in donnees.ZONES_IMAGE
                for p in glob.glob(os.path.join(VISUELS, zone, "**", "*"), recursive=True)
                if os.path.isfile(p))


def test_inventaire_grave():
    assert len(IMAGES) == 127
    assert all(i.endswith(".png") for i in IMAGES)
    assert len(EXCEPTIONS) == 21
    assert set(EXCEPTIONS) <= set(IMAGES)


@pytest.mark.parametrize("relatif", [i for i in IMAGES if i not in EXCEPTIONS])
def test_image_conforme(relatif):
    with open(os.path.join(VISUELS, relatif), "rb") as f:
        assert donnees.verifier_image(relatif.split("/")[0], f.read()) == []


@pytest.mark.parametrize("relatif", EXCEPTIONS)
def test_exception_toujours_hors_contrat(relatif):
    # Une exception convertie doit SORTIR de la liste (sinon elle masquerait une régression).
    with open(os.path.join(VISUELS, relatif), "rb") as f:
        assert donnees.verifier_image(relatif.split("/")[0], f.read()) != []
