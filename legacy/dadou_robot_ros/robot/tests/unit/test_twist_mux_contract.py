"""Contrat GELÉ de la chaîne roues (twist_mux) -- vérifié depuis le YAML réel,
pas depuis une copie (une divergence config/contrat serait un trou de sécurité).

Priorités : remote (télécommande physique, 100) > web (pilotage web, 50) >
follow (suivi de personne autonome, 20) > anim (animations, 10). Le verrou
e_stop est latché à 255. Tous les timeouts de topic sont à 0.5 s. C'est le
contrat du plan (etude-interface-web.md §5) étendu au suivi (2026-07-11) : ni
le web ni le suivi autonome ne peuvent JAMAIS prendre le pas sur la
télécommande physique.

pyyaml est présent dans le venv de dev (vérifié) ; on parse donc le vrai fichier
livré au twist_mux plutôt que de dupliquer les valeurs ici.
"""

import pathlib

import yaml

# conf/ros2_dependencies/robot_drive/config/twist_mux.yaml, remonté depuis
# robot/tests/unit/ (4 parents jusqu'à la racine du dépôt).
TWIST_MUX_YAML = (
    pathlib.Path(__file__).resolve().parents[3]
    / "conf" / "ros2_dependencies" / "robot_drive" / "config" / "twist_mux.yaml"
)


def _params() -> dict:
    with TWIST_MUX_YAML.open() as f:
        data = yaml.safe_load(f)
    return data["twist_mux"]["ros__parameters"]


def test_yaml_existe_et_se_parse():
    params = _params()
    assert "topics" in params
    assert "locks" in params


def test_use_stamped_false_obligatoire_en_jazzy():
    # Toute la chaîne (bridge, deadman, plugin DiffDrive gz) parle Twist simple :
    # use_stamped: true casserait l'arbitrage en silence (voir twist_mux.yaml).
    assert _params()["use_stamped"] is False


def test_priorites_remote_100_web_50_follow_20_anim_10():
    topics = _params()["topics"]
    assert topics["remote"]["priority"] == 100
    assert topics["web"]["priority"] == 50
    assert topics["follow"]["priority"] == 20
    assert topics["anim"]["priority"] == 10
    # L'ordre STRUCTUREL du plan : la télécommande physique domine le web, qui
    # domine le suivi autonome, qui domine les animations. Un web ou un suivi
    # à >= 100 serait un trou de sécurité (l'autonome ne doit JAMAIS pouvoir
    # résister à une reprise en main humaine).
    assert (topics["remote"]["priority"]
            > topics["web"]["priority"]
            > topics["follow"]["priority"]
            > topics["anim"]["priority"])


def test_web_ecoute_bien_cmd_vel_web():
    assert _params()["topics"]["web"]["topic"] == "cmd_vel_web"


def test_follow_ecoute_bien_cmd_vel_follow():
    assert _params()["topics"]["follow"]["topic"] == "cmd_vel_follow"


def test_tous_les_timeouts_topics_a_un_demi_seconde():
    topics = _params()["topics"]
    for nom, entree in topics.items():
        assert entree["timeout"] == 0.5, nom


def test_lock_e_stop_priorite_255():
    locks = _params()["locks"]
    assert locks["e_stop"]["topic"] == "e_stop"
    assert locks["e_stop"]["priority"] == 255
    # timeout 0.0 = latché (le verrou ne se relâche pas tout seul).
    assert locks["e_stop"]["timeout"] == 0.0
    # Le verrou domine TOUTES les sources de commande (roues comprises).
    max_topic_priority = max(e["priority"] for e in _params()["topics"].values())
    assert locks["e_stop"]["priority"] > max_topic_priority
