"""La CI racine (.github/workflows/tests.yml) : chaque suite de la matrice est complète.

Vécu du 19/11 au 22/11 : la suite didier_corps_sur avait été ajoutée sans clé `requirements`
(perdue en résolvant un conflit de fusion) ; `pip install -r` sans argument faisait échouer la
CI de main à chaque fusion, sans qu'aucun test local ne le voie.
"""
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[4]
WORKFLOW = RACINE / ".github" / "workflows" / "tests.yml"


def _matrice():
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    (job,) = doc["jobs"].values()
    return job["strategy"]["matrix"]["include"]


def test_chaque_suite_a_un_dossier_et_un_fichier_de_dependances_existants():
    for entree in _matrice():
        nom = entree.get("suite", "?")
        assert entree.get("dir"), f"{nom} : clé dir manquante"
        assert entree.get("requirements"), f"{nom} : clé requirements manquante"
        assert (RACINE / entree["dir"]).is_dir(), f"{nom} : dossier {entree['dir']} absent"
        assert (RACINE / entree["requirements"]).is_file(), \
            f"{nom} : fichier {entree['requirements']} absent"


def test_les_huit_suites_documentees_sont_dans_la_ci():
    suites = {e["suite"] for e in _matrice()}
    assert suites == {
        "didier_core", "dadou_utils_ros", "didier_jeu", "theatre_contrats",
        "didier_corps_sur", "didier_perception", "didier_vision", "telecommande (legacy)",
        # Lot L3a (28/11, spec L3 décision 8) : le gabarit d'appareil.
        "theatre_gabarit",
    }
