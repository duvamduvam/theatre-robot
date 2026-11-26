"""Reprise de route APRÈS UN GESTE de la bouche (David, 15/11 21:35 : « il faut
que la route se remette automatiquement quand besoin ») — valeurs et instants
GRAVÉS (ticks de 0,1 s ; graine des tests : durées tirées 17,1 s puis 26,3 s).

Séance : après chaque geste demandé, Didier restait planté (route_driver
« route : disabled »). Lot S1 (25/11) : c'est LA reprise unique (silence tiré dans
[10, 40] s) qui le relance ; la parole remet le silence à zéro (règle du 02/11,
étendue aux gestes par la spec S1 — avant, 10 s fixes, parole sans effet).

Mutations (doivent rougir) :
  - reprise jamais armée dans _finir -> test_aller_voir_arrivee_repart_au_silence_tire
  - stop de David qui ne désarme pas -> test_stop_de_david_ne_repart_pas
  - « go » de David repassé par le score -> test_en_route_dit_par_david_repart_tout_de_suite
"""
from conftest import fabriquer

from test_reponse_bouche import AV_ELEPHANT, ELEPHANT, bouche, jouer_regisseur, regisseur_2121
from test_selecteur import GO_DAVID, GO_DIDIER, journal, marche, moves

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
    return [(t, m) for t, m in moves(out) if m in (GO_DAVID, GO_DIDIER)]


def test_aller_voir_arrivee_repart_au_silence_tire():
    out = scene([])
    assert gos(out) == [(22.1, GO_DIDIER)]                       # arrivée 5,0 + 17,1 s
    assert [(t, p["pourquoi"]) for t, p in journal(out, "reprise")] == [
        (22.1, "reprise : il repart de lui-même (geste terminé, après 17,1 s de silence)")]


def test_parole_continue_repousse_la_reprise():
    out = scene(parle_chaque_seconde(5, 30), t1=60.0)
    assert gos(out) == [(47.1, GO_DIDIER)]                       # dernière parole 30,0 + 17,1 s


def test_stop_de_david_ne_repart_pas():
    out = scene([(8.0, lambda s, t: s.sur_console({"cmd": "stop"}, t))], t1=60.0)
    assert gos(out) == []
    assert [(t, p["pourquoi"]) for t, p in journal(out, "reprise_annulee")] == [
        (8.0, "stop de David → il ne repartira pas de lui-même")]


def test_stop_vocal_ne_repart_pas():
    out = scene([(8.0, bouche("stop"))], t1=60.0)               # mot d'arrêt : « david »
    assert gos(out) == []


def test_route_off_par_david_ne_repart_pas():
    out = scene([(8.0, lambda s, t: s.sur_route_cause("cmd", t))], t1=60.0)
    assert gos(out) == []
    assert [t for t, _ in journal(out, "reprise_annulee")] == [8.0]


def test_nouveau_geste_echoue_re_arme_la_reprise():
    # Tour (refusé, no_tour) demandé à 12 s : il part à la réception (ordre), le refus tombe à
    # 12,1 s hors de la route (« arrived ») -> nouvelle reprise, 2e tirage : 12,1 + 26,3 = 38,4 s.
    out = scene([(12.0, bouche(ELEPHANT))], t1=45.0)
    assert [t for t, m in moves(out) if m == ELEPHANT] == [12.0]
    assert gos(out) == [(38.4, GO_DIDIER)]
    assert [p["pourquoi"] for _, p in journal(out, "reprise")] == [
        "reprise : il repart de lui-même (geste échoué, après 26,3 s de silence)"]


def test_en_route_dit_par_david_repart_tout_de_suite():
    # 1 s après l'arrivée, David dit « en route » (ancienne forme : « david ») : go immédiat.
    out = scene([(6.0, bouche("go"))])
    assert gos(out) == [(6.0, GO_DAVID)]
    assert journal(out, "reprise") == []                       # la reprise auto est caduque


def test_geste_refuse_sans_quitter_la_route_pas_de_go():
    out = jouer_regisseur(fabriquer(pools={}), 40.0, [(0.0, marche), (1.0, bouche(ELEPHANT))], regisseur_2121)
    assert gos(out) == []                                       # route_state « on » : déjà en route
