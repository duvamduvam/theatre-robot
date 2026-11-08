"""Source d'images de la perception (webcam / Gazebo) — SANS ROS, valeurs gravées en dur."""
import pytest

from didier_vision.tracking.camera_source import (
    SOURCE_GAZEBO, SOURCE_WEBCAM, available_sources, camera_is_partner_effective,
    decode_camera_source, image_to_bgr, resolve_source)


def test_valeurs_publiees_gravees():
    # Contrat avec la page web : ne pas renommer.
    assert SOURCE_WEBCAM == "webcam"
    assert SOURCE_GAZEBO == "gazebo"


@pytest.mark.parametrize("raw", ["webcam", '"webcam"', " WebCam "])
def test_decode_webcam(raw):
    assert decode_camera_source(raw) == "webcam"


@pytest.mark.parametrize("raw", ["gazebo", '"gazebo"', " GAZEBO "])
def test_decode_gazebo(raw):
    assert decode_camera_source(raw) == "gazebo"


@pytest.mark.parametrize("raw", ["", "gazebo2", "on", "1", "true", "null", "[1]", "{}", "0", None])
def test_decode_inconnu_ne_change_rien(raw):
    assert decode_camera_source(raw) is None


def test_sources_disponibles():
    assert available_sources("") == ["webcam"]
    assert available_sources("  ") == ["webcam"]
    assert available_sources("camera/image_raw") == ["webcam", "gazebo"]


def test_gazebo_refuse_si_indisponible():
    assert resolve_source("webcam", "gazebo", "") == "webcam"


def test_gazebo_accepte_si_topic_configure():
    assert resolve_source("webcam", "gazebo", "camera/image_raw") == "gazebo"
    assert resolve_source("gazebo", "webcam", "camera/image_raw") == "webcam"


def test_webcam_toujours_accepte():
    assert resolve_source("gazebo", "webcam", "") == "webcam"


def test_rgb8_vers_bgr():
    # 2 lignes x 3 pixels : (R,G,B) par pixel, sans remplissage.
    data = bytes([
        1, 2, 3, 4, 5, 6, 7, 8, 9,
        10, 11, 12, 13, 14, 15, 16, 17, 18,
    ])
    out = image_to_bgr("rgb8", 3, 2, 9, data)
    assert out.shape == (2, 3, 3)
    assert out.dtype.name == "uint8"
    assert out.flags["C_CONTIGUOUS"]
    assert out.tolist() == [
        [[3, 2, 1], [6, 5, 4], [9, 8, 7]],
        [[12, 11, 10], [15, 14, 13], [18, 17, 16]],
    ]


def test_rgb8_step_superieur_a_largeur():
    # step 12 > 3*3 : 3 octets de remplissage (99) par ligne, à jeter.
    data = bytes([
        1, 2, 3, 4, 5, 6, 7, 8, 9, 99, 99, 99,
        10, 11, 12, 13, 14, 15, 16, 17, 18, 99, 99, 99,
    ])
    out = image_to_bgr("rgb8", 3, 2, 12, data)
    assert out.tolist() == [
        [[3, 2, 1], [6, 5, 4], [9, 8, 7]],
        [[12, 11, 10], [15, 14, 13], [18, 17, 16]],
    ]


@pytest.mark.parametrize("encoding", ["bgr8", "mono8", "rgba8", "16UC1", ""])
def test_encoding_inconnu_refuse(encoding):
    with pytest.raises(ValueError):
        image_to_bgr(encoding, 3, 2, 9, bytes(18))


def test_dimensions_incoherentes_refusees():
    with pytest.raises(ValueError):
        image_to_bgr("rgb8", 3, 2, 8, bytes(16))   # step < w*3
    with pytest.raises(ValueError):
        image_to_bgr("rgb8", 3, 2, 9, bytes(17))   # données trop courtes
    with pytest.raises(ValueError):
        image_to_bgr("rgb8", 0, 2, 0, b"")


@pytest.mark.parametrize("base,source,attendu", [
    (True, "webcam", True),
    (True, "gazebo", False),
    (False, "webcam", False),
    (False, "gazebo", False),
])
def test_drapeau_partenaire_selon_la_source(base, source, attendu):
    assert camera_is_partner_effective(base, source) is attendu
