"""Le câblage physique du visage, gravé dans le marbre.

Vérité terrain établie le 2026-07-11 à la mire « calib-couleurs » (lecture
humaine sur le vrai robot, vu de face) : bouche en serpentin entrant en bas à
droite, yeux à matrice unique. Si un de ces tests casse, c'est que la table
d'ImageMapping ne correspond plus au câblage RÉEL — ne pas « corriger » le
test sans re-passer la mire sur le robot.
"""
import unittest

from robot.visual.image_mapping import ImageMapping, MATRIX, MOUTH_WIDTH, MOUTH_HEIGHT


def render(mapping, width, height, start=0, strip_len=600):
    """Applique la table sur une image dont chaque pixel est unique (x, y)."""
    image = [[(x, y) for x in range(width)] for y in range(height)]
    strip = [None] * strip_len
    mapping.mapping(strip, image, start)
    return strip


class TestMouthMapping(unittest.TestCase):

    def setUp(self):
        self.strip = render(ImageMapping.mouth(), MOUTH_WIDTH, MOUTH_HEIGHT)

    def cell_of(self, index):
        """Retourne l'ensemble des pixels image (x, y) écrits dans un bloc de 64."""
        return {self.strip[i] for i in range(index, index + 64)}

    def test_couvre_exactement_les_384_leds(self):
        ecrits = [i for i, v in enumerate(self.strip) if v is not None]
        self.assertEqual(ecrits, list(range(384)))

    def test_serpentin_bloc_par_cellule(self):
        # Mire couleurs : bas-droite=0, bas-centre=64, bas-gauche=128,
        # haut-gauche=192, haut-centre=256, haut-droite=320.
        attendu = {
            0: (2, 1), 64: (1, 1), 128: (0, 1),   # (colonne, rangée) image
            192: (0, 0), 256: (1, 0), 320: (2, 0),
        }
        for offset, (cx, cy) in attendu.items():
            zone = {(x, y) for x in range(cx * 8, cx * 8 + 8)
                    for y in range(cy * 8, cy * 8 + 8)}
            self.assertEqual(self.cell_of(offset), zone,
                             "bloc {} != cellule image {}".format(offset, (cx, cy)))

    def test_orientation_interne(self):
        # Mire calib 2026-07-11 : rangée haute montée à l'endroit, rangée
        # basse tête-bêche (rot180). Coin haut-gauche de la cellule
        # haut-gauche (bloc 192, à l'endroit) = 1er pixel du bloc ; coin
        # haut-gauche de la cellule bas-droite (bloc 0, rot180) = DERNIER.
        self.assertEqual(self.strip[192], (0, 0))
        self.assertEqual(self.strip[63], (16, 8))

    def test_image_mauvaise_taille_refusee(self):
        strip = [None] * 600
        ImageMapping.mouth().mapping(strip, [[(0, 0)] * 8] * 8, 0)
        self.assertTrue(all(v is None for v in strip),
                        "une image 8x8 ne doit pas être écrite par la table bouche")


class TestEyeMapping(unittest.TestCase):

    def test_couvre_64_leds_a_partir_du_start(self):
        # Câblage CONTIGU (mire bordure du 2026-07-11) : bouche 0-383,
        # œil droit 384-447, œil gauche 448-511 — aucun trou. Les starts
        # historiques 385/449 décalaient tout le contenu d'une LED.
        strip = render(ImageMapping.eye(), MATRIX, MATRIX, start=448)
        ecrits = [i for i, v in enumerate(strip) if v is not None]
        self.assertEqual(ecrits, list(range(448, 512)))

    def test_orientation_interne(self):
        # Matrices d'yeux montées tête-bêche (rot180) : le coin haut-gauche
        # de l'image s'écrit sur le DERNIER index du bloc.
        strip = render(ImageMapping.eye(), MATRIX, MATRIX, start=0)
        self.assertEqual(strip[63], (0, 0))


if __name__ == "__main__":
    unittest.main()
