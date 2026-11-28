"""Pictogrammes du visage v2 (docs/etudes/etude-visage.md, §12) — PAS du code de robot.

Règle de style, la même que pour les émotions : un trait néon de 2 LED, une couleur par
image (deux au plus), fond noir, formes simples. Les pictos de bouche (24x16) sont dessinés
8 fois trop fin puis moyennés, comme le reste de la maquette ; les yeux-symboles (8x8) sont
trop petits pour ça : ils se dessinent LED par LED, comme une lettre.

Lancer depuis la racine du dépôt :
    .venv/bin/python docs/etudes/visage/pictos.py
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import maquette_visage as m

ICI = Path(__file__).resolve().parent
S = 8          # sur-échantillonnage
L, H = 24, 16  # bouche
T = 1.7        # épaisseur du trait, en LED

CYAN, AMBRE, ROSE, ROUGE, BLANC, VERT, BLEU = m.CYAN, m.AMBRE, m.ROSE, m.ROUGE, m.BLANC, m.VERT, m.BLEU_PALE
OR = (255, 200, 40)


class Toile:
    """Une zone 24x16 où l'on dessine en coordonnées LED (flottantes), plusieurs couleurs."""

    def __init__(self, l: int = L, h: int = H):
        self.l, self.h = l, h
        self.im = Image.new("RGB", (l * S, h * S))
        self.d = ImageDraw.Draw(self.im)

    def _p(self, pts):
        return [(x * S, y * S) for x, y in pts]

    def trait(self, pts, c, t: float = T, ferme: bool = False):
        pts = list(pts) + ([pts[0]] if ferme else [])
        self.d.line(self._p(pts), fill=c, width=round(t * S), joint="curve")
        for x, y in pts:  # bouts ronds
            r = t * S / 2
            self.d.ellipse((x * S - r, y * S - r, x * S + r, y * S + r), fill=c)

    def cercle(self, cx, cy, r, c, t: float = T, plein: bool = False):
        b = ((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S)
        self.d.ellipse(b, fill=c if plein else None, outline=c, width=round(t * S))

    def arc(self, cx, cy, r, a0, a1, c, t: float = T):
        self.d.arc(((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S), a0, a1, fill=c, width=round(t * S))

    def plein(self, pts, c):
        self.d.polygon(self._p(pts), fill=c)

    def rect(self, x0, y0, x1, y1, c, plein: bool = False, t: float = T):
        self.d.rectangle((x0 * S, y0 * S, x1 * S, y1 * S), fill=c if plein else None, outline=c, width=round(t * S))

    def texte(self, s: str, x: int, y: int, c, e: int = 1):
        """Police 3x5 (chiffres et quelques lettres), posée sur la grille des LED : nette."""
        for ch in s:
            g = POLICE_3X5.get(ch)
            if g is None:
                x += 2 * e
                continue
            for j, ligne in enumerate(g):
                for i, v in enumerate(ligne):
                    if v == "X":
                        self.d.rectangle(((x + i * e) * S, (y + j * e) * S, (x + (i + 1) * e) * S - 1, (y + (j + 1) * e) * S - 1), fill=c)
            x += (len(g[0]) + 1) * e

    def rgb(self) -> np.ndarray:
        a = np.asarray(self.im).astype(float).reshape(self.h, S, self.l, S, 3).mean(axis=(1, 3))
        return a.clip(0, 255).astype(np.uint8)


POLICE_3X5 = {
    "0": ["XXX", "X.X", "X.X", "X.X", "XXX"], "1": [".X.", "XX.", ".X.", ".X.", "XXX"],
    "2": ["XXX", "..X", "XXX", "X..", "XXX"], "3": ["XXX", "..X", "XXX", "..X", "XXX"],
    "4": ["X.X", "X.X", "XXX", "..X", "..X"], "5": ["XXX", "X..", "XXX", "..X", "XXX"],
    "6": ["XXX", "X..", "XXX", "X.X", "XXX"], "7": ["XXX", "..X", ".X.", ".X.", ".X."],
    "8": ["XXX", "X.X", "XXX", "X.X", "XXX"], "9": ["XXX", "X.X", "XXX", "..X", "XXX"],
    "/": ["..X", "..X", ".X.", "X..", "X.."], "?": ["XXX", "..X", ".XX", "...", ".X."],
    "!": ["X", "X", "X", ".", "X"], "Z": ["XXX", "..X", ".X.", "X..", "XXX"],
    "O": ["XXX", "X.X", "X.X", "X.X", "XXX"], "K": ["X.X", "XX.", "X..", "XX.", "X.X"],
    "U": ["X.X", "X.X", "X.X", "X.X", "XXX"], "I": ["XXX", ".X.", ".X.", ".X.", "XXX"],
    "N": ["X.X", "XXX", "XXX", "X.X", "X.X"], "%": ["X.X", "..X", ".X.", "X..", "X.X"],
    "#": [".X.X.", "XXXXX", ".X.X.", "XXXXX", ".X.X."], "*": ["X.X", ".X.", "X.X", "...", "..."],
}


# ---------------------------------------------------------------------------------------
# Pictos de BOUCHE (24x16). Chacun rend une image RGB ; `t` (0..1) anime quand ça a un sens.
# ---------------------------------------------------------------------------------------
def ampoule(t=0.0):
    z = Toile()
    z.cercle(12, 6, 4.6, AMBRE)
    z.rect(10.2, 11.2, 13.8, 13.6, AMBRE, plein=True)
    if t > 0.5:  # elle s'allume : rayons
        for a in (-150, -120, -60, -30):
            dx, dy = math.cos(math.radians(a)), math.sin(math.radians(a))
            z.trait([(12 + 6.6 * dx, 6 + 6.6 * dy), (12 + 8.6 * dx, 6 + 8.6 * dy)], OR, 1.2)
        z.cercle(12, 6, 2.2, OR, plein=True)
    return z.rgb()


def boussole(t=0.0):
    z = Toile()
    z.cercle(12, 8, 7.0, CYAN, 1.4)
    a = math.radians(-90 + 360 * t)
    z.trait([(12, 8), (12 + 5.2 * math.cos(a), 8 + 5.2 * math.sin(a))], ROUGE, 1.8)
    z.trait([(12, 8), (12 - 3.6 * math.cos(a), 8 - 3.6 * math.sin(a))], BLANC, 1.4)
    return z.rgb()


def fleche(sens="droite", c=VERT):
    z = Toile()
    if sens == "haut":
        z.trait([(12, 14), (12, 2.5)], c)
        z.trait([(7, 7.5), (12, 2.5), (17, 7.5)], c)
    else:
        z.trait([(3.5, 8), (20, 8)], c)
        z.trait([(15, 3), (20, 8), (15, 13)], c)
    a = z.rgb()
    return a[:, ::-1] if sens == "gauche" else a


def wifi(t=1.0, barre=False):
    z = Toile()
    for k, r in enumerate((3.2, 6.4, 9.6)):
        if t * 3 > k:
            z.arc(12, 13.5, r, 228, 312, CYAN, 1.6)
    z.cercle(12, 13.2, 1.0, CYAN, plein=True)
    if barre:
        z.trait([(5, 2.5), (19, 14)], ROUGE, 1.8)
    return z.rgb()


def batterie(t=0.2):
    z = Toile()
    c = ROUGE if t < 0.25 else VERT
    z.rect(3, 4, 19, 12.5, BLANC, t=1.3)
    z.rect(19.6, 6.5, 21.4, 10, BLANC, plein=True)
    if t > 0.02:
        z.rect(4.8, 5.8, 4.8 + 12.4 * t, 10.7, c, plein=True)
    return z.rgb()


def sablier(t=0.0):
    z = Toile()
    z.trait([(7, 2), (17, 2)], AMBRE)
    z.trait([(7, 14), (17, 14)], AMBRE)
    z.trait([(7.5, 2.5), (12, 8), (16.5, 2.5)], AMBRE, 1.3)
    z.trait([(7.5, 13.5), (12, 8), (16.5, 13.5)], AMBRE, 1.3)
    h = 3.2 * t
    z.plein([(12 - h, 13.4), (12 + h, 13.4), (12, 13.4 - h)], OR)
    return z.rgb()


def mise_a_jour(n=3, total=47):
    z = Toile()
    z.texte(f"{n}/{total}", 12 - 2 * len(f"{n}/{total}"), 1, CYAN)
    z.rect(1.5, 9, 22.5, 13.5, CYAN, t=1.2)
    z.rect(2.8, 10.2, 2.8 + 18.4 * n / total, 12.3, CYAN, plein=True)
    return z.rgb()


def erreur_404():
    z = Toile()
    z.texte("404", 3, 3, ROUGE, e=2)
    return z.rgb()


def nuage(t=0.0, fleche_haut=False):
    z = Toile()
    for cx, cy, r in ((8, 10.5, 3.4), (12.5, 8, 4.4), (17, 10.5, 3.2)):
        z.cercle(cx, cy, r, BLANC, plein=True)
    z.rect(8, 10, 17, 13.6, BLANC, plein=True)
    if fleche_haut:  # l'envoi vers le nuage : l'âme monte
        y = 13.5 - 6 * t
        z.trait([(12.5, y + 2.5), (12.5, y - 1.5)], CYAN, 1.5)
        z.trait([(10.5, y + 0.5), (12.5, y - 1.5), (14.5, y + 0.5)], CYAN, 1.5)
    return z.rgb()


def note(t=0.0):
    z = Toile()
    dy = -1.0 if t > 0.5 else 0.0
    z.cercle(9, 11.5 + dy, 2.3, ROSE, plein=True)
    z.cercle(16, 10 + dy, 2.3, ROSE, plein=True)
    z.trait([(11, 11.5 + dy), (11, 3.5 + dy), (18, 2 + dy), (18, 10 + dy)], ROSE, 1.4)
    return z.rgb()


def coeur(t=1.0, c=ROSE):
    z = Toile()
    xs, ys = np.meshgrid((np.arange(L * S) + 0.5) / S, (np.arange(H * S) + 0.5) / S)
    k = 5.6 + 1.1 * t
    u, v = (xs - 12) / k, -(ys - 7.4) / k
    masque = (u * u + v * v - 1) ** 3 - u * u * v ** 3 < 0
    a = masque.reshape(H, S, L, S).mean(axis=(1, 3))
    return (a[..., None] * np.array(c)).astype(np.uint8)


def bisou(t=0.0):
    z = Toile()
    o = 1.2 * t
    z.trait([(5, 8), (9, 5 - o), (12, 6.4 - o), (15, 5 - o), (19, 8)], ROSE, 1.8)
    z.trait([(5, 8), (12, 12.5 + o), (19, 8)], ROSE, 2.0)
    return z.rgb()


def attention(t=1.0):
    z = Toile()
    c = AMBRE if t > 0.5 else (120, 70, 0)
    z.trait([(12, 1.5), (21.5, 14), (2.5, 14)], c, 1.6, ferme=True)
    z.rect(11.2, 5.5, 12.8, 10, c, plein=True)
    z.rect(11.2, 11.2, 12.8, 12.6, c, plein=True)
    return z.rgb()


def porte(t=0.0):
    z = Toile()
    z.arc(12, 7, 5.5, 180, 360, OR, 1.5)
    z.trait([(6.5, 7), (6.5, 15)], OR, 1.5)
    z.trait([(17.5, 7), (17.5, 15)], OR, 1.5)
    if t > 0.5:  # elle s'entrouvre : de la lumière
        z.rect(8.2, 5.5, 15.8, 15, BLANC, plein=True)
    else:
        z.cercle(15, 10.5, 0.8, OR, plein=True)
    return z.rgb()


def fantome(t=0.0):
    """L'âme qui s'échappe (le fantôme qui sort de la bouche, dans la grammaire du manga)."""
    z = Toile()
    dy = -2.5 * t
    z.cercle(12, 7 + dy, 4.6, BLANC, plein=True)
    z.rect(7.4, 7 + dy, 16.6, 13.5 + dy, BLANC, plein=True)
    for cx in (9, 12, 15):
        z.cercle(cx, 13.8 + dy, 1.15, (0, 0, 0), plein=True)
    for cx in (10.3, 13.7):
        z.cercle(cx, 6.8 + dy, 0.95, (0, 0, 0), plein=True)
    return z.rgb()


def zzz(t=0.0):
    z = Toile()
    z.texte("Z", 4, 9, BLEU)
    if t > 0.33:
        z.texte("Z", 10, 5, BLEU)
    if t > 0.66:
        z.texte("Z", 16, 1, BLEU)
    return z.rgb()


def coche(c=VERT):
    """Oui : une coche, lisible de loin et sans langue."""
    z = Toile()
    z.trait([(5, 8.5), (10, 13.5), (19.5, 2.5)], c, 2.2)
    return z.rgb()


def croix(c=ROUGE):
    """Non : une croix."""
    z = Toile()
    z.trait([(6.5, 2.5), (17.5, 13.5)], c, 2.2)
    z.trait([(17.5, 2.5), (6.5, 13.5)], c, 2.2)
    return z.rgb()


def mot(s: str, c=CYAN):
    z = Toile()
    e = 2 if len(s) <= 3 else 1
    larg = sum((len(POLICE_3X5.get(ch, ["..."])[0]) + 1) * e for ch in s) - e
    z.texte(s, (L - larg) // 2, (H - 5 * e) // 2, c, e)
    return z.rgb()


# ---------------------------------------------------------------------------------------
# Yeux-symboles (8x8), dessinés LED par LED. '#' = couleur principale, 'o' = seconde couleur.
# ---------------------------------------------------------------------------------------
YEUX = {
    "spirale": (CYAN, None, ["XXXXXXX.", "X.....X.", "X.XXX.X.", "X.X.X.X.", "X.X...X.", "X.XXXXX.", "X.......", "XXXXXXXX"]),
    "croix": (CYAN, None, ["XX....XX", "XXX..XXX", ".XXXXXX.", "..XXXX..", "..XXXX..", ".XXXXXX.", "XXX..XXX", "XX....XX"]),
    "etoile": (OR, None, ["...XX...", "...XX...", "XXXXXXXX", ".XXXXXX.", "..XXXX..", ".XXXXXX.", ".XX..XX.", "XX....XX"]),
    "ange": (CYAN, OR, [".oooooo.", "........", "..XXXX..", ".XXXXXX.", ".XX..XX.", ".XX..XX.", ".XXXXXX.", "..XXXX.."]),
    "diable": (ROUGE, None, ["X......X", "XX....XX", "XXXXXXXX", "XXXXXXXX", "XXX..XXX", "XXX..XXX", ".XXXXXX.", "..XXXX.."]),
    "interro": (AMBRE, None, [".XXXXXX.", "XX....XX", "......XX", "....XXX.", "...XX...", "...XX...", "........", "...XX..."]),
    "exclam": (AMBRE, None, ["...XX...", "...XX...", "...XX...", "...XX...", "...XX...", "........", "...XX...", "...XX..."]),
    "ennui": (CYAN, None, ["........", "........", "........", "XXXXXXXX", "XXXX..XX", "XXXX..XX", ".XXXXXX.", "........"]),
}


def oeil_symbole(nom: str, miroir: bool = False) -> np.ndarray:
    c1, c2, lignes = YEUX[nom]
    a = np.zeros((8, 8, 3), np.uint8)
    for y, ligne in enumerate(lignes):
        for x, ch in enumerate(ligne):
            if ch == "X":
                a[y, x] = c1
            elif ch == "o":
                a[y, x] = c2
    return a[:, ::-1] if miroir else a


# ---------------------------------------------------------------------------------------
# La planche de propositions : trois familles, plus le texte.
# ---------------------------------------------------------------------------------------
def visage(yeux, bouche) -> np.ndarray:
    """`yeux` : nom d'un œil-symbole ou d'une expression du vocabulaire (ses yeux à elle)."""
    c = np.zeros((28, 28, 3), np.uint8)
    if yeux in YEUX:
        og, od = oeil_symbole(yeux), oeil_symbole(yeux, miroir=True)
    else:
        v = m.VOCABULAIRE[yeux]
        og, od = m.dessiner_oeil(v.oeil_g), m.dessiner_oeil(v.oeil_d, miroir=True)
    c[1:9, 3:11], c[1:9, 17:25], c[11:27, 2:26] = og, od, bouche
    return c


def bouche_de(nom: str) -> np.ndarray:
    return m.dessiner_bouche(m.VOCABULAIRE[nom].bouche)


FAMILLES = [
    ("LUI — les symboles de bande dessinée (lisibles de loin, sans mot)", [
        ("étourdi", visage("spirale", bouche_de("surprise"))),
        ("K.O.", visage("croix", bouche_de("triste"))),
        ("des étoiles plein les yeux", visage("etoile", bouche_de("joie"))),
        ("une idée !", visage("émerveillé", ampoule(1))),
        ("hein ?", visage("interro", bouche_de("réfléchit"))),
        ("il chante", visage("joie", note(0))),
        ("ennui", visage("ennui", bouche_de("réfléchit"))),
        ("bisou", visage("amour", bisou(0))),
        ("grand amour", visage("amour", coeur(1))),
        ("dodo", visage("dodo", zzz(1))),
        ("gros mot", visage("colère", mot("#!*", ROUGE))),
    ]),
    ("SA MACHINE — une âme hébergée par une start-up d'éternité en faillite", [
        ("mise à jour 3/47", visage("ennui", mise_a_jour(3, 47))),
        ("âme introuvable", visage("croix", erreur_404())),
        ("pas de réseau", visage("interro", wifi(1, barre=True))),
        ("il cherche le réseau", visage("réfléchit", wifi(0.67))),
        ("batterie faible", visage("triste", batterie(0.15))),
        ("patientez", visage("ennui", sablier(0.6))),
        ("envoi dans le nuage", visage("ange", nuage(0.5, fleche_haut=True))),
        ("attention", visage("exclam", attention(1))),
        ("l'âme s'échappe", visage("croix", fantome(0.3))),
    ]),
    ("SA QUÊTE — il cherche un endroit, les passants savent où", [
        ("la boussole s'affole", visage("spirale", boussole(0.15))),
        ("c'est par là ! (le passant montre)", visage("émerveillé", fleche("droite"))),
        ("par là ?", visage("interro", fleche("gauche", AMBRE))),
        ("tout droit", visage("joie", fleche("haut"))),
        ("la porte", visage("etoile", porte(1))),
        ("mode ange", visage("ange", bouche_de("joie"))),
        ("mode diable", visage("diable", m.dessiner_bouche(m.replace(m.VOCABULAIRE["malice"].bouche, couleur=ROUGE)))),
        ("oui", visage("joie", coche())),
        ("non", visage("colère", croix())),
    ]),
]


def planche(sortie: Path) -> None:
    e, col = 7, 11
    Lc, Hc = 28 * e + 10, 28 * e + 30
    haut = sum(34 + -(-len(cases) // col) * Hc for _, cases in FAMILLES)
    pl = Image.new("RGB", (col * Lc + 8, haut + 10), (26, 26, 26))
    d = ImageDraw.Draw(pl)
    y = 6
    for titre, cases in FAMILLES:
        d.text((8, y + 6), titre, fill=(255, 255, 255), font=m.POLICE)
        y += 34
        for i, (nom, c) in enumerate(cases):
            x = 8 + (i % col) * Lc
            yy = y + (i // col) * Hc
            pl.paste(m.agrandir(c, e), (x, yy + 20))
            d.text((x, yy + 2), nom, fill=(200, 200, 200), font=m.POLICE)
        y += -(-len(cases) // col) * Hc
    pl.save(sortie)
    print("écrit", sortie.relative_to(m.RACINE), pl.size)


if __name__ == "__main__":
    planche(ICI / "pictos-propositions.png")
