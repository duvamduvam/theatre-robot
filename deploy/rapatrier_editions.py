"""Rapatriement des éditions du robot vers data/ du PC (lot L1d-4, 13/11) — la logique du
playbook rapatrier-editions.yml, pure de ROS et d'Ansible (stdlib + theatre_contrats).

Spec : docs/spec-L1-contrats-donnees.md, « L1d », décision 13. Le Pi ne garde jamais une
retouche que le dépôt ignore : chaque écriture de data_edit_node y laisse une ligne au journal
json/backup/EDITIONS-EN-ATTENTE.jsonl ; le playbook met ce journal de côté, tire du Pi les
fichiers qu'il nomme dans un dossier temporaire, puis ce script les reporte dans data/ :
  - séquence, image : le fichier du Pi, tel quel ;
  - expression, lumière, brique : SEULEMENT les entrées nommées au journal
    (donnees.poser_entree) — tirer le fichier entier écraserait une entrée commitée sur le PC
    et pas encore déployée.
Puis les quatre tests de données et celui des images : rouges, data/ est REMIS dans son état
d'avant (le journal reste en attente sur le Pi, on corrige et on relance) ; verts, les copies
« rapatrie » sont préparées pour json/backup/<date>/ du Pi. La porte sim n'arrête pas : ce qui
revient du robot n'a pas été joué en sim, c'est attendu (« N élément(s) à rejouer »).
Il ne commite JAMAIS.

  python3 rapatrier_editions.py preparer  --journal J --depot D --data-dir D/data
  python3 rapatrier_editions.py appliquer --journal J --pi-dir P --data-dir D/data
                                          --depot D --python PY --sortie S

`preparer` : journal lisible, noms valides, aucune cible modifiée localement dans git ; imprime
les chemins (relatifs à data/) à tirer du Pi. `appliquer` : report, tests, copies, résultat
dans S/resultat.json. Code 0 = fait, 1 = refus (message lisible), 2 = appel faux.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

from theatre_contrats import donnees

# Les tests de data/ (spec, décision 13) : les quatre du contrat et celui des images. Ceux de
# la porte sim (test_validations_sim.py) n'en sont PAS : rouges, ils n'arrêtent rien.
TESTS_DONNEES = (
    "test/unit/test_sequences_json.py",
    "test/unit/test_sequences_assets.py",
    "test/unit/test_expressions_json.py",
    "test/unit/test_lights_json.py",
    "test/unit/test_visuels_png.py",
)
# Racine du package dont les tests sont lancés (relative au dépôt).
PACKAGE_TESTS = "packages/didier_core"
DOSSIER_RAPATRIES = "rapatries"
FICHIER_RESULTAT = "resultat.json"


class Refus(Exception):
    """Rapatriement refusé : rien n'a été écrit dans data/ (ou tout y a été remis)."""


# ================================================================ journal
def lire_journal(texte):
    """Lignes du journal (dicts), dans l'ordre. Une ligne illisible ou un nom hors forme =
    Refus : le journal vient du Pi, un nom forgé (« ../ ») ne doit jamais devenir un chemin."""
    lignes = []
    for numero, brute in enumerate(texte.splitlines(), 1):
        if not brute.strip():
            continue
        try:
            ligne = json.loads(brute)
        except ValueError:
            raise Refus("journal, ligne {} : JSON illisible".format(numero))
        if not isinstance(ligne, dict):
            raise Refus("journal, ligne {} : objet attendu".format(numero))
        kind, name = ligne.get("kind"), ligne.get("name")
        if kind not in donnees.KINDS:
            raise Refus("journal, ligne {} : kind {!r} inconnu".format(numero, kind))
        if not donnees.nom_valide(kind, name):
            raise Refus("journal, ligne {} : nom {!r} hors forme pour {}".format(numero, name, kind))
        lignes.append(ligne)
    return lignes


def elements(lignes):
    """[(kind, name, sha256 de la DERNIÈRE ligne)] sans doublon, dans l'ordre d'apparition :
    une entrée retouchée trois fois n'est rapatriée qu'une fois, dans son état final."""
    derniers = {}
    for ligne in lignes:
        derniers[(ligne["kind"], ligne["name"])] = ligne.get("sha256")
    return [(kind, name, sha) for (kind, name), sha in derniers.items()]


def chemin_relatif(kind, name):
    """Fichier visé, relatif à data/ (même table que l'écrivain : donnees.KINDS)."""
    if kind in donnees.FICHIERS_A_ENTREES:
        return donnees.FICHIERS_A_ENTREES[kind]
    if kind == "sequence":
        return "{}/{}.json".format(donnees.DOSSIER_SEQUENCES, name)
    return "{}/{}.png".format(donnees.DOSSIER_VISUELS, name)


def fichiers_a_tirer(lignes):
    """Chemins relatifs à data/ à tirer du Pi, sans doublon, dans l'ordre d'apparition."""
    vus = []
    for kind, name, _ in elements(lignes):
        relatif = chemin_relatif(kind, name)
        if relatif not in vus:
            vus.append(relatif)
    return vus


def nom_rapatrie(kind, name):
    """Copie gardée sur le Pi (json/backup/<date>/) : `<dossier>__<nom>__rapatrie.json` pour
    une séquence, `<zone>__<nom>__rapatrie.png` pour une image, `<kind>__<nom>__rapatrie.json`
    (l'entrée seule) pour les trois autres — « / » et espaces en « _ », comme les sauvegardes."""
    if kind == "sequence":
        return "{}__rapatrie.json".format(name.replace("/", "__"))
    if kind == "image":
        return "{}__rapatrie.png".format(name.replace("/", "__"))
    return "{}__{}__rapatrie.json".format(kind, re.sub(r"[/ ]", "_", name))


# ================================================================ git (refus avant tout tirage)
def modifies_dans_git(depot, data_dir, relatifs):
    """Cibles qui ont une modification locale non commitée (`git status --porcelain`) :
    rapatrier par-dessus mélangerait deux retouches sans que le diff dise laquelle est laquelle."""
    chemins = [os.path.join(data_dir, r) for r in relatifs]
    sortie = subprocess.run(["git", "-C", depot, "status", "--porcelain", "--"] + chemins,
                            check=True, capture_output=True, text=True).stdout
    return [l for l in sortie.splitlines() if l.strip()]


# ================================================================ report dans data/
def _lire_octets(chemin):
    with open(chemin, "rb") as f:
        return f.read()


def _ecrire_octets(chemin, octets):
    with open(chemin, "wb") as f:
        f.write(octets)


def reporter(lignes, pi_dir, data_dir):
    """Reporte dans `data_dir` ce que nomme le journal, depuis les fichiers tirés du Pi
    (`pi_dir`, même disposition que data/). Rend (originaux, rapatries, messages) :
    originaux = {chemin: octets d'avant ou None si absent} (pour `restaurer`) ;
    rapatries = [(nom_rapatrie, octets)] ; messages = lignes lisibles.

    Un élément absent du Pi est ignoré (écriture interrompue : le journal est écrit AVANT le
    fichier, une ligne en trop est possible) ; un sha du Pi différent de la dernière ligne est
    dit, et c'est l'état du Pi qui est rapatrié."""
    originaux, rapatries, messages = {}, [], []
    fichiers_a_entrees = {}     # relatif -> dict du PC en cours de report

    def noter_original(chemin):
        if chemin not in originaux:
            originaux[chemin] = _lire_octets(chemin) if os.path.isfile(chemin) else None

    for kind, name, sha_journal in elements(lignes):
        relatif = chemin_relatif(kind, name)
        source = os.path.join(pi_dir, relatif)
        cible = os.path.join(data_dir, relatif)
        if not os.path.isfile(source):
            messages.append("ignorée (absente du Pi) : {} {}".format(kind, name))
            continue
        if kind in donnees.FICHIERS_A_ENTREES:
            with open(source, encoding="utf-8") as f:
                du_pi = json.load(f)
            if name not in du_pi:
                messages.append("ignorée (absente du Pi) : {} {}".format(kind, name))
                continue
            entree = du_pi[name]
            sha = donnees.sha256_entree(entree)
            if relatif not in fichiers_a_entrees:
                noter_original(cible)
                with open(cible, encoding="utf-8") as f:
                    fichiers_a_entrees[relatif] = json.load(f)
            fichiers_a_entrees[relatif] = donnees.poser_entree(fichiers_a_entrees[relatif], name, entree)
            rapatries.append((nom_rapatrie(kind, name), donnees.serialiser(entree)))
        else:
            if not os.path.isdir(os.path.dirname(cible)):
                raise Refus("{} {} : dossier {} absent du PC (une création de dossier passe par "
                            "git)".format(kind, name, os.path.relpath(os.path.dirname(cible), data_dir)))
            octets = _lire_octets(source)
            sha = donnees.sha256_octets(octets)
            noter_original(cible)
            _ecrire_octets(cible, octets)
            rapatries.append((nom_rapatrie(kind, name), octets))
        if sha_journal and sha != sha_journal:
            messages.append("le Pi porte une autre version que la dernière journalisée : {} {} "
                            "(rapatriée telle qu'elle est sur le Pi)".format(kind, name))
        messages.append("rapatriée : {} {}".format(kind, name))
    for relatif, fichier in fichiers_a_entrees.items():
        _ecrire_octets(os.path.join(data_dir, relatif), donnees.serialiser(fichier))
    return originaux, rapatries, messages


def restaurer(originaux):
    """Remet chaque fichier touché dans son état d'avant ; un fichier créé est effacé."""
    for chemin, octets in originaux.items():
        if octets is None:
            if os.path.exists(chemin):
                os.remove(chemin)
        else:
            _ecrire_octets(chemin, octets)


def lancer_tests(depot, python):
    """Les tests de data/ (TESTS_DONNEES) ; rend le code de sortie de pytest."""
    commande = [python, "-m", "pytest", "-q", "-o", "addopts=", "-p", "no:cacheprovider"]
    return subprocess.run(commande + list(TESTS_DONNEES), cwd=os.path.join(depot, PACKAGE_TESTS)).returncode


def appliquer(lignes, pi_dir, data_dir, sortie, lancer=None, maintenant=None):
    """Report + tests + copies « rapatrie ». `lancer()` rend le code des tests de data/ (injecté
    par les tests ; le CLI y met lancer_tests). Rouge : data/ remis à l'identique, Refus.
    Vert : rend le résultat (dict, aussi écrit dans `sortie`/resultat.json)."""
    maintenant = maintenant or datetime.datetime.now()
    originaux, rapatries, messages = reporter(lignes, pi_dir, data_dir)
    if lancer is not None and lancer() != 0:
        restaurer(originaux)
        raise Refus("tests de data/ ROUGES sur les retouches du robot : data/ est remis dans "
                    "son état d'avant, le journal reste en attente sur le Pi. Corriger sur le robot "
                    "(ou écraser : deploy-pios.yml -e ecraser_editions=true), puis relancer.")
    dossier = os.path.join(sortie, DOSSIER_RAPATRIES)
    os.makedirs(dossier, exist_ok=True)
    for nom, octets in rapatries:
        _ecrire_octets(os.path.join(dossier, nom), octets)
    a_rejouer = donnees.non_validees(data_dir)
    resultat = {
        "date": maintenant.strftime("%Y-%m-%d"), "heure": maintenant.strftime("%H%M%S"),
        "messages": messages, "rapatries": [nom for nom, _ in rapatries],
        "non_validees": a_rejouer,
    }
    with open(os.path.join(sortie, FICHIER_RESULTAT), "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=1)
    return resultat


# ================================================================ ligne de commande
def _lire_fichier_journal(chemin):
    with open(chemin, encoding="utf-8") as f:
        return lire_journal(f.read())


def main(argv=None):
    parseur = argparse.ArgumentParser(description="Rapatriement des éditions du robot (L1d-4).")
    sous = parseur.add_subparsers(dest="commande", required=True)
    p = sous.add_parser("preparer")
    p.add_argument("--journal", required=True)
    p.add_argument("--depot", required=True)
    p.add_argument("--data-dir", required=True)
    a = sous.add_parser("appliquer")
    for option in ("--journal", "--pi-dir", "--data-dir", "--depot", "--python", "--sortie"):
        a.add_argument(option, required=True)
    try:
        args = parseur.parse_args(argv)
    except SystemExit:
        return 2
    try:
        lignes = _lire_fichier_journal(args.journal)
        if args.commande == "preparer":
            relatifs = fichiers_a_tirer(lignes)
            modifies = modifies_dans_git(args.depot, args.data_dir, relatifs)
            if modifies:
                raise Refus("modification(s) locale(s) non commitée(s) sur un fichier visé — rien "
                            "n'est copié ; commiter ou annuler d'abord :\n  " + "\n  ".join(modifies))
            for relatif in relatifs:
                print(relatif)
            return 0
        resultat = appliquer(lignes, args.pi_dir, args.data_dir, args.sortie,
                             lancer=lambda: lancer_tests(args.depot, args.python))
        for message in resultat["messages"]:
            print(message)
        return 0
    except Refus as refus:
        print("REFUS : {}".format(refus))
        return 1


if __name__ == "__main__":
    sys.exit(main())
