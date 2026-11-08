"""Tests du STT distant (OpenRouterStt) et du repli local (FallbackStt) —
didier_vision/ai/stt.py. Aucun appel réseau : faux clients injectés."""
import logging
import sys
import types

from didier_vision.ai.stt import FallbackStt, OpenRouterStt, pcm_to_wav_bytes
from didier_vision.vision_config import config


def test_wav_en_memoire_entete_grave():
    wav = pcm_to_wav_bytes(b"\x01\x00\x02\x00", 16000)
    # RIFF, taille, WAVE, fmt PCM mono 16 kHz 16 bits, data de 4 octets.
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    assert wav[22:24] == b"\x01\x00"                  # 1 canal
    assert wav[24:28] == (16000).to_bytes(4, "little")
    assert wav[34:36] == b"\x10\x00"                  # 16 bits
    assert wav[-4:] == b"\x01\x00\x02\x00" and len(wav) == 48


class _FakeTranscriptions:
    def __init__(self, text):
        self.text, self.calls = text, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return types.SimpleNamespace(text=self.text)


def _fake_client(text):
    tr = _FakeTranscriptions(text)
    return types.SimpleNamespace(audio=types.SimpleNamespace(transcriptions=tr)), tr


def test_openrouter_stt_envoie_modele_langue_et_wav():
    client, tr = _fake_client("  Bonjour Didier.  ")
    stt = OpenRouterStt(model="mistralai/voxtral-mini-transcribe", base_url="https://x",
                        client_factory=lambda: client)
    assert stt.transcribe(b"\x00\x00" * 10, 16000) == "Bonjour Didier."
    call = tr.calls[0]
    assert call["model"] == "mistralai/voxtral-mini-transcribe"
    assert call["language"] == "fr"
    name, data, mime = call["file"]
    assert (name, mime) == ("parole.wav", "audio/wav") and data[:4] == b"RIFF"
    assert "prompt" not in call     # vocabulaire sans effet mesuré : pas envoyé


def test_client_par_defaut_sans_nouvel_essai(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setattr("didier_vision.ai.stt.get_secret", lambda name: f"clé-{name}")
    OpenRouterStt(model="m", base_url="https://or", timeout_s=4.0)._get_client()
    assert captured == {"base_url": "https://or", "api_key": "clé-openrouter_key",
                        "timeout": 4.0, "max_retries": 0}


class _Stt:
    def __init__(self, text="", fail=False):
        self.text, self.fail, self.calls = text, fail, 0

    def transcribe(self, pcm, rate):
        self.calls += 1
        if self.fail:
            raise TimeoutError("liaison 4G morte")
        return self.text


def test_repli_principal_ok():
    primary, local = _Stt("distant"), _Stt("local")
    assert FallbackStt(primary, local).transcribe(b"", 16000) == "distant"
    assert local.calls == 0


def test_repli_texte_vide_n_est_pas_un_echec():
    primary, local = _Stt(""), _Stt("local")
    assert FallbackStt(primary, local).transcribe(b"", 16000) == ""
    assert local.calls == 0


def test_repli_sur_exception_avec_warning(caplog):
    primary, local = _Stt(fail=True), _Stt("local")
    with caplog.at_level(logging.WARNING, logger="didier_vision.ai.stt"):
        assert FallbackStt(primary, local).transcribe(b"", 16000) == "local"
    assert caplog.records[0].message == ("STT distant en échec (liaison 4G morte) — "
                                         "repli sur le STT local.")


def test_mise_de_cote_apres_deux_echecs_puis_retour():
    t = [0.0]
    primary, local = _Stt(fail=True), _Stt("local")
    stt = FallbackStt(primary, local, clock=lambda: t[0])
    stt.transcribe(b"", 16000)            # échec 1
    t[0] = 5.0
    stt.transcribe(b"", 16000)            # échec 2 → local seul 60 s
    t[0] = 64.9
    stt.transcribe(b"", 16000)
    assert primary.calls == 2             # pas réessayé pendant la mise de côté
    t[0] = 65.0
    primary.fail, primary.text = False, "revenu"
    assert stt.transcribe(b"", 16000) == "revenu"
    assert primary.calls == 3 and local.calls == 3


def test_config_stt_valeurs_gravees():
    assert config["chat_stt_backend"] == "openrouter"
    assert config["chat_stt_remote_model"] == "mistralai/voxtral-mini-transcribe"
    assert config["chat_stt_timeout_s"] == 4.0
