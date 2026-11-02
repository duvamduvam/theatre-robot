"""Les organes de Didier : chaque nom est À LA FOIS le topic StringTime qui le
commande, la piste d'une séquence JSON et la clé du payload correspondant.

Critère d'appartenance (vérifiable, relevé le 2026-11-02) : topic consommé par
un node ACTIONNEUR du robot (servo_node, lights_node, wheels_node, audio_node,
relays_node). L'étude d'architecture annonçait « 11 organes » sans en donner la
liste ; ce critère en donne 10 — SYSTEM (consommé par system_node) n'est pas un
organe, c'est l'administration de la machine.

Valeurs reprises À L'IDENTIQUE de dadou_utils_ros/utils_static.py : les
modifier casse le robot, la télécommande et les séquences JSON en même temps.
"""

AUDIO = 'audio'
FACE = 'face'
LEFT_ARM = 'left_arm'
LEFT_EYE = 'left_eye'
NECK = 'neck'
RELAY = 'relay'
RIGHT_ARM = 'right_arm'
RIGHT_EYE = 'right_eye'
ROBOT_LIGHTS = 'robot_lights'
WHEELS = 'wheels'

# Ordre stable (alphabétique) : sert aux itérations et au test d'inventaire.
ORGANS = (AUDIO, FACE, LEFT_ARM, LEFT_EYE, NECK, RELAY, RIGHT_ARM, RIGHT_EYE,
          ROBOT_LIGHTS, WHEELS)
