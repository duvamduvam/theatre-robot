#!/usr/bin/env python3
"""Géométrie des tours « faire le tour de X » (lot M3, spec-aller-voir.md §8.1).

    python3 tools/compute_tours.py <monde.sdf> <itinéraire.yaml> [> config/<itinéraire>_tours.yaml]

POURQUOI un fichier GÉNÉRÉ : l'ancre d'un POI n'est PAS le centre de l'objet
(poubelle_tri : ancre (27 ; 1,4), bacs centrés en (27 ; 2,4)) ; le tour se
calcule sur la géométrie de COLLISION du monde Gazebo, une fois, ici — jamais
à la main, jamais au démarrage d'un node (le SDF n'est pas installé avec
robot_rehearsal). test_tours.py regénère et compare : un monde retouché sans
regénération rougit.

Règles (spec §8.1), pour chaque POI de l'itinéraire, le modèle SDF de MÊME nom :
  - chaque collision = un disque (centre au sol, rayon d'emprise e) :
    cylindre -> rayon, boîte -> demi-diagonale (x, y), sphère -> rayon ;
    rotation de lien ignorée -> MAJORANT. ÉCART ASSUMÉ : une primitive
    INCLINÉE (roll/pitch, ex. roues du vélo, banane couchée) n'est plus
    majorée par ces valeurs (un cylindre couché s'étale sur sa longueur) ;
    elle prend alors le rayon de sa SPHÈRE englobante, majorant pour toute
    rotation — c'est l'intention écrite (« majorant ») ;
  - centre = milieu de la boîte englobante (x, y) des disques ;
  - rayon objet = max (distance centre -> centre du disque + e) ;
  - rayon de tour = rayon objet + TOUR_CLEARANCE_M, arrondi au 0,1 m
    SUPÉRIEUR, au moins TOUR_MIN_RADIUS_M ;
  - tour IMPOSSIBLE (POI absent du fichier) si rayon > TOUR_MAX_RADIUS_M, ou
    si un AUTRE modèle (tous sauf le SOL, liste explicite GROUND_MODELS) a une
    collision à moins de 0,5 m de l'anneau [r − 0,6 ; r + 0,6]. Cette
    distance-là est mesurée sur l'emprise RÉELLE (polygone convexe des coins
    projetés, disque pour cylindre vertical et sphère), pas sur le disque
    majorant : le hall des Nefs (30 × 12 m) en disque de 16 m interdirait le
    tour de poubelle_tri, posée à 4,6 m de sa façade. La bordure de quai
    (chute dans la Loire derrière) et les façades SONT des obstacles
    (décision du 01/11, sécurité d'abord : l'ancienne règle « emprise > 50 m
    = sol » les écartait, et 5 tours passaient dans un mur ou dans l'eau).
Stdlib + yaml. Sortie déterministe (même entrée -> même texte, octet pour octet).
"""
from __future__ import annotations

import math
import pathlib
import sys
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

import yaml

# Lancé depuis un checkout (pas installé) : le package Python est le voisin.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from robot_rehearsal.contracts import TOUR_CLEARANCE_M, TOUR_MAX_RADIUS_M, TOUR_MIN_RADIUS_M  # noqa: E402

# Modèles SOL, seuls ignorés comme obstacles (on roule dessus). Liste
# EXPLICITE, pas une règle de taille (décision du 01/11) : un grand modèle
# (bordure de quai, façades, Loire) est un obstacle, mesuré sur son emprise
# réelle. Un nouveau monde avec un autre sol l'ajoute ici, en connaissance de cause.
GROUND_MODELS = frozenset({"esplanade"})
# Demi-largeur de l'anneau balayé : Didier (0,4) + écart radial toléré en
# régime (0,2) ; tout obstacle à moins de RING_MARGIN_M de cet anneau = refus.
RING_HALF_WIDTH_M = 0.6
RING_MARGIN_M = 0.5
# Une primitive est « verticale » si son axe z local reste à moins de ce
# cosinus de la verticale (tolérance d'arrondi des poses écrites à 1e-6).
_VERTICAL_COS = 1.0 - 1e-9

HEADER = ("# GÉNÉRÉ — ne pas éditer. tools/compute_tours.py <monde.sdf> <itinéraire.yaml>\n"
          "# Tours « faire le tour de X » (spec-aller-voir.md §8.1) : centre (x, y) et rayon\n"
          "# de l'orbite, depuis la géométrie de COLLISION du monde. POI absent = pas de tour.\n")

Disc = Tuple[float, float, float]   # (x, y, rayon d'emprise)
Mat = List[List[float]]
# Emprise réelle au sol d'une collision : ("disc", x, y, e) ou ("poly", points).
Shape = tuple


def _floats(text: Optional[str], n: int) -> List[float]:
    v = [float(t) for t in (text or "").split()]
    return (v + [0.0] * n)[:n]


def _rot(roll: float, pitch: float, yaw: float) -> Mat:
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return [[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr]]


def _compose(parent: Tuple[Mat, Tuple[float, float, float]], el) -> Tuple[Mat, Tuple[float, float, float]]:
    """Pose SDF de `el` (relative au parent, `<pose>` absente = identité) -> pose monde."""
    R, t = parent
    p = _floats(el.findtext("pose"), 6)
    Rl = _rot(*p[3:])
    R2 = [[sum(R[i][k] * Rl[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    t2 = tuple(sum(R[i][k] * p[k] for k in range(3)) + t[i] for i in range(3))
    return R2, t2


def _extent(geometry, R: Mat) -> float:
    """Rayon d'emprise au sol d'une primitive (cf. docstring : règle de la
    spec si verticale, sphère englobante si inclinée)."""
    vertical = R[2][2] >= _VERTICAL_COS
    box, cyl, sph = geometry.find("box"), geometry.find("cylinder"), geometry.find("sphere")
    if box is not None:
        sx, sy, sz = _floats(box.findtext("size"), 3)
        return math.hypot(sx, sy) / 2 if vertical else math.sqrt(sx * sx + sy * sy + sz * sz) / 2
    if cyl is not None:
        r, length = float(cyl.findtext("radius")), float(cyl.findtext("length"))
        return r if vertical else math.hypot(r, length / 2)
    if sph is not None:
        return float(sph.findtext("radius"))
    # Une primitive inconnue (mesh, plane) ne se majore pas ici : refus franc.
    raise ValueError(f"primitive de collision non gérée : {[c.tag for c in geometry]}")


def _footprint(geometry, R: Mat, t) -> Shape:
    """Emprise RÉELLE au sol (majorée de l'épaisseur d'un trait) : disque
    exact si cylindre vertical ou sphère, sinon polygone convexe des points
    de la primitive projetés (coins d'une boîte ; cercles d'extrémité d'un
    cylindre incliné, échantillonnés sur un polygone CIRCONSCRIT)."""
    box, cyl, sph = geometry.find("box"), geometry.find("cylinder"), geometry.find("sphere")
    vertical = R[2][2] >= _VERTICAL_COS
    if sph is not None:
        return ("disc", t[0], t[1], float(sph.findtext("radius")))
    if cyl is not None:
        r, length = float(cyl.findtext("radius")), float(cyl.findtext("length"))
        if vertical:
            return ("disc", t[0], t[1], r)
        n = 24
        rc = r / math.cos(math.pi / n)   # circonscrit : le polygone contient le cercle
        local = [(rc * math.cos(2 * math.pi * k / n), rc * math.sin(2 * math.pi * k / n), z)
                 for k in range(n) for z in (-length / 2, length / 2)]
    elif box is not None:
        sx, sy, sz = _floats(box.findtext("size"), 3)
        local = [(a * sx / 2, b * sy / 2, c * sz / 2) for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]
    else:
        raise ValueError(f"primitive de collision non gérée : {[c.tag for c in geometry]}")
    pts = [(sum(R[0][k] * p[k] for k in range(3)) + t[0], sum(R[1][k] * p[k] for k in range(3)) + t[1])
           for p in local]
    return ("poly", _hull(pts))


def _cross(o, a, b) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _hull(points):
    """Enveloppe convexe 2D (chaîne monotone), sens trigonométrique."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _dist_point_segment(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    n2 = dx * dx + dy * dy
    u = 0.0 if n2 == 0.0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n2))
    return math.hypot(p[0] - a[0] - u * dx, p[1] - a[1] - u * dy)


def _radial_span(shape: Shape, cx: float, cy: float) -> Tuple[float, float]:
    """(distance min, distance max) du centre C à l'emprise. Une forme convexe
    (connexe) couvre toutes les distances entre les deux."""
    if shape[0] == "disc":
        _, x, y, e = shape
        d = math.hypot(x - cx, y - cy)
        return max(0.0, d - e), d + e
    poly, c = shape[1], (cx, cy)
    d_max = max(math.hypot(x - cx, y - cy) for x, y in poly)
    if len(poly) >= 3 and all(_cross(a, b, c) >= 0.0 for a, b in zip(poly, poly[1:] + poly[:1])):
        return 0.0, d_max   # C dans le polygone
    d_min = min(_dist_point_segment(c, a, b) for a, b in zip(poly, poly[1:] + poly[:1]))
    return d_min, d_max


def model_shapes(sdf_path) -> Dict[str, List[Tuple[Disc, Shape]]]:
    """Modèles du monde -> pour chaque collision (repère monde) : (disque
    majorant de la règle de rayon, emprise réelle pour le dégagement)."""
    world = ET.parse(str(sdf_path)).getroot().find("world")
    identity = ([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], (0.0, 0.0, 0.0))
    out: Dict[str, List[Tuple[Disc, Shape]]] = {}
    for model in world.findall("model"):
        m = _compose(identity, model)
        shapes = out.setdefault(model.get("name"), [])
        for link in model.findall("link"):
            lk = _compose(m, link)
            for col in link.findall("collision"):
                R, t = _compose(lk, col)
                geometry = col.find("geometry")
                shapes.append(((t[0], t[1], _extent(geometry, R)), _footprint(geometry, R, t)))
    return out


def _bbox(discs: List[Disc]) -> Tuple[float, float, float, float]:
    return (min(x - e for x, _, e in discs), max(x + e for x, _, e in discs),
            min(y - e for _, y, e in discs), max(y + e for _, y, e in discs))


def _ceil_tenth(value: float) -> float:
    # round(…, 6) d'abord : 2,0 calculé 2,0000000001 ne doit pas devenir 2,1.
    return math.ceil(round(value * 10.0, 6)) / 10.0


def ring_clearance(shape: Shape, cx: float, cy: float, r: float) -> float:
    """Distance (≥ 0, 0 = chevauche) entre une emprise et l'anneau [r − w ; r + w]."""
    d_min, d_max = _radial_span(shape, cx, cy)
    lo, hi = r - RING_HALF_WIDTH_M, r + RING_HALF_WIDTH_M
    return lo - d_max if d_max < lo else d_min - hi if d_min > hi else 0.0


def ground_models(shapes: Dict[str, List[Tuple[Disc, Shape]]]) -> List[str]:
    """Modèles SOL présents dans le monde (GROUND_MODELS), ignorés comme obstacles."""
    return sorted(name for name in shapes if name in GROUND_MODELS)


def tour_of(name: str, shapes: Dict[str, List[Tuple[Disc, Shape]]]) -> Optional[Tuple[float, float, float]]:
    """(cx, cy, rayon de tour) AVANT les refus, ou None sans collision."""
    own = [d for d, _ in shapes.get(name, [])]
    if not own:
        return None
    x0, x1, y0, y1 = _bbox(own)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    r_obj = max(math.hypot(x - cx, y - cy) + e for x, y, e in own)
    return cx, cy, max(_ceil_tenth(r_obj + TOUR_CLEARANCE_M), TOUR_MIN_RADIUS_M)


def blockers(name: str, cx: float, cy: float, r: float,
             shapes: Dict[str, List[Tuple[Disc, Shape]]]) -> List[str]:
    """AUTRES modèles (hors sol) dont une collision est à < RING_MARGIN_M de l'anneau."""
    ground = set(ground_models(shapes))
    return sorted(other for other, items in shapes.items()
                  if other != name and other not in ground
                  and any(ring_clearance(s, cx, cy, r) < RING_MARGIN_M for _, s in items))


def compute_tours(sdf_path, route_path) -> Dict[str, Dict[str, float]]:
    """-> {poi: {x, y, rayon}} des POI qui ADMETTENT un tour (cf. règles)."""
    shapes = model_shapes(sdf_path)
    with open(route_path, encoding="utf-8") as f:
        pois = [p["name"] for p in (yaml.safe_load(f) or {}).get("pois", [])]
    tours: Dict[str, Dict[str, float]] = {}
    for name in pois:
        tour = tour_of(name, shapes)
        if tour is None:
            continue   # POI sans modèle (ou sans collision) : rien à contourner, pas de tour
        cx, cy, r = tour
        if r > TOUR_MAX_RADIUS_M or blockers(name, cx, cy, r, shapes):
            continue
        tours[name] = {"x": round(cx, 3), "y": round(cy, 3), "rayon": r}
    return tours


def render(tours: Dict[str, Dict[str, float]]) -> str:
    """Texte du fichier (en-tête + YAML trié)."""
    body = yaml.safe_dump(tours, sort_keys=True, allow_unicode=True, default_flow_style=None) if tours else "{}\n"
    return HEADER + body


def main(argv: List[str]) -> int:
    if len(argv) != 3:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    sys.stdout.write(render(compute_tours(argv[1], argv[2])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
