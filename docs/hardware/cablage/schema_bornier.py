#!/usr/bin/env python3
"""Génère bornier-distribution.svg : le plan simple du bornier, une ligne par tension.

Vert = bornier à vis 5,08 de 2 points, comme ceux du coffre. Gris = cosse à vis, pour tout
câble de plus de 2,5 mm² : la fiche verte n'en accepte pas davantage, et sa série est
annoncée autour de 10 A. Fusible et section viennent de cahier-cablage.csv.

Le moins est regroupé par domaine, puis un seul fil par domaine va à l'étoile : c'est la règle
de l'étude §6 (une cosse par domaine), et cela évite de saturer la barre.

Usage : python3 schema_bornier.py
"""
import csv
from html import escape
from pathlib import Path

ICI = Path(__file__).parent
LIGNES = {l["repere"]: l for l in csv.DictReader(
    (ICI / "cahier-cablage.csv").open(encoding="utf-8"), delimiter=";")}
SECTION_MAX_VERT = 2.5
R, M, J, A, B = "#c00000", "#e07000", "#a08a00", "#7a2fb0", "#1f5fd0"
RANGEES = (
    ("24 V PERMANENT", R, ["Depuis le pack"], (("P10", "SD-50B-5", "contrôle"), ("P11", "SD-50B-5", "vision"),
     ("P12", "SD-50B-12", ""), ("P13", "SD-150B-12", "audio"), ("P14", "Routeur", ""),
     ("P15", "Carte", "Puissance"), None, None)),
    ("24 V MOTEURS", M, ["Après le relais"], (("P05", "SmartDrive", "gauche"), ("P06", "SmartDrive", "droit"),
     ("P07", "ASME", "bras gauche"), ("P08", "ASME", "bras droit"), ("P09", "ASME", "cou"), None)),
    ("12 V CONTRÔLE", J, ["SD-50B-12"], (("P18", "Carte Puissance", "J20"), ("P25", "Carte Puissance", "J28"), None)),
    ("12 V AUDIO", A, ["SD-150B-12"], (("P28", "Ampli", "Focal"), ("P29", "Carte", "Audio"),
     ("P30", "VoiceTone", ""), None)),
    ("5 V CONTRÔLE", B, ["SD-50B-5 contrôle"], (("P20", "Carte Puissance", "J20"),)),
    ("5 V VISION", B, ["SD-50B-5 vision"], (("P21", "Pi 5", ""),)),
)
ENTREE_COSSE = {"24 V PERMANENT", "24 V MOTEURS", "12 V AUDIO"}   # 6 mm², ou 12,5 A de la SD-150
LARG, HAUT_R, X0, PAS = 1420, 128, 400, 124
HAUT = 112 + HAUT_R * (len(RANGEES) + 1) + 40
svg = []


def texte(x, y, t, taille=15, ancre="middle", gras=False, couleur="#000"):
    g = ' font-weight="bold"' if gras else ""
    svg.append(f'<text x="{x}" y="{y}" font-size="{taille}" text-anchor="{ancre}" fill="{couleur}"{g}>{escape(t)}</text>')


def rect(x, y, l, h, fond, bord="#333", r=4):
    svg.append(f'<rect x="{x}" y="{y}" width="{l}" height="{h}" rx="{r}" fill="{fond}" stroke="{bord}" stroke-width="1.5"/>')


def borne(x, y, cosse):
    """Une sortie : bornier vert 2 points, ou deux cosses à vis si le câble est trop gros."""
    rect(x, y, 88, 40, "#9a9a9a" if cosse else "#2e9e4f")
    for i, s in enumerate("+-"):
        cx = x + 24 + i * 40
        svg.append(f'<circle cx="{cx}" cy="{y + 20}" r="11" fill="#e8e8e8" stroke="#333"/>')
        texte(cx, y + 26, s, 18, gras=True)


texte(30, 42, "Bornier de distribution de Didier", 28, "start", True)
texte(30, 70, "Une ligne par tension. Chaque + passe par son fusible. Le − de chaque ligne rejoint la barre de masse.", 16, "start")
rect(30, 84, 30, 18, "#2e9e4f")
texte(68, 99, "bornier à vis 2 points, comme ceux du coffre", 14, "start")
rect(420, 84, 30, 18, "#9a9a9a")
texte(458, 99, "cosse à vis : câble trop gros pour le bornier vert", 14, "start")
rect(850, 84, 30, 18, "#fff", "#999")
texte(888, 99, "emplacement libre", 14, "start")

for i, (nom, c, entree, sorties) in enumerate(RANGEES):
    y = 118 + i * HAUT_R
    rect(30, y, LARG - 60, HAUT_R - 12, "#fafaf6", "#ccc", 8)
    rect(30, y, 12, HAUT_R - 12, c, c, 3)
    texte(54, y + 62, nom, 17, "start", True, c)
    texte(292, y + 24, "ENTRÉE", 13, gras=True)
    borne(248, y + 32, nom in ENTREE_COSSE)
    texte(292, y + 92, entree[0], 13)
    # Le bus : l'entrée alimente tous les fusibles de la ligne
    bus_y = y + 14
    svg.append(f'<polyline points="336,{y + 44} 372,{y + 44} 372,{bus_y} {X0 + 44 + (len(sorties) - 1) * PAS},{bus_y}" '
               f'fill="none" stroke="{c}" stroke-width="4"/>')
    for k, s in enumerate(sorties):
        x = X0 + k * PAS
        svg.append(f'<line x1="{x + 44}" y1="{bus_y}" x2="{x + 44}" y2="{y + 44}" stroke="{c}" stroke-width="3"/>')
        if s is None:
            rect(x, y + 44, 88, 40, "#fff", "#999")
            texte(x + 44, y + 69, "libre", 13, couleur="#777")
            continue
        rep, l1, l2 = s
        ligne = LIGNES[rep]
        rect(x + 22, y + 22, 44, 20, "#fff", c, 2)
        texte(x + 44, y + 37, f"{ligne['fusible_A'].replace('.', ',')} A", 13, gras=True)
        borne(x, y + 44, float(ligne["section_mm2"]) > SECTION_MAX_VERT)
        texte(x + 44, y + 100, l1, 13, gras=True)
        if l2:
            texte(x + 44, y + 114, l2, 12)

y = 118 + len(RANGEES) * HAUT_R
rect(30, y, LARG - 60, HAUT_R - 12, "#f0f0f0", "#ccc", 8)
rect(30, y, 12, HAUT_R - 12, "#000", "#000", 3)
texte(54, y + 62, "MASSE", 17, "start", True)
rect(250, y + 42, 1020, 18, "#222", "#000", 2)
texte(760, y + 30, "barre de masse en étoile, une seule liaison par groupe", 14, gras=True)
for k, t in enumerate(("Pack −", "24 V −", "Contrôle −", "Vision et audio −", "Moteurs − (à trancher)")):
    x = 340 + k * 205
    svg.append(f'<circle cx="{x}" cy="{y + 51}" r="9" fill="#c9b57a" stroke="#000"/>')
    texte(x, y + 88, t, 14, gras=True)

(ICI / "bornier-distribution.svg").write_text(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARG}" height="{HAUT}" viewBox="0 0 {LARG} {HAUT}" '
    f'font-family="sans-serif"><title>Bornier de distribution de Didier</title>'
    f'<rect width="{LARG}" height="{HAUT}" fill="#fff"/>' + "".join(svg) + "</svg>\n", encoding="utf-8")
print("bornier-distribution.svg écrit")
