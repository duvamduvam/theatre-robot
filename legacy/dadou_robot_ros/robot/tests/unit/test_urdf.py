"""Validation structurelle de l'URDF (généré depuis le xacro).

Garantit que le modèle reste chargeable (RViz/Gazebo) et que les joints
portent les noms attendus par le code robot (neck, left_arm, ...).
"""

import os
import xml.etree.ElementTree as ET

import pytest
import xacro

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
XACRO_PATH = os.path.join(REPO_ROOT, "conf", "ros2_dependencies", "robot_description",
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

GZ_XACRO_PATH = os.path.join(REPO_ROOT, "conf", "ros2_dependencies", "robot_description",
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
