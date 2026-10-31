"""Arrêt d'urgence vocal DÉTERMINISTE (lot N1/P1, 2026-10-23).

QUOI : is_emergency_stop(texte) dit si un énoncé compris par Didier est un
       ordre d'arrêt d'URGENCE (« Stop ! », « Didier, arrête ! »). Branché par
       ConversationEngine AVANT l'appel LLM : l'intention "stop" part sur
       rehearsal/chat_move dès la fin du STT, sans attendre la génération de
       la réplique (le chemin LLM, clé "marche" du JSON de FIN, mettait
       ~1,5-2 s de plus — dadou_robot_ros/docs/etude-niveaux-reflexion.md §1).
POURQUOI des mots-clés et pas le LLM : décision de David du 23/10 (étude
       §10, point 3) — mots-clés pour l'URGENCE SEULEMENT. Règle stricte :
       l'énoncé ne doit contenir QUE des mots d'arrêt et des mots de
       remplissage (« Didier », « tout de suite », « non non »…). Dès qu'un
       autre mot apparaît (« arrête de râler », « on s'arrête à la
       boulangerie ? »), la phrase a un contexte : elle part au LLM, qui le
       comprend. Faux positif bénin (Didier s'arrête, il le joue) contre faux
       négatif grave (il ne s'arrête pas) : la liste vise QUE l'arrêt, jamais
       un mot qui met en mouvement.
POURQUOI ce n'est PAS un arrêt de sécurité : il ne touche que le régisseur
       (intention), jamais la chaîne roues. Le deadman, la télécommande et
       l'e_stop restent les arrêts effectifs (étude §7).
Module PUR (stdlib seule) : testé en CI sans ROS (test_emergency.py).
"""
from __future__ import annotations

import unicodedata
from typing import Optional

# Formes d'arrêt, normalisées (minuscules, SANS accents) : « arrête »,
# « arrêtez », « arrêter » deviennent arrete/arretez/arreter.
# Revue adversariale du 23/10 (I1) : « Arrêtes ! » (faute courante du STT),
# « Arrêt ! », « Stoppez ! », « Freinez ! », « Halt! » n'arrêtaient pas Didier.
STOP_WORDS = frozenset({"stop", "stoppe", "stopper", "arrete", "arretez", "arreter",
                        "halte", "urgence", "freine",
                        "arretes", "arret", "stoppez", "freinez", "halt"})

# Mots tolérés AUTOUR d'un mot d'arrêt sans changer le sens d'urgence.
# « s », « te » : restes de l'élision (« s'il te plaît » -> s il te plait).
# Ne JAMAIS y mettre un mot porteur de sens (« de » seul est sûr : « arrête
# de râler » tombe sur « raler », hors liste).
# Revue adversariale du 23/10 (I1) : interjections de panique (« Ah stop ! »,
# « Euh, stop ! », « Stop, attends ! ») et « Arrête de bouger ! » partaient au
# LLM. « bouge »/« bouger »/« plus » sont sûrs : sans mot d'arrêt (« Bouge
# plus »), rien ne part ; « ne t'arrête plus » tombe sur « ne », hors liste.
FILLERS = frozenset({"didier", "toi", "tout", "de", "suite", "non", "mais", "eh",
                     "he", "oh", "ho", "la", "attention", "s", "il", "te", "plait", "vous",
                     "maintenant",
                     "ah", "hey", "euh", "ok", "attends", "bouge", "bouger", "plus"})

# Plafond de mots DISTINCTS : au-delà, ce n'est plus un cri, c'est une phrase
# (elle part au LLM). Revue adversariale du 23/10 (I1) : le plafond portait
# sur le nombre TOTAL de mots — « Non non non non non arrête arrête arrête
# arrête » (9 mots, 2 distincts) n'arrêtait pas Didier ; la répétition est
# justement la forme de la panique.
MAX_WORDS = 8


def _words(text: str) -> list:
    """Mots normalisés : minuscules, accents retirés (NFD puis suppression
    des marques combinantes Mn), tout ce qui n'est pas une lettre devient
    un espace (ponctuation, tirets d'« arrête-toi », apostrophes, chiffres)."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    letters = "".join(" " if not ch.isalpha() else ch
                      for ch in decomposed if unicodedata.category(ch) != "Mn")
    return letters.split()


def is_emergency_stop(text: Optional[str]) -> bool:
    """Vrai SSI au moins un mot de STOP_WORDS, TOUS les mots dans
    STOP_WORDS ∪ FILLERS, et au plus MAX_WORDS mots DISTINCTS (les
    répétitions ne comptent pas). Jamais d'exception (None ou vide -> False)."""
    words = _words(text or "")
    if not words or len(set(words)) > MAX_WORDS:
        return False
    return (any(word in STOP_WORDS for word in words)
            and all(word in STOP_WORDS or word in FILLERS for word in words))


def contains_stop_word(text: Optional[str]) -> bool:
    """Vrai si AU MOINS un mot de STOP_WORDS apparaît, où que ce soit dans
    le texte (même normalisation que is_emergency_stop). Critère LÂCHE,
    réservé à l'écoute GARDE pendant une réplique (vision.ai.conversation,
    revue du 31/10, I1) : la tranche captée contient aussi l'ÉCHO de Didier
    (« … la boulangerie. Stop ! Je disais… »), que is_emergency_stop refuse à
    raison (autres mots = phrase avec contexte). Ici, pas de LLM derrière pour
    comprendre le contexte : on s'arrête. Faux positifs ASSUMÉS, sens sûr :
    Didier qui dit lui-même « arrête » ou « l'arrêt de bus », David qui dit
    « arrête de râler » — Didier se tait et s'arrête. L'écoute NORMALE garde
    is_emergency_stop (règle stricte du 23/10). Jamais d'exception."""
    return any(word in STOP_WORDS for word in _words(text or ""))
