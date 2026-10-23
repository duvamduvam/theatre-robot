"""Tests de vision/ai/stage.py (lot R3 « Chantiers », 2026-10-14) — état de
régie du chat, PUR (sans ROS). Spec fermée : dadou_robot_ros/docs/
etude-repetition-simulee.md §13.4 point 3 et §13.6.

Valeurs GRAVÉES partout (règle du parc : un test qui recalcule l'attendu avec
la fonction testée ne teste rien) — bornes à la seconde près, tirages seedés
écrits en clair. Ce sont ces tests qui doivent rougir si un garde-fou
(plafond 60 s, péremption 120 s, phantom ponctuel) est retiré.
"""
import random

import pytest

from vision.ai import stage
from vision.ai.stage import StageState, encode_transcript, garble_text

T0 = 1000.0  # instant de référence (horloge monotone simulée)


# ---------------------------------------------------------------------------
# Constantes du contrat (gravées : elles sont partagées avec le régisseur)
# ---------------------------------------------------------------------------

def test_constantes_du_contrat():
    assert stage.INSTRUCTION_TTL_S == 120.0
    assert stage.FAULT_MAX_S == 60.0
    assert stage.FAULT_OPS == ("pass", "delay", "garble", "deaf", "mute", "phantom")
    assert len(stage.GARBLE_TEXTS) == 8


# ---------------------------------------------------------------------------
# File des textes tapés
# ---------------------------------------------------------------------------

def test_file_des_textes_fifo_et_rognee():
    s = StageState()
    assert s.pop_text() is None
    assert s.has_text() is False
    s.push_text("  bonjour Didier ")
    s.push_text("tu m'entends ?")
    assert s.has_text() is True
    assert s.pop_text() == "bonjour Didier"
    assert s.pop_text() == "tu m'entends ?"
    assert s.pop_text() is None


@pytest.mark.parametrize("text", ["", "   ", None])
def test_texte_vide_refuse(text):
    s = StageState()
    with pytest.raises(ValueError):
        s.push_text(text)
    assert s.has_text() is False


# ---------------------------------------------------------------------------
# Consigne : levée par "", péremption locale 120 s
# ---------------------------------------------------------------------------

def test_consigne_posee_puis_levee():
    s = StageState()
    assert s.instruction(T0) is None
    s.set_instruction("Tu es amoureux du lampadaire.", T0)
    assert s.instruction(T0 + 1.0) == "Tu es amoureux du lampadaire."
    s.set_instruction("", T0 + 2.0)
    assert s.instruction(T0 + 3.0) is None


def test_consigne_perimee_a_120_s():
    s = StageState()
    s.set_instruction("Tu boudes.", T0)
    assert s.instruction(T0 + 119.9) == "Tu boudes."
    assert s.instruction(T0 + 120.0) is None
    # Oubliée pour de bon (pas seulement masquée) : même en « revenant en
    # arrière », elle ne réapparaît pas.
    assert s.instruction(T0 + 10.0) is None


def test_nouvelle_consigne_rearme_la_peremption():
    s = StageState()
    s.set_instruction("Tu boudes.", T0)
    s.set_instruction("Tu es pressé.", T0 + 100.0)
    assert s.instruction(T0 + 219.9) == "Tu es pressé."
    assert s.instruction(T0 + 220.0) is None


# ---------------------------------------------------------------------------
# Panne : durée = until_ms (DURÉE relative), plafond local 60 s
# ---------------------------------------------------------------------------

def test_panne_par_defaut_pass():
    assert StageState().fault(T0) == ("pass", {})


def test_panne_retombe_seule_a_l_echeance():
    s = StageState()
    s.set_fault("deaf", {}, 20000, T0)
    assert s.fault(T0 + 19.9) == ("deaf", {})
    assert s.fault(T0 + 20.0) == ("pass", {})


@pytest.mark.parametrize("until_ms", [
    3_600_000,      # une heure : plafonnée
    60_001,         # juste au-dessus du plafond
    None,           # sans échéance = le plafond
    0,              # absurde
    -5,             # absurde
    "20000",        # pas un nombre
    True,           # booléen (isinstance(True, int) est vrai en Python)
    float("nan"),
    float("inf"),
])
def test_panne_plafonnee_a_60_s(until_ms):
    s = StageState()
    s.set_fault("mute", {}, until_ms, T0)
    assert s.fault(T0 + 59.9) == ("mute", {})
    assert s.fault(T0 + 60.0) == ("pass", {})


def test_panne_pass_desarme_tout_de_suite():
    s = StageState()
    s.set_fault("garble", {}, 30000, T0)
    s.set_fault("pass", {}, None, T0 + 1.0)
    assert s.fault(T0 + 1.0) == ("pass", {})


def test_panne_params_normalises_et_copies():
    s = StageState()
    s.set_fault("delay", {"delay_ms": 6000, "inconnu": 1}, 40000, T0)
    op, params = s.fault(T0)
    assert (op, params) == ("delay", {"delay_ms": 6000})
    params["delay_ms"] = 1  # l'appelant ne touche jamais l'état interne
    assert s.fault(T0) == ("delay", {"delay_ms": 6000})


def test_garble_texts_gardes_rognes():
    s = StageState()
    s.set_fault("garble", {"texts": [" Tu as dit banane ? "]}, 30000, T0)
    assert s.fault(T0) == ("garble", {"texts": ["Tu as dit banane ?"]})


# ---------------------------------------------------------------------------
# phantom : PONCTUEL — texte enfilé, jamais armé comme régime
# ---------------------------------------------------------------------------

def test_phantom_est_ponctuel():
    s = StageState()
    s.set_fault("phantom", {"text": "Sous-titres réalisés par la communauté d'Amara.org"},
                5000, T0)
    assert s.fault(T0) == ("pass", {})
    assert s.pop_text() == "Sous-titres réalisés par la communauté d'Amara.org"
    assert s.pop_text() is None


def test_phantom_ne_touche_pas_la_panne_en_cours():
    # Un fantôme est un événement, pas un régime (cf. docstring de set_fault).
    s = StageState()
    s.set_fault("deaf", {}, 20000, T0)
    s.set_fault("phantom", {"text": "klaxon"}, None, T0 + 1.0)
    assert s.fault(T0 + 2.0) == ("deaf", {})
    assert s.pop_text() == "klaxon"


# ---------------------------------------------------------------------------
# Refus : params invalides -> ValueError, état INCHANGÉ
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("op,params", [
    ("explose", {}),                          # op inconnue
    ("delay", {}),                            # delay_ms manquant
    ("delay", {"delay_ms": 0}),
    ("delay", {"delay_ms": True}),
    ("delay", {"delay_ms": "6000"}),
    ("delay", {"delay_ms": 60_001}),          # au-delà du plafond de la panne
    ("garble", {"texts": "Astérix"}),         # pas une liste
    ("garble", {"texts": []}),
    ("garble", {"texts": ["ok", ""]}),
    ("garble", {"texts": ["ok", 3]}),
    ("phantom", {}),
    ("phantom", {"text": "   "}),
    ("phantom", {"text": 42}),
    ("deaf", ["pas", "un", "objet"]),
])
def test_params_invalides_refuses_sans_toucher_l_etat(op, params):
    s = StageState()
    s.set_fault("mute", {}, 30000, T0)
    with pytest.raises(ValueError):
        s.set_fault(op, params, 10000, T0 + 1.0)
    assert s.fault(T0 + 2.0) == ("mute", {})
    assert s.pop_text() is None


def test_delay_bornes_acceptees():
    s = StageState()
    s.set_fault("delay", {"delay_ms": 1}, 1000, T0)
    assert s.fault(T0) == ("delay", {"delay_ms": 1})
    s.set_fault("delay", {"delay_ms": 60000}, 1000, T0)
    assert s.fault(T0) == ("delay", {"delay_ms": 60000})


# ---------------------------------------------------------------------------
# Contresens : tirage déterministe (rng injecté), valeurs gravées
# ---------------------------------------------------------------------------

def test_garble_text_deterministe_avec_graine():
    rng = random.Random(42)
    assert [garble_text(rng) for _ in range(3)] == [
        "Sous-titres réalisés par la communauté d'Amara.org",
        "Il parle d'Astérix ?",
        "C'est combien le kilo de boulons ?",
    ]


def test_garble_text_tire_dans_params_texts():
    rng = random.Random(7)
    assert garble_text(rng, ["Tu as dit banane ?", "Tu as dit cabane ?"]) == "Tu as dit cabane ?"


def test_garble_texts_non_vides_et_distincts():
    assert all(text.strip() for text in stage.GARBLE_TEXTS)
    assert len(set(stage.GARBLE_TEXTS)) == 8


# ---------------------------------------------------------------------------
# Transcript : payload gravé (contrat avec la page « scène » côté robot)
# ---------------------------------------------------------------------------

def test_encode_transcript_payload_grave():
    assert encode_transcript("didier", "C'est prévu.", 1760436000123) == (
        '{"role": "didier", "text": "C\'est prévu.", "t_ms": 1760436000123}')


# ---------------------------------------------------------------------------
# Metteur en scène intérieur (lot P, 2026-10-23, dadou_robot_ros/docs/
# spec-metteur-en-scene.md) : tableau de situation (TTL 5 s, constante du
# contrat partagé) et emplacement UNIQUE du tour spontané (TTL 8 s).
# ---------------------------------------------------------------------------

def test_constantes_du_metteur_en_scene():
    assert stage.PROMPT_TTL_S == 8.0
    assert stage.SITUATION_TTL_S == 5.0   # importée du contrat, pas recopiée


def test_situation_absente_par_defaut():
    assert StageState().situation(T0) is None


def test_situation_presente_a_4_9_s_absente_a_5_1_s():
    state = StageState()
    state.set_situation("  David à ta gauche.  ", T0)
    assert state.situation(T0 + 4.9) == "David à ta gauche."
    assert state.situation(T0 + 5.1) is None


def test_situation_vide_retire_le_tableau():
    state = StageState()
    state.set_situation("Personne en vue.", T0)
    state.set_situation("", T0 + 1)
    assert state.situation(T0 + 1) is None


def test_nouvelle_situation_rearme_la_peremption():
    state = StageState()
    state.set_situation("ancienne", T0)
    state.set_situation("neuve", T0 + 4)
    assert state.situation(T0 + 8) == "neuve"
    assert state.situation(T0 + 9.1) is None


def test_prompt_absent_par_defaut():
    assert StageState().pop_prompt(T0) is None


def test_prompt_consomme_une_seule_fois():
    state = StageState()
    state.push_prompt("Demande à la dame en rouge.", T0)
    assert state.pop_prompt(T0 + 1) == "Demande à la dame en rouge."
    assert state.pop_prompt(T0 + 1) is None


def test_prompt_present_a_7_9_s_perime_a_8_1_s():
    state = StageState()
    state.push_prompt("Relance.", T0)
    assert state.pop_prompt(T0 + 7.9) == "Relance."
    state.push_prompt("Relance.", T0)
    assert state.pop_prompt(T0 + 8.1) is None
    # Périmée = jetée pour de bon, pas gardée pour plus tard.
    assert state.pop_prompt(T0 + 8.1) is None


def test_prompt_emplacement_unique_le_plus_recent_remplace():
    state = StageState()
    state.push_prompt("vieille direction", T0)
    state.push_prompt("direction neuve", T0 + 2)
    assert state.pop_prompt(T0 + 9) == "direction neuve"   # 7 s après la NEUVE
    assert state.pop_prompt(T0 + 9) is None


@pytest.mark.parametrize("direction", ["", "   ", None])
def test_prompt_vide_refuse(direction):
    state = StageState()
    with pytest.raises(ValueError):
        state.push_prompt(direction, T0)
    assert state.pop_prompt(T0) is None
