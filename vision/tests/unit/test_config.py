"""Tests du chargement de la configuration (vision/vision_config.py).

Aucun appel réseau, aucune dépendance au conf/secret réel de la machine : on
pointe explicitement vers des chemins de test (tmp_path, conf/secret.example)
pour que le résultat soit le même en local et en CI (où conf/secret n'existe
pas, puisque gitignoré).
"""
import os

import pytest

from vision import vision_config

SECRET_EXAMPLE = os.path.join(vision_config.REPO_ROOT, "conf", "secret.example")


def test_load_secrets_missing_file_raises_clear_error(tmp_path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError, match="conf/secret.example"):
        vision_config.load_secrets(str(missing))


def test_load_secrets_parses_example_file():
    secrets = vision_config.load_secrets(SECRET_EXAMPLE)
    assert "chatgpt_key" in secrets
    assert secrets["chatgpt_key"]  # valeur factice non vide


def test_load_secrets_ignores_comments_and_blank_lines(tmp_path):
    secret_file = tmp_path / "secret"
    secret_file.write_text("# commentaire\n\nchatgpt_key=une-cle-de-test\n")

    secrets = vision_config.load_secrets(str(secret_file))

    assert secrets == {"chatgpt_key": "une-cle-de-test"}


def test_get_secret_missing_key_raises_key_error(tmp_path, monkeypatch):
    secret_file = tmp_path / "secret"
    secret_file.write_text("chatgpt_key=une-cle-de-test\n")
    monkeypatch.setattr(vision_config, "SECRET_FILE", str(secret_file))

    assert vision_config.get_secret("chatgpt_key") == "une-cle-de-test"
    with pytest.raises(KeyError):
        vision_config.get_secret("inexistant")


def test_default_config_has_no_hardcoded_secret():
    # Le dict `config` ne doit contenir que des valeurs par défaut publiques.
    assert "chatgpt_key" not in vision_config.config
    assert vision_config.config["gpt_model"] == "gpt-4o"
    assert vision_config.config["gpt_voice"] == "alloy"


# --- Facteur VAD surchargeable au banc (CHAT_VAD_FACTOR, 22/10) ---------------

def test_vad_sans_variable_garde_le_defaut_valide_du_robot():
    # Valeur gravée : 1.3 = défaut validé sur le proto (VadConfig) — le Pi ne
    # pose pas la variable, il doit retomber EXACTEMENT dessus.
    assert vision_config.vad_config_from_env({}).threshold_factor == 1.3


def test_vad_variable_posee_remplace_le_facteur_seulement():
    vad = vision_config.vad_config_from_env({"CHAT_VAD_FACTOR": " 3.5 "})
    assert vad.threshold_factor == 3.5
    assert vad.end_silence_ms == 600  # le reste n'est pas touché


@pytest.mark.parametrize("raw", ["abc", "1", "0.8", "-2"])
def test_vad_variable_invalide_ou_trop_basse_refusee(raw):
    with pytest.raises(ValueError, match="CHAT_VAD_FACTOR"):
        vision_config.vad_config_from_env({"CHAT_VAD_FACTOR": raw})


def test_partenaire_absent_ou_vide_donne_none():
    assert vision_config.partner_from_env({}) is None
    assert vision_config.partner_from_env({"CHAT_PARTENAIRE": "  "}) is None


def test_partenaire_pose_est_nettoye():
    assert vision_config.partner_from_env({"CHAT_PARTENAIRE": " David "}) == "David"
