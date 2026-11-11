#!/usr/bin/env python3
"""Trie par NETTETÉ les images extraites d'une vidéo d'atelier, et les renomme
par horodatage pour qu'un repère du rapport soit une adresse dans la vidéo.

POURQUOI CE SCRIPT EXISTE
-------------------------
Les inventaires matériel du projet (stock d'atelier le 2026-09-02, robot le
2026-09-03) se dépouillent en lisant des centaines d'images extraites d'une
vidéo filmée à MAIN LEVÉE. Une bonne moitié est inexploitable : bougé, mise au
point en cours de course, panoramique. Les faire lire par un agent coûte des
jetons pour rien, et — plus grave — une sérigraphie devinée sur une image floue
devient une référence FAUSSE dans un inventaire censé éviter des achats.

Le tri se fait sur la VARIANCE DU LAPLACIEN : une image nette a des transitions
franches (forte variance des dérivées secondes), une image floue les a lissées.
C'est le critère utilisé pour l'inventaire du stock ; il est ici versionné, la
première fois il ne l'avait pas été.

PAS D'OPENCV VOLONTAIREMENT : le venv du projet n'a que numpy et PIL, et ajouter
cv2 (~90 Mo) pour un noyau 3×3 ne se justifie pas. Le laplacien est convolué à la
main ci-dessous.

USAGE
-----
    ffmpeg -v error -i video.mp4 -vf "fps=1,scale=1600:-1" -q:v 2 \
           frames_all/a_%04d.jpg -y
    .venv/bin/python conf/scripts/frames-nettete.py frames_all/ triees/ --percentile 25

`a_%04d.jpg` doit être extrait à **fps=1** : le script en déduit l'horodatage
(a_0001 = seconde 0), d'où le nom de sortie `tXXXX.jpg` où XXXX = secondes. Un
repère `t0495` du rapport se rejoue alors directement dans le lecteur vidéo à
8 min 15 s — c'est la seule « adresse » dont dispose un inventaire filmé.
"""

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# Noyau laplacien 8-voisins : plus sensible aux détails fins qu'un 4-voisins,
# ce qui compte ici car ce qu'on cherche à lire, ce sont des sérigraphies de
# quelques pixels de haut.
LAPLACIEN = np.array([[1.0, 1.0, 1.0],
                      [1.0, -8.0, 1.0],
                      [1.0, 1.0, 1.0]])


def variance_laplacien(chemin: Path, cote_max: int = 1000) -> float:
    """Score de netteté d'une image. Plus c'est grand, plus c'est net.

    L'image est réduite avant mesure : à pleine résolution le score dépend
    surtout du bruit du capteur, et le calcul est 3× plus lent pour un
    classement identique.
    """
    with Image.open(chemin) as img:
        img = img.convert("L")  # niveaux de gris : la netteté n'est pas une affaire de couleur
        img.thumbnail((cote_max, cote_max), Image.Resampling.BILINEAR)
        a = np.asarray(img, dtype=np.float64)

    if a.shape[0] < 3 or a.shape[1] < 3:
        return 0.0

    # Convolution 3×3 par vues décalées : ~10× plus rapide qu'une double boucle
    # Python, et sans dépendance scipy.
    conv = np.zeros((a.shape[0] - 2, a.shape[1] - 2), dtype=np.float64)
    for di in range(3):
        for dj in range(3):
            poids = LAPLACIEN[di, dj]
            if poids:
                conv += poids * a[di:di + a.shape[0] - 2, dj:dj + a.shape[1] - 2]
    return float(conv.var())


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", type=Path, help="dossier des images a_XXXX.jpg (extraites à fps=1)")
    p.add_argument("destination", type=Path, help="dossier de sortie (images retenues, nommées tXXXX.jpg)")
    p.add_argument("--percentile", type=float, default=25.0,
                   help="pourcentage des images LES PLUS FLOUES à écarter (défaut : 25)")
    p.add_argument("--rapport", type=Path, default=None,
                   help="fichier CSV des scores (défaut : <destination>/nettete.csv)")
    args = p.parse_args()

    images = sorted(args.source.glob("*.jpg"))
    if not images:
        print(f"Aucune image .jpg dans {args.source}", file=sys.stderr)
        return 1

    scores = []
    for i, chemin in enumerate(images, 1):
        scores.append((chemin, variance_laplacien(chemin)))
        if i % 25 == 0 or i == len(images):
            print(f"  netteté calculée : {i}/{len(images)}", file=sys.stderr)

    valeurs = np.array([s for _, s in scores])
    seuil = float(np.percentile(valeurs, args.percentile))

    args.destination.mkdir(parents=True, exist_ok=True)
    rapport = args.rapport or args.destination / "nettete.csv"

    retenues = 0
    lignes = ["source,horodatage_s,score_nettete,retenue"]
    for chemin, score in scores:
        # a_0001.jpg → seconde 0 (première image de la vidéo).
        numero = int("".join(c for c in chemin.stem if c.isdigit()))
        seconde = numero - 1
        garde = score >= seuil
        if garde:
            shutil.copy2(chemin, args.destination / f"t{seconde:04d}.jpg")
            retenues += 1
        lignes.append(f"{chemin.name},{seconde},{score:.1f},{int(garde)}")
    rapport.write_text("\n".join(lignes) + "\n", encoding="utf-8")

    print(f"\nSeuil (percentile {args.percentile:g}) : {seuil:.1f}")
    print(f"Retenues : {retenues}/{len(images)}  →  {args.destination}")
    print(f"Scores   : {rapport}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
