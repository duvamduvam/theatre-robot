"""Journal du sélecteur — RÉUTILISE robot/diagnostic/journal.py (format boîte
noire : t_mono_ms, t_wall, source, type, payload), pas de copie.

Ajout propre au jeu (porte T6) : chaque ligne porte un `pourquoi` NON VIDE —
refusé à l'écriture sinon (JournalError), jamais une ligne muette.
Fichier : <dossier>/<horodatage>_<pid>_jeu.jsonl, un par démarrage (contrat
JournalWriter : t_mono_ms repart de zéro à chaque boot).
"""
import os
import pathlib
from datetime import datetime

from robot.diagnostic.journal import JournalError, JournalWriter, make_event

SOURCE = "didier_jeu"


def evenement(t_mono_ms: int, type_: str, payload: dict):
    pourquoi = payload.get("pourquoi") if isinstance(payload, dict) else None
    if not isinstance(pourquoi, str) or not pourquoi.strip():
        raise JournalError(f"{type_} : `pourquoi` non vide obligatoire (porte T6)")
    return make_event(t_mono_ms, SOURCE, type_, payload)


class Journal:
    """Écrit les lignes du sélecteur ; ecrire() rend la ligne JSONL (publiée
    aussi sur jeu/journal pour la page scène)."""

    def __init__(self, dossier, maintenant=None):
        maintenant = maintenant or datetime.now()
        pathlib.Path(dossier).mkdir(parents=True, exist_ok=True)
        self.chemin = pathlib.Path(dossier) / f"{maintenant:%Y%m%d-%H%M%S}_{os.getpid()}_jeu.jsonl"
        self._fichier = open(self.chemin, "a", encoding="utf-8")
        self._writer = JournalWriter(self._fichier)

    def ecrire(self, t_mono_ms: int, type_: str, payload: dict) -> str:
        ev = evenement(t_mono_ms, type_, payload)
        self._writer.append(ev)
        return ev.to_line()

    def fermer(self) -> None:
        self._fichier.close()
