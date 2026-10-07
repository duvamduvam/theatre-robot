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
# régisseur (lot R2) qui les traduit en instruction de jeu.
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
HEARTBEAT_TOPIC = "rehearsal/heartbeat"
HEARTBEAT_TIMEOUT_MS = 1000
# Ordres aux relais : StringTime JSON {"relay": nom, "op": ..., "params": {...},
# "until_ms": durée}. Un relais n'obéit qu'aux ordres qui portent son nom.
RELAY_CMD_TOPIC = "rehearsal/relay_cmd"
# Canal JOUÉ (instruction de jeu vers le chat — consommateur au lot R3) : le
# régisseur publie ici et journalise ; personne ne l'écoute encore.
INSTRUCTION_TOPIC = "rehearsal/instruction"

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
FAULT_MAX_DURATION_S = {"relay": 60.0, "pause": 30.0, "kill": 0.0, "speed": 120.0,
                        "instruction": 0.0}
