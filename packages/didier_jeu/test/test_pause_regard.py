"""« Regarde ça » = s'arrêter, regarder, repartir (lot « texte raccord », séance du 18/11 21:35).

Séance : « il y a une lettre sur le banc, tu pourrais regarder » -> la bouche demandait « aller voir
banc » (20 m, refusé) et le corps continuait sa route pendant que Didier parlait de l'enveloppe.
Désormais la bouche demande une PAUSE (chat_move "pause") : le sélecteur relaie « stop » tout de
suite, sans verrou, puis « go » après reprise.apres_regard_s = 6 s (valeurs et instants GRAVÉS,
ticks de 0,1 s).

Mutations (doivent rougir) :
  - pause jamais armée (pas de reprise)        -> test_pause_en_marche_stop_tout_de_suite_puis_go_a_6_s
  - délai de la pause = apres_geste_s (10 s)   -> idem (go à 6 s, pas à 10)
  - reprise annulée par route_state « on »     -> idem (la pause garde la route « on »)
  - stop de David qui ne désarme pas la pause  -> test_stop_de_david_pendant_la_pause_ne_repart_pas
  - pause qui pose le verrou                   -> test_pause_sans_verrou_un_geste_peut_suivre
  - pause qui relance un Didier déjà arrêté    -> test_pause_deja_arrete_ne_repart_jamais
"""
from conftest import fabriquer

from test_reponse_bouche import AV_ELEPHANT, bouche, jouer_regisseur, regisseur_2121
from test_selecteur import journal, marche, moves


def scene(evenements, t1=20.0):
    return jouer_regisseur(fabriquer(pools={}), t1, [(0.0, marche)] + evenements, regisseur_2121)


def stops_gos(out):
    return [(t, m) for t, m in moves(out) if m in ("stop", "go")]


def test_pause_en_marche_stop_tout_de_suite_puis_go_a_6_s():
    out = scene([(2.0, bouche("pause"))] + [(float(k), lambda s, t: s.sur_parole("il parle", t))
                                           for k in range(3, 9)])
    assert stops_gos(out) == [(2.0, "stop"), (8.0, "go")]      # la parole ne repousse rien
    assert [(t, p["pourquoi"]) for t, p in journal(out, "pause_regard")] == [
        (2.0, "« regarde » → il s'arrête et regarde, il repartira seul dans 6 s")]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "reprise")] == [
        (8.0, "reprise : il rejoint sa route (regard terminé, 6 s)")]


def test_pause_sans_verrou_un_geste_peut_suivre():
    sel = fabriquer(pools={})
    marche(sel, 0.0)
    sel.sur_chat_move_bouche("pause", 1.0)
    assert not sel.verrou_stop


def test_stop_de_david_pendant_la_pause_ne_repart_pas():
    out = scene([(2.0, bouche("pause")), (4.0, lambda s, t: s.sur_console({"cmd": "stop"}, t))])
    assert stops_gos(out) == [(2.0, "stop"), (4.0, "stop")]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "reprise_annulee")] == [
        (4.0, "stop de console → il ne rejoint pas sa route de lui-même")]


def test_route_off_par_david_pendant_la_pause_ne_repart_pas():
    out = scene([(2.0, bouche("pause")), (3.0, lambda s, t: s.sur_route_cause("cmd", t))])
    assert stops_gos(out) == [(2.0, "stop")]


def test_pause_deja_arrete_ne_repart_jamais():
    out = scene([(1.0, bouche("stop")), (2.0, bouche("pause"))])
    assert stops_gos(out) == [(1.0, "stop")]
    assert [p["pourquoi"] for _, p in journal(out, "pause_regard")] == [
        "« regarde » : il est déjà arrêté → il regarde sans repartir de lui-même"]


def test_pause_hors_route_regarde_sur_place():
    out = jouer_regisseur(fabriquer(pools={}), 10.0, [(1.0, bouche("pause"))], regisseur_2121)
    assert stops_gos(out) == []
    assert [p["pourquoi"] for _, p in journal(out, "pause_regard")] == [
        "« regarde » : il n'est pas en route (inconnu) → il regarde sur place"]


def test_pause_pendant_un_aller_voir_l_annule_puis_rejoint_la_route():
    # aller_voir accepté à 1,3 s, « regarde » à 3 s : l'aller_voir est annulé (le stop du
    # régisseur annule aussi sa manœuvre), puis « go » à 9 s : il rejoint sa route.
    out = scene([(1.0, bouche(AV_ELEPHANT)), (3.0, bouche("pause"))])
    assert [(t, m) for t, m in moves(out)] == [(1.3, AV_ELEPHANT), (3.0, "stop"), (9.0, "go")]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "annulation")] == [
        (3.0, "« regarde » : il s'arrête pour regarder → il arrête de faire ce qu'il a dit "
              "(aller voir « elephant »)")]


def test_mode_degrade_la_pause_est_un_stop():
    from didier_jeu.relais import RelaisSeul
    r = RelaisSeul("test")
    r.vider_sorties()
    r.sur_chat_move_bouche("pause", 1.0)
    assert [s for s in r.vider_sorties() if s[0] == "chat_move"] == [("chat_move", "stop")]
    assert r.verrou.actif
