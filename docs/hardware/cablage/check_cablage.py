#!/usr/bin/env python3
"""Contrôle du cahier de câblage de Didier (cahier-cablage.csv).

Le cahier fait foi (plan-refonte-electrique.md §4) : un fil qui n'y est pas n'existe
pas. Ce script vérifie ce qu'une relecture humaine rate le plus souvent :

1. chaque fil de PUISSANCE porte un fusible (ou un PTC) et une section ;
2. la section est suffisante pour le fusible qui la protège (table §RÈGLE) ;
3. les repères sont uniques et les familles connues ;
4. il liste les longueurs manquantes (elles se mesurent sur le robot, étape 1 du plan).

Usage : python3 check_cablage.py [cahier-cablage.csv]
Sortie : une ligne par défaut, code de retour 1 s'il y a au moins une ERREUR.
Les longueurs manquantes sont des AVERTISSEMENTS (attendus tant que rien n'est mesuré).

RÈGLE section ↔ fusible : cuivre souple, trajets courts (< 2 m), 30 °C ambiant, un
fusible qui tient 1,5 × In pendant une heure. Section minimale en mm² pour un
calibre donné ; au-dessus de 40 A, demander un calcul. C'est volontairement
conservateur : dans un coffre fermé en bois, le fil n'est pas refroidi.
"""
import csv
import sys
from pathlib import Path

SECTION_MIN = [  # (calibre max du fusible en A, section minimale en mm²)
    (2, 0.25), (3, 0.5), (5, 0.75), (7.5, 1.0), (10, 1.5), (15, 2.5),
    (20, 2.5), (25, 4.0), (30, 4.0), (40, 6.0), (50, 10.0),
]
FAMILLES = {"puissance", "logique", "audio", "masse"}
PROTECTIONS_NON_NUMERIQUES = {"PTC"}  # protégé, mais pas par un calibre en ampères


def section_mini(fusible_a: float) -> float:
    for calibre, section in SECTION_MIN:
        if fusible_a <= calibre:
            return section
    raise ValueError(f"calibre {fusible_a} A hors table : calcul à la main")


def nombre(texte: str):
    """'1.5' → 1.5 ; '0.25 blindé' → 0.25 ; 'nappe', 'coax', '' → None."""
    premier = texte.strip().split(" ")[0].replace(",", ".")
    try:
        return float(premier)
    except ValueError:
        return None


def controler(chemin: Path):
    erreurs, avertissements = [], []
    reperes = set()
    with chemin.open(encoding="utf-8") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    for ligne in lignes:
        rep = ligne["repere"]
        if rep in reperes:
            erreurs.append(f"{rep}: repère en double")
        reperes.add(rep)
        if ligne["famille"] not in FAMILLES:
            erreurs.append(f"{rep}: famille inconnue « {ligne['famille']} »")
        if ligne["statut"] == "sur_carte":
            continue  # pas un fil
        section = nombre(ligne["section_mm2"])
        fusible_txt = ligne["fusible_A"].strip()
        fusible = nombre(fusible_txt)
        if ligne["famille"] == "puissance":
            if not fusible_txt:
                erreurs.append(f"{rep}: fil de puissance sans fusible ({ligne['de']} → {ligne['a']})")
            if section is None and ligne["section_mm2"].strip() not in {"câble USB", "nappe"}:
                erreurs.append(f"{rep}: fil de puissance sans section")
        if fusible is not None and section is not None:
            mini = section_mini(fusible)
            if section < mini:
                erreurs.append(
                    f"{rep}: section {section} mm² < {mini} mm² exigés par un fusible de {fusible} A"
                )
        elif fusible_txt and fusible is None and fusible_txt not in PROTECTIONS_NON_NUMERIQUES:
            erreurs.append(f"{rep}: fusible illisible « {fusible_txt} »")
        if not ligne["longueur_cm"].strip() and ligne["statut"] in {"a_cabler", "a_commander"}:
            avertissements.append(f"{rep}: longueur à mesurer")
    return lignes, erreurs, avertissements


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "-v"]
    chemin = Path(args[0]) if args else Path(__file__).with_name("cahier-cablage.csv")
    lignes, erreurs, avertissements = controler(chemin)
    for e in erreurs:
        print("ERREUR ", e)
    print(f"{len(lignes)} lignes, {len(erreurs)} erreur(s), {len(avertissements)} longueur(s) à mesurer")
    if avertissements and "-v" in sys.argv:
        for a in avertissements:
            print("  à mesurer", a)
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
