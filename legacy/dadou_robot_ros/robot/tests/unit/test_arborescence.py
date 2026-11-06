"""Arborescence du mono-dépôt : les 6 packages ROS autonomes du robot ont déménagé de
legacy/dadou_robot_ros/conf/ros2_dependencies/ vers packages/ (lot L1e-1, 06/11),
puis ont été renommés robot_* -> didier_* (lot L1e-2, 07/11). Ce test grave le
résultat, la liste que le rôle Ansible `synchronise` pousse sur le Pi robot, et la
liste des anciens noms qu'il efface des Pi (packages_retires).

Pourquoi graver la liste de l'hôte robot : le `colcon build` d'un Pi compile TOUT
ros2_ws/src/ ; un package en trop (sim-only) ou en moins (chaîne roues) se découvre
sinon sur le robot. Les listes sont lues dans le VRAI fichier `hosts`.
"""
import pathlib
import xml.etree.ElementTree as ET

import yaml

ROBOT = pathlib.Path(__file__).resolve().parents[3]      # legacy/dadou_robot_ros
LEGACY = ROBOT.parent
MONO = LEGACY.parent
PACKAGES = MONO / "packages"
HOSTS = LEGACY / "dadou_utils_ros" / "ansible" / "hosts"
VARS = LEGACY / "dadou_utils_ros" / "ansible" / "vars" / "main.yml"

SIX_DEMENAGES = ["didier_bringup", "didier_description", "didier_drive",
                 "didier_rehearsal", "didier_sim", "didier_web"]
# Anciens noms (avant L1e-2) : ne doivent plus exister dans packages/, et sont la
# liste `packages_retires` que le rôle synchronise efface des Pi. Écrits en dur
# (pas dérivés des nouveaux) : un test qui recalcule l'attendu ne teste rien.
ANCIENS_NOMS = ["robot_bringup", "robot_description", "robot_drive",
                "robot_rehearsal", "robot_sim", "robot_web"]
# Parmi les six, ceux en ament_python (marqueur resource/<nom> obligatoire) ; les
# trois autres sont ament_cmake (pas de marqueur).
SIX_AMENT_PYTHON = ["didier_drive", "didier_rehearsal", "didier_web"]
COMMUNS = ["theatre_contrats", "robot_interfaces"]
# Liste GRAVÉE de l'hôte robot : exactement ce que le Pi reçoit depuis avant L1e-1,
# sous les noms de L1e-2 (aucun changement de comportement ; le tri « sim-only hors
# du Pi » est L1e-4). didier_jeu (sim-only) n'y figure PAS, et ne doit jamais y
# figurer sans décision.
HOTE_ROBOT_GRAVE = ["didier_bringup", "didier_description", "didier_drive", "didier_rehearsal",
                    "didier_sim", "didier_web", "robot_interfaces", "theatre_contrats"]


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


# --- L1e-2 : renommage robot_* -> didier_* -------------------------------------

def _nom_declare(package_xml):
    return ET.parse(package_xml).getroot().findtext("name")


def _build_type(package_xml):
    return ET.parse(package_xml).getroot().findtext("export/build_type")


def test_les_six_ont_un_package_xml_dont_le_nom_est_celui_du_dossier():
    for nom in SIX_DEMENAGES:
        assert _nom_declare(PACKAGES / nom / "package.xml") == nom, nom


def test_aucun_ancien_nom_ne_subsiste_dans_packages():
    for ancien in ANCIENS_NOMS:
        assert not (PACKAGES / ancien).exists(), ancien


def test_packages_retires_est_la_liste_gravee_des_six_anciens_noms():
    retires = yaml.safe_load(VARS.read_text(encoding="utf-8"))["packages_retires"]
    assert sorted(retires) == ANCIENS_NOMS
    assert len(retires) == len(set(retires)), "doublon dans packages_retires"


def test_la_tache_de_nettoyage_precede_la_copie_des_packages():
    """Le nettoyage doit passer AVANT le rsync (sinon colcon compile anciens et
    nouveaux au build qui suit) et couvrir src/, build/ et install/."""
    taches = yaml.safe_load((LEGACY / "dadou_utils_ros" / "ansible" / "roles" / "synchronise"
                             / "tasks" / "main.yml").read_text(encoding="utf-8"))
    noms = [t.get("name", "") for t in taches]
    nettoyage = next(i for i, t in enumerate(taches) if "packages_retires" in str(t.get("loop", "")))
    copie = next(i for i, n in enumerate(noms) if n.startswith("Synchronize mono-repo package"))
    assert nettoyage < copie
    t = taches[nettoyage]
    assert t["file"]["state"] == "absent" and t.get("become") is True
    assert "['src', 'build', 'install']" in t["loop"]


def test_l_hote_robot_lance_le_bringup_renomme():
    assert _hosts()["robot"]["hosts"]["r"]["launch_cmd"] == "ros2 launch didier_bringup robot_app.launch.py"


def test_le_marqueur_resource_de_chaque_ament_python_porte_le_nom_du_package():
    ament_python = sorted(p.parent.name for p in PACKAGES.glob("*/package.xml")
                          if _build_type(p) == "ament_python")
    # Garde-fou : la recherche doit trouver les trois des six (sinon le test ne vérifie rien).
    assert set(SIX_AMENT_PYTHON) <= set(ament_python), ament_python
    for nom in ament_python:
        ressources = sorted(f.name for f in (PACKAGES / nom / "resource").iterdir())
        assert ressources == [nom], (nom, ressources)
