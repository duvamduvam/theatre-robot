"""Tests de vision/ai/move_task.py (lot M4, 01/11, dadou_robot_ros/docs/
spec-aller-voir.md §9.1) — tâche en cours : ouverture, continuation, budget
8 gestes / 180 s, goto_suivant ignoré, défaut SÛR des raisons inconnues.
Horloge injectée (`now`) : tout se joue à la seconde près, sans ROS. Les
textes de continuation sont GRAVÉS en dur (jamais recalculés avec la
fonction testée)."""
import pytest

from vision.ai import move_task as move_task_module
from vision.ai.move_task import MoveTask

DEMANDE = "fais le tour de la place"
T0 = 100.0


def _arrive(name="tour de poubelle_tri", travelled=12.57):
    return {"name": name, "result": "arrived", "reason": "arrived", "travelled": travelled}


def _abort(reason, name="avancer 3 m", travelled=0.4):
    return {"name": name, "result": "aborted", "reason": reason, "travelled": travelled}


def _tache_ouverte(now=T0):
    task = MoveTask()
    task.gesture_emitted(DEMANDE, False, now)
    return task


def test_budget_grave():
    assert move_task_module.TASK_MAX_STEPS == 8
    assert move_task_module.TASK_MAX_S == 180.0


# --- Ouverture / continuation ------------------------------------------------

def test_sans_tache_aucune_continuation():
    task = MoveTask()
    assert task.on_result(_arrive(), T0) is None
    assert task.pop_continuation() is None
    assert task.steps == 0


def test_tour_humain_ouvre_une_tache_et_l_arrivee_rend_la_continuation():
    task = _tache_ouverte()
    assert task.is_open() and task.steps == 1
    texte = task.on_result(_arrive(), T0 + 30)
    assert texte == (
        "Ton geste « tour de poubelle_tri » est terminé (12.57 m parcourus). "
        "Ta tâche, demandée par David : « fais le tour de la place ». Si elle n'est pas "
        "finie, dis où tu en es en quelques mots et fais le geste suivant ; si elle est "
        "finie, dis-le en une phrase, SANS clé de geste.")
    # Rangée dans l'emplacement, consommée une seule fois.
    assert task.pop_continuation() == texte
    assert task.pop_continuation() is None


def test_distance_entiere_et_illisible():
    task = _tache_ouverte()
    assert task.on_result(_arrive(travelled=3.0), T0).startswith(
        "Ton geste « tour de poubelle_tri » est terminé (3 m parcourus). ")
    task.gesture_emitted("", True, T0)
    assert task.on_result(_arrive(travelled=None), T0).startswith(
        "Ton geste « tour de poubelle_tri » est terminé (? m parcourus). ")


@pytest.mark.parametrize("reason, clair", [
    ("timeout", "trop long"),
    ("stalled", "bloqué"),
    ("off_track", "sorti de sa trajectoire"),
    ("max_travel", "trop de chemin parcouru"),
    ("too_far", "trop loin"),
])
def test_interruption_par_une_borne_poursuit_avec_la_raison_en_clair(reason, clair):
    task = _tache_ouverte()
    assert task.on_result(_abort(reason), T0 + 1) == (
        f"Ton geste « avancer 3 m » s'est interrompu ({clair}). "
        "Ta tâche, demandée par David : « fais le tour de la place ». Si elle n'est pas "
        "finie, dis où tu en es en quelques mots et fais le geste suivant ; si elle est "
        "finie, dis-le en une phrase, SANS clé de geste.")
    assert task.is_open()


def test_continuation_compte_les_gestes_de_la_meme_tache():
    task = _tache_ouverte()
    task.on_result(_arrive(), T0 + 1)
    task.gesture_emitted("texte ignoré en continuation", True, T0 + 2)
    assert task.steps == 2
    # La demande d'origine reste celle de David.
    assert "« fais le tour de la place »" in task.on_result(_arrive(), T0 + 3)


def test_nouveau_tour_humain_remplace_la_tache():
    task = _tache_ouverte()
    task.on_result(_arrive(), T0 + 1)
    task.gesture_emitted("va voir les anneaux", False, T0 + 2)
    assert task.steps == 1
    assert task.pop_continuation() is None     # l'ancienne continuation tombe
    assert "« va voir les anneaux »" in task.on_result(_arrive(), T0 + 3)


def test_continuation_sans_tache_ne_rouvre_rien():
    task = MoveTask()
    task.gesture_emitted("", True, T0)
    assert not task.is_open()
    assert task.on_result(_arrive(), T0) is None


def test_issue_sans_geste_en_vol_ignoree():
    # Continuation déjà rendue, aucun nouveau geste : une seconde issue
    # (doublon, geste d'avant) ne relance rien.
    task = _tache_ouverte()
    assert task.on_result(_arrive(), T0 + 1) is not None
    task.pop_continuation()
    assert task.on_result(_arrive(), T0 + 2) is None
    assert task.is_open()


# --- goto_suivant ---------------------------------------------------------------

def test_goto_suivant_ignore_la_tache_attend_le_sien():
    task = _tache_ouverte()
    assert task.on_result(_abort("goto_suivant"), T0 + 1) is None
    assert task.is_open()
    assert task.pop_continuation() is None
    # L'issue du NOUVEL ordre arrive ensuite : continuation.
    assert task.on_result(_arrive(), T0 + 2) is not None


# --- Défaut SÛR -------------------------------------------------------------------

@pytest.mark.parametrize("payload", [
    _abort("cancel"), _abort("cancelled"), _abort("stop"), _abort("on"), _abort("off"),
    _abort("raison_inventee_demain"), _abort(None),
    {"name": "x", "result": "aborted"},
    "pas un dict", None, ["arrived"],
])
def test_raison_inconnue_ferme_la_tache(payload):
    task = _tache_ouverte()
    assert task.on_result(payload, T0 + 1) is None
    assert not task.is_open()
    assert task.on_result(_arrive(), T0 + 2) is None


# --- Budget ---------------------------------------------------------------------

def test_budget_huit_gestes():
    task = _tache_ouverte()
    for step in range(2, 9):
        assert task.on_result(_arrive(), T0 + step) is not None
        task.gesture_emitted("", True, T0 + step)
    assert task.steps == 8
    # Issue du 8e geste : budget épuisé, tâche close, rien à dire.
    assert task.on_result(_arrive(), T0 + 9) is None
    assert not task.is_open()


def test_septieme_geste_encore_dans_le_budget():
    task = _tache_ouverte()
    for step in range(2, 8):
        task.on_result(_arrive(), T0 + step)
        task.gesture_emitted("", True, T0 + step)
    assert task.steps == 7
    assert task.on_result(_arrive(), T0 + 8) is not None


def test_budget_180_s():
    task = _tache_ouverte()
    assert task.on_result(_arrive(), T0 + 179.9) is not None
    task.gesture_emitted("", True, T0 + 179.9)
    assert task.on_result(_arrive(), T0 + 180.0) is None
    assert not task.is_open()


# --- close ----------------------------------------------------------------------

def test_close_vide_l_emplacement_et_journalise(caplog):
    task = _tache_ouverte()
    task.on_result(_arrive(), T0 + 1)
    with caplog.at_level("INFO", logger="vision.ai.move_task"):
        assert task.close("stop") is True
    assert task.pop_continuation() is None
    assert task.steps == 0
    assert any("Tâche close (stop)" in r.message for r in caplog.records)


def test_close_sans_tache_silencieux(caplog):
    with caplog.at_level("INFO", logger="vision.ai.move_task"):
        assert MoveTask().close("stop") is False
    assert caplog.records == []
