"""Règles du sélecteur (spec A1 §3, §6, §8) — valeurs GRAVÉES en dur, et pour
chaque règle chiffrée une MUTATION (le réglage muté par surcharge) qui prouve
que le test mord : la même scène, règle cassée, viole la propriété.

Horloge simulée : ticks de 0,1 s (tick_s), aucun sleep.
"""
import pytest

from conftest import fabriquer

OBJETS = [{"name": "anneaux", "desc": "bagues", "x": 10.0, "y": 10.0},
          {"name": "flaque", "desc": "eau", "x": 30.0, "y": 0.0}]


def jouer(sel, t0, t1, evenements=None, continu=None, dt=0.1):
    """Ticks de t0 à t1 inclus. evenements : [(t, f(sel, t))] déclenchés juste
    avant le tick de t ; continu : f(sel, t) appelé à chaque tick (boîte de
    personne à 10 Hz). -> [(t, *sortie)]."""
    evs = sorted(evenements or [], key=lambda e: e[0])
    out = []
    n = int(round((t1 - t0) / dt))
    for i in range(n + 1):
        t = round(t0 + i * dt, 6)
        while evs and evs[0][0] <= t + 1e-9:
            evs.pop(0)[1](sel, t)
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
    """Route en marche, objets connus, pose à l'origine cap +x."""
    sel.sur_route_state("on", t)
    sel.sur_objets(OBJETS)
    sel.sur_pose(0.0, 0.0, 0.0)


# ================================================================== T5 arrêt vocal
def test_stop_de_la_bouche_relaye_a_la_reception_sans_tick():
    sel = fabriquer()
    sel.sur_chat_move_bouche("stop", 5.0)
    sorties = sel.vider_sorties()
    # Avant tout tick : le relais est IMMÉDIAT, sans score.
    assert sorties[0] == ("chat_move", "stop")
    assert [s[1] for s in sorties if s[0] == "journal"] == ["relais_stop"]
    assert sel.verrou_stop


def test_verrou_jusqu_au_go_aucun_deplacement():
    sel = fabriquer()
    out = jouer(sel, 0.0, 20.0, [
        (0.0, marche),
        (1.0, lambda s, t: s.sur_chat_move_bouche("stop", t)),
        (2.0, lambda s, t: s.sur_chat_move_bouche({"cmd": "avancer", "metres": 1.0}, t)),
        (3.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "anneaux"}, t)),
        (15.0, lambda s, t: s.sur_console({"cmd": "go"}, t)),
    ])
    assert moves(out) == [(1.0, "stop"), (15.0, "go")]
    assert [p["source"] for _, p in journal(out, "relais_go")] == ["console"]
    assert any("arrêté jusqu'au go" in p["pourquoi"] for _, p in journal(out, "refus"))


# ================================================================== T1 jamais deux changements < 2 s
def _scene_rupture(sel):
    # Piste née à 0 -> regarder ; la bouche (0,9 >= seuil de rupture) demande à 0,5.
    return jouer(sel, 0.0, 6.0, [(0.0, marche),
                                 (0.5, lambda s, t: s.sur_chat_move_bouche({"cmd": "avancer", "metres": 1.0}, t))],
                 continu=boite(0.0, 6.0))


def test_deux_decisions_differentes_jamais_a_moins_de_2_s():
    d = decisions(_scene_rupture(fabriquer()))
    assert [a for _, a, _ in d] == ["regarder", "bouche"]
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
    assert len(m) == 1 and m[0][1]["reaction_a"] == "p1"
    assert m[0][0] - 5.0 == pytest.approx(0.6) and m[0][0] - 5.0 <= 1.0
    assert m[0][1]["pourquoi"] == ("il continue (une expression spontanée) : la nouvelle offre (0,70) "
                                   "ne suffit pas à l'interrompre (il faut 0,90)")


def test_naissance_de_piste_libre_donne_un_choix_en_moins_de_1_s():
    out = jouer(fabriquer(), 0.0, 2.0, continu=boite(0.0, 2.0))
    d = journal(out, "decision")
    assert d[0][1]["reaction_a"] == "p1" and d[0][0] <= 1.0
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
    assert moves(out) == [(4.3, "stop")]                                 # 3 s après l'intention
    assert [p["cible"] for _, p in journal(out, "arret_didier")] == ["anneaux"]


@pytest.mark.parametrize("ordre", [{"cmd": "ignore"}, {"cmd": "ignore", "cible": "anneaux"},
                                   {"cmd": "va_la", "cible": "flaque"}])
def test_lubie_refusee_par_la_console_dans_les_3_s(ordre):
    out = jouer(fabriquer(), 0.0, 8.0, [(0.0, marche), (1.0, _poi("anneaux")),
                                        (2.5, lambda s, t: s.sur_console(ordre, t))])
    assert "stop" not in [m for _, m in moves(out)]
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
    return jouer(sel, 0.0, 140.0, [(0.0, marche), (1.0, _poi("anneaux")),
                                   # la route reprend (go de Didier à ~94 s) : nouveau POI à 100 s
                                   (95.0, lambda s, t: s.sur_route_state("on", t)),
                                   (100.0, _poi("flaque")), (125.0, _poi("flaque"))])


def test_arrets_de_didier_espaces_de_120_s():
    out = _deux_lubies(fabriquer())
    arrets = [t for t, _ in journal(out, "arret_didier")]
    assert arrets[0] == pytest.approx(4.3)
    assert all(b - a >= 120.0 for a, b in zip(arrets, arrets[1:]))
    assert len(arrets) == 2 and arrets[1] == pytest.approx(128.3)


def test_mutation_refractaire_arret_didier():
    out = _deux_lubies(fabriquer({"refractaire_s.arret_didier": 0.0}))
    arrets = [t for t, _ in journal(out, "arret_didier")]
    assert any(b - a < 120.0 for a, b in zip(arrets, arrets[1:]))


# ================================================================== reprise 90 s
def test_reprise_go_de_didier_90_s_apres_son_arret():
    out = jouer(fabriquer(), 0.0, 100.0, [(0.0, marche), (1.0, _poi("anneaux"))])
    gos = [t for t, m in moves(out) if m == "go"]
    # Stop à 4,3 s -> pression de route à 1 à 94,3 s. Gravé : 99,6 s, parce que
    # (a) l'expression spontanée de 91,3 s est ENGAGÉE jusqu'à 97,3 s (4 + 2 s)
    # et se finit ; (b) la reprise est elle-même une initiative SPONTANÉE (ni
    # offre ni console) : 8 s après celle de 91,3 s -> 99,3 s, + 0,3 s d'hystérésis.
    assert gos == [pytest.approx(99.6)]
    assert gos[0] - 4.3 >= 90.0
    acts = [d[1] for d in decisions(out)]
    assert acts[0] == "lubie" and acts[-1] == "repartir" and set(acts[1:-1]) == {"spontanee"}
    # Pendant l'arrêt, l'intention propose de repartir.
    assert any(o[2].get("proposition") == "repartir ?" for o in out if o[1] == "intention")


def test_mutation_delai_de_reprise():
    out = jouer(fabriquer({"reprise.delai_s": 10.0}), 0.0, 100.0, [(0.0, marche), (1.0, _poi("anneaux"))])
    assert [t for t, m in moves(out) if m == "go"][0] < 20.0


@pytest.mark.parametrize("ordre", [{"cmd": "stop"}, {"cmd": "ignore"}])
def test_pas_de_go_automatique_apres_stop_ou_ignore_de_la_console(ordre):
    out = jouer(fabriquer(), 0.0, 300.0, [(0.0, marche), (1.0, _poi("anneaux")),
                                          (30.0, lambda s, t: s.sur_console(ordre, t))])
    assert "go" not in [m for _, m in moves(out)]
    # Et il ne PROPOSE plus de repartir : la décision est à David.
    assert not any(o[2].get("proposition") for o in out if o[1] == "intention" and o[0] >= 30.0)


def test_jamais_de_go_automatique_apres_un_stop_de_la_bouche():
    out = jouer(fabriquer(), 0.0, 300.0, [(0.0, marche), (1.0, lambda s, t: s.sur_chat_move_bouche("stop", t))])
    assert moves(out) == [(1.0, "stop")]


def test_jamais_de_go_automatique_apres_un_stop_de_david():
    # Stop de la CONSOLE (David) après une lubie : ni reprise, ni go, 300 s durant.
    out = jouer(fabriquer(), 0.0, 300.0, [(0.0, marche), (1.0, _poi("anneaux")),
                                          (10.0, lambda s, t: s.sur_console({"cmd": "stop"}, t))])
    assert moves(out) == [(4.3, "stop"), (10.0, "stop")]


def test_go_de_la_bouche_ne_leve_pas_un_stop_de_david():
    out = jouer(fabriquer(), 0.0, 20.0, [
        (0.0, marche),
        (1.0, lambda s, t: s.sur_console({"cmd": "stop"}, t)),
        (5.0, lambda s, t: s.sur_chat_move_bouche("go", t)),
        (8.0, lambda s, t: s.sur_chat_move_bouche({"cmd": "avancer", "metres": 1.0}, t)),
    ])
    assert moves(out) == [(1.0, "stop")]                    # rien ne part
    assert any("David" in p["pourquoi"] for _, p in journal(out, "refus"))


def test_go_de_la_bouche_leve_le_stop_de_la_bouche_et_console_leve_tout():
    out = jouer(fabriquer(), 0.0, 10.0, [
        (0.0, marche),
        (1.0, lambda s, t: s.sur_chat_move_bouche("stop", t)),
        (2.0, lambda s, t: s.sur_chat_move_bouche("go", t)),
        (3.0, lambda s, t: s.sur_chat_move_bouche("stop", t)),
        (3.5, lambda s, t: s.sur_console({"cmd": "stop"}, t)),
        (4.0, lambda s, t: s.sur_console({"cmd": "go"}, t)),
    ])
    assert moves(out) == [(1.0, "stop"), (2.0, "go"), (3.0, "stop"), (3.5, "stop"), (4.0, "go")]


# ================================================================== fatigue
def _trois_deplacements(sel):
    evs = [(0.0, marche)]
    for i, t0 in enumerate((1.0, 13.0, 25.0, 37.0)):
        evs.append((t0, lambda s, t: s.sur_chat_move_bouche({"cmd": "avancer", "metres": 1.0}, t)))
        evs.append((t0 + 1.0, lambda s, t: s.sur_route_state("goto", t)))
        evs.append((t0 + 2.0, lambda s, t: s.sur_goto_result({"result": "arrived"}, t)))
    return jouer(sel, 0.0, 45.0, evs)


def test_fatigue_interdit_le_deplacement_au_dessus_de_0_8():
    # Retombée coupée pour isoler la règle : 3 déplacements × 0,3 = 0,9 > 0,8,
    # la 4e demande (37 s) est refusée.
    sel = fabriquer({"pulsions.fatigue.retombee_par_s": 0.0, "refractaire_s.deplacement": 0.0})
    out = _trois_deplacements(sel)
    assert len([m for _, m in moves(out)]) == 3          # la 4e est refusée (fatigue 0,9 > 0,8)


def test_mutation_seuil_de_fatigue():
    sel = fabriquer({"pulsions.fatigue.retombee_par_s": 0.0, "refractaire_s.deplacement": 0.0,
                     "pulsions.fatigue.seuil_interdit": 1.0})
    assert len(moves(_trois_deplacements(sel))) == 4


def test_fatigue_retombe_avec_les_valeurs_gravees():
    # Valeurs gravées (retombée 0,05/s) : 12 s entre deux -> 0,3 − 0,6 < 0 : jamais interdit.
    out = _trois_deplacements(fabriquer({"refractaire_s.deplacement": 0.0}))
    assert len(moves(out)) == 4


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
    assert moves(out) == [(1.3, {"cmd": "aller_voir", "objet": "anneaux"})]
    d = journal(out, "decision")[0][1]
    assert d["considerations"]["console"] == 1.0 and d["branche"] == "ordre_macro"


def test_va_la_piste_tourne_puis_avance_1_m():
    out = jouer(fabriquer(), 0.0, 6.0, [
        (0.0, marche),
        (2.5, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "p1"}, t)),
        (3.5, lambda s, t: s.sur_route_state("goto", t)),
        (4.0, lambda s, t: s.sur_goto_result({"result": "arrived"}, t)),
    ], continu=boite(0.0, 6.0, azimut=0.5))
    assert [m for _, m in moves(out)] == [{"cmd": "tourner", "angle_deg": -15.0},   # azimut +0,5 = droite
                                         {"cmd": "avancer", "metres": 1.0}]


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
    assert [m for _, m in moves(out2)] == [{"cmd": "aller_voir", "objet": "anneaux"}]


def test_reviens_envoie_go():
    out = jouer(fabriquer(), 0.0, 3.0, [(0.0, marche), (1.0, lambda s, t: s.sur_console({"cmd": "reviens"}, t))])
    assert moves(out) == [(1.3, "go")]


# ================================================================== bouche, metteur en scène, arbitrage
def test_bouche_aller_voir_devient_une_intention_ponderee():
    out = jouer(fabriquer(), 0.0, 2.0, [(0.0, marche),
                                        (0.5, lambda s, t: s.sur_chat_move_bouche({"cmd": "aller_voir",
                                                                                  "objet": "flaque"}, t))])
    assert moves(out) == [(0.8, {"cmd": "aller_voir", "objet": "flaque"})]
    assert journal(out, "decision")[0][1]["action"] == "bouche"


def test_metteur_en_scene_mot_cle():
    sel = fabriquer()
    sel.sur_situation("Didier, approche-toi doucement de lui", 0.0)
    assert sel.metteur["action"] == "approcher"
    sel.sur_mission({"indication": "Regarde la grue"}, 1.0)
    assert sel.metteur["action"] == "regarder"


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
    assert moves(out2) == [(4.3, "stop")]


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
    assert "lubie « anneaux » réclamée, pas de refus en 3 s → il s'arrête" in textes
    assert "une personne, p1 (offre 0,63) + curiosité (0,92) → la regarder" in textes
    assert "David : ignorer p1 pendant 30 s" in textes
    for t in textes:
        assert "animation_state" not in t and "offre(s)" not in t and "poi_event" not in t, t
        assert not any(c.isdigit() and "." in t[i:i + 3] for i, c in enumerate(t)), t   # virgule décimale


# ================================================================== reprise après 90 s de SILENCE (David, 02/11)
def _reprise(parole_a=None):
    evs = [(0.0, marche), (1.0, _poi("anneaux"))]
    if parole_a is not None:
        evs.append((parole_a, lambda s, t: s.sur_parole("dis donc, tu fais quoi ?", t)))
    # Sans expressions (pools vides) : la reprise n'est retardée par rien d'autre.
    out = jouer(fabriquer(pools={}), 0.0, 200.0, evs)
    stop = [t for t, m in moves(out) if m == "stop"][0]
    return stop, [t for t, m in moves(out) if m == "go"]


def test_parole_a_80_s_repousse_le_go_a_170_s():
    stop, gos = _reprise(parole_a=4.3 + 80.0)
    assert stop == pytest.approx(4.3)
    assert not [g for g in gos if g < stop + 170.0 - 1e-6]          # pas de go à 90 s
    assert len(gos) == 1 and stop + 170.0 <= gos[0] <= stop + 170.0 + 0.5   # go à 170 s (+ hystérésis)


def test_sans_parole_le_go_part_a_90_s():
    stop, gos = _reprise()
    assert len(gos) == 1 and stop + 90.0 <= gos[0] <= stop + 90.5
