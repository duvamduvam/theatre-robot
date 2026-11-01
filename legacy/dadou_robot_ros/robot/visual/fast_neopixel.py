"""Écriture NeoPixel vendorisée : chemin DIRECT vers _rpi_ws281x, sleep conservé.

POURQUOI ce module existe (révisé le 2026-07-13 — lire avant de « simplifier »)
------------------------------------------------------------------------------
1. Le chemin d'écriture STANDARD de Blinka (neopixel.NeoPixel -> résolution de
   backend) NE FONCTIONNE PAS dans le conteneur du robot : la détection part
   sur un backend générique — ruban quasi noir, quelques pixels égarés, aucune
   erreur levée (constaté le 2026-07-13 : retour au driver stock -> visage
   éteint ; script de test stock suspendu). Ce module court-circuite la
   résolution en construisant lui-même le contrôleur ws2811 (copie de la
   fonction `neopixel_write` du backend bcm283x de Blinka).

2. Le `time.sleep(0.001 * (len(buf)//100 + 1))` post-render de Blinka est
   CONSERVÉ : c'est l'attente de fin de trame sur le fil (~31 ms pour
   1000 LED). Sa suppression (version du 2026-07-11 au 2026-07-13) corrompait
   les trames à chaque rendu : le ruban latchait en cours d'émission et
   affichait « deux signaux entrelacés ». Le C de _rpi_ws281x n'assure PAS
   seul cette protection en pratique (Pi 4, rpi-ws281x 5.0.0). Post-mortem :
   docs/incidents/2026-07-13-glitch-visage-driver-led.md. NE PAS retenter.

Conséquence cadence : chaque show() bloque ~31 ms -> lights_node s'auto-limite
sous animation continue ; le tick global 20 Hz (TICK_PERIOD_S) reste valable
pour les autres nodes.

Ce qu'on garde IDENTIQUE à Blinka (code matériel validé) : init `ws2811_t`,
boucle de conversion buf->`ws2811_led_set`, `ws2811_render`, sleep final,
gestion d'erreurs, cleanup atexit.

Imports matériels différés (même pattern que robot/actions/wheels.py) : ce module
doit s'importer sur x86 (collecte pytest, poste de dev). `_rpi_ws281x` n'est
importé qu'à la PREMIÈRE transmission, et `neopixel` (qui tire board/digitalio,
absents hors Pi) qu'à l'accès à la classe `FastNeoPixel` (via __getattr__).
"""

import atexit
import time

# Configuration LED copiée VERBATIM de Blinka bcm283x — ne rien régler ici :
# on ne supporte qu'une bande 800 kHz, canal DMA 10, luminosité gérée en amont
# par la lib neopixel (le buffer reçu est DÉJÀ post-brightness).
LED_FREQ_HZ = 800000  # Fréquence du signal LED — seul 800 kHz est supporté.
LED_DMA_NUM = 10       # Canal DMA (0-14).
LED_BRIGHTNESS = 255   # Luminosité gérée dans la lib neopixel (donc 255 ici).
LED_INVERT = 0         # Pas de logique inversée.

# État « statique » : une seule bande LED par Pi. On réinitialise le contrôleur
# si le buffer d'entrée change d'identité (même logique que Blinka).
_led_strip = None
_buf = None


def _neopixel_detect_channel(pin_id):
    """Canal PWM du BCM283x pour un GPIO donné.

    Le SoC n'a que deux générateurs PWM : PWM1 est câblé sur GPIO 13/19/41/45/53
    (canal 1), PWM0 partout ailleurs (canal 0). Notre bande est sur D18 = GPIO18
    = PWM0 => canal 0. On garde la détection générique (elle est triviale) plutôt
    que de figer 0, pour rester correct si le pin change un jour.
    """
    if pin_id in (13, 19, 41, 45, 53):
        return 1
    return 0


def _fast_neopixel_write(gpio, buf):
    """Copie de `neopixel_write` (Blinka bcm283x), sleep de fin de trame COMPRIS.

    `gpio` est un DigitalInOut (accès `gpio._pin.id`) ; `buf` est le bytearray
    post-brightness fourni par adafruit_pixelbuf. Même contrat que Blinka.
    """
    global _led_strip, _buf
    # Import différé : la lib native _rpi_ws281x n'existe que sur le Pi.
    import _rpi_ws281x as ws  # pylint: disable=import-error

    led_channel = _neopixel_detect_channel(gpio._pin.id)

    if _led_strip is None or buf is not _buf:
        # Sans danger si _led_strip est None (garde interne).
        _fast_neopixel_cleanup()

        _led_strip = ws.new_ws2811_t()
        _buf = buf

        # Initialise les deux canaux à « éteint ».
        for channum in range(2):
            channel = ws.ws2811_channel_get(_led_strip, channum)
            ws.ws2811_channel_t_count_set(channel, 0)
            ws.ws2811_channel_t_gpionum_set(channel, 0)
            ws.ws2811_channel_t_invert_set(channel, 0)
            ws.ws2811_channel_t_brightness_set(channel, 0)

        channel = ws.ws2811_channel_get(_led_strip, led_channel)

        # Initialise le canal utilisé : 3 octets/pixel (RGB) ou 4 (RGBW).
        count = 0
        if len(buf) % 3 == 0:
            strip_type = ws.WS2811_STRIP_RGB
            count = len(buf) // 3
        elif len(buf) % 4 == 0:
            strip_type = ws.SK6812_STRIP_RGBW
            count = len(buf) // 4
        else:
            raise RuntimeError("We only support 3 or 4 bytes-per-pixel")

        ws.ws2811_channel_t_count_set(channel, count)
        ws.ws2811_channel_t_gpionum_set(channel, gpio._pin.id)
        ws.ws2811_channel_t_invert_set(channel, LED_INVERT)
        ws.ws2811_channel_t_brightness_set(channel, LED_BRIGHTNESS)
        ws.ws2811_channel_t_strip_type_set(channel, strip_type)

        # Initialise le contrôleur.
        ws.ws2811_t_freq_set(_led_strip, LED_FREQ_HZ)
        ws.ws2811_t_dmanum_set(_led_strip, LED_DMA_NUM)

        resp = ws.ws2811_init(_led_strip)
        if resp != ws.WS2811_SUCCESS:
            if resp == -5:
                raise RuntimeError(
                    "NeoPixel support requires running with sudo, please try again!"
                )
            message = ws.ws2811_get_return_t_str(resp)
            raise RuntimeError(
                "ws2811_init failed with code {0} ({1})".format(resp, message)
            )
        atexit.register(_fast_neopixel_cleanup)

    channel = ws.ws2811_channel_get(_led_strip, led_channel)
    if gpio._pin.id != ws.ws2811_channel_t_gpionum_get(channel):
        raise RuntimeError("Raspberry Pi neopixel support is for one strip only!")

    if ws.ws2811_channel_t_strip_type_get(channel) == ws.WS2811_STRIP_RGB:
        bpp = 3
    else:
        bpp = 4

    # Conversion buffer -> pixels (identique à Blinka).
    for i in range(len(buf) // bpp):
        r = buf[bpp * i]
        g = buf[bpp * i + 1]
        b = buf[bpp * i + 2]
        if bpp == 3:
            pixel = (r << 16) | (g << 8) | b
        else:
            w = buf[bpp * i + 3]
            pixel = (w << 24) | (r << 16) | (g << 8) | b
        ws.ws2811_led_set(channel, i, pixel)

    resp = ws.ws2811_render(_led_strip)
    if resp != ws.WS2811_SUCCESS:
        message = ws.ws2811_get_return_t_str(resp)
        raise RuntimeError(
            "ws2811_render failed with code {0} ({1})".format(resp, message)
        )
    # Attente de fin de trame (Blinka) — INDISPENSABLE : ws2811_render rend la
    # main pendant que le DMA émet encore ; sans cette pause la trame suivante
    # écrase l'émission en cours (glitch « deux signaux », incident 2026-07-13).
    time.sleep(0.001 * ((len(buf) // 100) + 1))


def _fast_neopixel_cleanup():
    """Libère la structure ws2811_t (appelé à la sortie via atexit)."""
    global _led_strip
    if _led_strip is None:
        return
    # Import différé : cohérent avec _fast_neopixel_write (lib Pi uniquement).
    import _rpi_ws281x as ws  # pylint: disable=import-error
    ws.ws2811_fini(_led_strip)
    ws.delete_ws2811_t(_led_strip)
    _led_strip = None


def __getattr__(name):
    """Fournit `FastNeoPixel` en différé (PEP 562).

    On ne peut pas écrire `class FastNeoPixel(neopixel.NeoPixel)` au niveau module
    sans importer `neopixel` (qui tire board/digitalio, absents sur x86) et casser
    la collecte pytest. La classe n'est donc construite qu'au PREMIER accès à
    l'attribut `FastNeoPixel` — c'est-à-dire à l'instanciation côté lights_node,
    sur le Pi uniquement.
    """
    if name == "FastNeoPixel":
        import neopixel  # import différé : lib Pi (board/digitalio) absente sur x86

        class FastNeoPixel(neopixel.NeoPixel):
            """NeoPixel dont `_transmit` passe par l'écriture vendorisée.

            Court-circuite la résolution de backend de Blinka (cassée dans le
            conteneur — voir la docstring du module), sleep de fin de trame
            conservé.
            """

            def _transmit(self, buffer):
                # Même contrat que neopixel.NeoPixel._transmit (self.pin,
                # buffer post-brightness), mais via notre écriture vendorisée.
                _fast_neopixel_write(self.pin, buffer)

        # Mémorise pour les accès suivants (évite de reconstruire la classe).
        globals()["FastNeoPixel"] = FastNeoPixel
        return FastNeoPixel

    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name)
    )
