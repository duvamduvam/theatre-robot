"""Géométrie du corps sûr (spec A0 §4.1-4.2) — logique PURE, stdlib seule.

Repère `base_link` : x vers l'avant, y vers la gauche, origine au centre de la
boîte de collision de l'URDF. La caisse est un RECTANGLE majorant (cotes
estimées depuis les photos, à mesurer en A0-7) ; on mesure tout « de la
caisse », jamais du centre (étude §3.2).

Pas de TF sur le chemin de sécurité : la pose du lidar arrive en paramètre
(`PoseLidar`), lue dans le YAML du corps sûr.
"""
import math
from dataclasses import dataclass

# Échantillonnage du cercle balayé pour l'invariant du pivot : 0,1°. Les quatre
# points cardinaux (où tombe le maximum quand l'essieu est dans la caisse) sont
# des multiples exacts de ce pas, donc toujours évalués.
PAS_PIVOT_DEG = 0.1
# Garde de l'invariant du pivot : le disque balayé tient dans la zone d'arrêt
# avec 5 cm de marge (§4.1).
GARDE_PIVOT_M = 0.05


@dataclass(frozen=True)
class Caisse:
    """Rectangle de la caisse dans `base_link` (m). `x_essieu` = centre de
    rotation d'un pivot ; `rayon_balayage` = de l'essieu au point le plus
    éloigné du corps RÉEL (bout de la flèche arrière), pas au coin du
    rectangle majorant.

    `Caisse()` sans argument = les défauts de la spec §4.1 (URDF, cotes estimées)
    — pour les outils et les tests ; le nœud lit TOUJOURS les cinq cotes dans le
    YAML (`reglages` refuse une cote manquante)."""
    x_avant: float = 0.30
    x_arriere: float = -0.57
    demi_largeur: float = 0.40
    x_essieu: float = 0.10
    rayon_balayage: float = 0.65


@dataclass(frozen=True)
class PoseLidar:
    """Pose de `laser_frame` dans `base_link` : position (m) et lacet (rad,
    sens trigonométrique). Un lacet faux se voit au banc (§10.1, geste 3)."""
    x: float
    y: float
    lacet_rad: float


def distance_caisse(caisse: Caisse, x: float, y: float) -> float:
    """Distance euclidienne du point (x, y) au rectangle de la caisse ; 0 dedans
    ou sur le bord. La zone d'arrêt = les points à moins de la marge : le
    rectangle gonflé, coins arrondis."""
    dx = max(caisse.x_arriere - x, 0.0, x - caisse.x_avant)
    dy = max(abs(y) - caisse.demi_largeur, 0.0)
    return math.hypot(dx, dy)


def point_dans_base(pose: PoseLidar, angle_rad: float, distance_m: float) -> tuple[float, float]:
    """Un rayon (angle dans `laser_frame`, distance) → point (x, y) dans `base_link`."""
    cap = pose.lacet_rad + angle_rad
    return (pose.x + distance_m * math.cos(cap), pose.y + distance_m * math.sin(cap))


def points_dans_base(pose: PoseLidar, angle_min: float, increment: float,
                     distances: list[float]) -> list[tuple[float, float]]:
    """Balayage (`angle_min`, `angle_increment` en rad, `ranges`) → points dans
    `base_link`, dans l'ordre des rayons. Les distances NON FINIES sont sautées
    (`inf`, `NaN` : ni obstacle ni preuve de vie, §4.3) ; portée et masques ne
    sont PAS appliqués ici (c'est `balayage.lire_balayage`). Pour garder
    l'indice du rayon, appeler `point_dans_base` rayon par rayon."""
    points = []
    for i, r in enumerate(distances):
        if math.isfinite(r):
            points.append(point_dans_base(pose, angle_min + i * increment, r))
    return points


def ecart_pivot(caisse: Caisse) -> float:
    """Plus grande `distance_caisse` d'un point du cercle balayé par un pivot
    (centre (x_essieu, 0), rayon `rayon_balayage`). Défauts : 0,10 + 0,65 − 0,30
    = 0,45 (le point avant)."""
    pas = round(360.0 / PAS_PIVOT_DEG)
    pire = 0.0
    for k in range(pas):
        a = math.radians(k * PAS_PIVOT_DEG)
        x = caisse.x_essieu + caisse.rayon_balayage * math.cos(a)
        y = caisse.rayon_balayage * math.sin(a)
        pire = max(pire, distance_caisse(caisse, x, y))
    return pire


def invariant_pivot(caisse: Caisse, marge_arret_m: float) -> tuple[bool, float]:
    """(respecté, écart) : le disque balayé tient dans la zone d'arrêt avec 5 cm
    de garde, `ecart_pivot ≤ marge_arret − 0,05` (§4.1). C'est ce qui rend vraie
    la règle « rotation seulement si rien à moins de la marge sur tout le
    tour ». Violé → la configuration est refusée (`reglages`)."""
    ecart = ecart_pivot(caisse)
    return ecart <= marge_arret_m - GARDE_PIVOT_M, ecart
