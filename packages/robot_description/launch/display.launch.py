"""Affiche le robot dans RViz avec des sliders pour bouger cou, bras et yeux.

Usage (dans le conteneur x86 avec DISPLAY) :
    ros2 launch robot_description display.launch.py
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch_ros.actions import Node, PushRosNamespace
from launch_ros.parameter_descriptions import ParameterValue
from launch.substitutions import Command, EnvironmentVariable, LaunchConfiguration


def generate_launch_description():
    urdf_path = os.path.join(
        get_package_share_directory("robot_description"), "urdf", "dadou_robot.urdf.xacro")

    robot_description = ParameterValue(Command(["xacro ", urdf_path]), value_type=str)

    return LaunchDescription([
        DeclareLaunchArgument("robot_name",
                              default_value=EnvironmentVariable("ROBOT_NAME", default_value="didier"),
                              description="Nom du robot = namespace ABSOLU de tous les nœuds"
                                          " (défaut : variable ROBOT_NAME, sinon didier)"),

        # Lot L1b : UN groupe, UN PushRosNamespace absolu (/didier/... par défaut),
        # jamais de namespace= par nœud. robot_description et joint_states suivent
        # le namespace ; /tf reste global (TransformBroadcaster).
        GroupAction([
            PushRosNamespace(["/", LaunchConfiguration("robot_name")]),

            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                parameters=[{"robot_description": robot_description}],
            ),
            Node(
                package="joint_state_publisher_gui",
                executable="joint_state_publisher_gui",
            ),
            Node(
                package="rviz2",
                executable="rviz2",
            ),
        ]),
    ])
