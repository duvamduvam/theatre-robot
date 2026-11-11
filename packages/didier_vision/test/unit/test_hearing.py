"""« Oreille de Didier » (didier_vision.ai.hearing) + source du STT (FallbackStt.last_source).
Valeurs gravées."""
import json
from pathlib import Path

from didier_vision.ai.hearing import asound_targets, describe_chain, encode_chain, encode_hearing
from didier_vision.ai.stt import FallbackStt

# L1e-4c (11/11) : le banc PC de la vision est machines/sim/banc-vision/.
BANC = Path(__file__).resolve().parents[4] / "machines" / "sim" / "banc-vision"


def test_asound_targets_vrai_fichier_banc():
    t = asound_targets((BANC / "asound-pc.conf").read_text(encoding="utf-8"))
    assert t["micro"] and t["sortie"] and t["gain"] is not None


def test_asound_targets_pi_sans_device():
    assert asound_targets("pcm.casque_mic { type plug slave.pcm \"hw:Array\" }") == \
        {"micro": None, "sortie": None, "gain": None}


def test_describe_chain_distant_et_local():
    a = {"micro": "bluez_input.X", "sortie": "bluez_output.X", "gain": 0.15}
    c = describe_chain(mic_device="casque_mic", out_device="mixette", asound=a, stt_backend="openrouter",
                       stt_remote_model="mistralai/voxtral-mini-transcribe", whisper_model="small",
                       vad_factor=6, llm_model="anthropic/claude-haiku", persona="mauvaisefoi")
    assert c["transcription"] == "mistralai/voxtral-mini-transcribe (distant, OpenRouter)"
    assert c["repli"] == "whisper small (local)"
    assert c["micro"] == "bluez_input.X" and c["attenuation_micro"] == 0.15
    assert c["detection_parole"] == "VAD énergie, facteur 6"
    l = describe_chain(mic_device="casque_mic", out_device="mixette", asound={}, stt_backend="local",
                       stt_remote_model="m", whisper_model="base", vad_factor=1.3, llm_model="x", persona="bougon")
    assert l["transcription"] == "whisper base (local)" and l["repli"] is None and l["micro"] == "casque_mic"
    assert json.loads(encode_chain(l))["sortie"] == "mixette"


def test_encode_hearing():
    h = json.loads(encode_hearing({"stt_text": "Salut, dis-y-ais !", "stt_ms": 812.4, "total_ms": 2101.6,
                                   "abandoned": False}, "distant", 1000))
    assert h == {"t_ms": 1000, "entendu": "Salut, dis-y-ais !", "moteur": "distant", "stt_ms": 812,
                 "reponse_ms": 2102, "verdict": "gardé"}
    h = json.loads(encode_hearing({"stt_text": "...", "stt_ms": 300, "abandoned": True}, "repli", 1))
    assert h["verdict"] == "jeté : rien de compréhensible" and h["moteur"] == "REPLI local (le distant a échoué)"
    assert h["reponse_ms"] is None
    h = json.loads(encode_hearing({"stt_text": "stop", "abandoned": True}, None, 1))
    assert h["verdict"].startswith("jeté (") and h["moteur"] == "local"


class _Ok:
    def transcribe(self, pcm, sr): return "ok"


class _Ko:
    def transcribe(self, pcm, sr): raise RuntimeError("réseau")


def test_fallback_last_source():
    t = [0.0]
    f = FallbackStt(_Ok(), _Ok(), clock=lambda: t[0])
    assert f.last_source is None
    f.transcribe(b"", 16000); assert f.last_source == "distant"
    g = FallbackStt(_Ko(), _Ok(), failures_before_cooldown=2, cooldown_s=60, clock=lambda: t[0])
    g.transcribe(b"", 16000); assert g.last_source == "repli"
    g.transcribe(b"", 16000); assert g.last_source == "repli"      # 2e échec -> cooldown armé
    g.transcribe(b"", 16000); assert g.last_source == "local-pause"
