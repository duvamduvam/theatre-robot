"""Contrat du nœud corps_sur (spec A0 §3.2, §6.1) : noms, types, QoS GRAVÉS ; le nœud n'en code
aucun en dur et n'a aucun « if » de règle ; l'insertion dans la chaîne (twist_mux, drive.launch).

Le nœud importe rclpy : il n'est jamais importé sur l'hôte, on lit son SOURCE (AST)."""
import ast
import re

import yaml

from conftest import MONO
from didier_corps_sur import contrat
from didier_corps_sur.contrat import Qos

PKG = MONO / "packages" / "didier_corps_sur"
NODE = PKG / "didier_corps_sur" / "corps_sur_node.py"
DRIVE = MONO / "packages" / "didier_drive"


def test_noms_graves():
    assert contrat.NOM_NOEUD == "corps_sur"
    assert contrat.CONFIG_DEFAUT == "/home/ros2_ws/src/robot/conf/corps_sur.yaml"
    assert contrat.ENTREES == {"anim": "cmd_vel_anim", "follow": "cmd_vel_follow", "web": "cmd_vel_web"}
    assert contrat.SORTIES == {"anim": "cmd_vel_anim_sur", "follow": "cmd_vel_follow_sur",
                               "web": "cmd_vel_web_sur"}
    assert (contrat.SCAN, contrat.E_STOP, contrat.BATTEMENT, contrat.REARMER, contrat.ETAT,
            contrat.DIAGNOSTICS) == ("scan", "e_stop", "superviseur/battement", "corps_sur/rearmer",
                                     "corps_sur/etat", "diagnostics")
    tous = (*contrat.ABONNEMENTS, *contrat.PUBLICATIONS)
    assert all(not n.startswith("/") for n in tous)   # relatifs : sous /<ROBOT_NAME>/
    assert len(set(tous)) == 12


def test_types_graves():
    t = "geometry_msgs/msg/Twist"
    assert contrat.TYPES == {
        "scan": "sensor_msgs/msg/LaserScan", "e_stop": "std_msgs/msg/Bool",
        "superviseur/battement": "std_msgs/msg/Empty", "corps_sur/rearmer": "std_msgs/msg/Empty",
        "corps_sur/etat": "theatre_interfaces/msg/StringTime",
        "diagnostics": "diagnostic_msgs/msg/DiagnosticArray",
        "cmd_vel_anim": t, "cmd_vel_follow": t, "cmd_vel_web": t,
        "cmd_vel_anim_sur": t, "cmd_vel_follow_sur": t, "cmd_vel_web_sur": t}


def test_qos_gravees():
    fiable1, fiable10 = Qos(True, 1), Qos(True, 10)
    assert contrat.QOS == {
        "scan": Qos(False, 1), "e_stop": fiable10, "superviseur/battement": Qos(False, 1),
        "corps_sur/rearmer": fiable10, "corps_sur/etat": Qos(True, 1, True), "diagnostics": fiable10,
        "cmd_vel_anim": fiable1, "cmd_vel_follow": fiable1, "cmd_vel_web": fiable1,
        "cmd_vel_anim_sur": fiable10, "cmd_vel_follow_sur": fiable10, "cmd_vel_web_sur": fiable10}
    assert (contrat.PERIODE_TIC_S, contrat.TICS_PAR_DIAGNOSTIC) == (0.05, 20)


def test_l_etat_latche_est_celui_de_theatre_contrats():
    """latched() = TRANSIENT_LOCAL profondeur 1, fiable par défaut (theatre_contrats/qos.py)."""
    src = (MONO / "packages" / "theatre_contrats" / "theatre_contrats" / "qos.py").read_text(encoding="utf-8")
    assert "QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)" in src
    assert contrat.QOS["corps_sur/etat"] == Qos(fiable=True, profondeur=1, latche=True)


def test_les_demandes_sont_les_topics_des_publieurs():
    """Les publieurs ne changent pas (§3.1) : wheels_bridge (anim), person_follower et
    route_driver (follow), web_bridge (web)."""
    bridge = (DRIVE / "didier_drive" / "wheels_bridge_node.py").read_text(encoding="utf-8")
    assert re.search(r'^CMD_VEL_ANIM_TOPIC = "cmd_vel_anim"$', bridge, re.M)
    follower = (MONO / "packages/didier_core/didier_core/nodes/person_follower_node.py").read_text(encoding="utf-8")
    assert re.search(r'^CMD_VEL_TOPIC = "cmd_vel_follow"', follower, re.M)
    route = (MONO / "packages/didier_rehearsal/didier_rehearsal/contracts.py").read_text(encoding="utf-8")
    assert re.search(r'^CMD_VEL_TOPIC = "cmd_vel_follow"$', route, re.M)
    web = (MONO / "packages/didier_web/didier_web/web_bridge_node.py").read_text(encoding="utf-8")
    assert 'create_publisher(Twist, "cmd_vel_web", 10)' in web


def test_twist_mux_ecoute_les_sorties_sures_et_la_telecommande_brute():
    params = yaml.safe_load((DRIVE / "config" / "twist_mux.yaml").read_text(encoding="utf-8"))
    entrees = {k: v["topic"] for k, v in params["twist_mux"]["ros__parameters"]["topics"].items()}
    assert entrees == {"remote": "cmd_vel_remote", "web": "cmd_vel_web_sur",
                       "follow": "cmd_vel_follow_sur", "anim": "cmd_vel_anim_sur"}


def _arbre():
    return ast.parse(NODE.read_text(encoding="utf-8"))


def test_le_noeud_ne_code_aucun_nom_de_topic():
    """Tout nom vient de `contrat` : aucune chaîne du nœud n'est un nom de topic du contrat."""
    noms = set(contrat.TYPES)
    litteraux = {n.value for n in ast.walk(_arbre()) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert not litteraux & noms


def test_le_noeud_n_a_aucun_if_de_regle():
    """Les seuls tests du nœud : republier l'état s'il a changé, diagnostics une fois sur 20,
    traduire une QoS, journaliser un réarmement accepté ou refusé, `if __name__`. Une règle de plus ici rougit : elle va dans `moteur`."""
    tests = sorted(ast.unparse(n.test) for n in ast.walk(_arbre()) if isinstance(n, (ast.If, ast.IfExp)))
    assert tests == ["__name__ == '__main__'", "accepte", "q.fiable", "q.latche",
                     "self._tics % contrat.TICS_PAR_DIAGNOSTIC == 0", "texte == self._etat_publie"]


def test_chaque_appel_du_journal_a_une_severite_fixe():
    """rclpy lève ValueError (« Logger severity cannot be changed between calls ») si une même
    ligne journalise sous deux sévérités. 21/11 en sim : `journal = info if accepte else warning`
    a tué le nœud au premier réarmement REFUSÉ après un accepté. Gravé : aucune sévérité choisie
    à l'exécution, et le réarmement a ses deux sites d'appel."""
    arbre = _arbre()
    for n in ast.walk(arbre):
        if isinstance(n, ast.IfExp):
            for branche in (n.body, n.orelse):
                assert "get_logger()" not in ast.unparse(branche), ast.unparse(n)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "log":
            raise AssertionError(f"get_logger().log(…, sévérité variable) : {ast.unparse(n)}")
    rearmer = next(f for f in ast.walk(arbre) if isinstance(f, ast.FunctionDef) and f.name == "_sur_rearmer")
    appels = [ast.unparse(n.func) for n in ast.walk(rearmer)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("info", "warning")]
    assert sorted(appels) == ["self.get_logger().info", "self.get_logger().warning"]


def test_aucun_module_pur_n_importe_ros():
    for p in sorted((PKG / "didier_corps_sur").glob("*.py")):
        if p.name == "corps_sur_node.py":
            continue
        src = p.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(import|from)\s+(rclpy|numpy|rosidl|geometry_msgs|sensor_msgs)\b", src, re.M), p.name


def test_le_noeud_s_arrete_sur_configuration_refusee_et_zero_sur_exception():
    main = next(f for f in _arbre().body if isinstance(f, ast.FunctionDef) and f.name == "main")
    corps_main = ast.unparse(main)
    assert "except ReglagesError" in corps_main and "sys.exit(2)" in corps_main
    assert "noeud.zero_partout()" in corps_main


def test_point_d_entree():
    setup = (PKG / "setup.py").read_text(encoding="utf-8")
    assert "'corps_sur_node = didier_corps_sur.corps_sur_node:main'" in setup


def _drive_launch():
    return ast.parse((DRIVE / "launch" / "drive.launch.py").read_text(encoding="utf-8"))


def test_drive_launch_lance_corps_sur_sans_relance_dans_le_groupe():
    noeuds = [c for c in ast.walk(_drive_launch()) if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "Node"]
    corps = [c for c in noeuds if any(k.arg == "package" and getattr(k.value, "value", None) == "didier_corps_sur"
                                      for k in c.keywords)]
    assert len(corps) == 1
    kw = {k.arg: k.value for k in corps[0].keywords}
    assert ast.literal_eval(kw["executable"]) == "corps_sur_node"
    assert ast.literal_eval(kw["name"]) == "corps_sur"
    assert ast.literal_eval(kw["respawn"]) is False
    assert ast.unparse(kw["parameters"]) == (
        "[{'use_sim_time': use_sim_time, 'config': LaunchConfiguration('corps_sur_config')}]")
    src = (DRIVE / "launch" / "drive.launch.py").read_text(encoding="utf-8")
    assert 'DeclareLaunchArgument("corps_sur_config", default_value="/home/ros2_ws/src/robot/conf/corps_sur.yaml"' in src
    paquet = (DRIVE / "package.xml").read_text(encoding="utf-8")
    assert "<exec_depend>didier_corps_sur</exec_depend>" in paquet


def test_la_sim_passe_sa_configuration():
    entree = (MONO / "machines" / "sim" / "robot" / "entree.sh").read_text(encoding="utf-8")
    assert "corps_sur_config:=/home/ros2_ws/sim/corps_sur.yaml" in entree
    compose = yaml.safe_load((MONO / "machines" / "sim" / "docker-compose.yml").read_text(encoding="utf-8"))
    assert "./robot/corps_sur.yaml:/home/ros2_ws/sim/corps_sur.yaml:ro" in compose["services"]["robot"]["volumes"]
