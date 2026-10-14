"""Tests de vision/ai/llm_stream.py — client_factory injectable : AUCUN
appel réseau ni import openai réel dans ce fichier (cf. docstring de
StreamingBrain : le vrai client OpenAI n'est construit que si aucun
client_factory n'est fourni, jamais le cas ici).

Isolation ChatDB : même pattern que test_chat_db.py — configure() vers un
fichier SQLite temporaire AVANT toute création de StreamingBrain (qui crée
une session ChatDB à la construction), jamais le fichier de prod.
"""
from vision.ai.llm_stream import StreamingBrain
from vision.db.chat_db import ChatDB


class FakeDelta:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.delta = FakeDelta(content)


class FakeChunk:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    """Simule client.chat.completions.create(..., stream=True) : renvoie un
    itérable de FakeChunk correspondant à `deltas`, et enregistre les
    arguments reçus pour vérification (modèle/messages/max_tokens/stream)."""

    def __init__(self, deltas):
        self._deltas = deltas
        self.last_call = None

    def create(self, **kwargs):
        self.last_call = kwargs
        return [FakeChunk(d) for d in self._deltas]


class FakeChat:
    def __init__(self, completions):
        self.completions = completions


class FakeClient:
    def __init__(self, deltas):
        self.completions = FakeCompletions(deltas)
        self.chat = FakeChat(self.completions)


def _configure_test_db(tmp_path):
    ChatDB.configure(str(tmp_path / "test_llm_stream.db"))


# --------------------------------------------------------------------------
# stream_reply() : deltas renvoyés tels quels, None/vide filtrés.
# --------------------------------------------------------------------------

def test_stream_reply_yields_non_empty_deltas_in_order(tmp_path):
    _configure_test_db(tmp_path)
    client = FakeClient(["Bon", "jour", None, "", " !"])  # None/"" doivent être filtrés

    brain = StreamingBrain(
        model="anthropic/claude-haiku-4.5",
        base_url="https://openrouter.ai/api/v1",
        system_prompt="Tu es Didier.",
        client_factory=lambda: client,
    )

    deltas = list(brain.stream_reply("Salut Didier"))

    assert deltas == ["Bon", "jour", " !"]


def test_stream_reply_sends_expected_model_and_system_prompt(tmp_path):
    _configure_test_db(tmp_path)
    client = FakeClient(["Salut."])

    brain = StreamingBrain(
        model="anthropic/claude-haiku-4.5",
        base_url="https://openrouter.ai/api/v1",
        system_prompt="Tu es Didier, robot de théâtre.",
        max_tokens=42,
        client_factory=lambda: client,
    )

    list(brain.stream_reply("Salut"))

    call = client.completions.last_call
    assert call["model"] == "anthropic/claude-haiku-4.5"
    assert call["max_tokens"] == 42
    assert call["stream"] is True
    assert call["messages"][0] == {"role": "system", "content": "Tu es Didier, robot de théâtre."}
    # Le message utilisateur ajouté par stream_reply() apparaît bien dans
    # l'historique envoyé (juste après le system prompt).
    assert {"role": "user", "content": "Salut"} in call["messages"]


# --------------------------------------------------------------------------
# Historique (ChatDB réutilisé) : persistance et history_limit.
# --------------------------------------------------------------------------

def test_history_accumulates_across_turns(tmp_path):
    _configure_test_db(tmp_path)
    client = FakeClient(["Réponse un."])

    brain = StreamingBrain(
        model="m", base_url="https://x", system_prompt="sys",
        client_factory=lambda: client,
    )

    list(brain.stream_reply("Premier message"))

    history = brain._history_entry.get_history()
    assert history == [
        {"role": "user", "content": "Premier message"},
        {"role": "assistant", "content": "Réponse un."},
    ]

    client.completions._deltas = ["Réponse deux."]
    list(brain.stream_reply("Deuxième message"))

    history = brain._history_entry.get_history()
    assert history == [
        {"role": "user", "content": "Premier message"},
        {"role": "assistant", "content": "Réponse un."},
        {"role": "user", "content": "Deuxième message"},
        {"role": "assistant", "content": "Réponse deux."},
    ]


def test_only_the_personality_prompt_is_sent_as_system_role(tmp_path):
    # Verrou du bug du 2026-09-13 : c'est CE test qui aurait attrapé la
    # régression (role=system pour les répliques de Didier stockées en
    # historique). Le seul message "system" envoyé au LLM doit être le
    # prompt de personnalité ajouté par stream_reply() — aucun message
    # "system" ne doit provenir de l'historique, même après plusieurs tours.
    _configure_test_db(tmp_path)
    client = FakeClient(["Réponse un."])

    brain = StreamingBrain(
        model="m", base_url="https://x", system_prompt="Tu es Didier.",
        client_factory=lambda: client,
    )

    list(brain.stream_reply("Premier message"))

    client.completions._deltas = ["Réponse deux."]
    list(brain.stream_reply("Deuxième message"))

    messages = client.completions.last_call["messages"]
    system_messages = [m for m in messages if m["role"] == "system"]
    assert system_messages == [{"role": "system", "content": "Tu es Didier."}]


def test_history_limit_truncates_messages_sent_to_llm(tmp_path):
    _configure_test_db(tmp_path)
    client = FakeClient(["ok"])

    brain = StreamingBrain(
        model="m", base_url="https://x", system_prompt="sys",
        history_limit=2, client_factory=lambda: client,
    )

    # Pré-remplit l'historique avec 4 messages (2 tours), directement via
    # ChatDB (pas via stream_reply, pour ne pas déclencher d'appel LLM ici).
    for i in range(4):
        brain._history_entry.add_user_text("msg %d" % i)

    list(brain.stream_reply("dernier message"))

    call = client.completions.last_call
    # messages = [system] + les 2 DERNIERS de l'historique tronqué
    # (history_limit=2), le dernier étant "dernier message" lui-même (ajouté
    # par stream_reply avant l'appel).
    assert call["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "msg 3"},
        {"role": "user", "content": "dernier message"},
    ]


# --------------------------------------------------------------------------
# Chargement paresseux : constructible sans secret tant qu'un client_factory
# est fourni ; _get_client() ne construit le client qu'UNE fois (mémoïsé).
# --------------------------------------------------------------------------

def test_client_factory_called_lazily_and_only_once(tmp_path):
    _configure_test_db(tmp_path)
    build_count = 0
    client = FakeClient(["a"])

    def factory():
        nonlocal build_count
        build_count += 1
        return client

    brain = StreamingBrain(model="m", base_url="https://x", client_factory=factory)
    assert build_count == 0  # rien construit au constructeur (paresseux)

    list(brain.stream_reply("un"))
    assert build_count == 1

    client.completions._deltas = ["b"]
    list(brain.stream_reply("deux"))
    assert build_count == 1  # pas reconstruit au deuxième tour (mémoïsé)


# --------------------------------------------------------------------------
# reconfigure() : changement de personnalité à chaud (lot D3, cf.
# vision.ai.personas et le topic `persona` de chat_node) — nouveau prompt ET
# nouvelle session ChatDB, les deux ensemble (un historique hérité donnerait
# un Didier schizophrène, cf. docstring de reconfigure).
# --------------------------------------------------------------------------

def test_reconfigure_change_le_prompt_et_ouvre_une_nouvelle_session(tmp_path):
    _configure_test_db(tmp_path)
    client = FakeClient(["Oui."])

    brain = StreamingBrain(
        model="anthropic/claude-haiku-4.5",
        base_url="https://openrouter.ai/api/v1",
        system_prompt="PROMPT BOUGON",
        client_factory=lambda: client,
    )
    list(brain.stream_reply("premier tour, ancien personnage"))

    brain.reconfigure("PROMPT NAIF")
    list(brain.stream_reply("second tour, nouveau personnage"))

    call = client.completions.last_call
    # Nouveau prompt envoyé...
    assert call["messages"][0] == {"role": "system", "content": "PROMPT NAIF"}
    # ...et historique REPARTI À NEUF : l'échange de l'ancien personnage ne
    # doit pas figurer dans le contexte du nouveau (system + user courant
    # seulement).
    contents = [m["content"] for m in call["messages"]]
    assert "premier tour, ancien personnage" not in contents
    assert "second tour, nouveau personnage" in contents


# --------------------------------------------------------------------------
# extra_system : consigne de mise en scène (lot R3, topic chat_instruction,
# cf. vision.ai.stage) — SECOND message system, juste après le prompt de
# personnalité, jamais consigné dans l'historique.
# --------------------------------------------------------------------------

def test_extra_system_envoye_en_second_message_system(tmp_path):
    _configure_test_db(tmp_path)
    client = FakeClient(["Réponse un."])

    brain = StreamingBrain(
        model="m", base_url="https://x", system_prompt="Tu es Didier.",
        client_factory=lambda: client,
    )
    list(brain.stream_reply("Premier message"))

    client.completions._deltas = ["Réponse deux."]
    list(brain.stream_reply("Deuxième message", extra_system="Tu boudes."))

    # Texte EXACT gravé (préfixe compris) et place exacte : prompt, consigne,
    # puis l'historique — la consigne du tour courant n'est pas noyée après
    # les échanges passés.
    assert client.completions.last_call["messages"] == [
        {"role": "system", "content": "Tu es Didier."},
        {"role": "system",
         "content": "Consigne de mise en scène (à jouer, jamais à prononcer) : Tu boudes."},
        {"role": "user", "content": "Premier message"},
        {"role": "assistant", "content": "Réponse un."},
        {"role": "user", "content": "Deuxième message"},
    ]


def test_extra_system_jamais_historise(tmp_path):
    # Une consigne vaut pour le tour où elle est posée : l'historiser la
    # ferait survivre à sa levée (cf. docstring de stream_reply).
    _configure_test_db(tmp_path)
    client = FakeClient(["Oui."])

    brain = StreamingBrain(
        model="m", base_url="https://x", system_prompt="Tu es Didier.",
        client_factory=lambda: client,
    )
    list(brain.stream_reply("Salut", extra_system="Tu es pressé."))
    list(brain.stream_reply("Et alors ?"))

    assert brain._history_entry.get_history() == [
        {"role": "user", "content": "Salut"},
        {"role": "assistant", "content": "Oui."},
        {"role": "user", "content": "Et alors ?"},
        {"role": "assistant", "content": "Oui."},
    ]
    # Consigne levée (extra_system absent) : plus qu'UN message system.
    system_messages = [m for m in client.completions.last_call["messages"]
                       if m["role"] == "system"]
    assert system_messages == [{"role": "system", "content": "Tu es Didier."}]
