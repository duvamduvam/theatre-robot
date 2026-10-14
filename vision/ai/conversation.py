"""Orchestrateur d'un tour de conversation (V7) — colle les briques V1-V6
ensemble : micro -> VAD -> STT -> LLM streamé -> parseur de jeu -> TTS ->
lecture, avec publication des messages ROS (face/animation) au bon moment.

QUOI : ConversationEngine ne fait AUCUN I/O lui-même — tout (mic/vad/stt/
       brain/tts/player/publish) est injecté au constructeur. Ce module reste
       donc testable avec des fakes purs (cf. test_conversation.py), même si
       ce n'est pas un module "pur" au sens strict des lots V1-V5 (il
       ORCHESTRE des effets de bord, il ne les produit pas lui-même).
POURQUOI aucun thread supplémentaire créé ici : AudioPlayer a déjà le sien
       (lecture séquentielle en tâche de fond, cf. vision.audio.playback) ;
       run_once() est de toute façon bloquant sur la boucle d'écoute micro
       (read_frame) — ajouter un thread ici n'apporterait rien, juste de la
       complexité de synchronisation en plus.

DÉCISION (le déroulé du proto laissait un choix implicite à trancher) :
       thinking() est publié JUSTE APRÈS speech_end, AVANT même de savoir si
       le STT renverra du texte exploitable — donc thinking() part MÊME SI
       le tour est ensuite abandonné (STT vide/trop court). Choix VOLONTAIRE
       (pas un oubli) : le visage "reflechit" est une réaction honnête au
       fait que le STT est réellement en train de tourner (calcul bloquant
       en cours), pas une promesse qu'une réponse va suivre — le spectateur
       voit le robot "y penser", ce qui reste cohérent même si l'énoncé
       capté était en fait trop court pour être exploité. cf.
       test_conversation.py::test_stt_inexploitable_publie_thinking_puis_idle
       pour le test qui fige ce choix.

       CORRECTIF du 2026-07-12 (étude d'arbitrage des actionneurs, scénario
       S1 côté robot, cf. dadou_robot_ros/docs/etude-arbitrage-actionneurs.md
       §3/§5.1) : la « limite connue acceptée » ci-dessus (le visage restait
       coincé sur "reflechit" après un tour abandonné, faute de rattrapage)
       est CORRIGÉE — la condition documentée à l'époque ("à revisiter si ça
       se voit mal sur scène") était remplie, constaté sur le vrai robot.
       run_once() publie désormais idle() (retour au neutre) dans la branche
       STT inexploitable, AVANT de relancer le micro. thinking() reste publié
       dès speech_end SANS changement (réaction honnête toujours voulue) :
       seule la SORTIE d'un tour abandonné change, pas son entrée.

       ÉLARGISSEMENT du 2026-08-30 (gate « source audio vivante », half-
       duplex élargi, cf. dadou_robot_ros/docs/
       etude-declenchement-conversation.md §10) : deux kwargs OPTIONNELS
       `gate` et `show_audio_active` (défaut None = comportement HISTORIQUE
       inchangé à l'octet près, clause de réversibilité du lot). Quand ils
       sont fournis, `_listen_for_utterance` jette toute trame bruyante/
       écrêtée/de spectacle AVANT qu'elle n'atteigne la VAD, et
       `_speak_reply` arme une queue acoustique (`arm_tail`) avant de
       relancer le micro, dans ses DEUX sorties (succès et exception).

       OBSERVABILITÉ (2026-09-13, demande de David en séance -- « un
       indicateur pour voir si ma voix passe », « la conversation n'est pas
       fluide du tout ») : deux kwargs OPTIONNELS de plus, `on_meter` et
       `on_timing` (défaut None = comportement HISTORIQUE inchangé à l'octet
       près, MÊME clause de réversibilité que `gate`/`show_audio_active`
       ci-dessus). `on_meter` est nourri à la cadence des trames (30 ms) par
       `_listen_for_utterance` -- niveau/crête/blocage gate/état VAD, de quoi
       dessiner un vumètre web temps réel (cf. vision/nodes/chat_node.py,
       paramètre `diag_port`). `on_timing` est nourri une fois par tour par
       `run_once`/`_speak_reply` -- durées STT/latence LLM/latence premier
       son/latence totale perçue, pour comprendre OÙ part le temps d'un tour.
       Les DEUX callbacks tournent dans le thread de conversation et NE
       DOIVENT JAMAIS le faire dérailler : un vumètre qui plante ne doit
       jamais rendre Didier muet, cf. `_notify_meter`/`_notify_timing`.

       CORRECTIF du 2026-09-13 (David, en séance : « la bouche n'est pas
       raccord avec la parole » -- pas une demande de synchronisation
       labiale, juste « recaler la fin »/faire cesser le mouvement à la fin
       de la réplique) : MÊME défaut que le CORRECTIF du 2026-07-12
       ci-dessus, jamais porté sur le chemin NOMINAL de `_speak_reply`.
       Mécanisme : l'expression "parle" (json/expressions.json,
       dadou_robot_ros) a `"loop": true` -- Face la rejoue indéfiniment tant
       qu'AUCUN autre message n'arrive sur le topic face. `speaking_stop()`
       coupe la SÉQUENCE de servos (topic animation) mais ne publie RIEN sur
       le topic face ; `self._perf.emotion(emotion_params)` renvoie une liste
       VIDE dès que le LLM n'a pas émis de JSON d'émotion final exploitable
       (cas courant) -- résultat : la bouche continuait de s'agiter pendant
       toute la pause d'écoute suivante, sans qu'aucun message face ne
       vienne jamais l'arrêter. `_speak_reply` publie désormais idle() (visage
       neutre) en RATTRAPAGE si `emotion(...)` n'a rien produit (chemin
       nominal), et de façon INCONDITIONNELLE sur le chemin d'erreur LLM/TTS
       (une panne ne laisse jamais un `emotion_params` de fin fiable) --
       toujours APRÈS `speaking_stop()`, jamais avant.

       RÉGIE (2026-10-14, lot R3 « Chantiers », dadou_robot_ros/docs/
       etude-repetition-simulee.md §13.6) : deux kwargs OPTIONNELS de plus,
       `stage` (vision.ai.stage.StageState) et `on_transcript` -- défaut None
       = comportement HISTORIQUE inchangé, MÊME clause de réversibilité que
       ci-dessus (les tests existants restent verts sans y toucher). Avec
       `stage` : un texte TAPÉ par la régie est servi comme un énoncé entendu
       (ni micro ni STT, au début du tour ou en interrompant l'écoute), la
       PANNE courante est appliquée au texte compris (deaf = tour abandonné,
       garble = contresens, delay = sommeil avant le LLM, mute = répliques
       non synthétisées), et la CONSIGNE courante part au LLM comme second
       message system. `on_transcript(role, texte)` reçoit ce que Didier a
       compris ("david", après garble) et chaque phrase qu'il dit ("didier")
       -- jamais les consignes ni les pannes (David ignore le tirage).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional, Union

from vision.ai import performance
from vision.ai.stage import ROLE_DAVID, ROLE_DIDIER, StageState, garble_text
from vision.ai.stream_parser import Didascalie, Emotion, Sentence, StreamPerformanceParser

# Logger stdlib (PAS le logger rclpy : ce module reste sans dépendance ROS,
# cf. docstring — le node chat configure le niveau/format dans son main()).
# Les tours de conversation sont journalisés ici (STT, répliques, abandons) :
# indispensable pour suivre un protocole physique en direct — le premier test
# micro réel (2026-07-11) s'est fait à l'aveugle faute de ces logs.
logger = logging.getLogger(__name__)

# Attente (s) par défaut avant de retenter un tour quand le flux micro est
# mort : sans elle, run_forever repart IMMÉDIATEMENT dans run_once -> un
# périphérique indisponible (arecord orphelin, câble débranché) devient une
# boucle serrée qui respawne arecord en continu (~200 % CPU constatés au
# premier test réel, 2026-07-11). 0,5 s suffit : assez court pour reprendre
# vite quand le micro revient, assez long pour que la boucle soit inoffensive.
DEAD_MIC_BACKOFF_S = 0.5

# Pas de sondage (s) de la file des textes tapés pendant l'attente « micro
# mort » (cf. _wait_dead_mic_backoff) : un texte de la régie doit être servi
# même quand le micro est HS (banc sans micro, carte débranchée) — attendre
# le backoff à l'aveugle le retarderait pour rien. 50 ms : imperceptible
# pour la régie, négligeable en CPU.
STAGE_POLL_S = 0.05


def has_usable_text(text: Optional[str]) -> bool:
    """Un texte STT est exploitable s'il contient au moins 2 caractères
    alphanumériques. POURQUOI pas un simple len(strip()) : whisper transcrit
    le bruit pur en ponctuation ("... ... ..."), qui passait l'ancien filtre
    et déclenchait un appel LLM payant + une réplique de Didier sans que
    personne n'ait parlé (constaté au premier test micro caméra, 2026-07-11)."""
    if not text:
        return False
    return sum(1 for ch in text if ch.isalnum()) >= 2


class ConversationEngine:
    """Un tour de conversation = un cycle écoute -> pensée -> parole complet.
    Toutes les dépendances (I/O réelles ou fakes de test) sont injectées."""

    def __init__(self, *, mic, vad, stt, brain, tts, player,
                 publish: Callable[[object], None],
                 perf=None,
                 beeps_pcm: bytes = b"", beeps_rate: int = 22050,
                 refresh_ms: int = 15000,
                 dead_mic_backoff_s: float = DEAD_MIC_BACKOFF_S,
                 on_state: Optional[Callable[[str], None]] = None,
                 initial_state: Optional[str] = None,
                 gate=None,
                 show_audio_active: Optional[Callable[[], bool]] = None,
                 on_meter: Optional[Callable[[float, float, bool, bool], None]] = None,
                 on_timing: Optional[Callable[[dict], None]] = None,
                 stage: Optional[StageState] = None,
                 on_transcript: Optional[Callable[[str, str], None]] = None):
        self._mic = mic
        self._vad = vad
        # Gate « source audio vivante » (half-duplex élargi, cf.
        # dadou_robot_ros/docs/etude-declenchement-conversation.md §10) :
        # None = comportement HISTORIQUE inchangé à l'octet près (clause de
        # réversibilité du lot, cf. §10.5 -- les tests existants restent
        # verts sans y toucher). `show_audio_active` est un CALLABLE (pas un
        # bool figé au constructeur) : il doit refléter l'état COURANT de
        # l'animation en cours à chaque frame, recalculé à la volée par
        # chat_node (cf. arbitration.effective_state, qui applique sa propre
        # péremption deadman) — un bool gelé à la construction serait faux
        # dès la première séquence de spectacle lancée après coup.
        self._gate = gate
        self._show_audio_active = show_audio_active
        # Vumètre web (2026-09-13, cf. docstring de module OBSERVABILITÉ) :
        # None = comportement HISTORIQUE inchangé (aucun coût -- cf.
        # _listen_for_utterance, frame_peak() n'est même pas calculé si ni
        # `on_meter` ni `gate` ne sont branchés) ; câblé par chat_node quand
        # `diag_port` > 0.
        self._on_meter = on_meter
        # Latences par tour (même lot) : None = comportement historique inchangé.
        self._on_timing = on_timing
        # Régie (lot R3, cf. docstring de module RÉGIE) : None = comportement
        # historique inchangé. Partagé avec chat_node, qui l'ÉCRIT depuis le
        # thread rclpy.spin — StageState porte son propre verrou.
        self._stage = stage
        # Transcript (même lot) : None = personne n'écoute.
        self._on_transcript = on_transcript
        self._stt = stt
        self._brain = brain
        self._tts = tts
        self._player = player
        self._publish = publish
        # Callback d'état optionnel (chat_node V2, lot D0 outillage) : expose
        # listening/thinking/speaking/off pour la régie, le télédiagnostic et
        # le futur engagement_node (cf. dadou_robot_ros/docs/
        # etude-declenchement-conversation.md §6.2 -- IN_CONVERSATION a besoin
        # de savoir si le chat écoute encore). None = personne n'écoute
        # (comportement actuel inchangé, cf. _set_state ci-dessous).
        self._on_state = on_state
        # Dédup interne (cf. _set_state) : None au départ, aucun état n'a
        # encore été vu.
        self._last_state: Optional[str] = None
        # perf par défaut = le MODULE vision.ai.performance lui-même (ses
        # fonctions thinking/speaking_start/... sont utilisées comme
        # namespace) — un fake de test fournit un objet avec les mêmes noms
        # de fonctions, sans avoir à mocker un module entier.
        self._perf = perf if perf is not None else performance
        self._refresh_ms = refresh_ms
        # Injectable pour les tests (0.0 = pas d'attente) — cf. constante
        # DEAD_MIC_BACKOFF_S pour le pourquoi de la valeur par défaut.
        self._dead_mic_backoff_s = dead_mic_backoff_s
        # Interrupteur de mode interactif, posé par run_forever (None tant
        # qu'on n'y est pas passé) : run_once s'en sert UNIQUEMENT pour
        # distinguer « micro mort » (incident -> warning + backoff + restart)
        # de « micro coupé volontairement par le toggle OFF » (silencieux,
        # pas de restart — le micro doit RESTER coupé pendant la pause).
        self._enabled: Optional[threading.Event] = None

        # La piste de bips est écrite en wav temporaire UNE SEULE FOIS ici
        # (pas à chaque tour) : son contenu ne change pas d'un tour à
        # l'autre, cf. vision.audio.playback.write_wav_tempfile. Import
        # différé (pas en tête de module) : conversation.py doit rester
        # important sans exiger que vision.audio.playback soit disponible
        # dans TOUS les contextes qui pourraient un jour importer ce module
        # (aucun aujourd'hui, mais évite d'ajouter un couplage silencieux) —
        # en pratique playback.py est pur stdlib+numpy, donc ceci reste sûr
        # même en CI minimal.
        self._beeps_path: Optional[str] = None
        if beeps_pcm:
            from vision.audio.playback import write_wav_tempfile
            self._beeps_path = write_wav_tempfile(beeps_pcm, beeps_rate)

        # État initial émis PAR LE MOTEUR à la construction (et non poussé de
        # l'extérieur en écrivant _last_state, ce qui violerait la frontière
        # de la brique pure) : un abonné ROS latché (chat_node publie en
        # TRANSIENT_LOCAL) doit trouver une valeur dès la souscription, MÊME
        # avant le premier tour — la dédup de _set_state absorbera ensuite le
        # "listening" que run_once() re-signalera au démarrage du thread.
        if initial_state is not None:
            self._set_state(initial_state)

    def _set_state(self, state: str) -> None:
        """Notifie `on_state` d'un changement d'état ("listening"/"thinking"/
        "speaking"/"off"), avec DÉDUPLICATION sur `_last_state` : nécessaire
        car certains points d'émission sont appelés en boucle (la pause
        toggle OFF de run_forever ré-attend à 0,2 s tant que le mode
        interactif reste désactivé ; "speaking" est réémis à chaque Sentence,
        cf. _handle_event) -- sans dédup, un abonné ROS recevrait un flot de
        messages identiques pour rien. try/except : `on_state` finira par
        publier sur un topic ROS (chat_node), un monde que cette brique pure
        ne connaît pas -- un callback qui plante ne doit JAMAIS interrompre un
        tour de conversation en cours, seulement perdre cette notification
        d'état (log warning pour ne pas le perdre en silence)."""
        if self._on_state is None or state == self._last_state:
            return
        self._last_state = state
        try:
            self._on_state(state)
        except Exception:
            logger.warning("Callback on_state en échec (état %r ignoré).", state, exc_info=True)

    def _notify_meter(self, level: float, peak: float, blocked: bool, in_speech: bool) -> None:
        """Notifie `on_meter` (vumètre web, cf. docstring de module
        OBSERVABILITÉ) pour LA TRAME courante -- appelé à la cadence des
        trames (30 ms) par `_listen_for_utterance`. try/except EN DEBUG (pas
        warning, contrairement à `_notify_timing` ci-dessous) : à cette
        cadence, un souci récurrent spammerait le journal pour rien ; le
        vumètre est un outil de confort, jamais un signal de sécurité, cf.
        docstring de module -- un plantage ne doit perdre QUE cette
        notification, jamais faire taire Didier."""
        if self._on_meter is None:
            return
        try:
            self._on_meter(level, peak, blocked, in_speech)
        except Exception:
            logger.debug("Callback on_meter en échec (trame ignorée).", exc_info=True)

    def _notify_timing(self, timing: dict) -> None:
        """Notifie `on_timing` (console de diagnostic web) UNE fois par tour
        qui a réellement atteint le STT (cf. run_once : les abandons AVANT le
        STT -- flux micro mort, coupure volontaire -- n'ont rien à mesurer et
        ne déclenchent jamais cet appel, cf. docstring de `run_once`).
        try/except EN WARNING (pas debug, contrairement à `_notify_meter`) :
        un tour, ça n'arrive pas à 33 Hz -- un warning par tour raté reste
        lisible et utile, sans spammer le journal."""
        if self._on_timing is None:
            return
        try:
            self._on_timing(timing)
        except Exception:
            logger.warning("Callback on_timing en échec (mesure du tour perdue).", exc_info=True)

    def _notify_transcript(self, role: str, text: str) -> None:
        """Notifie `on_transcript` (topic chat_transcript, cf. docstring de
        module RÉGIE). Même garde que `_notify_timing` (warning, pas debug :
        une ligne de dialogue, ça n'arrive pas à 33 Hz) — une page de régie
        cassée ne doit jamais rendre Didier muet."""
        if self._on_transcript is None:
            return
        try:
            self._on_transcript(role, text)
        except Exception:
            logger.warning("Callback on_transcript en échec (ligne %r perdue).", role,
                           exc_info=True)

    def _publish_all(self, messages) -> None:
        """publish() ne prend qu'UN SEUL message à la fois (contrat du
        constructeur) ; les fonctions de vision.ai.performance renvoient des
        LISTES (parfois vides, ex: emotion(None)) — ce helper fait le pont,
        dans l'ordre, sans jamais publier quoi que ce soit pour une liste
        vide (une liste vide = "rien à jouer", pas une erreur)."""
        for message in messages:
            self._publish(message)

    def _handle_event(self, event, emotion_params, timing_marks: dict, mute: bool = False):
        """Traduit UN événement du parseur de flux (Sentence/Didascalie/
        Emotion) en effet de bord (publish + synthèse/lecture), et retourne
        les params d'émotion à retenir (inchangés sauf si `event` EST
        l'Emotion — un seul JSON d'émotion possible par tour, en toute fin de
        flux, cf. stream_parser.flush()).

        `timing_marks` (dict mutable {"first_sentence_at", "first_play_at"},
        cf. `_speak_reply`) : horodate le PREMIER événement de chaque sorte
        rencontré dans le tour, pour `on_timing` (docstring de module
        OBSERVABILITÉ) — jamais réécrit une fois posé (`if ... is None`), une
        réponse a en général plusieurs Sentence mais seule la latence du
        PREMIER son compte pour la latence perçue par le spectateur.

        `mute` (panne de régie, cf. docstring de module RÉGIE) : la Sentence
        n'est ni synthétisée ni jouée — tout le reste part normalement
        (transcript, bouche "parle", didascalies, émotion) : c'est le bug
        réel simulé, « texte sans voix » (audio muet en silence)."""
        if isinstance(event, Sentence):
            if timing_marks["first_sentence_at"] is None:
                # Horodaté AVANT même la synthèse TTS qui suit (elle peut
                # prendre du temps) : c'est la latence "il réfléchit" telle
                # que vécue par le spectateur, cf. on_timing.
                timing_marks["first_sentence_at"] = time.monotonic()
            # Journalisée AVANT la synthèse : si le TTS plante, la trace dit
            # quand même ce que Didier ALLAIT dire (diagnostic en direct).
            logger.info("Didier : %s", event.text)
            self._notify_transcript(ROLE_DIDIER, event.text)
            # "speaking" : dédup absorbe la répétition à CHAQUE Sentence d'un
            # même tour (une réponse a en général plusieurs phrases).
            self._set_state("speaking")
            # speaking_start republié à CHAQUE Sentence (pas seulement la
            # première) : sert de rafraîchissement — cf. commentaire
            # chat_animation_refresh_ms dans vision_config.py, l'animation
            # "parle" doit rester active tant que le TTS streame encore.
            self._publish_all(self._perf.speaking_start(self._refresh_ms))
            if mute:
                return emotion_params
            pcm, sample_rate = self._tts.synthesize(event.text)
            # play() enfile : la synthèse de la Sentence SUIVANTE peut se
            # faire pendant que celle-ci joue encore (pipeline N/N+1 porté
            # par AudioPlayer, cf. vision.audio.playback).
            self._player.play(pcm, sample_rate)
            if timing_marks["first_play_at"] is None:
                # Premier son ENFILÉ pour lecture (cf. on_timing) — AudioPlayer
                # joue en tâche de fond, donc c'est une approximation par excès
                # du début RÉEL du son (léger délai de mise en file), largement
                # suffisant pour un diagnostic de latence perçue.
                timing_marks["first_play_at"] = time.monotonic()
            return emotion_params

        if isinstance(event, Didascalie):
            self._publish_all(self._perf.didascalie(event.action))
            return emotion_params

        if isinstance(event, Emotion):
            return event.params

        return emotion_params

    def run_once(self) -> bool:
        """Un tour complet. Retourne True seulement si le tour a été mené
        jusqu'au bout (émotion publiée) ; False dans tous les cas
        d'abandon : flux micro mort, STT vide/trop court, ou erreur
        LLM/TTS (le spectacle continue, cf. docstring de module)."""
        # Texte tapé en attente (régie, cf. docstring de module RÉGIE) :
        # servi SANS démarrer le micro ni passer par le STT.
        typed = self._stage.pop_text() if self._stage is not None else None
        if typed is not None:
            return self._serve_typed_text(typed)

        self._mic.start()
        self._set_state("listening")

        speech_bytes = self._listen_for_utterance()
        if isinstance(speech_bytes, str):
            # Texte tapé arrivé PENDANT l'écoute (cf. _listen_for_utterance,
            # qui a déjà coupé le micro et jeté l'énoncé partiel).
            return self._serve_typed_text(speech_bytes)
        if speech_bytes is None:
            if self._enabled is not None and not self._enabled.is_set():
                # Coupure VOLONTAIRE (toggle chat OFF pendant l'écoute, cf.
                # chat_node._on_chat_cmd qui fait mic.stop()) : pas un
                # incident — ni warning ni backoff ni restart, le micro doit
                # rester coupé pendant toute la pause.
                logger.info("Écoute interrompue (mode interactif désactivé).")
                return False
            # Flux micro mort en cours d'écoute : on retente un démarrage et
            # on abandonne CE tour (pas d'exception qui remonterait jusqu'à
            # run_forever — un souci matériel ponctuel ne doit pas arrêter la
            # boucle de conversation). Le log + le backoff sont indispensables :
            # sans eux, un micro durablement indisponible devient une boucle
            # serrée INVISIBLE qui respawne arecord en continu (cf. constante
            # DEAD_MIC_BACKOFF_S — vécu au premier test réel, 2026-07-11).
            logger.warning(
                "Flux micro mort en cours d'écoute — nouvel essai dans %.1f s.",
                self._dead_mic_backoff_s)
            if self._dead_mic_backoff_s > 0:
                if self._stage is None:
                    time.sleep(self._dead_mic_backoff_s)
                else:
                    self._wait_dead_mic_backoff()
            self._mic.start()
            return False

        # Horodatage de FIN D'ÉNONCÉ (speech_end, cf. on_timing/docstring de
        # module OBSERVABILITÉ) : point de départ de `total_ms` -- la latence
        # perçue par le spectateur commence au dernier mot prononcé, pas au
        # début du tour ni à la fin du STT qui suit.
        speech_end_at = time.monotonic()

        # Anti-larsen : le micro est coupé AVANT que Didier ne parle (cf.
        # vision.audio.mic.MicCapture.stop). thinking() est publié ICI, cf.
        # décision documentée en tête de module (avant même de savoir si le
        # STT renverra du texte exploitable).
        self._mic.stop()
        self._publish_all(self._perf.thinking())
        self._set_state("thinking")

        if self._beeps_path is not None:
            # Fire-and-forget : les bips jouent PENDANT le transcribe()
            # bloquant qui suit, cf. vision.audio.playback.play_async_raw.
            self._player.play_async_raw(self._beeps_path)

        # stt_ms mesuré autour de l'appel bloquant (cf. on_timing) : c'est la
        # durée RÉELLE payée par ce tour, pas une estimation.
        stt_started_at = time.monotonic()
        text = self._stt.transcribe(speech_bytes, self._mic.sample_rate)
        stt_ms = (time.monotonic() - stt_started_at) * 1000

        if not has_usable_text(text):
            # Bruit ou énoncé trop court : PAS d'appel LLM (payant), retour à
            # l'écoute. Loggé en INFO : c'est la trace qui permet de régler le
            # VAD/gain micro quand Didier « entend des voix » sur scène.
            logger.info("Tour abandonné, STT inexploitable : %r", text)
            # abandoned=True, champs AVAL (après le STT) à None : ce tour n'a
            # jamais atteint le LLM/TTS, il n'y a rien de plus à mesurer (cf.
            # docstring de module OBSERVABILITÉ).
            self._notify_timing({
                "stt_ms": stt_ms, "llm_first_ms": None, "audio_first_ms": None,
                "total_ms": None, "stt_text": text, "abandoned": True,
            })
            # Rattrapage idle() AVANT de relancer le micro (cf. docstring de
            # module, correctif 2026-07-12) : sans ça, le visage restait
            # coincé sur "reflechit" (publié par thinking() ci-dessus) pour
            # tout le reste de la pause d'écoute suivante — visible sur scène.
            self._publish_all(self._perf.idle())
            self._mic.start()
            self._set_state("listening")
            return False

        logger.info("STT : %r", text)
        return self._reply_with_stage(text, stt_ms=stt_ms, speech_end_at=speech_end_at)

    def _wait_dead_mic_backoff(self) -> None:
        """Backoff « micro mort » quand la régie est branchée : même durée
        que le time.sleep historique, mais en SONDANT la file des textes
        tapés (pas de STAGE_POLL_S) — un texte arrivé pendant l'attente
        l'écourte, il sera servi dès le tour suivant (cf. run_once)."""
        deadline = time.monotonic() + self._dead_mic_backoff_s
        while not self._stage.has_text():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(STAGE_POLL_S, remaining))

    def _serve_typed_text(self, text: str) -> bool:
        """Un texte TAPÉ (régie ou phantom) est servi comme un énoncé entendu
        dont le STT aurait déjà tourné : mêmes réactions visibles que le
        chemin micro (thinking + bips, « il y pense »), sans micro ni STT.
        mic.stop() d'abord : le micro tourne peut-être depuis la fin du tour
        précédent (anti-larsen, comme le chemin micro avant thinking)."""
        self._mic.stop()
        self._publish_all(self._perf.thinking())
        self._set_state("thinking")
        if self._beeps_path is not None:
            self._player.play_async_raw(self._beeps_path)
        logger.info("Texte tapé : %r", text)
        return self._reply_with_stage(text)

    def _reply_with_stage(self, text: str, *, stt_ms: float = 0.0,
                          speech_end_at: Optional[float] = None) -> bool:
        """Applique la PANNE de régie courante au texte compris (STT ou texte
        tapé), publie la ligne "david" du transcript, puis répond. Sans
        `stage` : panne "pass" -> appel _speak_reply strictement historique.
        La panne est lue UNE fois par tour (instantané) : une échéance qui
        tombe en pleine réplique ne la coupe pas à moitié."""
        op, params = (self._stage.fault(time.monotonic()) if self._stage is not None
                      else ("pass", {}))
        # stt_text du dict on_timing = ce que le STT a VRAIMENT produit (la
        # console de diagnostic dit la vérité technique, même sous garble).
        stt_text = text
        if op == "deaf":
            # Énoncé jeté, comme un STT inexploitable (même sortie : idle()
            # avant de relancer le micro, cf. correctif du 2026-07-12) —
            # aucune ligne de transcript : Didier n'a rien entendu.
            logger.info("Tour abandonné, panne deaf : %r", text)
            self._notify_timing({
                "stt_ms": stt_ms, "llm_first_ms": None, "audio_first_ms": None,
                "total_ms": None, "stt_text": stt_text, "abandoned": True,
            })
            self._publish_all(self._perf.idle())
            self._mic.start()
            self._set_state("listening")
            return False
        if op == "garble":
            text = garble_text(self._stage.rng, params.get("texts"))
            logger.info("Panne garble : %r compris comme %r", stt_text, text)
        self._notify_transcript(ROLE_DAVID, text)
        if op == "delay":
            # AVANT l'appel LLM : les bips jouent déjà (fire-and-forget), le
            # visage est sur "reflechit", l'état reste "thinking" — c'est la
            # latence du Pi 5 (4 à 9 s mesurées) rejouée telle quelle.
            logger.info("Panne delay : %d ms avant le LLM", params["delay_ms"])
            time.sleep(params["delay_ms"] / 1000)
        return self._speak_reply(text, stt_ms=stt_ms, stt_text=stt_text,
                                 speech_end_at=speech_end_at, mute=(op == "mute"))

    def _listen_for_utterance(self) -> Union[bytes, str, None]:
        """Boucle micro -> VAD jusqu'à détecter la fin d'un énoncé. Retourne
        les octets PCM accumulés depuis le pré-roll, ou None si le flux
        micro est mort avant la fin de l'énoncé — ou une `str` (régie) : un
        texte tapé arrivé pendant l'écoute, qui l'INTERROMPT (bytes et str
        sont des types disjoints : run_once les distingue par isinstance)."""
        speech_bytes = b""
        in_speech = False

        while True:
            frame = self._mic.read_frame()
            # Texte tapé (régie) : vérifié à CHAQUE trame — c'est CE sondage
            # qui interrompt l'écoute (chat_node n'arrête pas le micro depuis
            # son thread, cf. ChatNode._on_chat_text) — et aussi quand
            # read_frame() rend None : un texte en attente passe avant le
            # diagnostic « micro mort ». L'énoncé partiel est jeté et la VAD ramenée
            # en IDLE (même raison que le blocage du gate ci-dessous : sinon
            # elle attendrait la fin d'une phrase qu'on ne lui donne plus).
            typed = self._stage.pop_text() if self._stage is not None else None
            if typed is not None:
                self._mic.stop()
                self._vad.reset()
                return typed
            if frame is None:
                return None

            level = self._mic.frame_rms(frame)

            # frame_peak() n'est calculé QUE si un consommateur en a
            # effectivement besoin (gate OU vumètre web, cf. on_meter,
            # docstring de module OBSERVABILITÉ) : c'est un calcul numpy
            # (np.max(np.abs(...))) à la cadence des trames (30 ms) -- inutile
            # de le payer pour rien quand ni l'un ni l'autre n'est branché
            # (comportement historique : gate=None, on_meter=None).
            peak = (self._mic.frame_peak(frame)
                    if (self._gate is not None or self._on_meter is not None) else 0.0)

            blocked = False
            if self._gate is not None:
                # Gate évalué AVANT la VAD (cf. §10.5.1 de l'étude) : la VAD
                # ne doit JAMAIS voir une trame bruyante. Sa calibration est
                # à usage unique (médiane des 1000 premières ms) -- une sono
                # vivante pendant cette fenêtre empoisonnerait le seuil pour
                # toute la vie de l'instance, rendant Didier durablement
                # sourd à un humain sans que rien ne le signale.
                show_audio = (self._show_audio_active() if self._show_audio_active
                              is not None else False)
                blocked = self._gate.feed(level, peak, show_audio)

            # Vumètre web (cf. docstring de module OBSERVABILITÉ) : notifié
            # pour CHAQUE trame lue, bloquée ou non -- c'est justement le
            # blocage par le gate que David veut voir en direct ("ma voix
            # passe-t-elle ?"). `in_speech` reflète l'état AVANT le
            # traitement de CETTE trame (une trame de speech_start n'est donc
            # pas encore "en parole" à l'instant de cette notification).
            self._notify_meter(level, peak, blocked, in_speech)

            if blocked:
                # Trame bloquée : jetée avant la VAD. Un blocage en
                # pleine phrase jette l'énoncé PARTIEL (jamais de
                # recollage d'avant/après un trou de gate, cf. §10.5.2) ;
                # le pré-roll est purgé (§10.5.3, sinon la prochaine
                # phrase légitime démarrerait avec du bruit de sono dans
                # son pré-roll) ; la VAD est ramenée en IDLE (§10.5.4,
                # sans quoi une VAD restée en SPEECH attendrait son
                # end_silence_ms sur des trames qu'elle ne reçoit plus).
                speech_bytes = b""
                in_speech = False
                self._mic.purge_preroll()
                self._vad.reset()
                continue

            event = self._vad.feed(level)

            if not in_speech:
                # Tant que la parole n'a pas VRAIMENT commencé (VAD encore en
                # CALIBRATING/IDLE), on ne fait qu'alimenter la machine à
                # états — feed() renvoie None, la boucle continue.
                if event is not None and event.kind == "speech_start":
                    in_speech = True
                    # preroll() inclut déjà cette trame de déclenchement
                    # comme entrée la plus récente du ring buffer (cf.
                    # vision.audio.mic.MicCapture.read_frame/preroll) : pas
                    # besoin de la rajouter une seconde fois ici.
                    speech_bytes = self._mic.preroll()
                continue

            speech_bytes += frame
            if event is not None and event.kind == "speech_end":
                return speech_bytes

    def _speak_reply(self, text: str, *, stt_ms: float = 0.0, stt_text: str = "",
                      speech_end_at: Optional[float] = None, mute: bool = False) -> bool:
        """Génère et joue la réponse du LLM pour `text` déjà transcrit ;
        retourne True si le tour est allé jusqu'au bout, False sur erreur
        LLM/TTS (log + retour à l'écoute, le spectacle continue).

        `stt_ms`/`stt_text`/`speech_end_at` (cf. run_once, docstring de
        module OBSERVABILITÉ) : mesures du tour DÉJÀ prises en amont,
        transmises telles quelles pour composer le dict `on_timing` en fin de
        méthode — cette méthode n'a besoin de mesurer QUE ce qui se passe à
        partir d'ici (latence LLM, latence premier son).

        `mute` : panne de régie, transmise à _handle_event (cf. son docstring)."""
        parser = StreamPerformanceParser()
        emotion_params = None
        # Horodatage de départ pour llm_first_ms/audio_first_ms (relatifs au
        # début de CETTE méthode, cf. docstring de module OBSERVABILITÉ) ;
        # timing_marks : dict mutable rempli par _handle_event, jamais réécrit
        # une fois un jalon posé (seul le PREMIER Sentence/son de la réponse
        # compte pour la latence perçue).
        reply_started_at = time.monotonic()
        timing_marks = {"first_sentence_at": None, "first_play_at": None}

        try:
            if self._stage is None:
                deltas = self._brain.stream_reply(text)
            else:
                # Consigne de jeu courante (None si aucune, levée ou périmée,
                # cf. StageState.instruction) relue à CHAQUE tour.
                deltas = self._brain.stream_reply(
                    text, extra_system=self._stage.instruction(time.monotonic()))
            for delta in deltas:
                for event in parser.feed(delta):
                    emotion_params = self._handle_event(
                        event, emotion_params, timing_marks, mute)
            for event in parser.flush():
                emotion_params = self._handle_event(event, emotion_params, timing_marks, mute)
        except Exception:
            # Le spectacle continue : une panne LLM/TTS ponctuelle ne doit
            # jamais arrêter la conversation, seulement ce tour-ci.
            logging.exception(
                "Erreur pendant la génération/synthèse de la réponse — tour abandonné.")
            self._publish_all(self._perf.speaking_stop())
            # Rattrapage visage (2026-09-13, "la bouche n'est pas raccord avec
            # la parole" -- David ; cf. DÉCISION/CORRECTIF en tête de module) :
            # speaking_stop() coupe la SÉQUENCE de servos (topic animation)
            # mais ne publie RIEN sur le topic face -- or l'expression "parle"
            # (json/expressions.json, dadou_robot_ros) a loop:true, Face la
            # rejoue donc indéfiniment tant qu'aucun AUTRE message face
            # n'arrive. Sur ce chemin d'erreur, emotion_params ne reflète
            # JAMAIS un état de fin fiable (la panne a coupé la génération
            # avant tout JSON d'émotion, ou en plein milieu) : idle()
            # INCONDITIONNEL ici, contrairement au chemin nominal ci-dessous
            # qui peut se permettre de retenir une émotion réellement conclue.
            self._publish_all(self._perf.idle())
            if self._gate is not None:
                # Queue acoustique (C2) même sur ABANDON : le player peut
                # encore être en train de jouer ce qui était déjà enfilé
                # (aucun drain() sur ce chemin, cf. commentaire du test
                # test_erreur_llm_publie_quand_meme_speaking_stop) — la
                # réverbération/le tampon ALSA de CE résidu ne doit pas être
                # réécoutée dès la reprise du micro (§10.5, arm_tail avant
                # _mic.start() dans les DEUX sorties de _speak_reply).
                self._gate.arm_tail()
            self._mic.start()
            self._set_state("listening")
            # abandoned=True comme le cas STT inexploitable de run_once (même
            # sémantique : ce tour n'a pas produit de réponse) -- les jalons
            # aval restent None si la panne a eu lieu AVANT toute Sentence/
            # lecture (cas le plus courant, ex. erreur réseau LLM), mais
            # reflètent une valeur RÉELLE si la panne a frappé après coup
            # (ex. TTS en échec sur la 2e phrase, la 1re a bien été jouée) --
            # timing_marks porte déjà cette nuance, pas besoin de la
            # dupliquer ici.
            self._notify_timing(self._build_timing(
                stt_ms, stt_text, timing_marks, reply_started_at, speech_end_at, abandoned=True))
            return False

        self._player.drain()
        self._publish_all(self._perf.speaking_stop())
        # Rattrapage visage (2026-09-13, cf. DÉCISION/CORRECTIF en tête de
        # module pour le mécanisme complet) : self._perf.emotion(...) renvoie
        # une liste VIDE dès que le LLM n'a pas émis de JSON d'émotion final
        # (cas courant) ou une clé d'émotion inconnue du mapping -- dans ce
        # cas AUCUN message ne part sur le topic face, et l'expression "parle"
        # (loop:true côté robot) continue de s'agiter pendant toute l'écoute
        # suivante, speaking_stop() n'ayant coupé QUE la séquence de servos.
        # MÊME trou que celui corrigé le 2026-07-12 sur le chemin "STT
        # inexploitable" (rattrapage idle() avant de relancer le micro),
        # jamais porté jusqu'ici sur le chemin NOMINAL : on garantit
        # désormais qu'AU MOINS un message face part à la fin de CHAQUE
        # réplique -- l'émotion si le LLM en a conclu une exploitable, idle()
        # sinon (jamais les deux : une émotion fraîchement choisie ne doit pas
        # être écrasée par un neutre superflu).
        emotion_messages = self._perf.emotion(emotion_params)
        self._publish_all(emotion_messages if emotion_messages else self._perf.idle())
        if self._gate is not None:
            # Queue acoustique (C2) après un drain() réussi : cf. commentaire
            # ci-dessus, même raison, chemin nominal.
            self._gate.arm_tail()
        self._mic.start()
        self._set_state("listening")
        self._notify_timing(self._build_timing(
            stt_ms, stt_text, timing_marks, reply_started_at, speech_end_at, abandoned=False))
        return True

    @staticmethod
    def _build_timing(stt_ms: float, stt_text: str, timing_marks: dict,
                       reply_started_at: float, speech_end_at: Optional[float],
                       *, abandoned: bool) -> dict:
        """Assemble le dict `on_timing` (cf. docstring de constructeur) à
        partir des horodatages relevés pendant CE tour. Un jalon jamais
        atteint (Sentence/lecture jamais produites, ex. panne LLM avant tout
        texte) reste None plutôt qu'une durée fantaisiste -- la console de
        diagnostic doit pouvoir distinguer "pas encore mesuré" de "zéro
        seconde". `speech_end_at` peut être None (défaut du paramètre,
        n'arrive jamais en pratique via run_once, mais garde cette méthode
        appelable isolément dans les tests sans fournir cette valeur)."""
        def ms_since(started_at, mark_at):
            if mark_at is None or started_at is None:
                return None
            return (mark_at - started_at) * 1000

        return {
            "stt_ms": stt_ms,
            "llm_first_ms": ms_since(reply_started_at, timing_marks["first_sentence_at"]),
            "audio_first_ms": ms_since(reply_started_at, timing_marks["first_play_at"]),
            "total_ms": ms_since(speech_end_at, timing_marks["first_play_at"]),
            "stt_text": stt_text,
            "abandoned": abandoned,
        }

    def run_forever(self, stop_event: threading.Event,
                    enabled: Optional[threading.Event] = None) -> None:
        """Enchaîne les tours jusqu'à stop_event.set() (typiquement déclenché
        par le node ROS appelant à l'arrêt, cf. chat_node V2). Pas de thread
        créé ici, cf. docstring de module.

        `enabled` (optionnel) : interrupteur de MODE INTERACTIF piloté par
        l'appelant (topic `chat` "on"/"off" côté node). Quand il est baissé,
        aucun tour ne démarre — la boucle attend par petits pas (wait borné,
        PAS un wait() infini : il faut re-vérifier stop_event régulièrement
        pour que l'arrêt du node reste réactif même en pause). La bascule OFF
        en PLEIN tour ne coupe pas la réplique en cours (choix scénique :
        Didier finit sa phrase) — c'est le mic.stop() fait par l'appelant qui
        interrompt une ÉCOUTE en cours, cf. chat_node._on_chat_cmd."""
        self._enabled = enabled
        while not stop_event.is_set():
            if enabled is not None and not enabled.is_set():
                # mic.stop() idempotent À CHAQUE passage : certains chemins de
                # fin de tour redémarrent le micro (fin de réplique, STT
                # inexploitable) AVANT que la boucle ne voie le toggle baissé
                # — on garantit ici qu'en pause, le micro est TOUJOURS coupé,
                # quel que soit le chemin qui a rendu la main.
                self._mic.stop()
                # "off" : dédup absorbe la boucle d'attente (ré-émis à chaque
                # itération de 0,2 s tant que la pause dure) -- un seul
                # message part réellement vers on_state par pause.
                self._set_state("off")
                enabled.wait(timeout=0.2)
                continue
            self.run_once()
