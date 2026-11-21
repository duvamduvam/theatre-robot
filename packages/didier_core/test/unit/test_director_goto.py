"""Arbitrage « aller voir » du régisseur (didier_rehearsal.director, lot M1,
spec-aller-voir.md §2.1, §3) — logique PURE, valeurs GRAVÉES.

Mutations du lot M1 (doivent rougir) :
  - (O1) cible prise par le nom au lieu de l'id -> test_cible_par_id_seulement
  - off_by_david toujours False -> test_refus_route_off_par_david
  - retirer le refus too_far -> test_refus_trop_loin
  - accept_goto rend la vitesse retenue sans min(…) -> test_accept_goto_jamais_au_dessus_de_la_batterie
Revue O1 (19/11) — distance d'arrêt selon la TAILLE de l'objet :
  - standoff fixe 1,5 (taille ignorée)                 -> test_standoff_tient_compte_de_l_emprise
  - taille inconnue prise pour 0 (pas de borne prudente) -> test_standoff_taille_inconnue_borne_prudente
  - emprise lue sur le rayon d'ORBITE (2,2) au payload  -> test_objets_payload_marque_les_objets_qui_ont_un_tour
  - _number sans garde OverflowError                   -> test_avancer_nombre_geant_refuse_sans_exception
"""
import dataclasses
import json
import pathlib

import pytest

from didier_rehearsal.director import (GotoPolicy, VoiceMove, decide_forward, decide_goto, goto_order, move_reply,
                                      objects_payload, poi_name_of, standoff_pour, garde_corps_sur_m)
from didier_corps_sur.reglages import charger_reglages

PACKAGES = pathlib.Path(__file__).resolve().parents[3]
from theatre_contrats.objets import Objet, Tableau
from didier_rehearsal.route import Poi, Tour

ANNEAUX = Poi("anneaux", 78.42, 4.19, 2.5, desc="bagues géantes",
              alias=("anneaux", "bagues", "anneaux de buren", "cercles"))
TABLE = Poi("table_basse", 17.8, 1.4, 2.5)
POIS = (TABLE, ANNEAUX)


def test_objets_payload_ordre_itineraire_desc_ou_nom():
    # x, y (ancre du POI) : ajoutés au lot A1 (sélecteur de jeu, regard vers l'objet).
    # tour (15/11) : False sans tours fournis.
    # alias (O1, 18/11) : la résolution d'un nom dit vit dans le tableau des objets.
    assert json.loads(objects_payload(POIS)) == [
        {"name": "table_basse", "desc": "table_basse", "alias": [], "x": 17.8, "y": 1.4, "tour": False},
        {"name": "anneaux", "desc": "bagues géantes", "alias": ["anneaux", "bagues", "anneaux de buren", "cercles"],
         "x": 78.42, "y": 4.19, "tour": False}]
    assert objects_payload(()) == "[]"
    assert "géantes" in objects_payload(POIS)             # lisible (ensure_ascii=False)


def test_objets_payload_marque_les_objets_qui_ont_un_tour():
    # 15/11 : le chat doit savoir quels objets acceptent « faire le tour ».
    # O1 (18/11) : + centre de la géométrie de collision (cible d'« aller voir »).
    # Revue O1 (19/11) : + EMPRISE = orbite 2,2 − dégagement 1,0 (majorant de la collision) ; le
    # rayon d'orbite, lui, ne part plus (il réglait la fusion caméra à tort).
    objets = json.loads(objects_payload(POIS, {"anneaux": Tour(79.0, 6.5, 2.2)}))
    assert [(o["name"], o["tour"]) for o in objets] == [("table_basse", False), ("anneaux", True)]
    assert "cx" not in objets[0] and "emprise" not in objets[0]
    assert (objets[1]["cx"], objets[1]["cy"], objets[1]["emprise"]) == (79.0, 6.5, 1.2)
    assert "rayon" not in objets[1]


def test_move_reply_payload_grave():
    assert json.loads(move_reply({"cmd": "tour_de", "objet": "éléphant", "sens": "gauche"}, "no_tour")) == {
        "demande": {"cmd": "tour_de", "objet": "éléphant", "sens": "gauche"}, "effect": "no_tour",
        "reason": None, "name": None, "source": "director"}
    assert move_reply({"cmd": "avancer", "metres": -1}, "invalid", "recul") == (
        '{"demande": {"cmd": "avancer", "metres": -1}, "effect": "invalid", "reason": "recul", '
        '"name": null, "source": "director"}')
    assert json.loads(move_reply({"cmd": "tour_de", "objet": "banc"}, "accepted", name="tour de banc"))["name"] == (
        "tour de banc")


def _tableau(*objets_):
    return Tableau(tuple(objets_))


# Objets du tableau (lot O1) : la régie ne lit QUE l'id et la position.
O_ANNEAUX = Objet(id="carte/anneaux", nom="anneaux", x=78.42, y=4.19)
O_TABLE = Objet(id="carte/table_basse", nom="table_basse", x=17.8, y=2.1)
O_VU_ROBOT = Objet(id="vu/3", nom="vélo", sources=("vu",), repere="robot", x=4.0, y=1.0)
O_SANS_POSITION = Objet(id="vu/4", nom="sac", sources=("vu",), repere="robot")
TABLEAU = _tableau(O_TABLE, O_ANNEAUX, O_VU_ROBOT, O_SANS_POSITION)


def _goto(id_, pose=(70.0, 0.0), off_by_david=False, tableau=TABLEAU, objet="peu importe"):
    return decide_goto({"cmd": "aller_voir", "objet": objet, "id": id_}, tableau=tableau, pose=pose,
                       off_by_david=off_by_david)


def test_cible_par_id_seulement():
    # O1 (18/11) : le nom dit ne compte plus ici, il a été résolu dans le tableau.
    assert _goto("carte/anneaux", objet="la table").objet is O_ANNEAUX
    assert _goto(None, objet="anneaux").effect == "unknown"
    assert _goto("anneaux").effect == "unknown"            # un nom n'est pas un id
    assert _goto("carte/anneaux", tableau=None).effect == "unknown"   # tableau jamais reçu
    assert decide_goto("anneaux", tableau=TABLEAU, pose=(70.0, 0.0), off_by_david=False).effect == "unknown"


def test_accepte_avec_distance():
    d = _goto("carte/anneaux")
    assert (d.effect, d.objet, round(d.distance, 3)) == ("accepted", O_ANNEAUX, 9.405)   # √(8,42² + 4,19²)


def test_refus_sans_position_monde():
    assert (_goto("vu/3").effect, _goto("vu/4").effect) == ("no_position", "no_position")


def test_refus_route_off_par_david():
    d = _goto("carte/anneaux", off_by_david=True)
    assert (d.effect, d.objet) == ("route_off_by_david", O_ANNEAUX)


def test_refus_trop_loin():
    assert _goto("carte/anneaux", pose=(38.42, 4.19)).effect == "accepted"  # 40 m pile
    d = _goto("carte/anneaux", pose=(38.4, 4.19))
    assert (d.effect, round(d.distance, 2)) == ("too_far", 40.02)


def test_refus_sans_pose():
    assert _goto("carte/anneaux", pose=None).effect == "no_pose"


# Garde du corps sûr (A0-4, 22/11) : caisse.x_avant 0,30 + bande ARRET 0,60, lus dans le VRAI fichier
# de la sim (et du robot : mêmes cotes) par garde_corps_sur_m. Gravée ici, jamais recalculée.
GARDE = 0.90
CONF_SIM = PACKAGES / ".." / "machines" / "sim" / "robot" / "corps_sur.yaml"
CONF_ROBOT = PACKAGES / ".." / "machines" / "robot" / "corps_sur.yaml"


@pytest.mark.parametrize("chemin, domaine", [(CONF_SIM, "43"), (CONF_ROBOT, None)])
def test_garde_lue_dans_les_reglages_du_corps_sur(chemin, domaine):
    assert round(garde_corps_sur_m(charger_reglages(str(chemin), domaine)), 6) == GARDE


def test_garde_suit_les_reglages_et_n_est_pas_recopiee():
    """Mutants visés : une constante à la place des réglages, x_arriere au lieu de x_avant, la
    bande RALENTI au lieu de la bande ARRET."""
    r = charger_reglages(str(CONF_SIM), "43")
    autre = dataclasses.replace(r, caisse=dataclasses.replace(r.caisse, x_avant=0.40),
                                zones=dataclasses.replace(r.zones, marge_arret_m=0.70))
    assert round(garde_corps_sur_m(autre), 6) == 1.10


def test_ordre_route_goto_position_du_tableau():
    # Position du TABLEAU (centre de la table, 2,1) et non l'ancre du POI (1,4) ; emprise de la
    # table (orbite 1,7 − 1,0 = 0,7) -> arrêt à 0,7 + 0,90 (garde du corps sûr) + 0,5 (marge) = 2,1 m
    # du centre : l'avant de la caisse reste HORS de la bande ARRET (CONV D5, fumée 2026-11-21-2149 :
    # garé à 1,7 m, Didier était à 0,55 m de la table, en ARRET, et ne repartait plus).
    table = Objet(id="carte/table_basse", nom="table_basse", x=17.8, y=2.1, emprise_m=0.7)
    assert json.loads(goto_order(table, GARDE)) == {"name": "table_basse", "x": 17.8, "y": 2.1, "standoff": 2.1}
    # Taille inconnue : borne prudente 1,5 + 0,90 + 0,5 = 2,9 m.
    assert json.loads(goto_order(O_TABLE, GARDE))["standoff"] == 2.9


@pytest.mark.parametrize("emprise, attendu", [
    (1.1, 2.5),      # le banc de la revue (O1 : 2,1) : 1,1 + 0,90 + 0,5
    (0.7, 2.1),      # table basse (O1 : 1,7)
    (0.5, 1.9),      # orbite au plancher (pigeon, plot) : 0,5 + 1,4
    (0.2, 1.6),      # petit objet : au-dessus du plancher GOTO_STANDOFF_M (1,5)
    (0.0, 1.5),      # emprise nulle : 1,4 < 1,5, le plancher
    (5.0, 6.4),      # plus grand objet qui a un tour (orbite ≤ 6) : 5,0 + 1,4
    (100.0, 40.0),   # absurde : borné au plafond de parse_order
])
def test_standoff_tient_compte_de_l_emprise_et_du_corps_sur(emprise, attendu):
    assert standoff_pour(emprise, GARDE) == attendu


def test_la_garde_du_corps_sur_l_emporte_sur_le_rayon_de_didier():
    """Le terme O1 (roulette, 0,5) reste : il ne gagne que si la garde est plus petite."""
    assert standoff_pour(1.1, 0.3) == 2.1
    assert standoff_pour(1.1, 1.2) == 2.8


@pytest.mark.parametrize("garde", [None, 0.0, -0.9, float("nan"), float("inf"), "0.9", True])
def test_sans_garde_valide_aucun_standoff(garde):
    with pytest.raises(ValueError):
        standoff_pour(1.1, garde)


@pytest.mark.parametrize("emprise", [None, -1.0, float("nan"), float("inf"), "1", True, 10 ** 400])
def test_standoff_taille_inconnue_borne_prudente(emprise):
    assert standoff_pour(emprise, GARDE) == 2.9


def test_avancer_nombre_geant_refuse_sans_exception():
    # Revue O1 (19/11) : math.isfinite(10**400) lève OverflowError — dans le callback du régisseur.
    d = decide_forward({"cmd": "avancer", "metres": 10 ** 400}, pose_known=True, off_by_david=False)
    assert (d.effect, d.reason, d.order) == ("invalid", "illisible", None)


def test_poi_name_of():
    assert (poi_name_of(O_TABLE), poi_name_of(O_VU_ROBOT), poi_name_of(None)) == ("table_basse", None, None)


# --- arrêt vocal levé à l'acceptation ---------------------------------------------

def test_accept_goto_leve_l_arret_vocal_a_la_vitesse_du_go():
    v = VoiceMove()
    v.decide("stop", 0.0, in_session=True, lubie_active=False, route_on=True,
             relaunch_refusal=None, speed_in_effect=0.6)
    d = v.accept_goto(lubie_active=False, speed_in_effect=0.6)
    assert (d.effect, d.speed, v.hold_before) == ("goto", 0.6, None)


def test_accept_goto_jamais_au_dessus_de_la_batterie():
    v = VoiceMove()
    v.decide("stop", 0.0, in_session=True, lubie_active=False, route_on=True,
             relaunch_refusal=None, speed_in_effect=0.8)
    assert v.accept_goto(lubie_active=False, speed_in_effect=0.4).speed == 0.4


def test_accept_goto_sans_arret_ne_publie_aucune_vitesse_et_ferme_la_lubie():
    v = VoiceMove()
    assert (v.accept_goto(lubie_active=False, speed_in_effect=0.6).speed) is None
    assert v.accept_goto(lubie_active=True, speed_in_effect=0.6).effect == "close_lubie"


def test_accept_goto_annule_une_salve_de_relance():
    v = VoiceMove()
    v.decide("go", 0.0, in_session=True, lubie_active=False, route_on=False,
             relaunch_refusal=None, speed_in_effect=0.5)
    assert v.relaunching
    v.accept_goto(lubie_active=False, speed_in_effect=0.5)
    assert not v.relaunching


def test_go_rejoin_releve_l_arret_et_relance():
    v = VoiceMove()
    v.decide("stop", 0.0, in_session=True, lubie_active=False, route_on=False,
             relaunch_refusal=None, speed_in_effect=0.5)
    d = v.decide("go", 5.0, in_session=True, lubie_active=False, route_on=False,
                 relaunch_refusal="etat_inconnu", speed_in_effect=0.5, rejoin=True)
    assert (d.effect, d.speed, d.rejoin, v.relaunching) == ("resume", 0.5, True, True)
    w = VoiceMove()
    d = w.decide("go", 5.0, in_session=True, lubie_active=False, route_on=False,
                 relaunch_refusal="etat_inconnu", speed_in_effect=0.5, rejoin=True)
    assert (d.effect, d.rejoin) == ("rejoin", True)


# --- GotoPolicy --------------------------------------------------------------------

def test_policy_issues_journalisees():
    g = GotoPolicy()
    g.accept("anneaux")
    assert g.note_state("goto", 0.5) is None
    assert g.note_state("arrived", 0.5) == ("goto_arrived", {"name": "anneaux"})
    g.accept("flaque")
    g.note_state("goto", 0.5)
    assert g.note_state("off", 0.5) == ("goto_abort", {"name": "flaque"})
    g.accept("banc")
    g.note_state("goto", 0.5)
    g.cancel("stop")
    assert g.note_state("off", 0.5) == ("goto_cancelled", {"name": "banc", "by": "stop"})


def test_policy_reprise_jamais_contre_david():
    g = GotoPolicy()
    assert not g.rejoin_allowed("arrived", False)          # pas notre manœuvre
    g.accept("anneaux")
    g.note_state("goto", 0.5)
    g.note_state("arrived", 0.5)
    assert g.rejoin_allowed("arrived", False)
    assert not g.rejoin_allowed("arrived", True)           # `off` de David vu
    assert g.note_route_cmd("off") is None                 # arrivé : rien en cours
    assert g.owned is None and not g.rejoin_allowed("off", False)


def test_policy_cause_publiee_libere():
    g = GotoPolicy()
    g.accept("anneaux")
    g.note_cause()                                         # boot ou `off` par commande
    assert g.owned is None


def test_policy_off_by_david():
    g = GotoPolicy()
    assert g.off_by_david("off", "cmd", False)
    assert g.off_by_david("on", "boot", True)
    assert not g.off_by_david("on", "cmd", False)          # cause périmée d'un off/on : route ON
    assert not g.off_by_david("off", "boot", False)
    g.accept("anneaux")
    assert not g.off_by_david("off", "cmd", False)         # « off » qui suit NOTRE manœuvre


def test_policy_fader_reprend_seulement_arrive_et_sur_un_geste():
    g = GotoPolicy()
    g.accept("anneaux")
    g.note_state("goto", 0.5)
    assert not g.fader_rejoins(0.8, "goto", False)
    g.note_state("arrived", 0.5)
    assert not g.fader_rejoins(0.55, "arrived", False)     # jitter, pas un geste
    assert not g.fader_rejoins(0.0, "arrived", False)      # vers zéro : reste arrêté
    assert not g.fader_rejoins(0.8, "arrived", True)
    assert g.fader_rejoins(0.56, "arrived", False)


def test_skip_poi_saute_seulement_les_lubies_en_attente_de_ce_poi():
    from didier_rehearsal.director import Director
    from didier_rehearsal.scenario import load_scenario
    sc = load_scenario({"name": "e", "seed": 0, "duration_s": 300, "faults": [
        {"id": "lubie_banc", "type": "lubie", "t": "poi", "poi": "banc", "duration_s": 60},
        {"id": "lubie_flaque", "type": "lubie", "t": "poi", "poi": "flaque", "duration_s": 60},
        {"id": "consigne_banc", "type": "instruction", "t": "poi", "poi": "banc", "text": "x"}]},
        pois={"banc": "Un banc.", "flaque": "Une flaque."})
    d = Director(sc)
    assert d.skip_poi("banc") == []                         # hors séance : rien
    d.start(0.0)
    assert d.skip_poi("banc") == ["lubie_banc"]
    assert d.status() == {"lubie_banc": "skipped", "lubie_flaque": "pending", "consigne_banc": "pending"}
    assert [a.fault.id for a in d.trigger("banc", 1.0) if a.kind == "start"] == ["consigne_banc"]


def test_policy_cible_seulement_en_goto_ou_arrive():
    g = GotoPolicy()
    g.accept("anneaux")
    assert not g.is_target("anneaux", "on")
    assert g.is_target("anneaux", "goto") and g.is_target("anneaux", "arrived")
    assert not g.is_target("flaque", "goto")
