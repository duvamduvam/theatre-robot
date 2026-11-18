"""Ce que le lidar ne voit pas : régions vues / aveugles (spec A0 §5.2) — PUR.

La BANDE D'ARRÊT = la zone d'arrêt moins la caisse : les points à une
`distance_caisse` strictement comprise entre 0 et `marge_arret_m`. Elle est
échantillonnée sur une grille de pas `pas_m`, aux CENTRES des cases : x = (i + ½)·pas,
y = (j + ½)·pas dans `base_link`. Ce décalage d'un demi-pas évite qu'un
échantillon tombe pile sur un bord de la caisse (0,30 ; −0,57 ; ±0,40 sont des
multiples de 5 cm) et rend la grille symétrique en y (y = 0 n'est jamais
échantillonné : les deux flancs se partagent proprement).

Quatre régions, définies comme la spec les écrit, coins compris :
- AVANT : x > x_avant (les deux coins avant arrondis y sont) ;
- ARRIERE : x < x_arriere (les deux coins arrière y sont) ;
- FLANC_G / FLANC_D : x_arriere ≤ x ≤ x_avant, selon le signe de y.

Un échantillon est AVEUGLE si son relèvement vu du lidar (dans `laser_frame`,
donc lacet retranché) tombe dans un masque (convention de `balayage`). Seuls les
masques comptent : la portée minimale (5 cm autour du capteur) et l'ombre du
corps ne sont pas modélisées — l'ombre du corps est précisément ce que les
masques mesurés recouvrent. Une région est VUE si sa part aveugle est ≤
`part_aveugle_max`. Une région sans aucun échantillon est comptée aveugle.
"""
import math
from typing import TypedDict

from didier_corps_sur.balayage import dans_masque
from didier_corps_sur.geometrie import Caisse, PoseLidar, distance_caisse

AVANT = "avant"
ARRIERE = "arriere"
FLANC_G = "flanc_g"
FLANC_D = "flanc_d"
REGIONS = (AVANT, ARRIERE, FLANC_G, FLANC_D)


class RegionCouverte(TypedDict):
    """Un dict, pour être sérialisable en JSON tel quel (état, outils)."""
    part_aveugle: float
    vue: bool
    echantillons: int
    aveugles: int


def region_de(caisse: Caisse, x: float, y: float) -> str:
    """Région d'un point de la bande (coins → AVANT / ARRIERE)."""
    if x > caisse.x_avant:
        return AVANT
    if x < caisse.x_arriere:
        return ARRIERE
    return FLANC_G if y > 0 else FLANC_D


def relevement_deg(pose: PoseLidar, x: float, y: float) -> float:
    """Angle du point vu du lidar, dans `laser_frame`, en degrés."""
    return math.degrees(math.atan2(y - pose.y, x - pose.x) - pose.lacet_rad)


def calculer_couverture(caisse: Caisse, pose: PoseLidar,
                        masques_deg: tuple[tuple[float, float], ...] | list[list[float]],
                        marge_arret_m: float = 0.60, pas_m: float = 0.05,
                        part_aveugle_max: float = 0.10) -> dict[str, RegionCouverte]:
    """{"avant"|"arriere"|"flanc_g"|"flanc_d": {"part_aveugle", "vue",
    "echantillons", "aveugles"}}, dans l'ordre de REGIONS (sérialisable en JSON)."""
    if not pas_m > 0:
        raise ValueError(f"couverture : pas_m doit être > 0 (reçu {pas_m})")
    masques = tuple((float(m[0]), float(m[1])) for m in masques_deg)
    total = dict.fromkeys(REGIONS, 0)
    aveugles = dict.fromkeys(REGIONS, 0)
    # Indices couvrant la boîte englobante de la zone d'arrêt, avec une case de rab.
    i_min = math.floor((caisse.x_arriere - marge_arret_m) / pas_m) - 1
    i_max = math.ceil((caisse.x_avant + marge_arret_m) / pas_m) + 1
    j_max = math.ceil((caisse.demi_largeur + marge_arret_m) / pas_m) + 1
    for i in range(i_min, i_max + 1):
        x = (i + 0.5) * pas_m
        for j in range(-j_max - 1, j_max + 1):
            y = (j + 0.5) * pas_m
            d = distance_caisse(caisse, x, y)
            if not 0.0 < d < marge_arret_m:
                continue
            region = region_de(caisse, x, y)
            total[region] += 1
            if dans_masque(relevement_deg(pose, x, y), masques):
                aveugles[region] += 1
    resultat = {}
    for region in REGIONS:
        n = total[region]
        part = aveugles[region] / n if n else 1.0
        resultat[region] = RegionCouverte(part_aveugle=part, vue=part <= part_aveugle_max,
                                          echantillons=n, aveugles=aveugles[region])
    return resultat


def vue_de(couverture: dict[str, RegionCouverte]) -> dict[str, bool]:
    """{région: vue} — la forme publiée dans l'état (§5.7) et lue par `filtre`."""
    return {region: couverture[region]["vue"] for region in REGIONS}
