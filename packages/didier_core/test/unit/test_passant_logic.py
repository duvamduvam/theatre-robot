"""Tests de la logique pure du passant simulé (didier_sim_lib.passant_logic, spec A0 §8.4).

Valeurs attendues GRAVÉES, calculées à la main (rotation de 90° ou 180°, triangle 3-4-5) :
aucune n'est recalculée par la fonction testée.
"""
import math

import pytest

from didier_sim_lib.passant_logic import (
    Demande,
    Trajet,
    lacet_depuis_quaternion,
    lire_demande,
    position,
    trajet_monde,
    vers_monde,
)


def test_demande_valide_repere_didier_par_defaut():
    assert lire_demande('{"de": [1, 2], "a": [1, -2], "vitesse": 1.0}') == \
        Demande(de=(1.0, 2.0), a=(1.0, -2.0), vitesse=1.0, repere="didier")


@pytest.mark.parametrize("texte", [
    "pas du json",
    "[1, 2]",
    '{"de": [1, 2], "vitesse": 1.0}',                              # a manquant
    '{"de": [1, 2, 3], "a": [1, -2], "vitesse": 1.0}',             # trois coordonnées
    '{"de": [1, 2], "a": [1, -2], "vitesse": 0}',                  # immobile
    '{"de": [1, 2], "a": [1, -2], "vitesse": 3.5}',                # au-delà de 3 m/s
    '{"de": [1, 2], "a": [1, 2], "vitesse": 1.0}',                 # segment nul
    '{"de": [0, 0], "a": [31, 0], "vitesse": 1.0}',                # plus de 30 m
    '{"de": [1, 2], "a": [1, -2], "vitesse": 1.0, "repere": "x"}', # repère inconnu
    '{"de": [1, "NaN"], "a": [1, -2], "vitesse": 1.0}',            # non fini
])
def test_demandes_refusees(texte):
    with pytest.raises(ValueError):
        lire_demande(texte)


def test_vers_monde_rotation_quart_de_tour():
    # Didier en (2 ; 3) tourné vers +y : 1 m devant lui = (2 ; 4).
    x, y = vers_monde((1.0, 0.0), 2.0, 3.0, math.pi / 2)
    assert (x, y) == pytest.approx((2.0, 4.0), abs=1e-12)


def test_vers_monde_demi_tour():
    x, y = vers_monde((1.0, 2.0), 0.0, 0.0, math.pi)
    assert (x, y) == pytest.approx((-1.0, -2.0), abs=1e-12)


def test_lacet_quaternion_quart_de_tour():
    assert lacet_depuis_quaternion(math.sin(math.pi / 4), math.cos(math.pi / 4)) == \
        pytest.approx(1.5707963267948966, abs=1e-12)


def test_trajet_repere_didier_exige_la_verite_terrain():
    d = Demande(de=(1.0, 0.0), a=(1.0, -2.0), vitesse=1.0, repere="didier")
    with pytest.raises(ValueError):
        trajet_monde(d, 0.0, None)


def test_trajet_repere_didier_converti():
    # Didier en (1 ; 1), lacet 90° : (1 ; 0) → (1 ; 2) ; (1 ; −2) → (3 ; 2).
    t = trajet_monde(Demande(de=(1.0, 0.0), a=(1.0, -2.0), vitesse=1.0, repere="didier"),
                     5.0, (1.0, 1.0, math.pi / 2))
    assert t.de == pytest.approx((1.0, 2.0), abs=1e-12)
    assert t.a == pytest.approx((3.0, 2.0), abs=1e-12)
    assert t.t0 == 5.0


def test_trajet_repere_monde_tel_quel():
    t = trajet_monde(Demande(de=(1.0, 0.0), a=(1.0, -2.0), vitesse=1.0, repere="monde"), 0.0, None)
    assert (t.de, t.a) == ((1.0, 0.0), (1.0, -2.0))


def test_position_le_long_du_segment_3_4_5():
    t = Trajet(de=(0.0, 0.0), a=(3.0, 4.0), vitesse=1.0, t0=10.0)   # 5 m en 5 s
    assert t.duree == pytest.approx(5.0)
    assert position(t, 9.0) == ((0.0, 0.0), False)                   # avant le départ
    p, fini = position(t, 12.0)
    assert p == pytest.approx((1.2, 1.6), abs=1e-12) and fini is False
    assert position(t, 15.0) == ((3.0, 4.0), True)
    assert position(t, 20.0) == ((3.0, 4.0), True)                  # reste à l'arrivée
