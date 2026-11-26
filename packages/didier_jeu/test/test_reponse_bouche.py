"""Réponse à la bouche (15/11) — toute demande de GESTE de la bouche a une
issue que le chat apprend (rehearsal/chat_move_reply), et un déplacement
refusé n'a pas eu lieu (réfractaires et fatigue rendus). Valeurs et instants
GRAVÉS (ticks de 0,1 s, réglages réels : hystérésis 0,3 s, TTL 3 s,
deplacement_accuse 3 s, réfractaire « deplacement » 10 s).

Séance du 15/11 reproduite : « fais le tour de la grue jaune » refusé par le
régisseur (no_tour), puis « fais le tour de l'éléphant » 10 s plus tard —
le sélecteur journalisait « il y réfléchit » et PLUS RIEN : la demande
mourait au bout de son TTL, bloquée par l'arrêt de Didier (120 s) compté au
refus précédent, sans que le chat le sache.

Lot S1 (25/11) : un geste de la bouche d'origine « david » est un ORDRE, transmis À LA
RÉCEPTION ; plus de demande qui « meurt » au bout de son TTL (supprimé : _bouche_sans_suite et
les codes fatigue / trop_tot / ignore). Il n'est refusé (« dropped ») que sous le verrou de
David, sans superviseur, ou vers un objet hors d'atteinte.

Mutations (doivent rougir) :
  - _rendre_refractaires vidé -> test_refus_rend_refractaires_et_fatigue
  - réponse « no_reply » retirée -> test_regisseur_muet_repond_no_reply_a_4_1_s
  - accusé par la réponse « accepted » retiré -> test_reponse_acceptee_accuse_sans_route_state
"""
import pytest

from conftest import fabriquer

from test_selecteur import STOP_DAVID, journal, jouer, marche, moves

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
    # Les DEUX demandes partent au régisseur, à la réception (avant : l'éléphant mourait en silence).
    assert moves(out) == [(1.0, GRUE), (11.0, ELEPHANT)]
    fins = [(t, p["pourquoi"]) for t, p in journal(out, "fin")]
    assert fins == [
        (1.1, "faire ce qu'il a dit (faire le tour de « grue_jaune ») : le régisseur refuse (no_tour) : "
              "il n'a pas bougé"),
        (11.1, "faire ce qu'il a dit (faire le tour de « elephant ») : le régisseur refuse (no_tour) : "
               "il n'a pas bougé")]
    # Le régisseur a répondu lui-même au chat : le jeu n'ajoute rien.
    assert reponses(out) == []


def test_refus_rend_refractaires_et_fatigue():
    sel = fabriquer(pools={})
    jouer_regisseur(sel, 2.0, [(0.0, marche), (1.0, bouche(GRUE))], refus_no_tour)
    assert sel.derniers == {}                       # ni « deplacement » ni « arret_didier »
    assert sel.pulsions.fatigue == 0.0


def test_ordre_redemande_juste_apres_un_geste_reussi_part_tout_de_suite():
    """Avant le lot S1 : redemandé 6 s après un geste réussi, il mourait « trop_tot » (réfractaire
    « deplacement », 10 s). Un ordre de David n'est plus refusé pour ça : il part à la réception."""
    def arrive(demande):
        return {"demande": demande, "effect": "accepted", "reason": None, "source": "director"}
    sel = fabriquer(pools={})
    evs = [(0.0, marche), (1.0, bouche({"cmd": "aller_voir", "objet": "banc"})),
           (5.0, lambda s, t: s.sur_goto_result({"name": "banc", "result": "arrived"}, t)),
           (7.0, bouche(ELEPHANT))]
    out = jouer_regisseur(sel, 12.0, evs, arrive)
    assert moves(out) == [(1.0, {"cmd": "aller_voir", "objet": "banc"}), (7.0, ELEPHANT)]
    assert reponses(out) == [] and journal(out, "refus") == []


def test_demande_sous_verrou_repond_dropped_arrete():
    out = jouer_regisseur(fabriquer(pools={}), 6.0, [(0.0, marche), (1.0, bouche("stop")), (2.0, bouche(ELEPHANT))],
                          refus_no_tour)
    assert moves(out) == [(1.0, STOP_DAVID)]
    # Refusé À LA RÉCEPTION (avant le lot S1 : au bout du TTL de l'offre, 5,0 s).
    assert reponses(out) == [(2.0, {"demande": ELEPHANT, "effect": "dropped", "reason": "arrete",
                                    "source": "jeu"})]


def test_proposition_de_geste_de_didier_non_retenue_et_dite_au_chat():
    """Une demande de geste d'origine « didier » (aucun producteur en S1 : la bouche ne décide
    aucun mouvement) ne part pas, et le chat le sait (« pas_retenu »)."""
    propo = dict(ELEPHANT, origine="didier")
    out = jouer_regisseur(fabriquer(pools={}), 3.0, [(0.0, marche), (1.0, bouche(propo))], refus_no_tour)
    assert moves(out) == []
    assert reponses(out) == [(1.0, {"demande": propo, "effect": "dropped", "reason": "pas_retenu",
                                    "source": "jeu"})]


def test_regisseur_muet_repond_no_reply_a_4_1_s():
    sel = fabriquer(pools={})
    out = jouer_regisseur(sel, 6.0, [(0.0, marche), (1.0, bouche(ELEPHANT))], lambda d: None)
    assert moves(out) == [(1.0, ELEPHANT)]
    # Parti à 1,0 s ; muet au-delà de durees_s.deplacement_accuse (3 s) -> 4,1 s.
    assert reponses(out) == [(4.1, {"demande": ELEPHANT, "effect": "no_reply", "reason": None,
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
        ("chat_move", STOP_DAVID)]


def test_jeu_node_publie_et_ecoute_la_reponse_au_geste():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "didier_jeu" / "jeu_node.py").read_text(encoding="utf-8")
    assert "self.create_publisher(StringTime, CHAT_MOVE_REPLY_TOPIC, 10)" in src
    assert "self.create_subscription(StringTime, CHAT_MOVE_REPLY_TOPIC, self._json(self.sel.sur_move_reply), 10)" in src




# --- Séance du 15/11 21:21 : nouvelle demande pendant qu'un geste roule ----------------
AV_ELEPHANT = {"cmd": "aller_voir", "objet": "elephant"}


def regisseur_2121(demande):
    """aller_voir accepté (ordre « elephant ») ; tour de l'éléphant refusé (côté Loire)."""
    if demande.get("cmd") == "aller_voir":
        return {"demande": demande, "effect": "accepted", "reason": None, "name": demande["objet"],
                "source": "director"}
    return {"demande": demande, "effect": "no_tour", "reason": None, "name": None, "source": "director"}


def test_seance_2121_tour_pendant_aller_voir_puis_arrivee_de_l_ancien():
    """aller_voir elephant en cours -> « fais le tour de l'éléphant » 10 s après ->
    l'ancien aller_voir arrive. Avant : même clé « bouche:elephant », la demande
    du tour mourait (« autre chose l'a emporté ») et l'arrivée de l'ancien
    finissait « il est arrivé ». Maintenant : le tour INTERROMPT l'aller_voir (le
    plus récent ordre de David, lot S1 : à la réception), part au régisseur, est
    refusé ; l'arrivée de l'ancien ne finit rien."""
    out = jouer_regisseur(fabriquer(pools={}), 16.0, [
        (0.0, marche), (1.0, bouche(AV_ELEPHANT)), (11.0, bouche(ELEPHANT)),
        (13.0, lambda s, t: s.sur_goto_result({"name": "elephant", "result": "arrived", "reason": "arrived",
                                               "travelled": 3.17}, t)),
    ], regisseur_2121)
    assert moves(out) == [(1.0, AV_ELEPHANT), (11.0, ELEPHANT)]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "annulation")] == [
        (11.0, "David demande : faire le tour de « elephant » → il arrête de faire ce "
               "qu'il a dit (aller voir « elephant »)")]
    assert [(t, p["pourquoi"]) for t, p in journal(out, "fin")] == [
        (11.1, "faire ce qu'il a dit (faire le tour de « elephant ») : le régisseur refuse (no_tour) : "
               "il n'a pas bougé")]
    assert journal(out, "refus") == [] and reponses(out) == []


def test_issue_d_un_autre_ordre_ignoree_pendant_l_engagement():
    sel = fabriquer(pools={})
    out = jouer_regisseur(sel, 6.0, [
        (0.0, marche), (1.0, bouche(AV_ELEPHANT)),
        (3.0, lambda s, t: s.sur_goto_result({"name": "tour de banc", "result": "arrived"}, t)),
    ], regisseur_2121)
    assert [(t, p["pourquoi"]) for t, p in journal(out, "issue_ignoree")] == [
        (3.0, "issue de « tour de banc » ignorée : il attend celle de « elephant »")]
    assert journal(out, "fin") == [] and sel.en_cours.etape == AV_ELEPHANT
