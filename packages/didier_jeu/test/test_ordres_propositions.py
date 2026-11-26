"""Lot S1 (25/11) — ordres et propositions, une seule reprise (docs/spec-S1-ordres-propositions.md
§5, tests 1 à 4 et 9 ; les tests 5-6 sont dans didier_vision, 7-8 dans didier_core).

Valeurs et instants GRAVÉS : ticks de 0,1 s, réglages réels (reprise [10, 40] s), graine des
tests conftest.GRAINE = 3 -> première durée tirée 17,1 s, deuxième 26,3 s.

Mutations faites à la livraison (doivent rougir) :
  - un « stop » d'origine « didier » qui pose le verrou      -> test_1_*, test_2_*
  - la parole qui ne remet plus le silence à zéro          -> test_2_une_parole_remet_le_silence_a_zero
  - la fatigue rendue aux ordres (_refus_deplacement)       -> test_4_*
"""
from conftest import fabriquer

from test_reponse_bouche import AV_ELEPHANT, bouche, jouer_regisseur, regisseur_2121, reponses
from test_selecteur import journal, jouer, marche, moves

# La marche telle que le sélecteur la publie sur jeu/chat_move (contrat lot S1), écrite EN DUR.
STOP_DAVID = {"cmd": "stop", "origine": "david"}
STOP_DIDIER = {"cmd": "stop", "origine": "didier"}
GO_DAVID = {"cmd": "go", "origine": "david"}
GO_DIDIER = {"cmd": "go", "origine": "didier"}
AV_ELEPHANT_DAVID = dict(AV_ELEPHANT, origine="david")


def marches(out):
    return [(t, m) for t, m in moves(out) if not isinstance(m, dict) or m.get("cmd") in ("stop", "go")]


# ---------------------------------------------------------------- 1. un ordre de David n'est jamais annulé
def test_1_le_verrou_de_david_ne_tombe_ni_sur_un_stop_ni_sur_un_go_de_didier():
    sel = fabriquer(pools={})
    out = jouer(sel, 0.0, 120.0, [(0.0, marche), (1.0, bouche(STOP_DAVID)), (2.0, bouche(STOP_DIDIER)),
                                  (3.0, bouche(GO_DIDIER))])
    # Le stop de Didier est relayé (un arrêt n'est jamais refusé), le go de Didier jamais.
    assert moves(out) == [(1.0, STOP_DAVID), (2.0, STOP_DIDIER)]
    assert sel.verrou_david is True
    assert journal(out, "reprise_armee") == []                     # rien ne repartira sous son verrou
    assert [p["pourquoi"] for _, p in journal(out, "refus")] == [
        "« go » proposé par Didier : ignoré (seule sa reprise, après le silence, le relance)"]


def test_1_un_stop_de_didier_pendant_un_geste_de_david_arrete_sans_verrou_et_arme_la_reprise():
    """Spec §5.1 (« attention ») : le stop de Didier ARRÊTE quand même le corps — sens sûr, il
    est relayé et le geste engagé tombe — mais ne pose pas de verrou, et la reprise s'arme."""
    sel = fabriquer(pools={})
    out = jouer_regisseur(sel, 25.0, [(0.0, marche), (1.0, bouche(AV_ELEPHANT_DAVID)), (3.0, bouche(STOP_DIDIER))],
                          regisseur_2121)
    # L'ordre de David part À LA RÉCEPTION (sans score) ; le stop de Didier aussi ; puis la reprise.
    assert moves(out) == [(1.0, AV_ELEPHANT_DAVID), (3.0, STOP_DIDIER), (20.1, GO_DIDIER)]
    assert sel.verrou_david is False
    assert [(t, p["pourquoi"]) for t, p in journal(out, "annulation")] == [
        (3.0, "stop de Didier → il arrête de faire ce qu'il a dit (aller voir « elephant »)")]


# ---------------------------------------------------------------- 2. ce que Didier arrête, il le relance
def test_2_stop_de_didier_go_seul_apres_le_silence_tire():
    out = jouer(fabriquer(pools={}), 0.0, 60.0, [(0.0, marche), (1.0, bouche(STOP_DIDIER))])
    assert marches(out) == [(1.0, STOP_DIDIER), (18.1, GO_DIDIER)]          # 1,0 + 17,1 s
    assert [(t, p["pourquoi"]) for t, p in journal(out, "reprise_armee")] == [
        (1.0, "il s'est arrêté de lui-même → il repartira après 17,1 s de silence")]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "reprise")] == [
        (18.1, "reprise : il repart de lui-même (il s'est arrêté de lui-même, après 17,1 s de silence)")]


def test_2_une_parole_remet_le_silence_a_zero_sans_retirer():
    out = jouer(fabriquer(pools={}), 0.0, 60.0, [(0.0, marche), (1.0, bouche(STOP_DIDIER)),
                                                 (10.0, lambda s, t: s.sur_parole("attends un peu", t))])
    assert marches(out) == [(1.0, STOP_DIDIER), (27.1, GO_DIDIER)]          # 10,0 + 17,1 s, même tirage
    assert len(journal(out, "reprise_armee")) == 1


def test_2_lubie_puis_reprise_au_deuxieme_tirage():
    """Deux arrêts de Didier : chacun tire SA durée (17,1 puis 26,3 s)."""
    out = jouer(fabriquer(pools={}), 0.0, 80.0, [
        (0.0, marche), (1.0, bouche(STOP_DIDIER)),
        (20.0, lambda s, t: s.sur_route_state("on", t)), (21.0, bouche(STOP_DIDIER))])
    assert marches(out) == [(1.0, STOP_DIDIER), (18.1, GO_DIDIER), (21.0, STOP_DIDIER), (47.3, GO_DIDIER)]


# ---------------------------------------------------------------- 3. arrêt de David : jamais de reprise seule
def test_3_stop_de_david_aucune_reprise_jusqu_a_son_go():
    out = jouer(fabriquer(pools={}), 0.0, 200.0, [(0.0, marche), (1.0, bouche(STOP_DAVID)),
                                                  (150.0, lambda s, t: s.sur_console({"cmd": "go"}, t))])
    assert moves(out) == [(1.0, STOP_DAVID), (150.0, GO_DAVID)]


def test_3_stop_de_david_desarme_une_reprise_de_didier():
    out = jouer(fabriquer(pools={}), 0.0, 120.0, [(0.0, marche), (1.0, bouche(STOP_DIDIER)),
                                                  (5.0, lambda s, t: s.sur_console({"cmd": "stop"}, t))])
    assert moves(out) == [(1.0, STOP_DIDIER), (5.0, STOP_DAVID)]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "reprise_annulee")] == [
        (5.0, "stop de David → il ne repartira pas de lui-même")]


# ---------------------------------------------------------------- 4. un ordre n'est jamais refusé pour ses pulsions
def _pulsions_au_maximum(sel, t):
    """Fatigue au plafond (> seuil 0,8), tous les réfractaires « à l'instant », « plus lent »."""
    sel.pulsions.fatigue = 1.0
    sel.pulsions.ennui = 1.0
    for cat in ("deplacement", "arret_didier", "expression", "regarder"):
        sel.derniers[cat] = t
    sel.plus_lent_fin = t + 60.0


def test_4_ordre_de_la_bouche_jamais_refuse_pour_fatigue_trop_tot_pas_retenu():
    av = [dict({"cmd": "avancer", "metres": m}, origine="david") for m in (1.0, 2.0, 3.0)]
    sel = fabriquer(pools={})
    out = jouer(sel, 0.0, 8.0, [(0.0, marche), (1.0, bouche(av[0])), (2.0, bouche(av[1])), (3.0, bouche(av[2]))],
                continu=_pulsions_au_maximum)
    assert moves(out) == [(1.0, av[0]), (2.0, av[1]), (3.0, av[2])]      # chacun À LA RÉCEPTION
    # Aucun refus du sélecteur (le « no_reply » de 6,1 s vient du régisseur absent du banc).
    assert [r["effect"] for _, r in reponses(out)] == ["no_reply"] and journal(out, "refus") == []


def test_4_ordre_de_la_console_jamais_refuse_pour_fatigue_ni_trop_tot():
    sel = fabriquer(pools={})
    out = jouer(sel, 0.0, 4.0, [(0.0, marche),
                                (1.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "banc"}, t))],
                continu=_pulsions_au_maximum)
    # Par le score (hystérésis 0,3 s), mais ni fatigue ni réfractaire ne l'arrêtent.
    assert moves(out) == [(1.3, {"cmd": "aller_voir", "objet": "banc", "id": "carte/banc", "origine": "david"})]
    assert journal(out, "refus") == []


def test_4_la_fatigue_borne_toujours_ses_propres_deplacements():
    from didier_jeu.scores import Candidat
    sel = fabriquer(pools={})
    sel.pulsions.fatigue = 0.81
    assert sel._permis(Candidat("approcher", "p1"), True) is False
    sel.pulsions.fatigue = 0.79
    assert sel._permis(Candidat("approcher", "p1"), True) is True


# ---------------------------------------------------------------- 9. anciennes formes lues « david »
def test_9_anciennes_formes_lues_comme_david():
    from didier_rehearsal.contracts import lire_chat_move
    assert lire_chat_move("stop") == ("stop", "david")
    assert lire_chat_move({"cmd": "go"}) == ("go", "david")
    assert lire_chat_move({"cmd": "pause", "origine": "didier"}) == ("pause", "didier")
    assert lire_chat_move({"cmd": "go", "origine": "lune"}) == ("go", None)
    assert lire_chat_move({"cmd": "avancer", "metres": 1.0}) == ({"cmd": "avancer", "metres": 1.0}, "david")


def test_9_chaine_stop_verrouille_et_chaine_go_le_leve():
    sel = fabriquer(pools={})
    out = jouer(sel, 0.0, 80.0, [(0.0, marche), (1.0, bouche("stop")), (2.0, bouche({"cmd": "stop"})),
                                 (60.0, bouche("go"))])
    assert moves(out) == [(1.0, STOP_DAVID), (2.0, STOP_DAVID), (60.0, GO_DAVID)]
    assert journal(out, "reprise_armee") == []


def test_9_stop_d_origine_inconnue_lu_david_les_autres_refuses():
    sel = fabriquer(pools={})
    out = jouer(sel, 0.0, 3.0, [(0.0, marche), (1.0, bouche({"cmd": "stop", "origine": "lune"})),
                                (2.0, bouche({"cmd": "go", "origine": "lune"}))])
    assert moves(out) == [(1.0, STOP_DAVID)] and sel.verrou_david is True


def test_9_geste_sans_origine_est_un_ordre():
    out = jouer_regisseur(fabriquer(pools={}), 2.0, [(0.0, marche), (1.0, bouche(AV_ELEPHANT))], regisseur_2121)
    assert moves(out) == [(1.0, AV_ELEPHANT)]                      # relayé tel quel (le chat apparie)
    assert [p["pourquoi"] for _, p in journal(out, "ordre")] == ["David : aller voir « elephant » → il y va tout de suite"]
