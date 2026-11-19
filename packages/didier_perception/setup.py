from setuptools import find_packages, setup

package_name = 'didier_perception'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='dadou',
    maintainer_email='achats@duvam.net',
    description='Perception de Didier : tableau des objets (scene/objets), lots O0-O1',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'objets_node = didier_perception.objets_node:main',
        ],
    },
)
