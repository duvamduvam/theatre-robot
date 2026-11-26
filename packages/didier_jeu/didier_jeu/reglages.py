"""Chargement de config/reglages.yaml — refus EXPLICITE d'un fichier incomplet.

Un réglage manquant ne prend jamais de valeur par défaut cachée dans le code :
le seul endroit où vivent les chiffres est le YAML (et sa copie gravée dans
test/test_reglages.py). Accès par chemin pointé : r.get("hysteresis.marge").
"""
import yaml

# Chemins OBLIGATOIRES (un oubli dans le YAML = refus au démarrage du node).
REQUIS = (
    "tick_s", "hysteresis.marge", "hysteresis.duree_s", "changement.min_s",
    "reaction.maintien_apres_s", "engagement.seuil_rupture", "offres.ttl_s",
    "offres.valeur.personne", "offres.valeur.objet",
    "pistes.perte_s", "pistes.nouvelle_apres_s", "pistes.confiance_min",
    "pulsions.ennui.montee_par_s", "pulsions.ennui.plafond",
    "pulsions.curiosite.saut", "pulsions.curiosite.retombee_par_s",
    "pulsions.lubie.par_poi", "pulsions.lubie.retombee_par_s", "pulsions.lubie.plafond",
    "pulsions.fatigue.par_deplacement", "pulsions.fatigue.retombee_par_s",
    "pulsions.fatigue.seuil_interdit",
    "refractaire_s.initiative_spontanee", "refractaire_s.arret_didier",
    "refractaire_s.expression", "refractaire_s.regarder", "refractaire_s.deplacement",
    "lubie.delai_refus_s", "reprise.min_s", "reprise.max_s",
    "superviseur.mode", "superviseur.silence_max_s",
    "console.ignore_s", "console.ordre_ttl_s", "console.joue_avec_s",
    "console.plus_lent_s", "console.plus_lent_facteur",
    "poids.offre", "poids.pulsion", "poids.console",
    "immobilite.base", "immobilite.pente_ennui", "gains", "emplois",
    "durees_s.regarder", "durees_s.expression_defaut", "durees_s.expression_marge",
    "durees_s.deplacement_max", "durees_s.deplacement_accuse", "durees_s.arret",
    "durees_s.relais", "regard.demi_champ_deg", "approche.hauteur_max",
)
MODES_SUPERVISEUR = ("suppose", "exigeant")


class ReglagesError(ValueError):
    """Réglages invalides — le message dit quel chemin."""


class Reglages:
    def __init__(self, data: dict):
        if not isinstance(data, dict):
            raise ReglagesError("reglages : dictionnaire attendu à la racine")
        self._data = data
        for chemin in REQUIS:
            self.get(chemin)
        if self.get("superviseur.mode") not in MODES_SUPERVISEUR:
            raise ReglagesError(f"superviseur.mode : attendu parmi {MODES_SUPERVISEUR}")
        # Lot S1 : la durée de silence d'une reprise est TIRÉE dans [min_s, max_s].
        if not 0.0 < self.get("reprise.min_s") <= self.get("reprise.max_s"):
            raise ReglagesError("reprise : attendu 0 < min_s <= max_s")

    def get(self, chemin: str):
        node = self._data
        for cle in chemin.split("."):
            if not isinstance(node, dict) or cle not in node:
                raise ReglagesError(f"réglage manquant : {chemin}")
            node = node[cle]
        return node

    def gain(self, action: str) -> float:
        gains = self.get("gains")
        if action not in gains:
            raise ReglagesError(f"gains.{action} manquant")
        return float(gains[action])


def charger_reglages(chemin) -> Reglages:
    with open(chemin, encoding="utf-8") as f:
        return Reglages(yaml.safe_load(f))
