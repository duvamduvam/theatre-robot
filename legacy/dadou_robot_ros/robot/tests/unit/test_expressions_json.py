"""Valide le contrat de données de json/expressions.json (consommé par robot/actions/face.py).

Contrat vérifié :
 - duration : nombre > 0 ; loop : bool (champs lus sans garde par Face.update) ;
 - mouths/left_eyes/right_eyes : listes de keyframes [t, nom_de_fichier] ;
   t est un nombre dans [0, 1], croissant au fil de la piste (même règle que
   les séquences d'animation, voir test_sequences_json.py) ;
 - chaque fichier référencé EXISTE sous medias/visuals/mouth (mouths) ou
   medias/visuals/eye (left_eyes/right_eyes) ;
 - chaque PNG référencé a la BONNE TAILLE : bouche 24x16 (MOUTH_WIDTH/HEIGHT,
   voir robot/visual/image_mapping.py), œil 8x8 (MATRIX). ImageMapping.mapping()
   REFUSE silencieusement (log error, rien n'est écrit) une image de mauvaise
   taille : un PNG mal dimensionné ne casse rien au runtime, il produit juste
   un visage figé/mort en silence — autant l'attraper ici, à la donnée.

Remarque sur le champ « name » : la spec de départ de ce test demandait
name == clé comme champ obligatoire. Exploration du code : AbstractJsonActions.
load_keys_and_names_sequences() (robot/actions/abstract_json_actions.py)
INJECTE lui-même sequences_name[cle][NAME] = cle au chargement — le champ
n'a donc PAS besoin d'être présent dans le JSON (36 des 37 expressions actuelles
ne l'ont pas, seule "sexy" le porte). On vérifie donc seulement la cohérence
QUAND il est présent, sans l'exiger.
"""

import json
import os

import pytest

try:
    import imageio.v2 as imageio
except ImportError:  # pragma: no cover - imageio est dans requirements-test
    imageio = None

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EXPRESSIONS_FILE = os.path.join(REPO_ROOT, "json", "expressions.json")
MOUTH_DIR = os.path.join(REPO_ROOT, "medias", "visuals", "mouth")
EYE_DIR = os.path.join(REPO_ROOT, "medias", "visuals", "eye")

# Dimensions attendues (robot/visual/image_mapping.py : MOUTH_WIDTH/MOUTH_HEIGHT/MATRIX).
MOUTH_SIZE = (24, 16)  # (largeur, hauteur)
EYE_SIZE = (8, 8)

TRACK_FIELDS = ("mouths", "left_eyes", "right_eyes")
TRACK_DIR = {"mouths": MOUTH_DIR, "left_eyes": EYE_DIR, "right_eyes": EYE_DIR}
TRACK_SIZE = {"mouths": MOUTH_SIZE, "left_eyes": EYE_SIZE, "right_eyes": EYE_SIZE}

# Références mortes préexistantes, à trancher : AUCUNE connue à ce jour (exploration
# du 2026-07-11 : les 37 expressions référencent des fichiers existants, aux bonnes
# dimensions). Garder la liste vide et le mécanisme prêts pour de futures entrées.
EXCEPTIONS = []

with open(EXPRESSIONS_FILE) as f:
    EXPRESSIONS = json.load(f)

EXPRESSION_NAMES = sorted(EXPRESSIONS.keys())


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def png_size(path):
    """Retourne (largeur, hauteur) d'un PNG. imageio est déjà utilisé par
    robot/visual/visual.py (Visual.__init__) : même lecteur que la prod."""
    image = imageio.imread(path)
    height, width = image.shape[0], image.shape[1]
    return width, height


def check_visual_track(expression_name, track_name, track):
    # Liste VIDE autorisée : Track.frames (robot/sequences/track.py) traite
    # explicitement une piste vide comme « aucune activation, poll toujours
    # None » — c'est la façon documentée de dire « ne pas toucher cet
    # actionneur » (ex. expression "internet" : yeux non animés).
    assert isinstance(track, list), \
        "{} : piste {} : liste attendue".format(expression_name, track_name)

    previous_t = -1
    for i, keyframe in enumerate(track):
        where = "{} : {}[{}]".format(expression_name, track_name, i)
        assert isinstance(keyframe, list) and len(keyframe) == 2, \
            "{} : keyframe [t, fichier] attendu, reçu {!r}".format(where, keyframe)
        t, filename = keyframe
        assert is_number(t) and 0 <= t <= 1, "{} : temps hors [0,1] : {!r}".format(where, t)
        assert t >= previous_t, "{} : keyframes non triés (t={} après t={})".format(where, t, previous_t)
        previous_t = t

        assert isinstance(filename, str), "{} : nom de fichier attendu, reçu {!r}".format(where, filename)

        if (expression_name, track_name, filename) in EXCEPTIONS:
            continue

        full_path = os.path.join(TRACK_DIR[track_name], filename)
        assert os.path.isfile(full_path), \
            "{} : visuel introuvable : {}".format(where, full_path)

        if imageio is not None:
            width, height = png_size(full_path)
            expected = TRACK_SIZE[track_name]
            assert (width, height) == expected, \
                "{} : {} fait {}x{}, attendu {}x{} (ImageMapping refuserait ce visuel en silence)".format(
                    where, filename, width, height, expected[0], expected[1])


def test_expressions_file_exists():
    assert len(EXPRESSIONS) >= 30, "expressions introuvables sous {}".format(EXPRESSIONS_FILE)


@pytest.mark.parametrize("name", EXPRESSION_NAMES)
def test_expression_format(name):
    expression = EXPRESSIONS[name]

    # Champ "name" : optionnel dans le fichier (injecté par le loader depuis la
    # clé), mais s'il est présent il doit être cohérent avec la clé.
    if "name" in expression:
        assert expression["name"] == name, \
            "{} : champ name {!r} != clé {!r}".format(name, expression["name"], name)

    assert is_number(expression.get("duration")) and expression["duration"] > 0, \
        "{} : champ 'duration' (nombre > 0) obligatoire".format(name)
    assert isinstance(expression.get("loop"), bool), \
        "{} : champ 'loop' (bool) obligatoire".format(name)

    for track_name in TRACK_FIELDS:
        assert track_name in expression, "{} : piste '{}' obligatoire".format(name, track_name)
        check_visual_track(name, track_name, expression[track_name])
