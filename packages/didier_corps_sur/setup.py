import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'didier_corps_sur'

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
    description='Corps sûr de Didier (lot A0) : filtre des entrées autonomes des roues',
    license='MIT',
    tests_require=['pytest'],
    # Pas encore d'exécutable : le nœud corps_sur arrive au sous-lot A0-4.
    entry_points={'console_scripts': []},
)
