"""Tests de didier_vision/ai/emergency.py (lot P1, arrêt d'urgence vocal, 2026-10-23).

Listes GRAVÉES de la spec fermée (dadou_robot_ros/docs/spec-metteur-en-scene.md
§P1) : décision de David — mots-clés pour l'URGENCE seulement. Les faux
doivent rester faux (une phrase avec un contexte part au LLM), les vrais
doivent rester vrais (un faux négatif = Didier qui ne s'arrête pas).
"""
import pytest

from didier_vision.ai.emergency import (FILLERS, MAX_WORDS, STOP_WORDS, contains_stop_word,
                                 is_emergency_stop, normalized_words, stop_words_in)


@pytest.mark.parametrize("texte", [
    "Stop !",
    "Didier, stop !",
    "Arrête !",
    "Arrête-toi !",
    "Arrête tout de suite !",
    "Stop stop stop",
    "Halte !",
    "Urgence !",
    "Arrêtez !",
    "STOP",
    "Non non non, arrête !",
    # Revue adversariale du 23/10 (I1) : cris de panique qui partaient au LLM
    # (répétitions au-delà de 8 mots, nouvelles formes, interjections).
    "Didier ! Didier ! Arrête ! Arrête ! Arrête-toi tout de suite !",
    "Non non non non non arrête arrête arrête arrête",
    "Arrêtes !",
    "Arrêtes-toi !",
    "Arrêt !",
    "Stoppez !",
    "Freinez !",
    "Halt!",
    "Ah stop !",
    "Hey stop",
    "Ok stop",
    "Euh, stop !",
    "Stop, attends !",
    "Arrête de bouger !",
    " ".join(["stop"] * 9),
])
def test_urgences_reconnues(texte):
    assert is_emergency_stop(texte) is True


@pytest.mark.parametrize("texte", [
    "Arrête de râler",
    "On s'arrête à la boulangerie ?",
    "Tu peux t'arrêter là-bas ?",
    "C'est pas une urgence",
    "",
    "Stoppe la musique",
    "Stop ou encore",
    # Remplissage seul, aucun mot d'arrêt (revue du 23/10, I1) : rien ne part.
    "Attends",
    "Bouge plus",
])
def test_phrases_avec_contexte_laissees_au_llm(texte):
    assert is_emergency_stop(texte) is False


def test_none_n_est_pas_une_urgence():
    assert is_emergency_stop(None) is False


def test_remplissage_seul_n_est_pas_une_urgence():
    # Que des mots de remplissage, aucun mot d'arrêt : rien à arrêter.
    assert is_emergency_stop("Didier, tout de suite !") is False


def test_plafond_de_huit_mots_distincts():
    # Revue adversariale du 23/10 (I1) : le plafond porte sur les mots
    # DISTINCTS — 9 « stop » restent un cri (l'ancien plafond total les
    # refusait) ; 9 mots distincts, même tous tolérés, sont une phrase.
    assert is_emergency_stop(" ".join(["stop"] * 9)) is True
    assert is_emergency_stop(" ".join(["arrête"] * 30)) is True
    assert is_emergency_stop("didier stop arrête toi tout de suite non") is True     # 8
    assert is_emergency_stop("didier stop arrête toi tout de suite non mais") is False  # 9


def test_listes_gravees():
    assert MAX_WORDS == 8
    assert STOP_WORDS == {"stop", "stoppe", "stopper", "arrete", "arretez", "arreter",
                          "halte", "urgence", "freine",
                          "arretes", "arret", "stoppez", "freinez", "halt",
                          "freiner", "stoppes"}
    assert FILLERS == {"didier", "toi", "tout", "de", "suite", "non", "mais", "eh",
                       "he", "oh", "ho", "la", "attention", "s", "il", "te", "plait",
                       "vous", "maintenant",
                       "ah", "hey", "euh", "ok", "attends", "bouge", "bouger", "plus"}


def test_normalisation_accents_et_ponctuation():
    # « Arrêtez, s'il vous plaît ! » : accents retirés, apostrophe = espace.
    assert is_emergency_stop("Arrêtez, s'il vous plaît !") is True
    assert is_emergency_stop("ARRÊTE… MAINTENANT !!!") is True


# --------------------------------------------------------------------------
# contains_stop_word : critère LÂCHE de l'écoute garde (revue du 31/10, I1) —
# la tranche contient l'écho de Didier autour du « Stop ! » de David.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("texte", [
    "Stop !",
    "et puis la boulangerie. Stop ! Je disais donc",   # écho + cri
    "Arrête de râler",                                 # contexte : sens sûr
    "on descend à l'arrêt de bus",                     # Didier lui-même : sens sûr
    "HALTE là",
    "Arrêtez-vous",
])
def test_contains_stop_word_vrai(texte):
    assert contains_stop_word(texte) is True


@pytest.mark.parametrize("texte", [
    None, "", "...", "c'est joli", "on continue tout droit", "stoppeur", "arrêtoir",
])
def test_contains_stop_word_faux(texte):
    assert contains_stop_word(texte) is False


def test_contains_stop_word_ne_change_pas_is_emergency_stop():
    # Le critère strict de l'écoute NORMALE reste celui du 23/10.
    assert is_emergency_stop("et puis la boulangerie. Stop ! Je disais donc") is False


# --------------------------------------------------------------------------
# Seconde revue du 31/10 (mineur 3) : cri allongé et nouvelles formes, pour
# LES DEUX critères.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("texte", ["Stooop !", "Arrrête !", "Stoooooop stop", "Freiner !",
                                   "Stoppes !", "Arrrrêêête-toi !"])
def test_cri_allonge_et_nouvelles_formes(texte):
    assert is_emergency_stop(texte) is True
    assert contains_stop_word(texte) is True


def test_lettres_repetees_ramenees_a_une():
    assert normalized_words("Stooop, Arrrête !") == {"stop", "arete"}
    # Les doubles légitimes restent intacts.
    assert normalized_words("arrête stoppe") == {"arrete", "stoppe"}
    # Collision ASSUMÉE de la forme écrasée (sens sûr, cf. _is_stop).
    assert contains_stop_word("une arête de poisson") is True


def test_stop_words_in_rend_les_formes_normalisees():
    assert stop_words_in("Bon, je m'arrête là, stop.") == {"arrete", "stop"}
    assert stop_words_in("c'est joli") == set()
    assert stop_words_in(None) == set()
