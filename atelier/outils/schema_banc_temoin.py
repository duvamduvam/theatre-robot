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
texte(148.5, 10, "Banc témoin B0 — câblage (relevé dans le code du robot, 07/11/2026)", 4.2, "middle", True)
texte(148.5, 15.5, "Aucun moteur, aucun driver moteur. Même câblage logique que Didier : PCA9685 0x40, "
      "PCF8574 0x21, LED sur GPIO 18.", PETIT, "middle")

# --- Raspberry Pi 4 (da66fc96, démarre sur USB) -------------------------------------------
boite(8, 24, 62, 122, "Raspberry Pi 4", "da66fc96 · démarre sur USB")
PI_D = 70  # bord droit
pi = {
    "3V3": 40, "SDA": 50, "SCL": 60, "GND": 72, "G18": 88, "G12": 112, "G16": 124, "G20": 136,
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

# Alimentation propre du Pi
boite(8, 152, 62, 16, "Chargeur USB-C du Pi", "SEULE alimentation du Pi")
ligne((39, 152), (39, 146), epaisseur=TRAIT_BOITE)

# --- Bus I²C et 3,3 V : colonnes verticales ----------------------------------------------
COL = {"3V3": 100, "SDA": 106, "SCL": 112}
pca = {"3V3": 38, "SDA": 46, "SCL": 54, "GND": 62}
pcf = {"3V3": 98, "SDA": 106, "SCL": 114, "GND": 122}
for net in ("3V3", "SDA", "SCL"):
    x = COL[net]
    ligne((PI_D, pi[net]), (x, pi[net]))
    point(x, pi[net])
    ligne((x, min(pca[net], pi[net])), (x, pcf[net]))
    for y in (pca[net], pcf[net]):
        ligne((x, y), (130, y))
        point(x, y)
texte(COL["3V3"], 30, "3,3 V", PETIT, "middle")
texte(COL["SDA"] + 0.5, 34, "SDA", PETIT, "middle")
texte(COL["SCL"] + 1, 30, "SCL", PETIT, "middle")

# Masse du Pi : le seul lien avec l'alimentation du banc
ligne((PI_D, pi["GND"]), (80, pi["GND"]))
masse(80, pi["GND"])
texte(74, pi["GND"] + 11, "masse commune", PETIT)

# --- PCA9685 ------------------------------------------------------------------------------
boite(130, 24, 72, 62, "PCA9685", "0x40 · servos ET roues")
for net, nom in (("3V3", "VCC"), ("SDA", "SDA"), ("SCL", "SCL"), ("GND", "GND")):
    broche(130, pca[net], nom, "gauche")
ligne((130, pca["GND"]), (124, pca["GND"]))
masse(124, pca["GND"])
broche(202, 32, "V+ (bornier)", "droite")
ligne((202, 32), (208, 32))
etiquette(208, 32, "5V BANC")
broche(202, 44, "ch 0 · sens G", "droite")
broche(202, 51, "ch 1 · PWM G", "droite")
broche(202, 58, "ch 2 · PWM D", "droite")
broche(202, 65, "ch 3 · sens D", "droite")
for y in (44, 51, 58, 65):
    resistance(202, 222, y, "330 Ω")
    # LED témoin : triangle + barre, cathode vers la masse
    elements.append(f'<polygon points="222,{y - 1.6} 222,{y + 1.6} 225,{y}" fill="none" stroke="black" '
                    f'stroke-width="{TRAIT}"/>')
    ligne((225, y - 1.6), (225, y + 1.6))
    ligne((225, y), (229, y))
point(229, 51)
ligne((229, 44), (229, 68))
masse(229, 68)
texte(233, 48, "4 LED témoins", PETIT)
texte(233, 52, "(facultatif)", PETIT)
texte(233, 58, "JAMAIS de driver", PETIT, gras=True)
texte(233, 62, "moteur sur 0 à 3", PETIT, gras=True)
broche(202, 78, "ch 4 · cou", "droite")
ligne((202, 78), (212, 78))
texte(213, 79, "servo facultatif (emprunté à la tête), alimenté par V+", PETIT)

# --- PCF8574 ------------------------------------------------------------------------------
boite(130, 90, 72, 38, "PCF8574", "0x21 · relais")
for net, nom in (("3V3", "VCC"), ("SDA", "SDA"), ("SCL", "SCL"), ("GND", "GND")):
    broche(130, pcf[net], nom, "gauche")
ligne((130, pcf["GND"]), (124, pcf["GND"]))
masse(124, pcf["GND"])
texte(200, 108, "cavaliers : A0 = 1,", PETIT, "end")
texte(200, 112, "A1 = 0, A2 = 0", PETIT, "end")
texte(200, 120, "vérifier : 8574, pas 8575", PETIT, "end", gras=True)

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
texte(166, 188, "+ 100 nF entre les broches 14 et 7", PETIT, "middle")

# --- Matrice WS2812B ----------------------------------------------------------------------
boite(240, 140, 50, 46, "Matrice", "WS2812B 8×8")
resistance(202, 240, y_1y, "330 Ω")
broche(240, y_1y, "DIN", "gauche")
broche(240, 156, "5 V", "gauche")
broche(290, 168, "GND", "droite")
etiquette(240, 156, "5V BANC", vers_droite=False)
ligne((290, 168), (293, 168))
masse(293, 168)
texte(265, 182, "+ 470 à 1 000 µF", PETIT, "middle")
texte(265, 185.5, "entre 5 V et GND", PETIT, "middle")

# --- Alimentation du banc DIANQI ------------------------------------------------------------
boite(240, 90, 50, 40, "DIANQI D-30A", "alimentation du banc")
broche(240, 104, "+5 V", "gauche")
broche(240, 112, "GND", "gauche")
broche(240, 120, "+12 V", "gauche")
etiquette(240, 104, "5V BANC", vers_droite=False)
ligne((240, 112), (232, 112))
masse(232, 112)
texte(238, 123, "isolé", PETIT, "end", gras=True)
texte(265, 127, "luminosité LED bridée", PETIT, "middle")

# --- Boutons et LED d'état ----------------------------------------------------------------
for nom, cle in (("arrêt", "G16"), ("réarm. / appui long = extinction", "G20")):
    y = pi[cle]
    bouton(PI_D, y)
    ligne((PI_D + 10, y), (84, y))
    masse(84, y)
texte(72, pi["G16"] - 4, "arrêt", PETIT)
texte(72, pi["G20"] - 4, "réarm.", PETIT)
y = pi["G12"]
resistance(PI_D, 80, y, "330 Ω")
elements.append(f'<polygon points="80,{y - 1.6} 80,{y + 1.6} 83,{y}" fill="none" stroke="black" '
                f'stroke-width="{TRAIT}"/>')
ligne((83, y - 1.6), (83, y + 1.6))
ligne((83, y), (86, y))
masse(86, y)
texte(84.5, y - 2.5, "état", PETIT)

# --- Avertissement et légende -------------------------------------------------------------
elements.append(f'<rect x="8" y="173" width="110" height="30" fill="none" stroke="black" '
                f'stroke-width="1"/>')
texte(12, 179, "RÈGLE N° 1 (incident de la nappe du 04/11)", TEXTE, gras=True)
texte(12, 185, "Le Pi n'est alimenté QUE par son chargeur USB-C.", PETIT)
texte(12, 189.5, "Aucun fil entre les broches 5 V du Pi et le banc.", PETIT)
texte(12, 194, "Seule la masse est commune, par un seul fil (broche 6).", PETIT)
texte(12, 198.5, "GPIO 20 : appui court = réarmement, long = éteint le Pi du banc.", PETIT)

texte(214, 197, "Légende : même étiquette = même fil ;", PETIT)
etiquette(214, 202, "5V BANC")
texte(232, 203, "= +5 V de la DIANQI ;", PETIT)
masse(268, 199.5)
texte(272, 203, "= masse commune", PETIT)

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
