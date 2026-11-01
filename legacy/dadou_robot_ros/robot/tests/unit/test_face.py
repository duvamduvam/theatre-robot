"""Tests de caractérisation de Face : figent le comportement ACTUEL du rendu
d'expressions AVANT le refactoring prévu des pistes de keyframes.

On exerce le VRAI code de prod : vrais json/expressions.json, vrais PNG de
medias/visuals (via imageio), vraie table ImageMapping. Seuls le strip LED
(matériel) et l'horloge sont doublés. Si un de ces tests casse après un
refactoring, c'est que le comportement observable du visage a bougé -- à
reconfirmer à la caméra sur le robot avant de « corriger » le test.
"""

import pytest

from dadou_utils_ros.utils.time_utils import TimeUtils
from dadou_utils_ros.utils_static import FACE
from robot.robot_static import LIGHTS_PIN
from robot.robot_config import config
from robot.files.robot_json_manager import RobotJsonManager
from robot.actions.face import Face

# LIGHTS_PIN n'est peuplé que sur le Pi (board.D18) : Face.__init__ le lit dans
# un log debug. Hors matériel on pose une valeur neutre pour pouvoir construire.
config.setdefault(LIGHTS_PIN, None)


class FakeStrip:
    """Ruban LED factice : 600 pixels (comme le vrai strip global) + compteur
    d'appels show(). Face n'écrit que par __setitem__ (via ImageMapping) et
    déclenche l'affichage par show()."""

    def __init__(self, size=600):
        self.pixels = [None] * size
        self.show_calls = 0

    def __setitem__(self, index, value):
        self.pixels[index] = value

    def __getitem__(self, index):
        return self.pixels[index]

    def __len__(self):
        return len(self.pixels)

    def show(self):
        self.show_calls += 1


@pytest.fixture(scope="module")
def json_manager():
    # Charge réellement expressions.json + colors.json + ... du dépôt.
    return RobotJsonManager(config)


@pytest.fixture
def clock(monkeypatch):
    state = {"now": 1_000_000}
    monkeypatch.setattr(TimeUtils, "current_milli_time", staticmethod(lambda: state["now"]))
    return state


def make_face(json_manager, strip):
    return Face(config, json_manager, strip)


def non_black_pixels(strip):
    return [i for i, v in enumerate(strip.pixels) if v is not None]


def snapshot(strip):
    # Les pixels imageio sont des arrays numpy : on fige en tuples pour pouvoir
    # comparer deux états sans ambiguïté de vérité (numpy lève sinon).
    return [None if v is None else tuple(int(c) for c in v) for v in strip.pixels]


# --- a) construction : l'expression default est chargée et show() appelé ---

def test_construction_charge_default_et_affiche(json_manager):
    strip = FakeStrip()
    face = make_face(json_manager, strip)

    assert face.current_face == "default"
    assert strip.show_calls >= 1
    # La default écrit bouche + deux yeux : le strip n'est pas resté vierge.
    assert len(non_black_pixels(strip)) > 0


# --- b) update calib : ancres du câblage connu (cohérent test_image_mapping) ---

def test_update_calib_ecrit_les_ancres_connues(json_manager):
    strip = FakeStrip()
    face = make_face(json_manager, strip)
    strip.show_calls = 0

    face.update({FACE: "calib"})

    # calib-bouche.png : pixel fichier (0,0) est blanc. La table bouche envoie
    # le pixel image (0,0) sur l'index 192 (coin haut-gauche de la matrice
    # haut-gauche, montée à l'endroit) -- même ancre que test_image_mapping.
    assert strip[192] is not None
    assert tuple(strip[192]) != (0, 0, 0)
    # Les deux yeux (œil droit à 384, œil gauche à 448 -- câblage contigu) sont
    # aussi peints par la mire.
    assert strip[384] is not None
    assert strip[448] is not None
    assert strip.show_calls >= 1


# --- c) avancement temporel d'une expression multi-frames (joie) ---

def test_avancement_temporel_change_le_contenu(json_manager, clock):
    strip = FakeStrip()
    face = make_face(json_manager, strip)

    face.update({FACE: "joie"})  # duration 2000, loop, bouche 2 frames (0.55 / 1.0)
    show_after_load = strip.show_calls
    snapshot_initial = snapshot(strip)  # bouche = joie-sourire.png

    # Sémantique documentée : la frame [t, image] est affichée JUSQU'À
    # t*duration -> joie-rire.png (frame 2) apparaît à 0.55*2000 = 1100 ms.
    # (L'ancien moteur l'émettait à SON t = 2000 ms : un éclair en fin de
    # cycle au lieu de 45 % du temps — bug corrigé au refactoring Track.)
    clock["now"] += 1101
    face.process()

    assert strip.show_calls > show_after_load  # show() rappelé par process()
    assert snapshot(strip) != snapshot_initial  # la bouche est passée au rire

    # Au wrap du cycle (2000 ms), la frame 1 (sourire) revient.
    clock["now"] += 1000
    face.process()
    assert snapshot(strip) == snapshot_initial


# --- d) update stop -> retour à l'expression default ---

def test_update_stop_revient_au_default(json_manager):
    strip = FakeStrip()
    face = make_face(json_manager, strip)
    face.update({FACE: "calib"})
    assert face.current_face == "calib"

    face.update({FACE: "stop"})

    assert face.current_face == "default"


# --- e) expression inconnue : pas d'exception, strip inchangé ---

def test_expression_inconnue_ne_change_rien(json_manager):
    strip = FakeStrip()
    face = make_face(json_manager, strip)
    before = list(strip.pixels)
    show_before = strip.show_calls

    result = face.update({FACE: "nexistepas"})

    assert strip.pixels == before
    assert strip.show_calls == show_before
    assert result == {FACE: "nexistepas"}  # msg renvoyé tel quel
