#!/usr/bin/env python3
"""Génère l'implantation du banc témoin sur PLAQUE À BANDES (stripboard), avec vérification.

Même circuit que `implantation_banc_temoin.py` (plaque à pastilles) et que le schéma
`schema_banc_temoin.py`. Sur une plaque à bandes, chaque rangée est une bande de cuivre continue :
le circuit se fait par COUPURES (foret de 3-4 mm tourné à la main sur le trou, côté cuivre) et par
STRAPS (fils posés côté composants, soudés à leurs deux bouts seulement).

Pourquoi un générateur qui VÉRIFIE : sur une plaque à bandes, une coupure oubliée ou un strap
décalé d'un trou fait un court-circuit invisible. Le script reconstruit les liaisons électriques
(bandes moins coupures, plus straps) et les compare à la liste des réseaux attendus : il refuse
d'écrire le dessin s'il trouve un court-circuit ou une coupure de trop.

Choix d'implantation :
- les rangées des modules sont ALIGNÉES sur les bandes : ISO1540 côté 2 → SCL rangée 5, SDA
  rangée 6, comme le support du PCA9685 ROUES (GND · OE · SCL · SDA · VCC · V+, rangées 3 à 8) :
  le bus I²C passe par le cuivre, sans strap ;
- liaisons hors plaque en JST-XH (détrompées, verrouillées) : J1a I²C (4 pts) en face de
  l'ISO1540, J1b GPIO (4 pts), J3 matrice (3 pts), J5/J6 vers le MDD10A (3 pts) ; côté Pi, câble
  JST → Dupont femelle, fil par fil : aucune broche 5 V du Pi n'arrive sur la plaque ;
- J5/J6 sortent les canaux roues AVANT les résistances des témoins : les LED restent branchées
  en parallèle et montrent ce que reçoit le driver ;
- les LED témoins des roues alternent signal et masse (J4 = ch0 · GND · ch1 · GND · ch2 · GND · ch3) :
  chaque LED tient entre deux bandes voisines, sa résistance est EN LIGNE sur la bande (une coupure
  entre ses deux pattes) ;
- la matrice WS2812B ne tire JAMAIS son courant par les bandes : ses fils d'alimentation vont au
  bornier J2 ; J3 ne porte que DIN et la référence.

Brochages : mêmes sources et même réserve que la plaque à pastilles (À VÉRIFIER sur les modules
réels avant de souder). Les contours des modules sont INDICATIFS : poser les modules à blanc
sur leurs barrettes avant de souder.

Plaque : 60 × 140 mm (54 trous × 25 bandes, compté par David : 25 bandes), la seule du stock assez grande (11/11) ; le
PCA9685 0x41 et le PCF8574 n'y tiennent pas : ils se branchent en chaîne sur J7, hors plaque.

Usage : implantation_banc_temoin_bandes.py [sortie.svg]  (défaut : docs/etudes/banc-temoin-bandes.svg)
        implantation_banc_temoin_bandes.py --liste       (coupures, straps, composants en Markdown)
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

PAS = 2.54
ECHELLE = 1.8  # dessin agrandi : on compte les trous
COLS, RANGS = 54, 25  # plaque à bandes 60 × 140 mm, bandes dans la longueur
X0, Y0 = 34.0, 26.0
TEXTE, PETIT = 3.0, 2.6

Trou = tuple[int, int]

# =================================================================== données du circuit
# Broches : (trou, réseau, repère). Le réseau sert à la vérification.
BROCHES: list[tuple[Trou, str, str]] = []
# Straps (fils côté composants) : (réseau, trou A, trou B)
STRAPS: list[tuple[str, Trou, Trou]] = []
# Coupures de bande (côté cuivre) : le trou coupé ne touche plus rien
COUPURES: set[Trou] = set()
# Composants à deux pattes posés à travers ou le long des bandes : (repère, valeur, A, B)
DIPOLES: list[tuple[str, str, Trou, Trou, str]] = []  # (repère, valeur, A, B, sorte)


def broche(c: int, r: int, reseau: str, repere: str) -> None:
    BROCHES.append(((c, r), reseau, repere))


def strap(reseau: str, a: Trou, b: Trou) -> None:
    STRAPS.append((reseau, a, b))


def couper(c: int, *rangs: int) -> None:
    for r in rangs:
        COUPURES.add((c, r))


def dipole(repere: str, valeur: str, a: Trou, net_a: str, b: Trou, net_b: str, sorte: str) -> None:
    DIPOLES.append((repere, valeur, a, b, sorte))
    broche(*a, net_a, f"{repere}.1")
    broche(*b, net_b, f"{repere}.2")


# ------------------------------------------------------------------- J1a (I²C du Pi) + ISO1540
J1A = [("3V3", "3,3 V (1)"), ("SCL_PI", "SCL (5)"), ("SDA_PI", "SDA (3)"), ("GND", "GND (6)")]
for i, (net, _) in enumerate(J1A):
    broche(0, 4 + i, net, f"J1a.{i + 1}")
for i, (n1, n2) in enumerate((("3V3", "5V"), ("SCL_PI", "SCL"), ("SDA_PI", "SDA"), ("GND", "GND"))):
    broche(5, 4 + i, n1, f"ISO.côté1.{i + 1}")
    broche(10, 4 + i, n2, f"ISO.côté2.{i + 1}")
couper(7, 4, 5, 6)  # sépare les deux côtés de l'ISO1540 (la masse, commune, n'est pas coupée)
couper(13, 4)  # VCC2 (5 V) | OE des roues
couper(11, 7)  # masse côté gauche | 5 V du bus
strap("5V", (12, 4), (12, 7))  # VCC2 de l'ISO1540 au 5 V du bus
strap("GND", (1, 3), (1, 7))  # masse du Pi et de l'ISO1540 à la bande GND du bus (bande 3)

# ------------------------------------------------------------------- PCA9685 0x40 ROUES (bandes 3-8)
PCA_BROCHES = ["GND", "OE", "SCL", "SDA", "VCC", "V+"]
for i, nom in enumerate(PCA_BROCHES):
    net = {"OE": "OE_ROUES", "VCC": "5V", "V+": "V+_ROUES"}.get(nom, nom)
    broche(15, 3 + i, net, f"PCA40.{nom}")
couper(13, 8)  # V+ des roues : la bande ne va pas dans la zone de gauche
dipole("R10", "10 kΩ", (40, 4), "OE_ROUES", (40, 7), "5V", "resistance")
broche(41, 3, "GND", "JP1.2")
broche(41, 4, "OE_ROUES", "JP1.1")

# ------------------------------------------------------------------- J4/J5/J6 + LED témoins (bandes 0-7)
couper(42, 4, 5, 6, 7)  # isole la zone des témoins du bus
for k in range(4):
    r = 2 * k
    broche(43, r, f"CH{k}", f"J4.ch{k}")
    if k < 3:
        broche(43, r + 1, "GND", f"J4.GND{k + 1}")
    couper(49, r)  # résistance en ligne : une coupure entre ses pattes
    dipole(f"R{4 + k}", "330 Ω", (47, r), f"CH{k}", (51, r), f"LED{k}", "resistance")
    dipole(f"D{1 + k}", "LED", (52, r), f"LED{k}", (52, r + 1), "GND", "led")
# J5/J6 : JST 3 points vers le MDD10A (étage B3), pris AVANT les résistances des témoins.
# L'alternance signal/masse de J4 donne gratuitement « sens · GND · PWM » par roue
# (robot_config : gauche = sens ch0 + PWM ch1, droite = PWM ch2 + sens ch3).
for i, net in enumerate(["CH0", "GND", "CH1"]):
    broche(45, i, net, f"J5.{i + 1}")
for i, net in enumerate(["CH2", "GND", "CH3"]):
    broche(45, 4 + i, net, f"J6.{i + 1}")
strap("GND", (53, 1), (53, 3))
strap("GND", (53, 5), (53, 7))
strap("GND", (50, 3), (50, 5))

# ------------------------------------------------------------------- J7 : bus I²C 5 V vers les modules déportés
# Même ordre que J11 de la carte Moteurs (5 V · SDA · SCL · GND). Sur la plaque de 60 × 140, le
# PCA9685 0x41 (servos) et le PCF8574 0x21 (relais) n'ont plus de place : ils se branchent en
# chaîne sur J7 (barrettes traversantes des modules), posés sur le socle.
for i, net in enumerate(["5V", "SDA", "SCL", "GND"]):
    broche(53, 9 + i, net, f"J7.{i + 1}")
couper(13, 9, 10, 11, 12)
strap("5V", (41, 7), (41, 9))
strap("SDA", (39, 6), (39, 10))
strap("SCL", (38, 5), (38, 11))
strap("GND", (44, 3), (44, 12))
strap("GND", (26, 12), (26, 13))  # bande 12 (GND de J7) à la broche 1 de U1

# ------------------------------------------------------------------- 74AHCT125 (support DIP-14) + rails
# Broches 1-7 colonne 36, bandes 13-19 ; broches 14-8 colonne 39. Rails : 20 = 5 V, 21 = DIN, 22 = GND.
U1_GAUCHE = ["GND", "GPIO18", "1Y", "5V", "GND", "NC6", "GND"]  # 1OE 1A 1Y 2OE 2A 2Y GND
U1_DROITE = ["5V", "5V", "GND", "NC11", "5V", "GND", "NC8"]  # VCC 4OE 4A 4Y 3OE 3A 3Y
for i in range(7):
    broche(36, 13 + i, U1_GAUCHE[i], f"U1.{i + 1}")
    broche(39, 13 + i, U1_DROITE[i], f"U1.{14 - i}")
couper(37, *range(13, 20))
couper(13, 13, 15, 16, 17, 18, 19, 20, 21)  # la bande 14 (GPIO18) va de J1b à U1 sans coupure
couper(33, 21)  # DIN : seulement de R2 à J3
strap("GND", (32, 13), (32, 17))
strap("GND", (31, 17), (31, 19))
strap("GND", (30, 19), (30, 22))
strap("5V", (35, 16), (35, 20))
dipole("R2", "330 Ω", (34, 15), "1Y", (34, 21), "DIN", "resistance")
dipole("C1", "100 nF", (40, 13), "5V", (40, 15), "GND", "ceramique")
strap("5V", (41, 13), (41, 14))
strap("5V", (42, 14), (42, 17))
strap("5V", (43, 17), (43, 20))
strap("GND", (44, 15), (44, 18))
strap("GND", (45, 18), (45, 22))
strap("5V", (28, 7), (28, 20))  # rail 5 V vers le bus (bande 7)
broche(51, 20, "5V", "J2.+5V")
broche(51, 22, "GND", "J2.GND")
dipole("C2", "1000 µF", (48, 20), "5V", (48, 22), "GND", "chimique")
broche(53, 20, "5V", "J3.5V")
broche(53, 21, "DIN", "J3.DIN")
broche(53, 22, "GND", "J3.GND")

# ------------------------------------------------------------------- J1b (GPIO), boutons, LED d'état
J1B = [("GPIO16", "GPIO16 (36)"), ("GPIO20", "GPIO20 (38)"), ("GPIO12", "GPIO12 (32)"), ("GPIO18", "GPIO18 (12)")]
for i, (net, _) in enumerate(J1B):  # JST 4 points, bandes 11-14
    broche(0, 11 + i, net, f"J1b.{i + 1}")
# Boutons 6×6 sur les bandes 20 (signal) et 22 (masse) ; la bande 20 est coupée entre les deux.
couper(6, 20)
for repere, net, c in (("SW1", "GPIO16", 1), ("SW2", "GPIO20", 8)):
    for dc in (0, 3):
        broche(c + dc, 20, net, f"{repere}.{'a' if dc == 0 else 'b'}")
        broche(c + dc, 22, "GND", f"{repere}.{'c' if dc == 0 else 'd'}")
strap("GPIO16", (2, 11), (2, 20))
strap("GPIO20", (9, 12), (9, 20))
dipole("R3", "330 Ω", (4, 13), "GPIO12", (4, 17), "LED_ETAT", "resistance")
dipole("D5", "LED", (6, 17), "LED_ETAT", (6, 18), "GND", "led")
strap("GND", (7, 18), (7, 22))


# =================================================================== vérification
def verifier() -> list[str]:
    """Reconstruit les liaisons (bandes − coupures + straps) et les compare aux réseaux attendus."""
    parent: dict[Trou, Trou] = {}

    def racine(t: Trou) -> Trou:
        parent.setdefault(t, t)
        while parent[t] != t:
            parent[t] = parent[parent[t]]
            t = parent[t]
        return t

    def unir(a: Trou, b: Trou) -> None:
        parent[racine(a)] = racine(b)

    for r in range(RANGS):
        for c in range(COLS - 1):
            if (c, r) not in COUPURES and (c + 1, r) not in COUPURES:
                unir((c, r), (c + 1, r))
    for _, a, b in STRAPS:
        unir(a, b)

    erreurs: list[str] = []
    occupes: dict[Trou, str] = {}
    for t, _, rep in BROCHES:
        if t in occupes:
            erreurs.append(f"trou {t} pris deux fois : {occupes[t]} et {rep}")
        occupes[t] = rep
    for net, a, b in STRAPS:
        for t in (a, b):
            if t in occupes:
                erreurs.append(f"strap {net} {a}-{b} : trou {t} déjà pris par {occupes[t]}")
            occupes[t] = f"strap {net}"
    for t in occupes:
        if t in COUPURES:
            erreurs.append(f"{occupes[t]} posé sur une coupure {t}")
        if not (0 <= t[0] < COLS and 0 <= t[1] < RANGS):
            erreurs.append(f"{occupes[t]} hors plaque {t}")

    par_reseau: dict[str, set[Trou]] = defaultdict(set)
    par_groupe: dict[Trou, set[str]] = defaultdict(set)
    for t, net, rep in BROCHES:
        par_reseau[net].add(racine(t))
        par_groupe[racine(t)].add(net)
    for net, a, b in STRAPS:  # un strap doit relier deux points de SON réseau
        par_groupe[racine(a)].add(net)
    for net, groupes in par_reseau.items():
        if len(groupes) > 1:
            erreurs.append(f"réseau {net} coupé en {len(groupes)} morceaux")
    for nets in par_groupe.values():
        if len(nets) > 1:
            erreurs.append(f"COURT-CIRCUIT entre {sorted(nets)}")
    return erreurs


# =================================================================== dessin
el: list[str] = []


def P(c: float, r: float) -> tuple[float, float]:
    return (X0 + (c + 0.5) * PAS * ECHELLE, Y0 + (r + 0.5) * PAS * ECHELLE)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def texte(x: float, y: float, s: str, t: float = PETIT, ancre: str = "start", gras: bool = False) -> None:
    g = ' font-weight="bold"' if gras else ""
    el.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{t}" text-anchor="{ancre}"{g}>{esc(s)}</text>')


def texte_trou(c: float, r: float, s: str, dx: float = 0, dy: float = 0, ancre: str = "start",
               gras: bool = False, t: float = PETIT) -> None:
    x, y = P(c, r)
    texte(x + dx, y + dy + 0.9, s, t, ancre, gras)


def ligne(a: Trou, b: Trou, ep: float, tirets: str = "") -> None:
    (x1, y1), (x2, y2) = P(*a), P(*b)
    d = f' stroke-dasharray="{tirets}"' if tirets else ""
    el.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="black" '
              f'stroke-width="{ep}" stroke-linecap="round"{d}/>')


def pastille(c: int, r: int, carree: bool = False) -> None:
    x, y = P(c, r)
    if carree:
        el.append(f'<rect x="{x - 1.1:.2f}" y="{y - 1.1:.2f}" width="2.2" height="2.2" fill="black"/>')
    else:
        el.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.1" fill="black"/>')


def contour(c1: float, r1: float, c2: float, r2: float, titre: str = "", sous: str = "",
            indicatif: bool = True, titre_en_bas: bool = False) -> None:
    x1, y1 = P(c1 - 0.5, r1 - 0.5)
    x2, y2 = P(c2 + 0.5, r2 + 0.5)
    d = ' stroke-dasharray="2.5,1.2"' if indicatif else ""
    el.append(f'<rect x="{x1:.2f}" y="{y1:.2f}" width="{x2 - x1:.2f}" height="{y2 - y1:.2f}" '
              f'fill="none" stroke="black" stroke-width="0.5"{d}/>')
    if titre:
        ty = y2 - 4.6 if titre_en_bas else y1 + 4.2
        texte(x2 - 1.5, ty, titre, TEXTE, "end", True)
        if sous:
            texte(x2 - 1.5, ty + 3.4, sous, PETIT, "end")


STYLE = {"5V": (0.9, ""), "GND": (0.6, "1.6,0.9")}


def dessiner() -> str:
    # ---- titre, plaque, bandes, trous, numéros
    texte(148.5, 9, "Banc témoin — implantation sur plaque à bandes 60 × 140 mm (vue côté composants)",
          4.2, "middle", True)
    texte(148.5, 14.5, "Dessin agrandi ×1,8 : compter les trous (colonnes 0-53, bandes 0-24 dans la longueur). "
          "✕ = coupure de bande (côté cuivre) ; trait plein = strap côté composants.", PETIT, "middle")
    bx1, by1 = P(-0.5, -0.5)
    bx2, by2 = P(COLS - 0.5, RANGS - 0.5)
    el.append(f'<rect x="{bx1:.2f}" y="{by1:.2f}" width="{bx2 - bx1:.2f}" height="{by2 - by1:.2f}" '
              f'fill="none" stroke="black" stroke-width="0.8"/>')
    for r in range(RANGS):
        _, y = P(0, r)
        h = PAS * ECHELLE * 0.62
        el.append(f'<rect x="{bx1 + 0.4:.2f}" y="{y - h / 2:.2f}" width="{bx2 - bx1 - 0.8:.2f}" '
                  f'height="{h:.2f}" rx="0.6" fill="none" stroke="black" stroke-width="0.1"/>')
        for c in range(COLS):
            x, _ = P(c, r)
            el.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.35" fill="none" stroke="black" stroke-width="0.13"/>')
    for c in range(0, COLS, 5):
        x, _ = P(c, 0)
        texte(x, by1 - 1.2, str(c), PETIT, "middle")
    for r in range(0, RANGS, 5):
        _, y = P(0, r)
        texte(bx2 + 11, y + 0.9, str(r), PETIT, "start")

    # ---- contours des modules (indicatifs) et titres
    contour(2.5, 2, 12.5, 9, "ISO1540")
    texte_trou(5, 8.2, "côté 1", ancre="middle")
    texte_trou(10, 8.2, "côté 2", ancre="middle")
    contour(14, 0.5, 39, 10.5, "PCA9685 0x40 — ROUES", "aucun driver moteur sur le banc", titre_en_bas=True)
    contour(35.5, 12.4, 39.5, 19.6, indicatif=False)
    texte_trou(37.5, 11.5, "U1 74AHCT125", ancre="middle", gras=True)
    texte_trou(36, 13, "1", dx=-1.6, ancre="end")

    # ---- straps
    for net, a, b in STRAPS:
        ep, t = STYLE.get(net, (0.45, ""))
        ligne(a, b, ep, t)

    # ---- dipôles
    for repere, valeur, a, b, sorte in DIPOLES:
        (x1, y1), (x2, y2) = P(*a), P(*b)
        ligne(a, b, 0.4)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        vertical = a[0] == b[0]
        if sorte == "resistance":
            w, h = (2.8, 6.5) if vertical else (6.5, 2.8)
            el.append(f'<rect x="{mx - w / 2:.2f}" y="{my - h / 2:.2f}" width="{w}" height="{h}" '
                      f'fill="white" stroke="black" stroke-width="0.4"/>')
        elif sorte == "led":
            el.append(f'<polygon points="{mx - 1.8:.2f},{my - 1.4:.2f} {mx + 1.8:.2f},{my - 1.4:.2f} '
                      f'{mx:.2f},{my + 1.4:.2f}" fill="white" stroke="black" stroke-width="0.4"/>')
            el.append(f'<line x1="{mx - 1.8:.2f}" y1="{my + 1.4:.2f}" x2="{mx + 1.8:.2f}" y2="{my + 1.4:.2f}" '
                      f'stroke="black" stroke-width="0.4"/>')
        elif sorte in ("ceramique", "chimique"):
            for dy in (-0.8, 0.8):
                el.append(f'<line x1="{mx - 2:.2f}" y1="{my + dy:.2f}" x2="{mx + 2:.2f}" y2="{my + dy:.2f}" '
                          f'stroke="black" stroke-width="0.6"/>')
            if sorte == "chimique":
                texte(mx + 2.3, my - 1.2, "+", PETIT)
        pastille(*a, carree=(sorte == "led"))
        pastille(*b)

    # ---- broches des composants et connecteurs
    for (c, r), _, rep in BROCHES:
        if not rep.split(".")[0] in {d[0] for d in DIPOLES}:
            pastille(c, r, carree=rep.endswith(".1") or rep in ("PCA40.GND", "PCA41.GND"))

    # ---- coupures (par-dessus tout)
    for c, r in sorted(COUPURES):
        x, y = P(c, r)
        for s in (1, -1):
            el.append(f'<line x1="{x - 1.5:.2f}" y1="{y - 1.5 * s:.2f}" x2="{x + 1.5:.2f}" y2="{y + 1.5 * s:.2f}" '
                      f'stroke="black" stroke-width="0.7"/>')

    # ---- étiquettes
    for i, (_, nom) in enumerate(J1A):
        texte_trou(0, 4 + i, nom, dx=-3.4, ancre="end")
    texte_trou(0, 2.6, "J1a Pi", dx=-3.4, ancre="end", gras=True)
    for i, (_, nom) in enumerate(J1B):
        texte_trou(0, 11 + i, nom, dx=-3.4, ancre="end")
    texte_trou(0, 9.6, "J1b Pi", dx=-3.4, ancre="end", gras=True)
    # embases JST-XH (contour du boîtier, côté verrou à droite)
    for c, r0, n in ((0, 4, 4), (0, 11, 4), (53, 20, 3), (45, 0, 3), (45, 4, 3), (53, 9, 4)):
        x1, y1 = P(c - 0.45, r0 - 0.6)
        x2, y2 = P(c + 0.45, r0 + n - 0.4)
        el.append(f'<rect x="{x1:.2f}" y="{y1:.2f}" width="{x2 - x1:.2f}" height="{y2 - y1:.2f}" '
                  f'fill="none" stroke="black" stroke-width="0.6"/>')
    for i, nom in enumerate(PCA_BROCHES):
        texte_trou(15, 3 + i, nom, dx=1.8)
    texte_trou(40, 5.5, "R10", dx=2.0)
    texte_trou(40, 6.5, "10k", dx=2.0)
    texte_trou(41, 2.0, "JP1", ancre="middle", gras=True)
    texte_trou(43, 7.4, "J4", ancre="middle", gras=True)
    texte_trou(45, 1, "J5", dx=2.6, gras=True)
    texte_trou(45, 5, "J6", dx=2.6, gras=True)
    texte_trou(53, 8.0, "J7 I²C 5 V", ancre="end", dx=1.2, gras=True)
    for i, nom in enumerate(["5V", "SDA", "SCL", "GND"]):
        texte_trou(53, 9 + i, nom, dx=-2.2, ancre="end")
    texte_trou(2.5, 18.9, "SW1", ancre="middle", gras=True)
    texte_trou(9.5, 18.9, "SW2", ancre="middle", gras=True)
    for c in (1, 8):  # contour des boutons 6×6
        contour(c, 20, c + 3, 22, indicatif=False)
    texte_trou(4, 15, "R3", dx=1.9)
    texte_trou(6, 17.5, "D5", dx=1.9)
    texte_trou(34, 17.6, "R2", dx=-1.9, ancre="end")
    texte_trou(40, 14, "C1", dx=2.2)
    texte_trou(48, 18.9, "C2", ancre="middle")
    texte_trou(51, 18.9, "J2", ancre="middle", gras=True)
    texte_trou(53, 18.9, "J3", ancre="middle", gras=True)
    for r, nom in ((20, "5 V"), (21, "DIN"), (22, "GND")):
        texte_trou(53, r, nom, dx=2.6, gras=True)
    texte_trou(30, 16.3, "PCA 0x41 (servos) et PCF8574 (relais) :", ancre="end")
    texte_trou(30, 17.3, "hors plaque, en chaîne sur J7", ancre="end")

    # ---- légende
    lx, ly = 14, 150
    texte(lx, ly - 4, "Légende :", TEXTE, gras=True)
    for i, (net, nom) in enumerate((("5V", "strap 5 V"), ("GND", "strap masse"), ("SIG", "strap signal"))):
        x = lx + i * 40
        ep, t = STYLE.get(net, (0.45, ""))
        d = f' stroke-dasharray="{t}"' if t else ""
        el.append(f'<line x1="{x}" y1="{ly}" x2="{x + 10}" y2="{ly}" stroke="black" stroke-width="{ep}"{d}/>')
        texte(x + 12, ly + 1, nom, PETIT)
    texte(lx + 122, ly + 1, "✕ coupure · □ broche 1 / anode · tirets = module (contour indicatif)", PETIT)
    texte(lx, ly + 7, "RÈGLE N° 1 : le Pi n'est alimenté QUE par son USB-C ; J1a/J1b en JST (Dupont femelle côté Pi), "
          "aucune broche 5 V du Pi sur la plaque. JP1 posé = roues actives ; retiré = PWM roues coupés.",
          PETIT, gras=True)
    texte(lx, ly + 17.5, "J4 (Dupont depuis les sorties 0-3 du PCA ROUES) : ch0 · GND · ch1 · GND · ch2 · GND · ch3.  "
          "J5 (JST, MDD10A roue G) : sens ch0 · GND · PWM ch1.  J6 (JST, roue D) : PWM ch2 · GND · sens ch3.", PETIT)
    texte(lx, ly + 12.5, "Coupures côté cuivre : plaque retournée, la colonne 0 passe à DROITE. "
          "Matrice : ses fils d'alimentation vont au bornier J2, jamais par les bandes. "
          "Bouton 6×6 : vérifier au multimètre quelles pattes commutent.", PETIT)

    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 297 210" '
            'font-family="DejaVu Sans, sans-serif">\n<rect width="297" height="210" fill="white"/>\n'
            + "\n".join(el) + "\n</svg>\n")


def liste() -> str:
    lignes = ["## Coupures (côté cuivre, colonne, bande)", ""]
    par_col: dict[int, list[int]] = defaultdict(list)
    for c, r in sorted(COUPURES):
        par_col[c].append(r)
    for c, rangs in sorted(par_col.items()):
        lignes.append(f"- colonne {c} : bandes {', '.join(map(str, sorted(rangs)))}")
    lignes += ["", f"Total : {len(COUPURES)} coupures.", "", "## Straps (côté composants)", "",
               "| Réseau | De (col, bande) | À (col, bande) |", "|---|---|---|"]
    for net, a, b in STRAPS:
        lignes.append(f"| {net} | {a[0]}, {a[1]} | {b[0]}, {b[1]} |")
    lignes += ["", "## Composants à deux pattes", "", "| Repère | Valeur | Patte 1 | Patte 2 |", "|---|---|---|---|"]
    for repere, valeur, a, b, _ in DIPOLES:
        lignes.append(f"| {repere} | {valeur} | {a[0]}, {a[1]} | {b[0]}, {b[1]} |")
    return "\n".join(lignes)


if __name__ == "__main__":
    erreurs = verifier()
    if erreurs:
        print("Implantation REFUSÉE :", *erreurs, sep="\n  ", file=sys.stderr)
        sys.exit(1)
    if "--liste" in sys.argv:
        print(liste())
    else:
        sortie = Path(sys.argv[1]) if len(sys.argv) > 1 else \
            Path(__file__).resolve().parents[2] / "docs/etudes/banc-temoin-bandes.svg"
        sortie.write_text(dessiner(), encoding="utf-8")
        print(f"Implantation vérifiée ({len(COUPURES)} coupures, {len(STRAPS)} straps) : {sortie}")
