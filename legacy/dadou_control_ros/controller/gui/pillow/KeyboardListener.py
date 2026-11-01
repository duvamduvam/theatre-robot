from pynput import keyboard

from controller.buttons.button_config import BUTTONS_LAYOUT
from controller.control_config import IHR, IMR, IBR, MHR, MMR, MBR, AHR, AMR, ABR, OHR, OMR, OBR
from dadou_utils_ros.utils_static import DEFAULT

MAPPING_RIGHT = {
    "a": IHR,
    "q": IMR,
    "w": IBR,
    "z": MHR,
    "s": MMR,
    "x": MBR,
    "e": AHR,
    "d": AMR,
    "c": ABR,
    "r": OHR,
    "f": OMR,
    "v": OBR,
}

class KeyboardListener:
    def __init__(self, image_generator):
        self.image_generator = image_generator
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

        self.key = ""

    def on_press(self, k):
        try:
            #self.key = str(k.char)
            if str(k.char) in MAPPING_RIGHT:
                self.key = BUTTONS_LAYOUT[DEFAULT][MAPPING_RIGHT[str(k.char)]]

                #self.key = MAPPING_RIGHT[str(k.char)]
            else:
                self.key = str(k.char)
        except AttributeError:
            self.key = str(k)

    def get_key(self):
        key = self.key
        self.key = None
        return key