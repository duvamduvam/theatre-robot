"""Tickets « Noter un problème » de la page scène — logique PURE (stdlib seule).

QUOI : ce que le pont web écrit quand David clique « Ticket » : son texte, l'heure, le
domaine (sim/robot) et l'instantané des topics VISIBLES à cet instant (route_state,
chat_state, jeu/intention… — jamais les topics masqués : `snapshot_visible` est appliqué
par l'appelant, un ticket ne doit pas trahir le tirage de la répétition).
POURQUOI un fichier par ticket, en JSON, dans le dossier de log du conteneur : le pont
n'a pas à connaître le reste de la chaîne. Le RAMASSEUR du PC
(legacy/dadou_robot_ros/conf/scripts/ramasser_traces.py) lit ces fichiers, y joint les
journaux de l'instant et les range dans traces/tickets/ — là où vivent aussi les tickets
qu'il ouvre lui-même sur les erreurs détectées. Une seule boîte, deux origines.

Horloge injectée (`now_s`, `t_wall`) : testable sans attendre ni patcher time.
"""
from __future__ import annotations

import re

# Anti-rafale : un double-clic ou une page boguée ne remplit pas le disque. 2 s suffisent
# à écarter le doublon sans gêner deux tickets voulus d'affilée.
INTERVALLE_MIN_S = 2.0

_NON_CHIFFRE = re.compile(r"[^0-9]+")


def nom_fichier(t_wall: str, numero: int) -> str:
    """`2026-11-08T16:50:03.123+00:00`, 7 → `20261108-165003-007.json`.
    Le numéro (compteur du pont) départage deux tickets de la même seconde ; trié par
    nom = trié par heure, c'est ce que lit le ramasseur."""
    chiffres = _NON_CHIFFRE.sub("", t_wall)[:14]  # AAAAMMJJhhmmss
    return "{}-{}-{:03d}.json".format(chiffres[:8], chiffres[8:14], numero % 1000)


def construire_ticket(texte: str, t_wall: str, domain_id: int, mode: str,
                      topics_visibles: dict) -> dict:
    """Le contenu du fichier. `origine` = page : le ramasseur distingue ainsi le ticket
    de David (toujours ouvert, jamais dédoublonné) du ticket qu'il détecte lui-même."""
    return {
        "origine": "page",
        "t_wall": t_wall,
        "domain_id": domain_id,
        "mode": mode,
        "texte": texte,
        "topics": topics_visibles,
    }


class PareRafale:
    """Refuse un ticket arrivé moins de INTERVALLE_MIN_S après le précédent accepté."""

    def __init__(self, intervalle_s: float = INTERVALLE_MIN_S):
        self.intervalle_s = intervalle_s
        self._dernier_s = None
        self.compteur = 0

    def admettre(self, now_s: float) -> bool:
        if self._dernier_s is not None and now_s - self._dernier_s < self.intervalle_s:
            return False
        self._dernier_s = now_s
        self.compteur += 1
        return True
