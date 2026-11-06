import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'robot_drive'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='dadou',
    maintainer_email='achats@duvam.net',
    description='Chaîne de commande roues : bridge StringTime -> Twist, deadman sécurité, twist_mux',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'wheels_bridge = robot_drive.wheels_bridge_node:main',
            'twist_deadman = robot_drive.twist_deadman_node:main',
        ],
    },
)
