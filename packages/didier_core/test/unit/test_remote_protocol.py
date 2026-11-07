"""Tests du protocole de la télécommande USB (boîtier RP2040, étude §4).

Ces tests exercent EXACTEMENT le code qui tournera sur le RP2040 et dans le
décodeur hôte (`firmware/remote_usb/remote_protocol.py`), pas une
reproduction. C'est la règle du projet, et elle est ici doublement due : ce
module porte l'homme-mort d'une machine de 50 kg, et une convention recopiée
finit toujours par diverger du côté qui n'est pas testé.
"""

import pytest

from remote_protocol import (
    AXE_MAX,
    FLAG_BACK,
    FLAG_DEADMAN,
    FLAG_DOWN,
    FLAG_JOY_SW,
    FLAG_UP,
    FLAG_VALIDATE,
    FLAGS_MASK,
    RemoteState,
    apply_deadzone,
    crc8,
    decode_frame,
    encode_frame,
    menu_enabled,
    pressed,
)


# ---------------------------------------------------------------------------
#  Les drapeaux
# ---------------------------------------------------------------------------

def test_chaque_drapeau_occupe_un_bit_distinct():
    # Deux boutons sur le même bit, et l'hôte confondrait « valider » avec
    # « retour » — ou pire, un bouton avec l'homme-mort.
    drapeaux = (FLAG_DEADMAN, FLAG_UP, FLAG_DOWN, FLAG_VALIDATE,
                FLAG_BACK, FLAG_JOY_SW)
    assert sorted(drapeaux) == [0x01, 0x02, 0x04, 0x08, 0x10, 0x20]
    cumul = 0
    for drapeau in drapeaux:
        assert cumul & drapeau == 0
        cumul |= drapeau
    assert cumul == FLAGS_MASK


def test_chaque_drapeau_est_epingle_a_sa_valeur():
    # Le test ci-dessus est invariant par PERMUTATION : échanger FLAG_UP et
    # FLAG_DOWN le laisserait vert. Or le firmware `code.py` (lot T2) câblera
    # les poussoirs d'après ces bits précis, et l'hôte les relira de même : un
    # échange silencieux donnerait un menu qui descend quand on monte —
    # inutilisable en scène, et sans rien pour le signaler.
    assert FLAG_DEADMAN == 0x01
    assert FLAG_UP == 0x02
    assert FLAG_DOWN == 0x04
    assert FLAG_VALIDATE == 0x08
    assert FLAG_BACK == 0x10
    assert FLAG_JOY_SW == 0x20


def test_pressed_lit_le_bon_bit():
    flags = FLAG_DEADMAN | FLAG_VALIDATE
    assert pressed(flags, FLAG_DEADMAN)
    assert pressed(flags, FLAG_VALIDATE)
    assert not pressed(flags, FLAG_UP)
    assert not pressed(0, FLAG_DEADMAN)


# ---------------------------------------------------------------------------
#  SÉCURITÉ : le menu est inerte tant que l'homme-mort est tenu (§4.4)
# ---------------------------------------------------------------------------

def test_SECURITE_le_menu_est_inerte_des_que_lhomme_mort_est_tenu():
    # Règle NON négociable de l'étude : naviguer un écran à deux mains pendant
    # que 50 kg roulent, c'est l'accident. On balaie les 64 combinaisons des 6
    # bits : AUCUNE ne doit rendre le menu vivant si l'homme-mort est tenu.
    # Le bit de l'homme-mort est épinglé ici même : le balayage ci-dessous
    # resterait vert si FLAG_DEADMAN passait sur le bit d'un autre bouton — il
    # vérifierait alors fidèlement la règle appliquée au MAUVAIS poussoir.
    assert FLAG_DEADMAN == 0x01
    for flags in range(FLAGS_MASK + 1):
        if flags & FLAG_DEADMAN:
            assert menu_enabled(flags) is False
        else:
            assert menu_enabled(flags) is True


def test_SECURITE_letat_decode_porte_la_meme_regle_que_la_fonction():
    # Ce que ce test vérifie RÉELLEMENT : que `RemoteState.menu_enabled` est
    # toujours une simple délégation à `menu_enabled()`, et non une seconde
    # implémentation de la règle. Il ne peut pas détecter une divergence de la
    # règle elle-même (les deux membres appellent le même code et bougeraient
    # ensemble) — c'est le balayage du test précédent qui grave la règle. Ici
    # on interdit le fork, qui est la façon canonique de la voir diverger.
    for flags in range(FLAGS_MASK + 1):
        etat = decode_frame(encode_frame(0, 0, 0, flags))
        assert etat.menu_enabled is menu_enabled(flags)
        assert etat.deadman is bool(flags & FLAG_DEADMAN)


def test_RemoteState_deadman_suit_le_masque():
    assert RemoteState(0, 0, 0, FLAG_DEADMAN).deadman is True
    assert RemoteState(0, 0, 0, FLAG_UP | FLAG_BACK).deadman is False
    assert RemoteState(0, 0, 0, 0).deadman is False


def test_RemoteState_a_un_repr_lisible():
    # Un état qui s'affiche « <object at 0x…> » dans un log de conduite ne sert
    # à rien le jour où il faut comprendre ce que le boîtier a envoyé.
    texte = repr(RemoteState(7, -12, 34, FLAG_DEADMAN))
    assert "seq=7" in texte and "x=-12" in texte and "y=34" in texte
    assert "0x01" in texte


# ---------------------------------------------------------------------------
#  Trames : aller-retour
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seq,x,y,flags", [
    (0, 0, 0, 0),
    (1, 500, -500, FLAG_DEADMAN),
    (42, -1000, 1000, FLAG_DEADMAN | FLAG_UP),
    (255, 1000, -1000, FLAGS_MASK),
    (128, -1, 1, FLAG_JOY_SW),
    (7, 0, -999, FLAG_DOWN | FLAG_BACK),
])
def test_une_trame_construite_se_relit_a_lidentique(seq, x, y, flags):
    trame = encode_frame(seq, x, y, flags)
    assert trame.endswith("\n")
    etat = decode_frame(trame)
    assert etat is not None
    assert (etat.seq, etat.x, etat.y, etat.flags) == (seq, x, y, flags)


def test_le_format_de_trame_est_bien_celui_de_letude():
    # `R;<seq>;<x>;<y>;<flags>;<crc8>` — format gravé au §4.5, lu des deux
    # côtés du câble. Le changer sans le dire casserait le lien en silence.
    morceaux = encode_frame(3, -250, 250, FLAG_DEADMAN).strip().split(";")
    assert morceaux[0] == "R"
    assert len(morceaux) == 6
    assert morceaux[1:4] == ["3", "-250", "250"]
    assert morceaux[4] == "01"                 # flags : 2 chiffres, minuscule
    assert len(morceaux[5]) == 2               # CRC sur 2 chiffres hexa


def test_les_champs_hexa_sont_en_minuscules():
    # Le format impose le minuscule pour flags et CRC (le préfixe « R », lui,
    # est majuscule). Un encodeur qui sortirait « 3F » resterait relisible par
    # NOTRE décodeur, mais pas forcément par un outil tiers branché sur le port.
    morceaux = encode_frame(1, 0, 0, FLAG_BACK | FLAG_JOY_SW).strip().split(";")
    assert morceaux[4] == "30"
    for champ in morceaux[4:]:
        assert champ == champ.lower()


def test_seq_boucle_sur_un_octet():
    assert decode_frame(encode_frame(255, 0, 0, 0)).seq == 255
    assert decode_frame(encode_frame(256, 0, 0, 0)).seq == 0
    assert decode_frame(encode_frame(257, 0, 0, 0)).seq == 1


def test_les_axes_sont_bornes_a_lencodage_plutot_que_de_lever():
    # À 50 Hz dans une boucle de firmware, une exception sur un axe hors borne
    # couperait l'émission — donc la seule preuve de vie du boîtier.
    assert decode_frame(encode_frame(0, 30000, -30000, 0)).x == AXE_MAX
    assert decode_frame(encode_frame(0, 30000, -30000, 0)).y == -AXE_MAX


# ---------------------------------------------------------------------------
#  Trames : le CRC
# ---------------------------------------------------------------------------

def test_crc8_est_deterministe_et_tient_sur_un_octet():
    for texte in ("R;0;0;0;00", "R;255;-1000;1000;3f", ""):
        assert crc8(texte) == crc8(texte)
        assert 0 <= crc8(texte) <= 0xFF


def test_crc8_grave_le_vecteur_canonique_du_CRC8_SMBUS():
    # LA valeur qui fige l'algorithme. « 123456789 » est le vecteur d'essai
    # canonique des CRC : pour CRC-8/SMBUS (polynôme 0x07, init 0x00, sans
    # réflexion ni XOR final), il vaut 0xf4. Tous les autres tests du CRC
    # recalculent la valeur attendue avec `crc8()` lui-même : changer le
    # polynôme en 0x31 ou l'init en 0xFF les laisserait TOUS verts.
    #
    # Cette valeur est aussi ce qui permet au décodeur hôte — écrit dans un
    # AUTRE dépôt (`dadou_control_ros`), sans une ligne de code partagée avec
    # celui-ci — de prouver qu'il calcule bien le MÊME CRC : il lui suffit de
    # vérifier ce vecteur. Sans lui, la seule façon de s'en apercevoir serait
    # un boîtier branché qui refuse 100 % des trames, un soir de représentation.
    assert crc8("123456789") == 0xF4


def test_crc8_grave_la_valeur_dune_charge_utile_du_protocole():
    # Une charge utile réelle (ce que couvre le CRC : tout ce qui précède le
    # dernier « ; »), avec sa valeur relevée en exécutant le code. Le vecteur
    # canonique fige l'algorithme ; celui-ci fige son application à NOTRE
    # format — y compris le fait que le CRC ne couvre ni ce « ; » ni le « \n ».
    assert crc8("R;0;0;0;00") == 0xE0
    assert crc8("R;42;123;-456;03") == 0xF6


def test_deux_trames_completes_sont_gravees_caractere_par_caractere():
    # Trames attendues écrites EN DUR, chaîne littérale entière : c'est le
    # contrat d'octets que le décodeur hôte devra relire. Toute évolution du
    # format, du CRC ou de la casse de l'hexadécimal casse ici, visiblement,
    # au lieu de se découvrir câble en main.
    assert encode_frame(0, 0, 0, 0) == "R;0;0;0;00;e0\n"
    assert encode_frame(7, -250, 1000, FLAG_DEADMAN) == "R;7;-250;1000;01;3e\n"
    assert encode_frame(255, 1000, -1000, FLAGS_MASK) == "R;255;1000;-1000;3f;bb\n"


def test_crc8_donne_le_meme_resultat_sur_du_texte_et_sur_des_octets():
    # Le firmware manipule du texte, le décodeur hôte lit des bytes bruts sur
    # le port série : les deux doivent tomber sur la même valeur.
    texte = "R;12;-34;56;09"
    assert crc8(texte) == crc8(texte.encode("ascii"))


def test_le_crc_rejette_un_octet_modifie_nimporte_ou_dans_la_trame():
    # LE cas qui compte : un caractère changé par une troncature ou un buffer
    # réassemblé de travers donne une consigne de vitesse plausible et fausse.
    trame = encode_frame(42, 123, -456, FLAG_DEADMAN)
    charge = trame.strip()
    for position in range(len(charge)):
        origine = charge[position]
        remplacant = "8" if origine != "8" else "7"
        corrompue = charge[:position] + remplacant + charge[position + 1:] + "\n"
        if corrompue == trame:
            continue
        etat = decode_frame(corrompue)
        # Soit la trame est refusée (cas attendu), soit elle est malformée au
        # point de ne plus rien décoder — jamais un état DIFFÉRENT accepté.
        assert etat is None, corrompue


def test_le_crc_rejette_un_crc_modifie():
    trame = encode_frame(1, 10, 20, 0).strip()
    mauvais = trame[:-2] + ("00" if trame[-2:] != "00" else "01")
    assert decode_frame(mauvais) is None


# ---------------------------------------------------------------------------
#  Trames : tout ce qui doit être REFUSÉ
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ligne", [
    "",                                  # rien
    "\n",                                # ligne vide
    "R",                                 # préfixe seul
    "R;",                                # tronquée après le préfixe
    "R;1;0;0;00",                        # champ manquant (pas de CRC)
    "R;1;0;0",                           # tronquée en plein milieu
    "R;1;0;0;00;00;00",                  # champ en trop
    "X;1;0;0;00;00",                     # préfixe faux
    "ODO 1 2 3 00",                      # trame de l'odométrie, autre appareil
    "R;a;0;0;00;00",                     # seq non numérique
    "R;1;x;0;00;00",                     # x non numérique
    "R;1;0;y;00;00",                     # y non numérique
    "R;1;0;0;zz;00",                     # flags non hexadécimaux
    "R;1;0;0;00;zz",                     # CRC non hexadécimal
    "R;1;0;0;00;0",                      # CRC tronqué à un chiffre
    "R;1;0;0;00;000",                    # CRC de trois chiffres
    "R;1;0;0;;00",                       # flags vide
    "R;1;;0;00;00",                      # champ vide
    "R;1;+1;0;00;00",                    # signe « + » : pas notre format
    "R;1; 1;0;00;00",                    # espace parasite DANS un champ
    "bruit R;1;0;0;00;00",               # préfixe noyé dans du bruit
    "R;256;0;0;00;00",                   # seq hors octet
    "R;-1;0;0;00;00",                    # seq négatif
    "R;1;1001;0;00;00",                  # x hors bornes
    "R;1;0;-1001;00;00",                 # y hors bornes
])
def test_toute_ligne_malformee_est_refusee_sans_valeur_approchee(ligne):
    # Principe du projet : charge utile invalide = REFUS, jamais une valeur
    # « à peu près ». Refuser coûte 20 ms ; inventer un axe coûte un accident.
    assert decode_frame(ligne) is None


def test_une_trame_hors_bornes_est_refusee_meme_avec_un_bon_crc():
    # Le piège : reconstruire un CRC correct sur une trame hors protocole ne
    # doit pas suffire — les bornes font partie du contrat, pas le CRC seul.
    charge = "R;1;1001;0;00"
    trame = "%s;%02x\n" % (charge, crc8(charge))
    assert decode_frame(trame) is None


def test_les_butees_exactes_restent_acceptees():
    # Contrôle symétrique du test précédent : ±1000 est DANS le contrat.
    for valeur in (-AXE_MAX, AXE_MAX):
        charge = "R;1;%d;%d;00" % (valeur, valeur)
        trame = "%s;%02x\n" % (charge, crc8(charge))
        assert decode_frame(trame) is not None


# ---------------------------------------------------------------------------
#  Trames : ce qui est toléré (et seulement au bord de la ligne)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("habillage", [
    "%s\n", "%s\r\n", "  %s  \n", "\t%s", "%s",
])
def test_les_fins_de_ligne_et_espaces_de_bord_sont_toleres(habillage):
    charge = encode_frame(9, -42, 42, FLAG_DEADMAN).strip()
    etat = decode_frame(habillage % charge)
    assert etat is not None
    assert (etat.seq, etat.x, etat.y) == (9, -42, 42)


def test_seuls_les_espaces_ascii_de_bord_sont_rognes():
    # `strip()` sans argument retire AUSSI, sur CPython, les espaces unicode
    # (NBSP, U+2007, U+0085) — mais pas sur MicroPython. Le module tournant des
    # deux côtés du câble, la règle doit être la même : seuls " \t\r\n".
    charge = encode_frame(9, -42, 42, FLAG_DEADMAN).strip()
    for espace in ("\u00a0", "\u2007", "\u0085"):   # NBSP, U+2007, NEL
        assert decode_frame(espace + charge) is None


def test_un_champ_en_chiffres_non_ascii_est_refuse():
    # `str.isdigit()` est vrai sur CPython pour « ١٢ » (arabe-indien) et « １２ »
    # (pleine chasse), et `int()` les convertit — mais MicroPython non. Une
    # trame acceptée par l'hôte et refusée par le boîtier (ou l'inverse) est une
    # divergence dormante : le contrôle doit être strictement ASCII.
    for chiffres in ("١٢", "１２"):
        charge = "R;1;%s;0;00" % chiffres
        trame = "%s;%02x\n" % (charge, crc8(charge))
        assert decode_frame(trame) is None


# ---------------------------------------------------------------------------
#  Entrées du décodeur hôte : octets bruts et types inattendus
# ---------------------------------------------------------------------------

def test_une_trame_en_octets_se_decode_comme_en_texte():
    # Le décodeur hôte lit des `bytes` sur le port série. Exiger un `.decode()`
    # avant l'appel, c'était déplacer le problème chez l'appelant — et en ascii
    # ça lève précisément sur les trames corrompues (cf. test suivant).
    trame = encode_frame(42, -123, 456, FLAG_DEADMAN | FLAG_UP)
    texte = decode_frame(trame)
    octets = decode_frame(trame.encode("ascii"))
    assert octets is not None
    assert (octets.seq, octets.x, octets.y, octets.flags) == (
        texte.seq, texte.x, texte.y, texte.flags)


def test_un_octet_hors_ascii_donne_None_sans_lever():
    # LE cas pour lequel le CRC existe : un octet corrompu > 0x7F. En ascii,
    # le décodage lèverait UnicodeDecodeError et tuerait la boucle de lecture
    # de l'hôte en pleine représentation. En latin-1 (bijectif sur 0..255), il
    # devient un caractère quelconque, la trame est simplement refusée.
    trame = bytearray(encode_frame(5, 100, -100, 0).encode("ascii"))
    trame[4] = 0xFF
    assert decode_frame(bytes(trame)) is None
    assert decode_frame(trame) is None          # bytearray aussi


@pytest.mark.parametrize("entree", [3.14, None, [], 42, object()])
def test_une_entree_qui_nest_ni_texte_ni_octets_donne_None(entree):
    # Ce décodeur est appelé dans une boucle de lecture : il REFUSE, il ne lève
    # pas. Un `None` renvoyé par une lecture série qui a expiré ne doit pas
    # remonter en AttributeError jusqu'à tuer le nœud.
    assert decode_frame(entree) is None


# ---------------------------------------------------------------------------
#  Zone morte des axes
# ---------------------------------------------------------------------------

def test_le_centre_exact_donne_zero():
    assert apply_deadzone(32768, 32768, 32768, 100) == 0


def test_linterieur_de_la_zone_morte_donne_exactement_zero():
    # Un manche au repos qui dérive de quelques LSB ne doit PAS faire avancer
    # 50 kg. « Presque zéro » n'existe pas ici : c'est zéro.
    for raw in range(32768 - 3000, 32768 + 3001, 500):
        if abs(raw - 32768) <= 3200:     # 100/1000 de la demi-course
            assert apply_deadzone(raw, 32768, 32000, 100) == 0


def test_juste_au_dessus_de_la_zone_morte_la_sortie_repart_de_zero():
    # Le re-étalement : sans lui, sortir de la zone morte ferait sauter la
    # consigne à 10 % d'un coup — un à-coup de 50 kg à l'endroit précis où
    # l'opérateur cherche la finesse.
    centre, demi_course, zone = 32768, 32000, 100
    # Bord de zone (magnitude == 100) : encore 0.
    bord = centre + (zone * demi_course) // AXE_MAX
    assert apply_deadzone(bord, centre, demi_course, zone) == 0
    # Juste au-delà : petite valeur non nulle, pas un saut.
    valeurs = [apply_deadzone(bord + pas, centre, demi_course, zone)
               for pas in range(1, 40)]
    assert max(valeurs) > 0
    assert max(valeurs) < 50


def test_la_sortie_est_monotone_et_sans_marche_a_la_sortie_de_zone():
    # On balaie toute la demi-course : la sortie doit croître sans jamais
    # bondir. Une marche > 2 % de l'échelle trahirait un re-étalement raté.
    centre, demi_course, zone = 2048, 2048, 120
    precedent = 0
    for raw in range(centre, centre + demi_course + 1):
        valeur = apply_deadzone(raw, centre, demi_course, zone)
        assert valeur >= precedent
        assert valeur - precedent <= 20
        precedent = valeur
    assert precedent == AXE_MAX


def test_les_butees_donnent_plus_ou_moins_mille():
    assert apply_deadzone(65535, 32768, 32767, 100) == AXE_MAX
    assert apply_deadzone(1, 32768, 32767, 100) == -AXE_MAX


def test_les_valeurs_brutes_aberrantes_saturent_sans_lever():
    # ADC débranché, masse flottante, calibration fausse : ça sature, ça ne
    # lève pas. Une exception ici tuerait la boucle d'émission à 50 Hz.
    assert apply_deadzone(10 ** 9, 32768, 32000, 100) == AXE_MAX
    assert apply_deadzone(-10 ** 9, 32768, 32000, 100) == -AXE_MAX


def test_le_signe_est_symetrique_autour_du_centre():
    for ecart in (500, 5000, 20000, 31999):
        positif = apply_deadzone(32768 + ecart, 32768, 32000, 150)
        negatif = apply_deadzone(32768 - ecart, 32768, 32000, 150)
        assert positif == -negatif


def test_une_demi_course_nulle_ou_negative_donne_zero():
    # Paramètre pas encore calibré : on renvoie « pas de commande », on ne
    # divise pas par zéro au milieu d'une boucle de conduite.
    assert apply_deadzone(50000, 32768, 0, 100) == 0
    assert apply_deadzone(50000, 32768, -32000, 100) == 0


def test_une_zone_morte_couvrant_toute_la_course_rend_laxe_inerte():
    # Cas dégénéré d'une mauvaise calibration : inerte vaut mieux qu'imprévu.
    assert apply_deadzone(65535, 32768, 32000, AXE_MAX) == 0
    assert apply_deadzone(65535, 32768, 32000, 5000) == 0


def test_une_zone_morte_nulle_laisse_passer_le_moindre_ecart():
    assert apply_deadzone(32769, 32768, 32000, 0) == 0   # < 1 unité de sortie
    assert apply_deadzone(32768 + 32, 32768, 32000, 0) == 1


def test_la_sortie_reste_toujours_dans_les_bornes_du_protocole():
    # Contrat croisé avec la trame : ce que produit apply_deadzone doit
    # toujours pouvoir être encodé sans être borné au passage.
    for raw in (0, 1, 32768, 65535, -50000, 10 ** 6):
        for zone in (0, 50, 999):
            valeur = apply_deadzone(raw, 32768, 32000, zone)
            assert -AXE_MAX <= valeur <= AXE_MAX
