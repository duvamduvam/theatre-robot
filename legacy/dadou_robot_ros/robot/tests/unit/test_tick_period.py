"""TICK_PERIOD_S : cadence globale des nodes (hors chaîne roues, gelée).

20 Hz reste la cible. Note incident 2026-07-13 : le driver LED Blinka bloque
~31 ms par show() — attente de fin de trame INDISPENSABLE (sa suppression via
FastNeoPixel corrompait les trames : visage « deux signaux entrelacés », voir
docs/incidents/2026-07-13-glitch-visage-driver-led.md). lights_node s'auto-
limite donc sous charge d'animation ; les autres nodes tiennent le 20 Hz.
"""

from robot.robot_static import TICK_PERIOD_S


def test_tick_period_is_20hz():
    """La constante est lue par tous les nodes : la figer évite une dérive
    silencieuse de cadence (rampe servos, deadmans d'animation)."""
    assert TICK_PERIOD_S == 0.05
