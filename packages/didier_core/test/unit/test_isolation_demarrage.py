"""Une panne matérielle au démarrage reste locale à son nœud (incident du 2026-11-04).
Mutation (2026-11-04) : retirer le try de robot_config -> test_config_survit_a_board_casse ;
retirer le try de RelaysManager -> test_relais_sans_pcf8574_desactive_sans_mourir."""
import importlib
import sys
import types
from unittest.mock import MagicMock

import pytest

from dadou_utils_ros.misc import Misc
from didier_core.robot_static import DIGITAL_CHANNELS_ENABLED, I2C_ENABLED, JSON_RELAYS, LIGHTS_PIN, \
    RESTART_PIN, SHUTDOWN_PIN, STATUS_LED_PIN


class _BoardCasse:
    """Chercheur d'import : `import board` lève ce que lève Blinka sans gpiod."""

    def find_spec(self, name, path=None, target=None):
        if name == "board":
            raise RuntimeError("The platform library 'gpiod' was not found.")
        return None


@pytest.fixture
def sur_un_pi(monkeypatch):
    monkeypatch.setattr(Misc, "is_raspberrypi", staticmethod(lambda: True))


def test_config_survit_a_board_casse(monkeypatch, sur_un_pi):
    monkeypatch.delitem(sys.modules, "board", raising=False)
    monkeypatch.setattr(sys, "meta_path", [_BoardCasse()] + sys.meta_path)
    original = sys.modules.pop("didier_core.robot_config", None)
    try:
        config = importlib.import_module("didier_core.robot_config").config
        assert config[SHUTDOWN_PIN] is None
        assert config[RESTART_PIN] is None
        assert config[STATUS_LED_PIN] is None
        assert config[LIGHTS_PIN] is None
    finally:
        sys.modules.pop("didier_core.robot_config", None)
        if original is not None:
            sys.modules["didier_core.robot_config"] = original


def _relais(monkeypatch, pcf8574):
    from didier_core.actions.relays import RelaysManager
    monkeypatch.setitem(sys.modules, "board", MagicMock())
    monkeypatch.setitem(sys.modules, "adafruit_pcf8574", types.SimpleNamespace(PCF8574=pcf8574))
    json_manager = MagicMock()
    json_manager.open_json.return_value = {}
    config = {I2C_ENABLED: True, DIGITAL_CHANNELS_ENABLED: True, JSON_RELAYS: "relays.json"}
    return RelaysManager(config, json_manager)


def test_relais_sans_pcf8574_desactive_sans_mourir(monkeypatch, sur_un_pi):
    pcf = MagicMock(side_effect=ValueError("No I2C device at address: 0x21"))
    relais = _relais(monkeypatch, pcf)
    assert relais.i2c_enabled is False
    assert relais.update({"relay": "klaxon"}) == {"relay": "klaxon"}
    relais.process()


def test_relais_avec_pcf8574_reste_actif(monkeypatch, sur_un_pi):
    relais = _relais(monkeypatch, MagicMock())
    assert relais.i2c_enabled is True
    assert relais.klaxon.value is True
