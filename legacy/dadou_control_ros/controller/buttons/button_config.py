import copy
import logging
from dataclasses import dataclass
from typing import Optional

from dadou_utils_ros.singleton import SingletonMeta
from dadou_utils_ros.utils_static import (
    AUDIO, ANGLO, BACKWARD, FORWARD, LEFT, MODE, MOUTH, RIGHT, WHEELS, NECK, LEFT_ARM, RIGHT_ARM, DOWN, UP, NAME,
    KEY, FACE, ANIMATION, LIGHTS, STOP, DEFAULT, SPEAK, INCLINO, RIGHT_EYE, LEFT_EYE, DURATION, TYPE, A, B, X, Y,
)
from controller.control_static import (
    EYES, LONG, NEXT, PLAYLIST, SHORT, ARMS, CMD, CONFIG, PLAYLIST_LIST, GLOVE, GAMEPAD, L1, L2, R1, R2, START,
    SELECT, LX, LY, RX, RY, XBOX, DESIGNATE, FOLLOW,
)
from controller.control_config import SINGLE_GLOVE_9DOF, SINGLE_GLOVE, \
    DUAL_GLOVE_9DOF_LEFT, DUAL_GLOVE_9DOF_RIGHT, DUAL_GLOVE_LEFT, DUAL_GLOVE_RIGHT, IHL, IML, IHR, IMR, IBR, MHL, MHR, \
    MML, MMR, MBL, MBR, AHL, AHR, AML, AMR, ABL, ABR, OHL, OHR, OML, OMR, OBL, OBR, IBL, config

BUTTONS = "buttons"
RELAY = "relay"
OCTAVER = "octaver"

INPUT_KEYS = [[IBL, MBL, ABL, OBL],
        [IML, MML, AML, OML],
        [IHL, MHL, AHL, OHL]]

GAMEPAD_KEYS = (A, B, X, Y, L1, L2, R1, R2, START, SELECT, MODE, UP, DOWN, LEFT, RIGHT)
JOYSTICK_KEYS = (LX, LY, RX, RY)


@dataclass(frozen=True)
class GamepadMapping:
    a_button: Optional[int] = None
    b_button: Optional[int] = None
    x_button: Optional[int] = None
    y_button: Optional[int] = None
    start_button: Optional[int] = None
    select_button: Optional[int] = None
    mode_button: Optional[int] = None
    l1_button: Optional[int] = None
    r1_button: Optional[int] = None
    l2_button: Optional[int] = None
    r2_button: Optional[int] = None
    lx_axis: Optional[int] = None
    ly_axis: Optional[int] = None
    rx_axis: Optional[int] = None
    ry_axis: Optional[int] = None
    l2_axis: Optional[int] = None
    r2_axis: Optional[int] = None
    invert_ly: bool = False
    invert_ry: bool = False


XBOX_MAPPING = GamepadMapping(
    a_button=0,
    b_button=1,
    x_button=3,
    y_button=4,
    start_button=11,
    select_button=10,
    mode_button=12,
    l1_button=6,
    r1_button=7,
    l2_button=8,
    r2_button=9,
    lx_axis=11,
    ly_axis=12,
    rx_axis=13,
    ry_axis=14,
    l2_axis=15,
    r2_axis=16,
    invert_ly=True,
    invert_ry=True,
)

GAMEPAD_MAPPING = {XBOX: XBOX_MAPPING}

KEYS_MAPPING = {'2': IHL, '1': IML, '12': IBL, '5': MHL, '4': MML, '3': MBL, '8': AHL, '7': AML, '6': ABL, '11': OHL, '10': OML, '9': OBL,
                'm': IHR, 'n': IMR, 'o': IBR, 'p': MHR, 'q': MMR, 'r': MBR, 's': AHR, 't': AMR, 'u': ABR, 'v': OHR, 'w': OMR, 'x': OBR}


CONTROL_CONFIG = [[DEFAULT, PLAYLIST, "VIDE"], ["VIDE", "VIDE", "VIDE"], ["VIDE", "VIDE", "VIDE"]]
PLAYLIST_CONFIG = [config[PLAYLIST_LIST], ["pub1", "VIDE", "VIDE"]]

base = {
    IHL: {NAME: "vo off", CMD: {RELAY: "off"}},
    IML: {NAME: "ca va", CMD: {AUDIO: 'ca-va'}},
    IBL: {NAME: "sympa toi", CMD: {ANIMATION: 'crazy'}},
    MHL: {NAME: "wh right", CMD: {WHEELS: RIGHT}},
    MML: {NAME: "wh left", CMD: {WHEELS: LEFT}},
    MBL: {NAME: "ro vo", CMD: {RELAY: "pitched_voice", ANIMATION: "speak"}},
    AHL: {NAME: "wh for", CMD: {WHEELS: FORWARD}},
    AML: {NAME: "wh back", CMD: {WHEELS: BACKWARD}},
    ABL: {NAME: "klaxon", CMD: {RELAY: "klaxon"}},
    OHL: {NAME: "bug", CMD: {ANIMATION: {TYPE: "bug"}}},
    OML: {NAME: "bug1", CMD: {ANIMATION: "bug1",
        DURATION: 5000, AUDIO: "street/promotion-vie-eternelle.mp3"}},
    OBL: {NAME: STOP, CMD: {ANIMATION: STOP}},

    # « C'est moi » (2026-09-14). IHR portait le libellé MORT "Inclino" avec une
    # commande VIDE : un bouton câblé qui ne faisait rien. L'inclinomètre du gant
    # 9DOF ne passe pas par là (Buttons.get intercepte les trames série dont le
    # premier caractère est "I", bien avant KEYS_MAPPING) — réaffecter IHR ne
    # casse donc rien.
    # Geste : David se plante devant Didier et appuie. Le suivi se VERROUILLE sur
    # la personne la plus CENTRÉE (pas la plus grosse : la plus centrée est la
    # seule que David contrôle, même si un badaud est plus près). Sans ça, en rue,
    # Didier fixe systématiquement le spectateur du premier rang.
    # Ne touche AUCUN actionneur : pure perception, donc aucun enjeu roues.
    IHR: {NAME: "c'est moi", CMD: {DESIGNATE: "on"}},
    IMR: {NAME: "rarm down", CMD: {RIGHT_ARM: DOWN}},
    IBR: {NAME: "rarm up", CMD: {RIGHT_ARM: UP}},
    MHR: {NAME: "neck right", CMD: {NECK: DOWN}},
    MMR: {NAME: "larm down", CMD: {LEFT_ARM: DOWN}},
    MBR: {NAME: "larm up", CMD: {LEFT_ARM: UP}},
    AHR: {NAME: "neck left", CMD: {NECK: UP}},
    AMR: {NAME: "leye down", CMD: {RIGHT_EYE: DOWN}},
    ABR: {NAME: "leye up", CMD: {RIGHT_EYE: UP}},
    OHR: {NAME: "mute", CMD: {"mute": "mute"}},
    OMR: {NAME: "reye down", CMD: {LEFT_EYE: DOWN}},
    OBR: {NAME: "reye up", CMD: {LEFT_EYE: UP}},

    # GAMEPAD
    A: {NAME: "ro vo", CMD: {RELAY: "pitched_voice", ANIMATION: "speak"}},
    B: {NAME: "vo off", CMD: {RELAY: "off"}},
    X: {NAME: "bug", CMD: {ANIMATION: {TYPE: "bug"}}},
    Y: {NAME: "klaxon", CMD: {RELAY: "klaxon"}},
    L1: {NAME: "neck left", CMD: {NECK: UP}},
    L2: {NAME: "larm down", CMD: {LEFT_ARM: UP}},
    R1: {NAME: "neck left", CMD: {NECK: DOWN}},
    R2: {NAME: "larm down", CMD: {LEFT_ARM: DOWN}},
    # « Suis-moi » (2026-09-14) : activation du suivi de personne AUX ROUES.
    # DEUX boutons distincts, PAS une bascule : la bascule oblige à connaître
    # l'état courant pour savoir ce qu'un appui va faire. Pour une commande qui
    # met 50 kg en mouvement tout seuls, explicite vaut mieux que malin —
    # SELECT arrête, toujours, quel que soit l'état.
    # SUR LE GAMEPAD ET PAS SUR LE GANT, DÉLIBÉRÉMENT : le gant n'a qu'un seul
    # bouton libre (IHR) et il va à « c'est moi », qui est sans danger. Le suivi
    # roues, lui, reste SIM-ONLY tant que le test scénique au sol et le protocole
    # caméra roues hors sol n'ont pas eu lieu (docs/chantiers.md) : il n'a rien à
    # faire à portée de pouce pendant un spectacle. À déplacer sur le gant APRÈS
    # ces deux étapes, si David le souhaite.
    # Rappel : la télécommande garde la priorité absolue (twist_mux remote 100 >
    # follow 20), donc conduire à la main écrase le suivi à tout instant.
    START: {NAME: "suis-moi", CMD: {FOLLOW: "on"}},
    SELECT: {NAME: "stop suivi", CMD: {FOLLOW: "off"}},
    # Relâchement de la désignation. Sans lui, « c'est moi » serait une porte à
    # SENS UNIQUE : une fois verrouillé sur David, Didier ne pourrait plus
    # revenir au regard libre (la personne la plus proche) autrement qu'en ligne
    # de commande. Or l'étude interaction a tranché que Didier parle AUSSI au
    # public — regarder ailleurs que David doit rester jouable.
    # ⚠️ ERGONOMIE À ARBITRER AVEC DAVID : armer se fait au GANT (IHR) et
    # relâcher à la MANETTE, ce qui est bancal en jeu. C'est faute de second
    # bouton libre sur le gant — les 24 sont pris. Si le relâchement doit vivre
    # au gant, il faudra libérer une touche en déplaçant une autre fonction.
    MODE: {NAME: "regard libre", CMD: {DESIGNATE: "off"}},
    UP: {NAME: "wh for", CMD: {WHEELS: UP}},
    DOWN: {NAME: "wh back", CMD: {WHEELS: DOWN}},
    LEFT: {NAME: "wh left", CMD: {WHEELS: LEFT}},
    RIGHT: {NAME: "wh right", CMD: {WHEELS: RIGHT}}

}

playlist = copy.copy(base)
playlist[IBL] = {NAME: "pl next", CMD: {PLAYLIST: NEXT}}

BUTTONS_LAYOUT = {
    PLAYLIST: playlist,
    DEFAULT: base
}


class Buttons(metaclass=SingletonMeta):

    @staticmethod
    def get(type, key):
        if key[0] == "I":
            return {INCLINO: key[1:]}
        if key in KEYS_MAPPING:
            return BUTTONS_LAYOUT[type][KEYS_MAPPING[key]][CMD]
        elif key in GAMEPAD_KEYS:
            button_cfg = BUTTONS_LAYOUT[DEFAULT].get(key)
            if isinstance(button_cfg, dict):
                return button_cfg.get(CMD)
            return button_cfg
        else:
            logging.error("key {} not in button layout".format(key))
