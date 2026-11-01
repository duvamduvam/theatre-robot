import logging
import random

from dadou_utils_ros.utils.time_utils import TimeUtils
from robot.robot_static import STOP_ANIMATION_KEYS, TYPES, RANDOM_ANIMATION_LOW, \
    RANDOM_ANIMATION_HIGH, STOP_KEY, RANDOM_TYPE
from dadou_utils_ros.utils_static import ANIMATION, AUDIO, AUDIOS, KEY, NECK, FACE, FACES, \
    LIGHTS, WHEELS, NAME, DURATION, RANDOM, SEQUENCES_DIRECTORY, LEFT_ARM, RIGHT_ARM, LEFT_EYE, \
    RIGHT_EYE, ROBOT_LIGHTS, TYPE
from robot.actions.abstract_json_actions import AbstractJsonActions
from robot.sequences.track import Track
from robot.sequences.random_animation_start import RandomAnimationStart


class AnimationManager(AbstractJsonActions):

    def __init__(self, config, json_manager):
        # État par instance (était au niveau classe = partagé entre instances,
        # piège Python). Mêmes valeurs par défaut ; random_duration est réécrit
        # plus bas avec un tirage aléatoire.
        self.current_key = None
        self.playing = False
        self.start = False
        self.last_time = 0
        self.timeout = 0
        self.random_duration = 0
        self.last_random = 0
        self.datas = None
        self.duration = 0
        self.audios_animation = None
        self.left_arm_animation = None
        self.right_arm_animation = None
        self.left_eye_animation = None
        self.right_eye_animation = None
        self.necks_animation = None
        self.faces_animation = None
        self.lights_animation = None
        self.wheels_animation = None
        self.current_animation = None

        self.config = config
        super().__init__(config=config, json_manager=json_manager, action_type=ANIMATION, sequence_dir=self.config[SEQUENCES_DIRECTORY])
        self.stop_keys = self.config[STOP_ANIMATION_KEYS]
        self.random_animation_sequence = []
        self.random_duration = random.randint(self.config[RANDOM_ANIMATION_LOW], self.config[RANDOM_ANIMATION_HIGH])
        RandomAnimationStart.value = TimeUtils.current_milli_time()
        logging.debug("random duration time {}".format(self.random_duration))
        self.load_random_animation_sequences()

    def load_random_animation_sequences(self):
        random_types = []
        if RANDOM_TYPE in self.config and self.config[RANDOM_TYPE]:
            random_types = self.config[RANDOM_TYPE]

        for seq_key in self.sequences_name.keys():
            sequence = self.sequences_name[seq_key]

            if TYPES in sequence.keys():
                for t in sequence[TYPES]:
                    if t in random_types:
                        self.random_animation_sequence.append(sequence[NAME])
                        continue

    def random(self):
        # Non branché — futur mode autonome : déclenche une animation aléatoire
        # au bout d'un délai. Aucun node ne l'appelle pour l'instant.
        if TimeUtils.is_time(RandomAnimationStart.value, self.random_duration):
            if len(self.random_animation_sequence) > 0:
                random_index = random.randint(0, len(self.random_animation_sequence)-1)
                RandomAnimationStart.value = TimeUtils.current_milli_time()
                self.update({ANIMATION: self.random_animation_sequence[random_index]})
                self.random_duration = random.randint(self.config[RANDOM_ANIMATION_LOW],
                                                      self.config[RANDOM_ANIMATION_HIGH])
                logging.info('random animation {}'.format(self.random_animation_sequence[random_index]))

    def update(self, msg):
        logging.info("incoming msg {}".format(msg))
        if msg and KEY in msg and msg[KEY] in self.config[STOP_KEY]:
            return msg.update(self.stop())
        elif ANIMATION in msg and not msg[ANIMATION]:
            self.stop()
        elif RANDOM in msg:
            logging.info("activate random {}".format(msg[RANDOM]))
            self.config[RANDOM] = msg[RANDOM]
        elif ANIMATION in msg and isinstance(msg[ANIMATION], dict) and TYPE in msg[ANIMATION]:
            logging.info("random animation {}".format(msg[ANIMATION][TYPE]))
            rand_sequence = self.get_random_sequence(msg[ANIMATION][TYPE])
            self.get_animation({ANIMATION: rand_sequence})
        elif ANIMATION in msg:
            self.get_animation(msg)

        return msg

    def get_animation(self, msg):
        animation = self.get_sequence(msg, False)

        if not animation:
            #self.duration = 0
            return

        self.current_animation = animation
        logging.info('start animation {}'.format(self.current_animation[NAME]))

        self.playing = True
        self.start = True

        if DURATION in msg and msg[DURATION] != 0:
            self.duration = msg[DURATION]
        else:
            self.duration = self.current_animation[DURATION]
            
        self.last_time = TimeUtils.current_milli_time()
        self.last_random = TimeUtils.current_milli_time()

        logging.info(animation)

        # Track.emissions : la piste est la liste de keyframes sous la clé du
        # dict d'animation (current_animation.get(KEY)). Clé absente/vide ->
        # emissions([]) -> has_data False (exactement l'ancien Animation).
        now = TimeUtils.current_milli_time()
        self.audios_animation = Track.emissions(self.current_animation.get(AUDIOS), self.duration, now)
        self.left_arm_animation = Track.emissions(self.current_animation.get(LEFT_ARM), self.duration, now)
        self.right_arm_animation = Track.emissions(self.current_animation.get(RIGHT_ARM), self.duration, now)
        self.left_eye_animation = Track.emissions(self.current_animation.get(LEFT_EYE), self.duration, now)
        self.right_eye_animation = Track.emissions(self.current_animation.get(RIGHT_EYE), self.duration, now)
        self.necks_animation = Track.emissions(self.current_animation.get(NECK), self.duration, now)
        self.faces_animation = Track.emissions(self.current_animation.get(FACES), self.duration, now)
        self.lights_animation = Track.emissions(self.current_animation.get(ROBOT_LIGHTS), self.duration, now)
        self.wheels_animation = Track.emissions(self.current_animation.get(WHEELS), self.duration, now)

    def stop(self):
        if self.playing:
            logging.info('stop animation')
            self.playing = False
        return {ANIMATION: False}

    def remaining_ms(self):
        if not self.playing:
            return 0
        elapsed = TimeUtils.current_milli_time() - self.last_time
        return max(0, int(self.duration - elapsed))

    def state_name(self):
        """Nom de la séquence en cours, ou "" au repos — publié latché par le
        node sur le topic animation_state (arbitrage amont : les comportements
        autonomes gaze/chat se taisent tant qu'une séquence a la main,
        cf. docs/etude-arbitrage-actionneurs.md lot B)."""
        if not self.playing or not self.current_animation:
            return ""
        return self.current_animation[NAME]

    def process(self):
        if self.playing and TimeUtils.is_time(self.last_time, self.duration):
            return self.stop()

        if not self.playing:
            return {}

        events = {}

        if self.start:
            events[ANIMATION] = True
            events[DURATION] = self.duration
            self.start = False

        self.fill_event(events, AUDIO, self.audios_animation)
        self.fill_event(events, LEFT_ARM, self.left_arm_animation)
        self.fill_event(events, RIGHT_ARM, self.right_arm_animation)
        self.fill_event(events, LEFT_EYE, self.left_eye_animation)
        self.fill_event(events, RIGHT_EYE, self.right_eye_animation)
        self.fill_event(events, NECK, self.necks_animation)
        self.fill_event(events, WHEELS, self.wheels_animation)
        self.fill_event(events, FACE, self.faces_animation)
        self.fill_event(events, ROBOT_LIGHTS, self.lights_animation)
        if len(events) > 0:
            # debug (et non warning) : ce log tombe à CHAQUE tick actif d'animation
            # (20 Hz depuis TICK_PERIOD_S) -> écriture fichier sur SD en boucle chaude.
            logging.debug('update animation {} with values {}'.format(self.current_animation[NAME], events))
            events[ANIMATION] = True
        return events

    def fill_event(self, events, key, track):
        if not track or not track.has_data:
            return
        event_action = track.poll(TimeUtils.current_milli_time())
        # `if event_action:` (et non `is not None`) : on conserve exactement le
        # comportement historique — une valeur falsy (servo 0.0, roues [0, 0])
        # n'est PAS transmise. C'est le « quirk latent » consigné dans CLAUDE.md
        # (une paire [0, 0] passait au plancher MIN_PWM) : le refactoring ne doit
        # rien changer à la sémantique, seulement au moteur temporel.
        if event_action:
            events[key] = event_action
