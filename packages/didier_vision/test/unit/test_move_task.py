"""Tests de didier_vision/ai/move_task.py (lot M4, 01/11, dadou_robot_ros/docs/
spec-aller-voir.md §9.1) — tâche en cours : ouverture, continuation, budget
8 gestes / 180 s, goto_suivant ignoré, défaut SÛR des raisons inconnues.
Horloge injectée (`now`) : tout se joue à la seconde près, sans ROS. Les
textes de continuation sont GRAVÉS en dur (jamais recalculés avec la
fonction testée)."""
import pytest

from didier_vision.ai import move_task as move_task_module
from didier_vision.ai.move_task import MoveTask

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
    with caplog.at_level("INFO", logger="didier_vision.ai.move_task"):
        assert task.close("stop") is True
    assert task.pop_continuation() is None
    assert task.steps == 0
    assert any("Tâche close (stop)" in r.message for r in caplog.records)


def test_close_sans_tache_silencieux(caplog):
    with caplog.at_level("INFO", logger="didier_vision.ai.move_task"):
        assert MoveTask().close("stop") is False
    assert caplog.records == []


# --- Geste refusé ou sans réponse (15/11, séance « fais le tour de l'éléphant ») ---
# Le régisseur refusait (no_tour) ou le sélecteur ne transmettait pas : la tâche
# restait ouverte et Didier affirmait le tour. Textes GRAVÉS en dur.

ELEPHANT = {"cmd": "tour_de", "objet": "elephant", "sens": "gauche"}
DEMANDE_ELEPHANT = "fais le tour de l'éléphant"
ECHEC_NO_TOUR = (
    "Ton geste « faire le tour de elephant » n'a PAS eu lieu : impossible d'en faire le tour, il n'y a "
    "pas la place tout autour (eau, mur ou obstacle). Tu n'as pas bougé. Ta tâche, demandée par David : "
    "« fais le tour de l'éléphant ». Dis-le en personnage, en une phrase : ne prétends JAMAIS l'avoir "
    "fait. Ne redemande pas ce geste-là ; si un autre geste sert la tâche, fais-le, sinon dis que tu ne "
    "peux pas, SANS clé de geste.")


def _reponse(effect, reason=None, demande=ELEPHANT, source="director"):
    return {"demande": demande, "effect": effect, "reason": reason, "source": source}


def _tache_elephant(now=T0):
    task = MoveTask()
    task.gesture_emitted(DEMANDE_ELEPHANT, False, now, gesture=dict(ELEPHANT))
    return task


def test_refus_no_tour_direction_d_echec_gravee():
    task = _tache_elephant()
    assert task.on_reply(_reponse("no_tour"), T0 + 0.1) == ECHEC_NO_TOUR
    assert task.pop_continuation() == ECHEC_NO_TOUR
    # La tâche CONTINUE honnêtement (un autre geste peut la servir) : ouverte,
    # plus de geste en vol (une 2e réponse ne redit rien).
    assert task.is_open() and task.steps == 1
    assert task.on_reply(_reponse("no_tour"), T0 + 0.2) is None


def test_acceptation_puis_arrivee_inchangee():
    task = _tache_elephant()
    acceptee = dict(_reponse("accepted"), name="tour de elephant")    # nom de l'ORDRE parti
    assert task.on_reply(acceptee, T0 + 0.1) is None
    assert task.check_ack(T0 + 60.0) is None                  # accepté : seule l'issue le finit
    assert task.on_result(_arrive("tour de elephant", 9.4), T0 + 60.0) == (
        "Ton geste « tour de elephant » est terminé (9.4 m parcourus). Ta tâche, demandée par David : "
        "« fais le tour de l'éléphant ». Si elle n'est pas finie, dis où tu en es en quelques mots et fais "
        "le geste suivant ; si elle est finie, dis-le en une phrase, SANS clé de geste.")


@pytest.mark.parametrize("reponse,raison", [
    (_reponse("unknown"), "tu ne connais pas cet objet ici, tu ne le trouves pas"),
    (_reponse("no_position"), "tu ne sais pas exactement où il est"),
    (_reponse("too_far"), "c'est trop loin d'ici"),
    (_reponse("no_pose"), "tu ne sais pas où tu es en ce moment"),
    (_reponse("route_off_by_david"), "David a coupé ta route, tu ne bouges pas sans lui"),
    (_reponse("invalid", "recul"), "tu ne sais pas reculer"),
    (_reponse("invalid", "hors_bornes"), "c'est plus que ce que ton corps sait faire en un geste"),
    (_reponse("invalid", "sens"), "le sens du tour était incompréhensible"),
    (_reponse("invalid", "nouveau"), "ta demande de geste était incompréhensible"),
    (_reponse("dropped", "trop_tot", source="jeu"), "tu viens déjà de te déplacer, pas tout de suite"),
    (_reponse("dropped", "arrete", source="jeu"), "tu es arrêté jusqu'à ce qu'on te dise de repartir"),
    (_reponse("dropped", "fatigue", source="jeu"), "tu es trop fatigué pour te déplacer maintenant"),
    (_reponse("dropped", "degrade", source="jeu"), "ton corps ne répond qu'à « stop » et « go » en ce moment"),
    (_reponse("dropped", "lune", source="jeu"), "le geste n'a pas pu se faire"),
    (_reponse("no_reply", source="jeu"), "personne n'a donné suite"),
    (_reponse("inconnu_demain"), "le geste n'a pas pu se faire"),          # défaut SÛR : un échec
    (_reponse(["hostile"], {"x": 1}), "le geste n'a pas pu se faire"),
])
def test_raisons_en_clair_gravees(reponse, raison):
    texte = _tache_elephant().on_reply(reponse, T0 + 0.1)
    assert texte.startswith(f"Ton geste « faire le tour de elephant » n'a PAS eu lieu : {raison}. "
                            "Tu n'as pas bougé.")


def test_reponse_d_un_autre_geste_ignoree():
    task = _tache_elephant()
    autre = {"cmd": "aller_voir", "objet": "flaque"}            # sélecteur ou console
    assert task.on_reply(_reponse("no_tour", demande=autre), T0 + 0.1) is None
    assert task.on_reply("illisible", T0 + 0.1) is None
    assert task.pop_continuation() is None


def test_sans_reponse_echec_a_8_s_exactement():
    assert move_task_module.ACK_TIMEOUT_S == 8.0
    task = _tache_elephant()
    assert task.check_ack(T0 + 7.9) is None
    texte = task.check_ack(T0 + 8.0)
    assert texte.startswith("Ton geste « faire le tour de elephant » n'a PAS eu lieu : personne n'a "
                            "donné suite. Tu n'as pas bougé.")
    assert task.check_ack(T0 + 20.0) is None                   # dit une seule fois


def test_reponse_arrivee_avant_la_notation_du_geste():
    """Le régisseur répond en quelques ms : la réponse peut devancer
    gesture_emitted (même thread de conversation que la publication)."""
    task = MoveTask()
    assert task.on_reply(_reponse("no_tour"), T0) is None
    task.gesture_emitted(DEMANDE_ELEPHANT, False, T0 + 0.05, gesture=dict(ELEPHANT))
    assert task.pop_continuation() == ECHEC_NO_TOUR


def test_reponse_precoce_perimee_ou_autre_ignoree():
    assert move_task_module.EARLY_REPLY_S == 2.0
    task = MoveTask()
    task.on_reply(_reponse("no_tour"), T0)
    task.gesture_emitted(DEMANDE_ELEPHANT, False, T0 + 2.5, gesture=dict(ELEPHANT))
    assert task.pop_continuation() is None
    task = MoveTask()
    task.on_reply(_reponse("no_tour", demande={"cmd": "avancer", "metres": 1}), T0)
    task.gesture_emitted(DEMANDE_ELEPHANT, False, T0 + 0.1, gesture=dict(ELEPHANT))
    assert task.pop_continuation() is None


def test_refus_budget_epuise_dit_l_echec_et_ferme():
    task = _tache_elephant()
    acceptee = dict(_reponse("accepted"), name="tour de poubelle_tri")
    for k in range(2, move_task_module.TASK_MAX_STEPS + 1):     # gestes 2..8, tous arrivés
        task.on_reply(acceptee, T0 + k)
        assert task.on_result(_arrive(), T0 + k) is not None
        task.pop_continuation()
        task.gesture_emitted(DEMANDE_ELEPHANT, True, T0 + k, gesture=dict(ELEPHANT))
    assert task.steps == 8
    assert task.on_reply(_reponse("no_tour"), T0 + 9.0) == (
        "Ton geste « faire le tour de elephant » n'a PAS eu lieu : impossible d'en faire le tour, il n'y a "
        "pas la place tout autour (eau, mur ou obstacle). Tu n'as pas bougé. Ta tâche, demandée par David : "
        "« fais le tour de l'éléphant », s'arrête là. Dis-le en personnage, en une phrase : ne prétends "
        "JAMAIS l'avoir fait, et SANS clé de geste.")
    assert not task.is_open()
    assert task.pop_continuation() is not None                 # l'échec est QUAND MÊME servi


def test_close_oublie_le_geste_en_vol():
    task = _tache_elephant()
    task.close("stop")
    assert task.on_reply(_reponse("no_tour"), T0 + 0.1) is None
    assert task.check_ack(T0 + 30.0) is None
    assert task.pop_continuation() is None


# --- Séance du 15/11 21:21 : l'arrivée d'un ANCIEN geste n'est jamais la fin du nouveau ---

AV_ELEPHANT = {"cmd": "aller_voir", "objet": "elephant"}
ARRIVEE_ANCIEN = {"name": "elephant", "result": "arrived", "reason": "arrived", "travelled": 3.17}


def test_seance_2121_arrivee_de_l_ancien_aller_voir_jamais_terminee_pour_le_tour():
    """EXACTEMENT la séquence : aller_voir elephant accepté et en route ->
    David demande le tour (tour humain) -> tour_de émis -> l'ancien aller_voir
    arrive (« elephant », 3,17 m) -> le sélecteur répond « pas_retenu ».
    Avant : « Ton geste « elephant » est terminé (3.17 m parcourus) »."""
    task = MoveTask()
    task.gesture_emitted("va voir l'éléphant", False, T0, gesture=dict(AV_ELEPHANT))
    task.on_reply(_reponse("accepted", demande=AV_ELEPHANT) | {"name": "elephant"}, T0 + 0.01)
    task.close("tour humain")                                       # 21:21:16
    task.gesture_emitted(DEMANDE_ELEPHANT, False, T0 + 21.0, gesture=dict(ELEPHANT))   # 21:21:17
    assert task.on_result(ARRIVEE_ANCIEN, T0 + 23.0) is None        # 21:21:19 : pas la sienne
    assert task.pop_continuation() is None
    texte = task.on_reply(_reponse("dropped", "pas_retenu", source="jeu"), T0 + 24.0)   # 21:21:20
    assert texte == (
        "Ton geste « faire le tour de elephant » n'a PAS eu lieu : ton corps ne t'a pas suivi. Tu n'as pas "
        "bougé. Ta tâche, demandée par David : « fais le tour de l'éléphant ». Dis-le en personnage, en une "
        "phrase : ne prétends JAMAIS l'avoir fait. Ne redemande pas ce geste-là ; si un autre geste sert la "
        "tâche, fais-le, sinon dis que tu ne peux pas, SANS clé de geste.")
    assert task.pop_continuation() == texte and "terminé" not in texte


def test_issue_d_un_autre_nom_ignoree_apres_acceptation():
    task = _tache_elephant()
    task.on_reply(dict(_reponse("accepted"), name="tour de elephant"), T0 + 0.1)
    assert task.on_result(ARRIVEE_ANCIEN, T0 + 5.0) is None             # « elephant » ≠ « tour de elephant »
    assert task.on_result(_arrive("tour de elephant", 9.4), T0 + 30.0).startswith(
        "Ton geste « tour de elephant » est terminé (9.4 m parcourus).")


def test_pas_ici_dit_la_distance_et_le_cote():
    # Scène du 15/11 21:29 (lot O1) : « tour du banc » à 22,3 m devant, refusé (tableau des objets).
    banc = {"cmd": "tour_de", "objet": "banc", "sens": "gauche", "id": "carte/banc"}
    task = MoveTask()
    task.gesture_emitted("fais le tour du banc", False, T0, gesture=dict(banc))
    texte = task.on_reply({"demande": banc, "effect": "dropped", "reason": "pas_ici", "distance_m": 22.3,
                           "cote": "devant", "source": "jeu"}, T0 + 0.1)
    assert texte.startswith("Ton geste « faire le tour de banc » n'a PAS eu lieu : il n'est pas ici : il est à "
                            "22 m devant toi, tu ne le vois pas d'où tu es. Tu n'as pas bougé.")
    sans = _tache_elephant().on_reply(_reponse("dropped", "pas_ici", source="jeu"), T0 + 0.1)
    assert sans.startswith("Ton geste « faire le tour de elephant » n'a PAS eu lieu : il n'est pas ici, tu ne le "
                           "vois pas d'où tu es.")


def test_hors_atteinte_dit_la_distance():
    texte = _tache_elephant().on_reply(dict(_reponse("dropped", "hors_atteinte", source="chat"), distance_m=13.2,
                                            cote="devant"), T0 + 0.1)
    assert texte.startswith("Ton geste « faire le tour de elephant » n'a PAS eu lieu : il est trop loin pour y "
                            "aller d'un seul geste (à 13 m devant toi).")
    sans = _tache_elephant().on_reply(dict(_reponse("dropped", "hors_atteinte"), cote="haut"), T0 + 0.1)
    assert "il est trop loin pour y aller d'un seul geste. Tu n'as pas bougé." in sans


# --------------------------------------------------------------------------
# Lot « texte raccord » (séance du 18/11 21:35) : la continuation dit si le geste a ÉCHOUÉ, et
# une réplique sans geste ferme la tâche « échec : geste refusé », jamais « fini ».
# --------------------------------------------------------------------------

AV_BANC = {"cmd": "aller_voir", "objet": "banc"}
REFUS_BANC = {"demande": AV_BANC, "effect": "dropped", "reason": "pas_ici", "distance_m": 22.3,
              "cote": "devant", "source": "chat"}


def test_refus_suite_en_echec_puis_close_echec():
    task = MoveTask()
    task.gesture_emitted("il y a une lettre sur le banc", False, 0.0, gesture=dict(AV_BANC))
    assert task.on_reply(REFUS_BANC, 0.1) is not None
    suite = task.pop_suite()
    assert suite.echec is True and suite.texte.startswith("Ton geste « aller voir banc » n'a PAS eu lieu")
    assert task.pop_suite() is None
    assert task.close_without_gesture() == "échec : geste refusé"
    assert task.last_close == "échec : geste refusé" and not task.is_open()
    assert task.close_without_gesture() is None                 # plus de tâche


def test_arrivee_suite_sans_echec_puis_close_fini():
    task = MoveTask()
    task.gesture_emitted("va voir la table", False, 0.0)
    task.on_result({"name": "table", "result": "arrived", "reason": "arrived", "travelled": 4.0}, 1.0)
    assert task.pop_suite().echec is False
    assert task.close_without_gesture() == "fini"


def test_geste_reussi_apres_un_echec_efface_l_echec():
    # Refus, puis un AUTRE geste de la même tâche, accepté et arrivé : la tâche finit « fini ».
    task = MoveTask()
    task.gesture_emitted("lettre", False, 0.0, gesture=dict(AV_BANC))
    task.on_reply(REFUS_BANC, 0.1)
    task.pop_suite()
    tourner = {"cmd": "tourner", "angle_deg": 10}
    task.gesture_emitted("lettre", True, 1.0, gesture=dict(tourner))
    task.on_reply({"demande": tourner, "effect": "accepted", "name": "tourner 10", "source": "director"}, 1.1)
    task.on_result({"name": "tourner 10", "result": "arrived", "reason": "arrived", "travelled": 0}, 2.0)
    assert task.pop_suite().echec is False
    assert task.close_without_gesture() == "fini"
