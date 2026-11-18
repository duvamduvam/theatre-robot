"""Contrat du tableau des objets (lot O0) — valeurs GRAVÉES, jamais recalculées par le code testé.

Mutants vérifiés à la main (18/11), chacun fait rougir au moins un test ci-dessous :
  - resoudre : candidats « ici » pris sans filtre (tous)          -> test_resoudre_loin_est_pas_ici
  - resoudre : départage sur |azimut| remplacé par la distance    -> test_resoudre_deux_candidats_axe
  - Objet.a_portee : <= PORTEE_M devenu <                         -> test_a_portee_borne_incluse
  - cote : 45 devenu 30                                           -> test_cote_decoupage
  - _objet : atteignable lu sans exiger de distance               -> test_decoder_atteignable_sans_distance
  - decoder : ids en double acceptés                              -> test_decoder_ecarte_les_illisibles
"""
import json

import pytest

from theatre_contrats import objets
from theatre_contrats.objets import (ICI, INCONNU, PAS_ICI, Objet, Pose, Tableau, cote, decoder, encoder,
                                     normaliser_nom, ou_dit, resoudre)

BANC = Objet(id="carte/banc", nom="banc", desc="banc en bois", alias=("banc", "banc en bois"),
             x=36.2, y=2.496, azimut_deg=6.4, distance_m=22.3, cote="devant", en_vue=False,
             tour=True, atteignable=False)
TABLE = Objet(id="carte/table_basse", nom="table_basse", desc="table très basse",
              alias=("table basse", "table", "petite table"), x=17.8, y=2.1, azimut_deg=29.0,
              distance_m=4.3, cote="devant", en_vue=True, tour=True, atteignable=True)
MANEGE = Objet(id="carte/carrousel", nom="carrousel", alias=("manège",), x=13.2, y=-2.0,
               azimut_deg=-111.8, distance_m=2.2, cote="droite", en_vue=False, atteignable=True)


def test_normaliser_nom():
    assert normaliser_nom("Les Anneaux !") == "anneaux"
    assert normaliser_nom("table_basse") == "table basse"
    assert normaliser_nom("l'eau") == "eau"
    assert normaliser_nom("Le MANÈGE") == "manege"
    assert normaliser_nom("anneaux de buren") == "anneaux de buren"   # article au milieu gardé
    assert normaliser_nom(None) == "" and normaliser_nom(42) == ""


def test_cote_decoupage():
    assert [cote(a) for a in (0, 45, 45.1, 135, 135.1, -45, -45.1, -135, -135.1, 180)] == [
        "devant", "devant", "gauche", "gauche", "derriere", "devant", "droite", "droite", "derriere",
        "derriere"]


def test_a_portee_borne_incluse():
    assert objets.PORTEE_M == 10.0
    assert Objet(id="a", nom="a", distance_m=10.0).a_portee
    assert not Objet(id="a", nom="a", distance_m=10.1).a_portee
    assert not Objet(id="a", nom="a").a_portee            # distance inconnue : jamais à portée


def test_resoudre_loin_est_pas_ici():
    t = Tableau((TABLE, MANEGE, BANC))
    r = resoudre(t, "le banc")
    assert r == objets.Resolution(PAS_ICI, BANC)
    assert ou_dit(r.objet) == "à 22 m devant toi"


def test_resoudre_alias_et_ici():
    t = Tableau((TABLE, MANEGE, BANC))
    assert resoudre(t, "la petite table").objet is TABLE
    assert resoudre(t, "Le manège").statut == ICI           # derrière à droite mais à portée
    assert resoudre(t, "carte/banc").objet is BANC          # l'id tel quel
    assert resoudre(t, "girafe") == objets.Resolution(INCONNU)
    assert resoudre(t, "") == objets.Resolution(INCONNU)
    assert resoudre(t, None) == objets.Resolution(INCONNU)


def test_resoudre_deux_candidats_axe():
    # Deux bancs à portée : celui dans l'axe du regard, même s'il est plus loin.
    proche_de_cote = Objet(id="vu/1", nom="banc 2", alias=("banc",), azimut_deg=-60.0, distance_m=3.0,
                           cote="droite")
    loin_dans_l_axe = Objet(id="vu/2", nom="banc", azimut_deg=5.0, distance_m=8.0, cote="devant",
                            en_vue=True)
    assert resoudre(Tableau((proche_de_cote, loin_dans_l_axe)), "banc").objet.id == "vu/2"
    # Aucun ici : le plus proche est rendu « pas ici ».
    a = Objet(id="a", nom="velo", distance_m=30.0)
    b = Objet(id="b", nom="velo 2", alias=("velo",), distance_m=20.0)
    assert resoudre(Tableau((a, b)), "vélo") == objets.Resolution(PAS_ICI, b)


def test_encoder_decoder_aller_retour():
    pose = Pose("monde", 14.0, 0.0, 0.0)
    raw = encoder([TABLE, BANC], pose, 1234)
    v = json.loads(raw)
    assert v["v"] == 1 and v["t_ms"] == 1234
    assert v["pose"] == {"repere": "monde", "x": 14.0, "y": 0.0, "cap_deg": 0.0}
    assert v["objets"][1] == {
        "id": "carte/banc", "nom": "banc", "desc": "banc en bois", "alias": ["banc", "banc en bois"],
        "sources": ["carte"], "repere": "monde", "x": 36.2, "y": 2.496, "sigma_m": 0.0,
        "azimut_deg": 6.4, "distance_m": 22.3, "cote": "devant", "en_vue": False, "vu_il_y_a_s": None,
        "tour": True, "atteignable": False}
    t = decoder(raw)
    assert t.objets == (TABLE, BANC) and t.pose == pose and t.rejetes == 0
    assert t.par_id("carte/banc") is t.objets[1] and t.par_id("x") is None and t.par_id(None) is None
    assert "très" in raw                                   # lisible au journal (ensure_ascii=False)


@pytest.mark.parametrize("raw", ["", "[]", "{}", '{"v": 2, "objets": []}', '{"v": 1, "objets": {}}', "nul"])
def test_decoder_enveloppe_fausse(raw):
    with pytest.raises(ValueError):
        decoder(raw)


def test_decoder_ecarte_les_illisibles():
    bons = TABLE.en_dict()
    raw = json.dumps({"v": 1, "pose": "?", "objets": [
        bons, dict(bons),                                   # id en double
        {**bons, "id": "z", "repere": "lune"}, {**bons, "id": "y", "sources": []},
        {**bons, "id": "w", "nom": " "}, 7]})
    t = decoder(raw)
    assert [o.id for o in t.objets] == ["carte/table_basse"] and t.rejetes == 5 and t.pose is None


def test_decoder_atteignable_sans_distance():
    # Défauts SÛRS : sans distance lisible, ni à portée ni atteignable, côté effacé.
    d = {**TABLE.en_dict(), "distance_m": "4", "cote": "devant"}
    o = decoder(json.dumps({"v": 1, "objets": [d]})).objets[0]
    assert (o.distance_m, o.azimut_deg, o.cote, o.atteignable, o.a_portee) == (None, None, None, False, False)
    d = {**TABLE.en_dict(), "x": None}
    assert decoder(json.dumps({"v": 1, "objets": [d]})).objets[0].atteignable is False
    d = {**TABLE.en_dict(), "sigma_m": -1, "en_vue": 1}
    o = decoder(json.dumps({"v": 1, "objets": [d]})).objets[0]
    assert o.sigma_m == float("inf") and o.en_vue is False


def test_ou_dit():
    assert ou_dit(MANEGE) == "à 2 m sur ta droite"
    assert ou_dit(Objet(id="a", nom="a", distance_m=0.4, cote="gauche")) == "à moins d'un mètre sur ta gauche"
    assert ou_dit(Objet(id="a", nom="a")) == ""
