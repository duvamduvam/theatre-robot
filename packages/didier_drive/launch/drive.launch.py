"""Chaîne de commande roues complète : twist_mux -> twist_deadman -> cmd_vel.

    ros2 launch didier_drive drive.launch.py
    ros2 launch didier_drive drive.launch.py use_sim_time:=true

twist_mux arbitre cmd_vel_remote (télécommande, priorité haute) et les trois
entrées autonomes filtrées par le CORPS SÛR (corps_sur, lot A0-4 : cmd_vel_web,
cmd_vel_follow, cmd_vel_anim -> cmd_vel_*_sur) sur cmd_vel_mux ; twist_deadman est
le dernier filet de sécurité avant cmd_vel (coupe si plus rien n'arrive) ;
wheels_bridge traduit le topic roues legacy (StringTime) vers
cmd_vel_remote/cmd_vel_anim.

Corps sûr (spec docs/spec-A0-corps-sur.md §3.1, §5.6) : lancé SANS relance
automatique (respawn faux : un redémarrage repasserait par DEMARRAGE et effacerait
un verrou ; mort, il ne publie plus rien et les roues autonomes s'arrêtent).
Sa configuration : argument corps_sur_config (défaut = la conf de la machine,
machines/robot/corps_sur.yaml copiée dans src/robot/conf/ ; la sim passe la sienne
par machines/sim/robot/entree.sh). Configuration absente ou refusée : le nœud
s'arrête, aucune source autonome ne fait tourner les roues.

Namespace (lot L1b) : tous les nœuds vivent sous /<ROBOT_NAME>/ (défaut
/didier/), donc /didier/cmd_vel, /didier/wheels, /didier/e_stop… Le namespace
est poussé en ABSOLU : inclus par robot_app.launch.py OU lancé seul (sim), le
résultat est le même (launch_ros ignore le namespace parent quand le poussé
commence par « / »). ⚠️ Aucun nom de topic n'a changé dans le code de la
chaîne : c'est le namespace qui les déplace — toute bascule sur le vrai robot
repasse par le protocole caméra (conf/scripts/validate-cmdvel-protocol.sh).
"""
import os

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node, PushRosNamespace


def _twist_mux_parameters():
    """Le contenu de config/twist_mux.yaml (fichier INCHANGÉ, seule source des
    entrées, priorités et du verrou e_stop), passé en DICTIONNAIRE.

    PIÈGE (mesuré le 04/11 dans l'image sim Jazzy) : passé en --params-file, ce
    YAML ne s'applique PLUS dès que le nœud est namespacé — sa clé racine
    `twist_mux:` désigne /twist_mux, pas /didier/twist_mux ; le mux démarre
    alors SANS entrées NI verrou e_stop (« Parameter not set »). Un dictionnaire,
    lui, est réécrit par launch_ros sous le nom complet du nœud : les mêmes
    paramètres, mêmes types, quel que soit le namespace (vérifié par
    `ros2 param get /didier2/twist_mux …` et gravé par test_namespace_contract)."""
    path = os.path.join(get_package_share_directory("didier_drive"), "config", "twist_mux.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["twist_mux"]["ros__parameters"]


def generate_launch_description():
    use_sim_time = LaunchConfiguration("use_sim_time")

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="false",
                              description="true en simulation Gazebo (horloge /clock)"),
        DeclareLaunchArgument("robot_name",
                              default_value=EnvironmentVariable("ROBOT_NAME", default_value="didier"),
                              description="Nom du robot = namespace ABSOLU de la chaîne (défaut :"
                                          " variable ROBOT_NAME, sinon didier)"),
        DeclareLaunchArgument("corps_sur_config", default_value="/home/ros2_ws/src/robot/conf/corps_sur.yaml",
                              description="YAML du corps sûr (défaut : la conf de la machine ; la sim"
                                          " passe /home/ros2_ws/sim/corps_sur.yaml)"),

        # Un seul PushRosNamespace pour tout le groupe, jamais de namespace= par
        # nœud (on l'oublierait au prochain).
        GroupAction([
            PushRosNamespace(["/", LaunchConfiguration("robot_name")]),

            Node(
                package="twist_mux",
                executable="twist_mux",
                name="twist_mux",
                parameters=[_twist_mux_parameters(), {"use_sim_time": use_sim_time}],
                # /diagnostics : diagnostic_updater de twist_mux le publie en ABSOLU ;
                # ramené sous le namespace (personne ne l'écoute, cf. L1b : seuls
                # /clock, /tf, /tf_static, /rosout, /parameter_events restent globaux).
                remappings=[("cmd_vel_out", "cmd_vel_mux"), ("/diagnostics", "diagnostics")],
            ),

            # Corps sûr (lot A0-4) : filtre EN LIGNE des trois entrées autonomes, devant le mux.
            Node(
                package="didier_corps_sur",
                executable="corps_sur_node",
                name="corps_sur",
                parameters=[{"use_sim_time": use_sim_time, "config": LaunchConfiguration("corps_sur_config")}],
                respawn=False,
                output="screen",
            ),

            Node(
                package="didier_drive",
                executable="twist_deadman",
                name="twist_deadman",
                parameters=[{"use_sim_time": use_sim_time}],
            ),

            Node(
                package="didier_drive",
                executable="wheels_bridge",
                name="wheels_bridge",
                parameters=[{"use_sim_time": use_sim_time}],
            ),
        ]),
    ])
