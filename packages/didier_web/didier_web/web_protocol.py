"""Protocole du pont web (W0), logique 100% PURE : aucun import rclpy/aiohttp/
robot/dadou_utils_ros -- testable sans ROS ni réseau (garde-fou AST dans
test_web_protocol.py, même motif que wheels_payload.py).

Trois responsabilités :
 - la WHITELIST des topics publiables (contrat de sécurité W0 : wheels/
   cmd_vel_* et e_stop ne DOIVENT jamais y figurer -- voir CLAUDE.md/
   docs/etude-interface-web.md, W0 = supervision + contenus, pas les roues),
   plus son extension SIM-ONLY de répétition (effective_whitelist) ;
 - le parsing/validation des messages client -> serveur (parse_client_message) ;
 - la session d'écriture exclusive + heartbeat (WebSession/SessionManager).

Horloge injectée partout (paramètre `now_s`) plutôt que time.time() interne :
c'est ce qui permet de tester le timeout heartbeat en avançant une horloge
factice à la main, sans time.sleep() ni monkeypatch (même philosophie que
TwistDeadman.is_expired(now_ms) dans didier_drive.deadman).
"""

import json
import math

# --- Whitelist des topics publiables --------------------------------------
# Chaînes littérales dupliquées volontairement (pas d'import dadou_utils_ros.
# utils_static) : didier_web est un package AUTONOME façon didier_drive, le
# conteneur de simulation ne l'embarque pas. wheels/cmd_vel_*/e_stop sont
# ABSENTS ici par construction -- c'est la garantie W0 (pas d'accès roues ni
# verrou e_stop tant que W1/W3 ne sont pas faits, voir etude-interface-web.md).
WHITELIST_SPECTACLE = {"animation", "face", "audio", "robot_lights"}
# "chat" (2026-07-12) : toggle on/off de la parole IA (conversation) — consommé
# par chat_node sur le Pi vision (même contrat StringTime "on"/"off" que
# "gaze"). Ce n'est PAS un topic d'actionneur : aucun risque roues/e_stop.
# "persona" (2026-07-13, lot D3) : sélection de la personnalité de Didier
# (payload = nom de variante "bougon"/"naif"/"vantard", cf. vision.ai.personas
# côté Pi vision) — même nature que "chat" : une commande de configuration du
# chat_node, pas un actionneur.
# "chat_text" / "chat_instruction" (2026-10-14, page « scène ») : la régie
# souffle à Didier un texte « entendu » SANS micro ni STT (chat_text), ou pose
# une consigne de jeu (chat_instruction, "" = levée) -- consommés par chat_node
# sur le Pi vision. Même nature que "chat"/"persona" : de la conversation, pas
# un actionneur. Utile en prod aussi (la régie peut souffler à Didier).
# PIÈGE : en répétition simulée, le régisseur de pannes publie lui aussi sur
# chat_instruction -- le pont ne peut pas distinguer la consigne de la régie de
# celle du régisseur ; la page « scène » ne doit donc JAMAIS afficher ce topic
# (David ne voit pas le tirage).
WHITELIST_TECHNIQUE = {"relay", "neck", "left_eye", "right_eye", "left_arm", "right_arm", "gaze", "chat", "persona", "system",
                       "chat_text", "chat_instruction"}
WHITELIST = WHITELIST_SPECTACLE | WHITELIST_TECHNIQUE

# Topics de RÉPÉTITION SIMULÉE (page « scène », 2026-10-14) : cheminement de
# Didier dans la rue (route on/off/restart, route_speed 0..1) et commande de
# séance du régisseur (rehearsal/cmd start/stop). SIM-ONLY : volontairement
# HORS de WHITELIST -- ils n'entrent dans la whitelist EFFECTIVE que si le node
# a rehearsal_enabled ET tourne en domaine 43 (rehearsal_allowed). Sur le vrai
# robot (domaine 42) ils sont refusés comme n'importe quel topic inconnu :
# aucun client web ne peut lancer une route.
# camera_enable (2026-10-31) : bouton « Webcam ON/OFF » de la page scène,
# StringTime "on"/"off" consommé côté vision ; sim seulement par construction
# (jamais écrivable sur le vrai robot, où la webcam n'est pas ce bouton-là).
# camera_source (2026-10-31) : sélecteur de SOURCE d'images de la perception,
# StringTime "webcam" | "gazebo", consommé côté vision (person_tracker) ; même
# raison que camera_enable : sim seulement, jamais écrivable sur le vrai robot.
# jeu/console (02/11, lot A1) : ordres macro du panneau « Jeu » vers le
# sélecteur de jeu (didier_jeu, SIM-ONLY, refus hors domaine 43) — va_la,
# joue_avec, ignore, reviens, plus_lent, stop, go — et battement {"presence":
# true} à 2 Hz. Même prudence que la route : sim seulement par construction.
WHITELIST_REPETITION = {"route", "route_speed", "rehearsal/cmd", "camera_enable",
                        "camera_source", "jeu/console"}

# Topics MASQUÉS dans le message `state` (2026-10-14, étude §13.1 « David ne
# voit pas le tirage ») : publiables depuis le web (ils restent dans la
# whitelist), mais leur DERNIÈRE VALEUR n'est jamais diffusée aux clients --
# `chat_instruction` porte la lubie en cours, `route_speed` trahit « batterie
# faible » et l'arrêt devant un objet. La page scène ne les lit pas ; la
# console `/` (tableau État, trames WS brutes) les verrait sans ce filtre.
TOPICS_MASQUES = frozenset({"chat_instruction", "route_speed"})


def snapshot_visible(topics: dict) -> dict:
    """Instantané des derniers payloads SANS les topics masqués -- appliqué par
    le node AVANT build_state : le filtre est pur et testable."""
    return {topic: info for topic, info in topics.items() if topic not in TOPICS_MASQUES}


def effective_whitelist(rehearsal_enabled: bool) -> frozenset:
    """Whitelist réellement appliquée par le node : WHITELIST, plus les topics
    de répétition SEULEMENT si le node les a activés. Passée au parseur
    (parse_client_message) ET utilisée pour créer les publishers : un topic
    absent d'ici n'a ni publisher ni chemin de parsing."""
    if rehearsal_enabled:
        return frozenset(WHITELIST | WHITELIST_REPETITION)
    return frozenset(WHITELIST)

# Topics d'ÉTAT observés en LECTURE SEULE (2026-07-13) : publiés latchés
# (TRANSIENT_LOCAL) par chat_node sur le Pi vision — le pont s'y abonne pour
# la surbrillance des options actives dans la console (Parole/Personnalité),
# mais ne crée AUCUN publisher dessus : ils ne sont pas dans WHITELIST, donc
# impossibles à publier depuis le web (un client qui forgerait un cmd
# "chat_state" est rejeté par la validation whitelist comme n'importe quel
# topic inconnu).
# route_state (2026-10-14, page « scène ») : état on/off du cheminement,
# latché par son publieur comme chat_state -- même abonnement TRANSIENT_LOCAL.
# chat_audio_chain (2026-10-31, « Oreille de Didier ») : le BRANCHEMENT du son
# (micro, atténuation, détection, transcription + repli, réponse, voix,
# sortie), latché par chat_node -- même abonnement TRANSIENT_LOCAL.
# rehearsal/state (2026-10-31) : état de la SÉANCE du régisseur (attente /
# en_cours / terminee) et ARRÊT VOCAL, latché par le régisseur. Aucune info de
# panne ni de lubie n'y passe (contrat : rehearsal_state.py) ; lecture seule.
# camera_state (2026-10-31) : "on"/"off" de la webcam de perception, latché
# côté vision en réponse à camera_enable -- l'ÉTAT RÉEL, pas le dernier clic.
# camera_source_state (2026-10-31) : "webcam"/"gazebo", source RÉELLEMENT utilisée,
# latchée côté vision en réponse à camera_source. camera_sources : JSON liste des
# sources DISPONIBLES (["webcam"] ou ["webcam","gazebo"]), latchée aussi ; la page
# masque « Caméra Gazebo » tant que "gazebo" n'y figure pas.
# jeu/intention (02/11, lot A1) : l'intention en cours du sélecteur de jeu
# ({"action", "cible", "pourquoi", "reste_ms", "jauges"…}), latchée par lui ;
# rehearsal/objects (02/11) : le vocabulaire d'objets du régisseur (latché), pour
# que « va là » propose les objets connus. Lecture seule, comme les autres.
# deploy_sha (04/11, lot L1c) : version déployée, latchée par catalogue_node -> badge
# version des deux pages. `catalogue` n'y est PAS : la page garde /api/catalog.
TOPICS_LECTURE = {"chat_state", "persona_state", "route_state", "chat_audio_chain",
                  "rehearsal/state", "camera_state", "camera_source_state",
                  "camera_sources", "jeu/intention", "rehearsal/objects",
                  "deploy_sha"}

# Topics de FLUX (2026-10-14) : un événement par message, à diffuser TOUS aux
# clients (message "feed"), contrairement à `state` qui ne porte que la
# dernière valeur toutes les 2 s -- une conversation perdrait des répliques.
# Lecture seule, comme TOPICS_LECTURE : pas de publisher, pas dans la whitelist.
# chat_hearing (2026-10-31) : un message par tour -- ce que Didier a ENTENDU,
# par quel moteur, en combien de temps, gardé ou jeté. Y compris les tours
# jetés, que le transcript ne montre pas (c'est eux qui expliquent un Didier
# « qui n'entend rien »).
# jeu/journal (02/11, lot A1) : une ligne du journal « pourquoi » du sélecteur de
# jeu par message (décisions, maintiens, refus) — la page en garde les 20 dernières.
TOPICS_FLUX = {"chat_transcript", "chat_hearing", "jeu/journal"}

# Session d'écriture : silence du writer au-delà de ce délai -> écriture
# libérée (personne ne la récupère automatiquement, cf. §2 du protocole).
WRITE_TIMEOUT_S = 3.0
# Cadence attendue du heartbeat client (exportée pour que l'UI s'y cale).
HEARTBEAT_PERIOD_S = 1.0

# Pilotage roues (W3, SIM-ONLY) : silence de commande de drive au-delà de ce
# délai -> le node publie UN Twist nul (arrêt franc). Distinct du deadman
# twist_mux (0.5 s) et du deadman local wheels_node (400 ms) : c'est un rempart
# APPLICATIF côté pont, propre au flux web (le pad relâché doit s'arrêter net,
# même si le navigateur cesse d'émettre sans fermer la WebSocket). 0.3 s < 0.5 s :
# le zéro web arrive avant que le timeout twist_mux ne coupe la source `web`.
DRIVE_TIMEOUT_S = 0.3


class ProtocolError(Exception):
    """Message client invalide (JSON cassé, type inconnu, topic hors
    whitelist, champ manquant). Le node l'attrape SANS fermer la connexion
    et répond {"type": "err", ...} -- motif du décodage StringTime commun
    (payload invalide = refus loggué, jamais une perte silencieuse)."""

    def __init__(self, raison):
        super().__init__(raison)
        self.raison = raison


# --- Parsing des messages client -> serveur --------------------------------

def _is_plain_int(value) -> bool:
    # bool est une sous-classe d'int en Python : un horodatage/une durée ne
    # peut pas être True/False, on l'exclut explicitement partout où on
    # attend un entier (hb.t, cmd.time).
    return isinstance(value, int) and not isinstance(value, bool)


def _clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def _finite_number(value):
    """Renvoie un float fini pour un int/float JSON, sinon None. bool exclu
    (sous-classe d'int : True/False n'est pas une consigne de joystick),
    NaN/inf refusés (math.isfinite) -- une consigne roues NON finie ne doit
    jamais atteindre le calcul de Twist."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _parse_auth(msg: dict) -> dict:
    token = msg.get("token")
    if token is not None and not isinstance(token, str):
        raise ProtocolError("auth.token doit être une chaîne ou null")
    return {"type": "auth", "token": token}


def _parse_hb(msg: dict) -> dict:
    t = msg.get("t")
    if not _is_plain_int(t):
        raise ProtocolError("hb.t manquant ou non entier")
    return {"type": "hb", "t": t}


def _parse_cmd(msg: dict, whitelist) -> dict:
    topic = msg.get("topic")
    # isinstance d'abord : un topic JSON liste/objet n'est pas hashable, `in`
    # sur un ensemble lèverait TypeError (donc hors ProtocolError : la
    # connexion du client tomberait au lieu d'un refus propre).
    if not isinstance(topic, str) or topic not in whitelist:
        if isinstance(topic, str) and topic in WHITELIST_REPETITION:
            raise ProtocolError("topic de répétition désactivé : {!r}".format(topic))
        raise ProtocolError("topic hors whitelist : {!r}".format(topic))
    if "value" not in msg:
        raise ProtocolError("cmd.value manquant")
    time_ms = msg.get("time", 0)
    if not _is_plain_int(time_ms):
        raise ProtocolError("cmd.time doit être un entier (ms)")
    # Borné ici et pas dans le node : StringTime.time est un int64, une valeur
    # hors bornes ferait lever rclpy à l'affectation et tuerait la connexion
    # du client au lieu d'un refus propre. Négatif refusé aussi : time est une
    # durée/un temps restant en ms, jamais négatif dans le contrat existant.
    if not 0 <= time_ms < 2 ** 63:
        raise ProtocolError("cmd.time hors bornes (0 <= ms < 2^63)")
    return {"type": "cmd", "topic": topic, "value": msg["value"], "time": time_ms}


def _parse_drive(msg: dict) -> dict:
    """Consigne de pilotage roues (SIM-ONLY, W3). x = linéaire avant/arrière,
    z = angulaire, tous deux normalisés [-1, 1]. Clamp SILENCIEUX (un joystick
    qui déborde de 1% ne doit pas spammer d'erreurs -- 15 Hz de messages) ;
    en revanche, un type non-numérique / NaN / inf est REFUSÉ (bug ou attaque,
    pas un simple débordement). Ce message ne passe PAS par la whitelist :
    c'est un canal séparé, publié en Twist par le node UNIQUEMENT si son
    paramètre drive_enabled est vrai (défaut false)."""
    x = _finite_number(msg.get("x"))
    z = _finite_number(msg.get("z"))
    if x is None:
        raise ProtocolError("drive.x doit être un nombre fini")
    if z is None:
        raise ProtocolError("drive.z doit être un nombre fini")
    return {"type": "drive", "x": _clamp(x, -1.0, 1.0), "z": _clamp(z, -1.0, 1.0)}


def drive_to_twist(x: float, z: float, max_linear: float, max_angular: float) -> tuple:
    """Consignes normalisées [-1, 1] -> (linéaire m/s, angulaire rad/s)
    PLAFONNÉES. C'EST le plafond de sécurité du plan ("clamp dans le backend",
    etude-interface-web.md §2.3) : quelles que soient les entrées, |lin| <=
    max_linear et |ang| <= max_angular. Le clamp est refait ici même si le
    parsing l'a déjà fait -- un navigateur bugué ou compromis ne peut pas
    l'outrepasser, c'est le dernier calcul avant publication du Twist."""
    lin = _clamp(x, -1.0, 1.0) * max_linear
    ang = _clamp(z, -1.0, 1.0) * max_angular
    return (lin, ang)


# Dispatch par type : chaque entrée valide/normalise son propre message
# (dict -> dict), les types sans champ additionnel se contentent de le
# renvoyer tel quel ("cmd" est traité à part, cf. parse_client_message).
# Table plutôt qu'une cascade de if/elif : c'est ce qui
# tenait parse_client_message() sous le seuil de complexité cyclomatique du
# linter (S3776) tout en gardant chaque règle isolée et testable.
_PARSERS = {
    "auth": _parse_auth,
    "hb": _parse_hb,
    "drive": _parse_drive,
    "take_control": lambda msg: {"type": "take_control"},
    "stop_all": lambda msg: {"type": "stop_all"},
}


def parse_client_message(raw: str, whitelist=WHITELIST) -> dict:
    """JSON brut reçu sur le WebSocket -> dict validé et normalisé (defaults
    appliqués, ex. cmd.time). Lève ProtocolError sur toute entrée invalide.
    `whitelist` = celle du node (effective_whitelist) ; par défaut la base
    WHITELIST, donc SANS topic de répétition : l'oubli est du côté sûr."""
    try:
        msg = json.loads(raw)
    except (TypeError, ValueError) as e:
        raise ProtocolError("JSON illisible : {}".format(e))

    if not isinstance(msg, dict):
        raise ProtocolError("message non-objet : {!r}".format(msg))

    msg_type = msg.get("type")
    if msg_type is None:
        raise ProtocolError("champ 'type' manquant")

    if msg_type == "cmd":
        # Seul parseur qui dépend du contexte (whitelist du node) : il sort de
        # la table _PARSERS pour ne pas imposer un paramètre inutilisé aux autres.
        return _parse_cmd(msg, whitelist)

    parser = _PARSERS.get(msg_type)
    if parser is None:
        raise ProtocolError("type de message inconnu : {!r}".format(msg_type))
    return parser(msg)


# --- Bouton STOP CONTENUS ---------------------------------------------------

def stop_all_commands(rehearsal_enabled: bool = False) -> list:
    """Liste EXACTE (topic, valeur_python) publiée par le bouton STOP CONTENUS,
    dans cet ordre. Pas de roues en W0 ; le verrou e_stop viendra en W1.
    Répétition activée (SIM-ONLY) : STOP coupe AUSSI le cheminement (`route off`
    -- la route est un mode latché, comme `follow` : sans ça, un STOP en pleine
    séance laisserait Didier continuer sa rue) et termine la séance
    (`rehearsal/cmd stop` : le régisseur révoque toutes ses pannes, SIGCONT
    compris). Le deadman reste derrière dans tous les cas.
    Lot A1 (revue du 02/11) : en répétition, STOP envoie D'ABORD {"cmd": "stop"}
    au sélecteur de jeu (jeu/console) — c'est un stop de David : verrou
    jusqu'au « go » de la console, jamais de reprise automatique."""
    commands = [
        ("animation", False),
        ("audio", "stop"),
        ("face", "stop"),
        ("neck", "stop"),
        ("left_eye", "stop"),
        ("right_eye", "stop"),
        ("left_arm", "stop"),
        ("right_arm", "stop"),
    ]
    if rehearsal_enabled:
        commands += [("jeu/console", {"cmd": "stop"}), ("route", "off"), ("rehearsal/cmd", "stop")]
    return commands


# --- Mode robot / sim (sécurité : toujours savoir à qui on parle) ----------

def mode_from_domain_id(domain_id: int) -> str:
    """domain 43 -> SIMULATION, 42 -> ROBOT RÉEL, autre -> INCONNU (affiché
    tel quel, jamais masqué : voir §2 de la spec, "on doit TOUJOURS savoir à
    qui on parle")."""
    if domain_id == 43:
        return "SIMULATION"
    if domain_id == 42:
        return "ROBOT RÉEL"
    return "INCONNU"


def rehearsal_allowed(domain_id: int) -> bool:
    """Les topics de répétition ne s'activent qu'en SIMULATION (domaine 43) :
    garde-fou structurel, même règle que le refus hors 43 du package de
    répétition lui-même. rehearsal_enabled=true sur le domaine 42 (ou un
    domaine inconnu) est donc ignoré par le node -- 'ne jamais mélanger'."""
    return mode_from_domain_id(domain_id) == "SIMULATION"


# --- Messages serveur -> client (constructeurs purs) ------------------------

def build_hello(domain_id: int, writer: bool, token_required: bool,
                drive_enabled: bool, max_linear: float, max_angular: float,
                rehearsal: bool = False, perception: bool = False,
                exterior: bool = False) -> dict:
    # drive_enabled/max_linear/max_angular : l'UI affiche les plafonds et
    # VERROUILLE le pad de pilotage si drive_enabled=false (WEB_DRIVE=false),
    # elle n'a donc pas à les deviner. Le plafond DUR reste appliqué serveur
    # (drive_to_twist) -- l'UI ne fait que refléter et éviter d'émettre pour rien.
    # rehearsal : la page « scène » n'AFFICHE les boutons de répétition (route,
    # vitesse, séance) que si le serveur les accepte ; défaut False = sûr.
    # perception : le serveur sert /perception (second flux vidéo, LECTURE SEULE,
    # ce que voit la perception de Didier) ; la page n'affiche son panneau que
    # si c'est vrai. Défaut False = flux absent, comme sur le vrai robot.
    # exterior : idem pour /exterior (« Didier vu de l'extérieur », caméra de
    # poursuite Gazebo, SIM-ONLY, lecture seule). Défaut False = absent.
    return {
        "type": "hello",
        "domain_id": domain_id,
        "mode": mode_from_domain_id(domain_id),
        "writer": writer,
        "token_required": token_required,
        "drive_enabled": drive_enabled,
        "max_linear": max_linear,
        "max_angular": max_angular,
        "rehearsal": rehearsal,
        "perception": perception,
        "exterior": exterior,
    }


def build_hb_ack(t) -> dict:
    return {"type": "hb_ack", "t": t}


def build_ack(topic: str) -> dict:
    return {"type": "ack", "topic": topic}


def build_err(reason: str) -> dict:
    return {"type": "err", "reason": reason}


def build_feed(topic: str, msg) -> dict:
    """Un événement d'un topic de FLUX (TOPICS_FLUX), diffusé tel quel à tous
    les clients dès sa réception -- pas de regroupement, pas d'âge : le client
    horodate et empile. `msg` = payload décodé (JSON) ou chaîne brute."""
    return {"type": "feed", "topic": topic, "msg": msg}


def build_state(topics: dict, nodes: list, clients: int, writer_present: bool) -> dict:
    return {"type": "state", "topics": topics, "nodes": nodes, "clients": clients,
            "writer_present": writer_present}


# --- Session d'écriture exclusive + heartbeat -------------------------------

class WebSession:
    """État d'un client connecté. authenticated conditionne tout le reste
    (take_control/heartbeat sont no-op pour un client non authentifié)."""

    def __init__(self):
        self.authenticated = False
        self.last_hb_s = None  # dernier battement reçu (horloge injectée), None si jamais


class SessionManager:
    """Gestion pure de l'auth + de l'écriture exclusive. Horloge TOUJOURS
    passée en paramètre (now_s) par l'appelant (le node), jamais lue en
    interne -- c'est ce qui rend check_timeouts()/heartbeat() testables sans
    horloge réelle."""

    def __init__(self, token: str | None):
        # Token serveur vide/None = accès libre (mode dev/sim, cf. §2).
        self.token = token or None
        self._sessions: dict[str, WebSession] = {}
        self.writer_id: str | None = None

    @property
    def token_required(self) -> bool:
        return self.token is not None

    def authenticate(self, client_id: str, token, now_s: float) -> bool:
        """Le premier client authentifié prend l'écriture automatiquement.
        Renvoie False (rejet) si un token serveur est configuré et que celui
        du client ne correspond pas -- la session reste non authentifiée."""
        if self.token_required and token != self.token:
            return False

        session = self._sessions.setdefault(client_id, WebSession())
        session.authenticated = True
        if self.writer_id is None:
            self._grant_write(client_id, now_s)
        return True

    def take_control(self, client_id: str, now_s: float) -> bool:
        """Reprise d'écriture EXPLICITE (opérateur unique, confirmée côté
        client). Toujours autorisée pour un client authentifié, même si un
        autre écrit déjà -- il n'y a qu'un seul opérateur en pratique."""
        session = self._sessions.get(client_id)
        if session is None or not session.authenticated:
            return False
        self._grant_write(client_id, now_s)
        return True

    def _grant_write(self, client_id: str, now_s: float) -> None:
        self.writer_id = client_id
        self._sessions[client_id].last_hb_s = now_s

    def heartbeat(self, client_id: str, now_s: float) -> bool:
        """Réarme l'horloge d'écriture. Un battement d'un non-writer est
        ignoré (il n'a rien à réarmer)."""
        if client_id != self.writer_id:
            return False
        self._sessions[client_id].last_hb_s = now_s
        return True

    def check_timeouts(self, now_s: float) -> str | None:
        """À appeler périodiquement par le node. Libère l'écriture si le
        writer est silencieux depuis plus de WRITE_TIMEOUT_S ; renvoie
        l'identifiant du client libéré (pour que le node le loggue et le
        notifie individuellement), ou None si rien n'a changé."""
        if self.writer_id is None:
            return None

        session = self._sessions.get(self.writer_id)
        if session is None or session.last_hb_s is None \
                or (now_s - session.last_hb_s) > WRITE_TIMEOUT_S:
            released_id = self.writer_id
            self.writer_id = None
            return released_id
        return None

    def remove_client(self, client_id: str) -> bool:
        """Déconnexion : la session est oubliée. Si c'était le writer,
        l'écriture est libérée -- personne ne la récupère automatiquement
        (cf. §2). Renvoie True si le writer a été libéré (pour le log)."""
        was_writer = (client_id == self.writer_id)
        self._sessions.pop(client_id, None)
        if was_writer:
            self.writer_id = None
        return was_writer

    def is_writer(self, client_id: str) -> bool:
        return client_id == self.writer_id

    def writer_present(self) -> bool:
        return self.writer_id is not None

    def client_count(self) -> int:
        return len(self._sessions)


# --- Flux de pilotage roues : décide QUAND publier un zéro (SIM-ONLY) --------

class DriveFlow:
    """Logique PURE d'arrêt du pilotage web (horloge injectée, motif
    SessionManager). Le pad relâché ou un navigateur qui cesse d'émettre sans
    fermer la WebSocket doivent produire UN Twist nul -- mais un seul, pas un
    flot (motif anti-spam de wheels_node : le twist_deadman inonde déjà de zéros
    à 20 Hz au repos, republier en continu ne ferait qu'encombrer les logs).

    Le node appelle on_drive() à chaque consigne reçue, puis should_zero()
    périodiquement (boucle 20 Hz) : celui-ci renvoie True UNE SEULE FOIS quand
    un drive a été reçu puis que le silence dépasse DRIVE_TIMEOUT_S."""

    def __init__(self):
        self._last_drive_s = None   # horloge du dernier on_drive(), None si aucun
        self._zero_pending = False  # un zéro reste à émettre après la salve courante

    def on_drive(self, now_s: float) -> None:
        """Mémorise une consigne de drive reçue (réarme l'échéance du zéro)."""
        self._last_drive_s = now_s
        self._zero_pending = True

    def should_zero(self, now_s: float) -> bool:
        """True UNE SEULE FOIS quand une salve de drive s'est tue depuis plus de
        DRIVE_TIMEOUT_S. Consomme l'état (les appels suivants renvoient False
        jusqu'au prochain on_drive)."""
        if (self._zero_pending and self._last_drive_s is not None
                and (now_s - self._last_drive_s) > DRIVE_TIMEOUT_S):
            self._zero_pending = False
            return True
        return False

    def reset(self) -> None:
        """Oublie toute salve en cours : plus aucun zéro à émettre. À appeler
        quand le zéro a DÉJÀ été publié par un autre chemin (déconnexion du
        writer, perte d'écriture, STOP) -- évite un double zéro/double log."""
        self._last_drive_s = None
        self._zero_pending = False
