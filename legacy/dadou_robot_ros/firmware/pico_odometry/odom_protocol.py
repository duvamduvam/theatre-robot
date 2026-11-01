"""Logique PURE de l'odométrie : décodage quadrature + protocole de trame.

Ce module est le SEUL endroit où vit ce raisonnement, et il tourne à trois
endroits sans être recopié :

  1. sur le **Pico** (firmware `main.py`) — il produit les trames ;
  2. dans le **nœud ROS 2** côté Pi — il les relit ;
  3. dans les **tests unitaires** du dépôt (`robot/tests/unit/`) — sur l'hôte,
     sans Pico ni matériel.

C'est la règle du projet : la vérification exécute le même code que la prod.
Un décodeur de quadrature retesté « en gros » dans un test qui le réécrit ne
prouve rien — c'est exactement comme ça qu'on inverse un signe sans le voir.

⚠️ CONTRAINTE : ce fichier est copié tel quel sur le Pico, donc il doit rester
compatible **MicroPython** — pas d'annotations de type, pas de dataclasses, pas
de f-strings, aucun import de la bibliothèque standard CPython.
"""

# ---------------------------------------------------------------------------
#  Décodage de quadrature ×4
# ---------------------------------------------------------------------------
#
# L'état des deux capteurs d'une roue est un mot de 2 bits : (B << 1) | A.
# En tournant, il parcourt un code de Gray — un SEUL bit change à la fois :
#
#       00 → 01 → 11 → 10 → 00 →  (un sens)
#       00 → 10 → 11 → 01 → 00 →  (l'autre)
#
# D'où le décodage : on indexe par (état_précédent << 2) | état_courant, et la
# table donne le pas. Les 4 index où les DEUX bits changent d'un coup sont
# IMPOSSIBLES physiquement — sauf si on a raté un front. On ne les compte pas
# comme 0 en silence : on les compte à part (`illegal`), parce qu'ils sont le
# symptôme observable d'une odométrie en train de mentir.
#
# ⚠️ Le SIGNE n'est pas une vérité absolue : il dépend du câblage (quel capteur
# est A) et du sens de montage de la roue. Il se fixe par `invert`, et se
# détermine au protocole caméra — jamais depuis un fauteuil.
#
# ⚠️ À NOTER, et c'est rassurant : les PC817 inversent la logique (« métal
# détecté = niveau BAS », étude §5). Inverser les DEUX voies transforme la
# séquence 00→01→11→10 en 11→10→00→01 — le même cycle, décalé. Le SENS est
# donc inchangé par l'inversion des optocoupleurs. Il n'y a rien à corriger.

QUAD_DELTA = (
    #  vers 00  01  10  11        depuis
    0, +1, -1, 0,              # 00
    -1, 0, 0, +1,              # 01
    +1, 0, 0, -1,              # 10
    0, -1, +1, 0,              # 11
)

# Les 4 transitions où les deux bits basculent ensemble : un front a été perdu.
QUAD_ILLEGAL = (
    False, False, False, True,
    False, False, True, False,
    False, True, False, False,
    True, False, False, False,
)


class QuadratureDecoder(object):
    """Accumule les pas d'UNE roue à partir des états successifs (0..3).

    Ne connaît ni le temps, ni le matériel : on lui pousse des états, il compte.
    C'est ce qui le rend testable sans Pico.
    """

    def __init__(self, invert=False):
        self.ticks = 0          # compteur cumulé, signé
        self.illegal = 0        # transitions impossibles vues (santé du lien)
        self._state = None      # None = on n'a pas encore d'état de référence
        self._sign = -1 if invert else 1

    def update(self, state):
        """Intègre un nouvel état de 2 bits. Renvoie le pas appliqué (-1/0/+1).

        Le tout PREMIER état ne produit aucun pas : sans état précédent, il n'y
        a pas de transition, donc pas de déplacement. Compter 1 ici ajouterait
        un tick fantôme à chaque démarrage.
        """
        state &= 0x03
        if self._state is None:
            self._state = state
            return 0
        index = (self._state << 2) | state
        self._state = state
        if QUAD_ILLEGAL[index]:
            self.illegal += 1
            return 0
        step = QUAD_DELTA[index] * self._sign
        self.ticks = wrap_ticks(self.ticks + step)
        return step


# ---------------------------------------------------------------------------
#  Protocole de trame (étude §6)
# ---------------------------------------------------------------------------
#
#     ODO <seq> <ticks_gauche> <ticks_droite> <crc>\n
#
# - `seq` : compteur 16 bits qui boucle. Ce n'est PAS décoratif — c'est lui
#   qui permet au Pi de voir qu'une trame a été perdue ou que le lien est mort.
# - `ticks` : compteurs CUMULÉS et signés (pas des deltas). Choix délibéré :
#   une trame perdue ne perd alors aucune distance, la suivante rattrape tout
#   d'elle-même. Avec des deltas, chaque trame perdue serait un morceau de
#   trajet effacé pour toujours — silencieusement.
# - `crc` : CRC-8 sur le texte qui précède, en deux chiffres hexadécimaux.
#
# La trame est du TEXTE, débogable à la main par un simple `cat` sur le port.

TICKS_MODULO = 0x100000000       # les compteurs bouclent sur 32 bits signés
TICKS_SIGNE = 0x80000000
SEQ_MODULO = 0x10000             # seq boucle sur 16 bits


def wrap_ticks(value):
    """Ramène un compteur dans l'intervalle 32 bits SIGNÉ.

    Le Pico compterait en entiers illimités (Python), mais le nœud ROS doit
    savoir gérer le bouclage : autant boucler dès la source, pour que le cas
    soit exercé en permanence plutôt que découvert au bout de trois mois.
    """
    value &= (TICKS_MODULO - 1)
    if value >= TICKS_SIGNE:
        value -= TICKS_MODULO
    return value


def delta_ticks(precedent, courant):
    """Écart entre deux compteurs cumulés, bouclage 32 bits compris.

    C'est LA fonction que le nœud ROS doit utiliser — jamais `courant -
    precedent`, qui produirait un saut de 4 milliards de ticks au bouclage,
    donc un téléport dans la carte de nav2.
    """
    return wrap_ticks(courant - precedent)


def crc8(texte):
    """CRC-8 (polynôme 0x07, init 0x00) sur l'ASCII de `texte`.

    Volontairement écrit en clair plutôt qu'en table : il tourne 50 fois par
    seconde sur des chaînes de ~30 octets, le coût est nul, et une table de
    256 valeurs recopiée à la main est une source d'erreur muette.
    """
    reste = 0
    for caractere in texte:
        reste ^= ord(caractere) & 0xFF
        for _ in range(8):
            if reste & 0x80:
                reste = ((reste << 1) ^ 0x07) & 0xFF
            else:
                reste = (reste << 1) & 0xFF
    return reste


def build_frame(seq, ticks_gauche, ticks_droite):
    """Fabrique une trame ODO complète, retour à la ligne compris."""
    charge = "ODO %d %d %d" % (
        seq % SEQ_MODULO,
        wrap_ticks(ticks_gauche),
        wrap_ticks(ticks_droite),
    )
    return "%s %02X\n" % (charge, crc8(charge))


def parse_frame(ligne):
    """Relit une trame. Renvoie (seq, gauche, droite), ou None si invalide.

    TOUT ce qui n'est pas une trame ODO parfaitement formée et au bon CRC
    renvoie None — jamais une valeur approchée. Le principe est celui du
    décodage StringTime du reste du projet : une charge utile invalide est un
    REFUS loggué, pas une perte silencieuse. Une trame à moitié lue, en
    odométrie, c'est un robot qui croit avoir avancé.
    """
    if not ligne:
        return None
    ligne = ligne.strip()
    if not ligne.startswith("ODO "):
        return None
    morceaux = ligne.split(" ")
    if len(morceaux) != 5:
        return None
    try:
        seq = int(morceaux[1])
        gauche = int(morceaux[2])
        droite = int(morceaux[3])
        crc_lu = int(morceaux[4], 16)
    except ValueError:
        return None
    if crc_lu != crc8(" ".join(morceaux[:4])):
        return None
    return (seq, gauche, droite)


def seq_perdues(seq_precedent, seq_courant):
    """Nombre de trames manquantes entre deux `seq` consécutifs (0 si aucune).

    Bouclage 16 bits compris. Sert au nœud ROS à publier un diagnostic honnête
    plutôt qu'à faire semblant que le lien est parfait.
    """
    return (seq_courant - seq_precedent - 1) % SEQ_MODULO
