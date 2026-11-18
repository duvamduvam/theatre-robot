"""geometrie : distance à la caisse, invariant du pivot, rayons → base_link (§6.2)."""
import math

import pytest

from didier_corps_sur.geometrie import (Caisse, PoseLidar, distance_caisse, ecart_pivot,
                                        invariant_pivot, point_dans_base, points_dans_base)

# Caisse par défaut de la spec §4.1, écrite en dur (pas Caisse()).
CAISSE = Caisse(x_avant=0.30, x_arriere=-0.57, demi_largeur=0.40, x_essieu=0.10, rayon_balayage=0.65)


def test_caisse_sans_argument_vaut_les_defauts_de_la_spec():
    assert Caisse() == CAISSE


@pytest.mark.parametrize("x, y, attendu", [
    (0.90, 0.0, 0.60),
    (0.80, 0.0, 0.50),
    (0.60, 0.80, 0.50),     # triangle 0,3-0,4-0,5 : coin avant gauche
    (0.0, 0.95, 0.55),
    (-1.17, 0.0, 0.60),
    (0.0, 0.0, 0.0),
    (-0.60, -0.80, 0.40112),  # coin arrière droit : dx 0,03, dy 0,40
])
def test_distance_caisse(x, y, attendu):
    assert distance_caisse(CAISSE, x, y) == pytest.approx(attendu, abs=1e-5)


def test_invariant_du_pivot_defauts_accepte():
    ok, ecart = invariant_pivot(CAISSE, 0.60)
    assert ok
    assert ecart == pytest.approx(0.45, abs=1e-9)


def test_invariant_du_pivot_essieu_avance_refuse():
    caisse = Caisse(0.30, -0.57, 0.40, 0.30, 0.65)
    ok, ecart = invariant_pivot(caisse, 0.60)
    assert not ok
    assert ecart == pytest.approx(0.65, abs=1e-9)


def test_invariant_du_pivot_borne_par_l_arriere_et_les_flancs():
    # Essieu reculé : le pire point est l'arrière, −0,57 − (−0,40 − 0,70) = 0,53.
    assert ecart_pivot(Caisse(0.30, -0.57, 0.40, -0.40, 0.70)) == pytest.approx(0.53, abs=1e-9)
    # Rayon large et caisse étroite : le pire point est un flanc, 0,90 − 0,20 = 0,70.
    assert ecart_pivot(Caisse(0.50, -0.50, 0.20, 0.0, 0.90)) == pytest.approx(0.70, abs=1e-9)


POSE_AVANT = PoseLidar(0.33, 0.0, 0.0)


def test_rayon_angle_0_devant():
    x, y = point_dans_base(POSE_AVANT, 0.0, 0.56)
    assert (x, y) == pytest.approx((0.89, 0.0), abs=1e-9)
    assert distance_caisse(CAISSE, x, y) == pytest.approx(0.59, abs=1e-9)


def test_rayon_angle_90_a_gauche():
    x, y = point_dans_base(POSE_AVANT, math.pi / 2, 0.90)
    assert (x, y) == pytest.approx((0.33, 0.90), abs=1e-9)
    assert distance_caisse(CAISSE, x, y) == pytest.approx(0.50090, abs=1e-5)  # dx 0,03, dy 0,50


def test_lidar_retourne_lacet_pi():
    x, y = point_dans_base(PoseLidar(0.33, 0.0, math.pi), 0.0, 0.50)
    assert (x, y) == pytest.approx((-0.17, 0.0), abs=1e-9)
    assert distance_caisse(CAISSE, x, y) == 0.0


def test_signe_du_lacet():
    # Lacet +90° (trigo) : le « devant » du lidar regarde à gauche de Didier (y > 0).
    x, y = point_dans_base(PoseLidar(0.33, 0.0, math.pi / 2), 0.0, 1.0)
    assert (x, y) == pytest.approx((0.33, 1.0), abs=1e-9)


def test_points_dans_base_saute_les_non_finis_et_garde_l_ordre():
    pts = points_dans_base(PoseLidar(0.0, 0.0, 0.0), 0.0, math.pi / 2,
                           [1.0, math.inf, math.nan, 2.0])
    assert len(pts) == 2
    assert pts[0] == pytest.approx((1.0, 0.0), abs=1e-9)
    assert pts[1] == pytest.approx((0.0, -2.0), abs=1e-9)  # 4e rayon : 270°
