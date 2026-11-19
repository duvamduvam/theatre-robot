"""reglages : config/corps_sur.yaml GRAVÉ en entier, bornes dures (§5.6, §6.2)."""
import copy

import pytest
import yaml

from conftest import CONFIG_YAML
from didier_corps_sur.geometrie import Caisse, PoseLidar
from didier_corps_sur.reglages import ReglagesError, charger_reglages, reglages_depuis

ATTENDU = {
    "terrain": "reel",
    "caisse": {"x_avant": 0.30, "x_arriere": -0.57, "demi_largeur": 0.40, "x_essieu": 0.10,
               "rayon_balayage": 0.65},
    "lidar": {"x": 0.33, "y": 0.0, "lacet_rad": 0.0, "hauteur_plan_m": 0.25,
              "masques_deg": [[90.0, 270.0]],
              "temoin": {"exige": False, "secteur_deg": None, "distance_m": None, "points_min": 0}},
    "balayage": {"portee_min_m": 0.05, "portee_max_m": 12.0, "rayons_min": 300, "age_max_reception_s": 0.25},
    "zones": {"marge_arret_m": 0.60, "marge_ralenti_m": 1.20, "facteur_ralenti": 0.5, "hysteresis_m": 0.05,
              "balayages_de_sortie": 3},
    "couverture": {"part_aveugle_max": 0.10, "angulaire_aveugle_autorise": False, "w_max_aveugle": 0.3},
    "canaux": {"anim": {"v_max": 0.25, "w_max": 0.5}, "follow": {"v_max": 0.25, "w_max": 0.5},
               "web": {"v_max": 0.25, "w_max": 0.5}},
    "capteur": {"perime_s": 0.30, "sante_s": 1.0},
    "superviseur": {"exige": True, "perime_s": 1.0},
    "duree": {"duree_max_mouvement_s": 4.0, "pause_s": 1.0},
}


def donnees():
    with open(CONFIG_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f)


def avec(chemin, valeur, data=None):
    data = copy.deepcopy(data or ATTENDU)
    node = data
    cles = chemin.split(".")
    for cle in cles[:-1]:
        node = node[cle]
    node[cles[-1]] = valeur
    return data


def test_config_gravee():
    assert donnees() == ATTENDU


def test_config_du_package_chargee():
    r = charger_reglages(CONFIG_YAML, "42")
    assert r.terrain == "reel"
    assert r.caisse == Caisse(0.30, -0.57, 0.40, 0.10, 0.65)
    assert r.lidar == PoseLidar(0.33, 0.0, 0.0)
    assert r.balayage.masques_deg == ((90.0, 270.0),)
    assert r.garde.superviseur_exige is True
    assert r.filtre.angulaire_aveugle_autorise is False
    assert r.filtre.plafonds["follow"].v_max == 0.25


# Les huit bornes dures du §5.6, chacune franchie d'un cran.
BORNES = [
    ("zones.marge_arret_m", 0.59, "marge_arret_m"),
    ("zones.marge_ralenti_m", 0.89, "marge_ralenti_m"),
    ("capteur.perime_s", 0.31, "capteur.perime_s"),
    ("superviseur.perime_s", 1.01, "superviseur.perime_s"),
    ("zones.facteur_ralenti", 0.51, "facteur_ralenti"),
    ("canaux.web.v_max", 0.91, "canaux.web.v_max"),
    ("couverture.part_aveugle_max", 0.11, "part_aveugle_max"),
    ("terrain", "sim", "hors ROS_DOMAIN_ID=43"),
]


@pytest.mark.parametrize("chemin, valeur, message", BORNES)
def test_borne_dure_franchie_refusee(chemin, valeur, message):
    with pytest.raises(ReglagesError, match=message):
        reglages_depuis(avec(chemin, valeur), "42")


def test_huit_messages_distincts():
    messages = set()
    for chemin, valeur, _ in BORNES:
        with pytest.raises(ReglagesError) as e:
            reglages_depuis(avec(chemin, valeur), "42")
        messages.add(str(e.value))
    assert len(messages) == 8


@pytest.mark.parametrize("chemin, valeur", [
    ("zones.marge_arret_m", 0.60), ("zones.marge_ralenti_m", 0.90), ("capteur.perime_s", 0.30),
    ("superviseur.perime_s", 1.0), ("zones.facteur_ralenti", 0.5), ("canaux.anim.v_max", 0.9),
    ("couverture.part_aveugle_max", 0.10),
])
def test_bornes_exactes_acceptees(chemin, valeur):
    reglages_depuis(avec(chemin, valeur), "42")


def test_terrain_sim_en_domaine_43_accepte():
    assert reglages_depuis(avec("terrain", "sim"), "43").terrain == "sim"


def test_terrain_reel_accepte_en_sim():
    # CS12 : la configuration du robot réel est jouée en sim.
    reglages_depuis(ATTENDU, "43")


@pytest.mark.parametrize("chemin, valeur", [
    ("canaux.follow.v_max", -0.2),       # inverserait le sens
    ("canaux.follow.v_max", 0.0),
    ("canaux.web.w_max", -1.0),
    ("zones.facteur_ralenti", -0.5),
    ("couverture.w_max_aveugle", 0.0),
    ("zones.balayages_de_sortie", 0),
    ("zones.balayages_de_sortie", 2.5),
    ("balayage.rayons_min", "300"),
    ("superviseur.exige", "oui"),
    ("terrain", "rue"),
    ("caisse.x_essieu", 0.30),            # invariant du pivot : 0,65 > 0,55
    ("lidar.masques_deg", [[90.0]]),
    ("lidar.masques_deg", [[float("nan"), 10.0]]),
])
def test_valeurs_absurdes_refusees(chemin, valeur):
    with pytest.raises(ReglagesError):
        reglages_depuis(avec(chemin, valeur), "42")


def test_invariant_du_pivot_dans_le_message():
    with pytest.raises(ReglagesError, match="invariant du pivot"):
        reglages_depuis(avec("caisse.x_essieu", 0.30), "42")


def test_reglage_manquant_refuse():
    data = copy.deepcopy(ATTENDU)
    del data["capteur"]["perime_s"]
    with pytest.raises(ReglagesError, match="capteur.perime_s"):
        reglages_depuis(data, "42")


def test_temoin_exige_complet():
    temoin = {"exige": True, "secteur_deg": [175.0, 185.0], "distance_m": [0.06, 0.10], "points_min": 5}
    r = reglages_depuis(avec("lidar.temoin", temoin), "42")
    assert r.balayage.temoin.points_min == 5
    with pytest.raises(ReglagesError):
        reglages_depuis(avec("lidar.temoin", dict(temoin, points_min=0)), "42")


def test_fichier_absent_refuse(tmp_path):
    with pytest.raises(ReglagesError, match="illisible"):
        charger_reglages(str(tmp_path / "absent.yaml"), "42")
