"""Gestes chiffrés « tourner » / « avancer » (didier_rehearsal.goto, lot M2,
spec-aller-voir.md §7.2-§7.3) — logique PURE, valeurs GRAVÉES à la main.
Réglages par défaut : pivots ≤ 0,6 rad/s (rampe 0,15/tick, gain 1,5), tolérance
de cap 0,1 rad, rampe linéaire 0,05/tick, arrivée à 0,3 m.

Passe de mutation du lot M2 (chaque ligne doit rougir) :
  - signe du pivot inversé (err = −reste) -> test_convention_gauche_positif
  - err du pivot replié par wrap_angle -> test_demi_tour_sens_deterministe_malgre_le_bruit
  - rotation non intégrée à travers ±π -> test_pivot_traverse_pi_et_arrive
  - référence du pivot non remise à la 1re pose FRAÎCHE -> test_pivot_ancre_sur_la_premiere_pose_fraiche
  - délai du pivot (15 s) retiré -> test_pivot_delai_15_s
  - translation du pivot non bornée -> test_pivot_pousse_abandon_max_travel
  - borne |turn_rad| retirée -> test_parse_refuse[tour complet]
  - borne forward_m > 5 retirée -> test_parse_refuse[5,01 m]
  - recul accepté -> test_parse_refuse[recul]
  - délai de la ligne droite (10 + 4 × m) retiré -> test_avancer_delai_10_plus_4_par_metre
  - borne 1,5 × m de la ligne droite retirée -> test_avancer_distance_parcourue_1_5_fois
  - FACE après la ligne droite -> test_avancer_arrive_sans_face
"""
import math

import pytest

from didier_rehearsal.goto import (ABORTED, ARRIVED, DRIVE, FACE, ForwardOrder, GotoConfig, GotoError, GotoOrder,
                                  GotoManeuver, TurnOrder, parse_order)

GAUCHE = TurnOrder("pivot +90°", math.pi / 2)
# Objet à gauche (0 ; 5) : ALIGN pivote d’abord de +π/2.
BANC_A_GAUCHE = GotoOrder("banc", 0.0, 5.0, 1.5)
DROITE = TurnOrder("pivot -90°", -math.pi / 2)
DEMI_TOUR = TurnOrder("pivot +180°", math.pi)


def _m(order, pose=(0.0, 0.0, 0.0), **cfg):
    g = GotoManeuver(order, 0, GotoConfig(**cfg))
    g.update_pose(*pose, 0)
    return g


def _r(out):
    return (round(out.lin, 6), round(out.ang, 6), out.phase, out.reason)


# --- ordres ----------------------------------------------------------------------

def test_parse_gestes_valides():
    assert parse_order({"turn_rad": 1.5708}) == TurnOrder("pivot +90°", 1.5708)
    assert parse_order({"turn_rad": -1.5708}).name == "pivot -90°"
    assert parse_order({"turn_rad": 3.1416}).turn_rad == 3.1416      # radians(180) arrondi : accepté
    assert parse_order({"forward_m": 2}) == ForwardOrder("avancer 2 m", 2.0)
    assert parse_order({"forward_m": 5}).metres == 5.0                # borne incluse
    assert parse_order({"forward_m": 0.5}).name == "avancer 0.5 m"


@pytest.mark.parametrize("value, fragment", [
    ({"turn_rad": 0}, "turn_rad"),
    ({"turn_rad": 3.2}, "turn_rad"),
    pytest.param({"turn_rad": 2 * math.pi}, "turn_rad", id="tour complet"),
    ({"turn_rad": float("nan")}, "turn_rad"),
    ({"turn_rad": True}, "turn_rad"),
    ({"turn_rad": "1.57"}, "turn_rad"),
    ({"forward_m": 0}, "forward_m"),
    pytest.param({"forward_m": -1}, "pas de recul", id="recul"),
    pytest.param({"forward_m": 5.01}, "forward_m", id="5,01 m"),
    ({"forward_m": float("inf")}, "forward_m"),
    ({"turn_rad": 1, "forward_m": 1}, "ambigu"),
    ({"name": "a", "x": 1, "y": 2, "standoff": 1.5, "turn_rad": 1}, "ambigu"),
])
def test_parse_refuse(value, fragment):
    with pytest.raises(GotoError) as exc:
        parse_order(value)
    assert fragment in str(exc.value)


# --- tourner ----------------------------------------------------------------------

def test_convention_gauche_positif():
    g, d = _m(GAUCHE), _m(DROITE)
    assert [round(g.tick(t, 1.0).ang, 6) for t in (10, 20, 30, 40, 50)] == [0.15, 0.3, 0.45, 0.6, 0.6]
    assert [round(d.tick(t, 1.0).ang, 6) for t in (10, 20, 30)] == [-0.15, -0.3, -0.45]
    assert g.phase == FACE


def test_pivot_sur_place_jamais_de_lineaire_et_arrive():
    g = _m(GAUCHE)
    assert _r(g.tick(10, 1.0)) == (0.0, 0.15, FACE, "ok")
    g.update_pose(0.0, 0.0, 1.0, 100)
    assert _r(g.tick(110, 1.0)) == (0.0, 0.3, FACE, "ok")             # reste 0,57 : gain 1,5 -> 0,6, rampe
    g.update_pose(0.0, 0.0, 1.5, 200)                                  # reste 0,0708 < 0,1
    assert _r(g.tick(210, 1.0)) == (0.0, 0.0, ARRIVED, "arrived")
    assert _r(g.tick(220, 1.0)) == (0.0, 0.0, ARRIVED, "arrived")     # terminal


def test_demi_tour_sens_deterministe_malgre_le_bruit():
    g = _m(DEMI_TOUR)
    assert round(g.tick(10, 1.0).ang, 6) == 0.15
    g.update_pose(0.0, 0.0, -0.02, 20)       # bruit vers la droite : wrap(π + 0,02) basculerait le sens
    assert round(g.tick(30, 1.0).ang, 6) == 0.3


def test_pivot_traverse_pi_et_arrive():
    g = _m(DEMI_TOUR, pose=(0.0, 0.0, 3.0))
    g.tick(10, 1.0)
    for k in range(1, 6):                    # 3,0 -> 5,6 rad, repliés dans ]-π, π]
        yaw = math.atan2(math.sin(3.0 + 0.52 * k), math.cos(3.0 + 0.52 * k))
        g.update_pose(0.0, 0.0, yaw, k * 100)
        assert g.tick(k * 100 + 10, 1.0).reason == "ok"
    g.update_pose(0.0, 0.0, math.atan2(math.sin(3.0 + 3.12), math.cos(3.0 + 3.12)), 600)
    assert _r(g.tick(610, 1.0)) == (0.0, 0.0, ARRIVED, "arrived")     # 3,12 tourné, reste 0,02


def test_pivot_ancre_sur_la_premiere_pose_fraiche():
    g = _m(GAUCHE)
    assert g.tick(1000, 1.0).reason == "odom_stale"                   # pose de 0 ms périmée
    g.update_pose(0.0, 0.0, 1.5, 1000)       # tourné à la main pendant le trou d'odométrie
    assert _r(g.tick(1010, 1.0)) == (0.0, 0.15, FACE, "ok")           # 90° comptés D'ICI


def test_pivot_delai_15_s():
    g = _m(GAUCHE)
    g.update_pose(0.0, 0.0, 0.0, 14990)
    assert g.tick(15000, 1.0).reason == "ok"
    out = g.tick(15001, 1.0)
    assert _r(out) == (0.0, 0.0, ABORTED, "timeout")


def test_pivot_delai_jamais_au_dessus_de_la_config():
    g = _m(GAUCHE, timeout_s=5.0)
    g.update_pose(0.0, 0.0, 0.0, 5000)
    assert g.tick(5001, 1.0).reason == "timeout"


def test_pivot_pousse_abandon_max_travel():
    g = _m(GAUCHE)
    g.tick(10, 1.0)
    g.update_pose(0.9, 0.0, 0.1, 100)
    assert g.tick(110, 1.0).reason == "ok"
    g.update_pose(1.05, 0.0, 0.2, 200)       # 1,05 m de translation > plancher 1 m
    assert _r(g.tick(210, 1.0)) == (0.0, 0.0, ABORTED, "max_travel")


def test_pivot_fader_zero_rien():
    g = _m(GAUCHE)
    assert _r(g.tick(10, 0.0)) == (0.0, 0.0, FACE, "held")


def test_pivot_pose_non_finie_ignoree_puis_perimee():
    g = _m(GAUCHE)
    g.update_pose(0.0, 0.0, float("nan"), 500)
    assert g.tick(700, 1.0).reason == "odom_stale"                    # la pose de 0 ms vieillit


def test_pivot_cancel_zero_franc_terminal():
    g = _m(GAUCHE)
    g.tick(10, 1.0)
    g.cancel()
    assert _r(g.tick(20, 1.0)) == (0.0, 0.0, ABORTED, "cancelled")


# --- avancer ----------------------------------------------------------------------

def test_avancer_point_fixe_sur_le_cap():
    g = _m(ForwardOrder("avancer 2 m", 2.0), pose=(1.0, 2.0, math.pi / 2))
    g.tick(10, 1.0)
    assert tuple(round(v, 6) for v in g.stop_point) == (1.0, 4.0)


def test_avancer_drive_direct_rampe_et_fader():
    g = _m(ForwardOrder("avancer 5 m", 5.0))
    outs = [g.tick(t, 0.5) for t in range(10, 80, 10)]
    assert [round(o.lin, 6) for o in outs] == [0.05, 0.1, 0.15, 0.2, 0.25, 0.25, 0.25]
    assert {o.ang for o in outs} == {0.0} and {o.phase for o in outs} == {DRIVE}


def test_avancer_plafonne_par_la_croisiere():
    g = _m(ForwardOrder("avancer 5 m", 5.0), max_lin=0.4)
    assert round(max(g.tick(t, 1.0).lin for t in range(10, 200, 10)), 6) == 0.4


def test_avancer_arrive_sans_face():
    g = _m(ForwardOrder("avancer 2 m", 2.0), pose=(0.0, 0.0, 0.0))
    g.tick(10, 1.0)
    g.update_pose(1.75, 0.0, 0.0, 100)       # 0,25 m avant : il CONTINUE (revue M2)
    assert g.tick(110, 1.0).reason == "ok"
    g.update_pose(1.96, 0.0, 0.3, 200)       # reste 0,04 < 0,05, de travers : pas de pivot final
    assert _r(g.tick(210, 1.0)) == (0.0, 0.0, ARRIVED, "arrived")


def test_avancer_delai_10_plus_4_par_metre():
    g = _m(ForwardOrder("avancer 2 m", 2.0))
    g.update_pose(0.0, 0.0, 0.0, 17990)
    assert g.tick(18000, 0.1).reason == "ok"           # 0,05 m/s : sous le seuil de calage
    assert _r(g.tick(18001, 0.1)) == (0.0, 0.0, ABORTED, "timeout")


def test_avancer_distance_parcourue_1_5_fois():
    g = _m(ForwardOrder("avancer 2 m", 2.0))
    g.tick(10, 1.0)
    g.update_pose(1.45, 0.0, 0.0, 100)
    g.update_pose(0.0, 0.0, 0.0, 200)                   # 2,9 m parcourus : sous 3
    assert g.tick(210, 1.0).reason == "ok"
    g.update_pose(0.2, 0.0, 0.0, 300)                   # 3,1 m > 1,5 × 2
    assert _r(g.tick(310, 1.0)) == (0.0, 0.0, ABORTED, "max_travel")


def test_avancer_calage_abandon():
    g = _m(ForwardOrder("avancer 5 m", 5.0))
    reasons = []
    for t in range(10, 3000, 100):
        g.update_pose(0.0, 0.0, 0.0, t)                 # contre un mur : la pose ne bouge pas
        reasons.append(g.tick(t, 1.0).reason)
    assert "stalled" in reasons and g.phase == ABORTED


def test_avancer_fader_zero_rien():
    g = _m(ForwardOrder("avancer 2 m", 2.0))
    assert _r(g.tick(10, 0.0)) == (0.0, 0.0, DRIVE, "held")


# --- revue M2 (31/10) ---------------------------------------------------------------
# Mutations (doivent rougir) :
#  - arrivée jugée à 0,3 m de P (ancien DRIVE) -> test_avancer_petite_distance_roule
#  - retour vers P après dépassement -> test_avancer_depasse_arrive_sans_retour
#  - cap tenu remplacé par visée de P -> test_avancer_tient_le_cap_initial
#  - plancher 0,1 m retiré -> test_parse_refuse_sous_10_cm
#  - plafond |ω| au fader retiré -> test_pivot_plafonne_par_le_fader
#  - plancher 0,15 rad/s retiré -> test_pivot_plancher_au_fader_bas
#  - calage du pivot retiré -> test_pivot_calage_abandon_stalled

def test_parse_refuse_sous_10_cm():
    assert parse_order({"forward_m": 0.1}).metres == 0.1               # borne incluse
    with pytest.raises(GotoError):
        parse_order({"forward_m": 0.09})


def test_avancer_petite_distance_roule():
    g = _m(ForwardOrder("avancer 0.2 m", 0.2))
    assert _r(g.tick(10, 1.0)) == (0.05, 0.0, DRIVE, "ok")             # l'ancien DRIVE arrivait d'emblée
    g.update_pose(0.1, 0.0, 0.0, 100)
    assert round(g.tick(110, 1.0).lin, 6) == 0.05                       # min(rampe 0,1 ; 0,5 × 0,1)
    g.update_pose(0.16, 0.0, 0.0, 200)
    assert g.tick(210, 1.0).reason == "arrived"                         # reste 0,04


def test_avancer_depasse_arrive_sans_retour():
    g = _m(ForwardOrder("avancer 1 m", 1.0))
    g.tick(10, 1.0)
    g.update_pose(1.4, 0.3, 0.0, 100)        # au-delà ET de côté : P serait derrière
    assert _r(g.tick(110, 1.0)) == (0.0, 0.0, ARRIVED, "arrived")


def test_avancer_tient_le_cap_initial():
    g = _m(ForwardOrder("avancer 5 m", 5.0))
    g.tick(10, 1.0)
    g.update_pose(1.0, 0.5, 0.0, 100)        # poussé de côté, cap intact : pas de correction vers P
    assert round(g.tick(110, 1.0).ang, 6) == 0.0
    g.update_pose(1.1, 0.5, 0.2, 200)        # cap dévié de +0,2 : ramené vers 0
    assert round(g.tick(210, 1.0).ang, 6) == -0.15


def test_pivot_plafonne_par_le_fader():
    g = _m(GAUCHE)
    assert [round(g.tick(t, 0.5).ang, 6) for t in (10, 20, 30, 40)] == [0.15, 0.3, 0.3, 0.3]   # 0,6 × 0,5
    h = _m(BANC_A_GAUCHE)
    assert [round(h.tick(t, 0.5).ang, 6) for t in (10, 20, 30)] == [0.15, 0.3, 0.3]           # ALIGN aussi


def test_pivot_plancher_au_fader_bas():
    g = _m(GAUCHE)
    assert [round(g.tick(t, 0.1).ang, 6) for t in (10, 20, 30)] == [0.15, 0.15, 0.15]         # pas 0,06


def test_pivot_calage_abandon_stalled():
    g = _m(GAUCHE)
    reasons = []
    for t in range(10, 3000, 100):
        g.update_pose(0.0, 0.0, 0.0, t)      # coincé : la pose ne tourne pas
        reasons.append(g.tick(t, 1.0).reason)
    assert reasons[:3] == ["ok", "ok", "ok"] and "stalled" in reasons and g.phase == ABORTED
    # |ω| ≤ 0,2 (fader bas, plancher 0,15) : pas de calage, le délai de 15 s couvre
    h = _m(GAUCHE)
    for t in range(10, 3000, 100):
        h.update_pose(0.0, 0.0, 0.0, t)
        assert h.tick(t, 0.1).reason == "ok"


def test_pivot_qui_tourne_ne_cale_pas():
    g = _m(TurnOrder("pivot +180°", math.pi))
    for k, t in enumerate(range(10, 4000, 100)):
        g.update_pose(0.0, 0.0, math.atan2(math.sin(0.06 * k), math.cos(0.06 * k)), t)
        assert g.tick(t, 1.0).reason in ("ok", "arrived")
