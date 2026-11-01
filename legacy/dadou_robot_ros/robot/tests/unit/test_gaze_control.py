"""Tests de la logique PURE du suivi du regard (robot.move.gaze_control).

Horloge passée en paramètre (now_ms) : aucun sleep, aucun temps réel, aucun ROS.
On isole souvent le mapping en mettant slew_max très grand (convergence en un tick)
et ema_alpha=1.0 (l'azimut lissé = l'azimut brut immédiatement) pour des assertions
déterministes ; des tests dédiés couvrent le lissage et le slew.
"""

import math

import pytest

from robot.move.gaze_control import (
    GazeControl,
    consigne_to_radians,
    IDLE,
    TRACKING,
    LOST,
)


# --------------------------------------------------------------------------
# Mapping consigne 0-99 -> radians (limites URDF neck : -pi/2 .. +pi/2)
# --------------------------------------------------------------------------
def test_radians_extremes_et_centre():
    assert consigne_to_radians(0) == pytest.approx(-math.pi / 2)
    assert consigne_to_radians(99) == pytest.approx(math.pi / 2)
    # 50 n'est pas exactement le milieu (49.5) -> quasi 0, léger biais assumé.
    assert consigne_to_radians(50) == pytest.approx(0.0, abs=0.02)


# --------------------------------------------------------------------------
# Mapping azimut -> consigne : centre, bords, sens, clamp
# --------------------------------------------------------------------------
def _gc(**kw):
    # Fabrique un GazeControl activé, mapping isolé (convergence immédiate).
    params = dict(gain=20, ema_alpha=1.0, slew_max=1000, enabled=True)
    params.update(kw)
    return GazeControl(**params)


def test_azimut_centre_donne_consigne_centre():
    gc = _gc()
    gc.update(azimuth=0.0, elevation=0.0, confidence=1.0, now_ms=0)
    assert gc.tick(now_ms=0) == 50


def test_azimut_bord_droit_amplitude_max():
    # azimut +1, gain 20, sens +1 -> 50 + 20 = 70.
    gc = _gc()
    gc.update(azimuth=1.0, elevation=0.0, confidence=1.0, now_ms=0)
    assert gc.tick(now_ms=0) == 70


def test_azimut_bord_gauche_amplitude_max():
    gc = _gc()
    gc.update(azimuth=-1.0, elevation=0.0, confidence=1.0, now_ms=0)
    assert gc.tick(now_ms=0) == 30


def test_direction_sign_inverse():
    gc = _gc(direction_sign=-1)
    gc.update(azimuth=1.0, elevation=0.0, confidence=1.0, now_ms=0)
    assert gc.tick(now_ms=0) == 30  # sens inversé -> bord droit tire vers le bas


def test_clamp_hors_plage():
    # azimut hors spec (2.0) : la consigne reste bornée à [centre-gain, centre+gain].
    gc = _gc()
    gc.update(azimuth=2.0, elevation=0.0, confidence=1.0, now_ms=0)
    assert gc.tick(now_ms=0) == 70


# --------------------------------------------------------------------------
# Seuil de confiance
# --------------------------------------------------------------------------
def test_confiance_basse_aucun_mouvement():
    gc = _gc(confidence_min=0.4)
    gc.update(azimuth=0.8, elevation=0.0, confidence=0.2, now_ms=0)
    # Détection ignorée -> reste IDLE -> rien à publier.
    assert gc.tick(now_ms=0) is None
    assert gc.state == IDLE


def test_confiance_au_seuil_bouge():
    gc = _gc(confidence_min=0.4)
    gc.update(azimuth=0.8, elevation=0.0, confidence=0.4, now_ms=0)
    assert gc.tick(now_ms=0) is not None
    assert gc.state == TRACKING


# --------------------------------------------------------------------------
# Slew limiter : la consigne ne varie pas de plus de slew_max par tick
# --------------------------------------------------------------------------
def test_slew_limite_la_variation_par_tick():
    gc = GazeControl(gain=20, ema_alpha=1.0, slew_max=3, enabled=True)
    gc.update(azimuth=1.0, elevation=0.0, confidence=1.0, now_ms=0)  # cible = 70
    # Départ au centre 50, pas de 3 -> 53, 56, 59...
    assert gc.tick(now_ms=0) == 53
    assert gc.tick(now_ms=0) == 56
    assert gc.tick(now_ms=0) == 59


def test_slew_converge_puis_stop():
    gc = GazeControl(gain=20, ema_alpha=1.0, slew_max=3, enabled=True)
    gc.update(azimuth=1.0, elevation=0.0, confidence=1.0, now_ms=0)  # cible = 70
    last = None
    for _ in range(50):
        out = gc.tick(now_ms=0)
        if out is not None:
            last = out
    assert last == 70  # convergé exactement à la cible


# --------------------------------------------------------------------------
# Pas de republication quand la consigne ne change pas
# --------------------------------------------------------------------------
def test_pas_de_republication_a_consigne_constante():
    gc = _gc()  # slew grand -> converge en un tick
    gc.update(azimuth=0.5, elevation=0.0, confidence=1.0, now_ms=0)
    first = gc.tick(now_ms=0)
    assert first == 60  # 50 + 20*0.5
    # Ticks suivants sans nouvelle info : consigne inchangée -> None (anti-spam).
    assert gc.tick(now_ms=0) is None
    assert gc.tick(now_ms=0) is None


# --------------------------------------------------------------------------
# Timeout -> LOST -> retour LENT au centre -> IDLE
# --------------------------------------------------------------------------
def test_timeout_retour_centre_puis_idle():
    gc = GazeControl(gain=20, ema_alpha=1.0, slew_max=1000, slew_return=1,
                     timeout_ms=1500, enabled=True)
    # Acquiert une cible à droite (converge tout de suite grâce au slew_max grand).
    gc.update(azimuth=1.0, elevation=0.0, confidence=1.0, now_ms=0)
    assert gc.tick(now_ms=0) == 70
    assert gc.state == TRACKING

    # Silence : au-delà du timeout -> LOST, retour lent (pas de 1 par tick).
    out = gc.tick(now_ms=2000)
    assert gc.state == LOST
    assert out == 69  # 70 -> 69 (slew_return=1)
    assert gc.tick(now_ms=2100) == 68

    # On laisse revenir jusqu'au centre.
    last = out
    for t in range(2200, 5000, 100):
        r = gc.tick(now_ms=t)
        if r is not None:
            last = r
    assert last == 50               # recentré
    assert gc.state == IDLE         # puis IDLE
    assert gc.tick(now_ms=6000) is None  # plus aucune publication


def test_reacquisition_relance_tracking():
    gc = GazeControl(gain=20, ema_alpha=1.0, slew_max=1000, slew_return=1,
                     timeout_ms=1500, enabled=True)
    gc.update(azimuth=1.0, elevation=0.0, confidence=1.0, now_ms=0)
    gc.tick(now_ms=0)
    gc.tick(now_ms=2000)            # bascule LOST
    assert gc.state == LOST
    # Nouvelle détection -> re-TRACKING immédiat.
    gc.update(azimuth=-1.0, elevation=0.0, confidence=1.0, now_ms=2100)
    assert gc.state == TRACKING
    assert gc.tick(now_ms=2100) == 30


# --------------------------------------------------------------------------
# Activation / désactivation (on/off) : reset complet
# --------------------------------------------------------------------------
def test_desactive_ne_publie_rien_et_reset():
    gc = GazeControl(gain=20, ema_alpha=1.0, slew_max=1000, enabled=True)
    gc.update(azimuth=1.0, elevation=0.0, confidence=1.0, now_ms=0)
    gc.tick(now_ms=0)               # position = 70
    gc.set_enabled(False)
    assert gc.tick(now_ms=0) is None
    assert gc.state == IDLE
    assert gc.position == 50        # reset au centre
    assert gc.last_published is None


def test_demarre_desactive_par_defaut():
    gc = GazeControl()              # enabled par défaut = False
    gc.update(azimuth=1.0, elevation=0.0, confidence=1.0, now_ms=0)
    assert gc.tick(now_ms=0) is None
    assert gc.state == IDLE


def test_reactivation_repart_propre():
    gc = GazeControl(gain=20, ema_alpha=1.0, slew_max=1000, enabled=True)
    gc.update(azimuth=1.0, elevation=0.0, confidence=1.0, now_ms=0)
    gc.tick(now_ms=0)
    gc.set_enabled(False)           # reset
    gc.set_enabled(True)            # ré-activation : état neutre, attend une détection
    assert gc.state == IDLE
    assert gc.tick(now_ms=0) is None
    gc.update(azimuth=-0.5, elevation=0.0, confidence=1.0, now_ms=0)
    assert gc.tick(now_ms=0) == 40  # 50 + 20*(-0.5)


# --------------------------------------------------------------------------
# Lissage EMA : l'azimut brut n'est pas suivi instantanément
# --------------------------------------------------------------------------
def test_ema_amortit_le_bruit():
    gc = GazeControl(gain=20, ema_alpha=0.5, slew_max=1000, enabled=True)
    # Premier échantillon initialise l'EMA (pas d'amortissement au démarrage).
    gc.update(azimuth=0.0, elevation=0.0, confidence=1.0, now_ms=0)
    assert gc.tick(now_ms=0) == 50
    # Saut brusque à 1.0 : EMA = 0.5*1 + 0.5*0 = 0.5 -> consigne 60, pas 70.
    gc.update(azimuth=1.0, elevation=0.0, confidence=1.0, now_ms=0)
    assert gc.tick(now_ms=0) == 60
