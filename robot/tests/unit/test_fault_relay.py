"""Relais de pannes (robot_rehearsal.fault_relay) — valeurs gravées, graine 0.
Mutation (2026-10-08) : inverser la condition de drop -> test_drop ; retirer le
chien de garde -> test_watchdog_retombe_en_passant ; retirer l'échéance ->
test_expiration ; mettre à jour _last_msg pendant freeze -> test_freeze."""
from robot_rehearsal.contracts import HEARTBEAT_TIMEOUT_MS
from robot_rehearsal.fault_relay import DELAY_QUEUE_MAX, ZERO, FaultRelay


def _relay(op=None, params=None, until=10_000):
    r = FaultRelay("cmd_vel_follow", seed=0)
    r.heartbeat(0)
    if op:
        r.set_op(op, params, 0, until)
    return r


def test_passant_par_defaut():
    r = _relay()
    assert r.op == "pass" and r.process("m1", 10) == ["m1"]


def test_drop():
    assert _relay("drop", {"p": 1.0}).process("m", 10) == []
    assert _relay("drop", {"p": 0.0}).process("m", 10) == ["m"]
    # p = 0,5, graine 0 : tirages random.Random(0).random() = 0.844, 0.758, 0.421, 0.259, 0.511
    r = _relay("drop", {"p": 0.5})
    assert [r.process(i, 10 + i) for i in range(5)] == [[0], [1], [], [], [4]]


def test_delay_horodatages():
    r = _relay("delay", {"delay_ms": 300})
    assert r.process("a", 100) == []
    assert r.process("b", 200) == []
    assert r.tick(399) == []
    assert r.tick(400) == ["a"]
    assert r.process("c", 500) == ["b"]
    assert r.tick(800) == ["c"]


def test_delay_file_bornee():
    r = _relay("delay", {"delay_ms": 100_000})
    for i in range(DELAY_QUEUE_MAX + 50):
        r.process(i, 1)
    assert len(r._queue) == DELAY_QUEUE_MAX


def test_freeze():
    r = _relay()
    r.process("avant", 10)
    r.set_op("freeze", {}, 20, 10_000)
    assert r.process("pendant1", 30) == ["avant"]
    assert r.process("pendant2", 40) == ["avant"]
    r.set_op("pass", {}, 50, None)
    assert r.process("apres", 60) == ["apres"]


def test_freeze_sans_historique_laisse_passer_le_premier():
    assert _relay("freeze").process("m", 10) == ["m"]


def test_zero():
    assert _relay("zero").process("m", 10) == [ZERO]


def test_expiration():
    r = _relay("zero", until=500)
    assert r.process("m", 499) == [ZERO]
    assert r.process("m", 500) == ["m"] and r.op == "pass"


def test_watchdog_retombe_en_passant():
    r = _relay("zero", until=100_000)
    r.heartbeat(100)
    assert r.process("m", 100 + HEARTBEAT_TIMEOUT_MS) == [ZERO]
    assert r.process("m", 101 + HEARTBEAT_TIMEOUT_MS) == ["m"] and r.op == "pass"
    # et sans AUCUN battement jamais reçu : passant d'office
    s = FaultRelay("x")
    s.set_op("zero", {}, 0, 10_000)
    assert s.process("m", 1) == ["m"]


def test_operation_inconnue_refusee():
    import pytest
    with pytest.raises(ValueError):
        _relay().set_op("explose", {}, 0, 10)
