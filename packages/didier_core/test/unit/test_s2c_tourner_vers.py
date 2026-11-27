"""Lot S2c — « se tourner vers un objet » (spec-S2-le-corps-raconte.md §5).

Vécu corrigé (séance du 25/11) : « regarde l'éléphant à droite » donnait un pivot DEVINÉ de
−90°, qui ne visait pas l'objet. Ici l'angle est CALCULÉ depuis la pose (x, y, cap) et la
position de l'objet ; le LLM ne fait plus que NOMMER.

Mutations du lot (doivent rougir) :
  - angle lu dans l'intention au lieu d'être calculé -> test_l_angle_de_l_intention_est_IGNORE
  - refus « no_pose » retiré (angle deviné sans cap) -> test_sans_pose_fraiche_aucun_angle_devine
  - tolérance « déjà face » retirée -> test_deja_face_ne_fait_pas_pivoter
  - garde « atteignable » appliquée à tourner_vers -> test_garde_se_tourner_vers_objet_lointain
"""
import json
import math

import pytest

from didier_rehearsal.director import TURN_TO_TOL_DEG, decide_turn_to
from theatre_contrats import objets
from theatre_contrats.objets import Objet, Tableau


def tableau(x, y, *, nom="elephant", repere="monde", atteignable=True, distance_m=4.0,
            en_vue=True):
    """`distance_m` / `en_vue` : un objet « ici » au sens du tableau (sinon toute garde le
    refuse « pas_ici », avant même la règle du lot)."""
    return Tableau(objets=(Objet(id="carte/" + nom, nom=nom, x=x, y=y, repere=repere,
                                 atteignable=atteignable, distance_m=distance_m,
                                 en_vue=en_vue),))


INTENT = {"cmd": "tourner_vers", "objet": "elephant", "id": "carte/elephant"}


# ---------------------------------------------------------------- angle CALCULÉ
@pytest.mark.parametrize("ox, oy, yaw_deg, attendu", [
    (3.0, 3.0, 0.0, 45.0),      # Didier cap 0 : l'objet est à +45° (sa GAUCHE)
    (3.0, -3.0, 0.0, -45.0),    # sa droite
    (-5.0, 0.0, 0.0, 180.0),    # pile derrière -> demi-tour
    (0.0, 5.0, 90.0, 0.0),      # il lui fait DÉJÀ face (cap 90 = +y)
    (5.0, 0.0, 180.0, 180.0),   # il lui tourne le dos -> demi-tour aussi
])
def test_angle_calcule_depuis_la_pose(ox, oy, yaw_deg, attendu):
    """|angle| est comparé : un demi-tour vaut +180 ou −180 selon le côté du wrap, c'est le
    MÊME pivot (route_driver intègre la rotation, cf. goto.TurnOrder)."""
    d = decide_turn_to(INTENT, tableau=tableau(ox, oy),
                       pose=(0.0, 0.0, math.radians(yaw_deg)), off_by_david=False)
    assert abs(d.angle_deg) == pytest.approx(abs(attendu), abs=0.05)
    if abs(attendu) not in (0.0, 180.0):
        assert math.copysign(1.0, d.angle_deg) == math.copysign(1.0, attendu)


def test_l_angle_de_l_intention_est_IGNORE():
    """Le LLM ne décide plus de l'angle : même s'il en met un, la régie calcule le sien."""
    intent = dict(INTENT, angle_deg=-90.0, sens="droite")
    d = decide_turn_to(intent, tableau=tableau(3.0, 3.0), pose=(0.0, 0.0, 0.0), off_by_david=False)
    assert d.effect == "accepted"
    assert d.angle_deg == pytest.approx(45.0, abs=0.05)   # et PAS -90


def test_ordre_identique_a_tourner():
    """Même chemin que « tourner » : route_goto reçoit {"turn_rad"}, rien de neuf."""
    d = decide_turn_to(INTENT, tableau=tableau(0.0, 1.0), pose=(0.0, 0.0, 0.0), off_by_david=False)
    assert d.effect == "accepted"
    assert json.loads(d.order)["turn_rad"] == pytest.approx(math.pi / 2)
    assert d.name == "pivot +90°"


# ---------------------------------------------------------------- refus, dans l'ordre
def test_objet_inconnu():
    d = decide_turn_to({"cmd": "tourner_vers", "id": "carte/zzz"}, tableau=tableau(1.0, 1.0),
                       pose=(0.0, 0.0, 0.0), off_by_david=False)
    assert d.effect == "unknown"


def test_objet_sans_position():
    d = decide_turn_to(INTENT, tableau=tableau(None, None), pose=(0.0, 0.0, 0.0), off_by_david=False)
    assert d.effect == "no_position"


def test_route_coupee_par_david_passe_avant_la_pose():
    d = decide_turn_to(INTENT, tableau=tableau(3.0, 3.0), pose=None, off_by_david=True)
    assert d.effect == "route_off_by_david"


def test_sans_pose_fraiche_aucun_angle_devine():
    """LE point du lot : sans cap frais, on ne devine RIEN (on refuse, on ne sature pas)."""
    d = decide_turn_to(INTENT, tableau=tableau(3.0, 3.0), pose=None, off_by_david=False)
    assert d.effect == "no_pose"
    assert d.order is None and d.angle_deg is None


def test_deja_face_ne_fait_pas_pivoter():
    """Sous la tolérance : aucun ordre (un pivot de 2° ne se voit pas et réveille le corps sûr)."""
    petit = math.radians(TURN_TO_TOL_DEG - 1.0)
    d = decide_turn_to(INTENT, tableau=tableau(math.cos(petit) * 5, math.sin(petit) * 5),
                       pose=(0.0, 0.0, 0.0), off_by_david=False)
    assert d.effect == "deja_face"
    assert d.order is None


def test_juste_au_dela_de_la_tolerance_il_pivote():
    grand = math.radians(TURN_TO_TOL_DEG + 1.0)
    d = decide_turn_to(INTENT, tableau=tableau(math.cos(grand) * 5, math.sin(grand) * 5),
                       pose=(0.0, 0.0, 0.0), off_by_david=False)
    assert d.effect == "accepted"


# ---------------------------------------------------------------- garde de la bouche
def test_garde_se_tourner_vers_objet_lointain():
    """« Se tourner vers » ne DÉPLACE pas Didier : la borne « atteignable » (10 m) ne s'y
    applique pas — il peut regarder une grue qu'il n'irait pas voir."""
    t = tableau(30.0, 0.0, atteignable=False, distance_m=30.0, en_vue=True)
    assert objets.garde_geste(t, dict(INTENT)).effect is None
    # ... alors qu'« aller voir » le même objet reste refusé.
    assert objets.garde_geste(t, {"cmd": "aller_voir", "objet": "elephant"}).effect == "dropped"


def test_garde_objet_pas_ici_refuse_quand_meme():
    """On ne se tourne pas vers ce qu'on ne situe pas : « inconnu » reste un refus."""
    t = tableau(3.0, 3.0)
    assert objets.garde_geste(t, {"cmd": "tourner_vers", "objet": "zzz"}).effect == "unknown"
