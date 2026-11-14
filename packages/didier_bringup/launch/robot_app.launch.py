from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import EnvironmentVariable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, PushRosNamespace
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

# Contrat inter-machines (noms des topics servo) : reste sur la lib partagée.
from dadou_utils_ros.utils_static import NAME, NECK, LEFT_ARM, RIGHT_ARM, LEFT_EYE, RIGHT_EYE
# Constantes internes au robot (numéros PWM, bornes servo) : rapatriées (cf. robot_static).
from didier_core.robot_static import HEAD_PWM_NB, DEFAULT_POS, MAX_POS, LEFT_ARM_NB, \
    RIGHT_ARM_NB, LEFT_EYE_NB, RIGHT_EYE_NB
from didier_core.robot_config import config


def generate_launch_description():
    # Lot L1b : tous les nœuds du robot (et la chaîne roues incluse) vivent sous
    # /<ROBOT_NAME>/ (défaut /didier/). Les actions sont collectées dans `group`
    # puis enveloppées dans UN GroupAction + PushRosNamespace ABSOLU en fin de
    # fonction — jamais de namespace= par nœud (on l'oublierait au prochain).
    group = []

    # name= rename node
    # remap topic remappings=
    # parameters=

    #remap_number_topic = ("number", "my_number")

    ai_server_node = Node(
        package="didier_core",
        executable="ai_node",
        name="ai_node"
    )

    animations_server_node = Node(
        package="didier_core",
        executable="animations_node",
        name="animations_node"
    )

    audio_server_node = Node(
        package="didier_core",
        executable="audio_node",
        name="audio_node"
    )

    face_server_node = Node(
        package="didier_core",
        executable="face_node",
        name="face_node"
    )

    lights_server_node = Node(
        package="didier_core",
        executable="lights_node",
        name="lights_node"
    )

    relays_server_node = Node(
        package="didier_core",
        executable="relays_node",
        name="relays_node"
    )

    system_server_node = Node(
        package="didier_core",
        executable="system_node",
        name="system_node"
    )

    wheels_server_node = Node(
        package="didier_core",
        executable="wheels_node",
        name="wheels_node"
    )

    neck_server_node = Node(
        package="didier_core",
        executable="servo_node",
        name="{}_node".format(NECK),
        parameters=[
            {NAME: NECK},
            {HEAD_PWM_NB: config[HEAD_PWM_NB]},
            {DEFAULT_POS: 50},
            {MAX_POS: 180}
        ]
    )

    left_arm_server_node = Node(
        package="didier_core",
        executable="servo_node",
        name="{}_node".format(LEFT_ARM),
        parameters=[
            {NAME: LEFT_ARM},
            {HEAD_PWM_NB: config[LEFT_ARM_NB]},
            {DEFAULT_POS: 90},
            {MAX_POS: 180}
        ]
    )

    right_arm_server_node = Node(
        package="didier_core",
        executable="servo_node",
        name="{}_node".format(RIGHT_ARM),
        parameters=[
            {NAME: RIGHT_ARM},
            {HEAD_PWM_NB: config[RIGHT_ARM_NB]},
            {DEFAULT_POS: 180},
            {MAX_POS: 180}
        ]
    )

    left_eye_server_node = Node(
        package="didier_core",
        executable="servo_node",
        name="{}_node".format(LEFT_EYE),
        parameters=[
            {NAME: LEFT_EYE},
            {HEAD_PWM_NB: config[LEFT_EYE_NB]},
            {DEFAULT_POS: 70},
            {MAX_POS: 180}
        ]
    )

    right_eye_server_node = Node(
        package="didier_core",
        executable="servo_node",
        name="{}_node".format(RIGHT_EYE),
        parameters=[
            {NAME: RIGHT_EYE},
            {HEAD_PWM_NB: config[RIGHT_EYE_NB]},
            {DEFAULT_POS: 45},
            {MAX_POS: 180}
        ]
    )

    #number_counter_node = Node(
    #    package="didier_core",
    #    executable="number_counter",
    #    name="my_number_counter",
    #    remappings=[
    #        remap_number_topic,
    #        ("count", "my_count"),
    #    ],
    #    parameters = [
    #        {"number_to_publish": 4},
    #        {"publish_frequency": 5.0}
    #    ]
    #)

    # Pont web (didier_web) : supervision + contenus + panneau technique depuis
    # un navigateur -- http://192.168.1.2:8765, badge rouge ROBOT RÉEL (domain 42).
    # SÉCURITÉ : drive_enabled = argument web_drive, false par défaut (aucun
    # argument sur le robot), le
    # publisher cmd_vel_web n'existe donc pas : le pilotage web reste SIM-ONLY
    # tant que test scénique au sol + protocole caméra ne sont pas faits
    # (docs/etude-interface-web.md §6). Retour vidéo (2026-07-11) : le flux
    # vient du Pi VISION — person_tracker publie camera/image_raw/compressed
    # (JPEG ~5 i/s, la webcam lui appartient en exclusif, cf. dadou_vision_ros)
    # -> camera_compressed=True, les octets sont servis TELS QUELS en MJPEG
    # (zéro ré-encodage sur le Pi robot). json_dir = structure assemblée par
    # Ansible (json/ à plat dans src/robot/, cf. docker-compose-sim.yml).
    #
    # L2b (spec L2, décision 15) : sept arguments, lus par CE nœud seul, dont les défauts sont
    # EXACTEMENT les valeurs d'avant (robot : aucun argument passé, rien ne change). Seul le
    # compose de la SIM en passe (machines/sim/robot/entree.sh) ; aucun machine.yml ni compose
    # ARM ne les cite (gravé par test_robot_app_sim.py). `value_type` explicite partout : une
    # LaunchConfiguration est une chaîne, et un topic vide ne doit pas être lu comme du YAML.
    web_bridge_node = Node(
        package="didier_web",
        executable="web_bridge",
        name="web_bridge_node",
        # data_edit_enabled (L1d-3) : MÊME variable DATA_EDIT que data_edit_node plus bas
        # (défaut false = ni publisher data_edit ni éditeur dans la page) ; data_dir par
        # défaut = src/robot, comme l'écrivain.
        parameters=[{
            "json_dir": "/home/ros2_ws/src/robot/json",
            "camera_topic": ParameterValue(LaunchConfiguration("camera_topic"), value_type=str),
            "camera_compressed": ParameterValue(LaunchConfiguration("camera_compressed"), value_type=bool),
            "data_edit_enabled": ParameterValue(
                EnvironmentVariable("DATA_EDIT", default_value="false"), value_type=bool),
            "web_port": ParameterValue(LaunchConfiguration("web_port"), value_type=int),
            # SÉCURITÉ : drive_enabled et rehearsal_enabled restent faux sur le robot (défauts) ;
            # le nœud ignore de toute façon rehearsal_enabled hors du domaine 43.
            "drive_enabled": ParameterValue(LaunchConfiguration("web_drive"), value_type=bool),
            "rehearsal_enabled": ParameterValue(LaunchConfiguration("rehearsal"), value_type=bool),
            "perception_topic": ParameterValue(LaunchConfiguration("perception_topic"), value_type=str),
            "exterior_topic": ParameterValue(LaunchConfiguration("exterior_topic"), value_type=str),
        }],
    )

    # Catalogue + version (L1c) : le robot publie, latchés, ce qu'il sait jouer
    # (`catalogue`) et le sha git déployé (`deploy_sha`). Toujours lancé (la
    # télécommande s'en sert même sans pont web). DEPLOY_SHA est écrit par
    # Ansible dans conf/ (monté dans le conteneur, survit aux rsync) ; absent
    # -> "dev". Mêmes chemins que web_bridge_node (json/ à plat dans src/robot/).
    catalogue_node = Node(
        package="didier_web",
        executable="catalogue",
        name="catalogue_node",
        parameters=[{
            "json_dir": "/home/ros2_ws/src/robot/json",
            "deploy_sha_file": "/home/ros2_ws/src/robot/conf/DEPLOY_SHA",
        }],
    )

    # Écrivain des données (L1d) : toujours lancé ; DÉSACTIVÉ tant que la variable DATA_EDIT
    # n'est pas "true" (il répond alors edition_desactivee à chaque demande). L'activer sur le
    # vrai robot est une décision de David (spec L1d, décision 10). data_dir par défaut =
    # src/robot (json/ et medias/ à plat, montés en lecture-écriture par le compose ARM).
    data_edit_node = Node(
        package="didier_web",
        executable="data_edit",
        name="data_edit_node",
        parameters=[{"enabled": ParameterValue(
            EnvironmentVariable("DATA_EDIT", default_value="false"), value_type=bool)}],
    )

    # Chaîne de commande roues (twist_mux -> twist_deadman -> cmd_vel + wheels_bridge).
    # Inoffensive en mode legacy : personne ne consomme /cmd_vel tant que
    # WHEELS_CMD_VEL_ENABLED est False. Nécessaire en mode /cmd_vel pour alimenter
    # wheels_node depuis la télécommande / les animations.
    drive_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare("didier_drive"), "launch", "drive.launch.py"])
        )
    )

    #group.append(ai_server_node)
    group.append(animations_server_node)
    group.append(audio_server_node)
    #group.append(face_server_node)
    group.append(lights_server_node)
    group.append(relays_server_node)
    group.append(system_server_node)
    group.append(wheels_server_node)
    group.append(neck_server_node)
    group.append(left_arm_server_node)
    group.append(right_arm_server_node)
    group.append(left_eye_server_node)
    group.append(right_eye_server_node)
    group.append(web_bridge_node)
    group.append(catalogue_node)
    group.append(data_edit_node)
    group.append(drive_launch)

    # drive.launch.py pousse lui aussi /<robot_name> en absolu : inclus ici, il
    # reçoit la même LaunchConfiguration robot_name, le résultat est identique.
    return LaunchDescription([
        DeclareLaunchArgument("robot_name",
                              default_value=EnvironmentVariable("ROBOT_NAME", default_value="didier"),
                              description="Nom du robot = namespace ABSOLU de tous les nœuds"
                                          " (défaut : variable ROBOT_NAME, sinon didier)"),
        # L2b (décision 15) : les sept arguments du pont web, défauts = valeurs d'avant L2.
        # `use_sim_time` n'est PAS déclaré ici : passé à `ros2 launch`, il atteint
        # drive.launch.py, qui le déclare (fait 12 de la spec) — la chaîne roues est intouchée.
        DeclareLaunchArgument("web_port", default_value="8765",
                              description="Port HTTP/WebSocket du pont web"),
        DeclareLaunchArgument("web_drive", default_value="false",
                              description="SÉCURITÉ (SIM-ONLY) : pilotage roues du pont web ; faux sur le robot"),
        DeclareLaunchArgument("rehearsal", default_value="false",
                              description="SÉCURITÉ (SIM-ONLY) : boutons de répétition de la page scène ;"
                                          " ignoré hors domaine 43"),
        DeclareLaunchArgument("camera_topic", default_value="camera/image_raw/compressed",
                              description="Flux vidéo de la page (robot : JPEG du Pi vision)"),
        DeclareLaunchArgument("camera_compressed", default_value="true",
                              description="true = camera_topic est un CompressedImage servi tel quel"),
        DeclareLaunchArgument("perception_topic", default_value="",
                              description="Ce que voit person_tracker (vide = panneau absent)"),
        DeclareLaunchArgument("exterior_topic", default_value="",
                              description="Caméra de poursuite de la sim (vide = panneau absent)"),
        GroupAction([PushRosNamespace(["/", LaunchConfiguration("robot_name")]), *group]),
    ])