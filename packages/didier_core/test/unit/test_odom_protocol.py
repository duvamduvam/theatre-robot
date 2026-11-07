"""Tests du décodage quadrature et du protocole de trame de l'odométrie.

Ces tests exercent EXACTEMENT le code qui tourne sur le Pico et dans le nœud
ROS (`firmware/pico_odometry/odom_protocol.py`), pas une reproduction. C'est la
règle du projet, et elle compte doublement ici : un signe inversé ou un
bouclage raté en odométrie ne casse rien — ça fait juste dériver la carte de
nav2, lentement, sans que personne ne le voie.
"""

import pytest

from odom_protocol import (
    QUAD_DELTA,
    QUAD_ILLEGAL,
    QuadratureDecoder,
    build_frame,
    crc8,
    delta_ticks,
    parse_frame,
    seq_perdues,
    wrap_ticks,
)

# Le cycle de Gray d'un tour de cible, dans le sens « avant » arbitraire.
CYCLE_AVANT = (0b00, 0b01, 0b11, 0b10)


def etats_avant(n_cibles):
    """Suite d'états correspondant à `n_cibles` cibles défilant en avant."""
    return [CYCLE_AVANT[i % 4] for i in range(4 * n_cibles + 1)]


# ---------------------------------------------------------------------------
#  La table de décodage
# ---------------------------------------------------------------------------

def test_table_delta_et_illegal_ont_16_entrees():
    assert len(QUAD_DELTA) == 16
    assert len(QUAD_ILLEGAL) == 16


def test_les_transitions_sans_changement_ne_comptent_rien():
    # Rester sur le même état (capteur au repos, robot à l'arrêt) ne doit
    # jamais produire de tick : sinon un robot immobile « avancerait ».
    for etat in range(4):
        assert QUAD_DELTA[(etat << 2) | etat] == 0
        assert not QUAD_ILLEGAL[(etat << 2) | etat]


def test_les_transitions_a_deux_bits_sont_marquees_illegales():
    # Les deux bits ne peuvent pas basculer ensemble : c'est physiquement
    # impossible en code de Gray, donc c'est un front perdu.
    for depuis in range(4):
        for vers in range(4):
            deux_bits_changent = bin(depuis ^ vers).count("1") == 2
            assert QUAD_ILLEGAL[(depuis << 2) | vers] is deux_bits_changent


def test_toute_transition_legale_dun_bit_vaut_un_pas():
    for depuis in range(4):
        for vers in range(4):
            if bin(depuis ^ vers).count("1") == 1:
                assert abs(QUAD_DELTA[(depuis << 2) | vers]) == 1


# ---------------------------------------------------------------------------
#  Le décodeur
# ---------------------------------------------------------------------------

def test_le_premier_etat_ne_produit_aucun_tick():
    # Sans état précédent il n'y a pas de transition. Compter ici ajouterait
    # un tick fantôme à chaque démarrage du Pico.
    decodeur = QuadratureDecoder()
    assert decodeur.update(0b11) == 0
    assert decodeur.ticks == 0


def test_un_tour_de_dix_cibles_donne_quarante_ticks():
    # C'est LE contrat de résolution de l'étude : 10 cibles, décodage ×4,
    # 40 fronts par tour. S'il tombe à 20, la résolution est fausse de moitié
    # et l'odométrie sous-estime toutes les distances.
    decodeur = QuadratureDecoder()
    for etat in etats_avant(10):
        decodeur.update(etat)
    assert decodeur.ticks == 40


def test_le_sens_arriere_decompte():
    decodeur = QuadratureDecoder()
    for etat in reversed(etats_avant(10)):
        decodeur.update(etat)
    assert decodeur.ticks == -40


def test_aller_puis_retour_revient_a_zero():
    # Un robot qui avance puis recule d'autant est revenu à son point de
    # départ. Si ce test tombe, l'odométrie accumule une erreur à chaque
    # manœuvre — et Didier manœuvre en permanence sur scène.
    decodeur = QuadratureDecoder()
    aller = etats_avant(7)
    for etat in aller:
        decodeur.update(etat)
    for etat in reversed(aller[:-1]):
        decodeur.update(etat)
    assert decodeur.ticks == 0


def test_le_drapeau_invert_change_le_signe_et_rien_dautre():
    normal, inverse = QuadratureDecoder(), QuadratureDecoder(invert=True)
    for etat in etats_avant(3):
        normal.update(etat)
        inverse.update(etat)
    assert normal.ticks == -inverse.ticks
    assert normal.ticks != 0


def test_inverser_les_deux_voies_ne_change_PAS_le_sens():
    # Les PC817 inversent la logique (« métal détecté = niveau BAS »). Comme
    # les DEUX voies sont inversées, le cycle de Gray est seulement décalé :
    # le sens est préservé. Ce test protège contre une « correction » du signe
    # qui serait faite au nom des optocoupleurs — elle serait fausse.
    direct, optocouple = QuadratureDecoder(), QuadratureDecoder()
    for etat in etats_avant(5):
        direct.update(etat)
        optocouple.update(~etat & 0b11)
    assert direct.ticks == optocouple.ticks


def test_un_front_perdu_est_compte_comme_illegal_et_pas_comme_du_mouvement():
    decodeur = QuadratureDecoder()
    decodeur.update(0b00)
    assert decodeur.update(0b11) == 0     # saut de 2 états : impossible
    assert decodeur.illegal == 1
    assert decodeur.ticks == 0


def test_le_compteur_boucle_en_32_bits_signes():
    decodeur = QuadratureDecoder()
    decodeur.ticks = 0x7FFFFFFF
    decodeur.update(0b00)
    decodeur.update(0b01)                 # +1 → doit basculer en négatif
    assert decodeur.ticks == -0x80000000


# ---------------------------------------------------------------------------
#  Bouclage des compteurs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("valeur,attendu", [
    (0, 0),
    (0x7FFFFFFF, 0x7FFFFFFF),
    (0x80000000, -0x80000000),
    (0x100000000, 0),
    (-1, -1),
])
def test_wrap_ticks(valeur, attendu):
    assert wrap_ticks(valeur) == attendu


def test_delta_ticks_traverse_le_bouclage_sans_teleporter():
    # Le piège : `courant - precedent` donnerait ici -4294967295, soit un saut
    # de 84 000 km. nav2 partirait à l'autre bout de la carte.
    assert delta_ticks(0x7FFFFFFF, -0x80000000) == 1
    assert delta_ticks(-0x80000000, 0x7FFFFFFF) == -1


def test_seq_perdues_compte_les_trames_manquantes():
    assert seq_perdues(10, 11) == 0
    assert seq_perdues(10, 13) == 2
    assert seq_perdues(65535, 0) == 0          # bouclage 16 bits
    assert seq_perdues(65534, 2) == 3


# ---------------------------------------------------------------------------
#  Trames
# ---------------------------------------------------------------------------

def test_une_trame_construite_se_relit():
    trame = build_frame(42, -1234, 5678)
    assert trame.endswith("\n")
    assert parse_frame(trame) == (42, -1234, 5678)


def test_le_format_de_trame_est_bien_celui_de_letude():
    # `ODO <seq> <ticks_g> <ticks_d> <crc>` — c'est ce format qui est gravé
    # dans l'étude §6 et que le nœud ROS attend. Le changer sans le dire
    # casserait le lien en silence.
    morceaux = build_frame(7, 100, -100).strip().split(" ")
    assert morceaux[0] == "ODO"
    assert len(morceaux) == 5
    assert morceaux[1:4] == ["7", "100", "-100"]
    assert len(morceaux[4]) == 2            # CRC sur 2 chiffres hexa


def test_le_crc_rejette_un_chiffre_modifie():
    # Le cas qui compte : un parasite qui change UN caractère du nombre de
    # ticks. Sans CRC, le robot croirait avoir fait un bond.
    trame = build_frame(1, 1000, 2000)
    corrompue = trame.replace("1000", "9000")
    assert parse_frame(corrompue) is None


def test_le_crc_rejette_un_crc_modifie():
    trame = build_frame(1, 10, 20)
    mauvais = trame.strip()[:-2] + ("00" if trame.strip()[-2:] != "00" else "01")
    assert parse_frame(mauvais) is None


@pytest.mark.parametrize("ligne", [
    "", "\n", "ODO", "ODO 1 2 3", "ODO 1 2 3 4 5", "STAT illegal_g=0",
    "ODO a b c 00", "ODO 1 2 3 ZZ", "bruit série ODO 1 2 3 00",
])
def test_toute_ligne_malformee_est_refusee_sans_valeur_approchee(ligne):
    # Principe du projet : charge utile invalide = REFUS, jamais une perte
    # silencieuse ni une valeur « à peu près ».
    assert parse_frame(ligne) is None


def test_la_ligne_de_sante_nest_pas_prise_pour_une_trame():
    assert parse_frame("STAT illegal_g=0 illegal_d=0") is None


def test_crc8_est_deterministe_et_tient_sur_un_octet():
    for texte in ("ODO 1 0 0", "ODO 65535 -2147483648 2147483647", ""):
        assert crc8(texte) == crc8(texte)
        assert 0 <= crc8(texte) <= 0xFF


def test_crc8_grave_le_vecteur_canonique_du_CRC8_SMBUS():
    # Le test ci-dessus est tautologique (`crc8(t) == crc8(t)`) : il vérifie le
    # déterminisme, pas l'ALGORITHME. Changer le polynôme 0x07 en 0x31, ou
    # l'init 0x00 en 0xFF, le laisserait vert — comme tous les autres tests du
    # CRC, qui recalculent l'attendu avec `crc8()` lui-même.
    #
    # « 123456789 » est le vecteur d'essai canonique des CRC : pour
    # CRC-8/SMBUS (polynôme 0x07, init 0x00, sans réflexion ni XOR final), il
    # vaut 0xf4. C'est cette valeur qui permet à un décodeur écrit ailleurs —
    # ou au firmware du Pico, qui ne partage pas ce fichier de tests — de
    # prouver qu'il calcule bien le MÊME CRC. Même vecteur que le protocole de
    # la télécommande (`firmware/remote_usb/remote_protocol.py`) : les deux
    # CRC sont le même algorithme, et doivent le rester.
    assert crc8("123456789") == 0xF4


def test_seq_boucle_sur_16_bits_dans_la_trame():
    assert parse_frame(build_frame(65536, 0, 0))[0] == 0
    assert parse_frame(build_frame(65537, 0, 0))[0] == 1
