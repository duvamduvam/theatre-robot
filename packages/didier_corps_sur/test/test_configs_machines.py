"""Les deux configurations de MACHINE (spec A0 §5.4) GRAVÉES en entier : machines/sim/robot/corps_sur.yaml
et machines/robot/corps_sur.yaml. Changer un chiffre exige de toucher ce test, dans un commit qui le dit."""
import copy

import pytest
import yaml

from conftest import MONO
from didier_corps_sur.moteur import CorpsSur
from didier_corps_sur.reglages import ReglagesError, charger_reglages

SIM = MONO / "machines" / "sim" / "robot" / "corps_sur.yaml"
ROBOT = MONO / "machines" / "robot" / "corps_sur.yaml"

COMMUN = {
    "caisse": {"x_avant": 0.30, "x_arriere": -0.57, "demi_largeur": 0.40, "x_essieu": 0.10,
               "rayon_balayage": 0.65},
    "lidar": {"x": 0.33, "y": 0.0, "lacet_rad": 0.0, "hauteur_plan_m": 0.25,
              "masques_deg": [[90.0, 270.0]],
              "temoin": {"exige": False, "secteur_deg": None, "distance_m": None, "points_min": 0}},
    "balayage": {"portee_min_m": 0.05, "portee_max_m": 12.0, "rayons_min": 300, "age_max_reception_s": 0.25},
    "zones": {"marge_arret_m": 0.60, "marge_ralenti_m": 1.20, "facteur_ralenti": 0.5, "hysteresis_m": 0.05,
              "balayages_de_sortie": 3},
    "capteur": {"perime_s": 0.30, "sante_s": 1.0},
}
ATTENDU_SIM = {
    "terrain": "sim", **copy.deepcopy(COMMUN),
    "couverture": {"part_aveugle_max": 0.10, "angulaire_aveugle_autorise": True, "w_max_aveugle": 1.0},
    "canaux": {"anim": {"v_max": 0.9, "w_max": 3.2}, "follow": {"v_max": 0.5, "w_max": 1.0},
               "web": {"v_max": 0.5, "w_max": 1.0}},
    "superviseur": {"exige": False, "perime_s": 1.0},
    "duree": {"duree_max_mouvement_s": 0.0, "pause_s": 1.0},
}
ATTENDU_ROBOT = {
    "terrain": "reel", **copy.deepcopy(COMMUN),
    "couverture": {"part_aveugle_max": 0.10, "angulaire_aveugle_autorise": False, "w_max_aveugle": 0.3},
    "canaux": {"anim": {"v_max": 0.25, "w_max": 0.5}, "follow": {"v_max": 0.25, "w_max": 0.5},
               "web": {"v_max": 0.25, "w_max": 0.5}},
    "superviseur": {"exige": False, "perime_s": 1.0},
    "duree": {"duree_max_mouvement_s": 4.0, "pause_s": 1.0},
}


def test_sim_gravee():
    assert yaml.safe_load(SIM.read_text(encoding="utf-8")) == ATTENDU_SIM


def test_robot_gravee():
    assert yaml.safe_load(ROBOT.read_text(encoding="utf-8")) == ATTENDU_ROBOT


def test_sim_refusee_hors_du_domaine_43():
    with pytest.raises(ReglagesError, match="terrain sim refusé hors ROS_DOMAIN_ID=43"):
        charger_reglages(str(SIM), "42")
    assert charger_reglages(str(SIM), "43").terrain == "sim"


def test_robot_accepte_partout():
    for domaine in ("42", "43", None):
        assert charger_reglages(str(ROBOT), domaine).terrain == "reel"


def test_couverture_pose_a_avant_seul():
    for chemin in (SIM, ROBOT):
        assert CorpsSur(charger_reglages(str(chemin), "43")).vue == {
            "avant": True, "arriere": False, "flanc_g": False, "flanc_d": False}, chemin.name
