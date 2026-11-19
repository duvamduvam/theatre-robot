"""garde : DEMARRAGE / ARME / VERROU, péremptions, réarmement, durée bornée (§5.5-5.6, §6.2).
Les tics ne tombent jamais pile sur un seuil (arrondi flottant)."""
import pytest

from didier_corps_sur.garde import (ARME, DEMARRAGE, VERROU, Garde, ParametresGarde)


def garde(exige=False, duree=0.0):
    return Garde(ParametresGarde(capteur_perime_s=0.30, sante_s=1.0, superviseur_exige=exige,
                                 superviseur_perime_s=1.0, duree_max_mouvement_s=duree, pause_s=1.0))


def nourrir(g, de, a, battement=False):
    """Balayages valides (et battements) à 10 Hz de `de` à `a` inclus."""
    i = round(de * 10)
    while i <= round(a * 10):
        t = i / 10
        if battement:
            g.battement(t)
        g.balayage_valide(t)
        i += 1


def test_demarrage_sans_capteur():
    g = garde()
    assert g.tic(5.0) == DEMARRAGE
    assert g.cause == "capteur_absent"


def test_demarrage_s_arme_seul_apres_une_seconde_saine():
    g = garde()
    nourrir(g, 0.0, 0.9)
    assert g.etat == DEMARRAGE
    assert g.cause == "sante_en_cours"
    nourrir(g, 1.0, 1.1)
    assert g.etat == ARME


def test_capteur_perdu():
    g = garde()
    nourrir(g, 0.0, 1.0)
    assert g.tic(1.25) == ARME
    assert g.tic(1.35) == VERROU
    assert g.cause == "capteur_perdu"


def test_superviseur_perdu():
    g = garde(exige=True)
    nourrir(g, 0.0, 5.0, battement=True)
    nourrir(g, 5.1, 6.0)
    assert g.tic(5.95) == ARME
    g.balayage_valide(6.05)
    assert g.tic(6.05) == VERROU
    assert g.cause == "superviseur_perdu"


def test_superviseur_exige_jamais_entendu():
    g = garde(exige=True)
    nourrir(g, 0.0, 3.0)
    assert g.etat == DEMARRAGE
    assert g.cause == "superviseur_absent"
    assert g.superviseur_etat(3.0) == "absent"


def test_superviseur_non_exige():
    assert garde().superviseur_etat(0.0) == "non_exige"


def test_e_stop_verrouille_sur_le_champ():
    g = garde()
    nourrir(g, 0.0, 1.5)
    assert g.noter_e_stop(True, 1.52) == VERROU
    assert g.cause == "e_stop"
    g.noter_e_stop(False, 1.6)
    nourrir(g, 1.6, 2.0)
    assert g.etat == VERROU          # relâcher rend la télécommande, pas l'autonomie


def test_e_stop_au_demarrage_empeche_d_armer():
    g = garde()
    g.noter_e_stop(True, 0.0)
    nourrir(g, 0.0, 2.0)
    assert g.etat == DEMARRAGE
    assert g.cause == "e_stop"


def test_rearmement_cause_presente_refuse():
    g = garde()
    nourrir(g, 0.0, 1.5)
    g.noter_e_stop(True, 1.52)
    nourrir(g, 1.6, 3.0)                 # capteur sain depuis longtemps
    ok, raison = g.rearmer(3.0)
    assert not ok
    assert "e_stop" in raison
    assert g.etat == VERROU


def test_rearmement_superviseur_encore_absent_refuse():
    g = garde(exige=True)
    nourrir(g, 0.0, 2.0, battement=True)
    nourrir(g, 2.1, 4.0)                 # battement coupé à 2,0 → VERROU à 3,1
    assert g.etat == VERROU
    ok, _ = g.rearmer(4.0)
    assert not ok


def test_rearmement_apres_capteur_perdu_attend_une_seconde_saine():
    g = garde()
    nourrir(g, 0.0, 1.0)
    g.tic(1.35)
    assert g.etat == VERROU
    nourrir(g, 2.0, 2.9)                 # sain depuis 2,0
    ok, raison = g.rearmer(2.9)          # 0,9 s
    assert not ok and "sain" in raison
    nourrir(g, 3.0, 3.1)
    ok, _ = g.rearmer(3.1)               # 1,1 s
    assert ok
    assert g.etat == ARME


def test_rearmement_sans_verrou_refuse():
    g = garde()
    assert g.rearmer(0.0)[0] is False


def _bouger(g, de, a, entree_nulle=False):
    """Entrée et sortie du canal follow à 20 Hz, de `de` à `a` inclus."""
    for i in range(round(de * 20), round(a * 20) + 1):
        t = i / 20
        g.noter_entree("follow", t, nulle=entree_nulle)
        g.noter_sortie("follow", t, nulle=entree_nulle or g.pause_duree)


def test_duree_bornee():
    g = garde(duree=4.0)
    _bouger(g, 0.0, 3.95)
    assert not g.pause_duree
    _bouger(g, 4.0, 4.05)
    assert g.pause_duree                 # PAUSE_DUREE à 4,05
    _bouger(g, 4.10, 5.0, entree_nulle=True)
    g.tic(5.0)
    assert g.pause_duree                 # entrées nulles depuis 0,9 s : maintenue
    _bouger(g, 5.05, 5.20, entree_nulle=True)
    g.tic(5.20)
    assert not g.pause_duree             # 1,1 s : levée


def test_duree_bornee_une_entree_qui_insiste_maintient_la_pause():
    g = garde(duree=4.0)
    _bouger(g, 0.0, 6.0)
    assert g.pause_duree


def test_duree_bornee_source_muette():
    g = garde(duree=4.0)
    _bouger(g, 0.0, 4.05)
    assert g.pause_duree
    # Plus rien après 4,05 : muette à 4,55, pause levée 1 s plus tard.
    g.tic(5.50)
    assert g.pause_duree
    g.tic(5.60)
    assert not g.pause_duree


def test_duree_bornee_interrompue_ne_compte_pas():
    g = garde(duree=4.0)
    _bouger(g, 0.0, 3.0)
    g.noter_sortie("follow", 3.02, nulle=True)
    _bouger(g, 3.05, 6.5)
    assert not g.pause_duree


def test_duree_desactivee():
    g = garde(duree=0.0)
    _bouger(g, 0.0, 10.0)
    assert not g.pause_duree


@pytest.mark.parametrize("canal", ["anim", "web"])
def test_duree_bornee_deux_canaux_relayes(canal):
    # Changer de canal ne remet pas le compteur à zéro.
    g = garde(duree=4.0)
    _bouger(g, 0.0, 2.0)
    for i in range(round(2.05 * 20), round(4.5 * 20) + 1):
        t = i / 20
        g.noter_entree(canal, t, nulle=False)
        g.noter_sortie(canal, t, nulle=g.pause_duree)
    assert g.pause_duree
