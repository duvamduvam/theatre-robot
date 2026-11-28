"""Nœud MINCE de l'appareil (geste G6) : un message = un appel à la logique, aucune règle
(verifier_appareil rougit sur tout `if` ici). La plomberie est dans theatre_gabarit.noeud."""
import sys

from theatre_gabarit.noeud import NoeudAppareil

from appareil_gabarit_core import contrat, logique, reglages
from appareil_gabarit_core.pilotes import materiel, sim


def main():
    app = NoeudAppareil(contrat.NOM_NOEUD, contrat.NOM_APPAREIL,
                        {"sim": sim.fabrique, "materiel": materiel.fabrique})
    try:
        r = reglages.charger(app.config)
    except reglages.ReglagesError as erreur:
        app.ros.get_logger().error(str(erreur))
        sys.exit(2)
    regles = logique.Logique(app.pilote, r)
    app.demarrer(regles.etat, regles.repos, regles.tic)
    # APPAREIL : un app.abonner(contrat.<ORDRE>, regles.<ordre>) par topic d'ordre du contrat.
    app.tourner()


if __name__ == "__main__":
    main()
