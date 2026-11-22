"""Maquette des glitchs et micro-bugs du visage (docs/etudes/etude-visage.md, §11).
PAS du code de robot : elle sert à juger les effets à l'œil et à choisir.

Un glitch est un CALQUE : une petite fonction qui abîme l'image d'une zone (œil 8x8 ou
bouche 24x16) pendant quelques images, puis rend l'image intacte. Il ne connaît pas
l'expression en cours : il s'applique à n'importe laquelle.

Lancer depuis la racine du dépôt :
    .venv/bin/python docs/etudes/visage/maquette_glitchs.py
"""
from __future__ import annotations

import colorsys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import maquette_visage as m

ICI = Path(__file__).resolve().parent
IPS = 20  # images par seconde du robot (tick de 50 ms)


# ---------------------------------------------------------------------------------------
# Les effets. Chacun prend une image RGB (h, l, 3) et rend une image de même taille.
# ---------------------------------------------------------------------------------------
def pixel_chaud(img, rng, n=2):
    """n LED coincées en blanc, n'importe où dans la zone (y compris dans le noir)."""
    out = img.copy()
    for _ in range(n):
        out[rng.integers(img.shape[0]), rng.integers(img.shape[1])] = (255, 255, 235)
    return out


def pixel_mort(img, rng, n=3):
    """n LED éteintes DANS le dessin : le trait a un trou."""
    out = img.copy()
    ys, xs = np.nonzero(img.sum(2) > 60)
    for i in rng.choice(len(ys), size=min(n, len(ys)), replace=False):
        out[ys[i], xs[i]] = 0
    return out


def ligne_decalee(img, rng, lignes=1, dx=2):
    """Une ou deux lignes glissent de côté : la déchirure d'écran."""
    out = img.copy()
    y0 = rng.integers(0, img.shape[0] - lignes + 1)
    out[y0:y0 + lignes] = np.roll(img[y0:y0 + lignes], dx * rng.choice([-1, 1]), axis=1)
    return out


def couleurs_separees(img, rng=None, dx=1):
    """Le vert part d'un côté, rouge et bleu de l'autre : frange colorée de part et d'autre."""
    out = img.copy()
    out[..., 1] = np.roll(img[..., 1], -dx, axis=1)
    out[..., 0] = np.roll(img[..., 0], dx, axis=1)
    out[..., 2] = np.roll(img[..., 2], dx, axis=1)
    return out


def saut(img, rng=None, dy=1):
    """Toute la zone saute d'une LED vers le haut ou le bas (image qui « roule »)."""
    return np.roll(img, dy, axis=0)


def baisse(img, rng=None, k=0.3):
    """La zone tombe à 30 % : un œil qui faiblit."""
    return (img * k).astype(np.uint8)


def neige(img, rng, n=5):
    """Quelques LED de couleurs vives au hasard, une image seulement."""
    out = img.copy()
    palette = [(255, 60, 140), (255, 150, 0), (60, 255, 90), (255, 255, 235)]
    for _ in range(n):
        out[rng.integers(img.shape[0]), rng.integers(img.shape[1])] = palette[rng.integers(len(palette))]
    return out


def derive(img, rng=None, tour=0.28):
    """La couleur tourne (cyan -> violet/magenta) puis revient : « ce n'est plus tout à fait lui »."""
    out = img.astype(float) / 255
    plat = out.reshape(-1, 3)
    for i, (r, g, b) in enumerate(plat):
        if r + g + b > 0.1:
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            plat[i] = colorsys.hsv_to_rgb((h + tour) % 1, s, v)
    return (plat.reshape(img.shape) * 255).astype(np.uint8)


def balayage(img, rng=None, ligne=0):
    """Une ligne sombre qui descend, comme un vieil écran."""
    out = img.copy()
    out[ligne % img.shape[0]] = out[ligne % img.shape[0]] // 5
    return out


def bloc(img, rng, cote=3):
    """Un petit carré recopié au mauvais endroit : la corruption de mémoire."""
    out = img.copy()
    h, l = img.shape[:2]
    c = min(cote, h, l)
    y1, x1 = rng.integers(0, h - c + 1), rng.integers(0, l - c + 1)
    y2, x2 = rng.integers(0, h - c + 1), rng.integers(0, l - c + 1)
    out[y2:y2 + c, x2:x2 + c] = img[y1:y1 + c, x1:x1 + c]
    return out


# ---------------------------------------------------------------------------------------
# Composition d'un visage complet avec un effet par zone
# ---------------------------------------------------------------------------------------
def zones(v: m.Visage):
    return [m.dessiner_oeil(v.oeil_g), m.dessiner_oeil(v.oeil_d, miroir=True), m.dessiner_bouche(v.bouche)]


def assembler(z) -> np.ndarray:
    c = np.zeros((28, 28, 3), np.uint8)
    c[1:9, 3:11], c[1:9, 17:25], c[11:27, 2:26] = z
    return c


def avec(v: m.Visage, effet, ou=(0, 1, 2), graine=3, **kw) -> np.ndarray:
    rng = np.random.default_rng(graine)
    z = zones(v)
    for i in ou:
        z[i] = effet(z[i], rng, **kw)
    return assembler(z)


REPOS = m.VOCABULAIRE["repos"]
JOIE = m.VOCABULAIRE["joie"]

# Le catalogue : (nom, ce que voit le public, images successives du glitch)
CATALOGUE = [
    ("pixel chaud", "une ou deux LED blanches hors du dessin", [avec(REPOS, pixel_chaud, ou=(2,), n=2), avec(REPOS, pixel_chaud, ou=(0,), n=1, graine=5)]),
    ("pixel mort", "un trou dans le trait", [avec(REPOS, pixel_mort, ou=(2,), n=4), avec(REPOS, pixel_mort, ou=(1,), n=3, graine=8)]),
    ("ligne décalée", "une ligne glisse de côté", [avec(REPOS, ligne_decalee, ou=(0,), dx=2, graine=4), avec(JOIE, ligne_decalee, ou=(2,), lignes=2, dx=3, graine=11)]),
    ("couleurs séparées", "frange verte et bleue", [avec(REPOS, couleurs_separees), avec(JOIE, couleurs_separees, dx=2)]),
    ("saut", "un œil sursaute d'une LED", [avec(REPOS, saut, ou=(1,), dy=-1), avec(REPOS, saut, ou=(0, 1), dy=1)]),
    ("baisse", "un œil faiblit", [avec(REPOS, baisse, ou=(0,)), avec(REPOS, baisse, ou=(2,), k=0.2)]),
    ("neige", "éclats de couleur, une image", [avec(REPOS, neige, ou=(2,), n=6), avec(REPOS, neige, ou=(0, 1), n=3, graine=9)]),
    ("dérive", "la couleur tourne au violet", [avec(REPOS, derive, tour=0.12), avec(REPOS, derive, tour=0.28)]),
    ("balayage", "une ligne sombre descend", [avec(JOIE, balayage, ou=(2,), ligne=6), avec(JOIE, balayage, ou=(2,), ligne=9)]),
    ("bloc", "un morceau au mauvais endroit", [avec(JOIE, bloc, ou=(2,), cote=4, graine=6), avec(REPOS, bloc, ou=(0,), cote=3, graine=2)]),
    ("lapsus", "une image d'une AUTRE émotion", [m.vignette(m.VOCABULAIRE["colère"]), m.vignette(m.VOCABULAIRE["amour"])]),
    ("œil en retard", "un seul œil cligne", [assembler([zones(REPOS)[0], m.dessiner_oeil(m.replace(REPOS.oeil_d, hauteur=1.8, arrondi=0.6, pupille=0), miroir=True), zones(REPOS)[2]])] * 2),
]


def planche(sortie: Path) -> None:
    e = 7
    L, H = 28 * e + 8, 28 * e + 8
    pl = Image.new("RGB", (330 + 3 * L, 34 + len(CATALOGUE) * H), (26, 26, 26))
    d = ImageDraw.Draw(pl)
    d.text((8, 8), "Micro-bugs du visage : image normale, puis deux exemples du glitch (il dure 1 à 6 images)", fill=(255, 255, 255), font=m.POLICE)
    base = {id(REPOS): m.vignette(REPOS)}
    for i, (nom, vu, images) in enumerate(CATALOGUE):
        y = 34 + i * H
        d.text((8, y + 60), nom, fill=(255, 255, 255), font=m.POLICE)
        d.text((8, y + 82), vu, fill=(170, 170, 170), font=m.POLICE)
        for j, c in enumerate([base[id(REPOS)]] + images):
            pl.paste(m.agrandir(c, e), (330 + j * L, y))
    pl.save(sortie)
    print("écrit", sortie.relative_to(m.RACINE), pl.size)


# ---------------------------------------------------------------------------------------
# L'animation : la « tension » monte, les micro-bugs se rapprochent, le bug éclate, il se remet.
# ---------------------------------------------------------------------------------------
MICRO = [  # (effet, zones possibles, durée en images, kwargs)
    (pixel_chaud, [(0,), (1,), (2,)], 2, {"n": 1}),
    (pixel_mort, [(2,), (0,)], 3, {"n": 3}),
    (ligne_decalee, [(0,), (1,), (2,)], 2, {"dx": 2}),
    (couleurs_separees, [(0, 1, 2), (2,)], 2, {}),
    (saut, [(0,), (1,)], 1, {"dy": -1}),
    (baisse, [(0,), (1,)], 3, {}),
    (neige, [(2,)], 1, {"n": 4}),
]


def animation(sortie: Path) -> None:
    rng = np.random.default_rng(12)
    images = []
    # tension par seconde : calme, ça monte, le bug, la retombée
    plan = [("calme", 3.0, 0.05), ("ça monte", 4.0, None), ("BUG JOUÉ", 2.5, 1.0), ("il se remet", 3.5, None), ("calme", 1.5, 0.05)]
    en_cours, reste = None, 0
    for etape, duree, tension_fixe in plan:
        n = round(duree * IPS)
        for i in range(n):
            if etape == "ça monte":
                tension = 0.05 + 0.75 * i / n
            elif etape == "il se remet":
                tension = 0.6 * (1 - i / n) ** 2
            else:
                tension = tension_fixe
            z = zones(REPOS)
            if etape == "BUG JOUÉ":
                # le grand bug : tout se déchire, la couleur dérive, de la neige partout
                for k in range(3):
                    z[k] = ligne_decalee(z[k], rng, lignes=2 if k == 2 else 1, dx=int(rng.integers(1, 4)))
                    if rng.random() < 0.6:
                        z[k] = couleurs_separees(z[k], dx=int(rng.integers(1, 3)))
                    if rng.random() < 0.5:
                        z[k] = neige(z[k], rng, n=3)
                if i > n * 0.6:
                    z = [derive(x, tour=0.28) for x in z]
            else:
                # micro-bugs : au calme un toutes les ~8 s, à tension 0,8 plus de deux par seconde
                if en_cours is None and rng.random() < (0.006 + 0.14 * tension ** 2):
                    effet, ou, dur, kw = MICRO[rng.integers(len(MICRO))]
                    en_cours, reste = (effet, ou[rng.integers(len(ou))], kw, int(rng.integers(1 << 30))), dur
                if en_cours is not None:
                    effet, ou, kw, graine = en_cours
                    g = np.random.default_rng(graine)
                    for k in ou:
                        z[k] = effet(z[k], g, **kw)
                    reste -= 1
                    if reste <= 0:
                        en_cours = None
            im = m.agrandir(assembler(z), 9)
            dessin = ImageDraw.Draw(im)
            dessin.text((6, 2), etape, fill=(200, 200, 200), font=m.POLICE)
            dessin.rectangle((6, 244, 6 + int(240 * tension), 248), fill=(255, 150, 0))  # jauge de tension
            images.append(im)
    images[0].save(sortie, save_all=True, append_images=images[1:], duration=1000 // IPS, loop=0)
    print("écrit", sortie.relative_to(m.RACINE), len(images), "images")


if __name__ == "__main__":
    planche(ICI / "glitchs-catalogue.png")
    animation(ICI / "glitchs-tension.gif")
