"""Lot L1a : les décodeurs StringTime passent par le codec commun
(theatre_contrats.stringtime) SANS changer de comportement.

Pour chaque site converti : l'extrait D'AVANT (recopié tel quel du code au
2026-11-02, avant le lot) et l'appel qui le remplace donnent la même issue —
même valeur ou même type d'exception — sur une batterie d'entrées qui couvre
les pièges connus (brut sans guillemets, null, entier JSON géant qui lève
ValueError hors JSONDecodeError, payload non-chaîne). Puis l'AST du site
prouve que c'est bien CET appel qui y est fait, et qu'il ne reste aucun
json.loads dans la fonction.

Les nodes eux-mêmes (rclpy) sont exercés par leurs harnais : test_gaze_look,
test_director_node, test_route_driver_node, test_web_protocol (pont).
"""
import ast
import json
import logging
import os

import pytest

from theatre_contrats import stringtime

# legacy/dadou_robot_ros (données du robot) ; le test vit dans packages/didier_core/test/unit (L1e-3c).
RACINE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))), "legacy", "dadou_robot_ros")
# packages/ du mono-dépôt (L1e-1) ; les SITES ci-dessous le citent en chemin relatif à RACINE.
DEPS = os.path.join(os.path.dirname(os.path.dirname(RACINE)), "packages")

ENTREES = [
    '"calib"', '{"brightness": 0.5}', 'false', 'true', 'null', '0', '1', '"1"', '0.5',
    'on', 'off', ' off ', '"on"', '', '   ', 'calib', '{"dir": "gauche", "hold_ms": 500}',
    '{"angle_deg": 30}', '[1, 2]', '{"poi": "nef", "event": "enter", "distance": 1.2}',
    '{"poi": "nef"}', '"boot"', ' "cmd" ', '\x0c"boot"', 'NaN', "1" * 5000, None, 0.7,
]


def issue(fonction, entree):
    """Valeur (repr, pour comparer NaN) ou type d'exception — jamais d'égalité approximative."""
    try:
        return ("valeur", repr(fonction(entree)))
    except Exception as e:  # noqa: BLE001 — on compare justement le TYPE levé
        return ("exception", type(e).__name__)


# ---------------------------------------------------------------- extraits d'AVANT (verbatim)

def avant_tolerant(raw):
    # gaze_control._parse_look, gaze_follower (x2), person_follower,
    # route_driver._decode, director.route_cmd_kind, director_node._on_chat_move
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        value = raw
    return value


def avant_speed_factor_decodage(raw):
    # director.speed_factor (la suite de la fonction est inchangée)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            pass
    return raw


def apres_speed_factor_decodage(raw):
    if isinstance(raw, str):
        raw = stringtime.decode_or_raw(raw, "route_speed")
    return raw


def avant_payload(ros_msg, topic):
    # robot/nodes/payload.py (décodeur commun de juillet)
    try:
        return json.loads(ros_msg.msg)
    except (json.JSONDecodeError, TypeError):
        logging.error("payload invalide sur '%s' (JSON attendu, ex. '\"nom\"' avec "
                      "guillemets) : %r", topic, ros_msg.msg)
        return None


class Msg:
    def __init__(self, msg):
        self.msg = msg


# ---------------------------------------------------------------- équivalence des issues

@pytest.mark.parametrize("entree", ENTREES, ids=repr)
def test_tolerant(entree):
    assert issue(stringtime.decode_or_raw, entree) == issue(avant_tolerant, entree)


@pytest.mark.parametrize("entree", ENTREES, ids=repr)
def test_speed_factor(entree):
    assert issue(apres_speed_factor_decodage, entree) == issue(avant_speed_factor_decodage, entree)


@pytest.mark.parametrize("entree", ENTREES, ids=repr)
def test_loads_nu(entree):
    # director_node (x3), fault_relay_node, web_bridge_node (x2) : except gardés tels quels.
    assert issue(stringtime.loads, entree) == issue(json.loads, entree)


@pytest.mark.parametrize("entree", ENTREES, ids=repr)
def test_payload_strict_valeur_et_log(entree, caplog):
    from didier_core.nodes.payload import decode
    with caplog.at_level(logging.ERROR):
        avant = issue(lambda e: avant_payload(Msg(e), "face"), entree)
        logs_avant = [r.getMessage() for r in caplog.records]
        caplog.clear()
        apres = issue(lambda e: decode(Msg(e), "face"), entree)
        logs_apres = [r.getMessage() for r in caplog.records]
    assert apres == avant
    assert logs_apres == logs_avant


def test_cas_graves():
    # Quelques issues ÉCRITES EN DUR, pour que l'équivalence ne compare pas
    # deux erreurs identiques sans qu'on le voie.
    assert issue(stringtime.decode_or_raw, "on") == ("valeur", "'on'")
    assert issue(stringtime.decode_or_raw, '"on"') == ("valeur", "'on'")
    assert issue(stringtime.decode_or_raw, "1" * 5000) == ("valeur", repr("1" * 5000))
    assert issue(stringtime.loads, "1" * 5000) == ("exception", "ValueError")
    assert issue(stringtime.loads, None) == ("exception", "TypeError")


# ---------------------------------------------------------------- le site fait bien CET appel

SITES = [
    # (fichier relatif à la racine du dépôt, fonction, appel attendu dans son corps)
    ("../../packages/didier_core/didier_core/nodes/payload.py", "decode", "stringtime.decode(ros_msg, topic)"),
    ("../../packages/didier_core/didier_core/move/gaze_control.py", "_parse_look", "stringtime.decode_or_raw(raw, 'look')"),
    ("../../packages/didier_core/didier_core/nodes/gaze_follower_node.py", "_on_animation_state",
     "stringtime.decode_or_raw(raw, ANIMATION_STATE_TOPIC)"),
    ("../../packages/didier_core/didier_core/nodes/gaze_follower_node.py", "_on_gaze_cmd", "stringtime.decode_or_raw(raw, GAZE_CMD_TOPIC)"),
    ("../../packages/didier_core/didier_core/nodes/person_follower_node.py", "_on_follow_cmd",
     "stringtime.decode_or_raw(raw, FOLLOW_CMD_TOPIC)"),
    ("../../packages/didier_rehearsal/didier_rehearsal/route_driver_node.py", "_decode",
     "stringtime.decode_or_raw(raw)"),
    ("../../packages/didier_rehearsal/didier_rehearsal/director.py", "speed_factor",
     "stringtime.decode_or_raw(raw, ROUTE_SPEED_TOPIC)"),
    ("../../packages/didier_rehearsal/didier_rehearsal/director.py", "route_cmd_kind",
     "stringtime.decode_or_raw(raw, ROUTE_CMD_TOPIC)"),
    ("../../packages/didier_rehearsal/didier_rehearsal/director_node.py", "_on_route_cause",
     "stringtime.loads(msg.msg)"),
    ("../../packages/didier_rehearsal/didier_rehearsal/director_node.py", "_on_goto_result",
     "stringtime.loads(msg.msg)"),
    ("../../packages/didier_rehearsal/didier_rehearsal/director_node.py", "_on_poi_event",
     "stringtime.loads(msg.msg)"),
    ("../../packages/didier_rehearsal/didier_rehearsal/director_node.py", "_on_chat_move",
     "stringtime.decode_or_raw(raw, CHAT_MOVE_TOPIC)"),
    ("../../packages/didier_rehearsal/didier_rehearsal/fault_relay_node.py", "_on_cmd",
     "stringtime.loads(msg.msg)"),
    ("../../packages/didier_web/didier_web/web_bridge_node.py", "_on_message",
     "stringtime.loads(msg.msg)"),
    ("../../packages/didier_web/didier_web/web_bridge_node.py", "_on_feed",
     "stringtime.loads(msg.msg)"),
]


def _fonction(chemin, nom):
    arbre = ast.parse(open(os.path.join(RACINE, chemin), encoding="utf-8").read())
    trouvees = [n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef) and n.name == nom]
    assert len(trouvees) == 1, f"{chemin}:{nom} introuvable ou ambigu"
    return trouvees[0]


@pytest.mark.parametrize("chemin,nom,appel", SITES, ids=lambda v: v if "/" not in v else None)
def test_site_appelle_le_codec(chemin, nom, appel):
    appels = [ast.unparse(n) for n in ast.walk(_fonction(chemin, nom)) if isinstance(n, ast.Call)]
    assert appel in appels
    assert not [a for a in appels if a.startswith("json.loads(")]


def test_traitements_d_echec_gardes():
    # Les sites en `loads` gardent EXACTEMENT leurs except (c'est ce qui fait
    # l'équivalence) : on les relit dans l'AST.
    attendus = {
        ("director_node.py", "_on_route_cause"): ["(ValueError, TypeError)"],
        ("director_node.py", "_on_goto_result"): ["(ValueError, TypeError)"],
        # liste COMPLÈTE des except de la fonction, dans l'ordre de l'AST : un except
        # ajouté plus bas (revue du 02/11) ne passe plus inaperçu
        ("director_node.py", "_on_poi_event"): ["(ValueError, TypeError, KeyError)", "Exception"],
        ("fault_relay_node.py", "_on_cmd"): ["ValueError", "ValueError"],
        ("web_bridge_node.py", "_on_message"): ["(TypeError, json.JSONDecodeError)"],
        ("web_bridge_node.py", "_on_feed"): ["(TypeError, json.JSONDecodeError)"],
    }
    for chemin, nom, _ in SITES:
        cle = (os.path.basename(chemin), nom)
        if cle in attendus:
            gestionnaires = [ast.unparse(h.type) for h in ast.walk(_fonction(chemin, nom))
                             if isinstance(h, ast.ExceptHandler) and h.type is not None]
            assert gestionnaires == attendus[cle], cle
