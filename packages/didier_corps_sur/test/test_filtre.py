"""filtre : transformation d'une consigne, courbure jamais changée (§5.2-5.3, §6.2)."""
import math
import random

import pytest

from didier_corps_sur.filtre import EtatFiltre, ParametresFiltre, Plafond, filtrer

TOUT_VU = {"avant": True, "arriere": True, "flanc_g": True, "flanc_d": True}
AVANT_SEUL = {"avant": True, "arriere": False, "flanc_g": False, "flanc_d": False}


def params(autorise=False, w_aveugle=0.3):
    p = Plafond(v_max=0.25, w_max=0.5)
    return ParametresFiltre(plafonds={"anim": p, "follow": p, "web": p}, facteur_ralenti=0.5,
                            w_max_aveugle=w_aveugle, angulaire_aveugle_autorise=autorise)


def etat(zone="LIBRE", vue=None, global_="ARME", pause=False):
    return EtatFiltre(etat=global_, zone=zone, pause_duree=pause, vue=TOUT_VU if vue is None else vue)


def test_libre_plafonne():
    v, w, motif = filtrer(0.4, 0.2, "follow", etat(), params())
    assert (v, w) == pytest.approx((0.25, 0.125), abs=1e-12)
    assert motif is None


def test_ralenti_plafonne_puis_divise():
    v, w, motif = filtrer(0.4, 0.2, "follow", etat("RALENTI"), params())
    assert (v, w) == pytest.approx((0.125, 0.0625), abs=1e-12)
    assert motif is None


def test_ralenti_touche_les_deux_composantes_sous_le_plafond():
    v, w, _ = filtrer(0.2, 0.4, "web", etat("RALENTI"), params())
    assert (v, w) == pytest.approx((0.1, 0.2), abs=1e-12)


def test_plafond_angulaire_reduit_aussi_v():
    v, w, _ = filtrer(0.1, 1.0, "anim", etat(), params())
    assert (v, w) == pytest.approx((0.05, 0.5), abs=1e-12)


def test_sous_les_plafonds_inchange():
    assert filtrer(0.1, 0.2, "anim", etat(), params()) == (0.1, 0.2, None)


def test_tour_non_vu_autorise():
    v, w, motif = filtrer(0.2, 0.6, "follow", etat(vue=AVANT_SEUL), params(autorise=True))
    assert (v, w) == pytest.approx((0.1, 0.3), abs=1e-12)
    assert motif is None


def test_tour_non_vu_non_autorise():
    assert filtrer(0.2, 0.6, "follow", etat(vue=AVANT_SEUL), params()) == (0.0, 0.0, "tour_aveugle")


def test_tour_non_vu_autorise_mais_avant_aveugle():
    vue = {"avant": False, "arriere": True, "flanc_g": True, "flanc_d": True}
    assert filtrer(0.0, 0.3, "follow", etat(vue=vue), params(autorise=True)) == \
        (0.0, 0.0, "tour_aveugle")


def test_w_max_aveugle_ne_relache_jamais_le_plafond_du_canal():
    v, w, _ = filtrer(0.0, 2.0, "follow", etat(vue=AVANT_SEUL), params(autorise=True, w_aveugle=3.0))
    assert w == pytest.approx(0.5, abs=1e-12)


def test_arriere_non_vue_recul_refuse():
    assert filtrer(-0.2, 0.0, "anim", etat(vue=AVANT_SEUL), params()) == (0.0, 0.0, "recul_aveugle")


def test_avant_non_vu_avance_refusee():
    vue = {"avant": False, "arriere": True, "flanc_g": True, "flanc_d": True}
    assert filtrer(0.2, 0.0, "anim", etat(vue=vue), params()) == (0.0, 0.0, "avant_aveugle")


def test_region_absente_comptee_non_vue():
    assert filtrer(0.2, 0.0, "anim", etat(vue={}), params()) == (0.0, 0.0, "avant_aveugle")


def test_arret():
    assert filtrer(0.3, 0.4, "follow", etat("ARRET"), params()) == (0.0, 0.0, "ARRET")


def test_pause_duree():
    assert filtrer(0.1, 0.0, "follow", etat(pause=True), params()) == (0.0, 0.0, "PAUSE_DUREE")


@pytest.mark.parametrize("v, w", [(math.nan, 0.0), (0.1, math.inf), (-math.inf, 0.0)])
def test_consigne_invalide(v, w):
    assert filtrer(v, w, "web", etat(), params()) == (0.0, 0.0, "consigne_invalide")


@pytest.mark.parametrize("global_", ["DEMARRAGE", "VERROU"])
def test_etat_non_arme(global_):
    assert filtrer(0.1, 0.0, "web", etat(global_=global_), params()) == (0.0, 0.0, global_)


def test_canal_inconnu():
    with pytest.raises(ValueError, match="remote"):
        filtrer(0.1, 0.0, "remote", etat(), params())


def test_propriete_courbure_1000_tirages():
    """Sortie nulle, ou v'/ω' = v/ω (à 1e-9 près), avec un facteur 0 < k ≤ 1 commun,
    et jamais au-delà des plafonds. Graine fixe."""
    tirage = random.Random(20261118)
    zones = ["LIBRE", "RALENTI", "ARRET"]
    for _ in range(1000):
        v = tirage.uniform(-2.0, 2.0) if tirage.random() > 0.1 else 0.0
        w = tirage.uniform(-4.0, 4.0) if tirage.random() > 0.1 else 0.0
        vue = {r: tirage.random() > 0.3 for r in ("avant", "arriere", "flanc_g", "flanc_d")}
        e = etat(tirage.choice(zones), vue, tirage.choice(["ARME", "ARME", "VERROU"]),
                 tirage.random() < 0.1)
        p = params(autorise=tirage.random() > 0.5)
        v2, w2, _ = filtrer(v, w, tirage.choice(["anim", "follow", "web"]), e, p)
        assert abs(v2) <= 0.25 + 1e-12 and abs(w2) <= 0.5 + 1e-12
        if v2 == 0.0 and w2 == 0.0:
            continue
        # Même direction, même facteur sur les deux composantes.
        assert v2 * w - w2 * v == pytest.approx(0.0, abs=1e-9)
        k = v2 / v if v != 0 else w2 / w
        assert 0.0 < k <= 1.0 + 1e-12
        if v == 0:
            assert v2 == 0.0
        if w == 0:
            assert w2 == 0.0
