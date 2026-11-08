"""Arborescence du mono-dépôt : les 6 packages ROS autonomes du robot ont déménagé de
legacy/dadou_robot_ros/conf/ros2_dependencies/ vers packages/ (lot L1e-1, 06/11),
puis ont été renommés robot_* -> didier_* (lot L1e-2, 07/11) ; les messages
robot_interfaces sont devenus theatre_interfaces (lot L1e-3b, 07/11), et le cœur
`robot` est devenu le package packages/didier_core (lot L1e-3c, 07/11). Ce test grave le
résultat, la liste que le rôle Ansible `synchronise` pousse sur le Pi robot, et la
liste des anciens noms qu'il efface des Pi (packages_retires).

Pourquoi graver la liste de l'hôte robot : le `colcon build` d'un Pi compile TOUT
ros2_ws/src/ ; un package en trop (sim-only) ou en moins (chaîne roues) se découvre
sinon sur le robot. Les listes sont lues dans le VRAI fichier `hosts`.
"""
import pathlib
import xml.etree.ElementTree as ET

import yaml

ROBOT = pathlib.Path(__file__).resolve().parents[4] / "legacy" / "dadou_robot_ros"
LEGACY = ROBOT.parent
MONO = LEGACY.parent
PACKAGES = MONO / "packages"
# L1e-4a (08/11) : Ansible a quitté legacy/dadou_utils_ros/ansible/ pour deploy/ à la racine.
DEPLOY = MONO / "deploy"
HOSTS = DEPLOY / "hosts"
VARS = DEPLOY / "vars" / "main.yml"

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
# L1e-3b : ancien nom des messages, ajouté à `packages_retires` (même nettoyage des Pi que
# les six de L1e-2). Écrit en dur, comme ANCIENS_NOMS.
ANCIEN_NOM_INTERFACES = "robot_interfaces"
COMMUNS = ["theatre_contrats", "theatre_interfaces", "dadou_utils_ros"]
# Liste GRAVÉE de l'hôte robot : exactement ce que le Pi reçoit depuis avant L1e-1,
# sous les noms de L1e-2 (aucun changement de comportement ; le tri « sim-only hors
# du Pi » est L1e-4). didier_jeu (sim-only) n'y figure PAS, et ne doit jamais y
# figurer sans décision. dadou_utils_ros (lib partagée) y est depuis L1e-3a ;
# theatre_interfaces y remplace robot_interfaces depuis L1e-3b ; didier_core (le cœur, qui
# vivait dans src/robot/) y entre au L1e-3c.
HOTE_ROBOT_GRAVE = ["dadou_utils_ros", "didier_bringup", "didier_core", "didier_description",
                    "didier_drive", "didier_rehearsal", "didier_sim", "didier_web",
                    "theatre_contrats", "theatre_interfaces"]
# L1e-3a : chemins (sous ros2_ws/) des copies embarquées de la lib, effacés des Pi par la
# liste `chemins_retires_lib`. Écrits en dur, comme ANCIENS_NOMS.
CHEMINS_RETIRES_LIB = ["src/robot/dadou_utils_ros", "src/vision/dadou_utils_ros",
                       "src/controller/dadou_utils_ros",
                       # + build/install des 3 packages qui embarquaient la lib : une copie
                       # périmée dans install/<pkg> masquerait packages/dadou_utils_ros.
                       "build/robot", "install/robot", "build/vision", "install/vision",
                       "build/controller", "install/controller"]


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


def test_l_hote_robot_pousse_exactement_les_dix_packages_graves():
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


def test_packages_retires_est_la_liste_gravee_des_sept_anciens_noms():
    retires = yaml.safe_load(VARS.read_text(encoding="utf-8"))["packages_retires"]
    assert sorted(retires) == ["robot_bringup", "robot_description", "robot_drive",
                               "robot_interfaces", "robot_rehearsal", "robot_sim", "robot_web"]
    assert len(retires) == len(set(retires)), "doublon dans packages_retires"


def test_la_tache_de_nettoyage_precede_la_copie_des_packages():
    """Le nettoyage doit passer AVANT le rsync (sinon colcon compile anciens et
    nouveaux au build qui suit) et couvrir src/, build/ et install/."""
    taches = yaml.safe_load((DEPLOY / "roles" / "synchronise"
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


# --- L1e-3a : la lib partagée dadou_utils_ros devient un package de packages/ ----

def test_aucun_lien_symbolique_dadou_utils_ros_ne_subsiste_dans_legacy():
    """Les 3 dépôts embarquaient la lib par un symlink (copié par le rsync copy_links) :
    s'il revenait, le Pi aurait deux copies de la lib et la vieille pourrait masquer la neuve."""
    liens = [str(p.relative_to(MONO)) for p in LEGACY.rglob("dadou_utils_ros")
             if p.is_symlink() and ".venv" not in p.parts]
    assert liens == [], liens


def test_la_lib_est_un_package_dont_le_nom_est_celui_du_dossier():
    xml = PACKAGES / "dadou_utils_ros" / "package.xml"
    assert xml.is_file()
    assert _nom_declare(xml) == "dadou_utils_ros"
    assert _build_type(xml) == "ament_python"
    assert (PACKAGES / "dadou_utils_ros" / "dadou_utils_ros" / "__init__.py").is_file()


def test_la_lib_est_dans_packages_default():
    defaut = yaml.safe_load(VARS.read_text(encoding="utf-8"))["packages_default"]
    assert "dadou_utils_ros" in defaut


def test_chemins_retires_lib_est_la_liste_gravee_des_trois_copies_embarquees():
    retires = yaml.safe_load(VARS.read_text(encoding="utf-8"))["chemins_retires_lib"]
    assert sorted(retires) == sorted(CHEMINS_RETIRES_LIB)
    assert len(retires) == len(set(retires)), "doublon dans chemins_retires_lib"


def test_la_tache_de_nettoyage_de_la_lib_precede_la_copie_des_packages():
    taches = yaml.safe_load((DEPLOY / "roles" / "synchronise"
                             / "tasks" / "main.yml").read_text(encoding="utf-8"))
    noms = [t.get("name", "") for t in taches]
    nettoyage = next(i for i, t in enumerate(taches) if "chemins_retires_lib" in str(t.get("loop", "")))
    copie = next(i for i, n in enumerate(noms) if n.startswith("Synchronize mono-repo package"))
    assert nettoyage < copie
    t = taches[nettoyage]
    assert t["file"]["state"] == "absent" and t.get("become") is True
    assert t["file"]["path"].startswith("{{ ansible_env.HOME }}/{{ ros2_ws }}/")


# --- L1e-3b : robot_interfaces -> theatre_interfaces ------------------------------

def test_les_interfaces_sont_un_package_cmake_dont_le_nom_est_celui_du_dossier():
    xml = PACKAGES / "theatre_interfaces" / "package.xml"
    assert xml.is_file()
    assert _nom_declare(xml) == "theatre_interfaces"
    assert _build_type(xml) == "ament_cmake"
    cmake = (PACKAGES / "theatre_interfaces" / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "project(theatre_interfaces)" in cmake
    # Noms de MESSAGES inchangés : StringTime reste généré (le type de tous les topics).
    assert '"msg/StringTime.msg"' in cmake


def test_l_ancien_dossier_des_interfaces_n_existe_plus():
    assert not (PACKAGES / ANCIEN_NOM_INTERFACES).exists()


def test_plus_aucun_fichier_de_code_ni_de_conf_ne_cite_l_ancien_nom():
    """Imports, `<depend>`, compose, Dockerfiles, scripts CLI : un oubli ne se voit qu'au
    `colcon build` (dépendance introuvable) ou au démarrage d'un nœud (ImportError).
    Seule exception : la liste `packages_retires` d'Ansible, qui DOIT le citer."""
    suffixes = {".py", ".sh", ".yml", ".yaml", ".xml", ".txt", ".cfg", ".launch"}
    exclus = {".venv", "venv", ".git", "build", "install", "log", "__pycache__", "node_modules"}
    fautes = []
    for p in MONO.rglob("*"):
        if exclus & set(p.relative_to(MONO).parts) or not p.is_file():
            continue
        if p.suffix not in suffixes and not p.name.startswith("Dockerfile") \
                and p.name not in ("hosts", "Makefile") and p.parent.name != "scripts":
            continue
        if p in (VARS, pathlib.Path(__file__).resolve()):
            continue
        if ANCIEN_NOM_INTERFACES in p.read_text(encoding="utf-8", errors="ignore"):
            fautes.append(str(p.relative_to(MONO)))
    assert fautes == [], fautes


# --- L1e-3c : le cœur robot -> packages/didier_core ---------------------------------

CORE = PACKAGES / "didier_core"
# Chemins (sous ros2_ws/) de l'ancienne forme du package robot, effacés des Pi par la liste
# `chemins_retires_robot`. Écrits en dur, comme ANCIENS_NOMS.
CHEMINS_RETIRES_ROBOT = ["src/robot/robot", "src/robot/dadou_utils_ros", "src/robot/setup.py",
                         "src/robot/package.xml", "src/robot/setup.cfg", "src/robot/resource",
                         "src/robot/test", "build/robot", "install/robot",
                         # Restes sous conf/ que colcon trouve depuis que src/robot/ n'est plus un
                         # package (déploiement du 08/11) : ils recompilaient `robot` et les robot_*.
                         "src/robot/conf/ros2/setup.py", "src/robot/conf/ros2/package.xml",
                         "src/robot/conf/ros2/setup.cfg", "src/robot/conf/ros2/resource",
                         "src/robot/conf/ros2/test", "src/robot/conf/ros2_dependencies"]
# Exécutables du cœur : NOMS INCHANGÉS par le déménagement (décision 9 : aucun exécutable
# renommé — launch, scripts et ros2 run les tapent). Liste gravée, cibles comprises.
EXECUTABLES_CORE = {
    "animations_node": "didier_core.nodes.animations_node:main",
    "audio_node": "didier_core.nodes.audio_node:main",
    "face_sim": "didier_core.nodes.face_sim_node:main",
    "gaze_follower": "didier_core.nodes.gaze_follower_node:main",
    "lights_node": "didier_core.nodes.lights_node:main",
    "person_follower": "didier_core.nodes.person_follower_node:main",
    "relays_node": "didier_core.nodes.relays_node:main",
    "servo_node": "didier_core.nodes.servo_node:main",
    "system_node": "didier_core.nodes.system_node:main",
    "wheels_node": "didier_core.nodes.wheels_node:main",
}
SYNCHRONISE = DEPLOY / "roles" / "synchronise" / "tasks" / "main.yml"
COMPOSES = [ROBOT / "conf" / "docker" / d / f for d, f in
            (("arm", "docker-compose-arm.yml"), ("sim", "docker-compose-sim.yml"),
             ("x8664", "docker-compose-x86.yml"))]


def test_le_coeur_est_un_package_ament_python_dont_le_nom_est_celui_du_dossier():
    assert _nom_declare(CORE / "package.xml") == "didier_core"
    assert _build_type(CORE / "package.xml") == "ament_python"
    assert (CORE / "didier_core" / "__init__.py").is_file()
    assert (CORE / "didier_core" / "nodes" / "wheels_node.py").is_file()
    assert (CORE / "test" / "conftest.py").is_file() and (CORE / "pytest.ini").is_file()
    # Les tests ne sont PAS dans le module (ils seraient installés sur le Pi).
    assert not (CORE / "didier_core" / "tests").exists()


def test_l_ancien_module_robot_et_sa_forme_ament_ont_quitte_legacy():
    assert not (ROBOT / "robot").exists()
    for nom in ("setup.py", "package.xml", "setup.cfg", "resource", "test"):
        assert not (ROBOT / "conf" / "ros2" / nom).exists(), nom


def test_les_executables_du_coeur_gardent_leur_nom():
    import re
    setup = (CORE / "setup.py").read_text(encoding="utf-8")
    actifs = dict(re.findall(r'^\s*"(\w+) = ([\w.:]+)"', setup, re.M))
    assert actifs == EXECUTABLES_CORE
    assert "package_name = 'didier_core'" in setup
    cfg = (CORE / "setup.cfg").read_text(encoding="utf-8")
    assert "$base/lib/didier_core" in cfg and "lib/robot" not in cfg


def test_les_dependants_du_coeur_le_declarent_sous_son_nouveau_nom():
    for nom in ("didier_bringup", "didier_rehearsal", "didier_jeu"):
        deps = [d.text for d in ET.parse(PACKAGES / nom / "package.xml").getroot().iter("exec_depend")]
        assert "didier_core" in deps and "robot" not in deps, (nom, deps)


def test_chemins_retires_robot_est_la_liste_gravee_de_l_ancienne_forme():
    retires = yaml.safe_load(VARS.read_text(encoding="utf-8"))["chemins_retires_robot"]
    assert sorted(retires) == sorted(CHEMINS_RETIRES_ROBOT)
    assert len(retires) == len(set(retires)), "doublon dans chemins_retires_robot"
    # Les DONNÉES de src/robot/ ne doivent jamais y entrer.
    for donnee in ("src/robot/json", "src/robot/medias", "src/robot/conf", "src/robot/db", "src/robot"):
        assert donnee not in retires, donnee


def _source_robot(rel):
    """Fichier du PC que les copies de l'hôte robot (L1e-4b) poseraient en src/robot/<rel> —
    None si aucune copie n'y écrit : data/{json,medias,db}/ → src/robot/{json,medias,db}/,
    legacy/dadou_robot_ros/conf/ → src/robot/conf/, rien d'autre (plus de copie « projet »)."""
    tete = rel.split("/")[0]
    if tete in ("json", "medias", "db"):
        return MONO / "data" / rel
    if tete == "conf":
        return ROBOT / rel
    return None


def test_aucun_chemin_retire_du_coeur_n_existe_dans_l_arbre_rsynce():
    """Idempotence : une entrée de la liste encore présente dans ce que les copies du robot
    poussent reviendrait à chaque passage — effacée puis recopiée, « changed » sans fin
    (ecart-pi.sh rouge) et, pour un descripteur, un package fantôme compilé par colcon. Depuis
    L1e-4b, l'hôte robot ne reçoit plus que data/{json,medias,db} et conf/ (voir _source_robot)."""
    variables = yaml.safe_load(VARS.read_text(encoding="utf-8"))
    retires = variables["chemins_retires_robot"] + variables["chemins_retires_legacy_robot"]
    sources = [p[len("src/robot/"):] for p in retires if p.startswith("src/robot/")]
    assert sources, "aucune entrée src/robot/ : le test ne vérifierait rien"
    for rel in sources:
        source = _source_robot(rel)
        assert source is None or not source.exists(), rel


def test_le_nettoyage_du_coeur_est_conditionnel_et_precede_la_copie_des_packages():
    taches = yaml.safe_load(SYNCHRONISE.read_text(encoding="utf-8"))
    noms = [t.get("name", "") for t in taches]
    nettoyage = next(i for i, t in enumerate(taches) if "chemins_retires_robot" in str(t.get("loop", "")))
    detection = next(i for i, t in enumerate(taches)
                     if "chemins_retires_robot" in str(t.get("shell", "")))
    copie = next(i for i, n in enumerate(noms) if n.startswith("Synchronize mono-repo package"))
    assert detection < nettoyage < copie
    t = taches[nettoyage]
    assert t["file"]["state"] == "absent" and t.get("become") is True
    assert t["file"]["path"].startswith("{{ ansible_env.HOME }}/{{ ros2_ws }}/")
    # Idempotent : seules les entrées détectées sont effacées ; la détection ne change rien
    # et tourne aussi en --check (ecart-pi.sh).
    registre = taches[detection]["register"]
    assert t["when"] == f"item in {registre}.stdout_lines"
    assert taches[detection]["changed_when"] is False and taches[detection]["check_mode"] is False


def test_la_sentinelle_du_coeur_est_dans_le_package_et_gitignoree():
    assert _hosts()["robot"]["hosts"]["r"]["sentinelle_build"] == "src/didier_core/change"
    script = (ROBOT / "conf" / "scripts" / "launch-ros-in-docker.sh").read_text(encoding="utf-8")
    assert "CHANGE_FILE=/home/ros2_ws/src/didier_core/change\n" in script
    ignores = (MONO / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "packages/didier_core/change" in ignores


def test_les_compose_montent_le_coeur_a_plat_et_posent_la_racine_des_donnees():
    for compose in COMPOSES:
        service = next(iter(yaml.safe_load(compose.read_text(encoding="utf-8"))["services"].values()))
        volumes = service["volumes"]
        coeur = [v for v in volumes if v.endswith(":/home/ros2_ws/src/didier_core")]
        assert len(coeur) == 1 and coeur[0].split(":")[0].endswith("/didier_core"), (compose.name, coeur)
        assert not [v for v in volumes if v.endswith("/src/robot/robot") or "/src/robot/setup.py" in v
                    or v.endswith(":/home/ros2_ws/src/robot")], compose.name
        assert "DIDIER_DATA_DIR=/home/ros2_ws/src/robot/" in service["environment"], compose.name
        assert service["build"]["additional_contexts"]["didier_core"].endswith("/didier_core"), compose.name


def test_plus_aucun_fichier_de_code_ni_de_conf_ne_cite_le_package_robot():
    """`package="robot"`, `ros2 run robot`, `src/robot/robot`, `from robot.`, `import robot` :
    un oubli ne se voit qu'au lancement (package introuvable) ou à l'import d'un nœud. Seule
    exception : la liste de nettoyage d'Ansible (vars/main.yml), qui DOIT citer l'ancienne forme."""
    import re
    motif = re.compile(r'package=["\']robot["\']|ros2 run robot\b|src/robot/robot\b'
                       r'|^\s*from robot[. ]|^\s*import robot\b', re.M)
    suffixes = {".py", ".sh", ".yml", ".yaml", ".xml", ".txt", ".cfg", ".launch", ".ini"}
    exclus = {".venv", "venv", ".git", "build", "install", "log", "__pycache__", "node_modules"}
    fautes = []
    for p in MONO.rglob("*"):
        if exclus & set(p.relative_to(MONO).parts) or not p.is_file():
            continue
        if p.suffix not in suffixes and not p.name.startswith("Dockerfile") \
                and p.name not in ("hosts", "Makefile", "Jenkinsfile") and p.parent.name != "scripts":
            continue
        if p in (VARS, pathlib.Path(__file__).resolve()):
            continue
        if motif.search(p.read_text(encoding="utf-8", errors="ignore")):
            fautes.append(str(p.relative_to(MONO)))
    assert fautes == [], fautes


# --- L1e-3d : la vision -> packages/didier_vision ----------------------------------------

import pytest  # noqa: E402  (bloc ajouté par lot : garde chaque lot lisible d'un tenant)

VISION = LEGACY / "dadou_vision_ros"
VISION_PKG = PACKAGES / "didier_vision"
EXECUTABLES_VISION = {
    "vision_status": "didier_vision.nodes.vision_status_node:main",
    "person_tracker": "didier_vision.nodes.person_tracker_node:main",
    "chat": "didier_vision.nodes.chat_node:main",
    "reflection": "didier_vision.nodes.reflection_node:main",
}


def test_la_vision_est_un_package_ament_python_dont_le_nom_est_celui_du_dossier():
    assert _nom_declare(VISION_PKG / "package.xml") == "didier_vision"
    assert _build_type(VISION_PKG / "package.xml") == "ament_python"
    assert (VISION_PKG / "didier_vision" / "__init__.py").is_file()
    assert (VISION_PKG / "didier_vision" / "nodes" / "chat_node.py").is_file()
    assert (VISION_PKG / "test" / "conftest.py").is_file() and (VISION_PKG / "pytest.ini").is_file()
    assert (VISION_PKG / "launch" / "vision.launch.py").is_file()
    assert (VISION_PKG / "resource" / "didier_vision").is_file()
    # Les tests ne sont PAS dans le module (ils seraient installés sur le Pi) ; la sentinelle
    # de build est gitignorée et ne vit jamais dans le module.
    assert not (VISION_PKG / "didier_vision" / "tests").exists()
    assert not (VISION_PKG / "didier_vision" / "change").exists()


def test_l_ancien_module_vision_et_sa_forme_ament_ont_quitte_legacy():
    assert not (VISION / "vision").exists()
    for nom in ("setup.py", "package.xml", "setup.cfg", "resource", "launch"):
        assert not (VISION / "conf" / "ros2" / nom).exists(), nom
    for nom in ("conftest.py", "pytest.ini"):
        assert not (VISION / nom).exists(), nom


def test_les_executables_de_la_vision_gardent_leur_nom():
    import re
    setup = (VISION_PKG / "setup.py").read_text(encoding="utf-8")
    actifs = dict(re.findall(r"^\s*'(\w+) = ([\w.:]+)'", setup, re.M))
    assert actifs == EXECUTABLES_VISION
    assert "package_name = 'didier_vision'" in setup
    assert "(os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py'))" in setup
    cfg = (VISION_PKG / "setup.cfg").read_text(encoding="utf-8")
    assert "$base/lib/didier_vision" in cfg and "lib/vision" not in cfg


def test_le_launch_de_la_vision_cible_le_package_renomme():
    launch = (VISION_PKG / "launch" / "vision.launch.py").read_text(encoding="utf-8")
    assert launch.count('package="didier_vision"') == 4
    assert 'package="vision"' not in launch


def test_la_sentinelle_de_la_vision_est_dans_le_package_et_gitignoree():
    script = (VISION / "conf" / "scripts" / "launch-ros-in-docker.sh").read_text(encoding="utf-8")
    assert "CHANGE_FILE=/home/ros2_ws/src/didier_vision/change\n" in script
    assert "ros2 launch didier_vision vision.launch.py" in script
    ignores = (MONO / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "packages/didier_vision/change" in ignores


def test_les_compose_de_la_vision_montent_le_package_a_plat_et_posent_la_racine_des_donnees():
    for nom, build in (("arm", True), ("x86", False)):
        compose = VISION / "conf" / "docker" / nom / f"docker-compose-{nom}.yml"
        service = next(iter(yaml.safe_load(compose.read_text(encoding="utf-8"))["services"].values()))
        volumes = service["volumes"]
        code = [v for v in volumes if v.endswith(":/home/ros2_ws/src/didier_vision")]
        assert len(code) == 1 and code[0].split(":")[0].endswith("/didier_vision"), (nom, code)
        # Plus de montage du module, de setup.py, de package.xml ni de launch sous src/vision/ ;
        # conf/ et medias/ (ARM) restent montés : ce sont les données.
        assert not [v for v in volumes if "/src/vision/vision" in v or "/src/vision/setup.py" in v
                    or "/src/vision/package.xml" in v or "/src/vision/launch" in v], nom
        assert "DIDIER_VISION_DATA_DIR=/home/ros2_ws/src/vision/" in service["environment"], nom
        if build:
            assert service["build"]["additional_contexts"]["didier_vision"].endswith("/didier_vision")
    dockerfile = (VISION / "conf" / "docker" / "arm" / "Dockerfile-arm").read_text(encoding="utf-8")
    assert "COPY --from=didier_vision . /home/ros2_ws/src/didier_vision\n" in dockerfile
    actives = [ligne for ligne in dockerfile.splitlines() if not ligne.lstrip().startswith("#")]
    assert not [ligne for ligne in actives if ligne.startswith("COPY vision/") or "conf/ros2" in ligne]
    build_x86 = (VISION / "conf" / "docker" / "x86" / "build-x86.sh").read_text(encoding="utf-8")
    assert '--build-context didier_vision="$PACKAGES/didier_vision"' in build_x86


def test_plus_aucun_fichier_de_code_ni_de_conf_ne_cite_le_package_vision():
    """`package="vision"`, `ros2 run|launch vision`, `src/vision/vision`, `from vision.`,
    `import vision` : un oubli ne se voit qu'au lancement ou à l'import d'un nœud. `hosts` et
    `vars/main.yml` (moitié Ansible, test suivant) sont traités à part."""
    import re
    motif = re.compile(r'package=["\']vision["\']|ros2 (?:run|launch) vision\b|src/vision/vision\b'
                       r'|^\s*from vision[. ]|^\s*import vision\b', re.M)
    suffixes = {".py", ".sh", ".yml", ".yaml", ".xml", ".txt", ".cfg", ".launch", ".ini"}
    exclus = {".venv", "venv", ".git", "build", "install", "log", "__pycache__", "node_modules"}
    fautes = []
    for p in MONO.rglob("*"):
        if exclus & set(p.relative_to(MONO).parts) or not p.is_file():
            continue
        if p.suffix not in suffixes and not p.name.startswith("Dockerfile") \
                and p.name not in ("Makefile", "Jenkinsfile") and p.parent.name != "scripts":
            continue
        if p in (HOSTS, VARS, pathlib.Path(__file__).resolve()):
            continue
        if motif.search(p.read_text(encoding="utf-8", errors="ignore")):
            fautes.append(str(p.relative_to(MONO)))
    assert fautes == [], fautes


def test_l_hote_vision_pousse_son_package_et_lit_sa_sentinelle_renommee():
    vision = _hosts()["vision"]["hosts"]["ai"]
    assert "didier_vision" in vision["packages"]
    assert vision["sentinelle_build"] == "src/didier_vision/change"
    assert vision["launch_cmd"] == "ros2 run didier_vision vision_status --ros-args -r __ns:=/didier"


# Ancienne forme de la vision sur le Pi (L1e-3d, 08/11), écrite en dur comme CHEMINS_RETIRES_ROBOT.
CHEMINS_RETIRES_VISION = [
    "src/vision/vision", "src/vision/setup.py", "src/vision/package.xml", "src/vision/setup.cfg",
    "src/vision/resource", "src/vision/launch", "src/vision/conftest.py", "src/vision/pytest.ini",
    "src/vision/conf/ros2", "build/vision", "install/vision",
]


def test_chemins_retires_vision_est_la_liste_gravee_et_epargne_les_donnees():
    retires = yaml.safe_load(VARS.read_text(encoding="utf-8"))["chemins_retires_vision"]
    assert sorted(retires) == sorted(CHEMINS_RETIRES_VISION)
    assert len(retires) == len(set(retires))
    for donnee in ("src/vision", "src/vision/conf", "src/vision/medias", "src/vision/mediamtx",
                   "src/vision/db", "src/vision/tools", "src/vision/conf/secret"):
        assert donnee not in retires, donnee
    # Idempotence : rien de la liste ne doit exister dans l'arbre rsyncé (sinon recopié à chaque passage).
    for rel in (p[len("src/vision/"):] for p in retires if p.startswith("src/vision/")):
        assert not (VISION / rel).exists(), rel


def test_le_nettoyage_couvre_aussi_la_vision():
    taches = yaml.safe_load(SYNCHRONISE.read_text(encoding="utf-8"))
    assert any("chemins_retires_vision" in str(t.get("loop", "")) for t in taches)
    assert any("chemins_retires_vision" in str(t.get("shell", "")) for t in taches)


# --- L1e-4a : Ansible -> deploy/ à la racine, épuré -----------------------------------------

# Écrits en dur (un test qui recalcule l'attendu ne teste rien). Rôles GARDÉS : tout ce qui restait
# après le ménage décidé par l'étude (§5.8) — y compris des rôles que plus aucun playbook courant
# n'appelle (nginx, ros_humble_*…), que la spec n'a pas listés : leur sort se tranche ailleurs.
ROLES_GARDES = [
    "activate-i2c", "blinka", "colcon_build", "command_root", "config-hote", "conteneur",
    "desktop_lunch", "dir_struct", "docker-arm64", "docker-compose", "docker-install",
    "docker-prune", "download-install-deb-from-url", "info", "linux-package", "logging", "nginx",
    "python", "ros_humble_base", "ros_humble_desktop", "screen-config", "secrets", "services",
    "set-bashrc", "start-scripts", "synchronise", "usb-audio",
]
ROLES_SUPPRIMES = ["activate-spi", "download-install-docker-from-url", "root_ssh",
                   "ros_dependencies", "waveshare-screen", "set-vim", "jenkins", "sonar"]
PLAYBOOKS_GARDES = ["deploy-pios.yml", "install-pios-lite.yml", "install-pios-full.yml",
                    "install-controller-ubuntu.yml"]
PLAYBOOKS_SUPPRIMES = ["install-ci.yml", "install-ci-github-actions.yml", "configure-local-ci.yml",
                       "install-test-pios.yml", "deploy-test-pios.yml"]


def test_ansible_vit_dans_deploy_et_plus_dans_legacy():
    assert (DEPLOY / "deploy-pios.yml").is_file()
    for f in ("hosts", "ecart-pi.sh", "vars/main.yml", "attendu/robot.txt", "attendu/vision.txt"):
        assert (DEPLOY / f).is_file(), f
    # Nextcloud ressuscite parfois un dossier après `git mv` : même vide, il ne doit pas revenir.
    assert not (LEGACY / "dadou_utils_ros" / "ansible").exists()
    assert not (LEGACY / "dadou_utils_ros" / "jenkins").exists()
    assert not (DEPLOY / "legacy").exists()
    assert not (DEPLOY / "group_vars" / "jenkins_server").exists()


def test_les_roles_de_deploy_sont_exactement_la_liste_gravee():
    presents = sorted(p.name for p in (DEPLOY / "roles").iterdir() if p.is_dir())
    assert presents == sorted(ROLES_GARDES)
    for role in ROLES_SUPPRIMES:
        assert not (DEPLOY / "roles" / role).exists(), role


def test_les_playbooks_ci_et_test_sont_supprimes():
    for pb in PLAYBOOKS_GARDES:
        assert (DEPLOY / pb).is_file(), pb
    for pb in PLAYBOOKS_SUPPRIMES:
        assert not (DEPLOY / pb).exists(), pb


def test_tout_role_appele_par_les_deux_playbooks_courants_existe():
    for pb in ("deploy-pios.yml", "install-pios-lite.yml"):
        roles = [r["role"] for r in yaml.safe_load((DEPLOY / pb).read_text(encoding="utf-8"))[0]["roles"]]
        assert roles, pb
        for role in roles:
            assert (DEPLOY / "roles" / role / "tasks" / "main.yml").is_file(), (pb, role)


def test_les_chemins_du_depot_se_deduisent_de_deploy_en_un_seul_dirname():
    variables = yaml.safe_load(VARS.read_text(encoding="utf-8"))
    assert variables["local_projects_dir"] == "{{ playbook_dir | dirname }}/legacy"
    assert variables["packages_dir"] == "{{ playbook_dir | dirname }}/packages"
    # L1e-4b : la racine elle-même (git status du sha déployé).
    assert variables["depot_dir"] == "{{ playbook_dir | dirname }}"
    # Ce que ces gabarits donnent depuis deploy/ doit exister.
    assert (DEPLOY.parent / "legacy" / "dadou_robot_ros").is_dir()
    assert (DEPLOY.parent / ".git").exists()
    assert (DEPLOY.parent / "packages" / "didier_core").is_dir()


def test_le_groupe_integration_a_quitte_l_inventaire():
    assert "integration" not in _hosts()


# --- L1e-4b : données du robot -> data/ à la racine ------------------------------------------

DONNEES = MONO / "data"
# Écrits en dur. Déchets de l'ancienne copie « projet » relevés sur le Pi robot le 08/11.
CHEMINS_RETIRES_LEGACY_ROBOT = [
    "src/robot/.claude", "src/robot/.github", "src/robot/.pytest_cache", "src/robot/.vscode",
    "src/robot/CLAUDE.md", "src/robot/README.md", "src/robot/ci", "src/robot/ci_test",
    "src/robot/conftest.py", "src/robot/dadou_robot_ros.code-workspace", "src/robot/docs",
    "src/robot/essais", "src/robot/firmware", "src/robot/launch.txt", "src/robot/pytest.ini",
    "src/robot/requirements-test.txt", "src/robot/requirements.txt", "src/robot/todo.txt",
]
# Chemins (relatifs à la racine du dépôt) qui décident du suffixe -dirty du sha déployé.
CHEMINS_DEPLOYES = ["packages", "data", "legacy/dadou_robot_ros/conf", "legacy/dadou_vision_ros",
                    "deploy"]
COMPOSES_PC = [ROBOT / "conf/docker/sim/docker-compose-sim.yml",
               ROBOT / "conf/docker/x8664/docker-compose-x86.yml"]
COMPOSE_ARM = ROBOT / "conf/docker/arm/docker-compose-arm.yml"


def _service(compose):
    return next(iter(yaml.safe_load(compose.read_text(encoding="utf-8"))["services"].values()))


def _taches():
    return yaml.safe_load(SYNCHRONISE.read_text(encoding="utf-8"))


def test_les_donnees_sont_dans_data_et_ont_quitte_legacy():
    for nom in ("json", "medias", "db"):
        assert (DONNEES / nom).is_dir(), nom
        # Nextcloud ressuscite parfois un dossier après `git mv` : même vide, il ne revient pas.
        assert not (ROBOT / nom).exists(), nom
    assert (DONNEES / "json" / "sequences").is_dir()
    assert (DONNEES / "medias" / "visuals" / "mouth").is_dir()
    assert (DONNEES / "db" / "sequences.db").is_file()


def test_les_compose_du_pc_montent_et_copient_depuis_data():
    for compose in COMPOSES_PC:
        service = _service(compose)
        assert service["build"]["additional_contexts"]["data"] == "../../../../../data", compose.name
        sources = {v.split(":")[1]: v.split(":")[0] for v in service["volumes"]}
        assert sources["/home/ros2_ws/src/robot/json"] == "../../../../../data/json", compose.name
        assert sources["/home/ros2_ws/src/robot/medias"] == "../../../../../data/medias", compose.name
        assert (compose.parent / "../../../../../data/json").resolve() == DONNEES / "json"
    # La sim monte AUSSI json/ pour leds_sim_node.
    assert "../../../../../data/json:/home/ros2_ws/json" in _service(COMPOSES_PC[0])["volumes"]


def test_le_compose_arm_garde_la_disposition_du_pi():
    """Le compose ARM tourne SUR LE PI (src/robot/conf/docker/arm/) : les données y sont dans
    src/robot/ (chemin Pi inchangé, décision L1e-4), soit ../../.. — pas data/."""
    service = _service(COMPOSE_ARM)
    assert service["build"]["additional_contexts"]["data"] == "../../.."
    assert "../../../json:/home/ros2_ws/src/robot/json" in service["volumes"]
    assert "../../../medias:/home/ros2_ws/src/robot/medias" in service["volumes"]


def test_les_dockerfiles_copient_les_donnees_depuis_le_contexte_data():
    for nom in ("arm/Dockerfile-arm", "x8664/Dockerfile-x86", "sim/Dockerfile-sim"):
        lignes = (ROBOT / "conf" / "docker" / nom).read_text(encoding="utf-8").splitlines()
        copies = [l for l in lignes if l.startswith("COPY ")]
        assert not [l for l in copies if l.split()[1] in ("json/", "medias/", "db/")], nom
        assert "COPY --from=data json/ /home/ros2_ws/src/robot/json/" in copies, nom
    for nom in ("arm/Dockerfile-arm", "x8664/Dockerfile-x86"):
        texte = (ROBOT / "conf" / "docker" / nom).read_text(encoding="utf-8")
        assert "COPY --from=data medias/ /home/ros2_ws/src/robot/medias/\n" in texte, nom


def test_seul_l_hote_robot_porte_donnees_dir():
    hotes = {h: v for g in _hosts().values() for h, v in (g.get("hosts") or {}).items()}
    porteurs = sorted(h for h, v in hotes.items() if v and "donnees_dir" in v)
    assert porteurs == ["r"]
    assert hotes["r"]["donnees_dir"] == "{{ playbook_dir | dirname }}/data"


def test_l_hote_robot_ne_recoit_plus_la_copie_projet():
    taches = _taches()
    projet = next(t for t in taches if str(t.get("name", "")).startswith("Synchronize directory")
                  and t["synchronize"]["src"] == "{{ local_projects_dir }}/{{ local_project_dir }}/")
    assert projet["when"] == "donnees_dir is not defined"
    a_plat = next(t for t in taches if str(t.get("synchronize", {}).get("src", "")).endswith("/conf/ros2/"))
    assert "donnees_dir is not defined" in a_plat["when"]


def test_l_hote_robot_recoit_data_et_conf_par_deux_copies_explicites():
    taches = _taches()
    donnees = next(t for t in taches if str(t.get("name", "")).startswith("Synchronize robot data"))
    assert donnees["when"] == "donnees_dir is defined"
    assert donnees["loop"] == ["json", "medias", "db"]
    assert donnees["synchronize"]["src"] == "{{ donnees_dir }}/{{ item }}/"
    assert donnees["synchronize"]["dest"] == "{{ ros2_ws }}/src/{{ project_ros_dir }}/{{ item }}/"
    conf = next(t for t in taches if str(t.get("name", "")).startswith("Synchronize robot conf"))
    assert conf["when"] == "donnees_dir is defined"
    assert conf["synchronize"]["src"] == "{{ local_projects_dir }}/{{ local_project_dir }}/conf/"
    assert conf["synchronize"]["dest"] == "{{ ros2_ws }}/src/{{ project_ros_dir }}/conf/"
    # Jamais un secret ni un workspace de banc par le rsync.
    for exclu in ("--exclude=/secret", "--exclude=/docker/sim/workspace/",
                  "--exclude=/docker/x86/workspace/", "--exclude=.venv/"):
        assert exclu in conf["synchronize"]["rsync_opts"], exclu
    copie = next(i for i, t in enumerate(taches) if str(t.get("name", "")).startswith("Synchronize mono-repo package"))
    assert taches.index(donnees) < copie and taches.index(conf) < copie


def test_chemins_retires_legacy_robot_est_la_liste_gravee_et_epargne_les_donnees():
    variables = yaml.safe_load(VARS.read_text(encoding="utf-8"))
    retires = variables["chemins_retires_legacy_robot"]
    assert sorted(retires) == sorted(CHEMINS_RETIRES_LEGACY_ROBOT)
    assert len(retires) == len(set(retires))
    for donnee in ("src/robot", "src/robot/json", "src/robot/medias", "src/robot/db", "src/robot/conf"):
        assert donnee not in retires, donnee
    assert not [p for p in retires if not p.startswith("src/robot/") or p.count("/") != 2], retires
    # Détection et effacement conditionnels : même tâche que l'ancienne forme du cœur.
    taches = _taches()
    assert any("chemins_retires_legacy_robot" in str(t.get("shell", "")) for t in taches)
    assert any("chemins_retires_legacy_robot" in str(t.get("loop", "")) for t in taches)
    assert "conf/docker/sim/workspace" in variables["dechets_rsync"]


def test_le_sha_deploye_ne_depend_que_des_chemins_deployes():
    variables = yaml.safe_load(VARS.read_text(encoding="utf-8"))
    assert variables["chemins_deployes"] == CHEMINS_DEPLOYES
    for chemin in CHEMINS_DEPLOYES:
        assert (MONO / chemin).is_dir(), chemin
    sha = next(t for t in _taches() if str(t.get("name", "")).startswith("Write the deployed git sha"))
    contenu = sha["copy"]["content"]
    assert ("lookup('pipe', 'git -C ' ~ depot_dir ~ ' status --porcelain -- ' ~ "
            "(chemins_deployes | join(' ')))") in contenu
    assert "rev-parse HEAD" in contenu and "local_projects_dir" not in contenu


def test_un_journal_de_fumee_non_suivi_ne_salit_pas_le_sha(tmp_path):
    """Comportement de la commande du rôle (git status --porcelain -- <chemins_deployes>) sur un
    dépôt jetable : un fichier non suivi sous docs/ (fumée en cours) n'y apparaît pas ; une
    modification d'un chemin déployé, si (vécu le 08/11 : sha faussement -dirty)."""
    import subprocess

    def git(*args):
        return subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True,
                              text=True, env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                                              "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                                              "HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}).stdout

    chemins = yaml.safe_load(VARS.read_text(encoding="utf-8"))["chemins_deployes"]
    git("init", "-q")
    for rel in [*chemins, "docs"]:
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)
        (tmp_path / rel / "suivi.txt").write_text("x\n")
    git("add", ".")
    git("commit", "-q", "-m", "init")
    (tmp_path / "docs" / "fumee" / "journaux" / "2026-11-08-1923").mkdir(parents=True)
    (tmp_path / "docs" / "fumee" / "journaux" / "2026-11-08-1923" / "resultat.json").write_text("{}")
    (tmp_path / "docs" / "suivi.txt").write_text("modifié\n")
    assert git("status", "--porcelain", "--", *chemins) == ""
    for rel in chemins:
        (tmp_path / rel / "suivi.txt").write_text("modifié\n")
        assert git("status", "--porcelain", "--", *chemins) != "", rel
        git("checkout", "-q", "--", rel)
