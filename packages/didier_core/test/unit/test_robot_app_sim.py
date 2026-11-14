"""Décision 15 de la spec L2 (lot L2b) — robot_app.launch.py gagne 7 arguments pour la SIM, et le
robot ne voit AUCUNE différence. Valeurs GRAVÉES en littéral (relevées sur main 8065be0, avant
L2b) : jamais recalculées avec le fichier testé.

Lu par AST (le venv de l'hôte n'a pas `launch`) :
  - sans argument, les paramètres effectifs de chaque nœud sont ceux d'avant ;
  - les sept arguments ne paramètrent QUE web_bridge_node ;
  - les blocs roues (wheels_node, drive_launch) et les 5 servos sont intouchés ; use_sim_time
    n'est pas déclaré (il passe par héritage jusqu'à drive.launch.py, fait 12 de la spec) ;
  - aucun fichier de configuration d'un Pi ne passe web_drive, rehearsal ou use_sim_time, ni ne
    cite complement_sim.launch.py.
"""
import ast
import pathlib
import re

MONO = pathlib.Path(__file__).resolve().parents[4]
ROBOT_APP = MONO / "packages" / "didier_bringup" / "launch" / "robot_app.launch.py"
COMPLEMENT = MONO / "packages" / "didier_bringup" / "launch" / "complement_sim.launch.py"
WEB_BRIDGE = MONO / "packages" / "didier_web" / "didier_web" / "web_bridge_node.py"

# Les sept arguments et leur défaut (= la valeur d'avant L2b), décision 15.
ARGUMENTS_SIM = {
    "web_port": "8765", "web_drive": "false", "rehearsal": "false",
    "camera_topic": "camera/image_raw/compressed", "camera_compressed": "true",
    "perception_topic": "", "exterior_topic": "",
}
# Paramètres EFFECTIFS de web_bridge_node sans argument. Avant L2b : json_dir, camera_topic,
# camera_compressed, data_edit_enabled ; les cinq clés neuves valent le défaut du nœud.
WEB_BRIDGE_SANS_ARGUMENT = {
    "json_dir": "/home/ros2_ws/src/robot/json",
    "camera_topic": "camera/image_raw/compressed",
    "camera_compressed": True,
    "data_edit_enabled": "env DATA_EDIT (défaut false)",
    "web_port": 8765,
    "drive_enabled": False,
    "rehearsal_enabled": False,
    "perception_topic": "",
    "exterior_topic": "",
}
# Défauts déclarés par le nœud pour les cinq clés neuves (web_bridge_node.py).
DEFAUTS_DU_NOEUD = {"web_port": "8765", "drive_enabled": "False", "rehearsal_enabled": "False",
                    "perception_topic": '""', "exterior_topic": '""'}
# Tous les autres appels, texte normalisé (ast.unparse) relevé sur main 8065be0.
AUTRES_APPELS = {
    "ai_server_node": "Node(package='didier_core', executable='ai_node', name='ai_node')",
    "animations_server_node": "Node(package='didier_core', executable='animations_node', name='animations_node')",
    "audio_server_node": "Node(package='didier_core', executable='audio_node', name='audio_node')",
    "face_server_node": "Node(package='didier_core', executable='face_node', name='face_node')",
    "lights_server_node": "Node(package='didier_core', executable='lights_node', name='lights_node')",
    "relays_server_node": "Node(package='didier_core', executable='relays_node', name='relays_node')",
    "system_server_node": "Node(package='didier_core', executable='system_node', name='system_node')",
    "wheels_server_node": "Node(package='didier_core', executable='wheels_node', name='wheels_node')",
    "neck_server_node": "Node(package='didier_core', executable='servo_node', name='{}_node'.format(NECK), "
                        "parameters=[{NAME: NECK}, {HEAD_PWM_NB: config[HEAD_PWM_NB]}, {DEFAULT_POS: 50}, {MAX_POS: 180}])",
    "left_arm_server_node": "Node(package='didier_core', executable='servo_node', name='{}_node'.format(LEFT_ARM), "
                            "parameters=[{NAME: LEFT_ARM}, {HEAD_PWM_NB: config[LEFT_ARM_NB]}, {DEFAULT_POS: 90}, "
                            "{MAX_POS: 180}])",
    "right_arm_server_node": "Node(package='didier_core', executable='servo_node', name='{}_node'.format(RIGHT_ARM), "
                             "parameters=[{NAME: RIGHT_ARM}, {HEAD_PWM_NB: config[RIGHT_ARM_NB]}, "
                             "{DEFAULT_POS: 180}, {MAX_POS: 180}])",
    "left_eye_server_node": "Node(package='didier_core', executable='servo_node', name='{}_node'.format(LEFT_EYE), "
                            "parameters=[{NAME: LEFT_EYE}, {HEAD_PWM_NB: config[LEFT_EYE_NB]}, {DEFAULT_POS: 70}, "
                            "{MAX_POS: 180}])",
    "right_eye_server_node": "Node(package='didier_core', executable='servo_node', name='{}_node'.format(RIGHT_EYE), "
                             "parameters=[{NAME: RIGHT_EYE}, {HEAD_PWM_NB: config[RIGHT_EYE_NB]}, "
                             "{DEFAULT_POS: 45}, {MAX_POS: 180}])",
    "catalogue_node": "Node(package='didier_web', executable='catalogue', name='catalogue_node', "
                      "parameters=[{'json_dir': '/home/ros2_ws/src/robot/json', "
                      "'deploy_sha_file': '/home/ros2_ws/src/robot/conf/DEPLOY_SHA'}])",
    "data_edit_node": "Node(package='didier_web', executable='data_edit', name='data_edit_node', "
                      "parameters=[{'enabled': ParameterValue(EnvironmentVariable('DATA_EDIT', "
                      "default_value='false'), value_type=bool)}])",
    "drive_launch": "IncludeLaunchDescription(PythonLaunchDescriptionSource(PathJoinSubstitution("
                    "[FindPackageShare('didier_drive'), 'launch', 'drive.launch.py'])))",
}
# Ordre de lancement (group.append), inchangé.
GROUPE = ["animations_server_node", "audio_server_node", "lights_server_node", "relays_server_node",
          "system_server_node", "wheels_server_node", "neck_server_node", "left_arm_server_node",
          "right_arm_server_node", "left_eye_server_node", "right_eye_server_node", "web_bridge_node",
          "catalogue_node", "data_edit_node", "drive_launch"]
BOOLEENS = {"true": True, "false": False}


def _arbre():
    return ast.parse(ROBOT_APP.read_text(encoding="utf-8"))


def _appels_affectes(arbre):
    return {n.targets[0].id: n.value for n in ast.walk(arbre)
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
            and getattr(n.value.func, "id", None) in ("Node", "IncludeLaunchDescription")}


def _arguments_declares(arbre):
    declares = {}
    for c in ast.walk(arbre):
        if isinstance(c, ast.Call) and getattr(c.func, "id", None) == "DeclareLaunchArgument":
            defaut = next(k.value for k in c.keywords if k.arg == "default_value")
            declares[c.args[0].value] = defaut.value if isinstance(defaut, ast.Constant) else ast.unparse(defaut)
    return declares


def _valeur_effective(noeud, declares):
    """Valeur d'un paramètre sans argument de launch : constante, ou défaut de l'argument typé."""
    if isinstance(noeud, ast.Constant):
        return noeud.value
    texte = ast.unparse(noeud)
    if texte == "ParameterValue(EnvironmentVariable('DATA_EDIT', default_value='false'), value_type=bool)":
        return "env DATA_EDIT (défaut false)"
    m = re.fullmatch(r"ParameterValue\(LaunchConfiguration\('(\w+)'\), value_type=(str|int|bool)\)", texte)
    assert m, texte
    brut = declares[m.group(1)]
    return {"str": str, "int": int, "bool": BOOLEENS.__getitem__}[m.group(2)](brut)


def test_les_sept_arguments_sont_declares_avec_les_defauts_d_avant():
    declares = _arguments_declares(_arbre())
    assert declares == {"robot_name": "EnvironmentVariable('ROBOT_NAME', default_value='didier')", **ARGUMENTS_SIM}


def test_use_sim_time_n_est_pas_declare():
    assert "use_sim_time" not in _arguments_declares(_arbre())


def test_sans_argument_le_pont_web_garde_ses_parametres_d_avant():
    arbre = _arbre()
    declares = _arguments_declares(arbre)
    web = _appels_affectes(arbre)["web_bridge_node"]
    params = next(k.value for k in web.keywords if k.arg == "parameters").elts
    assert len(params) == 1
    effectifs = {k.value: _valeur_effective(v, declares) for k, v in zip(params[0].keys, params[0].values)}
    assert effectifs == WEB_BRIDGE_SANS_ARGUMENT


def test_les_cles_neuves_valent_le_defaut_declare_par_le_noeud():
    src = WEB_BRIDGE.read_text(encoding="utf-8")
    for cle, defaut in DEFAUTS_DU_NOEUD.items():
        assert f'self.declare_parameter("{cle}", {defaut})' in src, cle


def test_les_sept_arguments_ne_parametrent_que_le_pont_web():
    arbre = _arbre()
    appels = _appels_affectes(arbre)
    for nom, appel in appels.items():
        if nom == "web_bridge_node":
            continue
        assert "LaunchConfiguration" not in ast.unparse(appel), nom
    lus = {c.args[0].value for c in ast.walk(appels["web_bridge_node"])
           if isinstance(c, ast.Call) and getattr(c.func, "id", None) == "LaunchConfiguration"}
    assert lus == set(ARGUMENTS_SIM)


def test_les_autres_noeuds_les_roues_et_les_servos_sont_intouches():
    appels = _appels_affectes(_arbre())
    assert {n: ast.unparse(a) for n, a in appels.items() if n != "web_bridge_node"} == AUTRES_APPELS


def test_l_ordre_de_lancement_est_inchange():
    lances = [c.args[0].id for c in ast.walk(_arbre()) if isinstance(c, ast.Call)
              and getattr(c.func, "attr", None) == "append" and getattr(c.func.value, "id", None) == "group"]
    assert lances == GROUPE


def _fichiers_des_pi():
    """Les fichiers de configuration qui partent sur un Pi et y décident du lancement."""
    machines = MONO / "machines"
    return [*sorted(machines.glob("*/machine.yml")), *sorted(machines.glob("*/docker/arm/*.yml")),
            *sorted((MONO / "legacy" / "dadou_control_ros" / "conf" / "docker" / "arm").glob("*.yml"))]


def test_aucun_fichier_d_un_pi_ne_passe_les_drapeaux_sim():
    fichiers = _fichiers_des_pi()
    assert len(fichiers) >= 4
    interdit = re.compile(r"\b(web_drive|rehearsal|use_sim_time)\s*:=|\b(WEB_DRIVE|REHEARSAL)\b|complement_sim")
    for f in fichiers:
        assert not interdit.search(f.read_text(encoding="utf-8")), f


def test_le_pi_robot_lance_le_bringup_sans_argument():
    src = (MONO / "machines" / "robot" / "machine.yml").read_text(encoding="utf-8")
    assert "\nlaunch_cmd: ros2 launch didier_bringup robot_app.launch.py\n" in src


def test_le_complement_sim_refuse_hors_43_avant_toute_action():
    fonction = next(n for n in ast.parse(COMPLEMENT.read_text(encoding="utf-8")).body
                    if isinstance(n, ast.FunctionDef) and n.name == "generate_launch_description")
    premiers = [ast.unparse(n).splitlines()[0] for n in fonction.body[:2]]
    assert premiers == ["domaine = os.environ.get('ROS_DOMAIN_ID', '').strip()",
                        "if domaine != DOMAINE_SIM:"]
    assert isinstance(fonction.body[1].body[0], ast.Raise)
    assert 'DOMAINE_SIM = "43"' in COMPLEMENT.read_text(encoding="utf-8")
