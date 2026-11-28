"""Règles PURES de l'appareil (geste G4) : stdlib, horloge passée en argument, pilotes injectés.

Le nœud (noeud.py) appelle `etat(t_ms)`, `repos()`, `tic(t_ms)` et une méthode par topic
d'ordre ; il ne décide rien. APPAREIL : écrire les règles du README (§ Comportement).
"""


class Logique:
    def __init__(self, pilote, reglages):
        self.pilote = pilote
        self.reglages = reglages

    def etat(self, t_ms):
        """(organes, refus) de l'enveloppe d'état (theatre_contrats.appareils)."""
        return [], None

    def repos(self):
        """Tous les pilotes au repos (démarrage, arrêt, exception)."""

    def tic(self, t_ms):
        """Appelé à 20 Hz : fins de lecture, fins d'impulsion…"""
