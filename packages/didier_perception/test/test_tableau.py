"""L'écrivain du tableau des objets (lot O0) — valeurs GRAVÉES (relevées à la main le 18/11 sur
config/chantiers.yaml et chantiers_tours.yaml : hypot/atan2 à la calculette, pas par le code testé).

Porte du lot O0 : la séance du 15/11 rejouée en test pur — Didier à x = 14, « banc » -> « connu,
pas ici, 22 m » (test_seance_15_11_banc_pas_ici).

Mutants vérifiés à la main (18/11), chacun fait rougir au moins un test :
  - VUE_MAX_M ignoré (en vue = seulement l'angle)            -> test_seance_15_11_banc_pas_ici
  - champ : <= champ_demi_deg devenu < 45                     -> test_seance_15_11_en_vue
  - atteignable : PORTEE_M ignorée                            -> test_seance_15_11_en_vue
  - atteignable : repère robot accepté                        -> test_repere_robot_jamais_cible
  - centre (cx, cy) ignoré au profit de l'ancre               -> test_carte_depuis_payload_centre
  - péremption 120 s supprimée                                -> test_peremption_vu
  - sigma : croissance par mètre supprimée                    -> test_sigma_grandit_et_tombe
  - noms uniques : suffixe donné au plus proche               -> test_noms_uniques_le_plus_proche_garde
  - fusion vu<->carte : seuil emprise + 1 m remplacé par 1 m  -> test_fusion_vu_carte
Revue O1 (19/11) :
  - fusion sur le rayon de l'ORBITE (2,1) au lieu de l'emprise (1,1) -> test_fusion_vu_carte
  - emprise inconnue : défaut 1 m oublié (seuil = 2·sigma seul)       -> test_fusion_emprise_inconnue_un_metre
  - emprise lue sur le rayon d'orbite / perdue à la publication       -> test_carte_depuis_payload_centre,
                                                                         test_emprise_publiee
  - _fini qui laisse passer l'OverflowError                            -> test_carte_depuis_payload_nombre_geant
"""
import json
import math
import os

import pytest
import yaml

from didier_perception import tableau as tb
from didier_perception.tableau import ObjetCarte, TableauObjets, carte_depuis_payload, sigma_creation
from didier_rehearsal.director import objects_payload
from didier_rehearsal.route import load_route, load_tours
from theatre_contrats import objets
from theatre_contrats.objets import ICI, PAS_ICI, decoder, encoder

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                      "didier_rehearsal", "config")


def _carte_chantiers():
    """La VRAIE carte, par le VRAI payload de la régie (director.objects_payload)."""
    with open(os.path.join(CONFIG, "chantiers.yaml"), encoding="utf-8") as f:
        route = load_route(yaml.safe_load(f))
    with open(os.path.join(CONFIG, "chantiers_tours.yaml"), encoding="utf-8") as f:
        tours = load_tours(yaml.safe_load(f), route.pois)
    return carte_depuis_payload(json.loads(objects_payload(route.pois, tours)))


def _tableau_a(x, y, cap_deg):
    t = TableauObjets()
    t.poser_carte(_carte_chantiers())
    t.poser_pose("monde", x, y, math.radians(cap_deg))
    # Par le fil, comme le lit un lecteur.
    return decoder(encoder(t.instantane(0.0), None, 0))


# ================================================================ la séance du 15/11
def test_seance_15_11_banc_pas_ici():
    lu = _tableau_a(14.0, 0.0, 0.0)
    r = lu.resoudre("le banc")
    assert r.statut == PAS_ICI
    o = r.objet
    assert (o.id, o.x, o.y, o.distance_m, o.azimut_deg, o.cote) == ("carte/banc", 36.2, 2.496, 22.3, 6.4, "devant")
    assert (o.en_vue, o.atteignable) == (False, False)
    assert objets.ou_dit(o) == "à 22 m devant toi"


def test_seance_15_11_en_vue():
    lu = _tableau_a(14.0, 0.0, 0.0)
    en_vue = [(o.nom, o.distance_m, o.azimut_deg, o.atteignable) for o in lu.objets if o.en_vue]
    assert en_vue == [("table_basse", 4.3, 28.9, True), ("poster_bizarre", 8.8, -17.8, True),
                      ("poubelle_tri", 13.2, 10.5, False)]
    a_portee = [(o.nom, o.distance_m, o.cote) for o in lu.objets if o.a_portee and not o.en_vue]
    assert a_portee == [("carrousel", 2.2, "droite"), ("elephant", 5.6, "derriere")]
    # Ce que David regardait à gauche : la table basse, à portée, résolue par un alias.
    assert lu.resoudre("la table").statut == ICI
    assert lu.resoudre("la table").objet.id == "carte/table_basse"
    # Trié par distance, tous là (30 POI), noms uniques.
    assert [o.nom for o in lu.objets[:3]] == ["carrousel", "table_basse", "elephant"]
    assert len(lu.objets) == 30 and len({o.nom for o in lu.objets}) == 30


def test_carte_depuis_payload_centre():
    carte = {o.nom: o for o in _carte_chantiers()}
    # Emprise = orbite 2,1 − dégagement 1,0 (majorant de la collision, à 0,1 m près).
    assert (carte["banc"].x, carte["banc"].y, carte["banc"].emprise_m, carte["banc"].tour) == (36.2, 2.496, 1.1, True)
    # Sans tour : l'ancre, emprise INCONNUE (jamais un défaut inventé).
    assert (carte["flaque"].x, carte["flaque"].y, carte["flaque"].emprise_m, carte["flaque"].tour) == (40.8, 0.0, None,
                                                                                                      False)
    assert carte["pigeon"].emprise_m == 0.5      # orbite au plancher 1,5 -> emprise ≤ 0,5
    assert carte["carrousel"].alias == ("carrousel", "manège", "chevaux de bois")
    assert carte["banc"].id == "carte/banc"
    assert (carte["pigeon"].x, carte["pigeon"].y) == (31.545, -2.4)    # centre ≠ ancre (31,6 ; -1,4)


def test_champ_bord_et_portee_de_vue():
    t = TableauObjets()
    # Objets à 5 m, azimuts 29,9° / 30,1° / -30,1°, puis un dans l'axe à 15,0 et 15,1 m.
    t.poser_carte([ObjetCarte("a", 4.331, 2.492), ObjetCarte("b", 4.323, 2.508), ObjetCarte("c", 4.323, -2.508),
                   ObjetCarte("d", 15.0, 0.0), ObjetCarte("e", 15.1, 0.0)])
    t.poser_pose("monde", 0.0, 0.0, 0.0)
    assert [(o.nom, o.azimut_deg, o.en_vue) for o in t.instantane(0.0)] == [
        ("a", 29.9, True), ("b", 30.1, False), ("c", -30.1, False), ("d", 0.0, True), ("e", 0.0, False)]


def test_carte_depuis_payload_tolerant():
    assert [o.nom for o in carte_depuis_payload([{"name": "a", "x": 1, "y": 2}, {"name": "a", "x": 0, "y": 0},
                                                 {"name": "", "x": 1, "y": 1}, {"name": "b", "x": "1", "y": 1},
                                                 {"name": "c", "x": 1, "y": float("nan")}, 3])] == ["a"]
    with pytest.raises(ValueError):
        carte_depuis_payload({"name": "a"})


def test_sans_pose_rien_n_est_ici():
    t = TableauObjets()
    t.poser_carte(_carte_chantiers())
    o = {x.id: x for x in t.instantane(0.0)}["carte/banc"]
    assert (o.distance_m, o.azimut_deg, o.cote, o.en_vue, o.atteignable) == (None, None, None, False, False)


def test_pose_dans_un_autre_repere_ne_compare_pas():
    t = TableauObjets()
    t.poser_carte([ObjetCarte("banc", 1.0, 0.0)])
    t.poser_pose("odom", 0.0, 0.0, 0.0)
    assert t.instantane(0.0)[0].distance_m is None


# ================================================================ objets vus (sources pour O2)
def test_fusion_vu_carte():
    t = TableauObjets()
    t.poser_carte([ObjetCarte("banc", 36.2, 2.5, alias=("banc en bois",), emprise_m=1.1)])
    t.poser_pose("monde", 32.5, 0.0, 0.0)
    # « banc en bois » vu à 2,0 m du centre : sous emprise + 1 m = 2,1 (2·sigma = 0,6) -> c'est
    # le banc de la carte.
    assert t.observer("Banc en bois", "monde", 36.2, 4.5, 0.3, 10.0) == "carte/banc"
    o = t.instantane(11.0)[0]
    assert (o.sources, o.x, o.y, o.vu_il_y_a_s, o.en_vue) == (("carte", "vu"), 36.2, 2.5, 1.0, True)
    # À 2,2 m : un autre objet (le sac posé par un passant… nommé banc).
    assert t.observer("banc", "monde", 36.2, 4.7, 0.3, 12.0) == "vu/1"
    # Incertain (sigma 1,5 -> 2·sigma = 3,0 > 2,1) : à 2,9 m, c'est encore le banc.
    assert t.observer("banc", "monde", 36.2, 5.4, 1.5, 12.0) == "carte/banc"
    # Nom incompatible tout près : un autre objet aussi.
    assert t.observer("vélo orange", "monde", 36.0, 2.5, 0.3, 12.0) == "vu/2"


def test_fusion_emprise_inconnue_un_metre():
    t = TableauObjets()
    t.poser_carte([ObjetCarte("borne", 10.0, 0.0)])          # emprise inconnue -> 1 m + 1 m = 2 m
    assert t.observer("borne", "monde", 11.9, 0.0, 0.3, 1.0) == "carte/borne"
    assert t.observer("borne", "monde", 12.1, 0.0, 0.3, 1.0) == "vu/1"


def test_emprise_publiee():
    t = TableauObjets()
    t.poser_carte([ObjetCarte("banc", 5.0, 0.0, emprise_m=1.1), ObjetCarte("flaque", 8.0, 0.0)])
    t.poser_pose("monde", 0.0, 0.0, 0.0)
    t.observer("sac", "monde", 3.0, 0.0, 0.3, 0.0)
    assert [(o.id, o.emprise_m) for o in t.instantane(0.0)] == [("vu/1", None), ("carte/banc", 1.1),
                                                                ("carte/flaque", None)]


def test_carte_depuis_payload_nombre_geant():
    # Revue O1 (19/11) : math.isfinite(10**400) lève OverflowError — jamais ici : élément sauté
    # (position illisible) ou emprise inconnue, jamais d'exception dans le callback de l'écrivain.
    carte = carte_depuis_payload([{"name": "a", "x": 10 ** 400, "y": 0.0},
                                  {"name": "b", "x": 1.0, "y": 2.0, "emprise": 10 ** 400},
                                  {"name": "c", "x": 1e7, "y": 0.0}])
    assert [(o.nom, o.x, o.y, o.emprise_m) for o in carte] == [("b", 1.0, 2.0, None)]


def test_noms_uniques_le_plus_proche_garde():
    t = TableauObjets()
    t.poser_carte([ObjetCarte("banc", 20.0, 0.0)])
    t.poser_pose("monde", 0.0, 0.0, 0.0)
    t.observer("banc", "monde", 5.0, 0.0, 0.3, 0.0)
    t.observer("Banc", "monde", 8.0, 0.0, 0.3, 0.0)
    assert [(o.id, o.nom) for o in t.instantane(0.0)] == [("vu/1", "banc"), ("vu/2", "Banc 2"),
                                                          ("carte/banc", "banc 3")]


def test_revu_meme_objet():
    t = TableauObjets()
    t.poser_pose("monde", 0.0, 0.0, 0.0)
    assert t.observer("vélo", "monde", 5.0, 1.0, 0.3, 0.0) == "vu/1"
    assert t.observer("vélo", "monde", 5.4, 1.2, 0.3, 4.0) == "vu/1"     # 0,45 m < 1 m : le même
    o = t.instantane(4.0)[0]
    assert (o.x, o.y, o.vu_il_y_a_s) == (5.4, 1.2, 0.0)


def test_vu_en_vue_puis_cible_puis_rien():
    t = TableauObjets()
    t.poser_pose("monde", 0.0, 0.0, 0.0)
    t.observer("vélo", "monde", 5.0, 0.0, 0.3, 0.0)
    assert [(o.en_vue, o.atteignable) for o in t.instantane(2.9)] == [(True, True)]
    assert [(o.en_vue, o.atteignable) for o in t.instantane(3.0)] == [(False, True)]
    assert [(o.en_vue, o.atteignable) for o in t.instantane(9.9)] == [(False, True)]
    assert [(o.en_vue, o.atteignable) for o in t.instantane(10.0)] == [(False, False)]


def test_peremption_vu():
    t = TableauObjets()
    t.poser_pose("monde", 0.0, 0.0, 0.0)
    t.observer("vélo", "monde", 5.0, 0.0, 0.3, 0.0)
    assert len(t.instantane(120.0)) == 1
    assert t.instantane(120.1) == []


def test_sigma_grandit_et_tombe():
    t = TableauObjets()
    t.poser_pose("monde", 0.0, 0.0, 0.0)
    t.observer("vélo", "monde", 5.0, 0.0, 0.8, 0.0)
    t.deplacement(4.0, 1.0)                     # +0,2 m -> 1,0 : encore une cible
    assert [(o.sigma_m, o.atteignable) for o in t.instantane(1.0)] == [(1.0, True)]
    t.deplacement(1.0, 1.5)                     # 1,05 : plus une cible
    assert [(o.sigma_m, o.atteignable) for o in t.instantane(1.5)] == [(1.05, False)]
    t.deplacement(19.0, 2.0)                    # 2,0 : gardé
    assert len(t.instantane(2.0)) == 1
    t.deplacement(0.2, 2.5)                     # 2,01 : tombe
    assert t.instantane(2.5) == []


def test_repere_robot_jamais_cible():
    t = TableauObjets()
    t.observer("vélo", "robot", 4.0, 3.0, 0.3, 0.0)        # sans pose : relatif au robot
    o = t.instantane(1.0)[0]
    assert (o.distance_m, o.azimut_deg, o.cote, o.en_vue, o.atteignable) == (5.0, 36.9, "devant", True, False)
    t.deplacement(0.1, 2.0)                  # il bouge : la position tombe, le nom reste 30 s
    o = t.instantane(3.0)[0]
    assert (o.x, o.distance_m, o.en_vue, o.atteignable, o.nom) == (None, None, False, False, "vélo")
    assert len(t.instantane(32.0)) == 1
    assert t.instantane(32.1) == []


def test_sigma_creation():
    # §6.4 : max(0,3 ; 4 % de d) + d²/h × σ_incl ; h = 1,06 m.
    assert sigma_creation(5.0, 1.06, 0.0) == pytest.approx(0.3)
    assert sigma_creation(10.0, 1.06, 0.0) == pytest.approx(0.4)
    assert sigma_creation(6.0, 1.06, 0.5) == pytest.approx(0.3 + 0.2964, abs=1e-3)
    assert sigma_creation(10.0, 1.06, 0.5) == pytest.approx(0.4 + 0.8233, abs=1e-3)


def test_constantes_gravees():
    assert (tb.CHAMP_DEMI_DEG, tb.VUE_MAX_M, tb.EN_VUE_VU_S, tb.ATTEIGNABLE_VU_S, tb.SIGMA_ATTEIGNABLE_M,
            tb.SIGMA_MAX_M, tb.SIGMA_PAR_METRE, tb.VU_PEREMPTION_S, tb.NOM_APRES_MOUVEMENT_S) == (
        30.0, 15.0, 3.0, 10.0, 1.0, 2.0, 0.05, 120.0, 30.0)
