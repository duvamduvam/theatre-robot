import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'robot_web'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        # static/ : servi tel quel par web_bridge_node (index.html/app.js/style.css),
        # AUCUN build JS -- glob('static/*') suffit, pas de sous-dossiers ici.
        (os.path.join('share', package_name, 'static'), glob('static/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='dadou',
    maintainer_email='achats@duvam.net',
    description="Pont web (WebSocket + HTTP) du robot : supervision, contenus, panneau technique",
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'web_bridge = robot_web.web_bridge_node:main',
        ],
    },
)
