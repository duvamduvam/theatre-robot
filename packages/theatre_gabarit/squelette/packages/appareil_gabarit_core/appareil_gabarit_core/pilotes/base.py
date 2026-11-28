"""Un Protocol par famille de matériel (geste G5) : ce que la logique appelle, rien de plus.

APPAREIL : les méthodes (ex. jouer, arreter, en_cours, sante) ; santé = ok / absent / erreur.
"""
from typing import Protocol


class Pilote(Protocol):
    def sante(self) -> str: ...
