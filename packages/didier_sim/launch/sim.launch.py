"""Simulation Gazebo (Harmonic) du robot Dadou.

Lance : serveur gz (+ GUI si headless:=false), spawn du robot depuis
robot_description, robot_state_publisher et le bridge ros_gz.

    ros2 launch didier_sim sim.launch.py            # avec GUI
    ros2 launch didier_sim sim.launch.py headless:=true
    ros2 launch didier_sim sim.launch.py world:=rue   # monde "rue" (étude répétition simulée)

    # Rejeu des séquences JSON (animations_node, package "didier_core" -- OFF par
    # défaut, comme gaze_follower : lancement explicite requis) :
    ros2 launch didier_sim sim.launch.py animations:=true
    # puis, dans un autre terminal (même domaine ROS que la sim, 43) :
    #   ros2 topic pub -1 /didier/animation theatre_interfaces/msg/StringTime '{msg: "\\"parle\\""}'

    # Aperçu web du visage LED (face_sim, package "didier_core" -- les matrices LED
    # n'ont aucun rendu dans Gazebo) -- OFF par défaut, même prudence :
    ros2 launch didier_sim sim.launch.py face:=true
    # puis http://localhost:8766 (face_port pour changer le port).

Tout tourne en use_sim_time (horloge /clock bridgée depuis gz).

Namespace (lot L1b) : tout vit sous /<ROBOT_NAME>/ (défaut /didier/, variable
d'environnement posée par docker-compose-sim.yml, ou robot_name:=…). La CLI ne
suit PAS : un nom relatif tapé dans `ros2 topic pub` se résout à la racine —
préfixer (/didier/animation) ou `--ros-args -r __ns:=/didier` pour un ros2 run.
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (Command, EnvironmentVariable, LaunchConfiguration, PathJoinSubstitution,
                                  PythonExpression)
from launch_ros.actions import Node, PushRosNamespace
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

# base_link est au centre de la caisse : rayon roue (0.13) + demi-hauteur
# de caisse (0.10), plus 1 cm de marge pour poser le robot sans le coincer.
SPAWN_Z = "0.24"


def generate_launch_description():
    headless = LaunchConfiguration("headless")
    animations = LaunchConfiguration("animations")
    web = LaunchConfiguration("web")
    face = LaunchConfiguration("face")
    # ParameterValue(value_type=int) obligatoire : une LaunchConfiguration est
    # une chaîne, or le node déclare web_port comme entier.
    web_port = ParameterValue(LaunchConfiguration("web_port"), value_type=int)
    face_port = ParameterValue(LaunchConfiguration("face_port"), value_type=int)
    # Idem en bool : "false"/"true" -> False/True (coercition launch). SÉCURITÉ :
    # ce drapeau active le PILOTAGE ROUES du pont web (publisher cmd_vel_web),
    # défaut false. La chaîne roues (drive.launch.py) n'est PAS lancée ici : la
    # conduite en sim demande de la lancer À LA MAIN dans le conteneur (cf.
    # operations.md) -- on ne veut pas de mouvement automatique au démarrage.
    web_drive = ParameterValue(LaunchConfiguration("web_drive"), value_type=bool)
    # Même coercition bool. SÉCURITÉ (SIM-ONLY) : n'ouvre au pont web QUE les
    # boutons de répétition de la page /scene ; ne lance rien d'autre (la route
    # et le régisseur se lancent À LA MAIN, cf. README du package de répétition).
    rehearsal = ParameterValue(LaunchConfiguration("rehearsal"), value_type=bool)

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
        DeclareLaunchArgument("animations", default_value="false",
                              description="true = lance animations_node (paquet didier_core, rejeu des"
                                           " séquences JSON) -- OFF par défaut, même prudence que"
                                           " gaze_follower : activation explicite requise"),
        DeclareLaunchArgument("web", default_value="false",
                              description="true = lance web_bridge_node (paquet didier_web, pont"
                                           " HTTP/WebSocket W0 -- supervision + contenus + panneau"
                                           " technique, AUCUN accès roues/e_stop) -- OFF par défaut,"
                                           " même prudence que animations/gaze_follower"),
        DeclareLaunchArgument("web_port", default_value="8765",
                              description="Port HTTP/WebSocket du pont web (8088 évité : défaut"
                                           " Superset, collision vue sur le PC de dev)"),
        DeclareLaunchArgument("web_drive", default_value="false",
                              description="SÉCURITÉ (SIM-ONLY) : true = pilotage roues du pont web"
                                           " actif (publisher cmd_vel_web, twist_mux prio 50). Défaut"
                                           " false. La chaîne roues (drive.launch.py) doit être"
                                           " lancée À LA MAIN pour conduire en sim (voir operations.md)."
                                           " Rien ici ne s'active sur le vrai robot (protocole caméra)."),
        DeclareLaunchArgument("rehearsal", default_value="false",
                              description="SÉCURITÉ (SIM-ONLY) : true = le pont web accepte les topics de"
                                           " répétition (route, route_speed, rehearsal/cmd) et la page"
                                           " /scene affiche ses boutons de route et de séance. Défaut"
                                           " false. NE LANCE PAS la route ni le régisseur (à la main)."
                                           " Sans effet sans web:=true."),
        DeclareLaunchArgument("face", default_value="false",
                              description="true = lance face_sim (paquet didier_core, aperçu web du visage"
                                           " LED -- les matrices LED n'ont aucun rendu dans Gazebo)."
                                           " OFF par défaut, même prudence que animations/web :"
                                           " activation explicite requise."),
        DeclareLaunchArgument("face_port", default_value="8766",
                              description="Port HTTP du flux MJPEG de l'aperçu visage (8765 déjà pris"
                                           " par le pont web, cf. web_port)."),

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

            # Visualisation LED (matériaux émissifs gz, cf. didier_sim_lib/leds_logic.py) :
            # écoute robot_lights/face côté ROS, publie material_color (relatif, bridgé vers
            # /world/stage/material_color, système gz UserCommands du monde `stage`).
            Node(
                package="didier_sim",
                executable="leds_sim_node",
                parameters=[{"use_sim_time": True}],
                output="screen",
            ),

            # Rejeu des servos (neck/left_arm/right_arm/left_eye/right_eye, cf.
            # didier_sim_lib/servos_logic.py) : écoute les 5 topics StringTime,
            # publie <servo>/position (relatif, radians) sur les JointPositionController gz.
            Node(
                package="didier_sim",
                executable="servos_sim_node",
                parameters=[{"use_sim_time": True}],
                output="screen",
            ),

            # Rejeu des séquences JSON (paquet "didier_core", le VRAI code du robot --
            # PAS un paquet didier_sim, cf. Dockerfile-sim/docker-compose-sim.yml
            # pour comment il est construit dans le conteneur sim). OFF par défaut
            # (animations:=false) : même prudence que gaze_follower, activation
            # explicite. LIMITE ASSUMÉE : AnimationManager/Animation utilisent
            # TimeUtils.current_milli_time() (horloge MURALE partout, jamais
            # get_clock()) -- comme sur le vrai robot, donc pas une régression,
            # mais le rejeu ne suit PAS l'horloge simulée (use_sim_time n'aurait
            # aucun effet ici ; on ne le passe donc pas, contrairement aux autres
            # nodes de ce fichier).
            Node(
                package="didier_core",
                executable="animations_node",
                output="screen",
                condition=IfCondition(animations),
            ),

            # Aperçu web du visage LED (paquet "didier_core", le VRAI code du visage --
            # didier_core.actions.face.Face + ImageMapping, réutilisés tels quels sur un
            # strip factice, cf. robot/nodes/face_sim_node.py). Aucune libs
            # matérielle requise (contrairement à animations_node dont le rejeu
            # des séquences peut piloter des actions qui, elles, en dépendraient
            # si jamais activées) -- mais OFF par défaut quand même (face:=false),
            # même prudence que animations/web : lancement explicite requis.
            Node(
                package="didier_core",
                executable="face_sim",
                output="screen",
                parameters=[{"face_port": face_port}],
                condition=IfCondition(face),
            ),

            # Catalogue + sha (L1c) : toujours lancé, comme sur le robot. json_dir par
            # défaut (montage sim) ; pas de deploy_sha_file -> deploy_sha = "dev".
            Node(
                package="didier_web",
                executable="catalogue",
                name="catalogue_node",
                output="screen",
            ),

            # Pont web W0 (paquet didier_web, autonome façon didier_drive). Pas de
            # use_sim_time (voir web.launch.py) : les timeouts de session sont en
            # horloge murale. json_dir par défaut ("/home/ros2_ws/json") est déjà
            # le bon montage en sim (docker-compose-sim.yml), pas de param à passer.
            # web_port surchargable (WEB_PORT côté compose) : le conteneur est en
            # réseau host, une collision de port avec le PC de dev est vite arrivée
            # (vécue avec 8088, pris par Superset).
            Node(
                package="didier_web",
                executable="web_bridge",
                name="web_bridge_node",
                output="screen",
                # drive_enabled = web_drive et rehearsal_enabled = rehearsal : SIM-ONLY,
                # défauts false. camera_topic laissé au défaut du node
                # ("camera/image_raw", bridgé depuis gz). perception_topic : ce que
                # voit person_tracker (webcam du PC, conteneur vision, même domaine 43),
                # servi en lecture seule sur /perception -> panneau « Ce que Didier voit ».
                # exterior_topic : caméra de poursuite gz (xacro, chase_camera_link),
                # servie en lecture seule sur /exterior -> « Didier vu de l'extérieur ».
                parameters=[{"web_port": web_port, "drive_enabled": web_drive,
                             "rehearsal_enabled": rehearsal,
                             "perception_topic": "camera/image_raw/compressed",
                             "exterior_topic": "camera_ext/image_raw"}],
                condition=IfCondition(web),
            ),
        ]),
    ])
