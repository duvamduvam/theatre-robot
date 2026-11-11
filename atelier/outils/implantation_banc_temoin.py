#!/usr/bin/env python3
"""Génère l'implantation du banc témoin sur plaque à pastilles soudée (SVG A4 paysage, noir pur).

Pourquoi un générateur : chaque trou, chaque fil est une donnée ; une correction (brochage
lu sur un vrai module, déplacement d'un composant) se fait ici en une ligne, et le dessin
ET la liste des fils se régénèrent ensemble, sans écart possible entre les deux.

Sources des brochages (rien n'est supposé) :
- PCA9685 (format HW-170) : support 1×6 GND · OE · SCL · SDA · VCC · V+ (pcb/kicad/carrier_design.py) ;
- ISO1540 Adafruit 4903 : deux rangées VCC · SCL · SDA · GND à 12,70 mm (lu dans le fichier
  Eagle officiel le 05/11, même source) ;
- PCF8574 HW-171 : VCC · GND · SDA · SCL (même source) — entraxe entre ses deux barrettes
  « à confirmer » depuis juillet, d'où un seul support dessiné ;
- 74AHCT125 : brochage DIP-14 standard ; adresses et GPIO : code du robot (étude §8).
À VÉRIFIER sur les modules réels avant de souder : les clones changent parfois l'ordre.

Vue de dessus (côté composants). Les fils sont sous la plaque : un fil peut passer sous un
composant, et deux fils isolés peuvent se croiser ; un point noir = soudure commune.

Usage : implantation_banc_temoin.py [sortie.svg]   (défaut : docs/etudes/banc-temoin-implantation.svg)
        implantation_banc_temoin.py --liste        (liste des fils en Markdown)
"""

from __future__ import annotations

import sys
from pathlib import Path

PAS = 2.54  # mm entre deux trous
ECHELLE = 1.6  # le dessin n'est PAS à l'échelle 1:1 : on compte les trous
COLS, RANGS = 63, 39  # plaque 160 × 100 mm
X0, Y0 = 31.0, 24.0
TEXTE, PETIT = 3.0, 2.6

el: list[str] = []


def P(c: float, r: float) -> tuple[float, float]:
    return (X0 + (c + 0.5) * PAS * ECHELLE, Y0 + (r + 0.5) * PAS * ECHELLE)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def texte(x: float, y: float, s: str, t: float = PETIT, ancre: str = "start", gras: bool = False) -> None:
    g = ' font-weight="bold"' if gras else ""
    el.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{t}" text-anchor="{ancre}"{g}>{esc(s)}</text>')


def texte_trou(c: float, r: float, s: str, dx: float = 0, dy: float = 0, ancre: str = "start",
               gras: bool = False) -> None:
    x, y = P(c, r)
    texte(x + dx, y + dy + 0.9, s, PETIT, ancre, gras)


STYLE = {  # réseau -> (épaisseur, tirets)
    "5V": (0.9, ""), "GND": (0.55, "1.6,0.9"), "3V3": (0.55, "0.4,0.7"),
}


def fil(reseau: str, *trous: tuple[int, int]) -> None:
    ep, tirets = STYLE.get(reseau, (0.4, ""))
    pts = " ".join("{:.2f},{:.2f}".format(*P(c, r)) for c, r in trous)
    d = f' stroke-dasharray="{tirets}"' if tirets else ""
    el.append(f'<polyline points="{pts}" fill="none" stroke="black" stroke-width="{ep}" '
              f'stroke-linejoin="round"{d}/>')
    FILS.append((reseau, trous[0], trous[-1]))


def jonction(c: int, r: int) -> None:
    x, y = P(c, r)
    el.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.0" fill="black"/>')


def pastille(c: int, r: int, carree: bool = False) -> None:
    x, y = P(c, r)
    if carree:
        el.append(f'<rect x="{x - 1.1:.2f}" y="{y - 1.1:.2f}" width="2.2" height="2.2" fill="black"/>')
    else:
        el.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.1" fill="black"/>')


def contour(c1: float, r1: float, c2: float, r2: float, titre: str, sous: str = "",
            indicatif: bool = False) -> None:
    x1, y1 = P(c1 - 0.5, r1 - 0.5)
    x2, y2 = P(c2 + 0.5, r2 + 0.5)
    d = ' stroke-dasharray="2.5,1.2"' if indicatif else ""
    el.append(f'<rect x="{x1:.2f}" y="{y1:.2f}" width="{x2 - x1:.2f}" height="{y2 - y1:.2f}" '
              f'fill="none" stroke="black" stroke-width="0.5"{d}/>')
    texte((x1 + x2) / 2, y1 + 4.2, titre, TEXTE, "middle", True)
    if sous:
        texte((x1 + x2) / 2, y1 + 7.6, sous, PETIT, "middle")


def resistance(c1: int, r1: int, c2: int, r2: int, valeur: str, cote: str = "droite") -> None:
    """Résistance couchée entre deux trous (corps dessiné au milieu)."""
    (x1, y1), (x2, y2) = P(c1, r1), P(c2, r2)
    el.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="black" stroke-width="0.4"/>')
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    if r1 == r2:
        el.append(f'<rect x="{mx - 4:.2f}" y="{my - 1.4:.2f}" width="8" height="2.8" fill="white" stroke="black" stroke-width="0.4"/>')
        texte(mx, my - 2.2, valeur, PETIT, "middle")
    else:
        el.append(f'<rect x="{mx - 1.4:.2f}" y="{my - 4:.2f}" width="2.8" height="8" fill="white" stroke="black" stroke-width="0.4"/>')
        texte(mx + (2.4 if cote == "droite" else -2.4), my + 1, valeur, PETIT, "start" if cote == "droite" else "end")
    pastille(c1, r1)
    pastille(c2, r2)


def led(c1: int, r1: int, c2: int, r2: int) -> None:
    """LED entre deux trous ; anode = (c1, r1) carrée, cathode = (c2, r2)."""
    (x1, y1), (x2, y2) = P(c1, r1), P(c2, r2)
    el.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="black" stroke-width="0.4"/>')
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    if r1 == r2:
        el.append(f'<polygon points="{mx - 1.6:.2f},{my - 1.8:.2f} {mx - 1.6:.2f},{my + 1.8:.2f} {mx + 1.6:.2f},{my:.2f}" fill="white" stroke="black" stroke-width="0.4"/>')
        el.append(f'<line x1="{mx + 1.6:.2f}" y1="{my - 1.8:.2f}" x2="{mx + 1.6:.2f}" y2="{my + 1.8:.2f}" stroke="black" stroke-width="0.4"/>')
    else:
        el.append(f'<polygon points="{mx - 1.8:.2f},{my - 1.6:.2f} {mx + 1.8:.2f},{my - 1.6:.2f} {mx:.2f},{my + 1.6:.2f}" fill="white" stroke="black" stroke-width="0.4"/>')
        el.append(f'<line x1="{mx - 1.8:.2f}" y1="{my + 1.6:.2f}" x2="{mx + 1.8:.2f}" y2="{my + 1.6:.2f}" stroke="black" stroke-width="0.4"/>')
    pastille(c1, r1, carree=True)
    pastille(c2, r2)


def barrette(c: int, r0: int, noms: list[str], cote: str = "gauche", titre: str = "") -> None:
    """Barrette verticale : une pastille par broche, nom écrit du côté demandé."""
    for i, nom in enumerate(noms):
        pastille(c, r0 + i, carree=(i == 0))
        if cote == "gauche":
            texte_trou(c, r0 + i, nom, dx=-2.2, ancre="end")
        elif cote == "droite":
            texte_trou(c, r0 + i, nom, dx=2.2)
    if titre:
        texte_trou(c, r0 - 1, titre, ancre="middle", gras=True, dy=-0.4)


FILS: list[tuple[str, tuple[int, int], tuple[int, int]]] = []

# ------------------------------------------------------------------- titre et plaque
texte(148.5, 9, "Banc témoin — implantation sur plaque à pastilles 160 × 100 mm (vue de dessus)", 4.2, "middle", True)
texte(148.5, 14.5, "Dessin agrandi ×1,6 : compter les trous (colonnes 0-62, rangées 0-38). "
      "Fils sous la plaque ; un point noir = soudure commune.", PETIT, "middle")
bx1, by1 = P(-0.5, -0.5)
bx2, by2 = P(COLS - 0.5, RANGS - 0.5)
el.append(f'<rect x="{bx1:.2f}" y="{by1:.2f}" width="{bx2 - bx1:.2f}" height="{by2 - by1:.2f}" '
          f'fill="none" stroke="black" stroke-width="0.8"/>')
for c in range(COLS):
    for r in range(RANGS):
        x, y = P(c, r)
        el.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.35" fill="none" stroke="black" stroke-width="0.13"/>')
for c in range(0, COLS, 5):
    x, _ = P(c, 0)
    texte(x, by1 - 1.2, str(c), PETIT, "middle")
for r in range(0, RANGS, 5):
    _, y = P(0, r)
    texte(bx2 + 1.2, y + 0.9, str(r), PETIT, "start")

# ------------------------------------------------------------------- J1 : vers le Pi
# Fils Dupont un par un depuis le Pi : AUCUNE broche 5 V ne peut arriver sur la plaque.
J1 = ["3,3 V (1)", "SCL (5)", "SDA (3)", "GND (6)", "GPIO12 (32)", "GPIO16 (36)", "GPIO20 (38)", "GPIO18 (12)"]
barrette(1, 3, J1, cote="gauche", titre="J1 Pi")

# ------------------------------------------------------------------- ISO1540
contour(5, 1, 12, 8, "ISO1540", "", indicatif=True)
barrette(6, 3, ["", "", "", ""], cote="none")
barrette(11, 3, ["", "", "", ""], cote="none")
for i, nom in enumerate(["VCC", "SCL", "SDA", "GND"]):
    texte_trou(8.5, 3 + i, nom, ancre="middle")
texte_trou(6, 7, "côté 1", ancre="middle")
texte_trou(11, 7, "côté 2", ancre="middle")
fil("3V3", (1, 3), (6, 3))
fil("I2C", (1, 4), (6, 4))
fil("I2C", (1, 5), (6, 5))
fil("GND", (1, 6), (6, 6))

# ------------------------------------------------------------------- épines et rails
# GND : colonne 14 + rangée 38 ; 5 V : colonne 15 + rangée 37 ; SCL : colonne 17 ; SDA : colonne 18
fil("GND", (14, 2), (14, 38))
fil("5V", (15, 0), (15, 37))
fil("I2C", (17, 4), (17, 27))
fil("I2C", (18, 5), (18, 26))
fil("GND", (4, 38), (61, 38))
fil("5V", (13, 37), (61, 37))
jonction(14, 38)
jonction(15, 37)
texte_trou(14, 38, "GND", dx=-1.5, dy=4.2, ancre="end", gras=True)
texte_trou(61, 37, "5 V", dx=2.4, gras=True)
texte_trou(61, 38, "GND", dx=2.4, gras=True)

fil("5V", (11, 3), (15, 3))
jonction(15, 3)
fil("I2C", (11, 4), (17, 4))
jonction(17, 4)
fil("I2C", (11, 5), (18, 5))
jonction(18, 5)
fil("GND", (11, 6), (14, 6))
jonction(14, 6)
texte_trou(16.6, 9, "SCL", ancre="end")
texte_trou(18.4, 9, "SDA", ancre="start")

# ------------------------------------------------------------------- PCA9685 0x40 ROUES
contour(22, 0, 46, 9, "PCA9685 0x40 — ROUES", "aucun driver moteur, jamais", indicatif=True)
barrette(22, 2, ["GND", "OE", "SCL", "SDA", "VCC", "V+"], cote="droite")
fil("GND", (22, 2), (14, 2))
jonction(14, 2)
fil("I2C", (22, 4), (17, 4))
fil("I2C", (22, 5), (18, 5))
fil("5V", (22, 6), (15, 6))
jonction(15, 6)
# OE_WHEELS : R10 10 kΩ vers 5 V = PWM coupés par défaut ; cavalier JP1 vers GND = roues actives
fil("OE", (22, 3), (19, 3))
jonction(20, 3)
resistance(20, 3, 20, 0, "10k", cote="droite")
fil("5V", (20, 0), (15, 0))
pastille(19, 3, carree=True)
pastille(19, 2)
jonction(19, 2)
texte_trou(19, 2.5, "JP1", dx=-2, ancre="end", gras=True)
texte_trou(20, 1, "R10", dx=-1.8, ancre="end")
texte_trou(22, 7, "V+ : bornier vert du module", dx=2.2, dy=4)

# ------------------------------------------------------------------- PCA9685 0x41 SERVOS
contour(22, 11, 46, 20, "PCA9685 0x41 — SERVOS", "facultatif tant que le code vise 0x40", indicatif=True)
barrette(22, 13, ["GND", "OE", "SCL", "SDA", "VCC", "V+"], cote="droite")
fil("GND", (22, 13), (14, 13))
jonction(14, 13)
fil("GND", (22, 14), (21, 14), (21, 13))
jonction(21, 13)
fil("I2C", (22, 15), (17, 15))
jonction(17, 15)
fil("I2C", (22, 16), (18, 16))
jonction(18, 16)
fil("5V", (22, 17), (15, 17))
jonction(15, 17)

# ------------------------------------------------------------------- PCF8574 0x21 relais
contour(22, 22, 41, 29, "PCF8574 0x21", "relais · cavaliers A0=1 A1=0 A2=0", indicatif=True)
barrette(22, 24, ["VCC", "GND", "SDA", "SCL"], cote="droite")
fil("5V", (22, 24), (15, 24))
jonction(15, 24)
fil("GND", (22, 25), (14, 25))
jonction(14, 25)
fil("I2C", (22, 26), (18, 26))
jonction(18, 26)
fil("I2C", (22, 27), (17, 27))
jonction(17, 27)

# ------------------------------------------------------------------- 74AHCT125 (support DIP-14)
contour(29, 30, 37, 33, "", "", indicatif=False)
for i in range(7):
    pastille(30 + i, 33, carree=(i == 0))  # broches 1 à 7
    pastille(30 + i, 30)  # broches 14 à 8
    texte_trou(30 + i, 33, str(i + 1), ancre="middle", dy=-2.0)
    texte_trou(30 + i, 30, str(14 - i), ancre="middle", dy=2.8)
texte_trou(28.6, 31.5, "74AHCT125", ancre="end", gras=True)
# Alimentation et entrées libres
fil("5V", (30, 30), (30, 29), (34, 29))
fil("5V", (31, 30), (31, 29))
fil("5V", (34, 30), (34, 29))
fil("5V", (29, 29), (30, 29))
fil("5V", (29, 29), (29, 37))
jonction(29, 37)
jonction(30, 29)
jonction(31, 29)
fil("GND", (32, 30), (32, 28), (37, 28))
fil("GND", (35, 30), (35, 28))
fil("GND", (37, 28), (37, 38))
jonction(35, 28)
jonction(37, 38)
fil("GND", (30, 33), (30, 34), (28, 34), (28, 38))
jonction(28, 38)
fil("5V", (33, 33), (33, 37))
jonction(33, 37)
fil("GND", (34, 33), (34, 34), (36, 34))
fil("GND", (36, 33), (36, 38))
jonction(36, 34)
jonction(36, 38)
# Données LED : GPIO18 -> 1A (broche 2) ; 1Y (broche 3) -> 330 Ω -> DIN de la matrice
fil("LED", (1, 10), (2, 10), (2, 35), (31, 35), (31, 33))
fil("LED", (32, 33), (32, 36), (40, 36))
resistance(40, 36, 47, 36, "R2 330 Ω")
fil("LED", (47, 36), (61, 36))
texte_trou(20, 35, "GPIO18 → 1A", dy=-1.6)
# Découplage
resistance(38, 37, 38, 38, "", cote="droite")
texte_trou(38, 37.5, "C1 100 nF", dx=2.4)

# ------------------------------------------------------------------- J3 : matrice WS2812B
barrette(61, 35, ["", "DIN", "5V", "GND"], cote="none")
texte_trou(61, 36, "DIN", dx=2.4, gras=True)
texte_trou(61, 34, "J3 matrice", ancre="end", dx=1, gras=True)
pastille(55, 37, carree=True)
pastille(55, 38)
texte_trou(55, 38, "C2 1000 µF (+ en haut)", ancre="middle", dy=4.4)
jonction(55, 37)
jonction(55, 38)

# ------------------------------------------------------------------- J2 : alimentation 5 V
barrette(12, 36, ["+5 V", "", "GND"], cote="gauche")
texte_trou(12, 34.6, "J2 alim", ancre="middle", gras=True)
fil("5V", (12, 36), (13, 36), (13, 37))
jonction(12, 38)

# ------------------------------------------------------------------- J4 + LED témoins des roues
barrette(50, 1, ["ch 0", "ch 1", "ch 2", "ch 3", "GND"], cote="gauche", titre="J4")
for i in range(4):
    resistance(50, 1 + i, 53, 1 + i, "")
    led(54, 1 + i, 57, 1 + i)
    fil("GND", (57, 1 + i), (58, 1 + i))
fil("GND", (58, 1), (58, 38))
fil("GND", (50, 5), (58, 5))
jonction(58, 5)
jonction(58, 38)
for i in (2, 3, 4):
    jonction(58, i)
texte_trou(51.5, 6, "4 × 330 Ω + 4 LED", dy=0.6)
texte_trou(50, 7, "Dupont depuis les sorties PWM 0-3", dy=0.5)
texte_trou(50, 8, "du PCA9685 ROUES", dy=1.2)

# ------------------------------------------------------------------- LED d'état et boutons
fil("SIG", (1, 7), (4, 7), (4, 12))
resistance(4, 12, 4, 17, "R3 330", cote="gauche")
led(4, 19, 4, 22)
fil("SIG", (4, 17), (4, 19))
fil("GND", (4, 22), (4, 38))
jonction(4, 38)
texte_trou(4, 23, "état", dx=-2, ancre="end")
for c_bouton, rang_j1, nom in ((6, 8, "SW1"), (9, 9, "SW2")):
    fil("SIG", (1, rang_j1), (c_bouton, rang_j1), (c_bouton, 20))
    pastille(c_bouton, 20)
    pastille(c_bouton, 22)
    bx, by = P(c_bouton - 0.6, 20)
    el.append(f'<rect x="{bx:.2f}" y="{by:.2f}" width="{1.2 * PAS * ECHELLE:.2f}" height="{2 * PAS * ECHELLE:.2f}" '
              f'fill="none" stroke="black" stroke-width="0.4"/>')
    texte_trou(c_bouton, 23.2, nom, ancre="middle", dy=1.2)
    fil("GND", (c_bouton, 22), (c_bouton, 38))
    jonction(c_bouton, 38)

# ------------------------------------------------------------------- légende
lx, ly = 14, 191
texte(lx, ly - 4, "Légende :", TEXTE, gras=True)
for i, (reseau, nom) in enumerate((("5V", "5 V du banc"), ("GND", "masse"), ("3V3", "3,3 V du Pi"),
                                   ("I2C", "signal (I²C, LED, boutons)"))):
    x = lx + i * 46
    ep, t = STYLE.get(reseau, (0.4, ""))
    d = f' stroke-dasharray="{t}"' if t else ""
    el.append(f'<line x1="{x}" y1="{ly}" x2="{x + 10}" y2="{ly}" stroke="black" stroke-width="{ep}"{d}/>')
    texte(x + 12, ly + 1, nom, PETIT)
texte(lx + 184, ly + 1, "□ broche 1 / anode ; tirets = module", PETIT)
texte(lx, ly + 12.5, "SW1 = arrêt (GPIO16), SW2 = réarmement (GPIO20, appui long = éteint le Pi du banc). Brochages à vérifier sur les modules réels avant de souder.", PETIT)
texte(lx, ly + 7, "RÈGLE N° 1 : le Pi n'est alimenté QUE par son USB-C ; J1 en fils Dupont un par un, "
      "aucune broche 5 V du Pi sur la plaque. JP1 posé = roues actives ; retiré = PWM roues coupés.", PETIT, gras=True)

svg = ('<?xml version="1.0" encoding="UTF-8"?>\n'
       '<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 297 210" '
       'font-family="DejaVu Sans, sans-serif">\n<rect width="297" height="210" fill="white"/>\n'
       + "\n".join(el) + "\n</svg>\n")

if __name__ == "__main__":
    if "--liste" in sys.argv:
        print("| Réseau | De (col, rang) | À (col, rang) |\n|---|---|---|")
        for reseau, a, b in FILS:
            print(f"| {reseau} | {a[0]}, {a[1]} | {b[0]}, {b[1]} |")
    else:
        sortie = Path(sys.argv[1]) if len(sys.argv) > 1 else \
            Path(__file__).resolve().parents[2] / "docs/etudes/banc-temoin-implantation.svg"
        sortie.write_text(svg, encoding="utf-8")
        print(f"Implantation écrite : {sortie}")
