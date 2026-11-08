"""Détection d'activité vocale (VAD) par énergie — logique PURE, stdlib
UNIQUEMENT (enum/dataclasses/statistics), testable en CI sans pyaudio/numpy.

QUOI : machine à états CALIBRATING -> IDLE <-> SPEECH. Le calcul du niveau
       sonore par frame (RMS/énergie d'un buffer micro) reste hors de ce
       module (côté didier_vision/nodes/chat_node.py, V2) — EnergyVad ne reçoit que
       des `float` déjà calculés, ce qui le rend testable avec des séquences
       de niveaux en dur, sans micro ni pyaudio.
POURQUOI un seuil calibré et non fixe : le bruit de fond (ventilo Pi, salle)
       varie d'un lieu à l'autre — une calibration au démarrage (médiane des
       niveaux pendant calibration_ms) rend le seuil robuste au silence ambiant
       réel plutôt qu'à une valeur magique choisie en atelier.
"""
from __future__ import annotations

import enum
import statistics
from dataclasses import dataclass
from typing import List, Optional


class VadState(enum.Enum):
    CALIBRATING = "calibrating"
    IDLE = "idle"
    SPEECH = "speech"


@dataclass(frozen=True)
class VadConfig:
    # Multiplicateur appliqué au plancher de bruit calibré pour obtenir le
    # seuil de déclenchement — 1.3 : marge modeste validée sur le prototype
    # (trop haut = rate les débuts de phrase doux, trop bas = déclenche sur
    # le bruit de fond lui-même).
    threshold_factor: float = 1.3
    # Fenêtre de pré-roll à restituer depuis un ring buffer côté appelant :
    # capte le tout début de la phrase, souvent mangé par les 3 frames de
    # confirmation ci-dessous (cf. EnergyVad.feed).
    preroll_ms: int = 450
    # Silence continu requis pour considérer la phrase terminée.
    end_silence_ms: int = 600
    # Durée de la calibration initiale (mesure du bruit de fond).
    calibration_ms: int = 1000
    # Garde-fou : coupe une phrase qui n'en finit pas (micro resté ouvert,
    # bruit continu mal filtré) plutôt que de streamer indéfiniment vers l'API.
    max_utterance_ms: int = 12000
    # Plancher absolu du seuil même si la calibration mesure un silence quasi
    # nul (micro très silencieux) — évite un seuil ~0 qui déclencherait sur le
    # moindre souffle.
    min_floor: float = 1.0


@dataclass(frozen=True)
class VadEvent:
    kind: str  # "speech_start" | "speech_end"
    preroll_frames: int = 0   # pertinent seulement pour "speech_start"
    reason: str = "silence"   # pertinent seulement pour "speech_end" : "silence" | "max_duration"


# Nombre de frames consécutives au-dessus du seuil requises pour confirmer un
# début de parole — évite de déclencher sur un pic isolé (toux, clic).
_FRAMES_TO_CONFIRM_SPEECH = 3


class EnergyVad:
    """Machine à états VAD par énergie, ré-armable (plusieurs tours de parole
    successifs sans recréer l'instance — seule la calibration initiale est à
    usage unique)."""

    def __init__(self, config: VadConfig, frame_ms: int):
        self._config = config
        self._frame_ms = frame_ms

        self._state = VadState.CALIBRATING
        self._calib_levels: List[float] = []
        self._calib_elapsed_ms = 0
        self._threshold: Optional[float] = None

        self._consecutive_above = 0
        self._consecutive_below_ms = 0
        self._speech_elapsed_ms = 0

    @property
    def state(self) -> VadState:
        return self._state

    @property
    def threshold(self) -> Optional[float]:
        """None pendant la calibration (pas encore de seuil déterminé)."""
        return self._threshold

    @property
    def floor_threshold(self) -> float:
        """Seuil PLANCHER de la config (min_floor × threshold_factor) — celui
        qu'une calibration sur un silence parfait donnerait. Plancher prudent
        de l'écoute garde quand l'écoute normale n'a pas encore de seuil
        (seconde revue du 31/10, mineur 4) : mieux vaut une garde trop
        sensible (elle transcrit l'écho, sans effet hors mot d'arrêt) qu'une
        garde calibrée sur la voix de Didier, donc sourde à David."""
        return self._config.min_floor * self._config.threshold_factor

    def feed(self, level: float) -> Optional[VadEvent]:
        """Traite le niveau sonore d'UNE frame. Retourne un VadEvent si un
        changement d'état se produit (début/fin de parole), None sinon."""
        if self._state is VadState.CALIBRATING:
            return self._feed_calibrating(level)
        if self._state is VadState.IDLE:
            return self._feed_idle(level)
        return self._feed_speech(level)

    def _feed_calibrating(self, level: float) -> Optional[VadEvent]:
        self._calib_levels.append(level)
        self._calib_elapsed_ms += self._frame_ms
        if self._calib_elapsed_ms >= self._config.calibration_ms:
            # Médiane plutôt que moyenne : insensible à un pic isolé pendant
            # la fenêtre de calibration (bruit externe ponctuel).
            median = statistics.median(self._calib_levels) if self._calib_levels else 0.0
            floor = max(median, self._config.min_floor)
            self._threshold = floor * self._config.threshold_factor
            self._state = VadState.IDLE
        return None

    def _feed_idle(self, level: float) -> Optional[VadEvent]:
        if level > self._threshold:
            self._consecutive_above += 1
        else:
            self._consecutive_above = 0

        if self._consecutive_above < _FRAMES_TO_CONFIRM_SPEECH:
            return None

        self._state = VadState.SPEECH
        self._consecutive_above = 0
        self._consecutive_below_ms = 0
        self._speech_elapsed_ms = 0
        preroll_frames = self._config.preroll_ms // self._frame_ms
        return VadEvent(kind="speech_start", preroll_frames=preroll_frames)

    def _feed_speech(self, level: float) -> Optional[VadEvent]:
        self._speech_elapsed_ms += self._frame_ms

        if level > self._threshold:
            # Un niveau au-dessus du seuil interrompt le compteur de silence :
            # une retombée brève (respiration, micro-pause) ne doit PAS couper
            # la phrase — seul un silence CONTINU de end_silence_ms coupe.
            self._consecutive_below_ms = 0
        else:
            self._consecutive_below_ms += self._frame_ms

        # max_duration prioritaire sur silence si les deux seuils sont
        # atteints à la même frame : c'est le garde-fou le plus dur, il ne
        # doit jamais être masqué par la détection de silence.
        if self._speech_elapsed_ms >= self._config.max_utterance_ms:
            self._reset_to_idle()
            return VadEvent(kind="speech_end", reason="max_duration")

        if self._consecutive_below_ms >= self._config.end_silence_ms:
            self._reset_to_idle()
            return VadEvent(kind="speech_end", reason="silence")

        return None

    def _reset_to_idle(self) -> None:
        """Repart en IDLE, ré-armé pour un futur speech_start — le seuil
        calibré est conservé (une seule calibration par instance)."""
        self._state = VadState.IDLE
        self._consecutive_above = 0
        self._consecutive_below_ms = 0
        self._speech_elapsed_ms = 0

    def reset(self) -> None:
        """Version PUBLIQUE de `_reset_to_idle`, pour un appelant externe qui
        vient d'invalider les trames en cours (cf. gate « source audio
        vivante », dadou_robot_ros/docs/etude-declenchement-conversation.md
        §10.5) : un blocage du gate en pleine phrase jette l'énoncé côté
        ConversationEngine, mais SANS ce reset, la VAD resterait en SPEECH et
        attendrait son `end_silence_ms` sur des trames qu'elle ne reçoit plus
        (le gate les jette avant qu'elles n'atteignent feed()) — la phrase
        SUIVANTE, légitime, ne déclencherait donc jamais de nouveau
        speech_start.

        No-op pendant CALIBRATING : il n'y a pas encore de seuil déterminé,
        rien à "remettre à IDLE" — appeler reset() ici casserait la mesure du
        bruit de fond en cours sans aucun bénéfice (le seuil est à usage
        unique, cf. docstring de module)."""
        if self._state is not VadState.CALIBRATING:
            self._reset_to_idle()

    def adopt_threshold(self, threshold: Optional[float]) -> None:
        """Reprend un seuil DÉJÀ calibré par une autre instance (même config)
        et repart en IDLE, sans calibration propre. Sert à l'écoute GARDE de
        didier_vision.ai.conversation (arrêt d'urgence pendant une réplique, 31/10) :
        elle tourne PENDANT que Didier parle — calibrer sur cette fenêtre
        mesurerait sa propre voix comme « bruit de fond » (seuil trop haut =
        un « Stop ! » de David ignoré, sans que rien ne le signale). Le seuil
        de l'écoute normale, mesuré sur le silence ambiant, est le bon.

        None (l'autre instance n'a pas encore fini sa calibration) = no-op :
        cette instance garde son propre état (calibration en cours ou seuil
        déjà adopté auparavant)."""
        if threshold is None:
            return
        self._threshold = threshold
        self._calib_levels = []
        self._calib_elapsed_ms = 0
        self._reset_to_idle()
