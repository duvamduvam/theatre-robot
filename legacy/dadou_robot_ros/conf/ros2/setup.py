from setuptools import find_packages, setup

package_name = 'robot'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='pi',
    maintainer_email='pi@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            #"ai_node = robot.nodes.ai_node:main",
            "animations_node = robot.nodes.animations_node:main",
            "audio_node = robot.nodes.audio_node:main",
            #face_node = robot.nodes.face_node:main",
            # Aperçu web du visage LED en SIMULATION (SIM-ONLY : lancé par
            # sim.launch.py derrière l'argument face:=true, jamais dans le
            # bringup du vrai robot -- cf. robot/nodes/face_sim_node.py).
            "face_sim = robot.nodes.face_sim_node:main",
            # Suivi du regard (cou seulement, jamais les roues). Lancé À LA MAIN
            # tant que le sens du cou n'est pas validé caméra (pas dans le bringup).
            "gaze_follower = robot.nodes.gaze_follower_node:main",
            "lights_node = robot.nodes.lights_node:main",
            # Suivi de personne AUX ROUES (cmd_vel_follow -> twist_mux prio 20).
            # SIM-ONLY, lancé À LA MAIN : test scénique au sol + protocole caméra
            # requis avant tout usage réel (cf. person_follower_node.py).
            "person_follower = robot.nodes.person_follower_node:main",
            "relays_node = robot.nodes.relays_node:main",
            "servo_node = robot.nodes.servo_node:main",
            "system_node = robot.nodes.system_node:main",
            "wheels_node = robot.nodes.wheels_node:main"
        ],
    },
)
