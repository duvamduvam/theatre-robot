#!/usr/bin/env python3
"""Génère schema-alim.svg : la distribution d'énergie de Didier, câble par câble.

Section, fusible et tension viennent de cahier-cablage.csv : le schéma ne recopie aucun
chiffre, il ne peut donc pas s'écarter du cahier. Le script refuse de produire le fichier
si une ligne de puissance ou de masse du cahier n'est pas dessinée.

Trait plein = ligne du cahier. Pointillé = câble ABSENT du cahier, proposé le 07/11, rien
n'est tranché. Couleurs : celles du cahier (étude intérieur §5), le jaune assombri pour
rester lisible sur fond blanc.

Usage : python3 schema_alim.py   (écrit schema-alim.svg à côté du cahier)
"""
import csv
from html import escape
from pathlib import Path

ICI = Path(__file__).parent
LIGNES = {l["repere"]: l for l in csv.DictReader(
    (ICI / "cahier-cablage.csv").open(encoding="utf-8"), delimiter=";")}
COULEUR = {"24V": "#c00000", "24V_MOT": "#e07000", "12V": "#a08a00",
           "12V_AUDIO": "#7a2fb0", "5V": "#1f5fd0", "": "#000000"}
LARGEUR, HAUTEUR = 1770, 1590
svg, dessines = [], set()


def texte(x, y, t, taille=13, ancre="start", gras=False, couleur="#000"):
    svg.append(f'<text x="{x}" y="{y}" font-size="{taille}" text-anchor="{ancre}" fill="{couleur}"'
               f'{" font-weight=\"bold\"" if gras else ""}>{escape(t)}</text>')


def boite(x, y, l, h, lignes, fond="#f2f2f2"):
    svg.append(f'<rect x="{x}" y="{y}" width="{l}" height="{h}" rx="4" fill="{fond}" stroke="#444"/>')
    y0 = y + h / 2 - (len(lignes) - 1) * 8 + 4
    for i, t in enumerate(lignes):
        texte(x + l / 2, y0 + i * 16, t, 13, "middle", gras=(i == 0))


def trait(points, couleur, epaisseur=2.5, pointille=False):
    p = " ".join(f"{x},{y}" for x, y in points)
    d = ' stroke-dasharray="9 6"' if pointille else ""
    svg.append(f'<polyline points="{p}" fill="none" stroke="{couleur}" stroke-width="{epaisseur}"{d}/>')


def fusible(x, y, calibre, couleur):
    svg.append(f'<rect x="{x - 21}" y="{y - 10}" width="42" height="20" fill="#fff" stroke="{couleur}" stroke-width="2"/>')
    texte(x, y + 5, f"{calibre} A", 12, "middle", True)


def etiquette(rep):
    """« P10 · 1,5 mm² · 5 A » : tout vient du cahier."""
    l = LIGNES[rep]
    dessines.add(rep)
    morceaux = [rep, f"{l['section_mm2'].replace('.', ',')} mm²"]
    if l["fusible_A"]:
        morceaux.append(f"{l['fusible_A'].replace('.', ',')} A")
    return " · ".join(morceaux)


def cable(rep, points, x_txt=None, y_txt=None):
    """Un câble du cahier, étiqueté par défaut au-dessus de son premier segment."""
    couleur = COULEUR[LIGNES[rep]["tension"]]
    trait(points, couleur, 3 if LIGNES[rep]["section_mm2"] in ("4", "6") else 2.5)
    x = x_txt if x_txt is not None else points[0][0] + 6
    y = y_txt if y_txt is not None else points[0][1] - 6
    texte(x, y, etiquette(rep), 12, couleur=couleur)
    return couleur


def zone(x, y, l, h, nom):
    svg.append(f'<rect x="{x}" y="{y}" width="{l}" height="{h}" rx="8" fill="#fafaf4" stroke="#bbb" stroke-dasharray="3 4"/>')
    texte(x + 10, y + 19, nom, 13, gras=True, couleur="#666")


# --- En-tête et légende
texte(30, 34, "Didier : distribution d'énergie, câble par câble (état du cahier au 07/11/2026)", 22, gras=True)
texte(30, 56, "Trait plein : ligne du cahier de câblage, avec repère · section · fusible.  "
              "Pointillé : câble absent du cahier, proposé, rien n'est tranché.", 13)
x = 30
for nom, cle in (("24 V permanent", "24V"), ("24 V moteurs", "24V_MOT"), ("12 V", "12V"),
                 ("12 V audio", "12V_AUDIO"), ("5 V", "5V"), ("masse", "")):
    trait([(x, 76), (x + 34, 76)], COULEUR[cle], 4)
    texte(x + 40, 81, nom, 13)
    x += 150

# --- Partie 1 : le côté plus
texte(30, 118, "1. Le côté plus", 18, gras=True)
zone(20, 130, 1060, 310, "CAISSE BASSE")
boite(40, 225, 120, 70, ["Pack 24 V", "+ BMS"], "#ffe9e9")
boite(40, 345, 120, 56, ["Chargeur", "Victron"])
cable("P16", [(100, 345), (100, 295)], 108)
BP = 470                                          # barre 24 V permanente (caisse basse)
fusible(310, 260, 40, COULEUR["24V"])
cable("P01", [(160, 260), (289, 260)])
cable("P02", [(331, 260), (BP, 260)], 338)
trait([(BP, 190), (BP, 400)], COULEUR["24V"], 7)
texte(BP - 14, 416, "Barre 24 V permanente", 12, "end", True)
boite(620, 165, 100, 60, ["Relais 40 A", "arrêt d'urgence"], "#ffe9e9")
cable("P03", [(BP, 195), (620, 195)], BP + 10)
BM = 860                                          # barre 24 V moteurs
trait([(BM, 150), (BM, 425)], COULEUR["24V_MOT"], 7)
texte(BM, 145, "Barre 24 V moteurs", 12, "middle", True)
cable("P04", [(720, 195), (BM, 195)], 726)

CHARGES_M = (("P05", "SmartDrive40 gauche"), ("P06", "SmartDrive40 droit"), ("P07", "ASME bras gauche"),
             ("P08", "ASME bras droit"), ("P09", "ASME cou (bouche)"))
for i, (rep, nom) in enumerate(CHARGES_M):
    y = 170 + i * 56
    fusible(BM + 50, y, LIGNES[rep]["fusible_A"].replace(".", ","), COULEUR["24V_MOT"])
    trait([(BM, y), (BM + 29, y)], COULEUR["24V_MOT"])
    cable(rep, [(BM + 71, y), (1100, y)], BM + 78)
    boite(1100, y - 21, 230, 42, [nom])

# Bloc permanent du coffre : sa liaison avec la barre de la caisse basse manque au cahier.
zone(20, 455, 1060, 780, "COFFRE")
BC = 300
trait([(BC, 500), (BC, 1190)], COULEUR["24V"], 7)
texte(BC, 1212, "Bloc 24 V permanent, 8 voies proposées", 12, "middle", True)
trait([(BP, 400), (BP, 440), (200, 440), (200, 520), (BC, 520)], COULEUR["24V"], 3, True)
texte(40, 500, "À ajouter : alimentation du", 12, couleur=COULEUR["24V"])
texte(40, 516, "bloc, 6 mm² proposés,", 12, couleur=COULEUR["24V"])
texte(40, 532, "sous le fusible général", 12, couleur=COULEUR["24V"])

CONV_X, CONV_L, N2_X, N2_L, N3_X = 560, 130, 1100, 230, 1500


def depart(rep, y):
    """Une voie du bloc permanent : barre, fusible, câble vers la droite."""
    fusible(BC + 50, y, LIGNES[rep]["fusible_A"], COULEUR["24V"])
    trait([(BC, y), (BC + 29, y)], COULEUR["24V"])
    cable(rep, [(BC + 71, y), (CONV_X, y)], BC + 78)


# SD-50B-5 n°2, contrôle : 5 V de la pile de cartes
depart("P10", 540)
boite(CONV_X, 515, CONV_L, 50, ["SD-50B-5 n°2", "contrôle"], "#e8f0ff")
fusible(880, 540, 10, COULEUR["5V"])
cable("P19", [(CONV_X + CONV_L, 540), (859, 540)], 696)
cable("P20", [(901, 540), (N2_X, 540)], 908)
boite(N2_X, 510, N2_L, 150, ["Carte Puissance", "J20 +5V", "J26, J27, J33"], "#e7f5e7")
for rep, nom, y in (("P22", "Pi 4", 530), ("P23", "Ruban LED bas", 585), ("P24", "Ruban LED yeux", 640)):
    cable(rep, [(N2_X + N2_L, y), (N3_X, y)], N2_X + N2_L + 4)
    boite(N3_X, y - 20, 240, 40, [nom])

# SD-50B-5 n°1, vision
depart("P11", 700)
boite(CONV_X, 675, CONV_L, 50, ["SD-50B-5 n°1", "vision"], "#e8f0ff")
cable("P21", [(CONV_X + CONV_L, 700), (N2_X, 700)], 700)
boite(N2_X, 680, N2_L, 40, ["Pi 5 (USB-C)"])

# SD-50B-12 : yeux, boucle d'arrêt, bobine du relais, odométrie
depart("P12", 790)
boite(CONV_X, 765, CONV_L, 100, ["SD-50B-12", "contrôle, 4,2 A"], "#fff7d6")
fusible(880, 790, 15, COULEUR["12V"])
cable("P17", [(CONV_X + CONV_L, 790), (859, 790)], 696)
cable("P18", [(901, 790), (N2_X, 790)], 908)
cable("P25", [(CONV_X + CONV_L, 845), (N2_X, 845)], 700)
boite(N2_X, 765, N2_L, 100, ["Carte Puissance", "J20 +12V ×2, J28", "J29, J25"], "#e7f5e7")
for rep, nom, y in (("P26", "Carte Moteurs V+ (yeux)", 785), ("P27", "Carte Odométrie J5", 845)):
    cable(rep, [(N2_X + N2_L, y), (N3_X, y)], N2_X + N2_L + 4)
    boite(N3_X, y - 20, 240, 40, [nom])

# SD-150B-12 : audio seul
depart("P13", 925)
boite(CONV_X, 900, CONV_L, 170, ["SD-150B-12", "audio, à acheter"], "#f1e6fa")
cable("P28", [(CONV_X + CONV_L, 925), (N2_X, 925)], 700)
boite(N2_X, 905, N2_L, 40, ["Ampli Focal (+12 V, REM)"])
cable("P29", [(CONV_X + CONV_L, 985), (N2_X, 985)], 700)
boite(N2_X, 965, N2_L, 60, ["Carte Audio", "J1, J7, J8"], "#e7f5e7")
for rep, nom, y in (("P31", "Klaxon", 975), ("P32", "Récepteur Shure BLX4", 1030)):
    cable(rep, [(N2_X + N2_L, y if rep == "P31" else 1015), (1480, y if rep == "P31" else 1015),
                (1480, y), (N3_X, y)], N2_X + N2_L + 4)
    boite(N3_X, y - 20, 240, 40, [nom])
cable("P30", [(CONV_X + CONV_L, 1050), (N2_X, 1050)], 700)
boite(N2_X, 1040, N2_L, 40, ["TC Helicon VoiceTone C1"])

# Petites voies
depart("P14", 1110)
boite(CONV_X, 1090, CONV_L, 40, ["Routeur RUT955"])
depart("P15", 1160)
boite(CONV_X, 1140, CONV_L, 40, ["Carte Puissance", "J20 24V_IN"], "#e7f5e7")
trait([(CONV_X + CONV_L, 1160), (N2_X, 1160)], COULEUR["24V"])
texte(700, 1154, "F5 sur la carte, sortie J32", 12, couleur=COULEUR["24V"])
boite(N2_X, 1140, N2_L, 40, ["Mini-voltmètre"])
texte(BC + 20, 1192, "+ 2 voies libres (proposition)", 12, couleur=COULEUR["24V"])

# --- Partie 2 : les retours de masse
Y0 = 1265
texte(30, Y0, "2. Les retours de masse", 18, gras=True)
ETOILE_Y = Y0 + 150
trait([(330, ETOILE_Y), (1500, ETOILE_Y)], "#000", 10)
texte(915, ETOILE_Y + 26, "Barre de masse en étoile (coffre)", 14, "middle", True)
HAUT = (("G02", "SD-50B-5 n°2 sortie −", 340), ("G03", "SD-50B-12 sortie −", 540),
        ("G04", "SD-50B-5 n°1 sortie −", 760), ("G05", "SD-150B-12 sortie −", 960),
        ("G07", "Carte Puissance J20 GND ×2", 1180))
for rep, nom, x in HAUT:
    boite(x, Y0 + 30, 190, 44, [nom])
    cable(rep, [(x + 95, Y0 + 74), (x + 95, ETOILE_Y)], x + 102, Y0 + 100)
texte(435, Y0 + 24, "domaine contrôle", 12, couleur="#666")
texte(855, Y0 + 24, "domaine vision et audio", 12, couleur="#666")
boite(40, Y0 + 30, 250, 44, ["À ajouter : moins d'entrée des", "4 convertisseurs et du routeur"], "#ffffff")
trait([(165, Y0 + 74), (165, ETOILE_Y), (330, ETOILE_Y)], "#000", 2.5, True)

BAS_Y = ETOILE_Y + 80
boite(600, BAS_Y, 170, 56, ["Pack −", "sortie BMS"], "#ffe9e9")
cable("G01", [(685, BAS_Y), (685, ETOILE_Y)], 692, BAS_Y - 34)
boite(1000, BAS_Y, 210, 56, ["Barre moins moteurs", "caisse basse"], "#ffe9e9")
boite(1330, BAS_Y, 340, 56, ["SmartDrive40 ×2 B−", "ASME ×3 : retour à ajouter"])
cable("G06", [(1330, BAS_Y + 28), (1210, BAS_Y + 28)], 1216)
trait([(1000, BAS_Y + 28), (770, BAS_Y + 28)], "#000", 4, True)
texte(885, BAS_Y + 20, "À ajouter", 12, "middle")
texte(885, BAS_Y + 48, "avis : vers le pack, l'étude dit vers l'étoile", 12, "middle")

# Le schéma n'a pas le droit d'oublier une ligne du cahier.
attendues = {r for r, l in LIGNES.items() if l["famille"] in ("puissance", "masse")}
manquantes = attendues - dessines
assert not manquantes, f"lignes du cahier non dessinées : {sorted(manquantes)}"

(ICI / "schema-alim.svg").write_text(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGEUR}" height="{HAUTEUR}" '
    f'viewBox="0 0 {LARGEUR} {HAUTEUR}" font-family="sans-serif">'
    f'<title>Didier : distribution d\'énergie, câble par câble</title>'
    f'<rect width="{LARGEUR}" height="{HAUTEUR}" fill="#fff"/>' + "".join(svg) + "</svg>\n",
    encoding="utf-8")
print(f"schema-alim.svg : {len(dessines)} lignes du cahier dessinées")
