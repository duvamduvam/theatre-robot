"""Aperçu web du visage LED en SIMULATION : reconstruit l'image vue par le
spectateur à partir du MÊME code de rendu que le vrai robot (Face +
ImageMapping, réutilisés tels quels, cf. robot/actions/face.py). Rien ici ne
réimplémente le câblage -- ce module ne fait qu'inverser les tables pour
dessiner, il ne les recalcule jamais.

PreviewStrip remplace FastNeoPixel (le driver matériel réel) : Face ne voit
aucune différence, il écrit des triplets RGB par __setitem__ et appelle
show() -- exactement le contrat déjà exercé par FakeStrip dans test_face.py.
"""

import numpy as np

from robot.actions.face import Face

# Longueur du strip réel (bouche 0-383 + oeil droit 384-447 + oeil gauche
# 448-511, cf. Face.MOUTH_START/REYE_START/LEYE_START) : le strip matériel a
# 1000 LED au total (robot_config.LIGHTS_LED_COUNT, corps compris), mais le
# visage n'en occupe que les 512 premières -- l'aperçu n'a besoin de rien
# d'autre.
STRIP_LEN = 512

# --- Disposition du rendu (unités PIXEL, avant upscale nearest) ------------
# Yeux 8x8 côte à côte en haut, bouche 24x16 dessous. Choisis pour que le
# rendu soit lisible sans prétendre reproduire les proportions physiques du
# visage (les LED ne sont pas carrées sur le vrai robot).
_MARGIN = 2      # marge autour de tout le visage
_EYE_GAP = 4     # espace entre les deux yeux
_ZONE_GAP = 2    # espace entre la rangée des yeux et la bouche
_EYES_ROW_WIDTH = Face.eye_image_mapping.width * 2 + _EYE_GAP

CANVAS_WIDTH = Face.mouth_image_mapping.width + 2 * _MARGIN
CANVAS_HEIGHT = (_MARGIN + Face.eye_image_mapping.height + _ZONE_GAP
                 + Face.mouth_image_mapping.height + _MARGIN)

# Coin haut-gauche de chaque zone dans le canevas (row, col). Publiques (pas
# de underscore) : la disposition est un contrat utile aux tests, pas un
# détail d'implémentation -- contrairement aux marges/gaps ci-dessus qui ne
# servent qu'à la calculer. Les yeux sont centrés horizontalement au-dessus
# de la bouche ; l'œil GAUCHE vu de face (LEYE_START) est posé À GAUCHE de
# l'image -- les noms du projet sont déjà en vue spectateur (cf.
# robot/visual/image_mapping.py), pas d'inversion ici.
_EYES_LEFT_X = _MARGIN + (Face.mouth_image_mapping.width - _EYES_ROW_WIDTH) // 2
_EYES_TOP_Y = _MARGIN
LEYE_ORIGIN = (_EYES_TOP_Y, _EYES_LEFT_X)
REYE_ORIGIN = (_EYES_TOP_Y, _EYES_LEFT_X + Face.eye_image_mapping.width + _EYE_GAP)
MOUTH_ORIGIN = (_EYES_TOP_Y + Face.eye_image_mapping.height + _ZONE_GAP, _MARGIN)


class PreviewStrip:
    """Ruban LED factice : buffer de STRIP_LEN triplets RGB + callback sur
    show(). Même contrat minimal que FakeStrip (test_face.py), utilisable
    directement par Face sans aucune adaptation.

    PAS de gestion de brightness ici : le facteur config[BRIGHTNESS]=0.05 est
    une contrainte MATÉRIELLE (éblouissement d'un ruban LED réel à pleine
    puissance), pas un choix de dessin -- l'appliquer à l'aperçu donnerait une
    image délavée sans rapport avec l'intention artistique des visuels.
    """

    def __init__(self, size=STRIP_LEN, on_show=None):
        self.pixels = [(0, 0, 0)] * size
        # Callback optionnel (le node face_sim_node y encode la frame JPEG) :
        # None par défaut pour rester utilisable en test pur, sans serveur.
        self.on_show = on_show

    def __setitem__(self, index, value):
        self.pixels[index] = value

    def __getitem__(self, index):
        return self.pixels[index]

    def __len__(self):
        return len(self.pixels)

    def show(self):
        if self.on_show is not None:
            self.on_show(self.pixels)


def _paint_zone(canvas, strip, mapping, start_pixel, origin):
    """Peint une zone en INVERSANT sa table : mapping.index_table[y][x] est
    l'index LED relatif écrit par Face pour le pixel image (y, x) -- ici on
    fait le chemin retour, LED -> pixel, pour reconstruire ce que voit le
    spectateur."""
    top, left = origin
    for y in range(mapping.height):
        row = mapping.index_table[y]
        for x in range(mapping.width):
            canvas[top + y, left + x] = strip[start_pixel + row[x]]


def render_face_rgb(strip, scale: int = 16) -> np.ndarray:
    """Reconstruit l'image RGB (uint8, HxWx3) vue par le spectateur à partir
    d'un strip (PreviewStrip ou toute séquence indexable de 512 triplets),
    en réutilisant TELLES QUELLES les tables Face.mouth_image_mapping et
    Face.eye_image_mapping. Upscale nearest (np.repeat) : les LED doivent
    rester des blocs carrés nets, pas un flou d'interpolation."""
    canvas = np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH, 3), dtype=np.uint8)

    _paint_zone(canvas, strip, Face.eye_image_mapping, Face.LEYE_START, LEYE_ORIGIN)
    _paint_zone(canvas, strip, Face.eye_image_mapping, Face.REYE_START, REYE_ORIGIN)
    _paint_zone(canvas, strip, Face.mouth_image_mapping, Face.MOUTH_START, MOUTH_ORIGIN)

    return np.repeat(np.repeat(canvas, scale, axis=0), scale, axis=1)
