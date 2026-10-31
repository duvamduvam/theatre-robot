"""Contrats GELÉS du package de répétition — un seul endroit pour les noms de
topics, les plafonds durs et les bornes. Les tests (test_rehearsal_contract.py)
lisent CE module et le comparent aux contrats voisins (chaîne roues, suivi).

SÉCURITÉ : le suiveur d'itinéraire publie sur le créneau PRIORITÉ 20 du
twist_mux (celui du suivi de personne, cf. robot_drive/config/twist_mux.yaml) —
structurellement SOUS la télécommande (100) et le web (50) ; le twist_deadman
(400 ms) reste derrière. Il n'existe AUCUN autre chemin de ce package vers les
roues : /cmd_vel final n'est jamais publié ici.
"""

# --- Topics -----------------------------------------------------------------
# Activation à chaud, même contrat que `follow`/`gaze`/`chat` : StringTime
# "on"/"off" (JSON ou brut tolérés). OFF au démarrage, toujours.
ROUTE_CMD_TOPIC = "route"
# Facteur de vitesse 0..1 (StringTime, payload nombre) : c'est le fader de la
# télécommande (profil « répétition », étude §4.5). Hors bornes -> borné.
ROUTE_SPEED_TOPIC = "route_speed"
# ÉTAT de la route, publié par route_driver en TRANSIENT_LOCAL (latché) :
# à chaque changement et au démarrage. C'est la SOURCE DE VÉRITÉ du
# régisseur (bug vécu le 2026-10-08 : il déduisait l'état d'un unique
# message `route on` volatile, raté sous charge → reboot sans relance).
# Lot M1 « aller voir » (spec-aller-voir.md §2.4) : + "goto" (manœuvre en
# cours) et "arrived" (arrêté face à l'objet). Payload BRUT (pas de JSON),
# lu tel quel par le régisseur et la page scène.
ROUTE_STATE_TOPIC = "route_state"
ROUTE_STATES = ("on", "off", "goto", "arrived")
# CAUSE du dernier état, publiée par route_driver en TRANSIENT_LOCAL (latché,
# des DEUX côtés) : StringTime, payload JSON "boot" (au démarrage du node : la
# route est éteinte faute d'ordre) | "cmd" (à CHAQUE extinction par commande,
# quel que soit le format accepté : "off", false, 0, "0"). Revue adversariale
# I1 (22/10) : le régisseur ne se fie plus à son ÉCOUTE du topic `route` (un
# `off` peut lui échapper, un régisseur relancé l'oublie) pour savoir si la
# route est OFF « par David » — la voix ne relance que sur state "off" ET
# cause "boot" ; cause jamais reçue = refus.
ROUTE_STATE_CAUSE_TOPIC = "route_state_cause"
ROUTE_STATE_CAUSES = ("boot", "cmd")
# Sortie roues : créneau du suivi de personne dans le twist_mux (prio 20).
# Le suivi de personne doit être OFF quand la route est ON (même créneau).
CMD_VEL_TOPIC = "cmd_vel_follow"
# Pose de Didier : VÉRITÉ TERRAIN de Gazebo (plugin OdometryPublisher du
# xacro, bridgée par robot_sim/config/gz_bridge.yaml) — PAS /odom du
# DiffDrive, qui intègre les roues : il ne se remet pas à zéro à une
# téléportation (set_pose au départ) et dérive au premier patinage sur une
# bordure (constaté le 2026-10-07). SIM-ONLY par construction : ce topic
# n'existe que dans Gazebo, le vrai robot n'a aucune odométrie.
ODOM_TOPIC = "/ground_truth/odom"
# Événements de proximité aux points d'intérêt : StringTime JSON
# {"poi": nom, "event": "enter"|"exit", "distance": m}. Consommés par le
# régisseur : un « enter » déclenche les éléments de scénario `t: poi` (R3).
POI_EVENT_TOPIC = "rehearsal/poi_event"

# --- Plafonds ABSOLUS (m/s, rad/s) -------------------------------------------
# IDENTIQUES à ceux du suivi de personne (robot.move.follow_control
# ABS_MAX_LIN/ABS_MAX_ANG) : même créneau du mux, mêmes 50 kg. Dupliqués ici
# parce que le package est autonome ; le test de contrat vérifie l'égalité.
ABS_MAX_LIN = 0.5
ABS_MAX_ANG = 1.0

# Hystérésis des points d'intérêt : on sort à radius * POI_EXIT_FACTOR pour
# ne pas enchaîner enter/exit sur le bruit d'odométrie à la frontière.
POI_EXIT_FACTOR = 1.3

# --- Régisseur de pannes (lot R2, canal TECHNIQUE) ------------------------------
# Commandes au régisseur : "start" | "stop" (termine les pannes actives, fin de
# scénario) | "abort" (idem, immédiat). StringTime.
DIRECTOR_CMD_TOPIC = "rehearsal/cmd"
# Battement du régisseur (StringTime, ~5 Hz). Un relais qui ne l'entend plus
# pendant HEARTBEAT_TIMEOUT_MS retombe SEUL en passant : régisseur mort =
# aucune panne ne reste armée.
# ÉTAT de la séance pour la page scène (2026-10-31), publié par le régisseur
# en TRANSIENT_LOCAL (latché, depth 1, des DEUX côtés) : StringTime, payload
# JSON {"seance": "attente"|"en_cours"|"terminee", "arret_vocal": bool}, à
# chaque changement et au démarrage. NE PORTE JAMAIS d'info de panne/lubie
# (David ne voit pas le tirage) : voir rehearsal_state.py.
REHEARSAL_STATE_TOPIC = "rehearsal/state"
HEARTBEAT_TOPIC = "rehearsal/heartbeat"
HEARTBEAT_TIMEOUT_MS = 1000
# Ordres aux relais : StringTime JSON {"relay": nom, "op": ..., "params": {...},
# "until_ms": durée}. Un relais n'obéit qu'aux ordres qui portent son nom.
RELAY_CMD_TOPIC = "rehearsal/relay_cmd"
# Canal JOUÉ : consigne de jeu GÉNÉRIQUE, consommée par chat_node (dépôt
# vision) — StringTime, payload chaîne JSON, "" = consigne levée. Pas préfixé
# rehearsal/ : en prod, la régie pourra souffler à Didier par le même topic
# (étude §13.4 ; était "rehearsal/instruction", jamais consommé).
INSTRUCTION_TOPIC = "chat_instruction"
# Pannes de CONVERSATION, exécutées par chat_node : StringTime JSON
# {"op": ..., "params": {...}, "until_ms": durée | null}. Ce canal n'a PAS de
# chien de garde (du texte, pas des roues) : la borne est tenue des DEUX côtés
# (FAULT_MAX_DURATION_S["chat"] ici, plafond local 60 s dans chat_node). Les
# chaînes sont un contrat partagé avec le dépôt vision (gravées des deux côtés).
CHAT_FAULT_TOPIC = "rehearsal/chat_fault"
CHAT_FAULT_OPS = ("pass", "delay", "garble", "deaf", "mute", "phantom")
# Mouvement à la voix (lot I1, 22/10) : ordre de marche demandé par Didier,
# StringTime, payload JSON "go" | "stop". PRODUCTEUR : chat_node (dépôt
# vision, seulement si CHAT_MOUVEMENT est posé — banc de répétition) ;
# CONSOMMATEUR : le régisseur SEUL, qui décide et agit par route /
# route_speed (jamais au-dessus de la vitesse en vigueur, jamais contre un
# `off` de David). Sur le vrai robot il n'y a pas de régisseur : sans effet.
# Chaîne gravée des deux côtés (CHAT_MOVE_TOPIC de chat_node).
CHAT_MOVE_TOPIC = "rehearsal/chat_move"
# Lot M1 (spec-aller-voir.md §2.2) : même topic, payload JSON OBJET
# {"cmd": "aller_voir", "objet": "<texte>"} en plus de "go"/"stop". Chaîne
# gravée des deux côtés.
CHAT_MOVE_GOTO_CMD = "aller_voir"
# Lot M2 (spec-aller-voir.md §7.2-§7.3) : gestes GÉNÉRAUX CHIFFRÉS (décision
# de David du 31/10 : composables plus tard par un planificateur, pas de cas
# figés). {"cmd": "tourner", "angle_deg": <signé, + = gauche>} (compat
# {"sens": clé de TURN_DEG_COMPAT}) ; {"cmd": "avancer", "metres": <m>}.
# Chaînes gravées des deux côtés.
CHAT_MOVE_TURN_CMD = "tourner"
CHAT_MOVE_FORWARD_CMD = "avancer"

# --- « Aller voir » (lot M1, spec-aller-voir.md) — SIM-ONLY -----------------------
# Vocabulaire d'objets (régisseur -> chat_node) : StringTime LATCHÉ (TRANSIENT_
# LOCAL depth 1, des DEUX côtés), publié au démarrage du régisseur, JSON liste
# [{"name", "desc"}] dans l'ordre de l'itinéraire. Gravé des deux côtés.
OBJECTS_TOPIC = "rehearsal/objects"
# Ordre de manœuvre (régisseur -> route_driver) : StringTime JSON
# {"name", "x", "y", "standoff"} ou "cancel". Le régisseur ORDONNE ; seul
# route_driver produit le Twist (sortie UNIQUE cmd_vel_follow, prio 20).
ROUTE_GOTO_TOPIC = "route_goto"
ROUTE_GOTO_CANCEL = "cancel"
# Issue d'une manœuvre (route_driver -> régisseur, revue M1) : StringTime JSON
# {"name", "result": "arrived"|"aborted", "reason", "travelled"}, VOLATILE —
# le DÉTAIL (timeout, max_travel, stalled, cancelled…) pour le journal ; la
# source de vérité de l'état reste route_state (latché).
ROUTE_GOTO_RESULT_TOPIC = "route_goto_result"
# Distance de jeu : Didier s'arrête à ce rayon de l'objet (m).
GOTO_STANDOFF_M = 1.5
# Plancher du standoff accepté par route_driver (revue M1) : en dessous, les
# 50 kg viendraient au contact de l'objet (pas d'évitement, spec §5).
GOTO_MIN_STANDOFF_M = 0.8
# Bornes de sûreté (spec §3-§4, tests gravés + mutation) :
#  - refus au-delà de cette distance pose -> objet (régisseur ET route_driver) ;
GOTO_MAX_DISTANCE_M = 40.0
#  - abandon au-delà de cette durée de manœuvre ;
GOTO_TIMEOUT_S = 60.0
#  - abandon au-delà de ce multiple de la distance initiale parcouru (détour,
#    oscillation, Didier poussé par la télécommande). Un Didier BLOQUÉ contre
#    un objet ne fait PAS grimper cette distance (la pose vérité terrain ne
#    bouge pas, même roues qui patinent) : c'est le détecteur de calage de
#    goto.py (raison « stalled ») qui l'arrête ;
GOTO_MAX_TRAVEL_FACTOR = 1.5
#  - rotation max des pivots ALIGN / FACE (et du cap corrigé en DRIVE), SOUS
#    ABS_MAX_ANG : un pivot sur place de 50 kg, plus doux que le suivi.
GOTO_MAX_ANG = 0.6
# « Tourner » (lot M2, §7.2) : pivot sur place d'un angle RELATIF, ordre
# route_goto {"turn_rad": radians(angle_deg)}. Convention ROS (REP 103, z vers
# le haut) : angle POSITIF = rotation vers la GAUCHE. 0 < |angle| ≤
# TURN_MAX_DEG, sinon refus (jamais saturé : un ordre faux ne tourne pas).
# Demi-tour de la compat = +180 : par la gauche, signe déterministe.
TURN_MAX_DEG = 180.0
TURN_DEG_COMPAT = {"gauche": 90.0, "droite": -90.0, "demi_tour": 180.0}
# Abandon d'un pivot au-delà de cette durée (π à 0,6 rad/s ≈ 5 s + rampes).
TURN_TIMEOUT_S = 15.0
# « Avancer » (lot M2, §7.3) : ligne droite sur le cap courant, ordre
# route_goto {"forward_m": m}, FORWARD_MIN_M ≤ m ≤ FORWARD_MAX_M. Négatif
# REFUSÉ : on ne recule pas (pas de capteur arrière, spec §5 : pas
# d'évitement). Sous FORWARD_MIN_M : refus (revue M2 — geste illisible).
FORWARD_MIN_M = 0.1
FORWARD_MAX_M = 5.0
# Abandon au-delà de FORWARD_TIMEOUT_BASE_S + FORWARD_TIMEOUT_PER_M_S × m.
FORWARD_TIMEOUT_BASE_S = 10.0
FORWARD_TIMEOUT_PER_M_S = 4.0

# Points de relais : nom -> (topic amont, topic aval, type). LISTE FERMÉE.
# Le producteur est lancé par rehearsal.launch.py avec un remap vers l'amont ;
# le relais republie vers l'aval (passant par défaut). /cmd_vel final, les
# topics de la télécommande et le deadman ne sont JAMAIS relayables : un relais
# mort sur cmd_vel_follow laisse le mux sans entrée -> deadman -> arrêt (sûr).
RELAYS = {
    "cmd_vel_follow": ("cmd_vel_follow_raw", "cmd_vel_follow", "twist"),
}
RELAY_OPS = ("pass", "drop", "delay", "freeze", "zero")

# Processus (nom d'exécutable, correspondance EXACTE sur la ligne de commande)
# que le régisseur a le droit de mettre en pause (SIGSTOP/SIGCONT) ou de tuer
# (SIGTERM). Liste FERMÉE et gravée par test : jamais twist_mux, twist_deadman,
# wheels_bridge (la chaîne de sécurité) ni le bridge gz.
PAUSABLE = ("route_driver", "face_sim", "servos_sim_node", "leds_sim_node",
            "animations_node", "gaze_follower", "person_follower")
KILLABLE = ("route_driver",)

# Durée MAXIMALE d'une panne par type (s) : au-delà, le régisseur la révoque
# même si le scénario en demandait plus. Une panne infinie n'existe pas.
# 0 = ponctuelle seulement. `instruction` est passée de 0 à 120 au lot R3
# (consigne bornée, levée par "" à la fin) — rétro-compatible : à 0 elle reste
# ponctuelle. 120 = la péremption locale de chat_node pour une consigne.
FAULT_MAX_DURATION_S = {"relay": 60.0, "pause": 30.0, "kill": 0.0, "speed": 120.0,
                        "instruction": 120.0, "lubie": 120.0, "chat": 60.0}

# Fermeture d'une lubie AU FADER (revue adversariale R3) : pendant une lubie
# qui a arrêté Didier, une consigne route_speed EXTERNE (fader du boîtier,
# page scène) qui s'écarte de PLUS de ce seuil de la vitesse en vigueur avant
# la lubie = David a bougé le fader -> la lubie se termine. Un seuil et pas
# l'égalité stricte : le boîtier de faders peut ré-émettre en continu sa
# position, avec le jitter de son ADC — une ré-émission n'est pas un geste
# (la page, elle, n'envoie qu'au changement).
EXTERNAL_SPEED_DELTA = 0.05

# --- Garde-fou DOMAINE ROS (revue adversariale du 2026-10-08, défaut n°6) -------
# Ce package ne doit JAMAIS tourner sur le domaine du vrai robot (42) : un shell
# où ROS_DOMAIN_ID=42 traîne (télécommande) lancerait la sim sur le domaine réel
# et le twist_mux de Didier recevrait cmd_vel_follow. Chaque node vérifie au
# démarrage et REFUSE hors du domaine autorisé.
SIM_DOMAIN_ID = 43


def check_domain(env: dict) -> int:
    """Lève RuntimeError si ROS_DOMAIN_ID (env) n'est pas SIM_DOMAIN_ID.
    Absent = défaut ROS 0 = refusé aussi : on ne devine pas."""
    raw = env.get("ROS_DOMAIN_ID", "")
    try:
        domain = int(raw)
    except (TypeError, ValueError):
        domain = -1
    if domain != SIM_DOMAIN_ID:
        raise RuntimeError(
            f"robot_rehearsal refuse de démarrer : ROS_DOMAIN_ID={raw!r}, attendu {SIM_DOMAIN_ID} "
            "(domaine de la SIMULATION — 42 est le vrai robot)")
    return domain
