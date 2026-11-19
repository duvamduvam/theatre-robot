"""moteur : le corps sûr assemblé — séquence des appels, ZÉRO ANTICIPÉ, état, diagnostics (A0-4).

Configurations RÉELLES des machines (machines/sim/robot/corps_sur.yaml, machines/robot/corps_sur.yaml).
Attendus écrits EN DUR. Balayages synthétiques : 500 rayons, rayon 0 = devant (angle 0),
pas 0,72° ; horloge du nœud injectée ; un balayage toutes les 0,1 s, stamp = instant de réception
moins 0,02 s (âge 20 ms, sous la borne de 0,25 s).
"""
import copy
import json
import math

import pytest
import yaml

from conftest import MONO
from didier_corps_sur.moteur import CorpsSur, Sortie, arrondir_d_min
from didier_corps_sur.reglages import reglages_depuis

SIM_YAML = MONO / "machines" / "sim" / "robot" / "corps_sur.yaml"
ROBOT_YAML = MONO / "machines" / "robot" / "corps_sur.yaml"
N = 500
INC = 2 * math.pi / N


def donnees(chemin):
    return yaml.safe_load(chemin.read_text(encoding="utf-8"))


def corps(chemin=SIM_YAML, **surcharges):
    data = copy.deepcopy(donnees(chemin))
    for cle, valeur in surcharges.items():
        noeud = data
        *tete, fin = cle.split("__")
        for c in tete:
            noeud = noeud[c]
        noeud[fin] = valeur
    return CorpsSur(reglages_depuis(data, "43"))


def balayage(c, t, points=()):
    """Un balayage reçu à t ; `points` = [(indice de rayon, distance)]."""
    d = [math.inf] * N
    for i, r in points:
        d[i] = r
    return c.balayage(t, t - 0.02, 0.0, INC, d)


def armer(c, de=0.0, a=1.0):
    """Balayages vides à 10 Hz de `de` à `a` inclus : sain depuis `de`, ARME à `de` + 1,0."""
    for k in range(round(de * 10), round(a * 10) + 1):
        balayage(c, k / 10)


# Un point à 0,56 m devant le lidar (0,33 ; 0) : (0,89 ; 0), à 0,59 m de la caisse → ARRET.
DEVANT_0_59 = [(0, 0.56)]


def test_demarrage_refuse_tout():
    c = corps()
    assert c.consigne("follow", 0.0, 0.3, 0.0) == [Sortie("follow", 0.0, 0.0, "DEMARRAGE")]
    assert c.etat(0.0)["etat"] == "DEMARRAGE"
    assert c.etat(0.0)["cause"] == "capteur_absent"


def test_arme_apres_une_seconde_saine_puis_laisse_passer():
    c = corps()
    armer(c, 0.0, 0.9)
    assert c.etat(0.9)["etat"] == "DEMARRAGE"
    balayage(c, 1.0)
    assert c.etat(1.0)["etat"] == "ARME"
    assert c.consigne("follow", 1.05, 0.3, 0.0) == [Sortie("follow", 0.3, 0.0, None)]


def test_zero_anticipe_sur_les_seuls_canaux_actifs():
    c = corps()
    c.consigne("web", 0.0, 0.2, 0.0)            # vieille de 1,1 s au moment de l'arrêt : muette
    armer(c)
    c.consigne("follow", 1.05, 0.3, 0.0)
    c.consigne("anim", 1.06, 0.4, 0.0)
    # Le balayage qui voit l'obstacle publie LUI-MÊME le zéro, sans attendre la source.
    assert balayage(c, 1.1, DEVANT_0_59) == [Sortie("anim", 0.0, 0.0, "ARRET"),
                                             Sortie("follow", 0.0, 0.0, "ARRET")]
    # Une seule fois : au passage en blocage, pas à chaque balayage.
    assert balayage(c, 1.2, DEVANT_0_59) == []
    assert c.consigne("follow", 1.25, 0.3, 0.0) == [Sortie("follow", 0.0, 0.0, "ARRET")]


def test_canal_actif_jusqu_a_une_seconde():
    c = corps()
    armer(c)
    c.consigne("follow", 1.0, 0.3, 0.0)
    for k in range(11, 20):
        balayage(c, k / 10)
    # 0,99 s après la dernière demande : encore actif (fenêtre = 2 × le délai du mux).
    assert balayage(c, 1.99, DEVANT_0_59) == [Sortie("follow", 0.0, 0.0, "ARRET")]
    d = corps()
    armer(d)
    d.consigne("follow", 1.0, 0.3, 0.0)
    for k in range(11, 21):
        balayage(d, k / 10)
    # 1,01 s après : muet, aucun zéro (le mux l'a déjà oublié depuis 0,5 s).
    assert balayage(d, 2.01, DEVANT_0_59) == []


def test_reprise_apres_trois_balayages_degages():
    c = corps()
    armer(c)
    balayage(c, 1.1, DEVANT_0_59)
    balayage(c, 1.2)
    balayage(c, 1.3)
    assert c.consigne("follow", 1.35, 0.3, 0.0) == [Sortie("follow", 0.0, 0.0, "ARRET")]
    balayage(c, 1.4)
    assert c.consigne("follow", 1.45, 0.3, 0.0) == [Sortie("follow", 0.3, 0.0, None)]


def test_ralenti_puis_plafond():
    c = corps()
    armer(c)
    # 0,57 m devant le lidar + 0,33 : (1,20 ; 0) → 0,90 m de la caisse : RALENTI.
    balayage(c, 1.1, [(0, 0.87)])
    assert c.consigne("follow", 1.15, 0.3, 0.0) == [Sortie("follow", 0.15, 0.0, None)]
    assert c.consigne("follow", 1.16, 0.8, 0.0) == [Sortie("follow", 0.25, 0.0, None)]


def test_capteur_perdu_au_tic_zero_et_verrou():
    c = corps()
    armer(c)
    c.consigne("follow", 1.05, 0.3, 0.0)
    assert c.tic(1.25) == []
    assert c.tic(1.35) == [Sortie("follow", 0.0, 0.0, "VERROU")]
    assert (c.etat(1.35)["etat"], c.etat(1.35)["cause"]) == ("VERROU", "capteur_perdu")


def test_verrou_ne_se_leve_que_par_rearmement():
    c = corps()
    armer(c)
    c.tic(1.35)
    armer(c, 2.0, 3.5)
    assert c.etat(3.5)["etat"] == "VERROU"
    assert c.consigne("follow", 3.55, 0.3, 0.0) == [Sortie("follow", 0.0, 0.0, "VERROU")]
    assert c.rearmer(3.56) == (True, "réarmé")
    assert c.consigne("follow", 3.57, 0.3, 0.0) == [Sortie("follow", 0.3, 0.0, None)]


def test_rearmement_refuse_capteur_sain_depuis_0_9_s():
    c = corps()
    armer(c)
    c.tic(1.35)
    armer(c, 2.0, 2.9)
    assert c.rearmer(2.9) == (False, "capteur sain depuis moins de 1.0 s")


def test_e_stop_zero_verrou_puis_rearmement_apres_relache():
    c = corps()
    armer(c)
    c.consigne("web", 1.05, 0.2, 0.0)
    assert c.e_stop(True, 1.06) == [Sortie("web", 0.0, 0.0, "VERROU")]
    assert c.etat(1.06)["cause"] == "e_stop"
    assert c.rearmer(1.07) == (False, "cause présente : e_stop")
    c.e_stop(False, 1.08)
    assert c.consigne("web", 1.09, 0.2, 0.0) == [Sortie("web", 0.0, 0.0, "VERROU")]
    assert c.rearmer(1.09) == (True, "réarmé")


def test_le_zero_part_aux_autres_canaux_quand_le_blocage_nait_pendant_une_demande():
    c = corps()
    armer(c)
    c.consigne("anim", 1.05, 0.4, 0.0)
    # Le capteur est périmé quand la demande follow arrive : le tic de la demande verrouille,
    # anim reçoit son zéro AVANT la sortie (nulle) de follow.
    assert c.consigne("follow", 1.35, 0.3, 0.0) == [Sortie("anim", 0.0, 0.0, "VERROU"),
                                                    Sortie("follow", 0.0, 0.0, "VERROU")]


def test_balayage_fige_ne_nourrit_pas_le_capteur():
    """Un republieur figé (même stamp, reçu de plus en plus tard) ne prouve pas que le lidar vit."""
    c = corps()
    armer(c)                                   # dernier balayage valide : reçu 1,0, stamp 0,98
    c.consigne("follow", 1.05, 0.3, 0.0)
    for t in (1.1, 1.2):
        c.balayage(t, 0.98, 0.0, INC, [math.inf] * N)
    assert c.tic(1.25) == []
    assert c.tic(1.35) == [Sortie("follow", 0.0, 0.0, "VERROU")]
    assert c.etat(1.35)["cause"] == "capteur_perdu"


def test_balayage_trop_vieux_ne_nourrit_pas_mais_arrete():
    """Invalide (âge 0,30 s > 0,25) : ne nourrit pas le chien de garde, mais l'obstacle qu'il
    montre fait ENTRER en ARRET (zéro anticipé)."""
    c = corps()
    armer(c)
    c.consigne("follow", 1.05, 0.3, 0.0)
    d = [math.inf] * N
    d[0] = 0.56
    assert c.balayage(1.1, 0.80, 0.0, INC, d) == [Sortie("follow", 0.0, 0.0, "ARRET")]
    assert c.tic(1.35) == []                   # déjà bloqué : aucun second zéro
    assert c.etat(1.35)["etat"] == "VERROU"    # 1,35 − 1,0 > 0,30 : le balayage trop vieux n'a rien nourri


def test_pause_duree_zero_anticipe_aux_autres_canaux():
    c = corps(ROBOT_YAML)
    armer(c)
    for k in range(0, 58):
        t = round(1.03 + 0.07 * k, 2)
        balayage(c, t)
        c.consigne("follow", t, 0.2, 0.0)
    # Dernière demande follow à 5,02 (3,99 s de mouvement) ; web demande au même instant.
    assert c.consigne("web", 5.02, 0.1, 0.0) == [Sortie("web", 0.1, 0.0, None)]
    # Le tic du balayage de 5,09 voit 4,06 s de mouvement : zéro anticipé sur les DEUX canaux actifs.
    assert balayage(c, 5.09) == [Sortie("follow", 0.0, 0.0, "PAUSE_DUREE"),
                                 Sortie("web", 0.0, 0.0, "PAUSE_DUREE")]
    assert c.consigne("follow", 5.09, 0.2, 0.0) == [Sortie("follow", 0.0, 0.0, "PAUSE_DUREE")]


def test_consigne_non_finie():
    c = corps()
    armer(c)
    assert c.consigne("follow", 1.05, math.nan, 0.0) == [Sortie("follow", 0.0, 0.0, "consigne_invalide")]
    assert c.consigne("follow", 1.06, 0.1, math.inf) == [Sortie("follow", 0.0, 0.0, "consigne_invalide")]


def test_canal_inconnu_refuse():
    with pytest.raises(ValueError):
        corps().consigne("remote", 0.0, 0.1, 0.0)


def test_sim_recul_refuse_tour_tolere():
    c = corps()
    armer(c)
    assert c.consigne("anim", 1.05, -0.4, 0.0) == [Sortie("anim", 0.0, 0.0, "recul_aveugle")]
    # Tour toléré en sim (décision du 18/11) : plafonné à min(3,2 ; w_max_aveugle 1,0).
    assert c.consigne("anim", 1.06, 0.4, 2.0) == [Sortie("anim", 0.2, 1.0, None)]


def test_robot_tour_refuse_vitesse_plafonnee():
    c = corps(ROBOT_YAML)
    armer(c)
    assert c.consigne("follow", 1.05, 0.0, 0.3) == [Sortie("follow", 0.0, 0.0, "tour_aveugle")]
    assert c.consigne("follow", 1.06, 0.4, 0.0) == [Sortie("follow", 0.25, 0.0, None)]


def test_arriere_vu_obstacle_derriere_pendant_le_recul():
    """CS5, seconde moitié, au niveau du moteur : la pose A de la sim ne voit pas l'arrière."""
    c = corps(lidar__masques_deg=[])
    assert c.vue == {"avant": True, "arriere": True, "flanc_g": True, "flanc_d": True}
    armer(c)
    assert c.consigne("anim", 1.05, -0.4, 0.0) == [Sortie("anim", -0.4, 0.0, None)]
    # Rayon 250 = angle π : (0,33 − 1,40 ; 0) = (−1,07 ; 0), à 0,50 m de l'arrière de la caisse.
    assert balayage(c, 1.1, [(250, 1.40)]) == [Sortie("anim", 0.0, 0.0, "ARRET")]


def test_pause_duree_robot():
    """Durée bornée 4,0 s (robot) : demandes et balayages toutes les 0,07 s à partir de 1,03
    (aucun instant pile sur le seuil) ; la sortie part à 1,03, la pause tombe à 1,03 + 4,06."""
    c = corps(ROBOT_YAML)
    armer(c)
    sorties = []
    for k in range(0, 62):
        t = round(1.03 + 0.07 * k, 2)
        balayage(c, t)
        sorties.append((t, c.consigne("follow", t, 0.2, 0.0)[-1]))
    passes = [t for t, s in sorties if s.v == 0.2]
    coupees = [t for t, s in sorties if s.motif == "PAUSE_DUREE"]
    assert (passes[0], passes[-1], coupees[0], len(passes)) == (1.03, 5.02, 5.09, 58)
    assert c.etat(5.1)["zone"] == "PAUSE_DUREE"
    # Reprise : toutes les entrées nulles pendant 1,0 s (pause_s), pas avant.
    t = 5.40
    for k in range(0, 16):
        t = round(5.40 + 0.07 * k, 2)
        balayage(c, t)
        c.consigne("follow", t, 0.0, 0.0)
    assert t == 6.45
    balayage(c, 6.46)
    assert c.consigne("follow", 6.46, 0.2, 0.0) == [Sortie("follow", 0.2, 0.0, None)]


def test_etat_publie_sim_arme():
    c = corps()
    armer(c)
    assert json.loads(c.etat_json(1.0)) == {
        "etat": "ARME", "cause": "", "zone": "LIBRE", "d_min_m": None,
        "vue": {"avant": True, "arriere": False, "flanc_g": False, "flanc_d": False},
        "superviseur": "non_exige", "temoin": "non_exige", "terrain": "sim"}
    balayage(c, 1.1, [(0, 0.87)])
    assert c.etat(1.1)["d_min_m"] == 0.9
    assert c.etat(1.1)["zone"] == "RALENTI"


def test_arrondi_d_min_a_5_cm():
    assert [arrondir_d_min(d) for d in (0.72, 0.738, 0.59, 0.0, math.inf)] == [0.7, 0.75, 0.6, 0.0, None]


def test_diagnostics_niveaux():
    sim = corps()
    assert sim.diagnostic(0.0, None).niveau == 1            # DEMARRAGE : WARN
    armer(sim)
    d = sim.diagnostic(1.0, 0.0021)
    assert (d.niveau, d.message) == (0, "ARME, zone LIBRE")
    valeurs = dict(d.valeurs)
    assert (valeurs["rayons"], valeurs["points_valides"], valeurs["duree_rappel_scan_max_ms"]) == ("500", "0", "2.10")
    sim.consigne("anim", 1.05, -0.4, 0.0)
    assert dict(sim.diagnostic(1.05, None).valeurs)["refus_anim"] == "recul_aveugle"
    sim.tic(1.4)
    assert sim.diagnostic(1.4, None).niveau == 2            # VERROU : ERROR
    robot = corps(ROBOT_YAML)
    armer(robot)
    d = robot.diagnostic(1.0, None)
    assert (d.niveau, d.message) == (1, "ARME, zone LIBRE ; non exigé(s) : superviseur, temoin")


def test_superviseur_exige_battement_coupe():
    c = corps(ROBOT_YAML, superviseur__exige=True)
    armer(c)
    assert (c.etat(1.0)["etat"], c.etat(1.0)["cause"]) == ("DEMARRAGE", "superviseur_absent")
    for k in range(11, 21):
        c.battement(k / 10)
        balayage(c, k / 10)
    assert c.etat(2.0)["etat"] == "ARME"
    # Battement coupé à 2,0 : le capteur vit, la source demande ; présent jusqu'à 3,0 inclus.
    for k in range(21, 31):
        balayage(c, k / 10)
        c.consigne("follow", k / 10, 0.2, 0.0)
    assert c.tic(2.95) == []
    assert c.tic(3.05) == [Sortie("follow", 0.0, 0.0, "VERROU")]
    assert (c.etat(3.05)["etat"], c.etat(3.05)["cause"]) == ("VERROU", "superviseur_perdu")
