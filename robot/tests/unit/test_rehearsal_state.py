"""État de séance exposé à la page scène (robot_rehearsal.rehearsal_state) --
logique PURE, valeurs gravées en dur (un test qui recalcule l'attendu avec la
fonction testée ne teste rien). Le publieur (node) : test_director_node.py ;
la lecture seule côté pont : test_web_protocol.py."""
import json

import pytest

from robot_rehearsal import contracts
from robot_rehearsal.rehearsal_state import rehearsal_state


@pytest.mark.parametrize("started,ended,hold,attendu", [
    (False, False, False, '{"seance": "attente", "arret_vocal": false}'),
    (False, False, True, '{"seance": "attente", "arret_vocal": true}'),     # « stop » vocal hors séance
    (True, False, False, '{"seance": "en_cours", "arret_vocal": false}'),
    (True, False, True, '{"seance": "en_cours", "arret_vocal": true}'),
    (True, True, False, '{"seance": "terminee", "arret_vocal": false}'),
    (True, True, True, '{"seance": "terminee", "arret_vocal": true}'),
    (False, True, False, '{"seance": "attente", "arret_vocal": false}'),    # incohérent : jamais démarrée
])
def test_payload_grave(started, ended, hold, attendu):
    assert rehearsal_state(started, ended, hold) == attendu


def test_payload_ne_porte_que_deux_cles_aucune_panne():
    """La page ne doit jamais trahir le tirage : exactement ces deux clés, rien
    de plus (ni id de panne, ni type, ni vitesse imposée)."""
    assert sorted(json.loads(rehearsal_state(True, False, True))) == ["arret_vocal", "seance"]


def test_topic_grave():
    assert contracts.REHEARSAL_STATE_TOPIC == "rehearsal/state"
