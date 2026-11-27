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
