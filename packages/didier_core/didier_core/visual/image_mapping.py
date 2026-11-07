"""Correspondance pixel d'image -> index LED du strip, par table précalculée.

CÂBLAGE PHYSIQUE (établi le 2026-07-11 à la mire « calib-couleurs », lecture
humaine sur le vrai robot, tout est décrit VU DE FACE par le spectateur) :

- Bouche : 24x16, six matrices 8x8 chaînées en SERPENTIN. La chaîne ENTRE EN
  BAS À DROITE, parcourt la rangée basse de droite à gauche, remonte, puis
  parcourt la rangée haute de gauche à droite :
      index 0-63    -> bas-droite      192-255 -> haut-gauche
      index 64-127  -> bas-centre      256-319 -> haut-centre
      index 128-191 -> bas-gauche      320-383 -> haut-droite
  (l'ancien code supposait haut-gauche -> haut-droite puis bas-gauche ->
  bas-droite, d'où le visage affiché tête-bêche ; l'ancienne compensation
  inverse_bottom_image est supprimée, la table encode TOUT le câblage.)

- Yeux : une matrice 8x8 chacun. ATTENTION au nommage : la piste dessinée à
  start_pixel=385 est l'œil DROIT vu de face, celle à 448 l'œil GAUCHE
  (constaté à la mire : œil gauche vert = piste right_eyes d'alors).
  Les starts sont portés par face.py, la table est relative (0..63).

- Orientation interne des matrices (calée à la mire « calib » du 2026-07-11 :
  123 tête en bas quand le haut était flippé, E et F en miroir) : les matrices
  de la rangée HAUTE de la bouche sont montées À L'ENDROIT, celles de la
  rangée BASSE et des YEUX sont montées TÊTE-BÊCHE (rotation 180°) — logique
  de câblage en serpentin, le connecteur ressort du bon côté.
"""

MATRIX = 8  # matrices carrées 8x8

# Offset du bloc de 64 LED de chaque cellule (rangée, colonne) de la bouche,
# rangée 0 = haut, colonne 0 = gauche, vu de face.
MOUTH_CELL_OFFSETS = {
    (0, 0): 192, (0, 1): 256, (0, 2): 320,
    (1, 0): 128, (1, 1): 64, (1, 2): 0,
}
MOUTH_WIDTH = 24
MOUTH_HEIGHT = 16
# Rotation 180° du contenu d'une matrice, par zone (montage tête-bêche).
MOUTH_TOP_ROT180 = False
MOUTH_BOTTOM_ROT180 = True
EYE_ROT180 = True


class ImageMapping:

    def __init__(self, index_table):
        self.index_table = index_table
        self.height = len(index_table)
        self.width = len(index_table[0])

    @classmethod
    def mouth(cls):
        table = [[0] * MOUTH_WIDTH for _ in range(MOUTH_HEIGHT)]
        for y in range(MOUTH_HEIGHT):
            for x in range(MOUTH_WIDTH):
                offset = MOUTH_CELL_OFFSETS[(y // MATRIX, x // MATRIX)]
                rot180 = MOUTH_BOTTOM_ROT180 if y >= MATRIX else MOUTH_TOP_ROT180
                r, c = y % MATRIX, x % MATRIX
                if rot180:
                    r, c = MATRIX - 1 - r, MATRIX - 1 - c
                table[y][x] = offset + r * MATRIX + c
        return cls(table)

    @classmethod
    def eye(cls):
        table = [[0] * MATRIX for _ in range(MATRIX)]
        for y in range(MATRIX):
            for x in range(MATRIX):
                r, c = (MATRIX - 1 - y, MATRIX - 1 - x) if EYE_ROT180 else (y, x)
                table[y][x] = r * MATRIX + c
        return cls(table)

    def mapping(self, pixels, image, start_pixel):
        # Garde-fou : un PNG à la mauvaise taille écrirait hors zone (les yeux
        # partagent le strip avec la bouche et le corps).
        if len(image) != self.height or len(image[0]) != self.width:
            import logging
            logging.error("image %sx%s incompatible avec la table %sx%s",
                          len(image[0]), len(image), self.width, self.height)
            return
        for y in range(self.height):
            row = self.index_table[y]
            for x in range(self.width):
                pixels[row[x] + start_pixel] = image[y][x]
