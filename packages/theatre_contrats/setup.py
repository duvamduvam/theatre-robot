from setuptools import find_packages, setup

package_name = 'theatre_contrats'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test', 'tools']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='dadou',
    maintainer_email='achats@duvam.net',
    description='Contrat commun du parc Didier : topics, clés, organes, codec StringTime, QoS',
    license='MIT',
    tests_require=['pytest'],
)
