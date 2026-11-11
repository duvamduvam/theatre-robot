#!/usr/bin/env python3
"""Génère le schéma de câblage du banc témoin (B0) en SVG A4 paysage, noir pur.

Pourquoi un générateur plutôt qu'un dessin : le schéma doit suivre le code du robot
(broches, adresses, canaux relevés le 07/11 dans robot_config.py, wheels.py, relays.py,
status.py) ; une valeur qui change se corrige ici, une ligne, et le SVG se régénère.

Contraintes d'impression (imprimante thermique A4 de l'atelier) : noir pur, traits
≥ 0,125 mm, texte ≥ 7 pt (2,5 mm). Unités du SVG : millimètres.

Usage : schema_banc_temoin.py [sortie.svg]   (défaut : docs/etudes/banc-temoin-cablage.svg)
"""

from __future__ import annotations

import sys
from pathlib import Path

TRAIT = 0.4  # mm : fils
TRAIT_BOITE = 0.6
TEXTE = 3.0  # mm ≈ 8,5 pt
PETIT = 2.6  # mm ≈ 7,4 pt (minimum lisible)

elements: list[str] = []


def texte(x: float, y: float, s: str, taille: float = TEXTE, ancre: str = "start",
          gras: bool = False) -> None:
    poids = ' font-weight="bold"' if gras else ""
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    elements.append(f'<text x="{x}" y="{y}" font-size="{taille}" text-anchor="{ancre}"{poids}>{s}</text>')


def ligne(*points: tuple[float, float], epaisseur: float = TRAIT, tirets: bool = False) -> None:
    pts = " ".join(f"{x},{y}" for x, y in points)
    style = ' stroke-dasharray="1.5,1"' if tirets else ""
    elements.append(f'<polyline points="{pts}" fill="none" stroke="black" stroke-width="{epaisseur}"{style}/>')


def boite(x: float, y: float, l: float, h: float, titre: str, sous_titre: str = "") -> None:
    elements.append(f'<rect x="{x}" y="{y}" width="{l}" height="{h}" fill="none" stroke="black" '
                    f'stroke-width="{TRAIT_BOITE}"/>')
    texte(x + l / 2, y + 5, titre, TEXTE + 0.4, "middle", gras=True)
    if sous_titre:
        texte(x + l / 2, y + 9, sous_titre, PETIT, "middle")


def point(x: float, y: float) -> None:
    elements.append(f'<circle cx="{x}" cy="{y}" r="0.9" fill="black"/>')


def masse(x: float, y: float) -> None:
    """Symbole de masse : trait descendant puis trois barres."""
    ligne((x, y), (x, y + 3))
    for i, demi in enumerate((2.4, 1.6, 0.8)):
        ligne((x - demi, y + 3 + i * 0.9), (x + demi, y + 3 + i * 0.9))


def etiquette(x: float, y: float, nom: str, vers_droite: bool = True) -> None:
    """Étiquette de réseau (drapeau) : même nom = même fil."""
    largeur = len(nom) * 1.75 + 3
    x0 = x if vers_droite else x - largeur
    pointe = x0 + largeur + 2 if vers_droite else x0 - 2
    base = x0 + largeur if vers_droite else x0
    elements.append(
        f'<polygon points="{x0},{y - 2} {base},{y - 2} {pointe},{y} {base},{y + 2} {x0},{y + 2}" '
        f'fill="none" stroke="black" stroke-width="{TRAIT}"/>'
        if vers_droite else
        f'<polygon points="{pointe},{y} {base},{y - 2} {base + largeur},{y - 2} {base + largeur},{y + 2} '
        f'{base},{y + 2}" fill="none" stroke="black" stroke-width="{TRAIT}"/>')
    texte(x0 + largeur / 2, y + 1, nom, PETIT, "middle", gras=True)


def resistance(x1: float, x2: float, y: float, valeur: str) -> None:
    milieu = (x1 + x2) / 2
    ligne((x1, y), (milieu - 4, y))
    elements.append(f'<rect x="{milieu - 4}" y="{y - 1.3}" width="8" height="2.6" fill="none" '
                    f'stroke="black" stroke-width="{TRAIT}"/>')
    ligne((milieu + 4, y), (x2, y))
    texte(milieu, y - 2.2, valeur, PETIT, "middle")


def bouton(x: float, y: float) -> None:
    """Poussoir à fermeture entre (x, y) et (x+10, y)."""
    ligne((x, y), (x + 3, y))
    ligne((x + 7, y), (x + 10, y))
    ligne((x + 3, y - 1.8), (x + 7, y - 1.8))
    ligne((x + 5, y - 1.8), (x + 5, y - 3.5))


def broche(x: float, y: float, nom: str, cote: str) -> None:
    """Nom de broche écrit à l'intérieur d'une boîte, du côté du fil."""
    if cote == "droite":
        texte(x - 1.5, y + 1, nom, PETIT, "end")
    else:
        texte(x + 1.5, y + 1, nom, PETIT, "start")


# --- Titre --------------------------------------------------------------------------------
texte(148.5, 10, "Banc témoin — câblage (code du robot relevé le 07/11, plaque à bandes du 11/11)", 4.2, "middle", True)
texte(148.5, 15.5, "Même câblage logique que Didier : PCA9685 0x40 derrière un ISO1540, LED sur GPIO 18. "
      "Roues en l'air par un MDD10A (étage B3). Jx = connecteur de la plaque.", PETIT, "middle")

# --- Raspberry Pi 4 (da66fc96, démarre sur USB) -------------------------------------------
boite(8, 24, 62, 122, "Raspberry Pi 4", "da66fc96 · démarre sur USB")
PI_D = 70  # bord droit
pi = {
    "3V3": 46, "SDA": 54, "SCL": 62, "GND": 72, "G18": 92, "G12": 112, "G16": 124, "G20": 136,
}
broche(PI_D, pi["3V3"], "broche 1 · 3,3 V", "droite")
broche(PI_D, pi["SDA"], "broche 3 · SDA", "droite")
broche(PI_D, pi["SCL"], "broche 5 · SCL", "droite")
broche(PI_D, pi["GND"], "broche 6 · masse", "droite")
broche(PI_D, pi["G18"], "broche 12 · GPIO 18", "droite")
broche(PI_D, pi["G12"], "broche 32 · GPIO 12", "droite")
broche(PI_D, pi["G16"], "broche 36 · GPIO 16", "droite")
broche(PI_D, pi["G20"], "broche 38 · GPIO 20", "droite")
texte(12, 100, "broches 2 et 4 (5 V) :", PETIT, gras=True)
texte(12, 104, "NE RIEN BRANCHER", PETIT, gras=True)
texte(72, 68.5, "J1a (JST 4)", PETIT, gras=True)
texte(72, 88, "J1b (JST 4)", PETIT, gras=True)

# Alimentation propre du Pi
boite(8, 152, 62, 16, "Chargeur USB-C du Pi", "source 1 · SEULE alimentation du Pi")
ligne((39, 152), (39, 146), epaisseur=TRAIT_BOITE)

# --- Isolateur ISO1540, comme sur la carte Sécurité du robot ------------------------------
# Côté 1 = Pi (3,3 V), côté 2 = cartes (5 V). Les deux masses sont communes : il sépare et
# adapte le bus (3,3 V → 5 V), ce n'est pas une barrière galvanique.
boite(80, 32, 24, 52, "ISO1540", "3,3 V │ 5 V")
iso = {"3V3": 46, "SDA": 54, "SCL": 62, "GND": 72}
for net, nom1, nom2 in (("3V3", "VCC1", "VCC2"), ("SDA", "SDA1", "SDA2"), ("SCL", "SCL1", "SCL2")):
    ligne((PI_D, pi[net]), (80, iso[net]))
    broche(80, iso[net], nom1, "gauche")
    broche(104, iso[net], nom2, "droite")
broche(80, iso["GND"], "GND1", "gauche")
broche(104, 78, "GND2", "droite")
ligne((104, 78), (107, 78), (107, 82))
masse(107, 82)

# --- Bus 5 V derrière l'isolateur : colonnes verticales -----------------------------------
COL = {"5V": 110, "SDA": 115, "SCL": 120}
pca = {"5V": 38, "SDA": 46, "SCL": 54, "GND": 62}
j7 = {"5V": 98, "SDA": 106, "SCL": 114, "GND": 122}
for net, y_iso in (("5V", iso["3V3"]), ("SDA", iso["SDA"]), ("SCL", iso["SCL"])):
    x = COL[net]
    ligne((104, y_iso), (x, y_iso))
    point(x, y_iso)
    ligne((x, min(pca[net], y_iso)), (x, j7[net]))
    for y in (pca[net], j7[net]):
        ligne((x, y), (130, y))
        point(x, y)
ligne((COL["5V"], 38), (COL["5V"], 29))
etiquette(COL["5V"], 27, "5V BANC", vers_droite=False)

# Masse du Pi : le seul lien avec les alimentations du banc (comme sur le robot)
ligne((PI_D, pi["GND"]), (80, iso["GND"]))
ligne((76, pi["GND"]), (76, pi["GND"] + 4))
masse(76, pi["GND"] + 4)

# --- PCA9685 0x40 ROUES (sur la plaque) ---------------------------------------------------
boite(130, 24, 72, 62, "PCA9685 0x40", "roues ch 0-3 · servos ch 4+ (code actuel)")
for net, nom in (("5V", "VCC"), ("SDA", "SDA"), ("SCL", "SCL"), ("GND", "GND")):
    broche(130, pca[net], nom, "gauche")
ligne((130, pca["GND"]), (125, pca["GND"]))
masse(125, pca["GND"])
# OE : R10 vers le 5 V (PWM coupés par défaut), JP1 vers la masse (posé = roues actives)
broche(202, 33, "OE", "droite")
ligne((202, 33), (208, 33))
point(208, 33)
resistance(208, 226, 33, "R10 10 kΩ")
etiquette(226, 33, "5V BANC")
ligne((208, 33), (208, 35))
elements.append('<circle cx="208" cy="35.8" r="0.7" fill="none" stroke="black" stroke-width="0.3"/>')
elements.append('<circle cx="208" cy="38.2" r="0.7" fill="none" stroke="black" stroke-width="0.3"/>')
ligne((208, 39), (208, 39.5))
masse(208, 39.5)
texte(205, 39, "JP1 posé = roues actives", PETIT, "end")
CH = (48, 54, 60, 66)
for y, nom in zip(CH, ("ch 0 · sens G", "ch 1 · PWM G", "ch 2 · PWM D", "ch 3 · sens D")):
    broche(202, y, nom, "droite")
    resistance(202, 222, y, "")
    elements.append(f'<polygon points="222,{y - 1.6} 222,{y + 1.6} 225,{y}" fill="none" stroke="black" '
                    f'stroke-width="{TRAIT}"/>')
    ligne((225, y - 1.6), (225, y + 1.6))
    ligne((225, y), (229, y))
ligne((229, 48), (229, 68))
masse(229, 68)
texte(200, 71.5, "témoins : J4 + 4 × 330 Ω + LED", PETIT, "end")
broche(202, 76, "ch 4 · servo", "droite")
broche(202, 82, "V+ (bornier)", "droite")
ligne((202, 82), (206, 82))
etiquette(206, 82, "5V SERVOS")

# --- MDD10A et moteurs (étage B3, hors plaque) ---------------------------------------------
boite(246, 24, 46, 48, "MDD10A", "Cytron · hors plaque")
for y, s_ in ((36, "DIR1 ← ch 0 (J5)"), (40.5, "PWM1 ← ch 1 (J5)"), (45, "PWM2 ← ch 2 (J6)"),
              (49.5, "DIR2 ← ch 3 (J6)"), (54, "GND ← J5 / J6"), (59, "M1 → N20 gauche"), (63.5, "M2 → N20 droite")):
    texte(248, y, s_, PETIT)
texte(248, 68.5, "VIN ← 12V MOT", PETIT, gras=True)

# --- Alimentation des moteurs : chargeur 12 V (source 3) ------------------------------------
boite(240, 76, 52, 13, "Chargeur 12 V (jack)", "source 3 · ≥ 2 A · polarité vérifiée")
texte(242, 92, "+12 V → 1N5819 →", PETIT)
etiquette(270, 91, "12V MOT")
texte(242, 97, "12V MOT → LM2596 réglé à 5 V →", PETIT)
etiquette(242, 101.5, "5V SERVOS")
texte(242, 106.5, "(régler à vide, au multimètre)", PETIT)

# --- Modules déportés sur J7 (hors plaque, sur le socle) ------------------------------------
elements.append('<rect x="130" y="90" width="72" height="38" fill="none" stroke="black" '
                'stroke-width="0.6" stroke-dasharray="2.5,1.2"/>')
texte(166, 95, "Sur J7 (JST 4, hors plaque)", TEXTE + 0.4, "middle", gras=True)
for net, nom in (("5V", "5 V"), ("SDA", "SDA"), ("SCL", "SCL"), ("GND", "GND")):
    broche(130, j7[net], nom, "gauche")
ligne((130, j7["GND"]), (125, j7["GND"]))
masse(125, j7["GND"])
texte(150, 101.5, "→ PCF8574 0x21 (relais)", PETIT, gras=True)
texte(150, 105.5, "   cavaliers A0 = 1, A1 = A2 = 0", PETIT)
texte(150, 110.5, "→ PCA9685 0x41 (servos)", PETIT, gras=True)
texte(150, 114.5, "   V+ ←", PETIT)
etiquette(162, 114, "5V SERVOS")
texte(150, 120, "chaînés par leurs barrettes", PETIT)
texte(150, 124, "traversantes", PETIT)

# --- 74AHCT125 ----------------------------------------------------------------------------
boite(130, 138, 72, 56, "74AHCT125", "DIP-14 · 3,3 V → 5 V")
y_1a, y_oe, y_7, y_in = 150, 158, 166, 174
broche(130, y_1a, "2 · 1A", "gauche")
broche(130, y_oe, "1 · 1OE", "gauche")
broche(130, y_7, "7 · GND", "gauche")
broche(130, y_in, "5, 9, 12 · entrées libres", "gauche")
ligne((PI_D, pi["G18"]), (96, pi["G18"]), (96, y_1a), (130, y_1a))
texte(100, y_1a - 1.5, "données LED", PETIT)
for y in (y_oe, y_7, y_in):
    ligne((130, y), (120, y))
ligne((120, y_oe), (120, y_in + 2))
masse(120, y_in + 2)
y_14, y_oe2, y_1y = 150, 160, 176
broche(202, y_14, "14 · VCC", "droite")
broche(202, y_oe2, "4, 10, 13 · OE libres", "droite")
broche(202, y_1y, "3 · 1Y", "droite")
ligne((202, y_14), (208, y_14))
etiquette(208, y_14, "5V BANC")
ligne((202, y_oe2), (208, y_oe2))
etiquette(208, y_oe2, "5V BANC")
texte(166, 188, "+ C1 100 nF entre les broches 14 et 7", PETIT, "middle")

# --- Matrice WS2812B ----------------------------------------------------------------------
boite(240, 140, 50, 46, "Matrice", "WS2812B 8×8 · J3 (JST 3)")
resistance(202, 240, y_1y, "R2 330 Ω")
broche(240, y_1y, "DIN", "gauche")
broche(240, 156, "5 V", "gauche")
broche(290, 168, "GND", "droite")
etiquette(240, 156, "5V BANC", vers_droite=False)
ligne((290, 168), (293, 168))
masse(293, 168)
texte(265, 180, "courant par J2, pas les bandes", PETIT, "middle")
texte(265, 184, "C2 1 000 µF entre 5 V et GND", PETIT, "middle")

# --- Alimentation logique : DIANQI 5 V (source 2) -------------------------------------------
boite(240, 112, 50, 24, "DIANQI 5 V 4 A", "source 2 · bornier J2")
broche(240, 124, "+5 V", "gauche")
broche(240, 131, "GND", "gauche")
etiquette(240, 124, "5V BANC", vers_droite=False)
ligne((240, 131), (232, 131))
masse(232, 131)

# --- Boutons et LED d'état ----------------------------------------------------------------
for nom, cle in (("arrêt", "G16"), ("réarm. / appui long = extinction", "G20")):
    y = pi[cle]
    bouton(PI_D, y)
    ligne((PI_D + 10, y), (84, y))
    masse(84, y)
texte(72, pi["G16"] - 4, "SW1 arrêt", PETIT)
texte(72, pi["G20"] - 4, "SW2 réarm.", PETIT)
y = pi["G12"]
resistance(PI_D, 80, y, "R3 330")
elements.append(f'<polygon points="80,{y - 1.6} 80,{y + 1.6} 83,{y}" fill="none" stroke="black" '
                f'stroke-width="{TRAIT}"/>')
ligne((83, y - 1.6), (83, y + 1.6))
ligne((83, y), (86, y))
masse(86, y)
texte(84.5, y - 2.5, "D5 état", PETIT)

# --- Avertissement et légende -------------------------------------------------------------
elements.append(f'<rect x="8" y="173" width="110" height="30" fill="none" stroke="black" '
                f'stroke-width="1"/>')
texte(12, 179, "RÈGLE N° 1 (incident de la nappe du 04/11)", TEXTE, gras=True)
texte(12, 185, "Le Pi n'est alimenté QUE par son chargeur USB-C.", PETIT)
texte(12, 189.5, "Aucun fil entre les broches 5 V du Pi et le banc.", PETIT)
texte(12, 194, "Masse commune à tout ; 5 V, 12 V et servos séparés.", PETIT)
texte(12, 198.5, "Cartes I²C en 5 V derrière l'ISO1540, comme le robot.", PETIT)

texte(214, 197, "Légende : même étiquette = même fil ;", PETIT)
etiquette(214, 202, "5V BANC")
texte(232, 203, "= +5 V DIANQI ;", PETIT)
masse(262, 199.5)
texte(266, 203, "= masse commune", PETIT)

svg = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 297 210" '
    'font-family="DejaVu Sans, sans-serif">\n'
    '<rect width="297" height="210" fill="white"/>\n'
    + "\n".join(elements) + "\n</svg>\n"
)

sortie = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    Path(__file__).resolve().parents[2] / "docs/etudes/banc-temoin-cablage.svg"
sortie.write_text(svg, encoding="utf-8")
print(f"Schéma écrit : {sortie}")
