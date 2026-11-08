"""File de lecture audio — I/O PURE (subprocess `aplay` + thread + queue).

QUOI : deux façons de lire du son, pour deux besoins différents du proto
       validé (cf. CLAUDE.md du 10/07) :
         - play(pcm, sample_rate) : enfile dans une file SÉQUENTIELLE lue par
           un thread dédié — c'est le pipeline TTS (une Sentence à la fois,
           dans l'ordre). POURQUOI une file plutôt qu'un simple appel
           bloquant : elle permet à l'appelant (didier_vision.ai.conversation) de
           synthétiser la phrase N+1 PENDANT que la phrase N est encore en
           train de jouer — play() N+1 revient immédiatement, le thread
           lecteur enchaîne les fichiers un par un dès que le précédent est
           terminé (sémantique "pipeline" du proto validé).
         - play_async_raw(path) : fire-and-forget, HORS de la file — lance
           `aplay` directement sans attendre ni passer par le thread lecteur.
           POURQUOI séparé : les bips de réflexion (didier_vision.audio.beeps)
           doivent jouer PENDANT que le STT tourne (appel bloquant côté
           appelant), donc AVANT qu'aucune Sentence TTS n'existe encore —
           les faire passer par la même file que le pipeline TTS n'aurait
           rien changé ici en pratique (la file serait vide à ce moment-là),
           mais les garder hors-file documente l'intention : ce son n'est
           jamais soumis à l'ordonnancement N/N+1 de la parole.
POURQUOI run_cmd injectable : mêmes raisons que didier_vision.audio.mic — les tests
       remplacent subprocess.Popen par un faux process (sans .wait() bloquant)
       pour ne jamais dépendre du binaire aplay ni d'un périphérique audio.
"""
from __future__ import annotations

import os
import queue
import subprocess
import tempfile
import threading
import wave


def write_wav_tempfile(pcm: bytes, sample_rate: int) -> str:
    """Écrit un PCM int16 mono dans un fichier .wav TEMPORAIRE, retourne son
    chemin. Fonction MODULE-LEVEL (pas méthode d'AudioPlayer) : réutilisée
    par didier_vision.ai.conversation.ConversationEngine pour pré-écrire la piste de
    bips de réflexion UNE SEULE FOIS à la construction (le contenu ne change
    pas d'un tour à l'autre) plutôt que de dupliquer cette logique d'écriture
    wav ailleurs."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # int16
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return path


class AudioPlayer:
    """Lecteur audio ALSA (`aplay`) à file séquentielle + canal fire-and-forget."""

    def __init__(self, device: str, run_cmd=None):
        self._device = device
        self._run_cmd = run_cmd or subprocess.Popen
        self._queue: "queue.Queue" = queue.Queue()
        # Interruption (cf. interrupt(), 31/10) : `_epoch` est le numéro de
        # « génération » courant — chaque fichier enfilé porte celui de son
        # play(), le lecteur saute tout fichier d'une génération périmée.
        # `_current` = aplay en cours (None entre deux fichiers). Les deux
        # sous `_lock` : interrupt() est appelé depuis un AUTRE thread (écoute
        # garde de la conversation) que le lecteur et que play().
        self._lock = threading.Lock()
        self._epoch = 0
        self._current = None
        # Thread daemon : ne bloque jamais l'arrêt du process si stop()
        # n'était pas appelé explicitement (garde-fou, stop() reste la voie
        # normale de terminaison propre).
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def play(self, pcm: bytes, sample_rate: int) -> None:
        """Enfile un chunk PCM à jouer (thread lecteur, wav temporaire +
        aplay) — voir docstring de module pour la sémantique pipeline N/N+1."""
        path = write_wav_tempfile(pcm, sample_rate)
        with self._lock:
            epoch = self._epoch
        self._queue.put((path, epoch))

    def play_async_raw(self, path) -> None:
        """Fire-and-forget : lance `aplay` directement sur un fichier déjà
        existant, SANS passer par la file ni attendre la fin de lecture (voir
        docstring de module — POURQUOI hors-file)."""
        self._run_cmd(["aplay", "-q", "-D", self._device, str(path)])

    def _worker(self) -> None:
        """Boucle du thread lecteur : consomme la file dans l'ordre, un
        fichier à la fois (c'est CETTE sérialisation qui donne le pipeline
        N/N+1 — pendant que ce thread bloque sur proc.wait(), l'appelant peut
        déjà avoir enfilé le fichier N+1)."""
        while True:
            item = self._queue.get()
            if item is None:  # sentinelle d'arrêt posée par stop()
                self._queue.task_done()
                break
            path, epoch = item
            try:
                # Démarrage SOUS le verrou : interrupt() ne peut pas tomber
                # entre « génération vérifiée » et « aplay lancé » (sinon le
                # fichier, déjà sorti de la file, jouerait en entier malgré
                # l'interruption). Popen ne fait que fork/exec : bref.
                with self._lock:
                    proc = None
                    if epoch == self._epoch:
                        proc = self._run_cmd(["aplay", "-q", "-D", self._device, path])
                        self._current = proc
                if proc is not None:
                    proc.wait()
            finally:
                with self._lock:
                    self._current = None
                # Le wav de play() est temporaire (write_wav_tempfile) : on le
                # supprime après lecture, que la lecture ait réussi ou non
                # (OSError ignorée : fichier déjà absent n'est pas une erreur
                # ici, seul le nettoyage best-effort compte).
                try:
                    os.remove(path)
                except OSError:
                    pass
                self._queue.task_done()

    def drain(self) -> None:
        """Bloque jusqu'à ce que la file soit entièrement jouée (utilisé en
        fin de tour de conversation, après la dernière Sentence enfilée)."""
        self._queue.join()

    def interrupt(self) -> None:
        """Coupe la lecture EN COURS et abandonne tout ce qui est déjà en file
        (arrêt d'urgence vocal pendant une réplique, cf. didier_vision.ai.conversation
        — 31/10). Le thread lecteur, lui, CONTINUE : un play() ultérieur joue
        normalement. À ne pas confondre avec stop(), qui termine le lecteur
        pour de bon APRÈS avoir tout joué (sentinelle en fin de file).
        Les fichiers sautés sont quand même supprimés et comptés (task_done) :
        drain() revient dès que le lecteur a vidé la file. Appelable depuis
        n'importe quel thread, idempotent, jamais d'exception (process déjà
        terminé = rien à couper)."""
        with self._lock:
            self._epoch += 1
            proc = self._current
            if proc is not None:
                try:
                    proc.terminate()
                except (OSError, AttributeError):
                    pass

    def stop(self) -> None:
        """Termine le thread lecteur proprement (sentinelle None + join)."""
        self._queue.put(None)
        self._thread.join()
