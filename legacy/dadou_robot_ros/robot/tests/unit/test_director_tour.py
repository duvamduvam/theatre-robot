"""Régisseur × « faire le tour de X » (lot M3, spec-aller-voir.md §8.2-§8.3) —
arbitrage PUR puis node avec rclpy SIMULÉ (banc RÉUTILISÉ de
test_director_node.py). Valeurs GRAVÉES.

Mutations du lot M3 (doivent rougir) :
  - refus no_tour retiré (tour inventé) -> test_refus_dans_l_ordre, test_node_sans_fichier_de_tours_no_tour
  - sens droite = +1 -> test_sens_gauche_droite_et_defaut
  - sens invalide deviné -> test_sens_gauche_droite_et_defaut
  - distance jugée à l'ancre au lieu du centre -> test_trop_loin_juge_au_centre
  - refus route_off_by_david retiré -> test_node_refus_route_off_par_david
  - arrêt vocal non levé -> test_node_tour_leve_l_arret_vocal
  - « stop » sans cancel -> test_node_stop_annule_le_tour
  - cible du tour non transmise (lubie de l'objet tourné non sautée) -> test_node_lubie_de_l_objet_tourne_sautee
"""
import json

import pytest

from robot.tests.unit.test_director_node import (LUBIE, _creer, _echos, _etat_route, _fader, _journal, _poi,
                                                 _publie, _recevoir, _voix, regisseur)  # noqa: F401 (fixture)
from robot.tests.unit.test_director_node_goto import _odom
from didier_rehearsal.director import decide_tour
from didier_rehearsal.route import Tour, load_route

POIS = load_route({"name": "r", "waypoints": [[0, 0], [1, 0]],
                   "pois": [{"name": "poubelle_tri", "x": 27.0, "y": 1.4, "radius": 2.5, "alias": ["poubelles"]},
                            {"name": "flaque", "x": 10.0, "y": 0.0, "radius": 2.5},
                            {"name": "loin", "x": 39.0, "y": 0.0, "radius": 2.5}]}).pois
TOURS = {"poubelle_tri": Tour(27.0, 2.4, 2.1), "loin": Tour(45.0, 0.0, 2.0)}


def _d(intent, pose=(20.0, 0.0), off_by_david=False):
    d = decide_tour(intent, pois=POIS, tours=TOURS, pose=pose, off_by_david=off_by_david)
    return d.effect, d.reason, d.name, None if d.order is None else json.loads(d.order)


# --- arbitrage pur -------------------------------------------------------------------

def test_accepte_ordre_grave():
    assert _d({"cmd": "tour_de", "objet": "les poubelles"}) == (
        "accepted", None, "tour de poubelle_tri",
        {"name": "tour de poubelle_tri", "orbit_x": 27.0, "orbit_y": 2.4, "orbit_r": 2.1, "orbit_dir": 1})


def test_sens_gauche_droite_et_defaut():
    assert _d({"objet": "poubelle_tri", "sens": "gauche"})[3]["orbit_dir"] == 1
    assert _d({"objet": "poubelle_tri", "sens": " Droite "})[3]["orbit_dir"] == -1
    assert _d({"objet": "poubelle_tri"})[3]["orbit_dir"] == 1                      # absent = gauche
    assert _d({"objet": "poubelle_tri", "sens": "haut"})[:2] == ("invalid", "sens")
    assert _d({"objet": "poubelle_tri", "sens": None})[:2] == ("invalid", "sens")  # présent mais vide


def test_refus_dans_l_ordre():
    assert _d({"objet": "lune"}, off_by_david=True)[0] == "unknown"
    assert _d({"objet": "flaque"}, off_by_david=True)[:3] == ("no_tour", None, "tour de flaque")
    assert _d({"objet": "poubelle_tri", "sens": "haut"}, off_by_david=True)[0] == "invalid"
    assert _d({"objet": "poubelle_tri"}, off_by_david=True, pose=None)[0] == "route_off_by_david"
    assert _d({"objet": "poubelle_tri"}, pose=None)[0] == "no_pose"
    assert _d({"objet": 12})[0] == "unknown"                                          # payload LLM hostile


def test_trop_loin_juge_au_centre():
    # Ancre de « loin » à 39 m (sous 40), centre du tour à 45 m : refusé.
    d = decide_tour({"objet": "loin"}, pois=POIS, tours=TOURS, pose=(0.0, 0.0), off_by_david=False)
    assert (d.effect, d.distance) == ("too_far", 45.0)


# --- node --------------------------------------------------------------------------

def _tours_frere(tmp_path, contenu):
    """Fichier frère de l'itinéraire écrit par _creer (route.yaml -> route_tours.yaml)."""
    (tmp_path / "route_tours.yaml").write_text(contenu, encoding="utf-8")


TOUR_BANC = "banc: {x: 5.0, y: 0.5, rayon: 2.0}\n"


def _tour(noeud, intent, t=None):
    if t is not None:
        noeud.horloge.t = t
    _recevoir(noeud, "rehearsal/chat_move", json.dumps({"cmd": "tour_de", **intent}))


def _tours_journal(noeud):
    return [p for t, p in _journal(noeud) if t == "tour_de"]


def _ordres(noeud):
    return [json.loads(m) for m in _publie(noeud, "route_goto")]


def test_node_tour_accepte_hors_seance(regisseur, monkeypatch, tmp_path):
    _tours_frere(tmp_path, TOUR_BANC)
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _etat_route(n, "off", cause="boot")
    _odom(n, 1.0, 0.0)
    _tour(n, {"objet": "le banc", "sens": "droite", "bavard": "x"})
    assert _tours_journal(n) == [{"objet": "le banc", "sens": "droite", "effect": "accepted",
                                  "name": "tour de banc", "distance": 4.03}]       # champs du contrat seuls
    assert _ordres(n) == [{"name": "tour de banc", "orbit_x": 5.0, "orbit_y": 0.5, "orbit_r": 2.0,
                           "orbit_dir": -1}]


def test_node_sans_fichier_de_tours_no_tour(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])         # pas de route_tours.yaml : pas d'erreur
    _odom(n, 1.0, 0.0)
    _tour(n, {"objet": "banc"})
    assert _tours_journal(n) == [{"objet": "banc", "effect": "no_tour", "name": "tour de banc"}]
    assert _ordres(n) == []


def test_node_fichier_de_tours_invalide_refuse_au_demarrage(regisseur, monkeypatch, tmp_path):
    _tours_frere(tmp_path, "inconnu: {x: 0, y: 0, rayon: 2}\n")
    with pytest.raises(RuntimeError) as exc:
        _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    assert "tours invalides" in str(exc.value)


def test_node_refus_route_off_par_david(regisseur, monkeypatch, tmp_path):
    _tours_frere(tmp_path, TOUR_BANC)
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _odom(n, 1.0, 0.0)
    _recevoir(n, "route", "on"); _etat_route(n, "on")
    _recevoir(n, "route", "off")                    # `off` de David VU
    _tour(n, {"objet": "banc"})
    assert [p["effect"] for p in _tours_journal(n)] == ["route_off_by_david"]
    assert _ordres(n) == []


def test_node_tour_leve_l_arret_vocal(regisseur, monkeypatch, tmp_path):
    _tours_frere(tmp_path, TOUR_BANC)
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.6")
    _recevoir(n, "route", "on"); _etat_route(n, "on")
    _odom(n, 1.0, 0.0)
    _voix(n, "stop", t=1001.0)
    _echos(n)
    _odom(n, 1.0, 0.0, t=1002.0)
    _tour(n, {"objet": "banc"})
    assert _publie(n, "route_speed") == ["0", "0.6"]
    assert n.voice.hold_before is None
    assert ("voice_hold_released", {"by": "tour_de", "speed": 0.6}) in _journal(n)
    assert _ordres(n)[0] == "cancel" and _ordres(n)[1]["name"] == "tour de banc"


def test_node_stop_annule_le_tour(regisseur, monkeypatch, tmp_path):
    _tours_frere(tmp_path, TOUR_BANC)
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _odom(n, 1.0, 0.0)
    _tour(n, {"objet": "banc"})
    _etat_route(n, "goto")
    _voix(n, "stop", t=1001.0)
    assert _publie(n, "route_goto")[-1] == '"cancel"'
    _etat_route(n, "off")
    assert _journal(n)[-1] == ("goto_cancelled", {"name": "tour de banc", "by": "stop"})


def test_node_lubie_de_l_objet_tourne_sautee(regisseur, monkeypatch, tmp_path):
    _tours_frere(tmp_path, TOUR_BANC)
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _recevoir(n, "rehearsal/cmd", "start")
    _odom(n, 1.0, 0.0, t=1001.0)
    _tour(n, {"objet": "banc"})
    _etat_route(n, "goto")
    _poi(n, "banc", "enter")                        # en tournant autour, il entre dans le rayon du POI
    assert ("lubie_skipped", {"poi": "banc", "ids": ["lubie_banc"], "reason": "goto_target"}) in _journal(n)


def test_litteraux_partages_avec_chat_node():
    """Chaînes et bornes gravées des DEUX côtés (chat_node, dépôt vision)."""
    from didier_rehearsal import contracts
    assert contracts.CHAT_MOVE_TOUR_CMD == "tour_de"
    assert contracts.TOUR_SENS == {"gauche": 1, "droite": -1} and contracts.TOUR_SENS_DEFAUT == "gauche"
    assert (contracts.TOUR_CLEARANCE_M, contracts.TOUR_MIN_RADIUS_M, contracts.TOUR_MAX_RADIUS_M) == (1.0, 1.5, 6.0)
    assert (contracts.TOUR_CRUISE_MS, contracts.TOUR_MIN_MS, contracts.TOUR_MAX_DEV_M) == (0.35, 0.1, 1.0)
