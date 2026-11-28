"""Choix du pilote d'un appareil : `sim` ou `materiel` (spec L3 décisions 2 et 4).

La couture sim/réel est DANS le nœud (étude architecture §5.7) : le reste du code est identique,
la logique ne sait pas quel pilote elle a. Le launch passe `pilote:=materiel` par défaut (rien à
poser sur le Pi) ; la sim passe `pilote:=sim` par l'entrée du compose, jamais par une variable
lue côté appareil.

Garde-fou : un pilote `sim` hors du domaine 43 (celui de la sim) est REFUSÉ — un appareil qui
croirait jouer en sim sur le vrai réseau du spectacle mentirait sur ce qu'il fait. Refus =
`PiloteRefuse`, que le nœud traduit en sortie code 2.

Santé d'un pilote : `ok` / `absent` (matériel non trouvé : le nœud reste vivant) / `erreur`
(les mêmes valeurs que la santé d'un organe, theatre_contrats.appareils.SANTES).
Python PUR, stdlib seulement.
"""
from typing import Any, Callable, Mapping

from theatre_contrats.appareils import SANTES

SIM = "sim"
MATERIEL = "materiel"
PILOTES = (SIM, MATERIEL)
DOMAINE_SIM = 43
OK, ABSENT, ERREUR = SANTES
CODE_SORTIE_REFUS = 2


class PiloteRefuse(Exception):
    """Pilote inconnu, sans fabrique, ou `sim` hors domaine 43 : le nœud sort en code 2."""

    code_sortie = CODE_SORTIE_REFUS


def domaine(ros_domain_id: Any) -> int | None:
    """ROS_DOMAIN_ID lu (entier ou chaîne) ; illisible ou absent -> None (jamais 43 par défaut)."""
    if isinstance(ros_domain_id, bool):
        return None
    try:
        return int(str(ros_domain_id).strip())
    except ValueError:
        return None


def choisir(nom: str, fabriques: Mapping[str, Callable[[], Any]], ros_domain_id: Any) -> Any:
    """Construit le pilote `nom` par sa fabrique ; lève PiloteRefuse (message lisible)."""
    if nom not in PILOTES:
        raise PiloteRefuse(f"pilote inconnu : {nom!r} (attendu : {', '.join(PILOTES)})")
    if nom == SIM and domaine(ros_domain_id) != DOMAINE_SIM:
        raise PiloteRefuse(f"pilote sim refusé hors du domaine {DOMAINE_SIM} "
                           f"(ROS_DOMAIN_ID={ros_domain_id!r})")
    if nom not in fabriques:
        raise PiloteRefuse(f"pilote {nom!r} sans fabrique dans cet appareil")
    return fabriques[nom]()


def sante_valide(sante: Any) -> bool:
    return sante in SANTES
