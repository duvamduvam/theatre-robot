"""L'ARBRE (ce qui est PERMIS quand) — py_trees, spec A1 §3.

Racine = sélecteur de PRIORITÉS (le premier enfant qui réussit gagne) :
  1. arrêt vocal    : un « stop » a été relayé (bouche ou console) -> verrou
                      jusqu'au « go » : aucune action de déplacement ;
                      expressions et regards permis (le relais lui-même est fait
                      À LA RÉCEPTION, jamais pondéré : selecteur.relayer_stop) ;
  2. superviseur absent (mode « exigeant » seulement) : aucun déplacement ;
  3. ordre macro en cours (console) : il peut interrompre l'action engagée ;
  4. action engagée : on la finit — seule une offre de valeur >=
                      engagement.seuil_rupture peut l'interrompre ;
  5. choisir        : la feuille de score, tout est permis.
Les feuilles « choisir » délèguent au sélecteur (Selecteur.choisir) : l'arbre
porte la STRUCTURE, le score la VARIÉTÉ (décision 7 du 02/11). Les verrous
communs à toutes les branches (fatigue, « ignore », réfractaires) vivent dans
le sélecteur et le score, pas ici.
"""
import py_trees
from py_trees.common import Status


class Condition(py_trees.behaviour.Behaviour):
    """SUCCESS si le prédicat (sans argument) est vrai, FAILURE sinon."""

    def __init__(self, name, predicat):
        super().__init__(name)
        self.predicat = predicat

    def update(self):
        return Status.SUCCESS if self.predicat() else Status.FAILURE


class Choisir(py_trees.behaviour.Behaviour):
    """Feuille de score : délègue au sélecteur avec les permissions de sa branche.
    Réussit toujours (« ne rien changer » est un résultat)."""

    def __init__(self, name, selecteur, deplacement_permis, interrompt):
        super().__init__(name)
        self.selecteur = selecteur
        self.deplacement_permis = deplacement_permis
        self.interrompt = interrompt

    def update(self):
        self.selecteur.choisir(self.name, self.deplacement_permis, self.interrompt)
        return Status.SUCCESS


def _branche(nom, predicat, selecteur, deplacement_permis, interrompt):
    return py_trees.composites.Sequence(nom, memory=False, children=[
        Condition(nom + " ?", predicat),
        Choisir(nom, selecteur, deplacement_permis, interrompt),
    ])


# Noms des branches (champ `branche` des lignes de décision du journal).
ARRET_VOCAL = "arret_vocal"
SUPERVISEUR_ABSENT = "superviseur_absent"
ORDRE_MACRO = "ordre_macro"
ENGAGEE = "engagee"
CHOISIR = "choisir"
BRANCHES = (ARRET_VOCAL, SUPERVISEUR_ABSENT, ORDRE_MACRO, ENGAGEE, CHOISIR)


def construire(selecteur) -> py_trees.behaviour.Behaviour:
    """L'arbre du sélecteur, dans l'ordre de priorité GRAVÉ (test_arbre.py)."""
    return py_trees.composites.Selector("permis", memory=False, children=[
        _branche(ARRET_VOCAL, selecteur.verrouille, selecteur, False, False),
        _branche(SUPERVISEUR_ABSENT, selecteur.superviseur_absent, selecteur, False, False),
        _branche(ORDRE_MACRO, selecteur.ordre_en_cours, selecteur, True, True),
        _branche(ENGAGEE, selecteur.engagee, selecteur, True, False),
        Choisir(CHOISIR, selecteur, True, False),
    ])
