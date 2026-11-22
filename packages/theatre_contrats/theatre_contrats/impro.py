"""Contrat de l'IMPROVISATION (lot I0, 22/11) — STOP IMPRO, propositions du scénariste, répertoire.

Étude : docs/etudes/etude-improvisation.md §3.2 (la boucle scénariste -> sélecteur) et §4.1
(STOP IMPRO). Quatre topics StringTime (noms dans topics.py) :

| topic                | QoS      | écrivain                 | payload                                      |
|----------------------|----------|--------------------------|----------------------------------------------|
| `jeu/impro`          | volatile | page scène, télécommande | "on" | "off" (JSON ou brut)                  |
| `jeu/impro_state`    | latché   | le sélecteur SEUL        | {"impro", "cause", "t_ms"}                   |
| `jeu/proposition`    | volatile | la réflexion             | {"quoi", "cible", "pourquoi"}                |
| `jeu/repertoire`     | latché   | le sélecteur SEUL        | [{"id", "genre", "desc", "dispo", "dans_s"}] |

Même forme que `route` / `route_state` : la COMMANDE est un geste, l'ÉTAT est la vérité, la page
n'affiche que l'état. La commande est volatile : un sélecteur relancé ne doit jamais relire un
« on » périmé (option écartée au §4.1).

Règle des décodeurs : le payload vient d'un autre processus (et, pour la proposition, d'un LLM).
Ils ne lèvent JAMAIS ; un payload illisible rend None (commande, état, proposition) ou une liste
sans les entrées fautives (répertoire). Le sens sûr est celui de l'appelant : un état d'impro
illisible se lit OFF (`impro_allumee`). Les encodeurs, eux, lèvent ValueError : c'est le code du
dépôt qui se trompe, pas le fil.

Python PUR, stdlib seulement.
"""
import json
import math
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence

ON = "on"
OFF = "off"
ETATS = (ON, OFF)
# Pourquoi l'impro est dans son état (§4.1) : démarrage (toujours OFF), commande de David,
# STOP CONTENUS, plus de battement de superviseur depuis 3 s, arrêt d'urgence.
CAUSES = ("demarrage", "cmd", "stop_contenus", "sans_superviseur", "e_stop")

# Genres d'une entrée du répertoire jouable (§3.2).
GENRES = ("bug", "lubie", "expression", "regard")
# Le répertoire envoyé au scénariste : une douzaine de lignes au plus (§3.4, coût LLM).
REPERTOIRE_MAX = 12

# Bornes des textes du fil (le scénariste est un LLM : un texte trop long est tronqué, jamais
# refusé — la proposition reste lisible).
ID_MAX_CHARS = 64
POURQUOI_MAX_CHARS = 120
DESC_MAX_CHARS = 80
# Au-delà, un délai du répertoire est absurde (s) : l'entrée est écartée.
DANS_S_MAX = 86_400.0


def _texte(valeur: object, maximum: int) -> Optional[str]:
    """Chaîne non vide après strip, tronquée à `maximum` ; None sinon."""
    if not isinstance(valeur, str):
        return None
    propre = valeur.strip()
    return propre[:maximum] if propre else None


def _id(valeur: object) -> Optional[str]:
    """Un identifiant : chaîne non vide, sans espace autour, au plus ID_MAX_CHARS (JAMAIS
    tronquée : un id coupé en désignerait un autre)."""
    if not isinstance(valeur, str):
        return None
    propre = valeur.strip()
    return propre if propre and len(propre) <= ID_MAX_CHARS else None


def _charger(raw: object) -> Any:
    """json.loads sans exception (RecursionError comprise : payload hostile)."""
    if not isinstance(raw, (str, bytes, bytearray)):
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError, RecursionError):
        return None


# ================================================================ jeu/impro (commande)
def encoder_commande(etat: str) -> str:
    if etat not in ETATS:
        raise ValueError("commande d'impro {!r} : attendu {}".format(etat, ETATS))
    return json.dumps(etat)


def decoder_commande(raw: object) -> Optional[str]:
    """"on" | "off", ou None. JSON ('"on"') ou brut ('on', tapé à la main), casse et espaces
    ignorés, comme la commande de route."""
    valeur: Any = _charger(raw) if isinstance(raw, str) else None
    if valeur is None and isinstance(raw, str):
        valeur = raw
    if not isinstance(valeur, str):
        return None
    valeur = valeur.strip().lower()
    return valeur if valeur in ETATS else None


# ================================================================ jeu/impro_state (état latché)
@dataclass(frozen=True)
class EtatImpro:
    impro: str
    cause: str
    t_ms: int


def encoder_etat(impro: str, cause: str, t_ms: int) -> str:
    if impro not in ETATS:
        raise ValueError("état d'impro {!r} : attendu {}".format(impro, ETATS))
    if cause not in CAUSES:
        raise ValueError("cause {!r} : attendue parmi {}".format(cause, CAUSES))
    if isinstance(t_ms, bool) or not isinstance(t_ms, int) or t_ms < 0:
        raise ValueError("t_ms {!r} : entier >= 0 attendu".format(t_ms))
    return json.dumps({"impro": impro, "cause": cause, "t_ms": t_ms})


def decoder_etat(raw: object) -> Optional[EtatImpro]:
    """L'état publié par le sélecteur, ou None si illisible (champ manquant, valeur hors
    liste). Un lecteur qui reçoit None tient l'impro pour ÉTEINTE (`impro_allumee`)."""
    data = _charger(raw)
    if not isinstance(data, dict):
        return None
    impro, cause, t_ms = data.get("impro"), data.get("cause"), data.get("t_ms")
    if impro not in ETATS or cause not in CAUSES:
        return None
    if isinstance(t_ms, bool) or not isinstance(t_ms, int) or t_ms < 0:
        return None
    return EtatImpro(impro, cause, t_ms)


def impro_allumee(etat: Optional[EtatImpro]) -> bool:
    """Le sens sûr : seul un état LISIBLE qui dit "on" allume l'impro."""
    return etat is not None and etat.impro == ON


# ================================================================ jeu/proposition (scénariste)
@dataclass(frozen=True)
class Proposition:
    quoi: str
    cible: Optional[str]
    pourquoi: str


def encoder_proposition(quoi: str, cible: Optional[str], pourquoi: str) -> str:
    if _id(quoi) is None:
        raise ValueError("quoi {!r} : identifiant non vide de {} caractères au plus".format(quoi, ID_MAX_CHARS))
    if cible is not None and _id(cible) is None:
        raise ValueError("cible {!r} : identifiant ou None".format(cible))
    if not isinstance(pourquoi, str):
        raise ValueError("pourquoi : chaîne attendue")
    return json.dumps({"quoi": quoi.strip(), "cible": cible.strip() if cible else None,
                       "pourquoi": pourquoi.strip()[:POURQUOI_MAX_CHARS]}, ensure_ascii=False)


def decoder_proposition(raw: object) -> Optional[Proposition]:
    """La proposition, ou None : `quoi` absent ou hors forme = rien à peser. Une cible hors
    forme retombe à None (la proposition reste, sans cible) ; `pourquoi` est tronqué."""
    data = _charger(raw)
    if not isinstance(data, dict):
        return None
    quoi = _id(data.get("quoi"))
    if quoi is None:
        return None
    return Proposition(quoi=quoi, cible=_id(data.get("cible")),
                       pourquoi=_texte(data.get("pourquoi"), POURQUOI_MAX_CHARS) or "")


# ================================================================ jeu/repertoire (liste fermée)
@dataclass(frozen=True)
class EntreeRepertoire:
    id: str
    genre: str
    desc: str
    dispo: bool
    dans_s: float   # dans combien de secondes l'entrée redevient jouable (0 si dispo)


def _dans_s_valide(valeur: object) -> bool:
    return (isinstance(valeur, (int, float)) and not isinstance(valeur, bool)
            and math.isfinite(valeur) and 0 <= valeur <= DANS_S_MAX)


def encoder_repertoire(entrees: Sequence[EntreeRepertoire]) -> str:
    if len(entrees) > REPERTOIRE_MAX:
        raise ValueError("répertoire de {} entrées : {} au plus".format(len(entrees), REPERTOIRE_MAX))
    vus = set()
    lignes = []
    for e in entrees:
        if _id(e.id) is None or e.genre not in GENRES or not isinstance(e.dispo, bool) \
                or not _dans_s_valide(e.dans_s) or not isinstance(e.desc, str):
            raise ValueError("entrée de répertoire invalide : {!r}".format(e))
        if e.id in vus:
            raise ValueError("id {!r} en double dans le répertoire".format(e.id))
        vus.add(e.id)
        lignes.append({"id": e.id, "genre": e.genre, "desc": e.desc[:DESC_MAX_CHARS],
                       "dispo": e.dispo, "dans_s": round(float(e.dans_s), 1)})
    return json.dumps(lignes, ensure_ascii=False)


def decoder_repertoire(raw: object) -> List[EntreeRepertoire]:
    """Les entrées lisibles, dans l'ordre, REPERTOIRE_MAX au plus ; une entrée fautive (ou un
    id déjà vu) est écartée, jamais devinée. Payload illisible = liste vide : rien n'est jouable."""
    data = _charger(raw)
    if not isinstance(data, list):
        return []
    entrees: List[EntreeRepertoire] = []
    vus = set()
    for ligne in data:
        if len(entrees) == REPERTOIRE_MAX:
            break
        if not isinstance(ligne, dict):
            continue
        ident, genre, dispo, dans_s = _id(ligne.get("id")), ligne.get("genre"), ligne.get("dispo"), ligne.get("dans_s")
        if ident is None or ident in vus or genre not in GENRES or not isinstance(dispo, bool) \
                or not _dans_s_valide(dans_s) or not isinstance(dans_s, (int, float)):
            continue
        vus.add(ident)
        entrees.append(EntreeRepertoire(id=ident, genre=genre, desc=_texte(ligne.get("desc"), DESC_MAX_CHARS) or "",
                                        dispo=dispo, dans_s=float(dans_s)))
    return entrees


# Raisons d'un refus de proposition (journal du sélecteur, retour par jeu/intention).
REFUS_INCONNU = "inconnu"
REFUS_INDISPONIBLE = "indisponible"


def refus_proposition(proposition: Proposition, repertoire: Sequence[EntreeRepertoire]) -> Optional[str]:
    """None si la proposition nomme une entrée DISPONIBLE du répertoire publié ; sinon la
    raison du refus. Le scénariste ne peut nommer que ce que le sélecteur a lui-même mis dans
    la liste (§3.2) : c'est ici que « une idée hors liste » devient un refus, pas un geste."""
    for entree in repertoire:
        if entree.id == proposition.quoi:
            return None if entree.dispo else REFUS_INDISPONIBLE
    return REFUS_INCONNU
