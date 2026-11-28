"""Aides de test des appareils (spec L3 décisions 2 et 6) : pilote enregistreur, `verifier_appareil`.

`verifier_appareil(dossier)` rend la LISTE DES GESTES qui restent pour que l'appareil soit complet
(liste vide = complet). Le `test_gabarit.py` de chaque appareil fait `assert verifier_appareil(PKG)
== []` : tant qu'un geste manque, le test est rouge et son diff EST la liste des gestes — le
générateur (tools/nouvel_appareil.py) n'édite donc aucun fichier partagé. Numéros de gestes :
README du gabarit (packages/theatre_gabarit/README.md), G1 à G11.

Les 9 causes, dans cet ordre :
1. un titre du README-contrat manque (8 titres, dans l'ordre de TITRES_README) ;
2. le mot APPAREIL du squelette subsiste (un trou à remplir) ;
3. un topic de `contrat.TOPICS` est absolu, ou absent de theatre_contrats.topics ;
4. l'appareil n'est pas au registre (theatre_contrats.appareils.REGISTRE) ;
5. machines/<m>/machine.yml manque, ou n'a pas packages, launch_cmd, noeuds_attendus,
   sentinelle_build ;
6. le package n'est pas dans la matrice de .github/workflows/tests.yml ;
7. le service <m> manque dans machines/sim/docker-compose.yml ;
8. aucune épreuve de machines/sim/fumee/plan.toml ne porte son id ;
9. le nœud contient une règle : un `if` de noeud.py autre que SI_PERMIS_NOEUD.

Hôte seulement (PyYAML, tomllib) : jamais importé par un nœud.
"""
import ast
import importlib.util
import pathlib
import re
import tomllib
from typing import Any

import yaml

from theatre_contrats import appareils, topics

TITRES_README = ("Rôle", "Machine", "Topics", "Comportement", "Pilotes", "Simuler", "Tester",
                 "Déployer")
TROU = re.compile(r"\bAPPAREIL\b")
CLES_MACHINE = ("packages", "launch_cmd", "noeuds_attendus", "sentinelle_build")
SI_PERMIS_NOEUD = ["__name__ == '__main__'"]
SUFFIXE = "_core"


class Enregistreur:
    """Faux pilote : tout appel de méthode est noté dans `journal` (nom, arguments) et rend
    `rendus[nom]` (None par défaut). Sert aux tests de la logique d'un appareil."""

    def __init__(self, **rendus: Any) -> None:
        self.journal: list = []
        self.rendus = rendus

    def __getattr__(self, nom: str) -> Any:
        if nom.startswith("_"):
            raise AttributeError(nom)

        def appel(*args: Any) -> Any:
            self.journal.append((nom, args))
            return self.rendus.get(nom)
        return appel


def _lire(chemin: pathlib.Path) -> str | None:
    try:
        return chemin.read_text(encoding="utf-8")
    except OSError:
        return None


def _titres_manquants(readme: str | None) -> list[str]:
    if readme is None:
        return ["G7 README-contrat : README.md absent"]
    titres = [l[3:].strip() for l in readme.splitlines() if l.startswith("## ")]
    if [t for t in titres if t in TITRES_README] == list(TITRES_README):
        return []
    manquants = [t for t in TITRES_README if t not in titres]
    detail = ", ".join(manquants) if manquants else "ordre faux"
    return [f"G7 README-contrat : titres « ## » attendus dans l'ordre {' · '.join(TITRES_README)} ({detail})"]


def _trous(dossiers: list[pathlib.Path], racine: pathlib.Path) -> list[str]:
    restes = []
    for d in dossiers:
        for f in sorted(p for p in d.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            texte = _lire(f)
            if texte is not None and TROU.search(texte):
                restes.append(f"trou APPAREIL à remplir : {f.relative_to(racine)}")
    return restes


def _contrat(fichier: pathlib.Path) -> list[str]:
    spec = importlib.util.spec_from_file_location("_contrat_verifie", fichier)
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        noms = tuple(module.TOPICS)
    except Exception as erreur:  # noqa: BLE001 — tout défaut du contrat devient un geste
        return [f"G2 contrat : {fichier.name} illisible ou sans TOPICS ({erreur!r})"]
    connus = {v for k, v in vars(topics).items() if k.isupper() and isinstance(v, str)}
    return [f"G2 contrat : topic {n!r} absolu ou absent de theatre_contrats.topics"
            for n in noms if not isinstance(n, str) or n.startswith("/") or n not in connus]


def _machine(fichier: pathlib.Path) -> list[str]:
    texte = _lire(fichier)
    if texte is None:
        return [f"G8 machine : {fichier.parent.name}/machine.yml absent"]
    try:
        d = yaml.safe_load(texte) or {}
    except yaml.YAMLError:
        d = {}
    manquantes = [c for c in CLES_MACHINE if not isinstance(d, dict) or c not in d]
    return [f"G8 machine : machine.yml sans {', '.join(manquantes)}"] if manquantes else []


def _ci(fichier: pathlib.Path, paquet: str) -> list[str]:
    try:
        lignes = yaml.safe_load(_lire(fichier) or "")["jobs"]["unit"]["strategy"]["matrix"]["include"]
    except (TypeError, KeyError, yaml.YAMLError):
        lignes = []
    if any(isinstance(l, dict) and l.get("dir") == f"packages/{paquet}" for l in lignes):
        return []
    return [f"G8 CI : ligne « suite: {paquet} » absente de .github/workflows/tests.yml"]


def _service_sim(fichier: pathlib.Path, nom: str) -> list[str]:
    try:
        services = yaml.safe_load(_lire(fichier) or "")["services"]
    except (TypeError, KeyError, yaml.YAMLError):
        services = {}
    return [] if nom in (services or {}) else [
        f"G9 sim : service « {nom} » absent de machines/sim/docker-compose.yml"]


def _epreuve(fichier: pathlib.Path, nom: str) -> list[str]:
    try:
        ids = [e.get("id") for e in tomllib.loads(_lire(fichier) or "").get("epreuve", [])]
    except tomllib.TOMLDecodeError:
        ids = []
    return [] if nom in ids else [f"G10 fumée : aucune épreuve id = « {nom} » dans machines/sim/fumee/plan.toml"]


def _regles_du_noeud(fichier: pathlib.Path) -> list[str]:
    texte = _lire(fichier)
    if texte is None:
        return ["G6 nœud : noeud.py absent"]
    tests = sorted(ast.unparse(n.test) for n in ast.walk(ast.parse(texte))
                   if isinstance(n, (ast.If, ast.IfExp)))
    autres = [t for t in tests if t not in SI_PERMIS_NOEUD]
    return [f"G6 nœud : règle dans noeud.py (`if {t}`) — elle va dans logique.py" for t in autres]


def verifier_appareil(dossier: Any) -> list[str]:
    """Les gestes qui restent pour l'appareil du package `dossier` (packages/<nom>_core)."""
    paquet_dir = pathlib.Path(dossier).resolve()
    racine = paquet_dir.parents[1]
    paquet = paquet_dir.name
    nom = paquet[:-len(SUFFIXE)] if paquet.endswith(SUFFIXE) else paquet
    module = paquet_dir / paquet
    gestes = _titres_manquants(_lire(paquet_dir / "README.md"))
    gestes += _trous([paquet_dir, racine / "machines" / nom, racine / "machines" / "sim" / nom], racine)
    gestes += _contrat(module / "contrat.py")
    if nom not in appareils.REGISTRE:
        gestes.append(f"G2 contrat : « {nom} » absent de theatre_contrats.appareils.REGISTRE")
    gestes += _machine(racine / "machines" / nom / "machine.yml")
    gestes += _ci(racine / ".github" / "workflows" / "tests.yml", paquet)
    gestes += _service_sim(racine / "machines" / "sim" / "docker-compose.yml", nom)
    gestes += _epreuve(racine / "machines" / "sim" / "fumee" / "plan.toml", nom)
    gestes += _regles_du_noeud(module / "noeud.py")
    return gestes
