"""Tests d'AnimationManager : temps restant (base du deadman roues) et chargement réel.

Le test de chargement construit le manager avec la vraie config et le vrai
dossier json/sequences/ : il garantit que toutes les séquences du dépôt
restent chargeables par le robot.
"""

import pytest

from dadou_utils_ros.utils.time_utils import TimeUtils
from dadou_utils_ros.utils_static import ANIMATION, DURATION
from robot.robot_config import config
from robot.sequences.animation_manager import AnimationManager

T0 = 1_000_000


@pytest.fixture
def clock(monkeypatch):
    state = {"now": T0}
    monkeypatch.setattr(TimeUtils, "current_milli_time", staticmethod(lambda: state["now"]))
    return state


@pytest.fixture
def bare_manager():
    manager = object.__new__(AnimationManager)
    manager.playing = False
    manager.duration = 0
    manager.last_time = 0
    return manager


def test_remaining_ms_zero_when_not_playing(bare_manager, clock):
    assert bare_manager.remaining_ms() == 0


def test_remaining_ms_counts_down(bare_manager, clock):
    bare_manager.playing = True
    bare_manager.duration = 30000
    bare_manager.last_time = T0

    assert bare_manager.remaining_ms() == 30000
    clock["now"] = T0 + 10000
    assert bare_manager.remaining_ms() == 20000
    clock["now"] = T0 + 40000
    assert bare_manager.remaining_ms() == 0    # jamais négatif


def test_stop_returns_animation_false(bare_manager):
    bare_manager.playing = True
    assert bare_manager.stop() == {ANIMATION: False}
    assert bare_manager.playing is False


@pytest.fixture(scope="module")
def real_manager():
    from robot.files.robot_json_manager import RobotJsonManager
    return AnimationManager(config, RobotJsonManager(config))


def test_all_repo_sequences_load(real_manager):
    assert len(real_manager.sequences_name) >= 40
    assert "moon-walk" in real_manager.sequences_name


def test_start_animation_sets_duration_and_remaining(real_manager, clock):
    real_manager.update({ANIMATION: "moon-walk"})

    assert real_manager.playing is True
    assert real_manager.duration == real_manager.sequences_name["moon-walk"][DURATION]
    clock["now"] = T0 + 5000
    assert real_manager.remaining_ms() == real_manager.duration - 5000
    real_manager.stop()


class TestStateName:
    """state_name() : source de vérité du topic animation_state (lot B de
    l'arbitrage actionneurs, docs/etude-arbitrage-actionneurs.md) — gaze/chat
    s'y abonnent pour savoir si une séquence a la main sur visage/tête.
    """

    def test_repos_donne_chaine_vide(self, real_manager):
        # Repos garanti par le stop() de fin de test précédent, mais on ne
        # suppose pas l'ordre : on stoppe explicitement d'abord.
        real_manager.stop()
        assert real_manager.state_name() == ""

    def test_animation_en_cours_donne_son_nom(self, real_manager, clock):
        real_manager.update({ANIMATION: "moon-walk"})
        assert real_manager.state_name() == "moon-walk"
        real_manager.stop()

    def test_stop_repasse_a_vide(self, real_manager, clock):
        real_manager.update({ANIMATION: "moon-walk"})
        real_manager.stop()
        assert real_manager.state_name() == ""

    def test_expiration_de_duree_repasse_a_vide(self, real_manager, clock):
        # process() au-delà de la durée déclenche le stop() interne (comme le
        # deadman roues) : state_name() doit suivre sans appel explicite à stop().
        real_manager.update({ANIMATION: "moon-walk"})
        duration = real_manager.duration
        clock["now"] = T0 + duration + 1000
        real_manager.process()
        assert real_manager.state_name() == ""
