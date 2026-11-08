"""BUTTONS_LAYOUT contre le catalogue que le robot publie (lot L1c).

Le robot publie `catalogue` (web_catalog.build_catalog, depuis json/) ; la
télécommande garde ses boutons en dur, mais un bouton qui vise une séquence,
un audio, un relais, une expression ou une lumière INEXISTANTS ne joue rien,
sans erreur (publish() n'a aucun retour). Ce test le rend rouge.

Le catalogue est construit ICI par la même fonction que le nœud du robot, sur
data/json du mono-dépôt (L1e-4b, chemin calculé depuis ce fichier) : même code que
la prod, pas une reproduction. Les valeurs attendues sont lues dans le catalogue,
jamais recopiées.

Formes acceptées gravées : ANIMATION = nom de séquence, STOP, ou {TYPE: …}
(tirage par type côté robot) ; AUDIO = un CHEMIN (value), pas le label.
"""
import pathlib

import pytest

from dadou_utils_ros.utils_static import ANIMATION, AUDIO, FACE, RELAY, ROBOT_LIGHTS, STOP, TYPE
from controller.buttons.button_config import BUTTONS_LAYOUT
from didier_web.web_catalog import build_catalog

JSON_DIR = pathlib.Path(__file__).resolve().parents[5] / "data" / "json"
CATALOGUE = build_catalog(JSON_DIR)

# clé de commande -> famille du catalogue où la valeur doit se trouver.
FAMILLES = {
    ANIMATION: "animations", AUDIO: "audios", RELAY: "relays", FACE: "faces",
    ROBOT_LIGHTS: "robot_lights",
}

# Aucun bouton en défaut connu depuis le 07/11 : les 3 trouvés par ce test (« ca va »,
# « sympa toi », l'audio de « bug1 ») ont été tranchés par David — supprimés ou allégés.
# Un nouveau défaut se déclare ici en xfail(strict=True) avec sa raison, le temps
# que David tranche ; strict=True oblige à retirer la ligne une fois corrigé.
DEFAUTS_CONNUS = {}


def _valeurs_attendues(famille):
    valeurs = CATALOGUE[famille]
    if famille == "audios":
        return {entree["value"] for entree in valeurs}
    return set(valeurs)


def _commandes_visees():
    for mode, layout in BUTTONS_LAYOUT.items():
        for bouton, entree in layout.items():
            if entree == 0:
                continue
            for cle, valeur in entree["cmd"].items():
                if cle in FAMILLES:
                    yield mode, bouton, entree["name"], cle, valeur


def _cas():
    for mode, bouton, libelle, cle, valeur in _commandes_visees():
        marques = []
        if (mode, bouton, cle) in DEFAUTS_CONNUS:
            marques.append(pytest.mark.xfail(
                strict=True, reason=DEFAUTS_CONNUS[(mode, bouton, cle)]))
        yield pytest.param(mode, bouton, libelle, cle, valeur,
                           id="{}-{}-{}".format(mode, bouton, cle), marks=marques)


def test_le_catalogue_de_reference_n_est_pas_vide():
    # Sans ça, un json/ introuvable ferait « échouer » tous les boutons pour la
    # mauvaise raison (ou, pire, les ferait tous passer sur des familles vides).
    assert JSON_DIR.is_dir()
    for famille in FAMILLES.values():
        assert CATALOGUE[famille], "famille '{}' vide dans {}".format(famille, JSON_DIR)


@pytest.mark.parametrize("mode,bouton,libelle,cle,valeur", list(_cas()))
def test_bouton_vise_une_cible_existante(mode, bouton, libelle, cle, valeur):
    famille = FAMILLES[cle]
    if cle == ANIMATION and (valeur == STOP or (isinstance(valeur, dict) and TYPE in valeur)):
        return  # formes acceptées : arrêt, tirage par type
    assert valeur in _valeurs_attendues(famille), \
        "mode '{}', bouton {} '{}' : {}={!r} absent de la famille '{}' du catalogue".format(
            mode, bouton, libelle, cle, valeur, famille)
