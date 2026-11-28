from setuptools import find_packages, setup

package_name = 'theatre_gabarit'

setup(
    name=package_name,
    version='0.1.0',
    # squelette/ n'est PAS un module : il est recopié par tools/nouvel_appareil.py (COLCON_IGNORE).
    packages=find_packages(exclude=['test', 'squelette', 'squelette.*']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='dadou',
    maintainer_email='achats@duvam.net',
    description="Gabarit d'appareil du parc Didier (lot L3a) : la plomberie commune des appareils",
    license='MIT',
    tests_require=['pytest'],
)
