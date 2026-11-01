"""Décodage du boîtier de FADERS (device série `sliders`, RP2040-Zero, 9600 bauds)
— logique PURE, par PROFIL (stdlib + Misc.mapping seulement, aucun ROS).

Le firmware envoie 2 caractères (un fader, valeur 10..99) ou 4 (deux faders).
Historiquement SerialInputs.send_sliders mappait EN DUR : 2 → cou (0..1),
4 → roues gauche/droite (−100..100). Ce module reproduit ce comportement dans
le profil "default" (OCTET POUR OCTET, test gravé) et ajoute le profil
"repetition" (salle de répétition simulée, étude dadou_robot_ros/docs/
etude-repetition-simulee.md §4.5 : décision de David du 07/10 — un fader du
boîtier déjà en stock commande la vitesse du cheminement de Didier).

POURQUOI des profils en DONNÉES et pas un `if` de plus : le prochain usage
du boîtier (danse, lumières…) sera une ligne de table, pas une branche de
code — et chaque profil est testé par les mêmes tests.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

from dadou_utils_ros.misc import Misc
from dadou_utils_ros.utils_static import LEFT, NECK, RIGHT, WHEELS

from controller.control_static import ROUTE_SPEED

# Plage brute du firmware (deux chiffres ASCII, 10..99 ; en deçà/au-delà,
# Misc.mapping borne).
RAW_MIN, RAW_MAX = 10, 99

# Cibles de décodage : (clé publiée, fonction brut -> valeur).
def _unit(raw: int) -> float:
    """0..1 : identique à l'historique float(mapping(..., 0, 100) / 100)."""
    return float(Misc.mapping(raw, RAW_MIN, RAW_MAX, 0, 100) / 100)


def _signed(raw: int) -> int:
    """−100..100 (pourcents roues), identique à l'historique."""
    return Misc.mapping(raw, RAW_MIN, RAW_MAX, -100, 100)


# Un profil = pour chaque longueur de message, comment le découper.
#   "single" : (clé, convertisseur)             -> {clé: valeur}
#   "pair"   : liste de (clé, convertisseur)    -> {clé1: v1, clé2: v2}
#   "pair_wheels" : spécial historique          -> {WHEELS: {LEFT, RIGHT}}
PROFILES: Dict[str, dict] = {
    # Comportement historique, octet pour octet (test_sliders_mapping.py).
    "default": {
        2: ("single", (NECK, _unit)),
        4: ("pair_wheels", None),
    },
    # Salle de répétition : fader 1 = vitesse du cheminement (0..1), fader 2 =
    # cou (0..1) — rien vers les roues : la route est déjà sur le créneau
    # prio 20 du mux, les roues restent au joystick (prio 100).
    "repetition": {
        2: ("single", (ROUTE_SPEED, _unit)),
        4: ("pair", [(ROUTE_SPEED, _unit), (NECK, _unit)]),
    },
}


def resolve_profile(name: Optional[str]) -> str:
    """Nom de profil validé — REFUS explicite (ValueError) sinon : une faute
    de frappe dans SLIDERS_PROFILE ne doit pas donner silencieusement le
    comportement par défaut pendant une répétition."""
    if name is None or name == "":
        return "default"
    if name not in PROFILES:
        raise ValueError(
            f"profil de faders inconnu « {name} » ; profils : {sorted(PROFILES)}")
    return name


def decode_sliders(msg: str, profile: str = "default") -> Optional[dict]:
    """Message brut du boîtier -> dict publiable (clés = topics), ou None si la
    longueur n'est pas prévue par le profil (erreur loggée, comme avant)."""
    spec = PROFILES[resolve_profile(profile)].get(len(msg))
    if spec is None:
        logging.error("sliders : message de taille imprévue {!r} (profil {})".format(msg, profile))
        return None
    kind, target = spec
    if kind == "single":
        key, conv = target
        return {key: conv(int(msg[0:2]))}
    if kind == "pair":
        return {key: conv(int(msg[2 * i:2 * i + 2])) for i, (key, conv) in enumerate(target)}
    # pair_wheels : forme imbriquée historique, consommée par wheels_bridge/Wheels.
    return {WHEELS: {LEFT: _signed(int(msg[0:2])), RIGHT: _signed(int(msg[2:4]))}}


def profile_targets(name: str) -> Tuple[str, ...]:
    """Clés que le profil peut publier (pour le test de contrat PUBLISHER_LIST)."""
    keys = []
    for kind, target in PROFILES[resolve_profile(name)].values():
        if kind == "single":
            keys.append(target[0])
        elif kind == "pair":
            keys.extend(k for k, _ in target)
        else:
            keys.append(WHEELS)
    return tuple(keys)
