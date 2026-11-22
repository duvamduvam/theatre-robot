"""Maquette de l'étude du visage (docs/etudes/etude-visage.md) — PAS du code de robot.

Dessine un visage PARAMÉTRIQUE au format réel des matrices (yeux 8x8, bouche 24x16) et
produit les planches de l'étude. Sert à juger des propositions à l'œil avant d'écrire
quoi que ce soit dans `didier_core`.

Principe : chaque zone est dessinée 8 fois trop fin puis moyennée par bloc. Un bord qui
tombe au milieu d'une LED donne une LED à demi-intensité : c'est ce qui rend un mouvement
d'un quart de pixel visible, là où les PNG actuels sautent d'une LED entière.

Lancer depuis la racine du dépôt :
    .venv/bin/python docs/etudes/visage/maquette_visage.py
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[2]
SUR = 8  # sur-échantillonnage du dessin, par axe
try:  # police avec accents ; à défaut, celle de PIL (sans accents)
    POLICE = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
except OSError:
    POLICE = ImageFont.load_default()

# Le cœur ne se calcule pas à cette taille : il se dessine, comme une lettre.
COEUR = [".XX..XX.", "XXXXXXXX", "XXXXXXXX", "XXXXXXXX", ".XXXXXX.", "..XXXX..", "...XX...", "........"]

# Couleurs : toutes portent du VERT, le canal qui fait l'essentiel de la lumière perçue
# (luminance relative = 0,2126 R + 0,7152 V + 0,0722 B). Un bleu ou un violet pur est
# presque noir en plein jour.
CYAN = (0, 235, 255)
AMBRE = (255, 150, 0)
ROSE = (255, 60, 140)
ROUGE = (255, 40, 10)
BLEU_PALE = (70, 150, 255)
BLANC = (255, 255, 235)
VERT = (60, 255, 90)


@dataclass(frozen=True)
class Oeil:
    """Un œil 8x8. Les longueurs sont en LED, l'origine au centre de la matrice."""
    largeur: float = 6.0
    hauteur: float = 6.0
    arrondi: float = 1.6         # rayon des coins
    paupiere_haut: float = 0.0   # 0 = ouverte, 1 = fermée ; descend depuis le haut
    pente_haut: float = 0.0      # > 0 : la paupière descend vers le NEZ (colère) ; < 0 : vers l'extérieur (tristesse)
    paupiere_bas: float = 0.0    # remonte depuis le bas
    arc_bas: float = 0.0         # > 0 : la paupière du bas se bombe vers le haut (œil qui rit)
    pupille: float = 1.1         # rayon de la pupille sombre ; 0 = œil plein
    regard: tuple[float, float] = (0.0, 0.0)  # déplacement de la pupille, en LED
    couleur: tuple[int, int, int] = CYAN
    forme: str = "bloc"          # "bloc" (carré arrondi) ou "coeur"


@dataclass(frozen=True)
class Bouche:
    """La bouche 24x16. Le pan de FACE ne porte que les colonnes 8 à 15 : l'essentiel du
    dessin occupe presque toute la largeur (choix de David du 22/11) ; les pans de côté le prolongent."""
    largeur: float = 20.0      # sur 24 : la bouche occupe toute la largeur (David, 22/11)
    courbure: float = 0.0        # > 0 sourire, < 0 moue ; flèche de la courbe en LED
    ouverture: float = 0.0       # hauteur du vide entre les lèvres, en LED
    epaisseur: float = 2.0       # trait jamais sous 2 LED
    rond: float = 0.0            # 0..1 : resserre la bouche en « o »
    couleur: tuple[int, int, int] = CYAN


@dataclass(frozen=True)
class Visage:
    oeil_g: Oeil = Oeil()
    oeil_d: Oeil = Oeil()
    bouche: Bouche = Bouche()


def _grille(l: int, h: int):
    ys, xs = np.mgrid[0:h * SUR, 0:l * SUR]
    return (xs + 0.5) / SUR - l / 2, (ys + 0.5) / SUR - h / 2


def _moyenne(masque: np.ndarray, l: int, h: int) -> np.ndarray:
    return masque.reshape(h, SUR, l, SUR).mean(axis=(1, 3))


def dessiner_oeil(o: Oeil, cote: int = 8, miroir: bool = False) -> np.ndarray:
    """Rend l'œil en RGB (cote x cote). `miroir` : œil droit (les pentes s'inversent)."""
    k = cote / 8  # les mêmes paramètres servent à simuler un œil 16x16
    x, y = _grille(cote, cote)
    x, y = x / k, y / k
    if miroir:
        x = -x
    if o.forme == "coeur":
        motif = np.array([[c == "X" for c in ligne] for ligne in COEUR])
        col = np.clip(np.floor(x + 4).astype(int), 0, 7)
        lig = np.clip(np.floor(y + 4).astype(int), 0, 7)
        corps = motif[lig, col]
    else:
        dx = np.abs(x) - (o.largeur / 2 - o.arrondi)
        dy = np.abs(y) - (o.hauteur / 2 - o.arrondi)
        dehors = np.hypot(np.maximum(dx, 0), np.maximum(dy, 0))
        corps = (dehors <= o.arrondi) & (dx <= o.arrondi) & (dy <= o.arrondi)
    haut = -o.hauteur / 2 + o.paupiere_haut * o.hauteur + o.pente_haut * x
    bas = o.hauteur / 2 - o.paupiere_bas * o.hauteur - o.arc_bas * (1 - (x / (o.largeur / 2)) ** 2)
    visible = corps & (y >= haut) & (y <= bas)
    if o.pupille > 0:
        px, py = o.regard
        visible &= np.hypot(x - px, y - py) > o.pupille
    a = _moyenne(visible.astype(float), cote, cote)
    return (a[..., None] * np.array(o.couleur)).astype(np.uint8)


def dessiner_bouche(b: Bouche, l: int = 24, h: int = 16) -> np.ndarray:
    k = l / 24
    x, y = _grille(l, h)
    x, y = x / k, y / k
    demi = b.largeur / 2 * (1 - 0.45 * b.rond)
    t = np.clip(x / demi, -1, 1)
    profil = 1 - t * t                       # 1 au centre, 0 aux commissures
    milieu = b.courbure * (profil - 0.5)     # sourire : le centre descend
    ouvert = b.ouverture * profil ** (0.5 + 0.5 * (1 - b.rond))
    haut = milieu - ouvert / 2 - b.epaisseur / 2
    bas = milieu + ouvert / 2 + b.epaisseur / 2
    dans = (np.abs(x) <= demi) & (y >= haut) & (y <= bas)
    vide = (np.abs(x) <= demi) & (y >= milieu - ouvert / 2 + b.epaisseur / 2) & (y <= milieu + ouvert / 2 - b.epaisseur / 2)
    a = _moyenne(dans.astype(float), l, h) - 0.82 * _moyenne(vide.astype(float), l, h)
    return (np.clip(a, 0, 1)[..., None] * np.array(b.couleur)).astype(np.uint8)


def melange(a, b, t: float):
    """Interpole deux réglages de même type, champ par champ. C'est tout le moteur de
    transition : passer d'une expression à l'autre = glisser les nombres."""
    champs = {}
    for nom in a.__dataclass_fields__:
        va, vb = getattr(a, nom), getattr(b, nom)
        if isinstance(va, (Oeil, Bouche)):
            champs[nom] = melange(va, vb, t)
        elif isinstance(va, str):
            champs[nom] = va if t < 0.5 else vb
        elif isinstance(va, tuple):
            champs[nom] = tuple(x + (y - x) * t for x, y in zip(va, vb))
        else:
            champs[nom] = va + (vb - va) * t
    return replace(a, **champs)


# ---------------------------------------------------------------------------------------
# Le vocabulaire proposé : une expression = quelques nombres, plus un seul PNG.
# Les clés sont des étiquettes de planche ; dans le robot les noms restent sans accent
# (règle MOTIF_NOM_ENTREE de theatre_contrats) : ecoute, emerveille, colere, tristesse…
# ---------------------------------------------------------------------------------------
def _v(oeil: Oeil, bouche: Bouche, oeil_d: Oeil | None = None) -> Visage:
    return Visage(oeil, oeil_d or oeil, bouche)


NEUTRE = _v(Oeil(), Bouche(courbure=1.6))
VOCABULAIRE: dict[str, Visage] = {
    "repos": NEUTRE,
    "joie": _v(Oeil(paupiere_bas=0.18, arc_bas=2.6, pupille=0), Bouche(largeur=22, courbure=5.5, ouverture=4.0)),
    "émerveillé": _v(Oeil(largeur=7, hauteur=7, arrondi=2.6, pupille=1.5, regard=(0, -0.4), couleur=BLANC),
                     Bouche(largeur=11, ouverture=5, rond=1)),
    "amour": _v(Oeil(forme="coeur", largeur=8, hauteur=8, pupille=0, couleur=ROSE), Bouche(largeur=18, courbure=4.0, couleur=ROSE)),
    "triste": _v(Oeil(paupiere_haut=0.22, pente_haut=-0.45, pupille=0.9, regard=(0, 1.3), couleur=BLEU_PALE),
                 Bouche(largeur=18, courbure=-4.0, couleur=BLEU_PALE)),
    "colère": _v(Oeil(paupiere_haut=0.25, pente_haut=0.6, pupille=0, couleur=ROUGE),
                 Bouche(largeur=20, courbure=-3.4, epaisseur=2.4, couleur=ROUGE)),
    "surprise": _v(Oeil(largeur=7, hauteur=7.6, arrondi=3.0, pupille=0.8), Bouche(largeur=12, ouverture=7, rond=1)),
    "écoute": _v(Oeil(hauteur=7, pupille=1.3, couleur=VERT), Bouche(largeur=12, courbure=1.0, couleur=VERT)),
    "réfléchit": _v(Oeil(hauteur=5, regard=(1.0, -0.5), couleur=AMBRE),
                    Bouche(largeur=12, courbure=-0.8, couleur=AMBRE),
                    Oeil(regard=(-1.0, -1.0), couleur=AMBRE)),
    "parle": _v(Oeil(), Bouche(largeur=18, courbure=1.2, ouverture=5)),
    "malice": _v(Oeil(paupiere_haut=0.34, pupille=0.9, regard=(1.0, 1.0)),
                 Bouche(largeur=18, courbure=3.4),
                 Oeil(paupiere_haut=0.34, pupille=0.9, regard=(-1.0, 1.0))),
    "dodo": _v(Oeil(paupiere_haut=0.82, pupille=0, couleur=BLEU_PALE), Bouche(largeur=8, ouverture=1.5, rond=1, couleur=BLEU_PALE)),
}

# Les trois grammaires d'œil comparées dans l'étude.
def grammaire(v: Visage, nom: str) -> Visage:
    if nom == "bloc":      # œil plein, sans pupille (école Cozmo)
        return replace(v, oeil_g=replace(v.oeil_g, pupille=0), oeil_d=replace(v.oeil_d, pupille=0))
    return v               # "pupille" : œil plein + pupille sombre mobile (proposé)


# ---------------------------------------------------------------------------------------
# Rendu des planches
# ---------------------------------------------------------------------------------------
E = 10  # pixels d'écran par LED


def vignette(v: Visage, cote_oeil: int = 8, bouche=(24, 16)) -> np.ndarray:
    """Disposition de l'aperçu sim : deux yeux au-dessus de la bouche (pas les proportions
    réelles : sur le robot les yeux sont sur des tiges, bien plus écartés)."""
    kb = bouche[0] // 24
    ko = cote_oeil // 8
    unite = max(kb, ko)
    c = np.zeros((28 * unite, 28 * unite, 3), np.uint8)
    og = dessiner_oeil(v.oeil_g, cote_oeil)
    od = dessiner_oeil(v.oeil_d, cote_oeil, miroir=True)
    b = dessiner_bouche(v.bouche, *bouche)
    f = unite // ko
    og, od = (np.repeat(np.repeat(i, f, 0), f, 1) for i in (og, od))
    fb = unite // kb
    b = np.repeat(np.repeat(b, fb, 0), fb, 1)
    c[1 * unite:9 * unite, 3 * unite:11 * unite] = og
    c[1 * unite:9 * unite, 17 * unite:25 * unite] = od
    c[11 * unite:27 * unite, 2 * unite:26 * unite] = b
    return c


def agrandir(c: np.ndarray, e: int, grille: bool = True) -> Image.Image:
    im = np.repeat(np.repeat(c, e, 0), e, 1)
    if grille and e >= 6:   # joint sombre entre LED, comme la grille du diffuseur
        im[::e, :] = im[::e, :] // 3
        im[:, ::e] = im[:, ::e] // 3
    return Image.fromarray(im)


def planche(cases: list[tuple[str, np.ndarray]], colonnes: int, sortie: Path, e: int = E, titre: str = "") -> None:
    h0, l0 = cases[0][1].shape[:2]
    L, H = l0 * e + 10, h0 * e + 26
    lignes = -(-len(cases) // colonnes)
    haut = 30 if titre else 0
    pl = Image.new("RGB", (colonnes * L, lignes * H + haut), (26, 26, 26))
    d = ImageDraw.Draw(pl)
    if titre:
        d.text((8, 8), titre, fill=(255, 255, 255), font=POLICE)
    for i, (nom, c) in enumerate(cases):
        x, y = (i % colonnes) * L, (i // colonnes) * H + haut
        pl.paste(agrandir(c, e), (x + 5, y + 21))
        d.text((x + 6, y + 5), nom, fill=(235, 235, 235), font=POLICE)
    pl.save(sortie)
    print("écrit", sortie.relative_to(RACINE), pl.size)


def existant(nom: str) -> np.ndarray:
    """Première image de l'expression actuelle, lue dans data/ (aucune écriture)."""
    e = json.loads((RACINE / "data/json/expressions.json").read_text())[nom]
    def im(zone, piste):
        f = e[piste][0][1]
        return np.array(Image.open(RACINE / "data/medias/visuals" / zone / f).convert("RGB"))
    c = np.zeros((28, 28, 3), np.uint8)
    c[1:9, 3:11], c[1:9, 17:25], c[11:27, 2:26] = im("eye", "left_eyes"), im("eye", "right_eyes"), im("mouth", "mouths")
    return c


def vu_de_loin(c: np.ndarray, metres: float) -> Image.Image:
    """Ce qu'il reste du visage à `metres`, affiché pour un écran lu à 60 cm : même angle
    apparent (pas de LED 8,4 mm, lu sur les STL de la bouche ; écran supposé à 0,25 mm par
    pixel). Pure géométrie : ni l'éblouissement des LED la nuit ni le contraste de jour ne
    sont simulés — ceux-là se MESURENT sur le robot (protocole dans l'étude)."""
    e = max(1.0, 8.4 * (0.6 / metres) / 0.25)
    im = Image.fromarray(c).resize((round(c.shape[1] * e), round(c.shape[0] * e)), Image.BOX)
    return im.filter(ImageFilter.GaussianBlur(0.6))


def planche_distance(sortie: Path) -> None:
    colonnes = [("actuel : default", existant("default")), ("proposé : repos", vignette(VOCABULAIRE["repos"])),
                ("actuel : tristesse", existant("tristesse")), ("proposé : triste", vignette(VOCABULAIRE["triste"])),
                ("actuel : joie", existant("joie")), ("proposé : joie", vignette(VOCABULAIRE["joie"]))]
    distances = [3, 8, 15]
    marge, col = 70, 200
    hauteurs = [vu_de_loin(colonnes[0][1], m).height + 14 for m in distances]
    pl = Image.new("RGB", (marge + col * len(colonnes), 52 + sum(hauteurs)), (26, 26, 26))
    d = ImageDraw.Draw(pl)
    d.text((8, 6), "Taille apparente du visage, pour un écran lu à 60 cm (géométrie seule)", fill=(255, 255, 255), font=POLICE)
    for j, (n, _) in enumerate(colonnes):
        d.text((marge + j * col + 8, 28), n, fill=(235, 235, 235), font=POLICE)
    y = 52
    for m, h in zip(distances, hauteurs):
        d.text((8, y + h // 2 - 8), f"{m} m", fill=(235, 235, 235), font=POLICE)
        for j, (_, c) in enumerate(colonnes):
            im = vu_de_loin(c, m)
            pl.paste(im, (marge + j * col + (col - im.width) // 2, y + 7))
        y += h
    pl.save(sortie)
    print("écrit", sortie.relative_to(RACINE), pl.size)


def animation(sortie: Path) -> None:
    """Dix secondes de « vie » : repos qui cligne et regarde, puis écoute, réfléchit, parle,
    joie. Tout est obtenu en faisant glisser les nombres — aucune image dessinée à la main."""
    rng = np.random.default_rng(7)
    ips, images = 20, []
    script = [("repos", 2.5), ("écoute", 1.5), ("réfléchit", 1.5), ("parle", 2.5), ("joie", 1.5), ("repos", 0.5)]
    cibles = [(VOCABULAIRE[n], round(d * ips)) for n, d in script]
    courant = cibles[0][0]
    regard, cible_regard, clign = np.zeros(2), np.zeros(2), -1
    enveloppe = 0.0
    for idx, (cible, n) in enumerate(cibles):
        depart = courant
        for i in range(n):
            t = min(1.0, i / (0.25 * ips))                      # transition en 250 ms
            t = t * t * (3 - 2 * t)                             # départ et arrivée en douceur
            courant = melange(depart, cible, t)
            v = courant
            if rng.random() < 1 / (1.3 * ips):                  # petite saccade toutes les ~1,3 s
                cible_regard = rng.uniform(-1.2, 1.2, 2) * (1, 0.6)
            regard += (cible_regard - regard) * 0.5
            if clign < 0 and rng.random() < 1 / (3.5 * ips):    # ~17 clignements par minute
                clign = 0
            ferme = 0.0
            if clign >= 0:
                ferme = [0.6, 1.0, 1.0, 0.5, 0.15][clign]       # 250 ms, fermeture plus vive que l'ouverture
                clign = clign + 1 if clign < 4 else -1
            def vivant(o: Oeil) -> Oeil:
                return replace(o, regard=(o.regard[0] + regard[0], o.regard[1] + regard[1]),
                               paupiere_haut=max(o.paupiere_haut, ferme))
            b = v.bouche
            if script[idx][0] == "parle":                       # volume SIMULÉ (sinus) : la maquette n'écoute aucun son
                syll = abs(math.sin(i / ips * 2 * math.pi * 3.1)) * (0.5 + 0.5 * abs(math.sin(i / ips * 2.2)))
                enveloppe += (syll - enveloppe) * 0.6
                b = replace(b, ouverture=0.3 + 6.5 * enveloppe, largeur=b.largeur - 2 * enveloppe)
            v = Visage(vivant(v.oeil_g), vivant(v.oeil_d), b)
            im = agrandir(vignette(v), 9)
            ImageDraw.Draw(im).text((6, 2), script[idx][0], fill=(200, 200, 200), font=POLICE)
            images.append(im)
    images[0].save(sortie, save_all=True, append_images=images[1:], duration=1000 // ips, loop=0)
    print("écrit", sortie.relative_to(RACINE), len(images), "images")


def main() -> None:
    # 1. Le vocabulaire proposé, au format réel.
    planche([(n, vignette(v)) for n, v in VOCABULAIRE.items()], 6, ICI / "proposition-vocabulaire.png",
            titre="Proposition : un seul personnage, douze expressions — yeux 8x8, bouche 24x16 (matériel actuel)")
    # 2. Avant / après sur les expressions qui ont un équivalent.
    paires = [("default", "repos"), ("joie", "joie"), ("tristesse", "triste"), ("colere", "colère"),
              ("surprise", "surprise"), ("reflechit", "réfléchit")]
    cases = [(f"actuel : {a}", existant(a)) for a, _ in paires] + [(f"proposé : {p}", vignette(VOCABULAIRE[p])) for _, p in paires]
    planche(cases, 6, ICI / "avant-apres.png", titre="Avant (ligne du haut) / après (ligne du bas)")
    # 3. Les grammaires d'œil : plein, ou plein avec pupille.
    noms = ["repos", "joie", "triste", "colère", "malice", "réfléchit"]
    cases = [(f"œil plein : {n}", vignette(grammaire(VOCABULAIRE[n], "bloc"))) for n in noms]
    cases += [(f"avec pupille : {n}", vignette(VOCABULAIRE[n])) for n in noms]
    planche(cases, 6, ICI / "grammaires-oeil.png", titre="Œil plein (haut) contre œil à pupille mobile (bas)")
    # 4. Le regard et le quart de pixel.
    cases = [(f"regard {dx:+.2f}", vignette(replace(NEUTRE, oeil_g=replace(NEUTRE.oeil_g, regard=(dx, 0)),
                                                     oeil_d=replace(NEUTRE.oeil_d, regard=(-dx, 0)))))
             for dx in (-1.5, -1.0, -0.5, -0.25, 0, 0.25, 0.5, 1.0, 1.5)]
    planche(cases[:9], 9, ICI / "regard-sous-pixel.png", e=7, titre="La pupille glisse par quarts de LED (les deux yeux convergent / divergent ici pour l'exemple)")
    # 5. Ce que donnerait le même dessin sur des matrices deux fois plus fines.
    noms = ["repos", "joie", "triste", "malice"]
    cases = [(f"8x8 + 24x16 : {n}", np.repeat(np.repeat(vignette(VOCABULAIRE[n]), 2, 0), 2, 1)) for n in noms]
    cases += [(f"16x16 + 48x32 : {n}", vignette(VOCABULAIRE[n], 16, (48, 32))) for n in noms]
    planche(cases, 4, ICI / "resolution-double.png", e=5, titre="Même dessin : matériel actuel (haut) / pas deux fois plus fin (bas)")
    # 6. Lisibilité à distance.
    planche_distance(ICI / "lisibilite-distance.png")
    # 7. Animation.
    animation(ICI / "vie-du-visage.gif")


if __name__ == "__main__":
    main()
