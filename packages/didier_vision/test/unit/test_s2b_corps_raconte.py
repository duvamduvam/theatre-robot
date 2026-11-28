"""Lot S2b (`docs/spec-S2-le-corps-raconte.md` §3) — « demander d'abord, parler ensuite ».

CE QUE CES TESTS GRAVENT. Séance du 26/11, 21:14 : David fait STOP console, dit « allez,
go », et Didier répond « Ça y est, je fonce vers la grue ! » — alors que le sélecteur venait
de REFUSER ce go. Ici, la demande part au corps AVANT que la bouche parle, et la réplique est
écrite par un second appel qui connaît la réponse : le mensonge est structurellement
impossible.
"""

import threading
import time

import pytest

from didier_vision.ai import geste_dabord
from didier_vision.ai.conversation import ConversationEngine
from didier_vision.ai.stage import StageState


class _Brain:
    """Brain scripté par APPEL : chaque appel rend la liste de deltas suivante, et note la
    direction reçue (c'est elle qui porte la réponse du corps, cf. §3 « Appel 2 »)."""

    def __init__(self, reponses):
        self._reponses = list(reponses)
        self.appels = []          # [(user_text, direction), …]

    def stream_reply(self, user_text, extra_system=None, situation=None,
                     direction=None, historise=True):
        self.appels.append((user_text, direction))
        deltas = self._reponses.pop(0) if self._reponses else [""]
        for d in deltas:
            yield d


def _moteur(brain, *, on_move=None, stage=None):
    """Moteur réduit aux seules dépendances du chemin testé (aucun audio : on n'appelle que
    _tour_de_geste, pas un tour complet)."""
    return ConversationEngine(
        mic=None, vad=None, stt=None, brain=brain, tts=None, player=None,
        publish=lambda msg: None, on_move=on_move, stage=stage)


def _demande_geste(moteur, brain, texte="allez, go", direction=None):
    """Joue l'appel 1 et rend (params publiés, texte finalement dit)."""
    deltas = brain.stream_reply(texte)
    flux = moteur._tour_de_geste(deltas, texte, direction)
    return "".join(flux) if flux is not None else None


# --- Le tour SANS geste : rien ne change (latence inchangée, §3) ----------------------

def test_tour_sans_geste_la_replique_part_telle_quelle_et_sans_second_appel():
    brain = _Brain([["Bonjour ", "David !"]])
    publies = []
    moteur = _moteur(brain, on_move=publies.append)

    assert _demande_geste(moteur, brain, "bonjour") == "Bonjour David !"
    assert publies == [], "aucune demande de mouvement"
    assert len(brain.appels) == 1, "un seul appel LLM"


# --- Le tour AVEC geste : demander, attendre, puis parler -----------------------------

def test_le_geste_part_avant_toute_parole():
    brain = _Brain([['GESTE {"aller_voir": "banc"}\n'], ["J'y vais !"]])
    publies = []
    moteur = _moteur(brain, on_move=publies.append)

    dit = _demande_geste(moteur, brain, "va voir le banc")

    assert len(publies) == 1, "la demande est partie"
    assert publies[0]["cmd"] == "aller_voir" and publies[0]["objet"] == "banc"
    assert publies[0]["origine"] == "david"
    assert dit == "J'y vais !"
    assert len(brain.appels) == 2, "appel 1 (geste) puis appel 2 (réplique)"


def test_la_premiere_ligne_geste_nest_jamais_dite():
    brain = _Brain([['GESTE {"marche": "go"}\n', "ceci ne doit JAMAIS sortir"], ["En route !"]])
    moteur = _moteur(brain, on_move=lambda m: None)

    assert _demande_geste(moteur, brain) == "En route !"


def test_le_refus_du_corps_est_donne_a_la_bouche_avant_quelle_parle():
    """LE test du lot : STOP console + « allez, go » -> la bouche SAIT qu'elle n'ira pas."""
    brain = _Brain([['GESTE {"marche": "go"}\n'], ["Je voudrais bien, mais tu m'as arrêté."]])
    moteur = _moteur(brain, on_move=lambda m: None)

    def _repond():
        time.sleep(0.01)
        moteur.note_reponse_corps({"demande": {"cmd": "go"}, "effect": "dropped",
                                   "reason": "arrete", "source": "jeu"})
    threading.Thread(target=_repond, daemon=True).start()

    _demande_geste(moteur, brain)

    _, direction = brain.appels[1]
    assert "arrêté par David" in direction
    assert "GO à la console" in direction
    assert "ne dis jamais d'un mouvement qu'il est fait" in direction


def test_l_acceptation_du_corps_est_donnee_a_la_bouche():
    brain = _Brain([['GESTE {"aller_voir": "grue"}\n'], ["J'y fonce !"]])
    moteur = _moteur(brain, on_move=lambda m: None)
    moteur._corps_lock = moteur._corps_lock  # lisibilité

    def _repond():
        time.sleep(0.01)
        moteur.note_reponse_corps({"effect": "accepted", "source": "jeu"})
    threading.Thread(target=_repond, daemon=True).start()

    _demande_geste(moteur, brain, "va voir la grue")

    _, direction = brain.appels[1]
    assert "il accepte" in direction


@pytest.mark.parametrize("raison,attendu", [
    ("corps_sur", "ta sécurité te retient"),
    ("hors_seance", "la séance n'est pas lancée"),
    ("pas_ici", "n'est pas ici"),
    ("hors_atteinte", "trop loin"),
    ("sans_superviseur", "personne ne te surveille"),
])
def test_chaque_refus_est_dit_en_clair_a_la_bouche(raison, attendu):
    brain = _Brain([['GESTE {"aller_voir": "banc"}\n'], ["Ah."]])
    moteur = _moteur(brain, on_move=lambda m: None)

    def _repond():
        time.sleep(0.01)
        moteur.note_reponse_corps({"effect": "dropped", "reason": raison, "source": "jeu"})
    threading.Thread(target=_repond, daemon=True).start()

    _demande_geste(moteur, brain)
    assert attendu in brain.appels[1][1]


def test_corps_muet_la_bouche_doute_jamais_elle_naffirme():
    """Repli sûr : sans réponse dans le délai, la bouche ne dit pas que le geste est parti."""
    brain = _Brain([['GESTE {"marche": "go"}\n'], ["Je ne sais pas si je bouge…"]])
    moteur = _moteur(brain, on_move=lambda m: None)

    debut = time.monotonic()
    _demande_geste(moteur, brain)
    attendu_s = time.monotonic() - debut

    assert attendu_s >= geste_dabord.ATTENTE_CORPS_S * 0.8, "le délai de garde est respecté"
    assert attendu_s < geste_dabord.ATTENTE_CORPS_S + 0.5, "et il est BORNÉ"
    direction = brain.appels[1][1]
    assert "n'a pas répondu" in direction
    assert "il accepte" not in direction


def test_l_etat_du_corps_a_jour_accompagne_la_reponse():
    stage = StageState()
    stage.set_corps_phrase("Tu es arrêté. Seul un go de David te relance.", time.monotonic())
    brain = _Brain([['GESTE {"marche": "go"}\n'], ["Hmm."]])
    moteur = _moteur(brain, on_move=lambda m: None, stage=stage)

    def _repond():
        time.sleep(0.01)
        moteur.note_reponse_corps({"effect": "dropped", "reason": "arrete", "source": "jeu"})
    threading.Thread(target=_repond, daemon=True).start()

    _demande_geste(moteur, brain)
    assert "Tu es arrêté." in brain.appels[1][1]


def test_etat_du_corps_perime_nest_pas_donne():
    """Source muette : la bouche parle sans état plutôt qu'avec un état faux."""
    stage = StageState()
    stage.set_corps_phrase("Tu roules sur ta route.", time.monotonic() - 10.0)
    brain = _Brain([['GESTE {"marche": "go"}\n'], ["Hmm."]])
    moteur = _moteur(brain, on_move=lambda m: None, stage=stage)

    def _repond():
        time.sleep(0.01)
        moteur.note_reponse_corps({"effect": "accepted", "source": "jeu"})
    threading.Thread(target=_repond, daemon=True).start()

    _demande_geste(moteur, brain)
    assert "Tu roules" not in brain.appels[1][1]


# --- Garde-fous ----------------------------------------------------------------------

def test_une_reponse_hors_attente_est_ignoree():
    brain = _Brain([["Bonjour."]])
    moteur = _moteur(brain)
    assert moteur.note_reponse_corps({"effect": "accepted", "source": "jeu"}) is False


def test_une_seule_reponse_est_retenue():
    brain = _Brain([['GESTE {"marche": "go"}\n'], ["Ok."]])
    moteur = _moteur(brain, on_move=lambda m: None)
    attente = moteur._armer_attente_corps()
    assert moteur.note_reponse_corps({"effect": "accepted", "source": "jeu"}) is True
    assert moteur.note_reponse_corps({"effect": "dropped", "reason": "arrete",
                                      "source": "jeu"}) is False
    assert moteur._attendre_corps(attente)["effect"] == "accepted"


def test_publication_en_echec_la_bouche_parle_quand_meme():
    """Un on_move qui lève ne doit jamais rendre Didier muet."""
    def _leve(_msg):
        raise RuntimeError("publication en échec (test)")

    brain = _Brain([['GESTE {"marche": "go"}\n'], ["Je crois que je bouge."]])
    moteur = _moteur(brain, on_move=_leve)
    assert _demande_geste(moteur, brain) == "Je crois que je bouge."


# --- Revue adverse du 27/11 : le geste ne part JAMAIS deux fois ------------------------
#
# Le prompt interdit à l'appel 2 de remettre une clé de mouvement dans son JSON de fin,
# mais un LLM désobéit. Sans garde, David dit « va voir le banc » UNE fois et Didier part
# DEUX fois (ligne GESTE de l'appel 1, puis JSON de fin de l'appel 2).

def test_le_json_de_fin_de_lappel_2_ne_renvoie_pas_le_geste():
    publies = []
    brain = _Brain([['GESTE {"aller_voir": "banc"}\n'], ["J'y vais !"]])
    moteur = _moteur(brain, on_move=publies.append)
    moteur.note_reponse_corps  # (attente armée par _tour_de_geste)

    _demande_geste(moteur, brain, "va voir le banc")
    assert len(publies) == 1, "le geste est parti une fois (ligne GESTE)"

    # L'appel 2 répète la clé dans son JSON de fin : elle doit être IGNORÉE.
    assert moteur._notify_move({"aller_voir": "banc"}) is False
    assert len(publies) == 1, "le geste ne part pas une seconde fois"


def test_un_stop_du_json_de_fin_passe_toujours_apres_un_geste():
    """Garde non bloquante pour les arrêts : un « stop » n'est JAMAIS avalé."""
    publies = []
    brain = _Brain([['GESTE {"aller_voir": "banc"}\n'], ["J'y vais… non, j'arrête."]])
    moteur = _moteur(brain, on_move=publies.append)

    _demande_geste(moteur, brain, "va voir le banc")
    # (le retour de _notify_move dit « une pause est partie », pas « l'ordre est passé » :
    # c'est ce qui est PUBLIÉ qui fait foi.)
    moteur._notify_move({"marche": "stop"})
    assert any(p.get("cmd") == "stop" for p in publies), "le stop est bien parti"


def test_le_baillon_ne_fuit_pas_sur_le_tour_suivant():
    """Un tour de geste ne doit pas empêcher le geste du tour SUIVANT."""
    publies = []
    brain = _Brain([['GESTE {"aller_voir": "banc"}\n'], ["J'y vais !"]])
    moteur = _moteur(brain, on_move=publies.append)
    _demande_geste(moteur, brain, "va voir le banc")
    assert moteur._geste_deja_parti is True

    # Entrée d'un nouveau tour : le drapeau est remis à zéro (_speak_reply).
    moteur._geste_deja_parti = False
    moteur._notify_move({"aller_voir": "grue"})
    assert len(publies) == 2, "le geste du tour suivant part normalement"
    assert publies[-1].get("objet") == "grue"


def test_le_drapeau_est_remis_a_zero_a_lentree_de_chaque_tour():
    """Mutation du 27/11 : si `_geste_deja_parti` n'est pas remis à zéro à l'entrée de
    `_speak_reply`, le premier tour de geste BÂILLONNE les gestes de TOUS les tours
    suivants — David dirait « va voir la grue » et plus rien ne partirait.

    On appelle ici le VRAI `_speak_reply` (sans audio : tts/player None, mute=True), donc
    la ligne de remise à zéro est réellement exécutée."""
    class _Player:
        def drain(self):
            pass

        def play(self, *a, **k):
            pass

    class _Tts:
        def synth(self, *a, **k):
            return b""

    class _Mic:
        def start(self):
            pass

        def stop(self):
            pass

    publies = []
    brain = _Brain([['GESTE {"aller_voir": "banc"}\n'], ['J\'y vais ! {"emotion": "happy"}'],
                    ['GESTE {"aller_voir": "grue"}\n'], ['La grue ! {"emotion": "happy"}']])
    moteur = ConversationEngine(
        mic=_Mic(), vad=None, stt=None, brain=brain, tts=_Tts(), player=_Player(),
        publish=lambda msg: None, on_move=publies.append, stage=None)

    moteur._speak_reply("va voir le banc", mute=True)
    gestes_t1 = [p for p in publies if p.get("cmd") == "aller_voir"]
    assert len(gestes_t1) == 1, "tour 1 : le geste part une fois"

    # Tour 2, par le même chemin : le drapeau doit avoir été remis à zéro à l'entrée.
    moteur._speak_reply("va voir la grue", mute=True)
    gestes_t2 = [p for p in publies if p.get("cmd") == "aller_voir"]
    assert len(gestes_t2) == 2, (
        "tour 2 : le geste est bâillonné — `_geste_deja_parti` n'a pas été remis à zéro "
        "à l'entrée de _speak_reply")
    assert gestes_t2[-1].get("objet") == "grue"


# --- Fumée du 28/11 (main 74735a24) : « GESTE » PRONONCÉ ------------------------------
# « Va voir la table basse. » -> l'aller_voir part, le corps accepte, puis Didier dit
# « GESTE » et rien d'autre ; « Fais le tour de l'éléphant. » -> « GESTE » seul aussi. Cause :
# l'appel 2 porte le même prompt (gabarit GESTE compris) et la même demande ; le LLM
# recommence par `GESTE {…}`, et ce flux n'était pas filtré — le parseur coupait au « { » et
# disait « GESTE ». Ces tests rejouent les sorties fautives par le VRAI `_speak_reply` (parseur
# de flux compris, découpé en deltas comme l'API), sans audio (mute=True).

class _Muet:
    def drain(self):
        pass

    def play(self, *a, **k):
        pass

    def start(self):
        pass

    def stop(self):
        pass


def _tour_complet(reponses, texte, *, objets=None):
    """Joue un tour humain complet. -> (répliques dites au transcript, gestes publiés, brain)."""
    dits, publies = [], []
    brain = _Brain(reponses)
    moteur = ConversationEngine(
        mic=_Muet(), vad=None, stt=None, brain=brain, tts=None, player=_Muet(),
        publish=lambda msg: None, on_move=publies.append, stage=None,
        on_transcript=lambda role, t: dits.append(t))
    if objets is not None:
        moteur.set_objets(objets)
    moteur._speak_reply(texte, mute=True)
    return dits, publies, brain


def test_fumee_28_11_lappel_2_qui_recommence_par_geste_nest_pas_dit():
    """Le cas exact de la table basse : l'appel 2 ne rend QUE la ligne GESTE (et une émotion)."""
    dits, publies, brain = _tour_complet(
        [['GESTE {"aller_voir": "table_basse"}', "\n"],
         ['GES', 'TE {"aller_', 'voir": "table_basse"} {"emotion": "happy"}']],
        "Va voir la table basse.")
    assert dits == [], "« GESTE » ne doit jamais être dit"
    assert [p["cmd"] for p in publies] == ["aller_voir"], "le geste part une fois, pas deux"
    assert len(brain.appels) == 2, "l'appel 2 a bien lieu"
    assert "pas de ligne GESTE" in brain.appels[1][1], "la consigne de l'appel 2 l'interdit"


def test_fumee_28_11_lappel_2_parle_apres_sa_ligne_geste():
    dits, _, _ = _tour_complet(
        [['GESTE {"aller_voir": "table_basse"}\n'],
         ['GESTE {"aller_voir": "table_basse"}\n', "J'y vais, ", 'la table m\'appelle ! {"emotion": "happy"}']],
        "Va voir la table basse.")
    assert dits == ["J'y vais, la table m'appelle !"]


@pytest.mark.parametrize("appel_1", [
    ["GESTE"],                                            # le mot seul
    ["GESTE\n", '{"faire_le_tour": "elephant"}'],         # JSON sur la ligne suivante
    ["Geste", ' {faire_le_tour: elephant}\n', "Je fais le tour !"],   # JSON illisible
])
def test_ligne_geste_illisible_rien_nest_dit_aucun_geste_ne_part(appel_1):
    dits, publies, brain = _tour_complet([appel_1, ["ne doit pas être demandé"]],
                                         "Fais le tour de l'éléphant.")
    assert dits == []
    assert publies == [], "aucun geste inventé (ni par la ligne, ni par un JSON de fin)"
    assert len(brain.appels) == 1, "pas d'appel 2 sans geste lu"


def test_une_phrase_geste_au_milieu_dune_replique_nest_pas_dite():
    """Dernière barrière (Sentence du parseur) : « D'accord. GESTE {…} » sur une seule ligne."""
    dits, _, _ = _tour_complet([["D'accord. ", 'GESTE {"emotion": "happy"}']], "Tu viens ?")
    assert dits == ["D'accord."]


def test_fumee_28_11_le_refus_local_est_la_reponse_du_corps():
    """« Fais le tour de l'éléphant » refusé par le tableau des objets : rien n'est publié, mais
    la bouche doit apprendre la VRAIE raison, tout de suite — pas « ton corps n'a pas répondu »
    après 0,5 s d'attente."""
    from theatre_contrats import objets

    debut = time.monotonic()
    dits, publies, brain = _tour_complet(
        [['GESTE {"faire_le_tour": "elephant"}\n'], ["Un éléphant ? Je n'en vois pas ici."]],
        "Fais le tour de l'éléphant.", objets=objets.VIDE)
    duree = time.monotonic() - debut

    assert publies == [], "un geste refusé par le tableau n'est jamais publié"
    direction = brain.appels[1][1]
    assert "tu ne connais pas cet objet ici" in direction
    assert "n'a pas répondu" not in direction
    assert duree < geste_dabord.ATTENTE_CORPS_S * 0.8, "aucune attente du délai de garde"
    assert dits == ["Un éléphant ?", "Je n'en vois pas ici."]
