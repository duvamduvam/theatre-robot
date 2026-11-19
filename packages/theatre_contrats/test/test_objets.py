"""Contrat du tableau des objets (lot O0) — valeurs GRAVÉES, jamais recalculées par le code testé.

Mutants vérifiés à la main (18/11), chacun fait rougir au moins un test ci-dessous :
  - resoudre : candidats « ici » pris sans filtre (tous)          -> test_resoudre_loin_est_pas_ici
  - resoudre : départage sur |azimut| remplacé par la distance    -> test_resoudre_deux_candidats_axe
  - Objet.a_portee : <= PORTEE_M devenu <                         -> test_a_portee_borne_incluse
  - cote : 45 devenu 30                                           -> test_cote_decoupage
  - _objet : atteignable lu sans exiger de distance               -> test_decoder_atteignable_sans_distance
  - decoder : ids en double acceptés                              -> test_decoder_ecarte_les_illisibles
Revue O1 (19/11) :
  - nombre_fini sans garde OverflowError                          -> test_decoder_nombre_geant_jamais_d_exception
  - borne NOMBRE_MAX retirée                                       -> test_decoder_nombre_geant_jamais_d_exception
  - nombres absurdes non comptés (rien à journaliser)              -> test_decoder_nombre_geant_jamais_d_exception
  - emprise négative gardée                                        -> test_decoder_emprise
  - garde_geste : pas_ici / hors_atteinte confondus, no_tour sauté -> test_garde_geste
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
        "sources": ["carte"], "repere": "monde", "x": 36.2, "y": 2.496, "sigma_m": 0.0, "emprise_m": None,
        "azimut_deg": 6.4, "distance_m": 22.3, "cote": "devant", "en_vue": False, "vu_il_y_a_s": None,
        "tour": True, "atteignable": False}
    t = decoder(raw)
    assert t.objets == (TABLE, BANC) and t.pose == pose and t.rejetes == 0 and t.anomalies == 0
    assert objets.avertissement(t) is None
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


def test_decoder_nombre_geant_jamais_d_exception():
    """Revue O1 (19/11) : un entier JSON de 400 chiffres faisait lever OverflowError
    (math.isfinite) au décodeur — dans le callback de chaque lecteur. Désormais : champ ramené à
    son défaut SÛR, compté, et la phrase à journaliser est rendue par avertissement()."""
    geant = "1" + "0" * 400
    d = {**TABLE.en_dict(), "id": "g"}
    raw = json.dumps({"v": 1, "t_ms": 5, "pose": {"repere": "monde", "x": 0, "y": 0, "cap_deg": 0},
                      "objets": [d]})
    raw = raw.replace('"distance_m": 4.3', '"distance_m": ' + geant).replace('"x": 17.8', '"x": ' + geant)
    raw = raw.replace('"cap_deg": 0', '"cap_deg": -' + geant).replace('"t_ms": 5', '"t_ms": ' + geant + geant)
    t = decoder(raw)
    o = t.objets[0]
    assert (o.x, o.y, o.distance_m, o.azimut_deg, o.atteignable, o.a_portee) == (None, None, None, None, False, False)
    assert t.pose is None and t.t_ms == 0
    assert (t.rejetes, t.anomalies) == (0, 4)     # x, distance_m, cap_deg de la pose, t_ms
    assert objets.avertissement(t) == "4 nombre(s) absurde(s) ramené(s) à leur défaut sûr"
    # Au-delà de NOMBRE_MAX (1e6) : absurde aussi ; NaN et infini de même.
    d = {**TABLE.en_dict(), "sigma_m": 2e6, "vu_il_y_a_s": float("nan"), "y": float("inf")}
    t = decoder(json.dumps({"v": 1, "objets": [d, 7]}))
    assert (t.objets[0].sigma_m, t.objets[0].vu_il_y_a_s, t.objets[0].x) == (float("inf"), None, None)
    assert (t.rejetes, t.anomalies) == (1, 3)
    assert objets.avertissement(t) == ("1 objet(s) illisible(s) écarté(s) ; "
                                       "3 nombre(s) absurde(s) ramené(s) à leur défaut sûr")
    assert objets.nombre_fini(10 ** 400) is None and objets.nombre_fini(1e6) == 1e6
    assert objets.nombre_fini(-1e6 - 1) is None and objets.nombre_fini(True) is None


def test_decoder_emprise():
    for v, attendu in ((1.1, 1.1), (0, 0.0), (-0.5, None), ("1", None), (None, None)):
        d = {**TABLE.en_dict(), "emprise_m": v}
        assert decoder(json.dumps({"v": 1, "objets": [d]})).objets[0].emprise_m == attendu


def test_garde_geste():
    """LA garde de la bouche (chat_node et l'épreuve sim validate-objets.sh) — séance du 15/11."""
    t = Tableau((TABLE, BANC, MANEGE))
    g = objets.garde_geste
    assert g(t, {"cmd": "aller_voir", "objet": "le banc"}) == objets.Garde("dropped", "pas_ici", BANC)
    assert g(t, {"cmd": "aller_voir", "objet": "girafe"}) == objets.Garde("unknown", None, None)
    assert g(t, {"cmd": "tour_de", "objet": "manège"}) == objets.Garde("no_tour", None, MANEGE)
    assert g(t, {"cmd": "aller_voir", "objet": "petite table"}) == objets.Garde(None, None, TABLE)
    assert g(t, {"cmd": "tour_de", "objet": "table_basse"}) == objets.Garde(None, None, TABLE)
    loin = Objet(id="vu/1", nom="sac", sources=("vu",), x=1.0, y=1.0, distance_m=4.0, azimut_deg=0.0,
                 cote="devant", en_vue=True, atteignable=False)
    assert g(Tableau((loin,)), {"cmd": "aller_voir", "objet": "sac"}) == objets.Garde("dropped", "hors_atteinte", loin)
    # Les autres commandes passent sans objet ; jamais d'exception sur une demande faussée.
    assert g(t, {"cmd": "avancer", "metres": 1}) == objets.Garde() == g(t, "aller_voir") == g(t, {})
    assert g(objets.VIDE, {"cmd": "aller_voir", "objet": "banc"}).effect == "unknown"


def test_ou_dit():
    assert ou_dit(MANEGE) == "à 2 m sur ta droite"
    assert ou_dit(Objet(id="a", nom="a", distance_m=0.4, cote="gauche")) == "à moins d'un mètre sur ta gauche"
    assert ou_dit(Objet(id="a", nom="a")) == ""
    assert objets.ou(22.34, "derriere") == "à 22 m derrière toi"
    assert [objets.ou(*a) for a in ((None, "devant"), (3, "haut"), (True, "devant"), (-1, "devant"),
                                    (float("nan"), "devant"))] == ["", "", "", "", ""]
