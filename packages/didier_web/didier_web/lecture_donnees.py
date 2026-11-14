"""Lecture des données éditables pour la page scène (lot L1d-3, spec L1 « L1d », décision 11) :
ce que sert `GET /api/data`. Pure de ROS et d'aiohttp (stdlib + theatre_contrats), testée sur
un dossier jetable.

- `lister(data_dir, kind)` : noms triés, chacun avec l'état de la porte sim lu au registre
  (`rejeu` pour séquences, expressions et lumières ; `roues` pour une séquence à piste roues) :
  `a_jour`, `a_faire`, `heritee` (roues seulement), clé absente = sans objet.
- `lire(data_dir, kind, name)` : `{name, content, sha256}` — `sha256` est ce que l'éditeur
  rendra en `base_sha256` (octets du fichier pour séquence et image, JSON canonique de l'entrée
  sinon) ; une image est rendue en base64. None si le nom est hors forme ou absent.

Le juge des noms, des empreintes et du registre est `theatre_contrats.donnees` : rien n'est
recopié ici. Ce module ne fait que LIRE ; la seule écriture passe par `data_edit.traiter`.
"""
import base64
import json
import os

from theatre_contrats import donnees

A_JOUR = "a_jour"
A_FAIRE = "a_faire"
HERITEE = "heritee"


# ================================================================ liste
def lister(data_dir, kind):
    """[{name, rejeu?, roues?}] triés par nom ; [] pour un kind hors liste."""
    data_dir = str(data_dir)
    if kind not in donnees.KINDS:
        return []
    registre = donnees.lire_registre(data_dir) if kind in donnees.FAMILLES_REJOUEES else None
    elements = []
    for nom in sorted(_noms(data_dir, kind)):
        element = {"name": nom}
        if registre is not None:
            element.update(_etats(data_dir, kind, nom, registre))
        elements.append(element)
    return elements


def _noms(data_dir, kind):
    """Noms éditables (forme valide pour le kind) présents sur le disque."""
    if kind in donnees.FICHIERS_A_ENTREES:
        fichier = _lire_json(os.path.join(data_dir, donnees.FICHIERS_A_ENTREES[kind]))
        return [n for n in (fichier if isinstance(fichier, dict) else {}) if donnees.nom_valide(kind, n)]
    if kind == "sequence":
        racine, extension, zones = os.path.join(data_dir, donnees.DOSSIER_SEQUENCES), ".json", None
    else:
        racine, extension, zones = os.path.join(data_dir, donnees.DOSSIER_VISUELS), ".png", donnees.ZONES_IMAGE
    noms = []
    if not os.path.isdir(racine):
        return noms
    for dossier in sorted(os.listdir(racine)):
        chemin = os.path.join(racine, dossier)
        if (zones is not None and dossier not in zones) or not os.path.isdir(chemin):
            continue
        for fichier in os.listdir(chemin):
            nom = "{}/{}".format(dossier, fichier[:-len(extension)])
            if fichier.endswith(extension) and donnees.nom_valide(kind, nom):
                noms.append(nom)
    return noms


def _etats(data_dir, kind, nom, registre):
    entree = registre.get(kind, {}).get(nom, {})
    try:
        actuelle = donnees.empreinte_contenu(kind, nom, data_dir)
    except (OSError, ValueError):
        actuelle = None   # illisible : jamais « à jour »
    etats = {"rejeu": A_JOUR if actuelle is not None and entree.get("rejeu") == actuelle else A_FAIRE}
    if kind == "sequence":
        roues = donnees.empreinte_roues(_lire_json(_chemin(data_dir, kind, nom)))
        if roues is not None:
            if entree.get("roues") != roues:
                etats["roues"] = A_FAIRE
            else:
                etats["roues"] = HERITEE if entree.get("origine_roues") == "heritee" else A_JOUR
    return etats


# ================================================================ contenu
def lire(data_dir, kind, name):
    """{name, content, sha256} ou None (nom hors forme, élément absent)."""
    data_dir = str(data_dir)
    if kind not in donnees.KINDS or not donnees.nom_valide(kind, name):
        return None
    if kind in donnees.FICHIERS_A_ENTREES:
        fichier = _lire_json(os.path.join(data_dir, donnees.FICHIERS_A_ENTREES[kind]))
        if not isinstance(fichier, dict) or name not in fichier:
            return None
        return {"name": name, "content": fichier[name], "sha256": donnees.sha256_entree(fichier[name])}
    chemin = _chemin(data_dir, kind, name)
    if not os.path.isfile(chemin):
        return None
    with open(chemin, "rb") as f:
        octets = f.read()
    contenu = (base64.b64encode(octets).decode("ascii") if kind == "image"
               else json.loads(octets.decode("utf-8")))
    return {"name": name, "content": contenu, "sha256": donnees.sha256_octets(octets)}


def _chemin(data_dir, kind, name):
    if kind == "sequence":
        return os.path.join(data_dir, donnees.DOSSIER_SEQUENCES, name + ".json")
    return os.path.join(data_dir, donnees.DOSSIER_VISUELS, name + ".png")


def _lire_json(chemin):
    """Contenu JSON, ou None si absent ou illisible (une liste ne tombe pas pour un fichier)."""
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
