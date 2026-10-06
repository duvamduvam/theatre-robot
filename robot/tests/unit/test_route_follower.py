"""Cheminement de Didier dans la rue simulée (robot_rehearsal.route) — logique
PURE, valeurs GRAVÉES à la main (règle du 14/09 : un test qui recalcule
l'attendu avec la fonction testée ne teste rien).

Passe de mutation faite le 2026-10-07 (chaque ligne doit rougir) :
  - retirer `min(..., ABS_MAX_LIN)` au constructeur -> test_caps_absolus
  - inverser le signe de `err` -> test_tourne_vers_le_point
  - retirer le zéro franc de set_enabled(False) -> test_desactivation_zero_franc
  - retirer la condition odom_stale -> test_odometrie_perimee
  - retirer l'hystérésis (POI_EXIT_FACTOR -> 1.0) -> test_poi_hysteresis
  - retirer le critère « dépassé le long du segment » -> test_reaccroche_apres_poussee_jamais_en_arriere
"""
import math

import pytest

from robot_rehearsal.contracts import ABS_MAX_ANG, ABS_MAX_LIN
from robot_rehearsal.route import (PoiWatcher, Route, RouteConfig, RouteError, RouteFollower,
                                   load_route, Poi, wrap_angle, yaw_from_quaternion)

DROITE = Route("droite", ((0.0, 0.0), (10.0, 0.0)), ())


def _follower(route=DROITE, speed=1.0, **cfg):
    f = RouteFollower(route, RouteConfig(**cfg), enabled=True, speed=speed)
    return f


# --- validation ---------------------------------------------------------------

def test_load_route_valide():
    r = load_route({"name": "x", "waypoints": [[0, 0], [1, 2.5]],
                    "pois": [{"name": "banc", "x": 1, "y": 2, "radius": 0.5}]})
    assert r.waypoints == ((0.0, 0.0), (1.0, 2.5))
    assert r.pois == (Poi("banc", 1.0, 2.0, 0.5),)


@pytest.mark.parametrize("data, fragment", [
    ({"waypoints": [[0, 0], [1, 1]]}, "name"),
    ({"name": "x", "waypoints": [[0, 0]]}, "au moins 2"),
    ({"name": "x", "waypoints": [[0, 0], [1]]}, "waypoints[1]"),
    ({"name": "x", "waypoints": [[0, 0], ["a", 1]]}, "waypoints[1].x"),
    ({"name": "x", "waypoints": [[0, 0], [1, 1]], "pois": [{"name": "p", "x": 0, "y": 0, "radius": 0}]}, "radius"),
    ({"name": "x", "waypoints": [[0, 0], [1, 1]],
      "pois": [{"name": "p", "x": 0, "y": 0, "radius": 1}, {"name": "p", "x": 1, "y": 0, "radius": 1}]}, "double"),
    ({"name": "x", "waypoints": [[0, 0], [1, 1]], "pois": [{"name": "p", "x": float("nan"), "y": 0, "radius": 1}]}, "fini"),
])
def test_load_route_refuse_explicitement(data, fragment):
    with pytest.raises(RouteError) as exc:
        load_route(data)
    assert fragment in str(exc.value)


# --- géométrie ----------------------------------------------------------------

def test_yaw_from_quaternion():
    assert yaw_from_quaternion(0.0, 0.0, 0.0, 1.0) == 0.0
    assert round(yaw_from_quaternion(0.0, 0.0, 0.7071068, 0.7071068), 6) == 1.570796
    assert round(yaw_from_quaternion(0.0, 0.0, 1.0, 0.0), 6) == 3.141593


def test_wrap_angle():
    assert round(wrap_angle(3.0 + 2 * math.pi), 6) == 3.0
    assert round(wrap_angle(-3.5), 6) == round(2 * math.pi - 3.5, 6)


# --- suiveur ------------------------------------------------------------------

def test_demarre_desactive_et_zero():
    f = RouteFollower(DROITE)
    assert f.enabled is False
    out = f.tick(0)
    assert (out.lin, out.ang, out.finished, out.reason) == (0.0, 0.0, False, "disabled")


def test_sans_pose_zero():
    f = _follower()
    assert f.tick(0).reason == "no_pose"


def test_tout_droit_monte_en_slew():
    f = _follower()
    f.update_pose(0.0, 0.0, 0.0, 0)
    lins = [f.tick(t).lin for t in range(10, 100, 10)]
    # slew 0,05 par tick jusqu'au plafond max_lin 0,4 (facteur 1)
    assert [round(v, 6) for v in lins] == [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.4]
    assert f.tick(100).ang == 0.0
    assert f.waypoint_index == 1  # (0,0) atteint d'emblée -> on vise (10,0)


def test_tourne_vers_le_point():
    f = _follower()
    f.update_pose(0.0, 0.0, math.pi / 2, 0)   # regarde +y, le point est en +x
    out = f.tick(10)
    # err = -pi/2 -> ang cible = clamp(1.5 * -1.5708, ±0.8) = -0.8, slew 0.15
    assert round(out.ang, 6) == -0.15
    # erreur de cap > heading_slow_rad (0,8) -> on ne roule pas
    assert out.lin == 0.0


def test_wrap_du_cap():
    gauche = Route("g", ((0.0, 0.0), (-10.0, 0.0)), ())
    f = _follower(gauche)
    f.update_pose(0.0, 0.0, 3.0, 0)           # cible = pi, err = +0,14159
    assert round(f.tick(10).ang, 6) == 0.15    # cible 0,2124, slew 0,15
    g = _follower(gauche)
    g.update_pose(0.0, 0.0, -3.0, 0)          # err brut 6,14 -> wrap -0,14159
    assert round(g.tick(10).ang, 6) == -0.15


def test_facteur_vitesse():
    f = _follower(speed=0.5)
    f.update_pose(0.0, 0.0, 0.0, 0)
    lins = [f.tick(t).lin for t in range(10, 60, 10)]
    assert [round(v, 6) for v in lins] == [0.05, 0.1, 0.15, 0.2, 0.2]


def test_set_speed_borne_jamais_refuse():
    f = _follower()
    f.set_speed(1.7); assert f.speed == 1.0
    f.set_speed(-1); assert f.speed == 0.0
    f.set_speed("0.25"); assert f.speed == 0.25
    f.set_speed("n'importe quoi"); assert f.speed == 0.25   # ignoré, inchangé
    f.set_speed(float("nan")); assert f.speed == 0.25


def test_arrivee_zero_et_finished():
    f = _follower()
    f.update_pose(9.6, 0.0, 0.0, 0)   # à 0,4 m < arrive_radius 0,5 du dernier point
    out = f.tick(10)
    assert (out.lin, out.ang, out.finished, out.reason) == (0.0, 0.0, True, "finished")
    f.restart()
    assert f.waypoint_index == 0


def test_reaccroche_apres_poussee_jamais_en_arriere():
    trois = Route("t", ((0.0, 0.0), (10.0, 0.0), (20.0, 0.0)), ())
    f = _follower(trois)
    f.update_pose(12.0, 0.0, 0.0, 0)   # poussé 2 m après le 2e point (télécommande)
    out = f.tick(10)
    assert f.waypoint_index == 2       # (0,0) et (10,0) dépassés le long du segment
    assert (round(out.lin, 6), out.ang, out.reason) == (0.05, 0.0, "ok")   # tout droit vers (20,0)
    g = _follower(trois)
    g.update_pose(12.0, 3.0, 0.0, 0)   # poussé en avant ET sur le côté : on vise (20,0), pas (10,0)
    g.tick(10)
    assert g.waypoint_index == 2


def test_odometrie_perimee():
    f = _follower()
    f.update_pose(0.0, 0.0, 0.0, 0)
    assert f.tick(600).reason == "ok"
    out = f.tick(601)
    assert (out.lin, out.ang, out.reason) == (0.0, 0.0, "odom_stale")


def test_desactivation_zero_franc():
    f = _follower()
    f.update_pose(0.0, 0.0, 0.0, 0)
    for t in range(10, 90, 10):
        f.tick(t)
    assert round(f.tick(90).lin, 6) == 0.4
    f.set_enabled(False)
    out = f.tick(100)
    assert (out.lin, out.ang, out.reason) == (0.0, 0.0, "disabled")   # pas 0,35 : FRANC
    f.set_enabled(True)
    assert round(f.tick(110).lin, 6) == 0.05                           # repart du zéro


def test_caps_absolus():
    f = RouteFollower(DROITE, RouteConfig(max_lin=5.0, max_ang=3.0))
    assert f.config.max_lin == ABS_MAX_LIN == 0.5
    assert f.config.max_ang == ABS_MAX_ANG == 1.0


# --- points d'intérêt ---------------------------------------------------------

def test_poi_hysteresis():
    w = PoiWatcher((Poi("lampadaire", 10.0, 0.0, 2.0),))
    assert w.update(0.0, 0.0) == []
    ev = w.update(8.5, 0.0)
    assert [(e.poi, e.event, round(e.distance, 2)) for e in ev] == [("lampadaire", "enter", 1.5)]
    assert w.update(11.5, 0.0) == []           # dedans, rien
    assert w.update(12.5, 0.0) == []           # 2,5 < 2,6 : hystérésis, toujours dedans
    assert w.inside() == ("lampadaire",)
    ev = w.update(12.7, 0.0)
    assert [(e.poi, e.event, round(e.distance, 2)) for e in ev] == [("lampadaire", "exit", 2.7)]
    assert w.inside() == ()


def test_poi_ordre_deterministe():
    w = PoiWatcher((Poi("a", 0.0, 0.0, 5.0), Poi("b", 1.0, 0.0, 5.0)))
    assert [e.poi for e in w.update(0.5, 0.0)] == ["a", "b"]
