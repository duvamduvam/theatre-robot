"""Tests du contrat parole ↔ réflexion (didier_vision/ai/reflection_contract.py).
Valeurs GRAVÉES : un nom de topic ou une constante changés d'un seul côté
casseraient le lien entre les deux nodes sans erreur visible."""
from didier_vision.ai import reflection_contract as rc


def test_noms_de_topics_graves():
    assert rc.SITUATION_TOPIC == "chat_situation"
    assert rc.PROMPT_TOPIC == "chat_prompt"
    assert rc.REFLECT_TOPIC == "chat_reflect"
    assert rc.MISSION_STATE_TOPIC == "mission_state"


def test_peremption_plus_longue_que_la_republication():
    # Le tableau doit survivre entre deux republications, mais pas plus de
    # quelques secondes à la mort de la réflexion.
    assert rc.SITUATION_REPUBLISH_S == 1.0
    assert rc.SITUATION_TTL_S == 5.0


def test_situation_aller_retour():
    raw = rc.encode_situation("David à ta gauche.", 1234)
    assert raw == '{"text": "David à ta gauche.", "t_ms": 1234}'
    assert rc.decode_situation(raw) == "David à ta gauche."


def test_situation_vide_est_valide():
    assert rc.decode_situation('{"text": "", "t_ms": 0}') == ""


def test_situation_tronquee_au_plafond():
    raw = rc.encode_situation("x" * 2000, 0)
    assert len(rc.decode_situation(raw)) == 700


def test_situation_invalide_rend_none():
    assert rc.decode_situation("pas du json") is None
    assert rc.decode_situation('"une chaîne"') is None
    assert rc.decode_situation('{"t_ms": 3}') is None
    assert rc.decode_situation(None) is None


def test_prompt_aller_retour_et_vide():
    raw = rc.encode_prompt("Demande à la dame en rouge.", "personne ne parle")
    assert rc.decode_prompt(raw) == "Demande à la dame en rouge."
    assert rc.decode_prompt('{"direction": "   "}') is None
    assert rc.decode_prompt('{"raison": "x"}') is None
    assert rc.decode_prompt("[]") is None


def test_reflect_aller_retour_et_invalide():
    raw = rc.encode_reflect("Que tient l'enfant dans la main ?")
    assert rc.decode_reflect(raw) == "Que tient l'enfant dans la main ?"
    assert rc.decode_reflect('{"demande": 42}') is None
    assert rc.decode_reflect("{") is None
