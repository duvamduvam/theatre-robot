"""Reconnaissance vocale (STT) — interface + implémentation faster-whisper locale.

QUOI le Protocol SttEngine : point de swap explicite. Ce module fixe le
      CONTRAT (pcm + sample_rate -> texte), pas l'implémentation — la
      migration prévue vers whisper_ros (V3, cf. ARCHITECTURE.md) n'aura qu'à
      fournir une nouvelle classe respectant ce même Protocol, sans toucher à
      vision.ai.conversation (qui ne connaît que l'interface, injectée au
      constructeur de ConversationEngine). FasterWhisperStt est le choix
      RETENU pour V2 (local, pas d'appel réseau ni de latence API), mais n'est
      pas la seule implémentation possible.
POURQUOI l'import faster_whisper est DIFFÉRÉ (dans __init__, pas en tête de
      module) : faster_whisper n'est PAS dans requirements-test.txt (poids/
      compilation ARM hors du périmètre CI) — un import en tête de module
      casserait la collecte pytest en CI dès qu'un autre fichier importe
      vision.ai.stt (même sans jamais instancier FasterWhisperStt).
"""
from __future__ import annotations

import io
import logging
import os
import tempfile
import time
import wave
from typing import Callable, Optional, Protocol

from vision.vision_config import get_secret

logger = logging.getLogger(__name__)


class SttEngine(Protocol):
    """Contrat minimal attendu par vision.ai.conversation.ConversationEngine."""

    def transcribe(self, pcm: bytes, sample_rate: int) -> str:
        ...


class FasterWhisperStt:
    """STT local via faster-whisper (backend CTranslate2, CPU int8 — cible
    Raspberry Pi, pas de GPU)."""

    def __init__(self, model_name: str = "base", language: str = "fr"):
        # Import différé : voir docstring de module.
        from faster_whisper import WhisperModel

        # device="cpu" + compute_type="int8" : seule combinaison réaliste sur
        # un Pi (pas de CUDA) — int8 réduit la mémoire/latence au prix d'une
        # légère perte de précision, acceptable pour des réponses courtes
        # scéniques (cf. AI_REALTIME_RULES).
        self._model = WhisperModel(model_name, device="cpu", compute_type="int8")
        self._language = language

    def transcribe(self, pcm: bytes, sample_rate: int) -> str:
        # faster-whisper attend un chemin de fichier (ou un tableau numpy) :
        # on passe par un wav temporaire, le plus simple pour rester
        # cohérent avec le reste du repo (vision.audio.playback fait de même).
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            with wave.open(path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(pcm)

            # beam_size=1 : recherche gloutonne (pas de beam search) — plus
            # rapide, seul compromis tenable pour une latence scénique
            # acceptable (proto validé du 10/07) ; la qualité perdue est
            # marginale sur des énoncés courts.
            segments, _ = self._model.transcribe(path, language=self._language, beam_size=1)
            return " ".join(segment.text.strip() for segment in segments).strip()
        finally:
            try:
                os.remove(path)
            except OSError:
                pass


def pcm_to_wav_bytes(pcm: bytes, sample_rate: int) -> bytes:
    """PCM 16 bits mono -> fichier WAV complet en mémoire (ce qu'attend
    l'API /audio/transcriptions). 16 bits : c'est le format de MicCapture
    (même en-tête que FasterWhisperStt). ⚠️ Piège payé le 23/10 au banc : un
    flux 32 bits réécrit avec un en-tête 16 bits donne du bruit, et le
    modèle distant rend alors "" sans aucune erreur."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return buf.getvalue()


class OpenRouterStt:
    """STT DISTANT via OpenRouter (/audio/transcriptions, compatible OpenAI).

    POURQUOI (demande de David, 23/10 : « c'est vraiment crucial que je
    puisse être compris correctement ») : banc du 23/10 sur ses
    enregistrements (essais/voix/audio, voix de ventriloque — biais connu),
    Voxtral rend les phrases les plus complètes et les plus justes, en
    0,5-1,8 s, et rend "" sur un passage inintelligible au lieu d'inventer
    (whisper-large-v3 y hallucinait « Sous-titrage ST' 501 », gpt-4o-
    transcribe coupait la 2e prise). faster-whisper base (Pi) : 3,6-5,2 s et
    nettement plus d'erreurs. Le paramètre `prompt` (vocabulaire) est
    accepté mais sans effet mesuré : pas envoyé.

    Import openai DIFFÉRÉ et client paresseux, même patron que
    vision.ai.llm_stream.StreamingBrain (testable sans openai ni secret)."""

    def __init__(self, model: str, base_url: str, api_key_name: str = "openrouter_key",
                 language: str = "fr", timeout_s: float = 4.0, client_factory=None):
        self._model = model
        self._base_url = base_url
        self._api_key_name = api_key_name
        self._language = language
        self._timeout_s = timeout_s
        self._client_factory = client_factory
        self._client = None

    def _get_client(self):
        if self._client is None:
            if self._client_factory is not None:
                self._client = self._client_factory()
            else:
                from openai import OpenAI  # import différé, cf. docstring de module

                # max_retries=0 : un essai raté doit basculer TOUT DE SUITE sur
                # le STT local (FallbackStt) — le défaut du SDK (2 nouveaux
                # essais) ferait attendre jusqu'à 3 × timeout_s un humain qui
                # vient de parler.
                self._client = OpenAI(base_url=self._base_url,
                                      api_key=get_secret(self._api_key_name),
                                      timeout=self._timeout_s, max_retries=0)
        return self._client

    def transcribe(self, pcm: bytes, sample_rate: int) -> str:
        result = self._get_client().audio.transcriptions.create(
            model=self._model,
            file=("parole.wav", pcm_to_wav_bytes(pcm, sample_rate), "audio/wav"),
            language=self._language,
        )
        return (getattr(result, "text", "") or "").strip()


class FallbackStt:
    """STT principal (distant) avec REPLI automatique sur un STT local.

    Toute exception du principal (réseau coupé, 4G saturée en festival,
    quota, timeout) → warning + transcription locale du MÊME énoncé : Didier
    reste compréhensif, juste moins bien. Après `failures_before_cooldown`
    échecs CONSÉCUTIFS, le principal est mis de côté `cooldown_s` secondes
    (local seul) : sans ça, une liaison morte coûterait timeout_s de silence
    en plus à CHAQUE réplique. Un "" du principal n'est PAS un échec (c'est
    la bonne réponse à un bruit)."""

    def __init__(self, primary, fallback, failures_before_cooldown: int = 2,
                 cooldown_s: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self._primary = primary
        self._fallback = fallback
        self._failures_before_cooldown = failures_before_cooldown
        self._cooldown_s = cooldown_s
        self._clock = clock
        self._failures = 0
        self._cooldown_until: Optional[float] = None

    def transcribe(self, pcm: bytes, sample_rate: int) -> str:
        now = self._clock()
        if self._cooldown_until is not None and now < self._cooldown_until:
            return self._fallback.transcribe(pcm, sample_rate)
        try:
            text = self._primary.transcribe(pcm, sample_rate)
        except Exception as exc:  # noqa: BLE001 — toute panne distante = repli
            self._failures += 1
            if self._failures >= self._failures_before_cooldown:
                self._cooldown_until = now + self._cooldown_s
                logger.warning("STT distant en échec %d fois de suite (%s) — STT local "
                               "seul pendant %.0f s.", self._failures, exc, self._cooldown_s)
            else:
                logger.warning("STT distant en échec (%s) — repli sur le STT local.", exc)
            return self._fallback.transcribe(pcm, sample_rate)
        if self._failures or self._cooldown_until is not None:
            logger.info("STT distant rétabli.")
        self._failures = 0
        self._cooldown_until = None
        return text
