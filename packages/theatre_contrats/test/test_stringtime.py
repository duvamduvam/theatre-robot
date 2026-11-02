"""Codec StringTime : valeurs attendues ÉCRITES EN DUR (jamais recalculées par
json.loads ou par le code testé — un test qui recalcule l'attendu ne voit pas
une mutation du codec, leçon du 14/09).

Les cas « strict » rejouent ceux de dadou_robot_ros/robot/tests/unit/test_payload.py
(le décodeur commun de juillet dont decode est la copie) : même entrée, même sortie.
"""
import logging

import pytest

from theatre_contrats import stringtime


class FakeStringTime:
    def __init__(self, msg):
        self.msg = msg


ENTIER_GEANT = "1" * 5000   # > 4300 chiffres : ValueError, PAS JSONDecodeError


# ---------------------------------------------------------------- decode (strict)

def test_strict_nom_d_expression_json():
    assert stringtime.decode(FakeStringTime('"calib"'), "face") == "calib"


def test_strict_objet_json():
    assert stringtime.decode(FakeStringTime('{"brightness": 0.5}'), "robot_lights") == {"brightness": 0.5}


def test_strict_booleen_json():
    # L'arrêt d'animation se publie msg: "false" (booléen JSON).
    assert stringtime.decode(FakeStringTime('false'), "animation") is False


def test_strict_chaine_brute_refusee_avec_log(caplog):
    with caplog.at_level(logging.ERROR):
        assert stringtime.decode(FakeStringTime('calib'), "face") is None
    assert caplog.records[0].levelno == logging.ERROR
    assert caplog.records[0].getMessage() == (
        "payload invalide sur 'face' (JSON attendu, ex. '\"nom\"' avec guillemets) : 'calib'")


def test_strict_payload_non_chaine_refuse(caplog):
    with caplog.at_level(logging.ERROR):
        assert stringtime.decode(FakeStringTime(None), "face") is None
    assert len(caplog.records) == 1


def test_strict_entier_geant_propage_comme_avant():
    # payload.py n'attrapait que JSONDecodeError/TypeError : comportement conservé.
    with pytest.raises(ValueError):
        stringtime.decode_payload(ENTIER_GEANT, "face")


def test_strict_null_rend_none_sans_log(caplog):
    with caplog.at_level(logging.DEBUG):
        assert stringtime.decode_payload("null", "face") is None
    assert caplog.records == []


# ---------------------------------------------------------------- decode_or_raw (tolérant)

def test_tolerant_json_decode():
    assert stringtime.decode_or_raw('"on"') == "on"
    assert stringtime.decode_or_raw('0.5') == 0.5
    assert stringtime.decode_or_raw('{"dir": "gauche"}') == {"dir": "gauche"}
    assert stringtime.decode_or_raw('1') == 1
    assert stringtime.decode_or_raw('true') is True


def test_tolerant_brut_rendu_tel_quel_avec_log_debug(caplog):
    with caplog.at_level(logging.DEBUG):
        assert stringtime.decode_or_raw("on", "gaze") == "on"
        assert stringtime.decode_or_raw(" off ", "gaze") == " off "   # pas de strip
    assert [r.levelno for r in caplog.records] == [logging.DEBUG, logging.DEBUG]
    assert caplog.records[0].getMessage() == "payload non JSON sur 'gaze', pris brut : 'on'"


def test_tolerant_entier_geant_pris_brut():
    assert stringtime.decode_or_raw(ENTIER_GEANT) == ENTIER_GEANT


def test_tolerant_non_chaine_rendue_telle_quelle():
    assert stringtime.decode_or_raw(None) is None
    assert stringtime.decode_or_raw(0.7) == 0.7


def test_tolerant_imbrication_hostile_propage():
    with pytest.raises(RecursionError):
        stringtime.decode_or_raw("[" * 100000)


# ---------------------------------------------------------------- loads (nu)

def test_loads_leve_comme_json():
    assert stringtime.loads('{"poi": "nef", "event": "enter"}') == {"poi": "nef", "event": "enter"}
    with pytest.raises(ValueError):
        stringtime.loads("calib")
    with pytest.raises(TypeError):
        stringtime.loads(None)


# ---------------------------------------------------------------- encode

def test_encode_valeur_nue():
    assert stringtime.encode("joie") == {"msg": '"joie"', "time": 0, "anim": False}
    assert stringtime.encode(False, 45000, True) == {"msg": "false", "time": 45000, "anim": True}
    assert stringtime.encode({"dir": "gauche"}, 1500.0) == {"msg": '{"dir": "gauche"}', "time": 1500,
                                                            "anim": False}


def test_encode_avec_type_de_message():
    class StringTime:
        def __init__(self, msg, time, anim):
            self.msg, self.time, self.anim = msg, time, anim

    m = stringtime.encode("parle", 45000, msg_type=StringTime)
    assert (m.msg, m.time, m.anim) == ('"parle"', 45000, False)
