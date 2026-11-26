"""Règles du sélecteur (spec A1 §3, §6, §8 ; révisées par la spec S1 du 25/11) — valeurs
GRAVÉES en dur, et pour chaque règle chiffrée une MUTATION (le réglage muté par surcharge) qui
prouve que le test mord : la même scène, règle cassée, viole la propriété.

Horloge simulée : ticks de 0,1 s (tick_s), aucun sleep. Graine des reprises : conftest.GRAINE
(première durée tirée 17,1 s, deuxième 26,3 s). Les règles propres au lot S1 (origine, verrou
de David, une seule reprise) : test_ordres_propositions.py.
"""
import pytest

from conftest import fabriquer

from theatre_contrats.objets import Objet, Tableau

# Le tableau des objets (lot O1) tel que l'écrit didier_perception pour Didier à l'origine,
# cap +x : distances, azimuts et atteignabilité relevés à la main, GRAVÉS (le sélecteur les lit).
ANNEAUX = Objet(id="carte/anneaux", nom="anneaux", desc="bagues", x=10.0, y=10.0, distance_m=14.1,
                azimut_deg=45.0, cote="devant", en_vue=False, atteignable=False)
FLAQUE = Objet(id="carte/flaque", nom="flaque", desc="eau", x=30.0, y=0.0, distance_m=30.0, azimut_deg=0.0,
               cote="devant", en_vue=False, atteignable=False)
# Un objet atteignable (< 10 m), pour les demandes de la bouche.
BANC = Objet(id="carte/banc", nom="banc", x=5.0, y=0.0, distance_m=5.0, azimut_deg=0.0, cote="devant",
             en_vue=True, atteignable=True)
ELEPHANT_O = Objet(id="carte/elephant", nom="elephant", desc="statue", x=1.0, y=2.0, distance_m=2.2,
                   azimut_deg=63.4, cote="gauche", en_vue=False, atteignable=True)
TABLEAU = Tableau((ELEPHANT_O, BANC, ANNEAUX, FLAQUE))
# La marche publiée sur jeu/chat_move (lot S1 : elle porte son origine), écrite EN DUR.
STOP_DAVID = {"cmd": "stop", "origine": "david"}
STOP_DIDIER = {"cmd": "stop", "origine": "didier"}
GO_DAVID = {"cmd": "go", "origine": "david"}
GO_DIDIER = {"cmd": "go", "origine": "didier"}


def ecrivain(sel, t):
    """L'écrivain du tableau des objets (didier_perception) republie toutes les secondes : le
    dernier tableau posé par la scène est re-reçu aux secondes rondes (péremption, revue O1)."""
    if sel.tableau_recu is not None and abs(t - round(t)) < 1e-6:
        sel.sur_tableau(sel.tableau_recu, t)


def jouer(sel, t0, t1, evenements=None, continu=None, dt=0.1, ecrivain_vivant=True):
    """Ticks de t0 à t1 inclus. evenements : [(t, f(sel, t))] déclenchés juste
    avant le tick de t ; continu : f(sel, t) appelé à chaque tick (boîte de
    personne à 10 Hz) ; ecrivain_vivant : le tableau des objets est republié à
    1 Hz (False : l'écrivain se tait après la scène). -> [(t, *sortie)]."""
    evs = sorted(evenements or [], key=lambda e: e[0])
    out = []
    n = int(round((t1 - t0) / dt))
    for i in range(n + 1):
        t = round(t0 + i * dt, 6)
        while evs and evs[0][0] <= t + 1e-9:
            evs.pop(0)[1](sel, t)
        if ecrivain_vivant:
            ecrivain(sel, t)
        if continu is not None:
            continu(sel, t)
        sel.tick(t)
        out += [(t,) + s for s in sel.vider_sorties()]
    return out


def decisions(out):
    return [(t, s[2]["action"], s[2]["cible"]) for t, *s in [(o[0], *o[1:]) for o in out]
            if s[0] == "journal" and s[1] == "decision"]


def journal(out, type_):
    return [(o[0], o[3]) for o in out if o[1] == "journal" and o[2] == type_]


def moves(out):
    return [(o[0], o[2]) for o in out if o[1] == "chat_move"]


def boite(debut, fin, azimut=0.3, hauteur=0.4):
    def f(sel, t):
        if debut <= t <= fin:
            sel.sur_person_box(azimut, hauteur, 0.9, t)
    return f


def marche(sel, t):
    """Route en marche, tableau des objets vu de l'origine cap +x."""
    sel.sur_route_state("on", t)
    sel.sur_tableau(TABLEAU, t)


# ================================================================== T5 arrêt vocal
def test_stop_de_la_bouche_relaye_a_la_reception_sans_tick():
    sel = fabriquer()
    sel.sur_chat_move_bouche("stop", 5.0)
    sorties = sel.vider_sorties()
    # Avant tout tick : le relais est IMMÉDIAT, sans score.
    assert sorties[0] == ("chat_move", STOP_DAVID)     # ancienne forme : lue « david »
    assert [s[1] for s in sorties if s[0] == "journal"] == ["relais_stop"]
    assert sel.verrou_david


def test_verrou_jusqu_au_go_aucun_deplacement():
    sel = fabriquer()
    out = jouer(sel, 0.0, 20.0, [
        (0.0, marche),
        (1.0, lambda s, t: s.sur_chat_move_bouche("stop", t)),
        (2.0, lambda s, t: s.sur_chat_move_bouche({"cmd": "avancer", "metres": 1.0}, t)),
        (3.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "anneaux"}, t)),
        (15.0, lambda s, t: s.sur_console({"cmd": "go"}, t)),
    ])
    assert moves(out) == [(1.0, STOP_DAVID), (15.0, GO_DAVID)]
    assert [p["source"] for _, p in journal(out, "relais_go")] == ["console"]
    assert [p["pourquoi"] for _, p in journal(out, "refus")] == [
        "David voulait avancer de 1.0 m, mais non : il est arrêté jusqu'au go de David",
        "David : va voir « anneaux » — impossible : il est arrêté jusqu'au go de David"]


# ================================================================== T1 jamais deux changements < 2 s
def _scene_rupture(sel):
    # Piste née à 0 -> regarder ; David (console, ordre macro qui interrompt) envoie Didier
    # voir le banc à 0,5. (Avant le lot S1 : une demande de la bouche, offre 0,9 ; c'est
    # désormais un ordre exécuté sans score, hors de la porte T1.)
    return jouer(sel, 0.0, 6.0, [(0.0, marche),
                                 (0.5, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "banc"}, t))],
                 continu=boite(0.0, 6.0))


def test_deux_decisions_differentes_jamais_a_moins_de_2_s():
    d = decisions(_scene_rupture(fabriquer()))
    assert [a for _, a, _ in d] == ["regarder", "aller_voir"]
    assert d[1][0] - d[0][0] >= 2.0 - 1e-9   # 2,3 − 0,3 vaut 1,999… en flottant
    assert d[0][0] == pytest.approx(0.3)     # hystérésis 0,3 s après la naissance


def test_mutation_changement_min_s():
    d = decisions(_scene_rupture(fabriquer({"changement.min_s": 0.0})))
    assert d[1][0] - d[0][0] < 2.0


# ================================================================== hystérésis
def _premiere_spontanee(sel):
    d = decisions(jouer(sel, 0.0, 6.0))
    return d[0][0]


def test_hysteresis_marge_et_duree_gravees():
    # spontanée 0,6·e contre immobilité 0,3 − 0,3·e : la marge de 15 % exige
    # e >= 0,365 (3,7 s de calme), puis 0,3 s de domination -> 4,0 s.
    assert _premiere_spontanee(fabriquer()) == pytest.approx(4.0)


def test_mutation_hysteresis_marge():
    assert _premiere_spontanee(fabriquer({"hysteresis.marge": 0.0})) == pytest.approx(3.7)


def test_mutation_hysteresis_duree():
    assert _premiere_spontanee(fabriquer({"hysteresis.duree_s": 0.0})) == pytest.approx(3.8)


# ================================================================== engagement
def _scene_engagement(sel):
    # Regarder p1 engagé à 0,3 (tenue 3 s) ; un POI entre à 0,8 : offre 0,8 < 0,9.
    return jouer(sel, 0.0, 3.0, [(0.0, marche),
                                 (0.8, lambda s, t: s.sur_poi_event({"poi": "anneaux", "event": "enter"}, t))],
                 continu=boite(0.0, 3.0))


def test_offre_sous_le_seuil_n_interrompt_pas():
    assert [a for _, a, _ in decisions(_scene_engagement(fabriquer()))] == ["regarder"]


def test_mutation_seuil_de_rupture():
    acts = [a for _, a, _ in decisions(_scene_engagement(fabriquer({"engagement.seuil_rupture": 0.8,
                                                                    "changement.min_s": 0.0})))]
    assert acts == ["regarder", "lubie"]


# ================================================================== T3 réaction <= 1 s (choix OU maintien)
def _scene_reaction(sel):
    # Expression spontanée engagée à 4,0 ; une piste naît à 5,0.
    return jouer(sel, 0.0, 7.0, continu=boite(5.0, 7.0))


def test_naissance_de_piste_engagee_donne_un_maintien_en_moins_de_1_s():
    out = _scene_reaction(fabriquer())
    nee = journal(out, "naissance_piste")
    m = journal(out, "maintien")
    assert [(t, p["piste"]) for t, p in nee] == [(5.0, "p1")]
    assert len(m) == 1 and m[0][1]["reaction_a"] == ["p1"]
    assert m[0][0] - 5.0 == pytest.approx(0.6) and m[0][0] - 5.0 <= 1.0
    assert m[0][1]["pourquoi"] == ("il continue (une expression spontanée) : la nouvelle offre (0,70) "
                                   "ne suffit pas à l'interrompre (il faut 0,90)")


def test_naissance_de_piste_libre_donne_un_choix_en_moins_de_1_s():
    out = jouer(fabriquer(), 0.0, 2.0, continu=boite(0.0, 2.0))
    d = journal(out, "decision")
    assert d[0][1]["reaction_a"] == ["p1"] and d[0][0] <= 1.0
    assert journal(out, "maintien") == []


def test_mutation_maintien_trop_tard():
    out = _scene_reaction(fabriquer({"reaction.maintien_apres_s": 5.0}))
    assert [t for t, _ in journal(out, "maintien") if t - 5.0 <= 1.0] == []


# ================================================================== T2 initiatives spontanées >= 8 s
def _scene_spontanees(sel):
    """Chaque séquence finit 1 s après son départ (animation_state)."""
    fin = {}

    def anim(s, t):
        for nom, t_fin in list(fin.items()):
            if t >= t_fin:
                s.sur_animation_state("", t)
                del fin[nom]

    out = []
    for t_i in range(0, 600):
        t = round(t_i * 0.1, 6)
        anim(sel, t)
        sel.tick(t)
        for s in sel.vider_sorties():
            out.append((t,) + s)
            if s[0] == "animation":
                sel.sur_animation_state(s[1], t)
                fin[s[1]] = t + 1.0
    return [t for t, a, _ in decisions(out) if a == "spontanee"]


def test_initiatives_spontanees_espacees_de_8_s():
    ts = _scene_spontanees(fabriquer())
    assert len(ts) >= 5
    assert min(b - a for a, b in zip(ts, ts[1:])) >= 8.0


def test_mutation_refractaire_spontane():
    ts = _scene_spontanees(fabriquer({"refractaire_s.initiative_spontanee": 0.0,
                                      "refractaire_s.expression": 0.0}))
    assert min(b - a for a, b in zip(ts, ts[1:])) < 8.0


def test_rotation_des_sequences():
    out = jouer(fabriquer(), 0.0, 40.0)
    assert [o[2] for o in out if o[1] == "animation"][:3] == ["spont-a", "spont-b", "spont-a"]


# ================================================================== lubie : réclamée ET amorcée, puis stop
def _poi(nom):
    return lambda s, t: s.sur_poi_event({"poi": nom, "event": "enter", "distance": 3.0}, t)


def test_lubie_reclamee_amorcee_puis_stop_apres_3_s():
    out = jouer(fabriquer(), 0.0, 8.0, [(0.0, marche), (1.0, _poi("anneaux"))])
    assert decisions(out) == [(1.3, "lubie", "anneaux")]
    looks = [(o[0], o[2]) for o in out if o[1] == "look"]
    assert looks == [(1.3, {"angle_deg": 45.0, "hold_ms": 6000})]      # objet à (10, 10) : 45° à gauche
    intentions = [o[0] for o in out if o[1] == "intention" and o[2]["action"] == "lubie"]
    assert intentions[0] == 1.3
    assert moves(out) == [(4.3, STOP_DIDIER)]                            # 3 s après l'intention
    assert [p["cible"] for _, p in journal(out, "arret_didier")] == ["anneaux"]


@pytest.mark.parametrize("ordre", [{"cmd": "ignore"}, {"cmd": "ignore", "cible": "anneaux"},
                                   {"cmd": "va_la", "cible": "flaque"}])
def test_lubie_refusee_par_la_console_dans_les_3_s(ordre):
    out = jouer(fabriquer(), 0.0, 8.0, [(0.0, marche), (1.0, _poi("anneaux")),
                                        (2.5, lambda s, t: s.sur_console(ordre, t))])
    assert STOP_DIDIER not in [m for _, m in moves(out)]
    assert journal(out, "arret_didier") == []
    # Refusée À L'INSTANT de l'ordre (pas au choix suivant, 2 s plus tard).
    assert [(t, p["action"]) for t, p in journal(out, "annulation")] == [(2.5, "lubie")]


def test_pas_de_lubie_hors_route_ni_sous_verrou():
    hors_route = jouer(fabriquer(), 0.0, 8.0, [(0.0, marche), (0.5, lambda s, t: s.sur_route_state("arrived", t)),
                                               (1.0, _poi("anneaux"))])
    sous_verrou = jouer(fabriquer(), 0.0, 8.0, [(0.0, marche), (0.5, lambda s, t: s.sur_chat_move_bouche("stop", t)),
                                                (1.0, _poi("anneaux"))])
    for out in (hors_route, sous_verrou):
        assert "lubie" not in [a for _, a, _ in decisions(out)]


def _deux_lubies(sel):
    # Sans expressions (pools vides) : une expression engagée ne masque pas la 2e lubie.
    return jouer(sel, 0.0, 140.0, [(0.0, marche), (1.0, _poi("anneaux")),
                                   # il est reparti seul à 21,4 s (reprise, 17,1 s) : nouveau POI à 100 s
                                   (95.0, lambda s, t: s.sur_route_state("on", t)),
                                   (100.0, _poi("flaque")), (125.0, _poi("flaque"))])


def test_arrets_de_didier_espaces_de_120_s():
    out = _deux_lubies(fabriquer(pools={}))
    arrets = [t for t, _ in journal(out, "arret_didier")]
    assert arrets[0] == pytest.approx(4.3)
    assert all(b - a >= 120.0 for a, b in zip(arrets, arrets[1:]))
    assert len(arrets) == 2 and arrets[1] == pytest.approx(128.3)


def test_mutation_refractaire_arret_didier():
    out = _deux_lubies(fabriquer({"refractaire_s.arret_didier": 0.0}, pools={}))
    arrets = [t for t, _ in journal(out, "arret_didier")]
    assert any(b - a < 120.0 for a, b in zip(arrets, arrets[1:]))


# ================================================================== reprise après une lubie (lot S1 : tirée)
def test_reprise_go_de_didier_au_silence_tire_apres_sa_lubie():
    out = jouer(fabriquer(), 0.0, 100.0, [(0.0, marche), (1.0, _poi("anneaux"))])
    gos = [t for t, m in moves(out) if m == GO_DIDIER]
    # Stop à 4,3 s, durée tirée 17,1 s -> 21,4 s. Les expressions spontanées qui tombent
    # pendant l'arrêt ne la retardent pas (seul un DÉPLACEMENT engagé la fait attendre), et
    # elle ne passe plus par le score (avant le lot S1 : 99,6 s, réfractaire et hystérésis).
    assert gos == [pytest.approx(21.4)]
    acts = [d[1] for d in decisions(out)]
    assert acts[0] == "lubie" and "repartir" not in acts
    # Pendant l'arrêt, l'intention propose de repartir.
    assert any(o[2].get("proposition") == "repartir ?" for o in out if o[1] == "intention")


def test_mutation_delai_de_reprise():
    out = jouer(fabriquer({"reprise.min_s": 1.0, "reprise.max_s": 1.0}), 0.0, 100.0,
                [(0.0, marche), (1.0, _poi("anneaux"))])
    assert [t for t, m in moves(out) if m == GO_DIDIER] == [pytest.approx(5.3)]


@pytest.mark.parametrize("ordre", [{"cmd": "stop"}, {"cmd": "ignore"}])
def test_pas_de_go_automatique_apres_stop_ou_ignore_de_la_console(ordre):
    out = jouer(fabriquer(), 0.0, 300.0, [(0.0, marche), (1.0, _poi("anneaux")),
                                          (30.0, lambda s, t: s.sur_console(ordre, t))])
    assert "go" not in [m for _, m in moves(out)]
    # Et il ne PROPOSE plus de repartir : la décision est à David.
    assert not any(o[2].get("proposition") for o in out if o[1] == "intention" and o[0] >= 30.0)


def test_jamais_de_go_automatique_apres_un_stop_de_la_bouche():
    # « stop » en chaîne = ancienne forme, lue « david » (mot d'arrêt) : jamais de reprise.
    out = jouer(fabriquer(), 0.0, 300.0, [(0.0, marche), (1.0, lambda s, t: s.sur_chat_move_bouche("stop", t))])
    assert moves(out) == [(1.0, STOP_DAVID)]


def test_jamais_de_go_automatique_apres_un_stop_de_david():
    # Stop de la CONSOLE (David) après une lubie : ni reprise, ni go, 300 s durant.
    out = jouer(fabriquer(), 0.0, 300.0, [(0.0, marche), (1.0, _poi("anneaux")),
                                          (10.0, lambda s, t: s.sur_console({"cmd": "stop"}, t))])
    assert moves(out) == [(4.3, STOP_DIDIER), (10.0, STOP_DAVID)]


def test_go_de_didier_ne_leve_pas_un_stop_de_david():
    out = jouer(fabriquer(), 0.0, 20.0, [
        (0.0, marche),
        (1.0, lambda s, t: s.sur_console({"cmd": "stop"}, t)),
        (5.0, lambda s, t: s.sur_chat_move_bouche(GO_DIDIER, t)),
        (8.0, lambda s, t: s.sur_chat_move_bouche({"cmd": "avancer", "metres": 1.0}, t)),
    ])
    assert moves(out) == [(1.0, STOP_DAVID)]                # rien ne part
    assert [p["pourquoi"] for _, p in journal(out, "refus")] == [
        "« go » proposé par Didier : ignoré (seule sa reprise, après le silence, le relance)",
        "David voulait avancer de 1.0 m, mais non : il est arrêté jusqu'au go de David"]


def test_go_de_david_bouche_ou_console_leve_le_verrou_un_stop_de_didier_n_en_pose_pas():
    """Lot S1 : le verrou n'a qu'une source (supprimé : le verrou à deux sources du 02/11)."""
    sel = fabriquer()
    out = jouer(sel, 0.0, 10.0, [
        (0.0, marche),
        (1.0, lambda s, t: s.sur_chat_move_bouche("stop", t)),
        (2.0, lambda s, t: s.sur_chat_move_bouche("go", t)),
        (3.0, lambda s, t: s.sur_chat_move_bouche(STOP_DIDIER, t)),
        (3.5, lambda s, t: s.sur_console({"cmd": "stop"}, t)),
        (4.0, lambda s, t: s.sur_console({"cmd": "go"}, t)),
    ])
    assert moves(out) == [(1.0, STOP_DAVID), (2.0, GO_DAVID), (3.0, STOP_DIDIER), (3.5, STOP_DAVID),
                          (4.0, GO_DAVID)]
    assert sel.verrou_david is False


# ================================================================== fatigue (lot S1 : ses initiatives seulement)
def _trois_deplacements(sel):
    evs = [(0.0, marche)]
    for i, t0 in enumerate((1.0, 13.0, 25.0, 37.0)):
        evs.append((t0, lambda s, t: s.sur_chat_move_bouche({"cmd": "avancer", "metres": 1.0}, t)))
        evs.append((t0 + 1.0, lambda s, t: s.sur_route_state("goto", t)))
        evs.append((t0 + 2.0, lambda s, t: s.sur_goto_result({"result": "arrived"}, t)))
    return jouer(sel, 0.0, 45.0, evs)


def test_fatigue_interdit_ses_deplacements_au_dessus_de_0_8():
    sel = fabriquer()
    sel.pulsions.fatigue = 0.81
    assert sel._refus_deplacement(0.0) == "il est fatigué (0,81 > 0,80)"
    assert sel._refus_deplacement(0.0, ordre=True) is None      # un ordre de David passe (S1)
    sel.pulsions.fatigue = 0.8
    assert sel._refus_deplacement(0.0) is None


def test_mutation_seuil_de_fatigue():
    sel = fabriquer({"pulsions.fatigue.seuil_interdit": 1.0})
    sel.pulsions.fatigue = 0.81
    assert sel._refus_deplacement(0.0) is None


def test_ordres_de_la_bouche_comptent_la_fatigue_sans_y_etre_soumis():
    # Retombée coupée : 4 ordres × 0,3 -> fatigue au plafond, et les 4 partent quand même.
    sel = fabriquer({"pulsions.fatigue.retombee_par_s": 0.0})
    out = _trois_deplacements(sel)
    assert [t for t, _ in moves(out)] == [1.0, 13.0, 25.0, 37.0]
    assert sel.pulsions.fatigue == 1.0


# ================================================================== T4 console
def test_ignore_rien_vers_la_piste_pendant_30_s():
    out = jouer(fabriquer(), 0.0, 40.0,
                [(0.1, lambda s, t: s.sur_console({"cmd": "ignore", "cible": "p1"}, t))],
                continu=boite(0.0, 40.0))
    vers_p1 = [t for t, a, c in decisions(out) if c == "p1"]
    assert vers_p1 == [] or vers_p1[0] >= 30.1


def test_mutation_ignore_s():
    out = jouer(fabriquer({"console.ignore_s": 0.0}), 0.0, 5.0,
                [(0.1, lambda s, t: s.sur_console({"cmd": "ignore", "cible": "p1"}, t))],
                continu=boite(0.0, 5.0))
    assert [t for t, a, c in decisions(out) if c == "p1"][0] < 1.0


def test_va_la_objet_demande_aller_voir():
    out = jouer(fabriquer(), 0.0, 3.0, [(0.0, marche),
                                        (1.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "anneaux"}, t))])
    assert moves(out) == [(1.3, {"cmd": "aller_voir", "objet": "anneaux", "id": "carte/anneaux",   # id du tableau (O1)
                                 "origine": "david"})]
    d = journal(out, "decision")[0][1]
    assert d["considerations"]["console"] == 1.0 and d["branche"] == "ordre_macro"


def test_va_la_piste_tourne_puis_avance_1_m():
    out = jouer(fabriquer(), 0.0, 6.0, [
        (0.0, marche),
        (2.5, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "p1"}, t)),
        (3.5, lambda s, t: s.sur_route_state("goto", t)),
        (4.0, lambda s, t: s.sur_goto_result({"result": "arrived"}, t)),
    ], continu=boite(0.0, 6.0, azimut=0.5))
    assert [m for _, m in moves(out)] == [{"cmd": "tourner", "angle_deg": -15.0, "origine": "david"},   # azimut +0,5
                                         {"cmd": "avancer", "metres": 1.0, "origine": "david"}]


def test_va_la_cible_inconnue_refusee():
    out = jouer(fabriquer(), 0.0, 1.0, [(0.0, marche),
                                        (0.5, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "lune"}, t))])
    assert moves(out) == [] and len(journal(out, "refus")) == 1


def test_superviseur_exigeant_absent_aucun_deplacement():
    sel = fabriquer({"superviseur.mode": "exigeant"})
    out = jouer(sel, 0.0, 3.0, [(0.0, marche),
                                (1.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "anneaux"}, t))])
    assert moves(out) == []
    sel2 = fabriquer({"superviseur.mode": "exigeant"})
    out2 = jouer(sel2, 0.0, 3.0, [(0.0, marche),
                                  (1.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "anneaux",
                                                                    "presence": True}, t))])
    assert [m for _, m in moves(out2)] == [{"cmd": "aller_voir", "objet": "anneaux", "id": "carte/anneaux",
                                           "origine": "david"}]


def test_reviens_envoie_go():
    out = jouer(fabriquer(), 0.0, 3.0, [(0.0, marche), (1.0, lambda s, t: s.sur_console({"cmd": "reviens"}, t))])
    assert moves(out) == [(1.3, GO_DAVID)]


# ================================================================== bouche, arbitrage
def test_geste_de_la_bouche_est_un_ordre_parti_a_la_reception():
    """Lot S1 : plus une intention pondérée (offre 0,9, hystérésis 0,3 s) — un ORDRE."""
    out = jouer(fabriquer(), 0.0, 2.0, [(0.0, marche),
                                        (0.5, lambda s, t: s.sur_chat_move_bouche({"cmd": "aller_voir",
                                                                                  "objet": "banc"}, t))])
    assert moves(out) == [(0.5, {"cmd": "aller_voir", "objet": "banc"})]
    assert [p["pourquoi"] for _, p in journal(out, "ordre")] == ["David : aller voir « banc » → il y va tout de suite"]
    assert journal(out, "decision") == []


def test_plus_de_mots_cles_du_metteur_en_scene():
    """Lot S1 : sur_situation / sur_mission supprimés (fragiles, sans identifiant ni retour)."""
    sel = fabriquer()
    assert not hasattr(sel, "sur_situation") and not hasattr(sel, "sur_mission")


def test_pas_d_expression_quand_une_sequence_a_deja_la_main():
    sel = fabriquer()
    sel.sur_animation_state("parle", 0.0)
    assert decisions(jouer(sel, 0.0, 20.0)) == []


def test_intention_jamais_vide():
    sel = fabriquer()
    for t in (0.0, 5.0):
        i = sel.intention(t)
        assert i["action"] and i["pourquoi"]
    out = jouer(sel, 0.0, 30.0, continu=boite(10.0, 20.0))
    for o in out:
        if o[1] == "intention":
            assert o[2]["action"] and o[2]["pourquoi"]
        if o[1] == "journal":
            assert o[3]["pourquoi"].strip()


def test_route_off_par_david_desarme_la_reprise():
    out = jouer(fabriquer(), 0.0, 200.0, [(0.0, marche), (1.0, _poi("anneaux")),
                                          (20.0, lambda s, t: s.sur_route_cause("cmd", t))])
    assert "go" not in [m for _, m in moves(out)]
    assert len(journal(out, "reprise_annulee")) == 1


def test_route_off_par_david_annule_la_lubie_en_attente():
    out = jouer(fabriquer(), 0.0, 8.0, [(0.0, marche), (1.0, _poi("anneaux")),
                                        (2.0, lambda s, t: s.sur_route_cause("cmd", t))])
    assert moves(out) == []
    out2 = jouer(fabriquer(), 0.0, 8.0, [(0.0, marche), (1.0, _poi("anneaux")),
                                         (2.0, lambda s, t: s.sur_route_cause("boot", t))])
    assert moves(out2) == [(4.3, STOP_DIDIER)]


# ================================================================== journal lisible et cohérent (revue point 6)
def test_ligne_de_decision_photographiee_avant_mutation():
    out = jouer(fabriquer(), 0.0, 6.0)
    d = journal(out, "decision")[0][1]
    # Spontanée à 4,0 s : ennui 0,40 AU MOMENT du choix (l'action le remet à 0 ensuite).
    assert d["pulsions"]["ennui"] == 0.4
    assert d["pourquoi"] == "il s'ennuie (0,40) → une expression spontanée « spont-a »"


def test_pourquoi_lisible_par_un_humain():
    out = jouer(fabriquer(), 0.0, 130.0, [(0.0, marche), (1.0, _poi("anneaux")),
                                          (50.0, lambda s, t: s.sur_console({"cmd": "ignore", "cible": "p1"}, t))],
                continu=boite(20.0, 25.0))
    textes = [o[3]["pourquoi"] for o in out if o[1] == "journal"]
    # Valeurs AU MOMENT du choix (0,3 s d'hystérésis après la naissance de l'offre).
    assert "il passe près de « anneaux » (offre 0,72) + lubie (0,48) → réclamer de s'arrêter devant « anneaux »" \
        in textes
    assert "lubie « anneaux » réclamée, regard tourné vers elle, pas de refus en 3 s → il s'arrête" in textes
    assert "une personne, p1 (offre 0,63) + curiosité (0,92) → la regarder" in textes
    assert "David : ignorer p1 pendant 30 s" in textes
    for t in textes:
        assert "animation_state" not in t and "offre(s)" not in t and "poi_event" not in t, t
        assert not any(c.isdigit() and "." in t[i:i + 3] for i, c in enumerate(t)), t   # virgule décimale


# ================================================================== reprise après un SILENCE tiré (David, 02/11 ; S1)
def _reprise(parole_a=None):
    evs = [(0.0, marche), (1.0, _poi("anneaux"))]
    if parole_a is not None:
        evs.append((parole_a, lambda s, t: s.sur_parole("dis donc, tu fais quoi ?", t)))
    out = jouer(fabriquer(pools={}), 0.0, 200.0, evs)
    stop = [t for t, m in moves(out) if m == STOP_DIDIER][0]
    return stop, [t for t, m in moves(out) if m == GO_DIDIER]


def test_parole_a_10_s_repousse_le_go_a_27_1_s_apres():
    stop, gos = _reprise(parole_a=4.3 + 10.0)
    assert stop == pytest.approx(4.3)
    assert gos == [pytest.approx(4.3 + 10.0 + 17.1)]               # pas de go à 21,4 s


def test_sans_parole_le_go_part_au_silence_tire():
    stop, gos = _reprise()
    assert gos == [pytest.approx(4.3 + 17.1)]


# ================================================================== approches bornées (David, 02/11)
def jouer_avec_regisseur(sel, t1, evenements=(), continu=None):
    """Comme jouer(), mais chaque demande de manœuvre (chat_move objet) est
    accusée (route_state goto) au tick suivant et arrivée 1 s après."""
    evs = sorted(evenements, key=lambda e: e[0])
    out, a_faire = [], []
    for i in range(int(round(t1 / 0.1)) + 1):
        t = round(i * 0.1, 6)
        while evs and evs[0][0] <= t + 1e-9:
            evs.pop(0)[1](sel, t)
        for (tt, f) in [x for x in a_faire if x[0] <= t + 1e-9]:
            a_faire.remove((tt, f))
            f(t)
        ecrivain(sel, t)
        if continu is not None:
            continu(sel, t)
        sel.tick(t)
        for so in sel.vider_sorties():
            out.append((t,) + so)
            if so[0] == "chat_move" and isinstance(so[1], dict):
                a_faire.append((t + 0.1, lambda tt: sel.sur_route_state("goto", tt)))
                a_faire.append((t + 1.0, lambda tt: sel.sur_goto_result({"result": "arrived"}, tt)))
    return out


def avancees(out):
    return [t for t, m in moves(out) if isinstance(m, dict) and m.get("cmd") == "avancer"]


def test_va_la_vers_une_piste_trop_proche_refuse():
    out = jouer(fabriquer(), 0.0, 3.0, [(0.0, marche),
                                        (1.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "p1"}, t))],
                continu=boite(0.0, 3.0, hauteur=0.55))
    assert moves(out) == [] and "trop près" in journal(out, "refus")[0][1]["pourquoi"]


def test_joue_avec_approches_repetees_tant_qu_il_est_loin():
    sel = fabriquer({"refractaire_s.deplacement": 0.0, "console.joue_avec_s": 60.0}, pools={})
    out = jouer_avec_regisseur(sel, 40.0, [(0.0, marche),
                                           (1.0, lambda s, t: s.sur_console({"cmd": "joue_avec", "cible": "p1"}, t))],
                               continu=boite(0.0, 40.0, azimut=0.0, hauteur=0.4))
    assert len(avancees(out)) >= 2          # répétées : la console n'est pas un arrêt de Didier
    sel2 = fabriquer({"refractaire_s.deplacement": 0.0, "console.joue_avec_s": 60.0}, pools={})
    out2 = jouer_avec_regisseur(sel2, 40.0, [(0.0, marche),
                                             (1.0, lambda s, t: s.sur_console({"cmd": "joue_avec", "cible": "p1"}, t))],
                                continu=boite(0.0, 40.0, azimut=0.0, hauteur=0.6))
    assert avancees(out2) == []             # jamais au-delà de hauteur_max


def test_mutation_garde_de_distance():
    # (Avant le lot S1, éprouvée par un mot-clé du metteur en scène ; désormais par « joue avec ».)
    sel = fabriquer({"refractaire_s.deplacement": 0.0, "console.joue_avec_s": 60.0, "approche.hauteur_max": 1.0},
                    pools={})
    out = jouer_avec_regisseur(sel, 40.0, [(0.0, marche),
                                           (1.0, lambda s, t: s.sur_console({"cmd": "joue_avec", "cible": "p1"}, t))],
                               continu=boite(0.0, 40.0, azimut=0.0, hauteur=0.6))
    assert avancees(out)


# ================================================================== tout arrêt de Didier compte (revue point 11)
def _bouche_puis_lubie(**surcharges):
    sel = fabriquer(surcharges, pools={})
    return jouer_avec_regisseur(sel, 60.0, [
        (0.0, marche),
        (1.0, lambda s, t: s.sur_chat_move_bouche({"cmd": "aller_voir", "objet": "banc"}, t)),
        # David relance (go console) : la reprise armée tombe, seul le réfractaire commun reste.
        (20.0, lambda s, t: s.sur_console({"cmd": "go"}, t)),
        (20.5, lambda s, t: s.sur_route_state("on", t)),
        (30.0, _poi("anneaux")),
        (45.0, lambda s, t: s.sur_chat_move_bouche({"cmd": "avancer", "metres": 1.0}, t)),
    ])


def test_demande_de_la_bouche_n_est_pas_un_arret_de_didier():
    """DÉCISION DE DAVID (15/11) : une demande de geste de la bouche vient d'un
    humain — ni bloquée par l'arrêt de Didier de 120 s, ni comptée comme tel
    (comme un ordre de la console). Avant : ni la lubie à 30 s ni l'avancer à
    45 s ne partaient. Lot S1 : les gestes de la bouche sont des ORDRES, partis à la
    réception (plus des décisions du score) ; la lubie de 33,3 s arme la reprise
    (2e tirage, 26,3 s), que l'avancer de 45 s fait attendre puis ré-arme."""
    out = _bouche_puis_lubie()
    assert [(t, p["kind"]) for t, p in journal(out, "arret_didier")] == [(33.3, "lubie")]
    assert decisions(out) == [(30.3, "lubie", "anneaux")]
    assert moves(out) == [(1.0, {"cmd": "aller_voir", "objet": "banc"}), (20.0, GO_DAVID), (33.3, STOP_DIDIER),
                          (45.0, {"cmd": "avancer", "metres": 1.0})]


def test_tache_va_voir_l_elephant_puis_tour_du_banc_10_s_apres():
    """Décision de David (15/11) : les deux gestes d'une tâche partent au régisseur."""
    sel = fabriquer(pools={})
    out = jouer_avec_regisseur(sel, 20.0, [
        (0.0, marche),
        (1.0, lambda s, t: s.sur_chat_move_bouche({"cmd": "aller_voir", "objet": "elephant"}, t)),
        (11.0, lambda s, t: s.sur_chat_move_bouche({"cmd": "tour_de", "objet": "banc", "sens": "gauche"}, t)),
    ])
    # Lot S1 : deux ORDRES, chacun parti à la réception (ni réfractaire ni hystérésis).
    assert moves(out) == [(1.0, {"cmd": "aller_voir", "objet": "elephant"}),
                          (11.0, {"cmd": "tour_de", "objet": "banc", "sens": "gauche"})]
    assert journal(out, "refus") == []


def test_lubie_note_si_le_regard_est_parti():
    # Sans tableau (aucun azimut connu), pas de regard.
    sans_pose = jouer(fabriquer(), 0.0, 6.0, [(0.0, lambda s, t: s.sur_route_state("on", t)), (1.0, _poi("anneaux"))])
    a = journal(sans_pose, "arret_didier")[0][1]
    assert a["regard"] is False and [o for o in sans_pose if o[1] == "look"] == []
    avec = jouer(fabriquer(), 0.0, 6.0, [(0.0, marche), (1.0, _poi("anneaux"))])
    looks = [o[0] for o in avec if o[1] == "look"]
    a = journal(avec, "arret_didier")
    assert a[0][1]["regard"] is True and looks and looks[0] <= a[0][0] - 3.0 + 1e-9   # regard >= 3 s avant


def test_ordre_de_david_jamais_bloque_par_un_arret_de_didier():
    """Lubie de Didier (arrêt à 4,3 s), puis David : go et joue avec p1 à 12 s —
    l'approche part malgré les 120 s : un ordre de David n'est pas un arrêt de Didier."""
    sel = fabriquer({"refractaire_s.deplacement": 0.0}, pools={})
    out = jouer_avec_regisseur(sel, 30.0, [
        (0.0, marche), (1.0, _poi("anneaux")),
        (10.0, lambda s, t: s.sur_console({"cmd": "go"}, t)),
        (12.0, lambda s, t: s.sur_console({"cmd": "joue_avec", "cible": "p1"}, t)),
    ], continu=boite(11.0, 30.0, azimut=0.0, hauteur=0.4))
    assert [p["kind"] for _, p in journal(out, "arret_didier")] == ["lubie"]
    assert avancees(out) and avancees(out)[0] < 16.0


# ================================================================== réaction <= 1 s aux offres OBJET (revue point 14)
def test_offre_objet_choix_en_moins_de_1_s():
    out = jouer(fabriquer(), 0.0, 3.0, [(0.0, marche), (1.0, _poi("anneaux"))])
    d = journal(out, "decision")[0]
    assert d[1]["reaction_a"] == ["anneaux"] and d[0] - 1.0 <= 1.0


def test_offre_objet_maintien_en_moins_de_1_s_si_deja_arrete_recemment():
    out = jouer(fabriquer(pools={}), 0.0, 40.0, [(0.0, marche), (1.0, _poi("anneaux")),
                                                 (10.0, lambda s, t: s.sur_console({"cmd": "go"}, t)),
                                                 (20.0, _poi("flaque"))])
    m = [(t, p) for t, p in journal(out, "maintien") if p["reaction_a"] == ["flaque"]]
    assert len(m) == 1 and m[0][0] - 20.0 <= 1.0
    assert m[0][1]["pourquoi"] == ("il continue (rester tranquille) : « flaque », mais il s'est déjà arrêté "
                                   "il y a moins de 120 s")
