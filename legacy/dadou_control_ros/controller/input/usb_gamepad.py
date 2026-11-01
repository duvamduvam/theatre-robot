import os
import pygame
import logging
from typing import Optional, Dict, Any

from controller.buttons.button_config import Buttons, XBOX_MAPPING, GamepadMapping, GAMEPAD_MAPPING
from dadou_utils_ros.utils_static import A, B, X, Y, UP, DOWN, LEFT, RIGHT, MODE
from controller.control_static import GAMEPAD, L1, L2, R1, R2, START, SELECT, LX, LY, RX, RY, CONNECTED, XBOX


def _normalize_button_name(symbol: str) -> str:
    if isinstance(symbol, str):
        return symbol.upper()
    return str(symbol)


def _normalize_axis_name(symbol: str) -> str:
    if isinstance(symbol, str):
        return symbol.upper()
    return str(symbol)


BUTTON_NAME_MAP = {
    A: _normalize_button_name(A),
    B: _normalize_button_name(B),
    X: _normalize_button_name(X),
    Y: _normalize_button_name(Y),
    L1: _normalize_button_name(L1),
    L2: _normalize_button_name(L2),
    R1: _normalize_button_name(R1),
    R2: _normalize_button_name(R2),
    START: _normalize_button_name(START),
    SELECT: _normalize_button_name(SELECT),
    MODE : _normalize_button_name(MODE),
    UP: _normalize_button_name(UP),
    DOWN: _normalize_button_name(DOWN),
    LEFT: _normalize_button_name(LEFT),
    RIGHT: _normalize_button_name(RIGHT),
}

JOYSTICK_NAME_MAP = {
    LX: _normalize_axis_name(LX),
    LY: _normalize_axis_name(LY),
    RX: _normalize_axis_name(RX),
    RY: _normalize_axis_name(RY),
}

BUTTON_KEYS = tuple(BUTTON_NAME_MAP.values())
JOYSTICK_KEYS = tuple(JOYSTICK_NAME_MAP.values())
CONNECTED_KEY = str(CONNECTED)

BUTTON_ATTR_MAP = {
    BUTTON_NAME_MAP[A]: "a_button",
    BUTTON_NAME_MAP[B]: "b_button",
    BUTTON_NAME_MAP[X]: "x_button",
    BUTTON_NAME_MAP[Y]: "y_button",
    BUTTON_NAME_MAP[L1]: "l1_button",
    BUTTON_NAME_MAP[L2]: "l2_button",
    BUTTON_NAME_MAP[R1]: "r1_button",
    BUTTON_NAME_MAP[R2]: "r2_button",
    BUTTON_NAME_MAP[START]: "start_button",
    BUTTON_NAME_MAP[SELECT]: "select_button",
    BUTTON_NAME_MAP[MODE]: "mode_button",
}

AXIS_ATTR_MAP = {
    JOYSTICK_NAME_MAP[LX]: "lx_axis",
    JOYSTICK_NAME_MAP[LY]: "ly_axis",
    JOYSTICK_NAME_MAP[RX]: "rx_axis",
    JOYSTICK_NAME_MAP[RY]: "ry_axis",
}

TRIGGER_AXIS_ATTR_MAP = {
    BUTTON_NAME_MAP[L2]: "l2_axis",
    BUTTON_NAME_MAP[R2]: "r2_axis",
}

class USBGamepad:

    def __init__(self, node=None, controller_type: str = "auto"):
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.init()
        self.node = node
        #if pygame.mixer.get_init():
        #    pygame.mixer.quit()
        #try:
        #    pygame.display.set_mode((1, 1))
        #except Exception:
        #    pass
        #pygame.joystick.init()
        self.raw_state = {}
        self.gamepad: Optional[pygame.joystick.Joystick] = None
        self._warned_no_gamepad = False
        self.controller_type = controller_type.lower() if controller_type else "auto"
        # Neutral references to filter hardware bias/drift
        self._axis_neutral: Dict[str, Optional[int]] = {axis: None for axis in JOYSTICK_KEYS}
        self._axis_neutral_snap = 4
        self._trigger_neutral: Dict[str, Optional[float]] = {
            BUTTON_NAME_MAP[L2]: None,
            BUTTON_NAME_MAP[R2]: None,
        }
        self._trigger_threshold = 0.25
        self._raw_axis_log_threshold = 0.2
        self.mapping: GamepadMapping = XBOX_MAPPING
        self._prev_raw_logged = None

        if pygame.joystick.get_count() == 0:
            logging.info("Aucune manette détectée.")
            return

        self.gamepad = pygame.joystick.Joystick(0)
        self.gamepad.init()
        name = self.gamepad.get_name() or ""
        logging.info(f"Manette détectée : {name}")

        detected_type = self._detect_type_from_name(name) if self.controller_type == "auto" else self.controller_type
        self.mapping = GAMEPAD_MAPPING.get(detected_type, XBOX_MAPPING)
        if detected_type not in GAMEPAD_MAPPING:
            logging.error("gamepad not regcognized {}".format(detected_type))
        logging.info(f"Profil manette: {detected_type}")
        self._log_mapping_details(self.mapping)

    def _log_mapping_details(self, mapping: Optional[GamepadMapping]) -> None:
        if not mapping:
            logging.warning("Aucun mapping de manette disponible: utilisation du profil xbox par défaut")
            return

        button_lines = [
            f"A={mapping.a_button}",
            f"B={mapping.b_button}",
            f"X={mapping.x_button}",
            f"Y={mapping.y_button}",
            f"START={mapping.start_button}",
            f"SELECT={mapping.select_button}",
            f"MODE={mapping.mode_button}",
            f"L1={mapping.l1_button}",
            f"R1={mapping.r1_button}",
            f"L2={mapping.l2_button}",
            f"R2={mapping.r2_button}",
        ]
        axis_lines = [
            f"LX={mapping.lx_axis}",
            f"LY={mapping.ly_axis} (invert={mapping.invert_ly})",
            f"RX={mapping.rx_axis}",
            f"RY={mapping.ry_axis} (invert={mapping.invert_ry})"
        ]

        logging.info("Indices mapping boutons: %s", ", ".join(button_lines))
        logging.info("Indices mapping axes: %s", ", ".join(axis_lines))

    def _detect_type_from_name(self, name: str) -> str:
        n = name.lower()
        if any(k in n for k in [XBOX, "x-input", "xinput", "x-box", "shanwan"]):
            return XBOX
        if any(k in n for k in ["playstation", "dualshock", "dual sense", "dualsense", "sony"]):
            return "playstation"
        if any(k in n for k in ["switch", "nintendo", "pro controller"]):
            return "switch"
        if "gamecube" in n:
            return "gamecube"
        return "generic"

    def _scale_axis_to_0_99(self, v: float) -> int:
        # pygame retourne [-1.0, 1.0] -> on mappe sur [0, 99]
        s = int(round(((v + 1.0) / 2.0) * 99))
        return max(0, min(99, s))

    def _update_axis_neutral(self, axis: str, value: Optional[int]) -> None:
        if value is None:
            return
        neutral = self._axis_neutral.get(axis)
        if neutral is None:
            self._axis_neutral[axis] = value
            return
        if abs(value - neutral) <= self._axis_neutral_snap:
            self._axis_neutral[axis] = int(round(neutral * 0.8 + value * 0.2))

    def _neutral_value(self, axis: str) -> int:
        neutral = self._axis_neutral.get(axis)
        if neutral is None:
            return 50
        return neutral

    def _update_neutral_from_state(self, state: Dict[str, int]) -> None:
        for axis in JOYSTICK_KEYS:
            value = state.get(axis)
            if isinstance(value, int):
                self._update_axis_neutral(axis, value)

    def _trigger_from_axis(self, idx: Optional[int], name: str) -> int:
        if idx is None:
            return 0
        try:
            v = self.gamepad.get_axis(idx)
        except Exception:
            return 0
        norm = (v + 1.0) / 2.0
        norm = max(0.0, min(1.0, norm))
        neutral = self._trigger_neutral.get(name)
        if neutral is None:
            self._trigger_neutral[name] = norm
            return 0
        delta = norm - neutral
        if abs(delta) >= self._trigger_threshold:
            return 1
        self._trigger_neutral[name] = neutral * 0.9 + norm * 0.1
        return 0

    def get_normalized_state(self) -> Optional[Dict[str, int]]:
        if not self.gamepad:
            empty_state = {
                CONNECTED_KEY: 0,
            }
            empty_state.update({name: 0 for name in BUTTON_KEYS})
            empty_state.update({name: 0 for name in JOYSTICK_KEYS})
            return empty_state
        try:
            pygame.event.pump()
        except Exception:
            return None

        self.raw_state = {
            'axes': [self.gamepad.get_axis(i) for i in range(self.gamepad.get_numaxes())],
            'buttons': [self.gamepad.get_button(i) for i in range(self.gamepad.get_numbuttons())],
            'hats': [self.gamepad.get_hat(i) for i in range(self.gamepad.get_numhats())],
        }

        m = self.mapping

        def get_button(idx: Optional[int]) -> int:
            if idx is None:
                return 0
            try:
                return 1 if self.gamepad.get_button(idx) else 0
            except Exception:
                return 0

        btnA = get_button(m.a_button)
        btnB = get_button(m.b_button)
        btnX = get_button(m.x_button)
        btnY = get_button(m.y_button)
        btnSTART = get_button(m.start_button)
        btnSELECT = get_button(m.select_button)
        btnMODE = get_button(m.mode_button)
        btnL1 = get_button(m.l1_button)
        btnR1 = get_button(m.r1_button)
        # L2/R2 can be on buttons or axes; pressed if either is active
        btnL2_b = get_button(m.l2_button)
        btnR2_b = get_button(m.r2_button)

        def get_axis(idx: Optional[int]) -> int:
            if idx is None:
                return 0
            try:
                return self._scale_axis_to_0_99(self.gamepad.get_axis(idx))
            except Exception:
                return 0

        lx = get_axis(m.lx_axis)
        ly = get_axis(m.ly_axis)
        rx = get_axis(m.rx_axis)
        ry = get_axis(m.ry_axis)

        if m.invert_ly:
            ly = 99 - ly
        if m.invert_ry:
            ry = 99 - ry

        for axis_symbol, axis_value in ((LX, lx), (LY, ly), (RX, rx), (RY, ry)):
            axis_name = JOYSTICK_NAME_MAP.get(axis_symbol, str(axis_symbol))
            self._update_axis_neutral(axis_name, axis_value)

        # D-Pad via HAT si disponible
        up = down = left = right = 0
        try:
            if self.gamepad.get_numhats() > 0:
                hx, hy = self.gamepad.get_hat(0)
                left = 1 if hx < 0 else 0
                right = 1 if hx > 0 else 0
                up = 1 if hy > 0 else 0
                down = 1 if hy < 0 else 0
        except Exception:
            pass

        btnL2 = btnL2_b or self._trigger_from_axis(m.l2_axis, BUTTON_NAME_MAP[L2])
        btnR2 = btnR2_b or self._trigger_from_axis(m.r2_axis, BUTTON_NAME_MAP[R2])

        return {
            CONNECTED_KEY: 1,
            BUTTON_NAME_MAP[A]: btnA,
            BUTTON_NAME_MAP[B]: btnB,
            BUTTON_NAME_MAP[X]: btnX,
            BUTTON_NAME_MAP[Y]: btnY,
            BUTTON_NAME_MAP[L1]: btnL1,
            BUTTON_NAME_MAP[L2]: btnL2,
            BUTTON_NAME_MAP[R1]: btnR1,
            BUTTON_NAME_MAP[R2]: btnR2,
            BUTTON_NAME_MAP[START]: btnSTART,
            BUTTON_NAME_MAP[SELECT]: btnSELECT,
            BUTTON_NAME_MAP[MODE]: btnMODE,
            BUTTON_NAME_MAP[UP]: up,
            BUTTON_NAME_MAP[DOWN]: down,
            BUTTON_NAME_MAP[LEFT]: left,
            BUTTON_NAME_MAP[RIGHT]: right,
            JOYSTICK_NAME_MAP[LX]: lx,
            JOYSTICK_NAME_MAP[LY]: ly,
            JOYSTICK_NAME_MAP[RX]: rx,
            JOYSTICK_NAME_MAP[RY]: ry,
        }

    def active_inputs(
        self,
        state: Optional[Dict[str, int]] = None,
        deadzone: int = 10,
    ) -> Optional[Dict[str, Any]]:
        if state is None:
            state = self.get_normalized_state()

        if state is None:
            return None

        buttons = [btn for btn in BUTTON_KEYS if state.get(btn) == 1]

        active_axes: Dict[str, int] = {}

        #for axis in JOYSTICK_KEYS:
        #    value = state.get(axis)
        #    if not isinstance(value, int):
        #        continue
        #    if abs(value - 50) >= deadzone:
        #        active_axes[axis] = value

        self._update_neutral_from_state(state)

        return {"buttons": buttons, "joysticks": active_axes}

    def check_inputs(self):
        if not self.gamepad:
            if getattr(self, "_warned_no_gamepad", False) is False:
                logging.info("Aucune manette détectée: check() ignoré.")
                self._warned_no_gamepad = True
            return

        state = self.get_normalized_state()

        if state is None:
            return None

        active_inputs = self.active_inputs(state) or {"buttons": [], "joysticks": {}}

        if active_inputs["buttons"] or active_inputs["joysticks"]:
            logging.info(self.raw_state)
            buttons_str = ", ".join(active_inputs["buttons"]) or "aucun"
            joystick_details = (
                ", ".join(f"{axis}={value}" for axis, value in active_inputs["joysticks"].items())
                or "aucun"
            )
            results = {}
            for input in active_inputs["buttons"]:
                results[input] = Buttons.get(GAMEPAD, input)
                if self.node and results[input] is not None:
                    self.node.publish(results[input])
            return results

    #def print(self, msg):


        #logging.info(
        #    "Entrées brutes: boutons=%s axes=%s hats=%s | mapping_boutons=%s | mapping_axes=%s | mapping_triggers=%s | index->boutons=%s | index->axes=%s | index->triggers=%s",
        #    list(active_buttons),
        #    axes_log,
        #    hats_log,
        #    button_indices,
        #    axis_indices,
        #    trigger_axis_indices,
        #    raw_to_buttons,
        #    raw_to_axes,
        #    raw_to_triggers,
        #)
