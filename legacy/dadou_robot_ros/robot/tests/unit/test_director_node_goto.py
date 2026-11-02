"""Node `director` × « aller voir » (lot M1, spec-aller-voir.md §2-§3) avec
rclpy SIMULÉ — banc RÉUTILISÉ de test_director_node.py (même fixture, mêmes
factices), journal JSONL relu sur disque.

Mutations du lot M1 (doivent rougir) :
  - « stop » vocal sans cancel sur route_goto -> test_stop_vocal_publie_cancel_avant_le_zero
  - arrêt vocal non levé à l'acceptation -> test_acceptation_leve_l_arret_vocal_a_la_vitesse_du_go
  - min(retenue, batterie) retiré -> test_acceptation_jamais_au_dessus_de_la_batterie
  - refus route_off_by_david retiré -> test_refus_route_off_par_david_rien_ne_part
  - borne de fraîcheur de la pose retirée -> test_pose_perimee_refus_no_pose
Revue M1 (31/10) :
  - lubie de la cible non sautée -> test_lubie_de_la_cible_sautee_pendant_la_manoeuvre
"""
import json
import types

import pytest

from robot.tests.unit.test_director_node import (BATTERIE, LUBIE, _cmd, _creer, _echos, _etat_route,
                                                 _fader, _journal, _poi, _publie, _recevoir, _tick_a,
                                                 _voix, regisseur)  # noqa: F401 (fixture)

ORDRE_BANC = {"name": "banc", "x": 5.0, "y": 0.0, "standoff": 1.5}


def _odom(noeud, x, y, t=None):
    if t is not None:
        noeud.horloge.t = t
    pose = types.SimpleNamespace(position=types.SimpleNamespace(x=x, y=y, z=0.0))
    _qos, callback = noeud.abonnements["/ground_truth/odom"]
    callback(types.SimpleNamespace(pose=types.SimpleNamespace(pose=pose)))


def _aller_voir(noeud, objet, t=None):
    if t is not None:
        noeud.horloge.t = t
    _recevoir(noeud, "rehearsal/chat_move", json.dumps({"cmd": "aller_voir", "objet": objet}))


def _aller_voirs(noeud):
    return [p for t, p in _journal(noeud) if t == "aller_voir"]


def _ordres(noeud):
    return [json.loads(m) for m in _publie(noeud, "route_goto")]


def test_vocabulaire_latche_au_demarrage(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    qos = n.qos_publieurs["rehearsal/objects"]
    assert (qos.depth, qos.durability) == (1, "TRANSIENT_LOCAL")
    assert [json.loads(m) for m in _publie(n, "rehearsal/objects")] == [
        # x, y (ancre du POI) : ajoutés au lot A1 (sélecteur de jeu, regard vers l'objet).
        [{"name": "banc", "desc": "banc", "x": 5.0, "y": 0.0},
         {"name": "flaque", "desc": "flaque", "x": 12.0, "y": 0.0}]]


def test_accepte_hors_seance_et_ordonne(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _etat_route(n, "off", cause="boot")
    _odom(n, 1.0, 0.0)
    _aller_voir(n, "Le Banc")
    assert _aller_voirs(n) == [{"objet": "Le Banc", "effect": "accepted", "name": "banc", "distance": 4.0}]
    assert _ordres(n) == [ORDRE_BANC]
    assert "geometry_msgs" not in str(type(n.publishers["route_goto"]))   # jamais de Twist ici


def test_refus_inconnu_rien_ne_part(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _odom(n, 1.0, 0.0)
    _aller_voir(n, "pigeon")
    assert _aller_voirs(n) == [{"objet": "pigeon", "effect": "unknown"}]
    assert _ordres(n) == []


def test_refus_route_off_par_david_rien_ne_part(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _odom(n, 1.0, 0.0)
    _etat_route(n, "off", cause="cmd")              # David a coupé (son `off` raté par nous)
    _aller_voir(n, "banc")
    assert _aller_voirs(n) == [{"objet": "banc", "effect": "route_off_by_david", "name": "banc"}]
    _recevoir(n, "route", "on"); _etat_route(n, "on")
    _recevoir(n, "route", "off")                    # `off` VU
    _aller_voir(n, "banc")
    assert _aller_voirs(n)[-1]["effect"] == "route_off_by_david"
    assert _ordres(n) == []


def test_refus_trop_loin(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _odom(n, 45.5, 0.0)
    _aller_voir(n, "banc")
    assert _aller_voirs(n) == [{"objet": "banc", "effect": "too_far", "name": "banc", "distance": 40.5}]
    assert _ordres(n) == []


def test_pose_perimee_refus_no_pose(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _aller_voir(n, "banc")
    assert _aller_voirs(n)[-1]["effect"] == "no_pose"          # jamais reçue
    _odom(n, 1.0, 0.0, t=1000.0)
    _aller_voir(n, "banc", t=1000.5)
    assert _aller_voirs(n)[-1]["effect"] == "accepted"         # 500 ms : fraîche
    _aller_voir(n, "banc", t=1000.7)
    assert _aller_voirs(n)[-1]["effect"] == "no_pose"          # 700 ms : périmée


def test_stop_vocal_publie_cancel_avant_le_zero(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _odom(n, 1.0, 0.0)
    _aller_voir(n, "banc")
    _etat_route(n, "goto")
    _voix(n, "stop", t=1001.0)
    assert _publie(n, "route_goto")[-1] == '"cancel"'
    assert _publie(n, "route_speed") == ["0"]
    _etat_route(n, "off")
    assert _journal(n)[-1] == ("goto_cancelled", {"name": "banc", "by": "stop"})


def test_abort_publie_cancel(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _cmd(n, "start")
    _cmd(n, "abort")
    assert _publie(n, "route_goto") == ['"cancel"']


def test_acceptation_leve_l_arret_vocal_a_la_vitesse_du_go(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.6")
    _recevoir(n, "route", "on"); _etat_route(n, "on")
    _odom(n, 1.0, 0.0)
    _voix(n, "stop", t=1001.0)
    _echos(n)
    _odom(n, 1.0, 0.0, t=1002.0)
    _aller_voir(n, "banc")
    assert _publie(n, "route_speed") == ["0", "0.6"]
    assert n.voice.hold_before is None
    assert json.loads(_publie(n, "rehearsal/state")[-1])["arret_vocal"] is False
    assert _ordres(n) == ["cancel", ORDRE_BANC]     # le « cancel » vient du « stop »


def test_acceptation_jamais_au_dessus_de_la_batterie(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [BATTERIE])
    _fader(n, "0.9")
    _recevoir(n, "route", "on"); _etat_route(n, "on")
    _cmd(n, "start")
    _tick_a(n, 1200.0)                              # batterie 0.4 active
    _echos(n)
    _odom(n, 1.0, 0.0)
    _voix(n, "stop", t=1201.0)
    _echos(n)
    _odom(n, 1.0, 0.0, t=1202.0)
    _aller_voir(n, "banc")
    assert _publie(n, "route_speed") == ["0.4", "0", "0.4"]   # jamais le fader 0.9


def test_acceptation_ferme_une_lubie_comme_go(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.7")
    _cmd(n, "start")
    _poi(n, "banc", "enter")
    _echos(n)
    _odom(n, 1.0, 0.0, t=1010.0)
    _aller_voir(n, "flaque")
    assert _publie(n, "route_speed") == ["0", "0.7"]
    assert [p["closed_by"] for t, p in _journal(n) if t == "fault_stop"] == ["voix"]
    assert _ordres(n)[-1]["name"] == "flaque"


def test_go_apres_arrivee_relance_la_route(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _recevoir(n, "route", "on"); _etat_route(n, "on")
    _cmd(n, "start")
    _odom(n, 1.0, 0.0, t=1001.0)
    _aller_voir(n, "banc")
    _etat_route(n, "goto")
    _etat_route(n, "arrived")
    assert _journal(n)[-1] == ("goto_arrived", {"name": "banc"})
    _voix(n, "go", t=1010.0)
    assert _publie(n, "route") == ["on"]
    assert [p for t, p in _journal(n) if t == "voice_move"][-1] == {"cmd": "go", "effect": "rejoin",
                                                                     "rejoin": True}


def test_go_pendant_la_manoeuvre_deja_en_marche(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _etat_route(n, "off", cause="boot")
    _cmd(n, "start")
    _odom(n, 1.0, 0.0, t=1001.0)
    _aller_voir(n, "banc")
    _etat_route(n, "goto")
    _voix(n, "go", t=1005.0)
    assert _publie(n, "route") == []                # un « on » abandonnerait la manœuvre


def test_fader_apres_arrivee_relance_la_route(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.5")
    _recevoir(n, "route", "on"); _etat_route(n, "on")
    _odom(n, 1.0, 0.0)
    _aller_voir(n, "banc")
    _etat_route(n, "goto"); _etat_route(n, "arrived")
    _fader(n, "0.52")                               # jitter : rien
    assert _publie(n, "route") == []
    _fader(n, "0.7")
    assert _publie(n, "route") == ["on"]
    assert ("goto_rejoin", {"by": "fader", "value": 0.7}) in _journal(n)


def test_aller_voir_illisible_ne_tue_pas_le_node(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _recevoir(n, "rehearsal/chat_move", json.dumps({"cmd": "aller_voir"}))
    _recevoir(n, "rehearsal/chat_move", json.dumps({"cmd": "danser"}))
    assert _aller_voirs(n) == [{"objet": None, "effect": "unknown"}]
    assert [p for t, p in _journal(n) if t == "voice_move"] == [
        {"cmd": {"cmd": "danser"}, "effect": "ignored", "reason": "invalide"}]


LUBIE_FLAQUE = {"id": "lubie_flaque", "type": "lubie", "t": "poi", "poi": "flaque", "duration_s": 60}


def test_lubie_de_la_cible_sautee_pendant_la_manoeuvre(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE, LUBIE_FLAQUE])
    _recevoir(n, "route", "on"); _etat_route(n, "on")
    _cmd(n, "start")
    _odom(n, 1.0, 0.0, t=1001.0)
    _aller_voir(n, "banc")
    _etat_route(n, "goto")
    _poi(n, "banc", "enter")                        # à 1 m du but, standoff < rayon
    assert ("lubie_skipped", {"poi": "banc", "ids": ["lubie_banc"], "reason": "goto_target"}) in _journal(n)
    assert _publie(n, "chat_instruction") == [] and _publie(n, "route_speed") == []
    assert n.director.status()["lubie_banc"] == "skipped"
    _poi(n, "flaque", "enter")                      # les AUTRES lubies restent possibles
    assert n.director.status()["lubie_flaque"] == "active"


def test_lubie_de_la_cible_sautee_aussi_a_l_arrivee(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _recevoir(n, "route", "on"); _etat_route(n, "on")
    _cmd(n, "start")
    _odom(n, 1.0, 0.0, t=1001.0)
    _aller_voir(n, "banc")
    _etat_route(n, "goto"); _etat_route(n, "arrived")
    _poi(n, "banc", "enter")
    assert n.director.status()["lubie_banc"] == "skipped"


def test_lubie_hors_manoeuvre_part_normalement(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _recevoir(n, "route", "on"); _etat_route(n, "on")
    _cmd(n, "start")
    _poi(n, "banc", "enter")
    assert n.director.status()["lubie_banc"] == "active"


def test_issue_detaillee_journalisee(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    resultat = {"name": "banc", "result": "aborted", "reason": "stalled", "travelled": 0.4}
    _recevoir(n, "route_goto_result", json.dumps(resultat))
    assert _journal(n)[-1] == ("goto_result", resultat)
