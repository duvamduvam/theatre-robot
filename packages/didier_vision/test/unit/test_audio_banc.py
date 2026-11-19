"""Outil de réglage son/micro du banc PC (machines/sim/banc-vision/audio_banc.py) —
logique PURE, valeurs gravées. Lit le VRAI asound-pc.conf pour le contrat."""
import importlib.util
from pathlib import Path

import pytest

# L1e-4c (11/11) : le banc PC de la vision est machines/sim/banc-vision/.
BANC = Path(__file__).resolve().parents[4] / "machines" / "sim" / "banc-vision"
_spec = importlib.util.spec_from_file_location("audio_banc", BANC / "audio_banc.py")
ab = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ab)
CONF = (BANC / "asound-pc.conf").read_text(encoding="utf-8")


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


# ─── choisir auto (18/11) ─────────────────────────────────────────────────────
# Noms RÉELS relevés sur le PC du banc le 18/11.
PC_IN, PC_OUT = "alsa_input.pci-0000_00_1f.3.analog-stereo", "alsa_output.pci-0000_00_1f.3.analog-stereo"
SCARLETT = "alsa_input.usb-Focusrite_Scarlett_4i4_USB_0000000000000-00.analog-surround-21"
M50 = ("40:9C:A7:5B:66:D6", "M50")
M50_IN, M50_OUT = "bluez_input.40:9C:A7:5B:66:D6", "bluez_output.40_9C_A7_5B_66_D6.1"
RESPEAKER = "alsa_input.usb-Seeed_reSpeaker_XVF3800_4-Mic_Array-00.analog-stereo"


def test_auto_cas_du_18_11_scarlett_muette_micro_interne_vivant():
    micro, sortie, pourquoi = ab.plan_auto([], [PC_IN, SCARLETT, PC_OUT + ".monitor"], [PC_OUT],
                                           {PC_IN: 8268, SCARLETT: 1})
    assert (micro, sortie) == (PC_IN, "@DEFAULT_SINK@")
    assert "le micro peut entendre Didier" in pourquoi
    assert "micros muets écartés : " + SCARLETT in pourquoi


def test_auto_seuil_de_vie_grave():
    assert ab.CRETE_VIVANT == 30
    micro, _, _ = ab.plan_auto([], [PC_IN, SCARLETT], [], {PC_IN: 29, SCARLETT: 30})
    assert micro == SCARLETT


def test_auto_aucun_micro_vivant_le_dit():
    micro, _, pourquoi = ab.plan_auto([], [PC_IN, SCARLETT], [PC_OUT], {PC_IN: 0, SCARLETT: 2})
    assert micro == "@DEFAULT_SOURCE@"
    assert "AUCUN micro ne capte" in pourquoi


def test_auto_casque_micro_et_sortie():
    micro, sortie, pourquoi = ab.plan_auto([M50], [PC_IN, M50_IN], [PC_OUT, M50_OUT],
                                           {PC_IN: 900, M50_IN: 400})
    assert (micro, sortie) == (M50_IN, M50_OUT)
    assert pourquoi == f"micro = micro du casque M50 [{M50_IN}] ; sortie = casque M50"


def test_auto_respeaker_prime_sur_le_casque():
    micro, sortie, _ = ab.plan_auto([M50], [PC_IN, M50_IN, RESPEAKER], [PC_OUT, M50_OUT])
    assert (micro, sortie) == (RESPEAKER, M50_OUT)


def test_auto_usb_prime_sur_le_micro_interne():
    micro, _, _ = ab.plan_auto([], [PC_IN, SCARLETT], [], {PC_IN: 5000, SCARLETT: 300})
    assert micro == SCARLETT


def test_auto_casque_sans_hfp_sert_de_sortie_seulement():
    micro, sortie, pourquoi = ab.plan_auto([M50], [PC_IN], [PC_OUT, M50_OUT], {PC_IN: 900})
    assert (micro, sortie) == (PC_IN, M50_OUT)
    assert "entendre Didier" not in pourquoi


def test_auto_ignore_les_monitors():
    micro, _, _ = ab.plan_auto([], [PC_OUT + ".monitor"], [])
    assert micro == "@DEFAULT_SOURCE@"
