"""Tests de la logique pure de visualisation LED en sim (robot_sim_lib.leds_logic).

Le temps est toujours injecté (jamais time.time()/random.* non seedé côté
production) : chaque test pose un elapsed_ms explicite pour rester déterministe.
"""
import pytest

from robot_sim_lib.leds_logic import (
    BLACK,
    LedsSimState,
    active_brick_at,
    build_timeline,
    compute_effect_color,
    face_colors,
    is_animated_method,
)

COLORS = {
    "RED": [255, 0, 0],
    "GOLD": [255, 222, 30],
    "AQUA": [50, 255, 255],
    "PURPLE": [180, 0, 255],
}

LIGHTS_BASE = {
    "solid red": {"method": "solid", "color": "RED"},
    "blink purple": {"method": "blink", "color": "PURPLE"},
    "pulse red": {"method": "pulse", "color": "RED"},
    "rainbow": {"method": "rainbow"},
}

ROBOT_LIGHTS = {
    "two bricks": {
        "loop": False,
        "duration": 1000,
        "sequences": {"solid red": 0.5, "blink purple": 1.0},
    },
    "looping": {
        "loop": True,
        "duration": 1000,
        "sequences": {"solid red": 1.0},
    },
    "single at zero": {
        # cas réel (json/robot_lights.json "devil") : une seule brique à
        # position 0 -- doit rester active tout le temps de la séquence.
        "loop": True,
        "duration": 1000,
        "sequences": {"solid red": 0},
    },
}


# ---- timeline ----

def test_build_timeline_segments_are_cumulative():
    timeline = build_timeline({"a": 0.5, "b": 1.0}, duration_ms=1000)
    assert timeline == [("a", 0.0, 500.0), ("b", 500.0, 1000.0)]


def test_active_brick_within_first_segment():
    timeline = build_timeline({"a": 0.5, "b": 1.0}, duration_ms=1000)
    assert active_brick_at(timeline, loop=False, duration_ms=1000, elapsed_ms=100) == "a"


def test_active_brick_within_second_segment():
    timeline = build_timeline({"a": 0.5, "b": 1.0}, duration_ms=1000)
    assert active_brick_at(timeline, loop=False, duration_ms=1000, elapsed_ms=900) == "b"


def test_active_brick_none_past_duration_when_not_looping():
    timeline = build_timeline({"a": 0.5, "b": 1.0}, duration_ms=1000)
    assert active_brick_at(timeline, loop=False, duration_ms=1000, elapsed_ms=1500) is None


def test_active_brick_wraps_when_looping():
    timeline = build_timeline({"a": 0.5, "b": 1.0}, duration_ms=1000)
    # 1200 ms écoulés, boucle de 1000 ms -> équivalent à 200 ms -> segment "a"
    assert active_brick_at(timeline, loop=True, duration_ms=1000, elapsed_ms=1200) == "a"


def test_single_brick_at_position_zero_always_active():
    # cf. json/robot_lights.json "devil": {"sequences": {"solid red": 0}}
    timeline = build_timeline({"solid red": 0}, duration_ms=1000)
    assert active_brick_at(timeline, loop=True, duration_ms=1000, elapsed_ms=0) == "solid red"
    assert active_brick_at(timeline, loop=True, duration_ms=1000, elapsed_ms=999) == "solid red"


# ---- effets ----

def test_effect_solid_is_constant_base_color():
    brick = LIGHTS_BASE["solid red"]
    assert compute_effect_color(brick, 0, COLORS) == (255, 0, 0)
    assert compute_effect_color(brick, 12345, COLORS) == (255, 0, 0)


def test_effect_blink_toggles_at_half_second():
    brick = LIGHTS_BASE["blink purple"]
    assert compute_effect_color(brick, 0, COLORS) == (180, 0, 255)      # allumé
    assert compute_effect_color(brick, 600, COLORS) == BLACK            # éteint (0.6 % 1.0 >= 0.5)
    assert compute_effect_color(brick, 1000, COLORS) == (180, 0, 255)   # nouveau cycle, allumé


def test_effect_pulse_peaks_and_troughs():
    brick = LIGHTS_BASE["pulse red"]
    # période 2 s : creux à t=0 (intensité 0.5), pic à t=0.5s (intensité 1.0),
    # nul à t=1.5s (intensité 0.0).
    assert compute_effect_color(brick, 0, COLORS) == (128, 0, 0)
    assert compute_effect_color(brick, 500, COLORS) == (255, 0, 0)
    assert compute_effect_color(brick, 1500, COLORS) == BLACK


def test_effect_rainbow_cycles_hue_deterministically():
    brick = LIGHTS_BASE["rainbow"]
    # 0.2 tour/s : à t=0 -> rouge pur ; à t=2.5s -> demi-tour -> cyan pur.
    assert compute_effect_color(brick, 0, COLORS) == (255, 0, 0)
    assert compute_effect_color(brick, 2500, COLORS) == (0, 255, 255)


def test_is_animated_method_distinguishes_static_from_animated():
    assert is_animated_method("solid") is False
    assert is_animated_method("blink") is True
    assert is_animated_method("rainbow_chase") is True


# ---- LedsSimState : orchestration robot_lights ----

def test_state_starts_off():
    state = LedsSimState(ROBOT_LIGHTS)
    color, method = state.current_color_and_method(0, LIGHTS_BASE, COLORS)
    assert color is None and method is None


def test_state_stop_message_turns_off():
    state = LedsSimState(ROBOT_LIGHTS)
    state.update("two bricks", now_ms=0, override_duration_ms=None)
    state.update("stop", now_ms=100)
    color, _ = state.current_color_and_method(100, LIGHTS_BASE, COLORS)
    assert color is None


def test_state_plays_expected_brick_over_time():
    state = LedsSimState(ROBOT_LIGHTS)
    state.update("two bricks", now_ms=1000)
    color_first, method_first = state.current_color_and_method(1100, LIGHTS_BASE, COLORS)
    assert method_first == "solid" and color_first == (255, 0, 0)
    color_second, _ = state.current_color_and_method(1900, LIGHTS_BASE, COLORS)
    assert color_second == BLACK  # blink purple à t=900ms de la brique -> éteint


def test_state_non_looping_sequence_turns_off_at_end():
    state = LedsSimState(ROBOT_LIGHTS)
    state.update("two bricks", now_ms=0)
    color, method = state.current_color_and_method(5000, LIGHTS_BASE, COLORS)  # bien après duration=1000
    assert color is None and method is None
    assert state.sequence_name is None  # auto-stop, cf. "retour à éteint à la fin"


def test_state_time_field_overrides_duration():
    state = LedsSimState(ROBOT_LIGHTS)
    # duration JSON = 1000 ms, mais un StringTime.time non nul (ici 4000) la remplace :
    # à 1500ms écoulés on doit encore être dans la première moitié (solid red).
    state.update("two bricks", now_ms=0, override_duration_ms=4000)
    color, method = state.current_color_and_method(1500, LIGHTS_BASE, COLORS)
    assert method == "solid" and color == (255, 0, 0)


def test_state_unknown_sequence_raises_keyerror():
    state = LedsSimState(ROBOT_LIGHTS)
    with pytest.raises(KeyError):
        state.update("n'existe pas", now_ms=0)


def test_state_brightness_scales_output():
    state = LedsSimState(ROBOT_LIGHTS)
    state.update("looping", now_ms=0)
    state.set_brightness(0.5)
    color, _ = state.current_color_and_method(100, LIGHTS_BASE, COLORS)
    assert color == (128, 0, 0)  # moitié de (255,0,0)


def test_state_brightness_message_clamped_0_1():
    state = LedsSimState(ROBOT_LIGHTS)
    state.update({"brightness": 5}, now_ms=0)
    assert state.brightness == 1.0
    state.update({"brightness": -3}, now_ms=0)
    assert state.brightness == 0.0


# ---- face ----

def test_face_stop_turns_everything_off():
    colors = face_colors("stop", COLORS)
    assert colors == {"mouth": BLACK, "left_eye": BLACK, "right_eye": BLACK}


def test_face_expression_lights_mouth_gold_eyes_aqua():
    colors = face_colors("happy", COLORS)
    assert colors["mouth"] == (255, 222, 30)
    assert colors["left_eye"] == colors["right_eye"] == (50, 255, 255)
