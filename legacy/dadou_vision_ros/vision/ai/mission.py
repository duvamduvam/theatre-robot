"""État de mission de Didier — « cinq cases et des noms » (lot I0).

QUOI : mémoire dramatique de la quête : la destination, les cinq critères
      (validés ou non, par qui, avec quelle valeur), les guides rencontrés
      (prénom ou signalement) et la dernière indication reçue. Module PUR
      (stdlib seule) : testable en CI sans ROS ni LLM.
POURQUOI (cf. dadou_robot_ros/docs/etude-niveaux-reflexion.md §3 bis) : la
      boucle de réflexion tient le fil de l'histoire ; ce fil doit survivre
      aux tours de parole (la bouche n'a que la dernière réplique en tête). La
      boucle lente est l'AUTEUR unique de cet état (apply), la parole le
      lit sous forme de résumé dans le tableau de situation.
PIÈGE : le LLM propose, ce module dispose. `apply` ne fait confiance à rien :
      critère inconnu, déjà validé, valeur vide ou type inattendu = ignoré
      sans exception (un JSON de LLM ne doit jamais faire tomber le spectacle).
      Un critère validé ne se réécrit JAMAIS : sans ça une réflexion plus tard
      « corrigerait » la valeur gagnée par un passant.
"""
from __future__ import annotations

from typing import Optional

CRITERIA = ("love", "tenderness", "friendship", "speed", "strong")

# Plafonds (caractères) des champs écrits par la réflexion. Revue adversariale
# du 23/10 (I6) : un passant qui dicte un long texte (« retiens ça comme
# indication : … ») le faisait recopier tel quel dans la mission, relue à
# CHAQUE réplique — injection depuis la transcription et premier mot rallongé.
# Tronqué, jamais refusé : le fond utile tient dans ces longueurs.
VALEUR_MAX_CHARS = 60
INDICATION_MAX_CHARS = 160
NOM_MAX_CHARS = 40          # nom d'un guide, donc aussi « par » d'un critère
SIGNALEMENT_MAX_CHARS = 80


def _text(value, max_chars: int) -> Optional[str]:
    """Chaîne rognée et tronquée à `max_chars` ; None si absente, vide ou
    non-str (null/vide ignorés)."""
    if not isinstance(value, str):
        return None
    value = value.strip()[:max_chars].rstrip()
    return value or None


class MissionState:
    """État de la quête. Écrit par la réflexion seule (apply), lu partout."""

    def __init__(self, destination: str):
        self.destination = destination
        self.criteres: dict = {name: None for name in CRITERIA}
        self.guides: list = []
        self.indication: Optional[str] = None
        # Prochain numéro de guide à attribuer (commence à 1). Le numéro
        # appartient à la PERSONNE (attribué à sa première apparition, qu'elle
        # arrive par la clé "guide" ou par un critère validé) : « guide n°1 »
        # désigne donc toujours la même personne dans le résumé.
        self._next_guide = 1

    # -- écriture ----------------------------------------------------------

    def _find_guide(self, nom: str) -> Optional[dict]:
        wanted = nom.casefold()
        for guide in self.guides:
            if guide["nom"].casefold() == wanted:
                return guide
        return None

    def _add_guide(self, nom: str, signalement: str) -> dict:
        guide = {"nom": nom, "signalement": signalement, "guide": self._next_guide}
        self._next_guide += 1
        self.guides.append(guide)
        return guide

    def apply(self, update: dict) -> list:
        """Applique une mise à jour proposée par la réflexion ; rend les
        libellés des changements RÉELLEMENT appliqués (pour le log). Les clés
        inconnues et tout ce qui est invalide sont ignorés, jamais d'exception."""
        changes: list = []
        if not isinstance(update, dict):
            return changes

        valide = update.get("critere_valide")
        if isinstance(valide, dict):
            critere = _text(valide.get("critere"), NOM_MAX_CHARS)
            valeur = _text(valide.get("valeur"), VALEUR_MAX_CHARS)
            par = _text(valide.get("par"), NOM_MAX_CHARS)
            if (critere in self.criteres and self.criteres[critere] is None
                    and valeur and par):
                guide = self._find_guide(par) or self._add_guide(par, "")
                self.criteres[critere] = {"valeur": valeur, "par": par,
                                          "guide": guide["guide"]}
                changes.append(f"critère {critere} validé (« {valeur} », par {par}, "
                               f"guide n°{guide['guide']})")

        indication = _text(update.get("indication"), INDICATION_MAX_CHARS)
        if indication is not None and indication != self.indication:
            self.indication = indication
            changes.append(f"indication : {indication}")

        nouveau = update.get("guide")
        if isinstance(nouveau, dict):
            nom = _text(nouveau.get("nom"), NOM_MAX_CHARS)
            if nom and self._find_guide(nom) is None:
                guide = self._add_guide(
                    nom, _text(nouveau.get("signalement"), SIGNALEMENT_MAX_CHARS) or "")
                changes.append(f"guide : {nom} (n°{guide['guide']})")
        return changes

    # -- lecture -----------------------------------------------------------

    def complete(self) -> bool:
        return all(value is not None for value in self.criteres.values())

    def summary(self) -> str:
        """Résumé d'une ligne relu par la réflexion et le tableau. Sections
        absentes omises ; complète → conclusion dramatique en fin."""
        parts = [f"Mission : trouver {self.destination}."]
        valides = [(name, v) for name, v in self.criteres.items() if v is not None]
        if valides:
            items = "; ".join(
                f"{name} (« {v['valeur']} », par {v['par']}, guide n°{v['guide']})"
                for name, v in valides)
            parts.append(f"Critères validés : {items}.")
        restent = [name for name, v in self.criteres.items() if v is None]
        if restent:
            parts.append(f"Restent : {', '.join(restent)}.")
        if self.indication:
            # rstrip : le LLM finit souvent son indication par un point — sans
            # ça le résumé affichait « boulangerie.. » (banc réel du 23/10).
            parts.append(f"Dernière indication : {self.indication.rstrip(' .')}.")
        if self.guides:
            parts.append(f"Guides : {', '.join(g['nom'] for g in self.guides)}.")
        if self.complete():
            # Revue adversariale du 23/10 (M4) : « le paradis » était écrit en
            # dur — une autre destination (paramètre ROS) concluait sur le
            # paradis quand même.
            parts.append(f"Les cinq critères sont réunis : {self.destination}, c'est ici, "
                         "maintenant, avec ces gens-là.")
        return " ".join(parts)

    # -- (dé)sérialisation : payload du topic latché MISSION_STATE_TOPIC ----

    def to_dict(self) -> dict:
        return {
            "destination": self.destination,
            "criteres": {name: (dict(v) if v else None) for name, v in self.criteres.items()},
            "guides": [dict(g) for g in self.guides],
            "indication": self.indication,
            "next_guide": self._next_guide,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MissionState":
        """Inverse de to_dict. Tolérant : champ absent = valeur neuve."""
        state = cls(str(data.get("destination", "")))
        criteres = data.get("criteres") or {}
        for name in CRITERIA:
            value = criteres.get(name)
            state.criteres[name] = dict(value) if isinstance(value, dict) else None
        state.guides = [dict(g) for g in (data.get("guides") or []) if isinstance(g, dict)]
        state.indication = data.get("indication")
        default_next = max([g.get("guide", 0) for g in state.guides] + [0]) + 1
        state._next_guide = int(data.get("next_guide", default_next))
        return state
