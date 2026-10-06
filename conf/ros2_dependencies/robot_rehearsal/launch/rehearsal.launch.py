"""Répétition simulée — lance le cheminement de Didier (SIM-ONLY).

    ros2 launch robot_rehearsal rehearsal.launch.py                 # itinéraire rue.yaml, OFF
    ros2 launch robot_rehearsal rehearsal.launch.py speed:=0.3
    # puis, pour partir :  ros2 topic pub -1 route robot_interfaces/msg/StringTime '{msg: "on"}'

Prérequis dans le conteneur sim : sim.launch.py world:=rue ET la chaîne
roues (drive.launch.py use_sim_time:=true) — ce launch ne les lance PAS
(prudence habituelle : aucun mouvement automatique au démarrage). Le suivi
de personne doit rester OFF (même créneau prio 20 du mux).
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    route_file = PathJoinSubstitution([
        FindPackageShare("robot_rehearsal"), "config", [LaunchConfiguration("route"), ".yaml"],
    ])
    return LaunchDescription([
        DeclareLaunchArgument("route", default_value="rue",
                              description="nom du YAML d'itinéraire dans config/ (sans extension)"),
        DeclareLaunchArgument("speed", default_value="0.5",
                              description="facteur de vitesse initial 0..1 (modifiable à chaud par"
                                          " le topic route_speed — le fader de la télécommande)"),
        DeclareLaunchArgument("enabled", default_value="false",
                              description="SÉCURITÉ : true = part dès le lancement. Défaut false :"
                                          " activation explicite par le topic route (on/off)."),
        Node(
            package="robot_rehearsal",
            executable="route_driver",
            name="route_driver",
            output="screen",
            parameters=[{
                "route_file": route_file,
                "speed": ParameterValue(LaunchConfiguration("speed"), value_type=float),
                "enabled": ParameterValue(LaunchConfiguration("enabled"), value_type=bool),
            }],
        ),
    ])
