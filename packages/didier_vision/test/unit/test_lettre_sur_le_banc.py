"""La LETTRE SUR LE BANC rejouée côté bouche (lot « texte raccord », séance du 18/11 21:35).

Séance : David « il y a une lettre sur le banc, tu pourrais regarder » -> la bouche demande « aller
voir banc » -> refusé (le banc est à 22 m : « pas_ici ») -> Didier répond « Je vois bien une
enveloppe posée dessus » malgré la consigne -> la tâche est close « fini ». Désormais (valeurs et
textes GRAVÉS) :
  - la réplique qui suit le refus est CONTRÔLÉE avant d'être dite : « je vois… » rejetée (jamais
    synthétisée, jamais historisée), régénérée avec la CORRECTION, au plus 2 essais, puis repli ;
  - la tâche se ferme « échec : geste refusé », jamais « fini » ;
  - « regarde » = "marche": "pause" : on_move("pause") + regard (devant à défaut), jamais un geste.

Mutations (doivent rougir) :
  - contrôle débranché (echec ignoré)              -> test_seance_2135_je_vois_rejetee_puis_regeneree
  - borne d'essais retirée / repli absent          -> test_deux_pretentions_repli_sur
  - réplique rejetée historisée                    -> test_seance_2135_je_vois_rejetee_puis_regeneree
  - close « fini » après refus                     -> test_seance_2135_je_vois_rejetee_puis_regeneree
  - pause qui laisse passer le geste               -> test_pause_l_emporte_sur_aller_voir
  - pause permise en tour spontané                 -> test_pause_ignoree_en_tour_spontane
"""
import pytest

from didier_vision.ai import conversation as conversation_module
from didier_vision.ai import raccord
from didier_vision.ai.conversation import LOOK_HOLD_MS, TASK_USER_TEXT, ConversationEngine
from didier_vision.ai.move_task import CLOSE_DONE, CLOSE_FAILED, MoveTask
from didier_vision.ai.stage import StageState
from theatre_contrats.objets import Objet, Tableau

LETTRE = "Il y a une lettre sur le banc, tu pourrais regarder ?"
# Tableau vu de x = 14 (séance du 15/11, valeurs gravées dans didier_perception) : le banc à 22 m.
BANC = Objet(id="carte/banc", nom="banc", distance_m=22.3, azimut_deg=6.4, cote="devant", x=36.2, y=2.5,
             tour=True)
TABLE = Objet(id="carte/table_basse", nom="table_basse", distance_m=4.3, azimut_deg=3.0, cote="devant",
              x=18.3, y=1.4, en_vue=True, atteignable=True)
TABLEAU = Tableau((TABLE, BANC))
# La direction d'échec servie après le refus (texte de MoveTask, gravé dans test_move_task).
ECHEC_BANC = (
    "Ton geste « aller voir banc » n'a PAS eu lieu : il n'est pas ici : il est à 22 m devant toi, tu ne "
    "le vois pas d'où tu es. Tu n'as pas bougé. Ta tâche, demandée par David : « " + LETTRE + " ». "
    "Dis-le en personnage, en une phrase : ne prétends JAMAIS l'avoir fait. Ne redemande pas ce "
    "geste-là ; si un autre geste sert la tâche, fais-le, sinon dis que tu ne peux pas, SANS clé de "
    "geste.")
PREMIERE = 'Une lettre ? Allons voir ça ! {"emotion": "happy", "aller_voir": "banc"}'
SEANCE = 'Je vois bien une enveloppe posée dessus. {"emotion": "happy"}'
HONNETE = 'Le banc est bien trop loin, je ne distingue rien d\'ici. {"emotion": "sad"}'


class Horloge:
    def __init__(self):
        self.t = 100.0

    def monotonic(self):
        return self.t


@pytest.fixture
def horloge(monkeypatch):
    h = Horloge()
    monkeypatch.setattr(conversation_module, "time",
                        type("T", (), {"monotonic": staticmethod(h.monotonic),
                                       "sleep": staticmethod(lambda _s: None)}))
    return h


class Micro:
    """Chaque trame lue « dure » 1 s (silence) : la continuation passe à la première lecture."""
    sample_rate = 16000

    def __init__(self, horloge, n=4):
        self._h, self._n = horloge, n

    def start(self):
        pass

    def stop(self):
        pass

    def read_frame(self):
        self._h.t += 1.0
        if self._n <= 0:
            return None
        self._n -= 1
        return b"\x00"

    def frame_rms(self, _f):
        return 0.0

    def frame_peak(self, _f):
        return 0.0

    def preroll(self):
        return b""

    def purge_preroll(self):
        pass


class Vad:
    def feed(self, _level):
        return None

    def reset(self):
        pass


class Tts:
    def __init__(self):
        self.dits = []

    def synthesize(self, text):
        self.dits.append(text)
        return b"PCM", 22050


class Lecteur:
    def play(self, *_a):
        pass

    def play_async_raw(self, *_a):
        pass

    def drain(self):
        pass

    def interrupt(self):
        pass


class Cerveau:
    """Répliques scriptées, servies DANS L'ORDRE (une par appel) ; appels et historique notés.
    `panne` : lève au lieu de répondre."""

    def __init__(self, repliques, panne=False):
        self._repliques = list(repliques)
        self._panne = panne
        self.appels = []
        self.historique = []

    def stream_reply(self, user_text, **kwargs):
        self.appels.append(dict(kwargs, user_text=user_text))
        if self._panne:
            raise RuntimeError("panne LLM simulée")
        texte = self._repliques.pop(0)
        if kwargs.get("historise", True):
            self.historique += [("user", user_text), ("assistant", texte)]
        yield texte

    def record_exchange(self, user_text, reply_text):
        self.historique += [("user", user_text), ("assistant", reply_text)]


def moteur(horloge, cerveau, task, tableau=TABLEAU):
    ordres, regards = [], []
    tts = Tts()
    engine = ConversationEngine(
        mic=Micro(horloge), vad=Vad(), stt=None, brain=cerveau, tts=tts, player=Lecteur(),
        publish=lambda _m: None, refresh_ms=15000, dead_mic_backoff_s=0.0, stage=StageState(),
        on_move=ordres.append, on_look=regards.append, move_task=task)
    engine.set_objets(tableau)
    return engine, ordres, regards, tts


def tour_humain(engine, texte):
    engine._stage.push_text(texte)
    return engine.run_once()


def test_seance_2135_je_vois_rejetee_puis_regeneree(horloge, caplog):
    task = MoveTask()
    cerveau = Cerveau([PREMIERE, SEANCE, HONNETE])
    engine, ordres, _regards, tts = moteur(horloge, cerveau, task)
    assert tour_humain(engine, LETTRE) is True
    assert ordres == []                                     # « aller voir banc » jamais publié
    with caplog.at_level("INFO"):
        assert engine.run_once() is True                    # la continuation d'échec
    # Ce qui est DIT : la première réplique du tour humain, puis la réplique honnête — jamais « je vois ».
    assert tts.dits == ["Une lettre ?", "Allons voir ça !",
                        "Le banc est bien trop loin, je ne distingue rien d'ici."]
    # Deux essais hors historique ; le second porte la correction avec l'extrait rejeté.
    essais = cerveau.appels[1:]
    assert [a["historise"] for a in essais] == [False, False]
    assert essais[0]["direction"] == ECHEC_BANC
    assert essais[1]["direction"] == ECHEC_BANC + " " + raccord.CORRECTION.format(extrait="je vois")
    assert all(a["user_text"] == TASK_USER_TEXT for a in essais)
    # Historique : la réplique rejetée n'y est pas, la réplique dite oui.
    assert cerveau.historique[-2:] == [("user", TASK_USER_TEXT), ("assistant", HONNETE)]
    assert SEANCE not in [t for _r, t in cerveau.historique]
    # Tâche close en ÉCHEC, jamais « fini ».
    assert not task.is_open() and task.last_close == CLOSE_FAILED == "échec : geste refusé"
    assert f"Tâche close (échec : geste refusé) : {LETTRE!r} après 1 geste(s)." in [
        r.getMessage() for r in caplog.records]
    assert any(r.getMessage().startswith("Réplique contrôlée REJETÉE (essai 1/2) : prétend « je vois »")
               for r in caplog.records)


def test_deux_pretentions_repli_sur(horloge):
    task = MoveTask()
    # La seconde réplique fautive porte aussi un geste : JAMAIS émis (elle n'est pas jouée).
    cerveau = Cerveau([PREMIERE, SEANCE, 'J\'y vais ! {"emotion": "happy", "avancer": 3}'])
    engine, ordres, _regards, tts = moteur(horloge, cerveau, task)
    tour_humain(engine, LETTRE)
    assert engine.run_once() is True
    assert tts.dits[-1] == raccord.REPLI_REFUS
    assert len(cerveau.appels) == 1 + raccord.CONTROLE_ESSAIS_MAX
    assert ordres == []
    assert cerveau.historique[-1] == ("assistant", raccord.REPLI_REFUS)
    assert task.last_close == CLOSE_FAILED


def test_panne_llm_pendant_le_controle_repli_sur(horloge):
    task = MoveTask()
    cerveau = Cerveau([PREMIERE])
    engine, _ordres, _regards, tts = moteur(horloge, cerveau, task)
    tour_humain(engine, LETTRE)
    cerveau._panne = True
    assert engine.run_once() is True
    assert tts.dits[-1] == raccord.REPLI_REFUS
    assert task.last_close == CLOSE_FAILED


def test_reponse_honnete_du_premier_coup_un_seul_essai(horloge):
    task = MoveTask()
    cerveau = Cerveau([PREMIERE, HONNETE])
    engine, _ordres, _regards, tts = moteur(horloge, cerveau, task)
    tour_humain(engine, LETTRE)
    engine.run_once()
    assert len(cerveau.appels) == 2 and "ATTENTION" not in cerveau.appels[1]["direction"]
    assert tts.dits[-1] == "Le banc est bien trop loin, je ne distingue rien d'ici."


def test_continuation_reussie_non_controlee_close_fini(horloge):
    # Geste ARRIVÉ : la réplique est streamée comme avant (historisée, une seule passe), « fini ».
    task = MoveTask()
    task.gesture_emitted("va voir la table", False, horloge.t)
    task.on_result({"name": "table_basse", "result": "arrived", "reason": "arrived", "travelled": 4.0},
                   horloge.t)
    cerveau = Cerveau(['Me voilà devant la table. {"emotion": "happy"}'])
    engine, _ordres, _regards, tts = moteur(horloge, cerveau, task)
    assert engine.run_once() is True
    assert tts.dits == ["Me voilà devant la table."]
    assert "historise" not in cerveau.appels[0]
    assert task.last_close == CLOSE_DONE == "fini"


# ------------------------------------------------------------------ « regarde » = pause
REGARDE = 'Une lettre ? Je m\'arrête pour regarder. {"emotion": "surprise", "marche": "pause", "regarder": 10}'


def test_regarde_pause_et_regard(horloge):
    cerveau = Cerveau([REGARDE])
    engine, ordres, regards, _tts = moteur(horloge, cerveau, MoveTask())
    tour_humain(engine, LETTRE)
    assert ordres == ["pause"]
    assert regards == [{"angle_deg": 10, "hold_ms": LOOK_HOLD_MS}]


def test_pause_sans_regard_regarde_devant(horloge):
    cerveau = Cerveau(['Voyons. {"emotion": "surprise", "marche": "pause"}'])
    engine, ordres, regards, _tts = moteur(horloge, cerveau, MoveTask())
    tour_humain(engine, LETTRE)
    assert ordres == ["pause"] and regards == [{"angle_deg": 0, "hold_ms": 4000}]


def test_pause_l_emporte_sur_aller_voir(horloge):
    task = MoveTask()
    cerveau = Cerveau(['Voyons. {"emotion": "surprise", "marche": "pause", "aller_voir": "table_basse"}'])
    engine, ordres, _regards, _tts = moteur(horloge, cerveau, task)
    tour_humain(engine, LETTRE)
    assert ordres == ["pause"]
    assert not task.is_open()                               # aucune tâche : rien n'est parti


def test_stop_l_emporte_sur_pause(horloge):
    cerveau = Cerveau(['Halte. {"emotion": "neutral", "marche": "stop"}'])
    engine, ordres, _regards, _tts = moteur(horloge, cerveau, MoveTask())
    tour_humain(engine, "stop")                             # (l'arrêt d'urgence vocal part aussi)
    assert set(ordres) == {"stop"}


def test_pause_ignoree_en_tour_spontane(horloge):
    cerveau = Cerveau(['Tiens, un pigeon. {"emotion": "surprise", "marche": "pause", "regarder": 30}'])
    engine, ordres, regards, _tts = moteur(horloge, cerveau, MoveTask())
    engine._serve_prompt("Didier remarque un pigeon.")
    assert ordres == []
    assert regards == [{"angle_deg": 30, "hold_ms": 4000}]  # le regard, lui, reste permis

