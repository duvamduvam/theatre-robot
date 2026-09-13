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
import threading
import time

import pytest

from dadou_utils_ros.utils_static import ANIMATION, FACE

from vision.ai.conversation import ConversationEngine, has_usable_text
from vision.ai.performance import RosMessage
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
                  on_meter=None, on_timing=None):
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
