"""Répétition simulée — cheminement de Didier + relais + régisseur (SIM-ONLY).

    ros2 launch robot_rehearsal rehearsal.launch.py                 # route OFF, scénario demo chargé, en attente de « start »
    ros2 launch robot_rehearsal rehearsal.launch.py speed:=0.3 scenario:=demo seed:=42
    ros2 launch robot_rehearsal rehearsal.launch.py route:=chantiers scenario:=chantiers   # lot R3
    ros2 launch robot_rehearsal rehearsal.launch.py route:=chantiers scenario:=jeu-a1 jeu:=true   # lot A1
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

jeu:=true (lot A1, spec theatre-robot/docs/spec-A1-selecteur-de-jeu.md §1) :
UN SEUL DÉCIDEUR DU CORPS. Le régisseur écoute alors `jeu/chat_move` (le
sélecteur didier_jeu, lancé à part : ros2 run didier_jeu jeu_node) au lieu de
`rehearsal/chat_move` (la bouche, dont les demandes deviennent des intentions
que le sélecteur pondère ; son « stop » est relayé sans arbitrage), et CE
launch démarre lui-même le sélecteur (respawn) : jamais de remap sans relais.
director ne change pas. Défaut false = séance Chantiers inchangée.
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
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
        DeclareLaunchArgument("jeu", default_value="false",
                              description="true = lot A1 : le régisseur écoute jeu/chat_move (le"
                                          " sélecteur didier_jeu) au lieu de rehearsal/chat_move (la"
                                          " bouche). Défaut false : séance inchangée."),

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
        _director(scenario_file, route_file, UnlessCondition(LaunchConfiguration("jeu")), []),
        # Littéraux = robot_rehearsal.contracts.CHAT_MOVE_TOPIC et
        # theatre_contrats.topics.JEU_CHAT_MOVE (le launch n'importe pas le
        # package ; égalité gravée par test_rehearsal_contract.py).
        _director(scenario_file, route_file, IfCondition(LaunchConfiguration("jeu")),
                  [("rehearsal/chat_move", "jeu/chat_move")]),
        # Le sélecteur de jeu (packages/didier_jeu) — lancé ICI, sous la MÊME
        # condition que le remap (revue A1, bloquant 2) : le régisseur n'écoute
        # plus la bouche que si celui qui relaie son « stop » tourne. respawn
        # comme route_driver ; répertoire illisible -> il démarre quand même en
        # relais stop/go seul. Pas d'exec_depend didier_jeu dans package.xml :
        # didier_jeu dépend déjà de robot_rehearsal (cycle colcon) — le nom du
        # package n'est résolu qu'au lancement.
        Node(
            package="didier_jeu", executable="jeu_node", name="jeu_node", output="screen",
            condition=IfCondition(LaunchConfiguration("jeu")),
            respawn=True, respawn_delay=2.0,
        ),
    ])


def _director(scenario_file, route_file, condition, remappings):
    """Le régisseur — UNE définition, deux instances exclusives (jeu:=true ou
    non) : un remap ne se conditionne pas par une LaunchConfiguration."""
    return Node(
        package="robot_rehearsal", executable="director", name="director", output="screen",
        parameters=[{
            "scenario_file": scenario_file,
            "route_file": route_file,
            "speed": ParameterValue(LaunchConfiguration("speed"), value_type=float),
            "seed": ParameterValue(LaunchConfiguration("seed"), value_type=int),
            "autostart": ParameterValue(LaunchConfiguration("autostart"), value_type=bool),
        }],
        remappings=remappings,
        condition=condition,
    )
