"""Contrats GELÉS du package de répétition — un seul endroit pour les noms de
topics, les plafonds durs et les bornes. Les tests (test_rehearsal_contract.py)
lisent CE module et le comparent aux contrats voisins (chaîne roues, suivi).

SÉCURITÉ : le suiveur d'itinéraire publie sur le créneau PRIORITÉ 20 du
twist_mux (celui du suivi de personne, cf. didier_drive/config/twist_mux.yaml) —
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
# xacro, bridgée par didier_sim/config/gz_bridge.yaml) — PAS /odom du
# DiffDrive, qui intègre les roues : il ne se remet pas à zéro à une
# téléportation (set_pose au départ) et dérive au premier patinage sur une
# bordure (constaté le 2026-10-07). SIM-ONLY par construction : ce topic
# n'existe que dans Gazebo, le vrai robot n'a aucune odométrie.
# RELATIF depuis le lot L1b : /<robot>/ground_truth/odom côté ROS (le bridge
# est namespacé) ; le topic GZ, lui, reste /ground_truth/odom (xacro).
ODOM_TOPIC = "ground_truth/odom"
# Événements de proximité aux points d'intérêt : StringTime JSON
# {"poi": nom, "event": "enter"|"exit", "distance": m}. Consommés par le
# régisseur : un « enter » déclenche les éléments de scénario `t: poi` (R3).
POI_EVENT_TOPIC = "rehearsal/poi_event"

# --- Plafonds ABSOLUS (m/s, rad/s) -------------------------------------------
# IDENTIQUES à ceux du suivi de personne (didier_core.move.follow_control
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
# JOURNAL EN DIRECT pour la page scène (« Coulisses », décision de David du
# 18/11 : il voit désormais le tirage). Chaque événement du JSONL est aussi
# publié ici, VOLATILE (depth 10, jamais latché : un vieil événement ne doit
# pas rejouer à l'ouverture de la page) : StringTime, payload JSON
# {"type": str, "payload": dict, "t_ms": int (ms murales)}.
JOURNAL_TOPIC = "rehearsal/journal"
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
# ORIGINE (lot S1, 25/11, docs/spec-S1-ordres-propositions.md §1) : chaque demande dit qui la
# porte. Marche : {"cmd": "stop"|"go"|"pause", "origine": "david"|"didier"} ; les gestes
# (aller_voir, tourner, avancer, tour_de) gagnent le même champ. « david » = un ORDRE (mot
# d'arrêt, console, geste né d'un tour humain) ; « didier » = une PROPOSITION (le « marche:
# stop » interprété par le LLM ou la continuation d'une tâche, les reprises et lubies du
# sélecteur). Seul un ordre pose ou lève le verrou du sélecteur. Le régisseur n'ignore JAMAIS un
# « stop » ; il retient l'origine de l'arrêt vocal en cours : un « go » « didier » ne lève qu'un
# arrêt « didier », un « go » « david » lève tout ; hors séance, il refuse seulement les GESTES
# « didier » (règle R1 du 25/11, après la relecture adverse du lot S1).
# Les anciennes formes (chaîne "stop"/"go"/"pause", objet sans `origine`) restent acceptées
# et sont lues « david » (sens sûr pour un stop : il verrouille) — cf. lire_chat_move.
CHAT_MOVE_TOPIC = "rehearsal/chat_move"
CHAT_MOVE_ORIGINE_DAVID = "david"
CHAT_MOVE_ORIGINE_DIDIER = "didier"
CHAT_MOVE_ORIGINES = (CHAT_MOVE_ORIGINE_DAVID, CHAT_MOVE_ORIGINE_DIDIER)
# Ordres de marche (valeur de `cmd`, ou ancienne forme chaîne).
CHAT_MOVE_STOP = "stop"
CHAT_MOVE_GO = "go"
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
# Lot M3 (spec-aller-voir.md §8.2) : « faire le tour de X » en UN geste
# (David, 01/11 : pivot + 1 m + relance à chaque réplique, « super
# laborieux »). {"cmd": "tour_de", "objet": "<texte>", "sens": "gauche"|
# "droite"} (sens absent = "gauche"). Chaîne gravée des deux côtés.
CHAT_MOVE_TOUR_CMD = "tour_de"
# Lot « texte raccord » (18/11, séance de 21:35, « il y a une lettre sur le banc, tu pourrais
# regarder ») : payload JSON "pause" = « regarde ça » — s'arrêter, regarder (le regard part de la
# bouche sur `look`), puis reprendre la route. Consommateur : le sélecteur de jeu (jeu:=true), qui
# relaie « stop » sans verrou puis « go » après un silence tiré dans [reprise.min_s, reprise.max_s]
# (lot S1, 25/11 : une seule reprise) ; le régisseur seul (jeu:=false) et le relais dégradé la
# prennent pour un « stop » (sens sûr, sans reprise). Chaîne gravée des deux côtés
# (conversation.PAUSE_CMD de chat_node).
CHAT_MOVE_PAUSE = "pause"
CHAT_MOVE_MARCHE = (CHAT_MOVE_STOP, CHAT_MOVE_GO, CHAT_MOVE_PAUSE)
# Sens du tour -> orbit_dir de route_goto (+1 = trigonométrique, + = gauche
# comme TURN_DEG_COMPAT : l'objet reste à GAUCHE de Didier). Autre valeur ->
# refus « invalid » (jamais deviné) ; absent -> TOUR_SENS_DEFAUT.
TOUR_SENS = {"gauche": 1, "droite": -1}
TOUR_SENS_DEFAUT = "gauche"

# --- « Aller voir » (lot M1, spec-aller-voir.md) — SIM-ONLY -----------------------
# Vocabulaire d'objets (régisseur -> chat_node) : StringTime LATCHÉ (TRANSIENT_
# LOCAL depth 1, des DEUX côtés), publié au démarrage du régisseur, JSON liste
# [{"name", "desc", "x", "y"}] dans l'ordre de l'itinéraire. Gravé des deux
# côtés ; x, y (ancre du POI, m) ajoutés au lot A1 pour le sélecteur de jeu —
# chat_node ne lit que name/desc.
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
# RÉPONSE à un geste demandé (15/11, défaut vu en séance : « fais le tour de
# l'éléphant » refusé sans tour, Didier affirmait l'avoir fait) : StringTime
# JSON {"demande": <le dict de chat_move tel que reçu>, "effect": …,
# "reason": <sous-raison | null>, "name": <nom de l'ordre accepté | null>,
# "source": "director" | "jeu"}, VOLATILE. `name` (régisseur, accepted) = le
# `name` que route_goto_result renverra : seule l'issue de CET ordre finit la
# demande (séance du 15/11 21:21 : l'arrivée d'un ancien « aller voir
# elephant » était prise pour la fin du « tour de elephant »).
#  - source "director" : UNE réponse par geste arbitré (aller_voir, tour_de,
#    tourner, avancer ; jamais go/stop), effect = celui du journal
#    (accepted | unknown | no_position | no_tour | invalid | route_off_by_david |
#    no_pose | too_far | hors_seance — lot S1 : geste d'origine « didier » hors séance),
#    reason = sous-raison d'invalid (illisible, hors_bornes, recul, sens) ;
#  - source "jeu" (sélecteur didier_jeu, jeu:=true) : la demande de la bouche
#    n'a PAS été transmise (effect "dropped", reason = CHAT_MOVE_REPLY_JEU_REASONS)
#    ou le régisseur s'est tu (effect "no_reply").
# Consommateurs : chat_node (didier_vision.ai.move_task : un refus devient une
# fin de geste ÉCHOUÉE, dite en personnage) et le sélecteur (fin d'engagement).
# Le chat apparie par ÉGALITÉ de `demande` avec le geste qu'il a émis (le
# sélecteur relaie la demande de la bouche telle quelle). Nom gravé des deux
# côtés (CHAT_MOVE_REPLY_TOPIC de chat_node).
CHAT_MOVE_REPLY_TOPIC = "rehearsal/chat_move_reply"
CHAT_MOVE_REPLY_ACCEPTED = "accepted"
CHAT_MOVE_REPLY_DROPPED = "dropped"
CHAT_MOVE_REPLY_NO_REPLY = "no_reply"
# Raisons d'un « dropped » du sélecteur (codes gravés des deux côtés : le chat
# les traduit en clair, didier_vision.ai.move_task.REFUSAL_REASONS).
# « pas_ici » / « hors_atteinte » (lot O1, 18/11 ; remplacent « trop_loin » du 15/11) :
# aller_voir / tour_de de la bouche vers un objet du tableau des objets qui n'est pas
# `atteignable` — connu mais ni en vue ni à portée (pas_ici), ou en vue mais trop loin ou
# trop incertain (hors_atteinte) ; la réponse porte alors "distance_m" (m, 0,1) et "cote"
# (devant | gauche | droite | derriere) pour que Didier dise où il est. Le chat produit les
# MÊMES codes quand sa propre garde refuse (source "chat").
# Lot S1 (25/11) : un ORDRE de David n'est plus refusé que pour « arrete » (verrou de David),
# « sans_superviseur », « pas_ici » / « hors_atteinte » (impossible) — « fatigue », « trop_tot »
# et « ignore » ne servaient qu'à pondérer une demande de la bouche : retirés. « pas_retenu » ne
# sert plus qu'à une PROPOSITION de geste (origine « didier »), qu'aucun producteur n'émet en S1.
# Les refus « qui donnent du jeu » (étude assainissement §8.1, réponse 2) reviendront avec le
# régisseur LLM (lot S4), seul à pouvoir les dire.
CHAT_MOVE_REPLY_JEU_REASONS = ("arrete", "sans_superviseur", "pas_retenu", "degrade", "pas_ici",
                               "hors_atteinte")
# Distance de jeu : Didier s'arrête à ce rayon du CENTRE de l'objet (m) — un PLANCHER : la
# distance d'arrêt réelle tient compte de la TAILLE de l'objet (director.standoff_pour, revue O1
# du 19/11 : le banc, 1,1 m d'emprise, était touché à 1,5 m du centre — 1,1 + 0,4 de Didier) :
#   standoff = max(GOTO_STANDOFF_M, emprise + GOTO_DIDIER_RAYON_M + GOTO_MARGE_M,
#                  emprise + garde du corps sûr + GOTO_MARGE_M)   # A0-4, 22/11 : hors bande ARRET
#   (garde = caisse.x_avant + zones.marge_arret_m, lus dans les réglages du corps sûr)
GOTO_STANDOFF_M = 1.5
# Rayon balayé par Didier autour de son centre (m) : roulette arrière à 0,45 m (dadou_robot.urdf
# .xacro, caster_offset_x) — c'est elle qui frôle l'objet quand Didier pivote pour lui faire face.
GOTO_DIDIER_RAYON_M = 0.5
# Marge entre Didier et l'objet (m) : la tolérance d'arrivée de goto.py (arrive_tol_m 0,3 : il
# peut s'arrêter 0,3 m AVANT ou APRÈS le point visé) + 0,2 m de jeu réel.
GOTO_MARGE_M = 0.5
# Emprise PRÉSUMÉE d'un objet de taille inconnue (m) — borne prudente : POI sans géométrie de
# collision, objet vu par la caméra (O2). Standoff qui en découle : 1,5 + 0,90 + 0,5 = 2,9 m en sim
# (O1 : 1,5 + 0,5 + 0,5 = 2,5 m).
GOTO_EMPRISE_INCONNUE_M = 1.5
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
# « Faire le tour » (lot M3, §8) : orbite d'un cercle (centre, rayon) lu dans
# config/<itinéraire>_tours.yaml, GÉNÉRÉ depuis la géométrie de COLLISION du
# monde par tools/compute_tours.py (l'ancre d'un POI n'est pas le centre de
# l'objet). Ordre route_goto {"name", "orbit_x", "orbit_y", "orbit_r",
# "orbit_dir": 1 (gauche, trigo) | -1 (droite, horaire)}.
#  - rayon de tour = rayon de l'objet + ce dégagement (0,4 m de demi-largeur
#    de Didier + 0,6 m de marge : pas d'évitement, le cercle doit être libre) ;
TOUR_CLEARANCE_M = 1.0
#  - bornes du rayon (outil ET parse_order) : sous 1,5 m, l'orbite d'un 50 kg
#    devient un pivot qui frôle l'objet ; au-delà de 6 m, ce n'est plus « le
#    tour de l'objet » (on traverserait la rue) -> pas de tour ;
TOUR_MIN_RADIUS_M = 1.5
TOUR_MAX_RADIUS_M = 6.0
#  - vitesse de croisière sur le cercle (m/s), sous celle du fader × max_lin :
#    une courbe serrée se prend lentement ;
TOUR_CRUISE_MS = 0.35
#  - vitesse PLANCHER retenue pour le délai : GOTO_TIMEOUT_S + 2πr / TOUR_MIN_MS
#    (à fader bas, le tour doit pouvoir finir ; au-delà, abandon « timeout ») ;
TOUR_MIN_MS = 0.1
#  - écart radial max |d − r| pendant l'orbite : au-delà, Didier n'est plus
#    sur son cercle (poussé, bloqué, téléporté) -> abandon « off_track ».
TOUR_MAX_DEV_M = 1.0

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


def lire_chat_move(payload):
    """Une demande de chat_move DÉCODÉE (JSON ou brut) -> (demande, origine) — la règle de
    lecture UNIQUE du régisseur, du sélecteur et de son relais dégradé (lot S1, 25/11).
    - marche (chaîne "stop"/"go"/"pause", ou objet dont `cmd` en est une, casse et espaces
      normalisés : " STOP" est un stop — sens sûr) -> demande = la chaîne normalisée ; geste
      (tout autre objet) -> demande = l'objet TEL QUEL (`origine` comprise : la réponse au
      geste est appariée par égalité) ; autre valeur -> elle-même (invalide) ;
    - origine : `origine` de l'objet ; absente (ancienne forme) -> "david" ; présente mais hors
      CHAT_MOVE_ORIGINES -> None. Au consommateur de trancher None : un « stop » est alors lu
      « david » (un arrêt n'est jamais refusé), toute autre demande refusée."""
    if isinstance(payload, dict):
        origine = payload.get("origine", CHAT_MOVE_ORIGINE_DAVID)
        origine = origine if origine in CHAT_MOVE_ORIGINES else None
        cmd = _marche_normalisee(payload.get("cmd"))
        if cmd in CHAT_MOVE_MARCHE:
            return cmd, origine
        return payload, origine
    cmd = _marche_normalisee(payload)
    return (cmd if cmd in CHAT_MOVE_MARCHE else payload), CHAT_MOVE_ORIGINE_DAVID


def _marche_normalisee(valeur):
    """Chaîne rognée et en minuscules (la marche du contrat n'a que des minuscules) ; tout
    autre type tel quel."""
    return valeur.strip().lower() if isinstance(valeur, str) else valeur


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
            f"didier_rehearsal refuse de démarrer : ROS_DOMAIN_ID={raw!r}, attendu {SIM_DOMAIN_ID} "
            "(domaine de la SIMULATION — 42 est le vrai robot)")
    return domain
