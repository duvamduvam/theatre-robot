"""Tests du catalogue pur du pont web W0 (robot_web.web_catalog) CONTRE LES
VRAIS FICHIERS json/ du dépôt -- même motif que test_expressions_json.py /
test_sequences_assets.py : les contrats de données courent sur les vrais
assets, pas sur des fixtures synthétiques qui masqueraient une dérive de
structure (ex. si expressions.json changeait de forme demain).
"""

import json
import pathlib

from robot_web.web_catalog import build_catalog

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
JSON_DIR = REPO_ROOT / "json"


def test_json_dir_existe_bien_sous_le_depot():
    # Si ce test échoue, tous les autres de ce fichier sont sans objet :
    # mieux vaut un échec explicite ici qu'un catalogue vide silencieux.
    assert JSON_DIR.is_dir()


# --- faces -------------------------------------------------------------------

def test_faces_couvre_les_cles_de_expressions_json():
    catalogue = build_catalog(JSON_DIR)
    with (JSON_DIR / "expressions.json").open() as f:
        expressions = json.load(f)
    assert set(catalogue["faces"]) == set(expressions.keys())
    assert "joie" in catalogue["faces"]  # exemple cité dans docs/interfaces.md


def test_faces_est_trie():
    catalogue = build_catalog(JSON_DIR)
    assert catalogue["faces"] == sorted(catalogue["faces"])


# --- robot_lights (PAS lights.json, voir docstring de web_catalog) ----------

def test_robot_lights_couvre_les_cles_de_robot_lights_json():
    catalogue = build_catalog(JSON_DIR)
    with (JSON_DIR / "robot_lights.json").open() as f:
        robot_lights = json.load(f)
    assert set(catalogue["robot_lights"]) == set(robot_lights.keys())
    assert "trip" in catalogue["robot_lights"]  # exemple cité dans docs/interfaces.md


def test_robot_lights_n_est_pas_lights_json():
    """Garde-fou anti-régression : lights.json est un AUTRE projet de
    séquences (liste, pas dict, et pas le fichier chargé par Lights pour le
    topic robot_lights -- voir robot/robot_config.py JSON_LIGHTS='robot_lights.json')."""
    with (JSON_DIR / "lights.json").open() as f:
        lights = json.load(f)
    assert isinstance(lights, list)  # confirme que ce n'est structurellement pas la même chose


# --- audios --------------------------------------------------------------------

def test_audios_porte_label_et_value_exacte_a_publier():
    catalogue = build_catalog(JSON_DIR)
    with (JSON_DIR / "audios.json").open() as f:
        audios = json.load(f)

    # Chaque entrée catalogue doit être {"label": clé, "value": chemin exact}.
    for entree in catalogue["audios"]:
        assert set(entree.keys()) == {"label", "value"}
        assert audios[entree["label"]]["path"] == entree["value"]


def test_audios_exclut_les_entrees_a_path_vide():
    """"stop" (audios.json) a un path vide : c'est un mapping clavier legacy
    (KEY), pas une valeur AUDIO publiable -- publier "" casserait play_sound()
    sans rien jouer. Le bouton STOP CONTENUS couvre déjà l'arrêt audio."""
    catalogue = build_catalog(JSON_DIR)
    labels = {entree["label"] for entree in catalogue["audios"]}
    assert "stop" not in labels


# --- animations ------------------------------------------------------------------

def test_animations_couvre_les_noms_de_sequences_sans_extension():
    catalogue = build_catalog(JSON_DIR)
    noms_attendus = {p.stem for p in (JSON_DIR / "sequences").glob("**/*.json")}
    assert set(catalogue["animations"]) == noms_attendus
    assert "parle" in catalogue["animations"]  # json/sequences/didier/parle.json


# --- relays ----------------------------------------------------------------------

def test_relays_couvre_les_cles_de_relays_json():
    catalogue = build_catalog(JSON_DIR)
    with (JSON_DIR / "relays.json").open() as f:
        relays = json.load(f)
    assert set(catalogue["relays"]) == set(relays.keys())


# --- Robustesse : dossier/fichier manquant ---------------------------------------

def test_dossier_json_manquant_donne_un_catalogue_vide_sans_exception(tmp_path):
    catalogue = build_catalog(tmp_path / "inexistant")
    assert catalogue == {
        "faces": [], "audios": [], "animations": [], "relays": [], "robot_lights": [],
    }


def test_fichier_illisible_donne_une_entree_vide_sans_exception(tmp_path):
    (tmp_path / "expressions.json").write_text("{ceci n'est pas du json")
    catalogue = build_catalog(tmp_path)
    assert catalogue["faces"] == []


def test_sequences_dossier_absent_donne_animations_vides_sans_exception(tmp_path):
    (tmp_path / "expressions.json").write_text("{}")
    catalogue = build_catalog(tmp_path)
    assert catalogue["animations"] == []
