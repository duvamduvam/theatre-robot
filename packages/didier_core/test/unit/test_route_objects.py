"""Lot M1 « aller voir » côté itinéraire (didier_rehearsal.route) : objets
nommés (normalize_name, desc, alias) et REPRISE vers le waypoint le plus
proche devant — logique PURE, valeurs GRAVÉES ; l'itinéraire chantiers est lu
dans le VRAI fichier.

Mutations du lot M1 (doivent rougir) :
  - rejoin() sans effet -> test_rejoin_apres_demi_tour_revient_en_arriere
  - nearest_ahead_index renvoie le segment au lieu de sa fin -> test_nearest_ahead_index
  - retirer le refus d'un alias partagé -> test_alias_partage_par_deux_poi_refuse
  - retirer le zéro franc à facteur 0 (revue M1) -> test_facteur_zero_aucun_pivot_zero_franc
"""
import pathlib

import pytest
import yaml

from didier_rehearsal.route import (Poi, Route, RouteConfig, RouteError, RouteFollower, load_route,
                                   nearest_ahead_index, normalize_name)

ROOT = pathlib.Path(__file__).resolve().parents[4] / "legacy" / "dadou_robot_ros"
PACKAGES = ROOT.parents[1] / "packages"          # packages/ du mono-dépôt (L1e-1)
CHANTIERS = PACKAGES / "didier_rehearsal" / "config" / "chantiers.yaml"
LIGNE = ((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))


@pytest.mark.parametrize("texte, cle", [
    ("Les Anneaux !", "anneaux"),
    ("table_basse", "table basse"),
    ("l'eau", "eau"),
    ("L’Éléphant", "elephant"),
    ("de la flaque", "flaque"),
    ("anneaux de Buren", "anneaux de buren"),     # article AU MILIEU conservé
    ("  la   grue  JAUNE ", "grue jaune"),
    ("le", ""),
    (None, ""),
    (3, ""),
])
def test_normalize_name(texte, cle):
    assert normalize_name(texte) == cle


def _route(pois):
    return {"name": "x", "waypoints": [[0, 0], [1, 0]], "pois": pois}


def test_desc_et_alias_optionnels():
    r = load_route(_route([{"name": "banc", "x": 1, "y": 2, "radius": 1}]))
    assert r.pois == (Poi("banc", 1.0, 2.0, 1.0),)
    assert (r.pois[0].desc, r.pois[0].alias, r.pois[0].shown_desc) == ("", (), "banc")   # absent -> nom
    r = load_route(_route([{"name": "anneaux", "x": 1, "y": 2, "radius": 1, "desc": "bagues géantes",
                            "alias": ["bagues", "cercles"]}]))
    assert (r.pois[0].shown_desc, r.pois[0].alias) == ("bagues géantes", ("bagues", "cercles"))


@pytest.mark.parametrize("poi, fragment", [
    ({"desc": "un deux trois quatre cinq six sept"}, "6 mots au plus"),
    ({"desc": 3}, "desc"),
    ({"alias": "bagues"}, "alias"),
    ({"alias": ["bagues", ""]}, "alias[1]"),
    ({"alias": ["les"]}, "alias[0]"),
])
def test_desc_et_alias_refuses(poi, fragment):
    with pytest.raises(RouteError) as exc:
        load_route(_route([dict({"name": "a", "x": 0, "y": 0, "radius": 1}, **poi)]))
    assert fragment in str(exc.value)


def test_alias_partage_par_deux_poi_refuse():
    with pytest.raises(RouteError) as exc:
        load_route(_route([{"name": "nefs", "x": 0, "y": 0, "radius": 1, "alias": ["Hangar"]},
                           {"name": "hangar_bananes", "x": 5, "y": 0, "radius": 1, "alias": ["le hangar"]}]))
    assert "désigne déjà « nefs »" in str(exc.value)
    with pytest.raises(RouteError):   # alias = nom d'un AUTRE poi
        load_route(_route([{"name": "banc", "x": 0, "y": 0, "radius": 1},
                           {"name": "flaque", "x": 5, "y": 0, "radius": 1, "alias": ["le banc"]}]))


def test_nearest_ahead_index():
    assert nearest_ahead_index(LIGNE, -3.0, 0.5) == 0     # avant le départ
    assert nearest_ahead_index(LIGNE, 0.0, 0.0) == 0
    assert nearest_ahead_index(LIGNE, 4.0, 2.0) == 1
    assert nearest_ahead_index(LIGNE, 12.0, 1.5) == 2
    assert nearest_ahead_index(LIGNE, 23.5, -1.5) == 3
    assert nearest_ahead_index(LIGNE, 35.0, 0.0) == 3     # au-delà de la fin : le dernier


def _suiveur(x, y):
    f = RouteFollower(Route("l", LIGNE, ()), RouteConfig(), enabled=True)
    f.update_pose(x, y, 0.0, 0)
    return f


def test_rejoin_apres_demi_tour_revient_en_arriere():
    f = _suiveur(25.0, 0.0)
    f.tick(10)
    assert f.waypoint_index == 3
    f.update_pose(12.0, 1.5, 1.6, 20)     # demi-tour vers un objet DÉPASSÉ, face à lui
    f.rejoin()
    assert f.waypoint_index == 2          # pas 3 (sauterait 20 -> 30 à travers champ)


def test_rejoin_apres_objet_devant_saute_l_ancien_index():
    f = _suiveur(5.0, 0.0)
    f.tick(10)
    assert f.waypoint_index == 1
    f.update_pose(23.5, 1.5, 1.6, 20)
    f.rejoin()
    assert f.waypoint_index == 3          # l'ancien index 1 est DERRIÈRE


def test_rejoin_sans_pose_index_inchange():
    f = RouteFollower(Route("l", LIGNE, ()))
    f.rejoin()
    assert f.waypoint_index == 0


def test_chantiers_trente_desc_et_alias():
    route = load_route(yaml.safe_load(CHANTIERS.read_text(encoding="utf-8")))
    assert len(route.pois) == 30
    for p in route.pois:
        assert p.desc and len(p.desc.split()) <= 6, p.name
        assert p.alias, p.name
    anneaux = next(p for p in route.pois if p.name == "anneaux")
    assert (anneaux.desc, anneaux.alias) == ("bagues géantes",
                                             ("anneaux", "bagues", "anneaux de buren", "cercles"))


def test_facteur_zero_aucun_pivot_zero_franc():
    """Revue M1 : après rejoin(), Didier de travers pivotait à 0,8 rad/s fader à 0."""
    f = RouteFollower(Route("l", LIGNE, ()), RouteConfig(), enabled=True, speed=0.0)
    f.update_pose(12.0, 1.5, 1.6, 0)
    f.rejoin()
    out = f.tick(10)
    assert (out.lin, out.ang, out.finished, out.reason) == (0.0, 0.0, False, "held")
    g = _suiveur(0.0, 0.0)
    for t in range(10, 90, 10):
        g.tick(t)
    assert round(g.tick(90).lin, 6) == 0.4
    g.set_speed(0.0)
    out = g.tick(100)
    assert (out.lin, out.ang, out.reason) == (0.0, 0.0, "held")      # FRANC, pas 0,35
    g.set_speed(1.0)
    assert round(g.tick(110).lin, 6) == 0.05
