"""Tests du chargement de la configuration (vision/vision_config.py).

Aucun appel réseau, aucune dépendance au conf/secret réel de la machine : on
pointe explicitement vers des chemins de test (tmp_path, conf/secret.example)
pour que le résultat soit le même en local et en CI (où conf/secret n'existe
pas, puisque gitignoré).
"""
import os
import subprocess
import sys
from pathlib import Path

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


# --- Mouvement à la voix (CHAT_MOUVEMENT, lot I1, 22/10) -----------------------

@pytest.mark.parametrize("env", [{}, {"CHAT_MOUVEMENT": ""}, {"CHAT_MOUVEMENT": "   "}])
def test_mouvement_absent_ou_vide_desactive(env):
    # Le Pi ne pose pas la variable : aucun bloc de prompt, aucun publisher.
    assert vision_config.move_enabled_from_env(env) is False


@pytest.mark.parametrize("raw", ["true", "1", " Oui ", "ON", "True"])
def test_mouvement_valeurs_admises(raw):
    assert vision_config.move_enabled_from_env({"CHAT_MOUVEMENT": raw}) is True


@pytest.mark.parametrize("raw", ["false", " 0 ", "Off", "non"])
def test_mouvement_coupe_explicitement(raw):
    # CHAT_MOUVEMENT=false doit COUPER le mouvement sur le banc (22/10 : la
    # 1re version refusait le démarrage — couper obligeait à éditer le compose).
    assert vision_config.move_enabled_from_env({"CHAT_MOUVEMENT": raw}) is False


@pytest.mark.parametrize("raw", ["peut-être", "yes", "vrai", "2"])
def test_mouvement_toute_autre_valeur_refusee_au_demarrage(raw):
    # Une faute de frappe ne doit jamais couper (ou allumer) le mouvement en
    # silence : refus explicite au démarrage.
    with pytest.raises(ValueError, match="CHAT_MOUVEMENT"):
        vision_config.move_enabled_from_env({"CHAT_MOUVEMENT": raw})


# --- Modèle whisper surchargeable au banc (CHAT_WHISPER_MODEL, 22/10) ---------

def test_whisper_defaut_base_pour_le_pi():
    assert vision_config.whisper_model_from_env({}) == "base"


def test_whisper_small_au_banc():
    assert vision_config.whisper_model_from_env({"CHAT_WHISPER_MODEL": " Small "}) == "small"


@pytest.mark.parametrize("raw", ["large-v3", "petit", "smal"])
def test_whisper_modele_inconnu_refuse(raw):
    with pytest.raises(ValueError, match="CHAT_WHISPER_MODEL"):
        vision_config.whisper_model_from_env({"CHAT_WHISPER_MODEL": raw})


# --- Revue adversariale I1 (22/10) : env lu au démarrage du chat, jamais à l'import

_ENV_INVALIDES = {"CHAT_VAD_FACTOR": "abc", "CHAT_WHISPER_MODEL": "géant",
                  "CHAT_MOUVEMENT": "peut-être", "CHAT_PARTENAIRE": "David"}


def test_import_de_la_config_ne_leve_jamais_sur_un_env_invalide():
    # L'import tuait TOUS les nodes vision (person_tracker compris) : il doit
    # réussir et garder les défauts du ROBOT, quoi que contienne l'env.
    racine = Path(vision_config.__file__).resolve().parents[1]
    code = ("import vision.vision_config as v; c = v.config; "
            "print(c['chat_vad'].threshold_factor, c['chat_whisper_model'], "
            "c['chat_partner'], c['chat_move_enabled'])")
    sortie = subprocess.run([sys.executable, "-c", code], cwd=racine, capture_output=True, text=True,
                            env=dict(os.environ, **_ENV_INVALIDES))
    assert sortie.returncode == 0, sortie.stderr
    assert sortie.stdout.strip() == "1.3 base None False"


@pytest.mark.parametrize("var,valeur", [("CHAT_VAD_FACTOR", "abc"), ("CHAT_WHISPER_MODEL", "géant"),
                                        ("CHAT_MOUVEMENT", "peut-être")])
def test_surcharges_invalides_levent_au_demarrage_avec_le_nom(var, valeur):
    with pytest.raises(ValueError, match=var):
        vision_config.chat_env_overrides({var: valeur, "ROS_DOMAIN_ID": "43"})


def test_message_mouvement_liste_les_valeurs_vraies_et_fausses():
    with pytest.raises(ValueError) as exc:
        vision_config.move_enabled_from_env({"CHAT_MOUVEMENT": "peut-être"})
    assert "1/true/on/oui" in str(exc.value) and "0/false/off/non" in str(exc.value)


def test_surcharges_du_banc_appliquees():
    overrides, warnings = vision_config.chat_env_overrides({
        "CHAT_VAD_FACTOR": "6", "CHAT_WHISPER_MODEL": "small", "CHAT_PARTENAIRE": " David ",
        "CHAT_MOUVEMENT": "true", "ROS_DOMAIN_ID": "43"})
    assert overrides["chat_vad"].threshold_factor == 6.0
    assert (overrides["chat_whisper_model"], overrides["chat_partner"],
            overrides["chat_move_enabled"]) == ("small", "David", True)
    assert warnings == []


def test_sans_env_les_defauts_du_robot():
    overrides, warnings = vision_config.chat_env_overrides({})
    assert overrides["chat_vad"].threshold_factor == 1.3
    assert (overrides["chat_whisper_model"], overrides["chat_partner"],
            overrides["chat_move_enabled"]) == ("base", None, False)
    assert warnings == []                        # mouvement non demandé : rien à dire


@pytest.mark.parametrize("domaine", [None, "42", "0", " 43x", ""])
def test_mouvement_force_a_false_hors_du_domaine_43(domaine):
    env = {"CHAT_MOUVEMENT": "true"}
    if domaine is not None:
        env["ROS_DOMAIN_ID"] = domaine
    overrides, warnings = vision_config.chat_env_overrides(env)
    assert overrides["chat_move_enabled"] is False
    assert len(warnings) == 1
    assert "CHAT_MOUVEMENT IGNORÉ" in warnings[0] and "domaine 43" in warnings[0]


def test_mouvement_actif_en_domaine_43_espaces_toleres():
    overrides, _ = vision_config.chat_env_overrides({"CHAT_MOUVEMENT": "oui", "ROS_DOMAIN_ID": " 43 "})
    assert overrides["chat_move_enabled"] is True


# --- CHAT_REFLEXION (metteur en scène intérieur, 23/10/2026) ---------------

def test_reflexion_absente_ou_fausse_vaut_false():
    from vision.vision_config import reflection_enabled_from_env
    assert reflection_enabled_from_env({}) is False
    assert reflection_enabled_from_env({"CHAT_REFLEXION": " Non "}) is False


def test_reflexion_vraie_sans_garde_de_domaine():
    # Pas de garde ROS_DOMAIN_ID : la réflexion ne commande pas le corps.
    from vision.vision_config import chat_env_overrides
    overrides, warnings = chat_env_overrides({"CHAT_REFLEXION": "1", "ROS_DOMAIN_ID": "42"})
    assert overrides["chat_reflection_enabled"] is True
    assert warnings == []


def test_reflexion_invalide_leve():
    import pytest
    from vision.vision_config import reflection_enabled_from_env
    with pytest.raises(ValueError):
        reflection_enabled_from_env({"CHAT_REFLEXION": "peut-être"})


def test_config_reflexion_valeurs_gravees():
    from vision.vision_config import config
    assert config["chat_reflection_enabled"] is False
    assert config["reflection_model"] == "anthropic/claude-haiku-5.5"
    assert config["reflection_deep_model"] == "anthropic/claude-sonnet-5.5"
    assert config["reflection_extra_body"] == {"reasoning": {"effort": "medium"}}
    assert config["reflection_max_tokens"] == 3000
    assert config["reflection_use_image"] is True


def test_camera_is_partner_sim_et_partenaire():
    assert vision_config.camera_is_partner_from_env({"ROS_DOMAIN_ID": "43"}, "David") is True


def test_camera_is_partner_faux_hors_simulation():
    assert vision_config.camera_is_partner_from_env({"ROS_DOMAIN_ID": "42"}, "David") is False
    assert vision_config.camera_is_partner_from_env({}, "David") is False


def test_camera_is_partner_faux_sans_partenaire():
    for partner in ("", "  ", None):
        assert vision_config.camera_is_partner_from_env({"ROS_DOMAIN_ID": "43"}, partner) is False


# --- CHAT_LLM_MODEL (essai Sonnet pour la bouche, 31/10) ---

def test_llm_model_absent_garde_la_config():
    assert vision_config.llm_model_from_env({}) is None
    assert vision_config.llm_model_from_env({"CHAT_LLM_MODEL": "  "}) is None
    assert "chat_llm_model" not in vision_config.chat_env_overrides({})[0]


def test_llm_model_sonnet_accepte_et_fusionne():
    env = {"CHAT_LLM_MODEL": " Anthropic/Claude-Sonnet-5.5 "}
    assert vision_config.llm_model_from_env(env) == "anthropic/claude-sonnet-5.5"
    overrides = vision_config.chat_env_overrides(env)[0]
    assert overrides["chat_llm_model"] == "anthropic/claude-sonnet-5.5"
    # Sonnet 5.5 refuse {"enabled": False} (400, Didier muet) : effort minimal.
    assert overrides["chat_llm_extra_body"] == {"reasoning": {"effort": "minimal"}}
    assert overrides["chat_llm_max_tokens"] == 600


def test_llm_model_haiku_garde_la_reflexion_coupee():
    overrides = vision_config.chat_env_overrides({"CHAT_LLM_MODEL": "anthropic/claude-haiku-5.5"})[0]
    assert "chat_llm_extra_body" not in overrides
    assert "chat_llm_max_tokens" not in overrides


def test_llm_model_inconnu_refuse():
    import pytest
    with pytest.raises(ValueError):
        vision_config.llm_model_from_env({"CHAT_LLM_MODEL": "openai/gpt-5"})
