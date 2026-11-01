"""Arbitrage « aller voir » du régisseur (robot_rehearsal.director, lot M1,
spec-aller-voir.md §2.1, §3) — logique PURE, valeurs GRAVÉES.

Mutations du lot M1 (doivent rougir) :
  - resolve_object renvoie le premier POI -> test_resolution_normalisee
  - off_by_david toujours False -> test_refus_route_off_par_david
  - retirer le refus too_far -> test_refus_trop_loin
  - accept_goto rend la vitesse retenue sans min(…) -> test_accept_goto_jamais_au_dessus_de_la_batterie
"""
import json

from robot_rehearsal.director import (GotoPolicy, VoiceMove, decide_goto, goto_order, objects_payload,
                                      resolve_object)
from robot_rehearsal.route import Poi

ANNEAUX = Poi("anneaux", 78.42, 4.19, 2.5, desc="bagues géantes",
              alias=("anneaux", "bagues", "anneaux de buren", "cercles"))
TABLE = Poi("table_basse", 17.8, 1.4, 2.5)
POIS = (TABLE, ANNEAUX)


def test_objets_payload_ordre_itineraire_desc_ou_nom():
    assert json.loads(objects_payload(POIS)) == [{"name": "table_basse", "desc": "table_basse"},
                                                 {"name": "anneaux", "desc": "bagues géantes"}]
    assert objects_payload(()) == "[]"


def test_resolution_normalisee():
    assert resolve_object("les Anneaux de Buren", POIS) is ANNEAUX
    assert resolve_object("des bagues", POIS) is ANNEAUX
    assert resolve_object("la table basse", POIS) is TABLE
    assert resolve_object("table_basse", POIS) is TABLE
    assert resolve_object("anneau", POIS) is None          # rien de flou
    assert resolve_object("", POIS) is None
    assert resolve_object(None, POIS) is None


def test_accepte_avec_distance():
    d = decide_goto("bagues", pois=POIS, pose=(70.0, 0.0), off_by_david=False)
    assert (d.effect, d.poi, round(d.distance, 3)) == ("accepted", ANNEAUX, 9.405)   # √(8,42² + 4,19²)


def test_refus_inconnu():
    d = decide_goto("pigeon", pois=POIS, pose=(70.0, 0.0), off_by_david=False)
    assert (d.effect, d.poi) == ("unknown", None)


def test_refus_route_off_par_david():
    d = decide_goto("anneaux", pois=POIS, pose=(70.0, 0.0), off_by_david=True)
    assert (d.effect, d.poi) == ("route_off_by_david", ANNEAUX)


def test_refus_trop_loin():
    assert decide_goto("anneaux", pois=POIS, pose=(38.42, 4.19), off_by_david=False).effect == "accepted"  # 40 m pile
    d = decide_goto("anneaux", pois=POIS, pose=(38.4, 4.19), off_by_david=False)
    assert (d.effect, round(d.distance, 2)) == ("too_far", 40.02)


def test_refus_sans_pose():
    assert decide_goto("anneaux", pois=POIS, pose=None, off_by_david=False).effect == "no_pose"


def test_ordre_route_goto():
    assert json.loads(goto_order(ANNEAUX)) == {"name": "anneaux", "x": 78.42, "y": 4.19, "standoff": 1.5}


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
    from robot_rehearsal.director import Director
    from robot_rehearsal.scenario import load_scenario
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
