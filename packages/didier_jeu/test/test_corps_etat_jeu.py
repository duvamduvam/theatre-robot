"""Lot S2a (27/11) — le sélecteur ÉCRIT corps/etat et RÉPOND à toute demande de David
(docs/spec-S2-le-corps-raconte.md §2, §3, §7 test 3).

Valeurs et instants GRAVÉS : ticks de 0,1 s, réglages réels, graine conftest.GRAINE = 3 (première
reprise tirée : 17,1 s). Le tableau des objets est celui de test_selecteur (éléphant à 2,2 m sur la
gauche, banc à 5 m devant ; anneaux et flaque hors de portée).
"""
import json

import pytest

from conftest import fabriquer

from test_selecteur import (GO_DAVID, PIVOT_LUBIE, STOP_DAVID, STOP_DIDIER, journal, marche,
                            moves, _poi)
from test_reponse_bouche import bouche, reponses

ARME = {"etat": "ARME", "cause": "", "zone": "LIBRE", "d_min_m": 4.2}
VERROU = {"etat": "VERROU", "cause": "capteur_perdu", "zone": "LIBRE", "d_min_m": None}
AUTOUR = "Sur ta gauche à 2 m : « elephant » ; devant toi à 5 m : « banc »."
AV_BANC = {"cmd": "aller_voir", "objet": "banc", "id": "carte/banc", "origine": "david"}
TOUR_ELEPHANT = {"cmd": "tour_de", "objet": "elephant", "id": "carte/elephant", "sens": "gauche", "origine": "david"}
TOURNER = {"cmd": "tourner", "angle_deg": 90.0, "origine": "david"}
AVANCER = {"cmd": "avancer", "metres": 1.0, "origine": "david"}


def scene(sel, t):
    """Séance lancée, route en marche, tableau des objets, corps sûr armé : rien ne manque."""
    marche(sel, t)
    sel.sur_corps_sur(ARME, t)


def jouer_corps(sel, t0, t1, evenements, ecrivain_vivant=True):
    """Comme test_selecteur.jouer, plus ce que fait jeu_node._vider : rafraichir corps/etat avant
    chaque vidage. L'écrivain du tableau des objets republie toutes les secondes (sauf
    `ecrivain_vivant` False : il se tait après la scène)."""
    evs = sorted(evenements, key=lambda e: e[0])
    out = []
    for i in range(int(round((t1 - t0) / 0.1)) + 1):
        t = round(t0 + i * 0.1, 6)
        while evs and evs[0][0] <= t + 1e-9:
            evs.pop(0)[1](sel, t)
        if ecrivain_vivant and sel.tableau_recu is not None and abs(t - round(t)) < 1e-6:
            sel.sur_tableau(sel.tableau_recu, t)
        sel.tick(t)
        sel.rafraichir_corps(t)
        out += [(t,) + s for s in sel.vider_sorties()]
    return out


def corps(out):
    return [(o[0], json.loads(o[2])) for o in out if o[1] == "corps_etat"]


def causes(out):
    return [(t, p["marche"], p["cause"]) for t, p in journal(out, "corps_etat")]


# ================================================================ l'écrivain de corps/etat
def test_inconnu_tant_qu_une_source_manque_puis_republie_toutes_les_2_s():
    def route(s, t):
        s.sur_route_state("on", t)
        s.sur_tableau(marche.__globals__["TABLEAU"], t)
    out = jouer_corps(fabriquer(pools={}), 0.0, 5.0, [
        (0.0, route), (0.5, lambda s, t: s.sur_seance({"seance": "en_cours", "arret_vocal": False}, t)),
        (1.0, lambda s, t: s.sur_corps_sur(ARME, t))])
    pubs = corps(out)
    assert [t for t, _ in pubs] == [0.0, 1.0, 3.0, 5.0]       # changement à 1,0 s, puis toutes les 2 s
    assert pubs[0][1]["phrase"] == "Tu ne sais pas où en est ton corps."
    assert pubs[1][1] == {"v": 1, "t_ms": 1000, "marche": "en_route", "cause": "aucune", "qui_relance": None,
                          "repart_dans_s": None, "geste": None,
                          "ici": {"sur": None, "proches": [{"nom": "elephant", "cote": "gauche", "distance_m": 2.2},
                                                           {"nom": "banc", "cote": "devant", "distance_m": 5.0}]},
                          "phrase": "Tu roules sur ta route. " + AUTOUR}
    # Le journal : une ligne par changement de marche ou de cause, pas par republication.
    assert causes(out) == [(0.0, "empeche", "aucune"), (1.0, "en_route", "aucune")]
    assert [p["pourquoi"] for _, p in journal(out, "corps_etat")][1] == "Tu roules sur ta route. " + AUTOUR


def test_stop_de_david_l_etat_part_dans_le_meme_lot_derriere_le_stop_et_sa_reponse():
    sel = fabriquer(pools={})
    jouer_corps(sel, 0.0, 1.0, [(0.0, scene)])
    sel.sur_chat_move_bouche("stop", 1.05)
    sel.rafraichir_corps(1.05)
    lot = [s for s in sel.vider_sorties() if s[0] != "journal"]
    genres = [s[0] for s in lot]
    assert genres.index("chat_move") == 0                    # le stop, premier effet : jamais retardé
    assert genres.index("chat_move") < genres.index("chat_move_reply") < genres.index("corps_etat")
    e = json.loads(next(s[1] for s in lot if s[0] == "corps_etat"))
    assert (e["marche"], e["cause"], e["qui_relance"]) == ("arrete", "david_stop_voix", "david")
    assert e["phrase"] == "Tu es arrêté : David t'a dit stop. Seul un go de David te relance. " + AUTOUR


@pytest.mark.parametrize("evenement, cause, qui, phrase", [
    (lambda s, t: s.sur_console({"cmd": "stop"}, t), "david_stop_console", "david_console",
     "Tu es arrêté : David t'a arrêté à la console. Seul son bouton GO te relance. " + AUTOUR),
    (lambda s, t: (s.sur_route_cause("cmd", t), s.sur_route_state("off", t)), "david_route_off", "david_console",
     "Tu es arrêté : David a coupé ta route. Seul David la relance, sur la page. " + AUTOUR),
    (bouche(STOP_DIDIER), "didier_stop", "didier",
     "Tu es arrêté : c'est toi qui t'es arrêté. Tu repars dans 17 s si personne ne parle. " + AUTOUR),
    (bouche({"cmd": "pause", "origine": "david"}), "didier_pause", "didier",
     "Tu es arrêté pour regarder : c'est toi qui t'es arrêté. Tu repars dans 17 s si personne ne parle. " + AUTOUR),
])
def test_la_cause_vient_du_verrou_ou_de_la_reprise(evenement, cause, qui, phrase):
    out = jouer_corps(fabriquer(pools={}), 0.0, 2.0, [(0.0, scene), (1.0, evenement)])
    t, e = corps(out)[1]
    assert (t, e["marche"], e["cause"], e["qui_relance"], e["phrase"]) == (1.0, "arrete", cause, qui, phrase)


def test_reprise_le_reste_du_silence_glisse_sans_republier_a_chaque_tick():
    out = jouer_corps(fabriquer(pools={}), 0.0, 5.0, [(0.0, scene), (1.0, bouche(STOP_DIDIER))])
    assert [(t, e["cause"], e["repart_dans_s"]) for t, e in corps(out)] == [
        (0.0, "aucune", None), (1.0, "didier_stop", 17.1), (3.0, "didier_stop", 15.1), (5.0, "didier_stop", 13.1)]


def test_lubie_arretee_d_elle_meme():
    out = jouer_corps(fabriquer(), 0.0, 5.0, [(0.0, scene), (1.0, _poi("anneaux"))])
    # Lot S2c (28/11) : son arrêt est le pivot du CORPS vers l'objet, sans « stop » avant.
    assert moves(out) == [(4.3, PIVOT_LUBIE("anneaux"))]
    t, e = next((t, e) for t, e in corps(out) if e["cause"] == "didier_lubie")
    assert (t, e["qui_relance"], e["repart_dans_s"]) == (4.3, "didier", 17.1)
    assert e["phrase"] == ("Tu es arrêté, attiré par « anneaux » : c'est toi qui t'es arrêté. Tu repars dans 17 s "
                           "si personne ne parle. " + AUTOUR)


def test_geste_en_cours_puis_fini_et_reprise():
    out = jouer_corps(fabriquer(pools={}), 0.0, 6.0, [
        (0.0, scene), (1.0, bouche(AV_BANC)), (1.2, lambda s, t: s.sur_route_state("goto", t)),
        (5.0, lambda s, t: (s.sur_route_state("arrived", t),
                            s.sur_goto_result({"name": "banc", "result": "arrived", "travelled": 3.46}, t)))])
    assert causes(out) == [(0.0, "en_route", "aucune"), (1.0, "geste", "aucune"), (5.0, "arrete", "geste_fini")]
    pubs = dict(corps(out))
    assert pubs[1.0]["phrase"] == "Tu es en plein geste : aller voir « banc ». " + AUTOUR
    assert pubs[1.0]["geste"] == {"demande": AV_BANC, "etat": "en_cours", "raison": None, "parcouru_m": None}
    assert pubs[5.0]["geste"] == {"demande": AV_BANC, "etat": "arrive", "raison": None, "parcouru_m": 3.5}
    assert pubs[5.0]["phrase"] == ("Tu es arrêté : ton geste est fini. Tu repars dans 17 s si personne ne parle. "
                                   "Ton dernier geste (aller voir « banc ») est fini : tu es arrivé après 3,5 m.")


def test_corps_sur_verrouille_pendant_un_geste_il_passe_avant_tout():
    out = jouer_corps(fabriquer(pools={}), 0.0, 3.0, [
        (0.0, scene), (1.0, bouche(AV_BANC)), (1.2, lambda s, t: s.sur_route_state("goto", t)),
        (2.0, lambda s, t: s.sur_corps_sur(VERROU, t)),
        (2.5, lambda s, t: s.sur_goto_result({"name": "banc", "result": "aborted", "reason": "stalled",
                                              "travelled": 0.04}, t))])
    assert causes(out) == [(0.0, "en_route", "aucune"), (1.0, "geste", "aucune"),
                           (2.0, "empeche", "corps_sur_verrou")]
    e = corps(out)[-1][1]
    assert (e["qui_relance"], e["geste"]["etat"], e["geste"]["raison"]) == ("personne", "abandonne", "corps_sur")
    assert e["phrase"] == ("Tu ne peux pas bouger : ton corps est verrouillé par sécurité. Il faut le réarmer avant "
                           "tout. Ton dernier geste (aller voir « banc ») a été abandonné après 0,0 m : ton corps "
                           "est verrouillé par sécurité.")


def test_le_dernier_geste_est_dit_60_s_puis_oublie():
    loin = dict(AV_BANC, objet="anneaux", id="carte/anneaux")          # anneaux : à 14,1 m, pas ici
    out = jouer_corps(fabriquer(pools={}), 0.0, 61.3, [(0.0, scene), (1.0, bouche(loin))])
    pubs = dict(corps(out))
    assert pubs[1.0]["geste"] == {"demande": loin, "etat": "refuse", "raison": "pas_ici", "parcouru_m": 0.0}
    assert pubs[1.0]["phrase"] == ("Tu roules sur ta route. Ton dernier geste (aller voir « anneaux ») a été "
                                   "refusé, tu n'as pas bougé : ce n'est pas ici. " + AUTOUR)
    assert pubs[61.0]["geste"] is not None and pubs[61.1]["geste"] is None   # changement : republié tout de suite


def test_hors_seance_a_l_arret():
    def attente(s, t):
        s.sur_seance({"seance": "attente", "arret_vocal": False}, t)
        s.sur_route_state("off", t)
        s.sur_corps_sur(ARME, t)
    out = jouer_corps(fabriquer(pools={}), 0.0, 0.0, [(0.0, attente)])
    e = corps(out)[0][1]
    assert (e["marche"], e["cause"], e["qui_relance"], e["phrase"]) == (
        "empeche", "seance_non_lancee", "david_console",
        "Tu ne peux pas bouger : la séance n'est pas lancée. David peut la démarrer sur la page.")


def test_ici_sur_un_objet_et_un_autre_derriere():
    from theatre_contrats.objets import Objet, Tableau
    t_flaque = Tableau((Objet(id="carte/flaque", nom="flaque", x=0.0, y=0.0, distance_m=0.7, azimut_deg=10.0,
                              cote="devant", emprise_m=1.5),
                        Objet(id="carte/banc", nom="banc", x=-3.0, y=0.0, distance_m=3.0, azimut_deg=180.0,
                              cote="derriere", emprise_m=1.1)))
    out = jouer_corps(fabriquer(pools={}), 0.0, 0.0, [(0.0, scene), (0.0, lambda s, t: s.sur_tableau(t_flaque, t))])
    e = corps(out)[0][1]
    assert e["ici"] == {"sur": "flaque", "proches": [{"nom": "banc", "cote": "derriere", "distance_m": 3.0}]}
    assert e["phrase"] == "Tu roules sur ta route. Tu traverses : « flaque ». Derrière toi à 3 m : « banc »."


def test_tableau_perime_plus_rien_autour():
    # L'écrivain du tableau se tait après 0,0 s : périmé 3 s après (objets.PEREMPTION_S), plus rien autour.
    out = jouer_corps(fabriquer(pools={}), 0.0, 4.0, [(0.0, scene)], ecrivain_vivant=False)
    assert [(t, e["ici"]["proches"] != []) for t, e in corps(out)] == [(0.0, True), (2.0, True), (3.1, False)]


# ================================================================ réponse à toute demande de David
def test_3_une_reponse_pour_chaque_demande_de_david():
    out = jouer_corps(fabriquer(pools={}), 0.0, 8.0, [
        (0.0, scene), (1.0, bouche("stop")), (2.0, bouche(GO_DAVID)), (3.0, bouche({"cmd": "pause", "origine": "david"})),
        (4.0, bouche(AV_BANC)), (5.0, bouche(TOUR_ELEPHANT)), (6.0, bouche(TOURNER)), (7.0, bouche(AVANCER))])
    assert [(t, r["demande"], r["effect"], r["reason"]) for t, r in reponses(out)] == [
        (1.0, "stop", "accepted", None), (2.0, GO_DAVID, "accepted", None),
        (3.0, {"cmd": "pause", "origine": "david"}, "accepted", None), (4.0, AV_BANC, "accepted", None),
        (5.0, TOUR_ELEPHANT, "accepted", None), (6.0, TOURNER, "accepted", None), (7.0, AVANCER, "accepted", None)]
    assert all(r["source"] == "jeu" for _, r in reponses(out))
    assert moves(out) == [(1.0, STOP_DAVID), (2.0, GO_DAVID), (3.0, STOP_DIDIER), (4.0, AV_BANC), (5.0, TOUR_ELEPHANT),
                          (6.0, TOURNER), (7.0, AVANCER)]


def test_3_ordre_des_sorties_stop_d_abord_geste_apres_sa_reponse():
    sel = fabriquer(pools={})
    jouer_corps(sel, 0.0, 0.0, [(0.0, scene)])
    sel.sur_chat_move_bouche("stop", 1.0)
    assert [s[0] for s in sel.vider_sorties() if s[0] in ("chat_move", "chat_move_reply")] == \
        ["chat_move", "chat_move_reply"]
    sel.sur_chat_move_bouche(GO_DAVID, 1.1)
    sel.vider_sorties()
    sel.sur_chat_move_bouche(AV_BANC, 1.2)
    # Geste : sa réponse « accepted » part AVANT sa transmission, donc avant le verdict du régisseur.
    assert [s[0] for s in sel.vider_sorties() if s[0] in ("chat_move", "chat_move_reply")] == \
        ["chat_move_reply", "chat_move"]


@pytest.mark.parametrize("arret, genre", [
    (lambda s, t: s.sur_console({"cmd": "stop"}, t), "console"),
    (lambda s, t: (s.sur_route_cause("cmd", t), s.sur_route_state("off", t)), "route"),
])
def test_3_go_refuse_arrete_avec_le_genre_du_verrou(arret, genre):
    out = jouer_corps(fabriquer(pools={}), 0.0, 4.0, [(0.0, scene), (1.0, arret), (2.0, bouche(GO_DAVID)),
                                                     (3.0, bouche(AV_BANC))])
    assert reponses(out) == [
        (2.0, {"demande": GO_DAVID, "effect": "dropped", "reason": "arrete", "source": "jeu", "verrou": genre}),
        (3.0, {"demande": AV_BANC, "effect": "dropped", "reason": "arrete", "source": "jeu", "verrou": genre})]
    assert GO_DAVID not in [m for _, m in moves(out)] and AV_BANC not in [m for _, m in moves(out)]


def test_3_mot_d_arret_geste_refuse_verrou_voix_le_go_le_leve():
    out = jouer_corps(fabriquer(pools={}), 0.0, 4.0, [(0.0, scene), (1.0, bouche("stop")), (2.0, bouche(AV_BANC)),
                                                     (3.0, bouche(GO_DAVID))])
    assert [(t, r["effect"], r["reason"], r.get("verrou")) for t, r in reponses(out)] == [
        (1.0, "accepted", None, None), (2.0, "dropped", "arrete", "voix"), (3.0, "accepted", None, None)]


def test_3_hors_seance_un_ordre_de_david_part_jamais_hors_seance():
    """S1 (R1, R5) : un ordre de David part hors séance — le sélecteur ne refuse jamais
    « hors_seance » (c'est un code du régisseur, pour un geste « didier »)."""
    def route_seule(s, t):
        s.sur_seance({"seance": "attente", "arret_vocal": False}, t)
        s.sur_route_state("on", t)
        s.sur_tableau(marche.__globals__["TABLEAU"], t)
        s.sur_corps_sur(ARME, t)
    out = jouer_corps(fabriquer(pools={}), 0.0, 3.0, [(0.0, route_seule), (1.0, bouche(GO_DAVID)), (2.0, bouche(AV_BANC))])
    assert [(t, r["effect"]) for t, r in reponses(out)] == [(1.0, "accepted"), (2.0, "accepted")]


def test_3_sans_superviseur():
    out = jouer_corps(fabriquer({"superviseur.mode": "exigeant"}, pools={}), 0.0, 2.0,
                      [(0.0, scene), (1.0, bouche(AV_BANC))])
    assert reponses(out) == [(1.0, {"demande": AV_BANC, "effect": "dropped", "reason": "sans_superviseur",
                                    "source": "jeu"})]


def test_3_corps_sur_verrouille_go_et_geste_refuses_le_stop_jamais():
    out = jouer_corps(fabriquer(pools={}), 0.0, 4.0, [
        (0.0, scene), (0.5, lambda s, t: s.sur_corps_sur(VERROU, t)), (1.0, bouche("stop")), (2.0, bouche(GO_DAVID)),
        (3.0, bouche(AV_BANC))])
    assert [(t, r["effect"], r["reason"]) for t, r in reponses(out)] == [
        (1.0, "accepted", None), (2.0, "dropped", "corps_sur"), (3.0, "dropped", "corps_sur")]
    assert moves(out) == [(1.0, STOP_DAVID)]                  # ni go relayé ni geste transmis
    assert [p["code"] for _, p in journal(out, "refus")] == ["corps_sur", "corps_sur"]


def test_3_zone_arret_du_corps_sur_le_geste_part():
    """Zone ARRET : le corps sûr filtre chaque consigne ; un pivot pour se dégager doit partir."""
    out = jouer_corps(fabriquer(pools={}), 0.0, 2.0, [
        (0.0, scene), (0.5, lambda s, t: s.sur_corps_sur(dict(ARME, zone="ARRET"), t)), (1.0, bouche(TOURNER))])
    assert [(t, r["effect"]) for t, r in reponses(out)] == [(1.0, "accepted")]
    assert moves(out) == [(1.0, TOURNER)]
    assert corps(out)[1][1]["cause"] == "corps_sur_zone"


def test_3_une_demande_de_didier_n_a_pas_de_reponse():
    out = jouer_corps(fabriquer(pools={}), 0.0, 3.0, [(0.0, scene), (1.0, bouche(STOP_DIDIER)),
                                                     (2.0, bouche({"cmd": "pause", "origine": "didier"}))])
    assert reponses(out) == []


def test_corps_sur_illisible_le_precedent_reste():
    sel = fabriquer(pools={})
    jouer_corps(sel, 0.0, 0.0, [(0.0, scene)])
    sel.sur_corps_sur({"etat": "PANIQUE"}, 1.0)
    assert sel.corps_sur.etat == "ARME"
    assert [p["pourquoi"][:28] for _, p in journal([(1.0,) + s for s in sel.vider_sorties()], "corps_sur")] == [
        "état du corps sûr illisible "]


def test_genres_du_verrou_egaux_entre_le_relais_et_le_contrat():
    from didier_jeu import relais
    from didier_rehearsal.contracts import CHAT_MOVE_REPLY_VERROUS
    from theatre_contrats import corps_etat
    assert (relais.VERROU_CONSOLE, relais.VERROU_ROUTE, relais.VERROU_VOIX) == \
        (corps_etat.VERROU_CONSOLE, corps_etat.VERROU_ROUTE, corps_etat.VERROU_VOIX) == ("console", "route", "voix")
    assert set(CHAT_MOVE_REPLY_VERROUS) == {"console", "route", "voix"}


def test_jeu_node_publie_corps_etat_latche_et_ecoute_le_corps_sur_latche():
    """Lus dans le VRAI fichier du node (il importe rclpy : jamais importé sur l'hôte)."""
    import pathlib
    node = (pathlib.Path(__file__).resolve().parents[1] / "didier_jeu" / "jeu_node.py").read_text(encoding="utf-8")
    assert "self.create_publisher(StringTime, topics.CORPS_ETAT, qos.latched())" in node
    assert ("self.create_subscription(StringTime, topics.CORPS_SUR_ETAT, self._json(self.sel.sur_corps_sur),\n"
            "                                     qos.latched())") in node
    assert 'getattr(self.sel, "rafraichir_corps", None)' in node
    from didier_jeu.relais import RelaisSeul
    assert getattr(RelaisSeul("x"), "rafraichir_corps", None) is None     # mode dégradé : rien de publié
