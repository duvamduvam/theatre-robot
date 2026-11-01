from PIL import Image, ImageDraw

from controller.control_config import config
from controller.control_static import PURPLE


class PillowConfig:

    # Taille de l'image
    largeur = 320
    hauteur = 240

    change = False

    # Création de l'image
    image = Image.new("RGB", (largeur, hauteur), "white")
    draw = ImageDraw.Draw(image)

    # Définition des couleurs
    couleurs = [config[PURPLE], "green", "blue", "yellow", "purple", "orange"]

    def update(self):

        # Dimensions des cellules
        largeur_cellule = self.largeur // 2
        hauteur_cellule = self.hauteur // 3

        # Remplissage des cellules avec des couleurs différentes
        for i in range(3):
            for j in range(2):
                couleur = self.couleurs[i * 2 + j]
                x1 = j * largeur_cellule
                y1 = i * hauteur_cellule
                x2 = x1 + largeur_cellule
                y2 = y1 + hauteur_cellule
                self.draw.rectangle([x1, y1, x2, y2], fill=couleur)

        return self.image

    # Affichage de l'image
    #image.show()

    def process(self):
        return self.update()
        #if self.change:
        #    return self.image
