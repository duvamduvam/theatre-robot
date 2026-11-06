"""Arborescence du mono-dépôt (lot L1e-1, 2026-11-06) : les 6 packages ROS autonomes
du robot ont déménagé de legacy/dadou_robot_ros/conf/ros2_dependencies/ vers
packages/, SANS changer de nom. Ce test grave le résultat et la liste que le rôle
Ansible `synchronise` pousse sur le Pi robot.

Pourquoi graver la liste de l'hôte robot : le `colcon build` d'un Pi compile TOUT
ros2_ws/src/ ; un package en trop (sim-only) ou en moins (chaîne roues) se découvre
sinon sur le robot. Les listes sont lues dans le VRAI fichier `hosts`.
"""
import pathlib

import yaml

ROBOT = pathlib.Path(__file__).resolve().parents[3]      # legacy/dadou_robot_ros
LEGACY = ROBOT.parent
MONO = LEGACY.parent
PACKAGES = MONO / "packages"
HOSTS = LEGACY / "dadou_utils_ros" / "ansible" / "hosts"
VARS = LEGACY / "dadou_utils_ros" / "ansible" / "vars" / "main.yml"

SIX_DEMENAGES = ["robot_bringup", "robot_description", "robot_drive",
                 "robot_rehearsal", "robot_sim", "robot_web"]
COMMUNS = ["theatre_contrats", "robot_interfaces"]
# Liste GRAVÉE de l'hôte robot : exactement ce que le Pi reçoit depuis avant L1e-1
# (aucun changement de comportement ; le tri « sim-only hors du Pi » est L1e-4).
# didier_jeu (sim-only) n'y figure PAS, et ne doit jamais y figurer sans décision.
HOTE_ROBOT_GRAVE = sorted(COMMUNS + SIX_DEMENAGES)


def _hosts():
    return yaml.safe_load(HOSTS.read_text(encoding="utf-8"))


def _listes_packages():
    """Toutes les listes de packages ROS déclarées : (origine, liste)."""
    trouvees = []
    for groupe, contenu in _hosts().items():
        for hote, variables in (contenu.get("hosts") or {}).items():
            if variables and "packages" in variables:
                trouvees.append((f"hosts:{groupe}/{hote}", variables["packages"]))
    defaut = yaml.safe_load(VARS.read_text(encoding="utf-8")).get("packages_default")
    if defaut is not None:
        trouvees.append(("vars/main.yml:packages_default", defaut))
    return trouvees


def test_l_ancien_dossier_n_existe_plus():
    assert not (ROBOT / "conf" / "ros2_dependencies").exists()


def test_les_six_packages_sont_dans_packages_avec_leur_package_xml():
    for nom in SIX_DEMENAGES:
        assert (PACKAGES / nom / "package.xml").is_file(), nom


def test_l_hote_robot_pousse_exactement_les_huit_packages_graves():
    robot = _hosts()["robot"]["hosts"]["r"]
    assert sorted(robot["packages"]) == HOTE_ROBOT_GRAVE
    assert len(robot["packages"]) == len(set(robot["packages"])), "doublon dans la liste"


def test_les_communs_sont_la_liste_par_defaut():
    defaut = yaml.safe_load(VARS.read_text(encoding="utf-8"))["packages_default"]
    assert sorted(defaut) == sorted(COMMUNS)


def test_tout_package_cite_dans_une_liste_existe_dans_packages():
    listes = _listes_packages()
    assert listes, "aucune liste de packages trouvée : le test ne vérifierait rien"
    for origine, liste in listes:
        for nom in liste:
            assert (PACKAGES / nom / "package.xml").is_file(), f"{origine} cite {nom!r}, absent de packages/"


def test_la_variable_packages_n_est_plus_une_liste_apt():
    """Les gants déclaraient `packages: [vim, ...]` (paquets apt, jamais lus) : le rôle
    synchronise aurait tenté de rsync-er un dossier « vim »."""
    for origine, liste in _listes_packages():
        assert "vim" not in liste, origine
