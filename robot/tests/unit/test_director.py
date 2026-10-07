"""Ordonnanceur du régisseur (robot_rehearsal.director) — valeurs gravées.
Mutation (2026-10-08) : retirer l'exclusion par cible -> test_meme_cible_sautee ;
retirer l'arrêt à duration_s -> test_fin_de_scenario_arrete_tout ; retirer le
re-bornage FAULT_MAX_DURATION_S -> test_duree_rebornee ; cancel() qui laisse la cible
occupée -> test_cancel_libere_la_cible_sans_stop."""
from robot_rehearsal.director import Director
from robot_rehearsal.scenario import Fault, Scenario


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
from robot_rehearsal.director import ReenablePolicy


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
