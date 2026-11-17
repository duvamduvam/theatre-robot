"""Géométrie du banc de pointage (tools/banc_pointage.py) — valeurs GRAVÉES.

POURQUOI tester un outil d'atelier : sa projection au sol est la base du futur
module de la voie (b) (étude docs/etudes/etude-objets-vus-et-carte.md, lot O2),
et une erreur de géométrie y est silencieuse — le 17/11, une caméra cabrée de
1,6° non prise en compte faussait de 5 m les distances à 20 m sans rien casser.
Les attendus sont calculés À LA MAIN (focale = 320 / tan(1,047 / 2) = 554,38 px ;
caméra à 1,06 m, 15,5 cm en avant de l'origine du modèle), jamais avec la
fonction testée.
"""
import importlib.util
import math
import os

import pytest

_OUTIL = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "banc_pointage.py")
_spec = importlib.util.spec_from_file_location("banc_pointage", _OUTIL)
banc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(banc)


def test_focale_et_camera_nominale():
    assert banc.FOCAL_PX == pytest.approx(554.38, abs=0.01)
    cam = banc.nominal_camera((10.0, 2.0, 0.0))
    assert cam == pytest.approx((10.155, 2.0, 1.06, 0.0, 0.0, 0.0))


def test_pixel_sous_l_horizon_touche_le_sol_a_5_m():
    # 1,06 × 554,38 / 5 = 117,53 lignes sous le centre (240) -> v = 357,5.
    cam = banc.nominal_camera((0.0, 0.0, 0.0))
    x, y = banc.pixel_to_ground(cam, 320.0, 357.5)
    assert (x, y) == pytest.approx((0.155 + 5.0, 0.0), abs=0.005)


def test_colonne_a_gauche_donne_un_azimut_positif_et_un_point_a_gauche():
    # 100 px à gauche du centre : atan(100 / 554,38) = 10,23° ; à 5 m devant : 0,902 m à gauche.
    cam = banc.nominal_camera((0.0, 0.0, 0.0))
    assert banc.pixel_bearing_deg(cam, 220.0, 357.5) == pytest.approx(10.23, abs=0.01)
    assert banc.pixel_to_ground(cam, 220.0, 357.5) == pytest.approx((5.155, 0.902), abs=0.005)


def test_le_cap_tourne_le_point_dans_le_monde():
    # Cap +90° (vers +y) : « 5 m devant » devient 5 m en +y, la caméra est à y = 0,155.
    cam = banc.nominal_camera((3.0, 1.0, math.pi / 2))
    assert banc.pixel_to_ground(cam, 320.0, 357.5) == pytest.approx((3.0, 1.0 + 0.155 + 5.0), abs=0.005)


def test_au_dessus_ou_trop_pres_de_l_horizon_pas_de_distance():
    cam = banc.nominal_camera((0.0, 0.0, 0.0))
    assert banc.pixel_to_ground(cam, 320.0, 200.0) is None      # au-dessus
    assert banc.pixel_to_ground(cam, 320.0, 240.0) is None      # sur l'horizon
    assert banc.pixel_to_ground(cam, 320.0, 242.0) is None      # 0,21° : sous la marge de 0,3°
    assert banc.pixel_to_ground(cam, 320.0, 244.0) is not None  # 0,41°


def test_une_camera_cabree_de_1_6_degre_voit_le_meme_sol_plus_bas_dans_l_image():
    # La panne du 17/11. Point du sol à 20 m devant la caméra, vu par une caméra
    # cabrée de 1,6° (tangage −1,6°, REP 103) : il descend de 554,38 × tan(1,6°) ≈
    # 15,5 lignes. Projeté en IGNORANT l'inclinaison, il tombe à ≈ 13,1 m au lieu de 20.
    base = (0.0, 0.0, banc.BASE_Z_M, 0.0, math.radians(-1.6), 0.0)
    cabree = banc.camera_from_base(base)
    cible = (cabree[0] + 20.0, 0.0)
    u, v = banc.ground_to_pixel(cabree, cible)
    a_plat = banc.nominal_camera((0.0, 0.0, 0.0))
    assert v - banc.ground_to_pixel(a_plat, cible)[1] == pytest.approx(15.5, abs=0.6)
    assert banc.pixel_to_ground(cabree, u, v) == pytest.approx(cible, abs=0.01)         # bonne pose : exact
    faux = banc.pixel_to_ground(a_plat, u, v)
    assert faux[0] - a_plat[0] == pytest.approx(13.1, abs=0.4)                         # pose ignorée : −7 m


def test_reponse_pied_et_boite_donnent_le_point_au_sol_revendique():
    # [y, x] sur 1000 -> pixels 640×480 ; boîte -> milieu du bord BAS.
    assert banc.answer_pixel("pied", {"point": [500, 250]}) == pytest.approx((160.0, 240.0))
    assert banc.answer_pixel("boite", {"box_2d": [100, 200, 750, 400]}) == pytest.approx((192.0, 360.0))
    # Ordre [x, y] rendu par Qwen malgré la consigne : relu, il donne le même point.
    assert banc.answer_pixel("pied", {"point": [250, 500]}, xy_order=True) == pytest.approx((160.0, 240.0))
    assert banc.answer_pixel("boite", {"box_2d": [200, 100, 400, 750]}, xy_order=True) == pytest.approx((192.0, 360.0))


@pytest.mark.parametrize("valeur", [{}, {"point": [1200, 10]}, {"point": "ici"}, {"box_2d": [1, 2, 3]}])
def test_reponse_illisible_ou_hors_bornes_refusee(valeur):
    assert banc.answer_pixel("pied" if "box_2d" not in valeur else "boite", valeur) is None


def test_reponse_json_entouree_de_clotures():
    assert banc.parse_answer('```json\n{"visible": true, "point": [705, 410]}\n```') == {
        "visible": True, "point": [705, 410]}
    assert banc.parse_answer("je ne sais pas") is None
    assert banc.parse_inventory('[{"nom": "banc en bois", "box_2d": [1, 2, 3, 4]}, {"nom": "x"}]') == [
        ("banc en bois", [1.0, 2.0, 3.0, 4.0])]


def test_la_cle_ne_vient_que_de_l_environnement(monkeypatch, capsys):
    monkeypatch.delenv(banc.KEY_ENV, raising=False)
    assert banc.main(["interroger", "--dir", "/nonexistent"]) == 2
    assert banc.KEY_ENV in capsys.readouterr().out
