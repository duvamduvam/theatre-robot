"""Objets PROCHES de Didier (distance + côté) — logique PURE, testée sans ROS.

POURQUOI (séance du 15/11 21:29) : David regardait un objet à gauche (Didier
vers x ≈ 14 : table_basse, carrousel) ; le LLM a dit « le banc est là, bien en
vue » puis demandé le tour du banc, accepté à 22 m — Didier a roulé 22 m le
long de la route, David a cru qu'il « continuait la route ». Le chat ne
connaissait ni la distance ni la direction des objets : il confondait ce que
voit la caméra avec la liste. Le sélecteur (pose vérité terrain SIM-ONLY +
ancres de rehearsal/objects) publie donc les plus proches sur
jeu/objets_proches, que chat_node met dans le contexte du LLM.
"""
import math
from typing import Dict, List, Tuple

# Côté de l'objet vu de Didier (angle RELATIF, °, + = gauche, REP 103) :
# devant si |a| <= 45, gauche jusqu'à 135, droite jusqu'à -135, derrière sinon.
COTES = ("devant", "gauche", "droite", "derriere")
DEMI_SECTEUR_DEVANT_DEG = 45.0
LIMITE_DERRIERE_DEG = 135.0
# Les N plus proches suffisent (le prompt se paie à chaque tour).
N_PROCHES = 6


def cote(angle_deg: float) -> str:
    if abs(angle_deg) <= DEMI_SECTEUR_DEVANT_DEG:
        return "devant"
    if DEMI_SECTEUR_DEVANT_DEG < angle_deg <= LIMITE_DERRIERE_DEG:
        return "gauche"
    if -LIMITE_DERRIERE_DEG <= angle_deg < -DEMI_SECTEUR_DEVANT_DEG:
        return "droite"
    return "derriere"


def distance(pose: Tuple[float, float, float], xy: Tuple[float, float]) -> float:
    return math.hypot(xy[0] - pose[0], xy[1] - pose[1])


def objets_proches(pose, objets: Dict[str, Tuple[float, float]], n: int = N_PROCHES) -> List[dict]:
    """pose (x, y, cap rad) + {nom: (x, y)} -> les n plus proches, triés,
    [{"name", "distance_m" (0,1 m), "cote"}]. Pose inconnue -> []."""
    if pose is None:
        return []
    x, y, cap = pose
    out = []
    for nom, xy in objets.items():
        d = distance(pose, xy)
        rel = math.degrees(math.atan2(xy[1] - y, xy[0] - x) - cap)
        rel = (rel + 180.0) % 360.0 - 180.0
        out.append({"name": nom, "distance_m": round(d, 1), "cote": cote(rel)})
    out.sort(key=lambda o: (o["distance_m"], o["name"]))
    return out[:n]
