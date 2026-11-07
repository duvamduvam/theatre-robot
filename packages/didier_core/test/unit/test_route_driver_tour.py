"""Node `route_driver` × « faire le tour » (lot M3, spec-aller-voir.md §8.4) avec
rclpy SIMULÉ — banc RÉUTILISÉ de test_route_driver_goto.py : la sortie roues
(cmd_vel_follow) est gravée ici.

Mutations du lot M3 (doivent rougir) :
  - journal de l'ordre qui lit order.x (AttributeError : le callback tue le node)
    -> test_tour_accepte_etat_goto_et_pivot_d_entree
  - cancel sans zéro immédiat pendant le tour -> test_cancel_pendant_le_tour_zero_franc
  - même tour redemandé qui relance -> test_meme_tour_redemande_rien
"""
import json

from test.unit.test_route_driver_goto import (_etats, _odom, _recevoir, _tick, _twists,
                                                     pilote)  # noqa: F401 (fixture)

# Centre (5 ; 2), rayon 2 : Didier en (5 ; 0) est SUR le cercle, cap +x = tangent
# du sens gauche (trigo) — l'orbite démarre d'emblée.
TOUR = {"name": "tour de banc", "orbit_x": 5.0, "orbit_y": 2.0, "orbit_r": 2.0, "orbit_dir": 1}


def _resultats(noeud):
    return [json.loads(p) for t, p in noeud.publies if t == "route_goto_result"]


def test_tour_accepte_etat_goto_et_pivot_d_entree(pilote):
    _odom(pilote, 5.0, 0.0, 0.0, 0)
    _recevoir(pilote, "route_goto", json.dumps(TOUR))
    assert _etats(pilote)[-1] == "goto" and pilote.goto.order.name == "tour de banc"
    _tick(pilote, 10)
    _tick(pilote, 20)
    # Tangent : v rampe 0,05 / 0,1 ; ω = v / 2 (anticipation), sens gauche > 0.
    assert _twists(pilote) == [(0.05, 0.025), (0.1, 0.05)]


def test_cancel_pendant_le_tour_zero_franc(pilote):
    _odom(pilote, 5.0, 0.0, 0.0, 0)
    _recevoir(pilote, "route_goto", json.dumps(TOUR))
    _tick(pilote, 10)
    pilote.publies.clear()
    _recevoir(pilote, "route_goto", json.dumps("cancel"))
    assert _twists(pilote) == [(0.0, 0.0)] and _etats(pilote) == ["off"]   # AVANT tout tick


def test_meme_tour_redemande_rien(pilote):
    _odom(pilote, 5.0, 0.0, 0.0, 0)
    _recevoir(pilote, "route_goto", json.dumps(TOUR))
    avant = pilote.goto
    pilote.publies.clear()
    _recevoir(pilote, "route_goto", json.dumps(TOUR))
    assert pilote.goto is avant and pilote.publies == []


def test_tour_dans_l_autre_sens_nouvel_ordre(pilote):
    _odom(pilote, 5.0, 0.0, 0.0, 0)
    _recevoir(pilote, "route_goto", json.dumps(TOUR))
    _recevoir(pilote, "route_goto", json.dumps({**TOUR, "orbit_dir": -1}))
    assert pilote.goto.order.direction == -1
    assert _resultats(pilote)[-1]["reason"] == "goto_suivant"


def test_tour_hors_bornes_refuse(pilote):
    _odom(pilote, 5.0, 0.0, 0.0, 0)
    _recevoir(pilote, "route_goto", json.dumps({**TOUR, "orbit_r": 7.0}))
    assert pilote.goto is None and _twists(pilote) == []
