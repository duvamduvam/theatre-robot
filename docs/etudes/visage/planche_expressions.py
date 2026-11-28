"""Planche de contrôle : chaque expression de data/json/expressions.json, image par image,
rangée par monde (étude du visage §12). Lecture seule des données ; sert à valider à l'œil
avant le rejeu en sim et le déploiement.

    .venv/bin/python docs/etudes/visage/planche_expressions.py [sortie.png]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import maquette_visage as m

R = m.RACINE
MONDES = {
    "LUI — émotions et symboles de BD": [
        "default", "repos neon", "joie", "colere", "tristesse", "surprise", "malice", "emerveille", "amour neon",
        "etoiles", "voila", "etourdi", "ko", "idee", "hein", "chante", "ennui", "bored", "bisou", "sexy",
        "grand amour", "love", "gros mot", "dodo", "zzz"],
    "CONVERSATION": ["ecoute", "reflechit", "parle", "speak", "speak loop"],
    "SA MACHINE — âme hébergée par une start-up d'éternité en faillite": [
        "mise a jour", "upgrade", "404", "pas de reseau", "cherche reseau", "internet", "batterie",
        "patientez", "nuage", "brain", "attention", "warning", "fantome", "scooby-doo",
        "fuzz", "repos glitch", "glitch total", "off"],
    "SA QUÊTE — il cherche, les passants savent": [
        "boussole", "fleche droite", "fleche gauche", "tout droit", "porte", "ange", "diable",
        "default red", "repos braise", "speak red", "oui", "non"],
}
MAX_IMAGES = 8


def charger(zone, fichier):
    return np.array(Image.open(R / "data/medias/visuals" / zone / fichier).convert("RGB"))


def images(e):
    """Images distinctes d'une expression, dans l'ordre (sémantique de Face : la frame
    [t, f] est affichée jusqu'à t)."""
    def a(p, t):
        return next(f for tt, f in p if t <= tt + 1e-9)
    ts = sorted({t for k in ("left_eyes", "right_eyes", "mouths") for t, _ in e[k]})
    vues = []
    for t in ts:
        c = (a(e["left_eyes"], t), a(e["right_eyes"], t), a(e["mouths"], t))
        if c not in vues:
            vues.append(c)
    return vues


def main(sortie: Path) -> None:
    ex = json.loads((R / "data/json/expressions.json").read_text(encoding="utf-8"))
    oublies = [n for n in ex if not n.startswith("calib") and not any(n in v for v in MONDES.values())]
    if oublies:
        MONDES["NON RANGÉES"] = oublies
    e, cote = 5, 28 * 5 + 6
    lignes = [(titre, n) for titre, noms in MONDES.items() for n in noms if n in ex]
    largeur = 190 + MAX_IMAGES * cote
    hauteur = 10 + sum(cote + 6 for _ in lignes) + 34 * len(MONDES)
    pl = Image.new("RGB", (largeur, hauteur), (26, 26, 26))
    d = ImageDraw.Draw(pl)
    y, titre_courant = 6, None
    for titre, n in lignes:
        if titre != titre_courant:
            d.text((8, y + 8), titre, fill=(255, 255, 255), font=m.POLICE)
            y, titre_courant = y + 34, titre
        x = ex[n]
        d.text((8, y + cote // 2 - 16), n, fill=(235, 235, 235), font=m.POLICE)
        d.text((8, y + cote // 2 + 2), f"{x['duration']} ms{' ↻' if x['loop'] else ''}", fill=(140, 140, 140), font=m.POLICE)
        for i, (g, dr, b) in enumerate(images(x)[:MAX_IMAGES]):
            c = np.zeros((28, 28, 3), np.uint8)
            c[1:9, 3:11], c[1:9, 17:25], c[11:27, 2:26] = charger("eye", g), charger("eye", dr), charger("mouth", b)
            pl.paste(m.agrandir(c, e), (190 + i * cote, y))
        y += cote + 6
    pl.save(sortie)
    print("écrit", sortie, pl.size, len(lignes), "expressions")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "planche-complete.png")
