"""Validation structurelle de l'URDF (généré depuis le xacro).

Garantit que le modèle reste chargeable (RViz/Gazebo) et que les joints
portent les noms attendus par le code robot (neck, left_arm, ...).
"""

import os
import xml.etree.ElementTree as ET

import pytest
import xacro

# legacy/dadou_robot_ros (ancien dépôt du robot) ; le test vit dans packages/didier_core/test/unit (L1e-3c).
REPO_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))), "legacy", "dadou_robot_ros")
# packages/ du mono-dépôt (L1e-1) : didier_description y a déménagé de conf/ du robot.
PACKAGES_DIR = os.path.join(REPO_ROOT, "..", "..", "packages")
XACRO_PATH = os.path.join(PACKAGES_DIR, "didier_description",
                          "urdf", "dadou_robot.urdf.xacro")

SERVO_JOINTS = {"neck", "left_arm", "right_arm", "left_eye", "right_eye"}
WHEEL_JOINTS = {"wheel_left_joint", "wheel_right_joint"}


@pytest.fixture(scope="module")
def urdf():
    return ET.fromstring(xacro.process_file(XACRO_PATH).toxml())


def test_xacro_generates_valid_urdf(urdf):
    assert urdf.tag == "robot"
    assert urdf.get("name") == "dadou_robot"


def test_joints_reference_existing_links(urdf):
    links = {l.get("name") for l in urdf.findall("link")}
    for joint in urdf.findall("joint"):
        parent = joint.find("parent").get("link")
        child = joint.find("child").get("link")
        assert parent in links, "joint {} : parent {} inconnu".format(joint.get("name"), parent)
        assert child in links, "joint {} : child {} inconnu".format(joint.get("name"), child)


def test_tree_has_single_root(urdf):
    links = {l.get("name") for l in urdf.findall("link")}
    children = {j.find("child").get("link") for j in urdf.findall("joint")}
    roots = links - children
    assert roots == {"base_link"}, "racines de l'arbre : {}".format(roots)


def test_servo_joints_exist_with_limits(urdf):
    joints = {j.get("name"): j for j in urdf.findall("joint")}
    assert SERVO_JOINTS <= set(joints), "joints servo manquants : {}".format(SERVO_JOINTS - set(joints))
    for name in SERVO_JOINTS:
        joint = joints[name]
        assert joint.get("type") == "revolute"
        limit = joint.find("limit")
        assert limit is not None and float(limit.get("lower")) < float(limit.get("upper"))


def test_wheel_joints_are_continuous(urdf):
    joints = {j.get("name"): j for j in urdf.findall("joint")}
    for name in WHEEL_JOINTS:
        assert joints[name].get("type") == "continuous"


def test_links_have_positive_mass(urdf):
    for link in urdf.findall("link"):
        inertial = link.find("inertial")
        if inertial is not None:
            assert float(inertial.find("mass").get("value")) > 0, link.get("name")


# ======== Extension Gazebo (dadou_robot_gz.urdf.xacro) ========

GZ_XACRO_PATH = os.path.join(PACKAGES_DIR, "didier_description",
                             "urdf", "dadou_robot_gz.urdf.xacro")


@pytest.fixture(scope="module")
def gz_urdf():
    return ET.fromstring(xacro.process_file(GZ_XACRO_PATH).toxml())


def _gz_plugins(gz_urdf):
    return [p for g in gz_urdf.findall("gazebo") for p in g.findall("plugin")]


def test_gz_xacro_includes_full_robot(gz_urdf):
    """L'include relatif ramène bien tout le modèle nominal."""
    links = {l.get("name") for l in gz_urdf.findall("link")}
    assert {"base_link", "torso_link", "head_link"} <= links


def test_gz_diff_drive_matches_wheel_joints(gz_urdf):
    """Le plugin DiffDrive référence les vrais joints de roues."""
    plugins = {p.get("name"): p for p in _gz_plugins(gz_urdf)}
    dd = plugins.get("gz::sim::systems::DiffDrive")
    assert dd is not None, "plugin DiffDrive absent"
    joints = {j.get("name") for j in gz_urdf.findall("joint")}
    assert dd.find("left_joint").text in joints
    assert dd.find("right_joint").text in joints
    # Géométrie cohérente avec le modèle (propriétés xacro partagées)
    assert float(dd.find("wheel_separation").text) == pytest.approx(0.58)
    assert float(dd.find("wheel_radius").text) == pytest.approx(0.13)


def test_gz_one_position_controller_per_servo(gz_urdf):
    """Chaque servo du code a son contrôleur gz, topic /<servo>/position."""
    controllers = {
        p.find("joint_name").text: p
        for p in _gz_plugins(gz_urdf)
        if p.get("name") == "gz::sim::systems::JointPositionController"
    }
    assert set(controllers) == SERVO_JOINTS
    for name, plugin in controllers.items():
        assert plugin.find("topic").text == "/{}/position".format(name)


# ======== Lidar simulé (spec A0 §8.1) : caractéristiques du RPLIDAR C1, GRAVÉES ========

def _capteur_lidar(gz_urdf):
    capteurs = [s for g in gz_urdf.findall("gazebo") for s in g.findall("sensor")
                if s.get("type") == "gpu_lidar"]
    assert len(capteurs) == 1
    return capteurs[0]


def test_gz_lidar_pose_par_defaut_face_avant_plan_a_25_cm(gz_urdf):
    """Défauts xacro = pose A de la spec (face avant, plan à 0,25 m : sol à z = −0,23)."""
    joint = next(j for j in gz_urdf.findall("joint") if j.get("name") == "laser_joint")
    assert joint.find("parent").get("link") == "base_link"
    assert joint.find("child").get("link") == "laser_frame"
    xyz = [float(v) for v in joint.find("origin").get("xyz").split()]
    rpy = [float(v) for v in joint.find("origin").get("rpy").split()]
    assert xyz == [0.33, 0.0, 0.02]
    assert rpy == [0.0, 0.0, 0.0]
    lien = next(l for l in gz_urdf.findall("link") if l.get("name") == "laser_frame")
    assert lien.find("collision") is None          # sans collision (spec §8.1)


def test_gz_lidar_pose_en_arguments():
    doc = ET.fromstring(xacro.process_file(
        GZ_XACRO_PATH, mappings={"lidar_x": "0.27", "lidar_z": "0.22", "lidar_lacet": "3.14159"}).toxml())
    joint = next(j for j in doc.findall("joint") if j.get("name") == "laser_joint")
    assert joint.find("origin").get("xyz") == "0.27 0.0 0.22"
    assert joint.find("origin").get("rpy") == "0 0 3.14159"


def test_gz_lidar_caracteristiques_c1(gz_urdf):
    s = _capteur_lidar(gz_urdf)
    assert s.findtext("topic") == "scan"
    assert s.findtext("gz_frame_id") == "laser_frame"
    assert float(s.findtext("update_rate")) == 10.0          # ne se baisse pas (porte des 200 ms)
    h = s.find("lidar/scan/horizontal")
    assert int(h.findtext("samples")) == 500
    assert float(h.findtext("min_angle")) == -3.14159265
    assert float(h.findtext("max_angle")) == 3.12902628     # −π + 499 × 2π/500 : pas de 0,72°
    assert int(s.findtext("lidar/scan/vertical/samples")) == 1
    assert float(s.findtext("lidar/range/min")) == 0.05
    assert float(s.findtext("lidar/range/max")) == 12.0
    assert float(s.findtext("lidar/range/resolution")) == 0.015
    assert s.findtext("lidar/noise/type") == "gaussian"
    assert float(s.findtext("lidar/noise/stddev")) == 0.01


def test_gz_lidar_pose_egale_a_celle_du_corps_sur_de_la_sim(gz_urdf):
    """Spec A0 §8.1 : les défauts du xacro gz et la pose lue par le corps sûr de la sim
    (machines/sim/robot/corps_sur.yaml) sont les mêmes — sinon le filtre placerait les points
    ailleurs que là où le lidar simulé les voit."""
    import yaml
    conf = os.path.join(PACKAGES_DIR, "..", "machines", "sim", "robot", "corps_sur.yaml")
    with open(conf, encoding="utf-8") as f:
        lidar = yaml.safe_load(f)["lidar"]
    joint = next(j for j in gz_urdf.findall("joint") if j.get("name") == "laser_joint")
    x, y, z = (float(v) for v in joint.find("origin").get("xyz").split())
    lacet = float(joint.find("origin").get("rpy").split()[2])
    assert (lidar["x"], lidar["y"], lidar["lacet_rad"]) == (x, y, lacet) == (0.33, 0.0, 0.0)
    # Plan de balayage : z du lidar + 0,23 (base_link au-dessus du sol) = 0,25 m.
    assert lidar["hauteur_plan_m"] == round(z + 0.23, 2) == 0.25
