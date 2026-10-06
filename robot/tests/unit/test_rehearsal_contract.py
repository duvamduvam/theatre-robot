"""Contrats GELÉS de la salle de répétition (robot_rehearsal) — lus dans les
VRAIS fichiers (package, itinéraire, launch de bringup), jamais des copies.

Trois garanties :
 1. plafonds durs IDENTIQUES à ceux du suivi de personne (même créneau du
    mux, mêmes 50 kg) ;
 2. ANTI-FUITE : le package sim-only n'est référencé nulle part dans le code
    embarqué (robot/, robot_bringup, robot_drive, robot_web) ;
 3. l'itinéraire livré (config/rue.yaml) est valide, reste sur le trottoir du
    monde rue.sdf, et ses POI sont exactement ceux attendus.
"""
import pathlib

import yaml

from robot.move.follow_control import ABS_MAX_ANG as FOLLOW_MAX_ANG, ABS_MAX_LIN as FOLLOW_MAX_LIN
from robot_rehearsal import contracts
from robot_rehearsal.route import load_route

ROOT = pathlib.Path(__file__).resolve().parents[3]
PKG = ROOT / "conf" / "ros2_dependencies" / "robot_rehearsal"

# Géométrie du trottoir de rue.sdf (dupliquée depuis la spec du monde, étude
# §12 : trottoir 70 x 3 centré (30, 0) -> x ∈ [-5, 65], y ∈ [-1.5, 1.5]).
TROTTOIR_X = (-5.0, 65.0)
TROTTOIR_Y = (-1.5, 1.5)


def test_plafonds_identiques_au_suivi():
    assert contracts.ABS_MAX_LIN == FOLLOW_MAX_LIN == 0.5
    assert contracts.ABS_MAX_ANG == FOLLOW_MAX_ANG == 1.0


def test_sortie_sur_le_creneau_du_suivi_jamais_cmd_vel_final():
    assert contracts.CMD_VEL_TOPIC == "cmd_vel_follow"
    assert contracts.CMD_VEL_TOPIC != "cmd_vel"
    assert contracts.ODOM_TOPIC == "/ground_truth/odom"


def test_verite_terrain_declaree_dans_le_xacro_et_le_bridge():
    """Le topic de pose consommé par le cheminement doit exister de bout en
    bout : plugin OdometryPublisher dans le xacro gz ET entrée GZ_TO_ROS du
    bridge, avec le MÊME nom que le contrat. Lu dans les vrais fichiers."""
    xacro = (ROOT / "conf" / "ros2_dependencies" / "robot_description" / "urdf"
             / "dadou_robot_gz.urdf.xacro").read_text(encoding="utf-8")
    assert "gz::sim::systems::OdometryPublisher" in xacro
    assert f"<odom_topic>{contracts.ODOM_TOPIC}</odom_topic>" in xacro
    bridge = yaml.safe_load((ROOT / "conf" / "ros2_dependencies" / "robot_sim" / "config"
                             / "gz_bridge.yaml").read_text(encoding="utf-8"))
    entries = [e for e in bridge if e["ros_topic_name"] == contracts.ODOM_TOPIC]
    assert len(entries) == 1
    assert entries[0]["ros_type_name"] == "nav_msgs/msg/Odometry"
    assert entries[0]["direction"] == "GZ_TO_ROS"


def test_anti_fuite_aucune_reference_dans_le_code_embarque():
    zones = [
        ROOT / "robot",
        ROOT / "conf" / "ros2",
        ROOT / "conf" / "ros2_dependencies" / "robot_bringup",
        ROOT / "conf" / "ros2_dependencies" / "robot_drive",
        ROOT / "conf" / "ros2_dependencies" / "robot_web",
    ]
    fuites = []
    for zone in zones:
        for path in zone.rglob("*"):
            if not path.is_file() or path.suffix not in (".py", ".xml", ".yaml", ".yml", ".sh", ".txt", ".cfg"):
                continue
            if "tests" in path.parts:   # les tests ont le droit d'en parler
                continue
            if "robot_rehearsal" in path.read_text(encoding="utf-8", errors="ignore"):
                fuites.append(str(path.relative_to(ROOT)))
    assert fuites == [], f"robot_rehearsal référencé dans le code embarqué : {fuites}"


def test_itineraire_rue_valide_et_sur_le_trottoir():
    with (PKG / "config" / "rue.yaml").open(encoding="utf-8") as f:
        route = load_route(yaml.safe_load(f))
    assert route.name == "hangar-a-bananes"
    assert len(route.waypoints) == 10
    for x, y in route.waypoints:
        assert TROTTOIR_X[0] <= x <= TROTTOIR_X[1]
        assert TROTTOIR_Y[0] <= y <= TROTTOIR_Y[1]
    # Monotone en x : on va vers le hangar, jamais en arrière.
    xs = [x for x, _ in route.waypoints]
    assert xs == sorted(xs)
    assert tuple(p.name for p in route.pois) == (
        "lampadaire_1", "banc", "boulangerie", "lampadaire_2", "chien",
        "poubelle", "terrasse", "lampadaire_3", "hangar_bananes",
    )


def test_launch_off_par_defaut():
    launch = (PKG / "launch" / "rehearsal.launch.py").read_text(encoding="utf-8")
    assert 'DeclareLaunchArgument("enabled", default_value="false"' in launch
