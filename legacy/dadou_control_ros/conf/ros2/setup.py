import os
import sys

from setuptools import find_packages, setup

package_name = 'controller'

# Vérifier la variable d'environnement DISPLAY et l'argument --use-gui
use_gui = os.environ.get('GUI') and os.environ.get('GUI') == "yes"
has_display = os.environ.get('DISPLAY')
#if has_display and use_gui:
#    controller_node = "controller.nodes.main_gui:main"
#else:
#    controller_node = "controller.nodes.main_no_gui:main"

controller_node = "controller.nodes.main_gui:main"

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='pi',
    maintainer_email='pi@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=[
        'pytest',
        'numpy',
        'spidev'
    ],
    entry_points={
        'console_scripts': [
            "controller_node = {}".format(controller_node)
        ],
    },
)
