"""Lot L1a : les décodeurs StringTime de la vision passent par le codec commun
(theatre_contrats.stringtime) sans changer leurs SORTIES.

- reflection_contract._load_object : décodage STRICT (décision du 02/11) —
  mêmes sorties qu'avant pour toute entrée, entier JSON géant compris ; seul
  ajout : un log ERROR avec le topic quand le payload est invalide.
- chat_node._on_goto_result : `loads` nu, son except et son warning gardés.
Même méthode que le test homonyme de dadou_robot_ros : extrait d'AVANT
recopié tel quel, issue comparée, puis l'AST prouve l'appel fait par le site.
"""
import ast
import json
import logging
import os

import pytest

from vision.ai import reflection_contract

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ENTREES = [
    '{"text": "ok", "t_ms": 3}', '{"direction": "  vas-y  "}', '{"demande": ""}', '{}', '[]',
    'null', '"texte"', '1', '', 'pas du json', "1" * 5000, None, 0.5, '{"text": 3}',
]


def issue(fonction, entree):
    try:
        return ("valeur", repr(fonction(entree)))
    except Exception as e:  # noqa: BLE001 — on compare le TYPE levé
        return ("exception", type(e).__name__)


def avant_load_object(raw):
    # reflection_contract._load_object au 2026-11-02, avant le lot L1a
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


@pytest.mark.parametrize("entree", ENTREES, ids=repr)
def test_load_object(entree):
    apres = issue(lambda e: reflection_contract._load_object(e, reflection_contract.SITUATION_TOPIC), entree)
    assert apres == issue(avant_load_object, entree)


@pytest.mark.parametrize("entree", ENTREES, ids=repr)
def test_decodeurs_publics_jamais_d_exception(entree):
    for decodeur in (reflection_contract.decode_situation, reflection_contract.decode_prompt,
                     reflection_contract.decode_reflect):
        assert issue(decodeur, entree)[0] == "valeur"


def test_invalide_logge_avec_le_topic(caplog):
    with caplog.at_level(logging.ERROR):
        assert reflection_contract.decode_prompt("pas du json") is None
    assert [r.getMessage() for r in caplog.records] == [
        "payload invalide sur 'chat_prompt' (JSON attendu, ex. '\"nom\"' avec guillemets) : 'pas du json'"]


def _fonction(chemin, nom):
    arbre = ast.parse(open(os.path.join(RACINE, chemin), encoding="utf-8").read())
    trouvees = [n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef) and n.name == nom]
    assert len(trouvees) == 1
    return trouvees[0]


def test_chat_node_goto_result_passe_par_loads():
    f = _fonction("vision/nodes/chat_node.py", "_on_goto_result")
    appels = [ast.unparse(n) for n in ast.walk(f) if isinstance(n, ast.Call)]
    assert "stringtime.loads(ros_msg.msg)" in appels
    assert not [a for a in appels if a.startswith("json.loads(")]
    gestionnaires = [ast.unparse(h.type) for h in ast.walk(f) if isinstance(h, ast.ExceptHandler)]
    assert gestionnaires == ["(ValueError, TypeError)"]


def test_reflection_contract_passe_par_le_strict():
    appels = [ast.unparse(n) for n in ast.walk(_fonction("vision/ai/reflection_contract.py", "_load_object"))
              if isinstance(n, ast.Call)]
    assert "stringtime.decode_payload(raw, topic)" in appels
    assert not [a for a in appels if a.startswith("json.loads(")]
