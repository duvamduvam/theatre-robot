"""Lecture du YAML du corps sûr et BORNES DURES (spec A0 §5.6) — PyYAML seulement.

Un fichier incomplet, mal typé ou hors bornes est REFUSÉ (le nœud ne démarre
pas : plus aucune sortie, donc aucun mouvement autonome). Aucune valeur par
défaut cachée dans le code : tout chiffre vit dans le YAML. Une configuration
ne peut qu'être PLUS STRICTE que la décision ; les huit bornes de la spec sont
`BORNES_DURES`, les autres contrôles ne refusent que l'absurde (signes, types,
intervalles vides), jamais une valeur plus prudente.

Le domaine ROS est passé en argument (le nœud lit ROS_DOMAIN_ID) : ce module ne
lit pas l'environnement.
"""
import math
from dataclasses import dataclass
from typing import Any

import yaml

from didier_corps_sur.balayage import ParametresBalayage, Temoin
from didier_corps_sur.filtre import CANAUX, ParametresFiltre, Plafond
from didier_corps_sur.garde import ParametresGarde
from didier_corps_sur.geometrie import Caisse, PoseLidar, invariant_pivot
from didier_corps_sur.zones import ParametresZones

TERRAINS = ("sim", "reel")
DOMAINE_SIM = "43"
# Les huit bornes dures du §5.6 (valeurs de la décision ; écrites aussi en dur
# dans test/test_reglages.py).
MARGE_ARRET_MIN_M = 0.60
ECART_RALENTI_MIN_M = 0.30
CAPTEUR_PERIME_MAX_S = 0.30
SUPERVISEUR_PERIME_MAX_S = 1.0
FACTEUR_RALENTI_MAX = 0.5
V_MAX_MAX = 0.9
PART_AVEUGLE_MAX_MAX = 0.10
# Tolérance des comparaisons de bornes : 0,60 + 0,30 vaut 0,8999999999999999.
EPS = 1e-9


class ReglagesError(ValueError):
    """Configuration refusée — le message dit quel réglage et pourquoi."""


@dataclass(frozen=True)
class Reglages:
    terrain: str
    caisse: Caisse
    lidar: PoseLidar
    hauteur_plan_m: float
    balayage: ParametresBalayage
    zones: ParametresZones
    part_aveugle_max: float
    filtre: ParametresFiltre
    garde: ParametresGarde


def _get(data: Any, chemin: str) -> Any:
    node = data
    for cle in chemin.split("."):
        if not isinstance(node, dict) or cle not in node:
            raise ReglagesError(f"réglage manquant : {chemin}")
        node = node[cle]
    return node


def _nombre(data: Any, chemin: str) -> float:
    valeur = _get(data, chemin)
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)) or not math.isfinite(valeur):
        raise ReglagesError(f"{chemin} : nombre fini attendu (reçu {valeur!r})")
    return float(valeur)


def _entier(data: Any, chemin: str) -> int:
    valeur = _get(data, chemin)
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        raise ReglagesError(f"{chemin} : entier attendu (reçu {valeur!r})")
    return valeur


def _booleen(data: Any, chemin: str) -> bool:
    valeur = _get(data, chemin)
    if not isinstance(valeur, bool):
        raise ReglagesError(f"{chemin} : booléen attendu (reçu {valeur!r})")
    return valeur


def _paire(valeur: Any, chemin: str) -> tuple[float, float]:
    if (not isinstance(valeur, (list, tuple)) or len(valeur) != 2
            or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
                   for x in valeur)):
        raise ReglagesError(f"{chemin} : paire [a, b] de nombres finis attendue (reçu {valeur!r})")
    return float(valeur[0]), float(valeur[1])


def _exiger(condition: bool, message: str) -> None:
    if not condition:
        raise ReglagesError(message)


def reglages_depuis(data: Any, ros_domain_id: str | None) -> Reglages:
    """dict (YAML lu) + domaine ROS → Reglages, ou ReglagesError."""
    _exiger(isinstance(data, dict), "corps_sur : dictionnaire attendu à la racine")
    terrain = _get(data, "terrain")
    _exiger(terrain in TERRAINS, f"terrain : attendu parmi {TERRAINS} (reçu {terrain!r})")
    # Borne dure 8 : la conf de sim ne tourne qu'en domaine 43.
    _exiger(terrain != "sim" or ros_domain_id == DOMAINE_SIM,
            f"terrain sim refusé hors ROS_DOMAIN_ID={DOMAINE_SIM} (reçu {ros_domain_id!r})")

    caisse = Caisse(*(_nombre(data, f"caisse.{c}") for c in
                      ("x_avant", "x_arriere", "demi_largeur", "x_essieu", "rayon_balayage")))
    _exiger(caisse.x_arriere < caisse.x_avant, "caisse : x_arriere doit être < x_avant")
    _exiger(caisse.demi_largeur > 0 and caisse.rayon_balayage > 0,
            "caisse : demi_largeur et rayon_balayage doivent être > 0")
    lidar = PoseLidar(_nombre(data, "lidar.x"), _nombre(data, "lidar.y"), _nombre(data, "lidar.lacet_rad"))
    hauteur = _nombre(data, "lidar.hauteur_plan_m")
    masques_bruts = _get(data, "lidar.masques_deg")
    _exiger(isinstance(masques_bruts, list), "lidar.masques_deg : liste de [debut, fin] attendue")
    masques = tuple(_paire(m, f"lidar.masques_deg[{i}]") for i, m in enumerate(masques_bruts))

    exige_temoin = _booleen(data, "lidar.temoin.exige")
    if exige_temoin:
        secteur = _paire(_get(data, "lidar.temoin.secteur_deg"), "lidar.temoin.secteur_deg")
        distance = _paire(_get(data, "lidar.temoin.distance_m"), "lidar.temoin.distance_m")
        points_min = _entier(data, "lidar.temoin.points_min")
        _exiger(0 < distance[0] < distance[1], "lidar.temoin.distance_m : 0 < min < max attendu")
        _exiger(points_min >= 1, "lidar.temoin.points_min : au moins 1")
    else:
        secteur, distance, points_min = (0.0, 0.0), (0.0, 0.0), 0
    temoin = Temoin(exige_temoin, secteur, distance, points_min)

    balayage = ParametresBalayage(
        portee_min_m=_nombre(data, "balayage.portee_min_m"),
        portee_max_m=_nombre(data, "balayage.portee_max_m"),
        rayons_min=_entier(data, "balayage.rayons_min"),
        age_max_reception_s=_nombre(data, "balayage.age_max_reception_s"),
        masques_deg=masques, temoin=temoin)
    _exiger(0 <= balayage.portee_min_m < balayage.portee_max_m,
            "balayage : 0 ≤ portee_min_m < portee_max_m attendu")
    _exiger(balayage.rayons_min >= 1, "balayage.rayons_min : au moins 1")
    _exiger(balayage.age_max_reception_s > 0, "balayage.age_max_reception_s : > 0 attendu")

    zones = ParametresZones(
        marge_arret_m=_nombre(data, "zones.marge_arret_m"),
        marge_ralenti_m=_nombre(data, "zones.marge_ralenti_m"),
        hysteresis_m=_nombre(data, "zones.hysteresis_m"),
        balayages_de_sortie=_entier(data, "zones.balayages_de_sortie"))
    # Bornes dures 1 et 2.
    _exiger(zones.marge_arret_m >= MARGE_ARRET_MIN_M - EPS,
            f"zones.marge_arret_m : au moins {MARGE_ARRET_MIN_M} m (reçu {zones.marge_arret_m})")
    _exiger(zones.marge_ralenti_m >= zones.marge_arret_m + ECART_RALENTI_MIN_M - EPS,
            f"zones.marge_ralenti_m : au moins marge_arret_m + {ECART_RALENTI_MIN_M} m "
            f"(reçu {zones.marge_ralenti_m})")
    _exiger(zones.hysteresis_m >= 0, "zones.hysteresis_m : ≥ 0 attendu")
    _exiger(zones.balayages_de_sortie >= 1, "zones.balayages_de_sortie : au moins 1")

    facteur = _nombre(data, "zones.facteur_ralenti")
    # Borne dure 5 (un facteur négatif inverserait le sens : refusé aussi).
    _exiger(0 <= facteur <= FACTEUR_RALENTI_MAX + EPS,
            f"zones.facteur_ralenti : entre 0 et {FACTEUR_RALENTI_MAX} (reçu {facteur})")

    part = _nombre(data, "couverture.part_aveugle_max")
    # Borne dure 7.
    _exiger(0 <= part <= PART_AVEUGLE_MAX_MAX + EPS,
            f"couverture.part_aveugle_max : au plus {PART_AVEUGLE_MAX_MAX} (reçu {part})")
    w_aveugle = _nombre(data, "couverture.w_max_aveugle")
    _exiger(w_aveugle > 0, "couverture.w_max_aveugle : > 0 attendu")

    plafonds = {}
    for canal in CANAUX:
        v_max = _nombre(data, f"canaux.{canal}.v_max")
        w_max = _nombre(data, f"canaux.{canal}.w_max")
        # Borne dure 6 (un plafond ≤ 0 inverserait ou figerait le sens : refusé).
        _exiger(0 < v_max <= V_MAX_MAX + EPS,
                f"canaux.{canal}.v_max : au plus {V_MAX_MAX} m/s et > 0 (reçu {v_max})")
        _exiger(w_max > 0, f"canaux.{canal}.w_max : > 0 attendu (reçu {w_max})")
        plafonds[canal] = Plafond(v_max, w_max)
    filtre = ParametresFiltre(plafonds, facteur, w_aveugle,
                              _booleen(data, "couverture.angulaire_aveugle_autorise"))

    garde = ParametresGarde(
        capteur_perime_s=_nombre(data, "capteur.perime_s"),
        sante_s=_nombre(data, "capteur.sante_s"),
        superviseur_exige=_booleen(data, "superviseur.exige"),
        superviseur_perime_s=_nombre(data, "superviseur.perime_s"),
        duree_max_mouvement_s=_nombre(data, "duree.duree_max_mouvement_s"),
        pause_s=_nombre(data, "duree.pause_s"))
    # Bornes dures 3 et 4.
    _exiger(0 < garde.capteur_perime_s <= CAPTEUR_PERIME_MAX_S + EPS,
            f"capteur.perime_s : au plus {CAPTEUR_PERIME_MAX_S} s (reçu {garde.capteur_perime_s})")
    _exiger(0 < garde.superviseur_perime_s <= SUPERVISEUR_PERIME_MAX_S + EPS,
            f"superviseur.perime_s : au plus {SUPERVISEUR_PERIME_MAX_S} s "
            f"(reçu {garde.superviseur_perime_s})")
    _exiger(garde.sante_s >= 0, "capteur.sante_s : ≥ 0 attendu")
    _exiger(garde.duree_max_mouvement_s >= 0 and garde.pause_s >= 0,
            "duree : duree_max_mouvement_s et pause_s ≥ 0 attendus (0 = durée non bornée)")

    # Invariant du pivot (§4.1) : refus d'une caisse qui balaierait hors de la zone d'arrêt.
    respecte, ecart = invariant_pivot(caisse, zones.marge_arret_m)
    _exiger(respecte, f"invariant du pivot violé : le disque balayé sort de {ecart:.3f} m de la caisse, "
                      f"au plus {zones.marge_arret_m - 0.05:.3f} m admis")

    return Reglages(terrain, caisse, lidar, hauteur, balayage, zones, part, filtre, garde)


def charger_reglages(chemin: str, ros_domain_id: str | None) -> Reglages:
    """Fichier YAML → Reglages ; fichier absent ou illisible → ReglagesError."""
    try:
        with open(chemin, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        raise ReglagesError(f"corps_sur : fichier de configuration illisible {chemin} ({e})") from e
    return reglages_depuis(data, ros_domain_id)
