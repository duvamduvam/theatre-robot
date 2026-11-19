"""balayage : validité des points et des balayages, masques, témoin (§4.2-4.3, §6.2)."""
import math

import pytest

from didier_corps_sur.balayage import (ParametresBalayage, Temoin, dans_arc, lire_balayage)
from didier_corps_sur.geometrie import Caisse, PoseLidar
from didier_corps_sur.zones import ARRET, ParametresZones, Zones

CAISSE = Caisse(0.30, -0.57, 0.40, 0.10, 0.65)
POSE = PoseLidar(0.33, 0.0, 0.0)
SANS_TEMOIN = Temoin(False, (0.0, 0.0), (0.0, 0.0), 0)
# Témoin : auto-retours du support, secteur 175-185°, entre 0,06 et 0,10 m, 5 points.
TEMOIN = Temoin(True, (175.0, 185.0), (0.06, 0.10), 5)
N = 500
INC = 2 * math.pi / N   # 0,72°, rayon 0 = angle 0 (devant)


def params(masques=(), temoin=SANS_TEMOIN):
    return ParametresBalayage(portee_min_m=0.05, portee_max_m=12.0, rayons_min=300,
                              age_max_reception_s=0.25, masques_deg=tuple(masques), temoin=temoin)


def lire(distances, p=None, stamp=10.0, precedent=9.9, maintenant=10.05):
    return lire_balayage(p or params(), CAISSE, POSE, stamp, precedent, maintenant,
                         0.0, INC, distances)


def vide():
    return [math.inf] * N


def zone_de(lecture):
    z = Zones(ParametresZones(0.60, 1.20, 0.05, 3))
    return z.observer(lecture.d_min_m, lecture.valide)


def test_un_point_devant_a_0_56_arrete():
    d = vide()
    d[0] = 0.56
    lecture = lire(d)
    assert lecture.valide
    assert lecture.points_valides == 1
    assert lecture.d_min_m == pytest.approx(0.59, abs=1e-9)
    assert zone_de(lecture) == ARRET


def test_le_meme_dans_un_masque_est_ignore():
    d = vide()
    d[0] = 0.56
    lecture = lire(d, params(masques=[(-5.0, 5.0)]))
    assert lecture.points_valides == 0
    assert lecture.d_min_m == math.inf


@pytest.mark.parametrize("r", [0.04, math.nan, 0.0, 12.5, -0.3])
def test_points_hors_portee_ou_non_finis_ignores(r):
    d = vide()
    d[0] = r
    lecture = lire(d)
    assert lecture.points_valides == 0
    assert lecture.d_min_m == math.inf


def test_portee_bornes_comprises():
    d = vide()
    d[0] = 0.05
    d[N // 2] = 12.0
    assert lire(d).points_valides == 2


def test_retour_dans_la_caisse_hors_masque():
    d = vide()
    d[N // 2] = 0.20     # vers l'arrière, à 0,20 m : x = 0,13, dans la caisse
    lecture = lire(d)
    assert lecture.retour_dans_caisse
    assert lecture.d_min_m == 0.0


def test_299_rayons_invalide():
    assert lire([math.inf] * 299).motifs == ("rayons_insuffisants",)
    assert lire([math.inf] * 300).valide


def test_stamp_egal_au_precedent_invalide():
    assert lire(vide(), stamp=10.0, precedent=10.0).motifs == ("stamp_non_croissant",)
    assert lire(vide(), stamp=10.0, precedent=None).valide


def test_age_0_26_invalide():
    assert lire(vide(), stamp=10.0, maintenant=10.26).motifs == ("trop_vieux",)
    assert lire(vide(), stamp=10.0, maintenant=10.24).valide


def test_temoin_exige_et_absent_invalide():
    assert lire(vide(), params(temoin=TEMOIN)).motifs == ("temoin_absent",)


def test_temoin_present_valide():
    d = vide()
    for i in range(246, 254):      # 177,1° à 182,2° : 8 rayons à 0,08 m
        d[i] = 0.08
    lecture = lire(d, params(masques=[(90.0, 270.0)], temoin=TEMOIN))
    assert lecture.valide
    assert lecture.temoin_points == 8
    assert lecture.points_valides == 0     # le témoin est masqué : jamais un obstacle


def test_temoin_trop_peu_de_points_invalide():
    d = vide()
    for i in range(248, 252):      # 4 points < 5
        d[i] = 0.08
    assert lire(d, params(masques=[(90.0, 270.0)], temoin=TEMOIN)).motifs == ("temoin_absent",)


def test_quatre_motifs_distincts():
    motifs = {lire([math.inf] * 299).motifs, lire(vide(), stamp=10.0, precedent=10.0).motifs,
              lire(vide(), stamp=10.0, maintenant=10.26).motifs, lire(vide(), params(temoin=TEMOIN)).motifs}
    assert len(motifs) == 4


def test_un_balayage_invalide_porte_quand_meme_son_obstacle():
    d = [math.inf] * 299
    d[0] = 0.56
    lecture = lire(d)
    assert not lecture.valide
    assert lecture.d_min_m == pytest.approx(0.59, abs=1e-9)


@pytest.mark.parametrize("angle, debut, fin, attendu", [
    (180.0, 90.0, 270.0, True),
    (0.0, 90.0, 270.0, False),
    (-90.0, 90.0, 270.0, True),     # −90 ≡ 270, borne comprise
    (-150.0, 100.0, -100.0, True),  # [100 ; −100] traverse ±180° : l'arrière
    (0.0, 100.0, -100.0, False),
    (0.0, 350.0, 10.0, True),       # traverse 0
    (5.0, -10.0, 10.0, True),
    (180.0, 270.0, 90.0, False),    # [270 ; 90] = l'avant, l'ordre compte
    (45.0, 0.0, 360.0, True),       # tour complet
    (45.0, 30.0, 30.0, False),
    (30.0, 30.0, 30.0, True),
])
def test_convention_des_masques(angle, debut, fin, attendu):
    assert dans_arc(angle, debut, fin) is attendu
