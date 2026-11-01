"""Chaîne de commande roues complète : twist_mux -> twist_deadman -> cmd_vel.

    ros2 launch robot_drive drive.launch.py
    ros2 launch robot_drive drive.launch.py use_sim_time:=true

twist_mux arbitre cmd_vel_remote (télécommande, priorité haute) et cmd_vel_anim
(animations, priorité basse) sur cmd_vel_mux ; twist_deadman est le dernier
filet de sécurité avant cmd_vel (coupe si plus rien n'arrive) ; wheels_bridge
traduit le topic roues legacy (StringTime) vers cmd_vel_remote/cmd_vel_anim.
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    use_sim_time = LaunchConfiguration("use_sim_time")

    twist_mux_config = PathJoinSubstitution([
        FindPackageShare("robot_drive"), "config", "twist_mux.yaml",
    ])

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="false",
                              description="true en simulation Gazebo (horloge /clock)"),

        Node(
            package="twist_mux",
            executable="twist_mux",
            name="twist_mux",
            parameters=[twist_mux_config, {"use_sim_time": use_sim_time}],
            remappings=[("cmd_vel_out", "cmd_vel_mux")],
        ),

        Node(
            package="robot_drive",
            executable="twist_deadman",
            name="twist_deadman",
            parameters=[{"use_sim_time": use_sim_time}],
        ),

        Node(
            package="robot_drive",
            executable="wheels_bridge",
            name="wheels_bridge",
            parameters=[{"use_sim_time": use_sim_time}],
        ),
    ])
