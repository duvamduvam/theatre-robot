"""Contrat commun des actions pilotées par les nodes ROS.

Avant ce contrat, update()/process() n'étaient qu'une convention de nommage :
chaque classe réinventait sa signature et son retour, et deux classes-mères
rivales ont coexisté (l'une est morte au nettoyage de 2026-07-11). Ici le
contrat est STRUCTUREL : une action qui ne l'implémente pas ne s'instancie pas.
"""
from abc import ABC, abstractmethod


class Action(ABC):

    @abstractmethod
    def update(self, msg):
        """Traite un message entrant ({action_type: valeur, DURATION?, ANIMATION?}).

        Retour : dict d'événements à publier, ou None/msg (ignoré par tous les
        nodes SAUF animations_node, qui republie les événements de son
        AnimationManager vers les topics par piste)."""

    @abstractmethod
    def process(self):
        """Tick périodique (10 Hz). Même convention de retour qu'update()."""
