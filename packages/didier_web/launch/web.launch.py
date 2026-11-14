"""Pont web du robot (W0) : supervision + contenus + panneau technique.

    ros2 launch didier_web web.launch.py
    ros2 launch didier_web web.launch.py web_port:=8765 token:=secret

Pas de use_sim_time ici : les timeouts de session (heartbeat WRITE_TIMEOUT_S)
sont mesurés en horloge MURALE (time.monotonic(), voir web_protocol.py), pas
en horloge simulée -- un opérateur humain de l'autre côté du WebSocket vit en
temps réel, que le Gazebo tourne à 1x, en pause ou accéléré n'y change rien.
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node, PushRosNamespace
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    # ParameterValue(value_type=...) obligatoire : une LaunchConfiguration est
    # une chaîne, or le node déclare web_port en int et drive_enabled en bool
    # ("false"/"true" -> False/True via la coercition launch).
    web_port = ParameterValue(LaunchConfiguration("web_port"), value_type=int)
    drive_enabled = ParameterValue(LaunchConfiguration("drive_enabled"), value_type=bool)
    max_linear = ParameterValue(LaunchConfiguration("max_linear"), value_type=float)
    max_angular = ParameterValue(LaunchConfiguration("max_angular"), value_type=float)
    rehearsal_enabled = ParameterValue(LaunchConfiguration("rehearsal_enabled"), value_type=bool)
    data_edit_enabled = ParameterValue(LaunchConfiguration("data_edit_enabled"), value_type=bool)

    return LaunchDescription([
        DeclareLaunchArgument("web_port", default_value="8765",
                              description="Port HTTP/WebSocket du pont web (8088 évité : défaut"
                                           " Superset, collision vue sur le PC de dev)"),
        DeclareLaunchArgument("token", default_value="",
                              description="Token d'auth ; vide = accès libre (dev/sim)"),
        DeclareLaunchArgument("json_dir", default_value="/home/ros2_ws/json",
                              description="Dossier json/ (catalogue faces/audios/animations/relais/lights)"),
        # SÉCURITÉ : pilotage roues. Défauts SÛRS : désactivé, plafonds prudents.
        DeclareLaunchArgument("drive_enabled", default_value="false",
                              description="SÉCURITÉ : true = pilotage roues actif (publisher"
                                           " cmd_vel_web). Défaut false -- rien ne bouge sans."),
        DeclareLaunchArgument("max_linear", default_value="0.5",
                              description="Plafond DUR vitesse linéaire (m/s) appliqué serveur"),
        DeclareLaunchArgument("max_angular", default_value="1.0",
                              description="Plafond DUR vitesse angulaire (rad/s) appliqué serveur"),
        # SÉCURITÉ (SIM-ONLY) : boutons de répétition de la page /scene (route,
        # vitesse, séance). Défaut false ; même true, le node les ignore hors du
        # domaine ROS 43 (simulation) -- le vrai robot (42) ne les a jamais.
        DeclareLaunchArgument("rehearsal_enabled", default_value="false",
                              description="SÉCURITÉ (SIM-ONLY) : true = le pont accepte les topics de"
                                           " répétition (route, route_speed, rehearsal/cmd) pour la"
                                           " page /scene. Ignoré hors domaine 43. Défaut false."),
        # Lot L1d-3 : le pont relaie les retouches de la page scène vers data_edit_node.
        # Défaut false = aucun publisher data_edit, éditeur absent de la page.
        DeclareLaunchArgument("data_edit_enabled", default_value="false",
                              description="true = le pont relaie les retouches de données (type"
                                           " WebSocket data_edit) vers data_edit_node ; même valeur"
                                           " que son `enabled` (drapeau DATA_EDIT). Défaut false."),
        DeclareLaunchArgument("data_dir", default_value="/home/ros2_ws/src/robot",
                              description="Racine des données (json/ + medias/) lue par GET /api/data"),
        DeclareLaunchArgument("camera_topic", default_value="camera/image_raw",
                              description="Topic sensor_msgs/Image de la caméra embarquée (retour vidéo)"),
        DeclareLaunchArgument("camera_compressed", default_value="false",
                              description="true = camera_topic porte du CompressedImage JPEG"
                                           " (vrai robot : flux du Pi vision), servi tel quel ;"
                                           " false = Image brut à encoder (sim : caméra gz)"),
        DeclareLaunchArgument("perception_topic", default_value="",
                              description="Topic sensor_msgs/CompressedImage de ce que voit la perception"
                                           " (ex. camera/image_raw/compressed), servi en LECTURE SEULE"
                                           " sur /perception. Vide (défaut) = désactivé, aucun abonnement."),

        DeclareLaunchArgument("exterior_topic", default_value="",
                              description="Topic sensor_msgs/Image de la caméra de poursuite (sim :"
                                           " camera_ext/image_raw), servi en LECTURE SEULE sur"
                                           " /exterior. Vide (défaut) = désactivé, aucun abonnement."),

        DeclareLaunchArgument("robot_name",
                              default_value=EnvironmentVariable("ROBOT_NAME", default_value="didier"),
                              description="Nom du robot = namespace ABSOLU de tous les nœuds"
                                          " (défaut : variable ROBOT_NAME, sinon didier)"),

        # Lot L1b : UN groupe, UN PushRosNamespace absolu (/didier/... par défaut),
        # jamais de namespace= par nœud (on l'oublierait au prochain).
        GroupAction([
            PushRosNamespace(["/", LaunchConfiguration("robot_name")]),

            Node(
                package="didier_web",
                executable="web_bridge",
                name="web_bridge_node",
                parameters=[{
                    "web_port": web_port,
                    "token": LaunchConfiguration("token"),
                    "json_dir": LaunchConfiguration("json_dir"),
                    "drive_enabled": drive_enabled,
                    "max_linear": max_linear,
                    "max_angular": max_angular,
                    "rehearsal_enabled": rehearsal_enabled,
                    "data_edit_enabled": data_edit_enabled,
                    "data_dir": LaunchConfiguration("data_dir"),
                    "perception_topic": LaunchConfiguration("perception_topic"),
                    "exterior_topic": LaunchConfiguration("exterior_topic"),
                    "camera_topic": LaunchConfiguration("camera_topic"),
                    "camera_compressed": ParameterValue(
                        LaunchConfiguration("camera_compressed"), value_type=bool),
                }],
            ),
        ]),
    ])
