"""Répétition simulée — cheminement de Didier + relais + régisseur (SIM-ONLY).

    ros2 launch robot_rehearsal rehearsal.launch.py                 # route OFF, scénario demo chargé, en attente de « start »
    ros2 launch robot_rehearsal rehearsal.launch.py speed:=0.3 scenario:=demo seed:=42
    ros2 launch robot_rehearsal rehearsal.launch.py route:=chantiers scenario:=chantiers   # lot R3
    # partir :      ros2 topic pub -1 route robot_interfaces/msg/StringTime '{msg: "on"}'
    # régisseur :   ros2 topic pub -1 rehearsal/cmd robot_interfaces/msg/StringTime '{msg: "start"}'   (stop | abort)

Topologie : route_driver publie `cmd_vel_follow_raw` (remap) -> fault_relay
(passant par défaut) -> `cmd_vel_follow` -> twist_mux prio 20. Le régisseur
(director) ne publie jamais de Twist : il parle aux relais, aux processus de la
liste blanche, à route/route_speed, et journalise.

Prérequis dans le conteneur sim : sim.launch.py world:=rue ET la chaîne roues
(drive.launch.py use_sim_time:=true) — ce launch ne les lance PAS (aucun
mouvement automatique au démarrage). Le suivi de personne doit rester OFF
(même créneau prio 20 du mux).
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    share = FindPackageShare("robot_rehearsal")
    route_file = PathJoinSubstitution([share, "config", [LaunchConfiguration("route"), ".yaml"]])
    scenario_file = PathJoinSubstitution([share, "config", "scenarios",
                                          [LaunchConfiguration("scenario"), ".yaml"]])
    return LaunchDescription([
        DeclareLaunchArgument("route", default_value="rue",
                              description="nom du YAML d'itinéraire dans config/ (sans extension)"),
        DeclareLaunchArgument("speed", default_value="0.5",
                              description="facteur de vitesse initial 0..1 (modifiable à chaud par"
                                          " le topic route_speed — le fader de la télécommande)"),
        DeclareLaunchArgument("enabled", default_value="false",
                              description="SÉCURITÉ : true = part dès le lancement. Défaut false :"
                                          " activation explicite par le topic route (on/off)."),
        DeclareLaunchArgument("scenario", default_value="demo",
                              description="nom du YAML de scénario dans config/scenarios/ (sans extension)"),
        DeclareLaunchArgument("seed", default_value="-1",
                              description="graine du scénario (-1 = celle du fichier) ; même graine = même séance"),
        DeclareLaunchArgument("autostart", default_value="false",
                              description="true = le scénario démarre au lancement. Défaut false :"
                                          " « start » explicite sur rehearsal/cmd."),

        # Cheminement : publie vers l'AMONT du relais. respawn : une panne
        # « kill » le fait renaître après respawn_delay (le reboot-prétexte) ;
        # il renaît OFF, le régisseur renvoie « route on » (reenable).
        Node(
            package="robot_rehearsal", executable="route_driver", name="route_driver", output="screen",
            parameters=[{
                "route_file": route_file,
                "speed": ParameterValue(LaunchConfiguration("speed"), value_type=float),
                "enabled": ParameterValue(LaunchConfiguration("enabled"), value_type=bool),
            }],
            remappings=[("cmd_vel_follow", "cmd_vel_follow_raw")],
            respawn=True, respawn_delay=5.0,
        ),
        # Relais de pannes sur cmd_vel_follow (passant par défaut, chien de garde 1 s).
        Node(
            package="robot_rehearsal", executable="fault_relay", name="fault_relay_cmd_vel_follow",
            output="screen", parameters=[{"relay": "cmd_vel_follow"}],
            respawn=True, respawn_delay=2.0,   # relais mort = mux sans entrée = deadman ; il renaît passant
        ),
        # Régisseur : charge le scénario, attend « start ». Il lit le MÊME
        # itinéraire que route_driver (noms de POI, textes des lubies) : un
        # scénario qui référence un POI absent de `route` est refusé au démarrage.
        # Et la MÊME vitesse initiale : c'est celle qu'il rend à la fin d'un
        # speed / d'une lubie tant qu'aucun fader n'a parlé.
        Node(
            package="robot_rehearsal", executable="director", name="director", output="screen",
            parameters=[{
                "scenario_file": scenario_file,
                "route_file": route_file,
                "speed": ParameterValue(LaunchConfiguration("speed"), value_type=float),
                "seed": ParameterValue(LaunchConfiguration("seed"), value_type=int),
                "autostart": ParameterValue(LaunchConfiguration("autostart"), value_type=bool),
            }],
        ),
    ])
