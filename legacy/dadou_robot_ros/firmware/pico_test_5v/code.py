"""Témoin d'arrivée 5 V — RP2040-Zero / RP2040-One (CircuitPython).

Sacrifiable : on branche CETTE carte sur le rail 5 V du robot AVANT d'y
remettre les Raspberry Pi. Elle ne commande rien, elle ne fait que clignoter.

CE QUE LA COULEUR DIT — c'est tout l'intérêt du montage :

    5 flashs blancs  = la carte VIENT de démarrer (signature de boot)
    rouge            = elle tourne depuis moins de 10 s
    orange           = moins d'une minute
    jaune            = moins de cinq minutes
    vert             = plus de cinq minutes sans redémarrer  →  le rail tient

Un rail qui s'effondre sous charge fait redémarrer la carte : la séquence de
boot repart et la couleur retombe au rouge. C'est ça qu'on cherche à voir, et
c'est précisément ce qu'une LED bêtement allumée ne montre PAS.

⚠️ LIMITE À CONNAÎTRE — « ça clignote » ne veut pas dire « bon pour un Pi ».
Le régulateur de la carte tient encore sous 3 V : elle clignotera gaiement sur
un rail à 3,8 V qui ferait planter un Raspberry Pi 4 (qui exige 4,75-5,25 V).
Ce programme prouve la PRÉSENCE et la STABILITÉ du rail, pas sa VALEUR.
Pour la valeur : multimètre, ou le pont diviseur optionnel ci-dessous.
"""

import time

import board
import digitalio
import neopixel_write

# --- Câblage -----------------------------------------------------------------

# ⚠️ La LED de la Zero/One est une WS2812 RGB sur GP16. Il n'y a AUCUNE LED sur
# GP25 (c'est celle du Pico officiel) : `DigitalInOut(GP25)` n'aurait levé
# aucune erreur — la broche existe sur la puce — et le témoin serait resté noir
# sans le moindre message. Piège déjà consigné dans ../pico_odometry/README.md.
BROCHE_LED = getattr(board, "NEOPIXEL", board.GP16)

# Mesure de tension : DÉSACTIVÉE par défaut, car elle exige un pont diviseur
# externe. Mettre le rapport du pont ici pour l'activer (2.0 = deux résistances
# égales, p. ex. 2 × 100 kΩ, qui ramènent 5 V à 2,5 V).
#
# ⛔ NE JAMAIS relier le 5 V directement à une broche : les entrées du RP2040
#    sont en 3,3 V et une injection à 5 V détruit la broche, voire la puce.
DIVISEUR = None
BROCHE_MESURE = board.GP26  # A0 — utilisée seulement si DIVISEUR n'est pas None
PLAGE_PI = (4.75, 5.25)  # ce qu'un Raspberry Pi 4 exige à son entrée

# --- Rythme et couleurs ------------------------------------------------------

# Les couleurs restent volontairement sombres : une WS2812 à pleine puissance
# éblouit et sature l'œil, ce qui rend les teintes indiscernables.
FLASHS_BOOT = 5
DUREE_FLASH_S = 0.08

# (ancienneté en secondes, couleur) — le premier palier atteint gagne.
PALIERS = (
    (10, (60, 0, 0)),  # rouge   — démarrage tout frais
    (60, (55, 18, 0)),  # orange
    (300, (45, 45, 0)),  # jaune
)
COULEUR_STABLE = (0, 60, 0)  # vert — au-delà du dernier palier
COULEUR_ALERTE = (60, 0, 60)  # violet — tension hors plage (mémorisé)

PERIODE_BATTEMENT_S = 1.0
# Double flash « toc-toc » : deux fenêtres allumées par seconde. Un motif
# temporel, pas une couleur — impossible à confondre avec la signature de boot.
FENETRES_ALLUMEES = ((0.00, 0.09), (0.20, 0.29))


class Temoin:
    """La WS2812, écrite UNIQUEMENT quand la couleur change.

    Réécrire la trame à chaque tour de boucle est inutile et risqué : le
    dépôt a déjà perdu un visage entier sur des trames WS2812 trop
    rapprochées (docs/incidents/2026-07-13-glitch-visage-driver-led.md).
    N'écrire que sur changement espace naturellement les trames de ≥ 80 ms.
    """

    def __init__(self, broche):
        self._pin = digitalio.DigitalInOut(broche)
        self._pin.direction = digitalio.Direction.OUTPUT
        self._derniere = None

    def couleur(self, rvb):
        if rvb == self._derniere:
            return
        self._derniere = rvb
        rouge, vert, bleu = rvb
        # ⚠️ La WS2812 attend l'ordre VERT, ROUGE, BLEU — pas RVB.
        neopixel_write.neopixel_write(self._pin, bytearray((vert, rouge, bleu)))

    def eteindre(self):
        self.couleur((0, 0, 0))


def sequence_de_boot(temoin):
    """Signature de démarrage : impossible à confondre avec le régime.

    C'est le seul moyen de distinguer « ça tourne depuis le début » de « ça
    vient de redémarrer pour la troisième fois ».
    """
    for _ in range(FLASHS_BOOT):
        temoin.couleur((50, 50, 50))
        time.sleep(DUREE_FLASH_S)
        temoin.eteindre()
        time.sleep(DUREE_FLASH_S)


def couleur_du_moment(anciennete_s):
    for seuil, couleur in PALIERS:
        if anciennete_s < seuil:
            return couleur
    return COULEUR_STABLE


def lecteur_de_tension():
    """Renvoie une fonction de lecture, ou None si la mesure est désactivée.

    Sur Zero/One il n'existe aucun pont diviseur interne vers le rail (le Pico
    officiel, lui, en a un sur VSYS). Sans pont externe, lire l'ADC ne
    mesurerait qu'une broche flottante : on préfère ne RIEN afficher plutôt
    qu'une tension inventée.
    """
    if DIVISEUR is None:
        return None
    import analogio

    entree = analogio.AnalogIn(BROCHE_MESURE)

    def lire():
        # read_u16() est mis à l'échelle sur 16 bits quelle que soit la
        # résolution réelle du convertisseur (12 bits sur RP2040).
        brut = sum(entree.value for _ in range(16)) / 16
        return brut / 65535 * entree.reference_voltage * DIVISEUR

    return lire


def main():
    temoin = Temoin(BROCHE_LED)
    sequence_de_boot(temoin)

    lire_tension = lecteur_de_tension()
    depart_ns = time.monotonic_ns()
    # Latché volontairement : on veut savoir qu'un creux A EU LIEU même si on
    # regarde la carte dix minutes plus tard.
    defaut_vu = False
    mini = None
    prochain_rapport_s = 0.0

    while True:
        anciennete_s = (time.monotonic_ns() - depart_ns) / 1_000_000_000

        if lire_tension is not None:
            tension = lire_tension()
            mini = tension if mini is None else min(mini, tension)
            if not (PLAGE_PI[0] <= tension <= PLAGE_PI[1]):
                defaut_vu = True
            if anciennete_s >= prochain_rapport_s:
                prochain_rapport_s = anciennete_s + 10
                print(
                    "t={:.0f}s  {:.2f} V  mini={:.2f} V  {}".format(
                        anciennete_s, tension, mini, "DEFAUT" if defaut_vu else "ok"
                    )
                )

        phase = anciennete_s % PERIODE_BATTEMENT_S
        allumee = any(debut <= phase < fin for debut, fin in FENETRES_ALLUMEES)
        if allumee:
            couleur = COULEUR_ALERTE if defaut_vu else couleur_du_moment(anciennete_s)
            temoin.couleur(couleur)
        else:
            temoin.eteindre()

        time.sleep(0.01)


main()
