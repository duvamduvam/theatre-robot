"""Le RÉPERTOIRE de Didier : ce qu'il peut jouer (spec A1 §2, §8.4).

- Séquences : json/sequences/**.json qui ont une clé `types`, SAUF celles de
  `bugs/` (des pannes jouées, pas du jeu) et SAUF toute séquence qui a une
  piste `wheels` NON VIDE : A1 n'a pas de corps sûr, rien ne doit bouger les
  roues hors des verrous du sélecteur (une piste roues de séquence passe en
  prio 10 du twist_mux, sans fatigue, sans superviseur, sans « stop »).
- Nom d'une séquence = nom du fichier sans .json : c'est la clé que
  animations_node résout (robot/actions/abstract_json_actions.py).
- Emploi d'une séquence = premier type de reglages `emplois` (dans l'ordre du
  réglage : bonjour -> accueil, random -> spontanee…) qu'elle porte ; aucun =
  « sans emploi ».
- Vocabulaire de déplacements (config/deplacements.yaml) -> payload régisseur.
"""
import json
import pathlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import yaml

# Dossier des séquences de PANNES (bugs joués par le régisseur) : jamais du jeu.
DOSSIER_EXCLU = "bugs"
# Commandes que le régisseur accepte sur chat_move (robot_rehearsal.contracts :
# CHAT_MOVE_GOTO_CMD, CHAT_MOVE_TOUR_CMD, CHAT_MOVE_TURN_CMD,
# CHAT_MOVE_FORWARD_CMD) ; égalité gravée par test_repertoire.py.
COMMANDES_REGISSEUR = ("aller_voir", "tour_de", "tourner", "avancer")


class RepertoireError(ValueError):
    """Répertoire invalide — le message dit quoi."""


@dataclass(frozen=True)
class Sequence:
    nom: str
    types: Tuple[str, ...]
    duree_s: Optional[float]   # clé `duration` (ms) -> s ; None si absente
    chemin: str                # relatif au dossier des séquences
    roues: bool                # piste `wheels` non vide
    a_types: bool              # clé `types` présente (même vide)


def _a_des_roues(data: dict) -> bool:
    return bool(data.get("wheels"))


def lire_sequences(dossier) -> List[Sequence]:
    """Toutes les séquences du dossier (récursif), triées par chemin."""
    racine = pathlib.Path(dossier)
    sequences = []
    for f in sorted(racine.rglob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise RepertoireError(f"séquence illisible {f}: {e}") from e
        if not isinstance(data, dict):
            continue
        types = data.get("types")
        duree = data.get("duration")
        sequences.append(Sequence(
            nom=f.stem,
            types=tuple(types) if isinstance(types, list) else (),
            duree_s=float(duree) / 1000.0 if isinstance(duree, (int, float)) and duree > 0 else None,
            chemin=str(f.relative_to(racine)),
            roues=_a_des_roues(data),
            a_types="types" in data,
        ))
    return sequences


def candidates(dossier) -> List[Sequence]:
    """Séquences JOUABLES par le sélecteur (filtre gravé en test) : clé
    `types` présente, hors bugs/, sans piste roues."""
    return [s for s in lire_sequences(dossier)
            if s.a_types
            and pathlib.PurePath(s.chemin).parts[0] != DOSSIER_EXCLU
            and not s.roues]


def par_emploi(sequences, emplois: Dict[str, str]) -> Tuple[Dict[str, List[Sequence]], List[str]]:
    """-> ({emploi: [séquences]}, [noms sans emploi]). Un nom présent dans deux
    dossiers (animations_node n'en garde qu'un) n'est compté qu'une fois."""
    pools: Dict[str, List[Sequence]] = {}
    sans_emploi: List[str] = []
    vus = set()
    for s in sequences:
        if s.nom in vus:
            continue
        vus.add(s.nom)
        # Ordre des `emplois` du RÉGLAGE (bonjour d'abord) : une séquence
        # ["random", "bonjour"] est un accueil, pas une expression spontanée.
        emploi = next((e for t, e in emplois.items() if t in s.types), None)
        if emploi is None:
            sans_emploi.append(s.nom)
        else:
            pools.setdefault(emploi, []).append(s)
    return pools, sans_emploi


def charger_deplacements(chemin) -> Dict[str, dict]:
    with open(chemin, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return valider_deplacements(data)


def valider_deplacements(data) -> Dict[str, dict]:
    """Chaque verbe -> {cmd: commande du régisseur, ...paramètres fixes}."""
    if not isinstance(data, dict) or not data:
        raise RepertoireError("deplacements : dictionnaire non vide attendu")
    for verbe, modele in data.items():
        if not isinstance(modele, dict) or modele.get("cmd") not in COMMANDES_REGISSEUR:
            raise RepertoireError(f"deplacements.{verbe} : cmd attendue parmi {COMMANDES_REGISSEUR}")
        if modele["cmd"] == "avancer":
            metres = modele.get("metres")
            # Le régisseur refuse un avancer négatif ou < 0,1 m (FORWARD_MIN_M) :
            # un tel verbe ne ferait que des refus.
            if not isinstance(metres, (int, float)) or metres < 0.1:
                raise RepertoireError(f"deplacements.{verbe} : metres >= 0,1 attendu (pas de recul)")
    return data


def commande(deplacements: Dict[str, dict], verbe: str, **params) -> dict:
    """Payload de chat_move pour un verbe du vocabulaire (+ paramètres du moment)."""
    if verbe not in deplacements:
        raise RepertoireError(f"verbe de déplacement inconnu : {verbe}")
    payload = dict(deplacements[verbe])
    payload.update(params)
    return payload


def payload_animation(seq: Sequence) -> str:
    """msg du StringTime `animation` : le NOM en JSON chaîne (guillemets)."""
    return json.dumps(seq.nom)
