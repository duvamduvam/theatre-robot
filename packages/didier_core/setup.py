from setuptools import find_packages, setup

package_name = 'didier_core'

setup(
    name=package_name,
    version='0.0.0',
    # Le module seulement : test/ (tests hôte) n'est pas installé.
    packages=find_packages(include=['didier_core', 'didier_core.*']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='dadou',
    maintainer_email='achats@duvam.net',
    description='Cœur embarqué de Didier (servos, roues, LED, audio, animations)',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            #"ai_node = didier_core.nodes.ai_node:main",
            "animations_node = didier_core.nodes.animations_node:main",
            "audio_node = didier_core.nodes.audio_node:main",
            #face_node = didier_core.nodes.face_node:main",
            # Aperçu web du visage LED en SIMULATION (SIM-ONLY : lancé par
            # sim.launch.py derrière l'argument face:=true, jamais dans le
            # bringup du vrai robot -- cf. didier_core/nodes/face_sim_node.py).
            "face_sim = didier_core.nodes.face_sim_node:main",
            # Suivi du regard (cou seulement, jamais les roues). Lancé À LA MAIN
            # tant que le sens du cou n'est pas validé caméra (pas dans le bringup).
            "gaze_follower = didier_core.nodes.gaze_follower_node:main",
            "lights_node = didier_core.nodes.lights_node:main",
            # Suivi de personne AUX ROUES (cmd_vel_follow -> twist_mux prio 20).
            # SIM-ONLY, lancé À LA MAIN : test scénique au sol + protocole caméra
            # requis avant tout usage réel (cf. person_follower_node.py).
            "person_follower = didier_core.nodes.person_follower_node:main",
            "relays_node = didier_core.nodes.relays_node:main",
            "servo_node = didier_core.nodes.servo_node:main",
            "system_node = didier_core.nodes.system_node:main",
            "wheels_node = didier_core.nodes.wheels_node:main"
        ],
    },
)
