"""Capture micro — I/O PURE (subprocess + tampon), AUCUNE logique VAD ici.

QUOI : lance `arecord` en sous-processus (flux S16_LE mono brut sur stdout),
       lit des trames de taille fixe (frame_ms), et garde les `preroll_frames`
       dernières dans un ring buffer (deque). Le calcul du niveau sonore
       (RMS) est fourni ICI (frame_rms) car c'est une opération triviale sur
       les octets d'UNE trame, mais la MACHINE À ÉTATS qui décide "c'est de
       la parole ou pas" reste entièrement dans didier_vision.audio.vad.EnergyVad
       (déjà pure/testée) — ce module ne fait qu'alimenter cette machine en
       niveaux, il ne décide jamais rien lui-même.
POURQUOI subprocess arecord plutôt que pyaudio/sounddevice : le proto validé
       (cf. CLAUDE.md du 10/07) tourne déjà avec cet outil en ligne de
       commande sur le Pi 5, pas de dépendance Python supplémentaire à faire
       compiler sur ARM (pyaudio nécessite portaudio-dev, déjà une dépendance
       existante ailleurs dans le repo — inutile d'en rajouter une deuxième
       voie pour la même chose).
POURQUOI run_cmd injectable : permet aux tests de remplacer
       subprocess.Popen par un faux processus (stdout = io.BytesIO ou
       équivalent scripté) SANS jamais lancer arecord pour de vrai — la CI
       n'a ni le binaire arecord ni de périphérique audio.
"""
from __future__ import annotations

import subprocess
import threading
from collections import deque
from typing import Optional

import numpy as np

# Largeur d'un échantillon S16_LE mono : 2 octets. Utilisé pour convertir
# frame_ms (durée) en taille de trame en OCTETS (taille exacte lue à chaque
# read_frame(), condition de détection de flux mort ci-dessous).
_BYTES_PER_SAMPLE = 2


def frame_peak(frame: bytes) -> float:
    """Crête absolue (max des |échantillon|) d'une trame S16_LE mono —
    fonction PURE extraite de MicCapture (exposée en méthode liée ci-dessous,
    même patron que `frame_rms` juste en dessous, POUR LA MÊME RAISON :
    didier_vision.audio.vad_replay doit rejouer un enregistrement de rue à travers
    le MÊME calcul que la prod).

    POURQUOI la crête en plus du RMS (cf. dadou_robot_ros/docs/
    etude-declenchement-conversation.md §10.3/§10.4) : c'est la mesure que
    consomme didier_vision.audio.live_audio_gate.LiveAudioGate pour détecter
    l'ÉCRÊTAGE (l'entrée sature quand la voix HF de David passe par la
    sono) — un signal peut écrêter en gardant un RMS moyen sous le seuil de
    niveau (une syllabe forte isolée au milieu d'un silence), donc les deux
    mesures sont complémentaires, jamais interchangeables."""
    if not frame:
        return 0.0
    samples = np.frombuffer(frame, dtype=np.int16)
    return float(np.max(np.abs(samples)))


def frame_rms(frame: bytes) -> float:
    """Niveau sonore RMS (racine de la moyenne des carrés) d'une trame S16_LE
    mono — la mesure attendue par didier_vision.audio.vad.EnergyVad.feed.

    QUOI : fonction PURE extraite de MicCapture (qui l'expose en méthode liée
           ci-dessous pour ne rien casser côté ConversationEngine, cf.
           didier_vision.ai.conversation._listen_for_utterance : self._mic.frame_rms(frame))
           POURQUOI extraite (lot D0 outillage, cf. dadou_robot_ros/docs/
           etude-declenchement-conversation.md §5.5/§7, D0 = mesures &
           calibration) : didier_vision.audio.vad_replay DOIT réutiliser EXACTEMENT
           le même calcul que la prod (règle du projet, cf. CLAUDE.md
           "la vérification doit exécuter le MÊME code que la prod") — une
           fonction pure importable évite de dupliquer la formule dans l'outil
           de rejeu, ce qui aurait pu diverger silencieusement de MicCapture."""
    if not frame:
        return 0.0
    samples = np.frombuffer(frame, dtype=np.int16).astype(np.float64)
    return float(np.sqrt(np.mean(samples ** 2)))


class MicCapture:
    """Capture continue d'un micro ALSA via `arecord`, découpée en trames de
    taille fixe, avec un tampon de pré-roll (les N dernières trames)."""

    def __init__(self, device: str, sample_rate: int = 16000, frame_ms: int = 30,
                 preroll_frames: int = 15, run_cmd=None):
        self._device = device
        self.sample_rate = sample_rate
        self._frame_ms = frame_ms
        # Taille exacte d'une trame en octets : sample_rate * frame_ms / 1000
        # échantillons, * 2 octets/échantillon (S16_LE mono).
        self._frame_bytes = int(round(sample_rate * frame_ms / 1000)) * _BYTES_PER_SAMPLE
        # run_cmd par défaut = subprocess.Popen ; les tests injectent un faux
        # process (stdout scripté) pour ne jamais dépendre du binaire arecord.
        self._run_cmd = run_cmd or subprocess.Popen
        self._process = None
        # start()/stop() appelés par TROIS threads (seconde revue du 31/10) :
        # conversation, lecteur de l'écoute garde, callback ROS chat OFF
        # (chat_node._on_chat_cmd). Sans verrou, un stop() pouvait trouver
        # `_process` non-None puis None entre deux lignes (AttributeError
        # non rattrapée côté ROS) ou un start() doubler arecord.
        self._lock = threading.Lock()
        # maxlen=preroll_frames : deque borné, les trames les plus anciennes
        # sortent automatiquement quand le tampon déborde — pas de gestion
        # manuelle de taille nécessaire.
        self._ring: deque = deque(maxlen=preroll_frames)

    def start(self) -> None:
        """Lance `arecord` si aucun flux n'est déjà en cours (idempotent —
        évite de doubler le processus si start() est appelé deux fois de
        suite, ce qui arrive dans le déroulé normal d'un tour, cf.
        didier_vision.ai.conversation)."""
        with self._lock:
            self._start_locked()

    def _start_locked(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return  # déjà en cours

        cmd = [
            "arecord", "-q",
            "-D", self._device,
            "-f", "S16_LE",
            "-r", str(self.sample_rate),
            "-c", "1",
            "-t", "raw",
        ]
        self._process = self._run_cmd(cmd, stdout=subprocess.PIPE)

    def stop(self) -> None:
        """Coupe le flux micro et PURGE le ring buffer.

        PIÈGE (documenté, cf. spec) : la purge est volontaire, pas un oubli.
        stop() est appelé juste avant que Didier ne parle (anti-larsen) — si
        le tampon de pré-roll survivait au redémarrage suivant, un restart
        rapide pourrait faire réapparaître dans le pré-roll du PROCHAIN tour
        des trames captées juste avant l'arrêt (potentiellement la toute fin
        de la voix de Didier elle-même, via la sortie haut-parleur captée par
        le micro). Purger à chaque stop() garantit que le pré-roll du tour
        suivant ne contient QUE de l'audio capté après le redémarrage."""
        with self._lock:
            process, self._process = self._process, None
            if process is not None:
                process.terminate()
                if hasattr(process, "wait"):
                    process.wait()
        self.purge_preroll()

    def purge_preroll(self) -> None:
        """Vide le ring buffer de pré-roll — extrait de `stop()` ci-dessus
        (qui continue de l'appeler, cf. son docstring pour le POURQUOI
        initial) pour être réutilisé par le gate « source audio vivante »
        (cf. didier_vision.ai.conversation._listen_for_utterance et
        dadou_robot_ros/docs/etude-declenchement-conversation.md §10.5) :
        une trame bloquée par le gate (sono/HF vivant, séquence de spectacle)
        ne doit JAMAIS pouvoir réapparaître dans le pré-roll du PROCHAIN
        énoncé accepté — exactement le même risque que celui documenté dans
        stop(), pour la même raison, mais déclenché par un AUTRE événement
        (un blocage du gate, pas un stop() complet du flux)."""
        self._ring.clear()

    def read_frame(self) -> Optional[bytes]:
        """Lit UNE trame de taille fixe depuis le flux micro.

        Retourne None si le flux est mort (process jamais démarré, ou stdout
        renvoie moins d'octets que la taille de trame attendue — cas normal
        d'un pipe bufferisé : read(n) ne renvoie moins de n qu'à l'EOF réel).
        """
        # `_process` lu UNE seule fois (pas de verrou ici : read() bloque une
        # trame entière, il ne doit pas retenir start/stop) — un stop()
        # concurrent le remet à None, la copie locale reste valable et son
        # flux rend EOF.
        process = self._process
        stdout = process.stdout if process is not None else None
        if stdout is None:
            return None

        data = stdout.read(self._frame_bytes)
        if not data or len(data) < self._frame_bytes:
            return None

        # Le ring buffer est mis à jour AVANT de retourner la trame : preroll()
        # appelé juste après un read_frame() inclut donc cette trame comme
        # entrée la plus récente (cf. docstring preroll() ci-dessous — c'est
        # voulu, ça évite tout doublon côté appelant qui accumulerait
        # preroll() + frame).
        self._ring.append(data)
        return data

    def frame_rms(self, frame: bytes) -> float:
        """Méthode liée qui délègue à la fonction pure module-level
        `frame_rms` ci-dessus (cf. son docstring POURQUOI) — conservée pour
        ne rien changer côté appelants existants (self._mic.frame_rms(frame),
        cf. didier_vision.ai.conversation)."""
        return frame_rms(frame)

    def frame_peak(self, frame: bytes) -> float:
        """Méthode liée qui délègue à la fonction pure module-level
        `frame_peak` ci-dessus (cf. son docstring POURQUOI) — même patron que
        `frame_rms`, pour le même appelant (self._mic.frame_peak(frame), cf.
        didier_vision.ai.conversation._listen_for_utterance)."""
        return frame_peak(frame)

    def preroll(self) -> bytes:
        """Contenu actuel du ring buffer, concaténé dans l'ordre chronologique
        (le plus ancien en premier). Si read_frame() vient d'être appelé, la
        trame qu'il a retournée est déjà la plus récente de ce tampon (cf.
        read_frame ci-dessus) : un appelant qui détecte un speech_start sur
        cette trame peut donc utiliser preroll() SEUL comme point de départ
        de l'énoncé, sans ajouter la trame une seconde fois."""
        return b"".join(self._ring)
