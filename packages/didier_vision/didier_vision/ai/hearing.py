"""« Oreille de Didier » — ce qu'il a entendu, par quel moteur, et le
branchement complet du son (micro -> transcription -> réponse -> voix).
Logique PURE (stdlib + vision_config), testée sans ROS.

POURQUOI (31/10, David en séance : « je dis salut Didier et ça part de travers,
quel est le branchement transcription ? je veux que ce soit visible sur le
site ») : la chaîne avait au moins trois réglages invisibles qui changent ce
que Didier comprend — le casque réellement ouvert, l'atténuation du micro, le
moteur de transcription (Voxtral distant ou whisper local, et le repli de l'un
sur l'autre). Le même jour, le banc tournait du code du 22/10 SANS Voxtral et
personne ne pouvait le voir. Deux messages pour la page scène :
  - chat_audio_chain (latché, une fois au démarrage) : le BRANCHEMENT ;
  - chat_hearing (un par tour) : ce qui a été ENTENDU et par qui, gardé ou jeté.
"""
from __future__ import annotations

import json
import re
from typing import Optional

# Libellés lisibles des sources de FallbackStt.last_source (didier_vision.ai.stt).
SOURCE_LABELS = {
    "distant": "distant",
    "repli": "REPLI local (le distant a échoué)",
    "local-pause": "local (distant en pause après échecs)",
    "local": "local",
}


def asound_targets(asound_text: str) -> dict:
    """Lit dans /etc/asound.conf (banc PC) les cibles PipeWire des alias de
    Didier et l'atténuation du micro. -> {"micro", "sortie", "gain"} ; une
    valeur absente reste None (sur le Pi, les alias visent des cartes ALSA
    par nom : pas de ligne `device` -> None, et c'est normal)."""
    def device(bloc: str) -> Optional[str]:
        m = re.search(re.escape(bloc) + r"\s*\{[^}]*?device\s+\"([^\"]*)\"", asound_text, re.S)
        return m.group(1) if m else None
    g = re.search(r"ttable\.0\.0\s+([0-9.]+)", asound_text)
    return {"micro": device("pcm.casque_mic_bt"), "sortie": device("pcm.mixette"),
            "gain": float(g.group(1)) if g else None}


def describe_chain(*, mic_device: str, out_device: str, asound: dict, stt_backend: str,
                   stt_remote_model: str, whisper_model: str, vad_factor: float,
                   llm_model: str, persona: str) -> dict:
    """Le branchement complet, dans l'ordre où le son le traverse."""
    if stt_backend == "openrouter":
        stt = f"{stt_remote_model} (distant, OpenRouter)"
        repli = f"whisper {whisper_model} (local)"
    else:
        stt = f"whisper {whisper_model} (local)"
        repli = None
    return {
        "micro": asound.get("micro") or mic_device,
        "attenuation_micro": asound.get("gain"),
        "detection_parole": f"VAD énergie, facteur {vad_factor:g}",
        "transcription": stt,
        "repli": repli,
        "reponse": f"{llm_model} — persona {persona}",
        "voix": "piper (local)",
        "sortie": asound.get("sortie") or out_device,
    }


def encode_chain(chain: dict) -> str:
    return json.dumps(chain, ensure_ascii=False, sort_keys=True)


def encode_hearing(timing: dict, source: Optional[str], t_ms: int) -> str:
    """Un tour : ce qui a été entendu, par qui, en combien de temps, gardé ou
    jeté (et pourquoi). `timing` = dict on_timing de ConversationEngine."""
    text = timing.get("stt_text") or ""
    abandoned = bool(timing.get("abandoned"))
    if not abandoned:
        verdict = "gardé"
    elif not text.strip(" .…!?") :
        verdict = "jeté : rien de compréhensible"
    else:
        verdict = "jeté (arrêt d'urgence ou panne de scène)"
    def ms(k):
        v = timing.get(k)
        return None if v is None else int(round(v))
    return json.dumps({
        "t_ms": int(t_ms), "entendu": text, "moteur": SOURCE_LABELS.get(source or "local", source),
        "stt_ms": ms("stt_ms"), "reponse_ms": ms("total_ms"), "verdict": verdict,
    }, ensure_ascii=False, sort_keys=True)
