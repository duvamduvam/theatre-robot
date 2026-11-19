"""couverture : régions vues / aveugles (§5.2, §6.2), caisse par défaut, lidar en pose A.

VALEURS GRAVÉES obtenues UNE fois par une SECONDE MÉTHODE indépendante (script
jetable hors dépôt, 18/11) : la même grille de 5 cm recomptée en ENTIERS
(millimètres : centres 50 i + 25, bande 0 < d² < 600², régions par comparaisons
entières, masques dépliés en intervalles non bouclants de [0, 360)). Comptes :
avant 416, arrière 428, chaque flanc 204 échantillons.
- masque [90 ; 270] : avant 40/416 (la colonne x = 0,325, derrière le capteur),
  arrière 428/428, flancs 204/204 ;
- masque [170 ; 190] : arrière 100/428, rien ailleurs.
Contrôle continu (aires exactes à la main) au pas de 1 cm :
- [90 ; 270], avant : bande 0,30 < x < 0,33 = 2·(0,4·0,03 + ∫₀^0,03 √(0,36−t²) dt)
  = 0,05998 m² sur 0,48 + 0,18π = 1,04549 m² → 0,05738 ;
- [170 ; 190], arrière : coin de ±10° entre x = −0,57 et −1,17 vus de x = 0,33,
  tan 10°·(1,50² − 0,90²) = 0,25392 m² sur 1,04549 m² → 0,24286.
"""
import json
import math

import pytest

from didier_corps_sur.couverture import calculer_couverture, vue_de
from didier_corps_sur.geometrie import Caisse, PoseLidar

CAISSE = Caisse(0.30, -0.57, 0.40, 0.10, 0.65)
POSE_A = PoseLidar(0.33, 0.0, 0.0)


def resume(couv):
    return {r: (c["aveugles"], c["echantillons"]) for r, c in couv.items()}


def test_aucun_masque_quatre_vues():
    couv = calculer_couverture(CAISSE, POSE_A, [])
    assert resume(couv) == {"avant": (0, 416), "arriere": (0, 428), "flanc_g": (0, 204), "flanc_d": (0, 204)}
    assert vue_de(couv) == {"avant": True, "arriere": True, "flanc_g": True, "flanc_d": True}


def test_masque_arriere_avant_vue_seule():
    couv = calculer_couverture(CAISSE, POSE_A, [[90.0, 270.0]])
    assert resume(couv) == {"avant": (40, 416), "arriere": (428, 428),
                            "flanc_g": (204, 204), "flanc_d": (204, 204)}
    assert couv["avant"]["part_aveugle"] == pytest.approx(0.0961538, abs=1e-6)  # sous 0,10 de peu
    assert vue_de(couv) == {"avant": True, "arriere": False, "flanc_g": False, "flanc_d": False}


def test_masque_170_190_arriere_aveugle():
    couv = calculer_couverture(CAISSE, POSE_A, [[170.0, 190.0]])
    assert resume(couv) == {"avant": (0, 416), "arriere": (100, 428),
                            "flanc_g": (0, 204), "flanc_d": (0, 204)}
    assert couv["arriere"]["part_aveugle"] == pytest.approx(0.2336449, abs=1e-6)
    assert vue_de(couv) == {"avant": True, "arriere": False, "flanc_g": True, "flanc_d": True}


def test_masque_dans_laser_frame_suit_le_lacet():
    # Lidar retourné (lacet π) : son [−10 ; 10] regarde l'arrière de Didier, comme [170 ; 190] à lacet 0.
    couv = calculer_couverture(CAISSE, PoseLidar(0.33, 0.0, math.pi), [[-10.0, 10.0]])
    assert resume(couv)["arriere"] == (100, 428)
    assert resume(couv)["avant"] == (0, 416)


def test_signe_du_lacet_dans_la_couverture():
    # Lidar tourné de +90° (trigo) : son [80 ; 100] (droit devant LUI) regarde l'arrière
    # de Didier (80 + 90 … 100 + 90 = 170 … 190 dans base_link). Un signe faux le
    # ferait regarder l'avant. Seconde méthode : identique à [170 ; 190] à lacet 0.
    couv = calculer_couverture(CAISSE, PoseLidar(0.33, 0.0, math.pi / 2), [[80.0, 100.0]])
    assert resume(couv) == {"avant": (0, 416), "arriere": (100, 428),
                            "flanc_g": (0, 204), "flanc_d": (0, 204)}


def test_masque_dissymetrique_separe_les_flancs():
    # [60 ; 120] (à gauche du lidar) n'aveugle que le flanc gauche et des coins avant.
    couv = calculer_couverture(CAISSE, POSE_A, [[60.0, 120.0]])
    assert couv["flanc_d"]["aveugles"] == 0
    assert couv["flanc_g"]["aveugles"] > 0


@pytest.mark.parametrize("masque, region, continu", [
    ([90.0, 270.0], "avant", 0.05738),
    ([170.0, 190.0], "arriere", 0.24286),
])
def test_pas_de_1_cm_proche_de_l_aire_exacte(masque, region, continu):
    couv = calculer_couverture(CAISSE, POSE_A, [masque], pas_m=0.01)
    assert couv[region]["part_aveugle"] == pytest.approx(continu, abs=0.002)


def test_seuil_de_part_aveugle():
    # 40/416 = 0,096 : vue à 0,10, non vue à 0,09.
    assert calculer_couverture(CAISSE, POSE_A, [[90.0, 270.0]], part_aveugle_max=0.09)["avant"]["vue"] is False


def test_serialisable_en_json():
    couv = calculer_couverture(CAISSE, POSE_A, [[90.0, 270.0]])
    assert list(json.loads(json.dumps(couv))) == ["avant", "arriere", "flanc_g", "flanc_d"]


def test_pas_nul_refuse():
    with pytest.raises(ValueError):
        calculer_couverture(CAISSE, POSE_A, [], pas_m=0.0)
