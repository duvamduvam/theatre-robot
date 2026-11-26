"""Sélecteur × tableau des objets (lot O1, 18/11) — la séance du 15/11 21:29 rejouée.

Scène RÉELLE de l'itinéraire Chantiers, Didier en (14, 0) cap +x : le tableau est celui qu'écrit
didier_perception (valeurs gravées, relevées à la calculette sur config/chantiers.yaml et le
fichier des tours). Le sélecteur ne calcule plus aucune distance : il LIT `atteignable`.

Séance : le LLM a dit « le banc est là, bien en vue » et demandé le tour du banc, accepté à
22 m ; Didier a roulé 22 m le long de la route.

Mutations (doivent rougir) :
  - _hors_atteinte qui rend toujours False -> test_tour_du_banc_a_22_m_refuse_sans_partir
  - « hors_atteinte » et « pas_ici » confondus -> test_poubelle_en_vue_mais_hors_atteinte
  - va_la soumis à atteignable -> test_console_va_la_jamais_bornee_a_10_m
  - regard de lubie sur un azimut recalculé au lieu de celui du tableau -> test_lubie_regarde_l_azimut_du_tableau
Revue O1 (19/11) — péremption (theatre_contrats.objets.PEREMPTION_S = 3 s) :
  - tableau() qui rend le dernier reçu sans regarder son âge      -> test_tableau_perime_plus_de_regard_ni_de_va_la
  - borne > devenue >= (3,0 s pile = encore frais)                 -> test_tableau_frais_jusqu_a_3_s_pile
"""
from conftest import fabriquer

from theatre_contrats.objets import VIDE, Objet, Tableau

from test_selecteur import jouer, journal, moves

BANC = Objet(id="carte/banc", nom="banc", desc="banc en bois", alias=("banc", "banc en bois"), x=36.2, y=2.496,
             distance_m=22.3, azimut_deg=6.4, cote="devant", en_vue=False, tour=True, atteignable=False)
TABLE = Objet(id="carte/table_basse", nom="table_basse", alias=("table basse", "table"), x=17.8, y=2.1,
              distance_m=4.3, azimut_deg=28.9, cote="devant", en_vue=True, tour=True, atteignable=True)
POUBELLE = Objet(id="carte/poubelle_tri", nom="poubelle_tri", alias=("poubelles",), x=27.0, y=2.4,
                 distance_m=13.2, azimut_deg=10.5, cote="devant", en_vue=True, tour=True, atteignable=False)
TABLEAU_X14 = Tableau((TABLE, POUBELLE, BANC))


def scene_x14(s, t):
    s.sur_route_state("on", t)
    s.sur_tableau(TABLEAU_X14, t)


def reponses(out):
    return [(o[0], o[2]) for o in out if o[1] == "chat_move_reply"]


def test_tour_du_banc_a_22_m_refuse_sans_partir():
    tour = {"cmd": "tour_de", "objet": "le banc", "sens": "gauche", "id": "carte/banc"}
    out = jouer(fabriquer(pools={}), 0.0, 5.0, [(0.0, scene_x14), (1.0, lambda s, t: s.sur_chat_move_bouche(tour, t))])
    assert moves(out) == []
    assert reponses(out) == [(1.0, {"demande": tour, "effect": "dropped", "reason": "pas_ici", "source": "jeu",
                                    "distance_m": 22.3, "cote": "devant"})]
    assert [(p["pourquoi"], p["id"]) for _, p in journal(out, "refus")] == [
        ("il voulait faire le tour de « le banc », mais non : « banc » est à 22 m devant toi, hors d'atteinte",
         "carte/banc")]


def test_poubelle_en_vue_mais_hors_atteinte():
    av = {"cmd": "aller_voir", "objet": "poubelles", "id": "carte/poubelle_tri"}
    out = jouer(fabriquer(pools={}), 0.0, 3.0, [(0.0, scene_x14), (1.0, lambda s, t: s.sur_chat_move_bouche(av, t))])
    assert moves(out) == []
    assert reponses(out)[0][1]["reason"] == "hors_atteinte"


def test_aller_voir_table_basse_proche_part():
    av = {"cmd": "aller_voir", "objet": "table_basse", "id": "carte/table_basse"}
    # (jusqu'à 4 s : sans régisseur dans ce banc, le « no_reply » tomberait à 4,1 s)
    out = jouer(fabriquer(pools={}), 0.0, 4.0, [(0.0, scene_x14), (1.0, lambda s, t: s.sur_chat_move_bouche(av, t))])
    assert moves(out) == [(1.0, av)]                  # un ordre : parti à la réception (lot S1)
    assert reponses(out) == []


def test_sans_id_la_regie_juge():
    av = {"cmd": "aller_voir", "objet": "banc"}
    out = jouer(fabriquer(pools={}), 0.0, 4.0, [(0.0, scene_x14), (1.0, lambda s, t: s.sur_chat_move_bouche(av, t))])
    assert moves(out) == [(1.0, av)]


def test_console_va_la_jamais_bornee_a_10_m():
    # Un ordre de DAVID : la cible du tableau, avec son id, même à 22 m (la régie borne à 40 m).
    out = jouer(fabriquer(pools={}), 0.0, 5.0, [(0.0, scene_x14),
                                                (1.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "le banc"}, t))])
    assert moves(out) == [(1.3, {"cmd": "aller_voir", "objet": "banc", "id": "carte/banc", "origine": "david"})]


def test_console_va_la_inconnu_refuse():
    out = jouer(fabriquer(pools={}), 0.0, 2.0, [(0.0, scene_x14),
                                                (1.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "girafe"}, t))])
    assert moves(out) == []
    assert [p["cible"] for _, p in journal(out, "refus")] == ["girafe"]


def test_lubie_regarde_l_azimut_du_tableau():
    out = jouer(fabriquer(), 0.0, 3.0, [(0.0, scene_x14),
                                        (1.0, lambda s, t: s.sur_poi_event({"poi": "table_basse", "event": "enter"}, t))])
    assert [o[2]["angle_deg"] for o in out if o[1] == "look"] == [28.9]


# ================================================================ péremption (revue O1, 19/11)
def test_tableau_perime_plus_de_regard_ni_de_va_la():
    """L'écrivain se tait après t = 0 : à 5 s, la table basse n'existe plus pour le sélecteur —
    ni regard figé sur son azimut de 28,9°, ni « va là » vers elle ; l'oubli est journalisé."""
    evenements = [(0.0, scene_x14),
                  (5.0, lambda s, t: s.sur_poi_event({"poi": "table_basse", "event": "enter"}, t)),
                  (6.0, lambda s, t: s.sur_console({"cmd": "va_la", "cible": "table basse"}, t))]
    mort = jouer(fabriquer(pools={}), 0.0, 8.0, evenements, ecrivain_vivant=False)
    assert [o for o in mort if o[1] == "look"] == []
    assert moves(mort) == []
    assert [(t, p["pourquoi"]) for t, p in journal(mort, "tableau")] == [
        (3.1, "tableau des objets muet depuis plus de 3 s : objets oubliés")]
    # Même scène, écrivain vivant : le regard et l'ordre partent (le test mord sur la péremption).
    vivant = jouer(fabriquer(pools={}), 0.0, 8.0, evenements)
    assert [o[2]["angle_deg"] for o in vivant if o[1] == "look"] == [28.9]


def test_tableau_frais_jusqu_a_3_s_pile():
    s = fabriquer(pools={})
    s.sur_tableau(TABLEAU_X14, 10.0)
    assert s.tableau(13.0) is TABLEAU_X14
    assert s.tableau(13.01) is VIDE
    # Republié : frais de nouveau, et le retour est journalisé.
    s.sur_tableau(TABLEAU_X14, 14.0)
    assert s.tableau(14.0) is TABLEAU_X14
    assert [o[2]["pourquoi"] for o in s.vider_sorties() if o[:2] == ("journal", "tableau")] == [
        "tableau des objets muet depuis plus de 3 s : objets oubliés", "tableau des objets revenu (3 objet(s))"]
