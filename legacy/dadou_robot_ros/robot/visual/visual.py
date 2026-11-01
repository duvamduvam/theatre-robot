import logging
import os

import imageio.v2 as imageio


class Visual:
    """Une image de visage chargée telle quelle : depuis le refactoring du
    câblage (2026-07-11), TOUTE l'adaptation au montage physique vit dans
    ImageMapping — plus aucune transformation au chargement (l'ancien
    inverse_bottom_image compensait partiellement, et à tort, le serpentin
    de la bouche)."""

    def __init__(self, path):
        self.name = os.path.basename(path)
        logging.debug("chargement visuel %s", self.name)
        self.rgb = imageio.imread(path)
