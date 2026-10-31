"""Tests de vision/ai/conversation.py (V7) — orchestrateur d'un tour de
conversation. Fakes PURS uniquement : AUCUN subprocess/réseau (mic/vad/stt/
brain/tts/player sont tous des objets scriptés, jamais les vraies
implémentations arecord/aplay/openai/faster-whisper/piper de vision/audio et
vision/ai — celles-ci restent hors de portée de la CI, cf. CLAUDE.md).

TIMELINE : une liste UNIQUE partagée par tous les fakes, où chaque effet de
bord observable (mic start/stop, publish, transcribe, stream_reply,
synthesize, play, drain) ajoute un tuple. Les tests assertent des séquences
ordonnées de cette timeline — c'est l'ordre CROISÉ entre briques (micro coupé
avant thinking, animation republiée avant chaque synthèse, speaking_stop
publié même en cas d'erreur...) qui est le vrai contrat de
ConversationEngine, pas le comportement isolé d'un seul fake.
"""
import json
import os
import random
import threading
import time
import types

import pytest

from dadou_utils_ros.utils_static import ANIMATION, FACE

from vision.ai import conversation as conversation_module
from vision.ai.conversation import ConversationEngine, has_usable_text
from vision.ai.performance import RosMessage
from vision.ai.stage import StageState
from vision.audio.vad import VadEvent

REFRESH_MS = 15000
BEEPS_PCM = b"\x00\x01" * 100  # contenu bidon, seule la présence compte ici
BEEPS_RATE = 22050


# ---------------------------------------------------------------------------
# Fakes — un seul rôle chacun, tous n'écrivent que dans la timeline partagée.
# ---------------------------------------------------------------------------

class FakeMic:
    """Micro scripté : consomme une liste FIXE de trames ; frame_rms est sans
    objet ici (le fake VAD ci-dessous ignore le niveau, cf. FakeVad) —
    seul le NOMBRE d'appels à read_frame() doit correspondre au nombre
    d'événements scriptés dans FakeVad (un feed() par read_frame(), cf.
    ConversationEngine._listen_for_utterance)."""

    sample_rate = 16000

    def __init__(self, timeline, frames, preroll=b"PREROLL"):
        self._timeline = timeline
        self._frames = list(frames)
        self._preroll = preroll

    def start(self):
        self._timeline.append(("mic_start",))

    def stop(self):
        self._timeline.append(("mic_stop",))

    def read_frame(self):
        if not self._frames:
            return None
        return self._frames.pop(0)

    def frame_rms(self, frame):
        return 0.0  # valeur sans importance : FakeVad ne l'utilise pas

    def frame_peak(self, frame):
        # Valeur sans importance ici aussi : dans les tests du gate (cf. plus
        # bas), c'est FakeGate qui décide du blocage via sa séquence
        # scriptée, jamais via level/peak — même logique que frame_rms.
        return 0.0

    def preroll(self):
        return self._preroll

    def purge_preroll(self):
        # Purge du pré-roll appelée par le gate (§10.5.3) quand une trame est
        # bloquée en pleine phrase — notée dans la timeline pour les tests
        # dédiés au gate ci-dessous (jamais invoquée quand gate=None).
        self._timeline.append(("mic_purge_preroll",))


class FakeVad:
    """VAD scripté : renvoie une séquence FIXE de VadEvent/None, un par
    feed() — reproduit une machine à états réelle sans en être une (le
    comportement de EnergyVad est déjà testé indépendamment, cf.
    test_vad.py)."""

    def __init__(self, events, timeline=None):
        self._events = list(events)
        # timeline optionnelle (None par défaut, cf. usages existants qui ne
        # la fournissent pas) : sert UNIQUEMENT à noter les appels à reset()
        # pour les tests du gate — feed() n'y écrit RIEN, pour ne jamais
        # perturber les assertions de séquence COMPLÈTE des tests existants.
        self._timeline = timeline
        # Compteur de trames VUES par feed() — le test de contrat §10.8
        # ("une trame bloquée n'atteint jamais la VAD") s'appuie dessus :
        # un faux VAD qui compte, comme demandé par la spec.
        self.feed_calls = 0

    def feed(self, level):
        self.feed_calls += 1
        if not self._events:
            return None
        return self._events.pop(0)

    def reset(self):
        if self._timeline is not None:
            self._timeline.append(("vad_reset",))


class FakeStt:
    def __init__(self, timeline, text):
        self._timeline = timeline
        self._text = text

    def transcribe(self, pcm, sample_rate):
        self._timeline.append(("stt_transcribe", pcm, sample_rate))
        return self._text


class FakeSttQuiLeve:
    """STT qui lève à CHAQUE appel (erreur de dépendance, fichier
    temporaire illisible…) : le tour doit être abandonné proprement, jamais
    propager (cf. garde ajoutée le 22/10 dans run_once)."""
    def __init__(self, timeline):
        self._timeline = timeline

    def transcribe(self, pcm, sample_rate):
        self._timeline.append(("stt_transcribe", pcm, sample_rate))
        raise TypeError("open() got an unexpected keyword argument 'metadata_errors'")


class FakeBrain:
    """Brain scripté : stream_reply() yield une séquence FIXE de deltas
    (indépendante du texte reçu, qui est quand même noté dans la timeline
    pour vérifier qu'il a bien été transmis tel quel) ; peut lever une
    erreur APRÈS avoir tout streamé, pour simuler une panne LLM en cours de
    génération (cf. test_erreur_llm_publie_quand_meme_speaking_stop)."""

    def __init__(self, timeline, deltas, raise_error=False):
        self._timeline = timeline
        self._deltas = deltas
        self._raise_error = raise_error

    def stream_reply(self, user_text):
        self._timeline.append(("brain_stream_reply", user_text))
        for delta in self._deltas:
            yield delta
        if self._raise_error:
            raise RuntimeError("panne LLM simulée (test)")


class FakeTts:
    def __init__(self, timeline):
        self._timeline = timeline

    def synthesize(self, text):
        self._timeline.append(("tts_synthesize", text))
        return (b"PCM:" + text.encode(), 22050)


class FakePlayer:
    def __init__(self, timeline):
        self._timeline = timeline

    def play(self, pcm, sample_rate):
        self._timeline.append(("player_play", pcm, sample_rate))

    def play_async_raw(self, path):
        self._timeline.append(("player_play_async_raw", path))

    def drain(self):
        self._timeline.append(("player_drain",))


def _make_publish(timeline):
    def publish(message):
        timeline.append(("publish", message))
    return publish


class FakeGate:
    """Gate scripté : feed() consomme une séquence FIXE de booléens (un par
    trame VUE, bloquée ou pas — un appel par frame lue, cf.
    ConversationEngine._listen_for_utterance) et note chaque appel dans la
    timeline partagée. La vraie temporisation (hold_s, écrêtage...) est
    testée indépendamment côté vision.audio.live_audio_gate (cf.
    test_live_audio_gate.py) : ici on ne teste QUE le câblage — l'ordre des
    appels côté ConversationEngine, pas la décision elle-même."""

    def __init__(self, timeline, blocked_sequence):
        self._timeline = timeline
        self._blocked_sequence = list(blocked_sequence)

    def feed(self, level, peak, show_audio=False):
        self._timeline.append(("gate_feed", level, peak, show_audio))
        if not self._blocked_sequence:
            return False
        return self._blocked_sequence.pop(0)

    def arm_tail(self):
        self._timeline.append(("gate_arm_tail",))


def _make_engine(timeline, *, frames, vad_events, stt_text, brain_deltas,
                  brain_raises=False, beeps=True, on_state=None,
                  initial_state=None, gate=None, show_audio_active=None,
                  on_meter=None, on_timing=None, on_move=None, on_reflect=None,
                  on_look=None):
    """Assemble un ConversationEngine avec des fakes câblés sur la même
    timeline — factorise le câblage répété par les tests ci-dessous.
    L'appelant est responsable de _cleanup_beeps(engine) en fin de test.
    dead_mic_backoff_s=0.0 : pas d'attente réelle dans les tests (la valeur
    par défaut ferait dormir 0,5 s chaque test de flux micro mort).
    gate/show_audio_active/on_meter/on_timing : None par défaut (cf. les
    tests dédiés plus bas), pour ne rien changer aux appels existants de
    cette factory."""
    return ConversationEngine(
        mic=FakeMic(timeline, frames),
        vad=FakeVad(vad_events, timeline=timeline),
        stt=FakeStt(timeline, stt_text),
        brain=FakeBrain(timeline, brain_deltas, raise_error=brain_raises),
        tts=FakeTts(timeline),
        player=FakePlayer(timeline),
        publish=_make_publish(timeline),
        beeps_pcm=BEEPS_PCM if beeps else b"",
        beeps_rate=BEEPS_RATE,
        refresh_ms=REFRESH_MS,
        dead_mic_backoff_s=0.0,
        on_state=on_state,
        initial_state=initial_state,
        gate=gate,
        show_audio_active=show_audio_active,
        on_meter=on_meter,
        on_timing=on_timing,
        on_move=on_move,
        on_reflect=on_reflect,
        on_look=on_look,
    )


def _cleanup_beeps(engine):
    """Supprime le wav temporaire des bips écrit une fois au constructeur
    (cf. ConversationEngine.__init__) — sans quoi chaque test laisserait un
    fichier orphelin dans /tmp."""
    path = engine._beeps_path
    if path is not None and os.path.exists(path):
        os.remove(path)


@pytest.fixture
def timeline():
    return []


# --------------------------------------------------------------------------
# Trame micro/VAD commune : 3 trames, speech_start sur la 2e, speech_end sur
# la 3e — suffisant pour déclencher un tour complet dans tous les tests.
# --------------------------------------------------------------------------

def _speech_frames_and_events():
    frames = [b"f0", b"f1", b"f2"]
    events = [
        None,
        VadEvent(kind="speech_start", preroll_frames=2),
        VadEvent(kind="speech_end", reason="silence"),
    ]
    return frames, events


# --------------------------------------------------------------------------
# Tour nominal : ordre exact des publish + pipeline TTS phrase par phrase.
# --------------------------------------------------------------------------

def test_nominal_turn_ordre_exact_des_evenements(timeline):
    frames, events = _speech_frames_and_events()
    # Réponse LLM streamée en UN SEUL delta : "Salut." (phrase confirmée),
    # une didascalie *rit* (mappée sur "joie", cf. performance.py), une
    # deuxième phrase "Comment ça va ?", puis le JSON d'émotion final. Un
    # seul delta suffit à produire tous ces événements dès le feed() (cf.
    # stream_parser.py : seule la partie JSON est retenue pour le flush()).
    deltas = ['Salut. *rit* Comment ça va ? {"emotion": "happy"}']

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="raconte une blague", brain_deltas=deltas,
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True

    beeps_path = engine._beeps_path
    assert beeps_path is not None

    assert timeline == [
        ("mic_start",),
        ("mic_stop",),
        ("publish", RosMessage(FACE, json.dumps("reflechit"))),
        ("player_play_async_raw", beeps_path),
        ("stt_transcribe", b"PREROLLf2", 16000),
        ("brain_stream_reply", "raconte une blague"),
        ("publish", RosMessage(ANIMATION, json.dumps("parle"), time_ms=REFRESH_MS)),
        ("tts_synthesize", "Salut."),
        ("player_play", b"PCM:Salut.", 22050),
        ("publish", RosMessage(FACE, json.dumps("joie"))),  # didascalie "rit"
        ("publish", RosMessage(ANIMATION, json.dumps("parle"), time_ms=REFRESH_MS)),
        ("tts_synthesize", "Comment ça va ?"),
        # Bytes non-ASCII (ç/à) : littéral b"..." interdit en Python, on
        # encode dynamiquement plutôt que de simplifier le texte de test.
        ("player_play", b"PCM:" + "Comment ça va ?".encode(), 22050),
        ("player_drain",),
        ("publish", RosMessage(ANIMATION, json.dumps(False))),  # speaking_stop
        ("publish", RosMessage(FACE, json.dumps("joie"))),  # emotion happy -> joie
        ("mic_start",),
    ]


def test_micro_coupe_avant_la_parole_et_redemarre_apres(timeline):
    # Même scénario que le tour nominal : on vérifie ICI spécifiquement la
    # règle anti-larsen (cf. vision.audio.mic.MicCapture.stop) — le micro
    # est coupé AVANT toute publication liée à la réponse, et redémarré
    # SEULEMENT après que toute la parole a été jouée (drain + speaking_stop
    # + emotion), jamais entre-temps.
    frames, events = _speech_frames_and_events()
    deltas = ['Salut. {"emotion": "neutral"}']

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="salut", brain_deltas=deltas,
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    tags = [event[0] for event in timeline]

    mic_stop_index = tags.index("mic_stop")
    # Aucun mic_start entre le mic_stop initial et la toute fin du tour.
    assert "mic_start" not in tags[mic_stop_index + 1:-1]
    # Le dernier événement de la timeline est bien le redémarrage du micro.
    assert tags[-1] == "mic_start"
    # Le micro est coupé avant toute action côté parole (bips/STT/LLM/TTS).
    assert mic_stop_index < tags.index("player_play_async_raw")
    assert mic_stop_index < tags.index("stt_transcribe")


# --------------------------------------------------------------------------
# STT inexploitable (vide, trop court, ou PONCTUATION PURE — whisper transcrit
# le bruit en "... ... ...", vécu au premier test micro caméra 2026-07-11) :
# thinking() est publié quand même (décision documentée en tête de
# vision/ai/conversation.py — réaction honnête au fait que le STT tournait
# réellement), PUIS idle() en rattrapage (correctif 2026-07-12, étude
# d'arbitrage des actionneurs côté robot, scénario S1 : le visage ne doit
# plus rester coincé sur "reflechit" après un tour abandonné) — rien d'autre
# après, surtout pas d'appel LLM payant.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("stt_text", ["", "a", "... ... ... ...", " ?! . "])
def test_stt_inexploitable_publie_thinking_puis_idle(timeline, stt_text):
    frames, events = _speech_frames_and_events()

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text=stt_text, brain_deltas=["ne doit jamais être utilisé"],
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is False

    tags = [event[0] for event in timeline]
    # thinking() PUIS idle() : ce sont les DEUX SEULS publish de tout le
    # tour (plus rien après le rattrapage, cf. commentaire ci-dessus).
    publishes = [event[1] for event in timeline if event[0] == "publish"]
    assert publishes == [
        RosMessage(FACE, json.dumps("reflechit")),
        RosMessage(FACE, json.dumps("stop")),  # idle()
    ]
    # Le LLM n'a JAMAIS été sollicité : le tour est abandonné avant.
    assert "brain_stream_reply" not in tags
    assert "tts_synthesize" not in tags
    # Le micro est bien redémarré malgré l'abandon, APRÈS le rattrapage idle().
    assert tags[-1] == "mic_start"
    assert tags.count("mic_start") == 2  # le start() initial + le restart
    assert tags.index("publish") < tags.index("mic_start", 1)


# --------------------------------------------------------------------------
# Panne LLM en cours de génération : le spectacle continue (speaking_stop
# publié quand même, tour abandonné proprement, pas d'exception qui remonte).
# --------------------------------------------------------------------------

def test_erreur_llm_publie_quand_meme_speaking_stop(timeline):
    frames, events = _speech_frames_and_events()
    # Un premier delta produit une Sentence complète (donc une synthèse/
    # lecture AVANT la panne) ; le générateur lève ensuite une erreur après
    # avoir tout streamé (cf. FakeBrain.stream_reply).
    deltas = ["Bonjour ! "]

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="salut", brain_deltas=deltas, brain_raises=True,
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is False

    tags = [event[0] for event in timeline]
    # La phrase reçue AVANT la panne a bien été jouée.
    assert ("tts_synthesize", "Bonjour !") in timeline
    assert ("player_play", b"PCM:Bonjour !", 22050) in timeline
    # speaking_stop est publié MALGRÉ l'erreur, PUIS idle() (correctif du
    # 2026-09-13, cf. DÉCISION/CORRECTIF en tête de module) : sans lui,
    # l'expression "parle" (loop:true côté robot) resterait à s'agiter
    # indéfiniment après un tour cassé, aucun JSON d'émotion n'ayant jamais
    # été vu (tour abandonné avant flush()) pour la remplacer.
    publishes = [event[1] for event in timeline if event[0] == "publish"]
    assert publishes[-2] == RosMessage(ANIMATION, json.dumps(False))
    assert publishes[-1] == RosMessage(FACE, json.dumps("stop"))
    # drain() n'est PAS appelé : on abandonne immédiatement sur erreur, sans
    # attendre la fin de la lecture de ce qui est déjà en file.
    assert "player_drain" not in tags
    assert tags[-1] == "mic_start"


# --------------------------------------------------------------------------
# Rattrapage visage en fin de réplique (2026-09-13, "la bouche n'est pas
# raccord avec la parole" -- David, cf. DÉCISION/CORRECTIF en tête de module).
# C'est le test ci-dessous (sans émotion finale) qui aurait attrapé le bug :
# emotion(None) renvoie une liste vide, donc AUCUN publish sur le topic face
# ne partait après speaking_stop() -- l'expression "parle" (loop:true côté
# robot) restait à s'agiter indéfiniment pendant toute l'écoute suivante.
# --------------------------------------------------------------------------

def test_tour_nominal_sans_emotion_publie_idle_en_rattrapage(timeline):
    frames, events = _speech_frames_and_events()

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="salut", brain_deltas=["Salut."],  # aucun JSON d'émotion
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    publishes = [event[1] for event in timeline if event[0] == "publish"]
    # ORDRE : idle() part APRÈS speaking_stop(), jamais avant -- sinon
    # l'animation "parle" encore en cours réécraserait le visage neutre.
    assert publishes[-2] == RosMessage(ANIMATION, json.dumps(False))  # speaking_stop
    assert publishes[-1] == RosMessage(FACE, json.dumps("stop"))  # idle()


def test_tour_nominal_avec_emotion_ne_publie_pas_idle_en_plus(timeline):
    # Une émotion EST exploitée par le LLM : elle doit être publiée telle
    # quelle, JAMAIS écrasée par un idle() superflu juste après (le rattrapage
    # ne doit se déclencher QUE quand emotion() n'a rien produit).
    frames, events = _speech_frames_and_events()

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="salut", brain_deltas=['Salut. {"emotion": "happy"}'],
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    publishes = [event[1] for event in timeline if event[0] == "publish"]
    assert publishes[-2] == RosMessage(ANIMATION, json.dumps(False))  # speaking_stop
    assert publishes[-1] == RosMessage(FACE, json.dumps("joie"))  # emotion happy -> joie, PAS idle()


# --------------------------------------------------------------------------
# Flux micro mort en cours d'écoute : abandon propre, pas d'exception.
# --------------------------------------------------------------------------

def test_flux_micro_mort_abandonne_le_tour_proprement(timeline, caplog):
    # Une seule trame puis plus rien (read_frame() renverra None ensuite) :
    # aucun speech_start n'est jamais atteint.
    frames = [b"f0"]
    vad_events = [None]

    engine = _make_engine(
        timeline, frames=frames, vad_events=vad_events,
        stt_text="jamais utilisé", brain_deltas=["jamais utilisé"],
    )
    try:
        with caplog.at_level("WARNING", logger="vision.ai.conversation"):
            result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is False
    tags = [event[0] for event in timeline]
    assert "publish" not in tags  # même thinking() n'est pas atteint ici
    assert "stt_transcribe" not in tags
    assert tags == ["mic_start", "mic_start"]  # start initial + restart sur flux mort
    # L'incident est VISIBLE dans les logs (le premier test réel a montré
    # qu'une boucle micro-mort silencieuse est indiagnosticable en direct).
    assert any("micro mort" in record.message for record in caplog.records)


# --------------------------------------------------------------------------
# Filtre de texte STT exploitable : au moins 2 caractères alphanumériques
# (whisper transcrit le bruit pur en ponctuation, cf. has_usable_text).
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    (None, False),
    ("", False),
    ("a", False),                    # 1 seul alphanumérique
    ("... ... ... ...", False),      # bruit transcrit en ponctuation pure
    (" ?! . ", False),
    ("ça", True),                    # 2 alphanumériques (accentué compris)
    ("Salut Didier !", True),
    ("a1", True),
])
def test_has_usable_text(text, expected):
    assert has_usable_text(text) is expected


# --------------------------------------------------------------------------
# Mode interactif (toggle chat on/off, cf. chat_node) : en pause, AUCUN tour
# ne démarre et le micro est maintenu coupé ; une coupure micro volontaire
# (OFF pendant l'écoute) n'est PAS traitée comme un incident.
# --------------------------------------------------------------------------

def test_run_forever_en_pause_ne_lance_aucun_tour_et_coupe_le_micro(timeline):
    engine = _make_engine(
        timeline, frames=[b"f0"], vad_events=[None],
        stt_text="jamais utilisé", brain_deltas=["jamais utilisé"],
    )
    stop_event = threading.Event()
    enabled = threading.Event()  # baissé = mode interactif désactivé

    thread = threading.Thread(
        target=engine.run_forever, args=(stop_event, enabled), daemon=True)
    try:
        thread.start()
        time.sleep(0.05)  # laisse la boucle de pause tourner quelques cycles
        stop_event.set()
        thread.join(timeout=2.0)
        assert not thread.is_alive()
    finally:
        stop_event.set()
        _cleanup_beeps(engine)

    tags = [event[0] for event in timeline]
    # Aucun tour n'a démarré (pas de mic_start = pas de run_once) ; le micro
    # a été activement maintenu coupé pendant la pause.
    assert "mic_start" not in tags
    assert "mic_stop" in tags


def test_micro_coupe_volontairement_pas_de_restart_ni_warning(timeline, caplog):
    # Coupure volontaire : l'interrupteur est BAISSÉ au moment où le flux
    # micro meurt (scénario toggle OFF pendant l'écoute, cf.
    # chat_node._on_chat_cmd qui fait mic.stop()).
    engine = _make_engine(
        timeline, frames=[b"f0"], vad_events=[None],
        stt_text="jamais utilisé", brain_deltas=["jamais utilisé"],
    )
    engine._enabled = threading.Event()  # posé normalement par run_forever

    try:
        with caplog.at_level("INFO", logger="vision.ai.conversation"):
            result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is False
    tags = [event[0] for event in timeline]
    # PAS de restart micro : il doit rester coupé pendant toute la pause.
    assert tags == ["mic_start"]  # uniquement le start initial du tour
    # Pas de warning « micro mort » : ce n'est pas un incident.
    assert not any(record.levelname == "WARNING" for record in caplog.records)


# --------------------------------------------------------------------------
# Topic d'état du chat (`on_state`, lot D0 outillage — cf.
# dadou_robot_ros/docs/etude-declenchement-conversation.md §6.1/§6.2 : l'état
# listening/thinking/speaking/off est consommé par la régie, le
# télédiagnostic et le futur engagement_node). Dédup interne testée ici, pas
# seulement câblée : c'est le contrat qui protège un abonné ROS d'un flot de
# messages identiques (pause à 5 Hz, speaking republié par Sentence).
# --------------------------------------------------------------------------

def test_tour_complet_emet_la_sequence_d_etats_avec_dedup_speaking(timeline):
    # Deux Sentences dans la réponse (cf. deltas) : "speaking" ne doit
    # apparaître qu'UNE SEULE FOIS dans la séquence malgré les deux
    # publications de speaking_start (dédup interne de _set_state).
    frames, events = _speech_frames_and_events()
    deltas = ['Salut. Comment ça va ? {"emotion": "neutral"}']
    states = []

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="salut", brain_deltas=deltas, on_state=states.append,
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    assert states == ["listening", "thinking", "speaking", "listening"]


def test_tour_abandonne_stt_inexploitable_n_emet_jamais_speaking(timeline):
    frames, events = _speech_frames_and_events()
    states = []

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="a", brain_deltas=["ne doit jamais être utilisé"],
        on_state=states.append,
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is False
    assert states == ["listening", "thinking", "listening"]
    assert "speaking" not in states


def test_callback_on_state_qui_leve_ne_casse_pas_le_tour(timeline, caplog):
    # Un on_state qui plante à CHAQUE appel ne doit jamais empêcher le tour
    # de se terminer normalement (try/except de _set_state) -- seule la
    # notification d'état est perdue, jamais le tour de conversation.
    frames, events = _speech_frames_and_events()
    deltas = ['Salut. {"emotion": "neutral"}']

    def on_state(_state):
        raise RuntimeError("callback on_state cassé (test)")

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="salut", brain_deltas=deltas, on_state=on_state,
    )
    try:
        with caplog.at_level("WARNING", logger="vision.ai.conversation"):
            result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True  # le tour est allé jusqu'au bout malgré le callback cassé
    assert any("on_state" in record.message for record in caplog.records)


def test_initial_state_emis_par_le_moteur_et_deduplique_au_premier_tour(timeline):
    # L'état initial est émis PAR LE MOTEUR à la construction (chat_node lui
    # passe initial_state="listening" pour que le topic latché ait une valeur
    # avant même le premier tour) — et la dédup absorbe le "listening" que
    # run_once() re-signale ensuite : UN SEUL "listening" en tête de séquence,
    # jamais de doublon sur le topic. Fige aussi l'interdit de revue : c'est
    # le constructeur qui amorce _last_state, pas un écrivain extérieur.
    frames, events = _speech_frames_and_events()
    deltas = ['Salut. {"emotion": "neutral"}']
    states = []

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="salut", brain_deltas=deltas, on_state=states.append,
        initial_state="listening",
    )
    try:
        assert states == ["listening"]  # émis dès la construction
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    assert states == ["listening", "thinking", "speaking", "listening"]


def test_run_forever_pause_off_emis_une_seule_fois(timeline):
    # Plusieurs itérations de la boucle d'attente (0,2 s) pendant la pause :
    # "off" ne doit être notifié qu'UNE SEULE FOIS grâce à la dédup, pas à
    # chaque tour de boucle.
    engine = _make_engine(
        timeline, frames=[b"f0"], vad_events=[None],
        stt_text="jamais utilisé", brain_deltas=["jamais utilisé"],
    )
    states = []
    engine._on_state = states.append
    stop_event = threading.Event()
    enabled = threading.Event()  # baissé = mode interactif désactivé

    thread = threading.Thread(
        target=engine.run_forever, args=(stop_event, enabled), daemon=True)
    try:
        thread.start()
        time.sleep(0.5)  # laisse plusieurs cycles d'attente de 0,2 s tourner
        stop_event.set()
        thread.join(timeout=2.0)
        assert not thread.is_alive()
    finally:
        stop_event.set()
        _cleanup_beeps(engine)

    assert states == ["off"]


# --------------------------------------------------------------------------
# Gate « source audio vivante » (half-duplex élargi, lot du 2026-08-30, cf.
# dadou_robot_ros/docs/etude-declenchement-conversation.md §10) — contrat de
# tests fixé par §10.8 : les trames bloquées n'atteignent jamais la VAD, un
# blocage en pleine phrase jette l'énoncé partiel, gate=None laisse le
# comportement strictement inchangé, et le micro redémarre avec le gate
# amorcé (arm_tail) après drain(). La vraie décision de blocage (niveaux,
# écrêtage, maintien...) est testée indépendamment côté
# test_live_audio_gate.py -- ici on ne teste QUE le câblage.
# --------------------------------------------------------------------------

def test_trame_bloquee_par_le_gate_n_atteint_jamais_la_vad(timeline):
    # 3 trames, celle du MILIEU est bloquée : la VAD ne doit voir QUE les
    # deux autres (feed_calls == 2, jamais 3) -- "faux VAD compteur" demandé
    # par la spec (§10.8).
    frames = [b"f0", b"f1", b"f2"]
    vad = FakeVad([None, None])
    gate = FakeGate(timeline, blocked_sequence=[False, True, False])

    engine = ConversationEngine(
        mic=FakeMic(timeline, frames),
        vad=vad,
        stt=FakeStt(timeline, "jamais utilisé"),
        brain=FakeBrain(timeline, ["jamais utilisé"]),
        tts=FakeTts(timeline),
        player=FakePlayer(timeline),
        publish=_make_publish(timeline),
        gate=gate,
    )
    try:
        result = engine._listen_for_utterance()
    finally:
        _cleanup_beeps(engine)

    assert result is None  # frames épuisées sans qu'aucune parole ne démarre
    assert vad.feed_calls == 2  # PAS 3 : la trame bloquée n'a jamais atteint feed()
    # La trame bloquée est quand même vue par le gate lui-même (3 appels).
    gate_calls = [event for event in timeline if event[0] == "gate_feed"]
    assert len(gate_calls) == 3


def test_blocage_en_pleine_phrase_jette_l_enonce_partiel(timeline):
    # Un premier speech_start démarre un énoncé (f0, f1 accumulées), puis le
    # gate bloque EN PLEIN MILIEU (f2) : l'énoncé partiel doit être jeté (pas
    # de recollage), le pré-roll purgé et la VAD réarmée -- un DEUXIÈME
    # speech_start légitime (f3, f4) doit repartir de zéro.
    frames = [b"f0", b"f1", b"f2", b"f3", b"f4"]
    vad_events = [
        VadEvent(kind="speech_start", preroll_frames=2),  # f0
        None,                                              # f1 (mi-phrase)
        VadEvent(kind="speech_start", preroll_frames=2),  # f3 (nouveau départ)
        VadEvent(kind="speech_end", reason="silence"),    # f4
    ]
    gate = FakeGate(timeline, blocked_sequence=[False, False, True, False, False])

    engine = _make_engine(
        timeline, frames=frames, vad_events=vad_events,
        stt_text="peu importe", brain_deltas=["peu importe {\"emotion\": \"neutral\"}"],
        gate=gate,
    )
    try:
        engine.run_once()
    finally:
        _cleanup_beeps(engine)

    # Le STT reçoit UNIQUEMENT le pré-roll + f4 du SECOND énoncé -- si le
    # partiel (PREROLL+f1) n'avait pas été jeté, ces octets se retrouveraient
    # concaténés ou dédoublés dans les octets transmis.
    assert ("stt_transcribe", b"PREROLLf4", 16000) in timeline
    tags = [event[0] for event in timeline]
    assert tags.count("mic_purge_preroll") == 1  # une seule trame bloquée
    assert tags.count("vad_reset") == 1


def test_gate_none_laisse_le_chemin_gate_totalement_inerte(timeline):
    # gate=None (défaut) : AUCUNE méthode liée au gate ne doit jamais être
    # sollicitée -- clause de réversibilité du lot (§10.5 : "les tests
    # existants restent verts sans y toucher"). Vérifié ici en profondeur
    # (pas seulement par l'absence de régression sur les tests existants)
    # avec un mic/VAD qui LÈVENT si frame_peak/purge_preroll/reset sont
    # appelés malgré tout.
    class PoisonedMic(FakeMic):
        def frame_peak(self, frame):
            raise AssertionError("frame_peak appelé alors que gate=None")

        def purge_preroll(self):
            raise AssertionError("purge_preroll appelé alors que gate=None")

    class PoisonedVad(FakeVad):
        def reset(self):
            raise AssertionError("vad.reset() appelé alors que gate=None")

    frames, events = _speech_frames_and_events()
    engine = ConversationEngine(
        mic=PoisonedMic(timeline, frames),
        vad=PoisonedVad(events),
        stt=FakeStt(timeline, "salut"),
        brain=FakeBrain(timeline, ['Salut. {"emotion": "neutral"}']),
        tts=FakeTts(timeline),
        player=FakePlayer(timeline),
        publish=_make_publish(timeline),
        beeps_pcm=BEEPS_PCM, beeps_rate=BEEPS_RATE, refresh_ms=REFRESH_MS,
        dead_mic_backoff_s=0.0,
        # gate et show_audio_active volontairement OMIS (défaut None).
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True  # le tour s'est déroulé normalement malgré les pièges


def test_apres_drain_le_micro_redemarre_avec_le_gate_amorce(timeline):
    # arm_tail() DOIT être appelé juste AVANT le mic_start final qui relance
    # l'écoute après que Didier a fini de parler (§10.5 : "dans les DEUX
    # sorties de _speak_reply") -- chemin nominal (succès, après drain()).
    frames, events = _speech_frames_and_events()
    gate = FakeGate(timeline, blocked_sequence=[False, False, False])

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="salut", brain_deltas=['Salut. {"emotion": "neutral"}'],
        gate=gate,
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    tags = [event[0] for event in timeline]
    final_mic_start = tags.index("mic_start", 1)  # le restart, pas le start initial
    assert tags[final_mic_start - 1] == "gate_arm_tail"


def test_apres_une_erreur_llm_le_micro_redemarre_aussi_avec_le_gate_amorce(timeline):
    # Même exigence que ci-dessus, sur l'AUTRE sortie de _speak_reply (celle
    # de l'exception) : le player peut encore jouer un reliquat déjà enfilé
    # (pas de drain() sur ce chemin) -- la queue acoustique doit quand même
    # être armée avant de réécouter.
    frames, events = _speech_frames_and_events()
    gate = FakeGate(timeline, blocked_sequence=[False, False, False])

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="salut", brain_deltas=["Bonjour ! "], brain_raises=True,
        gate=gate,
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is False
    tags = [event[0] for event in timeline]
    final_mic_start = tags.index("mic_start", 1)
    assert tags[final_mic_start - 1] == "gate_arm_tail"


def test_show_audio_active_est_transmis_au_gate_a_chaque_trame(timeline):
    # show_audio_active est un CALLABLE réévalué à chaque frame (pas un bool
    # figé, cf. docstring de ConversationEngine.__init__) : sa valeur de
    # retour doit se retrouver telle quelle dans le show_audio passé à
    # gate.feed().
    frames = [b"f0", b"f1"]
    gate = FakeGate(timeline, blocked_sequence=[False, False])

    engine = ConversationEngine(
        mic=FakeMic(timeline, frames),
        vad=FakeVad([None, None]),
        stt=FakeStt(timeline, "jamais utilisé"),
        brain=FakeBrain(timeline, ["jamais utilisé"]),
        tts=FakeTts(timeline),
        player=FakePlayer(timeline),
        publish=_make_publish(timeline),
        gate=gate, show_audio_active=lambda: True,
    )
    try:
        engine._listen_for_utterance()
    finally:
        _cleanup_beeps(engine)

    gate_calls = [event for event in timeline if event[0] == "gate_feed"]
    assert len(gate_calls) == 2
    assert all(call[3] is True for call in gate_calls)


# --------------------------------------------------------------------------
# Vumètre web + latences par tour (2026-09-13, demande de David en séance —
# cf. docstring de module OBSERVABILITÉ). Mêmes clauses de réversibilité que
# le gate ci-dessus : gate/show_audio_active/on_meter/on_timing restent
# indépendants les uns des autres, on_meter/on_timing=None (déjà le défaut de
# TOUS les tests précédents de ce fichier, jamais modifiés) prouve que le
# reste de la suite couvre déjà "sans les kwargs, rien ne change".
# --------------------------------------------------------------------------

def test_on_meter_appele_pour_chaque_trame_avec_blocage_gate(timeline):
    # 3 trames, celle du MILIEU bloquée par le gate : on_meter doit être
    # notifié pour LES TROIS (contrairement à la VAD qui n'en voit que 2, cf.
    # test_trame_bloquee_par_le_gate_n_atteint_jamais_la_vad) -- c'est
    # justement ce blocage que le vumètre web doit pouvoir montrer en direct.
    frames = [b"f0", b"f1", b"f2"]
    vad = FakeVad([None, None])
    gate = FakeGate(timeline, blocked_sequence=[False, True, False])
    meter_calls = []

    engine = ConversationEngine(
        mic=FakeMic(timeline, frames),
        vad=vad,
        stt=FakeStt(timeline, "jamais utilisé"),
        brain=FakeBrain(timeline, ["jamais utilisé"]),
        tts=FakeTts(timeline),
        player=FakePlayer(timeline),
        publish=_make_publish(timeline),
        gate=gate,
        on_meter=lambda level, peak, blocked, in_speech:
            meter_calls.append((level, peak, blocked, in_speech)),
    )
    try:
        engine._listen_for_utterance()
    finally:
        _cleanup_beeps(engine)

    assert len(meter_calls) == 3  # une notification par trame LUE, pas par trame VUE par la VAD
    assert [call[2] for call in meter_calls] == [False, True, False]


def test_on_meter_sans_gate_blocked_toujours_false(timeline):
    # gate=None (comportement historique, cf. clause de réversibilité) :
    # on_meter reste utilisable seul, blocked vaut toujours False -- il n'y a
    # simplement personne pour jeter une trame.
    frames, events = _speech_frames_and_events()
    meter_calls = []

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="salut", brain_deltas=['Salut. {"emotion": "neutral"}'],
        on_meter=lambda level, peak, blocked, in_speech:
            meter_calls.append((level, peak, blocked, in_speech)),
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    assert len(meter_calls) == 3  # les 3 trames de _speech_frames_and_events()
    assert all(call[2] is False for call in meter_calls)


def test_callback_on_meter_qui_leve_ne_casse_pas_le_tour(timeline, caplog):
    # Le vumètre est un outil de confort, jamais un signal de sécurité (cf.
    # docstring de module) : un on_meter qui plante à CHAQUE trame ne doit
    # jamais empêcher le tour de se terminer normalement.
    frames, events = _speech_frames_and_events()

    def failing_meter(level, peak, blocked, in_speech):
        raise RuntimeError("vumètre cassé (test)")

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="salut", brain_deltas=['Salut. {"emotion": "neutral"}'],
        on_meter=failing_meter,
    )
    try:
        with caplog.at_level("DEBUG", logger="vision.ai.conversation"):
            result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True  # le tour est allé jusqu'au bout malgré le callback cassé
    assert any("on_meter" in record.message for record in caplog.records)


def test_on_timing_appele_une_fois_par_tour_nominal(timeline):
    # UNE SEULE notification par tour, même si la réponse contient plusieurs
    # Sentence (donc plusieurs synthèses/lectures) -- seul le PREMIER jalon de
    # chaque sorte compte pour la latence perçue.
    frames, events = _speech_frames_and_events()
    timing_calls = []

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="salut", brain_deltas=['Salut. Comment ça va ? {"emotion": "neutral"}'],
        on_timing=lambda timing: timing_calls.append(timing),
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    assert len(timing_calls) == 1
    timing = timing_calls[0]
    assert timing["abandoned"] is False
    assert timing["stt_text"] == "salut"
    # Tous les jalons sont atteints dans un tour nominal : aucun ne doit
    # rester None (cf. docstring de module -- None = "jamais atteint").
    assert timing["stt_ms"] >= 0.0
    assert timing["llm_first_ms"] is not None and timing["llm_first_ms"] >= 0.0
    assert timing["audio_first_ms"] is not None and timing["audio_first_ms"] >= 0.0
    assert timing["total_ms"] is not None and timing["total_ms"] >= 0.0


def test_on_timing_abandoned_sur_stt_inexploitable(timeline):
    # Réplique EXACTE du contrat documenté en tête de module : STT
    # inexploitable -> abandoned=True, champs AVAL (après le STT) à None.
    frames, events = _speech_frames_and_events()
    timing_calls = []

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="... ...", brain_deltas=["jamais utilisé"],
        on_timing=lambda timing: timing_calls.append(timing),
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is False
    assert len(timing_calls) == 1
    timing = timing_calls[0]
    assert timing["abandoned"] is True
    assert timing["stt_text"] == "... ..."
    assert timing["stt_ms"] >= 0.0  # le STT, lui, a bien tourné
    assert timing["llm_first_ms"] is None
    assert timing["audio_first_ms"] is None
    assert timing["total_ms"] is None


def test_on_timing_abandoned_sur_erreur_llm(timeline):
    # Extension du contrat documenté (cf. commentaire de _speak_reply) : une
    # panne LLM/TTS EST aussi la fin d'un tour, donc notifiée -- ici la panne
    # survient AVANT toute Sentence (aucun delta ne contient de frontière de
    # phrase), les jalons aval restent donc None comme sur l'abandon STT.
    frames, events = _speech_frames_and_events()
    timing_calls = []

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        # "Bonjour" SANS terminateur de phrase (contrairement au delta du
        # test test_erreur_llm_publie_quand_meme_speaking_stop) : aucune
        # frontière de phrase n'est encore vue quand l'exception part, donc
        # aucune Sentence n'est jamais émise -- condition nécessaire pour
        # tester le cas "jalons aval jamais atteints".
        stt_text="salut", brain_deltas=["Bonjour"], brain_raises=True,
        on_timing=lambda timing: timing_calls.append(timing),
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is False
    assert len(timing_calls) == 1
    timing = timing_calls[0]
    assert timing["abandoned"] is True
    assert timing["llm_first_ms"] is None
    assert timing["audio_first_ms"] is None
    assert timing["total_ms"] is None


def test_on_timing_jamais_appele_si_flux_micro_mort_avant_le_stt(timeline):
    # Un tour qui n'atteint jamais le STT (flux micro mort en cours d'écoute)
    # n'a rien à mesurer -- cf. docstring de run_once : ce chemin ne doit
    # JAMAIS déclencher on_timing (pas de notification à moitié remplie).
    timing_calls = []

    engine = _make_engine(
        timeline, frames=[], vad_events=[],
        stt_text="jamais utilisé", brain_deltas=["jamais utilisé"],
        on_timing=lambda timing: timing_calls.append(timing),
    )
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is False
    assert timing_calls == []


def test_callback_on_timing_qui_leve_ne_casse_pas_le_tour(timeline, caplog):
    # Même exigence que pour on_meter/on_state : un tableau de bord cassé ne
    # doit jamais rendre Didier muet.
    frames, events = _speech_frames_and_events()

    def failing_timing(_timing):
        raise RuntimeError("console de diagnostic cassée (test)")

    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="salut", brain_deltas=['Salut. {"emotion": "neutral"}'],
        on_timing=failing_timing,
    )
    try:
        with caplog.at_level("WARNING", logger="vision.ai.conversation"):
            result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True  # le tour est allé jusqu'au bout malgré le callback cassé
    assert any("on_timing" in record.message for record in caplog.records)


# --------------------------------------------------------------------------
# Régie du chat (lot R3 « Chantiers », 2026-10-14 — dadou_robot_ros/docs/
# etude-repetition-simulee.md §13.6, cf. docstring de module RÉGIE de
# vision.ai.conversation) : texte tapé sans micro ni STT, pannes deaf/garble/
# delay/mute/phantom, consigne en second message system, transcript. Les
# bornes de StageState (plafond, péremption) sont testées dans test_stage.py ;
# ici on teste le CÂBLAGE dans le tour. Les pannes sont armées avec
# time.monotonic() : c'est l'horloge que le moteur lit.
# --------------------------------------------------------------------------

PARLE = RosMessage(ANIMATION, json.dumps("parle"), time_ms=REFRESH_MS)
THINKING = RosMessage(FACE, json.dumps("reflechit"))
IDLE = RosMessage(FACE, json.dumps("stop"))
SPEAKING_STOP = RosMessage(ANIMATION, json.dumps(False))
JOIE = RosMessage(FACE, json.dumps("joie"))


class FakeStageBrain(FakeBrain):
    """FakeBrain qui accepte `extra_system` (consigne de régie) et le note à
    part, dans l'ordre des appels — la timeline garde le même tuple
    ("brain_stream_reply", texte) que les tests historiques.
    `**kwargs` (metteur en scène, lot P) : situation/direction notés dans
    `calls` (un dict par appel) pour les tests qui les lisent."""

    def __init__(self, timeline, deltas, raise_error=False):
        super().__init__(timeline, deltas, raise_error=raise_error)
        self.extra_systems = []
        self.calls = []

    def stream_reply(self, user_text, extra_system=None, **kwargs):
        self.extra_systems.append(extra_system)
        self.calls.append(dict(kwargs, user_text=user_text, extra_system=extra_system))
        yield from super().stream_reply(user_text)


class FakeMicAvecRegie(FakeMic):
    """FakeMic qui appelle `on_read(n)` (n = numéro de lecture, à partir de 1)
    AVANT de rendre la trame : simule un callback chat_node qui pousse un
    texte pendant que le moteur écoute (thread rclpy.spin en vrai)."""

    def __init__(self, timeline, frames, on_read):
        super().__init__(timeline, frames)
        self._on_read = on_read
        self._reads = 0

    def read_frame(self):
        self._reads += 1
        self._on_read(self._reads)
        return super().read_frame()


def _make_stage_engine(timeline, stage, *, brain_deltas, frames=(), vad_events=(),
                       stt_text="jamais utilisé", mic=None, on_state=None,
                       on_transcript=None, on_timing=None, dead_mic_backoff_s=0.0,
                       on_move=None, on_reflect=None):
    """Factory dédiée aux tests de régie (la factory historique reste
    intacte) : renvoie (engine, brain) pour lire brain.extra_systems."""
    brain = FakeStageBrain(timeline, brain_deltas)
    engine = ConversationEngine(
        mic=mic if mic is not None else FakeMic(timeline, frames),
        vad=FakeVad(vad_events, timeline=timeline),
        stt=FakeStt(timeline, stt_text),
        brain=brain,
        tts=FakeTts(timeline),
        player=FakePlayer(timeline),
        publish=_make_publish(timeline),
        beeps_pcm=BEEPS_PCM,
        beeps_rate=BEEPS_RATE,
        refresh_ms=REFRESH_MS,
        dead_mic_backoff_s=dead_mic_backoff_s,
        on_state=on_state,
        on_timing=on_timing,
        stage=stage,
        on_transcript=on_transcript,
        on_move=on_move,
        on_reflect=on_reflect,
    )
    return engine, brain


def _transcript_recorder():
    lines = []
    return lines, lambda role, text: lines.append((role, text))


def test_texte_tape_servi_sans_micro_ni_stt(timeline):
    stage = StageState()
    stage.push_text("bonjour Didier")
    states = []
    lines, on_transcript = _transcript_recorder()
    engine, _brain = _make_stage_engine(
        timeline, stage, brain_deltas=['Salut. {"emotion": "happy"}'],
        on_state=states.append, on_transcript=on_transcript)
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    # Pas de mic_start en tête, pas de STT : le micro est coupé (il tournait
    # peut-être depuis la fin du tour précédent), puis le tour se joue comme
    # après un STT.
    assert timeline == [
        ("mic_stop",),
        ("publish", THINKING),
        ("player_play_async_raw", engine._beeps_path),
        ("brain_stream_reply", "bonjour Didier"),
        ("publish", PARLE),
        ("tts_synthesize", "Salut."),
        ("player_play", b"PCM:Salut.", 22050),
        ("player_drain",),
        ("publish", SPEAKING_STOP),
        ("publish", JOIE),
        ("mic_start",),
    ]
    assert states == ["thinking", "speaking", "listening"]
    assert lines == [("david", "bonjour Didier"), ("didier", "Salut.")]
    assert stage.has_text() is False


def test_texte_tape_pendant_l_ecoute_l_interrompt(timeline):
    stage = StageState()
    frames, events = _speech_frames_and_events()

    def on_read(n):
        if n == 3:  # en pleine phrase : f1 a déclenché speech_start
            stage.push_text("tu m'entends ?")

    mic = FakeMicAvecRegie(timeline, frames, on_read)
    engine, _brain = _make_stage_engine(
        timeline, stage, brain_deltas=["Oui."], frames=frames, vad_events=events,
        stt_text="ne doit jamais être transcrit", mic=mic)
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    tags = [event[0] for event in timeline]
    # L'énoncé PARTIEL (pré-roll + f1) est jeté : jamais transcrit.
    assert "stt_transcribe" not in tags
    # Écoute interrompue : micro coupé + VAD ramenée en IDLE, puis le texte
    # est servi (second mic_stop = anti-larsen de _serve_typed_text,
    # idempotent sur le vrai MicCapture).
    assert timeline[:5] == [
        ("mic_start",),
        ("mic_stop",),
        ("vad_reset",),
        ("mic_stop",),
        ("publish", THINKING),
    ]
    assert ("brain_stream_reply", "tu m'entends ?") in timeline


def test_texte_tape_avec_micro_coupe_n_est_pas_un_micro_mort(timeline, caplog):
    # read_frame() rend None (flux coupé) alors qu'un texte attend déjà dans
    # la file : le texte est servi, pas de faux « micro mort ».
    stage = StageState()

    def on_read(n):
        if n == 1:
            stage.push_text("allô ?")

    mic = FakeMicAvecRegie(timeline, [], on_read)  # read_frame() -> None
    engine, _brain = _make_stage_engine(timeline, stage, brain_deltas=["Oui."], mic=mic)
    try:
        with caplog.at_level("WARNING", logger="vision.ai.conversation"):
            result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    assert ("brain_stream_reply", "allô ?") in timeline
    assert not any("micro mort" in record.message for record in caplog.records)


def test_backoff_micro_mort_sonde_la_file_au_lieu_de_dormir(timeline, monkeypatch):
    stage = StageState()
    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        stage.push_text("le micro est mort, mais moi je tape")

    monkeypatch.setattr(conversation_module.time, "sleep", fake_sleep)
    engine, _brain = _make_stage_engine(
        timeline, stage, brain_deltas=["Je t'entends."], dead_mic_backoff_s=5.0)
    try:
        first = engine.run_once()   # micro mort : backoff écourté par le texte
        second = engine.run_once()  # le texte est servi au tour suivant
    finally:
        _cleanup_beeps(engine)

    assert first is False
    # UN SEUL pas de sondage (STAGE_POLL_S = 0,05 s), jamais le sleep(5.0)
    # aveugle de l'historique.
    assert sleeps == [0.05]
    assert second is True
    assert ("brain_stream_reply", "le micro est mort, mais moi je tape") in timeline


def test_panne_deaf_abandonne_le_tour_comme_un_stt_inexploitable(timeline, caplog):
    stage = StageState()
    stage.set_fault("deaf", {}, 20000, time.monotonic())
    frames, events = _speech_frames_and_events()
    states = []
    lines, on_transcript = _transcript_recorder()
    engine, brain = _make_stage_engine(
        timeline, stage, brain_deltas=["ne doit jamais être utilisé"], frames=frames,
        vad_events=events, stt_text="raconte une blague",
        on_state=states.append, on_transcript=on_transcript)
    try:
        with caplog.at_level("INFO", logger="vision.ai.conversation"):
            result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is False
    tags = [event[0] for event in timeline]
    assert "stt_transcribe" in tags          # le STT a tourné…
    assert "brain_stream_reply" not in tags  # …mais Didier n'a rien « entendu »
    publishes = [event[1] for event in timeline if event[0] == "publish"]
    assert publishes == [THINKING, IDLE]
    assert tags[-1] == "mic_start"
    assert states == ["listening", "thinking", "listening"]
    assert lines == []  # aucune ligne de transcript : rien n'a été compris
    assert any("panne deaf" in record.message for record in caplog.records)


def test_panne_garble_remplace_le_texte_compris(timeline):
    stage = StageState(rng=random.Random(42))
    stage.set_fault("garble", {}, 30000, time.monotonic())
    frames, events = _speech_frames_and_events()
    lines, on_transcript = _transcript_recorder()
    timings = []
    engine, _brain = _make_stage_engine(
        timeline, stage, brain_deltas=["Astérix ? Jamais entendu parler."], frames=frames,
        vad_events=events, stt_text="raconte une blague",
        on_transcript=on_transcript, on_timing=timings.append)
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    garbled = "Sous-titres réalisés par la communauté d'Amara.org"  # graine 42
    assert ("brain_stream_reply", garbled) in timeline
    assert ("brain_stream_reply", "raconte une blague") not in timeline
    # Transcript = ce que Didier a COMPRIS ; la console de diagnostic, elle,
    # garde la vérité technique du STT.
    assert lines[0] == ("david", garbled)
    assert timings[0]["stt_text"] == "raconte une blague"


def test_panne_garble_tire_dans_params_texts(timeline):
    stage = StageState()
    stage.set_fault("garble", {"texts": ["Tu as dit banane ?"]}, 30000, time.monotonic())
    stage.push_text("tu as dit quoi ?")
    engine, _brain = _make_stage_engine(timeline, stage, brain_deltas=["Banane."])
    try:
        engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert ("brain_stream_reply", "Tu as dit banane ?") in timeline


def test_panne_delay_dort_avant_le_llm_pendant_les_bips(timeline, monkeypatch):
    stage = StageState()
    stage.set_fault("delay", {"delay_ms": 6000}, 40000, time.monotonic())
    monkeypatch.setattr(conversation_module.time, "sleep",
                        lambda seconds: timeline.append(("sleep", seconds)))
    frames, events = _speech_frames_and_events()
    states = []
    engine, _brain = _make_stage_engine(
        timeline, stage, brain_deltas=['Euh… oui. {"emotion": "neutral"}'], frames=frames,
        vad_events=events, stt_text="tu es lent", on_state=states.append)
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    tags = [event[0] for event in timeline]
    assert ("sleep", 6.0) in timeline
    assert tags.count("sleep") == 1
    # APRÈS le STT et les bips, AVANT l'appel LLM.
    assert tags.index("player_play_async_raw") < tags.index("sleep")
    assert tags.index("stt_transcribe") < tags.index("sleep") < tags.index("brain_stream_reply")
    # L'état reste "thinking" pendant le sommeil (pas d'état intermédiaire).
    assert states == ["listening", "thinking", "speaking", "listening"]


def test_panne_mute_texte_sans_voix(timeline):
    stage = StageState()
    stage.set_fault("mute", {}, 20000, time.monotonic())
    stage.push_text("chante-moi quelque chose")
    lines, on_transcript = _transcript_recorder()
    engine, _brain = _make_stage_engine(
        timeline, stage,
        brain_deltas=['Salut. *rit* Comment ça va ? {"emotion": "happy"}'],
        on_transcript=on_transcript)
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    tags = [event[0] for event in timeline]
    assert "tts_synthesize" not in tags
    assert "player_play" not in tags
    # Tout le reste joue normalement : bouche, didascalie, émotion finale.
    publishes = [event[1] for event in timeline if event[0] == "publish"]
    assert publishes == [THINKING, PARLE, JOIE, PARLE, SPEAKING_STOP, JOIE]
    assert lines == [("david", "chante-moi quelque chose"),
                     ("didier", "Salut."), ("didier", "Comment ça va ?")]


def test_consigne_transmise_au_brain_puis_levee(timeline):
    stage = StageState()
    stage.set_instruction("Tu es amoureux du lampadaire.", time.monotonic())
    engine, brain = _make_stage_engine(timeline, stage, brain_deltas=["Qu'il est beau."])
    try:
        stage.push_text("on avance ?")
        engine.run_once()
        stage.set_instruction("", time.monotonic())
        stage.push_text("et maintenant ?")
        engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert brain.extra_systems == ["Tu es amoureux du lampadaire.", None]


def test_phantom_servi_comme_un_enonce_entendu(timeline):
    stage = StageState()
    stage.set_fault("phantom", {"text": "Sous-titres réalisés par la communauté d'Amara.org"},
                    1000, time.monotonic())
    lines, on_transcript = _transcript_recorder()
    engine, _brain = _make_stage_engine(
        timeline, stage, brain_deltas=["Merci à eux."], on_transcript=on_transcript)
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    assert lines[0] == ("david", "Sous-titres réalisés par la communauté d'Amara.org")
    assert stage.fault(time.monotonic()) == ("pass", {})


def test_transcript_sans_stage_et_appel_brain_historique(timeline):
    # on_transcript est indépendant de `stage` ; sans stage, le brain est
    # appelé SANS extra_system (FakeBrain historique ne l'accepte même pas).
    frames, events = _speech_frames_and_events()
    lines, on_transcript = _transcript_recorder()
    engine = ConversationEngine(
        mic=FakeMic(timeline, frames), vad=FakeVad(events, timeline=timeline),
        stt=FakeStt(timeline, "salut"), brain=FakeBrain(timeline, ["Salut. Ça va ?"]),
        tts=FakeTts(timeline), player=FakePlayer(timeline), publish=_make_publish(timeline),
        refresh_ms=REFRESH_MS, dead_mic_backoff_s=0.0, on_transcript=on_transcript,
    )
    assert engine.run_once() is True
    assert lines == [("david", "salut"), ("didier", "Salut."), ("didier", "Ça va ?")]


def test_callback_on_transcript_qui_leve_ne_casse_pas_le_tour(timeline, caplog):
    stage = StageState()
    stage.push_text("salut")

    def failing_transcript(_role, _text):
        raise RuntimeError("page scène cassée (test)")

    engine, _brain = _make_stage_engine(
        timeline, stage, brain_deltas=['Salut. {"emotion": "neutral"}'],
        on_transcript=failing_transcript)
    try:
        with caplog.at_level("WARNING", logger="vision.ai.conversation"):
            result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    assert ("tts_synthesize", "Salut.") in timeline
    assert any("on_transcript" in record.message for record in caplog.records)


def test_erreur_stt_abandonne_le_tour_sans_tuer_le_moteur(timeline):
    """Une exception du STT (22/10 : PyAV 19 vs faster-whisper 1.2.1) ne doit
    PAS remonter de run_once : le tour est abandonné comme un STT
    inexploitable (thinking puis idle, micro relancé), le LLM n'est jamais
    appelé, et le tour SUIVANT se déroule normalement — sans cette garde, le
    thread run_forever mourait et Didier restait sourd jusqu'au redémarrage."""
    frames, events = _speech_frames_and_events()
    engine = _make_engine(
        timeline, frames=frames, vad_events=events,
        stt_text="jamais utilisé", brain_deltas=["ne doit jamais être utilisé"],
    )
    engine._stt = FakeSttQuiLeve(timeline)
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)
    assert result is False
    tags = [event[0] for event in timeline]
    assert "stt_transcribe" in tags
    assert "brain_stream_reply" not in tags
    publishes = [event[1] for event in timeline if event[0] == "publish"]
    assert publishes == [
        RosMessage(FACE, json.dumps("reflechit")),
        RosMessage(FACE, json.dumps("stop")),  # idle() : le visage ne reste pas sur « réfléchit »
    ]
    # Le micro est relancé pour le tour suivant (mic_start APRÈS mic_stop).
    assert tags.index("mic_stop") < len(tags) - 1 - tags[::-1].index("mic_start")


# --------------------------------------------------------------------------
# Mouvement à la voix (lot I1, 2026-10-22, dadou_robot_ros/docs/
# etude-repetition-simulee.md §13.11) : la clé "marche" du JSON de fin part
# sur on_move, normalisée, et RIEN d'autre que "go"/"stop" ne passe.
# --------------------------------------------------------------------------

def _tour_avec_marche(timeline, deltas, on_move):
    frames, events = _speech_frames_and_events()
    engine = _make_engine(timeline, frames=frames, vad_events=events,
                          stt_text="avance", brain_deltas=deltas, on_move=on_move)
    try:
        return engine.run_once()
    finally:
        _cleanup_beeps(engine)


def test_marche_go_appelle_on_move_une_fois(timeline):
    ordres = []
    assert _tour_avec_marche(timeline, ['On y va. {"emotion": "happy", "marche": "go"}'],
                             ordres.append) is True
    assert ordres == ["go"]
    # L'émotion joue toujours : la clé en plus ne gêne pas le visage.
    publishes = [event[1] for event in timeline if event[0] == "publish"]
    assert publishes[-1] == RosMessage(FACE, json.dumps("joie"))


def test_marche_normalisee_casse_et_espaces(timeline):
    ordres = []
    _tour_avec_marche(timeline, ['Halte. {"emotion": "neutral", "marche": "STOP "}'], ordres.append)
    assert ordres == ["stop"]


@pytest.mark.parametrize("valeur", ['"recule"', '"vas-y"', '""', "true", "1", "null",
                                    '["go"]', "3.5"])
def test_marche_autre_valeur_ignoree_avec_warning(timeline, caplog, valeur):
    ordres = []
    with caplog.at_level("WARNING", logger="vision.ai.conversation"):
        result = _tour_avec_marche(
            timeline, ['Bof. {"emotion": "neutral", "marche": ' + valeur + '}'], ordres.append)
    assert result is True
    assert ordres == []
    assert any("marche" in record.message for record in caplog.records)


def test_sans_cle_marche_rien_n_est_appele(timeline, caplog):
    ordres = []
    with caplog.at_level("WARNING", logger="vision.ai.conversation"):
        _tour_avec_marche(timeline, ['Salut. {"emotion": "happy"}'], ordres.append)
    assert ordres == []
    assert not any("marche" in record.message for record in caplog.records)


def test_on_move_none_aucun_effet(timeline, caplog):
    # Comportement historique : la clé n'est même pas lue (pas de warning,
    # même sur une valeur invalide), le tour est identique.
    with caplog.at_level("WARNING", logger="vision.ai.conversation"):
        assert _tour_avec_marche(timeline, ['Ok. {"emotion": "happy", "marche": "recule"}'],
                                 None) is True
    assert not any("marche" in record.message for record in caplog.records)
    publishes = [event[1] for event in timeline if event[0] == "publish"]
    assert publishes[-1] == RosMessage(FACE, json.dumps("joie"))


def test_on_move_qui_leve_ne_casse_pas_le_tour(timeline, caplog):
    def on_move(_cmd):
        raise RuntimeError("publisher cassé (test)")

    with caplog.at_level("ERROR", logger="vision.ai.conversation"):
        result = _tour_avec_marche(
            timeline, ['On y va. {"emotion": "happy", "marche": "go"}'], on_move)
    assert result is True
    assert ("tts_synthesize", "On y va.") in timeline
    publishes = [event[1] for event in timeline if event[0] == "publish"]
    assert publishes[-2:] == [SPEAKING_STOP, JOIE]   # le tour s'est fini normalement
    assert any("on_move" in record.message for record in caplog.records)


def test_marche_part_meme_pendant_une_panne_mute(timeline):
    stage = StageState()
    stage.set_fault("mute", {}, 20000, time.monotonic())
    stage.push_text("repars")
    ordres = []
    engine, _brain = _make_stage_engine(
        timeline, stage, brain_deltas=['Je repars. {"emotion": "happy", "marche": "go"}'],
        on_move=ordres.append)
    try:
        assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert "tts_synthesize" not in [event[0] for event in timeline]   # la voix est coupée…
    assert ordres == ["go"]                                         # …pas les jambes


# --------------------------------------------------------------------------
# Metteur en scène intérieur (lot P, 2026-10-23, dadou_robot_ros/docs/
# spec-metteur-en-scene.md) : arrêt d'urgence vocal AVANT le LLM, tableau de
# situation relu à chaque tour, tour spontané pendant un silence, demande de
# réflexion par la clé "reflechir".
# --------------------------------------------------------------------------

SPONTANE = "(Silence. Personne ne te parle : c'est à toi de relancer la scène.)"


def test_texte_user_du_tour_spontane_grave():
    assert conversation_module.SPONTANEOUS_USER_TEXT == SPONTANE
    assert conversation_module.SPONTANEOUS_MIN_SILENCE_S == 3.0


# --- P1 : arrêt d'urgence vocal ---------------------------------------------

def _move_dans_la_timeline(timeline):
    return lambda cmd: timeline.append(("move", cmd))


def test_urgence_emise_avant_le_llm_puis_le_tour_continue(timeline):
    frames, events = _speech_frames_and_events()
    engine = _make_engine(timeline, frames=frames, vad_events=events,
                          stt_text="Didier, stop !",
                          brain_deltas=['Bon, bon, je m\'arrête. {"emotion": "neutral"}'],
                          on_move=_move_dans_la_timeline(timeline))
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    tags = [event[0] for event in timeline]
    # L'intention part APRÈS le STT et AVANT le premier appel LLM…
    assert timeline.index(("move", "stop")) < tags.index("brain_stream_reply")
    assert tags.index("stt_transcribe") < timeline.index(("move", "stop"))
    # …une seule fois, et le tour va jusqu'au bout (Didier joue l'arrêt).
    assert timeline.count(("move", "stop")) == 1
    assert ("brain_stream_reply", "Didier, stop !") in timeline
    assert ("tts_synthesize", "Bon, bon, je m'arrête.") in timeline


def test_urgence_avant_la_ligne_david_du_transcript(timeline):
    stage = StageState()
    stage.push_text("Arrête !")
    engine, _brain = _make_stage_engine(
        timeline, stage, brain_deltas=["D'accord."],
        on_move=_move_dans_la_timeline(timeline))
    engine._on_transcript = lambda role, text: timeline.append(("transcript", role, text))
    try:
        assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert (timeline.index(("move", "stop"))
            < timeline.index(("transcript", "david", "Arrête !"))
            < [e[0] for e in timeline].index("brain_stream_reply"))


def test_phrase_avec_contexte_ne_declenche_pas_l_urgence(timeline, caplog):
    ordres = []
    frames, events = _speech_frames_and_events()
    engine = _make_engine(timeline, frames=frames, vad_events=events,
                          stt_text="Arrête de râler", brain_deltas=["Je ne râle pas."],
                          on_move=ordres.append)
    try:
        with caplog.at_level("WARNING", logger="vision.ai.conversation"):
            assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert ordres == []
    assert not any("URGENCE" in record.message for record in caplog.records)


def test_urgence_puis_marche_stop_du_llm_emet_deux_fois(timeline):
    # Le régisseur est idempotent (hold republié) : pas de dédup ici.
    ordres = []
    _tour = _make_engine(timeline, frames=_speech_frames_and_events()[0],
                         vad_events=_speech_frames_and_events()[1], stt_text="Stop !",
                         brain_deltas=['Je stoppe. {"emotion": "neutral", "marche": "stop"}'],
                         on_move=ordres.append)
    try:
        assert _tour.run_once() is True
    finally:
        _cleanup_beeps(_tour)
    assert ordres == ["stop", "stop"]


def test_urgence_avec_on_move_qui_leve_le_tour_continue(timeline, caplog):
    def on_move(_cmd):
        raise RuntimeError("publisher cassé (test)")

    frames, events = _speech_frames_and_events()
    engine = _make_engine(timeline, frames=frames, vad_events=events, stt_text="Halte !",
                          brain_deltas=['Halte. {"emotion": "neutral"}'], on_move=on_move)
    try:
        with caplog.at_level("WARNING", logger="vision.ai.conversation"):
            result = engine.run_once()
    finally:
        _cleanup_beeps(engine)
    assert result is True
    assert ("brain_stream_reply", "Halte !") in timeline
    assert ("tts_synthesize", "Halte.") in timeline
    messages = [record.message for record in caplog.records]
    assert "ARRÊT D'URGENCE vocal : 'Halte !'" in messages
    assert any("on_move" in message for message in messages)


def test_urgence_sans_on_move_loggue_non_transmis(timeline, caplog):
    # Révisé le 23/10 : sans régisseur (vrai robot), l'arrêt vocal n'agit
    # pas — le log doit le DIRE (sinon un essai réel ferait croire l'inverse).
    frames, events = _speech_frames_and_events()
    engine = _make_engine(timeline, frames=frames, vad_events=events, stt_text="Stop !",
                          brain_deltas=["Bien."])
    try:
        with caplog.at_level("WARNING", logger="vision.ai.conversation"):
            assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert [record.message for record in caplog.records] == [
        "ARRÊT D'URGENCE vocal entendu mais NON transmis "
        "(mouvement à la voix désactivé) : 'Stop !'"]


def test_urgence_testee_sur_le_stt_avant_la_panne_garble(timeline):
    # Revue adversariale du 23/10 (I3) : l'urgence est testée sur ce que le
    # STT a VRAIMENT produit, AVANT garble — la panne simule l'incompréhension
    # de la conversation, jamais la surdité à l'urgence. Avant : « Stop ! »
    # garblé en contresens n'arrêtait pas Didier.
    stage = StageState()
    stage.set_fault("garble", {"texts": ["Tu as dit banane ?"]}, 30000, time.monotonic())
    stage.push_text("Stop !")
    lines, on_transcript = _transcript_recorder()
    engine, _brain = _make_stage_engine(timeline, stage, brain_deltas=["Banane ?"],
                                        on_move=_move_dans_la_timeline(timeline),
                                        on_transcript=on_transcript)
    try:
        assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    # L'intention part AVANT le LLM, qui reçoit quand même le contresens.
    assert timeline.count(("move", "stop")) == 1
    assert (timeline.index(("move", "stop"))
            < timeline.index(("brain_stream_reply", "Tu as dit banane ?")))
    assert lines[0] == ("david", "Tu as dit banane ?")


def test_contresens_garble_qui_ressemble_a_un_stop_n_arrete_pas(timeline):
    # Corollaire (I3) : seul l'énoncé ENTENDU compte — un contresens tiré par
    # la régie n'invente pas un ordre que personne n'a crié.
    stage = StageState()
    stage.set_fault("garble", {"texts": ["Arrête-toi !"]}, 30000, time.monotonic())
    stage.push_text("Bonjour Didier")
    ordres = []
    engine, _brain = _make_stage_engine(timeline, stage, brain_deltas=["Quoi ?"],
                                        on_move=ordres.append)
    try:
        assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert ordres == []
    assert ("brain_stream_reply", "Arrête-toi !") in timeline


def test_urgence_transmise_sous_panne_deaf_puis_enonce_jete(timeline):
    # Revue adversariale du 23/10 (I3), réécrit (gravait l'inverse) : sous
    # panne deaf, l'intention stop PART, puis l'énoncé est jeté comme avant
    # (aucun LLM, aucune ligne de transcript, idle puis micro relancé).
    stage = StageState()
    stage.set_fault("deaf", {}, 30000, time.monotonic())
    stage.push_text("Stop !")
    lines, on_transcript = _transcript_recorder()
    engine, _brain = _make_stage_engine(timeline, stage, brain_deltas=["jamais"],
                                        on_move=_move_dans_la_timeline(timeline),
                                        on_transcript=on_transcript)
    try:
        assert engine.run_once() is False
    finally:
        _cleanup_beeps(engine)
    assert timeline.count(("move", "stop")) == 1
    assert "brain_stream_reply" not in [event[0] for event in timeline]
    assert lines == []
    assert timeline.index(("move", "stop")) < timeline.index(("publish", IDLE))
    assert timeline[-1] == ("mic_start",)


# --- P2 : tableau de situation relu à chaque tour ---------------------------

def test_situation_transmise_au_brain(timeline):
    stage = StageState()
    stage.set_situation("Une dame en rouge à ta droite.", time.monotonic())
    stage.push_text("Tu vois quelqu'un ?")
    engine, brain = _make_stage_engine(timeline, stage, brain_deltas=["Oui."])
    try:
        assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert brain.calls == [{"user_text": "Tu vois quelqu'un ?", "extra_system": None,
                            "situation": "Une dame en rouge à ta droite.", "direction": None}]


def test_situation_perimee_n_est_pas_transmise(timeline):
    stage = StageState()
    stage.set_situation("Deux enfants devant toi.", time.monotonic() - 5.1)
    stage.push_text("Et maintenant ?")
    engine, brain = _make_stage_engine(timeline, stage, brain_deltas=["Rien."])
    try:
        assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert brain.calls[0]["situation"] is None


# --- P3 : tour spontané -----------------------------------------------------

class FakeClock:
    """Horloge monotone simulée, avancée par le micro (cf. FakeMicHorloge) :
    chaque lecture de trame « dure » `step` secondes."""

    def __init__(self, start=100.0):
        self.t = start

    def monotonic(self):
        return self.t


class FakeMicHorloge(FakeMic):
    """FakeMic qui avance l'horloge de `step` s à CHAQUE read_frame (y
    compris quand le flux est épuisé -> None : micro coupé par chat OFF)."""

    def __init__(self, timeline, frames, clock, step):
        super().__init__(timeline, frames)
        self._clock = clock
        self._step = step

    def read_frame(self):
        self._clock.t += self._step
        return super().read_frame()


@pytest.fixture
def clock(monkeypatch):
    # On remplace la référence `time` DU MODULE conversation seulement (pas le
    # module time global) : le moteur lit cette horloge, le reste du process non.
    fake = FakeClock()
    monkeypatch.setattr(conversation_module, "time",
                        type("FakeTime", (), {"monotonic": staticmethod(fake.monotonic),
                                              "sleep": staticmethod(lambda _s: None)}))
    return fake


def _spontane_engine(timeline, stage, clock, *, frames, vad_events=(), step=1.0,
                     stt_text="jamais utilisé", brain_deltas=("Alors, on y va ?",)):
    mic = FakeMicHorloge(timeline, frames, clock, step)
    return _make_stage_engine(timeline, stage, brain_deltas=list(brain_deltas), frames=frames,
                              vad_events=vad_events, stt_text=stt_text, mic=mic)


def test_tour_spontane_servi_en_silence_apres_3_s(timeline, clock):
    stage = StageState()
    stage.push_prompt("Demande à la dame en rouge si elle connaît le Titan.", clock.t)
    states = []
    lines, on_transcript = _transcript_recorder()
    engine, brain = _spontane_engine(timeline, stage, clock,
                                     frames=[b"f0", b"f1", b"f2", b"f3", b"f4"])
    engine._on_state = states.append
    engine._on_transcript = on_transcript
    try:
        result = engine.run_once()
    finally:
        _cleanup_beeps(engine)

    assert result is True
    # 3 trames lues (t = +1, +2, +3 s) : servi à la 3e, pas avant.
    assert engine._mic._frames == [b"f3", b"f4"]
    # Micro coupé + VAD remise à zéro, puis thinking SANS bips, puis la réplique.
    assert timeline == [
        ("mic_start",),
        ("mic_stop",),
        ("vad_reset",),
        ("mic_stop",),
        ("publish", THINKING),
        ("brain_stream_reply", SPONTANE),
        ("publish", PARLE),
        ("tts_synthesize", "Alors, on y va ?"),
        ("player_play", b"PCM:Alors, on y va ?", 22050),
        ("player_drain",),
        ("publish", SPEAKING_STOP),
        ("publish", IDLE),
        ("mic_start",),
    ]
    assert brain.calls[0]["direction"] == "Demande à la dame en rouge si elle connaît le Titan."
    assert states == ["listening", "thinking", "speaking", "listening"]
    # Pas de ligne "david" : personne n'a parlé.
    assert lines == [("didier", "Alors, on y va ?")]
    assert stage.pop_prompt(clock.t) is None   # consommé


def test_tour_spontane_non_servi_avant_3_s_d_ecoute(timeline, clock):
    stage = StageState()
    stage.push_prompt("Relance.", clock.t)
    # 2 trames (t = +1, +2 s) puis flux épuisé (t = +3 s, None) : l'écoute
    # n'a jamais atteint 3 s AVEC une trame.
    engine, brain = _spontane_engine(timeline, stage, clock, frames=[b"f0", b"f1"])
    try:
        assert engine.run_once() is False
    finally:
        _cleanup_beeps(engine)
    assert brain.calls == []
    assert stage.pop_prompt(clock.t) == "Relance."   # pas consommée pour rien


def test_tour_spontane_jamais_quand_le_micro_est_coupe(timeline, clock):
    # Chat OFF : mic.stop() -> read_frame() rend None. Même avec 5 s
    # écoulées, aucune direction n'est servie (elle attendra ou se périmera).
    stage = StageState()
    stage.push_prompt("Relance.", clock.t)
    engine, brain = _spontane_engine(timeline, stage, clock, frames=[], step=5.0)
    try:
        assert engine.run_once() is False
    finally:
        _cleanup_beeps(engine)
    assert brain.calls == []
    assert stage.pop_prompt(clock.t) == "Relance."


def test_tour_spontane_non_servi_pendant_que_quelqu_un_parle(timeline, clock):
    stage = StageState()
    stage.push_prompt("Relance.", clock.t)
    frames = [b"f0", b"f1", b"f2", b"f3", b"f4", b"f5"]
    events = [VadEvent(kind="speech_start", preroll_frames=2), None, None, None, None,
              VadEvent(kind="speech_end", reason="silence")]
    engine, brain = _spontane_engine(timeline, stage, clock, frames=frames,
                                     vad_events=events, stt_text="je te parle")
    try:
        assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    # La parole de David est servie, pas la direction (6 s d'écoute pourtant).
    assert brain.calls[0]["user_text"] == "je te parle"
    assert brain.calls[0]["direction"] is None
    # Réécrit (revue adversariale du 23/10, I7) : l'énoncé de David a VIDÉ
    # l'emplacement — la direction, calculée avant, ne sera pas jouée après.
    assert stage.pop_prompt(clock.t) is None


def test_tour_spontane_perime_n_est_pas_servi(timeline, clock):
    stage = StageState()
    stage.push_prompt("Vieille direction.", clock.t - 5.5)   # âgée de 8,5 s à la 3e trame
    engine, brain = _spontane_engine(timeline, stage, clock, frames=[b"f0", b"f1", b"f2"])
    try:
        assert engine.run_once() is False   # flux épuisé, rien servi
    finally:
        _cleanup_beeps(engine)
    assert brain.calls == []
    assert stage.pop_prompt(clock.t) is None   # jetée


def test_tour_spontane_sous_panne_mute_sans_voix(timeline, clock):
    stage = StageState()
    stage.set_fault("mute", {}, 20000, clock.t)
    stage.push_prompt("Relance.", clock.t)
    engine, _brain = _spontane_engine(timeline, stage, clock, frames=[b"f0", b"f1", b"f2"])
    try:
        assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert "tts_synthesize" not in [event[0] for event in timeline]


# --- P4 : demande de réflexion ----------------------------------------------

def _tour_reflechir(timeline, deltas, on_reflect, stage=None):
    if stage is None:
        stage = StageState()
    stage.push_text("Va demander à la dame en rouge si elle connaît le Titan")
    engine, _brain = _make_stage_engine(timeline, stage, brain_deltas=deltas,
                                        on_reflect=on_reflect)
    try:
        return engine.run_once()
    finally:
        _cleanup_beeps(engine)


def test_reflechir_appelle_on_reflect(timeline):
    demandes = []
    assert _tour_reflechir(
        timeline, ['Hmm. *réfléchit* {"emotion": "neutral", '
                   '"reflechir": " Demander le Titan à la dame en rouge. "}'],
        demandes.append) is True
    assert demandes == ["Demander le Titan à la dame en rouge."]


@pytest.mark.parametrize("valeur", ['""', '"   "', "null", "42", '["x"]', "true"])
def test_reflechir_vide_ou_non_chaine_ignore(timeline, valeur):
    demandes = []
    assert _tour_reflechir(
        timeline, ['Bof. {"emotion": "neutral", "reflechir": ' + valeur + '}'],
        demandes.append) is True
    assert demandes == []


def test_sans_cle_reflechir_rien(timeline):
    demandes = []
    _tour_reflechir(timeline, ['Salut. {"emotion": "happy"}'], demandes.append)
    assert demandes == []


def test_reflechir_part_meme_sous_panne_mute(timeline):
    stage = StageState()
    stage.set_fault("mute", {}, 20000, time.monotonic())
    demandes = []
    assert _tour_reflechir(
        timeline, ['Je regarde. {"emotion": "neutral", "reflechir": "Regarder."}'],
        demandes.append, stage=stage) is True
    assert "tts_synthesize" not in [event[0] for event in timeline]
    assert demandes == ["Regarder."]


def test_on_reflect_qui_leve_ne_casse_pas_le_tour(timeline, caplog):
    def on_reflect(_demande):
        raise RuntimeError("publisher cassé (test)")

    with caplog.at_level("ERROR", logger="vision.ai.conversation"):
        result = _tour_reflechir(
            timeline, ['Hmm. {"emotion": "happy", "reflechir": "Regarder."}'], on_reflect)
    assert result is True
    assert [e[1] for e in timeline if e[0] == "publish"][-2:] == [SPEAKING_STOP, JOIE]
    assert any("on_reflect" in record.message for record in caplog.records)


def test_tour_spontane_jamais_pendant_un_son_de_spectacle(timeline, clock):
    # Décision du 23/10 (revue du lot P) : une séquence joue du son → Didier
    # ne prend pas la parole de lui-même par-dessus, même après 3 s.
    stage = StageState()
    stage.push_prompt("Relance.", clock.t)
    engine, brain = _spontane_engine(timeline, stage, clock, frames=[b"f0", b"f1", b"f2", b"f3"])
    engine._show_audio_active = lambda: True
    try:
        assert engine.run_once() is False
    finally:
        _cleanup_beeps(engine)
    assert brain.calls == []
    # Toujours en attente : elle sera servie après le son, ou se périmera.
    assert stage.pop_prompt(clock.t) == "Relance."


# --------------------------------------------------------------------------
# Revue adversariale du 23/10 : corrections B1 (jamais de "go" spontané), I7
# (un énoncé de David vide l'emplacement), M5 (écart minimal côté parole).
# --------------------------------------------------------------------------

def test_tour_spontane_n_emet_jamais_go(timeline, clock, caplog):
    # B1 (bloquant), scénario : la direction « reprends la route » fait écrire
    # "marche": "go" au LLM — Didier repartait sans qu'aucun humain l'ait
    # demandé, y compris juste après un « stop » de David.
    stage = StageState()
    stage.push_prompt("Reprends la route.", clock.t)
    ordres = []
    engine, _brain = _spontane_engine(
        timeline, stage, clock, frames=[b"f0", b"f1", b"f2"],
        brain_deltas=['On repart ! {"emotion": "happy", "marche": "go"}'])
    engine._on_move = ordres.append
    try:
        with caplog.at_level("WARNING", logger="vision.ai.conversation"):
            assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert ordres == []
    assert [r.message for r in caplog.records] == [
        "Clé \"marche\" : go ignoré : tour spontané (aucun humain ne l'a demandé)."]
    # Le reste du tour est intact (la réplique est dite, l'émotion jouée).
    assert ("tts_synthesize", "On repart !") in timeline
    assert [e[1] for e in timeline if e[0] == "publish"][-1] == JOIE


def test_tour_spontane_transmet_stop(timeline, clock):
    # B1 : seul "stop" passe d'un tour spontané (s'arrêter n'est jamais dangereux).
    stage = StageState()
    stage.push_prompt("Arrête-toi devant la vitrine.", clock.t)
    ordres = []
    engine, _brain = _spontane_engine(
        timeline, stage, clock, frames=[b"f0", b"f1", b"f2"],
        brain_deltas=['Oh, une vitrine. {"emotion": "happy", "marche": " Stop"}'])
    engine._on_move = ordres.append
    try:
        assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert ordres == ["stop"]


def test_enonce_de_david_vide_l_emplacement_du_tour_spontane(timeline):
    # I7, scénario : la réflexion propose « demande-lui son prénom », David
    # le donne entre-temps — la direction ne doit pas être jouée APRÈS.
    stage = StageState()
    stage.push_prompt("Demande-lui son prénom.", time.monotonic())
    stage.push_text("Je m'appelle Marie.")
    engine, brain = _make_stage_engine(timeline, stage, brain_deltas=["Enchanté, Marie."])
    try:
        assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert brain.calls[0]["direction"] is None
    assert stage.pop_prompt(time.monotonic()) is None


def test_ecart_minimal_entre_deux_tours_spontanes_cote_parole(timeline, clock):
    # M5, scénario : un second éditeur de chat_prompt (ou un reflection_node
    # relancé, état perdu) pousse une direction juste après la précédente —
    # Didier enchaînait relance sur relance.
    assert conversation_module.SPONTANEOUS_MIN_GAP_S == 10.0
    stage = StageState()
    stage.push_prompt("Première relance.", clock.t)
    engine, brain = _spontane_engine(timeline, stage, clock, frames=[b"f0", b"f1", b"f2"])
    try:
        assert engine.run_once() is True               # servi à t = 103
        assert len(brain.calls) == 1
        # Trop tôt : 3 s de silence à t = 106, mais 3 s seulement depuis le
        # précédent — pas servie, et PAS consommée (elle reste, puis se périme).
        stage.push_prompt("Deuxième relance.", clock.t)
        engine._mic._frames = [b"g0", b"g1", b"g2"]
        assert engine.run_once() is False              # flux épuisé, rien servi
        assert len(brain.calls) == 1
        assert stage.pop_prompt(clock.t) == "Deuxième relance."
        # Pile 10 s après le précédent (t = 113) : servie.
        clock.t = 110.0
        stage.push_prompt("Troisième relance.", clock.t)
        engine._mic._frames = [b"h0", b"h1", b"h2"]
        assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert [c["direction"] for c in brain.calls] == ["Première relance.", "Troisième relance."]


# --------------------------------------------------------------------------
# Écoute GARDE pendant une réplique (2026-10-31, constaté en répétition
# simulée : « Stop ! » crié pendant que Didier parlait n'était jamais entendu,
# la route continuait d'avancer). Décision de David : pendant une réplique,
# Didier n'est interruptible QUE par un mot d'arrêt. Revue adversariale du
# 31/10 intégrée (B1, I1-I5, m1, m3). Les threads de la garde tournent pour
# de vrai : les fakes se synchronisent par threading.Event (bornés, jamais
# d'attente infinie en CI).
# --------------------------------------------------------------------------

WAIT_S = 2.0


def _wait_until(predicate, timeout=WAIT_S):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class GuardMic(FakeMic):
    """Micro lu par le thread LECTEUR de la garde (le texte est tapé, l'écoute
    normale ne lit rien). Ne rend ses trames qu'une fois `release` levé (par
    défaut au premier play() : la garde entend David PENDANT que Didier
    parle ; `release_on_start` : dès l'ouverture). stop() simule l'EOF
    d'arecord. Options : `block_when_empty` (flux vivant mais silencieux
    jusqu'au stop), `endless` (trames sans fin), `gates` {n° de trame:
    Event} (trame n rendue seulement une fois l'Event levé)."""

    def __init__(self, timeline, frames, *, release_on_start=False, block_when_empty=False,
                 endless=False, gates=None):
        super().__init__(timeline, frames)
        self.release = threading.Event()
        self.reads = 0
        self._stopped = threading.Event()
        self._release_on_start = release_on_start
        self._block_when_empty = block_when_empty
        self._endless = endless
        self._gates = gates or {}

    def start(self):
        # Flux neuf : il ne rend rien tant que Didier n'a pas parlé (le
        # mic.stop() d'avant la réplique a levé `release`, cf. stop()).
        self._stopped.clear()
        if self._release_on_start:
            self.release.set()
        else:
            self.release.clear()
        super().start()

    def stop(self):
        self._stopped.set()
        self.release.set()
        super().stop()

    def read_frame(self):
        self.release.wait(timeout=WAIT_S)
        if self._stopped.is_set():
            return None
        if self._endless:
            time.sleep(0.005)
            return b"x"
        gate = self._gates.get(self.reads)
        if gate is not None:
            gate.wait(timeout=WAIT_S)
        if not self._frames and self._block_when_empty:
            self._stopped.wait(timeout=WAIT_S)
            return None
        frame = super().read_frame()
        if frame is not None:
            self.reads += 1
        return frame

    def purge_preroll(self):
        pass   # hors timeline : appelée par la fermeture de la garde


class GuardVad(FakeVad):
    """VAD de garde scriptée + trace des seuils adoptés."""

    floor_threshold = 1.3   # = VadConfig() : min_floor 1.0 × threshold_factor 1.3

    def __init__(self, events):
        super().__init__(events)
        self.adopted = []

    def adopt_threshold(self, threshold):
        self.adopted.append(threshold)


class GuardStt:
    """STT de la garde : rend `text` (ou lève si `raises`), le PREMIER appel
    attendant éventuellement `hold` (STT lent). `entered`/`returned` : jalons
    de synchronisation des tests."""

    def __init__(self, text="Stop !", raises=False, hold=None):
        self.text = text
        self.raises = raises
        self.hold = hold
        self.calls = []
        self.entered = threading.Event()
        self.returned = threading.Event()

    def transcribe(self, pcm, sample_rate):
        self.calls.append((pcm, sample_rate))
        first = not self.entered.is_set()
        self.entered.set()
        try:
            if first and self.hold is not None:
                self.hold.wait(timeout=WAIT_S)
            if self.raises:
                raise RuntimeError("STT de garde cassé (test)")
            return self.text
        finally:
            self.returned.set()


class SourcedStt(GuardStt):
    """GuardStt qui, comme FallbackStt, écrit `last_source` à chaque appel."""

    def __init__(self, text):
        super().__init__(text)
        self.last_source = "distant"

    def transcribe(self, pcm, sample_rate):
        self.last_source = "repli"
        return super().transcribe(pcm, sample_rate)


class InterruptiblePlayer(FakePlayer):
    """FakePlayer + interrupt() ; le premier play() lève `mic.release` (sauf
    `release_on_play=False`) ; `on_drain` : appelé dans drain()."""

    def __init__(self, timeline, mic, *, release_on_play=True, on_drain=None):
        super().__init__(timeline)
        self._mic = mic
        self._release_on_play = release_on_play
        self._on_drain = on_drain
        self.interrupted = threading.Event()

    def play(self, pcm, sample_rate):
        super().play(pcm, sample_rate)
        if self._release_on_play:
            self._mic.release.set()

    def drain(self):
        super().drain()
        if self._on_drain is not None:
            self._on_drain()

    def interrupt(self):
        self._timeline.append(("player_interrupt",))
        self.interrupted.set()


class HookTts(FakeTts):
    """FakeTts qui appelle hooks[texte]() PENDANT la synthèse de ce texte."""

    def __init__(self, timeline, hooks):
        super().__init__(timeline)
        self._hooks = hooks

    def synthesize(self, text):
        result = super().synthesize(text)
        hook = self._hooks.get(text)
        if hook is not None:
            hook()
        return result


class PausingBrain(FakeStageBrain):
    """Brain qui streame son PREMIER delta, puis attend `pause()` (borné)
    avant les suivants : laisse à la garde le temps d'agir en pleine réplique.
    `raise_after_pause` : panne LLM juste après la pause."""

    def __init__(self, timeline, deltas, pause, raise_after_pause=False):
        super().__init__(timeline, deltas)
        self._pause = pause
        self._raise_after_pause = raise_after_pause

    def stream_reply(self, user_text, extra_system=None, **kwargs):
        self.calls.append(dict(kwargs, user_text=user_text, extra_system=extra_system))
        self._timeline.append(("brain_stream_reply", user_text))
        first, *rest = self._deltas
        yield first
        self._pause()
        if self._raise_after_pause:
            raise RuntimeError("panne LLM simulée après l'urgence (test)")
        yield from rest


# Deux phrases ; la 2e porte un "go" de fin : il ne doit JAMAIS partir après
# un arrêt vocal de la même réplique.
GUARD_DELTAS = ["Première phrase. ", 'Deuxième phrase. {"emotion": "happy", "marche": "go"}']
# Une tranche : speech_start sur la 1re trame, speech_end sur la 3e.
GUARD_FRAMES = [b"g0", b"g1", b"g2"]
GUARD_EVENTS = [VadEvent(kind="speech_start", preroll_frames=2), None,
                VadEvent(kind="speech_end", reason="silence")]
START = VadEvent(kind="speech_start", preroll_frames=2)
END = VadEvent(kind="speech_end", reason="silence")


def _guard_engine(timeline, *, stt, pause=lambda: None, on_move, guard=True,
                  mic=None, events=GUARD_EVENTS, player=None, tts=None,
                  raise_after_pause=False, stage=None, deltas=GUARD_DELTAS,
                  main_threshold=7.5):
    if stage is None:
        stage = StageState()
    stage.push_text("Raconte-moi la rue.")
    mic = mic if mic is not None else GuardMic(timeline, GUARD_FRAMES)
    main_vad = FakeVad([])
    main_vad.threshold = main_threshold   # seuil calibré de l'écoute normale
    guard_vad = GuardVad(events)
    player = player if player is not None else InterruptiblePlayer(timeline, mic)
    lines, on_transcript = _transcript_recorder()
    states = []
    engine = ConversationEngine(
        mic=mic, vad=main_vad, stt=stt,
        brain=PausingBrain(timeline, deltas, pause, raise_after_pause),
        tts=tts if tts is not None else FakeTts(timeline), player=player,
        publish=_make_publish(timeline),
        refresh_ms=REFRESH_MS, dead_mic_backoff_s=0.0, on_state=states.append,
        stage=stage, on_transcript=on_transcript, on_move=on_move,
        guard_vad=guard_vad if guard else None)
    return engine, mic, guard_vad, player, lines, states


def _ordres_thread_safe():
    ordres, lock = [], threading.Lock()

    def on_move(cmd):
        with lock:
            ordres.append(cmd)
    return ordres, on_move


def _tags(timeline):
    return [event[0] for event in timeline]


# --- Cas nominaux -----------------------------------------------------------

@pytest.mark.parametrize("entendu", [
    "Stop !",
    # I1 : la tranche contient l'écho de Didier autour du cri de David.
    "Première phrase. Stop ! Deuxième",
])
def test_garde_stop_pendant_la_replique_arrete_et_interrompt(timeline, caplog, entendu):
    ordres, on_move = _ordres_thread_safe()
    stt = GuardStt(entendu)
    holder = {}
    engine, mic, guard_vad, player, lines, states = _guard_engine(
        timeline, stt=stt, on_move=on_move,
        pause=lambda: holder["player"].interrupted.wait(timeout=WAIT_S))
    holder["player"] = player
    with caplog.at_level("WARNING", logger="vision.ai.conversation"):
        result = engine.run_once()

    assert result is False                       # tour interrompu, pas mené au bout
    assert ordres == ["stop"]                    # une fois, et JAMAIS le "go" de fin
    assert stt.calls == [(b"PREROLLg1g2", 16000)]  # même STT, tranche pré-roll + trames
    assert guard_vad.adopted == [7.5]            # seuil de l'écoute normale repris
    synth = [event[1] for event in timeline if event[0] == "tts_synthesize"]
    assert synth == ["Première phrase."]         # la 2e n'est jamais dite
    assert "player_interrupt" in _tags(timeline)
    publishes = [event[1] for event in timeline if event[0] == "publish"]
    assert publishes[-2:] == [SPEAKING_STOP, IDLE]   # bouche arrêtée, visage neutre
    assert lines[-1] == ("david", entendu)
    assert _tags(timeline).count("brain_stream_reply") == 1
    assert timeline[-1] == ("mic_start",)        # micro rendu à l'écoute normale
    assert states[-1] == "listening"
    assert f"ARRÊT D'URGENCE vocal pendant la réplique : {entendu!r}" in [
        record.message for record in caplog.records]


def test_garde_parole_quelconque_ne_coupe_rien(timeline):
    ordres, on_move = _ordres_thread_safe()
    stt = GuardStt("c'est joli")

    def pause():
        # Le texte est transcrit ET traité avant la suite de la réplique.
        stt.returned.wait(timeout=WAIT_S)
        time.sleep(0.2)

    engine, mic, _vad, player, lines, states = _guard_engine(
        timeline, stt=stt, on_move=on_move, pause=pause)
    assert engine.run_once() is True
    assert len(stt.calls) == 1                   # la garde a bien entendu…
    assert ordres == ["go"]                      # …sans rien émettre : seul le go de fin
    synth = [event[1] for event in timeline if event[0] == "tts_synthesize"]
    assert synth == ["Première phrase.", "Deuxième phrase."]
    assert "player_interrupt" not in _tags(timeline)
    assert ("david", "c'est joli") not in lines


def test_garde_sans_on_move_micro_coupe_pendant_la_replique(timeline):
    # Vrai robot (on_move None) : comportement historique, aucune écoute garde
    # — même si une VAD de garde est fournie.
    stt = GuardStt("Stop !")
    engine, mic, guard_vad, _player, _lines, _states = _guard_engine(
        timeline, stt=stt, on_move=None)
    assert engine.run_once() is True
    tags = _tags(timeline)
    # Micro coupé avant la réplique, relancé UNE seule fois, tout à la fin.
    assert tags[0] == "mic_stop"
    assert tags.count("mic_start") == 1
    assert timeline[-1] == ("mic_start",)
    assert mic.reads == 0 and stt.calls == [] and guard_vad.adopted == []


def test_garde_stt_qui_leve_la_replique_continue(timeline, caplog):
    ordres, on_move = _ordres_thread_safe()
    stt = GuardStt(raises=True)

    def pause():
        stt.returned.wait(timeout=WAIT_S)
        time.sleep(0.2)

    engine, *_ = _guard_engine(timeline, stt=stt, on_move=on_move, pause=pause)
    with caplog.at_level("WARNING", logger="vision.ai.conversation"):
        assert engine.run_once() is True
    assert len(stt.calls) == 1
    synth = [event[1] for event in timeline if event[0] == "tts_synthesize"]
    assert synth == ["Première phrase.", "Deuxième phrase."]
    assert ordres == ["go"]
    assert any(record.message.startswith("Écoute garde : STT en échec")
               for record in caplog.records)


# --- B1 : stop de FIN de réplique — l'ordre part, l'interruption non --------

def test_garde_stop_transcrit_apres_la_fin_de_replique_emet_quand_meme(timeline):
    ordres, on_move = _ordres_thread_safe()
    hold = threading.Event()
    stt = GuardStt("Stop !", hold=hold)
    # La réplique ne se finit qu'une fois la tranche PARTIE au STT ; le STT,
    # lui, ne rend qu'après la fin.
    engine, *_ = _guard_engine(timeline, stt=stt, on_move=on_move,
                               pause=lambda: stt.entered.wait(timeout=WAIT_S))
    try:
        assert engine.run_once() is True         # réplique allée au bout
        assert stt.entered.is_set()
    finally:
        hold.set()
    assert _wait_until(lambda: len(ordres) == 2)
    assert ordres == ["go", "stop"]              # le stop tardif PART, après le go
    assert "player_interrupt" not in _tags(timeline)   # mais n'interrompt rien


def test_garde_tranche_en_cours_a_la_fermeture_part_au_stt(timeline):
    # « Stop ! » dit pile à la fin : la VAD n'a pas encore vu le silence de
    # fin quand la réplique se ferme — la tranche partielle part quand même.
    ordres, on_move = _ordres_thread_safe()
    stt = GuardStt("Stop !")
    mic = GuardMic(timeline, GUARD_FRAMES, block_when_empty=True)
    engine, *_ = _guard_engine(
        timeline, stt=stt, on_move=on_move, mic=mic, events=[START, None, None],
        pause=lambda: _wait_until(lambda: mic.reads == 3))
    assert engine.run_once() is True
    assert _wait_until(lambda: len(ordres) == 2)
    assert stt.calls == [(b"PREROLLg1g2", 16000)]
    assert ordres == ["go", "stop"]
    assert "player_interrupt" not in _tags(timeline)


def test_garde_stop_tardif_part_avant_le_go_du_tour_suivant(timeline):
    ordres, on_move = _ordres_thread_safe()
    hold = threading.Event()
    stt = GuardStt("Stop !", hold=hold)
    engine, *_ = _guard_engine(timeline, stt=stt, on_move=on_move,
                               pause=lambda: stt.entered.wait(timeout=WAIT_S))
    assert engine.run_once() is True             # tour 1 : go, stop en attente de STT
    engine._stage.push_text("Avance !")
    timer = threading.Timer(0.3, hold.set)       # le STT tardif rend PENDANT le tour 2
    timer.start()
    try:
        assert engine.run_once() is True         # tour 2 : son go attend le stop tardif
    finally:
        timer.cancel()
        hold.set()
    assert ordres == ["go", "stop", "go"]        # la nouvelle intention de David gagne


# --- I2 : file STT bornée, les tranches récentes d'abord --------------------

def test_garde_file_bornee_garde_les_tranches_recentes(timeline):
    ordres, on_move = _ordres_thread_safe()
    hold = threading.Event()
    stt = GuardStt("bla bla", hold=hold)
    frames = [b"a0", b"a1", b"b0", b"b1", b"c0", b"c1", b"d0", b"d1"]
    # La 2e tranche n'est lue qu'une fois la 1re entrée en STT (bloqué) :
    # les 2e, 3e et 4e s'entassent dans une file de 2 places.
    mic = GuardMic(timeline, frames, gates={2: stt.entered})

    def pause():
        _wait_until(lambda: mic.reads == 8)
        time.sleep(0.05)
        hold.set()
        _wait_until(lambda: len(stt.calls) == 3)

    engine, *_ = _guard_engine(timeline, stt=stt, on_move=on_move, mic=mic,
                               events=[START, END] * 4, pause=pause)
    assert engine.run_once() is True
    time.sleep(0.2)
    assert [pcm for pcm, _rate in stt.calls] == [b"PREROLLa1", b"PREROLLc1", b"PREROLLd1"]


# --- I3 : garde armée dès _reply_with_stage (panne delay, attente LLM) ------

def test_garde_stop_pendant_la_panne_delay_sans_appel_llm(timeline):
    ordres, on_move = _ordres_thread_safe()
    stage = StageState()
    stage.set_fault("delay", {"delay_ms": 1500}, 30000, time.monotonic())
    stt = GuardStt("Stop !")
    mic = GuardMic(timeline, GUARD_FRAMES, release_on_start=True)
    engine, _mic, _vad, _player, lines, states = _guard_engine(
        timeline, stt=stt, on_move=on_move, mic=mic, stage=stage)
    started = time.monotonic()
    assert engine.run_once() is False
    assert time.monotonic() - started < 1.0      # l'attente de 1,5 s est écourtée
    assert ordres == ["stop"]
    assert "brain_stream_reply" not in _tags(timeline)
    assert lines == [("david", "Raconte-moi la rue."), ("david", "Stop !")]
    assert states[-1] == "listening" and timeline[-1] == ("mic_start",)


# --- I4 : chat OFF ----------------------------------------------------------

def test_garde_jamais_armee_chat_off(timeline):
    ordres, on_move = _ordres_thread_safe()
    stt = GuardStt("Stop !")
    engine, mic, guard_vad, *_ = _guard_engine(timeline, stt=stt, on_move=on_move)
    engine._enabled = threading.Event()          # toggle OFF (baissé)
    engine.run_once()
    assert _tags(timeline).count("mic_start") == 1   # seul le start historique de fin
    assert mic.reads == 0 and stt.calls == [] and guard_vad.adopted == []


def test_garde_chat_off_pendant_la_replique_recoupe_le_micro(timeline):
    ordres, on_move = _ordres_thread_safe()
    stt = GuardStt("bla")
    mic = GuardMic(timeline, [], endless=True)
    enabled = threading.Event()
    enabled.set()

    def pause():
        enabled.clear()                          # chat OFF en pleine réplique
        _wait_until(lambda: _tags(timeline).count("mic_stop") >= 2)

    engine, *_ = _guard_engine(timeline, stt=stt, on_move=on_move, mic=mic,
                               events=[], pause=pause)
    engine._enabled = enabled
    engine.run_once()
    tags = _tags(timeline)
    # Le micro est recoupé PAR LA GARDE pendant la réplique (avant le drain).
    assert "mic_stop" in tags[tags.index("player_play"):tags.index("player_drain")]


# --- I5 : contrôles de course ----------------------------------------------

def test_go_jamais_emis_apres_une_interruption_de_la_meme_replique(timeline):
    ordres, on_move = _ordres_thread_safe()
    engine, *_ = _guard_engine(timeline, stt=GuardStt(), on_move=on_move)
    interrupted = threading.Event()
    interrupted.set()
    engine._guard = types.SimpleNamespace(lock=threading.Lock(), interrupted=interrupted)
    engine._notify_move({"marche": "go"})
    engine._notify_move({"marche": "stop"})
    assert ordres == ["stop"]


def test_garde_stop_pendant_la_synthese_la_phrase_n_est_pas_jouee(timeline):
    ordres, on_move = _ordres_thread_safe()
    stt = GuardStt("Stop !")
    mic = GuardMic(timeline, GUARD_FRAMES)
    player = InterruptiblePlayer(timeline, mic, release_on_play=False)

    def pendant_la_synthese():
        mic.release.set()
        player.interrupted.wait(timeout=WAIT_S)

    engine, *_ = _guard_engine(
        timeline, stt=stt, on_move=on_move, mic=mic, player=player,
        tts=HookTts(timeline, {"Deuxième phrase.": pendant_la_synthese}))
    assert engine.run_once() is False
    assert ("tts_synthesize", "Deuxième phrase.") in timeline
    assert _tags(timeline).count("player_play") == 1     # synthétisée, jamais jouée
    assert ordres == ["stop"]


def test_garde_stop_pendant_le_drain_sortie_interrompue(timeline):
    ordres, on_move = _ordres_thread_safe()
    stt = GuardStt("Stop !")
    mic = GuardMic(timeline, GUARD_FRAMES)
    holder = {}

    def pendant_le_drain():
        mic.release.set()
        holder["player"].interrupted.wait(timeout=WAIT_S)

    player = InterruptiblePlayer(timeline, mic, release_on_play=False, on_drain=pendant_le_drain)
    holder["player"] = player
    engine, _mic, _vad, _player, lines, _states = _guard_engine(
        timeline, stt=stt, on_move=on_move, mic=mic, player=player)
    assert engine.run_once() is False
    publishes = [event[1] for event in timeline if event[0] == "publish"]
    assert publishes[-2:] == [SPEAKING_STOP, IDLE]       # pas l'émotion "joie" de fin
    assert lines[-1] == ("david", "Stop !")
    assert ordres == ["go", "stop"]                      # go déjà parti, stop après


def test_garde_fermee_sur_le_chemin_d_exception(timeline):
    ordres, on_move = _ordres_thread_safe()
    engine, *_ = _guard_engine(timeline, stt=GuardStt("bla"), on_move=on_move,
                               raise_after_pause=True)
    assert engine.run_once() is False
    assert engine._guard is None
    assert timeline[-3:] == [("publish", IDLE), ("mic_stop",), ("mic_start",)]


def test_garde_panne_llm_apres_urgence_rejoue_interrupt(timeline):
    # m3 : la panne tombe APRÈS l'arrêt vocal — sortie d'interruption complète.
    ordres, on_move = _ordres_thread_safe()
    holder = {}
    engine, _mic, _vad, player, lines, states = _guard_engine(
        timeline, stt=GuardStt("Stop !"), on_move=on_move, raise_after_pause=True,
        pause=lambda: holder["player"].interrupted.wait(timeout=WAIT_S))
    holder["player"] = player
    assert engine.run_once() is False
    assert _tags(timeline).count("player_interrupt") == 2   # garde + rattrapage
    assert lines[-1] == ("david", "Stop !")
    assert ordres == ["stop"]
    assert states[-1] == "listening" and timeline[-1] == ("mic_start",)


# --- m1 : la garde n'écrase pas la source STT du tour -----------------------

def test_garde_n_ecrase_pas_la_source_stt(timeline):
    ordres, on_move = _ordres_thread_safe()
    stt = SourcedStt("c'est joli")

    def pause():
        stt.returned.wait(timeout=WAIT_S)
        time.sleep(0.2)

    engine, *_ = _guard_engine(timeline, stt=stt, on_move=on_move, pause=pause)
    assert engine.run_once() is True
    assert len(stt.calls) == 1
    assert stt.last_source == "distant"



# --- Seconde revue du 31/10 : écho de Didier, plancher VAD, source STT -------

def _pause_apres_stt(stt):
    def pause():
        stt.returned.wait(timeout=WAIT_S)
        time.sleep(0.2)
    return pause


M_ARRETE = ["D'accord, je m'arrête. ", 'Voilà. {"emotion": "happy"}']


def test_garde_echo_de_didier_je_m_arrete_ignore(timeline, caplog):
    # Important 1 : David a crié stop (écoute normale), Didier répond « je
    # m'arrête » — son propre écho ne doit pas couper sa réplique.
    ordres, on_move = _ordres_thread_safe()
    stt = GuardStt("je m'arrête")
    engine, *_ = _guard_engine(timeline, stt=stt, on_move=on_move, deltas=M_ARRETE,
                               pause=_pause_apres_stt(stt))
    with caplog.at_level("INFO", logger="vision.ai.conversation"):
        assert engine.run_once() is True
    assert len(stt.calls) == 1
    assert ordres == []
    synth = [event[1] for event in timeline if event[0] == "tts_synthesize"]
    assert synth == ["D'accord, je m'arrête.", "Voilà."]
    assert "player_interrupt" not in _tags(timeline)
    assert ("Écoute garde : \"je m'arrête\" ignoré — ['arrete'] déjà dit par Didier dans "
            "cette réplique (écho probable).") in [record.message for record in caplog.records]


def test_garde_stop_crie_pendant_une_replique_sans_stop_est_emis(timeline):
    # Didier a dit « arrête » (forme arrete), David crie « Stop ! » : autre
    # forme, l'ordre part et la réplique est interrompue.
    ordres, on_move = _ordres_thread_safe()
    holder = {}
    engine, _mic, _vad, player, _lines, _states = _guard_engine(
        timeline, stt=GuardStt("Stop !"), on_move=on_move, deltas=M_ARRETE,
        pause=lambda: holder["player"].interrupted.wait(timeout=WAIT_S))
    holder["player"] = player
    assert engine.run_once() is False
    assert ordres == ["stop"]
    synth = [event[1] for event in timeline if event[0] == "tts_synthesize"]
    assert synth == ["D'accord, je m'arrête."]


def test_garde_stop_crie_pendant_une_replique_qui_dit_stop_ignore(timeline):
    # FAUX NÉGATIF ACCEPTÉ ET GRAVÉ (cf. _ReplyGuard._handle_text) : Didier a
    # lui-même dit « stop » — un « Stop ! » de David est indiscernable de son
    # écho. Le deadman et la télécommande restent les arrêts effectifs.
    ordres, on_move = _ordres_thread_safe()
    stt = GuardStt("Stop !")
    engine, *_ = _guard_engine(timeline, stt=stt, on_move=on_move,
                               deltas=["Bon, stop, je me tais. ", 'Voilà. {"emotion": "happy"}'],
                               pause=_pause_apres_stt(stt))
    assert engine.run_once() is True
    assert len(stt.calls) == 1
    assert ordres == []
    assert "player_interrupt" not in _tags(timeline)


def test_garde_plancher_si_ecoute_normale_non_calibree(timeline):
    # Mineur 4 : 1er tour tapé — l'écoute normale n'a pas de seuil ; la garde
    # prend le plancher de la config, jamais une calibration sur Didier.
    ordres, on_move = _ordres_thread_safe()
    engine, _mic, guard_vad, *_ = _guard_engine(
        timeline, stt=GuardStt("bla"), on_move=on_move, main_threshold=None)
    engine.run_once()
    assert guard_vad.adopted == [1.3]


class _BrainQuiChangeLaSource(FakeBrain):
    """Simule une tranche de garde transcrite PENDANT la réplique : elle
    réécrit last_source du STT partagé."""

    def __init__(self, timeline, deltas, stt):
        super().__init__(timeline, deltas)
        self._stt = stt

    def stream_reply(self, user_text):
        self._stt.last_source = "repli"
        yield from super().stream_reply(user_text)


def test_source_stt_du_tour_dans_le_dict_de_timing(timeline):
    # Mineur 2 : la source affichée est celle du STT de DAVID (lue sous le
    # verrou juste après), pas celle que l'écoute garde a laissée ensuite.
    frames, events = _speech_frames_and_events()
    timings = []
    engine = _make_engine(timeline, frames=frames, vad_events=events, stt_text="salut",
                          brain_deltas=["Bonjour."], on_timing=timings.append)
    engine._stt.last_source = "distant"
    engine._brain = _BrainQuiChangeLaSource(timeline, ["Bonjour."], engine._stt)
    try:
        assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert timings[0]["stt_source"] == "distant"


# --------------------------------------------------------------------------
# « Aller voir » (lot M1, 31/10, dadou_robot_ros/docs/spec-aller-voir.md
# §2.2) : la clé "aller_voir" part sur on_move en dict du contrat ; c'est une
# MISE EN MOUVEMENT (jamais en spontané, barrière et verrou de la garde
# comme "go") ; stop > aller_voir > go.
# --------------------------------------------------------------------------

ANNEAUX = {"cmd": "aller_voir", "objet": "anneaux"}


def test_aller_voir_emis_rogne_au_format_du_contrat(timeline):
    ordres = []
    assert _tour_avec_marche(
        timeline, ['J\'y vais ! {"emotion": "happy", "aller_voir": "  anneaux "}'],
        ordres.append) is True
    assert ordres == [ANNEAUX]
    # Payload publié par chat_node (json.dumps de l'intention) : GRAVÉ, c'est
    # la chaîne que le régisseur décode.
    assert json.dumps(ordres[0]) == '{"cmd": "aller_voir", "objet": "anneaux"}'
    assert [e[1] for e in timeline if e[0] == "publish"][-1] == JOIE


def test_aller_voir_garde_la_casse(timeline):
    # La résolution (minuscules, accents, articles) est l'affaire du régisseur.
    ordres = []
    _tour_avec_marche(timeline, ['Allons. {"emotion": "happy", "aller_voir": "La Grue"}'],
                      ordres.append)
    assert ordres == [{"cmd": "aller_voir", "objet": "La Grue"}]


def test_aller_voir_et_stop_le_stop_gagne(timeline, caplog):
    ordres = []
    with caplog.at_level("WARNING", logger="vision.ai.conversation"):
        _tour_avec_marche(
            timeline, ['Euh. {"emotion": "neutral", "marche": "stop", "aller_voir": "anneaux"}'],
            ordres.append)
    assert ordres == ["stop"]
    assert any("aller_voir" in r.message and "stop" in r.message for r in caplog.records)


def test_aller_voir_gagne_sur_go_un_seul_ordre(timeline):
    ordres = []
    _tour_avec_marche(
        timeline, ['Hop. {"emotion": "happy", "marche": "go", "aller_voir": "anneaux"}'],
        ordres.append)
    assert ordres == [ANNEAUX]


# (Pas d'objet imbriqué : le parseur d'émotion refuse déjà le bloc JSON entier.)
@pytest.mark.parametrize("valeur", ['""', '"   "', "null", "42", "true", '["anneaux"]'])
def test_aller_voir_vide_ou_non_chaine_ignore_avec_warning(timeline, caplog, valeur):
    ordres = []
    with caplog.at_level("WARNING", logger="vision.ai.conversation"):
        assert _tour_avec_marche(
            timeline, ['Bof. {"emotion": "neutral", "aller_voir": ' + valeur + '}'],
            ordres.append) is True
    assert ordres == []
    assert any("aller_voir" in r.message for r in caplog.records)


def test_aller_voir_invalide_laisse_passer_le_go(timeline):
    ordres = []
    _tour_avec_marche(timeline, ['Hop. {"emotion": "happy", "marche": "go", "aller_voir": ""}'],
                      ordres.append)
    assert ordres == ["go"]


def test_aller_voir_sans_on_move_aucun_effet(timeline, caplog):
    # Vrai robot (mouvement à la voix non branché) : la clé n'est pas lue.
    with caplog.at_level("WARNING", logger="vision.ai.conversation"):
        assert _tour_avec_marche(
            timeline, ['Ok. {"emotion": "happy", "aller_voir": "anneaux"}'], None) is True
    assert caplog.records == []
    assert [e[1] for e in timeline if e[0] == "publish"][-1] == JOIE


def test_tour_spontane_n_emet_jamais_aller_voir(timeline, clock, caplog):
    # Revue B1 du 23/10 : un tour spontané ne met jamais Didier en mouvement.
    stage = StageState()
    stage.push_prompt("Va voir les anneaux.", clock.t)
    ordres = []
    engine, _brain = _spontane_engine(
        timeline, stage, clock, frames=[b"f0", b"f1", b"f2"],
        brain_deltas=['Les anneaux ! {"emotion": "happy", "marche": "go", '
                      '"aller_voir": "anneaux"}'])
    engine._on_move = ordres.append
    try:
        with caplog.at_level("WARNING", logger="vision.ai.conversation"):
            assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert ordres == []
    assert [r.message for r in caplog.records] == [
        "Clé \"aller_voir\" : 'anneaux' ignoré : tour spontané (aucun humain ne l'a demandé)."]


def test_tour_spontane_stop_avec_aller_voir_transmet_stop(timeline, clock):
    stage = StageState()
    stage.push_prompt("Arrête-toi.", clock.t)
    ordres = []
    engine, _brain = _spontane_engine(
        timeline, stage, clock, frames=[b"f0", b"f1", b"f2"],
        brain_deltas=['Halte. {"emotion": "happy", "marche": "stop", "aller_voir": "grue"}'])
    engine._on_move = ordres.append
    try:
        assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert ordres == ["stop"]


def test_aller_voir_jamais_emis_apres_une_interruption_de_la_meme_replique(timeline):
    ordres, on_move = _ordres_thread_safe()
    engine, *_ = _guard_engine(timeline, stt=GuardStt(), on_move=on_move)
    interrupted = threading.Event()
    interrupted.set()
    engine._guard = types.SimpleNamespace(lock=threading.Lock(), interrupted=interrupted)
    engine._notify_move({"aller_voir": "anneaux"})
    engine._notify_move({"marche": "stop"})
    assert ordres == ["stop"]


def test_aller_voir_pris_sous_le_verrou_de_la_garde(timeline):
    # L'urgence émet stop PUIS lève interrupted sous guard.lock : l'ordre ne
    # doit pas pouvoir partir tant que le verrou est tenu.
    ordres, on_move = _ordres_thread_safe()
    engine, *_ = _guard_engine(timeline, stt=GuardStt(), on_move=on_move)
    guard = types.SimpleNamespace(lock=threading.Lock(), interrupted=threading.Event())
    engine._guard = guard
    with guard.lock:
        worker = threading.Thread(target=engine._notify_move,
                                  args=({"aller_voir": "anneaux"},), daemon=True)
        worker.start()
        time.sleep(0.1)
        assert ordres == []                      # bloqué derrière le verrou
        guard.interrupted.set()                  # l'urgence tombe entre-temps
    worker.join(WAIT_S)
    assert ordres == []


def test_garde_stop_tardif_part_avant_l_aller_voir_du_tour_suivant(timeline):
    # Même barrière que pour "go" (B1, GUARD_LATE_GO_WAIT_S).
    deltas = ["Première phrase. ", 'Deuxième phrase. {"emotion": "happy", "aller_voir": "anneaux"}']
    ordres, on_move = _ordres_thread_safe()
    hold = threading.Event()
    stt = GuardStt("Stop !", hold=hold)
    engine, *_ = _guard_engine(timeline, stt=stt, on_move=on_move, deltas=deltas,
                               pause=lambda: stt.entered.wait(timeout=WAIT_S))
    assert engine.run_once() is True             # tour 1 : aller_voir, stop en attente
    engine._stage.push_text("Va voir les anneaux !")
    timer = threading.Timer(0.3, hold.set)       # le STT tardif rend PENDANT le tour 2
    timer.start()
    try:
        assert engine.run_once() is True
    finally:
        timer.cancel()
        hold.set()
    assert ordres == [ANNEAUX, "stop", ANNEAUX]  # la nouvelle intention de David gagne


# --------------------------------------------------------------------------
# Gestes chiffrés (lot M2, 31/10, dadou_robot_ros/docs/spec-aller-voir.md
# §7, décision de David) : "tourner" (degrés, + = gauche, |a| <= 180) et
# "avancer" (0 < m <= 5) sont des MISES EN MOUVEMENT (on_move, jamais en
# spontané, garde) ; préséance stop > aller_voir > tourner > avancer > go ;
# "regarder" (degrés) part sur on_look (tête seule, permis en spontané,
# émis EN PLUS d'un geste de mouvement).
# --------------------------------------------------------------------------

TOURNE_DROITE = {"cmd": "tourner", "angle_deg": -90}
AVANCE_UN = {"cmd": "avancer", "metres": 1}
REGARDE_DROITE = {"angle_deg": -60, "hold_ms": 4000}


def _tour_avec_cles(timeline, deltas, *, on_move=None, on_look=None):
    frames, events = _speech_frames_and_events()
    engine = _make_engine(timeline, frames=frames, vad_events=events,
                          stt_text="jette un œil sur ta droite", brain_deltas=deltas,
                          on_move=on_move, on_look=on_look)
    try:
        return engine.run_once()
    finally:
        _cleanup_beeps(engine)


def _ordre_pour(timeline, cles):
    """Un tour dont le JSON de fin porte `cles` (texte JSON brut, sans
    accolades) -> liste des ordres reçus par on_move."""
    ordres = []
    assert _tour_avec_cles(timeline, ['Hop. {"emotion": "happy", ' + cles + '}'],
                           on_move=ordres.append) is True
    return ordres


# --- « Tourner » --------------------------------------------------------------

@pytest.mark.parametrize("valeur, angle", [
    ("-90", -90), ("90", 90), ("45.5", 45.5), ("180", 180), ("-180", -180), ("0", 0),
    ('"gauche"', 90), ('"droite"', -90), ('"demi_tour"', 180),
    ('" Droite "', -90), ('"DEMI_TOUR"', 180)])
def test_tourner_emis_au_format_du_contrat(timeline, valeur, angle):
    ordres = _ordre_pour(timeline, '"tourner": ' + valeur)
    assert ordres == [{"cmd": "tourner", "angle_deg": angle}]
    assert [e[1] for e in timeline if e[0] == "publish"][-1] == JOIE


def test_tourner_payload_publie_grave(timeline):
    # Chaîne que le régisseur décode (json.dumps de chat_node._publish_move) ;
    # un entier reste un entier.
    assert json.dumps(_ordre_pour(timeline, '"tourner": "droite"')[0]) == (
        '{"cmd": "tourner", "angle_deg": -90}')


@pytest.mark.parametrize("valeur", ["181", "-180.5", "720", "NaN", "Infinity",
                                    '"90"', '"derriere"', '""',
                                    "null", "true", "false", '[90]'])
def test_tourner_illisible_ou_hors_bornes_ignore_avec_warning(timeline, caplog, valeur):
    with caplog.at_level("WARNING", logger="vision.ai.conversation"):
        assert _ordre_pour(timeline, '"tourner": ' + valeur) == []
    assert any("tourner" in r.message for r in caplog.records)


@pytest.mark.parametrize("graphie", ['"demi_tour"', '"demi-tour"', '" Demi Tour "'])
def test_tourner_demi_tour_toutes_graphies(timeline, graphie):
    assert json.dumps(_ordre_pour(timeline, '"tourner": ' + graphie)[0]) == (
        '{"cmd": "tourner", "angle_deg": 180}')


def test_tourner_invalide_laisse_passer_le_go(timeline):
    assert _ordre_pour(timeline, '"marche": "go", "tourner": 400') == ["go"]


def test_tourner_sans_on_move_aucun_effet(timeline, caplog):
    with caplog.at_level("WARNING", logger="vision.ai.conversation"):
        assert _tour_avec_cles(
            timeline, ['Ok. {"emotion": "happy", "tourner": -90, "avancer": 2}']) is True
    assert caplog.records == []


# --- « Avancer » --------------------------------------------------------------

@pytest.mark.parametrize("valeur, metres", [("1", 1), ("0.5", 0.5), ("5", 5), ("2.25", 2.25)])
def test_avancer_emis_au_format_du_contrat(timeline, valeur, metres):
    assert _ordre_pour(timeline, '"avancer": ' + valeur) == [
        {"cmd": "avancer", "metres": metres}]


def test_avancer_payload_publie_grave(timeline):
    assert json.dumps(_ordre_pour(timeline, '"avancer": 1.5')[0]) == (
        '{"cmd": "avancer", "metres": 1.5}')


@pytest.mark.parametrize("valeur", ["0", "-1", "-0.5", "5.01", "12", "NaN", "Infinity",
                                    '"1"', '"un peu"', '"gauche"', "null", "true", "[1]"])
def test_avancer_illisible_nul_negatif_ou_trop_loin_ignore_avec_warning(timeline, caplog,
                                                                          valeur):
    # Il ne recule pas (négatif), 0 n'est pas un geste, au-delà de 5 m : refus.
    with caplog.at_level("WARNING", logger="vision.ai.conversation"):
        assert _ordre_pour(timeline, '"avancer": ' + valeur) == []
    assert any("avancer" in r.message for r in caplog.records)


def test_avancer_refus_explique_qu_il_ne_recule_pas(timeline, caplog):
    with caplog.at_level("WARNING", logger="vision.ai.conversation"):
        _ordre_pour(timeline, '"avancer": -2')
    assert [r.message for r in caplog.records] == [
        "Clé \"avancer\" ignorée : -2 (attendu des mètres, 0 < m <= 5 : Didier ne recule pas)."]


# --- Préséance stop > aller_voir > tourner > avancer > go ------------------------

@pytest.mark.parametrize("cles, attendu", [
    ('"marche": "go", "tourner": -90', TOURNE_DROITE),
    ('"marche": "go", "avancer": 1', AVANCE_UN),
    ('"tourner": -90, "avancer": 1', TOURNE_DROITE),
    ('"avancer": 1, "tourner": -90', TOURNE_DROITE),          # l'ordre des clés ne compte pas
    ('"aller_voir": "anneaux", "tourner": -90', ANNEAUX),
    ('"avancer": 1, "aller_voir": "anneaux"', ANNEAUX),
    ('"marche": "go", "aller_voir": "anneaux", "tourner": -90, "avancer": 1', ANNEAUX),
    ('"marche": "go", "tourner": -90, "avancer": 1', TOURNE_DROITE),
    ('"marche": "stop", "tourner": -90', "stop"),
    ('"marche": "stop", "avancer": 1', "stop"),
    ('"marche": "stop", "aller_voir": "anneaux", "tourner": -90, "avancer": 1', "stop"),
    ('"tourner": 999, "avancer": 1', AVANCE_UN),               # perdant illisible = suivant
])
def test_preseance_des_gestes_un_seul_ordre(timeline, cles, attendu):
    assert _ordre_pour(timeline, cles) == [attendu]


def test_stop_journalise_chaque_geste_jete(timeline, caplog):
    with caplog.at_level("WARNING", logger="vision.ai.conversation"):
        assert _ordre_pour(timeline, '"marche": "stop", "tourner": -90, "avancer": 1') == ["stop"]
    messages = [r.message for r in caplog.records]
    assert ("Clé \"tourner\" : -90 ignoré : la même réplique demande \"stop\" "
            "(le stop gagne toujours).") in messages
    assert ("Clé \"avancer\" : 1 ignoré : la même réplique demande \"stop\" "
            "(le stop gagne toujours).") in messages


# --- Mise en mouvement : spontané, verrou et barrière de la garde --------------

@pytest.mark.parametrize("cles, cle, valeur", [
    ('"marche": "go", "tourner": -90', "tourner", "-90"),
    ('"avancer": 2', "avancer", "2")])
def test_tour_spontane_n_emet_jamais_tourner_ni_avancer(timeline, clock, caplog, cles, cle,
                                                        valeur):
    # Revue B1 du 23/10 : un tour spontané ne met jamais Didier en mouvement.
    stage = StageState()
    stage.push_prompt("Regarde ce qu'il y a à droite.", clock.t)
    ordres = []
    engine, _brain = _spontane_engine(
        timeline, stage, clock, frames=[b"f0", b"f1", b"f2"],
        brain_deltas=['Voyons ! {"emotion": "happy", ' + cles + '}'])
    engine._on_move = ordres.append
    try:
        with caplog.at_level("WARNING", logger="vision.ai.conversation"):
            assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert ordres == []
    assert [r.message for r in caplog.records] == [
        f"Clé \"{cle}\" : {valeur} ignoré : tour spontané (aucun humain ne l'a demandé)."]


@pytest.mark.parametrize("params", [{"tourner": -90}, {"avancer": 1}])
def test_geste_jamais_emis_apres_une_interruption_de_la_meme_replique(timeline, params):
    ordres, on_move = _ordres_thread_safe()
    engine, *_ = _guard_engine(timeline, stt=GuardStt(), on_move=on_move)
    interrupted = threading.Event()
    interrupted.set()
    engine._guard = types.SimpleNamespace(lock=threading.Lock(), interrupted=interrupted)
    engine._notify_move(params)
    engine._notify_move({"marche": "stop"})
    assert ordres == ["stop"]


@pytest.mark.parametrize("params", [{"tourner": 180}, {"avancer": 3}])
def test_geste_pris_sous_le_verrou_de_la_garde(timeline, params):
    ordres, on_move = _ordres_thread_safe()
    engine, *_ = _guard_engine(timeline, stt=GuardStt(), on_move=on_move)
    guard = types.SimpleNamespace(lock=threading.Lock(), interrupted=threading.Event())
    engine._guard = guard
    with guard.lock:
        worker = threading.Thread(target=engine._notify_move, args=(params,), daemon=True)
        worker.start()
        time.sleep(0.1)
        assert ordres == []                      # bloqué derrière le verrou
        guard.interrupted.set()                  # l'urgence tombe entre-temps
    worker.join(WAIT_S)
    assert ordres == []


@pytest.mark.parametrize("cles, ordre", [('"tourner": -90', TOURNE_DROITE),
                                         ('"avancer": 1', AVANCE_UN)])
def test_garde_stop_tardif_part_avant_le_geste_du_tour_suivant(timeline, cles, ordre):
    # Même barrière que pour "go" (B1, GUARD_LATE_GO_WAIT_S).
    deltas = ["Première phrase. ", 'Deuxième phrase. {"emotion": "happy", ' + cles + '}']
    ordres, on_move = _ordres_thread_safe()
    hold = threading.Event()
    stt = GuardStt("Stop !", hold=hold)
    engine, *_ = _guard_engine(timeline, stt=stt, on_move=on_move, deltas=deltas,
                               pause=lambda: stt.entered.wait(timeout=WAIT_S))
    assert engine.run_once() is True             # tour 1 : geste, stop en attente
    engine._stage.push_text("Encore !")
    timer = threading.Timer(0.3, hold.set)       # le STT tardif rend PENDANT le tour 2
    timer.start()
    try:
        assert engine.run_once() is True
    finally:
        timer.cancel()
        hold.set()
    assert ordres == [ordre, "stop", ordre]


# --- « Regarder » -----------------------------------------------------------

@pytest.mark.parametrize("valeur, angle", [
    ("-60", -60), ("30", 30), ("0", 0), ("12.5", 12.5), ("-90", -90),
    ('"gauche"', 60), ('"droite"', -60), ('"devant"', 0),
    ('"  Gauche "', 60), ('"DEVANT"', 0)])
def test_regarder_emis_au_format_du_contrat(timeline, valeur, angle):
    regards = []
    assert _tour_avec_cles(
        timeline, ['Tiens ! {"emotion": "happy", "regarder": ' + valeur + '}'],
        on_look=regards.append) is True
    assert regards == [{"angle_deg": angle, "hold_ms": 4000}]
    assert [e[1] for e in timeline if e[0] == "publish"][-1] == JOIE


def test_regarder_payload_publie_grave(timeline):
    regards = []
    _tour_avec_cles(timeline, ['Tiens. {"emotion": "happy", "regarder": "droite"}'],
                    on_look=regards.append)
    # Chaîne que gaze_follower_node décode (json.dumps de chat_node._publish_look).
    assert json.dumps(regards[0]) == '{"angle_deg": -60, "hold_ms": 4000}'


@pytest.mark.parametrize("valeur", ['"derriere"', '"haut"', '"demi_tour"', '"-60"', '""',
                                    "NaN", "Infinity", "null", "true", '[30]'])
def test_regarder_illisible_ignore_avec_warning(timeline, caplog, valeur):
    regards = []
    with caplog.at_level("WARNING", logger="vision.ai.conversation"):
        assert _tour_avec_cles(
            timeline, ['Bof. {"emotion": "neutral", "regarder": ' + valeur + '}'],
            on_look=regards.append) is True
    assert regards == []
    assert any("regarder" in r.message for r in caplog.records)


def test_regarder_sans_on_look_aucun_effet(timeline, caplog):
    # Mouvement à la voix non branché : la clé n'est pas lue, même avec on_move.
    ordres = []
    with caplog.at_level("WARNING", logger="vision.ai.conversation"):
        assert _tour_avec_cles(
            timeline, ['Ok. {"emotion": "happy", "regarder": -60}'],
            on_move=ordres.append) is True
    assert caplog.records == []
    assert ordres == []


def test_regarder_ne_passe_jamais_par_on_move(timeline):
    ordres, regards = [], []
    _tour_avec_cles(timeline, ['Tiens. {"emotion": "happy", "regarder": 60}'],
                    on_move=ordres.append, on_look=regards.append)
    assert ordres == []
    assert regards == [{"angle_deg": 60, "hold_ms": 4000}]


@pytest.mark.parametrize("cles, ordre", [
    ('"tourner": -90', TOURNE_DROITE), ('"avancer": 1', AVANCE_UN),
    ('"aller_voir": "anneaux"', ANNEAUX), ('"marche": "go"', "go"),
    ('"marche": "stop"', "stop")])
def test_regarder_en_plus_d_un_geste_les_deux_partent(timeline, cles, ordre):
    ordres, regards = [], []
    _tour_avec_cles(
        timeline, ['Voyons. {"emotion": "happy", "regarder": "droite", ' + cles + '}'],
        on_move=ordres.append, on_look=regards.append)
    assert ordres == [ordre]
    assert regards == [REGARDE_DROITE]


def test_tour_spontane_peut_regarder(timeline, clock):
    stage = StageState()
    stage.push_prompt("Jette un œil à droite.", clock.t)
    regards = []
    engine, _brain = _spontane_engine(
        timeline, stage, clock, frames=[b"f0", b"f1", b"f2"],
        brain_deltas=['Tiens ? {"emotion": "happy", "regarder": "droite"}'])
    engine._on_look = regards.append
    try:
        assert engine.run_once() is True
    finally:
        _cleanup_beeps(engine)
    assert regards == [REGARDE_DROITE]


def test_regarder_emis_meme_apres_interruption_de_la_garde(timeline):
    # Ni barrière ni verrou de garde pour la tête (cf. _notify_look).
    regards = []
    engine, *_ = _guard_engine(timeline, stt=GuardStt(), on_move=lambda cmd: None)
    engine._on_look = regards.append
    interrupted = threading.Event()
    interrupted.set()
    engine._guard = types.SimpleNamespace(lock=threading.Lock(), interrupted=interrupted)
    engine._notify_look({"regarder": "devant"})
    assert regards == [{"angle_deg": 0, "hold_ms": 4000}]


def test_on_look_qui_leve_ne_casse_pas_le_tour(timeline, caplog):
    def explose(_payload):
        raise RuntimeError("publish KO")
    with caplog.at_level("ERROR", logger="vision.ai.conversation"):
        assert _tour_avec_cles(
            timeline, ['Tiens. {"emotion": "happy", "regarder": "droite"}'],
            on_look=explose) is True
    assert [e[1] for e in timeline if e[0] == "publish"][-1] == JOIE
    assert any("on_look" in r.message for r in caplog.records)
