"""Contrat des BUGS JOUÉS (lot I0, 22/11) — un bug joué est une entrée du répertoire, pas une panne.

Étude : docs/etudes/etude-improvisation.md §2. Un bug joué = UNE séquence du dossier
`json/sequences/bugs-joues/`, de type "bug-joue", que le sélecteur choisit, annonce, joue et
rétablit (lot I1), et que la page scène joue à la main dès I0 (le visuel de David). Ce module
porte les GARANTIES DE CHARGEMENT (§2.1), une seule fois pour tout le dépôt : le contrat des
données (`donnees.verifier_sequence`, donc l'écrivain du robot et les tests de `data/`) les
applique à toute séquence de type "bug-joue", le répertoire du sélecteur et le pont web lisent
l'inventaire par `lire()`.

Garanties (chacune gravée par un test à valeur fixe, `test/test_bugs_joues.py`) :
- aucune piste `wheels` ni `relay`, même VIDE : un bug joué ne touche jamais les roues, un faux
  redémarrage ne coupe aucune vraie alimentation ;
- durée ≤ DUREE_MAX_MS (15 s) : au-delà, c'est une panne ;
- son ≤ SON_MAX_S (4 s) d'affilée : la porte audio est fermée pendant un son, le « stop » vocal y
  est sourd. Durée LUE AU MANIFESTE des audios privés (`duree_s`, wav seulement) : un audio sans
  durée connue est refusé ;
- classe "V" (visage, son, lumières, yeux) ou "M" (cou ou bras, attend le protocole caméra) ; une
  classe V ne porte aucune piste de cou ni de bras ;
- RÉTABLISSEMENT du repos : le visage et les lumières reviennent à l'entrée `default` au « stop »
  de fin. Le vrai code (didier_core.actions.face / lights) prend pour nouveau repos toute
  entrée marquée `"default": true` qu'on lui fait jouer (`off`, `fuzz`, `default dark`) : un bug
  qui joue `off` sans rejouer `default` ensuite laisserait Didier au visage noir après lui. Règle :
  la DERNIÈRE entrée marquée repos jouée par une piste est `default` lui-même ;
- `desc` (ce que le public voit, pour la page et le scénariste) obligatoire ; `direction`
  (ce que la bouche dit après, lot I1) facultative.

Python PUR, stdlib + theatre_contrats.donnees.
"""
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from theatre_contrats import donnees

DOSSIER = "bugs-joues"                       # sous json/sequences/
TYPE = "bug-joue"
DUREE_MAX_MS = 15_000
SON_MAX_S = 4.0
PISTES_INTERDITES = ("wheels", "relay")
CLASSES = ("V", "M")
PISTES_PORTEUSES = ("neck", "left_arm", "right_arm")   # interdites en classe V
REPOS = "default"                            # entrée de repos du visage ET des lumières
DESC_MAX_CHARS = 80
DIRECTION_MAX_CHARS = 200


def est_bug_joue(sequence: object) -> bool:
    types = sequence.get("types") if isinstance(sequence, dict) else None
    return isinstance(types, list) and TYPE in types


def _intervalles_audio(sequence: Dict[str, Any], duree_ms: Optional[float], manifeste: Dict[str, Any],
                       erreurs: List[str]) -> List[Tuple[float, float]]:
    """[(début_s, fin_s)] des sons de la piste `audios` ; erreurs pour un son sans durée
    connue ou trop long. Une valeur hors forme est jugée par donnees.verifier_sequence."""
    intervalles: List[Tuple[float, float]] = []
    for i, image in enumerate(sequence.get("audios") or []):
        if not (isinstance(image, list) and len(image) == 2 and donnees.est_nombre(image[0])):
            continue
        fichier = image[1]
        if fichier == donnees.COMMANDE_AUDIO_STOP or not isinstance(fichier, str):
            continue
        duree = (manifeste.get(fichier) or {}).get("duree_s")
        if not (donnees.est_nombre_fini(duree) and isinstance(duree, (int, float))):
            erreurs.append("audios[{}] : durée de {} inconnue au manifeste (wav attendu) : "
                           "un bug joué ne cite que des sons de {} s au plus".format(i, fichier, SON_MAX_S))
            continue
        if duree > SON_MAX_S:
            erreurs.append("audios[{}] : {} dure {:g} s, au-delà de {} s (SON_MAX_S)".format(
                i, fichier, duree, SON_MAX_S))
            continue
        if duree_ms is not None:
            debut = image[0] * duree_ms / 1000.0
            intervalles.append((debut, debut + duree))
    return intervalles


def _son_d_affilee(intervalles: List[Tuple[float, float]]) -> float:
    """Plus longue plage de son continu (s) : deux sons qui se touchent ou se chevauchent
    tiennent la porte audio fermée d'un seul tenant."""
    plus_long = 0.0
    debut = fin = 0.0
    premier = True
    for a, b in sorted(intervalles):
        if premier or a > fin:
            debut, fin, premier = a, b, False
        else:
            fin = max(fin, b)
        plus_long = max(plus_long, fin - debut)
    return plus_long


def _repos_retabli(piste: object, table: Dict[str, Any], nom_piste: str, erreurs: List[str]) -> None:
    """La dernière entrée marquée `"default": true` jouée par la piste doit être REPOS."""
    dernier = None
    for image in piste if isinstance(piste, list) else []:
        if isinstance(image, list) and len(image) == 2 and isinstance(image[1], str):
            entree = table.get(image[1])
            if isinstance(entree, dict) and entree.get("default"):
                dernier = image[1]
    if dernier is not None and dernier != REPOS:
        erreurs.append("{} : « {} » devient le repos (\"default\": true) et rien ne rejoue « {} » "
                       "après lui — Didier resterait ainsi après le bug".format(nom_piste, dernier, REPOS))


def verifier_bug_joue(sequence: object, references: Dict[str, Any]) -> List[str]:
    """Les garanties du §2.1 sur UNE séquence (toutes les fautes, liste vide = conforme). Ne
    refait pas le contrat général des séquences (donnees.verifier_sequence l'appelle)."""
    if not isinstance(sequence, dict):
        return ["bug joué : objet JSON attendu"]
    erreurs = []
    if not est_bug_joue(sequence):
        erreurs.append("types : {!r} absent (tout fichier de {}/ est un bug joué)".format(TYPE, DOSSIER))
    for piste in PISTES_INTERDITES:
        if piste in sequence:
            erreurs.append("piste {} interdite dans un bug joué (même vide)".format(piste))
    duree = sequence.get("duration")
    duree_ms = float(duree) if donnees.est_nombre(duree) and isinstance(duree, (int, float)) and duree > 0 else None
    if duree_ms is not None and duree_ms > DUREE_MAX_MS:
        erreurs.append("duration {} ms au-delà de {} ms (DUREE_MAX_MS) : au-delà, c'est une panne".format(
            duree, DUREE_MAX_MS))
    classe = sequence.get("classe")
    if classe not in CLASSES:
        erreurs.append("classe {!r} : attendue parmi {}".format(classe, CLASSES))
    elif classe == "V":
        for piste in PISTES_PORTEUSES:
            if sequence.get(piste):
                erreurs.append("piste {} dans un bug de classe V (cou et bras = classe M)".format(piste))
    desc = sequence.get("desc")
    if not (isinstance(desc, str) and desc.strip() and len(desc) <= DESC_MAX_CHARS):
        erreurs.append("desc : texte non vide de {} caractères au plus".format(DESC_MAX_CHARS))
    direction = sequence.get("direction")
    if direction is not None and not (isinstance(direction, str) and len(direction) <= DIRECTION_MAX_CHARS):
        erreurs.append("direction : texte de {} caractères au plus, ou absente".format(DIRECTION_MAX_CHARS))
    intervalles = _intervalles_audio(sequence, duree_ms, references["audios_manifeste"], erreurs)
    affilee = _son_d_affilee(intervalles)
    if affilee > SON_MAX_S:
        erreurs.append("audios : {:g} s de son d'affilée, au-delà de {} s (SON_MAX_S)".format(affilee, SON_MAX_S))
    _repos_retabli(sequence.get("faces"), references["expressions"], "faces", erreurs)
    _repos_retabli(sequence.get("robot_lights"), references["robot_lights"], "robot_lights", erreurs)
    return erreurs


# ================================================================ inventaire du dossier
@dataclass(frozen=True)
class BugJoue:
    id: str                    # nom du fichier = nom joué par animations_node
    chemin: str                # relatif au dossier des séquences
    desc: str
    classe: str
    duree_s: float
    direction: Optional[str]
    pistes: Tuple[str, ...]    # pistes non vides, triées (ce que le bug touche)


@dataclass(frozen=True)
class Inventaire:
    acceptes: Tuple[BugJoue, ...]
    refuses: Tuple[Tuple[str, Tuple[str, ...]], ...]   # (chemin, erreurs)


PISTES: Tuple[str, ...] = donnees.PISTES_SERVOS + donnees.AUTRES_PISTES


def lire(data_dir: "os.PathLike[str] | str", dossier_audios: "os.PathLike[str] | str | None" = None) -> Inventaire:
    """Inventaire des bugs joués de `data_dir` : chaque fichier de json/sequences/bugs-joues/
    jugé par le contrat COMPLET des séquences (qui applique les garanties ci-dessus) ; une
    séquence de type "bug-joue" rangée ailleurs est refusée aussi, comme un homonyme d'une autre
    séquence (animations_node résout par le nom de fichier et n'en garde qu'un). Un refus ne
    fait jamais tomber les autres. Ne lève que si le robot est cassé (fichier de référence
    illisible), comme charger_references."""
    references = donnees.charger_references(data_dir, dossier_audios)
    racine = os.path.join(str(data_dir), donnees.DOSSIER_SEQUENCES)
    acceptes: List[BugJoue] = []
    refuses: List[Tuple[str, Tuple[str, ...]]] = []
    noms: Dict[str, List[str]] = {}
    candidats: List[Tuple[str, str, Any, bool]] = []
    for dossier, _, fichiers in sorted(os.walk(racine)):
        for fichier in sorted(f for f in fichiers if f.endswith(".json")):
            chemin = os.path.relpath(os.path.join(dossier, fichier), racine).replace(os.sep, "/")
            nom = fichier[:-len(".json")]
            noms.setdefault(nom, []).append(chemin)
            dans_dossier = chemin.split("/")[0] == DOSSIER
            try:
                with open(os.path.join(dossier, fichier), encoding="utf-8") as f:
                    sequence = json.load(f)
            except (OSError, ValueError) as e:
                if dans_dossier:
                    refuses.append((chemin, ("illisible : {}".format(e),)))
                continue
            if dans_dossier or est_bug_joue(sequence):
                candidats.append((chemin, nom, sequence, dans_dossier))
    for chemin, nom, sequence, dans_dossier in candidats:
        erreurs = [] if dans_dossier else ["type {!r} hors du dossier {}/".format(TYPE, DOSSIER)]
        erreurs += donnees.verifier_sequence(sequence, references)
        if not est_bug_joue(sequence):
            # verifier_sequence n'applique les garanties qu'aux séquences TYPÉES bug-joue.
            erreurs += verifier_bug_joue(sequence, references)
        if len(noms[nom]) > 1:
            erreurs.append("nom « {} » en double ({}) : animations_node n'en jouerait qu'un".format(
                nom, ", ".join(noms[nom])))
        if erreurs:
            refuses.append((chemin, tuple(erreurs)))
            continue
        acceptes.append(BugJoue(
            id=nom, chemin=chemin, desc=sequence["desc"].strip(), classe=sequence["classe"],
            duree_s=sequence["duration"] / 1000.0, direction=sequence.get("direction"),
            pistes=tuple(sorted(p for p in PISTES if sequence.get(p)))))
    return Inventaire(tuple(acceptes), tuple(refuses))
