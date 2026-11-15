"""Distances du chat (15/11 21:29) — scène RÉELLE de l'itinéraire Chantiers
(ancres de config/chantiers.yaml), Didier en (14, 0), cap +x. Valeurs GRAVÉES.

Séance : le LLM a dit « le banc est là, bien en vue » et demandé le tour du
banc, accepté à 22 m ; Didier a roulé 22 m le long de la route.

Mutations (doivent rougir) :
  - _trop_loin qui rend toujours False -> test_tour_du_banc_a_22_m_refuse_sans_partir
  - côté gauche/droite inversé -> test_objets_proches_scene_x14
"""
from conftest import fabriquer

from didier_jeu.proximite import cote

from test_selecteur import jouer, journal, moves

CHANTIERS = [("nefs", 4.0, 2.0), ("elephant", 8.6, -1.4), ("carrousel", 13.2, -2.0),
             ("table_basse", 17.8, 1.4), ("poster_bizarre", 22.4, -1.4), ("poubelle_tri", 27.0, 1.4),
             ("pigeon", 31.6, -1.4), ("banc", 36.2, 1.4)]


def scene_x14(s, t):
    s.sur_route_state("on", t)
    s.sur_objets([{"name": n, "desc": n, "x": x, "y": y} for n, x, y in CHANTIERS])
    s.sur_pose(14.0, 0.0, 0.0)


def reponses(out):
    return [(o[0], o[2]) for o in out if o[1] == "chat_move_reply"]


def test_objets_proches_scene_x14():
    sel = fabriquer(pools={})
    scene_x14(sel, 0.0)
    assert sel.objets_proches() == [
        {"name": "carrousel", "distance_m": 2.2, "cote": "droite"},
        {"name": "table_basse", "distance_m": 4.0, "cote": "devant"},
        {"name": "elephant", "distance_m": 5.6, "cote": "derriere"},
        {"name": "poster_bizarre", "distance_m": 8.5, "cote": "devant"},
        {"name": "nefs", "distance_m": 10.2, "cote": "derriere"},
        {"name": "poubelle_tri", "distance_m": 13.1, "cote": "devant"}]


def test_cotes_bornes_gravees():
    assert [cote(a) for a in (0, 45, 45.1, 135, 135.1, -45, -45.1, -135, -135.1, 180)] == [
        "devant", "devant", "gauche", "gauche", "derriere", "devant", "droite", "droite", "derriere",
        "derriere"]


def test_tour_du_banc_a_22_m_refuse_sans_partir():
    tour = {"cmd": "tour_de", "objet": "le banc", "sens": "gauche"}
    out = jouer(fabriquer(pools={}), 0.0, 5.0, [(0.0, scene_x14), (1.0, lambda s, t: s.sur_chat_move_bouche(tour, t))])
    assert moves(out) == []
    assert reponses(out) == [(1.0, {"demande": tour, "effect": "dropped", "reason": "trop_loin", "source": "jeu",
                                    "distance_m": 22.2})]
    assert [p["pourquoi"] for _, p in journal(out, "refus")] == [
        "il voulait faire le tour de « le banc », mais non : « banc » est à 22,2 m (plus de 10 m)"]


def test_aller_voir_table_basse_proche_part():
    av = {"cmd": "aller_voir", "objet": "table_basse"}
    # (jusqu'à 4 s : sans régisseur dans ce banc, le « no_reply » tomberait à 4,4 s)
    out = jouer(fabriquer(pools={}), 0.0, 4.0, [(0.0, scene_x14), (1.0, lambda s, t: s.sur_chat_move_bouche(av, t))])
    assert moves(out) == [(1.3, av)]
    assert reponses(out) == []


def test_console_va_la_jamais_bornee_a_10_m():
    out = jouer(fabriquer(pools={}), 0.0, 5.0, [(0.0, scene_x14),
                                                (1.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "banc"}, t))])
    assert moves(out) == [(1.3, {"cmd": "aller_voir", "objet": "banc"})]
