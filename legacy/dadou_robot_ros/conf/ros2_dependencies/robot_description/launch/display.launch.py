"""Affiche le robot dans RViz avec des sliders pour bouger cou, bras et yeux.

Usage (dans le conteneur x86 avec DISPLAY) :
    ros2 launch robot_description display.launch.py
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch.substitutions import Command


def generate_launch_description():
    urdf_path = os.path.join(
        get_package_share_directory("robot_description"), "urdf", "dadou_robot.urdf.xacro")

    robot_description = ParameterValue(Command(["xacro ", urdf_path]), value_type=str)

    return LaunchDescription([
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
    ])
