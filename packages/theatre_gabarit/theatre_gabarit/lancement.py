"""`groupe_appareil(...)` : le launch d'un appareil en une ligne (spec L3 décisions 2, 4 et 11).

Ce qu'il pose, pareil pour tout appareil :
- argument `robot_name` (défaut : variable ROBOT_NAME, sinon `didier`) -> namespace ABSOLU
  `/<robot_name>/` par UN PushRosNamespace (jamais de namespace= par nœud, règle L1b) : un
  appareil du spectacle vit sous le nom du robot qu'il sert ;
- argument `pilote` (défaut `materiel` : rien à poser sur le Pi ; la sim passe `pilote:=sim`) ;
- argument `config` (défaut : la conf de la machine, `machines/<m>/<appareil>.yaml` copiée dans
  `src/<projet>/conf/`) ;
- le nœud, paramètres `pilote` et `config`, JAMAIS use_sim_time (horloge murale).

launch et launch_ros sont importés À L'APPEL : le module s'importe sur le PC.
"""
from typing import Any



def config_defaut(projet: str, appareil: str) -> str:
    """Convention des Pi (avant L2e) : src/<projet>/conf/<appareil>.yaml, vu du conteneur."""
    return f"/home/ros2_ws/src/{projet}/conf/{appareil}.yaml"


def groupe_appareil(paquet: str, executable: str, nom_noeud: str, config: str) -> list[Any]:
    """Les entités de launch d'un appareil : 3 arguments, puis le groupe namespacé."""
    from launch.actions import DeclareLaunchArgument, GroupAction
    from launch.substitutions import EnvironmentVariable, LaunchConfiguration
    from launch_ros.actions import Node, PushRosNamespace

    return [
        DeclareLaunchArgument("robot_name",
                              default_value=EnvironmentVariable("ROBOT_NAME", default_value="didier"),
                              description="nom du robot = namespace ABSOLU de l'appareil"),
        DeclareLaunchArgument("pilote", default_value="materiel",
                              description="sim (domaine 43 seulement) ou materiel"),
        DeclareLaunchArgument("config", default_value=config,
                              description="câblage de CETTE machine (YAML)"),
        GroupAction([
            PushRosNamespace(["/", LaunchConfiguration("robot_name")]),
            Node(package=paquet, executable=executable, name=nom_noeud, output="screen",
                 parameters=[{"pilote": LaunchConfiguration("pilote"),
                              "config": LaunchConfiguration("config")}]),
        ]),
    ]
