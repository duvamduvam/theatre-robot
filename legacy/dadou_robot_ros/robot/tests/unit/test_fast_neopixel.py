"""Tests de robot/visual/fast_neopixel.py.

Objectif : garantir les DEUX propriétés critiques du module, sans matériel Pi.

1. Le module s'importe sur x86 (aucun import matériel au niveau module).
2. L'écriture vendorisée `_fast_neopixel_write` exécute le chemin complet de
   conversion buffer -> pixels (ws2811_led_set pour chaque LED, puis
   ws2811_render) ET fait l'attente de fin de trame (`time.sleep`) — incident
   2026-07-13 : sans ce sleep, la trame suivante écrase l'émission en cours
   (visage « deux signaux entrelacés »). Le test verrouille sa PRÉSENCE,
   l'ancien test verrouillait son absence — ne pas ré-inverser sans relire
   docs/incidents/2026-07-13-glitch-visage-driver-led.md.
"""

import sys

import pytest


LED_COUNT = 1000            # config LIGHTS_LED_COUNT du vrai robot
BUF_LEN = LED_COUNT * 3     # 3 octets/pixel (RGB)


def test_module_imports_on_x86():
    """Import du module seul : aucune lib Pi requise (collecte pytest ok)."""
    import robot.visual.fast_neopixel as fnp  # noqa: F401
    assert hasattr(fnp, "_fast_neopixel_write")


def test_transmit_source_has_time_sleep():
    """Garde-fou statique : l'attente de fin de trame (`*.sleep(...)`) DOIT être
    présente dans le corps de _fast_neopixel_write (incident 2026-07-13).

    Analyse AST (et non recherche textuelle) : docstring et commentaires citent
    « time.sleep » — seul un vrai appel dans l'arbre syntaxique compte."""
    import ast
    import inspect
    import textwrap
    import robot.visual.fast_neopixel as fnp

    tree = ast.parse(textwrap.dedent(inspect.getsource(fnp._fast_neopixel_write)))
    sleep_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "sleep"
    ]
    assert len(sleep_calls) == 1


class _FakePin:
    """Imite board.Pin : neopixel_write lit gpio._pin.id."""
    def __init__(self, pin_id):
        self.id = pin_id


class _FakeGpio:
    """Imite digitalio.DigitalInOut passé par NeoPixel._transmit."""
    def __init__(self, pin_id):
        self._pin = _FakePin(pin_id)


class _FakeChannel:
    """Canal ws2811 factice : stocke les setters, restitue par les getters."""
    def __init__(self):
        self.count = 0
        self.gpionum = 0
        self.invert = 0
        self.brightness = 0
        self.strip_type = 0


class _FakeWs:
    """Faux module _rpi_ws281x : implémente exactement les symboles utilisés par
    _fast_neopixel_write, et ENREGISTRE les appels à ws2811_led_set / render."""

    WS2811_SUCCESS = 0
    WS2811_STRIP_RGB = 0x00081000
    SK6812_STRIP_RGBW = 0x18100800

    def __init__(self):
        self.channels = [_FakeChannel(), _FakeChannel()]
        self.led_set_calls = []   # (index, pixel)
        self.render_calls = 0
        self.init_calls = 0

    # --- construction / cycle de vie ---
    def new_ws2811_t(self):
        return object()  # opaque : on ne s'en sert que comme poignée

    def ws2811_channel_get(self, strip, channum):
        return self.channels[channum]

    def ws2811_init(self, strip):
        self.init_calls += 1
        return self.WS2811_SUCCESS

    def ws2811_get_return_t_str(self, resp):
        return "fake error {}".format(resp)

    def ws2811_fini(self, strip):
        pass

    def delete_ws2811_t(self, strip):
        pass

    # --- setters de canal ---
    def ws2811_channel_t_count_set(self, channel, count):
        channel.count = count

    def ws2811_channel_t_gpionum_set(self, channel, num):
        channel.gpionum = num

    def ws2811_channel_t_invert_set(self, channel, val):
        channel.invert = val

    def ws2811_channel_t_brightness_set(self, channel, val):
        channel.brightness = val

    def ws2811_channel_t_strip_type_set(self, channel, val):
        channel.strip_type = val

    # --- getters de canal ---
    def ws2811_channel_t_gpionum_get(self, channel):
        return channel.gpionum

    def ws2811_channel_t_strip_type_get(self, channel):
        return channel.strip_type

    # --- réglages contrôleur ---
    def ws2811_t_freq_set(self, strip, freq):
        pass

    def ws2811_t_dmanum_set(self, strip, dma):
        pass

    # --- rendu ---
    def ws2811_led_set(self, channel, index, pixel):
        self.led_set_calls.append((index, pixel))

    def ws2811_render(self, strip):
        self.render_calls += 1
        return self.WS2811_SUCCESS


@pytest.fixture
def fnp_with_fake_ws(monkeypatch):
    """Injecte un faux _rpi_ws281x et remet l'état module à zéro autour du test.

    Nettoyage indispensable : _fast_neopixel_write mémorise _led_strip / _buf en
    globals et enregistre un handler atexit. On les remet à None APRÈS le test
    pour que le handler atexit (qui court à la sortie de l'interpréteur, une fois
    le faux module retiré) trouve _led_strip None et ne réimporte rien."""
    import robot.visual.fast_neopixel as fnp

    fake = _FakeWs()
    monkeypatch.setitem(sys.modules, "_rpi_ws281x", fake)
    # État module propre avant le test.
    fnp._led_strip = None
    fnp._buf = None
    try:
        yield fnp, fake
    finally:
        fnp._led_strip = None
        fnp._buf = None


def test_write_converts_all_pixels_renders_and_waits(fnp_with_fake_ws, monkeypatch):
    """Chemin complet : 1000 pixels convertis + render + UNE attente de trame.

    Le sleep est intercepté (pas de vraie pause en test) et sa durée vérifiée :
    0.001 * (3000//100 + 1) = 31 ms pour 1000 LED RGB, la formule Blinka."""
    import robot.visual.fast_neopixel as fnp_module
    fnp, fake = fnp_with_fake_ws

    sleeps = []
    monkeypatch.setattr(fnp_module.time, "sleep", sleeps.append)

    # Buffer post-brightness typique : 1000 LED x RGB, valeurs distinctes pour
    # vérifier la conversion (r<<16)|(g<<8)|b.
    buf = bytearray(BUF_LEN)
    for i in range(LED_COUNT):
        buf[3 * i] = i % 256          # r
        buf[3 * i + 1] = (i * 2) % 256  # g
        buf[3 * i + 2] = (i * 3) % 256  # b

    gpio = _FakeGpio(18)  # D18 = GPIO18 = canal 0

    fnp._fast_neopixel_write(gpio, buf)

    # Contrôleur initialisé une fois, les 1000 LED poussées, render appelé,
    # attente de fin de trame faite (durée = formule Blinka).
    assert fake.init_calls == 1
    assert len(fake.led_set_calls) == LED_COUNT
    assert fake.render_calls == 1
    assert sleeps == [pytest.approx(0.031)]

    # Conversion correcte du premier et d'un pixel du milieu.
    idx0, pix0 = fake.led_set_calls[0]
    assert idx0 == 0 and pix0 == 0  # (0<<16)|(0<<8)|0
    idx1, pix1 = fake.led_set_calls[1]
    r, g, b = 1, 2, 3
    assert idx1 == 1 and pix1 == ((r << 16) | (g << 8) | b)


def test_detect_channel_d18_is_zero(fnp_with_fake_ws):
    """D18 (GPIO18 = PWM0) -> canal 0 ; un pin PWM1 (GPIO19) -> canal 1."""
    fnp, _ = fnp_with_fake_ws
    assert fnp._neopixel_detect_channel(18) == 0
    assert fnp._neopixel_detect_channel(19) == 1
