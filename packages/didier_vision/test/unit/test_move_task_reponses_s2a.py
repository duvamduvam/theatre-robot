"""Lot S2a (27/11) — la bouche ACTUELLE tolère les nouvelles réponses du sélecteur, sans changer
de comportement (spec-S2 §3 ; c'est le lot S2b qui s'en servira).

Depuis S2a, le sélecteur (source « jeu ») répond à TOUTE demande de David : « accepted » pour un
go, un stop, une pause et un geste transmis (cette réponse part AVANT la transmission du geste,
donc avant le verdict du régisseur), « dropped » + raison sinon — dont le nouveau code
« corps_sur » et le champ « verrou » d'un refus « arrete ». MoveTask n'est PAS modifié : ces
tests gravent qu'il reste sur ses rails.
"""
from didier_vision.ai.move_task import MoveTask

T0 = 100.0
ELEPHANT = {"cmd": "tour_de", "objet": "elephant", "sens": "gauche", "origine": "david"}
DEMANDE = "fais le tour de l'éléphant"
CONTINUATION = (
    "Ton geste « tour de elephant » est terminé (9.4 m parcourus). Ta tâche, demandée par David : "
    "« fais le tour de l'éléphant ». Si elle n'est pas finie, dis où tu en es en quelques mots et fais "
    "le geste suivant ; si elle est finie, dis-le en une phrase, SANS clé de geste.")


def _jeu(demande, effect, reason=None, **extra):
    return dict({"demande": demande, "effect": effect, "reason": reason, "source": "jeu"}, **extra)


def _regisseur_accepte(demande=ELEPHANT):
    return {"demande": demande, "effect": "accepted", "reason": None, "name": "tour de elephant",
            "source": "director"}


def _arrivee():
    return {"name": "tour de elephant", "result": "arrived", "reason": "arrived", "travelled": 9.4}


def test_accepted_du_jeu_puis_verdict_du_regisseur_la_tache_continue_comme_avant():
    task = MoveTask()
    task.gesture_emitted(DEMANDE, False, T0, gesture=dict(ELEPHANT))
    assert task.on_reply(_jeu(ELEPHANT, "accepted"), T0 + 0.01) is None
    assert task.on_reply(_regisseur_accepte(), T0 + 0.02) is None      # le `name` vient du régisseur
    assert task.on_result(_arrivee(), T0 + 30.0) == CONTINUATION


def test_accepted_du_jeu_arrive_avant_la_notation_du_geste():
    """La bouche publie puis note son geste : la réponse du jeu peut la devancer (gardée 2 s)."""
    task = MoveTask()
    assert task.on_reply(_jeu(ELEPHANT, "accepted"), T0) is None
    task.gesture_emitted(DEMANDE, False, T0 + 0.01, gesture=dict(ELEPHANT))
    assert task.on_reply(_regisseur_accepte(), T0 + 0.02) is None
    assert task.on_result(_arrivee(), T0 + 30.0) == CONTINUATION


def test_regisseur_muet_apres_l_accepted_du_jeu_le_no_reply_du_jeu_dit_encore_l_echec():
    task = MoveTask()
    task.gesture_emitted(DEMANDE, False, T0, gesture=dict(ELEPHANT))
    task.on_reply(_jeu(ELEPHANT, "accepted"), T0 + 0.01)
    texte = task.on_reply(_jeu(ELEPHANT, "no_reply"), T0 + 3.1)
    assert texte.startswith("Ton geste « faire le tour de elephant » n'a PAS eu lieu : personne n'a donné suite. "
                            "Tu n'as pas bougé.")


def test_reponses_a_go_stop_pause_sans_effet_sur_la_tache():
    task = MoveTask()
    task.gesture_emitted(DEMANDE, False, T0, gesture=dict(ELEPHANT))
    for demande in ("stop", {"cmd": "go", "origine": "david"}, {"cmd": "pause", "origine": "david"}):
        assert task.on_reply(_jeu(demande, "accepted"), T0 + 0.5) is None
        assert task.on_reply(_jeu(demande, "dropped", "arrete", verrou="console"), T0 + 0.6) is None
    assert task.pop_continuation() is None and task.is_open()
    task.on_reply(_regisseur_accepte(), T0 + 0.7)
    assert task.on_result(_arrivee(), T0 + 30.0) == CONTINUATION


def test_refus_corps_sur_et_arrete_avec_verrou_restent_des_echecs():
    """« corps_sur » n'a pas (encore) de texte : défaut SÛR, un échec — Didier ne prétend jamais
    le geste ; « verrou » est un champ en plus, ignoré."""
    for reponse, raison in ((_jeu(ELEPHANT, "dropped", "corps_sur"), "le geste n'a pas pu se faire"),
                            (_jeu(ELEPHANT, "dropped", "arrete", verrou="voix"),
                             "tu es arrêté jusqu'à ce qu'on te dise de repartir")):
        task = MoveTask()
        task.gesture_emitted(DEMANDE, False, T0, gesture=dict(ELEPHANT))
        assert task.on_reply(reponse, T0 + 0.1).startswith(
            f"Ton geste « faire le tour de elephant » n'a PAS eu lieu : {raison}. Tu n'as pas bougé.")
