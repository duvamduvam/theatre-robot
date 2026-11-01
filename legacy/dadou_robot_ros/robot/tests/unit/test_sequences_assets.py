"""Valide les RÉFÉRENCES CROISÉES des séquences JSON (json/sequences/**) vers
les autres bases de données JSON et les assets — complète test_sequences_json.py
qui ne valide que le FORMAT des pistes, pas ce qu'elles pointent.

Trois pistes concernées :
 - "faces" : [t, nom] -> nom doit être une clé de json/expressions.json
   (consommé par Face.update, robot/actions/face.py : self.sequences_name[msg[FACE]]) ;
 - "robot_lights" : [t, nom] -> nom doit être une clé de json/robot_lights.json
   (même mécanique, côté Lights) ;
 - "audios" : [t, valeur] -> soit le mot-clé "stop" (sentinelle STOP,
   utils_static.STOP = 'stop' : AudioManager.update() l'intercepte pour couper
   le son, ce n'est PAS un nom de fichier — voir json/sequences/eternel-show/stop.json),
   soit un chemin RELATIF à medias/audios/ (ex. "eternel-short/p7-1.mp3"),
   consommé tel quel par AudioManager.play_sound() :
   `self.config[AUDIOS_DIRECTORY] + audio`.

Existence des fichiers audio : medias/audios/ EST versionné dans ce dépôt
(vérifié : `git ls-files medias/audios | wc -l` -> 255 fichiers commités,
pas de règle .gitignore dessus) — on peut donc bel et bien vérifier
l'existence des fichiers référencés, pas seulement leur format.
"""

import glob
import json
import os
import re

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SEQUENCES_DIR = os.path.join(REPO_ROOT, "json", "sequences")
AUDIOS_DIR = os.path.join(REPO_ROOT, "medias", "audios")
EXPRESSIONS_FILE = os.path.join(REPO_ROOT, "json", "expressions.json")
ROBOT_LIGHTS_FILE = os.path.join(REPO_ROOT, "json", "robot_lights.json")

# Sentinelle de commande audio (utils_static.STOP), pas un nom de fichier :
# voir AudioManager.update() qui intercepte msg[AUDIO] == STOP avant toute
# tentative de lecture de fichier.
AUDIO_STOP_COMMAND = "stop"

AUDIO_FILENAME_RE = re.compile(r".+\.(mp3|wav)$", re.IGNORECASE)

# Références mortes préexistantes, à trancher : AUCUNE au moment d'écrire ce
# test. Une avait été découverte pendant l'exploration (2026-07-11) :
# "eternel-short/p7-1.mp3" référencé par appel-eternel-life.json et
# appel-eternel-life2.json pointait vers un fichier nommé par erreur
# "p7-1..mp3" (double point) sur disque. Typo évidente côté ASSET (le voisin
# p7-2.mp3 est correctement nommé, les deux séquences s'accordent sur
# "p7-1.mp3") -> fichier renommé plutôt que masqué ici par une exception.
EXCEPTIONS = []

with open(EXPRESSIONS_FILE) as f:
    EXPRESSIONS = json.load(f)
with open(ROBOT_LIGHTS_FILE) as f:
    ROBOT_LIGHTS = json.load(f)

SEQUENCE_FILES = sorted(glob.glob(os.path.join(SEQUENCES_DIR, "**", "*.json"), recursive=True))

# medias/audios est versionné dans ce dépôt (voir docstring) : on peut vérifier
# l'existence réelle des fichiers, pas seulement leur format.
AUDIOS_DIRECTORY_VERSIONED = os.path.isdir(AUDIOS_DIR)


@pytest.mark.parametrize("path", SEQUENCE_FILES, ids=lambda p: os.path.relpath(p, SEQUENCES_DIR))
def test_sequence_faces_references_exist(path):
    with open(path) as f:
        sequence = json.load(f)

    rel = os.path.relpath(path, SEQUENCES_DIR)
    for i, keyframe in enumerate(sequence.get("faces", [])):
        t, name = keyframe
        if (rel, "faces", name) in EXCEPTIONS:
            continue
        assert name in EXPRESSIONS, \
            "{} : faces[{}] référence l'expression inconnue {!r} (absente de {})".format(
                rel, i, name, EXPRESSIONS_FILE)


@pytest.mark.parametrize("path", SEQUENCE_FILES, ids=lambda p: os.path.relpath(p, SEQUENCES_DIR))
def test_sequence_robot_lights_references_exist(path):
    with open(path) as f:
        sequence = json.load(f)

    rel = os.path.relpath(path, SEQUENCES_DIR)
    for i, keyframe in enumerate(sequence.get("robot_lights", [])):
        t, name = keyframe
        if (rel, "robot_lights", name) in EXCEPTIONS:
            continue
        assert name in ROBOT_LIGHTS, \
            "{} : robot_lights[{}] référence la séquence lights inconnue {!r} (absente de {})".format(
                rel, i, name, ROBOT_LIGHTS_FILE)


@pytest.mark.parametrize("path", SEQUENCE_FILES, ids=lambda p: os.path.relpath(p, SEQUENCES_DIR))
def test_sequence_audios_references(path):
    with open(path) as f:
        sequence = json.load(f)

    rel = os.path.relpath(path, SEQUENCES_DIR)
    for i, keyframe in enumerate(sequence.get("audios", [])):
        t, value = keyframe
        where = "{} : audios[{}]".format(rel, i)

        if value == AUDIO_STOP_COMMAND:
            continue  # sentinelle de commande, pas un fichier

        assert AUDIO_FILENAME_RE.match(value), \
            "{} : {!r} n'a pas la forme nom.mp3/nom.wav (ni la sentinelle 'stop')".format(where, value)

        if (rel, "audios", value) in EXCEPTIONS:
            continue

        if AUDIOS_DIRECTORY_VERSIONED:
            full_path = os.path.join(AUDIOS_DIR, value)
            assert os.path.isfile(full_path), \
                "{} : fichier audio introuvable : {}".format(where, full_path)
        # sinon (répertoire non versionné dans ce checkout) : on ne peut vérifier
        # QUE le format du nom, pas l'existence -> pas d'assertion supplémentaire,
        # pour ne pas faire dépendre le résultat du test de l'environnement.
