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
    taches = yaml.safe_load((LEGACY / "dadou_utils_ros" / "ansible" / "roles" / "synchronise"
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
SYNCHRONISE = LEGACY / "dadou_utils_ros" / "ansible" / "roles" / "synchronise" / "tasks" / "main.yml"
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


def test_aucun_chemin_retire_du_coeur_n_existe_dans_l_arbre_rsynce():
    """Idempotence : le rsync du projet copie legacy/dadou_robot_ros/ vers src/robot/ et
    conf/ros2/ à plat dans src/robot/. Une entrée encore présente dans l'arbre reviendrait à
    chaque passage — effacée puis recopiée, « changed » sans fin (ecart-pi.sh rouge) et, pour
    un descripteur, un package fantôme compilé par colcon."""
    retires = yaml.safe_load(VARS.read_text(encoding="utf-8"))["chemins_retires_robot"]
    sources = [p[len("src/robot/"):] for p in retires if p.startswith("src/robot/")]
    assert sources, "aucune entrée src/robot/ : le test ne vérifierait rien"
    # Exclusions de la copie à plat de conf/ros2/ (points de montage vides créés en root par un
    # Docker du PC, non suivis) : lues dans le rôle, pas recopiées ici.
    taches = yaml.safe_load(SYNCHRONISE.read_text(encoding="utf-8"))
    a_plat = next(t for t in taches if str(t.get("name", "")).startswith("Synchronize directory")
                  and t["synchronize"]["src"].endswith("/conf/ros2/"))
    exclus = {o[len("--exclude=/"):].strip("/") for o in a_plat["synchronize"]["rsync_opts"]
              if o.startswith("--exclude=/")}
    assert "robot" in exclus, exclus
    for rel in sources:
        assert not (ROBOT / rel).exists(), rel
        if rel.split("/")[0] not in exclus:
            assert not (ROBOT / "conf" / "ros2" / rel).exists(), f"conf/ros2/{rel} (copié à plat)"


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
# Moitié « Ansible » du lot 3d (hosts, chemins_retires_vision, rsync de conf/ros2/) : réservée
# (zone Déploiement, feu vert de David attendu). strict=True : dès que l'hôte vision est migré,
# ces tests PASSENT et pytest échoue sur l'XPASS -> retirer le marqueur, c'est la porte.
ANSIBLE_3D_EN_ATTENTE = pytest.mark.xfail(
    strict=True, reason="moitié Ansible de L1e-3d en attente du feu vert de David")


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


@ANSIBLE_3D_EN_ATTENTE
def test_l_hote_vision_pousse_son_package_et_lit_sa_sentinelle_renommee():
    vision = _hosts()["vision"]["hosts"]["ai"]
    assert "didier_vision" in vision["packages"]
    assert vision["sentinelle_build"] == "src/didier_vision/change"
    assert vision["launch_cmd"] == "ros2 run didier_vision vision_status --ros-args -r __ns:=/didier"
