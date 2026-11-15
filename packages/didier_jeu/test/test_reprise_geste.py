"""Reprise de route APRÈS UN GESTE de la bouche (David, 15/11 21:35 : « il faut
que la route se remette automatiquement quand besoin ») — valeurs et instants
GRAVÉS (reprise.apres_geste_s = 10 s, ticks de 0,1 s).

Séance : après chaque geste demandé, Didier restait planté (route_driver
« route : disabled ») ; la seule reprise était 90 s de SILENCE, remise à zéro
par chaque parole — en conversation elle n'arrivait jamais.

Mutations (doivent rougir) :
  - reprise jamais armée dans _finir -> test_aller_voir_arrivee_parole_continue_repart_a_10_s
  - stop de David qui ne désarme pas -> test_stop_de_david_ne_repart_pas
  - « go » de la bouche repassé par le score -> test_en_route_dit_par_didier_repart_tout_de_suite
"""
from conftest import fabriquer

from test_reponse_bouche import AV_ELEPHANT, ELEPHANT, bouche, jouer_regisseur, regisseur_2121
from test_selecteur import journal, marche, moves

ARRIVEE = {"name": "elephant", "result": "arrived", "reason": "arrived", "travelled": 3.17}


def arrivee(s, t):
    s.sur_route_state("arrived", t)
    s.sur_goto_result(ARRIVEE, t)


def parle_chaque_seconde(debut, fin):
    return [(float(k), lambda s, t: s.sur_parole("il parle", t)) for k in range(debut, fin + 1)]


def scene(evenements, t1=30.0):
    return jouer_regisseur(fabriquer(pools={}), t1, [(0.0, marche), (1.0, bouche(AV_ELEPHANT)), (5.0, arrivee)]
                           + evenements, regisseur_2121)


def gos(out):
    return [t for t, m in moves(out) if m == "go"]


def test_aller_voir_arrivee_parole_continue_repart_a_10_s():
    out = scene(parle_chaque_seconde(5, 30))
    assert gos(out) == [15.0]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "reprise")] == [
        (15.0, "reprise : il rejoint sa route (geste terminé, 10 s)")]


def test_stop_de_david_ne_repart_pas():
    out = scene([(8.0, lambda s, t: s.sur_console({"cmd": "stop"}, t))], t1=60.0)
    assert gos(out) == []
    assert [(t, p["pourquoi"]) for t, p in journal(out, "reprise_annulee")] == [
        (8.0, "stop de console → il ne rejoint pas sa route de lui-même")]


def test_stop_vocal_ne_repart_pas():
    out = scene([(8.0, bouche("stop"))], t1=60.0)
    assert gos(out) == []


def test_route_off_par_david_ne_repart_pas():
    out = scene([(8.0, lambda s, t: s.sur_route_cause("cmd", t))], t1=60.0)
    assert gos(out) == []
    assert [t for t, _ in journal(out, "reprise_annulee")] == [8.0]


def test_nouveau_geste_annule_la_reprise_qui_repart_apres_lui():
    # Tour (refusé, no_tour) demandé à 12 s : pas de go à 15 s ; la reprise
    # repart 10 s après la fin ÉCHOUÉE du tour (décidé 12,3 s, refusé 12,4 s -> 22,4 s).
    out = scene([(12.0, bouche(ELEPHANT))])
    assert [t for t, m in moves(out) if m == ELEPHANT] == [12.3]
    assert gos(out) == [22.4]
    assert [p["pourquoi"] for _, p in journal(out, "reprise")] == [
        "reprise : il rejoint sa route (geste échoué, 10 s)"]


def test_en_route_dit_par_didier_repart_tout_de_suite():
    # 1 s après l'arrivée : avant, l'offre « go » mourait (réfractaire de 10 s).
    out = scene([(6.0, bouche("go"))])
    assert gos(out) == [6.0]
    assert journal(out, "reprise") == []                       # la reprise auto est caduque


def test_geste_refuse_sans_quitter_la_route_pas_de_go():
    out = jouer_regisseur(fabriquer(pools={}), 20.0, [(0.0, marche), (1.0, bouche(ELEPHANT))], regisseur_2121)
    assert gos(out) == []                                       # route_state « on » : déjà en route
