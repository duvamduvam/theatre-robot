"""Tests du deadman logiciel cmd_vel (robot_drive.deadman).

Horloge passée en paramètre : pas besoin de monkeypatcher le temps réel.
"""

from robot_drive.deadman import TwistDeadman


def test_never_fed_is_expired():
    deadman = TwistDeadman(timeout_ms=400)
    assert deadman.is_expired(0) is True
    assert deadman.is_expired(10_000) is True


def test_fed_not_expired_before_timeout():
    deadman = TwistDeadman(timeout_ms=400)
    deadman.feed(1000)
    assert deadman.is_expired(1399) is False
    assert deadman.is_expired(1400) is False


def test_expired_after_timeout():
    deadman = TwistDeadman(timeout_ms=400)
    deadman.feed(1000)
    assert deadman.is_expired(1401) is True


def test_re_feed_rearms():
    deadman = TwistDeadman(timeout_ms=400)
    deadman.feed(1000)
    assert deadman.is_expired(1401) is True
    deadman.feed(1401)
    assert deadman.is_expired(1500) is False
