"""Ordonnanceur du régisseur (didier_rehearsal.director) — valeurs gravées.
Mutation (2026-10-08) : retirer l'exclusion par cible -> test_meme_cible_sautee ;
retirer l'arrêt à duration_s -> test_fin_de_scenario_arrete_tout ; retirer le
re-bornage FAULT_MAX_DURATION_S -> test_duree_rebornee ; cancel() qui laisse la cible
occupée -> test_cancel_libere_la_cible_sans_stop.
Lot R3 (2026-10-14) : déclencheurs POI (trigger) et messages JSON partagés avec
chat_node (messages) — mutations listées dans le rapport du lot.
Revue adversariale R3 (2026-10-14) : abort avant start inerte, close_active
(fermeture au fader), restore explicite, phantom sans « pass », vitesse en
vigueur — mutations listées dans le rapport ; le node : test_director_node.py."""
from didier_rehearsal.director import Director
from didier_rehearsal.scenario import Fault, Scenario


def _sc(*faults, duration=100.0):
    return Scenario("t", 0, duration, tuple(faults))


def _pause(fid, t, d, proc="face_sim"):
    return Fault(fid, "pause", t, d, {"process": proc}, f"process:{proc}")


def _kinds(actions):
    return [(a.kind, a.fault.id if a.fault else None) for a in actions]


def test_inactif_avant_start():
    d = Director(_sc(_pause("a", 0.0, 5.0)))
    assert d.tick(0.0) == []
    assert d.status() == {"a": "pending"}


def test_start_stop_a_l_instant_relatif():
    d = Director(_sc(_pause("a", 2.0, 3.0)))
    d.start(100.0)                        # t0 = 100 : les instants sont RELATIFS
    assert d.tick(101.9) == []
    assert _kinds(d.tick(102.0)) == [("start", "a")]
    assert d.active() == ["a"]
    assert d.tick(104.9) == []
    assert _kinds(d.tick(105.0)) == [("stop", "a")]
    assert d.status() == {"a": "done"}
    assert d.active() == []


def test_ponctuelle_start_et_stop_meme_tick():
    f = Fault("k", "kill", 1.0, 0.0, {"process": "route_driver", "reenable": True}, "process:route_driver")
    d = Director(_sc(f)); d.start(0.0)
    assert _kinds(d.tick(1.0)) == [("start", "k"), ("stop", "k")]


def test_meme_cible_sautee():
    d = Director(_sc(_pause("a", 0.0, 10.0), _pause("b", 5.0, 2.0))); d.start(0.0)
    d.tick(0.0)
    assert _kinds(d.tick(5.0)) == [("skip", "b")]
    assert d.status() == {"a": "active", "b": "skipped"}
    # cibles différentes : pas d'exclusion
    e = Director(_sc(_pause("a", 0.0, 10.0), _pause("c", 5.0, 2.0, proc="servos_sim_node"))); e.start(0.0)
    e.tick(0.0)
    assert _kinds(e.tick(5.0)) == [("start", "c")]


def test_arret_avant_demarrage_libere_la_cible():
    d = Director(_sc(_pause("a", 0.0, 5.0), _pause("b", 5.0, 1.0))); d.start(0.0)
    d.tick(0.0)
    assert _kinds(d.tick(5.0)) == [("stop", "a"), ("start", "b")]


def test_duree_rebornee():
    # pause : max 30 s (contrats) — une durée de 999 est re-bornée à 30
    d = Director(_sc(_pause("a", 0.0, 999.0))); d.start(0.0)
    d.tick(0.0)
    assert d.tick(29.9) == []
    assert _kinds(d.tick(30.0)) == [("stop", "a")]


def test_fin_de_scenario_arrete_tout():
    d = Director(_sc(_pause("a", 0.0, 50.0), _pause("z", 99.0, 1.0, proc="leds_sim_node"), duration=20.0)); d.start(0.0)
    d.tick(0.0)
    assert _kinds(d.tick(20.0)) == [("stop", "a"), ("end", None)]
    assert d.status() == {"a": "done", "z": "skipped"}
    assert d.ended and d.tick(21.0) == []


def test_abort():
    d = Director(_sc(_pause("a", 0.0, 50.0), _pause("b", 10.0, 1.0, proc="leds_sim_node"))); d.start(0.0)
    d.tick(0.0)
    assert _kinds(d.abort(3.0)) == [("stop", "a"), ("end", None)]
    assert d.status() == {"a": "done", "b": "skipped"}
    assert d.abort(4.0) == []


def test_cancel_libere_la_cible_sans_stop():
    d = Director(_sc(_pause("a", 0.0, 10.0), _pause("b", 2.0, 1.0))); d.start(0.0)
    assert _kinds(d.tick(0.0)) == [("start", "a")]
    d.cancel("a", 0.5)                      # le node n'a pas pu l'appliquer
    assert d.status()["a"] == "error" and d.active() == []
    assert _kinds(d.tick(2.0)) == [("start", "b")]   # cible libre : b n'est pas sautée
    assert [k for k, _ in _kinds(d.tick(50.0))] == ["stop"]   # jamais de stop pour a


# --- ReenablePolicy (revue adversariale + bug vécu du 2026-10-08) -----------
from didier_rehearsal.director import ReenablePolicy


def test_relance_seulement_si_route_on_au_kill():
    p = ReenablePolicy(min_delay_s=6.0, max_delay_s=30.0, retry_s=1.0)
    assert p.arm("k1", 100.0) is False            # route jamais mise ON
    p.note_route_cmd("on")
    assert p.arm("k2", 100.0) is True
    assert p.due(105.9, True) == (False, [])      # trop tôt
    assert p.due(106.0, False) == (False, [])     # consommateur pas prêt
    assert p.due(106.0, True) == (True, [])       # envoi
    assert p.due(106.5, True) == (False, [])      # pas avant retry_s
    assert p.due(107.0, True) == (True, [])       # RÉ-ESSAI : pas confirmé
    assert p.note_state("on", 107.2) == ["k2"]    # confirmé par l'état latché
    assert p.due(108.0, True) == (False, []) and p.pending() == []


def test_off_de_david_annule_la_relance():
    p = ReenablePolicy(); p.note_route_cmd("on"); p.arm("k", 0.0)
    p.note_route_cmd("off")
    assert p.due(10.0, True) == (False, []) and p.route_on is False


def test_relance_expire_et_abort_vide():
    p = ReenablePolicy(min_delay_s=6.0, max_delay_s=30.0); p.note_route_cmd("on")
    p.arm("k", 0.0)
    assert p.due(30.0, False) == (False, ["k"])   # jamais confirmée -> expirée, dite
    p.arm("k2", 0.0)
    assert p.abort() == ["k2"] and p.due(10.0, True) == (False, [])


def test_etat_latche_arme_et_confirme_sans_annuler():
    """Bug du 08/10 : l'unique `route on` volatile avait été raté. L'état
    latché suffit à armer ; le « off » du route_driver RESPAWNÉ n'annule PAS ;
    un « on » reçu AVANT not_before ne confirme rien (c'est l'ancien état)."""
    p = ReenablePolicy(min_delay_s=6.0, max_delay_s=30.0)
    assert p.note_state("on", 0.0) == []          # aucun message `route on` vu
    assert p.arm("k", 0.0) is True
    assert p.note_state("on", 2.0) == []          # trop tôt : pas une confirmation
    p.note_state("off", 5.0)                      # route_driver respawné démarre OFF
    assert p.due(6.0, True) == (True, [])
    assert p.note_state("on", 6.3) == ["k"]
    assert p.note_state("n'importe quoi", 7.0) == [] and p.route_on is True


# --- Lot R3 : déclencheurs POI (trigger) ---------------------------------------

def _lubie(fid, poi, d=60.0, **params):
    pr = {"poi": poi, "text": None, "stop": True, "restore": 1.0}
    pr.update(params)
    return Fault(fid, "lubie", None, d, pr, "speed", trigger_poi=poi, draw_p=0.4)


def _speed(fid, t, d, value=0.4):
    return Fault(fid, "speed", t, d, {"value": value, "restore": 1.0}, "speed")


def test_tick_ne_demarre_jamais_un_declencheur_poi():
    d = Director(_sc(_lubie("l", "banc"))); d.start(0.0)
    assert d.tick(0.0) == [] and d.tick(50.0) == []
    assert d.status() == {"l": "pending"}


def test_trigger_demarre_et_arrete_a_duree_apres_l_enter():
    d = Director(_sc(_lubie("l", "banc"), _lubie("m", "flaque"))); d.start(100.0)
    assert d.trigger("lampadaire", 105.0) == []              # POI sans déclencheur : rien
    assert _kinds(d.trigger("banc", 110.0)) == [("start", "l")]
    assert d.status() == {"l": "active", "m": "pending"}     # seul le POI visé part
    assert d.tick(169.9) == []                               # rel 10 + 60 = 70
    assert _kinds(d.tick(170.0)) == [("stop", "l")]


def test_trigger_une_seule_fois_par_seance():
    d = Director(_sc(_lubie("l", "banc"))); d.start(0.0)
    assert _kinds(d.trigger("banc", 5.0)) == [("start", "l")]
    assert d.trigger("banc", 6.0) == []                      # 2e enter pendant la lubie
    d.tick(65.0)
    assert d.status() == {"l": "done"}
    assert d.trigger("banc", 70.0) == []                     # Didier repoussé en arrière : rien


def test_exclusion_speed_contre_lubie_sans_seconde_chance():
    d = Director(_sc(_speed("batterie", 0.0, 20.0), _lubie("l", "banc"))); d.start(0.0)
    assert _kinds(d.tick(0.0)) == [("start", "batterie")]
    assert _kinds(d.trigger("banc", 5.0)) == [("skip", "l")]
    assert d.status() == {"batterie": "active", "l": "skipped"}
    d.tick(20.0)                                             # cible libre…
    assert d.trigger("banc", 30.0) == []                     # …mais pas de seconde chance
    # et dans l'autre sens : lubie active -> le bug speed est sauté
    e = Director(_sc(_lubie("l", "banc"), _speed("batterie", 10.0, 20.0))); e.start(0.0)
    e.trigger("banc", 1.0)
    assert _kinds(e.tick(10.0)) == [("skip", "batterie")]


def test_trigger_libere_d_abord_les_arrets_echus():
    d = Director(_sc(_speed("batterie", 0.0, 10.0), _lubie("l", "banc"))); d.start(0.0)
    d.tick(0.0)
    # enter à 10.0 pile, AVANT le tick : la batterie est échue, la lubie part
    assert _kinds(d.trigger("banc", 10.0)) == [("stop", "batterie"), ("start", "l")]


def test_trigger_avant_start_ou_apres_la_fin():
    d = Director(_sc(_lubie("l", "banc"), duration=20.0))
    assert d.trigger("banc", 0.0) == [] and d.status() == {"l": "pending"}
    d.start(0.0)
    assert d.trigger("banc", 20.0) == []                     # durée atteinte, avant le tick de fin
    assert _kinds(d.tick(20.0)) == [("end", None)]
    assert d.status() == {"l": "skipped"}                    # jamais atteint -> skipped
    assert d.trigger("banc", 21.0) == []


def test_lubie_rebornee_a_120():
    d = Director(_sc(_lubie("l", "banc", d=999.0), duration=1000.0)); d.start(0.0)
    d.trigger("banc", 10.0)
    assert d.tick(129.9) == []
    assert _kinds(d.tick(130.0)) == [("stop", "l")]


def test_abort_saute_les_poi_jamais_atteints():
    d = Director(_sc(_lubie("l", "banc"), _lubie("m", "flaque"))); d.start(0.0)
    d.trigger("banc", 1.0)
    assert _kinds(d.abort(2.0)) == [("stop", "l"), ("end", None)]
    assert d.status() == {"l": "done", "m": "skipped"}


# --- Lot R3 : messages EXACTS (contrats partagés avec chat_node) ----------------
import pytest

from didier_rehearsal.director import messages


def test_messages_lubie():
    f = _lubie("l", "banc", restore=0.6)
    assert messages(f, "start", "Un banc : tu veux t'asseoir.") == [
        ("chat_instruction", '"Un banc : tu veux t\'asseoir."'),
        ("route_speed", "0"),
    ]
    assert messages(f, "stop") == [("chat_instruction", '""'), ("route_speed", "0.6")]
    g = _lubie("g", "banc", stop=False)
    assert messages(g, "start", "Éléphant") == [("chat_instruction", '"Éléphant"')]
    assert messages(g, "stop") == [("chat_instruction", '""')]     # vitesse jamais prise, jamais rendue


def test_messages_instruction_bornee_ou_ponctuelle():
    bornee = Fault("i", "instruction", 0.0, 30.0, {"text": "tu boudes"}, "instruction")
    assert messages(bornee, "start") == [("chat_instruction", '"tu boudes"')]
    assert messages(bornee, "stop") == [("chat_instruction", '""')]
    ponctuelle = Fault("j", "instruction", 0.0, 0.0, {"text": "tu boudes"}, "instruction")
    assert messages(ponctuelle, "stop") == []                       # R2 : rien à lever


def test_messages_chat_json_grave():
    delay = Fault("d", "chat", 0.0, 40.0, {"op": "delay", "params": {"delay_ms": 6000}}, "chat")
    assert messages(delay, "start") == [
        ("rehearsal/chat_fault", '{"op": "delay", "params": {"delay_ms": 6000}, "until_ms": 40000}')]
    assert messages(delay, "stop") == [
        ("rehearsal/chat_fault", '{"op": "pass", "params": {}, "until_ms": null}')]
    phantom = Fault("p", "chat", 0.0, 0.0, {"op": "phantom", "params": {"text": "communauté d'Amara.org"}}, "chat")
    assert messages(phantom, "start") == [
        ("rehearsal/chat_fault", '{"op": "phantom", "params": {"text": "communauté d\'Amara.org"}, "until_ms": 0}')]
    # re-borné à 60 s même si le scénario (non validé) en demandait plus : pas de chien de garde
    long = Fault("l", "chat", 0.0, 999.0, {"op": "deaf", "params": {}}, "chat")
    assert messages(long, "start") == [
        ("rehearsal/chat_fault", '{"op": "deaf", "params": {}, "until_ms": 60000}')]


def test_messages_refuse_un_type_non_messager():
    with pytest.raises(ValueError):
        messages(_pause("a", 0.0, 5.0), "start")


# --- Revue adversariale R3 (2026-10-14) ---------------------------------------------
from didier_rehearsal.director import fader_moved, speed_factor, speed_in_effect
from didier_rehearsal.scenario import load_scenario


def test_abort_avant_start_ne_fait_rien_et_la_seance_part_ensuite():
    """Défaut : un STOP avant START sautait toute la timeline (pending ->
    skipped) et le START suivant jouait une séance vide."""
    d = Director(_sc(_pause("a", 1.0, 5.0), _lubie("l", "banc")))
    assert d.abort(0.0) == []
    assert d.status() == {"a": "pending", "l": "pending"}
    assert (d.started, d.ended) == (False, False)
    d.start(10.0)
    assert _kinds(d.tick(11.0)) == [("start", "a")]
    assert _kinds(d.trigger("banc", 12.0)) == [("start", "l")]


def test_close_active_ferme_une_lubie_et_libere_la_cible():
    d = Director(_sc(_lubie("l", "banc"), _speed("batterie", 10.0, 5.0))); d.start(0.0)
    d.trigger("banc", 2.0)
    assert _kinds(d.close_active("speed", 3.0)) == [("stop", "l")]
    assert d.status() == {"l": "done", "batterie": "pending"} and d.active() == []
    assert _kinds(d.tick(10.0)) == [("start", "batterie")]       # cible libérée : pas sautée
    assert _kinds(d.tick(62.0)) == [("stop", "batterie")]       # l (échéance 62) : jamais de 2e stop
    assert d.close_active("lubie-inconnue", 63.0) == []


def test_close_active_ne_ferme_que_le_type_demande():
    """Une batterie faible (speed, MÊME cible) ne se ferme pas au fader."""
    d = Director(_sc(_speed("batterie", 0.0, 20.0))); d.start(0.0)
    d.tick(0.0)
    assert d.close_active("speed", 1.0) == [] and d.active() == ["batterie"]
    assert _kinds(d.close_active("speed", 1.0, only_type="speed")) == [("stop", "batterie")]


def test_messages_lubie_restore_explicite_ou_aucun():
    f = _lubie("l", "banc", restore=0.6)
    assert messages(f, "stop", "x", restore_value=0.35) == [
        ("chat_instruction", '""'), ("route_speed", "0.35")]                 # vitesse en vigueur
    assert messages(f, "stop", "x", restore_value=None) == [("chat_instruction", '""')]   # fermée au fader
    g = _lubie("g", "banc", stop=False)
    assert messages(g, "stop", "x", restore_value=0.35) == [("chat_instruction", '""')]   # jamais prise


def test_phantom_ne_leve_rien_et_ne_bloque_ni_n_est_bloque():
    sc = load_scenario({"name": "t", "duration_s": 100, "faults": [
        {"id": "g", "type": "chat", "op": "garble", "t": 0, "duration_s": 30},
        {"id": "p", "type": "chat", "op": "phantom", "params": {"text": "Amara.org"}, "t": 5},
        {"id": "d", "type": "chat", "op": "delay", "params": {"delay_ms": 6000}, "t": 6, "duration_s": 10},
    ]})
    phantom = next(f for f in sc.faults if f.id == "p")
    assert messages(phantom, "stop") == []           # un « pass » couperait le garble en cours
    d = Director(sc); d.start(0.0)
    assert _kinds(d.tick(0.0)) == [("start", "g")]
    assert _kinds(d.tick(5.0)) == [("start", "p"), ("stop", "p")]   # pas sauté par le garble
    assert _kinds(d.tick(6.0)) == [("skip", "d")]                    # delay/garble : même cible chat
    assert d.active() == ["g"]


def test_vitesse_en_vigueur_ordre_de_priorite():
    assert speed_in_effect(0.7, 0.3, 1.0) == 0.7     # le fader de David d'abord
    assert speed_in_effect(None, 0.3, 1.0) == 0.3    # sinon la vitesse du launch
    assert speed_in_effect(None, None, 1.0) == 1.0   # sinon restore du scénario
    assert speed_in_effect(0.0, 0.3, 1.0) == 0.0     # fader à zéro : une valeur, pas « inconnue »


def test_fader_moved_seuil_strict_a_0_05():
    assert fader_moved(0.5, 0.5) is False            # ré-émission du boîtier
    assert fader_moved(0.55, 0.5) is False           # 0,05 pile (0.05000000000000004 en flottant)
    assert fader_moved(0.45, 0.5) is False
    assert fader_moved(0.551, 0.5) is True
    assert fader_moved(0.0, 0.5) is True


def test_speed_factor_decode_comme_route_driver():
    assert speed_factor("0.7") == 0.7
    assert speed_factor('"0.7"') == 0.7              # chaîne JSON
    assert speed_factor("1.5") == 1.0 and speed_factor("-2") == 0.0   # borné, jamais refusé
    assert speed_factor("abc") is None and speed_factor("NaN") is None
    assert speed_factor(0.25) == 0.25                # paramètre ROS (déjà un nombre)


# --- Lot I1 (22/10) : mouvement à la voix — logique pure -------------------------
# Règles révisées par la revue adversariale I1 (D1 cause latchée, D3 « stop »
# toujours republié, D5 pas d'anti-rebond sur « stop »). Mutations listées
# dans le rapport du lot ; le node : test_director_node.py.
from didier_rehearsal.director import VoiceDecision, VoiceMove, route_cmd_kind

# Contexte par défaut : en séance, en route, rien d'arrêté, vitesse en vigueur 0.7.
_EN_ROUTE = dict(in_session=True, lubie_active=False,
                 route_on=True, relaunch_refusal="route_off_par_david", speed_in_effect=0.7)
_RELANCABLE = dict(route_on=False, relaunch_refusal=None)


def _ctx(**over):
    return dict(_EN_ROUTE, **over)


HOLD = VoiceDecision("hold", speed=0)


def test_voix_ordre_invalide_ignore():
    v = VoiceMove()
    for cmd in ("recule", "GO", "", None, 1, ["go"]):
        assert v.decide(cmd, 0.0, **_ctx()) == VoiceDecision("ignored", "invalide")
    assert v.hold_before is None


def test_voix_anti_rebond_2_s_sur_go_seulement():
    v = VoiceMove()
    assert v.decide("stop", 10.0, **_ctx()) == HOLD
    assert v.decide("stop", 10.1, **_ctx()) == HOLD          # « stop » : JAMAIS filtré
    assert v.decide("go", 10.5, **_ctx()) == VoiceDecision("resume", speed=0.7)
    assert v.decide("go", 12.49, **_ctx()) == VoiceDecision("ignored", "rebond")
    assert v.decide("go", 12.5, **_ctx()) == VoiceDecision("ignored", "deja_en_marche")
    # Un « stop » entre deux « go » : le second n'est plus « identique au précédent ».
    w = VoiceMove()
    w.decide("go", 0.0, **_ctx()); w.decide("stop", 0.5, **_ctx())
    assert w.decide("go", 1.0, **_ctx()) == VoiceDecision("resume", speed=0.7)


def test_voix_hors_seance_go_ignore_stop_applique():
    v = VoiceMove()
    assert v.decide("go", 0.0, **_ctx(in_session=False, lubie_active=True)) == \
        VoiceDecision("ignored", "hors_seance")
    assert v.decide("stop", 5.0, **_ctx(in_session=False)) == HOLD
    assert v.hold_before == 0.7


def test_voix_stop_toujours_republie_et_garde_la_vitesse_retenue():
    v = VoiceMove()
    assert v.decide("stop", 5.0, **_ctx(speed_in_effect=0.4)) == HOLD
    assert v.decide("stop", 6.0, **_ctx(speed_in_effect=0.9)) == HOLD
    assert v.hold_before == 0.4      # la 1re vitesse retenue, jamais écrasée


def test_voix_stop_pose_l_arret_meme_pendant_une_lubie():
    # Défaut vécu en sim le 22/10 : pendant une lubie stop, « stop » ne posait
    # pas d'arrêt vocal — la fin de la lubie rendait la vitesse.
    v = VoiceMove()
    assert v.decide("stop", 0.0, **_ctx(lubie_active=True, speed_in_effect=0.6)) == HOLD
    assert v.hold_before == 0.6


def test_voix_go_lubie_et_arret_une_seule_vitesse():
    v = VoiceMove(); v.decide("stop", 0.0, **_ctx(lubie_active=True, speed_in_effect=0.7))
    assert v.decide("go", 5.0, **_ctx(lubie_active=True, speed_in_effect=0.6)) == \
        VoiceDecision("close_lubie", speed=0.6)                 # min(retenue 0.7, en vigueur 0.6)
    assert v.hold_before is None


def test_voix_go_ordre_des_regles():
    # a. lubie active : fermée, AVANT même un arrêt vocal (levé avec elle)
    assert VoiceMove().decide("go", 0.0, **_ctx(lubie_active=True)) == VoiceDecision("close_lubie")
    v = VoiceMove(); v.decide("stop", 0.0, **_ctx())
    assert v.decide("go", 5.0, **_ctx(lubie_active=True)) == VoiceDecision("close_lubie", speed=0.7)
    # b. arrêt vocal : vitesse retenue rendue, arrêt levé
    v.decide("stop", 6.0, **_ctx())
    assert v.decide("go", 10.0, **_ctx()) == VoiceDecision("resume", speed=0.7)
    assert v.hold_before is None
    # c. route OFF : relance si aucun refus, sinon la raison du refus telle quelle
    assert v.decide("go", 15.0, **_ctx(**_RELANCABLE)) == VoiceDecision("relaunch")
    for refus in ("route_off_par_david", "cause_inconnue", "etat_inconnu"):
        w = VoiceMove()
        assert w.decide("go", 0.0, **_ctx(route_on=False, relaunch_refusal=refus)) == \
            VoiceDecision("ignored", refus)
        assert not w.relaunching
    # d. en route, rien d'arrêté
    assert VoiceMove().decide("go", 5.0, **_ctx()) == VoiceDecision("ignored", "deja_en_marche")


def test_voix_go_jamais_plus_vite_que_la_vitesse_en_vigueur():
    v = VoiceMove(); v.decide("stop", 0.0, **_ctx(speed_in_effect=0.7))
    # Jitter du boîtier sous le seuil : arrêt maintenu, mais vitesse en vigueur 0.68.
    assert v.decide("go", 5.0, **_ctx(speed_in_effect=0.68)) == VoiceDecision("resume", speed=0.68)


def test_voix_fader_leve_l_arret_au_dela_du_seuil_seulement():
    v = VoiceMove()
    assert v.fader(0.9) is False                 # pas d'arrêt vocal : rien à lever
    v.decide("stop", 0.0, **_ctx(speed_in_effect=0.5))
    assert v.fader(0.55) is False and v.hold_before == 0.5   # écart 0,05 : ré-émission
    assert v.fader(0.8) is True and v.hold_before is None
    assert v.decide("go", 5.0, **_ctx()) == VoiceDecision("ignored", "deja_en_marche")


def test_voix_release_hold_et_abort():
    v = VoiceMove(); v.decide("stop", 0.0, **_ctx(speed_in_effect=0.6))
    assert v.release_hold() == 0.6 and v.release_hold() is None
    v.decide("stop", 5.0, **_ctx(speed_in_effect=0.3))
    assert v.abort() == (0.3, False) and v.hold_before is None
    w = VoiceMove(); w.decide("go", 0.0, **_ctx(**_RELANCABLE))
    assert w.abort() == (None, True) and not w.relaunching


def test_voix_salve_de_relance_3_envois_puis_expiration():
    v = VoiceMove()
    assert v.relaunch_due(0.0) == (False, False)          # rien d'armé
    v.decide("go", 100.0, **_ctx(**_RELANCABLE))
    assert v.relaunch_due(100.0) == (True, False)
    assert v.relaunch_due(100.2) == (False, False)
    assert v.relaunch_due(100.5) == (True, False)
    assert v.relaunch_due(101.0) == (True, False)
    assert v.relaunch_due(101.5) == (False, False)        # 3 envois, pas un de plus
    assert v.relaunch_due(102.9) == (False, False)
    assert v.relaunch_due(103.0) == (False, True)         # jamais confirmée : expirée, dite
    assert not v.relaunching and v.relaunch_due(104.0) == (False, False)


def test_voix_relance_confirmee_par_l_etat_latche_seulement():
    v = VoiceMove()
    assert v.note_state("on") is False                    # rien d'armé : pas une confirmation
    v.decide("go", 10.0, **_ctx(**_RELANCABLE))
    assert v.note_state("off") is False
    assert v.note_state("on") is True and not v.relaunching


def test_voix_relance_annulee_par_off_ou_par_stop():
    v = VoiceMove()
    assert v.note_route_cmd("off") is False               # rien à annuler
    v.decide("go", 0.0, **_ctx(**_RELANCABLE))
    assert v.note_route_cmd("on") is False and v.relaunching
    assert v.note_route_cmd("off") is True and v.relaunch_due(0.5) == (False, False)
    w = VoiceMove()
    w.decide("go", 0.0, **_ctx(**_RELANCABLE))
    w.decide("stop", 0.3, **_ctx(route_on=False))
    assert not w.relaunching and w.relaunch_due(0.5) == (False, False)


@pytest.mark.parametrize("raw,attendu", [
    ("on", "on"), ('"on"', "on"), ("true", "on"), ("1", "on"), ('"1"', "on"),
    ("off", "off"), ('"off"', "off"), ("false", "off"), ("0", "off"), ('"0"', "off"),
    ("restart", None), ("OFF", None), (" off ", None), ("2", None), ("", None)])
def test_route_cmd_kind_memes_formats_que_route_driver(raw, attendu):
    assert route_cmd_kind(raw) == attendu


def test_reenable_relance_vocale_seulement_sur_off_latche_par_boot():
    p = ReenablePolicy()
    assert p.voice_relaunch_refusal() == "cause_inconnue"            # rien reçu : refus
    p.note_state("off", 0.0)
    assert p.voice_relaunch_refusal() == "cause_inconnue"            # état sans cause : refus
    p.note_cause("boot")
    assert p.voice_relaunch_refusal() is None and p.voice_may_relaunch()   # démarrage / respawn
    p.note_cause("n'importe quoi")                                   # ignorée : la dernière tient
    assert p.cause == "boot"
    p.note_state("on", 1.0)
    assert p.voice_relaunch_refusal() == "etat_inconnu"              # pas OFF au latch
    p.note_cause("cmd"); p.note_state("off", 2.0)                    # David coupe (n'importe quel format)
    assert p.voice_relaunch_refusal() == "route_off_par_david"


def test_reenable_ceinture_off_vu_sur_route_tient_apres_un_reboot():
    p = ReenablePolicy()
    p.note_route_cmd("on"); p.note_cause("boot"); p.note_state("on", 0.0)
    p.note_route_cmd("off")                                          # off VU, cause pas (encore) reçue
    assert (p.off_by_cmd, p.voice_relaunch_refusal()) == (True, "route_off_par_david")
    p.note_cause("boot"); p.note_state("off", 9.0)                   # reboot : la cause redit « boot »…
    assert p.voice_relaunch_refusal() == "route_off_par_david"       # …la ceinture tient
    p.note_route_cmd("on")                                           # seul un « on » efface
    assert p.off_by_cmd is False
    p.note_state("off", 12.0)                                        # respawn après kill
    assert p.voice_relaunch_refusal() is None
