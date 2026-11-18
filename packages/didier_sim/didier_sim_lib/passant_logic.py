"""Logique pure du PASSANT simulé (spec A0 §8.4) — aucun import ROS ni gz, stdlib seule.

Le passant est un cylindre statique du monde `stage` (r 0,20 m, h 1,7 m) que
`scripts/passant_sim_node` déplace par set_pose à 20 Hz le long d'un segment, à vitesse
constante. Il ne pousse pas Didier (pas de physique) : les épreuves mesurent une DISTANCE.

Demande (topic `sim/passant`, StringTime, JSON) :
    {"de": [x, y], "a": [x, y], "vitesse": 1.0, "repere": "didier"}
`repere` vaut "didier" par défaut : les points sont donnés dans le repère de Didier (x devant,
y à gauche, origine = base_link) À L'INSTANT DE LA DEMANDE, et convertis en repère monde avec
la vérité terrain (`ground_truth/odom`) ; "monde" les prend tels quels.

Tout le temps est injecté (horloge du nœud, simulée) : rien ici ne lit l'heure.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Tuple

Point = Tuple[float, float]

# Bornes de la demande : un passant marche (0,5 à 1,5 m/s dans les épreuves) ; au-delà de
# 3 m/s, ou d'un segment de plus de 30 m, c'est une faute de frappe, pas un passant.
VITESSE_MAX_M_S = 3.0
LONGUEUR_MAX_M = 30.0
REPERES = ("didier", "monde")


@dataclass(frozen=True)
class Demande:
    de: Point
    a: Point
    vitesse: float
    repere: str


@dataclass(frozen=True)
class Trajet:
    """Segment en repère MONDE, parcouru à `vitesse` à partir de `t0` (secondes, horloge du nœud)."""
    de: Point
    a: Point
    vitesse: float
    t0: float

    @property
    def longueur(self) -> float:
        return math.hypot(self.a[0] - self.de[0], self.a[1] - self.de[1])

    @property
    def duree(self) -> float:
        return self.longueur / self.vitesse


def _point(valeur: object, nom: str) -> Point:
    if not isinstance(valeur, (list, tuple)) or len(valeur) != 2:
        raise ValueError("%s : attendu [x, y]" % nom)
    x, y = (float(v) for v in valeur)
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError("%s : coordonnées non finies" % nom)
    return (x, y)


def lire_demande(texte: str) -> Demande:
    """JSON de `sim/passant` → Demande ; ValueError (message lisible) si quoi que ce soit cloche."""
    try:
        brut = json.loads(texte)
    except json.JSONDecodeError as exc:
        raise ValueError("JSON illisible : %s" % exc) from exc
    if not isinstance(brut, dict):
        raise ValueError("attendu un objet JSON {de, a, vitesse}")
    de = _point(brut.get("de"), "de")
    a = _point(brut.get("a"), "a")
    try:
        vitesse = float(brut.get("vitesse"))  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError("vitesse : nombre attendu") from exc
    if not (0.0 < vitesse <= VITESSE_MAX_M_S):
        raise ValueError("vitesse %.3f hors de ]0 ; %.1f] m/s" % (vitesse, VITESSE_MAX_M_S))
    longueur = math.hypot(a[0] - de[0], a[1] - de[1])
    if longueur == 0.0 or longueur > LONGUEUR_MAX_M:
        raise ValueError("segment de %.3f m hors de ]0 ; %.0f] m" % (longueur, LONGUEUR_MAX_M))
    repere = brut.get("repere", "didier")
    if repere not in REPERES:
        raise ValueError("repere %r inconnu (didier ou monde)" % (repere,))
    return Demande(de=de, a=a, vitesse=vitesse, repere=str(repere))


def vers_monde(point: Point, robot_x: float, robot_y: float, robot_lacet: float) -> Point:
    """Point du repère de Didier (x devant, y à gauche) → repère monde (rotation puis translation)."""
    c, s = math.cos(robot_lacet), math.sin(robot_lacet)
    return (robot_x + c * point[0] - s * point[1], robot_y + s * point[0] + c * point[1])


def lacet_depuis_quaternion(z: float, w: float) -> float:
    """Lacet d'un quaternion de rotation pure autour de z (la vérité terrain est 2D)."""
    return 2.0 * math.atan2(z, w)


def trajet_monde(demande: Demande, t0: float, pose_robot: Tuple[float, float, float] | None) -> Trajet:
    """Demande → Trajet en repère monde. `pose_robot` (x, y, lacet) est exigée en repère didier."""
    if demande.repere == "monde":
        return Trajet(demande.de, demande.a, demande.vitesse, t0)
    if pose_robot is None:
        raise ValueError("repere didier : aucune vérité terrain reçue (ground_truth/odom)")
    x, y, lacet = pose_robot
    return Trajet(vers_monde(demande.de, x, y, lacet), vers_monde(demande.a, x, y, lacet),
                  demande.vitesse, t0)


def position(trajet: Trajet, t: float) -> Tuple[Point, bool]:
    """Position du passant à l'instant t, et True si la course est finie (il reste alors en `a`).

    Avant t0 il est au départ ; la progression est bornée à [0 ; 1].
    """
    if trajet.duree <= 0.0:
        return trajet.a, True
    f = (t - trajet.t0) / trajet.duree
    if f >= 1.0:
        return trajet.a, True
    f = max(0.0, f)
    return ((trajet.de[0] + f * (trajet.a[0] - trajet.de[0]),
             trajet.de[1] + f * (trajet.a[1] - trajet.de[1])), False)
