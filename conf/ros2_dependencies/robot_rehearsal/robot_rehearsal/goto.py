"""Manœuvre « aller voir » (lot M1, spec-aller-voir.md §4) — logique PURE
(stdlib seulement), exécutée par route_driver, testée sans ROS.

Machine à états, une instance par ordre :
  ALIGN   pivot sur place (v = 0) vers le point d'arrêt P ;
  DRIVE   avance vers P, cap corrigé, v ≤ facteur du fader × ABS_MAX_LIN,
          rampe identique au suivi d'itinéraire (RouteConfig.lin_slew) ;
  FACE    pivot sur place face à la CIBLE (la caméra, fixée au buste, la
          voit de face) ;
  ARRIVED zéro franc, terminal : le node publie UN zéro puis se tait (le
          mux retombe, le deadman fait le reste).
P = cible − standoff le long de l'axe (pose de départ -> cible), calculé
UNE fois à la première pose : la manœuvre vise un point fixe, ce qui rend
la borne de distance parcourue mesurable.

SÉCURITÉ (tests gravés + mutation, test_goto.py) — toute sortie non « ok »
est (0, 0) :
  - cancel() (stop, route off, cancel) : zéro franc IMMÉDIAT, terminal ;
  - odométrie périmée (même seuil que le suivi) : zéro, la manœuvre attend ;
  - durée > GOTO_TIMEOUT_S ou distance parcourue > GOTO_MAX_TRAVEL_FACTOR ×
    distance initiale : abandon terminal (le node journalise goto_abort) ;
  - CALAGE (revue M1) : consigne v > stall_lin_ms et déplacement < stall_dist_m
    pendant stall_window_ms -> abandon « stalled » (Didier contre un objet :
    la pose ne bouge plus, la distance parcourue ne le verrait jamais) ;
  - pose non finie (NaN, inf) IGNORÉE : elle vieillit -> odométrie périmée
    -> zéro ; P et la borne de distance ne sont jamais calculés dessus ;
  - plafonds ABS_MAX_LIN / ABS_MAX_ANG appliqués au constructeur, et pivots
    sous GOTO_MAX_ANG ;
  - facteur de vitesse 0 (fader en bas, arrêt vocal, lubie stop) : zéro en
    TOUTE phase, pivots compris — un fader à zéro ne laisse rien tourner.
Pas d'évitement d'obstacle (spec §5) : ligne droite, SIM-ONLY.

GESTES CHIFFRÉS (lot M2, spec §7.2-§7.3) — même machine, mêmes bornes :
  TurnOrder    pivot seul : démarre en FACE, cap visé = cap de la première
               pose fraîche + turn_rad (+ = gauche, ROS). La rotation est
               INTÉGRÉE pas à pas (somme des wrap(Δyaw)), pas recalculée par
               wrap(cible − cap) : un demi-tour (π) aurait sinon un sens
               choisi au bruit de la pose près. Délai TURN_TIMEOUT_S ;
               translation bornée à min_travel_m (poussé = abandon).
               Calage propre (revue M2) : |ω| consigné > stall_ang_rads et
               rotation < stall_turn_rad pendant stall_window_ms -> « stalled ».
  ForwardOrder ligne droite : démarre en DRIVE en TENANT le cap de la
               première pose fraîche ; ARRIVED dès que la PROJECTION du
               déplacement sur ce cap atteint m (à forward_tol_m près) — pas
               de FACE, et jamais de pivot de retour s'il dépasse (revue
               M2 : viser un point P le faisait s'arrêter 0,3 m avant, et
               faire demi-tour au-delà). Délai FORWARD_TIMEOUT_BASE_S +
               FORWARD_TIMEOUT_PER_M_S × m ; distance parcourue ≤
               GOTO_MAX_TRAVEL_FACTOR × m ; calage, fader, croisière : ceux
               du DRIVE. Jamais de recul (m ≥ FORWARD_MIN_M).
Pivots (ALIGN, FACE, TurnOrder) : |ω| ≤ max_ang × facteur du fader, avec un
plancher pivot_min_ang dès que le facteur est > 0 (un pivot trop lent cale
sur le frottement) — revue M2.

FAIRE LE TOUR (lot M3, spec §8.4) — OrbitOrder, même machine, une phase de plus :
  ALIGN/DRIVE  vers le point d'entrée E = C + r·(pose − C)/|pose − C| (le
               point du cercle le plus proche ; à < ORBIT_CENTER_EPS_M du
               centre, E droit devant), arrivée à arrive_tol_m. Déjà sur le
               cercle : ORBIT d'emblée (viser E à 0 m = un cap au bruit près) ;
  ORBIT        cap visé = θ + dir·π/2 + dir·clamp(orbit_k_r·(d − r), ±orbit_max_corr)
               (trop loin -> rentre vers le centre), ω = ang_gain·erreur +
               dir·v/r (anticipation, sur le v RAMPÉ), v = min(max_lin × facteur,
               TOUR_CRUISE_MS) × facteur de cap (à l'entrée, il pivote d'abord).
               Angle balayé INTÉGRÉ pose à pose (Σ dir·wrap(Δθ)), cumul jamais
               sous zéro (un recul au départ ne crée pas de dette) ; ≥ 2π -> FACE ;
  FACE         pivot face au CENTRE, la vitesse linéaire de l'orbite retombe
               par la rampe (pas de pilage à 0,35 m/s) -> ARRIVED.
  Sûreté en plus : |d − r| > TOUR_MAX_DEV_M en ORBIT -> abandon « off_track » ;
  délai = timeout_s + 2πr / TOUR_MIN_MS ; distance parcourue ≤
  GOTO_MAX_TRAVEL_FACTOR × (|pose − E| + 2πr), plancher min_travel_m.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple, Union

from robot_rehearsal.contracts import (ABS_MAX_ANG, ABS_MAX_LIN, FORWARD_MAX_M, FORWARD_MIN_M,
                                       FORWARD_TIMEOUT_BASE_S,
                                       FORWARD_TIMEOUT_PER_M_S, GOTO_MAX_ANG, GOTO_MAX_DISTANCE_M,
                                       GOTO_MAX_TRAVEL_FACTOR, GOTO_MIN_STANDOFF_M, GOTO_TIMEOUT_S,
                                       TOUR_CRUISE_MS, TOUR_MAX_DEV_M, TOUR_MAX_RADIUS_M, TOUR_MIN_MS,
                                       TOUR_MIN_RADIUS_M, TURN_MAX_DEG, TURN_TIMEOUT_S)
from robot_rehearsal.route import RouteConfig, wrap_angle

ALIGN = "align"
DRIVE = "drive"
ORBIT = "orbit"
FACE = "face"
ARRIVED = "arrived"
ABORTED = "aborted"
# Phases terminales : plus aucune sortie non nulle, jamais.
TERMINAL = (ARRIVED, ABORTED)


class GotoError(ValueError):
    """Ordre de manœuvre invalide — le message dit QUOI."""


@dataclass(frozen=True)
class GotoOrder:
    name: str
    x: float
    y: float
    standoff: float


@dataclass(frozen=True)
class TurnOrder:
    name: str
    turn_rad: float


@dataclass(frozen=True)
class ForwardOrder:
    name: str
    metres: float


@dataclass(frozen=True)
class OrbitOrder:
    name: str
    cx: float
    cy: float
    radius: float
    # 1 = gauche (sens trigonométrique, l'objet à GAUCHE de Didier), -1 = droite.
    direction: int


Order = Union[GotoOrder, TurnOrder, ForwardOrder, OrbitOrder]

# Distance au centre sous laquelle la direction pose -> centre n'a plus de
# sens (spec §8.4) : le point d'entrée est alors pris droit devant.
ORBIT_CENTER_EPS_M = 0.2
# Clés de la forme « tour » de route_goto (une seule suffit à la désigner).
_ORBIT_KEYS = ("orbit_x", "orbit_y", "orbit_r", "orbit_dir")

# Tolérance de la borne du pivot : radians(180) arrondi par le producteur
# (3.1416 > π) ne doit pas être refusé ; un tour complet, si.
_TURN_MAX_RAD = math.radians(TURN_MAX_DEG) + 1e-3


def turn_name(turn_rad: float) -> str:
    """Nom d'un pivot (journal, état, déduplication) — MÊME texte des deux
    côtés : le régisseur l'utilise pour reconnaître l'issue de son ordre."""
    return f"pivot {math.degrees(turn_rad):+.0f}°"


def forward_name(metres: float) -> str:
    """Nom d'une ligne droite, même usage que turn_name."""
    return f"avancer {metres:g} m"


def tour_name(poi: str) -> str:
    """Nom d'un tour (spec §8.2 « tour de <poi> »), même usage que turn_name :
    le régisseur le met dans l'ordre et reconnaît l'issue sous ce nom."""
    return f"tour de {poi}"


def _finite(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GotoError(f"{where} : nombre attendu, reçu {value!r}")
    value = float(value)
    if not math.isfinite(value):
        raise GotoError(f"{where} : nombre fini attendu, reçu {value!r}")
    return value


def parse_order(value) -> Order:
    """Payload route_goto DÉJÀ décodé (dict) -> ordre validé. Refus explicite
    (GotoError), jamais de valeur devinée ni saturée : un ordre faux ne roule
    pas. Quatre formes EXCLUSIVES :
      {name, x, y, standoff}  standoff dans [GOTO_MIN_STANDOFF_M, GOTO_MAX_DISTANCE_M] ;
      {turn_rad}              0 < |turn_rad| ≤ radians(TURN_MAX_DEG) ;
      {forward_m}             FORWARD_MIN_M ≤ forward_m ≤ FORWARD_MAX_M (négatif : on ne recule pas) ;
      {name, orbit_x, orbit_y, orbit_r, orbit_dir}
                              orbit_r dans [TOUR_MIN_RADIUS_M, TOUR_MAX_RADIUS_M],
                              orbit_dir ∈ {1, -1} (jamais un booléen)."""
    if not isinstance(value, dict):
        raise GotoError(f"ordre : objet JSON {{name, x, y, standoff}} attendu, reçu {value!r}")
    kinds = [k for k in ("x", "turn_rad", "forward_m") if k in value]
    if any(k in value for k in _ORBIT_KEYS):
        kinds.append("orbit")
    if len(kinds) > 1:
        raise GotoError(f"ordre ambigu : {kinds} (une seule forme à la fois)")
    if kinds == ["orbit"]:
        return _parse_orbit(value)
    if kinds == ["turn_rad"]:
        turn = _finite(value["turn_rad"], "turn_rad")
        if not 0.0 < abs(turn) <= _TURN_MAX_RAD:
            raise GotoError(f"turn_rad : 0 < |a| ≤ {TURN_MAX_DEG:g}° attendu, reçu {turn}")
        return TurnOrder(turn_name(turn), turn)
    if kinds == ["forward_m"]:
        metres = _finite(value["forward_m"], "forward_m")
        if not FORWARD_MIN_M <= metres <= FORWARD_MAX_M:
            raise GotoError(f"forward_m : {FORWARD_MIN_M:g} ≤ m ≤ {FORWARD_MAX_M:g} attendu (pas de recul), "
                            f"reçu {metres}")
        return ForwardOrder(forward_name(metres), metres)
    name = value.get("name")
    if not isinstance(name, str) or not name:
        raise GotoError("name : chaîne non vide attendue")
    standoff = _finite(value.get("standoff"), "standoff")
    if not GOTO_MIN_STANDOFF_M <= standoff <= GOTO_MAX_DISTANCE_M:
        raise GotoError(f"standoff : entre {GOTO_MIN_STANDOFF_M} et {GOTO_MAX_DISTANCE_M} m attendu, "
                        f"reçu {standoff}")
    return GotoOrder(name, _finite(value.get("x"), "x"), _finite(value.get("y"), "y"), standoff)


def _parse_orbit(value: dict) -> OrbitOrder:
    name = value.get("name")
    if not isinstance(name, str) or not name:
        raise GotoError("name : chaîne non vide attendue")
    radius = _finite(value.get("orbit_r"), "orbit_r")
    if not TOUR_MIN_RADIUS_M <= radius <= TOUR_MAX_RADIUS_M:
        raise GotoError(f"orbit_r : entre {TOUR_MIN_RADIUS_M:g} et {TOUR_MAX_RADIUS_M:g} m attendu, reçu {radius}")
    direction = value.get("orbit_dir")
    # True == 1 en Python : un booléen n'est PAS un sens.
    if isinstance(direction, bool) or direction not in (1, -1):
        raise GotoError(f"orbit_dir : 1 (gauche) ou -1 (droite) attendu, reçu {direction!r}")
    return OrbitOrder(name, _finite(value.get("orbit_x"), "orbit_x"), _finite(value.get("orbit_y"), "orbit_y"),
                      radius, int(direction))


@dataclass(frozen=True)
class GotoConfig:
    """Réglages de la manœuvre — UNE source de vérité, documentée ici."""
    # v max à facteur 1 (spec §4 : fader × ABS_MAX_LIN) ; borné au constructeur.
    max_lin: float = ABS_MAX_LIN
    # Rotation max, pivots ET cap corrigé ; bornée par ABS_MAX_ANG au constructeur.
    max_ang: float = GOTO_MAX_ANG
    # rad/s par radian d'erreur de cap (même gain que le suivi).
    ang_gain: float = 1.5
    # ALIGN / FACE terminés sous cette erreur de cap (rad, ≈ 6°).
    heading_tol_rad: float = 0.1
    # DRIVE : comme le suivi, v décroît avec l'erreur de cap et s'annule au-delà.
    heading_slow_rad: float = 0.8
    # DRIVE terminé sous cette distance de P (m).
    arrive_tol_m: float = 0.3
    # DRIVE : v ≤ approach_gain × distance à P (1/s) — Didier ralentit à
    # l'approche au lieu de piler depuis 0,5 m/s : à arrive_tol, v ≤ 0,15.
    approach_gain: float = 0.5
    # Rampes par tick (10 Hz) : MÊMES valeurs que le suivi (spec §4).
    lin_slew: float = RouteConfig.lin_slew
    ang_slew: float = RouteConfig.ang_slew
    # Odométrie périmée : MÊME seuil que le suivi (spec §4).
    odom_timeout_ms: int = RouteConfig.odom_timeout_ms
    timeout_s: float = GOTO_TIMEOUT_S
    max_travel_factor: float = GOTO_MAX_TRAVEL_FACTOR
    # Plancher de la borne de distance parcourue (m) : un ordre donné à
    # 0,2 m du point d'arrêt (FACE seul) ne doit pas avorter sur le
    # tremblement de la pose pendant le pivot.
    min_travel_m: float = 1.0
    # Calage : consigne v au-dessus de ce seuil (m/s) et déplacement sous
    # stall_dist_m pendant stall_window_ms -> abandon « stalled ». À 0,1 m/s,
    # 2 s = 0,2 m attendus : 0,05 m laisse la marge du démarrage en rampe.
    stall_lin_ms: float = 0.1
    stall_dist_m: float = 0.05
    stall_window_ms: int = 2000
    # Calage d'un PIVOT (TurnOrder) : |ω| consigné au-dessus de ce seuil
    # (rad/s) et rotation sous stall_turn_rad pendant stall_window_ms.
    stall_ang_rads: float = 0.2
    stall_turn_rad: float = 0.05
    # Pivots : plancher du plafond |ω| au fader (rad/s), si facteur > 0.
    pivot_min_ang: float = 0.15
    # Ligne droite : arrivée quand il reste moins que ça à parcourir (m).
    forward_tol_m: float = 0.05
    # Orbite (spec §8.4) : correction de cap par mètre d'écart radial (rad/m),
    # plafonnée à orbit_max_corr (rad) — trop loin, il rentre vers le centre.
    orbit_k_r: float = 1.0
    orbit_max_corr: float = 0.6
    # Orbite : croisière sur le cercle (m/s), sous max_lin × facteur.
    orbit_cruise_ms: float = TOUR_CRUISE_MS
    # Orbite : écart radial |d − r| toléré (m) ; au-delà, abandon « off_track ».
    orbit_max_dev_m: float = TOUR_MAX_DEV_M


@dataclass
class GotoOutput:
    lin: float
    ang: float
    phase: str
    # "ok" | "held" (facteur 0) | "no_pose" | "odom_stale" | "arrived"
    # | "cancelled" | "timeout" | "max_travel" | "stalled" | "too_far" | "off_track"
    reason: str


class GotoManeuver:
    """Instancier à l'ordre ; update_pose() à chaque /odom, tick() à cadence
    fixe (10 Hz). Toute sortie non « ok » est (0, 0)."""

    def __init__(self, order: Order, now_ms: int, config: GotoConfig = GotoConfig()):
        self.order = order
        # Délai propre au geste (spec §7) : jamais au-dessus de celui de la config.
        timeout_s = config.timeout_s
        if isinstance(order, TurnOrder):
            timeout_s = min(timeout_s, TURN_TIMEOUT_S)
        elif isinstance(order, ForwardOrder):
            timeout_s = min(timeout_s, FORWARD_TIMEOUT_BASE_S + FORWARD_TIMEOUT_PER_M_S * order.metres)
        elif isinstance(order, OrbitOrder):
            # Spec §8.4 : délai de l'approche + un tour à la vitesse plancher.
            timeout_s = timeout_s + 2.0 * math.pi * order.radius / TOUR_MIN_MS
        # Plafonds absolus AU CONSTRUCTEUR (même garantie que RouteFollower) :
        # un paramètre trop grand ne peut pas les franchir.
        self.config = GotoConfig(
            **{**config.__dict__,
               "max_lin": min(config.max_lin, ABS_MAX_LIN),
               "max_ang": min(config.max_ang, GOTO_MAX_ANG, ABS_MAX_ANG),
               "timeout_s": timeout_s})
        self._start_ms = int(now_ms)
        # Pivot : FACE seul ; ligne droite : DRIVE seul ; aller voir : dès ALIGN.
        self._phase = (FACE if isinstance(order, TurnOrder)
                       else DRIVE if isinstance(order, ForwardOrder) else ALIGN)
        self._turned = 0.0   # pivot : rotation intégrée depuis la première pose fraîche
        self._turn_stall_ref: Optional[Tuple[int, float]] = None   # pivot : (instant, _turned)
        self._origin: Optional[Tuple[float, float, float]] = None   # ligne droite : pose de départ
        self._swept = 0.0    # orbite : angle balayé autour du centre (rad, ≥ 0, dans le sens demandé)
        self._reason = "ok"
        self._pose: Optional[Tuple[float, float, float]] = None
        self._pose_ms: Optional[int] = None
        self._stop: Optional[Tuple[float, float]] = None   # P, fixé à la première pose
        self._travel_max = 0.0
        self._travelled = 0.0
        self._lin = 0.0
        self._ang = 0.0
        # Calage : (instant, pose) de référence tant que la consigne dépasse
        # stall_lin_ms ; None dès qu'elle retombe.
        self._stall_ref: Optional[Tuple[int, float, float]] = None

    # --- état ----------------------------------------------------------------
    @property
    def phase(self) -> str:
        return self._phase

    @property
    def finished(self) -> bool:
        return self._phase in TERMINAL

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def stop_point(self) -> Optional[Tuple[float, float]]:
        return self._stop

    @property
    def travelled(self) -> float:
        return self._travelled

    @property
    def swept(self) -> float:
        """Orbite : angle balayé dans le sens demandé (rad), 0 hors ORBIT."""
        return self._swept

    # --- entrées -------------------------------------------------------------
    def update_pose(self, x: float, y: float, yaw: float, now_ms: int) -> None:
        x, y, yaw = float(x), float(y), float(yaw)
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(yaw)):
            # Pose non finie IGNORÉE (y compris la première) : la dernière
            # bonne vieillit et devient périmée -> zéro. Jamais de P, de borne
            # ni de distance parcourue calculés sur un NaN.
            return
        if self._pose is not None and not self.finished:
            # Distance RÉELLEMENT parcourue (somme des pas de la pose vérité
            # terrain), pas la distance au but : un détour, une oscillation ou
            # une poussée la font grimper. Un Didier BLOQUÉ, non (sa pose ne
            # bouge pas) : c'est le détecteur de calage qui le voit.
            self._travelled += math.hypot(x - self._pose[0], y - self._pose[1])
            # Rotation intégrée pas à pas (|Δyaw| ≪ π entre deux poses à 10+ Hz).
            self._turned += wrap_angle(yaw - self._pose[2])
            if self._phase == ORBIT:
                # Angle balayé autour du centre, pose à pose (|Δθ| ≪ π : en
                # ORBIT, d ≥ r − orbit_max_dev_m ≥ 0,5 m). Cumul plancher 0.
                o = self.order
                dtheta = wrap_angle(math.atan2(y - o.cy, x - o.cx)
                                    - math.atan2(self._pose[1] - o.cy, self._pose[0] - o.cx))
                self._swept = max(0.0, self._swept + o.direction * dtheta)
        self._pose = (x, y, yaw)
        self._pose_ms = int(now_ms)

    def cancel(self) -> None:
        """stop / route off / cancel : zéro franc, terminal, sur-le-champ."""
        self._end(ABORTED, "cancelled")

    # --- sortie --------------------------------------------------------------
    def _end(self, phase: str, reason: str) -> None:
        if not self.finished:
            self._phase, self._reason = phase, reason
        self._lin = self._ang = 0.0

    def _zero(self, reason: str) -> GotoOutput:
        self._lin = self._ang = 0.0
        return GotoOutput(0.0, 0.0, self._phase, reason)

    @staticmethod
    def _slew(current: float, target: float, step: float) -> float:
        if target > current + step:
            return current + step
        if target < current - step:
            return current - step
        return target

    def _first_pose(self) -> None:
        """Fixe P et la borne de distance à la première pose."""
        x, y, yaw = self._pose
        o, c = self.order, self.config
        if isinstance(o, TurnOrder):
            # Sur place : P = ici, translation tolérée = le plancher (tremblement).
            self._stop = (x, y)
            self._travel_max = c.min_travel_m
            self._travelled = self._turned = 0.0
            return
        if isinstance(o, ForwardOrder):
            # Cap et origine FIXÉS sur cette pose fraîche ; P (droit devant)
            # n'est plus qu'indicatif (stop_point), l'arrivée se juge à la projection.
            self._origin = (x, y, yaw)
            self._stop = (x + o.metres * math.cos(yaw), y + o.metres * math.sin(yaw))
            self._travel_max = max(c.max_travel_factor * o.metres, c.min_travel_m)
            self._travelled = 0.0
            return
        if isinstance(o, OrbitOrder):
            d = math.hypot(x - o.cx, y - o.cy)
            if d > GOTO_MAX_DISTANCE_M:
                self._end(ABORTED, "too_far")   # ceinture : le régisseur refuse déjà
                return
            if d < ORBIT_CENTER_EPS_M:
                # Direction pose -> centre indéfinie : E droit devant.
                ux, uy = math.cos(yaw), math.sin(yaw)
            else:
                ux, uy = (x - o.cx) / d, (y - o.cy) / d
            self._stop = (o.cx + o.radius * ux, o.cy + o.radius * uy)   # E
            approach = math.hypot(self._stop[0] - x, self._stop[1] - y)
            if approach < c.arrive_tol_m:
                # Déjà sur le cercle : viser E à quelques cm donnerait un cap au
                # bruit près (ALIGN pivoterait au hasard) — l'orbite pivote seule.
                self._phase = ORBIT
            self._travel_max = max(c.max_travel_factor * (approach + 2.0 * math.pi * o.radius),
                                   c.min_travel_m)
            self._travelled = self._swept = 0.0
            return
        d = math.hypot(o.x - x, o.y - y)
        if d > GOTO_MAX_DISTANCE_M:
            self._end(ABORTED, "too_far")   # ceinture : le régisseur refuse déjà
            return
        if d <= o.standoff + c.arrive_tol_m:
            # Déjà à distance de jeu (ou plus près) : pas de recul, on pivote.
            self._stop = (x, y)
            self._phase = FACE
        else:
            k = (d - o.standoff) / d
            self._stop = (x + k * (o.x - x), y + k * (o.y - y))
        self._travel_max = max(c.max_travel_factor * math.hypot(self._stop[0] - x, self._stop[1] - y),
                               c.min_travel_m)
        self._travelled = 0.0

    def tick(self, now_ms: int, speed: float) -> GotoOutput:
        """`speed` : facteur 0..1 du fader (borné ici aussi)."""
        if self.finished:
            return self._zero(self._reason)
        c = self.config
        if now_ms - self._start_ms > c.timeout_s * 1000.0:
            self._end(ABORTED, "timeout")
            return self._zero("timeout")
        if self._pose is None or self._pose_ms is None:
            return self._zero("no_pose")
        if now_ms - self._pose_ms > c.odom_timeout_ms:
            self._stall_ref = None   # un trou d'odométrie n'est pas un calage
            return self._zero("odom_stale")
        if self._stop is None:
            self._first_pose()
            if self.finished:
                return self._zero(self._reason)
        # Écrit « not <= » : un NaN dans la somme déclenche l'abandon au lieu
        # de désactiver la borne (toute comparaison à NaN est fausse).
        if not (self._travelled <= self._travel_max):
            self._end(ABORTED, "max_travel")
            return self._zero("max_travel")
        try:
            factor = min(1.0, max(0.0, float(speed)))
        except (TypeError, ValueError):
            factor = 0.0
        if not math.isfinite(factor) or factor == 0.0:
            self._stall_ref = None
            return self._zero("held")

        x, y, yaw = self._pose
        px, py = self._stop
        # Plafond |ω| des pivots au fader, plancher pour ne pas caler.
        pivot_cap = min(c.max_ang, max(c.max_ang * factor, c.pivot_min_ang))
        if isinstance(self.order, ForwardOrder):
            return self._forward(now_ms, factor)
        if self._phase == ALIGN:
            err = wrap_angle(math.atan2(py - y, px - x) - yaw)
            if abs(err) < c.heading_tol_rad:
                self._phase = DRIVE
            else:
                return self._out(0.0, err, pivot_cap)
        if self._phase == DRIVE:
            dist = math.hypot(px - x, py - y)
            if dist < c.arrive_tol_m:
                if isinstance(self.order, OrbitOrder):
                    # E atteint : l'orbite commence ICI (angle balayé compté
                    # à partir de cette pose) ; v ≤ approach_gain × arrive_tol,
                    # la rampe le ramène à 0 pendant le pivot d'entrée.
                    self._phase = ORBIT
                else:
                    self._phase = FACE
                    self._lin = 0.0   # depuis ≤ approach_gain × arrive_tol : arrêt doux
            else:
                err = wrap_angle(math.atan2(py - y, px - x) - yaw)
                heading_factor = max(0.0, 1.0 - abs(err) / c.heading_slow_rad)
                lin = min(c.max_lin * factor, c.approach_gain * dist) * heading_factor
                out = self._out(lin, err)
                if self._stalled(now_ms, out.lin):
                    self._end(ABORTED, "stalled")
                    return self._zero("stalled")
                return out
        if self._phase == ORBIT:
            out = self._orbit(factor, pivot_cap)
            if out is not None:
                if out.reason != "ok":
                    return out
                if self._stalled(now_ms, out.lin):
                    self._end(ABORTED, "stalled")
                    return self._zero("stalled")
                return out
        self._stall_ref = None   # pivots : aucune consigne linéaire, pas de calage
        # FACE
        if isinstance(self.order, TurnOrder):
            # Reste à tourner, NON replié dans ]-π, π] (cf. docstring de module).
            err = self.order.turn_rad - self._turned
        elif isinstance(self.order, OrbitOrder):
            err = wrap_angle(math.atan2(self.order.cy - y, self.order.cx - x) - yaw)
        else:
            err = wrap_angle(math.atan2(self.order.y - y, self.order.x - x) - yaw)
        if abs(err) < c.heading_tol_rad:
            self._end(ARRIVED, "arrived")
            return self._zero("arrived")
        out = self._out(0.0, err, pivot_cap)
        if isinstance(self.order, TurnOrder) and self._turn_stalled(now_ms, out.ang):
            self._end(ABORTED, "stalled")
            return self._zero("stalled")
        return out

    def _forward(self, now_ms: int, factor: float) -> GotoOutput:
        """Ligne droite (DRIVE seul) : cap initial TENU, arrivée à la projection."""
        c, (x0, y0, yaw0) = self.config, self._origin
        x, y, yaw = self._pose
        progress = (x - x0) * math.cos(yaw0) + (y - y0) * math.sin(yaw0)
        remaining = self.order.metres - progress
        if remaining <= c.forward_tol_m:
            # Atteint OU dépassé : arrêt, jamais de retour en arrière.
            self._end(ARRIVED, "arrived")
            return self._zero("arrived")
        err = wrap_angle(yaw0 - yaw)
        heading_factor = max(0.0, 1.0 - abs(err) / c.heading_slow_rad)
        lin = min(c.max_lin * factor, c.approach_gain * remaining) * heading_factor
        out = self._out(lin, err)
        if self._stalled(now_ms, out.lin):
            self._end(ABORTED, "stalled")
            return self._zero("stalled")
        return out

    def _orbit(self, factor: float, pivot_cap: float) -> Optional[GotoOutput]:
        """Phase ORBIT (spec §8.4). -> sortie, ou None si le tour est bouclé
        (phase passée à FACE : l'appelant enchaîne le pivot vers le centre).
        |ω| plafonné comme un PIVOT (au fader, revue M2) : à l'entrée, v = 0
        tant que le cap n'est pas tangent — c'est un pivot sur place ; en
        régime, l'anticipation v/r ≤ 0,5·f/1,5 reste sous 0,6·f."""
        c, o = self.config, self.order
        x, y, yaw = self._pose
        d = math.hypot(x - o.cx, y - o.cy)
        # Garde AVANT le test d'achèvement : une pose téléportée a pu gonfler
        # l'angle balayé (update_pose) ; elle abandonne, elle ne « finit » pas.
        # Écrit « not <= » : un NaN abandonne.
        if not (abs(d - o.radius) <= c.orbit_max_dev_m):
            self._end(ABORTED, "off_track")
            return self._zero("off_track")
        if self._swept >= 2.0 * math.pi:
            self._phase = FACE
            return None
        theta = math.atan2(y - o.cy, x - o.cx)
        corr = max(-c.orbit_max_corr, min(c.orbit_max_corr, c.orbit_k_r * (d - o.radius)))
        err = wrap_angle(theta + o.direction * (math.pi / 2 + corr) - yaw)
        heading_factor = max(0.0, 1.0 - abs(err) / c.heading_slow_rad)
        lin = min(c.max_lin * factor, c.orbit_cruise_ms) * heading_factor
        # Anticipation dir·v/r sur le v RAMPÉ (celui que les roues font vraiment).
        return self._out(lin, err, pivot_cap, curvature=o.direction / o.radius)

    def _turn_stalled(self, now_ms: int, ang: float) -> bool:
        """Pivot : |ω| consigné > stall_ang_rads sans rotation de stall_turn_rad
        depuis stall_window_ms ? (Didier coincé : la pose ne tourne plus.)"""
        c = self.config
        if abs(ang) <= c.stall_ang_rads:
            self._turn_stall_ref = None
            return False
        if self._turn_stall_ref is None or abs(self._turned - self._turn_stall_ref[1]) >= c.stall_turn_rad:
            self._turn_stall_ref = (int(now_ms), self._turned)
            return False
        return now_ms - self._turn_stall_ref[0] >= c.stall_window_ms

    def _stalled(self, now_ms: int, lin: float) -> bool:
        """Consigne v > stall_lin_ms sans déplacement de stall_dist_m depuis
        stall_window_ms ? Référence reprise à chaque déplacement suffisant."""
        c = self.config
        x, y, _yaw = self._pose
        if lin <= c.stall_lin_ms:
            self._stall_ref = None
            return False
        if self._stall_ref is None or math.hypot(x - self._stall_ref[1], y - self._stall_ref[2]) >= c.stall_dist_m:
            self._stall_ref = (int(now_ms), x, y)
            return False
        return now_ms - self._stall_ref[0] >= c.stall_window_ms

    def _out(self, lin_target: float, err: float, ang_cap: Optional[float] = None,
             curvature: float = 0.0) -> GotoOutput:
        """`curvature` (1/m) : anticipation ω += curvature × v rampé (orbite)."""
        c = self.config
        cap = c.max_ang if ang_cap is None else min(c.max_ang, ang_cap)
        self._lin = self._slew(self._lin, lin_target, c.lin_slew)
        ang_target = max(-cap, min(cap, c.ang_gain * err + curvature * self._lin))
        self._ang = self._slew(self._ang, ang_target, c.ang_slew)
        # Ceinture finale : jamais au-delà des plafonds absolus, quoi qu'il arrive au-dessus.
        lin = max(-ABS_MAX_LIN, min(ABS_MAX_LIN, self._lin))
        ang = max(-ABS_MAX_ANG, min(ABS_MAX_ANG, self._ang))
        return GotoOutput(lin, ang, self._phase, "ok")
