#!/usr/bin/env python3
"""Mesure des masques du lidar, du témoin de vie et de la couverture (spec A0 §4.2, §5.2, §8.3).

Le lidar voit le corps de Didier. Les secteurs correspondants se MESURENT en espace dégagé,
jamais ne se devinent. Deux temps, séparables (la capture exige ROS, l'analyse non) :

    # 1. capture : 100 balayages de `scan`, en JSON (sur le Pi, ou dans le conteneur `monde`)
    python3 mesurer_masques.py capturer --nombre 100 --topic /didier/scan > balayages.json
    # 2. analyse : masques, témoin, régions vues, extrait YAML pour corps_sur.yaml
    python3 mesurer_masques.py analyser balayages.json --pose 0.33 0 0 [--yaml]

Règles appliquées (spec §4.2, citées) :
  - MASQUE : « tout angle où un retour tombe dans la caisse gonflée de 5 cm sur 100 balayages
    est masqué, élargi de 2° de chaque côté » ;
  - TÉMOIN : auto-retours « stables (au moins 5 points, écart-type < 2 cm sur 100 balayages, à
    plus de 0,05 m) ». Choix de l'outil, écrits ici : un angle n'est « stable » que s'il revient
    dans AU MOINS 95 % des balayages ; le témoin est le plus long secteur CONTIGU d'angles
    stables ; sa bande de distance = [min des moyennes − 0,05 ; max des moyennes + 0,05] ;
    `points_min` = 80 % de ses points (arrondi au-dessous), jamais moins de 5 ;
  - COUVERTURE : `couverture.calculer_couverture` (logique du nœud, même code).

Toute la logique d'analyse est PURE (stdlib + didier_corps_sur) et testée
(test/test_mesurer_masques.py) ; rclpy n'est importé que par `capturer`.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# Outil lancé depuis le dépôt (PC) ou par chemin : le package voisin doit être importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GONFLAGE_CAISSE_M = 0.05      # « caisse gonflée de 5 cm »
ELARGISSEMENT_DEG = 2.0       # « élargi de 2° de chaque côté »
PRESENCE_STABLE = 0.95        # choix de l'outil (docstring)
TEMOIN_POINTS_MIN = 5
TEMOIN_ECART_TYPE_MAX_M = 0.02
TEMOIN_DISTANCE_MIN_M = 0.05
TEMOIN_BANDE_M = 0.05


@dataclass
class Balayage:
    """Le strict nécessaire d'un sensor_msgs/LaserScan, sérialisable en JSON."""
    angle_min: float
    angle_increment: float
    range_min: float
    range_max: float
    ranges: List[float]
    stamp: float = 0.0

    @staticmethod
    def depuis_dict(d: Dict) -> "Balayage":
        return Balayage(float(d["angle_min"]), float(d["angle_increment"]), float(d["range_min"]),
                        float(d["range_max"]), [float(r) for r in d["ranges"]], float(d.get("stamp", 0.0)))


@dataclass
class Resultat:
    masques_deg: List[List[float]]
    temoin: Dict
    couverture: Dict
    rayons: int
    angles_auto_retour: int
    champ_libre_deg: float
    notes: List[str] = field(default_factory=list)


def _norm_deg(a: float) -> float:
    """Angle en degrés ramené dans ]−180 ; 180]."""
    a = math.fmod(a, 360.0)
    if a <= -180.0:
        a += 360.0
    elif a > 180.0:
        a -= 360.0
    return a


def _fenetres_circulaires(indices: Sequence[int], n: int) -> List[Tuple[int, int]]:
    """Indices (triés, uniques) d'un tour de n rayons → fenêtres contiguës [début, fin] inclusives,
    la fenêtre qui traverse la couture n−1 → 0 étant recollée (début > fin)."""
    if not indices:
        return []
    s = sorted(set(indices))
    if len(s) == n:
        return [(0, n - 1)]
    fen: List[List[int]] = [[s[0], s[0]]]
    for i in s[1:]:
        if i == fen[-1][1] + 1:
            fen[-1][1] = i
        else:
            fen.append([i, i])
    if len(fen) > 1 and fen[0][0] == 0 and fen[-1][1] == n - 1:
        dernier = fen.pop()
        fen[0][0] = dernier[0]
    return [(a, b) for a, b in fen]


def _indices_en_masques(indices: Sequence[int], n: int, angle_min: float, inc: float) -> List[List[float]]:
    """Fenêtres d'indices → masques [début, fin] en degrés, élargis de 2° de chaque côté,
    normalisés dans ]−180 ; 180] (début > fin = le masque traverse ±180°), arrondis au 1/100°.
    Deux masques qui se chevauchent après élargissement sont fusionnés."""
    pas = math.degrees(inc)
    brut: List[Tuple[float, float]] = []
    for a, b in _fenetres_circulaires(indices, n):
        largeur = ((b - a) % n) * pas
        debut = math.degrees(angle_min) + a * pas - ELARGISSEMENT_DEG
        brut.append((debut, largeur + 2 * ELARGISSEMENT_DEG))
    if not brut:
        return []
    # Fusion sur le cercle : on déroule depuis le début du premier, en degrés continus.
    brut.sort()
    fusion: List[List[float]] = []
    for debut, largeur in brut:
        fin = debut + largeur
        if fusion and debut <= fusion[-1][1]:
            fusion[-1][1] = max(fusion[-1][1], fin)
        else:
            fusion.append([debut, fin])
    if len(fusion) > 1 and fusion[-1][1] - 360.0 >= fusion[0][0]:
        dernier = fusion.pop()
        fusion[0] = [dernier[0] - 360.0, max(fusion[0][1], dernier[1] - 360.0)]
    if any(f[1] - f[0] >= 360.0 for f in fusion):
        return [[-180.0, 180.0]]
    return [[round(_norm_deg(a), 2), round(_norm_deg(b), 2)] for a, b in fusion]


def analyser(balayages: Sequence[Balayage], caisse, pose, marge_arret_m: float = 0.60,
             part_aveugle_max: float = 0.10) -> Resultat:
    """Balayages en espace dégagé → masques, témoin, couverture. `caisse` : geometrie.Caisse ;
    `pose` : geometrie.PoseLidar. Aucune entrée ROS : testable sur le PC."""
    from didier_corps_sur import couverture, geometrie

    if not balayages:
        raise ValueError("aucun balayage")
    n = len(balayages[0].ranges)
    if any(len(b.ranges) != n for b in balayages):
        raise ValueError("balayages de tailles différentes : capture à refaire")
    ref = balayages[0]
    auto: set = set()
    mesures: Dict[int, List[float]] = {}
    for b in balayages:
        for i, r in enumerate(b.ranges):
            if not (math.isfinite(r) and b.range_min <= r <= b.range_max):
                continue
            angle = b.angle_min + i * b.angle_increment
            x, y = geometrie.point_dans_base(pose, angle, r)
            if geometrie.distance_caisse(caisse, x, y) <= GONFLAGE_CAISSE_M:
                auto.add(i)
                mesures.setdefault(i, []).append(r)
    masques = _indices_en_masques(sorted(auto), n, ref.angle_min, ref.angle_increment)

    # Témoin : angles d'auto-retour stables, puis le plus long secteur contigu.
    stables = []
    moyennes: Dict[int, float] = {}
    for i, rs in mesures.items():
        if len(rs) < PRESENCE_STABLE * len(balayages):
            continue
        m = statistics.fmean(rs)
        if m > TEMOIN_DISTANCE_MIN_M and statistics.pstdev(rs) < TEMOIN_ECART_TYPE_MAX_M:
            stables.append(i)
            moyennes[i] = m
    temoin: Dict = {"exige": False}
    meilleure = max(_fenetres_circulaires(stables, n), key=lambda f: (f[1] - f[0]) % n, default=None)
    if meilleure is not None:
        a, b = meilleure
        idx = [(a + k) % n for k in range(((b - a) % n) + 1)]
        if len(idx) >= TEMOIN_POINTS_MIN:
            pas = math.degrees(ref.angle_increment)
            d = [moyennes[i] for i in idx]
            temoin = {
                "exige": True,
                "secteur_deg": [round(_norm_deg(math.degrees(ref.angle_min) + a * pas), 2),
                                round(_norm_deg(math.degrees(ref.angle_min) + b * pas), 2)],
                "distance_m": [round(max(0.0, min(d) - TEMOIN_BANDE_M), 3), round(max(d) + TEMOIN_BANDE_M, 3)],
                "points_min": max(TEMOIN_POINTS_MIN, int(0.8 * len(idx))),
            }
    cov = couverture.calculer_couverture(caisse, pose, masques, marge_arret_m=marge_arret_m,
                                         part_aveugle_max=part_aveugle_max)
    masque_total = sum(((f - d) % 360.0) or 360.0 for d, f in masques)
    return Resultat(masques_deg=masques, temoin=temoin, couverture=cov, rayons=n,
                    angles_auto_retour=len(auto), champ_libre_deg=round(max(0.0, 360.0 - masque_total), 1))


def extrait_yaml(res: Resultat) -> str:
    """Les lignes à recopier dans corps_sur.yaml (masques et témoin)."""
    lignes = ["masques_deg:"] + ["  - [%s, %s]" % (a, b) for a, b in res.masques_deg]
    if not res.masques_deg:
        lignes = ["masques_deg: []"]
    t = res.temoin
    if t.get("exige"):
        lignes += ["temoin:", "  exige: true",
                   "  secteur_deg: [%s, %s]" % tuple(t["secteur_deg"]),
                   "  distance_m: [%s, %s]" % tuple(t["distance_m"]),
                   "  points_min: %d" % t["points_min"]]
    else:
        lignes += ["temoin:", "  exige: false   # aucun auto-retour stable : limite écrite (spec §4.2)"]
    return "\n".join(lignes)


# ----------------------------------------------------------------------------- capture (ROS)

def capturer(nombre: int, topic: str, delai_s: float) -> List[Dict]:
    """`nombre` balayages consécutifs de `topic` (QoS capteur, best effort). Importe rclpy ici seulement."""
    import time

    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import LaserScan

    rclpy.init()
    noeud = rclpy.create_node("mesurer_masques")
    recus: List[Dict] = []

    def sur_scan(m: LaserScan) -> None:
        if len(recus) < nombre:
            recus.append({"stamp": m.header.stamp.sec + m.header.stamp.nanosec * 1e-9,
                          "frame_id": m.header.frame_id, "angle_min": m.angle_min,
                          "angle_increment": m.angle_increment, "range_min": m.range_min,
                          "range_max": m.range_max,
                          "ranges": [r if math.isfinite(r) else None for r in m.ranges]})

    noeud.create_subscription(LaserScan, topic, sur_scan, qos_profile_sensor_data)
    limite = time.monotonic() + delai_s
    while len(recus) < nombre and time.monotonic() < limite:
        rclpy.spin_once(noeud, timeout_sec=0.2)
    noeud.destroy_node()
    rclpy.shutdown()
    if len(recus) < nombre:
        raise SystemExit("seulement %d balayages sur %d en %.0f s (topic %s)" % (len(recus), nombre, delai_s, topic))
    return recus


def charger(chemin: str) -> List[Balayage]:
    with open(chemin, encoding="utf-8") as f:
        brut = json.load(f)
    return [Balayage.depuis_dict({**d, "ranges": [math.inf if r is None else r for r in d["ranges"]]})
            for d in brut]


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sous = p.add_subparsers(dest="cmd", required=True)
    c = sous.add_parser("capturer", help="N balayages de scan → JSON (stdout)")
    c.add_argument("--nombre", type=int, default=100)
    c.add_argument("--topic", default="scan")
    c.add_argument("--delai", type=float, default=60.0, help="secondes au plus")
    a = sous.add_parser("analyser", help="JSON de balayages → masques, témoin, couverture")
    a.add_argument("fichier")
    a.add_argument("--pose", nargs=3, type=float, metavar=("X", "Y", "LACET_RAD"), required=True)
    a.add_argument("--yaml", action="store_true", help="n'afficher que l'extrait YAML")
    args = p.parse_args(argv)
    if args.cmd == "capturer":
        json.dump(capturer(args.nombre, args.topic, args.delai), sys.stdout)
        return 0
    from didier_corps_sur import geometrie
    res = analyser(charger(args.fichier), geometrie.Caisse(), geometrie.PoseLidar(*args.pose))
    if args.yaml:
        print(extrait_yaml(res))
    else:
        print(json.dumps({"rayons": res.rayons, "angles_auto_retour": res.angles_auto_retour,
                          "champ_libre_deg": res.champ_libre_deg, "masques_deg": res.masques_deg,
                          "temoin": res.temoin, "couverture": res.couverture}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
