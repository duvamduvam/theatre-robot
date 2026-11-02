#!/usr/bin/env python3
"""Inventaire des constantes de contrat : qui définit quoi, qui importe quoi.

C'est cet outil (analyse AST, imports multi-lignes compris) qui a montré le
2026-11-02 que le premier comptage de la spec L1 (grep ligne à ligne : « 58
importées, 32 mortes ») était faux : 94 constantes, 74 importées par le code,
3 vraiment mortes. Un grep rate les imports en plusieurs lignes ; ne pas y revenir.

Usage (depuis n'importe où) :
    python3 packages/theatre_contrats/tools/inventaire.py [racine du mono-dépôt]

Sortie : pour chaque nom importé depuis dadou_utils_ros.utils_static par les
dépôts consommateurs, son module de définition et ses consommateurs (code /
tests séparés) ; puis les noms définis que PERSONNE n'importe (morts côté
consommateurs — vérifier encore les usages internes de dadou_utils_ros avant
de supprimer : 17 constantes « mortes » pour les consommateurs servaient à la
lib elle-même le 2026-11-02).
"""
import ast
import os
import sys

CONSOMMATEURS = ("dadou_robot_ros", "dadou_control_ros", "dadou_vision_ros")
# Dossiers jamais parcourus : environnements, artefacts colcon, et le symlink
# dadou_utils_ros de chaque dépôt (la lib serait comptée trois fois).
EXCLUS = {".venv", "venv", "build", "install", "log", "__pycache__", ".git",
          "dadou_utils_ros", "node_modules"}
MODULES_CONTRAT = ("organs", "topics", "keys")


def definitions(chemin):
    """Noms assignés au niveau module (les ré-exports `from x import y` exclus)."""
    arbre = ast.parse(open(chemin, encoding="utf-8").read())
    noms = []
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign):
            noms += [c.id for c in noeud.targets if isinstance(c, ast.Name)]
    return noms


def est_test(chemin):
    nom = os.path.basename(chemin)
    return "/tests/" in chemin or "/test/" in chemin or nom.startswith("test_") or nom == "conftest.py"


def imports(racine_legacy):
    """{nom: {"code": {dépôts}, "tests": {dépôts}}} des imports de utils_static."""
    resultat = {}
    for depot in CONSOMMATEURS:
        for dossier, sous, fichiers in os.walk(os.path.join(racine_legacy, depot)):
            sous[:] = [s for s in sous if s not in EXCLUS]
            for f in fichiers:
                if not f.endswith(".py"):
                    continue
                chemin = os.path.join(dossier, f)
                try:
                    arbre = ast.parse(open(chemin, encoding="utf-8").read())
                except (SyntaxError, UnicodeDecodeError) as e:
                    print(f"ILLISIBLE {chemin} : {e}", file=sys.stderr)
                    continue
                for n in ast.walk(arbre):
                    if isinstance(n, ast.ImportFrom) and n.module and n.module.endswith("utils_static"):
                        for alias in n.names:
                            genre = "tests" if est_test(chemin) else "code"
                            resultat.setdefault(alias.name, {"code": set(), "tests": set()})[genre].add(depot)
    return resultat


def main():
    racine = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                             os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    legacy = os.path.join(racine, "legacy")
    origine = {}
    for mod in MODULES_CONTRAT:
        for nom in definitions(os.path.join(racine, "packages", "theatre_contrats",
                                            "theatre_contrats", mod + ".py")):
            origine[nom] = "theatre_contrats." + mod
    for nom in definitions(os.path.join(legacy, "dadou_utils_ros", "utils_static.py")):
        origine.setdefault(nom, "utils_static")
    utilises = imports(legacy)

    print(f"{len(origine)} noms définis (theatre_contrats + utils_static), "
          f"{sum(1 for v in utilises.values() if v['code'])} importés par du code, "
          f"{len(utilises)} en comptant les tests\n")
    for nom in sorted(utilises):
        u = utilises[nom]
        print(f"  {nom:26} {origine.get(nom, 'INDÉFINI !'):26} code={sorted(u['code'])} "
              f"tests={sorted(u['tests'])}")
    for depot in CONSOMMATEURS:
        print(f"{depot} : {sum(1 for u in utilises.values() if depot in u['code'])} importés par le code")
    morts = sorted(n for n in origine if n not in utilises and origine[n] == "utils_static")
    print(f"\nDéfinis dans utils_static, importés par AUCUN consommateur ({len(morts)}) :")
    for nom in morts:
        print(f"  {nom}")
    indefinis = sorted(n for n in utilises if n not in origine)
    if indefinis:
        print(f"\nIMPORTÉS MAIS INDÉFINIS : {indefinis}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
