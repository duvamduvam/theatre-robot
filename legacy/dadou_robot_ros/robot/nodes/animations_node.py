#!/usr/bin/env python3
import json
import logging
import logging.config

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy
from std_msgs.msg import String

from dadou_utils_ros.logging_conf import LoggingConf
from dadou_utils_ros.utils_static import RELAY, AUDIO, FACE, ROBOT_LIGHTS, NECK, LEFT_EYE, \
    RIGHT_EYE, LEFT_ARM, RIGHT_ARM, ANIMATION, ANIMATION_STATE, LOGGING_FILE_NAME, DURATION, STOP, WHEELS
from robot.files.robot_json_manager import RobotJsonManager
from robot.nodes.payload import decode
from robot.robot_config import config
from robot.robot_static import TICK_PERIOD_S
from robot.sequences.animation_manager import AnimationManager
from robot_interfaces.msg._string_time import StringTime


PUBLISHER_LIST = [AUDIO, FACE, ROBOT_LIGHTS, RELAY, NECK, LEFT_EYE, RIGHT_EYE, LEFT_ARM, RIGHT_ARM, WHEELS]

# Pistes dotées d'un deadman (arrêt de secours si ce node meurt en pleine
# animation) : elles reçoivent le temps RESTANT (remaining_ms) et non la durée
# figée, pour armer une échéance d'arrêt absolue côté action.
#  - WHEELS : sans ça, un crash laisserait les roues rouler (comportement
#    historique, INCHANGÉ).
#  - servos (cou/yeux/bras) : sans ça, un mode random tournerait pour toujours
#    (ajout 2026-07-11 -- les servos n'avaient aucun deadman).
DEADMAN_KEYS = (WHEELS, NECK, LEFT_EYE, RIGHT_EYE, LEFT_ARM, RIGHT_ARM)


class AnimationsNode(Node):
    def __init__(self):

        node_name = ANIMATION+"_node"
        super().__init__(node_name)
        logging.config.dictConfig(LoggingConf.get(config[LOGGING_FILE_NAME], node_name))

        robot_json_manager = RobotJsonManager(config)
        self.animations_manager = AnimationManager(config, robot_json_manager)

        self.action_publishers = {}
        for p in PUBLISHER_LIST:
            self.action_publishers[p] = self.create_publisher(StringTime, p, 10)

        # animation_state : topic d'ÉTAT (pas une piste d'actionneur) latché
        # TRANSIENT_LOCAL -- un abonné démarré en cours de spectacle (gaze
        # lancé à la main, cf. CLAUDE.md) reçoit l'état courant immédiatement
        # au lieu d'attendre la prochaine transition. depth=1 : seul le
        # dernier état compte, pas d'historique (docs/etude-arbitrage-actionneurs.md lot B).
        self.state_publisher = self.create_publisher(
            StringTime, ANIMATION_STATE,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self._published_state = None  # mémorise le dernier état publié (anti-spam transition)

        logging.info("Starting {}".format(node_name))

        self.subscription = self.create_subscription(
            StringTime,
            ANIMATION,
            self.listener_callback,
            10)

        self.timer = self.create_timer(TICK_PERIOD_S, self.timer_callback)

        # Publie l'état de repos "" dès le boot : un abonné latché voit
        # immédiatement qu'aucune séquence ne joue, sans attendre un premier
        # play/stop.
        self._publish_state()

    def listener_callback(self, ros_msg):
        logging.info("input : {}".format(ros_msg))
        value = decode(ros_msg, ANIMATION)
        if value is None:
            return
        animation_msg = {ANIMATION: value}
        if ros_msg.time != 0:
            animation_msg[DURATION] = ros_msg.time
        animations_msg = self.animations_manager.update(animation_msg)
        self.send_msgs(animations_msg)
        # force=True : un (re)démarrage de séquence doit TOUJOURS être republié,
        # même à nom inchangé (ex. « parle » reproclamé par le chat à chaque
        # phrase) : les abonnés arment une PÉREMPTION sur msg.time (garde-fou
        # façon deadman si ce node meurt en pleine séquence) — sans
        # re-publication, leur garde-fou expirerait en pleine séquence vivante.
        self._publish_state(force=True)

    def timer_callback(self):
        # Logique à exécuter en continu ici
        try:
            animations_msg = self.animations_manager.process()
            if animations_msg:
                self.send_msgs(animations_msg)
            self._publish_state()
        except Exception as e:
            logging.error(e, exc_info=True)

    def _publish_state(self, force=False):
        # Publie l'état d'activité SEULEMENT sur transition (démarrage,
        # changement de séquence, arrêt) : le topic est latché, les abonnés
        # tardifs reçoivent le dernier état sans qu'on inonde à 20 Hz.
        # force (redémarrage à nom identique) ne vaut que pour un état ACTIF :
        # re-forcer le repos "" n'apporterait rien aux abonnés.
        state = self.animations_manager.state_name()
        if state == self._published_state and not (force and state):
            return
        msg = StringTime()
        msg.msg = json.dumps(state)
        if state:
            # remaining_ms : les abonnés s'en servent pour PÉRIMER l'état si la
            # fin de séquence (le "" attendu) ne vient jamais (crash du node).
            msg.time = self.animations_manager.remaining_ms()
        self.state_publisher.publish(msg)
        self._published_state = state

    def send_msgs(self, animations_msg):
        # debug : appelé à chaque tick actif (20 Hz) -> boucle chaude, écriture SD.
        logging.debug("animations msg to publish {}".format(animations_msg))

        if ANIMATION in animations_msg and not animations_msg[ANIMATION]:
            # Arrêt d'animation = événement rare : on le garde en info.
            logging.info("send animations stop")
            msg = StringTime()
            msg.msg = json.dumps(STOP)
            for p in self.action_publishers:
                self.action_publishers[p].publish(msg)
            return

        if isinstance(animations_msg, dict):
            for k, v in animations_msg.items():
                if k in self.action_publishers:
                    # debug : une ligne par piste ET par tick actif -> boucle chaude.
                    logging.debug("publish {} in {}".format(v, k))
                    msg = StringTime()
                    if ANIMATION in animations_msg:
                        msg.anim = animations_msg[ANIMATION]
                    msg.msg = json.dumps(v)
                    if DURATION in animations_msg and animations_msg[DURATION] != 0:
                        msg.time = animations_msg[DURATION]
                    # Roues ET servos ont besoin du temps restant pour armer leur
                    # deadman : sans lui, un crash de ce node en pleine animation
                    # les laisserait tourner (roues qui roulent, random servo sans
                    # fin). La marge d'arrêt est ajoutée côté action.
                    if k in DEADMAN_KEYS and msg.anim:
                        msg.time = self.animations_manager.remaining_ms()
                    self.action_publishers[k].publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = AnimationsNode()
    try:
        while rclpy.ok():
            try:
                rclpy.spin_once(node)
            except Exception as e:
                logging.error(e, exc_info=True)
    except Exception as e:
        logging.error(e, exc_info=True)
    finally:
        rclpy.shutdown()

if __name__ == '__main__':
    main()
