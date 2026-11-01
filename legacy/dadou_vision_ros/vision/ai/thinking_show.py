"""Jeu de réflexion : ce que Didier JOUE pendant qu'il attend le metteur en scène.

QUOI : après une demande de réflexion (clé "reflechir" : « laisse-moi voir »),
      la réponse met 3-4 s à revenir. Pendant ce temps, `ThinkingShow` produit
      un visage « reflechit » puis 2-3 coups d'œil de la tête (topic `look`),
      angle, côté, tenue et rythme TIRÉS AU HASARD à chaque fois. Module PUR
      (stdlib, horloge et tirage injectés) : testable sans ROS.
POURQUOI (David, 01/11) : « un mode réflexion avec un genre de random pour
      avoir davantage de différence et attirer l'attention quand il
      réfléchit » — un silence immobile de plusieurs secondes tue la scène,
      un geste identique à chaque fois se voit comme une mécanique.
BORNES (contrat `look` du robot, dadou_robot_ros/docs/spec-aller-voir.md
      §7.1) : hold_ms 1000-8000 côté robot ; au plus 3 réarmements de suite
      (au-delà la tenue est coupée et `look` ignoré 4 s) -> MAX_GLANCES = 3
      (1 ordre + 2 réarmements). Angles ≤ 35° : la course utile du cou est
      ±36,4°, au-delà il sature.
FIN : réponse arrivée, Didier ou David reprend la parole (l'appelant appelle
      stop() : le tour qui suit pose son propre visage), ou TIMEOUT_S sans
      réponse (visage rendu) — jamais de geste orphelin après la réponse.
      Pas de son : les bips bloqueraient l'écoute pendant l'attente (la porte
      audio se ferme quand Didier joue un son), or David peut parler.
"""
from __future__ import annotations

import random
from typing import Optional

FACE_THINKING = "reflechit"
# Visage rendu à l'échéance sans réponse (même valeur que la fin de réplique,
# vision/ai/performance.py) : sinon il resterait figé sur « reflechit ».
FACE_IDLE = "stop"
MAX_GLANCES = 3
TIMEOUT_S = 12.0
ANGLE_MIN_DEG, ANGLE_MAX_DEG = 15.0, 35.0
HOLD_MIN_MS, HOLD_MAX_MS = 1000, 1600
# Premier coup d'œil : court délai (le visage « réfléchit » se voit d'abord).
FIRST_DELAY_S = (0.3, 0.8)
# Entre deux coups d'œil : la tenue est lancée à l'ARRIVÉE (rampe du cou),
# l'écart est donc compté depuis l'ordre précédent.
GAP_S = (1.4, 2.4)
# Probabilité de changer de côté au coup d'œil suivant (sinon il insiste).
SWITCH_SIDE_P = 0.7


class ThinkingShow:
    """start(now) -> actions ; tick(now) -> actions ; stop() coupe.
    Une action est ("face", "reflechit") ou ("look", {"angle_deg", "hold_ms"}).
    Non thread-safe : l'appelant sérialise (verrou du node)."""

    def __init__(self, rng: Optional[random.Random] = None):
        self._rng = rng or random.Random()
        self._active = False
        self._started = 0.0
        self._next_glance = 0.0
        self._glances = 0
        self._side = 1

    @property
    def active(self) -> bool:
        return self._active

    def start(self, now_s: float) -> list:
        """(Re)démarre le jeu : une nouvelle demande pendant le jeu repart à zéro
        (nouveau tirage) — le compteur de réarmements côté robot, lui, se remet
        à zéro seul quand la tête est revenue au repos."""
        self._active = True
        self._started = now_s
        self._glances = 0
        self._side = self._rng.choice((-1, 1))
        self._next_glance = now_s + self._rng.uniform(*FIRST_DELAY_S)
        return [("face", FACE_THINKING)]

    def stop(self) -> None:
        self._active = False

    def tick(self, now_s: float) -> list:
        if not self._active:
            return []
        if now_s - self._started >= TIMEOUT_S:
            self._active = False
            return [("face", FACE_IDLE)]
        # Coups d'œil épuisés : il reste « pensif » jusqu'à la réponse ou l'échéance.
        if self._glances >= MAX_GLANCES or now_s < self._next_glance:
            return []
        if self._glances > 0 and self._rng.random() < SWITCH_SIDE_P:
            self._side = -self._side
        angle = round(self._side * self._rng.uniform(ANGLE_MIN_DEG, ANGLE_MAX_DEG), 1)
        hold = self._rng.randint(HOLD_MIN_MS, HOLD_MAX_MS)
        self._glances += 1
        self._next_glance = now_s + self._rng.uniform(*GAP_S)
        return [("look", {"angle_deg": angle, "hold_ms": hold})]
