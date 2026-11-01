"""Logique pure de simulation des servos (aucune dépendance ROS/Gazebo).

Reproduit le comportement OBSERVABLE de robot/actions/servo.py (classe Servo,
méthodes update()/process()) SANS matériel I2C/PCA9685 : mêmes payloads que
les topics StringTime des servos (neck, left_arm, right_arm, left_eye,
right_eye -- valeur 0-99, "stop", {"default": x} ou keyframe
{"mode": "random", ...}), même sémantique d'arbitrage random.

Découpage volontaire (même philosophie que leds_logic.py / gaze_control.py) :
 - ICI : toute la logique (armement random, tirages, sortie sur durée), avec
   l'horloge ET le générateur aléatoire injectés (jamais time.time()/random
   module global) -- déterministe et testable sans ROS ni sleep, cf.
   robot/tests/unit/test_servos_sim_logic.py.
 - DANS le node (scripts/servos_sim_node) : uniquement les entrées/sorties ROS
   (JSON <-> StringTime, Float64 en radians).

DIVERGENCE RÉSOLUE (2026-07-11) avec robot/actions/servo.py : elle est
désormais alignée sur ce module. Historique -- Servo.process() lisait
`self.random_duration` armé par `if RANDOM_DURATION in msg:` où `msg` était le
dict TOP-LEVEL passé à update() (= {servo_type: {...}}), et non
`msg[servo_type]`. Une clé "random duration" placée normalement -- DANS le dict
du servo, comme le montrent les vraies séquences JSON et
robot/tests/sandbox/actions/test_servos.py
(`{NECK: {MODE: RANDOM, RANDOM_DURATION: 30000, ...}}`) -- n'était donc JAMAIS
lue par le vrai code (bug dormant : aucune séquence de spectacle n'utilisait
"random duration"). Depuis le passage du vrai Servo à la rampe linéaire, il lit
la clé au bon endroit (`msg[servo_type].get(RANDOM_DURATION, 0)`) et applique la
MÊME sémantique de sortie que ce module (retour NORMAL à l'échéance, position
laissée où le dernier tirage l'a mise). ServoSim reste la référence de
sémantique ; les deux implémentations doivent maintenant coïncider (à la rampe
matérielle près, absente en sim).
"""
import math
import random

# Clés JSON des payloads servo -- MÊMES valeurs que dadou_utils_ros.utils_static
# (MODE, RANDOM, RANDOM_MOVE_MIN, ...), dupliquées ici en toutes lettres pour ne
# PAS importer dadou_utils_ros : robot_sim reste un paquet AUTONOME (même règle
# que robot_drive et leds_sim_node -- aucun import robot.*/dadou_utils_ros).
MODE = "mode"
RANDOM = "random"
NORMAL = "normal"
RANDOM_MOVE_MIN = "random move min"
RANDOM_MOVE_MAX = "random move max"
RANDOM_TIME_MIN = "random time min"
RANDOM_TIME_MAX = "random time max"
RANDOM_DURATION = "random duration"
DEFAULT = "default"
STOP = "stop"

INPUT_MIN = 0
INPUT_MAX = 99

# Bornes des joints servo (radians) -- source : conf/ros2_dependencies/
# robot_description/urdf/dadou_robot.urdf.xacro, propriétés xacro
# `servo_lower`/`servo_upper` (= -pi/2 / +pi/2), appliquées aux joints `neck`,
# `${side}_arm`, `${side}_eye` (limit lower/upper, lignes ~72-73/198/220/243
# au 2026-07). Les 5 joints partagent AUJOURD'HUI les mêmes bornes de
# position (seuls effort/velocity diffèrent pour les yeux) ; on garde un
# dict par joint plutôt qu'une constante unique : rien ne garantit que la
# CAO ne les fera pas diverger un jour (ex. amplitude réduite pour les yeux).
JOINT_LIMITS = {
    "neck": (-math.pi / 2, math.pi / 2),
    "left_arm": (-math.pi / 2, math.pi / 2),
    "right_arm": (-math.pi / 2, math.pi / 2),
    "left_eye": (-math.pi / 2, math.pi / 2),
    "right_eye": (-math.pi / 2, math.pi / 2),
}

_REQUIRED_RANDOM_KEYS = (RANDOM_MOVE_MIN, RANDOM_MOVE_MAX, RANDOM_TIME_MIN, RANDOM_TIME_MAX)


def pos99_to_radians(pos, joint_min_rad, joint_max_rad):
    """Mapping linéaire consigne servo 0-99 -> bornes du joint (radians).
    0 -> joint_min_rad, 99 -> joint_max_rad. Même formule que
    robot.move.gaze_control.consigne_to_radians, généralisée aux bornes
    passées en paramètre (au lieu de +-pi/2 codé en dur) -- gaze_control reste
    la référence pour le joint `neck` en mode gaze, ce module la réutilise
    pour les 5 servos rejoués depuis les animations.

    Bornée : une consigne hors 0-99 (ne devrait pas arriver, ServoSim clampe
    déjà en interne) est ramenée dans la plage avant mapping -- garde-fou.
    """
    pos = max(INPUT_MIN, min(INPUT_MAX, pos))
    return joint_min_rad + (pos / float(INPUT_MAX)) * (joint_max_rad - joint_min_rad)


class ServoSim:
    """Un servo simulé (instancier une fois par servo : neck, left_arm, ...).

    update(payload, now_ms) : à appeler à CHAQUE message StringTime reçu.
    tick(now_ms) : à appeler à cadence FIXE (ex. 10 Hz, comme servo_node.py
      réel) -- renvoie la position 0-99 (float) à publier, ou None si rien de
      neuf (anti-spam interne : la sortie ne change que sur un mouvement
      réel, contrairement au vrai Servo qui écrit pwm_channel.angle en
      continu -- ici il n'y a pas de matériel à réécrire en boucle).
    """

    def __init__(self, default_pos=50, now_ms=0, rng=None):
        self.default_pos = float(default_pos)
        self.position = self.default_pos
        self.mode = NORMAL
        # RNG injecté : jamais le module `random` global directement, pour
        # pouvoir seeder/rejouer un tirage en test (cf. TimeUtils/horloge,
        # même logique d'injection que gaze_control/leds_logic).
        self.rng = rng if rng is not None else random.Random()
        # Position modifiée depuis le dernier tick() non consommé -- anti-spam :
        # tick() ne renvoie une valeur que sur un VRAI changement.
        self._dirty = False

        # État random -- mêmes noms que robot/actions/servo.py (audit croisé facile).
        self.random_move_min = 0
        self.random_move_max = 0
        self.random_time_min = 0
        self.random_time_max = 0
        self.random_last_time = now_ms
        self.random_next_time = 0
        # None = pas de random_duration armé (PAS 0 : 0 est une horloge sim
        # valide -- un random armé pile à now_ms=0 ne doit pas être confondu
        # avec "non armé", sinon la sortie auto ne se déclencherait jamais
        # pour une animation qui démarre à l'instant zéro de la simulation).
        self.random_start_time = None
        self.random_duration = 0

    def _set_position(self, value):
        value = max(INPUT_MIN, min(INPUT_MAX, float(value)))
        if value != self.position:
            self._dirty = True
        self.position = value

    def update(self, payload, now_ms):
        """payload : int/float 0-99 (ou 0-1, ramené *100 -- même quirk que
        Servo.update/set_angle : `if 0 <= value <= 1: value = value*100`),
        "stop" (retour à default_pos), {"default": x} (change ET applique la
        position de repos), ou {"mode": "random", "random move min/max": ..,
        "random time min/max": .., "random duration": .. (optionnel)}.
        """
        if payload == STOP:
            # Même règle que Servo.update : stop coupe le random en cours ET
            # ramène à la position de repos (pas juste un arrêt sur place).
            self._set_position(self.default_pos)
            self.mode = NORMAL
            return

        if isinstance(payload, dict) and DEFAULT in payload:
            default_angle = float(payload[DEFAULT])
            self.default_pos = default_angle
            self._set_position(default_angle)
            return

        if isinstance(payload, dict) and MODE in payload:
            self._arm_random(payload, now_ms)
            return

        if isinstance(payload, (int, float)) and not isinstance(payload, bool):
            value = payload * 100 if 0 <= payload <= 1 else payload
            self._set_position(value)
            self.mode = NORMAL
        # UP/DOWN et payloads non reconnus : non repris ici -- jamais utilisés
        # par les séquences JSON d'animation (seulement par la télécommande
        # manuelle en direct), hors scope du rejeu d'animation en sim.

    def _arm_random(self, payload, now_ms):
        """Traite une keyframe {"mode": "random", ...} : arme le tirage
        périodique (ou ignore, cf. règles ci-dessous). Extrait de update()
        pour la lisibilité (une seule responsabilité par branche)."""
        # "let the last instruction finish" (cf. Servo.update) : un ordre
        # random reçu pendant un random déjà actif est IGNORÉ -- seuls
        # stop/valeur numérique/default reprennent la main immédiatement.
        if self.mode == RANDOM:
            return
        if payload[MODE] != RANDOM:
            return  # seul le mode "random" est reconnu (pas d'autre mode côté servo)
        if not all(k in payload for k in _REQUIRED_RANDOM_KEYS):
            return  # keyframe malformée : ignorée, comme Servo.update (log + no-op)
        self.mode = RANDOM
        self.random_move_min = payload[RANDOM_MOVE_MIN]
        self.random_move_max = payload[RANDOM_MOVE_MAX]
        self.random_time_min = payload[RANDOM_TIME_MIN]
        self.random_time_max = payload[RANDOM_TIME_MAX]
        # random_duration=0 => pas de sortie auto (comportement par défaut de
        # Servo : self.random_duration ne vaut jamais rien tant que la clé
        # n'est pas fournie -- ici on lit la clé correctement, cf. note de
        # divergence en tête de fichier).
        self.random_duration = payload.get(RANDOM_DURATION, 0)
        self.random_start_time = now_ms if self.random_duration else None
        self.random_last_time = now_ms
        self.random_next_time = self.rng.randint(self.random_time_min, self.random_time_max)

    def tick(self, now_ms):
        """A appeler à cadence fixe. Renvoie la position 0-99 (float) à
        publier, ou None si rien de nouveau ce tick."""
        if self.mode == RANDOM:
            if self.random_start_time is not None and (now_ms - self.random_start_time) >= self.random_duration:
                # Sortie auto : on repasse en mode normal SANS retirer un
                # dernier mouvement ce tick (simplification volontaire --
                # le vrai Servo.process() peut, par un artefact d'ordre des
                # tests, encore appliquer un tirage sur ce même appel ; ça
                # ressemble à un accident de son code plutôt qu'un choix
                # voulu, pas reproduit ici). La position reste où le dernier
                # tirage l'a laissée (pas de retour à default_pos -- "stop"
                # est le seul chemin qui recentre).
                self.mode = NORMAL
            elif (now_ms - self.random_last_time) >= self.random_next_time:
                self._set_position(self.rng.randint(self.random_move_min, self.random_move_max))
                self.random_last_time = now_ms
                self.random_next_time = self.rng.randint(self.random_time_min, self.random_time_max)

        if self._dirty:
            self._dirty = False
            return self.position
        return None
