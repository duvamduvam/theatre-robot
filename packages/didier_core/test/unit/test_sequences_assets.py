"""Valide les RÉFÉRENCES CROISÉES des séquences de data/json/sequences/** — par le contrat
unique theatre_contrats.donnees.verifier_sequence (lot L1d, 12/11).

Trois pistes concernées (règles dans donnees.py, plus ici) :
 - "faces" : [t, nom] -> nom doit être une clé de json/expressions.json ;
 - "robot_lights" : [t, nom] -> nom doit être une clé de json/robot_lights.json ;
 - "audios" : [t, valeur] -> la sentinelle "stop" (AudioManager.update() l'intercepte, ce
   n'est PAS un fichier) ou un chemin relatif à medias/audios/, qui doit exister
   (medias/audios est versionné : on vérifie l'existence, pas seulement le format).
Le FORMAT des pistes : test_sequences_json.py.
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
MOTIFS_REFERENCES = ("référence l'expression", "référence la séquence lumière",
                     "nom.mp3/nom.wav", "fichier audio introuvable")


def test_audios_verifiables():
    # medias/audios/ est versionné : sans lui, seule la forme des noms serait jugée.
    assert REFERENCES["audios_verifiables"] is True


@pytest.mark.parametrize("path", SEQUENCE_FILES, ids=lambda p: os.path.relpath(p, SEQUENCES_DIR))
def test_sequence_references_exist(path):
    with open(path) as f:
        sequence = json.load(f)
    erreurs = [e for e in donnees.verifier_sequence(sequence, REFERENCES)
               if any(m in e for m in MOTIFS_REFERENCES)]
    assert erreurs == []
