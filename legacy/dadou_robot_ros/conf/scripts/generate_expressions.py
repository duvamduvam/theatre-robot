#!/usr/bin/env python3
"""Générateur des visuels d'expressions « néon » (repos + émotions + glitch).

Produit des PNG RGB aux formats EXACTS attendus par robot/actions/face.py :
 - bouche : 24x16 (3x2 matrices 8x8 ; le câblage serpentin réel est encodé
   dans la table d'ImageMapping, les PNG se dessinent TELS QUE VUS de face) ;
 - œil    : 8x8.
Le nom de visuel référencé dans expressions.json = nom de fichier AVEC extension
(Face.load_visuals indexe par basename), et le dictionnaire visuals est PARTAGÉ
entre bouches et yeux : les basenames doivent être uniques (d'où le préfixe oeil-).

Déterministe (seed fixe) : relancer le script régénère exactement les mêmes
frames de glitch — indispensable pour comparer avant/après en revue.

Usage : python3 conf/scripts/generate_expressions.py   (depuis la racine du repo)
Écrit dans medias/visuals/{mouth,eye}/ et fusionne les nouvelles expressions
dans json/expressions.json (n'écrase jamais une entrée existante).
"""

import json
import math
import os
import random

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MOUTH_DIR = os.path.join(REPO, "medias", "visuals", "mouth")
EYE_DIR = os.path.join(REPO, "medias", "visuals", "eye")
EXPR_JSON = os.path.join(REPO, "json", "expressions.json")

MW, MH = 24, 16   # bouche
EW, EH = 8, 8     # œil

# Palette néon : valeurs hautes exprès — sur LED, les demi-teintes paraissent éteintes.
CYAN = (0, 255, 255)
CYAN_DIM = (0, 90, 110)
BLEU = (0, 90, 255)
BLEU_NUIT = (0, 20, 60)
MAGENTA = (255, 0, 150)
ROSE = (255, 60, 120)
JAUNE = (255, 190, 0)
AMBRE = (255, 140, 0)
ORANGE = (255, 70, 0)
ROUGE = (255, 0, 0)
VERT = (60, 255, 0)
VIOLET = (170, 0, 255)
BLANC = (255, 255, 255)
OFF = (0, 0, 0)

# Pixels de glitch : couleurs volontairement disparates (effet « signal cassé »).
GLITCH_COLORS = [CYAN, MAGENTA, VERT, JAUNE, BLANC, VIOLET, ORANGE]

rng = random.Random(42)  # seed fixe = sortie reproductible


def blank(w, h):
    return [[OFF for _ in range(w)] for _ in range(h)]


def put(g, x, y, c):
    """Pose un pixel en ignorant silencieusement les débordements (traits d'arcs)."""
    if 0 <= y < len(g) and 0 <= x < len(g[0]):
        g[y][x] = c


def scale(c, f):
    return tuple(int(v * f) for v in c)


def save(g, folder, name):
    im = Image.new("RGB", (len(g[0]), len(g)))
    im.putdata([tuple(px) for row in g for px in row])
    im.save(os.path.join(folder, name))
    return name


def from_ascii(art, colors):
    """Grille depuis un dessin ASCII ('.' = éteint), pour les motifs fixes."""
    rows = [r for r in art.strip("\n").split("\n")]
    return [[colors.get(ch, OFF) for ch in row] for row in rows]


def scatter(g, count, colors, protect=()):
    """Éparpille `count` pixels aléatoires (le cœur de l'effet glitch)."""
    h, w = len(g), len(g[0])
    for _ in range(count):
        x, y = rng.randrange(w), rng.randrange(h)
        if (x, y) not in protect:
            g[y][x] = rng.choice(colors)
    return g


# ---------------------------------------------------------------- YEUX 8x8

def eye_disk(color, pupil, pupil_pos=(3, 3), lid=0):
    """Disque plein avec pupille 2x2 ; lid = rangées mangées par la paupière."""
    g = blank(EW, EH)
    for y in range(EH):
        for x in range(EW):
            if (x - 3.5) ** 2 + (y - 3.5) ** 2 <= 12.5 and y >= lid:
                g[y][x] = color
    px, py = pupil_pos
    for dy in range(2):
        for dx in range(2):
            put(g, px + dx, py + dy, pupil)
    return g


def gen_eyes():
    n = {}
    # Repos néon : pupille bleu nuit qui dérive + clignement (2 lignes cyan).
    n["oeil-neon-centre.png"] = eye_disk(CYAN, BLEU_NUIT, (3, 3))
    n["oeil-neon-gauche.png"] = eye_disk(CYAN, BLEU_NUIT, (1, 3))
    n["oeil-neon-droit.png"] = eye_disk(CYAN, BLEU_NUIT, (5, 3))
    clign = blank(EW, EH)
    for x in range(EW):
        clign[3][x] = CYAN
        clign[4][x] = CYAN_DIM
    n["oeil-neon-clign.png"] = clign

    # Repos braise : ambre chaud, variante blasée (paupière qui tombe).
    n["oeil-braise.png"] = eye_disk(AMBRE, (80, 20, 0), (3, 3))
    n["oeil-braise-blase.png"] = eye_disk(AMBRE, (80, 20, 0), (3, 4), lid=3)

    # Repos glitch : violet calme, puis l'œil « se casse ».
    n["oeil-violet.png"] = eye_disk(VIOLET, (30, 0, 50), (3, 3))
    for i in (1, 2):
        g = eye_disk(VIOLET, (30, 0, 50), (3, 3))
        scatter(g, 10 + 4 * i, GLITCH_COLORS)
        n["oeil-violet-glitch{}.png".format(i)] = g

    # Joie : chevron ^ jaune, pointes blanches.
    n["oeil-joie.png"] = from_ascii("""
........
...WW...
..JWWJ..
.JJ..JJ.
JJ....JJ
J......J
........
........""", {"J": JAUNE, "W": BLANC})

    # Colère : sourcil-triangle rouge, arête orange. gauche/droit en miroir
    # pour que les pentes convergent vers le centre du visage (air fâché).
    droit = from_ascii("""
O.......
RO......
RRO.....
RRRO....
RRRRO...
RRRRRO..
RRRRRR..
........""", {"R": ROUGE, "O": ORANGE})
    n["oeil-colere-droit.png"] = droit
    n["oeil-colere-gauche.png"] = [list(reversed(r)) for r in droit]
    flash = blank(EW, EH)
    for y in range(EH):
        for x in range(EW):
            if (x - 3.5) ** 2 + (y - 3.5) ** 2 <= 12.5:
                flash[y][x] = BLANC
    n["oeil-colere-flash.png"] = flash

    # Tristesse : paupière tombante bleue + larme cyan qui descend (3 frames).
    base = eye_disk(BLEU, BLEU_NUIT, (3, 4), lid=2)
    n["oeil-triste.png"] = base
    for i, ty in enumerate((5, 6, 7), start=1):
        g = [row[:] for row in base]
        put(g, 2, ty, CYAN)
        if ty < 7:
            put(g, 2, ty + 1, scale(CYAN, 0.4))  # traînée de la goutte
        n["oeil-triste-larme{}.png".format(i)] = g

    # Surprise : anneau blanc qui s'élargit, pupille minuscule.
    s1 = blank(EW, EH)
    for y in range(EH):
        for x in range(EW):
            d = (x - 3.5) ** 2 + (y - 3.5) ** 2
            if 4 <= d <= 8:
                s1[y][x] = BLANC
    put(s1, 3, 3, CYAN), put(s1, 4, 3, CYAN), put(s1, 3, 4, CYAN), put(s1, 4, 4, CYAN)
    n["oeil-surprise1.png"] = s1
    s2 = blank(EW, EH)
    for y in range(EH):
        for x in range(EW):
            d = (x - 3.5) ** 2 + (y - 3.5) ** 2
            if 9 <= d <= 14:
                s2[y][x] = BLANC
    put(s2, 3, 3, CYAN), put(s2, 4, 3, CYAN), put(s2, 3, 4, CYAN), put(s2, 4, 4, CYAN)
    n["oeil-surprise2.png"] = s2

    # Glitch total : l'œil n'est plus que des débris de pixels.
    for i in (1, 2, 3):
        g = blank(EW, EH)
        scatter(g, 14, GLITCH_COLORS)
        n["oeil-glitch{}.png".format(i)] = g

    # Mire œil : « F » cyan (asymétrique sur les deux axes) + pixel rouge en (0,0).
    n["oeil-calib.png"] = from_ascii("""
R.......
.CCCC...
.C......
.CCC....
.C......
.C......
........
........""", {"C": CYAN, "R": ROUGE})

    # Amour : cœurs magenta, grand et petit (battement).
    n["oeil-coeur.png"] = from_ascii("""
.MM..MM.
MMMMMMMM
MRMMMMMM
MMMMMMMM
.MMMMMM.
..MMMM..
...MM...
........""", {"M": MAGENTA, "R": ROSE})
    n["oeil-coeur-petit.png"] = from_ascii("""
........
..M..M..
.MMMMMM.
.MMMMMM.
..MMMM..
...MM...
........
........""", {"M": ROSE})
    return n


# -------------------------------------------------------------- BOUCHES 24x16

def arc(g, y0, amp, color, under=None, x0=3, x1=20, thickness=1):
    """Arc parabolique : amp > 0 = sourire (centre plus bas), amp < 0 = triste."""
    cx = (x0 + x1) / 2.0
    half = (x1 - x0) / 2.0
    for x in range(x0, x1 + 1):
        y = int(round(y0 + amp * (1 - ((x - cx) / half) ** 2)))
        for t in range(thickness):
            put(g, x, y + t, color)
        if under:
            put(g, x, y + thickness, under)
    return g


def gen_mouths():
    n = {}
    # Repos néon : sourire doux qui « respire » (pleine intensité / atténué)
    # + un petit sourire en coin pour casser la symétrie.
    n["sourire-neon1.png"] = arc(blank(MW, MH), 7, 4, CYAN, under=CYAN_DIM)
    n["sourire-neon2.png"] = arc(blank(MW, MH), 7, 4, scale(CYAN, 0.5), under=scale(CYAN_DIM, 0.5))
    smirk = blank(MW, MH)
    for x in range(3, 21):
        y = int(round(10 - 3.5 * ((x - 3) / 17.0) ** 1.6))
        put(smirk, x, y, CYAN)
        put(smirk, x, y + 1, CYAN_DIM)
    n["sourire-neon-smirk.png"] = smirk

    # Repos braise : ligne qui ondule comme une braise + étincelles jaunes.
    for i in range(3):
        g = blank(MW, MH)
        for x in range(2, 22):
            y = int(round(8 + 1.6 * math.sin(x * 0.7 + i * 2.1)))
            put(g, x, y, AMBRE)
            put(g, x, y + 1, scale(ORANGE, 0.7))
        for _ in range(2 + i):
            put(g, rng.randrange(3, 21), rng.randrange(3, 7), JAUNE)
        n["braise{}.png".format(i + 1)] = g

    # Repos glitch : ligne magenta stable, puis brefs sursauts de pixels éparpillés
    # avec segments décalés et recolorés (le robot « bugge » puis se reprend).
    calme = blank(MW, MH)
    for x in range(3, 21):
        calme[8][x] = MAGENTA
        calme[9][x] = scale(MAGENTA, 0.35)
    n["calme-magenta.png"] = calme
    for i in (1, 2):
        g = blank(MW, MH)
        x = 3
        while x < 21:  # la ligne se casse en segments décalés verticalement
            seg = rng.randint(2, 5)
            dy = rng.choice((-2, -1, 0, 1, 2))
            col = rng.choice((MAGENTA, CYAN, VERT, BLANC))
            for xx in range(x, min(x + seg, 21)):
                put(g, xx, 8 + dy, col)
            x += seg + rng.randint(0, 1)
        scatter(g, 12 + 6 * i, GLITCH_COLORS)
        n["glitch-doux{}.png".format(i)] = g

    # Joie : grand sourire jaune, puis rire ouvert (intérieur rose, dents blanches).
    n["joie-sourire.png"] = arc(blank(MW, MH), 5, 6, JAUNE, under=scale(ROSE, 0.6), thickness=2)
    rire = blank(MW, MH)
    for x in range(3, 21):
        cx, half = 11.5, 8.5
        ytop = int(round(4 + 1.5 * (1 - ((x - cx) / half) ** 2)))
        ybot = int(round(5 + 8 * (1 - ((x - cx) / half) ** 2)))
        put(rire, x, ytop, JAUNE)
        put(rire, x, ybot, JAUNE)
        for y in range(ytop + 1, ybot):
            put(rire, x, y, BLANC if y == ytop + 1 else ROSE)  # rangée de dents
    n["joie-rire.png"] = rire

    # Colère : zigzag rouge qui vibre (2 phases) + flash plein cadre.
    # Onde triangulaire CONTINUE (pas y qui saute de 3 → effet tirets décousus).
    tri = [0, 1, 2, 1, 0, -1, -2, -1]
    for i in (1, 2):
        g = blank(MW, MH)
        phase = 0 if i == 1 else 4  # phase opposée = la ligne « vibre »
        for x in range(2, 22):
            y = 8 + tri[(x + phase) % 8]
            put(g, x, y, ROUGE)
            put(g, x, y + 1, ORANGE)
        n["colere-zigzag{}.png".format(i)] = g
    flash = blank(MW, MH)
    for x in range(MW):
        flash[0][x] = ROUGE
        flash[MH - 1][x] = ROUGE
    for y in range(MH):
        flash[y][0] = ROUGE
        flash[y][MW - 1] = ROUGE
    scatter(flash, 26, [ORANGE, ROUGE, JAUNE])
    n["colere-flash.png"] = flash

    # Tristesse : arc inversé bleu, variante affaissée avec goutte cyan.
    n["triste-arc1.png"] = arc(blank(MW, MH), 11, -4, BLEU, under=scale(BLEU, 0.35))
    t2 = arc(blank(MW, MH), 11, -3, BLEU, under=scale(BLEU, 0.35))
    put(t2, 12, 14, CYAN)
    n["triste-arc2.png"] = t2

    # Surprise : « O » magenta qui grandit, halo cyan sur le plus grand.
    for i, (rx, ry) in enumerate(((3, 2.5), (5, 4), (8, 6)), start=1):
        g = blank(MW, MH)
        for y in range(MH):
            for x in range(MW):
                d = ((x - 11.5) / rx) ** 2 + ((y - 7.5) / ry) ** 2
                if 0.7 <= d <= 1.3:
                    g[y][x] = MAGENTA
                elif i == 3 and 1.5 <= d <= 1.9:
                    g[y][x] = scale(CYAN, 0.5)
        n["surprise-o{}.png".format(i)] = g

    # Glitch total : scanlines déchirées + pixels éparpillés + frame « dropout »
    # presque noire (le clignotement de l'écran qui meurt fait tout l'effet).
    for i in (1, 2, 3, 4):
        g = blank(MW, MH)
        if i == 3:
            scatter(g, 8, GLITCH_COLORS)  # dropout : presque rien
        else:
            for _ in range(5):
                y = rng.randrange(MH)
                x = rng.randrange(0, 12)
                seg = rng.randint(4, 12)
                col = rng.choice(GLITCH_COLORS)
                for xx in range(x, min(x + seg, MW)):
                    g[y][xx] = col
            scatter(g, 22, GLITCH_COLORS)
        n["glitch-total{}.png".format(i)] = g

    # Mire de calibration : motifs asymétriques sur les deux axes + coins colorés.
    # Sert à diagnostiquer la chaîne PNG→LED (flip, miroir, serpentin, débordement
    # ligne 8 du mapping). "123" en haut, "E" + bloc magenta en bas, coins :
    # blanc=haut-gauche, cyan=haut-droit, orange=bas-gauche, violet=bas-droit.
    calib = blank(MW, MH)
    DIGITS = {  # 3x5, dessinés rangées 1..5
        "1": ["_X_", "XX_", "_X_", "_X_", "XXX"],
        "2": ["XX_", "__X", "_X_", "X__", "XXX"],
        "3": ["XX_", "__X", "_X_", "__X", "XX_"],
    }
    for i, (d, col) in enumerate(zip("123", (ROUGE, VERT, BLEU))):
        for dy, row in enumerate(DIGITS[d]):
            for dx, ch in enumerate(row):
                if ch == "X":
                    put(calib, 3 + i * 5 + dx, 1 + dy, col)
    for dy, row in enumerate(["XXX", "X__", "XX_", "X__", "XXX"]):  # E jaune en bas-gauche
        for dx, ch in enumerate(row):
            if ch == "X":
                put(calib, 3 + dx, 9 + dy, JAUNE)
    for dy in (12, 13):  # bloc magenta bas-droit
        for dx in (19, 20):
            put(calib, dx, dy, MAGENTA)
    put(calib, 0, 0, BLANC)
    put(calib, 23, 0, CYAN)
    put(calib, 0, 15, ORANGE)
    put(calib, 23, 15, VIOLET)
    n["calib-bouche.png"] = calib

    # Amour : petit cœur rose (le grand = coeur.png arc-en-ciel existant).
    mini = blank(MW, MH)
    heart = ["..MM.MM..", ".MMMMMMM.", ".MMMMMMM.", "..MMMMM..", "...MMM...", "....M...."]
    for dy, row in enumerate(heart):
        for dx, ch in enumerate(row):
            if ch == "M":
                put(mini, 7 + dx, 5 + dy, ROSE)
    n["coeur-mini.png"] = mini
    return n


# ------------------------------------------------- MIRES ZONE-PAR-ZONE
# La webcam de vérification (Creality, focus fixe) ne résout PAS les pixels de
# la mire calib : impossible de lire « 123 » ou le « E ». En revanche elle
# résout la POSITION GROSSIÈRE d'un blob lumineux. D'où ces mires binaires :
# une seule zone allumée par expression, une capture = une réponse oui/non.
# Objectif : établir le câblage réel (yeux 385/448 croisés ?, ordre et
# orientation de la rangée basse de la bouche, frontière 448/449).

def zone(w, h, x0, x1, y0, y1, color=BLANC):
    """Rectangle plein [x0..x1] x [y0..y1] (bornes incluses), le reste éteint."""
    g = blank(w, h)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            g[y][x] = color
    return g


def gen_calib_zones():
    eyes, mouths = {}, {}
    eyes["oeil-noir.png"] = blank(EW, EH)
    eyes["oeil-plein.png"] = zone(EW, EH, 0, 7, 0, 7)
    # Un seul pixel : le DERNIER index écrit par la piste (start + 63).
    # Pour la piste à start=385 il tombe sur l'index 448, pile la frontière
    # ambiguë entre les deux yeux (448 vs 449) : l'œil où il s'allume tranche.
    eyes["oeil-px-dernier.png"] = zone(EW, EH, 7, 7, 7, 7)
    mouths["bouche-noire.png"] = blank(MW, MH)
    mouths["calib-bouche-haut.png"] = zone(MW, MH, 0, MW - 1, 0, 7)        # bande haute entière
    mouths["calib-bouche-haut-gauche.png"] = zone(MW, MH, 0, 7, 0, 7)      # 1re matrice du haut
    mouths["calib-bouche-bas-gauche.png"] = zone(MW, MH, 0, 7, 8, 15)      # 1re matrice du bas
    mouths["calib-bouche-ligne-basse.png"] = zone(MW, MH, 0, MW - 1, 15, 15)  # dernière ligne
    return eyes, mouths


def gen_reflechit():
    """Visuels « réfléchit » : regard qui cherche en l'air + barre de chargement.

    Sert d'état d'attente pendant le pipeline STT→LLM du mode conversation
    (latence jouée : le robot « pense » au lieu de sembler planté).
    """
    eyes, mouths = {}, {}
    # Pupille en haut (regard pensif) qui balaie gauche→centre→droite.
    for name, pos in (("hg", (1, 1)), ("hc", (3, 0)), ("hd", (5, 1))):
        eyes["oeil-reflechit-{}.png".format(name)] = eye_disk(CYAN, BLEU_NUIT, pos)

    # Barre de progression 4 frames : cadre discret, remplissage cyan.
    # Géométrie : cadre x2..21 / y6..9, remplissage 18 cases utiles (x3..20).
    for i, cells in enumerate((4, 9, 13, 18), start=1):
        g = blank(MW, MH)
        for x in range(2, 22):                       # lisières haut/bas du cadre
            put(g, x, 6, CYAN_DIM)
            put(g, x, 9, CYAN_DIM)
        for y in (7, 8):                             # montants gauche/droit
            put(g, 2, y, CYAN_DIM)
            put(g, 21, y, CYAN_DIM)
        for x in range(3, 3 + cells):                # remplissage progressif
            put(g, x, 7, CYAN)
            put(g, x, 8, CYAN)
        mouths["chargement{}.png".format(i)] = g
    return eyes, mouths


def gen_parle():
    """Bouches « articulation » pour l'expression parle : cycle petit→grand→moyen→fermé
    qui mime l'ouverture de bouche pendant la synthèse vocale (cf. NEW_EXPRESSIONS["parle"]).

    Pas de nouveaux yeux : l'expression réutilise oeil-neon-*.png (le regard "repos
    neon" existant suffit, seule la bouche doit bouger en rythme avec l'audio).
    """
    mouths = {}

    # Bouche fermée : simple ligne cyan (même esprit que sourire-neon1 : trait +
    # lisière CYAN_DIM en dessous pour donner de l'épaisseur sans un 2e pixel plein).
    ferme = blank(MW, MH)
    for x in range(3, 21):
        put(ferme, x, 8, CYAN)
        put(ferme, x, 9, CYAN_DIM)
    mouths["parle-neon-ferme.png"] = ferme

    # Bouches ouvertes : ellipse centrée (11.5, 8), une par taille d'ouverture.
    # Une seule équation ((x-cx)/rx)²+((y-cy)/ry)² pour intérieur ET contour :
    # plus simple et plus régulier qu'une 2e ellipse rétrécie de 1 px, qui serait
    # discontinue sur les petits rayons (rx=4 pour "petit").
    for name, (rx, ry) in (("petit", (4, 2)), ("moyen", (6, 4)), ("grand", (8, 5.5))):
        g = blank(MW, MH)
        cx, cy = 11.5, 8
        for y in range(MH):
            for x in range(MW):
                d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
                if d <= 1:
                    g[y][x] = CYAN if d >= 0.75 else BLEU_NUIT  # anneau proche du bord = contour
        mouths["parle-neon-{}.png".format(name)] = g
    return mouths


def gen_calib_couleurs():
    """Mire « une couleur par cellule » : 6 carrés de couleur, un par matrice.
    C'est elle qui a établi le câblage serpentin le 2026-07-11 (lecture humaine).
    Depuis le refactoring d'ImageMapping, le fichier doit s'afficher TEL QUEL :
    haut = rouge/vert/bleu, bas = blanc/jaune/magenta, de gauche à droite.
    Toute divergence à l'affichage = régression de la table de câblage.
    """
    eyes, mouths = {}, {}
    g = blank(MW, MH)
    for x0, col in ((0, ROUGE), (8, VERT), (16, BLEU)):
        for y in range(0, 8):
            for x in range(x0, x0 + 8):
                g[y][x] = col
    for x0, col in ((0, BLANC), (8, JAUNE), (16, MAGENTA)):
        for y in range(8, 16):
            for x in range(x0, x0 + 8):
                g[y][x] = col
    mouths["calib-couleurs.png"] = g
    eyes["oeil-rouge.png"] = zone(EW, EH, 0, 7, 0, 7, ROUGE)
    eyes["oeil-vert.png"] = zone(EW, EH, 0, 7, 0, 7, VERT)

    # Mires « bordure » : anneau sur le pourtour exact de chaque zone.
    # Le moindre décalage d'index (start ±1) casse l'anneau de façon flagrante
    # (bord éteint d'un côté, pixels orphelins de l'autre). C'est la mire qui
    # a établi le câblage contigu des yeux (384/448, sans trous).
    def bordure(w, h, color):
        g = blank(w, h)
        for x in range(w):
            g[0][x] = color
            g[h - 1][x] = color
        for y in range(h):
            g[y][0] = color
            g[y][w - 1] = color
        return g

    eyes["oeil-bordure.png"] = bordure(EW, EH, CYAN)
    mouths["bouche-bordure.png"] = bordure(MW, MH, JAUNE)
    return eyes, mouths


def calib_expr(leye, reye, mouth):
    """Expression une-frame pour mire (8 s, boucle, à lire sur une capture)."""
    return {
        "duration": 8000, "loop": True, "keys": [],
        "left_eyes": [[1.0, leye]],
        "right_eyes": [[1.0, reye]],
        "mouths": [[1.0, mouth]],
    }


# Une expression par question de câblage (voir gen_calib_zones).
CALIB_ZONE_EXPRESSIONS = {
    # Permutation des 6 matrices en une lecture : bloc d'index -> couleur.
    # 0-63 ROUGE, 64-127 VERT, 128-191 BLEU, 192-255 BLANC, 256-319 JAUNE,
    # 320-383 MAGENTA. Yeux : piste left_eyes ROUGE, right_eyes VERT.
    "calib-couleurs": calib_expr("oeil-rouge.png", "oeil-vert.png", "calib-couleurs.png"),
    # Anneaux sur le pourtour de chaque zone : tout décalage de start saute aux yeux.
    "calib-bords": calib_expr("oeil-bordure.png", "oeil-bordure.png", "bouche-bordure.png"),
    "calib-og": calib_expr("oeil-plein.png", "oeil-noir.png", "bouche-noire.png"),
    "calib-od": calib_expr("oeil-noir.png", "oeil-plein.png", "bouche-noire.png"),
    "calib-448": calib_expr("oeil-px-dernier.png", "oeil-noir.png", "bouche-noire.png"),
    "calib-bh": calib_expr("oeil-noir.png", "oeil-noir.png", "calib-bouche-haut.png"),
    "calib-bhg": calib_expr("oeil-noir.png", "oeil-noir.png", "calib-bouche-haut-gauche.png"),
    "calib-bbg": calib_expr("oeil-noir.png", "oeil-noir.png", "calib-bouche-bas-gauche.png"),
    "calib-blb": calib_expr("oeil-noir.png", "oeil-noir.png", "calib-bouche-ligne-basse.png"),
}


# ------------------------------------------------------------- EXPRESSIONS

# Rappel sémantique Sequence : frame [t, image] affichée jusqu'à t*duration
# (la première de 0 à t0). loop=false → retour au visage default après duration.
# keys volontairement vides : à mapper sur la télécommande quand validé.
NEW_EXPRESSIONS = {
    "calib": {
        # Mire de diagnostic PNG→LED : frames uniques, à lire sur une photo.
        "duration": 8000, "loop": True, "keys": [],
        "left_eyes": [[1.0, "oeil-calib.png"]],
        "right_eyes": [[1.0, "oeil-calib.png"]],
        "mouths": [[1.0, "calib-bouche.png"]],
    },
    "repos neon": {
        "duration": 6000, "loop": True, "keys": [],
        "left_eyes": [[0.30, "oeil-neon-centre.png"], [0.34, "oeil-neon-clign.png"],
                      [0.38, "oeil-neon-centre.png"], [0.55, "oeil-neon-gauche.png"],
                      [0.62, "oeil-neon-centre.png"], [0.80, "oeil-neon-droit.png"],
                      [0.96, "oeil-neon-centre.png"], [1.0, "oeil-neon-clign.png"]],
        "right_eyes": [[0.30, "oeil-neon-centre.png"], [0.34, "oeil-neon-clign.png"],
                       [0.38, "oeil-neon-centre.png"], [0.55, "oeil-neon-gauche.png"],
                       [0.62, "oeil-neon-centre.png"], [0.80, "oeil-neon-droit.png"],
                       [0.96, "oeil-neon-centre.png"], [1.0, "oeil-neon-clign.png"]],
        "mouths": [[0.45, "sourire-neon1.png"], [0.55, "sourire-neon2.png"],
                   [0.90, "sourire-neon1.png"], [1.0, "sourire-neon-smirk.png"]],
    },
    "repos braise": {
        "duration": 4000, "loop": True, "keys": [],
        "left_eyes": [[0.6, "oeil-braise.png"], [1.0, "oeil-braise-blase.png"]],
        "right_eyes": [[0.6, "oeil-braise.png"], [1.0, "oeil-braise-blase.png"]],
        "mouths": [[0.33, "braise1.png"], [0.66, "braise2.png"], [1.0, "braise3.png"]],
    },
    "repos glitch": {
        "duration": 7000, "loop": True, "keys": [],
        "left_eyes": [[0.40, "oeil-violet.png"], [0.44, "oeil-neon-clign.png"],
                      [0.70, "oeil-violet.png"], [0.74, "oeil-violet-glitch1.png"],
                      [0.78, "oeil-violet-glitch2.png"], [1.0, "oeil-violet.png"]],
        "right_eyes": [[0.40, "oeil-violet.png"], [0.44, "oeil-neon-clign.png"],
                       [0.70, "oeil-violet.png"], [0.74, "oeil-violet-glitch2.png"],
                       [0.78, "oeil-violet-glitch1.png"], [1.0, "oeil-violet.png"]],
        "mouths": [[0.70, "calme-magenta.png"], [0.73, "glitch-doux1.png"],
                   [0.76, "glitch-doux2.png"], [0.79, "glitch-doux1.png"],
                   [1.0, "calme-magenta.png"]],
    },
    "joie": {
        "duration": 2000, "loop": True, "keys": [],
        "left_eyes": [[1.0, "oeil-joie.png"]],
        "right_eyes": [[1.0, "oeil-joie.png"]],
        "mouths": [[0.55, "joie-sourire.png"], [1.0, "joie-rire.png"]],
    },
    "colere": {
        "duration": 900, "loop": True, "keys": [],
        "left_eyes": [[0.45, "oeil-colere-gauche.png"], [0.5, "oeil-colere-flash.png"],
                      [1.0, "oeil-colere-gauche.png"]],
        "right_eyes": [[0.45, "oeil-colere-droit.png"], [0.5, "oeil-colere-flash.png"],
                       [1.0, "oeil-colere-droit.png"]],
        "mouths": [[0.45, "colere-zigzag1.png"], [0.5, "colere-flash.png"],
                   [0.95, "colere-zigzag2.png"], [1.0, "colere-flash.png"]],
    },
    "tristesse": {
        "duration": 4500, "loop": True, "keys": [],
        "left_eyes": [[0.40, "oeil-triste.png"], [0.55, "oeil-triste-larme1.png"],
                      [0.70, "oeil-triste-larme2.png"], [0.85, "oeil-triste-larme3.png"],
                      [1.0, "oeil-triste.png"]],
        "right_eyes": [[0.55, "oeil-triste.png"], [0.70, "oeil-triste-larme1.png"],
                       [0.85, "oeil-triste-larme2.png"], [1.0, "oeil-triste-larme3.png"]],
        "mouths": [[0.6, "triste-arc1.png"], [1.0, "triste-arc2.png"]],
    },
    "surprise": {
        "duration": 2500, "loop": False, "keys": [],
        "left_eyes": [[0.2, "oeil-surprise1.png"], [1.0, "oeil-surprise2.png"]],
        "right_eyes": [[0.2, "oeil-surprise1.png"], [1.0, "oeil-surprise2.png"]],
        "mouths": [[0.15, "surprise-o1.png"], [0.3, "surprise-o2.png"],
                   [1.0, "surprise-o3.png"]],
    },
    "glitch total": {
        "duration": 1000, "loop": True, "keys": [],
        "left_eyes": [[0.33, "oeil-glitch1.png"], [0.66, "oeil-glitch2.png"],
                      [1.0, "oeil-glitch3.png"]],
        "right_eyes": [[0.33, "oeil-glitch2.png"], [0.66, "oeil-glitch3.png"],
                       [1.0, "oeil-glitch1.png"]],
        "mouths": [[0.25, "glitch-total1.png"], [0.5, "glitch-total2.png"],
                   [0.75, "glitch-total3.png"], [1.0, "glitch-total4.png"]],
    },
    "reflechit": {
        # État d'attente conversation : le regard cherche, la bouche « charge ».
        # 1,6 s en boucle = la barre se remplit ~3x pendant un tour de pipeline.
        "duration": 1600, "loop": True, "keys": [],
        "left_eyes": [[0.33, "oeil-reflechit-hg.png"], [0.66, "oeil-reflechit-hc.png"],
                      [1.0, "oeil-reflechit-hd.png"]],
        "right_eyes": [[0.33, "oeil-reflechit-hg.png"], [0.66, "oeil-reflechit-hc.png"],
                       [1.0, "oeil-reflechit-hd.png"]],
        "mouths": [[0.25, "chargement1.png"], [0.5, "chargement2.png"],
                   [0.75, "chargement3.png"], [1.0, "chargement4.png"]],
    },
    "amour neon": {
        "duration": 1800, "loop": True, "keys": [],
        "left_eyes": [[0.12, "oeil-coeur.png"], [0.20, "oeil-coeur-petit.png"],
                      [0.32, "oeil-coeur.png"], [1.0, "oeil-coeur-petit.png"]],
        "right_eyes": [[0.12, "oeil-coeur.png"], [0.20, "oeil-coeur-petit.png"],
                       [0.32, "oeil-coeur.png"], [1.0, "oeil-coeur-petit.png"]],
        # Battement « boum-boum » puis pause : deux pulsations rapprochées.
        "mouths": [[0.12, "coeur.png"], [0.20, "coeur-mini.png"],
                   [0.32, "coeur.png"], [1.0, "coeur-mini.png"]],
    },
    "parle": {
        # Boucle courte (800 ms) : bouche qui articule pendant la synthèse vocale,
        # regard neon repos discret (pas de nouveaux yeux, voir gen_parle).
        "duration": 800, "loop": True, "keys": [],
        "left_eyes":  [[0.5, "oeil-neon-centre.png"], [1.0, "oeil-neon-droit.png"]],
        "right_eyes": [[0.5, "oeil-neon-centre.png"], [1.0, "oeil-neon-gauche.png"]],
        "mouths": [[0.25, "parle-neon-petit.png"], [0.5, "parle-neon-grand.png"],
                   [0.75, "parle-neon-moyen.png"], [1.0, "parle-neon-ferme.png"]],
    },
}


def main():
    eyes = gen_eyes()
    mouths = gen_mouths()
    zone_eyes, zone_mouths = gen_calib_zones()
    eyes.update(zone_eyes)
    mouths.update(zone_mouths)
    couleur_eyes, couleur_mouths = gen_calib_couleurs()
    eyes.update(couleur_eyes)
    mouths.update(couleur_mouths)
    refl_eyes, refl_mouths = gen_reflechit()
    eyes.update(refl_eyes)
    mouths.update(refl_mouths)
    mouths.update(gen_parle())  # pas d'yeux nouveaux, cf. gen_parle
    for name, g in eyes.items():
        save(g, EYE_DIR, name)
    for name, g in mouths.items():
        save(g, MOUTH_DIR, name)
    print("PNG générés : {} yeux, {} bouches".format(len(eyes), len(mouths)))

    with open(EXPR_JSON) as f:
        expressions = json.load(f)
    added = []
    for name, expr in {**NEW_EXPRESSIONS, **CALIB_ZONE_EXPRESSIONS}.items():
        if name not in expressions:  # ne jamais écraser l'existant
            expressions[name] = {"name": name, **expr}
            added.append(name)
    with open(EXPR_JSON, "w") as f:
        json.dump(expressions, f, indent=4, ensure_ascii=False)
        f.write("\n")
    print("expressions.json : ajoutées -> {}".format(", ".join(added) or "aucune (déjà présentes)"))


if __name__ == "__main__":
    main()
