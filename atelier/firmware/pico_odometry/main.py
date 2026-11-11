"""Firmware Pico — comptage des 4 capteurs d'odométrie, trames vers le Pi.

Cible : Raspberry Pi Pico sous **MicroPython**, à déposer comme `main.py` avec
`odom_protocol.py` à côté (voir README.md).

⚠️ RÈGLE NON NÉGOCIABLE (étude §6) : **le Pico ne commande RIEN.** Il lit, il
compte, il rapporte. Il n'est pas sur le chemin de commande des roues. Si ce
lien meurt, on perd l'odométrie — donc la navigation autonome s'arrête — mais
AUCUN rempart de sécurité ne tombe : le deadman 400 ms de `wheels_node` reste
intact. Une panne d'odométrie ne peut produire qu'un arrêt, jamais un
emballement. Rien dans ce fichier ne doit jamais piloter une sortie.

Architecture, et pourquoi le PIO :
    Chaque roue a sa propre machine à états PIO qui SURVEILLE ses 2 broches et
    pousse le nouvel état de 2 bits dans sa FIFO à chaque changement. Le CPU
    vide les FIFO et décode (`odom_protocol.QuadratureDecoder`).

    L'intérêt n'est pas la vitesse — à 1 m/s chaque capteur ne sort que ~13
    impulsions/s, un facteur mille sous ce qu'un RP2040 encaisse. L'intérêt est
    l'ÉLASTICITÉ : la FIFO absorbe les pauses du ramasse-miettes MicroPython et
    tout retard de la boucle principale. Aucun front ne peut être manqué parce
    que le CPU regardait ailleurs — c'est précisément le défaut qui a fait
    écarter un comptage en Python sur le Pi 4.

    Et le `push()` est BLOQUANT : FIFO pleine, la machine à états attend au
    lieu de jeter l'événement. On peut prendre du retard, jamais perdre un pas.
"""

import sys

from machine import Pin, WDT
from micropython import const
from utime import ticks_diff, ticks_ms, sleep_ms

import rp2

from odom_protocol import QuadratureDecoder, build_frame

# ---------------------------------------------------------------------------
#  Brochage — DÉFINITIF, identique au schéma KiCad (wheel-odometry) et à la
#  plaque à trous de l'étape 2. Le firmware validé à l'établi est ainsi
#  exactement celui qui tournera sur la carte gravée.
# ---------------------------------------------------------------------------

GP_GAUCHE_A = const(2)      # ODO_LA — roue gauche, capteur A
# ODO_LB = GP3, contigu : la machine à états lit 2 broches à partir de la base.
GP_DROITE_A = const(4)      # ODO_RA — roue droite, capteur A
# ODO_RB = GP5, contigu.

# ⚠️ GP25 = LED intégrée DU PICO. Sur une **RP2040-Zero** (envisagée le 30/08)
# il n'y a PAS de LED sur GP25 : la carte porte une WS2812 RGB sur GP16.
# Le piège est muet — `Pin(25, Pin.OUT)` ne lève aucune erreur, la broche existe
# sur la puce, elle ne va simplement nulle part : le témoin de vie meurt sans
# un seul message, et c'est le premier moyen de savoir si le firmware tourne
# sans brancher d'ordinateur. Si on passe à la Zero : NE PAS importer un pilote
# NeoPixel pour ça — la carte prévoit déjà une LED de diagnostic par canal
# (étude §8 étape 4), en ajouter une sur un GPIO libre garde ce fichier simple.
GP_LED = const(25)          # LED intégrée : témoin de vie (Pico uniquement)

# Sens de comptage. INCONNU tant que le protocole caméra n'a pas été fait :
# il dépend du câblage et du montage de chaque roue. On ne le devine pas, on
# le MESURE (roue en l'air, on pousse la roue vers l'avant à la main, le
# compteur doit monter). Tant que ce n'est pas fait, ces deux valeurs sont des
# hypothèses assumées, pas des vérités.
INVERSER_GAUCHE = False
INVERSER_DROITE = False

# La carte fournit un rappel de 10 kΩ vers le 3,3 V (étude §5) : c'est LUI qui
# fabrique le niveau haut, le capteur NPN ne sachant que tirer vers la masse.
# Mettre True UNIQUEMENT pour un essai d'établi sans la carte — le rappel
# interne (~50 kΩ) suffit à voir bouger un signal, pas à tenir un câble d'1 m
# le long d'un moteur à balais.
RAPPEL_INTERNE = False

PERIODE_TRAME_MS = const(20)        # 50 Hz, comme prévu à l'étude §6
PERIODE_STAT_MS = const(5000)       # bilan de santé, plus lent (diagnostic)
WDT_MS = const(4000)                # chien de garde : le Pico se relance seul
FREQ_PIO = const(500_000)           # 100 k échantillons/s après la boucle de 5
                                    # instructions — 4 décades au-dessus du
                                    # besoin, et ça filtre les glitches < 10 µs


# ---------------------------------------------------------------------------
#  La machine à états PIO : « pousse l'état quand il change »
# ---------------------------------------------------------------------------
#
# Cinq instructions, aucune arithmétique : c'est volontaire. Tout le décodage
# (donc tout ce qui peut être FAUX) vit dans odom_protocol.py, testé sur
# l'hôte. Le PIO ne fait que ce qu'on ne peut pas tester ailleurs : regarder
# des broches sans jamais cligner.
#
# fifo_join=JOIN_RX donne 8 mots de profondeur au lieu de 4. À ~13 événements
# par seconde et par roue pour une lecture toutes les 20 ms, c'est un matelas
# de plusieurs secondes.

@rp2.asm_pio(autopush=False, in_shiftdir=rp2.PIO.SHIFT_LEFT,
             fifo_join=rp2.PIO.JOIN_RX)
def surveiller_etat():
    # État de départ dans X, sans rien pousser : au démarrage il n'y a pas de
    # transition, donc pas de pas (le décodeur ignore de toute façon son
    # premier état — ceinture et bretelles).
    mov(isr, null)
    in_(pins, 2)
    mov(x, isr)

    wrap_target()
    mov(isr, null)
    in_(pins, 2)
    mov(y, isr)
    jmp(x_not_y, "change")
    jmp("boucle")
    label("change")
    push()                  # BLOQUANT : on attend plutôt que de jeter un pas
    mov(x, y)
    label("boucle")
    wrap()


def demarrer_machine(numero, broche_base):
    """Arme une machine à états sur 2 broches contiguës (A puis B)."""
    tirage = Pin.PULL_UP if RAPPEL_INTERNE else None
    for decalage in (0, 1):
        Pin(broche_base + decalage, Pin.IN, tirage)
    machine = rp2.StateMachine(
        numero, surveiller_etat,
        freq=FREQ_PIO,
        in_base=Pin(broche_base),
    )
    machine.active(1)
    return machine


def main():
    led = Pin(GP_LED, Pin.OUT)

    roues = (
        (demarrer_machine(0, GP_GAUCHE_A), QuadratureDecoder(INVERSER_GAUCHE)),
        (demarrer_machine(1, GP_DROITE_A), QuadratureDecoder(INVERSER_DROITE)),
    )
    gauche, droite = roues[0][1], roues[1][1]

    # Le chien de garde n'est armé qu'ICI, une fois les machines à états
    # lancées : s'il l'était avant et que l'initialisation échouait, le Pico
    # redémarrerait en boucle sans jamais laisser voir l'erreur.
    chien = WDT(timeout=WDT_MS)

    seq = 0
    prochaine_trame = ticks_ms()
    prochain_stat = ticks_ms() + PERIODE_STAT_MS

    while True:
        chien.feed()

        # 1. Vider les FIFO. À faire à CHAQUE tour, pas seulement à l'instant
        #    d'émettre : c'est ce qui garde le matelas disponible.
        for machine, decodeur in roues:
            while machine.rx_fifo():
                decodeur.update(machine.get())

        maintenant = ticks_ms()

        # 2. Émettre la trame à 50 Hz, cadence tenue par échéance absolue (et
        #    non par un sleep de 20 ms, qui dériverait du temps de la boucle).
        if ticks_diff(maintenant, prochaine_trame) >= 0:
            prochaine_trame += PERIODE_TRAME_MS
            seq += 1
            sys.stdout.write(build_frame(seq, gauche.ticks, droite.ticks))
            if seq % 25 == 0:
                led.toggle()        # ~1,2 Hz : « je tourne et j'émets »

        # 3. Bilan de santé, sur une ligne à part : le nœud ROS ignore les
        #    lignes qu'il ne connaît pas, donc le format ODO reste intact.
        #    `illegal` non nul = des fronts se perdent (entrefer trop grand,
        #    câble parasité, disque qui bat) : c'est le seul symptôme visible
        #    d'une odométrie qui commence à mentir. Il ne doit JAMAIS grimper.
        if ticks_diff(maintenant, prochain_stat) >= 0:
            prochain_stat += PERIODE_STAT_MS
            sys.stdout.write("STAT illegal_g=%d illegal_d=%d\n"
                             % (gauche.illegal, droite.illegal))

        sleep_ms(1)


main()
