"""Valide le FORMAT de toutes les séquences de data/json/sequences/ — par le contrat unique
theatre_contrats.donnees.verifier_sequence (lot L1d, 12/11).

Jusqu'au lot L1d ce test PORTAIT le contrat (keys, duration, keyframes [t, valeur] dans
[0, 1] croissants, servos, roues) ; il est désormais extrait dans theatre_contrats/donnees.py,
lu aussi par l'écrivain du robot (didier_web.data_edit) : un seul juge pour ce qui arrive par
git et pour ce qui arrive par le topic data_edit. Une règle se change LÀ, jamais ici.
Les références croisées (faces, robot_lights, audios) : test_sequences_assets.py.
Durcissement de L1d : les bornes roues (décision 7 de la spec L1d : consigne ≤ 0.89, tenue
≤ 60 s, durée ≤ 300 s, arrêt final [0, 0], plus de commande texte ni de dict).
"""
import glob
import json
import os

import pytest

from theatre_contrats import donnees

# data/ du mono-dépôt (données du robot, L1e-4b) ; le test vit dans packages/didier_core/test/unit.
DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))), "data")
SEQUENCES_DIR = os.path.join(DATA_ROOT, "json", "sequences")

SEQUENCE_FILES = sorted(glob.glob(os.path.join(SEQUENCES_DIR, "**", "*.json"), recursive=True))
REFERENCES = donnees.charger_references(DATA_ROOT)

# Erreurs de FORMAT seulement (les messages de références sont jugés par test_sequences_assets.py).
MOTIFS_REFERENCES = ("référence l'expression", "référence la séquence lumière",
                     "nom.mp3/nom.wav", "fichier audio introuvable")


def test_sequences_directory_exists():
    assert len(SEQUENCE_FILES) >= 40, "séquences introuvables sous {}".format(SEQUENCES_DIR)


@pytest.mark.parametrize("path", SEQUENCE_FILES, ids=lambda p: os.path.relpath(p, SEQUENCES_DIR))
def test_sequence_file(path):
    with open(path) as f:
        sequence = json.load(f)
    erreurs = [e for e in donnees.verifier_sequence(sequence, REFERENCES)
               if not any(m in e for m in MOTIFS_REFERENCES)]
    assert erreurs == []


def test_pistes_roues_de_data_gravees():
    # Faits du 12/11 au soir (spec L1d, décision 7) : 24 pistes roues non vides, toutes
    # terminées par [0, 0] depuis que L1d-1 a ajouté l'arrêt final à iloveyou2 et seq1.
    a_roues = {}
    for path in SEQUENCE_FILES:
        with open(path) as f:
            sequence = json.load(f)
        if sequence.get("wheels"):
            a_roues[os.path.relpath(path, SEQUENCES_DIR)[:-5]] = sequence["wheels"][-1]
    assert len(a_roues) == 24
    assert a_roues["eternel-show/seq1"] == [1, [0, 0]]
    assert a_roues["eternel-show/iloveyou2"] == [1, [0, 0]]
