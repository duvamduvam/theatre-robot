"""Contrat GRAVÉ du lot L1b — un nom par robot (namespace /<ROBOT_NAME>/).

Spec : theatre-robot/docs/spec-L1-contrats-donnees.md, « L1b — conception
détaillée (04/11) », décision 7 (preuve host). Tout est lu dans les VRAIS
fichiers des trois dépôts (robot, vision, télécommande) — jamais des copies.
La preuve en simulation est conf/scripts/validate-namespace.sh.

 (a) chaque *.launch.py pousse un namespace ABSOLU (PushRosNamespace(["/", …]))
     tiré de ROBOT_NAME, et aucun Node n'a de namespace= à lui ;
 (b) gz_bridge.yaml : tout ros_topic_name est relatif sauf {/clock, /tf} ;
 (c) aucun nom de topic absolu dans le code des nœuds (grep de L1a étendu aux
     scripts sans extension de didier_sim et aux constantes ODOM_TOPIC /
     NECK_TOPIC_SIM, gravées relatives) ;
 (d) chaque script conf/scripts qui appelle `ros2 topic` définit NS= et ne
     tape aucun topic non préfixé (regex gravée) ;
 + les compose posent ROBOT_NAME, la télécommande le prend en __ns, et
   twist_mux reçoit sa config en dictionnaire (piège du params-file namespacé).
"""
import ast
import pathlib
import re

import yaml

ROBOT = pathlib.Path(__file__).resolve().parents[4] / "legacy" / "dadou_robot_ros"
LEGACY = ROBOT.parent
MONO = LEGACY.parent
VISION = LEGACY / "dadou_vision_ros"
CONTROL = LEGACY / "dadou_control_ros"
DEPS = MONO / "packages"      # L1e-1 : les packages ROS autonomes ont déménagé ici
# L1e-4c : conf/ du robot et de la vision -> machines/{robot,vision}/, la sim -> machines/sim/.
MACHINES = MONO / "machines"

# Les SEULS noms globaux admis, par construction ROS (TimeSource, TF, logs,
# événements de paramètres). Rien d'autre — validate-namespace.sh applique la
# même liste en sim.
EXCEPTIONS_GLOBALES = {"/clock", "/tf", "/tf_static", "/rosout", "/parameter_events"}
BRIDGE_ABSOLUS = {"/clock", "/tf"}

# Regex GRAVÉE (spec, décision 7 d) : après le verbe, le topic doit commencer
# par $ (préfixe $NS) ou / (absolu explicite). Options APRÈS le topic.
CLI_NON_PREFIXEE = re.compile(r"ros2 topic (pub|echo|hz) [^$/]")
# Le grep de la porte de sortie L1a (publisher/subscription sur un nom absolu).
CREATE_ABSOLU = re.compile(r"create_(publisher|subscription)\([^,]+,\s*f?['\"]/")

EXCLUS = {"build", "install", "log", ".venv", "node_modules", "__pycache__"}


def _fichiers(racine, motif):
    return sorted(p for p in racine.rglob(motif)
                  if p.is_file() and not EXCLUS.intersection(p.relative_to(racine).parts))


def _launch_files():
    return [p for r in (ROBOT, VISION, CONTROL, DEPS) for p in _fichiers(r, "*.launch.py")]


# --- (a) launch files ---------------------------------------------------------

def test_les_sept_launch_sont_inventories():
    noms = sorted(str(p.relative_to(MONO)) for p in _launch_files())
    assert noms == [
        "packages/didier_bringup/launch/robot_app.launch.py",
        "packages/didier_description/launch/display.launch.py",
        "packages/didier_drive/launch/drive.launch.py",
        "packages/didier_rehearsal/launch/rehearsal.launch.py",
        "packages/didier_sim/launch/sim.launch.py",
        "packages/didier_vision/launch/vision.launch.py",
        "packages/didier_web/launch/web.launch.py",
    ]


def _appels(arbre, nom):
    return [c for c in ast.walk(arbre) if isinstance(c, ast.Call)
            and (getattr(c.func, "id", None) == nom or getattr(c.func, "attr", None) == nom)]


def test_chaque_launch_pousse_un_namespace_absolu_tire_de_robot_name():
    for p in _launch_files():
        src = p.read_text(encoding="utf-8")
        assert "PushRosNamespace" in src and "ROBOT_NAME" in src, p
        arbre = ast.parse(src)
        pushes = _appels(arbre, "PushRosNamespace")
        assert len(pushes) == 1, f"{p} : un seul PushRosNamespace attendu"
        arg = pushes[0].args[0]
        # ABSOLU : ["/", LaunchConfiguration("robot_name")] — idempotent quand un
        # launch en inclut un autre (drive dans robot_app).
        assert isinstance(arg, ast.List) and isinstance(arg.elts[0], ast.Constant) \
            and arg.elts[0].value == "/", p
        assert ast.unparse(arg.elts[1]) == "LaunchConfiguration('robot_name')", p
        env = [c for c in _appels(arbre, "EnvironmentVariable")
               if c.args and getattr(c.args[0], "value", None) == "ROBOT_NAME"]
        assert len(env) == 1, p
        assert {k.arg: getattr(k.value, "value", None) for k in env[0].keywords} \
            == {"default_value": "didier"}, p


def test_aucun_node_n_a_son_propre_namespace():
    for p in _launch_files():
        for c in _appels(ast.parse(p.read_text(encoding="utf-8")), "Node"):
            assert "namespace" not in {k.arg for k in c.keywords}, p


def test_tous_les_nodes_sont_dans_le_groupe():
    """Seul ce que porte le LaunchDescription renvoyé est lancé : il ne doit
    contenir QUE des DeclareLaunchArgument et l'unique GroupAction namespacé —
    aucun Node ni include ne peut alors échapper au namespace."""
    for p in _launch_files():
        arbre = ast.parse(p.read_text(encoding="utf-8"))
        assert len(_appels(arbre, "GroupAction")) == 1, p
        assert "add_action" not in p.read_text(encoding="utf-8"), p
        descriptions = _appels(arbre, "LaunchDescription")
        assert len(descriptions) == 1, p
        elements = descriptions[0].args[0].elts
        types = [getattr(e.func, "id", None) if isinstance(e, ast.Call) else None for e in elements]
        assert types[-1] == "GroupAction" and set(types[:-1]) <= {"DeclareLaunchArgument"}, (p, types)
        groupe = elements[-1].args[0].elts
        assert getattr(groupe[0].func, "id", None) == "PushRosNamespace", p


# --- twist_mux : le piège du params-file sous namespace ------------------------

def test_twist_mux_recoit_sa_config_en_dictionnaire():
    """Mesuré le 04/11 : passé en --params-file, twist_mux.yaml (clé racine
    `twist_mux:`) ne s'applique PAS à /didier/twist_mux — mux sans entrées NI
    verrou e_stop. drive.launch lit le fichier et passe le dictionnaire."""
    src = (DEPS / "didier_drive" / "launch" / "drive.launch.py").read_text(encoding="utf-8")
    arbre = ast.parse(src)
    mux = [c for c in _appels(arbre, "Node")
           if any(k.arg == "executable" and getattr(k.value, "value", None) == "twist_mux" for k in c.keywords)]
    assert len(mux) == 1
    kw = {k.arg: k.value for k in mux[0].keywords}
    assert ast.unparse(kw["parameters"].elts[0]) == "_twist_mux_parameters()"
    assert ast.literal_eval(kw["remappings"]) == [("cmd_vel_out", "cmd_vel_mux"), ("/diagnostics", "diagnostics")]
    assert '["twist_mux"]["ros__parameters"]' in src and '"twist_mux.yaml"' in src
    # Le dictionnaire passé est bien celui du fichier, verrou e_stop compris.
    conf = yaml.safe_load((DEPS / "didier_drive" / "config" / "twist_mux.yaml").read_text(encoding="utf-8"))
    params = conf["twist_mux"]["ros__parameters"]
    assert params["locks"]["e_stop"] == {"topic": "e_stop", "timeout": 0.0, "priority": 255}
    assert {k: v["priority"] for k, v in params["topics"].items()} == \
        {"remote": 100, "web": 50, "follow": 20, "anim": 10}


# --- (b) bridge gz ------------------------------------------------------------

def test_bridge_noms_ros_relatifs_sauf_clock_et_tf():
    entrees = yaml.safe_load((DEPS / "didier_sim" / "config" / "gz_bridge.yaml").read_text(encoding="utf-8"))
    absolus = {e["ros_topic_name"] for e in entrees if e["ros_topic_name"].startswith("/")}
    assert absolus == BRIDGE_ABSOLUS
    assert BRIDGE_ABSOLUS <= EXCEPTIONS_GLOBALES
    # Côté gz, rien ne change (le monde ignore ROS) : valeurs gravées.
    gz = {e["ros_topic_name"]: e["gz_topic_name"] for e in entrees}
    assert gz["cmd_vel"] == "/cmd_vel"
    assert gz["ground_truth/odom"] == "/ground_truth/odom"
    assert gz["neck/position"] == "/neck/position"
    assert gz["material_color"] == "/world/stage/material_color"
    assert gz["/tf"] == "/tf_gz"


# --- (c) aucun nom absolu dans le code ----------------------------------------

def _code_des_noeuds():
    # Le cœur (L1e-3c) et la vision (L1e-3d) sont dans DEPS : packages/didier_core/didier_core,
    # packages/didier_vision/didier_vision.
    zones = [CONTROL / "controller",
             LEGACY / "dadou_utils_ros", DEPS]
    fichiers = []
    for z in zones:
        for p in _fichiers(z, "*"):
            if "tests" in p.parts or "test" in p.parts:
                continue
            # .py ET scripts sans extension (didier_sim/scripts/*_sim_node : ils
            # avaient échappé au balayage de la spec).
            if p.suffix == ".py" or (p.suffix == "" and p.read_bytes()[:2] == b"#!"):
                fichiers.append(p)
    return fichiers


def test_aucun_create_publisher_ou_subscription_sur_un_nom_absolu():
    fautes = [f"{p}:{i}" for p in _code_des_noeuds()
              for i, ligne in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1)
              if CREATE_ABSOLU.search(ligne)]
    assert fautes == []


def test_aucune_constante_de_topic_absolue():
    fautes = []
    for p in _code_des_noeuds():
        try:
            arbre = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in arbre.body:
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) \
                    and isinstance(n.value.value, str) and n.value.value.startswith("/"):
                for t in n.targets:
                    if isinstance(t, ast.Name) and "TOPIC" in t.id:
                        fautes.append(f"{p}:{t.id}={n.value.value}")
    assert fautes == []


def test_constantes_sim_gravees_relatives():
    from didier_rehearsal import contracts
    assert contracts.ODOM_TOPIC == "ground_truth/odom"
    gaze = (DEPS / "didier_core" / "didier_core" / "nodes" / "gaze_follower_node.py").read_text(encoding="utf-8")
    assert re.search(r'^NECK_TOPIC_SIM = "neck/position"$', gaze, re.M)
    sim = DEPS / "didier_sim" / "scripts"
    assert '"{}/position".format(name)' in (sim / "servos_sim_node").read_text(encoding="utf-8")
    assert 'create_publisher(MaterialColor, "material_color", 10)' in \
        (sim / "leds_sim_node").read_text(encoding="utf-8")


# --- (d) scripts CLI ----------------------------------------------------------

def _scripts_cli():
    racines = (MACHINES / "robot" / "scripts", MACHINES / "vision" / "scripts", MACHINES / "sim",
               CONTROL / "conf" / "scripts")
    return [p for r in racines for p in _fichiers(r, "*.sh")
            if "ros2 topic" in p.read_text(encoding="utf-8")]


def test_scripts_attendus_couverts():
    noms = {p.name for p in _scripts_cli()}
    assert {"pub.sh", "validate-rehearsal-route.sh", "validate-rehearsal-faults.sh",
            "validate-rehearsal-chantiers.sh", "validate-jeu-a1.sh", "validate-cmdvel-protocol.sh",
            "validate-namespace.sh", "collect-incident.sh", "calibre-distance.sh"} <= noms


def test_chaque_script_cli_definit_ns_et_prefixe_ses_topics():
    for p in _scripts_cli():
        src = p.read_text(encoding="utf-8")
        assert re.search(r'^NS="/\$\{ROBOT_NAME:-didier\}"$', src, re.M), f"{p} : NS= absent"
        fautes = [f"{p.name}:{i}: {l.strip()}" for i, l in enumerate(src.splitlines(), 1)
                  if CLI_NON_PREFIXEE.search(l)]
        assert fautes == []


def test_regex_cli_attrape_les_formes_fautives():
    """La regex gravée elle-même : elle DOIT rougir sur les formes d'avant L1b."""
    for faute in ['ros2 topic pub -1 route theatre_interfaces/msg/StringTime',
                  'ros2 topic echo --once "$1" --field x',
                  'ros2 topic echo route_state --once',
                  'ros2 topic hz cmd_vel']:
        assert CLI_NON_PREFIXEE.search(faute), faute
    for juste in ['ros2 topic pub $NS/route theatre_interfaces/msg/StringTime "{}" -1',
                  'ros2 topic echo $NS/ground_truth/odom --once', 'ros2 topic hz $NS/cmd_vel']:
        assert not CLI_NON_PREFIXEE.search(juste), juste


def test_pilote_rclpy_de_jeu_a1_namespace():
    src = (MACHINES / "sim" / "validate-jeu-a1.sh").read_text(encoding="utf-8")
    assert 'super().__init__("validate_jeu_a1", namespace=NS)' in src
    assert 'python3 - "$CAP/capture.json" "$DUREE" "$NS"' in src


# --- variable ROBOT_NAME : compose + télécommande ------------------------------

def test_les_compose_posent_robot_name():
    composes = [MACHINES / "robot/docker/arm/docker-compose-arm.yml",
                MACHINES / "sim/banc-robot/docker-compose-x86.yml",
                MACHINES / "sim/banc-robot/docker-compose-sim.yml",
                MACHINES / "vision/docker/arm/docker-compose-arm.yml",
                MACHINES / "sim/banc-vision/docker-compose-x86.yml",
                CONTROL / "conf/docker/arm/docker-compose-arm.yml", CONTROL / "conf/docker/x86/docker-compose-x86.yml"]
    for p in composes:
        assert "- ROBOT_NAME=${ROBOT_NAME:-didier}" in p.read_text(encoding="utf-8"), p


def test_la_telecommande_prend_le_meme_namespace():
    for nom in ("launch-ros-in-docker.sh", "launch-local-docker.sh"):
        src = (CONTROL / "conf" / "scripts" / nom).read_text(encoding="utf-8")
        assert "ros2 run controller controller_node --ros-args -r __ns:=/${ROBOT_NAME:-didier}" in src, nom
        assert re.search(r"^ros2 run controller controller_node$", src, re.M) is None, nom


def test_validate_namespace_monte_dans_la_sim():
    compose = (MACHINES / "sim/banc-robot/docker-compose-sim.yml").read_text(encoding="utf-8")
    assert "- ../validate-namespace.sh:/home/ros2_ws/validate-namespace.sh:ro" in compose
    script = (MACHINES / "sim" / "validate-namespace.sh").read_text(encoding="utf-8")
    # Même liste d'exceptions que ce test (gravée des deux côtés).
    for nom in sorted(EXCEPTIONS_GLOBALES):
        assert nom in script
