"""Tests de ChatDB (SQLite isolé en tmp_path — jamais le fichier de prod db/chat.db)."""
from vision.db.chat_db import ChatDB


def test_create_insert_and_history_summary(tmp_path):
    ChatDB.configure(str(tmp_path / "test_chat.db"))

    entry = ChatDB.create({})
    assert entry is not None
    assert entry.speaker_name is None

    entry.add_user_text("salut Didier")
    entry.add_assistant_text("salut, comment vas-tu ?")

    history = entry.get_history()
    assert history == [
        {"role": "user", "content": "salut Didier"},
        {"role": "assistant", "content": "salut, comment vas-tu ?"},
    ]


def test_add_assistant_text_uses_assistant_role_not_system(tmp_path):
    # Verrou du bug du 2026-09-13 : une réplique de Didier ne doit JAMAIS
    # être enregistrée avec le rôle "system" (sinon elle revient au LLM
    # comme une consigne plutôt que comme son propre tour, cf. llm_stream).
    ChatDB.configure(str(tmp_path / "test_chat_role.db"))

    entry = ChatDB.create({})
    entry.add_assistant_text("je suis Didier")

    assert entry.get_history() == [{"role": "assistant", "content": "je suis Didier"}]


def test_get_history_requalifie_les_anciennes_entrees_system_en_assistant(tmp_path):
    # Compat descendante : une base écrite AVANT le correctif contient
    # d'anciennes répliques de Didier sous role=system (le bug lui-même).
    # get_history() doit les requalifier à la lecture, sans quoi une
    # session déjà ouverte au moment de la mise à jour continuerait
    # d'injecter ces répliques comme consignes.
    ChatDB.configure(str(tmp_path / "test_chat_legacy.db"))

    entry = ChatDB.create({})
    entry.set_history([
        {"role": "user", "content": "salut Didier"},
        {"role": "system", "content": "ancienne réplique héritée du bug"},
    ])

    assert entry.get_history() == [
        {"role": "user", "content": "salut Didier"},
        {"role": "assistant", "content": "ancienne réplique héritée du bug"},
    ]


def test_tokens_defaults_to_zero_and_is_settable(tmp_path):
    ChatDB.configure(str(tmp_path / "test_chat_tokens.db"))

    entry = ChatDB.create({})
    assert entry.tokens == 0

    entry.tokens = 42
    assert entry.tokens == 42


def test_configure_creates_missing_directory(tmp_path):
    # db/ est gitignoré : sur une machine fraîche (CI), le dossier n'existe
    # pas encore. configure() doit le créer plutôt que planter.
    db_path = tmp_path / "nested" / "does" / "not" / "exist" / "chat.db"

    ChatDB.configure(str(db_path))

    assert db_path.parent.is_dir()
