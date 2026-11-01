"""Tests de robot/move/follow_control.py — logique PURE du suivi aux roues.

Ce module commande les 50 kg du robot : chaque garde-fou (zéro sur perte de
cible, zéro sur désactivation, plafonds absolus, marche arrière interdite,
confiance minimale) est figé ici par un test. Horloge passée en paramètre
(now_ms) : aucun sleep, tests déterministes.
"""

import pytest

from robot.move.follow_control import (
    ABS_MAX_ANG, ABS_MAX_LIN, FollowConfig, FollowControl,
)


def _engaged(config=None, now=1000):
    """Un FollowControl activé avec une cible fraîche : personne à droite de
    l'image (azimut +0.5), loin (hauteur 0.2 < cible 0.55), sûre (0.9)."""
    ctl = FollowControl(config or FollowConfig(), enabled=True)
    ctl.update(0.5, 0.2, 0.9, now)
    return ctl


def _converge(ctl, now, ticks=100):
    """Fait converger le slew : ticke en rafale (cible non périmée) et renvoie
    la dernière commande."""
    command = None
    for _ in range(ticks):
        command = ctl.tick(now)
    return command


# --------------------------------------------------------------------------
# Sécurité : désactivé par défaut, silence total.
# --------------------------------------------------------------------------

def test_desactive_par_defaut_aucune_publication():
    ctl = FollowControl(FollowConfig())
    ctl.update(0.5, 0.2, 0.9, 1000)  # ignoré : désactivé
    assert ctl.tick(1000) is None
    assert ctl.tick(1100) is None


def test_desactivation_en_plein_suivi_publie_un_zero_puis_silence():
    ctl = _engaged()
    assert ctl.tick(1010) is not None  # suivi actif, ça publie

    ctl.set_enabled(False)
    assert ctl.tick(1020) == (0.0, 0.0)  # zéro FRANC, une fois
    assert ctl.tick(1030) is None        # puis silence total
    assert ctl.tick(1040) is None


# --------------------------------------------------------------------------
# Sens et amplitude de la rotation.
# --------------------------------------------------------------------------

def test_personne_a_droite_rotation_horaire():
    # Azimut +0.5 (droite image caméra), direction_sign=+1 -> ang NÉGATIF
    # (rotation horaire, convention REP-103) pour recentrer.
    ctl = _engaged()
    lin, ang = _converge(ctl, 1010)
    assert ang < 0


def test_direction_sign_inverse_le_sens():
    ctl = _engaged(FollowConfig(direction_sign=-1))
    lin, ang = _converge(ctl, 1010)
    assert ang > 0


def test_zone_morte_azimut_zero_rotation():
    ctl = FollowControl(FollowConfig(az_deadzone=0.15), enabled=True)
    ctl.update(0.1, 0.2, 0.9, 1000)  # 0.1 < deadzone 0.15
    lin, ang = _converge(ctl, 1010)
    assert ang == 0.0
    assert lin > 0  # loin -> avance quand même


# --------------------------------------------------------------------------
# Avance/distance (hauteur de silhouette).
# --------------------------------------------------------------------------

def test_personne_loin_avance_personne_a_distance_stop():
    ctl = _engaged()  # hauteur 0.2 << cible 0.55
    lin, _ = _converge(ctl, 1010)
    assert lin > 0

    # La personne est maintenant à la distance de confort (dans la zone morte).
    ctl.update(0.0, 0.55, 0.9, 2000)
    # Purge le lissage EMA : plusieurs mesures à la bonne distance.
    for t in range(2001, 2020):
        ctl.update(0.0, 0.55, 0.9, t)
    lin, ang = _converge(ctl, 2020)
    assert lin == 0.0
    assert ang == 0.0


def test_personne_trop_proche_pas_de_recul_par_defaut():
    # Hauteur 0.9 >> cible 0.55 : la personne est TROP proche. Par défaut
    # (allow_reverse=False), le robot NE RECULE PAS (caméra vers l'avant =
    # recul aveugle) : il s'arrête, c'est tout.
    ctl = FollowControl(FollowConfig(), enabled=True)
    for t in range(1000, 1020):
        ctl.update(0.0, 0.9, 0.9, t)
    lin, _ = _converge(ctl, 1020)
    assert lin == 0.0


def test_recul_autorise_reste_borne():
    ctl = FollowControl(FollowConfig(allow_reverse=True, max_lin=0.25), enabled=True)
    for t in range(1000, 1020):
        ctl.update(0.0, 1.0, 0.9, t)
    lin, _ = _converge(ctl, 1020)
    assert lin < 0
    assert lin >= -0.25


# --------------------------------------------------------------------------
# Plafonds : paramètres ET absolus.
# --------------------------------------------------------------------------

def test_plafonds_parametres_respectes():
    ctl = _engaged(FollowConfig(ang_gain=100.0, lin_gain=100.0,
                                max_ang=0.6, max_lin=0.25))
    lin, ang = _converge(ctl, 1010)
    assert abs(ang) <= 0.6
    assert 0 < lin <= 0.25


def test_plafonds_absolus_bornent_les_parametres_exotiques():
    # Des plafonds de config délirants ne passent PAS les plafonds absolus.
    ctl = FollowControl(FollowConfig(max_lin=99.0, max_ang=99.0))
    assert ctl.max_lin <= ABS_MAX_LIN
    assert ctl.max_ang <= ABS_MAX_ANG


# --------------------------------------------------------------------------
# Perte de cible et confiance.
# --------------------------------------------------------------------------

def test_cible_perdue_zero_franc_immediat_puis_silence():
    ctl = _engaged(now=1000)
    assert ctl.tick(1010) is not None  # suivi actif

    # Plus aucune détection : au-delà du timeout, zéro FRANC (pas de slew),
    # puis plus rien.
    late = 1000 + FollowConfig().timeout_ms + 1
    assert ctl.tick(late) == (0.0, 0.0)
    assert ctl.tick(late + 10) is None


def test_confiance_basse_ignoree_et_ne_rafraichit_pas_le_timeout():
    ctl = _engaged(now=1000)
    # Détections douteuses en rafale : ignorées, le timeout court toujours.
    for t in range(1100, 1700, 50):
        ctl.update(0.5, 0.2, 0.1, t)  # confiance 0.1 < seuil 0.4
    late = 1000 + FollowConfig().timeout_ms + 1
    assert ctl.tick(late) == (0.0, 0.0)  # cible perdue malgré les updates douteux


# --------------------------------------------------------------------------
# Slew : pas d'à-coups.
# --------------------------------------------------------------------------

def test_slew_limite_la_variation_par_tick():
    cfg = FollowConfig(lin_slew=0.05, ang_slew=0.15)
    ctl = FollowControl(cfg, enabled=True)
    ctl.update(1.0, 0.0, 0.9, 1000)  # cible extrême : plein écart demandé
    lin, ang = ctl.tick(1010)
    # Premier tick : au plus UN pas de slew depuis 0.
    assert abs(lin) <= cfg.lin_slew + 1e-9
    assert abs(ang) <= cfg.ang_slew + 1e-9


def test_reacquisition_apres_perte_repart_de_zero():
    ctl = _engaged(now=1000)
    _converge(ctl, 1010)  # vitesses non nulles

    late = 1000 + FollowConfig().timeout_ms + 1
    ctl.tick(late)  # perte -> zéro + reset

    # Nouvelle personne : le slew repart de 0 (pas de la vitesse d'avant).
    ctl.update(-1.0, 0.2, 0.9, late + 100)
    lin, ang = ctl.tick(late + 110)
    assert abs(lin) <= FollowConfig().lin_slew + 1e-9
    assert abs(ang) <= FollowConfig().ang_slew + 1e-9
