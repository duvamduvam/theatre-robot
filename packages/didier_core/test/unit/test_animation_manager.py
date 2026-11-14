"""Tests d'AnimationManager : temps restant (base du deadman roues) et chargement réel.

Le test de chargement construit le manager avec la vraie config et le vrai
dossier json/sequences/ : il garantit que toutes les séquences du dépôt
restent chargeables par le robot.
"""

import pytest

from dadou_utils_ros.utils.time_utils import TimeUtils
from dadou_utils_ros.utils_static import ANIMATION, DURATION
from didier_core.robot_config import config
from didier_core.sequences.animation_manager import AnimationManager

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
    from didier_core.files.robot_json_manager import RobotJsonManager
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


# ================================================================ barrière de jeu roues (L1d-2)
# Décision 7 ter : sur le robot, une piste roues dont l'empreinte {duration, wheels} n'est pas
# validée au registre pour le FICHIER chargé est construite VIDE ; le reste de la séquence joue,
# le refus part sur roues_refusees. Levée en sim seulement (paramètre faux ET domaine 43).
import json as _json
import os as _os

from dadou_utils_ros.utils_static import JSON_DIRECTORY, SEQUENCES_DIRECTORY
from didier_core.sequences.animation_manager import exiger_validation_roues
from theatre_contrats import donnees

ROULE = {"keys": "R7", "duration": 4000, "neck": [[0, 0.3]], "wheels": [[0.1, [0.2, 0.2]], [0.5, [0, 0]]]}


@pytest.mark.parametrize("parametre, environ, attendu", [
    (True, {"ROS_DOMAIN_ID": "43"}, True),
    (False, {"ROS_DOMAIN_ID": "43"}, False),
    (False, {"ROS_DOMAIN_ID": "42"}, True),     # le vrai robot : la barrière tient toujours
    (False, {"ROS_DOMAIN_ID": ""}, True),
    (False, {}, True),
])
def test_exiger_validation_roues(parametre, environ, attendu):
    assert exiger_validation_roues(parametre, environ) is attendu


def _ecrire(chemin, valeur):
    _os.makedirs(_os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        _json.dump(valeur, f)


@pytest.fixture
def barriere(tmp_path):
    json_dir = tmp_path / "json"
    _ecrire(str(json_dir / "sequences" / "essai" / "roule.json"), ROULE)

    def construire(registre=None, exiger=True):
        if registre is not None:
            _ecrire(str(json_dir / "validations-sim.json"), registre)
        m = object.__new__(AnimationManager)
        m.config = dict(config)
        m.config[JSON_DIRECTORY] = str(json_dir) + "/"
        m.config[SEQUENCES_DIRECTORY] = str(json_dir / "sequences") + "/"
        m.action_type = ANIMATION
        m.sequences_key, m.sequences_name = {}, {}
        m.load_multi_files_sequences(m.config[SEQUENCES_DIRECTORY])
        m.playing = False
        m.exiger_validation_roues = exiger
        m.refus_roues = []
        m.relire_registre()
        return m
    return construire, json_dir


def _valide(chemin="essai/roule", sequence=ROULE):
    return {"version": 1, "sequence": {chemin: {"rejeu": "x", "roues": donnees.empreinte_roues(sequence),
                                                "origine_roues": "heritee"}}}


def test_roues_non_validees_piste_vide_reste_joue(barriere, clock):
    construire, _ = barriere
    m = construire()                       # registre absent : rien n'est validé
    m.update({ANIMATION: "roule"})
    assert m.playing is True
    assert m.wheels_animation.has_data is False
    assert m.necks_animation.has_data is True
    assert m.refus_roues == [{"name": "roule", "raison": "non_validee_sim"}]


def test_roues_validees_jouees(barriere, clock):
    construire, _ = barriere
    m = construire(_valide())
    m.update({ANIMATION: "roule"})
    assert m.wheels_animation.has_data is True
    assert m.refus_roues == []


def test_roues_jouees_barriere_levee(barriere, clock):
    construire, _ = barriere
    m = construire(exiger=False)
    m.update({ANIMATION: "roule"})
    assert m.wheels_animation.has_data is True
    assert m.refus_roues == []


def test_homonyme_valide_ailleurs_refuse(barriere, clock):
    construire, _ = barriere
    m = construire(_valide(chemin="autre/roule"))
    m.update({ANIMATION: "roule"})
    assert m.wheels_animation.has_data is False
    assert m.refus_roues == [{"name": "roule", "raison": "non_validee_sim"}]


def test_roues_retouchees_apres_validation_refusees(barriere, clock):
    construire, json_dir = barriere
    m = construire(_valide())
    _ecrire(str(json_dir / "sequences" / "essai" / "roule.json"), {**ROULE, "duration": 3000})
    assert m.recharger_sequence("essai/roule") is True     # relit aussi le registre
    m.update({ANIMATION: "roule"})
    assert m.wheels_animation.has_data is False


def test_validation_relue_au_rechargement(barriere, clock):
    construire, json_dir = barriere
    m = construire()
    _ecrire(str(json_dir / "validations-sim.json"), _valide())
    assert m.recharger_sequence("essai/roule") is True
    m.update({ANIMATION: "roule"})
    assert m.wheels_animation.has_data is True


def test_registre_illisible_aucune_roue(barriere, clock):
    construire, json_dir = barriere
    (json_dir / "validations-sim.json").write_text("{cassé", encoding="utf-8")
    m = construire()
    assert m.registre == donnees.registre_vide()
    m.update({ANIMATION: "roule"})
    assert m.wheels_animation.has_data is False
