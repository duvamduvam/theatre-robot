"""Parsing du payload roues, indépendant de ROS (stdlib uniquement).

Reproduit les formes acceptées par la branche WHEELS de Wheels.update()
(robot/actions/wheels.py) mais en pur : pas d'accès matériel, juste la
traduction payload JSON -> paire (gauche, droite) normalisée [-1, 1], ou
la constante STOP, ou None si non reconnu / non pertinent.

Les constantes du protocole StringTime sont dupliquées ici depuis
dadou_utils_ros.utils_static : ce sont des clés JSON FIGÉES (47 fichiers
séquences en dépendent) et robot_drive doit rester autonome — le conteneur
de simulation n'embarque pas dadou_utils_ros. Un test unitaire
(test_wheels_payload.py) vérifie qu'elles ne dérivent pas des originales.
"""

WHEELS = "wheels"
STOP = "stop"
FORWARD = "forward"
BACKWARD = "backward"
LEFT = "left"
RIGHT = "right"
SPEED = "speed"


def payload_to_pair(payload: dict) -> tuple | str | None:
    """msg JSON (déjà json.loads) -> (gauche, droite) dans [-1, 1], STOP, ou None."""
    if WHEELS not in payload:
        return None

    wheels = payload[WHEELS]

    if wheels == STOP:
        return STOP

    if isinstance(wheels, dict):
        # SPEED (réglage du plafond PWM) est traité par Wheels.update() lui-même,
        # pas ici : pas de consigne roue à en tirer.
        if SPEED in wheels:
            return None
        if LEFT in wheels and RIGHT in wheels:
            # Les dicts arrivent en pourcents (-100..100), comme côté PWM.
            return wheels[LEFT] / 100, wheels[RIGHT] / 100
        return None

    if isinstance(wheels, (list, tuple)) and len(wheels) == 2:
        left, right = wheels
        left = max(-1.0, min(1.0, left))
        right = max(-1.0, min(1.0, right))
        return left, right

    if wheels == FORWARD:
        return 0.5, 0.5
    if wheels == BACKWARD:
        return -0.5, -0.5
    if wheels == LEFT:
        return -0.5, 0.5
    if wheels == RIGHT:
        return 0.5, -0.5

    # Formats vus sur le topic mais non pilotables ici :
    #   - {WHEELS: {SPEED: pct}} -> réglage vitesse, voir payload_to_speed.
    #   - "UP" / "down" (D-pad manette, boutons UP/DOWN de la télécommande) : le
    #     robot legacy ne les traite pas non plus, on ne les invente pas ici.
    return None


def payload_to_speed(payload: dict) -> float | None:
    """msg JSON ré-emballé {WHEELS: valeur} -> facteur de vitesse 0..1, ou None.

    Format réel de la télécommande : {WHEELS: {SPEED: pct}} (pct entier 0..100,
    slider "vitesse"). Côté legacy ce message règle le plafond PWM (max_pwm) à
    pct% de la course ; ici on renvoie ce pourcentage en facteur 0..1 que le
    bridge applique en multiplicateur sur les Twist sortants.
    """
    if WHEELS not in payload:
        return None

    wheels = payload[WHEELS]
    if isinstance(wheels, dict) and SPEED in wheels:
        try:
            pct = float(wheels[SPEED])
        except (TypeError, ValueError):
            return None
        return max(0.0, min(1.0, pct / 100))

    return None
