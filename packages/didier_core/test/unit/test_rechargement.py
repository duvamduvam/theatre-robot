"""Rechargement à chaud (lot L1d, décision 9) : après une écriture de data_edit_node, le
robot relit DU DISQUE ce qui a changé, sans redémarrage. Valeurs GRAVÉES : l'entrée retouchée
a sa nouvelle valeur, une entrée voisine est inchangée ; fichier illisible = ancienne version
gardée. Le verdict lui-même (forme, nom revalidé) : theatre_contrats/test/test_donnees.py.
"""
import json
import os

import pytest

from dadou_utils_ros.utils_static import (
    ANIMATION, DEFAULT, FACE, JSON_DIRECTORY, JSON_EXPRESSIONS, JSON_LIGHTS, KEYS, NAME, ROBOT_LIGHTS,
    SEQUENCES_DIRECTORY,
)
from didier_core.actions.abstract_json_actions import AbstractJsonActions
from didier_core.actions.face import Face
from didier_core.actions.lights import Lights
from didier_core.robot_config import config
from didier_core.robot_static import EYE_VISUALS_PATH, LIGHTS_PIN, MOUTH_VISUALS_PATH, TYPES
from didier_core.sequences.animation_manager import AnimationManager

config.setdefault(LIGHTS_PIN, None)  # lu par Face.__init__ dans un log (valeur Pi seulement)


# ================================================================ séquences
@pytest.fixture
def manager(tmp_path):
    racine = tmp_path / "sequences"
    (racine / "essai").mkdir(parents=True)
    ecrire(racine / "essai" / "un.json", {"keys": "K1", "duration": 1000, "neck": [[0, 0.2]]})
    ecrire(racine / "essai" / "deux.json", {"keys": "K2", "duration": 2000, "types": ["little move"]})
    m = object.__new__(AnimationManager)
    m.config = dict(config)
    m.config[SEQUENCES_DIRECTORY] = str(racine) + "/"
    m.action_type = ANIMATION
    m.sequences_key, m.sequences_name = {}, {}
    m.load_multi_files_sequences(m.config[SEQUENCES_DIRECTORY])
    m.random_animation_sequence = []
    m.load_random_animation_sequences()
    return m, racine


def ecrire(chemin, valeur):
    chemin.write_text(json.dumps(valeur), encoding="utf-8")


def test_sequence_retouchee_relue_voisine_inchangee(manager):
    m, racine = manager
    ecrire(racine / "essai" / "un.json", {"keys": "K9", "duration": 1500, "neck": [[0, 0.37]]})
    assert m.recharger_sequence("essai/un") is True
    assert m.sequences_name["un"] == {"keys": "K9", "duration": 1500, "neck": [[0, 0.37]], NAME: "un"}
    # L'ancienne touche est purgée, la nouvelle pointe sur la nouvelle version.
    assert "K1" not in m.sequences_key
    assert m.sequences_key["K9"] is m.sequences_name["un"]
    assert m.sequences_name["deux"] == {"keys": "K2", "duration": 2000, "types": ["little move"], NAME: "deux"}
    assert m.sequences_key["K2"] is m.sequences_name["deux"]


def test_sequence_creee_jouable_et_tirage_reconstruit(manager):
    m, racine = manager
    assert m.random_animation_sequence == ["deux"]
    ecrire(racine / "essai" / "trois.json", {"keys": "K3", "duration": 500, TYPES: ["little move"]})
    m.recharger_sequence("essai/trois")
    assert m.sequences_name["trois"][NAME] == "trois"
    assert sorted(m.random_animation_sequence) == ["deux", "trois"]


def test_sequence_illisible_ancienne_gardee(manager):
    m, racine = manager
    ancienne = m.sequences_name["un"]
    (racine / "essai" / "un.json").write_text("{ cassé", encoding="utf-8")
    assert m.recharger_sequence("essai/un") is False
    assert m.sequences_name["un"] is ancienne
    assert m.sequences_key["K1"] is ancienne


def test_sequence_en_cours_garde_ses_pistes(manager):
    m, racine = manager
    m.playing = False
    m.update({ANIMATION: "un"})
    piste = m.necks_animation
    ecrire(racine / "essai" / "un.json", {"keys": "K1", "duration": 1000, "neck": [[0, 0.9]]})
    m.recharger_sequence("essai/un")
    assert m.necks_animation is piste
    assert m.current_animation["neck"] == [[0, 0.2]]


# ================================================================ visage
class FakeStrip:
    def __init__(self):
        self.pixels = [None] * 600

    def __setitem__(self, index, value):
        self.pixels[index] = value

    def __getitem__(self, index):
        return self.pixels[index]

    def __len__(self):
        return len(self.pixels)

    def show(self):
        pass


@pytest.fixture
def face(tmp_path, monkeypatch):
    """Face construite sur une COPIE des données réelles (json + visuels) : la retouche ne
    touche jamais data/ du dépôt."""
    import shutil
    from didier_core.files.robot_json_manager import RobotJsonManager
    json_dir = tmp_path / "json"
    shutil.copytree(config[JSON_DIRECTORY], json_dir)
    for zone, cle in (("mouth", MOUTH_VISUALS_PATH), ("eye", EYE_VISUALS_PATH)):
        shutil.copytree(config[cle], tmp_path / zone)
    conf = dict(config)
    conf[JSON_DIRECTORY] = str(json_dir) + "/"
    conf[MOUTH_VISUALS_PATH] = str(tmp_path / "mouth")
    conf[EYE_VISUALS_PATH] = str(tmp_path / "eye")
    f = Face(conf, RobotJsonManager(conf), FakeStrip())
    return f, json_dir, tmp_path


def test_expression_retouchee_relue_voisine_inchangee(face):
    f, json_dir, _ = face
    fichier = json_dir / "expressions.json"
    expressions = json.loads(fichier.read_text(encoding="utf-8"))
    voisine = dict(f.sequences_name["joie"])
    expressions["colere"]["duration"] = 1234
    expressions["l1d visage"] = {"duration": 500, "loop": False, "mouths": [[1, "woman-close.png"]],
                                 "left_eyes": [], "right_eyes": []}
    fichier.write_text(json.dumps(expressions), encoding="utf-8")
    f.recharger()
    assert f.sequences_name["colere"]["duration"] == 1234
    assert f.sequences_name["l1d visage"][NAME] == "l1d visage"
    assert f.sequences_name["joie"] == voisine
    # Redemander l'expression affichée applique la nouvelle version (current_face oublié).
    assert f.current_face == ""


def test_expression_illisible_ancienne_gardee(face):
    f, json_dir, _ = face
    avant = f.sequences_name
    (json_dir / "expressions.json").write_text("[", encoding="utf-8")
    f.recharger()
    assert f.sequences_name is avant


def test_image_seule_relue(face):
    f, _, racine = face
    voisine = f.visuals["oeil-droit.png"]
    avant = f.visuals["woman-close.png"].rgb.copy()
    # Une autre bouche RVB 8 bits du dépôt prend la place de woman-close.png sur le disque.
    (racine / "mouth" / "woman-close.png").write_bytes((racine / "mouth" / "bouche-bordure.png").read_bytes())
    f.recharger(image="mouth/woman-close")
    assert (f.visuals["woman-close.png"].rgb == f.visuals["bouche-bordure.png"].rgb).all()
    assert not (f.visuals["woman-close.png"].rgb == avant).all()
    assert f.visuals["oeil-droit.png"] is voisine


def test_image_illisible_ancienne_gardee(face):
    f, _, racine = face
    avant = f.visuals["woman-close.png"]
    (racine / "mouth" / "woman-close.png").write_bytes(b"pas une image")
    f.recharger(image="mouth/woman-close")
    assert f.visuals["woman-close.png"] is avant


# ================================================================ lumières
@pytest.fixture
def lights(tmp_path):
    import shutil
    from didier_core.files.robot_json_manager import RobotJsonManager
    json_dir = tmp_path / "json"
    shutil.copytree(config[JSON_DIRECTORY], json_dir)
    conf = dict(config)
    conf[JSON_DIRECTORY] = str(json_dir) + "/"
    manager = RobotJsonManager(conf)
    lum = object.__new__(Lights)
    AbstractJsonActions.__init__(lum, config=conf, json_manager=manager, json_file=conf[JSON_LIGHTS],
                                 action_type=ROBOT_LIGHTS)
    lum.light_type = ROBOT_LIGHTS
    from didier_core.robot_static import JSON_COLORS
    lum.colors = manager.get_json_file(conf[JSON_COLORS])
    lum.lights_base = lum.load_light_base(conf, manager)
    lum.default = DEFAULT
    return lum, json_dir


def test_lumiere_et_brique_relues_voisines_inchangees(lights):
    lum, json_dir = lights
    voisine_lumiere = dict(lum.sequences_name["trip"])
    voisine_brique = dict(lum.lights_base["love"])
    robot_lights = json.loads((json_dir / "robot_lights.json").read_text(encoding="utf-8"))
    robot_lights["l1d lumiere"] = {"duration": 3000, "loop": False, "sequences": {"love": 0.5, "oulala": 1}}
    (json_dir / "robot_lights.json").write_text(json.dumps(robot_lights), encoding="utf-8")
    base = json.loads((json_dir / "lights_base.json").read_text(encoding="utf-8"))
    base["oulala"] = {"method": "pulse", "color": "BLUE"}
    (json_dir / "lights_base.json").write_text(json.dumps(base), encoding="utf-8")
    lum.recharger()
    assert lum.sequences_name["l1d lumiere"]["sequences"] == {"love": 0.5, "oulala": 1}
    assert lum.lights_base["oulala"]["method"] == "pulse"
    assert lum.lights_base["oulala"]["color"] == (0, 0, 255)  # couleur résolue comme au démarrage
    assert lum.sequences_name["trip"] == voisine_lumiere
    assert lum.lights_base["love"] == voisine_brique


def test_briques_illisibles_anciennes_gardees(lights):
    lum, json_dir = lights
    avant = lum.lights_base
    (json_dir / "lights_base.json").write_text("{", encoding="utf-8")
    lum.recharger()
    assert lum.lights_base is avant
