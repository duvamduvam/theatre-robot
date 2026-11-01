"""Aperçu web du visage (simulation) : tests PURS du rendu, sans ROS ni
matériel. Le rendu réutilise TELLES QUELLES les tables de Face (câblage
gravé le 2026-07-11, cf. test_image_mapping.py/test_face.py) : ces tests
n'en recopient donc jamais les valeurs -- ils lisent
Face.mouth_image_mapping / Face.eye_image_mapping pour savoir où écrire et
où vérifier, comme test_image_mapping.py le fait déjà pour Face lui-même.
"""
import numpy as np

from robot.actions.face import Face
from robot.visual.face_preview import (
    CANVAS_HEIGHT, CANVAS_WIDTH, LEYE_ORIGIN, MOUTH_ORIGIN, REYE_ORIGIN,
    PreviewStrip, render_face_rgb,
)


def test_pixel_bouche_atterrit_a_la_position_attendue():
    strip = PreviewStrip()
    y, x = 0, 0  # coin haut-gauche de l'image bouche (cellule haut-gauche, cf. table)
    index = Face.MOUTH_START + Face.mouth_image_mapping.index_table[y][x]
    strip[index] = (255, 0, 0)

    image = render_face_rgb(strip, scale=1)

    top, left = MOUTH_ORIGIN
    assert tuple(image[top + y, left + x]) == (255, 0, 0)


def test_pixel_oeil_droit_atterrit_a_la_position_attendue():
    strip = PreviewStrip()
    y, x = 3, 5
    index = Face.REYE_START + Face.eye_image_mapping.index_table[y][x]
    strip[index] = (0, 255, 0)

    image = render_face_rgb(strip, scale=1)

    top, left = REYE_ORIGIN
    assert tuple(image[top + y, left + x]) == (0, 255, 0)


def test_oeil_gauche_vu_de_face_est_rendu_a_gauche_de_l_image():
    # Piège du câblage (cf. image_mapping.py) : LEYE_START est l'œil GAUCHE
    # vu de face -- il doit apparaître à une colonne PLUS PETITE que REYE_START
    # dans l'image (vue spectateur), pas l'inverse.
    strip = PreviewStrip()
    y, x = 0, 0
    strip[Face.LEYE_START + Face.eye_image_mapping.index_table[y][x]] = (10, 20, 30)
    strip[Face.REYE_START + Face.eye_image_mapping.index_table[y][x]] = (40, 50, 60)

    image = render_face_rgb(strip, scale=1)

    top_l, left_l = LEYE_ORIGIN
    top_r, left_r = REYE_ORIGIN
    assert left_l < left_r
    assert tuple(image[top_l + y, left_l + x]) == (10, 20, 30)
    assert tuple(image[top_r + y, left_r + x]) == (40, 50, 60)


def test_taille_du_rendu_suit_le_scale():
    strip = PreviewStrip()
    for scale in (1, 4, 16):
        image = render_face_rgb(strip, scale=scale)
        assert image.shape == (CANVAS_HEIGHT * scale, CANVAS_WIDTH * scale, 3)
        assert image.dtype == np.uint8


def test_preview_strip_declenche_le_callback_a_show():
    recues = []
    strip = PreviewStrip(on_show=lambda pixels: recues.append(list(pixels)))
    strip[0] = (1, 2, 3)

    strip.show()

    assert len(recues) == 1
    assert recues[0][0] == (1, 2, 3)


def test_preview_strip_sans_callback_ne_plante_pas():
    # on_show=None (défaut) : utilisable en test pur sans serveur -- show()
    # ne doit rien lever.
    strip = PreviewStrip()
    strip.show()
