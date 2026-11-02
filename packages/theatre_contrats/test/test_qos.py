"""Profils QoS, testés sans ROS : un faux module rclpy.qos capte les arguments."""
import sys
import types

import pytest

from theatre_contrats import qos


@pytest.fixture
def faux_rclpy(monkeypatch):
    mod_qos = types.ModuleType("rclpy.qos")

    class QoSProfile:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class DurabilityPolicy:
        TRANSIENT_LOCAL = "TRANSIENT_LOCAL"

    mod_qos.QoSProfile = QoSProfile
    mod_qos.DurabilityPolicy = DurabilityPolicy
    monkeypatch.setitem(sys.modules, "rclpy", types.ModuleType("rclpy"))
    monkeypatch.setitem(sys.modules, "rclpy.qos", mod_qos)


def test_import_sans_ros():
    # Le module s'est importé ci-dessus sans rclpy installé (hôte de dev).
    assert callable(qos.volatile) and callable(qos.latched)


def test_latched(faux_rclpy):
    assert qos.latched().kwargs == {"depth": 1, "durability": "TRANSIENT_LOCAL"}


def test_volatile(faux_rclpy):
    assert qos.volatile().kwargs == {"depth": 10}
    assert qos.volatile(1).kwargs == {"depth": 1}
