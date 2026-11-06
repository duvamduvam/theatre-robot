#!/usr/bin/env python3
"""Génère schema-dessus.svg : les trois platines vues de dessus, avec tous les câbles.

Platines et porte-fusibles sont à l'échelle (2 px/mm), avec les cotes relues dans
plans/elec/bloc-24v/bloc-24v.scad. Le placement des platines entre elles, les convertisseurs
et les charges ne sont PAS à l'échelle : la place réelle attend les mesures M9 et M12.

Section et fusible viennent de cahier-cablage.csv. Trait plein = ligne du cahier.
Pointillé = câble absent du cahier, proposé, rien n'est tranché. Le script refuse de produire
le fichier si une ligne de puissance ou de masse du cahier n'est pas dessinée.

Usage : python3 schema_dessus.py [chemin de bloc-24v.scad]
"""
import csv
import re
import sys
from html import escape
from pathlib import Path

ICI = Path(__file__).parent
SCAD = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    ICI.parents[5].parent / "plans/elec/bloc-24v/bloc-24v.scad"
TXT = SCAD.read_text(encoding="utf-8")


def cote(nom):
    return float(re.search(rf"^{nom}\s*=\s*([\d.]+)", TXT, re.M).group(1))


L, FUS_L, FUS_W, FUS4_L = cote("L"), cote("FUS_L"), cote("FUS_W"), cote("FUS4_L")
BAR_L, BAR_W, MARGE, JEU, NERV = cote("BAR_L"), cote("BAR_W"), cote("MARGE"), cote("JEU"), cote("NERV_EP")
BANDE = cote("BANDE")
W = MARGE + FUS_W + 2 * JEU + NERV + BAR_W + BANDE
S = 2                                    # px par mm sur les platines
PAS, BORNE1, GOUJON = 13.46, 32.3, 9.5   # lus à l'échelle du dessin de la fiche Blue Sea, ±1 mm

LIGNES = {l["repere"]: l for l in csv.DictReader(
    (ICI / "cahier-cablage.csv").open(encoding="utf-8"), delimiter=";")}
COUL = {"24V": "#c00000", "24V_MOT": "#e07000", "12V": "#a08a00",
        "12V_AUDIO": "#7a2fb0", "5V": "#1f5fd0", "": "#000000"}
LARG, HAUT = 2060, 1660
svg, dessines = [], set()


def texte(x, y, t, taille=12, ancre="start", gras=False, couleur="#000", halo="#fff"):
    g = ' font-weight="bold"' if gras else ""
    svg.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{taille}" text-anchor="{ancre}" '
               f'fill="{couleur}" stroke="{halo}" stroke-width="3" paint-order="stroke"{g}>{escape(t)}</text>')


def rect(x, y, l, h, fond, bord="#444", r=3):
    svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{l:.1f}" height="{h:.1f}" rx="{r}" fill="{fond}" stroke="{bord}"/>')


def boite(x, y, l, h, lignes, fond="#f2f2f2"):
    rect(x, y, l, h, fond)
    y0 = y + h / 2 - (len(lignes) - 1) * 7.5 + 4
    for i, t in enumerate(lignes):
        texte(x + l / 2, y0 + i * 15, t, 12, "middle", gras=(i == 0))


def fil(pts, couleur, ep=2.2, pointille=False):
    d = ' stroke-dasharray="8 5"' if pointille else ""
    p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    svg.append(f'<polyline points="{p}" fill="none" stroke="{couleur}" stroke-width="{ep}" stroke-linejoin="round"{d}/>')


def nom(rep):
    l = LIGNES[rep]
    dessines.add(rep)
    m = [rep, l["section_mm2"].replace(".", ",") + " mm²"]
    if l["fusible_A"]:
        m.append(l["fusible_A"].replace(".", ",") + " A")
    return " · ".join(m)


def cable(rep, pts, lab=None, ancre="start"):
    """Câble du cahier ; lab = position de l'étiquette, sinon pas d'étiquette répétée."""
    c = COUL[LIGNES[rep]["tension"]]
    fil(pts, c, 3 if LIGNES[rep]["section_mm2"] in ("4", "6") else 2.2)
    if lab:
        texte(lab[0], lab[1], nom(rep), 11, ancre, couleur=c)
    dessines.add(rep)


def ajout(pts, couleur, lab=None, t="", ancre="start"):
    fil(pts, couleur, 2, True)
    if lab:
        texte(lab[0], lab[1], t, 11, ancre, couleur=couleur)


class Platine:
    def __init__(self, x, y, titre, cote_titre="gauche"):
        self.x, self.y = x, y
        rect(x, y, L * S, W * S, "#dbe7f3", "#2a6ea8", 8)
        if cote_titre == "gauche":
            texte(x - 10, y + 22, titre, 13, "end", True, "#2a6ea8")
        else:
            texte(x + L * S + 10, y + W * S - 6, titre, 13, gras=True, couleur="#2a6ea8")
        for sx in (14, (L - 7) * S - 7):
            for sy in (14, (W - 7) * S):
                svg.append(f'<circle cx="{x + sx:.1f}" cy="{y + sy:.1f}" r="5" fill="#fff" stroke="#2a6ea8"/>')

    def px(self, mx):            # X modèle (0 au milieu) vers px
        return self.x + (mx + L / 2) * S

    def py(self, my):            # Y modèle (0 au milieu, + vers le haut) vers px
        return self.y + (W / 2 - my) * S


def fusibles(p, x0, y0, long_mm, voies, haut=False, couleur="#333"):
    """x0 : bout côté goujon, y0 : bord côté bornes, en mm modèle. haut : rangée retournée."""
    sens = -1 if haut else 1
    xa, xb = sorted((x0, x0 + sens * long_mm))
    ya, yb = sorted((y0, y0 + sens * FUS_W))
    rect(p.px(xa), p.py(yb), long_mm * S, FUS_W * S, "#4a4a4a", "#111")
    bornes = [(p.px(x0 + sens * (BORNE1 + i * PAS)), p.py(y0 + sens * 6)) for i in range(voies)]
    for bx, by in bornes:
        svg.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="6" fill="#c9b57a" stroke="#000"/>')
    gx, gy = p.px(x0 + sens * GOUJON), p.py(y0 + sens * FUS_W / 2)
    svg.append(f'<circle cx="{gx:.1f}" cy="{gy:.1f}" r="6" fill="#ffd27a" stroke="#000"/>')
    return (gx, gy), bornes


def barre(p, y_bas):
    rect(p.px(-BAR_L / 2), p.py(y_bas + BAR_W), BAR_L * S, BAR_W * S, "#3c3c3c", "#111")
    rect(p.px(-BAR_L / 2 + 8), p.py(y_bas + BAR_W / 2 + 5), (BAR_L - 16) * S, 20, "#c9b57a", "#111", 1)
    return [p.px(-60 + i * 13.33) for i in range(10)], p.py(y_bas + BAR_W / 2)


# ---------------------------------------------------------------- en-tête
texte(24, 34, "Didier : les trois platines vues de dessus, avec tout le câblage de puissance", 22, gras=True)
texte(24, 54, "Platines et porte-fusibles à l'échelle. Placement, convertisseurs et charges non à l'échelle.  "
              "Trait plein : cahier de câblage.  Pointillé : absent du cahier, proposé.", 13)
x = 24
for t, k in (("24 V permanent", "24V"), ("24 V moteurs", "24V_MOT"), ("12 V contrôle", "12V"),
             ("12 V audio", "12V_AUDIO"), ("5 V", "5V"), ("masse", "")):
    fil([(x, 72), (x + 30, 72)], COUL[k], 4)
    texte(x + 36, 76, t, 12)
    x += 150

R, M, J, A, B, K = COUL["24V"], COUL["24V_MOT"], COUL["12V"], COUL["12V_AUDIO"], COUL["5V"], "#000"

# ---------------------------------------------------------------- platine 24 V permanent
P1 = Platine(620, 170, "Platine 24 V PERMANENT (coffre)")
y_f0 = -W / 2 + MARGE
g1, t1 = fusibles(P1, -FUS_L / 2, y_f0, FUS_L, 8)
bv, by = barre(P1, y_f0 + FUS_W + 2 * JEU + NERV)
ynerv = P1.py(y_f0 + FUS_W + JEU + NERV)
rect(P1.px(-75), ynerv, 150 * S, NERV * S, "#2a6ea8", "#2a6ea8", 0)
texte(P1.px(0), by + 26, "barre de masse en étoile", 11, "middle", True, "#fff", "#3c3c3c")

C = {"n2": (120, 540), "b12": (350, 540), "n1": (1030, 540), "s150": (1250, 540)}
CW, CH = 190, 84
boite(*C["n2"], CW, CH, ["SD-50B-5 n°2", "contrôle, 5 V"], "#e8f0ff")
boite(*C["b12"], CW, CH, ["SD-50B-12", "contrôle, 12 V, 4,2 A"], "#fff7d6")
boite(*C["n1"], CW, CH, ["SD-50B-5 n°1", "vision, 5 V"], "#e8f0ff")
boite(*C["s150"], CW, CH, ["SD-150B-12", "audio, 12 V, à acheter"], "#f1e6fa")
boite(1040, 395, 180, 44, ["Routeur RUT955"])


def descend(rep, b, y, xc, lab):
    bx, by_ = b
    cable(rep, [(bx, by_), (bx, y), (xc, y), (xc, 540)], lab)


descend("P10", t1[0], 415, 280, (290, 410))
descend("P12", t1[1], 450, 510, (520, 445))
cable("P15", [t1[2], (t1[2][0], 490), (604, 490), (604, 1000), (400, 1000), (400, 1060)], (612, 485))
descend("P11", t1[3], 490, 1100, (900, 485))
descend("P13", t1[4], 455, 1320, (1240, 450))
cable("P14", [t1[5], (t1[5][0], 417), (1040, 417)], (t1[5][0] + 10, 412))
texte(t1[7][0] + 12, t1[7][1] + 4, "2 libres", 11, couleur=R)

# ---------------------------------------------------------------- platine basse tension
P2 = Platine(620, 770, "Platine 12 V / 5 V (coffre)", "droite")
rect(P2.px(-75), P2.py(NERV / 2), 150 * S, NERV * S, "#2a6ea8", "#2a6ea8", 0)
gb, tb = fusibles(P2, -14.5, -W / 2 + MARGE, FUS4_L, 4)
gh, th = fusibles(P2, 14.5, W / 2 - MARGE, FUS4_L, 4, haut=True)


def fus5(p, x, y, t):
    rect(p.px(x) - 42, p.py(y) - 14, 84, 28, "#fff", B)
    texte(p.px(x), p.py(y) + 5, t, 12, "middle", True, B)


fus5(P2, -50, -28, "5 V, 10 A")
fus5(P2, 50, 28, "5 V, 10 A")
texte(P2.px(-50), P2.py(-28) - 20, "contrôle, réf. à choisir", 11, "middle")
texte(P2.px(50), P2.py(28) + 32, "vision, réf. à choisir", 11, "middle")

# Vision et audio, à droite
ajout([(1345, 624), (1345, 672), (gh[0], 672), (gh[0], gh[1])], A, (1120, 666),
      "à ajouter : SD-150 + vers bus 12 V audio, 4 mm² proposés")
for rep, b, yl, xv, yb, n in (("P28", th[2], 712, 1510, 700, "Ampli Focal"),
                              ("P29", th[1], 728, 1524, 755, "Carte Audio J1, J7, J8"),
                              ("P30", th[0], 744, 1500, 810, "VoiceTone C1")):
    cable(rep, [b, (b[0], yl), (xv, yl), (xv, yb), (1540, yb)], (1056, yl - 3))
    boite(1540, yb - 21, 210, 42, [n], "#e7f5e7" if rep == "P29" else "#f2f2f2")
texte(th[3][0], th[3][1] - 22, "1 voie libre", 11, "middle", couleur=A)
cable("P31", [(1750, 745), (1830, 745), (1830, 720)], (1758, 738))
boite(1800, 678, 200, 42, ["Klaxon"])
cable("P32", [(1750, 765), (1830, 765), (1830, 790)], (1758, 782))
boite(1800, 790, 200, 42, ["Récepteur Shure BLX4"])
cable("P21", [(1125, 624), (1125, 640), (P2.px(50), 640), (P2.px(50), P2.py(28) - 14)], (1000, 634))
cable("P21", [(P2.px(50) + 42, P2.py(28)), (1020, P2.py(28)), (1020, 870), (1540, 870)], (1056, 864))
boite(1540, 849, 210, 42, ["Pi 5 (USB-C)"])

# Contrôle, à gauche
cable("P19", [(215, 624), (215, 648), (574, 648), (574, 1020), (P2.px(-70), 1020),
              (P2.px(-70), P2.py(-28) + 14)], (222, 642))
cable("P17", [(445, 624), (445, 640), (590, 640), (590, 1006), (gb[0], 1006), (gb[0], gb[1])], (452, 636))
cable("P20", [(P2.px(-30), P2.py(-28) + 14), (P2.px(-30), 1034), (452, 1034), (452, 1090), (430, 1090)], (620, 1046))
cable("P18", [tb[0], (tb[0][0], 1048), (466, 1048), (466, 1120), (430, 1120)], (624, 1060))
cable("P25", [tb[1], (tb[1][0], 1062), (480, 1062), (480, 1150), (430, 1150)], (640, 1074))
texte(tb[3][0] + 10, tb[3][1] + 26, "2 voies libres", 11, couleur=J)

boite(130, 1060, 300, 120, ["Carte Puissance", "J20 : 24V_IN, +12V ×2, +5V, GND ×2",
                            "J28, J25, J26, J27, J29, J33, J32"], "#e7f5e7")
ORIG = (("P22", "Pi 4", 150, B), ("P23", "Ruban LED bas", 280, B), ("P24", "Ruban LED yeux", 410, B),
        ("P26", "Moteurs V+ (yeux)", 540, J), ("P27", "Odométrie J5", 670, J))
for i, (rep, n, xb, c) in enumerate(ORIG):
    xs = 160 + i * 56
    yl = 1224 - i * 8                       # le départ le plus à droite passe au-dessus
    cable(rep, [(xs, 1180), (xs, yl), (xb + 55, yl), (xb + 55, 1240)], (xb + 60, 1235))
    boite(xb, 1240, 118, 40, [n])
fil([(404, 1180), (404, 1296), (900, 1296), (900, 1280)], R)
texte(640, 1312, "J32 vers mini-voltmètre, sous le fusible F5 de la carte", 11, couleur=R)
boite(842, 1240, 118, 40, ["Mini-voltmètre"])

# ---------------------------------------------------------------- platine moteurs
Y3 = 1395
P3 = Platine(620, Y3, "Platine 24 V MOTEURS (caisse basse)")
g3, t3 = fusibles(P3, -FUS_L / 2, y_f0, FUS_L, 8)
bv3, by3 = barre(P3, y_f0 + FUS_W + 2 * JEU + NERV)
rect(P3.px(-75), P3.py(y_f0 + FUS_W + JEU + NERV), 150 * S, NERV * S, "#2a6ea8", "#2a6ea8", 0)
texte(P3.px(0), by3 + 26, "barre moins moteurs", 11, "middle", True, "#fff", "#3c3c3c")

boite(30, Y3 + 62, 110, 62, ["Pack", "+ BMS"], "#ffe9e9")
boite(30, Y3 + 160, 110, 40, ["Chargeur"])
cable("P16", [(85, Y3 + 160), (85, Y3 + 124)], (92, Y3 + 146))
rect(250, Y3 + 82, 42, 22, "#fff", R)
texte(271, Y3 + 98, "40 A", 12, "middle", True)
cable("P01", [(140, Y3 + 93), (250, Y3 + 93)], (146, Y3 + 86))
cable("P02", [(292, Y3 + 93), (370, Y3 + 93)], (272, Y3 + 120))
fil([(370, Y3 + 36), (370, Y3 + 150)], R, 7)
texte(370, Y3 + 166, "Barre 24 V permanente", 11, "middle", True)
boite(462, Y3 + 120, 104, 50, ["Relais 40 A", "arrêt d'urgence"], "#ffe9e9")
cable("P03", [(370, Y3 + 140), (462, Y3 + 140)], (376, Y3 + 134))
cable("P04", [(566, Y3 + 140), (592, Y3 + 140), (592, g3[1]), g3], (514, Y3 + 186))

MOT = (("P05", "SmartDrive40 gauche", 4), ("P06", "SmartDrive40 droit", 3), ("P07", "ASME bras gauche", 2),
       ("P08", "ASME bras droit", 1), ("P09", "ASME cou (bouche)", 0))
for i, (rep, n, b) in enumerate(MOT):
    yb = Y3 + 12 + i * 44
    yl = Y3 + 222 + (4 - b) * 9
    xv = 1030 + (4 - b) * 13
    cable(rep, [t3[b], (t3[b][0], yl), (xv, yl), (xv, yb), (1220, yb)], (1096, yb - 5))
    boite(1220, yb - 19, 220, 38, [n])
texte(t3[7][0] + 12, t3[7][1] + 4, "3 libres", 11, couleur=M)

# ---------------------------------------------------------------- masses
ajout([(370, Y3 + 36), (370, Y3 + 20), (20, Y3 + 20), (20, g1[1]), g1], R, (28, 340),
      "à ajouter : alimentation du bloc, 6 mm² proposés")

def vers_barre(rep, pts, vis, lab=None, ajoute=False):
    """Retour vers une vis de la barre en étoile, par le haut de la platine."""
    fin = [(bv[vis], 128 + vis * 3), (bv[vis], by)]
    if ajoute:
        ajout(pts + fin, K, lab, rep)
    else:
        cable(rep, pts + fin, lab)


vers_barre("G02", [(135, 624), (135, 660), (96, 660), (96, 128)], 0, (100, 150))
vers_barre("G03", [(365, 624), (365, 664), (84, 664), (84, 131)], 1, (100, 166))
vers_barre("G07", [(130, 1080), (72, 1080), (72, 134)], 2, (100, 182))
vers_barre("moins d'entrée SD-50B-5 n°2", [(190, 540), (190, 137)], 3, (196, 200), True)
vers_barre("moins d'entrée SD-50B-12", [(365, 540), (365, 140)], 4, (370, 232), True)
vers_barre("moins d'entrée SD-50B-5 n°1", [(1045, 540), (1045, 143)], 9, (900, 200), True)
vers_barre("moins d'entrée SD-150B-12", [(1265, 540), (1265, 146)], 8, (1120, 200), True)
vers_barre("moins routeur", [(1205, 395), (1205, 149)], 7, (1100, 216), True)
vers_barre("G04", [(1045, 624), (1045, 656), (1460, 656), (1460, 152)], 6, (1466, 300))
vers_barre("G05", [(1265, 624), (1265, 644), (1474, 644), (1474, 155)], 5, (1480, 320))
vers_barre("retours ampli, Audio, VoiceTone, Pi 5", [(1650, 891), (1650, 915), (1488, 915), (1488, 158)], 5,
           (1494, 340), True)
cable("G01", [(50, Y3 + 62), (50, 122), (P1.px(0), 122), (P1.px(0), P1.y)], (58, 500))
texte(P1.px(0) + 6, 118, "G01 arrive sur un goujon de la barre", 11, couleur=K)

# Moteurs : retours par le haut de la platine
cable("G06", [(1220, Y3 + 12 - 8), (1190, Y3 + 12 - 8), (1190, Y3 - 22), (bv3[8], Y3 - 22), (bv3[8], by3)], (1000, Y3 - 28))
fil([(1220, Y3 + 48), (1190, Y3 + 48), (1190, Y3 + 4)], K)
ajout([(1440, Y3 + 100), (1460, Y3 + 100), (1460, Y3 - 36), (bv3[6], Y3 - 36), (bv3[6], by3)], K,
      (1240, Y3 - 42), "à ajouter : retours des 3 ASME")
ajout([(bv3[0], by3), (bv3[0], Y3 - 22), (110, Y3 - 22), (110, Y3 + 62)], K, (150, Y3 - 28),
      "à ajouter : barre moins moteurs vers Pack −, avis ; l'étude dit vers l'étoile")

attendues = {r for r, l in LIGNES.items() if l["famille"] in ("puissance", "masse")}
manquantes = attendues - dessines
assert not manquantes, f"lignes du cahier non dessinées : {sorted(manquantes)}"

(ICI / "schema-dessus.svg").write_text(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARG}" height="{HAUT}" viewBox="0 0 {LARG} {HAUT}" '
    f'font-family="sans-serif"><title>Didier : platines vues de dessus, tout le câblage de puissance</title>'
    f'<rect width="{LARG}" height="{HAUT}" fill="#fff"/>' + "".join(svg) + "</svg>\n", encoding="utf-8")
print(f"schema-dessus.svg : {len(dessines)} lignes du cahier dessinées")
