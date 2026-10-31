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
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from robot_rehearsal.contracts import (ABS_MAX_ANG, ABS_MAX_LIN, GOTO_MAX_ANG, GOTO_MAX_DISTANCE_M,
                                       GOTO_MAX_TRAVEL_FACTOR, GOTO_MIN_STANDOFF_M, GOTO_TIMEOUT_S)
from robot_rehearsal.route import RouteConfig, wrap_angle

ALIGN = "align"
DRIVE = "drive"
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


def _finite(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GotoError(f"{where} : nombre attendu, reçu {value!r}")
    value = float(value)
    if not math.isfinite(value):
        raise GotoError(f"{where} : nombre fini attendu, reçu {value!r}")
    return value


def parse_order(value) -> GotoOrder:
    """Payload route_goto DÉJÀ décodé (dict) -> GotoOrder validé. Refus
    explicite (GotoError), jamais de valeur devinée : un ordre faux ne roule
    pas. standoff dans [GOTO_MIN_STANDOFF_M, GOTO_MAX_DISTANCE_M]."""
    if not isinstance(value, dict):
        raise GotoError(f"ordre : objet JSON {{name, x, y, standoff}} attendu, reçu {value!r}")
    name = value.get("name")
    if not isinstance(name, str) or not name:
        raise GotoError("name : chaîne non vide attendue")
    standoff = _finite(value.get("standoff"), "standoff")
    if not GOTO_MIN_STANDOFF_M <= standoff <= GOTO_MAX_DISTANCE_M:
        raise GotoError(f"standoff : entre {GOTO_MIN_STANDOFF_M} et {GOTO_MAX_DISTANCE_M} m attendu, "
                        f"reçu {standoff}")
    return GotoOrder(name, _finite(value.get("x"), "x"), _finite(value.get("y"), "y"), standoff)


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


@dataclass
class GotoOutput:
    lin: float
    ang: float
    phase: str
    # "ok" | "held" (facteur 0) | "no_pose" | "odom_stale" | "arrived"
    # | "cancelled" | "timeout" | "max_travel" | "stalled" | "too_far"
    reason: str


class GotoManeuver:
    """Instancier à l'ordre ; update_pose() à chaque /odom, tick() à cadence
    fixe (10 Hz). Toute sortie non « ok » est (0, 0)."""

    def __init__(self, order: GotoOrder, now_ms: int, config: GotoConfig = GotoConfig()):
        self.order = order
        # Plafonds absolus AU CONSTRUCTEUR (même garantie que RouteFollower) :
        # un paramètre trop grand ne peut pas les franchir.
        self.config = GotoConfig(
            **{**config.__dict__,
               "max_lin": min(config.max_lin, ABS_MAX_LIN),
               "max_ang": min(config.max_ang, GOTO_MAX_ANG, ABS_MAX_ANG)})
        self._start_ms = int(now_ms)
        self._phase = ALIGN
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
        x, y, _yaw = self._pose
        o, c = self.order, self.config
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
        if self._phase == ALIGN:
            err = wrap_angle(math.atan2(py - y, px - x) - yaw)
            if abs(err) < c.heading_tol_rad:
                self._phase = DRIVE
            else:
                return self._out(0.0, err)
        if self._phase == DRIVE:
            dist = math.hypot(px - x, py - y)
            if dist < c.arrive_tol_m:
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
        self._stall_ref = None   # pivots : aucune consigne linéaire, pas de calage
        # FACE
        err = wrap_angle(math.atan2(self.order.y - y, self.order.x - x) - yaw)
        if abs(err) < c.heading_tol_rad:
            self._end(ARRIVED, "arrived")
            return self._zero("arrived")
        return self._out(0.0, err)

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

    def _out(self, lin_target: float, err: float) -> GotoOutput:
        c = self.config
        ang_target = max(-c.max_ang, min(c.max_ang, c.ang_gain * err))
        self._lin = self._slew(self._lin, lin_target, c.lin_slew)
        self._ang = self._slew(self._ang, ang_target, c.ang_slew)
        # Ceinture finale : jamais au-delà des plafonds absolus, quoi qu'il arrive au-dessus.
        lin = max(-ABS_MAX_LIN, min(ABS_MAX_LIN, self._lin))
        ang = max(-ABS_MAX_ANG, min(ABS_MAX_ANG, self._ang))
        return GotoOutput(lin, ang, self._phase, "ok")
