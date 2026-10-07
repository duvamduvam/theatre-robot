"""Journal d'événements JSONL — logique PURE (stdlib), une ligne par événement.

QUOI : le format UNIQUE de la boîte noire (télédiagnostic, étape 2) et de la
salle de répétition simulée (régisseur de pannes) : ce qui a été injecté, dit,
décidé, horodaté deux fois (monotone pour les durées, mural pour l'humain).
POURQUOI un seul format : la frise du débrief et le post-mortem d'incident se
lisent avec le MÊME outil ; un événement de répétition et un événement de rue
sont comparables.

Champs obligatoires : t_mono_ms (int), t_wall (str ISO), source (str), type
(str), payload (dict, peut être vide). Tout manquement = JournalError, jamais
une ligne « à peu près ».
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

REQUIRED = ("t_mono_ms", "t_wall", "source", "type", "payload")


class JournalError(ValueError):
    """Événement invalide — le message dit quel champ."""


@dataclass(frozen=True)
class Event:
    t_mono_ms: int
    t_wall: str
    source: str
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_line(self) -> str:
        # sort_keys : une ligne stable, diffable entre deux séances.
        return json.dumps({
            "t_mono_ms": self.t_mono_ms, "t_wall": self.t_wall, "source": self.source,
            "type": self.type, "payload": self.payload,
        }, sort_keys=True, ensure_ascii=False)


def make_event(t_mono_ms: int, source: str, type_: str, payload: Dict[str, Any] | None = None,
               *, t_wall: str | None = None) -> Event:
    """Construit un événement validé ; t_wall par défaut = maintenant (UTC ISO)."""
    if not isinstance(t_mono_ms, int) or isinstance(t_mono_ms, bool):
        raise JournalError("t_mono_ms : entier attendu")
    if not isinstance(source, str) or not source:
        raise JournalError("source : chaîne non vide attendue")
    if not isinstance(type_, str) or not type_:
        raise JournalError("type : chaîne non vide attendue")
    payload = {} if payload is None else payload
    if not isinstance(payload, dict):
        raise JournalError("payload : dictionnaire attendu")
    if t_wall is None:
        t_wall = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    return Event(t_mono_ms, t_wall, source, type_, payload)


def parse_line(line: str) -> Event:
    """Ligne JSONL -> Event validé (champs obligatoires présents et typés)."""
    try:
        data = json.loads(line)
    except ValueError as e:
        raise JournalError(f"ligne illisible : {e}") from e
    if not isinstance(data, dict):
        raise JournalError("ligne : objet JSON attendu")
    for key in REQUIRED:
        if key not in data:
            raise JournalError(f"champ obligatoire manquant : {key}")
    return make_event(data["t_mono_ms"], data["source"], data["type"], data["payload"],
                      t_wall=str(data["t_wall"]))


def parse_lines(lines: Iterable[str]) -> List[Event]:
    """Lecture d'un journal entier ; impose l'ordre MONOTONE (un journal
    désordonné est un journal corrompu, on le dit plutôt que de le trier)."""
    events: List[Event] = []
    last = None
    for n, raw in enumerate(lines, 1):
        raw = raw.strip()
        if not raw:
            continue
        ev = parse_line(raw)
        if last is not None and ev.t_mono_ms < last:
            raise JournalError(f"ligne {n} : t_mono_ms {ev.t_mono_ms} < précédent {last}")
        last = ev.t_mono_ms
        events.append(ev)
    return events
