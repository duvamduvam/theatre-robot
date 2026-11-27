"""Aperçu animé des animations du CORPS (data/json/robot_lights.json + lights_base.json),
pour juger le mouvement avant la sim. APPROXIMATION : imite les animations Adafruit
(chase, comet, pulse, sparkle, rainbow…) sur 40 LED en anneau ; la vitesse réelle est celle
du robot (vitesse fixée dans lights_animations.py), pas celle-ci.

    .venv/bin/python docs/etudes/visage/apercu_corps.py
"""
from __future__ import annotations

import colorsys
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import maquette_visage as m

R = m.RACINE
ICI = Path(__file__).resolve().parent
N, IPS = 40, 20
NOMS = ["default", "speak", "scan", "transfer", "comet", "amour", "ange", "colere", "devil", "dodo", "fete", "trip"]


def couleurs():
    c = json.loads((R / "data/json/colors.json").read_text())
    return {k: tuple(v[:3]) for k, v in c.items()}


def rendu(methode, rgb, t, rng):
    """Une image de l'anneau à l'instant t (secondes) pour une brique."""
    a = np.zeros((N, 3))
    c = np.array(rgb or (255, 255, 255), float)
    if methode in ("chase", "default"):
        pos = int(t * 10)
        for i in range(N):
            if (i + pos) % 9 < 3:
                a[i] = c
    elif methode == "comet":
        tete = int(t * 10) % N
        for k in range(10):
            a[(tete - k) % N] = c * (1 - k / 10)
    elif methode == "pulse":
        a[:] = c * (0.5 - 0.5 * np.cos(2 * np.pi * t))
    elif methode in ("sparkle", "sparkle_pulse"):
        a[:] = c * 0.15
        for i in rng.choice(N, 6, replace=False):
            a[i] = c
    elif methode == "blink":
        a[:] = c if int(t * 2) % 2 == 0 else 0
    elif methode == "solid":
        a[:] = c
    elif methode.startswith("rainbow") or methode == "color_cycle":
        for i in range(N):
            h = (i / N + t * 0.3) % 1
            a[i] = np.array(colorsys.hsv_to_rgb(h, 1, 1)) * 255
        if methode == "rainbow_comet":
            tete = int(t * 10) % N
            a *= np.array([[max(0.0, 1 - ((tete - i) % N) / 12)] for i in range(N)])
        if methode == "rainbow_sparkle":
            a *= 0.2
            for i in rng.choice(N, 8, replace=False):
                a[i] *= 5
    return a.clip(0, 255).astype(np.uint8)


def brique_a(entree, t_ms):
    """Brique active à t (sémantique Track : la brique [nom, fin] joue jusqu'à fin×durée)."""
    seq = sorted(entree["sequences"].items(), key=lambda kv: kv[1])
    d = entree["duration"]
    tt = t_ms % d if entree.get("loop") else min(t_ms, d)
    for nom, fin in seq:
        if tt <= fin * d:
            return nom
    return seq[-1][0]


def main():
    lum = json.loads((R / "data/json/robot_lights.json").read_text())
    briques = json.loads((R / "data/json/lights_base.json").read_text())
    pal = couleurs()
    rng = np.random.default_rng(3)
    images, duree = [], 8.0
    for k in range(int(duree * IPS)):
        t = k / IPS
        im = Image.new("RGB", (6 * 250, 2 * 120 + 30), (26, 26, 26))
        d = ImageDraw.Draw(im)
        d.text((8, 6), "Corps (approximation) — 12 animations, 40 LED en anneau", fill=(255, 255, 255), font=m.POLICE)
        for j, nom in enumerate(NOMS):
            e = lum[nom]
            b = brique_a(e, t * 1000)
            spec = briques.get(b, {"method": b})
            rgb = pal.get(spec.get("color")) if spec.get("color") else None
            anneau = rendu(spec.get("method", b), rgb, t, rng)
            x, y = (j % 6) * 250 + 10, 30 + (j // 6) * 120
            d.text((x, y), f"{nom}  ({b})", fill=(200, 200, 200), font=m.POLICE)
            cx, cy, r = x + 115, y + 68, 38
            for i in range(N):
                ang = 2 * np.pi * i / N
                px, py = cx + r * np.cos(ang), cy + r * np.sin(ang)
                d.ellipse((px - 4, py - 4, px + 4, py + 4), fill=tuple(int(v) for v in anneau[i]))
        images.append(im)
    sortie = ICI / "corps-animations.gif"
    images[0].save(sortie, save_all=True, append_images=images[1:], duration=1000 // IPS, loop=0)
    print("écrit", sortie.relative_to(R), len(images), "images")


if __name__ == "__main__":
    main()
