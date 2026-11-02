import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'didier_jeu'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='dadou',
    maintainer_email='achats@duvam.net',
    description='Sélecteur de jeu de Didier (lot A1, SIM-ONLY)',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'jeu_node = didier_jeu.jeu_node:main',
        ],
    },
)
