"""Logique PURE de la télécommande USB : trame montante, axes, règle du menu.

Comme `firmware/pico_odometry/odom_protocol.py`, ce module est le SEUL endroit
où vivent ces conventions, et il tourne à trois endroits sans être recopié :

  1. sur le **RP2040** (firmware `code.py`, lot T2) — il produit les trames ;
  2. dans le **décodeur hôte** (nœud ROS / logiciel du menu) — il les relit ;
  3. dans les **tests unitaires** du dépôt (`robot/tests/unit/`) — sur l'hôte,
     sans boîtier ni matériel.

Tout ce qui peut être *faux* — le masque des boutons, la zone morte, les
bornes des axes, le CRC, et surtout la règle de sécurité du menu — est ici.
C'est ce qui évite d'écrire deux fois une convention et d'inverser un axe (ou
de rendre le menu vivant pendant la conduite) sans s'en apercevoir.

⚠️ CONTRAINTE : ce fichier est copié tel quel sur le RP2040, donc il doit
rester compatible **CircuitPython** — pas d'annotations de type, pas de
dataclasses, pas d'enum, pas de f-strings, aucun import (même standard).

⚠️ Ce module ne commande RIEN et ne lit aucune broche : il ne sait que
fabriquer et relire du texte. Le fichier qui touche les broches est `code.py`,
et il n'est pas importable sur l'hôte.
"""

# ---------------------------------------------------------------------------
#  Les drapeaux (étude §4.3 et §4.4)
# ---------------------------------------------------------------------------
#
# Un seul octet transporte l'homme-mort et les 5 poussoirs. Les valeurs sont
# gravées ici parce qu'elles sont lues des deux côtés du câble : un bit décalé
# côté hôte ferait passer « bouton BAS » pour « homme-mort tenu ».

FLAG_DEADMAN = 0x01     # bit 0 — poussoir sous l'index, TENU = autorisation
FLAG_UP = 0x02          # bit 1 — menu : haut
FLAG_DOWN = 0x04        # bit 2 — menu : bas
FLAG_VALIDATE = 0x08    # bit 3 — menu : valider
FLAG_BACK = 0x10        # bit 4 — menu : retour
FLAG_JOY_SW = 0x20      # bit 5 — clic du manche (réservé, §4.4 : reste ouvert)

FLAGS_MASK = 0x3F       # les 6 bits définis ; le reste de l'octet est libre

# ---------------------------------------------------------------------------
#  Bornes et format de trame (étude §4.5)
# ---------------------------------------------------------------------------
#
#     R;<seq>;<x>;<y>;<flags>;<crc8>\n          émis à 50 Hz, sans condition
#
# - `seq` : compteur 0..255 qui boucle. Il sert à voir les trames perdues,
#   donc un lien qui se dégrade — il n'est pas décoratif.
# - `x`, `y` : entiers SIGNÉS -1000..+1000, zone morte déjà appliquée à bord
#   (§4.7 : la conduite est locale, elle ne dépend ni du menu ni de l'hôte).
# - `flags` : masque hexadécimal MINUSCULE sur 2 chiffres.
# - `crc8` : CRC-8 (polynôme 0x07, init 0x00) sur `R;<seq>;<x>;<y>;<flags>`,
#   c'est-à-dire tout ce qui précède le dernier « ; » — ni ce « ; », ni le
#   « \n ».
#
# ⚠️ **Pourquoi un CRC sur de l'USB, qui a déjà le sien ?** Parce que le CRC de
# l'USB protège le TRANSPORT, pas le décodage. Une trame tronquée à la
# reconnexion, un buffer réassemblé de travers, et `x` prend une valeur
# parfaitement plausible. Sur un chemin qui commande 50 kg de roues, une valeur
# plausible et fausse est le pire cas — pire qu'une absence de trame, que le
# deadman 400 ms en aval sait traiter.

PREFIXE = "R"
SEPARATEUR = ";"
NB_CHAMPS = 6           # R, seq, x, y, flags, crc

SEQ_MODULO = 256        # seq boucle sur un octet
AXE_MAX = 1000          # bornes des axes ET échelle de sortie de la zone morte


def crc8(data):
    """CRC-8 (polynôme 0x07, init 0x00) d'une chaîne ASCII ou d'octets.

    Accepte les deux formes parce que le firmware manipule du texte alors que
    le décodeur hôte lit souvent des `bytes` bruts sur le port série : les
    convertir avant l'appel serait une occasion de plus de se tromper.

    Écrit en clair plutôt qu'en table, comme dans `odom_protocol` : il tourne
    50 fois par seconde sur ~25 octets, le coût est nul, et une table de 256
    valeurs recopiée à la main est une source d'erreur muette.
    """
    reste = 0
    for element in data:
        # Chaîne -> caractères, bytes -> entiers : on normalise ici.
        if isinstance(element, str):
            octet = ord(element) & 0xFF
        else:
            octet = element & 0xFF
        reste ^= octet
        for _ in range(8):
            if reste & 0x80:
                reste = ((reste << 1) ^ 0x07) & 0xFF
            else:
                reste = (reste << 1) & 0xFF
    return reste


def _borner(valeur, maximum):
    """Sature `valeur` dans [-maximum, +maximum]."""
    if valeur > maximum:
        return maximum
    if valeur < -maximum:
        return -maximum
    return valeur


def encode_frame(seq, x, y, flags):
    """Fabrique une trame montante complète, retour à la ligne compris.

    Ne lève jamais **pour des entrées numériques** : à 50 Hz, dans une boucle
    de firmware, une exception sur un axe hors borne arrêterait l'émission —
    donc couperait la seule preuve de vie du boîtier, et l'hôte ne saurait plus
    distinguer un manche au repos d'un câble arraché. On borne et on émet ;
    c'est le côté sûr de l'erreur. En revanche un argument d'un AUTRE type
    (None, chaîne…) lève : c'est une erreur de programmation de l'appelant, pas
    une valeur de capteur, et elle doit se voir au lot T2, pas en scène.
    """
    charge = "%s;%d;%d;%d;%02x" % (
        PREFIXE,
        seq % SEQ_MODULO,
        _borner(x, AXE_MAX),
        _borner(y, AXE_MAX),
        flags & 0xFF,
    )
    return "%s;%02x\n" % (charge, crc8(charge))


CHIFFRES = "0123456789"


def _entier(texte):
    """Champ décimal signé -> entier, ou None s'il n'est pas EXACTEMENT ça.

    `int()` seul serait trop accueillant : il accepte " 12 ", "+12", "1_2".
    Un champ qui a besoin d'être « nettoyé » pour être lu est un champ dont on
    ne sait pas d'où il vient — on le refuse.

    Le contrôle est **strictement ASCII**, chiffre par chiffre, et non pas
    `str.isdigit()` : celui-ci est vrai sur CPython pour les chiffres
    arabes-indiens ou pleine chasse (« ١٢ », « １２ »), que `int()` convertit
    d'ailleurs sans broncher — mais il ne l'est PAS sur MicroPython. Le module
    tourne des deux côtés du câble : une règle d'acceptation qui dépend de
    l'interpréteur est une divergence dormante entre le boîtier et l'hôte.
    """
    if not texte:
        return None
    corps = texte[1:] if texte[0] == "-" else texte
    if not corps:
        return None
    for caractere in corps:
        if CHIFFRES.find(caractere) < 0:
            return None
    try:
        return int(texte)
    except ValueError:
        # Gardé pour un seul cas réel : CPython >= 3.11 refuse de convertir
        # au-delà de 4300 chiffres. Un champ pareil n'est pas une trame, mais
        # il ne doit pas non plus faire tomber la boucle de décodage.
        return None


def _hexa2(texte):
    """Champ hexadécimal de 2 chiffres -> entier 0..255, ou None.

    Longueur imposée : un champ d'une ou trois positions n'est pas une trame de
    ce protocole, c'est une trame d'autre chose (ou une trame coupée).
    """
    if not texte or len(texte) != 2:
        return None
    valeur = 0
    for caractere in texte:
        chiffre = "0123456789abcdef".find(caractere.lower())
        if chiffre < 0:
            return None
        valeur = (valeur << 4) | chiffre
    return valeur


class RemoteState(object):
    """État décodé d'UNE trame montante. Rien de plus : pas d'historique.

    Volontairement passif — c'est l'appelant qui décide quoi en faire, et lui
    seul qui connaît le temps (péremption, trames perdues).
    """

    def __init__(self, seq, x, y, flags):
        self.seq = seq
        self.x = x
        self.y = y
        self.flags = flags

    @property
    def deadman(self):
        """Homme-mort TENU. Absent = pas d'autorisation de rouler."""
        return pressed(self.flags, FLAG_DEADMAN)

    @property
    def menu_enabled(self):
        # Une SEULE implémentation de la règle de sécurité : on délègue à la
        # fonction du module (visible d'ici — les méthodes ne voient pas le
        # corps de la classe, donc ce nom désigne bien la fonction globale).
        return menu_enabled(self.flags)

    def __repr__(self):
        return "RemoteState(seq=%d, x=%d, y=%d, flags=0x%02x)" % (
            self.seq, self.x, self.y, self.flags,
        )


BORDS = " \t\r\n"


def decode_frame(line):
    """Relit une trame montante. Renvoie un `RemoteState`, ou None si invalide.

    Accepte du texte OU des octets (`bytes`/`bytearray`), parce que c'est sous
    cette forme que le décodeur hôte lit le port série. Tout autre type renvoie
    None : ce décodeur est appelé dans une boucle de lecture, il doit REFUSER,
    jamais lever.

    TOUT ce qui n'est pas une trame parfaitement formée et au bon CRC renvoie
    None — jamais une valeur approchée, jamais un champ « rattrapé ». Même
    principe que le décodage StringTime du reste du projet : une charge utile
    invalide est un REFUS, pas une perte silencieuse. Ici l'enjeu est plus
    direct encore : un `x` à moitié lu, c'est une consigne de vitesse inventée.

    Refuser coûte une trame, soit 20 ms à 50 Hz — la suivante arrive. Et si
    elles sont TOUTES refusées, l'absence de commande valide fait tomber le
    deadman 400 ms en aval, qui arrête le robot. L'échec va du bon côté.
    """
    if isinstance(line, (bytes, bytearray)):
        # latin-1 et PAS ascii : il est bijectif sur 0..255, donc il ne lève
        # jamais — or un octet > 0x7F est exactement le cas de corruption pour
        # lequel le CRC existe, et une exception là serait une panne de lecture
        # au lieu d'un simple refus. Bonus : latin-1 fait correspondre chaque
        # octet à `chr(octet)`, donc au `ord(c) & 0xFF` de `crc8` — le CRC
        # calculé sur le texte et sur les octets donne la même valeur.
        line = line.decode("latin-1")
    elif not isinstance(line, str):
        return None
    if not line:
        return None
    # Tolérance strictement limitée au bord de ligne : \r\n d'un terminal,
    # espaces d'un copier-coller. Rien n'est nettoyé À L'INTÉRIEUR de la trame.
    # Liste EXPLICITE et non `strip()` sans argument : celui-ci retire en plus,
    # sur CPython seulement, les espaces unicode (NBSP, U+2007, U+0085) — une
    # trame acceptée par l'hôte et refusée par le boîtier, ou l'inverse.
    ligne = line.strip(BORDS)
    if not ligne.startswith(PREFIXE + SEPARATEUR):
        return None
    morceaux = ligne.split(SEPARATEUR)
    if len(morceaux) != NB_CHAMPS:
        return None

    seq = _entier(morceaux[1])
    x = _entier(morceaux[2])
    y = _entier(morceaux[3])
    flags = _hexa2(morceaux[4])
    crc_lu = _hexa2(morceaux[5])
    if seq is None or x is None or y is None or flags is None or crc_lu is None:
        return None

    # Bornes du protocole : hors intervalle, ce n'est pas « à corriger », c'est
    # une trame dont on ne sait rien. `seq` est un octet, les axes ±1000.
    if seq < 0 or seq >= SEQ_MODULO:
        return None
    if x < -AXE_MAX or x > AXE_MAX or y < -AXE_MAX or y > AXE_MAX:
        return None

    if crc_lu != crc8(SEPARATEUR.join(morceaux[:5])):
        return None
    return RemoteState(seq, x, y, flags)


def pressed(flags, flag):
    """Vrai si le bit `flag` est présent dans `flags`."""
    return (flags & flag) != 0


def menu_enabled(flags):
    """Le menu accepte-t-il les touches ? RÈGLE DE SÉCURITÉ du §4.4.

    **Faux dès que l'homme-mort est tenu**, quelles que soient les autres
    touches. Naviguer un écran à deux mains pendant que 50 kg roulent, c'est
    l'accident. Cette règle vit ici, et nulle part ailleurs : l'écran, le menu
    hôte et le firmware doivent tous l'obtenir de cette fonction — dupliquée,
    elle finirait par diverger d'un côté, et ce côté-là serait dangereux.
    """
    return not pressed(flags, FLAG_DEADMAN)


def apply_deadzone(raw, center, span, deadzone):
    """Lecture brute d'ADC -> axe -1000..+1000, zone morte comprise.

    `raw` et `center` sont bruts (unités de l'ADC), `span` est la demi-course
    brute (> 0), `deadzone` est exprimée **en unités de SORTIE** (0..1000) —
    c'est-à-dire dans l'échelle qu'on lit dans la trame, pas dans celle du
    convertisseur, qui dépend du module et de sa résolution.

    ⚠️ La sortie est **re-étalée** au-delà de la zone morte : elle repart de 0
    au bord de celle-ci et atteint ±1000 en butée. Sans ça, le robot passerait
    d'un arrêt à 15 % de vitesse dès que le manche quitte la zone morte — un
    à-coup de 50 kg, à l'endroit précis où l'opérateur cherche la finesse. Le
    prix payé est une légère perte de résolution, invisible à la main — mais
    seulement pour une `deadzone` raisonnable : à `deadzone=999` il ne reste
    qu'une unité de course utile et la sortie saute de 0 à ±1000 en un pas
    d'ADC, ce qui est le contraire de l'effet recherché.

    Ne lève jamais : `span` nul ou négatif (paramètre pas encore calibré) donne
    0, une lecture aberrante sature. Un axe faux doit produire un arrêt, pas
    une exception qui tue la boucle d'émission.
    """
    if span <= 0:
        return 0
    if deadzone >= AXE_MAX:
        # Zone morte couvrant toute la course : le manche est inerte. Cas
        # dégénéré d'une mauvaise calibration, traité comme « pas de commande ».
        return 0
    if deadzone < 0:
        deadzone = 0

    ecart = raw - center
    signe = -1 if ecart < 0 else 1

    # Saturation AVANT le re-étalement : ça garde l'arithmétique dans de petits
    # entiers, ce qui compte sur le microcontrôleur, et le résultat est le même.
    magnitude = abs(ecart) * AXE_MAX // span
    if magnitude > AXE_MAX:
        magnitude = AXE_MAX
    if magnitude <= deadzone:
        return 0

    sortie = (magnitude - deadzone) * AXE_MAX // (AXE_MAX - deadzone)
    if sortie > AXE_MAX:
        sortie = AXE_MAX
    return signe * sortie
