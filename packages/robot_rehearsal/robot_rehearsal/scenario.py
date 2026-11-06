"""Scénario de pannes — logique PURE : lecture + VALIDATION (refus explicite)
d'un YAML déjà chargé, puis expansion des instants « random » avec une GRAINE
(timeline déterministe : même graine = même séance, rejouable).

Format :
  name: str ; seed: int (optionnel, défaut 0) ; duration_s: float > 0
  faults:
    - {id?: str, type: relay|pause|kill|speed|instruction|lubie|chat,
       t: float|"random"|"poi", duration_s: float >= 0, ...params selon le type}
Déclencheur POI (lot R3) : `t: poi` + `poi: <nom>` -> l'élément part sur
l'événement « enter » de ce POI (Fault.t_s = None, Fault.trigger_poi = nom),
au plus une fois. `p` (0..1, défaut 1) le TIRE AU CHARGEMENT avec la graine :
gardé (Scenario.faults) ou écarté une fois pour toutes (Scenario.undrawn).
`p` n'est accepté qu'avec `t: poi` — le `p` d'un relay drop est autre chose
(sa probabilité de drop), et les deux ensemble sont refusés (ambigu).
Params par type (tout le reste est refusé) :
  relay       : relay (∈ RELAYS), op (∈ RELAY_OPS), p (drop, 0..1), delay_ms (delay, >0)
  pause       : process (∈ PAUSABLE)
  kill        : process (∈ KILLABLE), reenable (bool, défaut true : renvoie
                `route on` après le respawn — le « reboot » reprend la route)
  speed       : value (0..1) — à la fin, la vitesse EN VIGUEUR est rendue
                (dernière consigne externe, sinon `speed` du launch) ; restore
                (0..1, défaut 1.0) n'est plus que le dernier recours
  instruction : text (str non vide) ; avec duration_s > 0, levée ("") à la fin
  lubie       : poi (str), text (str non vide, optionnel : sinon le champ
                `lubie` du POI dans l'itinéraire), stop (bool, défaut true :
                route_speed 0), restore (0..1, défaut 1.0 : dernier recours,
                comme pour speed)
  chat        : op (∈ CHAT_FAULT_OPS sauf pass), params (dict, validé par op) :
                delay -> delay_ms (entier >= 1) ; garble -> texts (liste de str,
                optionnelle) ; phantom -> text (str, PONCTUELLE, cible
                `chat:phantom`) ; deaf/mute -> rien. Hors phantom, duration_s > 0
                OBLIGATOIRE (0 = plafond 60 s côté chat_node, pas « ponctuel »)
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Tuple

from robot_rehearsal.contracts import (CHAT_FAULT_OPS, FAULT_MAX_DURATION_S, KILLABLE, PAUSABLE,
                                       RELAYS, RELAY_OPS)


class ScenarioError(ValueError):
    """Scénario invalide — le message dit QUOI et OÙ (faults[i].clé)."""


@dataclass(frozen=True)
class Fault:
    id: str
    type: str
    t_s: float | None   # instant de début (après expansion) ; None = déclenchée par un POI
    duration_s: float   # 0 = ponctuelle
    params: Dict[str, Any]
    target: str         # clé d'exclusion : deux pannes sur la même cible ne se chevauchent pas
    trigger_poi: str | None = None   # t: poi -> nom du POI dont l'« enter » la déclenche
    # Probabilité de tirage d'un déclencheur POI — DÉJÀ tirée au chargement,
    # gardée pour le journal seulement (ne pas confondre avec params["p"] d'un relay drop).
    draw_p: float = 1.0


@dataclass(frozen=True)
class Scenario:
    name: str
    seed: int
    duration_s: float
    # Temporelles triées par (t_s, id), PUIS déclencheurs POI triés par (poi, id).
    faults: Tuple[Fault, ...]
    # ids des déclencheurs POI écartés par le tirage (ordre du fichier) : le
    # journal dit ce qui n'a PAS été tiré, David ne le voit pas.
    undrawn: Tuple[str, ...] = ()


def _num(v, where, *, lo=None, hi=None) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ScenarioError(f"{where} : nombre fini attendu, reçu {v!r}")
    if lo is not None and v < lo:
        raise ScenarioError(f"{where} : >= {lo} attendu, reçu {v}")
    if hi is not None and v > hi:
        raise ScenarioError(f"{where} : <= {hi} attendu, reçu {v}")
    return float(v)


def _chat_params(op: str, raw, where: str) -> Dict[str, Any]:
    """Params d'une panne chat, validés PAR OP. Clés inconnues refusées : ce
    JSON part à chat_node (dépôt vision), qui ignorerait sans bruit une clé
    mal orthographiée (`delay` pour `delay_ms`) — la panne ne jouerait pas."""
    raw = {} if raw is None else raw
    if not isinstance(raw, dict):
        raise ScenarioError(f"{where} : dictionnaire attendu")
    allowed = {"delay": {"delay_ms"}, "garble": {"texts"}, "phantom": {"text"},
               "deaf": set(), "mute": set()}[op]
    extra = set(raw) - allowed
    if extra:
        raise ScenarioError(f"{where} : clés inconnues {sorted(extra)} pour op {op}")
    out: Dict[str, Any] = {}
    if op == "delay":
        d = raw.get("delay_ms")
        if isinstance(d, bool) or not isinstance(d, int) or d < 1:
            raise ScenarioError(f"{where}.delay_ms : entier >= 1 attendu, reçu {d!r}")
        out["delay_ms"] = d
    elif op == "garble" and "texts" in raw:
        texts = raw["texts"]
        if (not isinstance(texts, list) or not texts
                or not all(isinstance(x, str) and x.strip() for x in texts)):
            raise ScenarioError(f"{where}.texts : liste non vide de chaînes non vides attendue")
        out["texts"] = list(texts)
    elif op == "phantom":
        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ScenarioError(f"{where}.text : chaîne non vide attendue (énoncé fantôme)")
        out["text"] = text
    return out


def _validate_params(ftype: str, raw: dict, where: str, trigger_keys: set) -> Tuple[Dict[str, Any], str]:
    """-> (params validés, cible d'exclusion). `trigger_keys` : clés du
    déclencheur POI (poi, p), validées à part par _trigger."""
    known = {"id", "type", "t", "duration_s"} | trigger_keys
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
    elif ftype == "lubie":
        poi = raw.get("poi")
        if not isinstance(poi, str) or not poi:
            raise ScenarioError(f"{where}.poi : nom de POI non vide attendu")
        # Absent = le champ `lubie` du POI dans l'itinéraire (résolu par le
        # node). Vide est refusé : "" publié voudrait dire « consigne levée ».
        text = raw.get("text")
        if text is not None and (not isinstance(text, str) or not text.strip()):
            raise ScenarioError(f"{where}.text : chaîne non vide attendue (ou absente : lubie du POI)")
        stop = raw.get("stop", True)
        if not isinstance(stop, bool):
            raise ScenarioError(f"{where}.stop : booléen attendu")
        params = {"poi": poi, "text": text, "stop": stop,
                  "restore": _num(raw.get("restore", 1.0), f"{where}.restore", lo=0.0, hi=1.0)}
        known |= {"poi", "text", "stop", "restore"}
        # Cible « speed » (étude §13.4) : la lubie arrête Didier par route_speed ;
        # une batterie faible au même moment se marcherait dessus -> sautée.
        target = "speed"
    elif ftype == "chat":
        op = raw.get("op")
        if op not in CHAT_FAULT_OPS or op == "pass":
            raise ScenarioError(f"{where}.op : attendu parmi {[o for o in CHAT_FAULT_OPS if o != 'pass']}, reçu {op!r}")
        params = {"op": op, "params": _chat_params(op, raw.get("params"), f"{where}.params")}
        known |= {"op", "params"}
        # phantom a SA cible : ponctuel (un énoncé servi une fois), il ne doit
        # ni être sauté parce qu'un garble/deaf occupe `chat`, ni en bloquer un.
        target = "chat:phantom" if op == "phantom" else "chat"
    else:
        raise ScenarioError(f"{where}.type : attendu parmi {sorted(FAULT_MAX_DURATION_S)}, reçu {ftype!r}")
    extra = set(raw) - known
    if extra:
        raise ScenarioError(f"{where} : clés inconnues {sorted(extra)}")
    return params, target


def _trigger(ftype: str, raw: dict, where: str) -> Tuple[str | None, float]:
    """-> (POI déclencheur, probabilité de tirage) ; (None, 1.0) hors `t: poi`."""
    if raw.get("t") != "poi":
        # Le `p` d'un relay est sa probabilité de DROP (params), pas un tirage.
        if "p" in raw and ftype != "relay":
            raise ScenarioError(f"{where}.p : tirage au chargement réservé aux déclencheurs « t: poi »")
        return None, 1.0
    poi = raw.get("poi")
    if not isinstance(poi, str) or not poi:
        raise ScenarioError(f"{where}.poi : nom de POI non vide attendu avec « t: poi »")
    if ftype == "relay" and "p" in raw:
        # Probabilité de drop OU de tirage ? On refuse plutôt que de deviner.
        raise ScenarioError(f"{where}.p : ambigu sur un relay déclenché par POI (drop ou tirage ?), refusé")
    return poi, _num(raw.get("p", 1.0), f"{where}.p", lo=0.0, hi=1.0)


def _check_poi_refs(ftype: str, params: dict, trigger_poi: str | None,
                    pois: Mapping[str, str], where: str) -> None:
    """Références à l'itinéraire (nom de POI -> texte de sa lubie). Vérifiées
    pour TOUS les éléments, tirés ou non : un scénario ne doit pas être
    accepté avec une graine et refusé avec une autre."""
    if trigger_poi is not None and trigger_poi not in pois:
        raise ScenarioError(f"{where}.poi : POI « {trigger_poi} » absent de l'itinéraire")
    if ftype == "lubie":
        poi = params["poi"]
        if poi not in pois:
            raise ScenarioError(f"{where}.poi : POI « {poi} » absent de l'itinéraire")
        if params["text"] is None and not pois[poi].strip():
            raise ScenarioError(f"{where}.text : absent, et le POI « {poi} » n'a pas de champ lubie")


def load_scenario(data: dict, *, seed: int | None = None,
                  pois: Mapping[str, str] | None = None) -> Scenario:
    """dict -> Scenario validé et EXPANSÉ (les t: random sont tirés avec la
    graine ; `seed` en argument écrase celle du fichier — pour rejouer).
    `pois` (nom -> lubie, depuis l'itinéraire) : si fourni, chaque POI
    référencé (déclencheur, lubie) doit y exister, et une lubie sans `text`
    doit y trouver un texte. None = pas de vérification (tests, contrats)."""
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
    triggers: List[Fault] = []   # déclencheurs POI, tirés APRÈS la boucle
    ids = set()
    for i, raw in enumerate(raw_faults):
        where = f"faults[{i}]"
        if not isinstance(raw, dict):
            raise ScenarioError(f"{where} : dictionnaire attendu")
        ftype = raw.get("type")
        by_poi = raw.get("t") == "poi"
        # Déclencheur d'abord : un `p` hors `t: poi` reçoit SON message, pas
        # un « clés inconnues » qui ne dirait pas pourquoi.
        trigger_poi, draw_p = _trigger(str(ftype), raw, where)
        params, target = _validate_params(str(ftype), raw, where, {"poi", "p"} if by_poi else set())
        if pois is not None:
            _check_poi_refs(str(ftype), params, trigger_poi, pois, where)
        max_d = FAULT_MAX_DURATION_S[ftype]
        d = _num(raw.get("duration_s", 0.0), f"{where}.duration_s", lo=0.0)
        if max_d == 0.0 and d != 0.0:
            raise ScenarioError(f"{where}.duration_s : panne ponctuelle ({ftype}), 0 attendu")
        if ftype == "chat" and params["op"] == "phantom" and d != 0.0:
            # Un énoncé fantôme est servi une fois : une durée ne voudrait rien dire.
            raise ScenarioError(f"{where}.duration_s : panne ponctuelle (chat phantom), 0 attendu")
        if ftype == "chat" and params["op"] != "phantom" and d == 0.0:
            # chat_node lit until_ms 0 comme « son plafond local de 60 s », pas
            # comme ponctuel : un 0 oublié jouerait une minute de panne.
            raise ScenarioError(f"{where}.duration_s : 0 refusé pour chat {params['op']} "
                                "(chat_node le lirait comme son plafond de 60 s), durée > 0 attendue")
        if d > max_d:
            raise ScenarioError(f"{where}.duration_s : {d} > maximum {max_d} pour {ftype}")
        t_raw = raw.get("t")
        if by_poi:
            t = None
        elif t_raw == "random":
            # Tirage déterministe, dans l'ordre du fichier : la graine fixe tout.
            t = round(rng.uniform(0.0, max(0.0, duration - d)), 3)
        else:
            t = round(_num(t_raw, f"{where}.t", lo=0.0, hi=duration), 3)
        fid = raw.get("id", f"f{i}")
        if not isinstance(fid, str) or not fid:
            raise ScenarioError(f"{where}.id : chaîne non vide attendue")
        if fid in ids:
            raise ScenarioError(f"{where}.id : identifiant en double « {fid} »")
        ids.add(fid)
        fault = Fault(fid, str(ftype), t, d, params, target, trigger_poi, draw_p)
        (triggers if by_poi else faults).append(fault)

    # Tirage des déclencheurs POI APRÈS toutes les expansions `random`, dans
    # l'ordre du fichier : ajouter une lubie ne décale aucun instant tiré (les
    # timelines R2 restent identiques). Chaque déclencheur consomme UN tirage,
    # même à p = 1 : changer un p ne décale pas les tirages des suivants.
    # Revers assumé : ajouter un `t: random` décale les tirages POI.
    kept: List[Fault] = []
    undrawn: List[str] = []
    for f in triggers:
        if rng.random() < f.draw_p:
            kept.append(f)
        else:
            undrawn.append(f.id)

    faults.sort(key=lambda f: (f.t_s, f.id))
    kept.sort(key=lambda f: (f.trigger_poi, f.id))
    return Scenario(name=name, seed=seed, duration_s=duration, faults=tuple(faults + kept),
                    undrawn=tuple(undrawn))
