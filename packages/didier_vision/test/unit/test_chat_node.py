"""Tests de didier_vision/nodes/_chat_wiring.py — SANS rclpy.

QUOI : didier_vision/nodes/chat_node.py importe rclpy en tête de module (comme tous
       les nodes du repo) — son import échoue systématiquement en CI (rclpy
       absent du host, cf. CLAUDE.md "tests unitaires (host, sans ROS ni
       matériel)"). Les deux bouts de logique de chat_node testables sans ROS
       (traduction RosMessage -> kwargs StringTime, construction des défauts
       de paramètres ROS depuis la config) ont donc été extraits dans
       didier_vision/nodes/_chat_wiring.py, un module PUR (aucun rclpy ni
       theatre_interfaces) — ce fichier de test n'importe QUE lui (et les
       décodeurs des topics de régie de didier_vision.ai.stage, pur aussi), jamais
       didier_vision.nodes.chat_node.
"""
import ast
from pathlib import Path

import pytest

from didier_vision.ai.performance import RosMessage
from didier_vision.ai.stage import decode_fault_command, decode_text_payload
from didier_vision.nodes._chat_wiring import (decode_persona_command, default_chat_parameters,
                                        ros_message_to_string_time_kwargs)
from didier_vision.vision_config import config


# ---------------------------------------------------------------------------
# ros_message_to_string_time_kwargs
# ---------------------------------------------------------------------------

def test_ros_message_to_string_time_kwargs_payload_et_duree():
    message = RosMessage(topic="face", payload='"joie"', time_ms=1500)

    kwargs = ros_message_to_string_time_kwargs(message)

    assert kwargs == {"msg": '"joie"', "time": 1500, "anim": False}


def test_ros_message_to_string_time_kwargs_duree_par_defaut():
    # RosMessage.time_ms par défaut = 0 (cf. didier_vision.ai.performance.thinking,
    # qui ne fixe pas de durée) : le kwarg "time" doit refléter cette valeur
    # telle quelle, pas une valeur magique différente.
    message = RosMessage(topic="face", payload='"reflechit"')

    kwargs = ros_message_to_string_time_kwargs(message)

    assert kwargs["time"] == 0


def test_ros_message_to_string_time_kwargs_anim_toujours_false():
    # anim=False FIXE quel que soit le topic (cf. docstring du module :
    # chat_node ne rejoue jamais de SÉQUENCE d'animation, seulement des
    # commandes ponctuelles) — vérifié aussi bien sur face que sur animation.
    face_kwargs = ros_message_to_string_time_kwargs(RosMessage(topic="face", payload="1"))
    animation_kwargs = ros_message_to_string_time_kwargs(RosMessage(topic="animation", payload="1"))

    assert face_kwargs["anim"] is False
    assert animation_kwargs["anim"] is False


# ---------------------------------------------------------------------------
# default_chat_parameters
# ---------------------------------------------------------------------------

def test_default_chat_parameters_reprend_la_config_unique():
    # Chaque valeur DOIT venir de vision_config.config (source unique, cf.
    # docstring vision_config.py) — pas une copie qui pourrait diverger si
    # config["chat_*"] change un jour sans que ce module soit mis à jour.
    defaults = default_chat_parameters()

    assert defaults["llm_model"] == config["chat_llm_model"]
    assert defaults["llm_base_url"] == config["chat_llm_base_url"]
    assert defaults["whisper_model"] == config["chat_whisper_model"]
    assert defaults["stt_backend"] == config["chat_stt_backend"]
    assert defaults["stt_remote_model"] == config["chat_stt_remote_model"]
    assert defaults["piper_voice"] == config["chat_piper_voice"]
    assert defaults["mic_device"] == config["chat_mic_device"]
    assert defaults["out_device"] == config["chat_out_device"]
    assert defaults["refresh_ms"] == config["chat_animation_refresh_ms"]
    assert defaults["beep_seconds"] == config["chat_beep_seconds"]
    assert defaults["beep_amplitude"] == config["chat_beep_amplitude"]
    assert defaults["persona"] == config["chat_persona"]


def test_default_chat_parameters_couvre_exactement_les_parametres_ros():
    # Fige la liste des 10 paramètres ROS déclarés par ChatNode.__init__ : un
    # ajout/retrait de paramètre ROS doit être visible ici en revue, pas
    # découvert au runtime sur le robot. ("persona" ajouté au lot D3,
    # atelier du 2026-07-13 ; "beep_amplitude" ajouté le 2026-09-13.)
    assert set(default_chat_parameters().keys()) == {
        "llm_model", "llm_base_url", "whisper_model", "stt_backend", "stt_remote_model", "piper_voice",
        "mic_device", "out_device", "refresh_ms", "beep_seconds",
        "beep_amplitude", "persona",
    }


# ---------------------------------------------------------------------------
# decode_persona_command (lot D3 : topic `persona`, changement de
# personnalité à chaud)
# ---------------------------------------------------------------------------

def test_decode_persona_command_brut_et_json():
    # La console web envoie du brut, un `ros2 topic pub` de débogage envoie
    # souvent du JSON avec guillemets : les deux doivent donner le même nom.
    assert decode_persona_command("bougon") == "bougon"
    assert decode_persona_command('"bougon"') == "bougon"


def test_decode_persona_command_normalise_casse_et_espaces():
    # « Bougon » tapé à la main dans un ros2 topic pub doit matcher la clé
    # ASCII minuscule de didier_vision.ai.personas.
    assert decode_persona_command("  Bougon ") == "bougon"
    assert decode_persona_command('" NAIF"') == "naif"


def test_decode_persona_command_ne_valide_pas():
    # La validation appartient à personas.compose_system_prompt (le node
    # loggue un warning sur ValueError) : ici un nom inconnu ressort
    # normalisé, jamais une exception.
    assert decode_persona_command("grincheux") == "grincheux"


# ---------------------------------------------------------------------------
# Décodage des trois topics de RÉGIE (lot R3 « Chantiers », 2026-10-14 —
# chat_text, chat_instruction, rehearsal/chat_fault). La logique vit dans
# didier_vision.ai.stage (pur, importable sans rclpy) : les callbacks de chat_node
# ne font qu'appeler ces décodeurs et transformer ValueError en warning.
# Contrat chat_fault gravé avec les MÊMES chaînes que le régisseur
# (didier_rehearsal, §13.4 point 3).
# ---------------------------------------------------------------------------


def test_decode_text_payload_json_et_brut():
    # Le régisseur et la console web publient json.dumps(texte) ; un
    # `ros2 topic pub` de débogage envoie du brut : même texte rogné.
    assert decode_text_payload('"Tu es amoureux du lampadaire."') == "Tu es amoureux du lampadaire."
    assert decode_text_payload("  bonjour Didier ") == "bonjour Didier"
    assert decode_text_payload('" accentué é "') == "accentué é"


def test_decode_text_payload_json_non_chaine_garde_le_brut():
    # « 42 » ou « null » tapés au clavier sont des TEXTES, pas des valeurs.
    assert decode_text_payload("42") == "42"
    assert decode_text_payload("null") == "null"
    assert decode_text_payload("[1, 2]") == "[1, 2]"


def test_decode_text_payload_vide_vaut_levee_de_consigne():
    # chat_instruction : "" = consigne levée (le régisseur publie json.dumps("")).
    assert decode_text_payload('""') == ""
    assert decode_text_payload("") == ""


def test_decode_fault_command_contrat_du_regisseur():
    assert decode_fault_command(
        '{"op": "delay", "params": {"delay_ms": 6000}, "until_ms": 40000}'
    ) == ("delay", {"delay_ms": 6000}, 40000)
    assert decode_fault_command(
        '{"op": "phantom", "params": {"text": "Sous-titres réalisés par la '
        'communauté d\'Amara.org"}, "until_ms": 1000}'
    ) == ("phantom", {"text": "Sous-titres réalisés par la communauté d'Amara.org"}, 1000)
    # Fin de panne côté régisseur : {"op": "pass"} seul (params/until_ms absents).
    assert decode_fault_command('{"op": "pass"}') == ("pass", {}, None)
    assert decode_fault_command('{"op": "deaf", "params": null, "until_ms": null}') == (
        "deaf", {}, None)


@pytest.mark.parametrize("raw,fragment", [
    ("pas du json", "illisible"),
    ('"deaf"', "objet JSON attendu"),
    ("[1, 2]", "objet JSON attendu"),
    ('{"params": {}}', "op inconnue"),
    ('{"op": "explose"}', "op inconnue"),
    ('{"op": "garble", "params": ["Astérix"]}', "params doit être un objet"),
])
def test_decode_fault_command_refus_avec_message_precis(raw, fragment):
    with pytest.raises(ValueError) as excinfo:
        decode_fault_command(raw)
    assert fragment in str(excinfo.value)


# ---------------------------------------------------------------------------
# Callback chat_text : n'arrête PAS le micro (décision du 2026-10-14).
# MicCapture n'est pas sûr entre threads : un stop() depuis le thread
# rclpy.spin pendant que le thread de conversation lit/arrête le micro peut
# tuer ce dernier (AttributeError). Le moteur sonde la file à chaque trame et
# arrête le micro depuis SON thread. chat_node importe rclpy (absent en CI) :
# on inspecte donc son SOURCE (ast), sans l'importer.
# ---------------------------------------------------------------------------

CHAT_NODE_SOURCE = Path(__file__).resolve().parents[2] / "didier_vision" / "nodes" / "chat_node.py"


def _calls_in_method(source_path, method_name):
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    methods = [node for node in ast.walk(tree)
               if isinstance(node, ast.FunctionDef) and node.name == method_name]
    assert len(methods) == 1, f"{method_name} introuvable ou en double"
    return [ast.unparse(node.func) for node in ast.walk(methods[0])
            if isinstance(node, ast.Call)]


def test_callback_chat_text_n_arrete_pas_le_micro():
    calls = _calls_in_method(CHAT_NODE_SOURCE, "_on_chat_text")
    # Ancre : c'est bien le callback qui enfile le texte qu'on inspecte.
    assert "self._stage.push_text" in calls
    # Aucun appel au micro depuis le thread rclpy (ni stop, ni autre).
    assert "self._mic.stop" not in calls
    assert not any("_mic" in call for call in calls)


# ---------------------------------------------------------------------------
# Garde-fous de CÂBLAGE des topics de régie (revue adversariale du
# 2026-10-14 : aucun de ces points n'était testé, or chacun casse en
# SILENCE sur le robot -- pas de crash, juste une régie qui ne répond plus
# ou une fuite du tirage). Même procédé que ci-dessus : on lit le SOURCE de
# chat_node par `ast`, sans l'importer (rclpy absent du host).
# ---------------------------------------------------------------------------

def _chat_node_tree():
    return ast.parse(CHAT_NODE_SOURCE.read_text(encoding="utf-8"))


def _module_string_constants(tree):
    """{NOM: valeur} des seules affectations de tête de module `NOM = "littéral"`.
    Une constante RECALCULÉE (f-string, concaténation, import) n'y figure pas :
    c'est voulu, le test qui la réclame échoue au lieu de recalculer la même
    chose que le code et de ne rien prouver."""
    constants = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            constants[node.targets[0].id] = node.value.value
    return constants


def _chat_node_method(tree, method_name):
    """Méthode de la classe ChatNode (PAS n'importe quel `__init__` du
    fichier : _DiagState et DiagServer en ont un aussi)."""
    classes = [node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == "ChatNode"]
    assert len(classes) == 1, "classe ChatNode introuvable ou en double"
    methods = [node for node in classes[0].body
               if isinstance(node, ast.FunctionDef) and node.name == method_name]
    assert len(methods) == 1, f"ChatNode.{method_name} introuvable ou en double"
    return methods[0]


def _subscriptions(init):
    """[(type, topic, callback)] de chaque `self.create_subscription(...)` du
    constructeur, tels qu'écrits dans le source (ast.unparse) : le topic est
    donc le NOM de la constante (CHAT_TEXT_TOPIC), pas sa valeur."""
    found = []
    for node in ast.walk(init):
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "self.create_subscription":
            assert len(node.args) >= 3, ast.unparse(node)
            msg_type, topic, callback = (ast.unparse(arg) for arg in node.args[:3])
            found.append((msg_type, topic, callback))
    return found


def _publisher_topics(tree, constants):
    """Valeur RÉSOLUE du topic de chaque `self.create_publisher(...)` du fichier :
    une constante nommée est résolue par `constants`, un littéral inline est
    pris tel quel -- publier sur 'chat_text' en dur ne doit pas échapper au
    garde-fou anti-bouclage. Une constante non littérale ressort en <NOM>."""
    topics = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "self.create_publisher":
            topic = node.args[1]
            if isinstance(topic, ast.Constant):
                topics.append(topic.value)
            elif isinstance(topic, ast.Name):
                topics.append(constants.get(topic.id, f"<{topic.id}>"))
            else:
                topics.append(ast.unparse(topic))
    return topics


# --- (1) Les quatre noms de topics : valeurs EXACTES ------------------------
# CONTRAT PARTAGÉ avec le dépôt robot : ces chaînes sont aussi gravées de
# l'autre côté (les renommer d'un seul côté coupe la liaison SANS erreur --
# ROS accepte n'importe quel nom de topic, personne n'écoute plus, c'est tout) :
#   - "chat_instruction" et "rehearsal/chat_fault" : INSTRUCTION_TOPIC et
#     CHAT_FAULT_TOPIC dans packages/didier_rehearsal/didier_rehearsal/contracts.py (mono-dépôt)
#     (gravés par robot/tests/unit/test_rehearsal_contract.py, régisseur) ;
#   - "chat_text" et "chat_transcript" : le pont web du robot
#     (didier_web/web_protocol.py : WHITELIST_TECHNIQUE et TOPICS_FLUX, gravés
#     par robot/tests/unit/test_web_protocol.py, page « scène »).
# On compare donc à des LITTÉRAUX écrits ici, jamais à une valeur recalculée.

@pytest.mark.parametrize("nom,valeur", [
    ("CHAT_TEXT_TOPIC", "chat_text"),
    ("CHAT_INSTRUCTION_TOPIC", "chat_instruction"),
    ("CHAT_FAULT_TOPIC", "rehearsal/chat_fault"),
    ("CHAT_TRANSCRIPT_TOPIC", "chat_transcript"),
])
def test_topics_de_regie_ont_la_valeur_du_contrat(nom, valeur):
    constants = _module_string_constants(_chat_node_tree())

    assert constants.get(nom) == valeur, (
        f"{nom} doit rester le littéral {valeur!r} (contrat avec le dépôt robot), "
        f"trouvé {constants.get(nom)!r}")


# --- (2) Table abonnement -> callback ---------------------------------------
# Le risque le plus grave : `chat_instruction` branché sur _on_chat_text. La
# consigne de jeu (le tirage que David ignore, §13.1 de l'étude) serait alors
# enfilée comme un énoncé et DITE comme « David » dans le transcript affiché
# à l'écran -- fuite du tirage, et aucune erreur nulle part.

ABONNEMENTS_DE_REGIE = [
    ("CHAT_TEXT_TOPIC", "self._on_chat_text"),
    ("CHAT_INSTRUCTION_TOPIC", "self._on_chat_instruction"),
    ("CHAT_FAULT_TOPIC", "self._on_chat_fault"),
]


@pytest.mark.parametrize("topic,callback", ABONNEMENTS_DE_REGIE)
def test_chaque_topic_de_regie_est_abonne_une_fois_au_bon_callback(topic, callback):
    abonnements = _subscriptions(_chat_node_method(_chat_node_tree(), "__init__"))

    assert [(msg_type, cb) for msg_type, t, cb in abonnements if t == topic] == [
        ("StringTime", callback)], f"{topic} : abonnement absent, en double ou mal branché"


@pytest.mark.parametrize("topic,callback", ABONNEMENTS_DE_REGIE)
def test_chaque_callback_de_regie_ne_sert_que_son_topic(topic, callback):
    # Sens inverse : un callback de régie ne doit écouter QUE son topic. Sans
    # lui, brancher un 2e topic sur _on_chat_text passerait le test ci-dessus.
    abonnements = _subscriptions(_chat_node_method(_chat_node_tree(), "__init__"))

    assert [t for _, t, cb in abonnements if cb == callback] == [topic]


def test_le_transcript_n_est_jamais_ecoute_par_le_node():
    # Le transcript est une SORTIE : s'y abonner réinjecterait les répliques de
    # Didier dans sa propre boucle.
    abonnements = _subscriptions(_chat_node_method(_chat_node_tree(), "__init__"))

    assert "CHAT_TRANSCRIPT_TOPIC" not in [topic for _, topic, _ in abonnements]


# --- (3) Publication du transcript ------------------------------------------

def test_publisher_du_transcript_est_cree_sur_son_propre_topic():
    init = _chat_node_method(_chat_node_tree(), "__init__")
    creations = [node for node in ast.walk(init)
                 if isinstance(node, ast.Assign)
                 and [ast.unparse(t) for t in node.targets] == ["self._transcript_pub"]]
    assert len(creations) == 1, "self._transcript_pub créé zéro ou plusieurs fois"
    appel = creations[0].value
    assert isinstance(appel, ast.Call) and ast.unparse(appel.func) == "self.create_publisher"

    assert ast.unparse(appel.args[0]) == "StringTime"
    assert ast.unparse(appel.args[1]) == "CHAT_TRANSCRIPT_TOPIC"


def test_le_node_ne_publie_jamais_sur_ses_topics_d_entree():
    # Publier le transcript (ou quoi que ce soit) sur chat_text : Didier
    # « entendrait » ses propres répliques comme un texte de la régie et se
    # répondrait en boucle, sans fin et sans erreur. Vaut pour les littéraux
    # en dur comme pour les constantes (cf. _publisher_topics).
    tree = _chat_node_tree()
    publies = _publisher_topics(tree, _module_string_constants(tree))

    assert "chat_transcript" in publies  # ancre : le garde-fou voit bien les publishers
    assert not {"chat_text", "chat_instruction", "rehearsal/chat_fault"} & set(publies)


def test_publish_transcript_publie_par_le_publisher_dedie():
    calls = _calls_in_method(CHAT_NODE_SOURCE, "_publish_transcript")

    # Ancre : c'est bien la méthode qui encode puis publie la ligne.
    assert "stage.encode_transcript" in calls
    # Une seule publication, et sur le publisher du transcript -- pas sur un
    # publisher de _string_time_pubs (face/animation) ni sur un autre.
    assert [call for call in calls if call.endswith(".publish")] == [
        "self._transcript_pub.publish"]


# --- (4) _on_chat_fault transmet la durée décodée ---------------------------
# until_ms=None signifie « pas de durée annoncée » : StageState retombe sur le
# plafond local (FAULT_MAX_S = 60 s). Une panne demandée pour 6 s par le
# régisseur durerait alors 60 s, et aucun log d'erreur ne le dirait.

def test_on_chat_fault_passe_le_until_ms_decode_a_set_fault():
    methode = _chat_node_method(_chat_node_tree(), "_on_chat_fault")

    decodages = [node for node in ast.walk(methode)
                 if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                 and ast.unparse(node.value.func) == "stage.decode_fault_command"]
    assert len(decodages) == 1, "decode_fault_command appelé zéro ou plusieurs fois"
    cible = decodages[0].targets[0]
    assert isinstance(cible, ast.Tuple) and len(cible.elts) == 3
    assert all(isinstance(elt, ast.Name) for elt in cible.elts)
    op, params, until_ms = (elt.id for elt in cible.elts)  # 3e valeur = la durée

    appels = [node for node in ast.walk(methode)
              if isinstance(node, ast.Call) and ast.unparse(node.func) == "self._stage.set_fault"]
    assert len(appels) == 1, "set_fault appelé zéro ou plusieurs fois"
    assert not appels[0].keywords, "set_fault attendu en positionnel (op, params, until_ms, now)"
    assert [ast.unparse(arg) for arg in appels[0].args[:3]] == [op, params, until_ms]

    # Et la variable décodée n'est pas réécrasée entre le décodage et l'appel
    # (un `until_ms = None` glissé entre les deux passerait le contrôle ci-dessus).
    ecritures = [node for node in ast.walk(methode)
                 if isinstance(node, ast.Name) and node.id == until_ms
                 and isinstance(node.ctx, ast.Store)]
    assert len(ecritures) == 1


# ---------------------------------------------------------------------------
# Mouvement à la voix (lot I1, 2026-10-22, dadou_robot_ros/docs/
# etude-repetition-simulee.md §13.11). CONTRAT PARTAGÉ : "rehearsal/chat_move"
# est aussi gravé côté robot (CHAT_MOVE_TOPIC de didier_rehearsal/contracts.py,
# test_rehearsal_contract.py). Et la vision ne commande JAMAIS le mouvement
# directement : aucun publisher route / route_speed / cmd_vel dans ce node.
# ---------------------------------------------------------------------------

def test_topic_de_marche_a_la_valeur_du_contrat():
    assert _module_string_constants(_chat_node_tree()).get("CHAT_MOVE_TOPIC") == "rehearsal/chat_move"


def test_chat_node_ne_publie_jamais_sur_un_topic_de_mouvement():
    tree = _chat_node_tree()
    publies = _publisher_topics(tree, _module_string_constants(tree))

    assert "rehearsal/chat_move" in publies  # ancre : le publisher de marche est bien vu
    assert not {"route", "route_speed", "cmd_vel", "/cmd_vel", "cmd_vel_follow",
                "cmd_vel_remote", "wheels"} & set(publies)


def test_publish_move_publie_par_le_publisher_dedie_et_journalise():
    calls = _calls_in_method(CHAT_NODE_SOURCE, "_publish_move")

    assert [c for c in calls if c.endswith(".publish")] == ["self._move_pub.publish"]
    assert "json.dumps" in calls
    assert "self.get_logger().info" in calls


def test_publisher_de_marche_conditionne_et_branche_sur_on_move():
    init_source = ast.unparse(_chat_node_method(_chat_node_tree(), "__init__"))

    # Créé SEULEMENT si le mouvement est activé (rien ne fuit hors du banc)…
    assert ("self._move_pub = self.create_publisher(StringTime, CHAT_MOVE_TOPIC, 10) "
            "if config['chat_move_enabled'] else None") in init_source
    # …et le moteur ne reçoit le callback que dans ce cas.
    assert "on_move=self._publish_move if self._move_pub is not None else None" in init_source


# --- « Aller voir » (lot M1, 31/10, dadou_robot_ros/docs/spec-aller-voir.md
# §2.1) : "rehearsal/objects" est gravé côté robot aussi (contracts.py du
# régisseur). LATCHÉ des deux côtés : publié une seule fois au démarrage du
# régisseur, un abonné VOLATILE démarré après ne le recevrait jamais.

def test_topic_d_objets_a_la_valeur_du_contrat():
    assert (_module_string_constants(_chat_node_tree()).get("REHEARSAL_OBJECTS_TOPIC")
            == "rehearsal/objects")


def test_abonnement_objets_conditionne_au_mouvement_et_latche():
    init = _chat_node_method(_chat_node_tree(), "__init__")
    blocs = [node for node in ast.walk(init) if isinstance(node, ast.If)
             and ast.unparse(node.test) == "config['chat_move_enabled']"]
    assert len(blocs) == 1, "bloc `if config['chat_move_enabled']:` absent ou en double"
    attendu = [("StringTime", "REHEARSAL_OBJECTS_TOPIC", "self._on_objects")]
    assert _subscriptions(blocs[0]) == attendu
    assert [a for a in _subscriptions(init) if a[1] == "REHEARSAL_OBJECTS_TOPIC"] == attendu
    assert ("self.create_subscription(StringTime, REHEARSAL_OBJECTS_TOPIC, self._on_objects, "
            "QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))"
            in ast.unparse(blocs[0]))


def test_on_objects_decode_refuse_ou_remplace_sans_nouvelle_session():
    calls = _calls_in_method(CHAT_NODE_SOURCE, "_on_objects")
    assert "stage.decode_objects_payload" in calls
    assert "personas.objects_prompt" in calls
    assert "self._brain.set_objects_prompt" in calls
    assert "self.get_logger().warning" in calls
    # La spec l'exige : la session LLM n'est PAS réinitialisée.
    assert "self._brain.reconfigure" not in calls


# --- « Regarder » (lot M2, 31/10, spec-aller-voir.md §7.1) : "look" est
# gravé côté robot (gaze_follower_node). Choix prudent du lot : publié
# SEULEMENT avec le mouvement à la voix (banc sim).

def test_topic_de_regard_a_la_valeur_du_contrat():
    assert _module_string_constants(_chat_node_tree()).get("LOOK_TOPIC") == "look"


def test_publisher_de_regard_conditionne_au_mouvement_et_branche_sur_on_look():
    init_source = ast.unparse(_chat_node_method(_chat_node_tree(), "__init__"))
    assert ("self._look_pub = self.create_publisher(StringTime, LOOK_TOPIC, 10) "
            "if config['chat_move_enabled'] else None") in init_source
    assert "on_look=self._publish_look if self._look_pub is not None else None" in init_source


def test_publish_look_publie_par_le_publisher_dedie_et_journalise():
    calls = _calls_in_method(CHAT_NODE_SOURCE, "_publish_look")
    assert [c for c in calls if c.endswith(".publish")] == ["self._look_pub.publish"]
    assert "json.dumps" in calls
    assert "self.get_logger().info" in calls


def test_regard_publie_mais_toujours_aucun_topic_de_roues():
    tree = _chat_node_tree()
    publies = _publisher_topics(tree, _module_string_constants(tree))
    assert "look" in publies
    assert not {"route", "route_speed", "cmd_vel", "/cmd_vel", "cmd_vel_follow",
                "cmd_vel_remote", "wheels", "route_goto"} & set(publies)


@pytest.mark.parametrize("methode", ["__init__", "_on_persona"])
def test_les_deux_compositions_du_prompt_passent_move(methode):
    source = ast.unparse(_chat_node_method(_chat_node_tree(), methode))
    composes = [line for line in source.splitlines() if "compose_system_prompt" in line]

    assert len(composes) == 1, composes
    assert "move=config['chat_move_enabled']" in composes[0]
    # Revue adversariale du 23/10 (I5) : la demande de réflexion n'entre plus
    # dans le system prompt (ni au démarrage, ni au changement de persona).
    assert "reflect" not in composes[0]


def test_demande_de_reflexion_accrochee_au_tableau_de_situation():
    # Même revue (I5) : REFLECT_TEMPLATE passe par StreamingBrain(
    # situation_suffix=…), seulement si la réflexion est activée — la bouche
    # ne le lit qu'avec un tableau frais (cf. test_llm_stream.py).
    init_source = ast.unparse(_chat_node_method(_chat_node_tree(), "__init__"))
    assert ("situation_suffix=personas.REFLECT_TEMPLATE "
            "if config['chat_reflection_enabled'] else ''") in init_source


def test_surcharges_d_env_lues_au_demarrage_avant_les_parametres_ros():
    # Revue adversariale I1 (22/10) : l'env n'est plus lu à l'import de
    # vision_config — chat_node l'applique en TÊTE de constructeur, dans un
    # try qui transforme ValueError en ChatStartupError, et AVANT
    # default_chat_parameters() (le whisper du banc reste le défaut ROS).
    init = _chat_node_method(_chat_node_tree(), "__init__")
    essais = [node for node in ast.walk(init) if isinstance(node, ast.Try)
              and "chat_env_overrides()" in ast.unparse(node.body)]
    assert len(essais) == 1
    gestionnaire = ast.unparse(essais[0].handlers[0])
    assert "except ValueError" in gestionnaire and "raise ChatStartupError" in gestionnaire
    source = ast.unparse(init)
    assert (source.index("chat_env_overrides()") < source.index("config.update(overrides)")
            < source.index("default_chat_parameters()"))
    assert "self.get_logger().warning(warning)" in source


# ---------------------------------------------------------------------------
# Metteur en scène intérieur (lot P, 2026-10-23, dadou_robot_ros/docs/
# spec-metteur-en-scene.md). Noms de topics : constantes du contrat partagé
# (didier_vision.ai.reflection_contract, gravées par test_reflection_contract.py) —
# ici on vérifie qu'elles sont BRANCHÉES, et seulement si la réflexion est
# activée (sinon le chat doit rester strictement celui d'avant).
# ---------------------------------------------------------------------------

def _if_reflexion(init):
    blocs = [node for node in ast.walk(init) if isinstance(node, ast.If)
             and ast.unparse(node.test) == "config['chat_reflection_enabled']"]
    assert len(blocs) == 1, "bloc `if config['chat_reflection_enabled']:` absent ou en double"
    return blocs[0]


def test_abonnements_reflexion_conditionnes_et_bien_branches():
    init = _chat_node_method(_chat_node_tree(), "__init__")
    attendus = [("StringTime", "reflection_contract.SITUATION_TOPIC", "self._on_situation"),
                ("StringTime", "reflection_contract.PROMPT_TOPIC", "self._on_prompt")]
    # Les deux abonnements vivent DANS le bloc conditionnel…
    assert _subscriptions(_if_reflexion(init)) == attendus
    # …et nulle part ailleurs (pas de copie inconditionnelle).
    tous = _subscriptions(init)
    assert [a for a in tous if a[1].startswith("reflection_contract.")] == attendus


def test_publisher_de_reflexion_conditionne_et_branche_sur_on_reflect():
    init_source = ast.unparse(_chat_node_method(_chat_node_tree(), "__init__"))
    assert ("self._reflect_pub = self.create_publisher(StringTime, "
            "reflection_contract.REFLECT_TOPIC, 10) "
            "if config['chat_reflection_enabled'] else None") in init_source
    assert ("on_reflect=self._publish_reflect if self._reflect_pub is not None else None"
            in init_source)
    # Jamais de publication sur ses ENTRÉES de réflexion (Didier se servirait
    # ses propres tableaux / tours spontanés).
    tree = _chat_node_tree()
    publies = _publisher_topics(tree, _module_string_constants(tree))
    assert "reflection_contract.REFLECT_TOPIC" in publies   # ancre
    assert not {"reflection_contract.SITUATION_TOPIC", "reflection_contract.PROMPT_TOPIC",
                "chat_situation", "chat_prompt"} & set(publies)


def test_publish_reflect_encode_et_publie_par_le_publisher_dedie():
    calls = _calls_in_method(CHAT_NODE_SOURCE, "_publish_reflect")
    assert "reflection_contract.encode_reflect" in calls
    assert [c for c in calls if c.endswith(".publish")] == ["self._reflect_pub.publish"]
    assert "self.get_logger().info" in calls


def test_on_situation_decode_refuse_ou_range():
    calls = _calls_in_method(CHAT_NODE_SOURCE, "_on_situation")
    assert "reflection_contract.decode_situation" in calls
    assert "self._stage.set_situation" in calls
    assert "self.get_logger().warning" in calls
    source = ast.unparse(_chat_node_method(_chat_node_tree(), "_on_situation"))
    assert "tableau de situation refusé" in source


def test_on_prompt_decode_refuse_ou_range_sans_toucher_au_micro():
    calls = _calls_in_method(CHAT_NODE_SOURCE, "_on_prompt")
    assert "reflection_contract.decode_prompt" in calls
    assert "self._stage.push_prompt" in calls
    assert "self.get_logger().warning" in calls
    # Même règle que _on_chat_text : le moteur sert la direction depuis SON thread.
    assert not any("_mic" in call for call in calls)


# --- Tâche en cours (lot M4, 01/11, spec-aller-voir.md §9.3) : chat_node
# lit route_goto_result (contrat didier_rehearsal/contracts.py
# ROUTE_GOTO_RESULT_TOPIC) SEULEMENT si le mouvement à la voix est branché.

def test_topic_d_issue_de_geste_a_la_valeur_du_contrat():
    assert (_module_string_constants(_chat_node_tree()).get("ROUTE_GOTO_RESULT_TOPIC")
            == "route_goto_result")


def test_tache_et_abonnement_conditionnes_au_mouvement():
    init = _chat_node_method(_chat_node_tree(), "__init__")
    init_source = ast.unparse(init)
    assert ("self._move_task = MoveTask() if self._move_pub is not None else None"
            in init_source)
    assert "move_task=self._move_task" in init_source
    blocs = [node for node in ast.walk(init) if isinstance(node, ast.If)
             and ast.unparse(node.test) == "self._move_task is not None"]
    attendu = [("StringTime", "ROUTE_GOTO_RESULT_TOPIC", "self._on_goto_result")]
    assert len(blocs) == 1 and _subscriptions(blocs[0]) == attendu
    assert [a for a in _subscriptions(init) if a[1] == "ROUTE_GOTO_RESULT_TOPIC"] == attendu


def test_chat_off_ferme_la_tache():
    source = ast.unparse(_chat_node_method(_chat_node_tree(), "_on_chat_cmd"))
    assert "self._move_task.close('chat OFF')" in source
