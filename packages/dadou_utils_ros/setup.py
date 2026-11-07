from setuptools import find_packages, setup

package_name = 'dadou_utils_ros'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(include=['dadou_utils_ros', 'dadou_utils_ros.*']),
    # fonts/ (polices .ttf des écrans LCD) vit DANS le module : lu par chemin
    # relatif à __file__, il doit suivre le code à l'installation.
    package_data={'dadou_utils_ros': ['fonts/*']},
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='dadou',
    maintainer_email='achats@duvam.net',
    description='Lib partagée du parc Didier (communication, fichiers, LCD, journalisation)',
    license='MIT',
    tests_require=['pytest'],
)
