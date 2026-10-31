"""Logique PURE du cheminement de Didier dans la rue simulée (stdlib seulement).

Trois objets, aucun ROS :
  - load_route(dict) -> Route : lecture + VALIDATION d'un itinéraire (refus
    explicite RouteError, jamais de valeur devinée) ;
  - RouteFollower : suit la polyligne point par point, borné, lissé, et retombe
    à ZÉRO FRANC dès que quelque chose manque (désactivé, pas de pose,
    odométrie périmée, arrivé) ;
  - PoiWatcher : événements enter/exit à hystérésis autour des points
    d'intérêt (lampadaire, boulangerie, hangar...) — la matière des lubies ;
  - normalize_name / nearest_ahead_index (lot M1 « aller voir ») : la clé de
    correspondance des objets nommés par David, et l'index de REPRISE de
    l'itinéraire après une manœuvre.

POURQUOI un suivi de waypoints et pas un pure pursuit : la polyligne d'un
trottoir est douce, le robot roule à 0,4 m/s, et la simplicité se teste
(valeurs gravées dans test_route_follower.py). Pas d'évitement d'obstacle :
se bloquer sur le chien ou la terrasse EST une scène (étude §2).
"""
from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from robot_rehearsal.contracts import ABS_MAX_ANG, ABS_MAX_LIN, POI_EXIT_FACTOR


class RouteError(ValueError):
    """Itinéraire invalide — le message dit QUOI et OÙ (clé, index)."""


@dataclass(frozen=True)
class Poi:
    name: str
    x: float
    y: float
    radius: float
    # Lot R3, optionnels : `lubie` = consigne de jeu envoyée telle quelle au
    # chat par le régisseur (type de panne `lubie` sans `text`) ; `fermeture`
    # = indice de mise en scène, lu par PERSONNE en machine (débrief, écriture).
    lubie: str = ""
    fermeture: str = ""
    # Lot M1 « aller voir », optionnels : `desc` = ce qu'on VOIT (≤ DESC_MAX_WORDS
    # mots, envoyé à chat_node dans rehearsal/objects ; vide = le nom, cf.
    # Poi.shown_desc) ; `alias` = mots que David peut dire pour le désigner.
    desc: str = ""
    alias: Tuple[str, ...] = ()

    @property
    def shown_desc(self) -> str:
        """Description publiée : `desc`, sinon le nom (spec §2.1 « absent ->
        desc = nom »). Stockée vide pour qu'un POI sans desc reste égal à
        Poi(name, x, y, radius) — l'absence est une information."""
        return self.desc or self.name


# Plafond de mots d'une `desc` (spec §2.1) : elle part dans le prompt de
# chat_node pour CHAQUE objet, trente fois — une phrase longue le noierait.
DESC_MAX_WORDS = 6

# Articles retirés EN TÊTE par normalize_name (« les anneaux », « la flaque »,
# « l'eau », « de la flaque ») — jamais au milieu (« anneaux de buren »).
_ARTICLES = frozenset(("le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "au", "aux"))


def normalize_name(text: str) -> str:
    """Clé de correspondance d'un objet nommé (spec §3) : minuscules, sans
    accents, ponctuation et `_` en espaces, articles de tête retirés.
    « Les Anneaux ! » -> "anneaux" ; "table_basse" -> "table basse" ;
    « l'eau » -> "eau". Non-chaîne -> "" (jamais d'exception : le payload
    vient d'un LLM)."""
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    words = "".join(c if c.isalnum() else " " for c in plain).split()
    while words and words[0] in _ARTICLES:
        words.pop(0)
    return " ".join(words)


@dataclass(frozen=True)
class Route:
    name: str
    waypoints: Tuple[Tuple[float, float], ...]
    pois: Tuple[Poi, ...]


def _finite(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RouteError(f"{where} : nombre attendu, reçu {value!r}")
    value = float(value)
    if not math.isfinite(value):
        raise RouteError(f"{where} : nombre fini attendu, reçu {value!r}")
    return value


def load_route(data: dict) -> Route:
    """dict (YAML déjà chargé) -> Route validée. Clés : name (str), waypoints
    (liste de [x, y], au moins 2), pois (liste de {name, x, y, radius > 0,
    lubie?: str, fermeture?: str, desc?: str ≤ DESC_MAX_WORDS mots,
    alias?: [str]}, noms uniques ; optionnelle). Lot M1 : les noms ET alias
    normalisés (normalize_name) désignent UN SEUL POI — un mot partagé par
    deux objets enverrait Didier au hasard, refusé ici."""
    if not isinstance(data, dict):
        raise RouteError("itinéraire : un dictionnaire est attendu à la racine")
    name = data.get("name")
    if not isinstance(name, str) or not name:
        raise RouteError("name : chaîne non vide attendue")

    raw_wps = data.get("waypoints")
    if not isinstance(raw_wps, list) or len(raw_wps) < 2:
        raise RouteError("waypoints : liste d'au moins 2 points [x, y] attendue")
    waypoints: List[Tuple[float, float]] = []
    for i, wp in enumerate(raw_wps):
        if not isinstance(wp, (list, tuple)) or len(wp) != 2:
            raise RouteError(f"waypoints[{i}] : paire [x, y] attendue, reçu {wp!r}")
        waypoints.append((_finite(wp[0], f"waypoints[{i}].x"), _finite(wp[1], f"waypoints[{i}].y")))

    raw_pois = data.get("pois", [])
    if not isinstance(raw_pois, list):
        raise RouteError("pois : liste attendue")
    pois: List[Poi] = []
    seen = set()
    owner: Dict[str, str] = {}   # clé normalisée -> POI qu'elle désigne (nom ou alias)
    for i, p in enumerate(raw_pois):
        if not isinstance(p, dict):
            raise RouteError(f"pois[{i}] : dictionnaire {{name, x, y, radius}} attendu")
        pname = p.get("name")
        if not isinstance(pname, str) or not pname:
            raise RouteError(f"pois[{i}].name : chaîne non vide attendue")
        if pname in seen:
            raise RouteError(f"pois[{i}].name : nom en double « {pname} »")
        seen.add(pname)
        radius = _finite(p.get("radius"), f"pois[{i}].radius")
        if radius <= 0:
            raise RouteError(f"pois[{i}].radius : > 0 attendu, reçu {radius}")
        texts = {}
        for key in ("lubie", "fermeture"):
            # Une consigne non textuelle (nombre, liste) partirait telle quelle
            # au chat : refusée ici plutôt que convertie.
            value = p.get(key, "")
            if not isinstance(value, str):
                raise RouteError(f"pois[{i}].{key} : chaîne attendue, reçu {value!r}")
            texts[key] = value
        desc = p.get("desc", "")
        if not isinstance(desc, str):
            raise RouteError(f"pois[{i}].desc : chaîne attendue, reçu {desc!r}")
        if len(desc.split()) > DESC_MAX_WORDS:
            raise RouteError(f"pois[{i}].desc : {DESC_MAX_WORDS} mots au plus, reçu « {desc} »")
        raw_alias = p.get("alias", [])
        if not isinstance(raw_alias, list):
            raise RouteError(f"pois[{i}].alias : liste de chaînes attendue, reçu {raw_alias!r}")
        for j, a in enumerate(raw_alias):
            if not isinstance(a, str) or not normalize_name(a):
                raise RouteError(f"pois[{i}].alias[{j}] : mot non vide attendu, reçu {a!r}")
        for word in [pname] + raw_alias:
            key = normalize_name(word)
            if owner.setdefault(key, pname) != pname:
                raise RouteError(f"pois[{i}] : « {word} » désigne déjà « {owner[key]} » (nom ou alias)")
        pois.append(Poi(pname, _finite(p.get("x"), f"pois[{i}].x"),
                        _finite(p.get("y"), f"pois[{i}].y"), radius, **texts,
                        desc=desc, alias=tuple(raw_alias)))

    return Route(name=name, waypoints=tuple(waypoints), pois=tuple(pois))


def nearest_ahead_index(waypoints: Sequence[Tuple[float, float]], x: float, y: float) -> int:
    """Index de REPRISE de l'itinéraire depuis une pose quelconque (lot M1,
    spec §4 : après une manœuvre « aller voir », vers le waypoint le plus
    proche DEVANT, pas vers l'ancien index s'il est derrière). « Devant » =
    le long de l'itinéraire, pas selon le cap : Didier, face à l'objet, est
    de travers sur le chemin. Méthode : le segment le plus proche de la pose
    (projection bornée, premier en cas d'égalité) ; on vise sa FIN. Seule
    exception : avant le départ (projection au début du 1er segment) -> 0.
    RouteFollower.tick avance ensuite l'index s'il est déjà atteint."""
    best_d, best_i, best_t = math.inf, 0, 0.0
    for i in range(len(waypoints) - 1):
        (ax, ay), (bx, by) = waypoints[i], waypoints[i + 1]
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        t = 0.0 if length2 == 0.0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length2))
        d = math.hypot(ax + t * dx - x, ay + t * dy - y)
        if d < best_d:
            best_d, best_i, best_t = d, i, t
    if best_i == 0 and best_t == 0.0:
        return 0
    return best_i + 1


def yaw_from_quaternion(x: float, y: float, z: float, w: float) -> float:
    """Lacet (rad, REP-103 : +z anti-horaire) depuis un quaternion ROS."""
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def wrap_angle(a: float) -> float:
    """Ramène un angle dans ]-pi, pi]."""
    return math.atan2(math.sin(a), math.cos(a))


@dataclass(frozen=True)
class RouteConfig:
    """Réglages du cheminement — UNE source de vérité, documentée ici."""
    # Vitesse de croisière à facteur 1 (bornée par ABS_MAX_LIN au constructeur).
    # 0,4 m/s = un pas lent : Didier flâne, il ne fonce pas.
    max_lin: float = 0.4
    # Rotation max (bornée par ABS_MAX_ANG).
    max_ang: float = 0.8
    # rad/s par radian d'erreur de cap.
    ang_gain: float = 1.5
    # Waypoint « atteint » sous cette distance -> on vise le suivant.
    arrive_radius_m: float = 0.5
    # Au-delà de cette erreur de cap (rad), on ne roule plus : on tourne sur
    # place d'abord. Entre 0 et ce seuil, la vitesse linéaire décroît
    # linéairement — évite les grands arcs vers le caniveau.
    heading_slow_rad: float = 0.8
    # Slew par tick (10 Hz) : 0,05 -> 0,5 m/s² ; 0,15 -> 1,5 rad/s². Mêmes
    # valeurs que FollowConfig : même mécanique, mêmes à-coups à éviter.
    lin_slew: float = 0.05
    ang_slew: float = 0.15
    # Sans odométrie fraîche depuis ce délai -> zéro franc (une sim en pause,
    # un bridge mort : on ne roule pas sur une pose fantôme).
    odom_timeout_ms: int = 600


@dataclass
class RouteOutput:
    lin: float
    ang: float
    finished: bool
    # "ok" | "held" (facteur 0 : zéro, PUBLIÉ par le node) | "disabled" |
    # "no_pose" | "odom_stale" | "finished"
    reason: str


class RouteFollower:
    """Instancier une fois ; update_pose() à chaque /odom, tick() à cadence
    fixe (10 Hz). Démarre DÉSACTIVÉ. Toute sortie non « ok » est (0, 0)."""

    def __init__(self, route: Route, config: RouteConfig = RouteConfig(), *,
                 enabled: bool = False, speed: float = 1.0):
        self.route = route
        # Plafonds absolus appliqués AU CONSTRUCTEUR : un paramètre ROS trop
        # grand ne peut pas les franchir (même garantie que FollowControl).
        self.config = RouteConfig(
            max_lin=min(config.max_lin, ABS_MAX_LIN),
            max_ang=min(config.max_ang, ABS_MAX_ANG),
            ang_gain=config.ang_gain,
            arrive_radius_m=config.arrive_radius_m,
            heading_slow_rad=config.heading_slow_rad,
            lin_slew=config.lin_slew,
            ang_slew=config.ang_slew,
            odom_timeout_ms=config.odom_timeout_ms,
        )
        self._enabled = enabled
        self._speed = 0.0
        self.set_speed(speed)
        self._pose: Optional[Tuple[float, float, float]] = None
        self._pose_ms: Optional[int] = None
        self._index = 0
        self._lin = 0.0
        self._ang = 0.0

    # --- entrées -----------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def waypoint_index(self) -> int:
        return self._index

    def set_enabled(self, enabled: bool) -> None:
        if not enabled:
            # Zéro FRANC, pas lissé : désactiver = s'arrêter, tout de suite.
            self._lin = 0.0
            self._ang = 0.0
        self._enabled = bool(enabled)

    def set_speed(self, factor: float) -> None:
        """Facteur 0..1 (le fader). Hors bornes -> borné, jamais refusé : un
        fader qui dépasse ne doit pas couper la séance."""
        try:
            f = float(factor)
        except (TypeError, ValueError):
            return
        if not math.isfinite(f):
            return
        self._speed = min(1.0, max(0.0, f))

    def update_pose(self, x: float, y: float, yaw: float, now_ms: int) -> None:
        self._pose = (float(x), float(y), float(yaw))
        self._pose_ms = int(now_ms)

    def restart(self) -> None:
        """Reprend l'itinéraire depuis le premier point (nouvelle séance)."""
        self._index = 0

    def rejoin(self) -> None:
        """Après une manœuvre (lot M1) : vise le waypoint le plus proche
        DEVANT la pose courante (nearest_ahead_index) — y compris EN ARRIÈRE
        de l'ancien index (demi-tour vers un objet dépassé : on ne saute pas
        le bout de chemin qui reste). Sans pose : index inchangé."""
        if self._pose is not None:
            self._index = nearest_ahead_index(self.route.waypoints, self._pose[0], self._pose[1])

    # --- sortie ------------------------------------------------------------
    def _zero(self, reason: str, finished: bool = False) -> RouteOutput:
        self._lin = 0.0
        self._ang = 0.0
        return RouteOutput(0.0, 0.0, finished, reason)

    def _slew(self, current: float, target: float, step: float) -> float:
        if target > current + step:
            return current + step
        if target < current - step:
            return current - step
        return target

    def tick(self, now_ms: int) -> RouteOutput:
        if not self._enabled:
            return self._zero("disabled")
        if self._pose is None or self._pose_ms is None:
            return self._zero("no_pose")
        if now_ms - self._pose_ms > self.config.odom_timeout_ms:
            return self._zero("odom_stale")

        x, y, yaw = self._pose
        wps = self.route.waypoints
        # Avance l'index tant que le point courant est ATTEINT (rayon) ou
        # DÉPASSÉ le long du segment vers le suivant (projection > 0). Le
        # second critère est ce qui permet à la télécommande (prio 100) de
        # pousser Didier en avant sans qu'il rebrousse chemin vers un point
        # déjà passé : on ne revient JAMAIS en arrière sur l'itinéraire. Le
        # dernier point, lui, ne se valide qu'au rayon (c'est l'arrivée).
        while self._index < len(wps):
            tx, ty = wps[self._index]
            if math.hypot(tx - x, ty - y) < self.config.arrive_radius_m:
                self._index += 1
                continue
            if self._index + 1 < len(wps):
                nx, ny = wps[self._index + 1]
                if (x - tx) * (nx - tx) + (y - ty) * (ny - ty) > 0.0:
                    self._index += 1
                    continue
            break
        if self._index >= len(wps):
            return self._zero("finished", finished=True)
        if self._speed == 0.0:
            # Fader à zéro (arrêt vocal, lubie stop, David) : zéro FRANC, pas
            # même un pivot vers le waypoint (revue M1 : après rejoin(), Didier
            # pivotait à 0,8 rad/s fader en bas). Le node PUBLIE ce zéro à
            # chaque tick : le créneau 20 du mux reste tenu, comme avant.
            return self._zero("held")

        tx, ty = wps[self._index]
        err = wrap_angle(math.atan2(ty - y, tx - x) - yaw)
        c = self.config
        ang_target = max(-c.max_ang, min(c.max_ang, c.ang_gain * err))
        heading_factor = max(0.0, 1.0 - abs(err) / c.heading_slow_rad)
        lin_target = c.max_lin * self._speed * heading_factor

        self._lin = self._slew(self._lin, lin_target, c.lin_slew)
        self._ang = self._slew(self._ang, ang_target, c.ang_slew)
        return RouteOutput(self._lin, self._ang, False, "ok")


@dataclass
class PoiEvent:
    poi: str
    event: str      # "enter" | "exit"
    distance: float


class PoiWatcher:
    """Événements de proximité à hystérésis : enter sous radius, exit au-delà
    de radius * POI_EXIT_FACTOR. Une pose -> zéro, un ou plusieurs événements,
    dans l'ordre des POI de l'itinéraire (déterministe)."""

    def __init__(self, pois: Sequence[Poi]):
        self._pois = tuple(pois)
        self._inside: Dict[str, bool] = {p.name: False for p in self._pois}

    def update(self, x: float, y: float) -> List[PoiEvent]:
        events: List[PoiEvent] = []
        for p in self._pois:
            d = math.hypot(p.x - x, p.y - y)
            if not self._inside[p.name] and d < p.radius:
                self._inside[p.name] = True
                events.append(PoiEvent(p.name, "enter", d))
            elif self._inside[p.name] and d > p.radius * POI_EXIT_FACTOR:
                self._inside[p.name] = False
                events.append(PoiEvent(p.name, "exit", d))
        return events

    def inside(self) -> Tuple[str, ...]:
        return tuple(name for name, v in self._inside.items() if v)
