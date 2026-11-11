"""Racine des données de la vision = DIDIER_VISION_DATA_DIR (lot L1e-3d, décision 3 de la spec L1).

Le code a déménagé dans packages/didier_vision ; la vision n'a aucune donnée suivie (conf/ et
mediamtx/ sont dans machines/vision/, le reste est posé par Ansible ; conteneur : /home/ros2_ws/src/vision/). vision_config
lit la racine dans DIDIER_VISION_DATA_DIR, défaut = le chemin conteneur. Valeurs GRAVÉES ici :
un test qui recalculerait l'attendu avec vision_config ne testerait rien.

Chaque cas importe vision_config dans un PROCESSUS NEUF : la racine est lue à l'import, et le
processus de pytest a déjà la valeur posée par conftest.py.
"""
import os
import pathlib
import subprocess
import sys

LEGACY_VISION = pathlib.Path(__file__).resolve().parents[4] / "legacy" / "dadou_vision_ros"

_SONDE = ("from didier_vision import vision_config as v\n"
          "print(v.DATA_DIR)\n"
          "print(v.SECRET_FILE)\n"
          "print(v.config['db_directory'])\n"
          "print(v.config['pictures_folder'])\n"
          "print(v.config['chat_piper_voice'])\n")


def _chemins(valeur):
    """(racine, secret, db, pictures, voix) vus par vision_config avec la variable = valeur (None = absente)."""
    env = {k: v for k, v in os.environ.items() if k != "DIDIER_VISION_DATA_DIR"}
    if valeur is not None:
        env["DIDIER_VISION_DATA_DIR"] = valeur
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    sortie = subprocess.run([sys.executable, "-c", _SONDE], env=env, capture_output=True,
                            text=True, check=True, timeout=60)
    return sortie.stdout.splitlines()[-5:]


def test_sans_variable_la_racine_est_le_chemin_conteneur_historique():
    assert _chemins(None) == [
        "/home/ros2_ws/src/vision/", "/home/ros2_ws/src/vision/conf/secret",
        "/home/ros2_ws/src/vision/db/", "/home/ros2_ws/src/vision/medias/pictures/",
        "/home/ros2_ws/src/vision/medias/voices/didier.onnx"]


def test_une_variable_vide_vaut_absente():
    assert _chemins("")[0] == "/home/ros2_ws/src/vision/"


def test_la_variable_remplace_la_racine_et_la_barre_finale_est_ajoutee():
    assert _chemins("/srv/didier/vision") == [
        "/srv/didier/vision/", "/srv/didier/vision/conf/secret", "/srv/didier/vision/db/",
        "/srv/didier/vision/medias/pictures/", "/srv/didier/vision/medias/voices/didier.onnx"]
    assert _chemins("/srv/didier/vision/")[0] == "/srv/didier/vision/"


def test_sous_pytest_le_conftest_pointe_un_dossier_temporaire_hors_depot():
    # L1e-4e : plus de racine de données dans le dépôt (la config crée db/ à l'import).
    from didier_vision import vision_config
    assert os.path.basename(vision_config.DATA_DIR.rstrip("/")).startswith("didier-vision-donnees-")
    assert str(LEGACY_VISION) not in vision_config.DATA_DIR
    # L1e-4c (11/11) : conf/ a quitté la racine de données de l'hôte pour machines/vision/ (copiée
    # en src/vision/conf/ sur le Pi : le chemin conteneur, lui, ne change pas).
    assert not (LEGACY_VISION / "conf").exists()
    assert (LEGACY_VISION.parents[1] / "machines" / "vision" / "secret.example").is_file()
