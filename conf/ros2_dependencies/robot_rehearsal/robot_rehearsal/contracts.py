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
