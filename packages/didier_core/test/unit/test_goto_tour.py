"""« Faire le tour de X » (didier_rehearsal.goto, OrbitOrder, lot M3,
spec-aller-voir.md §8.4) — logique PURE, valeurs GRAVÉES à la main.
Réglages par défaut : pivots ≤ 0,6 rad/s (rampe 0,15/tick, gain 1,5), rampe
linéaire 0,05/tick, croisière orbite 0,35 m/s, correction radiale 1 rad/m
(≤ 0,6), arrivée sur le cercle à 0,3 m, écart radial toléré 1 m.

Repère des cas « à la main » : centre (0 ; 0), rayon 2. Sur le cercle en
(2 ; 0), la tangente du sens gauche (trigo) est le cap +π/2, celle du sens
droite −π/2.

Passe de mutation du lot M3 (chaque ligne doit rougir) :
  - garde off_track retirée -> test_off_track_poussé_hors_du_cercle, test_off_track_avant_l_achevement
  - garde off_track testée APRÈS l'achèvement -> test_off_track_avant_l_achevement
  - borne 2π de l'angle balayé (ex. 1,9π) -> test_angle_balaye_borne_2pi
  - plancher 0 du cumul retiré -> test_recul_au_depart_sans_dette
  - cancel sans zéro -> test_cancel_zero_franc_immediat
  - fader 0 laissant passer -> test_fader_zero_rien_en_orbite
  - sens ignoré (direction retirée de la correction / du cumul) ->
    test_correction_radiale_vers_le_centre_deux_sens, test_tour_complet_integre[droite]
  - anticipation v/r retirée -> test_orbite_tangente_anticipation
  - délai 2πr / 0,1 retiré -> test_delai_approche_plus_un_tour
"""
import math

import pytest

from didier_rehearsal.goto import (ABORTED, ALIGN, ARRIVED, DRIVE, FACE, ORBIT, GotoError, GotoManeuver,
                                  OrbitOrder, parse_order, tour_name)

GAUCHE = OrbitOrder("tour de objet", 0.0, 0.0, 2.0, 1)
DROITE = OrbitOrder("tour de objet", 0.0, 0.0, 2.0, -1)
POUBELLE = OrbitOrder("tour de poubelle_tri", 27.0, 2.4, 2.1, 1)


def _m(order, pose):
    g = GotoManeuver(order, 0)
    g.update_pose(*pose, 0)
    return g


def _r(out):
    return (round(out.lin, 6), round(out.ang, 6), out.phase, out.reason)


def _sur_le_cercle(angle, direction, r=2.0):
    """Pose sur le cercle de centre (0 ; 0), cap tangent dans le sens demandé."""
    return (r * math.cos(angle), r * math.sin(angle), angle + direction * math.pi / 2)


# --- ordres ----------------------------------------------------------------------

def test_nom_partage():
    assert tour_name("poubelle_tri") == "tour de poubelle_tri"


def test_parse_tour_valide():
    assert parse_order({"name": "tour de poubelle_tri", "orbit_x": 27.0, "orbit_y": 2.4, "orbit_r": 2.1,
                        "orbit_dir": 1}) == POUBELLE
    assert parse_order({"name": "t", "orbit_x": 0, "orbit_y": 0, "orbit_r": 1.5, "orbit_dir": -1}).direction == -1
    assert parse_order({"name": "t", "orbit_x": 0, "orbit_y": 0, "orbit_r": 6.0, "orbit_dir": 1}).radius == 6.0


ORBITE = {"name": "t", "orbit_x": 0.0, "orbit_y": 0.0, "orbit_r": 2.0, "orbit_dir": 1}


@pytest.mark.parametrize("change, fragment", [
    pytest.param({"orbit_r": 1.49}, "orbit_r", id="rayon sous 1,5"),
    pytest.param({"orbit_r": 6.01}, "orbit_r", id="rayon au-dela de 6"),
    pytest.param({"orbit_r": float("nan")}, "orbit_r", id="rayon NaN"),
    pytest.param({"orbit_x": float("inf")}, "orbit_x", id="centre infini"),
    pytest.param({"orbit_y": "2"}, "orbit_y", id="centre texte"),
    pytest.param({"orbit_dir": 0}, "orbit_dir", id="sens 0"),
    pytest.param({"orbit_dir": 2}, "orbit_dir", id="sens 2"),
    pytest.param({"orbit_dir": True}, "orbit_dir", id="sens booleen"),
    pytest.param({"orbit_dir": "1"}, "orbit_dir", id="sens texte"),
    pytest.param({"name": ""}, "name", id="sans nom"),
    pytest.param({"x": 1.0}, "ambigu", id="ambigu goto"),
    pytest.param({"turn_rad": 1.0}, "ambigu", id="ambigu pivot"),
])
def test_parse_tour_refuse(change, fragment):
    with pytest.raises(GotoError) as exc:
        parse_order({**ORBITE, **change})
    assert fragment in str(exc.value)


def test_parse_forme_tour_incomplete_refusee():
    with pytest.raises(GotoError) as exc:
        parse_order({"name": "t", "orbit_r": 2.0, "orbit_dir": 1})      # pas de centre
    assert "orbit_x" in str(exc.value)


# --- approche --------------------------------------------------------------------

def test_point_d_entree_le_plus_proche_et_bornes():
    # Depuis (20 ; 0) : |pose − C| = 7,4 ; E = C + 2,1 × (−7 ; −2,4) / 7,4.
    g = _m(POUBELLE, (20.0, 0.0, 0.0))
    assert _r(g.tick(10, 1.0))[2] == ALIGN
    assert tuple(round(v, 6) for v in g.stop_point) == (25.013514, 1.718919)
    # Délai : 60 + 2π × 2,1 / 0,1 = 191,946891 s.
    assert round(g.config.timeout_s, 6) == 191.946891


def test_au_centre_entree_droit_devant():
    g = _m(GAUCHE, (0.1, 0.0, math.pi / 2))      # à 0,1 m du centre : direction indéfinie
    g.tick(10, 1.0)
    assert tuple(round(v, 6) for v in g.stop_point) == (0.0, 2.0)


def test_deja_sur_le_cercle_orbite_d_emblee_pivot_d_entree():
    # Sur le cercle, cap RADIAL (0) : erreur π/2 -> v = 0, pivot vers la tangente.
    g = _m(GAUCHE, (2.0, 0.0, 0.0))
    outs = [_r(g.tick(t, 1.0)) for t in (10, 20, 30, 40, 50)]
    assert outs == [(0.0, 0.15, ORBIT, "ok"), (0.0, 0.3, ORBIT, "ok"), (0.0, 0.45, ORBIT, "ok"),
                    (0.0, 0.6, ORBIT, "ok"), (0.0, 0.6, ORBIT, "ok")]


def test_pivot_d_entree_plafonne_par_le_fader():
    g = _m(GAUCHE, (2.0, 0.0, 0.0))
    assert [round(g.tick(t, 0.5).ang, 6) for t in (10, 20, 30, 40)] == [0.15, 0.3, 0.3, 0.3]   # 0,6 × 0,5


def test_trop_loin_du_centre_abandon_too_far():
    g = _m(OrbitOrder("t", 41.0, 0.0, 2.0, 1), (0.0, 0.0, 0.0))
    assert _r(g.tick(10, 1.0)) == (0.0, 0.0, ABORTED, "too_far")


# --- orbite ----------------------------------------------------------------------

def test_orbite_tangente_anticipation():
    # Sur le cercle, cap tangent : v rampe 0,05 ; ω = 1,5 × 0 + dir × 0,05 / 2.
    assert _r(_m(GAUCHE, _sur_le_cercle(0.0, 1)).tick(10, 1.0)) == (0.05, 0.025, ORBIT, "ok")
    assert _r(_m(DROITE, _sur_le_cercle(0.0, -1)).tick(10, 1.0)) == (0.05, -0.025, ORBIT, "ok")


def test_correction_radiale_vers_le_centre_deux_sens():
    # À 2,25 m (0,25 de trop) : cap visé tangent + dir × 0,25 -> erreur dir × 0,25,
    # v cible 0,35 × (1 − 0,25/0,8) rampée, ω = 1,5 × 0,25 + v/2, rampe 0,15.
    g = _m(GAUCHE, (2.25, 0.0, math.pi / 2))
    assert [_r(g.tick(t, 1.0))[:2] for t in (10, 20, 30)] == [(0.05, 0.15), (0.1, 0.3), (0.15, 0.45)]
    d = _m(DROITE, (2.25, 0.0, -math.pi / 2))
    assert [_r(d.tick(t, 1.0))[:2] for t in (10, 20, 30)] == [(0.05, -0.15), (0.1, -0.3), (0.15, -0.45)]


def test_croisiere_orbite_0_35():
    g = _m(GAUCHE, _sur_le_cercle(0.0, 1))
    assert round(max(g.tick(t, 1.0).lin for t in range(10, 300, 10)), 6) == 0.35
    h = _m(GAUCHE, _sur_le_cercle(0.0, 1))
    assert round(max(h.tick(t, 0.4).lin for t in range(10, 300, 10)), 6) == 0.2   # 0,5 × 0,4 < 0,35


def _tourner(g, direction, angles, t0=0):
    """Pose posée sur le cercle à chaque angle (radians, dans le sens demandé), tick après chacune."""
    outs = []
    for k, a in enumerate(angles, start=1):
        t = t0 + 100 * k
        g.update_pose(*_sur_le_cercle(direction * a, direction), t)
        outs.append(g.tick(t + 10, 1.0))
    return outs


@pytest.mark.parametrize("direction", [1, -1], ids=["gauche", "droite"])
def test_angle_balaye_borne_2pi(direction):
    order = GAUCHE if direction == 1 else DROITE
    g = _m(order, _sur_le_cercle(0.0, direction))
    g.tick(10, 1.0)
    pas = [k * math.pi / 8 for k in range(1, 16)] + [15.9 * math.pi / 8]
    outs = _tourner(g, direction, pas)
    assert {(o.phase, o.reason) for o in outs} == {(ORBIT, "ok")}
    assert round(g.swept, 6) == round(15.9 * math.pi / 8, 6)
    out = _tourner(g, direction, [16.1 * math.pi / 8], t0=1700)[0]
    assert (out.phase, out.reason) == (FACE, "ok")                      # tour bouclé : pivot vers le centre
    # Face au centre (cap θ + π) : arrêt.
    theta = direction * 16.1 * math.pi / 8
    g.update_pose(2.0 * math.cos(theta), 2.0 * math.sin(theta), theta + math.pi, 2000)
    assert _r(g.tick(2010, 1.0)) == (0.0, 0.0, ARRIVED, "arrived")


def test_recul_au_depart_sans_dette():
    g = _m(GAUCHE, _sur_le_cercle(0.0, 1))
    g.tick(10, 1.0)
    g.update_pose(*_sur_le_cercle(-0.2, 1), 100)     # recule de 0,2 rad (poussé)
    assert g.swept == 0.0
    g.update_pose(*_sur_le_cercle(0.2, 1), 200)      # puis avance de 0,4 rad
    assert round(g.swept, 6) == 0.4                  # pas 0,2 : le recul n'a pas créé de dette


def test_recul_en_cours_de_tour_decompte():
    g = _m(GAUCHE, _sur_le_cercle(0.0, 1))
    g.tick(10, 1.0)
    for k, a in enumerate((0.5, 1.0, 0.7), start=1):
        g.update_pose(*_sur_le_cercle(a, 1), 100 * k)
    assert round(g.swept, 6) == 0.7                  # angle RÉEL balayé, pas la somme des |Δθ|


# --- sûreté ----------------------------------------------------------------------

def test_off_track_pousse_hors_du_cercle():
    g = _m(GAUCHE, _sur_le_cercle(0.0, 1))
    g.tick(10, 1.0)
    g.update_pose(2.95, 0.0, math.pi / 2, 100)       # écart 0,95 : encore toléré
    assert g.tick(110, 1.0).reason == "ok"
    g.update_pose(3.05, 0.0, math.pi / 2, 200)       # écart 1,05 > 1
    assert _r(g.tick(210, 1.0)) == (0.0, 0.0, ABORTED, "off_track")
    assert _r(g.tick(220, 1.0)) == (0.0, 0.0, ABORTED, "off_track")    # terminal


def test_off_track_vers_l_interieur():
    g = _m(GAUCHE, _sur_le_cercle(0.0, 1))
    g.tick(10, 1.0)
    g.update_pose(0.9, 0.0, math.pi / 2, 100)        # écart −1,1
    assert g.tick(110, 1.0).reason == "off_track"


def test_off_track_avant_l_achevement():
    # Presque bouclé, puis pose TÉLÉPORTÉE au-delà du tour ET hors du cercle :
    # abandon, pas « tour fini ».
    g = _m(GAUCHE, _sur_le_cercle(0.0, 1))
    g.tick(10, 1.0)
    _tourner(g, 1, [k * math.pi / 8 for k in range(1, 16)])
    a = 16.1 * math.pi / 8
    g.update_pose(3.6 * math.cos(a), 3.6 * math.sin(a), a + math.pi / 2, 1700)
    assert _r(g.tick(1710, 1.0)) == (0.0, 0.0, ABORTED, "off_track")


def test_off_track_pas_pendant_l_approche():
    g = _m(GAUCHE, (10.0, 0.0, math.pi))             # à 8 m du cercle : on approche
    assert g.tick(10, 1.0).reason == "ok" and g.phase in (ALIGN, DRIVE)


def test_cancel_zero_franc_immediat():
    g = _m(GAUCHE, _sur_le_cercle(0.0, 1))
    for t in range(10, 80, 10):
        assert g.tick(t, 1.0).lin > 0.0               # en mouvement
    g.cancel()
    assert _r(g.tick(80, 1.0)) == (0.0, 0.0, ABORTED, "cancelled")


def test_fader_zero_rien_en_orbite():
    g = _m(GAUCHE, _sur_le_cercle(0.0, 1))
    for t in (10, 20, 30):
        g.tick(t, 1.0)
    assert _r(g.tick(40, 0.0)) == (0.0, 0.0, ORBIT, "held")
    h = _m(GAUCHE, (2.0, 0.0, 0.0))                  # pivot d'entrée : rien non plus
    assert _r(h.tick(10, 0.0)) == (0.0, 0.0, ORBIT, "held")


def test_calage_en_orbite_abandon():
    g = _m(GAUCHE, _sur_le_cercle(0.0, 1))
    reasons = []
    for t in range(10, 3000, 100):
        g.update_pose(*_sur_le_cercle(0.0, 1), t)    # contre un obstacle : la pose ne bouge plus
        reasons.append(g.tick(t, 1.0).reason)
    assert reasons[:3] == ["ok", "ok", "ok"] and "stalled" in reasons and g.phase == ABORTED


def test_delai_approche_plus_un_tour():
    # r = 2 : 60 + 2π × 2 / 0,1 = 185,663706 s. Fader bas (0,05 m/s < seuil de calage).
    g = _m(GAUCHE, _sur_le_cercle(0.0, 1))
    g.update_pose(*_sur_le_cercle(0.0, 1), 185600)
    assert g.tick(185663, 0.1).reason == "ok"
    assert _r(g.tick(185664, 0.1)) == (0.0, 0.0, ABORTED, "timeout")


def test_distance_parcourue_bornee():
    # Sur le cercle : borne = 1,5 × (0 + 2π × 2) = 18,849556 m.
    g = _m(GAUCHE, _sur_le_cercle(0.0, 1))
    g.tick(10, 1.0)
    for k in range(1, 10):                           # va-et-vient : corde 2r·sin(π/6) = 2 m, 9 × 2 = 18 m
        g.update_pose(*_sur_le_cercle(0.0 if k % 2 == 0 else math.pi / 3, 1), 100 * k)
    assert g.tick(910, 1.0).reason == "ok"
    g.update_pose(*_sur_le_cercle(0.0, 1), 1000)     # 20 m > 18,85
    assert _r(g.tick(1010, 1.0)) == (0.0, 0.0, ABORTED, "max_travel")


def test_pose_non_finie_ignoree_puis_perimee():
    g = _m(GAUCHE, _sur_le_cercle(0.0, 1))
    g.tick(10, 1.0)
    g.update_pose(float("nan"), 0.0, 0.0, 300)
    assert g.swept == 0.0                            # rien d'intégré sur un NaN
    assert g.tick(700, 1.0).reason == "odom_stale"   # la pose de 0 ms vieillit


# --- tour complet (intégrateur cinématique) ------------------------------------------

def _integrer(order, pose, speed=1.0, ticks=4000):
    """Unicycle idéal à 10 Hz : la consigne du tick est appliquée 0,1 s, puis
    la pose (vérité terrain) revient 5 ms après."""
    g = GotoManeuver(order, 0)
    x, y, yaw = pose
    g.update_pose(x, y, yaw, 0)
    phases, max_lin_orbite, max_ang, max_dev = [], 0.0, 0.0, 0.0
    for k in range(1, ticks + 1):
        t = 100 * k
        out = g.tick(t, speed)
        if not phases or phases[-1] != out.phase:
            phases.append(out.phase)
        if out.phase == ORBIT:
            max_lin_orbite = max(max_lin_orbite, abs(out.lin))
            max_dev = max(max_dev, abs(math.hypot(x - order.cx, y - order.cy) - order.radius))
        max_ang = max(max_ang, abs(out.ang))
        x, y = x + out.lin * math.cos(yaw) * 0.1, y + out.lin * math.sin(yaw) * 0.1
        yaw = math.atan2(math.sin(yaw + out.ang * 0.1), math.cos(yaw + out.ang * 0.1))
        g.update_pose(x, y, yaw, t + 5)
        if g.finished:
            return g, t, (x, y, yaw), phases, max_lin_orbite, max_ang, max_dev
    raise AssertionError("tour jamais terminé")


@pytest.mark.parametrize("direction, fin_ms, pose_finale", [
    (1, 55800, (25.06, 1.6, 0.3)),
    (-1, 55800, (24.97, 1.85, 0.36)),
], ids=["gauche", "droite"])
def test_tour_complet_integre(direction, fin_ms, pose_finale):
    order = OrbitOrder("tour de poubelle_tri", 27.0, 2.4, 2.1, direction)
    g, t, (x, y, yaw), phases, max_lin, max_ang, max_dev = _integrer(order, (20.0, 0.0, 0.0))
    assert (g.phase, g.reason, t) == (ARRIVED, "arrived", fin_ms)
    assert phases == [ALIGN, DRIVE, ORBIT, FACE, ARRIVED]
    assert (round(x, 2), round(y, 2), round(yaw, 2)) == pose_finale
    assert g.swept >= 2 * math.pi
    # Arrêté sur le cercle, FACE au centre (tolérance de cap 0,1 rad).
    assert abs(math.hypot(x - 27.0, y - 2.4) - 2.1) < 0.3
    assert abs(math.atan2(math.sin(math.atan2(2.4 - y, 27.0 - x) - yaw),
                          math.cos(math.atan2(2.4 - y, 27.0 - x) - yaw))) < 0.1
    assert max_lin <= 0.35 and max_ang <= 0.6 and max_dev < 0.3


def test_tour_complet_sens_de_rotation():
    """Le sens demandé est le sens PARCOURU : cap moyen tourné (+ = gauche)."""
    for direction in (1, -1):
        order = OrbitOrder("t", 0.0, 0.0, 2.0, direction)
        g = GotoManeuver(order, 0)
        x, y, yaw = 2.0, 0.0, direction * math.pi / 2
        g.update_pose(x, y, yaw, 0)
        theta_cumul = 0.0
        for k in range(1, 60):
            out = g.tick(100 * k, 1.0)
            th0 = math.atan2(y, x)
            x, y = x + out.lin * math.cos(yaw) * 0.1, y + out.lin * math.sin(yaw) * 0.1
            yaw += out.ang * 0.1
            theta_cumul += math.atan2(math.sin(math.atan2(y, x) - th0), math.cos(math.atan2(y, x) - th0))
            g.update_pose(x, y, yaw, 100 * k + 5)
        assert direction * theta_cumul > 0.5                # parti dans le bon sens
