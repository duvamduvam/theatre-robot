"""zones : entrée immédiate, sortie retardée par hystérésis (§5.1, §6.2)."""
import math

import pytest

from didier_corps_sur.zones import ARRET, LIBRE, RALENTI, ParametresZones, Zones


def zones():
    return Zones(ParametresZones(marge_arret_m=0.60, marge_ralenti_m=1.20,
                                 hysteresis_m=0.05, balayages_de_sortie=3))


def test_suite_gravee_de_la_spec():
    z = zones()
    suite = [1.30, 1.10, 0.59, 0.62, 0.66, 0.66, 0.64, 0.66, 0.66, 0.66]
    attendu = [LIBRE, RALENTI, ARRET, ARRET, ARRET, ARRET, ARRET, ARRET, ARRET, RALENTI]
    assert [z.observer(d) for d in suite] == attendu


def test_sortie_de_ralenti_vers_libre():
    z = zones()
    assert [z.observer(d) for d in (1.10, 1.24, 1.26, 1.26, 1.26)] == \
        [RALENTI, RALENTI, RALENTI, RALENTI, LIBRE]


def test_sortie_d_arret_directement_vers_libre():
    z = zones()
    assert [z.observer(d) for d in (0.50, 2.0, 2.0, 2.0)] == [ARRET, ARRET, ARRET, LIBRE]


def test_libre_vers_arret_immediat():
    z = zones()
    assert [z.observer(d) for d in (math.inf, 0.0)] == [LIBRE, ARRET]


def test_seuils_exacts():
    z = zones()
    assert z.observer(0.60) == RALENTI      # 0,60 ≤ d < 1,20
    z = zones()
    assert z.observer(1.20) == LIBRE


def test_un_balayage_invalide_coupe_la_sortie():
    z = zones()
    z.observer(0.50)
    assert [z.observer(0.70), z.observer(0.70, valide=False), z.observer(0.70), z.observer(0.70)] == \
        [ARRET, ARRET, ARRET, ARRET]
    assert z.observer(0.70) == RALENTI


def test_un_balayage_invalide_fait_entrer_en_arret():
    z = zones()
    z.observer(2.0)
    assert z.observer(0.30, valide=False) == ARRET


@pytest.mark.parametrize("d, attendu", [(2.0, ARRET), (0.30, ARRET)])
def test_avant_tout_balayage_valide(d, attendu):
    z = zones()
    assert z.zone == ARRET
    assert z.observer(d, valide=False) == attendu
