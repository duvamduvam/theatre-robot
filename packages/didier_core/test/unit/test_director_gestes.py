"""Régisseur × gestes chiffrés « tourner » / « avancer » (lot M2,
spec-aller-voir.md §7.2-§7.3) — arbitrage PUR puis node avec rclpy SIMULÉ
(banc RÉUTILISÉ de test_director_node.py). Valeurs GRAVÉES.

Mutations du lot M2 (doivent rougir) :
  - signe de la compat inversé (gauche = −90) -> test_tourner_compat_sens
  - borne |angle| ≤ 180 retirée -> test_tourner_refus_hors_bornes
  - recul accepté -> test_avancer_refus_recul_et_bornes
  - borne 5 m retirée -> test_avancer_refus_recul_et_bornes
  - refus route_off_by_david retiré pour les gestes -> test_node_geste_refuse_route_off_par_david
  - arrêt vocal non levé à l'acceptation d'un geste -> test_node_tourner_leve_l_arret_vocal
  - « stop » sans cancel pendant un geste -> test_node_stop_annule_le_geste
"""
import json
import math

import pytest

from test.unit.test_director_node import (LUBIE, _cmd, _creer, _echos, _etat_route, _fader,
                                                 _journal, _publie, _recevoir, _voix,
                                                 regisseur)  # noqa: F401 (fixture)
from test.unit.test_director_node_goto import _odom
from didier_rehearsal.director import decide_forward, decide_turn


def _t(intent, pose_known=True, off_by_david=False):
    d = decide_turn(intent, pose_known=pose_known, off_by_david=off_by_david)
    return d.effect, d.reason, d.name, None if d.order is None else json.loads(d.order)


def _f(intent, pose_known=True, off_by_david=False):
    d = decide_forward(intent, pose_known=pose_known, off_by_david=off_by_david)
    return d.effect, d.reason, d.name, None if d.order is None else json.loads(d.order)


# --- arbitrage pur -------------------------------------------------------------------

def test_tourner_angle_signe_gauche_positif():
    assert _t({"angle_deg": 90}) == ("accepted", None, "pivot +90°", {"turn_rad": 1.5707963267948966})
    assert _t({"angle_deg": -45}) == ("accepted", None, "pivot -45°", {"turn_rad": -0.7853981633974483})
    assert _t({"angle_deg": 180})[3] == {"turn_rad": math.pi}


def test_tourner_compat_sens():
    assert _t({"sens": "gauche"})[2:] == ("pivot +90°", {"turn_rad": 1.5707963267948966})
    assert _t({"sens": "Droite "})[2:] == ("pivot -90°", {"turn_rad": -1.5707963267948966})
    assert _t({"sens": "demi_tour"})[2:] == ("pivot +180°", {"turn_rad": math.pi})
    assert _t({"angle_deg": 30, "sens": "droite"})[2] == "pivot +30°"     # angle_deg fait foi


@pytest.mark.parametrize("intent, reason", [
    ({"angle_deg": 0}, "hors_bornes"), ({"angle_deg": 180.5}, "hors_bornes"),
    ({"angle_deg": -270}, "hors_bornes"), ({"angle_deg": "90"}, "illisible"),
    ({"angle_deg": True}, "illisible"), ({"angle_deg": None, "sens": "gauche"}, "illisible"),
    ({"sens": "tout_droit"}, "illisible"), ({}, "illisible"),
])
def test_tourner_refus_hors_bornes(intent, reason):
    assert _t(intent) == ("invalid", reason, None, None)


def test_avancer_accepte():
    assert _f({"metres": 2}) == ("accepted", None, "avancer 2 m", {"forward_m": 2.0})
    assert _f({"metres": 5})[0] == "accepted"
    assert _f({"metres": 0.1})[0] == "accepted"                          # plancher inclus


@pytest.mark.parametrize("intent, reason", [
    ({"metres": -1}, "recul"), ({"metres": 0}, "hors_bornes"), ({"metres": 5.5}, "hors_bornes"),
    pytest.param({"metres": 0.09}, "hors_bornes", id="sous 10 cm"),
    ({"metres": "2"}, "illisible"), ({}, "illisible"), ({"metres": float("nan")}, "illisible"),
])
def test_avancer_refus_recul_et_bornes(intent, reason):
    assert _f(intent) == ("invalid", reason, None, None)


def test_refus_communs_dans_l_ordre():
    assert _t({"angle_deg": 90}, off_by_david=True, pose_known=False)[0] == "route_off_by_david"
    assert _t({"angle_deg": 90}, pose_known=False)[:3] == ("no_pose", None, "pivot +90°")
    assert _f({"metres": 1}, off_by_david=True)[0] == "route_off_by_david"
    assert _f({"metres": 1}, pose_known=False)[0] == "no_pose"
    assert _f({"metres": -1}, off_by_david=True)[:2] == ("invalid", "recul")   # invalide d'abord


# --- node --------------------------------------------------------------------------

def _geste(noeud, intent, t=None):
    if t is not None:
        noeud.horloge.t = t
    _recevoir(noeud, "rehearsal/chat_move", json.dumps(intent))


def _ordres(noeud):
    return [json.loads(m) for m in _publie(noeud, "route_goto")]


def test_node_tourner_accepte_hors_seance(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _etat_route(n, "off", cause="boot")
    _odom(n, 1.0, 0.0)
    _geste(n, {"cmd": "tourner", "angle_deg": 90, "bavard": "x"})
    assert [p for t, p in _journal(n) if t == "tourner"] == [
        {"angle_deg": 90, "effect": "accepted", "name": "pivot +90°"}]   # champs du contrat seuls
    assert _ordres(n) == [{"turn_rad": 1.5707963267948966}]


def test_node_avancer_refus_recul_rien_ne_part(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _odom(n, 1.0, 0.0)
    _geste(n, {"cmd": "avancer", "metres": -2})
    assert [p for t, p in _journal(n) if t == "avancer"] == [
        {"metres": -2, "effect": "invalid", "reason": "recul"}]
    assert _ordres(n) == []


def test_node_geste_refuse_route_off_par_david(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _odom(n, 1.0, 0.0)
    _recevoir(n, "route", "on"); _etat_route(n, "on")
    _recevoir(n, "route", "off")                    # `off` de David VU
    _geste(n, {"cmd": "tourner", "sens": "gauche"})
    _geste(n, {"cmd": "avancer", "metres": 1})
    assert [p["effect"] for t, p in _journal(n) if t in ("tourner", "avancer")] == [
        "route_off_by_david", "route_off_by_david"]
    assert _ordres(n) == []


def test_node_geste_sans_pose_refuse(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _geste(n, {"cmd": "avancer", "metres": 1})
    assert [p["effect"] for t, p in _journal(n) if t == "avancer"] == ["no_pose"]
    assert _ordres(n) == []


def test_node_tourner_leve_l_arret_vocal(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.6")
    _recevoir(n, "route", "on"); _etat_route(n, "on")
    _odom(n, 1.0, 0.0)
    _voix(n, "stop", t=1001.0)
    _echos(n)
    _odom(n, 1.0, 0.0, t=1002.0)
    _geste(n, {"cmd": "tourner", "sens": "droite"})
    assert _publie(n, "route_speed") == ["0", "0.6"]
    assert n.voice.hold_before is None
    assert ("voice_hold_released", {"by": "tourner", "speed": 0.6}) in _journal(n)
    assert _ordres(n) == ["cancel", {"turn_rad": -1.5707963267948966}]


def test_node_stop_annule_le_geste(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _odom(n, 1.0, 0.0)
    _geste(n, {"cmd": "avancer", "metres": 3})
    _etat_route(n, "goto")
    _voix(n, "stop", t=1001.0)
    assert _publie(n, "route_goto")[-1] == '"cancel"'
    _etat_route(n, "off")
    assert _journal(n)[-1] == ("goto_cancelled", {"name": "avancer 3 m", "by": "stop"})


def test_node_go_apres_pivot_rejoint(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _recevoir(n, "route", "on"); _etat_route(n, "on")
    _cmd(n, "start")
    _odom(n, 1.0, 0.0, t=1001.0)
    _geste(n, {"cmd": "tourner", "sens": "demi_tour"})
    _etat_route(n, "goto"); _etat_route(n, "arrived")
    assert _journal(n)[-1] == ("goto_arrived", {"name": "pivot +180°"})
    _voix(n, "go", t=1010.0)
    assert _publie(n, "route") == ["on"]


def test_litteraux_partages_avec_chat_node():
    """Chaînes et bornes gravées des DEUX côtés (chat_node, dépôt vision)."""
    from didier_rehearsal import contracts
    assert (contracts.CHAT_MOVE_TURN_CMD, contracts.CHAT_MOVE_FORWARD_CMD) == ("tourner", "avancer")
    assert contracts.TURN_DEG_COMPAT == {"gauche": 90.0, "droite": -90.0, "demi_tour": 180.0}
    assert (contracts.TURN_MAX_DEG, contracts.TURN_TIMEOUT_S) == (180.0, 15.0)
    assert contracts.FORWARD_MIN_M == 0.1
    assert (contracts.FORWARD_MAX_M, contracts.FORWARD_TIMEOUT_BASE_S, contracts.FORWARD_TIMEOUT_PER_M_S) == \
        (5.0, 10.0, 4.0)
