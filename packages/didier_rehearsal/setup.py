import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'didier_rehearsal'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'config', 'scenarios'), glob('config/scenarios/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='dadou',
    maintainer_email='achats@duvam.net',
    description='Salle de répétition simulée (SIM-ONLY) : cheminement de Didier dans la rue, points d intérêt',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'route_driver = didier_rehearsal.route_driver_node:main',
            'fault_relay = didier_rehearsal.fault_relay_node:main',
            'director = didier_rehearsal.director_node:main',
        ],
    },
)
