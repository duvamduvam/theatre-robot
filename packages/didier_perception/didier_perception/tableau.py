"""L'ÉCRIVAIN du tableau des objets — logique PURE (aucun import ROS), testée sans ROS.

Lot O0 (18/11), étude docs/etudes/etude-objets-vus-et-carte.md §6. Le contrat (forme d'un
objet, encodage, résolution d'un nom) est dans theatre_contrats.objets ; ici, ce que SEUL
l'écrivain calcule et que les lecteurs ne refont jamais :
  - la FUSION des sources : la carte (régie, `rehearsal/objects`) et, à partir d'O2, la caméra
    (un objet vu près d'un objet de carte de nom compatible EST cet objet ; la position de la
    carte gagne, la caméra apporte « je le vois ») — « près » : distance au CENTRE de l'objet de
    carte STRICTEMENT inférieure à max(2·sigma_m, emprise + 1 m), emprise inconnue = 1 m
    (EMPRISE_FUSION_DEFAUT_M) ; cf. observer ;
  - le NOM UNIQUE à un instant (deux bancs : « banc » le plus proche, « banc 2 ») ;
  - la PÉREMPTION des objets vus (§6.4) : une vieille position est pire qu'aucune ;
  - la géométrie vue de Didier MAINTENANT (distance, azimut, côté, « dans le champ ») ;
  - la règle `atteignable` (§6.5), à un seul endroit.
Horloge injectée (secondes, monotone) : aucun sleep dans les tests.
"""
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from theatre_contrats import objets as contrat
from theatre_contrats.objets import Objet, Pose, normaliser_nom

# Champ horizontal de la caméra, demi-angle (°) : 60° en sim (dadou_robot_gz.urdf.xacro,
# §2.2). Webcam réelle non mesurée (lot O4) : paramètre du nœud.
CHAMP_DEMI_DEG = 30.0
# Au-delà, un objet « dans l'axe » n'est plus EN VUE : à 15 m il reste moins de 40 lignes
# sous l'horizon (§4.3, la distance projetée y est jetée) et, sur la carte, rien ne dit qu'il
# n'est pas caché. C'est ce qui fait du banc à 22 m de la séance du 15/11 un « pas ici ».
VUE_MAX_M = 15.0
# Un objet VU est « en vue » s'il a été observé il y a moins de 3 s (§6.2), cible possible
# s'il l'a été il y a moins de 10 s (§6.5).
EN_VUE_VU_S = 3.0
ATTEIGNABLE_VU_S = 10.0
# Incertitude : cible si ≤ 1 m (§6.5) ; au-delà de 2 m l'objet vu tombe (§6.4).
SIGMA_ATTEIGNABLE_M = 1.0
SIGMA_MAX_M = 2.0
# Croissance de sigma : 5 % de la distance parcourue depuis l'observation (§6.4).
SIGMA_PAR_METRE = 0.05
# Fin de vie d'un objet vu : non revu depuis 120 s (§6.4).
VU_PEREMPTION_S = 120.0
# Repère `robot` (robot sans odométrie) : la position tombe au premier mouvement, le nom
# reste 30 s pour la parole (« le vélo qu'on a croisé »), jamais une cible (§6.4).
NOM_APRES_MOUVEMENT_S = 30.0
# Rapprochement vu ↔ vu (même objet revu) : à moins de max(2·sigma, 1 m).
MEME_VU_M = 1.0
# Rapprochement vu ↔ carte (§6.3) : à moins de max(2·sigma, emprise + FUSION_MARGE_M) du centre ;
# emprise de l'objet de carte inconnue (POI sans géométrie de collision) -> celle-ci (m). Ne sert
# QU'À la fusion : la distance d'arrêt d'un « aller voir » a sa propre borne prudente (régie).
FUSION_MARGE_M = 1.0
EMPRISE_FUSION_DEFAUT_M = 1.0


def sigma_creation(distance_m: float, hauteur_m: float, sigma_inclinaison_deg: float) -> float:
    """Écart-type (m) d'un objet vu à sa création (§6.4) : max(0,3 m ; 4 % de d) — le p90 du
    banc de mesure, question « pied » — plus d²/h × σ_inclinaison (rad). σ_inclinaison vaut 0
    en sim, 0,5° visé après la calibration O4 (+0,3 m à 6 m, +0,8 m à 10 m)."""
    d = max(0.0, distance_m)
    return max(0.3, 0.04 * d) + d * d / hauteur_m * math.radians(sigma_inclinaison_deg)


def azimut_relatif(pose: Pose, x: float, y: float) -> float:
    """Azimut (°, + = gauche, dans [-180, 180[) du point (x, y) vu de la pose."""
    rel = math.degrees(math.atan2(y - pose.y, x - pose.x)) - pose.cap_deg
    return (rel + 180.0) % 360.0 - 180.0


@dataclass(frozen=True)
class ObjetCarte:
    """Un objet de la carte (POI de la régie) : `x`, `y` = CENTRE de l'objet quand la
    géométrie de collision est connue (fichier des tours), sinon l'ancre du POI ; `emprise_m` =
    rayon d'emprise au sol autour de ce centre (majorant de la collision), None = inconnue."""
    nom: str
    x: float
    y: float
    desc: str = ""
    alias: Tuple[str, ...] = ()
    tour: bool = False
    emprise_m: Optional[float] = None

    @property
    def id(self) -> str:
        # Stable tant que la carte ne change pas : la régie le relie à SON POI (tours).
        return "carte/" + self.nom


@dataclass
class _Vu:
    id: str
    nom: str
    repere: str
    x: Optional[float]
    y: Optional[float]
    sigma_m: float
    t_obs: float
    t_mouvement: Optional[float] = None    # repère robot : instant où la position est tombée


def _compatible(etiquette: str, cles) -> bool:
    """Une étiquette d'inventaire (« banc en bois ») désigne-t-elle un objet de clés `cles`
    (« banc », « banc en bois ») ? Égalité normalisée, ou une clé contenue MOT POUR MOT."""
    e = normaliser_nom(etiquette)
    return bool(e) and any(e == k or f" {k} " in f" {e} " for k in cles)


class TableauObjets:
    """État de l'écrivain. Appels : poser_carte, poser_pose, observer, deplacement ; puis
    instantane(t) rend les objets à publier (et purge ce qui est périmé)."""

    def __init__(self, champ_demi_deg: float = CHAMP_DEMI_DEG, vue_max_m: float = VUE_MAX_M):
        self.champ_demi_deg = champ_demi_deg
        self.vue_max_m = vue_max_m
        self.carte: Dict[str, ObjetCarte] = {}
        self.pose: Optional[Pose] = None
        self.vus: Dict[str, _Vu] = {}
        self._vu_carte: Dict[str, float] = {}     # id de carte -> dernière observation caméra
        self._n = 0

    # --- sources ----------------------------------------------------------
    def poser_carte(self, objets: List[ObjetCarte]) -> None:
        """Remplace la carte (rehearsal/objects est latché : chaque message est la carte entière)."""
        self.carte = {o.id: o for o in objets}
        self._vu_carte = {k: v for k, v in self._vu_carte.items() if k in self.carte}

    def poser_pose(self, repere: str, x: float, y: float, cap_rad: float) -> None:
        self.pose = Pose(repere, x, y, math.degrees(cap_rad))

    def oublier_pose(self) -> None:
        self.pose = None

    def observer(self, etiquette: str, repere: str, x: float, y: float, sigma_m: float, t: float) -> str:
        """Un objet vu par la caméra (O2), position déjà projetée au sol dans `repere`. Rend
        l'`id` de l'objet du tableau qu'il crée, confirme ou rejoint. Fusion avec un objet de
        carte de nom compatible si la distance à son centre est STRICTEMENT inférieure à
        max(2·sigma_m, emprise + FUSION_MARGE_M) (emprise inconnue : EMPRISE_FUSION_DEFAUT_M)."""
        if repere != "robot":
            for o in self.carte.values():
                if repere != "monde":
                    break     # la carte est en repère monde : pas de comparaison sans transformée
                emprise = o.emprise_m if o.emprise_m is not None else EMPRISE_FUSION_DEFAUT_M
                seuil = max(2.0 * sigma_m, emprise + FUSION_MARGE_M)
                if _compatible(etiquette, {normaliser_nom(t_) for t_ in (o.nom,) + o.alias}) \
                        and math.hypot(o.x - x, o.y - y) < seuil:
                    self._vu_carte[o.id] = t
                    return o.id
        for v in self.vus.values():
            if v.repere == repere and v.x is not None and v.y is not None \
                    and _compatible(etiquette, {normaliser_nom(v.nom)}) \
                    and math.hypot(v.x - x, v.y - y) < max(2.0 * sigma_m, MEME_VU_M):
                v.x, v.y, v.sigma_m, v.t_obs, v.t_mouvement = x, y, sigma_m, t, None
                return v.id
        self._n += 1
        id_ = f"vu/{self._n}"
        self.vus[id_] = _Vu(id_, etiquette.strip(), repere, x, y, sigma_m, t)
        return id_

    def deplacement(self, distance_m: float, t: float) -> None:
        """Le robot a roulé de `distance_m` (> 0) : sigma des objets vus grandit ; en repère
        robot, la position tombe (le nom reste NOM_APRES_MOUVEMENT_S)."""
        if distance_m <= 0:
            return
        for v in self.vus.values():
            if v.repere == "robot":
                if v.x is not None:
                    v.x = v.y = None
                    v.t_mouvement = t
            else:
                v.sigma_m += SIGMA_PAR_METRE * distance_m

    # --- publication ------------------------------------------------------
    def _purger(self, t: float) -> None:
        for id_ in [k for k, v in self.vus.items()
                    if t - v.t_obs > VU_PEREMPTION_S or v.sigma_m > SIGMA_MAX_M
                    or (v.t_mouvement is not None and t - v.t_mouvement > NOM_APRES_MOUVEMENT_S)]:
            del self.vus[id_]

    def _geometrie(self, repere: str, x, y):
        """(distance, azimut) vus de Didier maintenant, ou (None, None)."""
        if x is None:
            return None, None
        if repere == "robot":       # x devant, y à gauche, relatif au robot à l'observation
            return math.hypot(x, y), math.degrees(math.atan2(y, x))
        if self.pose is None or self.pose.repere != repere:
            return None, None
        return math.hypot(x - self.pose.x, y - self.pose.y), azimut_relatif(self.pose, x, y)

    def _dans_le_champ(self, distance, azimut) -> bool:
        return distance is not None and distance <= self.vue_max_m and abs(azimut) <= self.champ_demi_deg

    def instantane(self, t: float) -> List[Objet]:
        """Objets à publier, triés par distance (inconnue en dernier), noms rendus uniques."""
        self._purger(t)
        bruts = []
        for o in self.carte.values():
            d, a = self._geometrie("monde", o.x, o.y)
            vu_t = self._vu_carte.get(o.id)
            age = None if vu_t is None else max(0.0, t - vu_t)
            en_vue = self._dans_le_champ(d, a) or (age is not None and age < EN_VUE_VU_S)
            bruts.append(dict(id=o.id, nom=o.nom, desc=o.desc, alias=o.alias,
                              sources=("carte", "vu") if age is not None else ("carte",),
                              repere="monde", x=o.x, y=o.y, sigma_m=0.0, distance=d, azimut=a,
                              en_vue=en_vue, age=age, tour=o.tour, emprise=o.emprise_m))
        for v in self.vus.values():
            d, a = self._geometrie(v.repere, v.x, v.y)
            age = max(0.0, t - v.t_obs)
            bruts.append(dict(id=v.id, nom=v.nom, desc="", alias=(), sources=("vu",), repere=v.repere,
                              x=v.x, y=v.y, sigma_m=v.sigma_m, distance=d, azimut=a,
                              en_vue=age < EN_VUE_VU_S and v.x is not None, age=age, tour=False,
                              emprise=None))
        bruts.sort(key=lambda b: (b["distance"] if b["distance"] is not None else math.inf, b["id"]))
        noms = _noms_uniques([b["nom"] for b in bruts])
        sortie = []
        for b, nom in zip(bruts, noms):
            d, a = b["distance"], b["azimut"]
            atteignable = (b["repere"] in ("monde", "odom") and b["x"] is not None and d is not None
                           and b["sigma_m"] <= SIGMA_ATTEIGNABLE_M and d <= contrat.PORTEE_M
                           and ("carte" in b["sources"] or b["age"] < ATTEIGNABLE_VU_S))
            sortie.append(Objet(
                id=b["id"], nom=nom, desc=b["desc"], alias=tuple(b["alias"]), sources=b["sources"],
                repere=b["repere"], x=_arrondi(b["x"], 3), y=_arrondi(b["y"], 3),
                sigma_m=round(b["sigma_m"], 2), emprise_m=_arrondi(b["emprise"], 2), azimut_deg=_arrondi(a, 1), distance_m=_arrondi(d, 1),
                cote=None if a is None else contrat.cote(a), en_vue=b["en_vue"],
                vu_il_y_a_s=_arrondi(b["age"], 1), tour=b["tour"], atteignable=atteignable))
        return sortie


def _arrondi(v, n):
    return None if v is None else round(v, n)


def _noms_uniques(noms: List[str]) -> List[str]:
    """Noms dans l'ordre reçu (déjà trié par distance) : le premier d'une même clé normalisée
    garde son nom, les suivants prennent « 2 », « 3 »… (§6.2 : « banc », « banc 2 »)."""
    vus: Dict[str, int] = {}
    sortie = []
    for nom in noms:
        cle = normaliser_nom(nom)
        vus[cle] = vus.get(cle, 0) + 1
        sortie.append(nom if vus[cle] == 1 else f"{nom} {vus[cle]}")
    return sortie


# ================================================================ source « carte »
def carte_depuis_payload(valeur) -> List[ObjetCarte]:
    """Payload décodé de `rehearsal/objects` (liste, director.objects_payload) -> objets de carte.
    Position : le CENTRE (`cx`, `cy`, géométrie de collision des tours) s'il est donné, sinon
    l'ancre (`x`, `y`) ; `emprise` (m, > 0) = rayon d'emprise autour du centre, absent ou faux =
    inconnue. Un élément illisible est sauté ; ValueError si ce n'est pas une liste."""
    if not isinstance(valeur, list):
        raise ValueError(f"rehearsal/objects : liste attendue, reçu {valeur!r:.80}")
    sortie, noms = [], set()
    for d in valeur:
        if not isinstance(d, dict) or not isinstance(d.get("name"), str) or not d["name"].strip():
            continue
        nom = d["name"].strip()
        x, y = _fini(d.get("cx", d.get("x"))), _fini(d.get("cy", d.get("y")))
        if x is None or y is None or nom in noms:
            continue
        noms.add(nom)
        alias = d.get("alias")
        emprise = _fini(d.get("emprise"))
        sortie.append(ObjetCarte(
            nom=nom, x=x, y=y, desc=d["desc"].strip() if isinstance(d.get("desc"), str) else "",
            alias=tuple(a for a in alias if isinstance(a, str) and a.strip()) if isinstance(alias, list) else (),
            tour=d.get("tour") is True, emprise_m=emprise if emprise is not None and emprise > 0 else None))
    return sortie


def _fini(v) -> Optional[float]:
    """Même règle que le décodeur du contrat (jamais d'OverflowError : revue O1, 19/11)."""
    return contrat.nombre_fini(v)
