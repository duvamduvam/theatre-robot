"""Sim multi-conteneurs (spec L2, lot L2b, décisions 1, 2, 7, 8, 10, 11, 14, 17, 18) — la
STRUCTURE de machines/sim/docker-compose.yml et de ce qu'il lance, gravée en littéral.

Ce que la porte prouve en vrai (docker compose up, fumée) ne se teste pas ici ; ce qui est
gravé, c'est ce qui rendrait la sim dangereuse ou fausse sans bruit : un domaine lu dans
l'environnement, un conteneur privilégié ou relancé seul, gz-transport hors de `monde`, un
conteneur robot qui n'est plus celui du Pi, l'échafaudage pid partagé passé dans un compose ARM.
"""
import ast
import pathlib
import re

import yaml

MONO = pathlib.Path(__file__).resolve().parents[4]
MACHINES = MONO / "machines"
SIM = MACHINES / "sim"
PACKAGES = MONO / "packages"
COMPOSE = SIM / "docker-compose.yml"
BANC = SIM / "docker-compose.banc.yml"

# Décision 1 : service -> (conteneur, image locale, Dockerfile relatif au dépôt).
SERVICES = {
    "monde": ("didier-sim-monde", "didier-sim/monde:local", "machines/sim/monde/Dockerfile"),
    "robot": ("didier-sim-robot", "didier-sim/robot:local", "machines/robot/docker/Dockerfile"),
    "vision": ("didier-sim-vision", "didier-sim/vision:local", "machines/vision/docker/Dockerfile"),
    "telecommande": ("didier-sim-telecommande", "didier-sim/telecommande:local",
                     "legacy/dadou_control_ros/conf/docker/x86/Dockerfile-x86"),
}
# Les packages du conteneur `monde` (décision 18 : Dockerfile-sim moins bringup, drive, web).
PACKAGES_MONDE = ["dadou_utils_ros", "didier_core", "didier_description", "didier_jeu", "didier_rehearsal",
                  "didier_sim", "theatre_contrats", "theatre_interfaces"]
INTERDITS_MONDE = {"didier_core", "didier_drive", "didier_web"}   # aucun de leurs exécutables dans monde
EPREUVES = ["validate-catalogue.sh", "validate-data-edit.sh", "validate-jeu-a1.sh", "validate-machines.sh",
            "validate-namespace.sh", "validate-rehearsal-chantiers.sh", "validate-rehearsal-faults.sh",
            "validate-rehearsal-route.sh"]
# Décision 2 : la dernière commande de l'entrée du robot, mot pour mot.
EXEC_ROBOT = ('exec /bin/bash /home/ros2_ws/src/robot/conf/scripts/launch-ros-in-docker.sh '
              'use_sim_time:=true camera_topic:=camera/image_raw camera_compressed:=false '
              'perception_topic:=camera/image_raw/compressed exterior_topic:=camera_ext/image_raw '
              'web_port:=${WEB_PORT:-8765} web_drive:=${WEB_DRIVE:-false} rehearsal:=${REHEARSAL:-false}')


def _compose(chemin=COMPOSE):
    return yaml.safe_load(chemin.read_text(encoding="utf-8"))


def _services():
    return _compose()["services"]


def _env(service):
    return dict(e.split("=", 1) for e in service.get("environment", []))


def _cibles(service):
    return {v.split(":")[1]: v.split(":")[0] for v in service.get("volumes", [])}


def _machine(nom):
    return yaml.safe_load((MACHINES / nom / "machine.yml").read_text(encoding="utf-8"))


def test_quatre_services_un_projet():
    compose = _compose()
    assert compose["name"] == "didier-sim"
    assert sorted(compose["services"]) == sorted(SERVICES)
    for nom, (conteneur, image, dockerfile) in SERVICES.items():
        s = compose["services"][nom]
        assert (s["container_name"], s["image"]) == (conteneur, image), nom
        assert (COMPOSE.parent / s["build"]["context"] / s["build"]["dockerfile"]).resolve() == MONO / dockerfile, nom


def test_domaine_43_en_litteral_partout_et_jamais_lu_dans_l_environnement():
    for nom, s in _services().items():
        assert _env(s)["ROS_DOMAIN_ID"] == "43", nom
        assert _env(s)["ROBOT_NAME"] == "${ROBOT_NAME:-didier}", nom
    for f in sorted(SIM.glob("*.yml")):
        assert "${ROS_DOMAIN_ID" not in f.read_text(encoding="utf-8"), f.name
        assert "ROS_DOMAIN_ID=42" not in f.read_text(encoding="utf-8"), f.name


def test_reseau_et_ipc_de_l_hote_partout():
    for nom, s in _services().items():
        assert (s["network_mode"], s["ipc"]) == ("host", "host"), nom


def test_aucun_service_privilegie_relance_ou_avec_dev():
    for nom, s in _services().items():
        assert "privileged" not in s and "restart" not in s and "devices" not in s, nom
        cibles = _cibles(s)
        assert "/dev" not in cibles and "/dev/snd" not in cibles, nom
        dev = sorted(c for c in cibles if c.startswith("/dev"))
        assert dev == (["/dev/dri"] if nom == "monde" else []), nom


def test_gz_transport_confine_a_monde():
    for nom, s in _services().items():
        gz = {k: v for k, v in _env(s).items() if k.startswith("GZ_")}
        assert gz == ({"GZ_IP": "127.0.0.1"} if nom == "monde" else {}), nom


def test_espace_de_processus_partage_avec_monde_en_sim_seulement():
    services = _services()
    assert "pid" not in services["monde"]
    for nom in ("robot", "vision", "telecommande"):
        assert services[nom]["pid"] == "service:monde", nom
    # Échafaudage de TEST : absent de tout compose qui part sur un Pi.
    arm = [*sorted(MACHINES.glob("*/docker/arm/*.yml")),
           *sorted((MONO / "legacy/dadou_control_ros/conf/docker/arm").glob("*.yml"))]
    assert len(arm) >= 3
    for f in arm:
        for s in _compose(f)["services"].values():
            assert "pid" not in s, f


def test_journaux_partages_par_monde_et_robot_et_colcon_par_service():
    services = _services()
    assert _cibles(services["monde"])["/home/ros2_ws/log"] == "./workspace/log"
    assert _cibles(services["robot"])["/home/ros2_ws/log"] == "./workspace/log"
    assert _cibles(services["vision"])["/home/ros2_ws/log"] == "./workspace/log-vision"
    assert _cibles(services["telecommande"])["/home/ros2_ws/log"] == "./workspace/log-telecommande"
    for nom, s in services.items():
        assert _env(s)["COLCON_LOG_PATH"] == f"/home/ros2_ws/log/colcon-{nom}", nom
        # build/ et install/ jamais persistés (colcon à chaque up).
        assert not [c for c in _cibles(s) if c in ("/home/ros2_ws/build", "/home/ros2_ws/install")], nom
    assert "machines/sim/workspace/" in (MONO / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_robot_et_vision_construisent_le_dockerfile_du_pi_avec_leur_liste_de_packages():
    services = _services()
    for machine, plus in (("robot", ["conf", "data"]), ("vision", ["conf"])):
        s, paquets = services[machine], sorted(_machine(machine)["packages"])
        contextes = s["build"]["additional_contexts"]
        assert sorted(contextes) == sorted(paquets + plus), machine
        for p in paquets:
            assert (COMPOSE.parent / contextes[p]).resolve() == PACKAGES / p, (machine, p)
        assert (COMPOSE.parent / contextes["conf"]).resolve() == MACHINES / machine
        montes = sorted(c.removeprefix("/home/ros2_ws/src/") for c in _cibles(s)
                        if c.startswith("/home/ros2_ws/src/") and "/" not in c.removeprefix("/home/ros2_ws/src/"))
        assert [m for m in montes if m not in ("robot", "vision")] == paquets, machine
    assert (COMPOSE.parent / services["robot"]["build"]["additional_contexts"]["data"]).resolve() == MONO / "data"


def test_monde_porte_ses_packages_ni_bringup_ni_drive_ni_web():
    s = _services()["monde"]
    assert sorted(set(s["build"]["additional_contexts"]) - {"data"}) == PACKAGES_MONDE
    montes = sorted(c.removeprefix("/home/ros2_ws/src/") for c in _cibles(s)
                    if c.startswith("/home/ros2_ws/src/") and "/" not in c.removeprefix("/home/ros2_ws/src/"))
    assert montes == PACKAGES_MONDE
    copies = sorted(l.split()[1].removeprefix("--from=") for l in
                    (SIM / "monde" / "Dockerfile").read_text(encoding="utf-8").splitlines()
                    if l.startswith("COPY --from=") and not l.startswith("COPY --from=data"))
    assert copies == PACKAGES_MONDE
    entree = (SIM / "monde" / "entree.sh").read_text(encoding="utf-8").replace("\\\n", " ")
    colcon = re.search(r"colcon build --packages-select ([^\n]+)", entree).group(1)
    assert sorted(colcon.split()) == PACKAGES_MONDE


def _executables_lances(launch):
    return {(ast.literal_eval(k.value) if isinstance(k.value, ast.Constant) else ast.unparse(k.value))
            for c in ast.walk(ast.parse(launch.read_text(encoding="utf-8")))
            if isinstance(c, ast.Call) and getattr(c.func, "id", None) == "Node"
            for k in c.keywords if k.arg == "package"}


def test_aucun_launch_de_monde_ne_demarre_un_executable_du_robot():
    for launch in (PACKAGES / "didier_sim/launch/monde.launch.py",
                   PACKAGES / "didier_rehearsal/launch/rehearsal.launch.py"):
        assert not _executables_lances(launch) & INTERDITS_MONDE, launch.name
    entree = (SIM / "monde" / "entree.sh").read_text(encoding="utf-8")
    assert [l for l in entree.splitlines() if "ros2 launch" in l and not l.lstrip().startswith("#")] == [
        "exec ros2 launch didier_sim monde.launch.py world:=${WORLD:-stage} headless:=${HEADLESS:-false}"]


def test_seul_monde_porte_gazebo():
    """Aucun autre conteneur ne lance de processus gz : ni ros_gz dans leurs Dockerfiles, ni gz
    dans ce que lance le robot (robot_app, drive, complement_sim)."""
    for rel in ("machines/robot/docker/Dockerfile", "machines/vision/docker/Dockerfile",
                "legacy/dadou_control_ros/conf/docker/x86/Dockerfile-x86"):
        assert "ros-gz" not in (MONO / rel).read_text(encoding="utf-8"), rel
    for launch in ("didier_bringup/launch/robot_app.launch.py", "didier_bringup/launch/complement_sim.launch.py",
                   "didier_drive/launch/drive.launch.py"):
        assert not {p for p in _executables_lances(PACKAGES / launch) if p.startswith("ros_gz")}, launch
    assert "ros-jazzy-ros-gz" in (SIM / "monde" / "Dockerfile").read_text(encoding="utf-8")


def test_les_epreuves_sont_montees_dans_monde_en_lecture_seule():
    cibles = _cibles(_services()["monde"])
    assert sorted(p.name for p in SIM.glob("validate-*.sh")) == EPREUVES
    for script in EPREUVES:
        assert cibles[f"/home/ros2_ws/{script}"] == f"./{script}", script
        assert f"./{script}:/home/ros2_ws/{script}:ro" in _services()["monde"]["volumes"]
    assert "..:/home/ros2_ws/machines:ro" in _services()["monde"]["volumes"]
    # Mêmes données que le robot, aux chemins que lisent les nœuds de sim et les épreuves.
    assert cibles["/home/ros2_ws/json"] == cibles["/home/ros2_ws/src/robot/json"] == "../../data/json"
    assert cibles["/home/ros2_ws/src/robot/medias"] == "../../data/medias"


def test_l_entree_du_robot_refuse_hors_43_et_lance_le_vrai_bringup_avec_les_arguments_de_la_sim():
    robot = _services()["robot"]
    assert robot["entrypoint"] == ["/bin/bash", "/home/ros2_ws/sim/entree-robot.sh"]
    assert "./robot/entree.sh:/home/ros2_ws/sim/entree-robot.sh:ro" in robot["volumes"]
    lignes = [l.strip() for l in (SIM / "robot" / "entree.sh").read_text(encoding="utf-8").splitlines()
              if l.strip() and not l.lstrip().startswith("#")]
    assert lignes[0] == 'if [ "${ROS_DOMAIN_ID:-}" != 43 ]; then'
    assert " ".join(l.rstrip("\\").strip() for l in lignes[lignes.index(
        "exec /bin/bash /home/ros2_ws/src/robot/conf/scripts/launch-ros-in-docker.sh \\"):]) == EXEC_ROBOT
    assert ("exec ros2 launch didier_bringup complement_sim.launch.py face:=${FACE:-false} "
            "face_port:=${FACE_PORT:-8766}") in lignes


def test_l_entree_du_monde_refuse_hors_43_avant_tout():
    lignes = [l for l in (SIM / "monde" / "entree.sh").read_text(encoding="utf-8").splitlines()
              if l.strip() and not l.lstrip().startswith("#")]
    assert lignes[:2] == ["set -e", 'if [ "${ROS_DOMAIN_ID:-}" != 43 ]; then']


def test_monde_launch_refuse_hors_43_avant_toute_action():
    src = (PACKAGES / "didier_sim/launch/monde.launch.py").read_text(encoding="utf-8")
    fonction = next(n for n in ast.parse(src).body
                    if isinstance(n, ast.FunctionDef) and n.name == "generate_launch_description")
    assert [ast.unparse(n).splitlines()[0] for n in fonction.body[:2]] == [
        "domaine = os.environ.get('ROS_DOMAIN_ID', '').strip()", "if domaine != DOMAINE_SIM:"]
    assert isinstance(fonction.body[1].body[0], ast.Raise)
    assert 'DOMAINE_SIM = "43"' in src


def test_la_vision_de_la_sim_n_a_ni_secret_ni_conversation():
    vision = _services()["vision"]
    env = _env(vision)
    assert (env["CHAT"], env["VISION_SIM_CAMERA_TOPIC"]) == ("false", "camera/image_raw")
    assert not [v for v in vision["volumes"] if "secret" in v or ".config/didier" in v]
    # Seul le script de démarrage du Pi est monté de la conf (pas un éventuel secret local).
    assert _cibles(vision)["/home/ros2_ws/src/vision/conf/scripts"] == "../vision/scripts"
    assert "/home/ros2_ws/src/vision/conf" not in _cibles(vision)
    for nom, s in _services().items():
        assert not [v for v in s.get("volumes", []) if ".config/didier" in v], nom


def test_la_surcouche_banc_ne_touche_que_la_vision():
    banc = _compose(BANC)["services"]
    assert sorted(banc) == ["vision"]
    v = banc["vision"]
    assert v["privileged"] is True
    assert "${HOME}/.config/didier/vision-conf-secret:/home/ros2_ws/src/vision/conf/secret:ro" in v["volumes"]
    assert "./banc-vision/asound-pc.conf:/etc/asound.conf:ro" in v["volumes"]
    assert "/dev:/dev" in v["volumes"]
    assert "ROS_DOMAIN_ID" not in "\n".join(v["environment"])   # le domaine reste celui de la base
    assert _env(v)["CHAT"] == "${CHAT:-false}"
