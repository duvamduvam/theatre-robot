"""Node `route_driver` × gestes chiffrés (lot M2, spec-aller-voir.md §7.2-§7.3)
avec rclpy SIMULÉ — banc RÉUTILISÉ de test_route_driver_goto.py : la sortie
roues (cmd_vel_follow) est gravée ici.

Mutations du lot M2 (doivent rougir) :
  - TurnOrder non reconnu par le node (refusé comme ordre invalide) -> test_pivot_gauche_omega_positif_puis_arrived
  - cancel sans zéro immédiat pendant un pivot -> test_cancel_pendant_le_pivot_zero_franc
  - ceinture off_by_david contournée pour les gestes -> test_geste_refuse_si_route_off_par_david
"""
import json
import math

from test.unit.test_route_driver_goto import (_etats, _odom, _recevoir, _tick, _twists,
                                                     pilote)  # noqa: F401 (fixture)

PIVOT_GAUCHE = json.dumps({"turn_rad": math.radians(90)})


def _resultats(noeud):
    return [json.loads(p) for t, p in noeud.publies if t == "route_goto_result"]


def test_pivot_gauche_omega_positif_puis_arrived(pilote):
    _odom(pilote, 5.0, 0.0, 0.0, 0)
    _recevoir(pilote, "route_goto", PIVOT_GAUCHE)
    assert _etats(pilote)[-1] == "goto" and pilote.goto.order.name == "pivot +90°"
    _tick(pilote, 10)
    _tick(pilote, 20)
    assert _twists(pilote) == [(0.0, 0.15), (0.0, 0.3)]      # + = gauche, jamais de linéaire
    _odom(pilote, 5.0, 0.0, 1.5, 100)
    _tick(pilote, 110)
    assert _etats(pilote)[-1] == "arrived" and pilote.goto is None
    assert _resultats(pilote) == [{"name": "pivot +90°", "result": "arrived", "reason": "arrived",
                                   "travelled": 0.0}]


def test_pivot_droite_omega_negatif(pilote):
    _odom(pilote, 5.0, 0.0, 0.0, 0)
    _recevoir(pilote, "route_goto", json.dumps({"turn_rad": -math.pi / 2}))
    _tick(pilote, 10)
    assert _twists(pilote) == [(0.0, -0.15)]


def test_cancel_pendant_le_pivot_zero_franc(pilote):
    _odom(pilote, 5.0, 0.0, 0.0, 0)
    _recevoir(pilote, "route_goto", PIVOT_GAUCHE)
    _tick(pilote, 10)
    pilote.publies.clear()
    _recevoir(pilote, "route_goto", json.dumps("cancel"))
    assert _twists(pilote) == [(0.0, 0.0)] and _etats(pilote) == ["off"]   # AVANT tout tick


def test_route_off_pendant_avancer_zero_franc(pilote):
    _odom(pilote, 5.0, 0.0, 0.0, 0)
    _recevoir(pilote, "route_goto", json.dumps({"forward_m": 2}))
    _tick(pilote, 10)
    assert _twists(pilote) == [(0.05, 0.0)]                   # ligne droite, rampe du suivi
    pilote.publies.clear()
    _recevoir(pilote, "route", "off")
    assert _twists(pilote) == [(0.0, 0.0)] and pilote.goto is None


def test_avancer_arrive_puis_go_rejoint(pilote):
    _recevoir(pilote, "route", "on")
    _odom(pilote, 15.0, 0.0, 0.0, 0)
    _tick(pilote, 10)
    _recevoir(pilote, "route_goto", json.dumps({"forward_m": 3}))
    _tick(pilote, 20)
    _odom(pilote, 17.96, 0.0, 0.0, 100)                        # projection 2,96 : reste 0,04
    _tick(pilote, 110)
    assert _etats(pilote)[-1] == "arrived"
    _recevoir(pilote, "route", "on")
    assert _etats(pilote)[-1] == "on" and pilote.follower.waypoint_index == 2   # (20, 0), devant


def test_geste_refuse_si_route_off_par_david(pilote):
    _recevoir(pilote, "route", "off")
    _odom(pilote, 5.0, 0.0, 0.0, 0)
    pilote.publies.clear()
    _recevoir(pilote, "route_goto", PIVOT_GAUCHE)
    _recevoir(pilote, "route_goto", json.dumps({"forward_m": 1}))
    _tick(pilote, 10)
    assert pilote.goto is None and pilote.publies == []


def test_recul_et_hors_bornes_refuses(pilote):
    _odom(pilote, 5.0, 0.0, 0.0, 0)
    for ordre in ({"forward_m": -1}, {"forward_m": 6}, {"turn_rad": 7}, {"turn_rad": 1, "forward_m": 1}):
        _recevoir(pilote, "route_goto", json.dumps(ordre))
    assert pilote.goto is None and _etats(pilote) == ["off"]


def test_meme_pivot_redemande_nouvel_ordre(pilote):
    _odom(pilote, 5.0, 0.0, 0.0, 0)
    _recevoir(pilote, "route_goto", PIVOT_GAUCHE)
    _tick(pilote, 10)
    _odom(pilote, 5.0, 0.0, 1.0, 50)                           # déjà tourné de 1 rad
    avant = pilote.goto
    pilote.publies.clear()
    _recevoir(pilote, "route_goto", PIVOT_GAUCHE)               # « encore à gauche »
    assert pilote.goto is not avant
    assert _resultats(pilote)[-1]["reason"] == "goto_suivant"
    assert _twists(pilote) == [(0.0, 0.0)]                      # l'ancien tombe : zéro franc
    _tick(pilote, 60)
    _odom(pilote, 5.0, 0.0, 1.5, 100)                           # 0,5 rad de plus : PAS arrivé
    _tick(pilote, 110)
    assert pilote.goto is not None                              # 90° comptés depuis 1 rad


def test_pivot_delai_15_s_abandon(pilote):
    _odom(pilote, 5.0, 0.0, 0.0, 0)
    _recevoir(pilote, "route_goto", PIVOT_GAUCHE)               # reçu à 0 ms
    _odom(pilote, 5.0, 0.0, 0.0, 14995)
    _tick(pilote, 15000)
    assert pilote.goto is not None
    _tick(pilote, 15001)
    assert pilote.goto is None and _etats(pilote)[-1] == "off"
    assert _resultats(pilote)[-1]["reason"] == "timeout"
