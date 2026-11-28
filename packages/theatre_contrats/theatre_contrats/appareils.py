"""Contrat commun des APPAREILS du parc (lot L3a, 28/11) — sono aujourd'hui, lumières demain.

Spec : docs/spec-L3-gabarit-sono.md §2, décisions 9 à 11. Un appareil est une machine du spectacle
hors du robot (sono, lumières de scène…) : il tourne sous le namespace du robot (`/<ROBOT_NAME>/`),
ses topics sont préfixés par son nom (`sono/…`), et il publie UN état, la même enveloppe pour tous.

Ce module porte ce que l'appareil, le pont web et la page scène doivent écrire PAREIL :
- `REGISTRE` : LA liste des appareils du parc (topic d'état + topics d'ordres par type d'organe),
  lue par le pont web pour construire ses listes (lecture, whitelists, `stop_all`) sans recopie ;
- l'enveloppe d'état (StringTime JSON, qos.latched() des DEUX côtés), forme gravée :
    {"v": 1, "appareil", "pilote": "sim"|"materiel", "sha", "t_ms",
     "organes": [{"nom", "type": "audio", "valeur", "debut_ms", "duree_ms", "sante"}
               | {"nom", "type": "relais", "valeur", "sante"}],
     "refus": null | {"code", "detail", "t_ms"}}
  `valeur` au repos : "" (audio), false (relais) ; `debut_ms`/`duree_ms` null au repos ; `refus` =
  le DERNIER ordre refusé, remis à null par le premier ordre accepté ; `sha` = conf/DEPLOY_SHA,
  "dev" si absent (sim). Publié en sim comme en réel (ce n'est pas un topic `sim/etat/*`).
- les types d'organes connus : `audio`, `relais` (un 3e type = un appareil qui en a besoin).

`encoder_etat` lève ValueError sur une forme fausse (bug de l'écrivain) ; `decoder_etat` ne lève
JAMAIS, quoi qu'on lui donne (relecture adverse du 28/11 : 20 000 « [ » levaient RecursionError
dans la boucle d'état du pont) : illisible, trop gros (> TAILLE_MAX_OCTETS), trop d'organes
(> ORGANES_MAX) ou d'un autre appareil que celui attendu -> None.
Python PUR, stdlib seulement.
"""
import json
from typing import Optional

from theatre_contrats import topics

VERSION = 1
AUDIO = "audio"
RELAIS = "relais"
TYPES_ORGANES = (AUDIO, RELAIS)
PILOTES = ("sim", "materiel")
SANTES = ("ok", "absent", "erreur")
SHA_DEV = "dev"
TAILLE_MAX_OCTETS = 64 * 1024
ORGANES_MAX = 16

# LA liste des appareils du parc : {appareil: {"etat": topic, "ordres": {type d'organe: topic}}}.
REGISTRE = {
    "sono": {"etat": topics.SONO_ETAT,
             "ordres": {AUDIO: topics.SONO_AUDIO, RELAIS: topics.SONO_RELAIS}},
}


# Noms d'appareil INTERDITS (relecture adverse du 28/11) : un appareil nommé comme un espace de
# topics existant (corps_sur, jeu, vision…) ou comme un préfixe de mouvement ou de séance
# publierait sous des noms que d'autres nœuds écoutent — roues comprises.
PREFIXES_RESERVES = ("cmd_vel", "route", "wheels", "chat", "rehearsal", "e_stop")


def espaces_reserves() -> frozenset:
    """Le 1er segment de chaque topic de theatre_contrats.topics, hors appareils du registre."""
    espaces = {v.split("/")[0] for k, v in vars(topics).items() if k.isupper() and isinstance(v, str)}
    return frozenset(espaces - set(REGISTRE))


def nom_reserve(nom: str) -> bool:
    return nom in espaces_reserves() or nom.startswith(PREFIXES_RESERVES)


def topics_etat() -> tuple:
    """Les topics d'état de tous les appareils, dans l'ordre du registre."""
    return tuple(a["etat"] for a in REGISTRE.values())


def topics_ordres(type_organe: Optional[str] = None) -> tuple:
    """Les topics d'ordres du registre ; d'un seul type d'organe si `type_organe` est donné."""
    return tuple(t for a in REGISTRE.values() for ty, t in a["ordres"].items()
                 if type_organe is None or ty == type_organe)


def organe_audio(nom: str, valeur: str = "", debut_ms: Optional[int] = None,
                 duree_ms: Optional[int] = None, sante: str = "ok") -> dict:
    """Un organe audio, clés dans l'ordre de l'enveloppe (repos par défaut)."""
    return {"nom": nom, "type": AUDIO, "valeur": valeur, "debut_ms": debut_ms,
            "duree_ms": duree_ms, "sante": sante}


def organe_relais(nom: str, valeur: bool = False, sante: str = "ok") -> dict:
    """Un organe relais, clés dans l'ordre de l'enveloppe (repos par défaut)."""
    return {"nom": nom, "type": RELAIS, "valeur": valeur, "sante": sante}


def refus(code: str, detail: str, t_ms: int) -> dict:
    """Le dernier ordre refusé, tel que l'enveloppe le porte."""
    return {"code": code, "detail": detail, "t_ms": t_ms}


def _entier(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _entier_ou_nul(x) -> bool:
    return x is None or _entier(x)


def _organe_valide(o) -> bool:
    if not isinstance(o, dict) or not isinstance(o.get("nom"), str) or not o["nom"]:
        return False
    if o.get("sante") not in SANTES:
        return False
    if o.get("type") == AUDIO:
        return (set(o) == {"nom", "type", "valeur", "debut_ms", "duree_ms", "sante"}
                and isinstance(o["valeur"], str)
                and _entier_ou_nul(o["debut_ms"]) and _entier_ou_nul(o["duree_ms"]))
    if o.get("type") == RELAIS:
        return set(o) == {"nom", "type", "valeur", "sante"} and isinstance(o["valeur"], bool)
    return False


def _refus_valide(r) -> bool:
    return r is None or (isinstance(r, dict) and set(r) == {"code", "detail", "t_ms"}
                         and isinstance(r["code"], str) and isinstance(r["detail"], str)
                         and _entier(r["t_ms"]))


def _etat_valide(d) -> bool:
    return (isinstance(d, dict)
            and set(d) == {"v", "appareil", "pilote", "sha", "t_ms", "organes", "refus"}
            and type(d["v"]) is int and d["v"] == VERSION
            and isinstance(d["appareil"], str) and bool(d["appareil"])
            and d["pilote"] in PILOTES and isinstance(d["sha"], str) and _entier(d["t_ms"])
            and isinstance(d["organes"], list) and len(d["organes"]) <= ORGANES_MAX
            and all(_organe_valide(o) for o in d["organes"])
            and _refus_valide(d["refus"]))


def encoder_etat(appareil: str, pilote: str, sha: str, t_ms: int, organes: list,
                 refus_: Optional[dict] = None) -> str:
    """Payload StringTime de `<appareil>/etat` (forme en tête de module). Lève ValueError."""
    d = {"v": VERSION, "appareil": appareil, "pilote": pilote, "sha": sha, "t_ms": t_ms,
         "organes": list(organes), "refus": refus_}
    if not _etat_valide(d):
        raise ValueError(f"enveloppe d'état invalide : {d!r}")
    return json.dumps(d, ensure_ascii=False)


def decoder_etat(brut, appareil: Optional[str] = None) -> Optional[dict]:
    """Enveloppe lue (chaîne JSON ou dict déjà décodé) ; illisible -> None, JAMAIS d'exception.
    `appareil` donné : une enveloppe d'un autre appareil est refusée (None)."""
    try:
        if isinstance(brut, (str, bytes)):
            if len(brut) > TAILLE_MAX_OCTETS:
                return None
            brut = json.loads(brut)
        if not _etat_valide(brut) or (appareil is not None and brut["appareil"] != appareil):
            return None
        return brut
    except Exception:  # noqa: BLE001 — RecursionError, MemoryError… : jamais propagé au lecteur
        return None
