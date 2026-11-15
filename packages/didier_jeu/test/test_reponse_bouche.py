"""Réponse à la bouche (15/11) — toute demande de GESTE de la bouche a une
issue que le chat apprend (rehearsal/chat_move_reply), et un déplacement
refusé n'a pas eu lieu (réfractaires et fatigue rendus). Valeurs et instants
GRAVÉS (ticks de 0,1 s, réglages réels : hystérésis 0,3 s, TTL 3 s,
deplacement_accuse 3 s, arrêt de Didier 120 s).

Séance du 15/11 reproduite : « fais le tour de la grue jaune » refusé par le
régisseur (no_tour), puis « fais le tour de l'éléphant » 10 s plus tard —
le sélecteur journalisait « il y réfléchit » et PLUS RIEN : la demande
mourait au bout de son TTL, bloquée par l'arrêt de Didier (120 s) compté au
refus précédent, sans que le chat le sache.

Mutations (doivent rougir) :
  - _rendre_refractaires vidé -> test_seance_du_15_11_elephant_transmis_apres_un_refus
  - _bouche_sans_suite vidé -> test_demande_morte_repond_dropped_trop_tot
  - réponse « no_reply » retirée -> test_regisseur_muet_repond_no_reply_a_4_4_s
  - accusé par la réponse « accepted » retiré -> test_reponse_acceptee_accuse_sans_route_state
"""
import pytest

from conftest import fabriquer

from test_selecteur import OBJETS, journal, jouer, marche, moves

GRUE = {"cmd": "tour_de", "objet": "grue_jaune", "sens": "gauche"}
ELEPHANT = {"cmd": "tour_de", "objet": "elephant", "sens": "gauche"}


def reponses(out):
    return [(o[0], o[2]) for o in out if o[1] == "chat_move_reply"]


def jouer_regisseur(sel, t1, evenements, effet):
    """Ticks de 0 à t1 ; le RÉGISSEUR factice répond `effet(demande)` (dict de
    réponse, ou None = muet) au tick suivant chaque chat_move objet."""
    evs = sorted(evenements, key=lambda e: e[0])
    out, a_faire = [], []
    for i in range(int(round(t1 / 0.1)) + 1):
        t = round(i * 0.1, 6)
        while evs and evs[0][0] <= t + 1e-9:
            evs.pop(0)[1](sel, t)
        for tt, rep in [x for x in a_faire if x[0] <= t + 1e-9]:
            a_faire.remove((tt, rep))
            sel.sur_move_reply(rep, t)
        sel.tick(t)
        for so in sel.vider_sorties():
            out.append((t,) + so)
            if so[0] == "chat_move" and isinstance(so[1], dict):
                rep = effet(so[1])
                if rep is not None:
                    a_faire.append((t + 0.1, rep))
    return out


def refus_no_tour(demande):
    return {"demande": demande, "effect": "no_tour", "reason": None, "source": "director"}


def bouche(demande):
    return lambda s, t: s.sur_chat_move_bouche(demande, t)


def test_seance_du_15_11_elephant_transmis_apres_un_refus():
    out = jouer_regisseur(fabriquer(pools={}), 20.0, [(0.0, marche), (1.0, bouche(GRUE)), (11.0, bouche(ELEPHANT))],
                          refus_no_tour)
    # Les DEUX demandes partent au régisseur (avant : l'éléphant mourait en silence).
    assert moves(out) == [(1.3, GRUE), (11.3, ELEPHANT)]
    fins = [(t, p["pourquoi"]) for t, p in journal(out, "fin")]
    assert fins == [
        (1.4, "faire ce qu'il a dit (faire le tour de « grue_jaune ») : le régisseur refuse (no_tour) : "
              "il n'a pas bougé"),
        (11.4, "faire ce qu'il a dit (faire le tour de « elephant ») : le régisseur refuse (no_tour) : "
               "il n'a pas bougé")]
    # Le régisseur a répondu lui-même au chat : le jeu n'ajoute rien.
    assert reponses(out) == []


def test_refus_rend_refractaires_et_fatigue():
    sel = fabriquer(pools={})
    jouer_regisseur(sel, 2.0, [(0.0, marche), (1.0, bouche(GRUE))], refus_no_tour)
    assert sel.derniers == {}                       # ni « deplacement » ni « arret_didier »
    assert sel.pulsions.fatigue == 0.0


def test_demande_morte_repond_dropped_trop_tot():
    """Après un geste RÉUSSI, la bouche redemande avant 120 s : non transmise,
    et le chat le sait (code trop_tot) au tick où l'offre meurt (TTL 3 s)."""
    def arrive(demande):
        return {"demande": demande, "effect": "accepted", "reason": None, "source": "director"}
    sel = fabriquer(pools={})
    evs = [(0.0, marche), (1.0, bouche({"cmd": "aller_voir", "objet": "flaque"})),
           (5.0, lambda s, t: s.sur_goto_result({"name": "flaque", "result": "arrived"}, t)),
           (20.0, bouche(ELEPHANT))]
    out = jouer_regisseur(sel, 25.0, evs, arrive)
    assert moves(out) == [(1.3, {"cmd": "aller_voir", "objet": "flaque"})]
    assert reponses(out) == [(23.0, {"demande": ELEPHANT, "effect": "dropped", "reason": "trop_tot",
                                     "source": "jeu"})]
    refus = [(t, p["pourquoi"], p["code"]) for t, p in journal(out, "refus")]
    # 20 s après l'arrivée : le déplacement (10 s) est passé, pas l'arrêt de Didier (120 s).
    assert refus == [(23.0, "il voulait faire le tour de « elephant », mais non : il s'est déjà arrêté "
                            "de lui-même il y a moins de 120 s", "trop_tot")]


def test_demande_sous_verrou_repond_dropped_arrete():
    out = jouer_regisseur(fabriquer(pools={}), 6.0, [(0.0, marche), (1.0, bouche("stop")), (2.0, bouche(ELEPHANT))],
                          refus_no_tour)
    assert moves(out) == [(1.0, "stop")]
    assert reponses(out) == [(5.0, {"demande": ELEPHANT, "effect": "dropped", "reason": "arrete",
                                    "source": "jeu"})]


def test_regisseur_muet_repond_no_reply_a_4_4_s():
    sel = fabriquer(pools={})
    out = jouer_regisseur(sel, 6.0, [(0.0, marche), (1.0, bouche(ELEPHANT))], lambda d: None)
    assert moves(out) == [(1.3, ELEPHANT)]
    assert reponses(out) == [(4.4, {"demande": ELEPHANT, "effect": "no_reply", "reason": None,
                                    "source": "jeu"})]
    assert sel.derniers == {} and sel.pulsions.fatigue == 0.0     # il n'a pas bougé


def test_reponse_acceptee_accuse_sans_route_state():
    def accepte(demande):
        return {"demande": demande, "effect": "accepted", "reason": None, "source": "director"}
    sel = fabriquer(pools={})
    out = jouer_regisseur(sel, 10.0, [(0.0, marche), (1.0, bouche(ELEPHANT))], accepte)
    assert journal(out, "fin") == [] and reponses(out) == []      # pas de faux « sans suite »
    assert sel.en_cours is not None and sel.en_cours.accuse is True


@pytest.mark.parametrize("rep", [
    {"demande": ELEPHANT, "effect": "dropped", "reason": "trop_tot", "source": "jeu"},   # notre propre écho
    {"demande": GRUE, "effect": "no_tour", "reason": None, "source": "director"},        # pas l'étape en cours
    "illisible",
])
def test_reponse_etrangere_ignoree(rep):
    sel = fabriquer(pools={})
    jouer(sel, 0.0, 1.5, [(0.0, marche), (1.0, bouche(ELEPHANT))])
    sel.sur_move_reply(rep, 1.6)
    assert sel.en_cours is not None and sel.en_cours.etape == ELEPHANT
    assert sel.vider_sorties() == []


def test_go_de_la_bouche_jamais_de_reponse():
    out = jouer(fabriquer(pools={}), 0.0, 6.0, [(0.0, marche), (1.0, bouche("stop")), (2.0, bouche("go")),
                                        (3.0, bouche("go"))])
    assert reponses(out) == []


def test_reponse_bouche_code_inconnu_refuse():
    from didier_jeu.relais import reponse_bouche
    with pytest.raises(ValueError):
        reponse_bouche(ELEPHANT, "dropped", "lune")
    assert reponse_bouche(ELEPHANT, "no_reply", None) == {"demande": ELEPHANT, "effect": "no_reply",
                                                          "reason": None, "source": "jeu"}


def test_relais_seul_repond_dropped_degrade():
    from didier_jeu.relais import RelaisSeul
    r = RelaisSeul("x")
    r.vider_sorties()
    r.sur_chat_move_bouche(ELEPHANT, 1.0)
    r.sur_chat_move_bouche("stop", 1.1)
    assert [s for s in r.vider_sorties() if s[0] != "journal"] == [
        ("chat_move_reply", {"demande": ELEPHANT, "effect": "dropped", "reason": "degrade", "source": "jeu"}),
        ("chat_move", "stop")]


def test_jeu_node_publie_et_ecoute_la_reponse_au_geste():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "didier_jeu" / "jeu_node.py").read_text(encoding="utf-8")
    assert "self.create_publisher(StringTime, CHAT_MOVE_REPLY_TOPIC, 10)" in src
    assert "self.create_subscription(StringTime, CHAT_MOVE_REPLY_TOPIC, self._json(self.sel.sur_move_reply), 10)" in src


def test_objets_sans_effet_sur_la_liste():
    # Garde du banc : OBJETS de test_selecteur (sans « tour ») restent lisibles.
    sel = fabriquer(pools={})
    sel.sur_objets(OBJETS + [{"name": "elephant", "desc": "statue", "x": 1.0, "y": 2.0, "tour": False}])
    assert sel.objets["elephant"] == (1.0, 2.0)
