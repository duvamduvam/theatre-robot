from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

# Contrat inter-machines (noms des topics servo) : reste sur la lib partagée.
from dadou_utils_ros.utils_static import NAME, NECK, LEFT_ARM, RIGHT_ARM, LEFT_EYE, RIGHT_EYE
# Constantes internes au robot (numéros PWM, bornes servo) : rapatriées (cf. robot_static).
from robot.robot_static import HEAD_PWM_NB, DEFAULT_POS, MAX_POS, LEFT_ARM_NB, \
    RIGHT_ARM_NB, LEFT_EYE_NB, RIGHT_EYE_NB
from robot.robot_config import config


def generate_launch_description():
    ld = LaunchDescription()

    # name= rename node
    # remap topic remappings=
    # parameters=

    #remap_number_topic = ("number", "my_number")

    ai_server_node = Node(
        package="robot",
        executable="ai_node",
        name="ai_node"
    )

    animations_server_node = Node(
        package="robot",
        executable="animations_node",
        name="animations_node"
    )

    audio_server_node = Node(
        package="robot",
        executable="audio_node",
        name="audio_node"
    )

    face_server_node = Node(
        package="robot",
        executable="face_node",
        name="face_node"
    )

    lights_server_node = Node(
        package="robot",
        executable="lights_node",
        name="lights_node"
    )

    relays_server_node = Node(
        package="robot",
        executable="relays_node",
        name="relays_node"
    )

    system_server_node = Node(
        package="robot",
        executable="system_node",
        name="system_node"
    )

    wheels_server_node = Node(
        package="robot",
        executable="wheels_node",
        name="wheels_node"
    )

    neck_server_node = Node(
        package="robot",
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
        package="robot",
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
        package="robot",
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
        package="robot",
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
        package="robot",
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
    #    package="robot",
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

    # Pont web (robot_web) : supervision + contenus + panneau technique depuis
    # un navigateur -- http://192.168.1.2:8765, badge rouge ROBOT RÉEL (domain 42).
    # SÉCURITÉ : drive_enabled n'est PAS passé -> false (défaut du node), le
    # publisher cmd_vel_web n'existe donc pas : le pilotage web reste SIM-ONLY
    # tant que test scénique au sol + protocole caméra ne sont pas faits
    # (docs/etude-interface-web.md §6). Retour vidéo (2026-07-11) : le flux
    # vient du Pi VISION — person_tracker publie camera/image_raw/compressed
    # (JPEG ~5 i/s, la webcam lui appartient en exclusif, cf. dadou_vision_ros)
    # -> camera_compressed=True, les octets sont servis TELS QUELS en MJPEG
    # (zéro ré-encodage sur le Pi robot). json_dir = structure assemblée par
    # Ansible (json/ à plat dans src/robot/, cf. docker-compose-sim.yml).
    web_bridge_node = Node(
        package="robot_web",
        executable="web_bridge",
        name="web_bridge_node",
        parameters=[{
            "json_dir": "/home/ros2_ws/src/robot/json",
            "camera_topic": "camera/image_raw/compressed",
            "camera_compressed": True,
        }],
    )

    # Chaîne de commande roues (twist_mux -> twist_deadman -> cmd_vel + wheels_bridge).
    # Inoffensive en mode legacy : personne ne consomme /cmd_vel tant que
    # WHEELS_CMD_VEL_ENABLED est False. Nécessaire en mode /cmd_vel pour alimenter
    # wheels_node depuis la télécommande / les animations.
    drive_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare("robot_drive"), "launch", "drive.launch.py"])
        )
    )

    #ld.add_action(ai_server_node)
    ld.add_action(animations_server_node)
    ld.add_action(audio_server_node)
    #ld.add_action(face_server_node)
    ld.add_action(lights_server_node)
    ld.add_action(relays_server_node)
    ld.add_action(system_server_node)
    ld.add_action(wheels_server_node)
    ld.add_action(neck_server_node)
    ld.add_action(left_arm_server_node)
    ld.add_action(right_arm_server_node)
    ld.add_action(left_eye_server_node)
    ld.add_action(right_eye_server_node)
    ld.add_action(web_bridge_node)
    ld.add_action(drive_launch)
    return ld