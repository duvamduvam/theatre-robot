"""Valide le format de toutes les séquences JSON du dossier json/sequences/.

Contrat vérifié (celui qu'attendent AnimationManager/Animation et les actions) :
 - champs obligatoires : keys (str), duration (nombre > 0) ;
 - chaque piste d'actionneur est une liste de keyframes [t, valeur] ;
 - t est un nombre dans [0, 1], croissant au fil de la piste ;
 - servos : valeur dans [0, 1], ou 'up'/'down'/'stop', ou dict avec 'mode' ;
 - roues : paire [gauche, droite] dans [-1, 1], ou commande texte, ou dict.
"""

import glob
import json
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SEQUENCES_DIR = os.path.join(REPO_ROOT, "json", "sequences")

SERVO_TRACKS = ("neck", "left_arm", "right_arm", "left_eye", "right_eye")
OTHER_TRACKS = ("audios", "faces", "wheels", "robot_lights")
SERVO_COMMANDS = ("up", "down", "stop")
WHEELS_COMMANDS = ("forward", "backward", "left", "right", "stop")

SEQUENCE_FILES = sorted(glob.glob(os.path.join(SEQUENCES_DIR, "**", "*.json"), recursive=True))


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_track(name, track):
    assert isinstance(track, list), "piste {} : liste attendue".format(name)
    previous_t = -1
    for i, keyframe in enumerate(track):
        where = "{}[{}]".format(name, i)
        assert isinstance(keyframe, list) and len(keyframe) == 2, \
            "{} : keyframe [t, valeur] attendu, reçu {!r}".format(where, keyframe)
        t, value = keyframe
        assert is_number(t) and 0 <= t <= 1, "{} : temps hors [0,1] : {!r}".format(where, t)
        assert t >= previous_t, "{} : keyframes non triés (t={} après t={})".format(where, t, previous_t)
        previous_t = t

        if name in SERVO_TRACKS:
            if is_number(value):
                assert 0 <= value <= 1, "{} : position servo hors [0,1] : {!r}".format(where, value)
            elif isinstance(value, str):
                assert value in SERVO_COMMANDS, "{} : commande servo inconnue : {!r}".format(where, value)
            else:
                assert isinstance(value, dict) and "mode" in value, \
                    "{} : valeur servo invalide : {!r}".format(where, value)
        elif name == "wheels":
            if isinstance(value, list):
                assert len(value) == 2 and all(is_number(v) and -1 <= v <= 1 for v in value), \
                    "{} : consigne roues hors [-1,1] : {!r}".format(where, value)
            elif isinstance(value, str):
                assert value in WHEELS_COMMANDS, "{} : commande roues inconnue : {!r}".format(where, value)
            else:
                assert isinstance(value, dict), "{} : valeur roues invalide : {!r}".format(where, value)


def test_sequences_directory_exists():
    assert len(SEQUENCE_FILES) >= 40, "séquences introuvables sous {}".format(SEQUENCES_DIR)


@pytest.mark.parametrize("path", SEQUENCE_FILES, ids=lambda p: os.path.relpath(p, SEQUENCES_DIR))
def test_sequence_file(path):
    with open(path) as f:
        sequence = json.load(f)

    assert isinstance(sequence.get("keys"), str), "champ 'keys' (str) obligatoire"
    assert is_number(sequence.get("duration")) and sequence["duration"] > 0, \
        "champ 'duration' (ms > 0) obligatoire"

    for track_name in SERVO_TRACKS + OTHER_TRACKS:
        if track_name in sequence:
            check_track(track_name, sequence[track_name])
