"""Tests du protocole pur du pont web W0 (didier_web.web_protocol).

Couvre : whitelist (garantie de sécurité W0 -- pas de roues/e_stop), parsing
des 5 types de message client, auth/écriture exclusive/heartbeat de
SessionManager (horloge injectée, jamais time.time() réel), le contenu exact
de stop_all_commands() et les constructeurs de messages serveur. Depuis la page
« scène » : whitelist de répétition SIM-ONLY (effective_whitelist), flux "feed",
contrat des pages statiques avec le protocole, et le pont lui-même (file de
flux entre le thread rclpy et la boucle asyncio) avec rclpy simulé.
"""

import ast
import asyncio
import importlib
import json
import pathlib
import re
import sys
import threading
import types

import pytest

from didier_web import web_catalog, web_protocol
from didier_web.web_protocol import (
    DRIVE_TIMEOUT_S, HEARTBEAT_PERIOD_S, TOPICS_FLUX, TOPICS_LECTURE, WHITELIST,
    WHITELIST_REPETITION, WHITELIST_SPECTACLE, WHITELIST_TECHNIQUE,
    WRITE_TIMEOUT_S, DriveFlow, ProtocolError, SessionManager, build_ack,
    build_err, build_feed, build_hb_ack, build_hello, build_state,
    drive_to_twist, effective_whitelist, mode_from_domain_id,
    TOPICS_MASQUES, parse_client_message, rehearsal_allowed, snapshot_visible,
    stop_all_commands,
)

# Racine du package didier_web (static/ est un frère de didier_web/ dans le dépôt).
PACKAGE_WEB = pathlib.Path(web_protocol.__file__).resolve().parent.parent
STATIC = PACKAGE_WEB / "static"

# Topics qui ne doivent JAMAIS pouvoir être publiés par le web, répétition
# activée ou non : les roues, le verrou e_stop, et tout ce qui est en lecture seule.
TOPICS_INTERDITS = ["wheels", "cmd_vel", "cmd_vel_web", "cmd_vel_remote", "cmd_vel_anim",
                    "cmd_vel_mux", "cmd_vel_follow", "e_stop"]


def imported_roots(module):
    """Racines des paquets réellement importés par un module (via son AST).
    Même motif que test_wheels_payload.py : didier_web doit rester un paquet
    autonome, importable dans le conteneur sim sans rclpy ni dadou_utils_ros."""
    tree = ast.parse(pathlib.Path(module.__file__).read_text())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


# --- Autonomie (garde-fou AST) ----------------------------------------------

def test_web_protocol_reste_autonome():
    roots = imported_roots(web_protocol)
    assert roots.isdisjoint(("rclpy", "aiohttp", "dadou_utils_ros", "robot")), roots


def test_web_catalog_reste_autonome():
    roots = imported_roots(web_catalog)
    assert roots.isdisjoint(("rclpy", "aiohttp", "dadou_utils_ros", "robot")), roots


# --- Whitelist : contrat de sécurité W0 -------------------------------------

def test_whitelist_n_expose_jamais_les_roues_ni_e_stop():
    """W0 = supervision + contenus + panneau technique. AUCUN accès roues ni
    verrou e_stop -- vérifié explicitement, pas juste "absent par hasard"."""
    interdits = {"wheels", "cmd_vel", "cmd_vel_web", "cmd_vel_remote", "cmd_vel_anim",
                 "cmd_vel_mux", "e_stop"}
    assert interdits.isdisjoint(WHITELIST)


def test_whitelist_est_l_union_spectacle_technique():
    # "chat" (2026-07-12) : toggle on/off de la parole IA (chat_node, Pi
    # vision) -- topic de commande comme "gaze", pas un actionneur.
    # "persona" (2026-07-13, lot D3) : sélection de la personnalité de Didier
    # (payload = nom de variante, cf. vision.ai.personas) -- même nature que
    # "chat", une commande de configuration, pas un actionneur.
    # "chat_text" / "chat_instruction" (2026-10-14, page « scène ») : la régie
    # souffle un texte « entendu » ou pose une consigne de jeu -- conversation,
    # pas un actionneur.
    assert WHITELIST == WHITELIST_SPECTACLE | WHITELIST_TECHNIQUE
    assert WHITELIST_SPECTACLE == {"animation", "face", "audio", "robot_lights"}
    assert WHITELIST_TECHNIQUE == {"relay", "neck", "left_eye", "right_eye", "left_arm",
                                    "right_arm", "gaze", "chat", "persona", "system",
                                    "chat_text", "chat_instruction"}


def test_topics_lecture_jamais_publiables():
    # Les topics d'ÉTAT observés par le pont (surbrillance des options
    # actives, 2026-07-13) ne doivent JAMAIS entrer dans la whitelist de
    # publication : un client web ne peut pas forger l'état du chat.
    # rehearsal/state (31/10) : séance + arrêt vocal du régisseur ; camera_state
    # (31/10) : état réel de la webcam de perception.
    # camera_source_state / camera_sources (31/10) : source d'images réelle de la
    # perception et liste des sources disponibles, latchées côté vision.
    # jeu/intention, rehearsal/objects (02/11, lot A1) : panneau « Jeu » de la page scène.
    # deploy_sha (04/11, lot L1c) : badge version ; `catalogue` n'y entre PAS.
    assert TOPICS_LECTURE == {"chat_state", "persona_state", "route_state", "chat_audio_chain",
                              "rehearsal/state", "camera_state", "camera_source_state",
                              "camera_sources", "jeu/intention", "rehearsal/objects",
                              "deploy_sha"}
    assert TOPICS_LECTURE.isdisjoint(WHITELIST)
    assert TOPICS_LECTURE.isdisjoint(WHITELIST_REPETITION)


# --- Parsing des messages client --------------------------------------------

def test_parse_auth_token_present():
    assert parse_client_message('{"type":"auth","token":"secret"}') == {
        "type": "auth", "token": "secret"}


def test_parse_auth_token_null():
    assert parse_client_message('{"type":"auth","token":null}') == {
        "type": "auth", "token": None}


def test_parse_auth_token_invalide_leve():
    with pytest.raises(ProtocolError):
        parse_client_message('{"type":"auth","token":42}')


def test_parse_hb():
    assert parse_client_message('{"type":"hb","t":1234}') == {"type": "hb", "t": 1234}


def test_parse_hb_sans_t_leve():
    with pytest.raises(ProtocolError):
        parse_client_message('{"type":"hb"}')


def test_parse_hb_t_booleen_refuse():
    """bool est une sous-classe d'int en Python : un horodatage True/False
    n'a pas de sens, on doit le rejeter explicitement (pas de faux positif)."""
    with pytest.raises(ProtocolError):
        parse_client_message('{"type":"hb","t":true}')


def test_parse_cmd_valide():
    assert parse_client_message('{"type":"cmd","topic":"face","value":"joie","time":500}') == {
        "type": "cmd", "topic": "face", "value": "joie", "time": 500}


def test_parse_cmd_time_defaut_zero():
    assert parse_client_message('{"type":"cmd","topic":"face","value":"joie"}')["time"] == 0


def test_parse_cmd_value_quelconque():
    """value est du JSON quelconque : objet, booléen, null, nombre..."""
    assert parse_client_message('{"type":"cmd","topic":"robot_lights","value":{"brightness":0.2}}'
                                 )["value"] == {"brightness": 0.2}
    assert parse_client_message('{"type":"cmd","topic":"animation","value":false}')["value"] is False


@pytest.mark.parametrize("time_ms", [-1, 2 ** 63])
def test_parse_cmd_time_hors_bornes_leve(time_ms):
    """StringTime.time est un int64 : hors bornes, rclpy lèverait à
    l'affectation dans le node et tuerait la connexion du client au lieu d'un
    refus propre. Négatif refusé aussi (time = durée ms, jamais négative)."""
    with pytest.raises(ProtocolError):
        parse_client_message(
            '{{"type":"cmd","topic":"face","value":"joie","time":{}}}'.format(time_ms))


def test_parse_cmd_sans_value_leve():
    with pytest.raises(ProtocolError):
        parse_client_message('{"type":"cmd","topic":"face"}')


def test_parse_cmd_topic_hors_whitelist_leve():
    with pytest.raises(ProtocolError):
        parse_client_message('{"type":"cmd","topic":"inconnu","value":1}')


@pytest.mark.parametrize("topic", ["wheels", "cmd_vel_web", "cmd_vel", "e_stop",
                                    "cmd_vel_remote", "cmd_vel_anim"])
def test_parse_cmd_roues_et_e_stop_toujours_refuses(topic):
    """Vérification EXPLICITE demandée par la spec : ces topics ne doivent
    jamais être acceptés par le pont web W0, quelle que soit la valeur envoyée."""
    with pytest.raises(ProtocolError):
        parse_client_message('{{"type":"cmd","topic":"{}","value":[0.5,0.5]}}'.format(topic))


def test_parse_take_control():
    assert parse_client_message('{"type":"take_control"}') == {"type": "take_control"}


def test_parse_stop_all():
    assert parse_client_message('{"type":"stop_all"}') == {"type": "stop_all"}


def test_parse_json_casse_leve():
    with pytest.raises(ProtocolError):
        parse_client_message('{"type": "cmd", ')


def test_parse_non_objet_leve():
    with pytest.raises(ProtocolError):
        parse_client_message('[1, 2, 3]')


def test_parse_type_manquant_leve():
    with pytest.raises(ProtocolError):
        parse_client_message('{"topic":"face","value":"joie"}')


def test_parse_type_inconnu_leve():
    with pytest.raises(ProtocolError):
        parse_client_message('{"type":"boum"}')


# --- stop_all_commands : liste et ordre exacts ------------------------------

def test_stop_all_commands_liste_et_ordre_exacts():
    assert stop_all_commands() == [
        ("animation", False),
        ("audio", "stop"),
        ("face", "stop"),
        ("neck", "stop"),
        ("left_eye", "stop"),
        ("right_eye", "stop"),
        ("left_arm", "stop"),
        ("right_arm", "stop"),
    ]


def test_stop_all_commands_repetition_coupe_la_route_et_la_seance():
    """SIM-ONLY : avec la répétition activée, STOP ajoute EXACTEMENT, à la fin,
    `route off` puis `rehearsal/cmd stop` (ordre : la route d'abord, la séance
    ensuite). Sans répétition, rien de plus (liste gravée ci-dessus)."""
    base = stop_all_commands()
    assert stop_all_commands(False) == base
    # Lot A1 (revue du 02/11) : le sélecteur de jeu reçoit un stop de David, en premier.
    assert stop_all_commands(True) == base + [("jeu/console", {"cmd": "stop"}), ("route", "off"),
                                              ("rehearsal/cmd", "stop")]
    assert {t for t, _ in stop_all_commands(True)} - {t for t, _ in base} == {"jeu/console", "route",
                                                                               "rehearsal/cmd"}
    assert {"jeu/console", "route", "rehearsal/cmd"} <= WHITELIST_REPETITION


def test_topics_masques_graves_et_filtres_du_state():
    """`chat_instruction` (la lubie en cours) et `route_speed` (batterie faible,
    arrêt devant un objet) ne sortent JAMAIS dans `state` : David ignore le
    tirage. Ils restent publiables (whitelist) -- seul l'écho est coupé."""
    assert TOPICS_MASQUES == frozenset({"chat_instruction", "route_speed"})
    assert "chat_instruction" in WHITELIST_TECHNIQUE
    assert "route_speed" in WHITELIST_REPETITION
    topics = {"chat_state": {"msg": "listening", "at_s": 1.0},
              "chat_instruction": {"msg": "tu es amoureux", "at_s": 1.0},
              "route_speed": {"msg": 0, "at_s": 1.0},
              "route_state": {"msg": "on", "at_s": 1.0}}
    assert snapshot_visible(topics) == {"chat_state": {"msg": "listening", "at_s": 1.0},
                                        "route_state": {"msg": "on", "at_s": 1.0}}
    assert snapshot_visible({}) == {}


def test_stop_all_commands_ne_touche_jamais_aux_roues():
    topics = {topic for topic, _value in stop_all_commands()}
    assert "wheels" not in topics
    assert "e_stop" not in topics


# --- Mode robot / sim --------------------------------------------------------

def test_mode_from_domain_id_simulation():
    assert mode_from_domain_id(43) == "SIMULATION"


def test_mode_from_domain_id_robot_reel():
    assert mode_from_domain_id(42) == "ROBOT RÉEL"


@pytest.mark.parametrize("domain_id", [0, 1, -1, 99])
def test_mode_from_domain_id_inconnu(domain_id):
    assert mode_from_domain_id(domain_id) == "INCONNU"


# --- Constructeurs de messages serveur --------------------------------------

def test_build_hello():
    assert build_hello(43, writer=True, token_required=False,
                       drive_enabled=False, max_linear=0.5, max_angular=1.0) == {
        "type": "hello", "domain_id": 43, "mode": "SIMULATION",
        "writer": True, "token_required": False,
        "drive_enabled": False, "max_linear": 0.5, "max_angular": 1.0,
        "rehearsal": False, "perception": False, "exterior": False}


def test_build_hello_expose_les_plafonds_et_l_etat_pilotage():
    """L'UI verrouille le pad et affiche les limites depuis ces champs :
    drive_enabled=true doit passer tel quel, avec ses plafonds."""
    hello = build_hello(42, writer=False, token_required=True,
                        drive_enabled=True, max_linear=0.3, max_angular=0.8)
    assert hello["drive_enabled"] is True
    assert hello["max_linear"] == 0.3
    assert hello["max_angular"] == 0.8


def test_build_hb_ack_echo_t():
    assert build_hb_ack(999) == {"type": "hb_ack", "t": 999}


def test_build_ack():
    assert build_ack("face") == {"type": "ack", "topic": "face"}


def test_build_err():
    assert build_err("topic hors whitelist") == {"type": "err", "reason": "topic hors whitelist"}


def test_build_state():
    assert build_state(topics={"face": {"msg": "joie", "age_s": 0.4}}, nodes=["lights_node"],
                        clients=2, writer_present=True) == {
        "type": "state",
        "topics": {"face": {"msg": "joie", "age_s": 0.4}},
        "nodes": ["lights_node"],
        "clients": 2,
        "writer_present": True,
    }


# --- SessionManager : auth ---------------------------------------------------

def test_auth_libre_quand_token_serveur_vide():
    sessions = SessionManager(token=None)
    assert sessions.token_required is False
    assert sessions.authenticate("c1", token=None, now_s=0.0) is True
    assert sessions.authenticate("c2", token="n'importe quoi", now_s=0.0) is True


def test_auth_avec_bon_token():
    sessions = SessionManager(token="secret")
    assert sessions.token_required is True
    assert sessions.authenticate("c1", token="secret", now_s=0.0) is True


def test_auth_avec_mauvais_token_rejetee():
    sessions = SessionManager(token="secret")
    assert sessions.authenticate("c1", token="faux", now_s=0.0) is False
    assert sessions.is_writer("c1") is False


# --- SessionManager : écriture exclusive ------------------------------------

def test_premier_client_authentifie_prend_l_ecriture():
    sessions = SessionManager(token=None)
    sessions.authenticate("c1", None, now_s=0.0)
    assert sessions.is_writer("c1") is True
    assert sessions.writer_present() is True


def test_second_client_est_lecteur():
    sessions = SessionManager(token=None)
    sessions.authenticate("c1", None, now_s=0.0)
    sessions.authenticate("c2", None, now_s=0.0)
    assert sessions.is_writer("c1") is True
    assert sessions.is_writer("c2") is False


def test_take_control_reprend_l_ecriture_explicitement():
    sessions = SessionManager(token=None)
    sessions.authenticate("c1", None, now_s=0.0)
    sessions.authenticate("c2", None, now_s=0.0)
    assert sessions.take_control("c2", now_s=1.0) is True
    assert sessions.is_writer("c2") is True
    assert sessions.is_writer("c1") is False


def test_take_control_refuse_si_non_authentifie():
    sessions = SessionManager(token="secret")
    assert sessions.take_control("inconnu", now_s=0.0) is False


def test_deconnexion_du_writer_libere_l_ecriture_sans_reprise_automatique():
    sessions = SessionManager(token=None)
    sessions.authenticate("c1", None, now_s=0.0)
    sessions.authenticate("c2", None, now_s=0.0)
    was_writer = sessions.remove_client("c1")
    assert was_writer is True
    assert sessions.writer_present() is False
    # c2 était lecteur, il ne récupère PAS l'écriture automatiquement.
    assert sessions.is_writer("c2") is False


def test_deconnexion_d_un_lecteur_ne_touche_pas_l_ecriture():
    sessions = SessionManager(token=None)
    sessions.authenticate("c1", None, now_s=0.0)
    sessions.authenticate("c2", None, now_s=0.0)
    was_writer = sessions.remove_client("c2")
    assert was_writer is False
    assert sessions.is_writer("c1") is True


# --- SessionManager : heartbeat / timeout -----------------------------------

def test_heartbeat_rearme_l_horloge_writer():
    sessions = SessionManager(token=None)
    sessions.authenticate("c1", None, now_s=0.0)
    assert sessions.heartbeat("c1", now_s=2.0) is True
    # Juste avant le timeout depuis le dernier battement (2.0 + 2.9 < 2.0 + WRITE_TIMEOUT_S) :
    assert sessions.check_timeouts(now_s=2.0 + WRITE_TIMEOUT_S - 0.1) is None
    assert sessions.is_writer("c1") is True


def test_heartbeat_ignore_pour_un_non_writer():
    sessions = SessionManager(token=None)
    sessions.authenticate("c1", None, now_s=0.0)
    sessions.authenticate("c2", None, now_s=0.0)
    assert sessions.heartbeat("c2", now_s=1.0) is False


def test_timeout_libere_l_ecriture_horloge_avancee_a_la_main():
    """Le coeur du test : aucune horloge réelle, on avance now_s à la main."""
    sessions = SessionManager(token=None)
    sessions.authenticate("c1", None, now_s=0.0)
    assert sessions.is_writer("c1") is True

    # Silence total au-delà de WRITE_TIMEOUT_S depuis l'auth (qui arme l'horloge) :
    released = sessions.check_timeouts(now_s=WRITE_TIMEOUT_S + 0.01)
    assert released == "c1"
    assert sessions.writer_present() is False
    assert sessions.is_writer("c1") is False


def test_timeout_ne_libere_rien_si_pas_de_writer():
    sessions = SessionManager(token=None)
    assert sessions.check_timeouts(now_s=1000.0) is None


def test_constante_heartbeat_period_inferieure_au_timeout():
    """Sanity check du couple de constantes exportées : le client doit battre
    plusieurs fois avant expiration, sinon la moindre latence réseau ferait
    perdre l'écriture en continu."""
    assert HEARTBEAT_PERIOD_S < WRITE_TIMEOUT_S


# --- Pilotage roues : parsing du message drive (SIM-ONLY) -------------------

def test_parse_drive_valide():
    assert parse_client_message('{"type":"drive","x":0.5,"z":-0.3}') == {
        "type": "drive", "x": 0.5, "z": -0.3}


def test_parse_drive_entiers_acceptes():
    # 0/1 entiers sont des nombres finis valides (convertis en float).
    msg = parse_client_message('{"type":"drive","x":1,"z":0}')
    assert msg["x"] == 1.0 and msg["z"] == 0.0


def test_parse_drive_clamp_silencieux():
    """Un joystick qui déborde de [-1, 1] est ramené SANS lever d'erreur (pas de
    spam à 15 Hz sur un dépassement de 1 %)."""
    msg = parse_client_message('{"type":"drive","x":1.4,"z":-2.0}')
    assert msg["x"] == 1.0
    assert msg["z"] == -1.0


@pytest.mark.parametrize("payload", [
    '{"type":"drive","x":true,"z":0}',       # bool exclu (sous-classe d'int)
    '{"type":"drive","x":0,"z":false}',
    '{"type":"drive","x":"0.5","z":0}',      # chaîne refusée
    '{"type":"drive","x":0}',                # z manquant
    '{"type":"drive","z":0}',                # x manquant
    '{"type":"drive","x":null,"z":0}',       # null refusé
])
def test_parse_drive_types_invalides_leves(payload):
    with pytest.raises(ProtocolError):
        parse_client_message(payload)


@pytest.mark.parametrize("valeur", ["NaN", "Infinity", "-Infinity"])
def test_parse_drive_non_fini_refuse(valeur):
    """NaN/inf (que json.loads accepte hélas) : une consigne roues non finie ne
    doit JAMAIS atteindre le calcul de Twist -- refus explicite."""
    with pytest.raises(ProtocolError):
        parse_client_message('{{"type":"drive","x":{},"z":0}}'.format(valeur))


# --- drive_to_twist : plafond de sécurité (clamp backend) -------------------

def test_drive_to_twist_plafonne():
    # Consignes à fond -> pile les plafonds, jamais au-delà.
    lin, ang = drive_to_twist(1.0, 1.0, max_linear=0.5, max_angular=1.0)
    assert lin == 0.5
    assert ang == 1.0


def test_drive_to_twist_signes_conserves():
    lin, ang = drive_to_twist(-1.0, 0.5, max_linear=0.4, max_angular=2.0)
    assert lin == -0.4
    assert ang == 1.0


def test_drive_to_twist_clamp_meme_hors_bornes():
    """C'EST le rempart : même une entrée hors [-1, 1] (navigateur bugué qui
    court-circuite le parsing) ne peut pas dépasser les plafonds."""
    lin, ang = drive_to_twist(5.0, -9.0, max_linear=0.5, max_angular=1.0)
    assert lin == 0.5
    assert ang == -1.0


def test_drive_to_twist_zero_reste_zero():
    assert drive_to_twist(0.0, 0.0, 0.5, 1.0) == (0.0, 0.0)


# --- DriveFlow : zéro publié une seule fois par arrêt -----------------------

def test_driveflow_pas_de_zero_sans_drive():
    flow = DriveFlow()
    assert flow.should_zero(now_s=100.0) is False


def test_driveflow_zero_apres_silence():
    flow = DriveFlow()
    flow.on_drive(now_s=0.0)
    # Toujours dans la fenêtre d'activité : pas de zéro.
    assert flow.should_zero(now_s=DRIVE_TIMEOUT_S) is False
    # Silence dépassé : UN zéro.
    assert flow.should_zero(now_s=DRIVE_TIMEOUT_S + 0.01) is True


def test_driveflow_zero_une_seule_fois():
    """Le coeur du contrat anti-spam : un seul True par arrêt, horloge avancée
    à la main."""
    flow = DriveFlow()
    flow.on_drive(now_s=0.0)
    assert flow.should_zero(now_s=1.0) is True
    # Toujours silence, mais le zéro a déjà été émis : plus rien.
    assert flow.should_zero(now_s=2.0) is False
    assert flow.should_zero(now_s=3.0) is False


def test_driveflow_reprend_apres_nouveau_drive():
    flow = DriveFlow()
    flow.on_drive(now_s=0.0)
    assert flow.should_zero(now_s=1.0) is True
    # Nouvelle salve : un nouveau zéro sera dû après son propre silence.
    flow.on_drive(now_s=2.0)
    assert flow.should_zero(now_s=2.1) is False
    assert flow.should_zero(now_s=2.0 + DRIVE_TIMEOUT_S + 0.01) is True


def test_driveflow_reset_annule_le_zero_pendant():
    """reset() = le zéro a déjà été publié par un autre chemin (déconnexion,
    STOP...) : DriveFlow ne doit pas en émettre un second."""
    flow = DriveFlow()
    flow.on_drive(now_s=0.0)
    flow.reset()
    assert flow.should_zero(now_s=100.0) is False


def test_drive_reste_hors_whitelist_cmd():
    """drive est un canal SÉPARÉ (Twist), pas un cmd : cmd_vel_web n'est jamais
    dans la whitelist, la garantie de sécurité W0 tient toujours."""
    assert "cmd_vel_web" not in WHITELIST
    with pytest.raises(ProtocolError):
        parse_client_message('{"type":"cmd","topic":"cmd_vel_web","value":[1,1]}')


# --- Page « scène » : whitelist de répétition (SIM-ONLY) ---------------------

# Valeurs GRAVÉES en toutes lettres (jamais recalculées depuis les constantes du
# module testé : un test qui recalcule l'attendu avec le code ne teste rien).
WHITELIST_BASE_GRAVEE = {
    "animation", "face", "audio", "robot_lights",
    "relay", "neck", "left_eye", "right_eye", "left_arm", "right_arm", "gaze",
    "chat", "persona", "system", "chat_text", "chat_instruction",
}
TOPICS_REPETITION_GRAVES = {"route", "route_speed", "rehearsal/cmd", "camera_enable",
                            "camera_source", "jeu/console"}


def test_whitelist_repetition_exacte_et_hors_whitelist_de_base():
    assert WHITELIST_REPETITION == TOPICS_REPETITION_GRAVES
    assert WHITELIST_REPETITION.isdisjoint(WHITELIST)


def test_camera_enable_ecrivable_seulement_en_repetition():
    """Bouton « Webcam ON/OFF » (31/10) : jamais écrivable hors répétition simulée
    (donc jamais sur le vrai robot) ; camera_state / rehearsal/state, eux, ne le
    sont dans AUCUN des deux cas (lecture seule)."""
    assert "camera_enable" not in effective_whitelist(False)
    assert "camera_enable" in effective_whitelist(True)
    with pytest.raises(ProtocolError):
        parse_client_message('{"type":"cmd","topic":"camera_enable","value":"off"}',
                             effective_whitelist(False))
    assert parse_client_message('{"type":"cmd","topic":"camera_enable","value":"off"}',
                                effective_whitelist(True))["topic"] == "camera_enable"
    for rehearsal in (False, True):
        for lecture in ("camera_state", "rehearsal/state"):
            with pytest.raises(ProtocolError):
                parse_client_message('{{"type":"cmd","topic":"{}","value":"on"}}'.format(lecture),
                                     effective_whitelist(rehearsal))


def test_camera_source_ecrivable_seulement_en_repetition():
    """Sélecteur de source d'images (31/10) : écrivable UNIQUEMENT en répétition
    simulée ; camera_source_state et camera_sources (états latchés par la vision)
    ne le sont dans AUCUN cas."""
    assert "camera_source" not in effective_whitelist(False)
    assert "camera_source" in effective_whitelist(True)
    with pytest.raises(ProtocolError):
        parse_client_message('{"type":"cmd","topic":"camera_source","value":"gazebo"}',
                             effective_whitelist(False))
    assert parse_client_message('{"type":"cmd","topic":"camera_source","value":"gazebo"}',
                                effective_whitelist(True))["topic"] == "camera_source"
    for rehearsal in (False, True):
        for lecture in ("camera_source_state", "camera_sources"):
            assert lecture not in effective_whitelist(rehearsal)
            with pytest.raises(ProtocolError):
                parse_client_message('{{"type":"cmd","topic":"{}","value":"webcam"}}'.format(lecture),
                                     effective_whitelist(rehearsal))


def test_whitelist_de_base_gravee():
    assert WHITELIST == WHITELIST_BASE_GRAVEE


def test_whitelist_effective_sans_repetition_est_la_base():
    assert effective_whitelist(False) == WHITELIST_BASE_GRAVEE


def test_whitelist_effective_avec_repetition_ajoute_exactement_cinq_topics():
    assert effective_whitelist(True) == WHITELIST_BASE_GRAVEE | TOPICS_REPETITION_GRAVES


def test_whitelist_effective_immuable():
    # Le node la partage entre publishers et parseur : personne ne doit pouvoir
    # l'élargir en cours de route.
    assert isinstance(effective_whitelist(True), frozenset)


@pytest.mark.parametrize("rehearsal", [False, True])
@pytest.mark.parametrize("topic", TOPICS_INTERDITS + ["chat_state", "persona_state",
                                                       "route_state", "chat_transcript",
                                                       "rehearsal/state", "camera_state",
                                                       "camera_source_state", "camera_sources"])
def test_topics_interdits_et_en_lecture_seule_jamais_publiables(topic, rehearsal):
    """Répétition activée ou non : ni les roues, ni e_stop, ni les topics d'état
    ou de flux (lecture seule) n'entrent dans la whitelist effective."""
    assert topic not in effective_whitelist(rehearsal)
    with pytest.raises(ProtocolError):
        parse_client_message('{{"type":"cmd","topic":"{}","value":1}}'.format(topic),
                             effective_whitelist(rehearsal))


@pytest.mark.parametrize("topic,valeur", [
    ("route", '"on"'), ("route", '"restart"'), ("route_speed", "0.5"),
    ("rehearsal/cmd", '"start"'),
])
def test_cmd_repetition_refusee_par_defaut_et_quand_desactivee(topic, valeur):
    raw = '{{"type":"cmd","topic":"{}","value":{}}}'.format(topic, valeur)
    # Sans whitelist passée : le défaut est la base, donc refus (oubli = côté sûr).
    with pytest.raises(ProtocolError) as defaut:
        parse_client_message(raw)
    assert "topic de répétition désactivé" in defaut.value.raison
    # Whitelist effective répétition OFF : même refus, même message clair.
    with pytest.raises(ProtocolError) as desactive:
        parse_client_message(raw, effective_whitelist(False))
    assert "topic de répétition désactivé" in desactive.value.raison
    assert topic in desactive.value.raison


@pytest.mark.parametrize("topic,valeur,attendu", [
    ("route", '"on"', "on"),
    ("route", '"off"', "off"),
    ("route", '"restart"', "restart"),
    ("route_speed", "0.5", 0.5),
    ("route_speed", "0", 0),
    ("rehearsal/cmd", '"start"', "start"),
    ("rehearsal/cmd", '"stop"', "stop"),
])
def test_cmd_repetition_acceptee_quand_activee(topic, valeur, attendu):
    raw = '{{"type":"cmd","topic":"{}","value":{}}}'.format(topic, valeur)
    assert parse_client_message(raw, effective_whitelist(True)) == {
        "type": "cmd", "topic": topic, "value": attendu, "time": 0}


def test_topic_inconnu_garde_son_message_hors_whitelist_meme_activee():
    with pytest.raises(ProtocolError) as exc:
        parse_client_message('{"type":"cmd","topic":"inconnu","value":1}', effective_whitelist(True))
    assert "hors whitelist" in exc.value.raison


@pytest.mark.parametrize("topic", ['["face"]', '{"a":1}', "42", "null", "true"])
def test_cmd_topic_non_chaine_refuse_proprement(topic):
    """Un topic JSON liste/objet n'est pas hashable : sans garde, `in` sur un
    ensemble lève TypeError (donc PAS ProtocolError) et la connexion du client
    tombe au lieu d'un refus. Défaut constaté avant la page « scène »."""
    with pytest.raises(ProtocolError):
        parse_client_message('{{"type":"cmd","topic":{},"value":1}}'.format(topic))


@pytest.mark.parametrize("topic,valeur", [
    ("chat_text", '"bonjour Didier"'),
    ("chat_instruction", '"tu es pressé"'),
    ("chat_instruction", '""'),   # "" = consigne levée : valeur vide VALIDE
])
def test_cmd_chat_text_et_chat_instruction_acceptes_en_prod(topic, valeur):
    raw = '{{"type":"cmd","topic":"{}","value":{}}}'.format(topic, valeur)
    assert parse_client_message(raw)["topic"] == topic


@pytest.mark.parametrize("domain_id,attendu", [(43, True), (42, False), (0, False), (-1, False), (99, False)])
def test_rehearsal_allowed_seulement_en_simulation(domain_id, attendu):
    assert rehearsal_allowed(domain_id) is attendu


# --- Page « scène » : lecture seule, flux et hello --------------------------------

def test_topics_flux_graves_et_jamais_publiables():
    assert TOPICS_FLUX == {"chat_transcript", "chat_hearing", "jeu/journal"}
    assert TOPICS_FLUX.isdisjoint(WHITELIST | WHITELIST_REPETITION | TOPICS_LECTURE)


def test_build_feed_evenement_de_conversation():
    replique = {"role": "david", "text": "bonjour", "t_ms": 1200}
    assert build_feed("chat_transcript", replique) == {
        "type": "feed", "topic": "chat_transcript",
        "msg": {"role": "david", "text": "bonjour", "t_ms": 1200}}


def test_build_feed_charge_brute_inchangee():
    assert build_feed("chat_transcript", "pas du json") == {
        "type": "feed", "topic": "chat_transcript", "msg": "pas du json"}


def test_build_hello_annonce_la_repetition():
    hello = build_hello(43, writer=True, token_required=False, drive_enabled=False,
                        max_linear=0.5, max_angular=1.0, rehearsal=True)
    assert hello["rehearsal"] is True


def test_build_hello_repetition_absente_par_defaut():
    # Défaut = False : un appelant qui oublie le champ n'ouvre rien.
    hello = build_hello(42, writer=False, token_required=True, drive_enabled=False,
                        max_linear=0.5, max_angular=1.0)
    assert hello["rehearsal"] is False


def test_build_hello_annonce_la_perception():
    hello = build_hello(43, writer=False, token_required=False, drive_enabled=False,
                        max_linear=0.5, max_angular=1.0, perception=True)
    assert hello["perception"] is True


def test_build_hello_perception_absente_par_defaut():
    # Défaut = False : sans perception_topic, le panneau reste masqué.
    hello = build_hello(42, writer=False, token_required=True, drive_enabled=False,
                        max_linear=0.5, max_angular=1.0)
    assert hello["perception"] is False


# --- Pages statiques : contrat avec le protocole -------------------------------------
# Le front n'a pas de test navigateur : ces gardes lisent les VRAIS fichiers et
# attrapent les erreurs qui casseraient une page au chargement (id manquant,
# déclaration en double entre scripts) ou qui trahiraient une règle de sécurité.

def _lire(nom):
    return (STATIC / nom).read_text(encoding="utf-8")


def _ids_html(nom):
    return set(re.findall(r'\bid="([^"]+)"', _lire(nom)))


def _ids_js(*noms):
    """Ids passés LITTÉRALEMENT à $("...") (les ids calculés échappent au test)."""
    return {i for nom in noms for i in re.findall(r'\$\("([^"]+)"\)', _lire(nom))}


def _declarations_globales(nom):
    """Noms déclarés au niveau racine d'un script classique : function/const/let
    en colonne 0. Un const déclaré par deux scripts = SyntaxError au chargement
    du second, donc page morte."""
    return set(re.findall(r"^(?:async\s+)?(?:function\s+(\w+)|(?:const|let|var)\s+(\w+))",
                          _lire(nom), re.M)) and {
        a or b for a, b in re.findall(
            r"^(?:async\s+)?(?:function\s+(\w+)|(?:const|let|var)\s+(\w+))", _lire(nom), re.M)}


@pytest.mark.parametrize("page,scripts", [
    ("index.html", ("commun.js", "app.js")),
    ("scene.html", ("commun.js", "scene.js")),
])
def test_page_fournit_tous_les_ids_que_ses_scripts_utilisent(page, scripts):
    manquants = _ids_js(*scripts) - _ids_html(page)
    assert manquants == set(), f"{page} : ids absents du HTML alors que le JS les lit : {sorted(manquants)}"


@pytest.mark.parametrize("page,script", [("index.html", "app.js"), ("scene.html", "scene.js")])
def test_commun_charge_avant_le_script_de_la_page(page, script):
    sources = re.findall(r'<script src="/static/([\w.]+)"', _lire(page))
    assert sources == ["commun.js", script]


@pytest.mark.parametrize("script", ["app.js", "scene.js"])
def test_script_de_page_ne_redeclare_rien_de_commun(script):
    doublons = _declarations_globales("commun.js") & _declarations_globales(script)
    assert doublons == set(), f"{script} redéclare des noms de commun.js : {sorted(doublons)}"


def test_scene_ne_lit_que_les_topics_d_etat_publics():
    """David ne voit pas le tirage : de `state`, la page scène ne lit QUE ces
    topics. Jamais chat_instruction (le régisseur y publie ses consignes)
    ni route_speed (une panne « batterie faible » y passerait).
    chat_audio_chain (31/10) : le branchement du son — public, il ne porte
    aucune panne (micro, moteurs, persona).
    jeu/intention (02/11, lot A1) : ce que le SÉLECTEUR DE JEU a choisi et
    pourquoi — la lisibilité voulue (spec A1 §5), pas un tirage du régisseur
    (la séance A1 tourne avec un scénario vide) ; rehearsal/objects : le
    vocabulaire d'objets, déjà public (envoyé à la bouche)."""
    lus = re.findall(r'valeurTopic\(msg\.topics, "([^"]+)"\)', _lire("scene.js"))
    assert sorted(lus) == ["camera_source_state", "camera_sources", "camera_state",
                           "chat_audio_chain", "chat_state", "jeu/intention", "persona_state",
                           "rehearsal/objects", "rehearsal/state", "route_state"]
    # Et aucun autre accès direct aux topics du message state.
    assert len(re.findall(r"msg\.topics", _lire("scene.js"))) == len(lus)


def test_scene_personas_graves():
    bloc = re.search(r"const PERSONAS = \[(.*?)\n\];", _lire("scene.js"), re.S).group(1)
    assert re.findall(r'\["(\w+)",', bloc) == ["bougon", "naif", "vantard", "mauvaisefoi"]


def test_scene_publie_seulement_des_topics_de_la_whitelist_effective():
    topics = set(re.findall(r'data-topic="([^"]+)"', _lire("scene.html")))
    topics |= set(re.findall(r'envoyerSaisie\("([^"]+)"', _lire("scene.js")))
    topics |= set(re.findall(r'creerBoutonCatalogue\("([^"]+)"', _lire("scene.js")))
    # jeu/console (02/11, lot A1) : panneau « Jeu » (ordres macro du sélecteur de jeu).
    assert topics == {"chat", "persona", "chat_text", "chat_instruction",
                      "route", "route_speed", "rehearsal/cmd", "camera_enable", "camera_source",
                      "jeu/console"}
    assert topics <= effective_whitelist(True)


def test_scene_boutons_de_repetition_masques_par_defaut():
    """Chaque élément de répétition de scene.html (boutons route/séance, curseur
    de vitesse) doit être sous un ancêtre `scene-repetition` portant `hidden` :
    sur le vrai robot, la page n'en montre aucun tant que hello.rehearsal n'est
    pas vrai."""
    from html.parser import HTMLParser

    class Analyse(HTMLParser):
        def __init__(self):
            super().__init__()
            self.pile = []        # (balise, protégé ?) des éléments ouverts
            self.trouves = []     # (identifiant, protégé ?) des éléments de répétition

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            classes = (attrs.get("class") or "").split()
            protege = "scene-repetition" in classes and "hidden" in attrs
            if tag not in ("input", "img", "br", "meta", "link"):
                self.pile.append((tag, protege))
            sous_protection = any(p for _t, p in self.pile)
            if attrs.get("data-topic") in TOPICS_REPETITION_GRAVES or attrs.get("id") == "scene-vitesse":
                self.trouves.append((attrs.get("data-topic") or attrs.get("id"), sous_protection))
            # Panneau « Jeu » (lot A1) : ses boutons publient jeu/console via scene.js.
            if "jeu-bouton" in classes:
                self.trouves.append((attrs.get("data-jeu"), sous_protection))

        def handle_endtag(self, tag):
            for i in range(len(self.pile) - 1, -1, -1):
                if self.pile[i][0] == tag:
                    del self.pile[i:]
                    break

    analyse = Analyse()
    analyse.feed(_lire("scene.html"))
    # 3 route + 2 séance + 2 webcam + 2 source + 1 curseur + 7 boutons du panneau « Jeu »
    # (va là, joue avec, ignore, reviens, plus lent, STOP, GO — STOP et GO distincts).
    assert len(analyse.trouves) == 17
    assert [x[0] for x in analyse.trouves[-7:]] == ["va_la", "joue_avec", "ignore", "reviens",
                                                    "plus_lent", "stop", "go"]
    assert [x for x in analyse.trouves if not x[1]] == []


def test_robot_web_ne_cite_jamais_le_package_de_repetition():
    """Anti-fuite étendu : test_rehearsal_contract ne lit que py/xml/yaml/sh/cfg ;
    ici TOUS les fichiers du package (html, js, css compris). Les noms de topics
    (route, rehearsal/cmd) sont permis -- pas le package sim-only lui-même."""
    fuites = []
    for chemin in PACKAGE_WEB.rglob("*"):
        if not chemin.is_file() or "__pycache__" in chemin.parts:
            continue
        if "didier_rehearsal" in chemin.read_text(encoding="utf-8", errors="ignore"):
            fuites.append(str(chemin.relative_to(PACKAGE_WEB)))
    assert fuites == []


# --- Le pont lui-même, rclpy simulé -----------------------------------------------------
# web_bridge_node importe rclpy : absent sur l'hôte de CI. On le remplace par un
# Node factice qui ENREGISTRE publishers et abonnements, le reste (aiohttp, PIL)
# est réel -- d'où l'importorskip : sans eux, ces tests sont ignorés, pas rouges.

class _Publieur:
    def __init__(self):
        self.messages = []

    def publish(self, msg):
        self.messages.append(msg)


class _Journal:
    def __init__(self):
        self.lignes = []

    def info(self, texte):
        self.lignes.append(("info", texte))

    def warning(self, texte):
        self.lignes.append(("warning", texte))

    def error(self, texte):
        self.lignes.append(("error", texte))


class _NodeFactice:
    imposes = {}   # nom de paramètre -> valeur, posé par le test AVANT la construction

    def __init__(self, nom):
        self.params = {}
        self.publishers = {}
        self.abonnements = {}   # topic -> (qos, callback)
        self.journal = _Journal()

    def declare_parameter(self, nom, defaut):
        self.params[nom] = self.imposes.get(nom, defaut)

    def get_parameter(self, nom):
        return types.SimpleNamespace(value=self.params[nom])

    def create_publisher(self, _type, topic, _qos):
        self.publishers[topic] = _Publieur()
        return self.publishers[topic]

    def create_subscription(self, _type, topic, callback, qos):
        self.abonnements[topic] = (qos, callback)

    def get_logger(self):
        return self.journal

    def get_node_names_and_namespaces(self):
        return []


class _StringTimeFactice:
    def __init__(self, msg="", time=0, anim=False):
        self.msg = msg
        self.time = time
        self.anim = anim


class _QoSFactice:
    def __init__(self, depth=10, durability="VOLATILE", reliability="RELIABLE"):
        self.depth = depth
        self.durability = durability
        self.reliability = reliability


def _module(nom, **attributs):
    module = types.ModuleType(nom)
    module.__dict__.update(attributs)
    return module


@pytest.fixture
def pont(monkeypatch):
    """Le module web_bridge_node importé avec rclpy & co simulés ; retire le
    module de sys.modules à la fin pour ne rien laisser derrière."""
    pytest.importorskip("aiohttp")
    pytest.importorskip("PIL")
    faux = {
        "rclpy": _module("rclpy"),
        "rclpy.node": _module("rclpy.node", Node=_NodeFactice),
        "rclpy.qos": _module("rclpy.qos", QoSProfile=_QoSFactice,
                             DurabilityPolicy=types.SimpleNamespace(TRANSIENT_LOCAL="TRANSIENT_LOCAL"),
                             ReliabilityPolicy=types.SimpleNamespace(BEST_EFFORT="BEST_EFFORT")),
        "ament_index_python": _module("ament_index_python"),
        "ament_index_python.packages": _module(
            "ament_index_python.packages", get_package_share_directory=lambda _nom: str(PACKAGE_WEB)),
        "geometry_msgs": _module("geometry_msgs"),
        "geometry_msgs.msg": _module("geometry_msgs.msg", Twist=type("Twist", (), {})),
        "sensor_msgs": _module("sensor_msgs"),
        "sensor_msgs.msg": _module("sensor_msgs.msg", CompressedImage=type("CompressedImage", (), {}),
                                   Image=type("Image", (), {})),
        "robot_interfaces": _module("robot_interfaces"),
        "robot_interfaces.msg": _module("robot_interfaces.msg", StringTime=_StringTimeFactice),
    }
    for nom, module in faux.items():
        monkeypatch.setitem(sys.modules, nom, module)
    monkeypatch.delitem(sys.modules, "didier_web.web_bridge_node", raising=False)
    module = importlib.import_module("didier_web.web_bridge_node")
    yield module
    sys.modules.pop("didier_web.web_bridge_node", None)


def _creer_noeud(pont, monkeypatch, domaine="43", **params):
    monkeypatch.setenv("ROS_DOMAIN_ID", domaine)
    monkeypatch.setattr(_NodeFactice, "imposes", params)
    return pont.WebBridgeNode()


def test_pont_par_defaut_sans_topics_de_repetition(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch)
    assert set(noeud.publishers) == WHITELIST_BASE_GRAVEE
    assert noeud.rehearsal_enabled is False
    assert noeud.hello_message("c1")["rehearsal"] is False


def test_pont_perception_desactivee_par_defaut(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch)
    assert noeud.perception_topic == ""
    assert "camera/image_raw/compressed" not in noeud.abonnements
    assert noeud.hello_message("c1")["perception"] is False


@pytest.mark.parametrize("domaine", ["43", "42"])
def test_pont_perception_active_lecture_seule(pont, monkeypatch, domaine):
    noeud = _creer_noeud(pont, monkeypatch, domaine=domaine,
                         perception_topic="camera/image_raw/compressed")
    assert noeud.hello_message("c1")["perception"] is True
    qos, callback = noeud.abonnements["camera/image_raw/compressed"]
    assert (qos.depth, qos.reliability) == (1, "BEST_EFFORT")
    # Lecture seule : aucun publisher sur ce topic, ni dans la whitelist.
    assert set(noeud.publishers) == WHITELIST_BASE_GRAVEE
    for rehearsal in (False, True):
        assert "camera/image_raw/compressed" not in effective_whitelist(rehearsal)
    with pytest.raises(ProtocolError):
        parse_client_message(
            '{"type":"cmd","topic":"camera/image_raw/compressed","value":1}',
            effective_whitelist(True))


def test_pont_perception_garde_le_jpeg_tel_quel(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch, perception_topic="camera/image_raw/compressed")
    _qos, callback = noeud.abonnements["camera/image_raw/compressed"]
    callback(types.SimpleNamespace(format="jpeg", data=b"\xff\xd8abc"))
    jpeg, _at = noeud.flux_perception.snapshot()
    assert jpeg == b"\xff\xd8abc"
    # Le flux caméra n'est pas touché, un format non JPEG est ignoré.
    assert noeud.flux_camera.snapshot()[0] is None
    noeud2 = _creer_noeud(pont, monkeypatch, perception_topic="p")
    noeud2.abonnements["p"][1](types.SimpleNamespace(format="png", data=b"x"))
    assert noeud2.flux_perception.snapshot()[0] is None


def test_build_hello_annonce_l_exterieur():
    hello = build_hello(43, writer=False, token_required=False, drive_enabled=False,
                        max_linear=0.5, max_angular=1.0, exterior=True)
    assert hello["exterior"] is True
    # Défaut = False : sans exterior_topic (vrai robot), le panneau reste masqué.
    hello = build_hello(42, writer=False, token_required=True, drive_enabled=False,
                        max_linear=0.5, max_angular=1.0)
    assert hello["exterior"] is False


def test_pont_exterieur_desactive_par_defaut(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch)
    assert noeud.exterior_topic == ""
    assert "camera_ext/image_raw" not in noeud.abonnements
    assert noeud.hello_message("c1")["exterior"] is False


@pytest.mark.parametrize("domaine", ["43", "42"])
def test_pont_exterieur_actif_lecture_seule(pont, monkeypatch, domaine):
    noeud = _creer_noeud(pont, monkeypatch, domaine=domaine,
                         exterior_topic="camera_ext/image_raw")
    assert noeud.hello_message("c1")["exterior"] is True
    qos, _callback = noeud.abonnements["camera_ext/image_raw"]
    assert (qos.depth, qos.reliability) == (1, "BEST_EFFORT")
    # Lecture seule : aucun publisher sur ce topic, ni dans la whitelist.
    assert set(noeud.publishers) == WHITELIST_BASE_GRAVEE
    for rehearsal in (False, True):
        assert "camera_ext/image_raw" not in effective_whitelist(rehearsal)
    with pytest.raises(ProtocolError):
        parse_client_message(
            '{"type":"cmd","topic":"camera_ext/image_raw","value":1}',
            effective_whitelist(True))


def test_pont_exterieur_encode_en_jpeg_sans_toucher_la_camera(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch, exterior_topic="camera_ext/image_raw")
    _qos, callback = noeud.abonnements["camera_ext/image_raw"]
    callback(types.SimpleNamespace(encoding="rgb8", width=2, height=2, data=bytes(12)))
    jpeg, _at = noeud.flux_exterieur.snapshot()
    assert jpeg[:2] == b"\xff\xd8"          # signature JPEG
    assert noeud.flux_camera.snapshot()[0] is None
    assert noeud.flux_perception.snapshot()[0] is None


def test_derniere_frame_jpeg_throttle(pont):
    flux = pont.DerniereFrameJpeg(10)   # 10 i/s : une frame admise par 0,1 s
    assert flux.admettre(1.0) is True
    assert flux.admettre(1.05) is False
    assert flux.admettre(1.1) is True


def test_pont_repetition_activee_en_simulation(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch, rehearsal_enabled=True)
    assert set(noeud.publishers) == WHITELIST_BASE_GRAVEE | TOPICS_REPETITION_GRAVES
    assert noeud.hello_message("c1")["rehearsal"] is True
    # Abonné aussi aux topics de répétition (la supervision voit les commandes).
    assert TOPICS_REPETITION_GRAVES <= set(noeud.abonnements)


@pytest.mark.parametrize("domaine", ["42", "0", "abc"])
def test_pont_repetition_demandee_hors_simulation_est_ignoree_et_dite(pont, monkeypatch, domaine):
    """Garde-fou « ne jamais mélanger » : rehearsal_enabled=true sur le domaine du
    vrai robot (ou inconnu) n'ouvre rien, et le dit en ERROR (jamais silencieux)."""
    noeud = _creer_noeud(pont, monkeypatch, domaine=domaine, rehearsal_enabled=True)
    assert noeud.rehearsal_enabled is False
    assert set(noeud.publishers) == WHITELIST_BASE_GRAVEE
    assert noeud.hello_message("c1")["rehearsal"] is False
    erreurs = [t for niveau, t in noeud.journal.lignes if niveau == "error"]
    assert len(erreurs) == 1 and "rehearsal_enabled IGNORÉ" in erreurs[0]


def test_pont_etats_latches_et_flux_sans_publisher(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch, rehearsal_enabled=True)
    # Lecture seule : aucun publisher sur un topic d'état ni de flux.
    assert set(noeud.publishers).isdisjoint(TOPICS_LECTURE | TOPICS_FLUX)
    # État latché par son publieur : abonné TRANSIENT_LOCAL depth 1 (sinon le
    # pont ne recevrait jamais l'état courant, seulement la prochaine transition).
    for topic in TOPICS_LECTURE:
        qos, _callback = noeud.abonnements[topic]
        assert (qos.depth, qos.durability) == (1, "TRANSIENT_LOCAL"), topic
    # Flux : QoS par défaut (10, volatile) -- compatible avec un publieur volatile.
    for topic in TOPICS_FLUX:
        qos, _callback = noeud.abonnements[topic]
        assert qos == 10, topic


def test_flux_avant_demarrage_de_la_boucle_est_jete_sans_erreur(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch)
    _qos, callback = noeud.abonnements["chat_transcript"]
    assert noeud.feed_sink is None
    callback(_StringTimeFactice(msg=json.dumps({"role": "david", "text": "x", "t_ms": 1})))


class _ClientFactice:
    """Un WebSocket de client, côté serveur : n'enregistre que ce qu'on lui envoie."""
    closed = False

    def __init__(self):
        self.recus = []

    async def send_json(self, payload):
        self.recus.append(payload)


@pytest.mark.filterwarnings("ignore:It is recommended to use web.AppKey")
def test_flux_diffuse_dans_l_ordre_depuis_le_thread_rclpy(pont, monkeypatch):
    """Le piège : le callback d'abonnement tourne dans le thread rclpy, les
    WebSockets appartiennent à la boucle asyncio. 200 répliques déposées depuis
    un AUTRE thread doivent arriver à TOUS les clients, toutes, dans l'ordre.
    La boucle tourne en mode DEBUG d'asyncio : il lève RuntimeError sur toute
    opération non thread-safe venue d'un autre thread (ex. queue.put_nowait
    direct depuis le callback) -- sans lui, le réveil de la boucle par ses
    minuteurs masquerait la faute."""
    noeud = _creer_noeud(pont, monkeypatch)
    _qos, callback = noeud.abonnements["chat_transcript"]
    clients = {"c1": _ClientFactice(), "c2": _ClientFactice()}
    total = 200

    async def scenario():
        app = pont.web.Application()
        app["node"] = noeud
        app["clients"] = clients
        boucles = pont._background_loops_ctx(app)
        await boucles.__anext__()          # démarre les boucles : feed_sink posé
        assert noeud.feed_sink is not None
        # Laisse le consommateur arriver à son `queue.get()` : c'est le getter en
        # attente qu'un dépôt non thread-safe tenterait de réveiller (et que le
        # mode debug sanctionne). Sans cette pause, la file se remplit avant que
        # personne n'attende et la faute passe inaperçue.
        await asyncio.sleep(0.05)

        def depuis_rclpy():
            for i in range(total):
                callback(_StringTimeFactice(
                    msg=json.dumps({"role": "didier", "text": str(i), "t_ms": i})))

        fil = threading.Thread(target=depuis_rclpy)
        fil.start()
        for _ in range(200):               # 2 s max
            if all(len(c.recus) == total for c in clients.values()):
                break
            await asyncio.sleep(0.01)
        fil.join()
        with pytest.raises(StopAsyncIteration):
            await boucles.__anext__()      # arrêt propre : boucles annulées
        assert noeud.feed_sink is None     # alimentation coupée en premier

    asyncio.run(scenario(), debug=True)
    attendu = [build_feed("chat_transcript", {"role": "didier", "text": str(i), "t_ms": i})
               for i in range(total)]
    assert clients["c1"].recus == attendu
    assert clients["c2"].recus == attendu


def test_flux_charge_non_json_transmise_brute(pont, monkeypatch):
    noeud = _creer_noeud(pont, monkeypatch)
    _qos, callback = noeud.abonnements["chat_transcript"]
    recus = []
    noeud.feed_sink = recus.append
    callback(_StringTimeFactice(msg="pas du json"))
    assert recus == [build_feed("chat_transcript", "pas du json")]


@pytest.mark.filterwarnings("ignore:It is recommended to use web.AppKey")
def test_pont_de_bout_en_bout_scene_cmd_et_flux(pont, monkeypatch):
    """Vrai serveur aiohttp, vrai WebSocket : /scene est servie, le hello annonce
    la répétition, une cmd `route` est publiée (valeur nue en JSON), une cmd de
    répétition est refusée quand elle est désactivée, et un feed poussé depuis un
    autre thread arrive au client."""
    from aiohttp.test_utils import TestClient, TestServer

    noeud = _creer_noeud(pont, monkeypatch, rehearsal_enabled=True)
    _qos, callback = noeud.abonnements["chat_transcript"]

    async def lire(ws, type_attendu):
        for _ in range(10):
            msg = await asyncio.wait_for(ws.receive_json(), timeout=2)
            if msg["type"] == type_attendu:
                return msg
        raise AssertionError("message {!r} jamais reçu".format(type_attendu))

    async def scenario():
        async with TestServer(pont.build_app(noeud)) as serveur, TestClient(serveur) as client:
            page = await client.get("/scene")
            assert page.status == 200
            assert "<title>Didier -- scène</title>" in await page.text()
            assert (await client.get("/static/scene.js")).status == 200
            assert (await client.get("/static/commun.js")).status == 200

            ws = await client.ws_connect("/ws")
            assert (await lire(ws, "hello"))["rehearsal"] is True
            await ws.send_json({"type": "auth", "token": None})
            assert (await lire(ws, "hello"))["writer"] is True

            await ws.send_json({"type": "cmd", "topic": "route", "value": "on"})
            assert (await lire(ws, "ack"))["topic"] == "route"
            assert [m.msg for m in noeud.publishers["route"].messages] == ['"on"']
            await ws.send_json({"type": "cmd", "topic": "route_speed", "value": 0.35})
            await lire(ws, "ack")
            assert [m.msg for m in noeud.publishers["route_speed"].messages] == ["0.35"]

            threading.Thread(target=callback, args=(_StringTimeFactice(
                msg=json.dumps({"role": "david", "text": "salut", "t_ms": 7})),)).start()
            assert await lire(ws, "feed") == build_feed(
                "chat_transcript", {"role": "david", "text": "salut", "t_ms": 7})
            await ws.close()

    asyncio.run(scenario())


@pytest.mark.filterwarnings("ignore:It is recommended to use web.AppKey")
def test_pont_de_bout_en_bout_repetition_desactivee_refuse_route(pont, monkeypatch):
    from aiohttp.test_utils import TestClient, TestServer

    noeud = _creer_noeud(pont, monkeypatch)   # rehearsal_enabled par défaut : false

    async def scenario():
        async with TestServer(pont.build_app(noeud)) as serveur, TestClient(serveur) as client:
            ws = await client.ws_connect("/ws")
            assert (await ws.receive_json())["rehearsal"] is False
            await ws.send_json({"type": "auth", "token": None})
            await ws.receive_json()
            await ws.send_json({"type": "cmd", "topic": "route", "value": "on"})
            refus = await ws.receive_json()
            assert refus["type"] == "err" and "topic de répétition désactivé" in refus["reason"]
            # Et un topic de liste (défaut TypeError d'avant) est un refus, pas une chute.
            await ws.send_json({"type": "cmd", "topic": ["route"], "value": "on"})
            assert (await ws.receive_json())["type"] == "err"
            assert not ws.closed
            await ws.close()

    asyncio.run(scenario())
    assert "route" not in noeud.publishers
