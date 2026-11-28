"""Pilote `materiel` (geste G5) : importe ses bibliothèques À L'APPEL (le module s'importe sur le
PC). Matériel absent : santé `absent`, jamais d'exception (le nœud reste vivant).
APPAREIL : le matériel et son câblage (README § Pilotes)."""


class PiloteMateriel:
    def sante(self):
        return "absent"


def fabrique():
    return PiloteMateriel()
