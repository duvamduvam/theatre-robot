"""Porte sim, barrière du DÉPLOIEMENT (lot L1d-2, décision 7 ter) : chaque séquence,
expression et lumière de data/ a son tampon `rejeu` à jour, chaque piste roues son tampon
`roues`, aucune entrée orpheline au registre (data/json/validations-sim.json).

Rouge = quelque chose de modifié n'a pas été joué en sim. Ne se corrige JAMAIS en retouchant le
registre à la main : `machines/sim/rejouer-modifiees.sh` (rejeu automatique, puis « Valider les
roues pour le robot » pour chaque piste roues touchée). Mode d'emploi : docs/operations.md,
« La porte sim : rejouer, valider les roues ».
"""
import os

from theatre_contrats import donnees

# data/ du mono-dépôt (données du robot, L1e-4b) ; le test vit dans packages/didier_core/test/unit.
DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))), "data")
REGISTRE = os.path.join(DATA_ROOT, donnees.FICHIER_REGISTRE)
REPARER = "à rejouer : machines/sim/rejouer-modifiees.sh (docs/operations.md, « La porte sim »)"


def test_registre_present_et_au_format():
    assert os.path.isfile(REGISTRE), REPARER
    registre = donnees.lire_registre(DATA_ROOT)
    assert registre["version"] == donnees.VERSION_REGISTRE
    assert set(registre) == {"version", *donnees.FAMILLES_REJOUEES}
    # Un seul format (indent=1, clés triées) : un registre retouché à la main se voit.
    with open(REGISTRE, "rb") as f:
        assert f.read() == donnees.serialiser_registre(registre)
    for nom, entree in registre["sequence"].items():
        assert set(entree) <= {"rejeu", "roues", "origine_roues"}, nom
        assert ("roues" in entree) == ("origine_roues" in entree), nom
        assert entree.get("origine_roues", "sim") in ("sim", "heritee"), nom
    for famille in ("expression", "lumiere"):
        for nom, entree in registre[famille].items():
            assert set(entree) == {"rejeu"}, (famille, nom)


def test_tout_est_rejoue_en_sim():
    assert donnees.a_rejouer(DATA_ROOT) == [], REPARER


def test_toute_piste_roues_est_validee():
    assert donnees.roues_a_valider(DATA_ROOT) == [], \
        "piste roues modifiée : la rejouer en sim puis « Valider les roues pour le robot »"


def test_aucune_entree_orpheline():
    assert donnees.orphelines(DATA_ROOT) == [], \
        "élément effacé ou renommé : l'observateur retire les orphelines à chaque écriture " \
        "(machines/sim/rejouer-modifiees.sh) ; sans rien à rejouer, retirer l'entrée à la main " \
        "ne valide rien"
