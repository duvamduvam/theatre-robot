"""Boîtier de faders — décodage par profil (controller/input/sliders_mapping.py).

Valeurs GRAVÉES à la main (Misc.mapping : (v-10)*(out_max-out_min)//89 + out_min,
bornée à 10..99). Le profil "default" doit être IDENTIQUE à l'ancien
SerialInputs.send_sliders — ces valeurs sont celles qu'il produisait.

Passe de mutation (2026-10-08) — chaque ligne doit rougir :
  - RAW_MAX 99 -> 100 : test_default_identique_a_l_historique
  - inverser l'ordre des cibles de "repetition" 4 car. : test_repetition
  - resolve_profile qui retombe sur "default" : test_profil_inconnu_refuse
"""
import pytest

from controller.control_config import PUBLISHER_LIST
from controller.control_static import ROUTE_SPEED
from controller.input.sliders_mapping import PROFILES, decode_sliders, profile_targets, resolve_profile
from dadou_utils_ros.utils_static import LEFT, NECK, RIGHT, WHEELS


@pytest.mark.parametrize("msg, attendu", [
    ("10", {NECK: 0.0}),
    ("99", {NECK: 1.0}),
    ("55", {NECK: 0.5}),          # (45*100)//89 = 50
    ("05", {NECK: 0.0}),          # borné à 10
    ("1099", {WHEELS: {LEFT: -100, RIGHT: 100}}),
    ("5580", {WHEELS: {LEFT: 1, RIGHT: 57}}),   # 9000//89-100 = 1 ; 14000//89-100 = 57
])
def test_default_identique_a_l_historique(msg, attendu):
    assert decode_sliders(msg, "default") == attendu


def test_taille_imprevue_rend_none():
    assert decode_sliders("123", "default") is None
    assert decode_sliders("", "repetition") is None


@pytest.mark.parametrize("msg, attendu", [
    ("55", {ROUTE_SPEED: 0.5}),
    ("10", {ROUTE_SPEED: 0.0}),
    ("5599", {ROUTE_SPEED: 0.5, NECK: 1.0}),
])
def test_repetition(msg, attendu):
    assert decode_sliders(msg, "repetition") == attendu


def test_repetition_ne_touche_jamais_les_roues():
    assert WHEELS not in profile_targets("repetition")


def test_profil_inconnu_refuse():
    assert resolve_profile(None) == "default"
    assert resolve_profile("") == "default"
    with pytest.raises(ValueError) as exc:
        resolve_profile("repetitoin")
    assert "repetitoin" in str(exc.value)


def test_toutes_les_cibles_sont_publiables():
    """publish() ignore en silence toute clé hors PUBLISHER_LIST : un profil qui
    viserait une clé absente ne ferait RIEN (piège `follow` du 14/09)."""
    for name in PROFILES:
        for key in profile_targets(name):
            assert key in PUBLISHER_LIST, (name, key)
