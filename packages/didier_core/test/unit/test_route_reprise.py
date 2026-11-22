"""Reprise de route après un « aller voir » (A0-4, décision du 22/11, CONV D5) : Didier rejoint
D'ABORD le point du chemin le plus proche (projection sur le segment courant), PUIS continue.

Vécu (fumées 2026-11-21-2149 et 2026-11-22-0123) : garé devant la table basse, Didier repartait en
diagonale vers le waypoint (20 ; 0). Il frôlait le coin de la table et le corps sûr l'arrêtait en
ARRET (0,6 m) : x gagne 0,00 m, D5 rouge.

Le cas de la table basse est rejoué ici HORS sim, avec le VRAI itinéraire chantiers, la VRAIE
caisse du corps sûr de la sim et la table du monde chantiers. Didier est intégré en unicycle à
10 Hz, au tick de route_driver. Valeurs GRAVÉES.

Mutations (doivent rougir) :
  - point de reprise jamais posé (ancienne diagonale)   -> test_reprise_table_*, test_rejoin_pose_*
  - point de reprise ignoré par tick (vise le waypoint)  -> test_reprise_table_*
  - point de reprise jamais levé (Didier y tourne en rond) -> test_reprise_table_nominale (x final)
  - projection remplacée par le waypoint de fin           -> test_rejoin_pose_la_projection
"""
import math
import pathlib
import re

import pytest
import yaml

from didier_corps_sur.geometrie import distance_caisse
from didier_corps_sur.reglages import charger_reglages
from didier_rehearsal.contracts import GOTO_MARGE_M
from didier_rehearsal.director import garde_corps_sur_m, standoff_pour
from didier_rehearsal.route import RouteConfig, RouteFollower, load_route, nearest_on_route

DEPOT = pathlib.Path(__file__).resolve().parents[4]
REGLAGES = charger_reglages(str(DEPOT / "machines" / "sim" / "robot" / "corps_sur.yaml"), "43")
ROUTE = load_route(yaml.safe_load((DEPOT / "packages" / "didier_rehearsal" / "config" / "chantiers.yaml")
                                  .read_text(encoding="utf-8")))
# Plateau de table_basse dans worlds/chantiers.sdf : modèle en (17,8 ; 1,4), lien décalé de
# (0 ; 0,7), boîte 1,2 × 0,6 (vérifié ci-dessous contre le fichier).
TABLE_CENTRE = (17.8, 2.1)
TABLE_DEMI = (0.6, 0.3)
EMPRISE_TABLE = 0.7                     # orbite 1,7 − 1,0 (test_director_goto)
DEPART_B = (9.5, 0.0)                   # Didier sur la route quand part « va voir la table basse »


def test_la_table_est_celle_du_monde():
    sdf = (DEPOT / "packages" / "didier_sim" / "worlds" / "chantiers.sdf").read_text(encoding="utf-8")
    bloc = sdf[sdf.index('name="table_basse"'):]
    assert re.search(r"<pose>17\.8 1\.4 0 0 0 0</pose>", bloc[:400])
    assert "<pose>0 0.7 0.3 0 0 0</pose>" in bloc[:800]
    assert "<box><size>1.2 0.6 0.04</size></box>" in bloc[:1200]


def _contour_table(n=60):
    (cx, cy), (hx, hy) = TABLE_CENTRE, TABLE_DEMI
    pts = []
    for i in range(n + 1):
        a, b = -hx + 2 * hx * i / n, -hy + 2 * hy * i / n
        pts += [(cx + a, cy - hy), (cx + a, cy + hy), (cx - hx, cy + b), (cx + hx, cy + b)]
    return pts


CONTOUR = _contour_table()


def _caisse_table(x, y, lacet):
    """Plus petite distance caisse du corps sûr ↔ plateau, ce que mesure le corps sûr (2D)."""
    c, s = math.cos(lacet), math.sin(lacet)
    return min(distance_caisse(REGLAGES.caisse, c * (px - x) + s * (py - y), -s * (px - x) + c * (py - y))
               for px, py in CONTOUR)


def _centre_table(x, y):
    (cx, cy), (hx, hy) = TABLE_CENTRE, TABLE_DEMI
    return math.hypot(max(abs(x - cx) - hx, 0.0), max(abs(y - cy) - hy, 0.0))


def _reprise(plus_pres_m=0.0):
    """Garé par aller_voir (standoff de la régie, moins `plus_pres_m` de tolérance d'arrivée), face à
    la table ; puis rejoin() et la route à pleine vitesse jusqu'après la table.
    -> (centre↔table au garage, min centre↔table, min caisse↔table, x final)."""
    st = standoff_pour(EMPRISE_TABLE, garde_corps_sur_m(REGLAGES)) - plus_pres_m
    ux, uy = TABLE_CENTRE[0] - DEPART_B[0], TABLE_CENTRE[1] - DEPART_B[1]
    norme = math.hypot(ux, uy)
    ux, uy = ux / norme, uy / norme
    x, y, lacet = TABLE_CENTRE[0] - st * ux, TABLE_CENTRE[1] - st * uy, math.atan2(uy, ux)
    f = RouteFollower(ROUTE, RouteConfig(), enabled=True, speed=1.0)
    t = 0
    f.update_pose(x, y, lacet, t)
    f.rejoin()
    garage = _centre_table(x, y)
    min_centre, min_caisse = garage, _caisse_table(x, y, lacet)
    for _ in range(900):
        t += 100
        f.update_pose(x, y, lacet, t)
        o = f.tick(t)
        lacet += o.ang * 0.1
        x += o.lin * 0.1 * math.cos(lacet)
        y += o.lin * 0.1 * math.sin(lacet)
        min_centre = min(min_centre, _centre_table(x, y))
        min_caisse = min(min_caisse, _caisse_table(x, y, lacet))
        if x > 21.0:
            break
    return garage, min_centre, min_caisse, x


def test_reprise_table_nominale_reste_a_garde_plus_marge():
    garage, min_centre, min_caisse, x_fin = _reprise()
    garde = garde_corps_sur_m(REGLAGES)
    assert round(garde + GOTO_MARGE_M, 6) == 1.4
    assert garage >= garde + GOTO_MARGE_M
    # La reprise ne ramène jamais Didier à moins de garde + marge de la table (ancienne diagonale :
    # 0,63 m), sa caisse ne frôle jamais la bande ARRET (ancienne : 0,23 m), et la route continue.
    assert min_centre >= garde + GOTO_MARGE_M, min_centre
    assert min_caisse >= REGLAGES.zones.marge_arret_m + 0.2, min_caisse
    assert x_fin > 21.0


def test_reprise_table_garee_au_plus_pres_de_la_tolerance():
    """Arrivée 0,3 m plus près (arrive_tol_m de goto.py) : la reprise ne s'en rapproche pas de plus de
    5 cm et la caisse reste HORS de la bande ARRET (ancienne diagonale : 0,10 m)."""
    garage, min_centre, min_caisse, x_fin = _reprise(plus_pres_m=0.3)
    assert min_centre >= garage - 0.05, (garage, min_centre)
    assert min_caisse > REGLAGES.zones.marge_arret_m, min_caisse
    assert x_fin > 21.0


def test_rejoin_pose_la_projection_sur_le_segment_courant():
    f = RouteFollower(ROUTE, RouteConfig(), enabled=True)
    f.update_pose(15.8, 1.6, 0.2, 0)
    f.rejoin()
    assert f.rejoin_point == pytest.approx((15.8, 0.0))
    assert ROUTE.waypoints[f.waypoint_index] == pytest.approx((20.0, 0.0))
    assert nearest_on_route(ROUTE.waypoints, 15.8, 1.6) == (f.waypoint_index, pytest.approx((15.8, 0.0)))


def test_rejoin_deja_sur_le_chemin_ne_pose_rien_et_restart_le_leve():
    f = RouteFollower(ROUTE, RouteConfig(), enabled=True)
    f.update_pose(15.8, 0.3, 0.0, 0)          # 0,3 m < arrive_radius_m (0,5)
    f.rejoin()
    assert f.rejoin_point is None
    f.update_pose(15.8, 1.6, 0.0, 0)
    f.rejoin()
    assert f.rejoin_point is not None
    f.restart()
    assert f.rejoin_point is None


def test_le_point_de_reprise_est_vise_puis_leve_sur_le_chemin():
    f = RouteFollower(ROUTE, RouteConfig(), enabled=True, speed=1.0)
    f.update_pose(15.8, 1.6, -math.pi / 2, 0)  # face au point de reprise (plein sud)
    f.rejoin()
    o = f.tick(100)
    assert abs(o.ang) < 1e-9                   # cap juste : vers (15,8 ; 0), pas vers (20 ; 0)
    f.update_pose(15.8, 0.4, -math.pi / 2, 200)
    f.tick(200)
    assert f.rejoin_point is None
