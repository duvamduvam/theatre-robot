"""Noms de topics du parc Didier — TOUJOURS relatifs (jamais de « / » initial).

Pourquoi relatifs : au lot L1b, chaque robot aura son namespace (`/didier/…`) ;
un nom absolu y échapperait. Sans namespace (situation actuelle), un nom
relatif se résout à l'identique (`vision/person` -> `/vision/person`) : passer
de l'absolu au relatif ne change RIEN sur le fil aujourd'hui.

Les organes (organs.py) sont aussi des topics : ils sont ré-exportés ici pour
qu'un consommateur trouve TOUS les noms de topics au même endroit.
"""

from theatre_contrats.organs import (  # noqa: F401  (ré-export voulu)
    AUDIO, FACE, LEFT_ARM, LEFT_EYE, NECK, RELAY, RIGHT_ARM, RIGHT_EYE,
    ROBOT_LIGHTS, WHEELS,
)

# ---------------------------------------------------------------- StringTime hors organes
ANIMATION = 'animation'
# État d'activité des animations (arbitrage amont, étude 2026-07-12 côté robot :
# docs/etude-arbitrage-actionneurs.md). Publié LATCHÉ par animations_node
# (qos.latched() des DEUX côtés — un abonné volatile ne reçoit pas l'état) :
# msg = json.dumps(nom de la séquence en cours) ou json.dumps("") au repos.
# Consommé par les comportements autonomes (gaze côté robot, chat côté vision)
# qui se taisent tant qu'une séquence a la main sur visage + tête.
ANIMATION_STATE = 'animation_state'
EXPRESSION = 'expression'
# Lumières de SCÈNE (appareil lights), à ne pas confondre avec ROBOT_LIGHTS.
LIGHTS = 'lights'
SPEAK = 'speak'
SYSTEM = 'system'

# ---------------------------------------------------------------- perception (Pi vision -> robot)
# geometry_msgs/PointStamped, x=azimut [-1..1], y=élévation [-1..1],
# z=confiance [0..1] ; silence = personne perdue. GELÉ (gaze_follower).
VISION_PERSON = 'vision/person'
# geometry_msgs/PointStamped, x=azimut, y=HAUTEUR de silhouette [0..1] (proxy
# de distance), z=confiance ; silence = perdue. Consommé par person_follower
# et reflection_node.
VISION_PERSON_BOX = 'vision/person_box'
# std_msgs/String '<hostname> uptime=<s>s' toutes les 5 s : preuve de vie du Pi vision.
VISION_STATUS = 'vision/status'
