import logging.config

from dadou_utils_ros.files.files_utils import FilesUtils
from dadou_utils_ros.utils.time_utils import TimeUtils
from robot.robot_static import MOUTH_VISUALS_PATH, EYE_VISUALS_PATH, LIGHTS_PIN, MOUTHS, \
    RIGHT_EYES, LEFT_EYES
from dadou_utils_ros.utils_static import NAME, DURATION, LOOP, KEY, FACE, DEFAULT, BASE_PATH, \
    JSON_EXPRESSIONS, ANIMATION, STOP
from robot.actions.abstract_json_actions import AbstractJsonActions
from robot.sequences.track import Track
from robot.visual.image_mapping import ImageMapping
from robot.visual.visual import Visual


#TODO wrong file name

class Face(AbstractJsonActions):
    # Les tables ImageMapping sont immuables (construites une fois, jamais mutées) :
    # elles restent au niveau classe. `visuals` (dict rempli à load_visuals) est en
    # revanche un état mutable -> initialisé par instance dans __init__ (piège Python).
    mouth_image_mapping = ImageMapping.mouth()
    eye_image_mapping = ImageMapping.eye()

    # Zones du strip (source unique). Yeux nommés VU DE FACE (spectateur) :
    # la mire couleurs du 2026-07-11 a montré que les pistes left/right
    # étaient croisées. Câblage CONTIGU, sans trous (mire bordure) :
    # bouche 0-383, œil droit 384-447, œil gauche 448-511. Les anciens
    # starts 385/449 décalaient tout le contenu d'une LED (« animations
    # 6x6 collées à gauche »).
    MOUTH_START = 0
    LEYE_START = 448
    REYE_START = 384

    mouth = None
    leye = None
    reye = None

    default = "default"

    element_duration = 0
    start_time = 0

    current_face = ""

    def __init__(self, config, json_manager,  strip):
        super().__init__(config=config, json_manager=json_manager, json_file=config[JSON_EXPRESSIONS], action_type=FACE)
        logging.debug("start face with pin " + str(config[LIGHTS_PIN]))
        self.visuals = {}
        self.config = config
        self.strip = strip
        self.load_visuals()
        self.update({FACE: self.default})

    def load_visuals(self):

        mouth_names = FilesUtils.get_folder_files(self.config[MOUTH_VISUALS_PATH])
        eye_names = FilesUtils.get_folder_files(self.config[EYE_VISUALS_PATH])

        for visual_path in mouth_names + eye_names:
            visual = Visual(visual_path)
            self.visuals[visual.name] = visual

    def get_visual(self, name):
        if name in self.visuals.keys():
            return self.visuals[name]
        else:
            logging.error("no visual name : " + name)

    def parts(self):
        # Triplets (piste, start_pixel, table). Le start_pixel ne vit plus dans
        # la piste (Track est générique) : il est réassocié ici. Chaque partie
        # rend avec SA table : la bouche (serpentin 6 matrices) et les yeux
        # (matrice unique) n'ont pas le même câblage.
        return ((self.mouth, self.MOUTH_START, self.mouth_image_mapping),
                (self.leye, self.LEYE_START, self.eye_image_mapping),
                (self.reye, self.REYE_START, self.eye_image_mapping))

    def update(self, msg):
        logging.info("incoming msg {}".format(msg))

        if msg[FACE] == STOP:
            self.update({FACE: self.default})

        json_seq = self.get_sequence(msg, True)
        if not json_seq:
            return msg

        if self.current_face == json_seq[NAME]:
            self.start_time = TimeUtils.current_milli_time()
            return msg

        self.current_face = json_seq[NAME]

        logging.info("update face sequences : " + json_seq[NAME])

        if ANIMATION in msg and msg[ANIMATION]:
            self.loop = True
        else:
            self.loop = json_seq[LOOP]
        if DEFAULT in json_seq:
            self.default = json_seq[NAME]
        self.element_duration = json_seq[DURATION]
        self.start_time = TimeUtils.current_milli_time()
        # Sémantique documentée (generate_expressions.py) : la frame [t, image]
        # est affichée JUSQU'À t*duration, la première de 0 à t0. L'ancien
        # moteur émettait chaque frame À SON propre t (un cran de retard) :
        # le « rire » de joie ne s'affichait qu'un éclair en fin de cycle.
        self.mouth = Track.frames(json_seq[MOUTHS], self.element_duration, self.loop, self.start_time)
        self.leye = Track.frames(json_seq[LEFT_EYES], self.element_duration, self.loop, self.start_time)
        self.reye = Track.frames(json_seq[RIGHT_EYES], self.element_duration, self.loop, self.start_time)
        self.show_first_frames()

        return msg

    def show_first_frames(self):
        # Passe de poll IMMÉDIATE après construction : l'activation à t=0 (la
        # première frame) sort au premier poll. Sans ça, une frame n'apparaît
        # qu'à son premier poll temporisé — les yeux d'une piste à frame unique
        # resteraient sur l'expression PRÉCÉDENTE toute la durée de la séquence
        # (2 à 8 s de visage périmé à chaque bascule). Un seul strip.show() pour
        # les trois parties.
        now = TimeUtils.current_milli_time()
        for track, start_pixel, mapping in self.parts():
            value = track.poll(now)
            if value is not None:
                visual = self.get_visual(value)
                if visual is not None:
                    mapping.mapping(self.strip, visual.rgb, start_pixel)
        self.strip.show()

    def animate_part(self, track, start_pixel, mapping: ImageMapping):
        value = track.poll(TimeUtils.current_milli_time())
        if value is not None:
            visual = self.get_visual(value)
            if visual is not None:
                mapping.mapping(self.strip, visual.rgb, start_pixel)
            return True
        return False

    def process(self):
        if not self.loop:
            if self.global_duration != 0:
                if TimeUtils.is_time(self.start_global_lime, self.global_duration):
                    self.global_duration = 0
                    self.update({FACE: DEFAULT})
            else:
                if self.start_time != 0 and TimeUtils.is_time(self.start_time, self.element_duration):
                    self.update({FACE: DEFAULT})

        # PAS de court-circuit : chaque partie doit avancer à chaque tick,
        # d'où le or bit à bit sur les trois résultats.
        change = False
        for track, start_pixel, mapping in self.parts():
            change |= self.animate_part(track, start_pixel, mapping)
        if change:
            self.strip.show()

