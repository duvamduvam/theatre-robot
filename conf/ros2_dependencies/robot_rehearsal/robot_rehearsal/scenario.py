"""Scénario de pannes — logique PURE : lecture + VALIDATION (refus explicite)
d'un YAML déjà chargé, puis expansion des instants « random » avec une GRAINE
(timeline déterministe : même graine = même séance, rejouable).

Format :
  name: str ; seed: int (optionnel, défaut 0) ; duration_s: float > 0
  faults:
    - {id?: str, type: relay|pause|kill|speed|instruction, t: float|"random",
       duration_s: float >= 0, ...params selon le type}
Params par type (tout le reste est refusé) :
  relay       : relay (∈ RELAYS), op (∈ RELAY_OPS), p (drop, 0..1), delay_ms (delay, >0)
  pause       : process (∈ PAUSABLE)
  kill        : process (∈ KILLABLE), reenable (bool, défaut true : renvoie
                `route on` après le respawn — le « reboot » reprend la route)
  speed       : value (0..1) — rétabli à restore (0..1, défaut 1.0) à la fin
  instruction : text (str non vide)
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from robot_rehearsal.contracts import (FAULT_MAX_DURATION_S, KILLABLE, PAUSABLE, RELAYS,
                                       RELAY_OPS)


class ScenarioError(ValueError):
    """Scénario invalide — le message dit QUOI et OÙ (faults[i].clé)."""


@dataclass(frozen=True)
class Fault:
    id: str
    type: str
    t_s: float          # instant de début (après expansion)
    duration_s: float   # 0 = ponctuelle
    params: Dict[str, Any]
    target: str         # clé d'exclusion : deux pannes sur la même cible ne se chevauchent pas


@dataclass(frozen=True)
class Scenario:
    name: str
    seed: int
    duration_s: float
    faults: Tuple[Fault, ...]   # triées par t_s puis id (ordre déterministe)


def _num(v, where, *, lo=None, hi=None) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ScenarioError(f"{where} : nombre fini attendu, reçu {v!r}")
    if lo is not None and v < lo:
        raise ScenarioError(f"{where} : >= {lo} attendu, reçu {v}")
    if hi is not None and v > hi:
        raise ScenarioError(f"{where} : <= {hi} attendu, reçu {v}")
    return float(v)


def _validate_params(ftype: str, raw: dict, where: str) -> Tuple[Dict[str, Any], str]:
    """-> (params validés, cible d'exclusion)."""
    known = {"id", "type", "t", "duration_s"}
    if ftype == "relay":
        relay = raw.get("relay")
        if relay not in RELAYS:
            raise ScenarioError(f"{where}.relay : attendu parmi {sorted(RELAYS)}, reçu {relay!r}")
        op = raw.get("op")
        if op not in RELAY_OPS or op == "pass":
            raise ScenarioError(f"{where}.op : attendu parmi {[o for o in RELAY_OPS if o != 'pass']}, reçu {op!r}")
        params: Dict[str, Any] = {"relay": relay, "op": op}
        if op == "drop":
            params["p"] = _num(raw.get("p", 1.0), f"{where}.p", lo=0.0, hi=1.0)
        if op == "delay":
            params["delay_ms"] = int(_num(raw.get("delay_ms"), f"{where}.delay_ms", lo=1))
        known |= {"relay", "op", "p", "delay_ms"}
        target = f"relay:{relay}"
    elif ftype == "pause":
        proc = raw.get("process")
        if proc not in PAUSABLE:
            raise ScenarioError(f"{where}.process : attendu parmi {list(PAUSABLE)}, reçu {proc!r}")
        params = {"process": proc}; known |= {"process"}; target = f"process:{proc}"
    elif ftype == "kill":
        proc = raw.get("process")
        if proc not in KILLABLE:
            raise ScenarioError(f"{where}.process : attendu parmi {list(KILLABLE)}, reçu {proc!r}")
        reenable = raw.get("reenable", True)
        if not isinstance(reenable, bool):
            raise ScenarioError(f"{where}.reenable : booléen attendu")
        params = {"process": proc, "reenable": reenable}; known |= {"process", "reenable"}
        target = f"process:{proc}"
    elif ftype == "speed":
        params = {"value": _num(raw.get("value"), f"{where}.value", lo=0.0, hi=1.0),
                  "restore": _num(raw.get("restore", 1.0), f"{where}.restore", lo=0.0, hi=1.0)}
        known |= {"value", "restore"}; target = "speed"
    elif ftype == "instruction":
        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ScenarioError(f"{where}.text : chaîne non vide attendue")
        params = {"text": text}; known |= {"text"}; target = "instruction"
    else:
        raise ScenarioError(f"{where}.type : attendu parmi {sorted(FAULT_MAX_DURATION_S)}, reçu {ftype!r}")
    extra = set(raw) - known
    if extra:
        raise ScenarioError(f"{where} : clés inconnues {sorted(extra)}")
    return params, target


def load_scenario(data: dict, *, seed: int | None = None) -> Scenario:
    """dict -> Scenario validé et EXPANSÉ (les t: random sont tirés avec la
    graine ; `seed` en argument écrase celle du fichier — pour rejouer)."""
    if not isinstance(data, dict):
        raise ScenarioError("scénario : dictionnaire attendu à la racine")
    name = data.get("name")
    if not isinstance(name, str) or not name:
        raise ScenarioError("name : chaîne non vide attendue")
    file_seed = data.get("seed", 0)
    if isinstance(file_seed, bool) or not isinstance(file_seed, int):
        raise ScenarioError("seed : entier attendu")
    seed = file_seed if seed is None else int(seed)
    duration = _num(data.get("duration_s"), "duration_s", lo=1.0)
    raw_faults = data.get("faults", [])
    if not isinstance(raw_faults, list):
        raise ScenarioError("faults : liste attendue")

    rng = random.Random(seed)
    faults: List[Fault] = []
    ids = set()
    for i, raw in enumerate(raw_faults):
        where = f"faults[{i}]"
        if not isinstance(raw, dict):
            raise ScenarioError(f"{where} : dictionnaire attendu")
        ftype = raw.get("type")
        params, target = _validate_params(str(ftype), raw, where)
        max_d = FAULT_MAX_DURATION_S[ftype]
        d = _num(raw.get("duration_s", 0.0), f"{where}.duration_s", lo=0.0)
        if max_d == 0.0 and d != 0.0:
            raise ScenarioError(f"{where}.duration_s : panne ponctuelle ({ftype}), 0 attendu")
        if d > max_d:
            raise ScenarioError(f"{where}.duration_s : {d} > maximum {max_d} pour {ftype}")
        t_raw = raw.get("t")
        if t_raw == "random":
            # Tirage déterministe, dans l'ordre du fichier : la graine fixe tout.
            t = rng.uniform(0.0, max(0.0, duration - d))
        else:
            t = _num(t_raw, f"{where}.t", lo=0.0, hi=duration)
        fid = raw.get("id", f"f{i}")
        if not isinstance(fid, str) or not fid:
            raise ScenarioError(f"{where}.id : chaîne non vide attendue")
        if fid in ids:
            raise ScenarioError(f"{where}.id : identifiant en double « {fid} »")
        ids.add(fid)
        faults.append(Fault(fid, str(ftype), round(t, 3), d, params, target))

    faults.sort(key=lambda f: (f.t_s, f.id))
    return Scenario(name=name, seed=seed, duration_s=duration, faults=tuple(faults))
