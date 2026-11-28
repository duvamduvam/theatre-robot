#!/usr/bin/env python3
"""Crée un appareil depuis le squelette du gabarit (spec L3 décisions 1, 3 et 6 ; geste G1).

    python3 packages/theatre_gabarit/tools/nouvel_appareil.py <nom> [--racine <mono-dépôt>]

Recopie packages/theatre_gabarit/squelette/ dans la racine en remplaçant `appareil_gabarit` par
<nom>, dans les chemins comme dans les textes :
    packages/<nom>_core/   machines/<nom>/   machines/sim/<nom>/entree.sh
Refuse si l'une de ces destinations existe déjà (rien n'est écrasé). N'ÉDITE AUCUN fichier
partagé (registre, topics, CI, compose, plan de fumée, inventaire Ansible) : ces gestes-là sont
dits par les tests rouges du nouvel appareil (`test_gabarit.py` -> verifier_appareil).
Python, bibliothèque standard + theatre_contrats (pur), lu dans le dépôt.
"""
import argparse
import pathlib
import re
import shutil
import sys

GABARIT = pathlib.Path(__file__).resolve().parents[1]
# Noms réservés : theatre_contrats.appareils.nom_reserve (pur, stdlib), lu depuis le dépôt.
sys.path.insert(0, str(GABARIT.parent / "theatre_contrats"))
from theatre_contrats.appareils import nom_reserve  # noqa: E402
SQUELETTE = GABARIT / "squelette"
JETON = "appareil_gabarit"
NOM_VALIDE = re.compile(r"^[a-z][a-z0-9_]{1,30}$")
IGNORES = ("COLCON_IGNORE", "__pycache__")


def destinations(racine: pathlib.Path, nom: str) -> list:
    return [racine / "packages" / f"{nom}_core", racine / "machines" / nom,
            racine / "machines" / "sim" / nom]


def creer(nom: str, racine: pathlib.Path) -> list:
    """Les fichiers écrits (chemins relatifs à la racine). Lève ValueError sur un refus."""
    if not NOM_VALIDE.match(nom) or nom.endswith("_core"):
        raise ValueError(f"nom refusé : {nom!r} (minuscules, chiffres, _ ; sans suffixe _core)")
    if nom_reserve(nom):
        raise ValueError(f"nom réservé : {nom!r} (espace de topics existant ou préfixe de mouvement)")
    deja = [d for d in destinations(racine, nom) if d.exists()]
    if deja:
        raise ValueError("existe déjà : " + ", ".join(str(d.relative_to(racine)) for d in deja))
    ecrits = []
    for source in sorted(SQUELETTE.rglob("*")):
        relatif = source.relative_to(SQUELETTE)
        if not source.is_file() or any(p in IGNORES for p in relatif.parts):
            continue
        cible = racine / str(relatif).replace(JETON, nom)
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(source.read_text(encoding="utf-8").replace(JETON, nom), encoding="utf-8")
        shutil.copymode(source, cible)
        ecrits.append(str(cible.relative_to(racine)))
    return ecrits


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="crée un appareil depuis le squelette du gabarit")
    p.add_argument("nom")
    p.add_argument("--racine", type=pathlib.Path, default=GABARIT.parents[1])
    a = p.parse_args(argv)
    try:
        ecrits = creer(a.nom, a.racine.resolve())
    except ValueError as erreur:
        print(f"refus : {erreur}", file=sys.stderr)
        return 2
    print("\n".join(ecrits))
    print(f"\n{len(ecrits)} fichiers. Suite : cd packages/{a.nom}_core && ../../.venv/bin/python -m pytest"
          " -q -o addopts=  — les tests rouges sont la liste des gestes (README du gabarit).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
