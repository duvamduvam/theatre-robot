"""Lot S1 (25-26/11) — ordres et propositions, une seule reprise (docs/spec-S1-ordres-propositions.md
§5 tests 1 à 4 et 9, puis règles R1 à R6 de la relecture adverse ; les tests 5-6 sont dans
didier_vision, 7-8 dans didier_core).

Valeurs et instants GRAVÉS : ticks de 0,1 s, réglages réels (reprise [10, 40] s), graine des
tests conftest.GRAINE = 3 -> première durée tirée 17,1 s, deuxième 26,3 s.

Le banc `jouer_avec_regisseur` (R5) enchaîne le sélecteur et le VRAI régisseur de la marche
(didier_rehearsal.director.VoiceMove) : chaque sortie chat_move du sélecteur lui est donnée
telle que jeu_node la publierait, et l'on regarde la vitesse qu'il impose — c'est la chaîne
complète qui doit faire repartir ou retenir Didier, pas chaque moitié séparément.

Mutations faites à la livraison (doivent rougir) : voir le rapport du lot (stop de Didier qui
verrouille, parole sans effet, fatigue rendue aux ordres, go de la bouche qui lève le verrou de
la console, re-émission R4 retirée, lubie permise hors séance, ordre console repassé par le score).
"""
import pytest

from conftest import fabriquer

from didier_rehearsal.contracts import lire_chat_move
from didier_rehearsal.director import VoiceMove
from test_reponse_bouche import AV_ELEPHANT, bouche, jouer_regisseur, regisseur_2121, reponses
from test_selecteur import SEANCE, boite, decisions, journal, jouer, marche, moves, _poi

# La marche telle que le sélecteur la publie sur jeu/chat_move (contrat lot S1), écrite EN DUR.
STOP_DAVID = {"cmd": "stop", "origine": "david"}
STOP_DIDIER = {"cmd": "stop", "origine": "didier"}
GO_DAVID = {"cmd": "go", "origine": "david"}
GO_DIDIER = {"cmd": "go", "origine": "didier"}
AV_ELEPHANT_DAVID = dict(AV_ELEPHANT, origine="david")


def marches(out):
    return [(t, m) for t, m in moves(out) if not isinstance(m, dict) or m.get("cmd") in ("stop", "go")]


def route_hors_seance(sel, t):
    """Route en marche et tableau des objets, mais séance NON lancée (rehearsal/state inconnu)."""
    sel.sur_route_state("on", t)
    sel.sur_tableau(marche.__globals__["TABLEAU"], t)


# ---------------------------------------------------------------- 1. un ordre de David n'est jamais annulé
def test_1_le_verrou_de_david_ne_tombe_ni_sur_un_stop_ni_sur_un_go_de_didier():
    sel = fabriquer(pools={})
    out = jouer(sel, 0.0, 120.0, [(0.0, marche), (1.0, bouche(STOP_DAVID)), (2.0, bouche(STOP_DIDIER)),
                                  (3.0, bouche(GO_DIDIER))])
    # Le stop de Didier est relayé (un arrêt n'est jamais refusé), le go de Didier jamais.
    assert moves(out) == [(1.0, STOP_DAVID), (2.0, STOP_DIDIER)]
    assert sel.verrou == "voix"
    assert journal(out, "reprise_armee") == []                     # rien ne repartira sous son verrou
    assert [p["pourquoi"] for _, p in journal(out, "refus")] == [
        "« go » proposé par Didier : ignoré (seule sa reprise, après le silence, le relance)"]


def test_1_r4_un_stop_de_didier_suspend_le_geste_de_david_repris_apres_le_silence():
    """Spec §5.1 révisé par R4 : le stop de Didier ARRÊTE le corps, sans verrou, mais SUSPEND
    l'ordre de David — à la reprise, le geste est ré-émis (origine « david ») au lieu du go."""
    sel = fabriquer(pools={})
    out = jouer_regisseur(sel, 25.0, [(0.0, marche), (1.0, bouche(AV_ELEPHANT_DAVID)), (3.0, bouche(STOP_DIDIER))],
                          regisseur_2121)
    assert moves(out) == [(1.0, AV_ELEPHANT_DAVID), (3.0, STOP_DIDIER), (20.1, AV_ELEPHANT_DAVID)]
    assert sel.verrou is None
    assert [(t, p["pourquoi"]) for t, p in journal(out, "ordre_suspendu")] == [
        (3.0, "ordre de David suspendu (aller voir « elephant ») : il le reprendra après le silence")]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "reprise")] == [
        (20.1, "ordre de David suspendu, repris après 17,1 s de silence (aller voir « elephant »)")]


def test_1_r4_un_stop_de_david_pendant_la_suspension_annule_tout():
    out = jouer_regisseur(fabriquer(pools={}), 40.0, [
        (0.0, marche), (1.0, bouche(AV_ELEPHANT_DAVID)), (3.0, bouche(STOP_DIDIER)),
        (5.0, lambda s, t: s.sur_console({"cmd": "stop"}, t))], regisseur_2121)
    assert moves(out) == [(1.0, AV_ELEPHANT_DAVID), (3.0, STOP_DIDIER), (5.0, STOP_DAVID)]


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


def test_2_deux_arrets_deux_tirages():
    """Deux arrêts de Didier : chacun tire SA durée (17,1 puis 26,3 s)."""
    out = jouer(fabriquer(pools={}), 0.0, 80.0, [
        (0.0, marche), (1.0, bouche(STOP_DIDIER)),
        (20.0, lambda s, t: s.sur_route_state("on", t)), (21.0, bouche(STOP_DIDIER))])
    assert marches(out) == [(1.0, STOP_DIDIER), (18.1, GO_DIDIER), (21.0, STOP_DIDIER), (47.3, GO_DIDIER)]


def test_2_r5_la_reprise_attend_le_superviseur():
    """Garde superviseur de la reprise (mode « exigeant ») : sans battement de la page, pas de go ;
    avec, le go part à l'instant tiré."""
    def presence(s, t):
        if abs(t * 2 - round(t * 2)) < 1e-6:                   # battement à 2 Hz
            s.sur_console({"presence": True}, t)
    sans = jouer(fabriquer({"superviseur.mode": "exigeant"}, pools={}), 0.0, 60.0,
                 [(0.0, marche), (1.0, bouche(STOP_DIDIER))])
    avec = jouer(fabriquer({"superviseur.mode": "exigeant"}, pools={}), 0.0, 60.0,
                 [(0.0, marche), (1.0, bouche(STOP_DIDIER))], continu=presence)
    assert marches(sans) == [(1.0, STOP_DIDIER)]
    assert marches(avec) == [(1.0, STOP_DIDIER), (18.1, GO_DIDIER)]


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


# ---------------------------------------------------------------- R3. verrou de David à deux genres
def test_go_de_la_bouche_ne_leve_pas_un_stop_de_david():
    """R3 (rétabli avec le VRAI message de la bouche en tour humain) : un STOP de la console
    n'est levé que par un GO de la console ; le « en route » dit à Didier ne suffit pas."""
    sel = fabriquer(pools={})
    out = jouer(sel, 0.0, 12.0, [(0.0, marche), (1.0, lambda s, t: s.sur_console({"cmd": "stop"}, t)),
                                 (5.0, bouche(GO_DAVID)), (8.0, lambda s, t: s.sur_console({"cmd": "go"}, t))])
    assert moves(out) == [(1.0, STOP_DAVID), (8.0, GO_DAVID)]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "refus")] == [
        (5.0, "« go » dit à Didier, mais David a arrêté à la console : seul un GO console le relance")]


def test_r3_route_off_de_david_verrou_de_la_route_le_go_vocal_ne_le_leve_pas():
    sel = fabriquer(pools={})
    out = jouer(sel, 0.0, 6.0, [(0.0, marche), (1.0, lambda s, t: s.sur_route_cause("cmd", t)),
                                (1.0, lambda s, t: s.sur_route_state("off", t)), (3.0, bouche(GO_DAVID))])
    assert sel.verrou == "route" and marches(out) == []
    assert [p["pourquoi"] for _, p in journal(out, "refus")] == [
        "« go » dit à Didier, mais David a coupé la route : elle se relance par la route (ou le GO console)"]


def test_r3_mot_d_arret_leve_par_le_go_de_david_en_tour_humain():
    sel = fabriquer(pools={})
    out = jouer(sel, 0.0, 6.0, [(0.0, marche), (1.0, bouche(STOP_DAVID)), (3.0, bouche(GO_DAVID))])
    assert moves(out) == [(1.0, STOP_DAVID), (3.0, GO_DAVID)] and sel.verrou is None


def test_r3_un_mot_d_arret_ne_rabaisse_jamais_le_verrou_de_la_console():
    sel = fabriquer(pools={})
    jouer(sel, 0.0, 4.0, [(0.0, marche), (1.0, lambda s, t: s.sur_console({"cmd": "stop"}, t)),
                          (2.0, bouche(STOP_DAVID))])
    assert sel.verrou == "console"


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
    # Aucun refus du sélecteur : chaque ordre est « accepted » à la réception (lot S2a) ; le
    # « no_reply » de 6,1 s vient du régisseur absent du banc.
    assert [(t, r["effect"]) for t, r in reponses(out)] == [(1.0, "accepted"), (2.0, "accepted"), (3.0, "accepted"),
                                                            (6.1, "no_reply")]
    assert journal(out, "refus") == []


def test_4_ordre_de_la_console_jamais_refuse_pour_fatigue_ni_trop_tot():
    sel = fabriquer(pools={})
    out = jouer(sel, 0.0, 4.0, [(0.0, marche),
                                (1.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "banc"}, t))],
                continu=_pulsions_au_maximum)
    # R6 : au tick de sa réception, sans score.
    assert moves(out) == [(1.0, {"cmd": "aller_voir", "objet": "banc", "id": "carte/banc", "origine": "david"})]
    assert journal(out, "refus") == []


def test_4_la_fatigue_borne_toujours_ses_propres_deplacements():
    from didier_jeu.scores import Candidat
    sel = fabriquer(pools={})
    sel.sur_seance(SEANCE, 0.0)
    sel.pulsions.fatigue = 0.81
    assert sel._permis(Candidat("approcher", "p1"), True) is False
    sel.pulsions.fatigue = 0.79
    assert sel._permis(Candidat("approcher", "p1"), True) is True


# ---------------------------------------------------------------- R6. un ordre passe avant toute initiative
def test_r6_ordre_de_la_console_pendant_une_expression_spontanee_part_au_tick():
    """Fumée du 26/11 (épreuve A1, T4) : « va_la p1 » à 162,1 s, expression spontanée choisie
    à 169,5 s, l'ordre mourait « pas faisable en 10 s, abandonné » à 172,2 s. Désormais l'ordre
    interrompt l'initiative et part au tick de sa réception, jamais d'expiration."""
    out = jouer(fabriquer(), 0.0, 20.0, [(0.0, marche),
                                         (5.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "p1"}, t))],
                continu=boite(4.6, 20.0))
    assert decisions(out)[0] == (4.0, "spontanee", None)                 # l'initiative en cours
    assert moves(out) == [(5.0, {"cmd": "tourner", "angle_deg": -9.0, "origine": "david"})]   # azimut +0,3
    assert [(t, p["pourquoi"]) for t, p in journal(out, "annulation")] == [
        (5.0, "David : va vers p1 → il arrête de une expression spontanée")]
    assert journal(out, "refus") == []


def test_r6_l_ordre_engage_n_est_pas_interrompu_par_le_score():
    sel = fabriquer()                                    # avec expressions spontanées (l'ennui monte)
    out = jouer_regisseur(sel, 30.0, [(0.0, marche),
                                      (1.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "banc"}, t))],
                          regisseur_2121)
    assert sel.en_cours is not None and sel.en_cours.candidat.action == "aller_voir" and decisions(out) == []


# ---------------------------------------------------------------- R2. hors séance, aucune initiative
def test_r2_aucune_lubie_hors_seance():
    hors = jouer(fabriquer(pools={}), 0.0, 8.0, [(0.0, route_hors_seance), (1.0, _poi("anneaux"))])
    en = jouer(fabriquer(pools={}), 0.0, 8.0, [(0.0, marche), (1.0, _poi("anneaux"))])
    assert decisions(hors) == [] and moves(hors) == []
    assert decisions(en) == [(1.3, "lubie", "anneaux")]


def test_r2_aucune_approche_de_son_initiative_hors_seance_joue_avec_permis():
    from didier_jeu.scores import Candidat
    sel = fabriquer(pools={})
    assert sel._permis(Candidat("approcher", "p1"), True) is False
    sel.joue_avec = {"cible": "p1", "fin": 99.0}                         # David : « joue avec lui »
    assert sel._permis(Candidat("approcher", "p1"), True) is True


def test_r2_hors_seance_pas_de_reprise_apres_un_geste_de_david():
    def arrivee(s, t):
        s.sur_route_state("arrived", t)
        s.sur_goto_result({"name": "elephant", "result": "arrived"}, t)
    out = jouer_regisseur(fabriquer(pools={}), 40.0, [(0.0, route_hors_seance), (1.0, bouche(AV_ELEPHANT_DAVID)),
                                                      (5.0, arrivee)], regisseur_2121)
    assert moves(out) == [(1.0, AV_ELEPHANT_DAVID)]                     # le geste de David part
    assert [(t, p["pourquoi"]) for t, p in journal(out, "reprise_annulee")] == [
        (5.0, "geste terminé, hors séance → il ne repartira pas de lui-même")]


# ---------------------------------------------------------------- R5. la chaîne sélecteur -> régisseur
class Regisseur:
    """Le VRAI VoiceMove, nourri des sorties chat_move du sélecteur ; route en marche à 0,7."""

    def __init__(self, en_seance: bool):
        self.voice, self.en_seance, self.vitesse, self.effets = VoiceMove(), en_seance, 0.7, []

    def recevoir(self, payload, t):
        cmd, origine = lire_chat_move(payload)
        if isinstance(cmd, dict):
            refus = self.voice.geste_refuse(origine, self.en_seance)
            if refus is None:
                self.voice.accept_goto(lubie_active=False, speed_in_effect=0.7)
                self.vitesse = 0.7                                        # la manœuvre roule
            self.effets.append((t, cmd["cmd"], refus or "accepted"))
            return
        d = self.voice.decide(cmd, t, lubie_active=False, route_on=True, relaunch_refusal="route_off_par_david",
                              speed_in_effect=0.7, origine=origine)
        if d.speed is not None:
            self.vitesse = d.speed
        self.effets.append((t, cmd, d.reason or d.effect))


def jouer_avec_regisseur(sel, reg, t1, evenements, seance):
    evs = [(0.0, (lambda s, t: s.sur_seance(SEANCE, t)) if seance else (lambda s, t: None)),
           (0.0, route_hors_seance)] + evenements
    out = jouer(sel, 0.0, t1, evs)
    for t, kind, *reste in out:
        if kind == "chat_move":
            reg.recevoir(reste[0], t)
    return out


@pytest.mark.parametrize("seance", [True, False])
def test_r5_pause_regard_il_repart_seance_ou_non(seance):
    reg = Regisseur(seance)
    jouer_avec_regisseur(fabriquer(pools={}), reg, 30.0, [(2.0, bouche({"cmd": "pause", "origine": "david"}))],
                         seance)
    assert reg.effets == [(2.0, "stop", "hold"), (19.1, "go", "resume")] and reg.vitesse == 0.7


@pytest.mark.parametrize("seance", [True, False])
def test_r5_stop_de_didier_applique_puis_il_repart(seance):
    reg = Regisseur(seance)
    jouer_avec_regisseur(fabriquer(pools={}), reg, 30.0, [(1.0, bouche(STOP_DIDIER))], seance)
    assert reg.effets == [(1.0, "stop", "hold"), (18.1, "go", "resume")] and reg.vitesse == 0.7


def test_r5_geste_de_david_hors_seance_il_part():
    reg = Regisseur(en_seance=False)
    reg.voice.decide("stop", 0.0, lubie_active=False, route_on=True, relaunch_refusal=None,
                     speed_in_effect=0.7, origine="didier")            # arrêté par Didier avant
    reg.vitesse = 0
    jouer_avec_regisseur(fabriquer(pools={}), reg, 3.0, [(1.0, bouche(dict(AV_ELEPHANT_DAVID)))], seance=False)
    assert reg.effets == [(1.0, "aller_voir", "accepted")] and reg.vitesse == 0.7


def test_r5_stop_console_puis_go_de_la_bouche_le_verrou_reste():
    reg = Regisseur(en_seance=True)
    jouer_avec_regisseur(fabriquer(pools={}), reg, 10.0, [(1.0, lambda s, t: s.sur_console({"cmd": "stop"}, t)),
                                                          (4.0, bouche(GO_DAVID))], seance=True)
    assert reg.effets == [(1.0, "stop", "hold")] and reg.vitesse == 0


def test_r5_mot_d_arret_puis_go_en_tour_humain_il_repart():
    reg = Regisseur(en_seance=False)
    jouer_avec_regisseur(fabriquer(pools={}), reg, 10.0, [(1.0, bouche(STOP_DAVID)), (4.0, bouche(GO_DAVID))],
                         seance=False)
    assert reg.effets == [(1.0, "stop", "hold"), (4.0, "go", "resume")] and reg.vitesse == 0.7


# ---------------------------------------------------------------- 9. anciennes formes lues « david »
def test_9_anciennes_formes_lues_comme_david():
    assert lire_chat_move("stop") == ("stop", "david")
    assert lire_chat_move(" STOP ") == ("stop", "david")                 # casse et espaces normalisés
    assert lire_chat_move({"cmd": "Go"}) == ("go", "david")
    assert lire_chat_move({"cmd": "pause", "origine": "didier"}) == ("pause", "didier")
    assert lire_chat_move({"cmd": "go", "origine": "lune"}) == ("go", None)
    assert lire_chat_move({"cmd": "avancer", "metres": 1.0}) == ({"cmd": "avancer", "metres": 1.0}, "david")


def test_9_chaine_stop_verrouille_et_chaine_go_le_leve():
    sel = fabriquer(pools={})
    out = jouer(sel, 0.0, 80.0, [(0.0, marche), (1.0, bouche("stop")), (2.0, bouche({"cmd": "stop"})),
                                 (60.0, bouche("go"))])
    assert moves(out) == [(1.0, STOP_DAVID), (2.0, STOP_DAVID), (60.0, GO_DAVID)]
    assert journal(out, "reprise_armee") == []


def test_9_stop_et_pause_d_origine_inconnue_lus_david_le_go_refuse():
    sel = fabriquer(pools={})
    out = jouer(sel, 0.0, 4.0, [(0.0, marche), (1.0, bouche({"cmd": "stop", "origine": "lune"})),
                                (2.0, bouche({"cmd": "go", "origine": "lune"})),
                                (3.0, bouche({"cmd": "pause", "origine": "lune"}))])
    assert moves(out) == [(1.0, STOP_DAVID), (3.0, STOP_DAVID)] and sel.verrou == "voix"


def test_9_geste_sans_origine_est_un_ordre():
    out = jouer_regisseur(fabriquer(pools={}), 2.0, [(0.0, marche), (1.0, bouche(AV_ELEPHANT))], regisseur_2121)
    assert moves(out) == [(1.0, AV_ELEPHANT)]                      # relayé tel quel (le chat apparie)
    assert [p["pourquoi"] for _, p in journal(out, "ordre")] == ["David : aller voir « elephant » → il y va tout de suite"]


# ================================================================ seconde relecture (26/11)
def _off(s, t):
    s.sur_route_cause("cmd", t)            # route_driver : la cause d'abord…
    s.sur_route_state("off", t)            # … puis l'état


def test_bloquant_route_off_puis_on_l_ordre_suivant_est_accepte():
    """Route OFF puis ON par David sans GO console (ce que font A1 et CONV) : avant, un verrou
    « console » fantôme restait, Didier roulait mais refusait tout. Le verrou « route » tombe au
    retour de la route à « on »."""
    sel = fabriquer(pools={})
    out = jouer_regisseur(sel, 6.0, [(0.0, marche), (1.0, _off), (3.0, lambda s, t: s.sur_route_state("on", t)),
                                     (4.0, bouche(AV_ELEPHANT_DAVID))], regisseur_2121)
    assert moves(out) == [(4.0, AV_ELEPHANT_DAVID)] and sel.verrou is None
    assert [(t, p["pourquoi"]) for t, p in journal(out, "verrou")] == [
        (1.0, "David a coupé la route → verrou de la route, levé quand il la remet"),
        (3.0, "David a remis la route → verrou de la route levé")]


def test_bloquant_le_on_latche_d_avant_le_off_ne_leve_rien():
    sel = fabriquer(pools={})
    jouer(sel, 0.0, 3.0, [(0.0, marche), (1.0, lambda s, t: s.sur_route_cause("cmd", t)),
                          (1.5, lambda s, t: s.sur_route_state("on", t))])
    assert sel.verrou == "route"


def test_bloquant_un_stop_console_garde_son_verrou_apres_off_et_on():
    sel = fabriquer(pools={})
    out = jouer(sel, 0.0, 6.0, [(0.0, marche), (1.0, lambda s, t: s.sur_console({"cmd": "stop"}, t)),
                                (2.0, _off), (3.0, lambda s, t: s.sur_route_state("on", t)),
                                (4.0, bouche(AV_ELEPHANT_DAVID))])
    assert sel.verrou == "console" and moves(out) == [(1.0, STOP_DAVID)]
    assert [r["reason"] for _, r in reponses(out)] == ["arrete"]


# ---------------------------------------------------------------- majeur 1 : jamais un ordre périmé
def test_m1_tout_nouvel_ordre_de_david_efface_l_ordre_suspendu():
    out = jouer_regisseur(fabriquer(pools={}), 25.0, [
        (0.0, marche), (1.0, bouche(AV_ELEPHANT_DAVID)), (3.0, bouche(STOP_DIDIER)),
        (5.0, lambda s, t: s.sur_console({"cmd": "plus_lent"}, t))], regisseur_2121)
    assert moves(out) == [(1.0, AV_ELEPHANT_DAVID), (3.0, STOP_DIDIER), (20.1, GO_DIDIER)]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "ordre_suspendu")][-1] == (
        5.0, "ordre de David suspendu oublié (aller voir « elephant ») : David donne un nouvel ordre")


def test_m1_r2_hors_seance_la_reprise_precedente_tombe_aussi():
    def arrivee(s, t):
        s.sur_route_state("arrived", t)
        s.sur_goto_result({"name": "elephant", "result": "arrived"}, t)
    out = jouer_regisseur(fabriquer(pools={}), 60.0, [
        (0.0, marche), (1.0, bouche(STOP_DIDIER)),                          # reprise armée : 18,1 s
        (2.0, lambda s, t: s.sur_seance({"seance": "terminee", "arret_vocal": False}, t)),
        (3.0, bouche(AV_ELEPHANT_DAVID)), (6.0, arrivee)], regisseur_2121)
    assert marches(out) == [(1.0, STOP_DIDIER)]                            # jamais de go périmé


def test_m1_ordre_suspendu_trop_ancien_abandonne():
    paroles = [(float(k), lambda s, t: s.sur_parole("encore", t)) for k in range(5, 61, 5)]
    out = jouer_regisseur(fabriquer(pools={}), 80.0, [
        (0.0, marche), (1.0, bouche(AV_ELEPHANT_DAVID)), (3.0, bouche(STOP_DIDIER))] + paroles, regisseur_2121)
    # Dernière parole à 60 s : reprise à 77,1 s, l'ordre (donné à 1,0 s) a 76,1 s (> 60) -> simple go.
    assert moves(out) == [(1.0, AV_ELEPHANT_DAVID), (3.0, STOP_DIDIER), (77.1, GO_DIDIER)]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "ordre_suspendu")][-1] == (
        77.1, "ordre de David abandonné : trop ancien (aller voir « elephant », donné il y a plus de 60 s)")


def test_m1_la_reemission_repasse_par_hors_atteinte():
    from theatre_contrats.objets import Objet, Tableau
    loin = Tableau((Objet(id="carte/elephant", nom="elephant", x=30.0, y=0.0, distance_m=30.0, azimut_deg=0.0,
                          cote="devant", en_vue=False, atteignable=False),))
    av = dict(AV_ELEPHANT_DAVID, id="carte/elephant")
    # jouer : l'écrivain republie le tableau (ici, « loin » dès 10 s) ; sans régisseur, le geste
    # n'est pas accusé, mais le stop de 3 s tombe avant les 3 s d'attente.
    out = jouer(fabriquer(pools={}), 0.0, 25.0, [
        (0.0, marche), (1.0, bouche(av)), (3.0, bouche(STOP_DIDIER)),
        (10.0, lambda s, t: s.sur_tableau(loin, t))])
    assert moves(out) == [(1.0, av), (3.0, STOP_DIDIER), (20.1, GO_DIDIER)]
    # (1,0 s : « accepted » de l'ordre d'origine, lot S2a ; la ré-émission R4 n'a pas de réponse
    # « accepted » — personne ne l'a demandée à l'instant —, son refus reste dit.)
    assert [(t, r["effect"], r["reason"]) for t, r in reponses(out)] == [(1.0, "accepted", None),
                                                                         (20.1, "dropped", "pas_ici")]


def test_m1_un_geste_relatif_n_est_jamais_rejoue():
    av = {"cmd": "avancer", "metres": 3.0, "origine": "david"}
    out = jouer(fabriquer(pools={}), 0.0, 25.0, [(0.0, marche), (1.0, bouche(av)),
                                                 (2.0, lambda s, t: s.sur_route_state("goto", t)),
                                                 (3.0, bouche(STOP_DIDIER))])
    assert moves(out) == [(1.0, av), (3.0, STOP_DIDIER), (20.1, GO_DIDIER)]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "ordre_suspendu")] == [
        (3.0, "geste relatif non repris (avancer de 3.0 m) : il ne mènerait plus au même endroit")]


# ---------------------------------------------------------------- majeur 2 : ordres de la console aussi
def test_m2_un_ordre_console_est_suspendu_et_un_second_stop_le_garde():
    av_banc = {"cmd": "aller_voir", "objet": "banc", "id": "carte/banc", "origine": "david"}
    out = jouer_regisseur(fabriquer(pools={}), 40.0, [
        (0.0, marche), (1.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "banc"}, t)),
        (3.0, bouche(STOP_DIDIER)), (8.0, bouche(STOP_DIDIER))], regisseur_2121)
    # Second stop : nouveau tirage (26,3 s) -> 34,3 s ; l'ordre (31 s d'âge) repart.
    assert moves(out) == [(1.0, av_banc), (3.0, STOP_DIDIER), (8.0, STOP_DIDIER), (34.3, av_banc)]


# ---------------------------------------------------------------- mineurs
def test_mineur_la_reprise_attend_la_fin_d_un_deplacement():
    sel = fabriquer(pools={})
    out = jouer_regisseur(sel, 40.0, [(0.0, marche), (1.0, bouche(STOP_DIDIER)), (5.0, bouche(AV_ELEPHANT_DAVID))],
                          regisseur_2121)
    assert marches(out) == [(1.0, STOP_DIDIER)]                            # pas de go à 18,1 s : le geste roule
    assert sel.en_cours is not None and sel.reprise is not None


def test_mineur_un_stop_fait_tomber_l_ordre_console_pas_encore_parti():
    # Un stop de Didier (sans verrou, donc rien d'autre ne retient l'ordre) : l'ordre reçu juste
    # avant, pas encore parti, tombe — rien ne repart derrière un arrêt (sens sûr).
    out = jouer(fabriquer(pools={}), 0.0, 4.0, [(0.0, marche),
                                                (2.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "banc"}, t)),
                                                (2.0, bouche(STOP_DIDIER))])
    assert moves(out) == [(2.0, STOP_DIDIER)]


def test_mineur_r2_la_fin_de_seance_desarme_la_reprise_apres_un_geste():
    def arrivee(s, t):
        s.sur_route_state("arrived", t)
        s.sur_goto_result({"name": "elephant", "result": "arrived"}, t)
    out = jouer_regisseur(fabriquer(pools={}), 40.0, [
        (0.0, marche), (1.0, bouche(AV_ELEPHANT_DAVID)), (5.0, arrivee),
        (10.0, lambda s, t: s.sur_seance({"seance": "terminee", "arret_vocal": False}, t))], regisseur_2121)
    assert marches(out) == []
    assert [(t, p["pourquoi"]) for t, p in journal(out, "reprise_annulee")] == [
        (10.0, "la séance s'est arrêtée → il ne repartira pas de lui-même")]


def test_mineur_l_ordre_console_passe_avant_la_reprise_du_meme_tick():
    out = jouer(fabriquer(pools={}), 0.0, 20.0, [
        (0.0, marche), (1.0, bouche(STOP_DIDIER)),
        (18.1, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "banc"}, t))])
    assert [(t, m) for t, m in moves(out) if t >= 18.0] == [
        (18.1, {"cmd": "aller_voir", "objet": "banc", "id": "carte/banc", "origine": "david"})]


def test_mineur_r6_rafale_le_meme_ordre_console_dans_la_seconde_est_ignore():
    sel = fabriquer(pools={})
    out = jouer(sel, 0.0, 4.0, [(0.0, marche),
                                (1.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "banc"}, t)),
                                (1.5, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "banc"}, t))])
    assert [t for t, m in moves(out)] == [1.0]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "console") if p.get("doublon")] == [
        (1.5, "David : va voir « banc » — reçu deux fois en moins de 1 s : le doublon est ignoré")]


def test_mineur_reviens_pendant_un_geste_annule_la_manoeuvre_puis_go():
    out = jouer_regisseur(fabriquer(pools={}), 8.0, [
        (0.0, marche), (1.0, bouche(AV_ELEPHANT_DAVID)), (1.5, lambda s, t: s.sur_route_state("goto", t)),
        (4.0, lambda s, t: s.sur_console({"cmd": "reviens"}, t)),
        (5.0, lambda s, t: s.sur_route_state("off", t))], regisseur_2121)       # le régisseur a annulé
    assert moves(out) == [(1.0, AV_ELEPHANT_DAVID), (4.0, STOP_DAVID), (5.0, GO_DAVID)]


def test_mineur_reviens_sans_confirmation_go_au_bout_de_5_s():
    out = jouer_regisseur(fabriquer(pools={}), 12.0, [
        (0.0, marche), (1.0, bouche(AV_ELEPHANT_DAVID)), (1.5, lambda s, t: s.sur_route_state("goto", t)),
        (4.0, lambda s, t: s.sur_console({"cmd": "reviens"}, t))], regisseur_2121)
    assert moves(out) == [(1.0, AV_ELEPHANT_DAVID), (4.0, STOP_DAVID), (9.0, GO_DAVID)]


# ================================================================ troisième relecture (26/11)
AV_ANNEAUX = {"cmd": "aller_voir", "objet": "anneaux", "id": "carte/anneaux", "origine": "david"}   # pas ici


def _suspendu_puis(evenement, t1=25.0):
    """Geste de David à 1 s, stop de Didier à 3 s (suspendu, reprise à 20,1 s), puis `evenement`."""
    return jouer(fabriquer(pools={}), 0.0, t1, [(0.0, marche), (1.0, bouche(AV_ELEPHANT_DAVID)),
                                                (3.0, bouche(STOP_DIDIER))] + evenement)


@pytest.mark.parametrize("evenement", [
    [(5.0, bouche(AV_ANNEAUX))],                                               # chat_move david REFUSÉ (pas_ici)
    [(5.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "lune"}, t))],  # ordre console refusé
    [(3.5, lambda s, t: s.sur_route_state("off", t)),                          # annulation de la manœuvre,
     (5.0, lambda s, t: s.sur_route_state("on", t))],                          # puis la route repart (M2)
    [(5.0, lambda s, t: s.sur_seance({"seance": "terminee", "arret_vocal": False}, t))],   # fin de séance
])
def test_3r_toute_action_de_david_efface_l_ordre_suspendu_meme_refusee(evenement):
    out = _suspendu_puis(evenement)
    # Plus de ré-émission : la reprise (arrêt posé par Didier, permise hors séance) fait un go.
    assert [(t, m) for t, m in moves(out) if t >= 20.0] == [(20.1, GO_DIDIER)]
    assert [(t, p["pourquoi"][:30]) for t, p in journal(out, "ordre_suspendu")][-1] == (
        5.0, "ordre de David suspendu oublié")


def test_3r_le_off_d_une_annulation_n_efface_pas_l_ordre_suspendu():
    """Le « off » qui suit l'annulation de la manœuvre par le stop de Didier n'est pas David."""
    out = _suspendu_puis([(3.5, lambda s, t: s.sur_route_state("off", t))])
    assert [(t, m) for t, m in moves(out) if t >= 20.0] == [(20.1, AV_ELEPHANT_DAVID)]


def test_3r_l_age_compte_depuis_l_ordre_d_origine():
    """Ordre à 1 s, suspendu à 3 s, ré-émis à 20,1 s, re-suspendu à 25 s : son âge reste celui
    de 1 s — à la reprise suivante (25 + 26,3 + paroles) il a dépassé 60 s."""
    paroles = [(float(k), lambda s, t: s.sur_parole("encore", t)) for k in (30, 35)]
    out = jouer_regisseur(fabriquer(pools={}), 70.0, [
        (0.0, marche), (1.0, bouche(AV_ELEPHANT_DAVID)), (3.0, bouche(STOP_DIDIER)),
        (25.0, bouche(STOP_DIDIER))] + paroles, regisseur_2121)
    # 2e tirage 26,3 s depuis la dernière parole (35 s) -> 61,3 s ; l'ordre a 60,3 s : abandonné.
    assert moves(out) == [(1.0, AV_ELEPHANT_DAVID), (3.0, STOP_DIDIER), (20.1, AV_ELEPHANT_DAVID),
                          (25.0, STOP_DIDIER), (61.3, GO_DIDIER)]


def test_3r_m3_la_route_ne_remplace_pas_un_verrou_plus_fort():
    sel = fabriquer(pools={})
    jouer(sel, 0.0, 3.0, [(0.0, marche), (1.0, bouche(STOP_DAVID)), (2.0, _off)])
    assert sel.verrou == "voix"


def test_3r_m4_un_ordre_refuse_n_arme_pas_le_rebond():
    out = jouer(fabriquer(pools={}), 0.0, 3.0, [
        (0.0, marche), (1.0, lambda s, t: s.sur_console({"cmd": "stop"}, t)),
        (1.2, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "banc"}, t)),     # refusé : arrêté
        (1.4, lambda s, t: s.sur_console({"cmd": "go"}, t)),
        (1.6, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "banc"}, t))])    # pas un doublon
    assert moves(out) == [(1.0, STOP_DAVID), (1.4, GO_DAVID),
                          (1.6, {"cmd": "aller_voir", "objet": "banc", "id": "carte/banc", "origine": "david"})]


def test_3r_m1_reviens_annule_un_geste_meme_avant_goto():
    out = jouer_regisseur(fabriquer(pools={}), 6.0, [
        (0.0, marche), (1.0, bouche(AV_ELEPHANT_DAVID)),
        (4.0, lambda s, t: s.sur_console({"cmd": "reviens"}, t))], regisseur_2121)
    assert moves(out) == [(1.0, AV_ELEPHANT_DAVID), (4.0, STOP_DAVID), (4.0, GO_DAVID)]


def test_3r_m2_stop_de_didier_pendant_le_reviens_la_reprise_part_en_david():
    """Le stop de Didier fait tomber le go du « reviens » : sa reprise lèvera l'arrêt « david »
    du reviens d'un go de David (un go de Didier serait refusé « arret_de_david »)."""
    out = jouer_regisseur(fabriquer(pools={}), 25.0, [
        (0.0, marche), (1.0, bouche(AV_ELEPHANT_DAVID)), (1.5, lambda s, t: s.sur_route_state("goto", t)),
        (4.0, lambda s, t: s.sur_console({"cmd": "reviens"}, t)), (4.5, bouche(STOP_DIDIER))], regisseur_2121)
    assert moves(out) == [(1.0, AV_ELEPHANT_DAVID), (4.0, STOP_DAVID), (4.5, STOP_DIDIER), (21.6, GO_DAVID)]


def test_3r_m2_reviens_tombe_sur_route_off_le_go_part_au_retour_de_la_route():
    out = jouer_regisseur(fabriquer(pools={}), 8.0, [
        (0.0, marche), (1.0, bouche(AV_ELEPHANT_DAVID)), (1.5, lambda s, t: s.sur_route_state("goto", t)),
        (4.0, lambda s, t: s.sur_console({"cmd": "reviens"}, t)), (4.5, _off),
        (6.0, lambda s, t: s.sur_route_state("on", t))], regisseur_2121)
    assert moves(out) == [(1.0, AV_ELEPHANT_DAVID), (4.0, STOP_DAVID), (6.0, GO_DAVID)]
