"""Validité des points et d'un balayage, masques, témoin (spec A0 §4.2-4.3) — PUR.

Convention des MASQUES (dans `laser_frame`, degrés, sens trigonométrique) : un
masque `[debut, fin]` couvre l'arc parcouru de `debut` à `fin` en tournant dans
le sens des angles CROISSANTS, bornes comprises, angles pris modulo 360. Donc :
`[90, 270]` = le demi-tour arrière (passe par 180°) ; `[170, 190]` = ±10° autour
de l'arrière ; `[350, 10]` et `[-10, 10]` = ±10° autour de l'avant (passe par 0) ;
`[270, 90]` = le demi-tour AVANT (l'ordre compte). Un masque dont `fin − debut`
vaut 360 ou plus couvre tout le tour ; `debut == fin` ne couvre que cet angle.

Le TÉMOIN (§4.2) : des auto-retours stables du corps, mesurés au banc. Ils sont
dans un secteur masqué (ce ne sont pas des obstacles) ; on les cherche donc parmi
les rayons BRUTS : distance finie dans `distance_m`, angle dans `secteur_deg`
(même convention qu'un masque). Moins de `points_min` → balayage invalide
(capteur aveuglé : capot, vitre sale, laser coupé).
"""
import math
from dataclasses import dataclass

from didier_corps_sur.geometrie import Caisse, PoseLidar, distance_caisse, point_dans_base

# Motifs d'invalidité d'un balayage (§4.3), dans l'ordre où ils sont examinés.
RAYONS_INSUFFISANTS = "rayons_insuffisants"
STAMP_NON_CROISSANT = "stamp_non_croissant"
TROP_VIEUX = "trop_vieux"
TEMOIN_ABSENT = "temoin_absent"
GEOMETRIE_INVALIDE = "geometrie_invalide"


@dataclass(frozen=True)
class Temoin:
    exige: bool
    secteur_deg: tuple[float, float]
    distance_m: tuple[float, float]
    points_min: int


@dataclass(frozen=True)
class ParametresBalayage:
    portee_min_m: float
    portee_max_m: float
    rayons_min: int
    age_max_reception_s: float
    masques_deg: tuple[tuple[float, float], ...]
    temoin: Temoin


@dataclass(frozen=True)
class Lecture:
    """Résultat d'un balayage. `valide` = il nourrit le chien de garde du
    capteur ; `d_min_m` = plus petite distance à la caisse des points valides
    (`inf` s'il n'y en a aucun) — calculée même pour un balayage invalide, pour
    que l'appelant puisse appliquer l'entrée immédiate en ARRET (§5.1)."""
    motifs: tuple[str, ...]
    d_min_m: float
    retour_dans_caisse: bool
    rayons: int
    points_valides: int
    temoin_points: int

    @property
    def valide(self) -> bool:
        return not self.motifs


def dans_arc(angle_deg: float, debut_deg: float, fin_deg: float) -> bool:
    """Vrai si l'angle est dans l'arc [debut → fin] parcouru en sens croissant
    (convention du module, voir la docstring)."""
    if fin_deg - debut_deg >= 360.0:
        return True
    etendue = (fin_deg - debut_deg) % 360.0
    return (angle_deg - debut_deg) % 360.0 <= etendue


def dans_masque(angle_deg: float, masques_deg: tuple[tuple[float, float], ...]) -> bool:
    return any(dans_arc(angle_deg, debut, fin) for debut, fin in masques_deg)


def lire_balayage(params: ParametresBalayage, caisse: Caisse, pose: PoseLidar,
                  stamp_s: float, stamp_precedent_s: float | None, maintenant_s: float,
                  angle_min: float, increment: float, distances: list[float]) -> Lecture:
    """Un `LaserScan` (horodatage, horloge du nœud, géométrie, `ranges`) → `Lecture`.

    Un point compte s'il est fini, dans [portee_min, portee_max] et hors masque.
    Le balayage est valide si : au moins `rayons_min` rayons ; `stamp` strictement
    postérieur au précédent (un republieur figé ne nourrit rien) ; âge à la
    réception ≤ `age_max_reception_s` ; témoin présent s'il est exigé.
    Tous les motifs trouvés sont rendus (diagnostic), pas seulement le premier.
    """
    motifs = []
    if len(distances) < params.rayons_min:
        motifs.append(RAYONS_INSUFFISANTS)
    if stamp_precedent_s is not None and not stamp_s > stamp_precedent_s:
        motifs.append(STAMP_NON_CROISSANT)
    if maintenant_s - stamp_s > params.age_max_reception_s:
        motifs.append(TROP_VIEUX)
    if not (math.isfinite(angle_min) and math.isfinite(increment)):
        # Géométrie illisible : aucun point ne peut être placé.
        motifs.append(GEOMETRIE_INVALIDE)
        return Lecture(tuple(motifs), math.inf, False, len(distances), 0, 0)

    d_min = math.inf
    valides = 0
    temoin = 0
    t = params.temoin
    for i, r in enumerate(distances):
        if not math.isfinite(r):
            continue
        angle = angle_min + i * increment
        angle_deg = math.degrees(angle)
        if t.exige and t.distance_m[0] <= r <= t.distance_m[1] \
                and dans_arc(angle_deg, t.secteur_deg[0], t.secteur_deg[1]):
            temoin += 1
        if not params.portee_min_m <= r <= params.portee_max_m:
            continue
        if dans_masque(angle_deg, params.masques_deg):
            continue
        valides += 1
        x, y = point_dans_base(pose, angle, r)
        d_min = min(d_min, distance_caisse(caisse, x, y))
    if t.exige and temoin < t.points_min:
        motifs.append(TEMOIN_ABSENT)
    # Un retour hors masque DANS la caisse = obstacle (motif retour_dans_caisse) :
    # des masques faux se voient tout de suite, Didier ne bouge pas (§4.2).
    return Lecture(tuple(motifs), d_min, d_min == 0.0, len(distances), valides, temoin)
