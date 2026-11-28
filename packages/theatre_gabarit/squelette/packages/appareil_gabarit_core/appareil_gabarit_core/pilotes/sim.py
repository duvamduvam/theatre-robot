"""Pilote `sim` (geste G5) : état en mémoire, stdlib, horloge injectée. Domaine 43 seulement
(theatre_gabarit.pilotes.choisir refuse ailleurs). APPAREIL : l'état simulé de chaque organe."""


class PiloteSim:
    def sante(self):
        return "ok"


def fabrique():
    return PiloteSim()
