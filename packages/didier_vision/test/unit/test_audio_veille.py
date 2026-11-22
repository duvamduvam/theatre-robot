"""Veille audio du banc PC (machines/sim/banc-vision/audio_veille.py, onglet « Audio » de la
page scène, 22/11) — logique PURE et commandes lancées, valeurs GRAVÉES. Rien n'y touche au
son réel du PC : subprocess est remplacé là où une commande partirait."""
import importlib.util
import io
import json
import struct
import sys
import threading
import urllib.request
import wave
from pathlib import Path

import pytest

BANC = Path(__file__).resolve().parents[4] / "machines" / "sim" / "banc-vision"
sys.path.insert(0, str(BANC))
_spec = importlib.util.spec_from_file_location("audio_veille", BANC / "audio_veille.py")
av = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(av)

MAC = "40:9C:A7:00:00:01"
CASQUES = [(MAC, "M50", True), ("AC:80:0A:00:00:02", "Sony", False)]

# Extrait RÉEL (anonymisé) de `LANG=C pactl list sources` : une source, un moniteur.
PACTL_SOURCES = """Source #418
\tState: RUNNING
\tName: alsa_input.pci-0000_00_1f.3.analog-stereo
\tDescription: Audio interne Stéréo analogique
\tDriver: PipeWire
\tMute: no
\tVolume: front-left: 65536 / 100% / 0,00 dB
Source #430
\tState: SUSPENDED
\tName: bluez_input.40_9C_A7_00_00_01.0
\tDescription: M50
\tMute: yes
"""


def test_crete_s16():
    assert av.crete_s16(struct.pack("<4h", 3, -1200, 500, 0)) == 1200
    assert av.crete_s16(struct.pack("<h", -32768)) == 32768
    assert av.crete_s16(b"") == 0
    assert av.crete_s16(b"\x05") == 0          # octet impair seul : ignoré


def test_fenetre_horloge_injectee():
    f = av.Fenetre(duree_s=5.0)
    f.ajouter(10.0, 100)
    f.ajouter(12.0, 40)
    f.ajouter(14.9, 7)
    assert f.crete_depuis(15.0, 0.15) == 7
    assert f.crete_depuis(15.0, 3.0) == 40      # 12.0 compris, 10.0 trop vieux
    assert f.crete_depuis(15.0, 5.0) == 100
    f.ajouter(16.0, 1)                          # 10.0 sort de la fenêtre de 5 s
    assert f.crete_depuis(16.0, 10.0) == 40
    assert f.crete_depuis(30.0, 1.0) is None


def test_lire_noeuds_pactl():
    assert av.lire_noeuds_pactl(PACTL_SOURCES) == {
        "alsa_input.pci-0000_00_1f.3.analog-stereo": {"description": "Audio interne Stéréo analogique", "muet": False},
        "bluez_input.40_9C_A7_00_00_01.0": {"description": "M50", "muet": True},
    }
    assert av.lire_noeuds_pactl("") == {}


def test_decrire_cote_casque_par_mac():
    noeuds = av.lire_noeuds_pactl(PACTL_SOURCES)
    assert av.decrire_cote("bluez_input.40_9C_A7_00_00_01.0", "@DEFAULT_SOURCE@", "x", noeuds, CASQUES) == {
        "conf": "bluez_input.40_9C_A7_00_00_01.0", "suit_ubuntu": False,
        "pipewire": "bluez_input.40_9C_A7_00_00_01.0", "nom": "M50", "present": True, "muet": True,
        "casque": {"nom": "M50", "connecte": True}}


def test_decrire_cote_defaut_ubuntu_resolu():
    noeuds = av.lire_noeuds_pactl(PACTL_SOURCES)
    d = av.decrire_cote("@DEFAULT_SOURCE@", "@DEFAULT_SOURCE@", "alsa_input.pci-0000_00_1f.3.analog-stereo",
                        noeuds, CASQUES)
    assert (d["suit_ubuntu"], d["nom"], d["present"], d["muet"], d["casque"]) == (
        True, "Audio interne Stéréo analogique", True, False, None)


def test_decrire_cote_casque_eteint_absent():
    d = av.decrire_cote("bluez_output.AC_80_0A_00_00_02.1", "@DEFAULT_SINK@", None, {}, CASQUES)
    assert (d["present"], d["muet"], d["nom"], d["casque"]) == (
        False, None, "Sony", {"nom": "Sony", "connecte": False})


def test_etat_niveau_muet_seulement_apres_3_s_d_ecoute():
    f = av.Fenetre()
    for i in range(60):                        # 3 s de trames à 50 ms, crête 12 (< 30)
        f.ajouter(100.0 + i * 0.05, 12)
    # Ouvert à 99.0 : amorçage 0,6 s -> 2,35 s d'écoute à 101.95 : pas encore « muet ».
    assert av.etat_niveau(f, 101.95, 99.0, None)["muet_constate"] is False
    e = av.etat_niveau(f, 102.95, 99.0, None)
    assert e == {"crete": 12, "crete_3s": 12, "ecoute_s": 3.4, "muet_constate": True,
                 "seuil_vivant": 30, "erreur": None}
    f.ajouter(102.96, 30)                      # une crête au seuil : vivant
    assert av.etat_niveau(f, 102.97, 99.0, None)["muet_constate"] is False


def test_etat_niveau_ferme():
    assert av.etat_niveau(av.Fenetre(), 5.0, None, "aucun micro à écouter") == {
        "crete": None, "crete_3s": None, "ecoute_s": None, "muet_constate": False,
        "seuil_vivant": 30, "erreur": "aucun micro à écouter"}


def test_bip_wav():
    brut = av.bip_wav()
    with wave.open(io.BytesIO(brut)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 16000, 5600)
        trames = w.readframes(5600)
    ech = struct.unpack("<5600h", trames)
    assert ech[0] == 0 and ech[-1] == 0                   # rampes : pas de clic
    assert 9700 <= max(ech) <= 9830                       # 0,3 de la pleine échelle


def test_resume_sortie():
    assert av.resume_sortie("  court \n") == "court"
    long = "a" * 10 + "FIN"
    assert av.resume_sortie(long, maximum=5) == "…" + "aFIN"


class _Resultat:
    def __init__(self, code=0, stderr=b""):
        self.returncode, self.stderr = code, stderr


def test_tester_joue_par_la_chaine_de_la_voix(monkeypatch):
    lances = []

    def faux_run(cmd, **kw):
        lances.append((cmd, kw["input"][:4]))
        return _Resultat()

    monkeypatch.setattr(av.subprocess, "run", faux_run)
    v = av.Veille(sonde=lambda: {})
    v.photo = {"sortie": {"nom": "M50"}}
    assert v.tester() == {"ok": True, "message": "bip joué par la tête sur « M50 »"}
    assert lances == [(["docker", "exec", "-i", "didier-sim-vision", "aplay", "-q", "-D", "mixette", "-"], b"RIFF")]


def test_tester_rapporte_l_echec_de_la_tete(monkeypatch):
    monkeypatch.setattr(av.subprocess, "run", lambda cmd, **kw: _Resultat(1, b"aplay: Connection refused\n"))
    v = av.Veille(sonde=lambda: {})
    assert v.tester() == {"ok": False, "message": "bip non joué par la tête : aplay: Connection refused"}
    assert v.etat()["derniere_action"]["ok"] is False


def test_redetecter_lance_choisir_auto_sans_redemarrer(monkeypatch):
    lances = []
    fini = threading.Event()

    def faux_run(cmd, **kw):
        lances.append(cmd[1:])
        fini.set()
        return type("R", (), {"returncode": 0, "stdout": "Choix automatique : …\n", "stderr": ""})()

    monkeypatch.setattr(av.subprocess, "run", faux_run)
    v = av.Veille(sonde=lambda: {})
    assert v.redetecter() == {"ok": True, "message": "re-détection lancée"}
    assert fini.wait(2)
    for _ in range(100):
        if not v.etat()["redetection"]["en_cours"]:
            break
        threading.Event().wait(0.01)
    assert lances == [[str(BANC / "audio_banc.py"), "choisir", "auto", "--sans-redemarrer"]]
    r = v.etat()["redetection"]
    assert (r["en_cours"], r["code"], r["resume"]) == (False, 0, "Choix automatique : …")


def test_redetecter_refuse_un_doublon():
    v = av.Veille(sonde=lambda: {})
    v.redetection["en_cours"] = True
    assert v.redetecter() == {"ok": False, "message": "re-détection déjà en cours"}


def test_service_http_local(monkeypatch):
    """/etat sert l'état ; une route inconnue répond 404 (rien d'autre n'est exposé)."""
    v = av.Veille(sonde=lambda: {})
    serveur = av.ThreadingHTTPServer(("127.0.0.1", 0), av.fabriquer_gestionnaire(v))
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    try:
        base = "http://127.0.0.1:{}".format(serveur.server_address[1])
        etat = json.load(urllib.request.urlopen(base + "/etat", timeout=2))
        assert (etat["v"], etat["micro"], etat["photo_age_s"]) == (1, None, None)
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/autre", timeout=2)
        assert e.value.code == 404
    finally:
        serveur.shutdown()
