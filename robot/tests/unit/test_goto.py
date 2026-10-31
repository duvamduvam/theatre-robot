"""Manœuvre « aller voir » (robot_rehearsal.goto, lot M1, spec-aller-voir.md
§4) — logique PURE, valeurs GRAVÉES à la main (règle du 14/09 : un test qui
recalcule l'attendu avec la fonction testée ne teste rien).

Passe de mutation du lot M1 (chaque ligne doit rougir) :
  - cancel() sans effet -> test_cancel_zero_franc_immediat_et_terminal
  - retirer la condition odom_stale -> test_odometrie_perimee_zero_sans_abandon
  - retirer le délai max -> test_delai_60_s_abandon
  - retirer la borne de distance parcourue -> test_distance_parcourue_1_5_fois
  - retirer les min(…) du constructeur -> test_plafonds_absolus
  - démarrer en DRIVE (sauter ALIGN) -> test_demi_tour_passe_par_align
Revue M1 (31/10) :
  - retirer `* heading_factor` -> test_drive_erreur_de_cap_annule_la_vitesse
  - pose non finie acceptée -> test_pose_non_finie_ignoree*
  - borne écrite `>` (NaN la désactive) -> test_distance_parcourue_nan_abandonne
  - retirer le détecteur de calage -> test_calage_abandon_stalled
  - plancher du standoff retiré -> test_parse_order_refuse_explicitement[standoff 0,79]
"""
import math

import pytest

from robot_rehearsal.contracts import ABS_MAX_LIN, GOTO_MAX_ANG
from robot_rehearsal.goto import (ABORTED, ALIGN, ARRIVED, DRIVE, FACE, GotoConfig, GotoError,
                                  GotoManeuver, GotoOrder, parse_order)

ANNEAUX = GotoOrder("anneaux", 10.0, 0.0, 1.5)   # P = (8,5 ; 0) depuis l'origine


def _goto(order=ANNEAUX, pose=(0.0, 0.0, 0.0), **cfg):
    g = GotoManeuver(order, 0, GotoConfig(**cfg))
    g.update_pose(*pose, 0)
    return g


def _r(out):
    return (round(out.lin, 6), round(out.ang, 6), out.phase, out.reason)


# --- ordre ----------------------------------------------------------------------

def test_parse_order_valide():
    assert parse_order({"name": "anneaux", "x": 78.42, "y": 4.19, "standoff": 1.5}) == \
        GotoOrder("anneaux", 78.42, 4.19, 1.5)
    assert parse_order({"name": "a", "x": 1, "y": 2, "standoff": 0.8}).standoff == 0.8   # plancher inclus


@pytest.mark.parametrize("value, fragment", [
    ("anneaux", "objet JSON"),
    ({"x": 1, "y": 2, "standoff": 1.5}, "name"),
    ({"name": "a", "x": "1", "y": 2, "standoff": 1.5}, "x"),
    ({"name": "a", "x": 1, "y": float("nan"), "standoff": 1.5}, "y"),
    ({"name": "a", "x": 1, "y": 2, "standoff": -0.1}, "standoff"),
    ({"name": "a", "x": 1, "y": 2, "standoff": 0.79}, "entre 0.8 et"),
    ({"name": "a", "x": 1, "y": 2, "standoff": 41}, "standoff"),
    ({"name": "a", "x": 1, "y": 2, "standoff": True}, "standoff"),
])
def test_parse_order_refuse_explicitement(value, fragment):
    with pytest.raises(GotoError) as exc:
        parse_order(value)
    assert fragment in str(exc.value)


# --- machine à états --------------------------------------------------------------

def test_point_d_arret_a_standoff_le_long_de_l_axe():
    g = _goto(GotoOrder("x", 3.0, 4.0, 1.5))     # d = 5, P à 3,5 m sur l'axe
    g.tick(10, 1.0)
    assert tuple(round(v, 6) for v in g.stop_point) == (2.1, 2.8)


def test_cible_devant_drive_avec_rampe_du_suivi_et_fader():
    g = _goto()
    outs = [g.tick(t, 0.5) for t in range(10, 80, 10)]
    # cap déjà bon : ALIGN franchi au 1er tick ; slew 0,05 jusqu'à 0,5 × ABS_MAX_LIN
    assert [round(o.lin, 6) for o in outs] == [0.05, 0.1, 0.15, 0.2, 0.25, 0.25, 0.25]
    assert {o.ang for o in outs} == {0.0} and {o.phase for o in outs} == {DRIVE}
    h = _goto()
    lins = [h.tick(t, 1.0).lin for t in range(10, 130, 10)]
    assert round(max(lins), 6) == ABS_MAX_LIN == 0.5   # fader 1 : jamais plus


def test_facteur_hors_bornes_borne():
    g = _goto()
    lins = [g.tick(t, 7.0).lin for t in range(10, 130, 10)]
    assert round(max(lins), 6) == 0.5


def test_demi_tour_passe_par_align():
    g = _goto(GotoOrder("flaque", -5.0, 0.0, 1.5))   # cible DERRIÈRE
    outs = [g.tick(t, 1.0) for t in range(10, 60, 10)]
    # pivot sur place, v = 0, |ω| plafonné à 0,6 (slew 0,15)
    assert [_r(o) for o in outs] == [(0.0, 0.15, ALIGN, "ok"), (0.0, 0.3, ALIGN, "ok"),
                                     (0.0, 0.45, ALIGN, "ok"), (0.0, 0.6, ALIGN, "ok"),
                                     (0.0, 0.6, ALIGN, "ok")]
    assert tuple(round(v, 6) for v in g.stop_point) == (-3.5, 0.0)
    g.update_pose(0.0, 0.0, math.pi - 0.05, 60)       # aligné
    assert g.tick(70, 1.0).phase == DRIVE


def test_deja_a_distance_de_jeu_pivote_face_puis_arrive():
    g = _goto(pose=(8.5, 0.0, math.pi / 2))           # à 1,5 m, regarde +y
    assert _r(g.tick(10, 1.0)) == (0.0, -0.15, FACE, "ok")
    assert g.stop_point == (8.5, 0.0)                 # pas de recul
    g.update_pose(8.5, 0.0, 0.05, 20)
    assert _r(g.tick(30, 1.0)) == (0.0, 0.0, ARRIVED, "arrived")
    assert g.finished
    g.update_pose(8.5, 0.0, 1.0, 40)                  # arrivé : plus rien ne tourne
    assert _r(g.tick(50, 1.0)) == (0.0, 0.0, ARRIVED, "arrived")


def test_trajet_complet_arrive_face_a_la_cible():
    """Intégration grossière (unicycle, 10 Hz) : ALIGN -> DRIVE -> ARRIVED. FACE se
    boucle dans le tick d'arrivée : en ligne droite, Didier arrive à P déjà face à
    la cible (le pivot FACE est gravé par test_deja_a_distance_de_jeu…)."""
    g = _goto(GotoOrder("anneaux", 6.0, 3.0, 1.5), pose=(0.0, 0.0, math.pi / 2))
    x, y, yaw, phases = 0.0, 0.0, math.pi / 2, []
    for k in range(1, 400):
        out = g.tick(k * 100, 1.0)
        phases.append(out.phase)
        if g.finished:
            break
        yaw += out.ang * 0.1
        x += out.lin * 0.1 * math.cos(yaw)
        y += out.lin * 0.1 * math.sin(yaw)
        g.update_pose(x, y, yaw, k * 100)
    assert g.phase == ARRIVED
    assert [p for i, p in enumerate(phases) if i == 0 or p != phases[i - 1]] == [ALIGN, DRIVE, ARRIVED]
    assert 1.2 < math.hypot(6.0 - x, 3.0 - y) < 1.9   # ~ distance de jeu


# --- sûreté (spec §4) -----------------------------------------------------------------

def test_cancel_zero_franc_immediat_et_terminal():
    g = _goto()
    for t in range(10, 60, 10):
        g.tick(t, 1.0)
    assert round(g.tick(60, 1.0).lin, 6) == 0.3
    g.cancel()
    assert _r(g.tick(70, 1.0)) == (0.0, 0.0, ABORTED, "cancelled")   # pas 0,25 : FRANC
    assert g.finished
    g.update_pose(0.0, 0.0, 0.0, 80)
    assert _r(g.tick(90, 1.0)) == (0.0, 0.0, ABORTED, "cancelled")   # jamais de reprise


def test_odometrie_perimee_zero_sans_abandon():
    g = _goto()
    assert g.tick(600, 1.0).reason == "ok"
    assert _r(g.tick(601, 1.0)) == (0.0, 0.0, DRIVE, "odom_stale")
    assert not g.finished
    g.update_pose(0.0, 0.0, 0.0, 700)
    assert _r(g.tick(710, 1.0)) == (0.05, 0.0, DRIVE, "ok")          # repart du zéro


def test_sans_pose_zero():
    g = GotoManeuver(ANNEAUX, 0)
    assert _r(g.tick(10, 1.0)) == (0.0, 0.0, ALIGN, "no_pose")


def test_delai_60_s_abandon():
    g = _goto(GotoOrder("x", 30.0, 0.0, 1.5))
    g.update_pose(0.0, 0.0, 0.0, 59990)
    assert g.tick(60000, 1.0).reason == "ok"
    assert _r(g.tick(60001, 1.0)) == (0.0, 0.0, ABORTED, "timeout")
    assert g.finished


def test_distance_parcourue_1_5_fois():
    g = _goto()                      # P à 8,5 m -> borne 12,75 m
    g.tick(10, 1.0)
    g.update_pose(6.0, 0.0, 0.0, 20)
    g.update_pose(0.0, 0.0, 0.0, 30)
    assert round(g.travelled, 6) == 12.0
    assert g.tick(40, 1.0).reason == "ok"
    g.update_pose(0.8, 0.0, 0.0, 50)
    assert _r(g.tick(60, 1.0)) == (0.0, 0.0, ABORTED, "max_travel")


def test_distance_parcourue_plancher_d_un_metre():
    g = _goto(pose=(8.5, 0.0, math.pi / 2))     # déjà en place : 1,5 × 0 -> plancher 1 m
    g.tick(10, 1.0)
    g.update_pose(8.5, 0.9, math.pi / 2, 20)
    assert g.tick(30, 1.0).reason == "ok"
    g.update_pose(8.5, 0.0, math.pi / 2, 40)
    assert g.tick(50, 1.0).reason == "max_travel"


def test_trop_loin_abandon_ceinture():
    g = _goto(GotoOrder("x", 40.1, 0.0, 1.5))
    assert _r(g.tick(10, 1.0)) == (0.0, 0.0, ABORTED, "too_far")


def test_fader_a_zero_aucun_pivot():
    g = _goto(GotoOrder("flaque", -5.0, 0.0, 1.5))
    assert _r(g.tick(10, 0.0)) == (0.0, 0.0, ALIGN, "held")
    assert _r(g.tick(20, 1.0)) == (0.0, 0.15, ALIGN, "ok")


def test_plafonds_absolus():
    g = GotoManeuver(ANNEAUX, 0, GotoConfig(max_lin=5.0, max_ang=3.0))
    assert g.config.max_lin == ABS_MAX_LIN == 0.5
    assert g.config.max_ang == GOTO_MAX_ANG == 0.6


# --- revue M1 (31/10) ------------------------------------------------------------------

def test_drive_erreur_de_cap_annule_la_vitesse():
    g = _goto()
    for t in range(10, 110, 10):
        g.tick(t, 1.0)
    assert round(g.tick(110, 1.0).lin, 6) == 0.5
    g.update_pose(0.0, 0.0, 0.9, 115)        # cap à 0,9 rad > heading_slow 0,8 : cible v = 0
    out = g.tick(120, 1.0)
    assert (round(out.lin, 6), out.phase) == (0.45, DRIVE)    # sans le facteur : 0,5
    for t in range(130, 220, 10):
        out = g.tick(t, 1.0)
    assert (round(out.lin, 6), round(out.ang, 6)) == (0.0, -0.6)   # roule plus, corrige le cap
    g.update_pose(0.0, 0.0, 0.4, 225)        # cap à 0,4 rad : cible v = 0,5 × 0,5 = 0,25
    lins = [round(g.tick(t, 1.0).lin, 6) for t in range(230, 300, 10)]
    assert lins == [0.05, 0.1, 0.15, 0.2, 0.25, 0.25, 0.25]


def test_pose_non_finie_ignoree_meme_la_premiere():
    g = GotoManeuver(ANNEAUX, 0)
    g.update_pose(float("nan"), 0.0, 0.0, 0)
    assert _r(g.tick(10, 1.0)) == (0.0, 0.0, ALIGN, "no_pose")
    assert g.stop_point is None
    g.update_pose(0.0, 0.0, float("inf"), 10)
    assert g.tick(20, 1.0).reason == "no_pose"
    g.update_pose(0.0, 0.0, 0.0, 20)
    assert g.tick(30, 1.0).reason == "ok" and g.stop_point == (8.5, 0.0)


def test_pose_non_finie_ignoree_devient_perimee():
    g = _goto()
    g.tick(10, 1.0)
    g.update_pose(float("nan"), float("nan"), 0.0, 500)
    assert g.travelled == 0.0                 # jamais de NaN dans la somme
    assert g.tick(600, 1.0).reason == "ok"    # la bonne pose (0 ms) tient 600 ms
    assert _r(g.tick(601, 1.0)) == (0.0, 0.0, DRIVE, "odom_stale")


def test_distance_parcourue_nan_abandonne():
    """Boîte blanche : update_pose filtre déjà les NaN ; la borne écrite
    « not <= » est la ceinture si un NaN entrait quand même dans la somme."""
    g = _goto()
    g.tick(10, 1.0)
    g._travelled = float("nan")
    assert _r(g.tick(20, 1.0)) == (0.0, 0.0, ABORTED, "max_travel")


def test_calage_abandon_stalled():
    g = _goto()
    for t in range(100, 2300, 100):          # pose figée (contre un objet), toujours fraîche
        g.update_pose(0.0, 0.0, 0.0, t - 50)
        assert g.tick(t, 1.0).reason == "ok", t   # v > 0,1 dès 300 ms : référence à 300
    g.update_pose(0.0, 0.0, 0.0, 2250)
    assert _r(g.tick(2300, 1.0)) == (0.0, 0.0, ABORTED, "stalled")


def test_pas_de_calage_si_didier_avance():
    g = _goto(GotoOrder("x", 30.0, 0.0, 1.5))
    x = 0.0
    for t in range(100, 4000, 100):
        out = g.tick(t, 1.0)
        assert out.reason == "ok", t
        x += out.lin * 0.1
        g.update_pose(x, 0.0, 0.0, t + 10)


def test_pas_de_calage_en_pivot():
    g = _goto(GotoOrder("flaque", -5.0, 0.0, 1.5))
    for t in range(100, 4000, 100):          # pivot ralenti par un objet : pas de consigne v
        g.update_pose(0.0, 0.0, 0.0, t - 50)
        assert g.tick(t, 1.0).reason == "ok"
