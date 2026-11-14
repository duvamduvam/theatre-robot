"""Le MONDE de la sim multi-conteneurs (spec L2, décision 18) — remplace sim.launch.py.

Conteneur `monde` (machines/sim/docker-compose.yml) : tout ce qui n'est pas une machine de Didier.
Lance : serveur gz (+ GUI si headless:=false), spawn du robot depuis robot_description,
robot_state_publisher, le pont ros_gz et le MATÉRIEL SIMULÉ (servos_sim_node, leds_sim_node),
abonné aux mêmes topics de commande que les nœuds matériels du vrai robot.

    ros2 launch didier_sim monde.launch.py                       # avec GUI
    ros2 launch didier_sim monde.launch.py headless:=true world:=chantiers

Le robot lui-même (robot_app.launch.py, animations_node, catalogue, data_edit, web_bridge, chaîne
roues) tourne dans le conteneur `robot`, avec le Dockerfile du Pi : AUCUN exécutable de
didier_core, didier_drive ou didier_web n'est lancé ici (gravé par test_compose_sim.py).

Première action : REFUS si ROS_DOMAIN_ID ≠ 43. Tout tourne en use_sim_time (horloge /clock
bridgée depuis gz). Namespace (lot L1b) : tout vit sous /<ROBOT_NAME>/ ; la CLI ne suit PAS
(préfixer /didier/… dans `ros2 topic pub`).
"""
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (Command, EnvironmentVariable, LaunchConfiguration, PathJoinSubstitution,
                                  PythonExpression)
from launch_ros.actions import Node, PushRosNamespace
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

DOMAINE_SIM = "43"
# base_link est au centre de la caisse : rayon roue (0.13) + demi-hauteur
# de caisse (0.10), plus 1 cm de marge pour poser le robot sans le coincer.
SPAWN_Z = "0.24"


def generate_launch_description():
    # Garde 43 AVANT toute action (même règle que machines/sim/monde/entree.sh).
    domaine = os.environ.get("ROS_DOMAIN_ID", "").strip()
    if domaine != DOMAINE_SIM:
        raise RuntimeError("monde.launch.py : ROS_DOMAIN_ID=%r, refusé (simulation = 43 seulement)" % domaine)

    headless = LaunchConfiguration("headless")

    # ⚠️ `robot_description` (variable, paramètre de robot_state_publisher, topic du
    # spawn) = nom STANDARD ROS de l'URDF, PAS le package (didier_description depuis
    # L1e-2) : ne jamais le renommer — le robot disparaîtrait de la sim sans erreur claire.
    robot_description = ParameterValue(
        Command([
            "xacro ",
            PathJoinSubstitution([
                FindPackageShare("didier_description"), "urdf", "dadou_robot_gz.urdf.xacro",
            ]),
        ]),
        value_type=str,
    )

    # Dossier des mondes ; le nom de fichier est assemblé ci-dessous. On concatène
    # dans la LISTE gz_args (le launch concatène les substitutions d'une liste)
    # plutôt que d'imbriquer une sous-liste dans PathJoinSubstitution, dont le
    # support des éléments composites n'est pas garanti en Jazzy.
    worlds_dir = PathJoinSubstitution([FindPackageShare("didier_sim"), "worlds"])

    # -r : la simulation démarre en lecture (pas en pause) ; -s : serveur seul.
    # Seul le FICHIER change avec `world` : le nom interne du monde reste `stage`
    # dans stage.sdf ET rue.sdf (contrat : bridge et leds_sim_node ciblent
    # /world/stage/material_color).
    gz_args = [
        worlds_dir, "/", LaunchConfiguration("world"), ".sdf", " -r",
        PythonExpression(["' -s' if '", headless, "' == 'true' else ''"]),
    ]

    return LaunchDescription([
        DeclareLaunchArgument("world", default_value="stage",
                              description="Monde gz : nom du fichier SANS extension dans worlds/"
                                           " (stage = scène de théâtre, rue = rue de la répétition, chantiers = Nefs → Titan grise"
                                           " simulée). Le nom interne du monde reste `stage`."),
        DeclareLaunchArgument("headless", default_value="false",
                              description="true = serveur gz seul, sans GUI"),
        DeclareLaunchArgument("robot_name",
                              default_value=EnvironmentVariable("ROBOT_NAME", default_value="didier"),
                              description="Nom du robot = namespace ABSOLU de tous les nœuds"
                                          " (défaut : variable ROBOT_NAME, sinon didier)"),

        # Lot L1b : UN groupe, UN PushRosNamespace absolu (/didier/... par défaut),
        # jamais de namespace= par nœud. Le bridge (gz_bridge.yaml : noms ROS
        # relatifs sauf /clock et /tf), robot_state_publisher (robot_description,
        # joint_states) et le spawn (-topic robot_description) sont DANS le groupe :
        # ils se suivent. Les noms côté gz ne changent pas (le monde ignore ROS).
        GroupAction([
            PushRosNamespace(["/", LaunchConfiguration("robot_name")]),

            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([FindPackageShare("ros_gz_sim"), "launch", "gz_sim.launch.py"])
                ),
                launch_arguments={"gz_args": gz_args}.items(),
            ),

            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                parameters=[{"robot_description": robot_description, "use_sim_time": True}],
            ),

            Node(
                package="ros_gz_sim",
                executable="create",
                arguments=["-topic", "robot_description", "-name", "dadou_robot", "-z", SPAWN_Z],
                output="screen",
            ),

            Node(
                package="ros_gz_bridge",
                executable="parameter_bridge",
                parameters=[{
                    "config_file": PathJoinSubstitution([
                        FindPackageShare("didier_sim"), "config", "gz_bridge.yaml",
                    ]),
                    "use_sim_time": True,
                }],
                output="screen",
            ),

            # Matériel simulé — LED (matériaux émissifs gz, cf. didier_sim_lib/leds_logic.py) :
            # écoute robot_lights/face côté ROS, publie material_color (relatif, bridgé vers
            # /world/stage/material_color, système gz UserCommands du monde `stage`).
            Node(
                package="didier_sim",
                executable="leds_sim_node",
                parameters=[{"use_sim_time": True}],
                output="screen",
            ),

            # Matériel simulé — servos (neck/left_arm/right_arm/left_eye/right_eye, cf.
            # didier_sim_lib/servos_logic.py) : écoute les 5 topics StringTime que les
            # servo_node du robot (inertes hors Pi) écoutent aussi, publie <servo>/position
            # (relatif, radians) sur les JointPositionController gz.
            Node(
                package="didier_sim",
                executable="servos_sim_node",
                parameters=[{"use_sim_time": True}],
                output="screen",
            ),
        ]),
    ])
