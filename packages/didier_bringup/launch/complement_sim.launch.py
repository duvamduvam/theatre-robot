"""Complément SIM du conteneur robot (spec L2, décision 17) — jamais lancé sur un Pi.

Le conteneur `robot` de la sim multi-conteneurs (machines/sim/docker-compose.yml) lance le VRAI
bringup (robot_app.launch.py) ET ce fichier, à côté, dans le même conteneur
(machines/sim/robot/entree.sh). Il ne porte que ce qui n'existe qu'en simulation :

  - face_sim (didier_core) : aperçu web du visage LED, les matrices n'ont aucun rendu dans
    Gazebo — si face:=true, http://localhost:<face_port> ;
  - validation_sim_node (didier_web, L1d-2) : l'observateur qui tamponne le registre des
    validations (json/validations-sim.json) ; il refuse lui-même de démarrer hors domaine 43.

    ros2 launch didier_bringup complement_sim.launch.py face:=true face_port:=8766

Première action : REFUS si ROS_DOMAIN_ID ≠ 43 (aucun nœud n'est créé). Aucun machine.yml ne
le cite (gravé par test_robot_app_sim.py).
"""
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.conditions import IfCondition
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node, PushRosNamespace
from launch_ros.parameter_descriptions import ParameterValue

DOMAINE_SIM = "43"


def generate_launch_description():
    # Garde 43 AVANT toute action : ce fichier part sur le Pi (didier_bringup), il ne doit
    # jamais y démarrer quoi que ce soit, même lancé à la main par erreur.
    domaine = os.environ.get("ROS_DOMAIN_ID", "").strip()
    if domaine != DOMAINE_SIM:
        raise RuntimeError("complement_sim.launch.py : ROS_DOMAIN_ID=%r, refusé (simulation = 43 seulement)"
                           % domaine)

    return LaunchDescription([
        DeclareLaunchArgument("face", default_value="false",
                              description="true = lance face_sim (aperçu web du visage LED)"),
        DeclareLaunchArgument("face_port", default_value="8766",
                              description="Port HTTP du flux MJPEG de l'aperçu visage"),
        DeclareLaunchArgument("robot_name",
                              default_value=EnvironmentVariable("ROBOT_NAME", default_value="didier"),
                              description="Nom du robot = namespace ABSOLU de tous les nœuds"
                                          " (défaut : variable ROBOT_NAME, sinon didier)"),
        GroupAction([
            PushRosNamespace(["/", LaunchConfiguration("robot_name")]),
            Node(
                package="didier_core",
                executable="face_sim",
                output="screen",
                # ParameterValue(int) : une LaunchConfiguration est une chaîne.
                parameters=[{"face_port": ParameterValue(LaunchConfiguration("face_port"), value_type=int)}],
                condition=IfCondition(LaunchConfiguration("face")),
            ),
            # data_dir par défaut (/home/ros2_ws/src/robot) = le montage de data/ du conteneur robot.
            Node(
                package="didier_web",
                executable="validation_sim",
                name="validation_sim_node",
                output="screen",
            ),
        ]),
    ])
