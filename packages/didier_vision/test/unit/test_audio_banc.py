"""Outil de réglage son/micro du banc PC (conf/docker/x86/audio_banc.py) —
logique PURE, valeurs gravées. Lit le VRAI asound-pc.conf pour le contrat."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4] / "legacy" / "dadou_vision_ros"
_spec = importlib.util.spec_from_file_location("audio_banc", ROOT / "conf/docker/x86/audio_banc.py")
ab = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ab)
CONF = (ROOT / "conf/docker/x86/asound-pc.conf").read_text(encoding="utf-8")


def test_le_vrai_fichier_respecte_le_contrat():
    d = ab.lire_devices(CONF)
    assert d["micro"] is not None and d["sortie"] is not None


def test_ecrire_ne_touche_que_les_deux_lignes():
    t = ab.ecrire_devices(CONF, "bluez_input.AA:BB", "bluez_output.AA:BB")
    assert ab.lire_devices(t) == {"micro": "bluez_input.AA:BB", "sortie": "bluez_output.AA:BB"}
    # tout le reste est identique, ligne à ligne
    diff = [(a, b) for a, b in zip(CONF.splitlines(), t.splitlines()) if a != b]
    assert len(diff) == 2 and len(CONF.splitlines()) == len(t.splitlines())


def test_defaut():
    t = ab.ecrire_devices(CONF, ab.DEFAULT_IN, ab.DEFAULT_OUT)
    assert ab.lire_devices(t) == {"micro": "@DEFAULT_SOURCE@", "sortie": "@DEFAULT_SINK@"}


def test_bloc_absent_refuse():
    with pytest.raises(ValueError):
        ab.ecrire_devices("pcm.autre { type pulse }", "a", "b")


def test_gain():
    assert "ttable.0.0 0.3" in ab.ecrire_gain(CONF, 0.3)
    for bad in (0, 1.5, -1):
        with pytest.raises(ValueError):
            ab.ecrire_gain(CONF, bad)


def test_trouver_noeud_deux_formats_de_mac():
    noms = ["alsa_output.pci-0000_00_1f.3.analog-stereo",
            "bluez_output.40_9C_A7_5B_66_D6.1", "bluez_output.40_9C_A7_5B_66_D6.1.monitor"]
    assert ab.trouver_noeud(noms, "40:9C:A7:5B:66:D6") == "bluez_output.40_9C_A7_5B_66_D6.1"
    assert ab.trouver_noeud(["bluez_input.40:9C:A7:5B:66:D6"], "40:9c:a7:5b:66:d6") == "bluez_input.40:9C:A7:5B:66:D6"
    assert ab.trouver_noeud(noms, "11:22:33:44:55:66") is None


def test_profil_hfp():
    assert ab.choisir_profil_hfp(["off", "a2dp-sink", "headset-head-unit-cvsd", "headset-head-unit-msbc"]) == "headset-head-unit-msbc"
    assert ab.choisir_profil_hfp(["off", "a2dp-sink", "headset-head-unit"]) == "headset-head-unit"
    assert ab.choisir_profil_hfp(["off", "a2dp-sink"]) is None


def test_resoudre_casque():
    app = [("40:9C:A7:5B:66:D6", "M50"), ("AC:80:0A:7F:3C:53", "WH-1000XM4"),
           ("E4:72:D7:FC:95:38", "HAYLOU S35 ANC")]
    assert ab.resoudre_casque(app, "m50") == ("40:9C:A7:5B:66:D6", "M50")
    assert ab.resoudre_casque(app, "haylou") == ("E4:72:D7:FC:95:38", "HAYLOU S35 ANC")
    assert ab.resoudre_casque(app, "ac:80:0a:7f:3c:53")[1] == "WH-1000XM4"
    assert ab.resoudre_casque(app, "inconnu") is None
    assert ab.resoudre_casque(app + [("X", "M50 bis")], "m5") is None   # ambigu -> refus
