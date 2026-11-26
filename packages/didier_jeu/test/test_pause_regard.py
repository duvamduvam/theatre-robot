"""« Regarde ça » = s'arrêter, regarder, repartir (lot « texte raccord », séance du 18/11 21:35).

Séance : « il y a une lettre sur le banc, tu pourrais regarder » -> la bouche demandait « aller voir
banc » (20 m, refusé) et le corps continuait sa route pendant que Didier parlait de l'enveloppe.
Désormais la bouche demande une PAUSE (chat_move "pause") : le sélecteur relaie « stop » tout de
suite, sans verrou, puis « go » par LA reprise (lot S1 : silence tiré, 17,1 s avec la graine des
tests ; la parole le remet à zéro — avant S1, 6 s fixes et la parole sans effet). Le stop porte
l'origine de la demande (« david » : c'est David qui a dit « regarde ») ; le go, « didier ».
Valeurs et instants GRAVÉS, ticks de 0,1 s.

Mutations (doivent rougir) :
  - pause jamais armée (pas de reprise)        -> test_pause_en_marche_stop_tout_de_suite_puis_go_au_silence
  - reprise annulée par route_state « on »     -> idem (la pause garde la route « on »)
  - stop de David qui ne désarme pas la pause  -> test_stop_de_david_pendant_la_pause_ne_repart_pas
  - pause qui pose le verrou                   -> test_pause_sans_verrou_un_geste_peut_suivre
  - pause qui relance un Didier déjà arrêté    -> test_pause_deja_arrete_ne_repart_jamais
"""
from conftest import fabriquer

from test_reponse_bouche import AV_ELEPHANT, bouche, jouer_regisseur, regisseur_2121
from test_selecteur import GO_DIDIER, STOP_DAVID, journal, marche, moves

PAUSE_DAVID = {"cmd": "pause", "origine": "david"}


def scene(evenements, t1=40.0):
    return jouer_regisseur(fabriquer(pools={}), t1, [(0.0, marche)] + evenements, regisseur_2121)


def stops_gos(out):
    return [(t, m) for t, m in moves(out) if isinstance(m, dict) and m.get("cmd") in ("stop", "go")]


def test_pause_en_marche_stop_tout_de_suite_puis_go_au_silence():
    out = scene([(2.0, bouche(PAUSE_DAVID))] + [(float(k), lambda s, t: s.sur_parole("il parle", t))
                                               for k in range(3, 9)])
    # Dernière parole à 8 s : go à 8 + 17,1 = 25,1 s (une seule reprise, lot S1).
    assert stops_gos(out) == [(2.0, STOP_DAVID), (25.1, GO_DIDIER)]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "pause_regard")] == [
        (2.0, "« regarde » → il s'arrête et regarde, il repartira seul")]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "reprise")] == [
        (25.1, "reprise : il repart de lui-même (regard terminé, après 17,1 s de silence)")]


def test_pause_sans_verrou_un_geste_peut_suivre():
    sel = fabriquer(pools={})
    marche(sel, 0.0)
    sel.sur_chat_move_bouche("pause", 1.0)
    assert not sel.verrou_david


def test_stop_de_david_pendant_la_pause_ne_repart_pas():
    out = scene([(2.0, bouche("pause")), (4.0, lambda s, t: s.sur_console({"cmd": "stop"}, t))])
    assert stops_gos(out) == [(2.0, STOP_DAVID), (4.0, STOP_DAVID)]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "reprise_annulee")] == [
        (4.0, "stop de David → il ne repartira pas de lui-même")]


def test_route_off_par_david_pendant_la_pause_ne_repart_pas():
    out = scene([(2.0, bouche("pause")), (3.0, lambda s, t: s.sur_route_cause("cmd", t))])
    assert stops_gos(out) == [(2.0, STOP_DAVID)]


def test_pause_deja_arrete_ne_repart_jamais():
    out = scene([(1.0, bouche("stop")), (2.0, bouche("pause"))])
    assert stops_gos(out) == [(1.0, STOP_DAVID)]
    assert [p["pourquoi"] for _, p in journal(out, "pause_regard")] == [
        "« regarde » : il est déjà arrêté → il regarde sans repartir de lui-même"]


def test_pause_hors_route_regarde_sur_place():
    out = jouer_regisseur(fabriquer(pools={}), 10.0, [(1.0, bouche("pause"))], regisseur_2121)
    assert stops_gos(out) == []
    assert [p["pourquoi"] for _, p in journal(out, "pause_regard")] == [
        "« regarde » : il n'est pas en route (inconnu) → il regarde sur place"]


def test_pause_pendant_un_aller_voir_l_annule_puis_rejoint_la_route():
    # aller_voir parti à 1,0 s (un ordre, lot S1), « regarde » à 3 s : l'aller_voir est annulé
    # (le stop du régisseur annule aussi sa manœuvre), puis « go » à 3 + 17,1 = 20,1 s.
    out = scene([(1.0, bouche(AV_ELEPHANT)), (3.0, bouche("pause"))])
    assert [(t, m) for t, m in moves(out)] == [(1.0, AV_ELEPHANT), (3.0, STOP_DAVID), (20.1, GO_DIDIER)]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "annulation")] == [
        (3.0, "« regarde » : il s'arrête pour regarder → il arrête de faire ce qu'il a dit "
              "(aller voir « elephant »)")]


def test_mode_degrade_la_pause_est_un_stop():
    from didier_jeu.relais import RelaisSeul
    r = RelaisSeul("test")
    r.vider_sorties()
    r.sur_chat_move_bouche("pause", 1.0)
    assert [s for s in r.vider_sorties() if s[0] == "chat_move"] == [("chat_move", STOP_DAVID)]
    assert r.verrou_david
