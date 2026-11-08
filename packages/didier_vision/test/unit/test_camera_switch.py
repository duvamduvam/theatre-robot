"""Décodage pur de `camera_enable` (coupe-webcam) — valeurs gravées en dur."""
import pytest

from didier_vision.tracking.camera_switch import CAMERA_OFF, CAMERA_ON, decode_camera_enable


@pytest.mark.parametrize("raw", ["on", '"on"', "true", "1", " ON ", '"On"', '"1"'])
def test_allumer(raw):
    assert decode_camera_enable(raw) is True


@pytest.mark.parametrize("raw", ["off", '"off"', "false", "0", " OFF ", '"Off"', '"0"'])
def test_couper(raw):
    assert decode_camera_enable(raw) is False


@pytest.mark.parametrize("raw", ["", "peut-etre", "2", "-1", "null", "[1]", "{}", "1.0", "0.0", "stop", None])
def test_valeur_inconnue_ne_change_rien(raw):
    assert decode_camera_enable(raw) is None


def test_valeurs_publiees_gravees():
    # Contrat avec la page web : ne pas renommer.
    assert CAMERA_ON == "on"
    assert CAMERA_OFF == "off"
