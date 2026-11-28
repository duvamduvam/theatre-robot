"""Launch de l'appareil : namespace absolu /<ROBOT_NAME>/, arguments pilote (défaut materiel) et
config (theatre_gabarit.lancement)."""
from launch import LaunchDescription
from theatre_gabarit.lancement import config_defaut, groupe_appareil


def generate_launch_description():
    return LaunchDescription(groupe_appareil(
        "appareil_gabarit_core", "appareil_gabarit_node", "appareil_gabarit",
        config_defaut("appareil_gabarit", "appareil_gabarit")))
