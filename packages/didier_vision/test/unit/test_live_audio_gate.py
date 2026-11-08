"""Tests de didier_vision/audio/live_audio_gate.py — logique PURE, stdlib uniquement
(aucun micro/numpy requis : LiveAudioGate ne consomme que des `level`/`peak`
déjà calculés et un bool `show_audio` déjà décidé, avec une horloge injectée).

Contrat fixé par dadou_robot_ros/docs/etude-declenchement-conversation.md
§10.8 : niveau fort bloque ; écrêtage bloque MÊME sous le seuil de niveau ;
le maintien tient puis retombe ; arm_tail bloque sur des trames silencieuses ;
une séquence de spectacle bloque mais « parle » ne bloque pas (ceci est du
ressort de l'appelant, cf. test_conversation.py -- LiveAudioGate lui-même ne
connaît que le bool show_audio déjà décidé) ; et surtout le test de
POLARITÉ : gate ouvert = la trame passe.
"""
from didier_vision.audio.live_audio_gate import LiveAudioGate, LiveAudioGateConfig


class FakeClock:
    """Horloge monotone scriptée : avance uniquement quand le test le décide
    (tick()), jamais toute seule — reproductible, aucun sleep réel."""

    def __init__(self, start: float = 0.0):
        self._now = start

    def __call__(self) -> float:
        return self._now

    def tick(self, seconds: float) -> None:
        self._now += seconds


def _make_gate(**config_kwargs):
    clock = FakeClock()
    gate = LiveAudioGate(LiveAudioGateConfig(**config_kwargs), now=clock)
    return gate, clock


# ---------------------------------------------------------------------------
# Polarité : LE test qui interdit l'inversion silencieuse (cf. §10.8 -- même
# famille de bug que le déphasage nul des capteurs d'odométrie et le contact
# NF du coup-de-poing, déjà coûteux à ce projet).
# ---------------------------------------------------------------------------

def test_gate_ouvert_la_trame_passe():
    gate, _clock = _make_gate()
    # Niveau et crête tous les deux sous leurs seuils respectifs, pas de
    # spectacle en cours : rien ne doit jamais bloquer.
    assert gate.feed(level=10.0, peak=100.0, show_audio=False) is False
    assert gate.blocked is False


# ---------------------------------------------------------------------------
# Niveau fort (C3, acoustique inconnue) : bloque.
# ---------------------------------------------------------------------------

def test_niveau_fort_bloque():
    gate, _clock = _make_gate(loud_rms=2800.0)
    assert gate.feed(level=3000.0, peak=100.0, show_audio=False) is True


# ---------------------------------------------------------------------------
# Écrêtage : bloque MÊME sous le seuil de niveau (une syllabe forte isolée
# peut écrêter sans faire monter le RMS moyen de la trame, cf. §10.3).
# ---------------------------------------------------------------------------

def test_ecretage_bloque_meme_sous_le_seuil_de_niveau():
    gate, _clock = _make_gate(loud_rms=2800.0, clip_peak=32000.0)
    # level très en dessous de loud_rms : seul le pic écrête.
    assert gate.feed(level=10.0, peak=32000.0, show_audio=False) is True


# ---------------------------------------------------------------------------
# Maintien (hold_s) : tient après la dernière trame bruyante, puis retombe.
# ---------------------------------------------------------------------------

def test_maintien_tient_puis_retombe():
    gate, clock = _make_gate(loud_rms=2800.0, hold_s=1.0)
    assert gate.feed(level=3000.0, peak=100.0) is True  # trame bruyante

    clock.tick(0.5)  # encore dans le maintien
    assert gate.feed(level=0.0, peak=0.0, show_audio=False) is True

    clock.tick(0.6)  # 1,1 s après la dernière trame bruyante : maintien expiré
    assert gate.feed(level=0.0, peak=0.0, show_audio=False) is False


def test_une_trame_bruyante_isolee_reamorce_le_maintien():
    # Chaque trame bruyante REPOUSSE l'échéance à now + hold_s (cf. docstring
    # LiveAudioGate.feed) : une succession de trames fortes espacées de moins
    # de hold_s ne doit jamais laisser retomber le gate entre elles.
    gate, clock = _make_gate(loud_rms=2800.0, hold_s=1.0)
    assert gate.feed(level=3000.0, peak=100.0) is True

    clock.tick(0.9)
    assert gate.feed(level=3000.0, peak=100.0) is True  # réarme le maintien

    clock.tick(0.9)  # 0,9 s depuis le dernier réarmement : encore tenu
    assert gate.feed(level=0.0, peak=0.0) is True


# ---------------------------------------------------------------------------
# arm_tail (C2, queue acoustique après drain()) : bloque des trames
# SILENCIEUSES pour tail_hold_s, sans qu'aucune condition de feed() ne soit
# jamais vraie -- c'est une anticipation posée AVANT toute mesure.
# ---------------------------------------------------------------------------

def test_arm_tail_bloque_des_trames_silencieuses():
    gate, clock = _make_gate(tail_hold_s=0.5)
    gate.arm_tail()

    assert gate.feed(level=0.0, peak=0.0, show_audio=False) is True

    clock.tick(0.6)  # tail_hold_s dépassé : rouvert
    assert gate.feed(level=0.0, peak=0.0, show_audio=False) is False


# ---------------------------------------------------------------------------
# Séquence de spectacle (C4) : show_audio=True bloque, indépendamment du
# niveau/de la crête -- le cas CHAT_ANIMATION ("parle" exclue) relève de la
# décision de l'APPELANT (chat_node._show_audio_active), pas de ce module,
# qui ne voit qu'un bool déjà tranché.
# ---------------------------------------------------------------------------

def test_sequence_de_spectacle_bloque_meme_en_silence():
    gate, _clock = _make_gate(loud_rms=2800.0, clip_peak=32000.0)
    assert gate.feed(level=0.0, peak=0.0, show_audio=True) is True


def test_absence_de_spectacle_ne_bloque_pas_a_elle_seule():
    gate, _clock = _make_gate(loud_rms=2800.0, clip_peak=32000.0)
    assert gate.feed(level=0.0, peak=0.0, show_audio=False) is False


# ---------------------------------------------------------------------------
# block_for : bloque explicitement pour une durée donnée à partir de
# maintenant, sans dépendre d'une mesure de trame.
# ---------------------------------------------------------------------------

def test_block_for_bloque_pour_la_duree_donnee():
    gate, clock = _make_gate()
    gate.block_for(2.0)

    assert gate.blocked is True
    clock.tick(1.9)
    assert gate.blocked is True
    clock.tick(0.2)
    assert gate.blocked is False


# ---------------------------------------------------------------------------
# Transitions journalisées en INFO (cf. §10.7 -- pas de nouvel état ROS, les
# transitions du gate sont la seule trace disponible).
# ---------------------------------------------------------------------------

def test_transition_de_blocage_journalisee_en_info(caplog):
    gate, clock = _make_gate(loud_rms=2800.0, hold_s=1.0)
    with caplog.at_level("INFO", logger="didier_vision.audio.live_audio_gate"):
        gate.feed(level=3000.0, peak=100.0)  # ouvert -> bloqué : une transition
        gate.feed(level=3000.0, peak=100.0)  # déjà bloqué : pas de nouvelle transition
        clock.tick(1.1)
        gate.feed(level=0.0, peak=0.0)       # bloqué -> ouvert : une transition

    messages = [record.message for record in caplog.records]
    assert sum("BLOQUÉ" in m for m in messages) == 1
    assert sum("rouvert" in m for m in messages) == 1
