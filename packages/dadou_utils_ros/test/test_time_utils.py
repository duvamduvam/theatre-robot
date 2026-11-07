"""Tests de TimeUtils (base de tous les timings d'animation et du deadman)."""

from dadou_utils_ros.utils.time_utils import TimeUtils


def test_is_time_strictly_after_timeout(monkeypatch):
    monkeypatch.setattr(TimeUtils, "current_milli_time", staticmethod(lambda: 1000))

    assert TimeUtils.is_time(last_time=500, time_out=400) is True    # 500 écoulées > 400
    assert TimeUtils.is_time(last_time=600, time_out=400) is False   # exactement 400 : pas encore
    assert TimeUtils.is_time(last_time=900, time_out=400) is False


def test_get_milli_time():
    assert TimeUtils.get_milli_time(2) == 2000
    assert TimeUtils.get_milli_time(0) == 0


def test_current_milli_time_is_monotonic_enough():
    a = TimeUtils.current_milli_time()
    b = TimeUtils.current_milli_time()
    assert isinstance(a, int) and b >= a
