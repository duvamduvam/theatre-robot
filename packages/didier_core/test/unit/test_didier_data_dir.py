"""Racine des données du cœur = DIDIER_DATA_DIR (lot L1e-3c, décision 3 de la spec L1).

Le code a déménagé dans packages/didier_core ; json/, medias/, db/, conf/ sont restés dans
legacy/dadou_robot_ros/ (conteneurs : /home/ros2_ws/src/robot/). robot_config.py lit la
racine dans DIDIER_DATA_DIR, défaut = le chemin conteneur. Valeurs GRAVÉES ici : un test qui
recalculerait l'attendu avec robot_config ne testerait rien.

Chaque cas importe robot_config dans un PROCESSUS NEUF : la racine est lue à l'import, et le
processus de pytest a déjà la valeur posée par conftest.py.
"""
import os
import pathlib
import subprocess
import sys

LEGACY_ROBOT = pathlib.Path(__file__).resolve().parents[4] / "legacy" / "dadou_robot_ros"

_SONDE = ("from didier_core.robot_config import config\n"
          "from dadou_utils_ros.utils_static import PROJECT_DIRECTORY, JSON_DIRECTORY, "
          "MEDIAS_DIRECTORY, CONFIG_DIRECTORY\n"
          "for cle in (PROJECT_DIRECTORY, JSON_DIRECTORY, MEDIAS_DIRECTORY, CONFIG_DIRECTORY):\n"
          "    print(config[cle])\n")


def _chemins(valeur):
    """(projet, json, medias, conf) vus par robot_config avec DIDIER_DATA_DIR=valeur (None = absente)."""
    env = {k: v for k, v in os.environ.items() if k != "DIDIER_DATA_DIR"}
    if valeur is not None:
        env["DIDIER_DATA_DIR"] = valeur
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    sortie = subprocess.run([sys.executable, "-c", _SONDE], env=env, capture_output=True,
                            text=True, check=True, timeout=60)
    # Les 4 DERNIÈRES lignes : l'import de la lib écrit déjà sur stdout (détection Raspberry).
    return sortie.stdout.splitlines()[-4:]


def test_sans_variable_la_racine_est_le_chemin_conteneur_historique():
    assert _chemins(None) == ["/home/ros2_ws/src/robot/", "/home/ros2_ws/src/robot/json/",
                              "/home/ros2_ws/src/robot/medias/", "/home/ros2_ws/src/robot/conf/"]


def test_une_variable_vide_vaut_absente():
    assert _chemins("")[0] == "/home/ros2_ws/src/robot/"


def test_la_variable_remplace_la_racine_et_la_barre_finale_est_ajoutee():
    assert _chemins("/srv/didier/data") == ["/srv/didier/data/", "/srv/didier/data/json/",
                                            "/srv/didier/data/medias/", "/srv/didier/data/conf/"]
    assert _chemins("/srv/didier/data/")[0] == "/srv/didier/data/"


def test_sous_pytest_le_conftest_pointe_les_donnees_de_legacy():
    from didier_core.robot_config import config
    from dadou_utils_ros.utils_static import PROJECT_DIRECTORY, JSON_DIRECTORY
    assert config[PROJECT_DIRECTORY] == str(LEGACY_ROBOT) + "/"
    assert pathlib.Path(config[JSON_DIRECTORY], "sequences").is_dir()
