"""Lot S2c — « se tourner vers un objet » (spec-S2-le-corps-raconte.md §5).

Vécu corrigé (séance du 25/11) : « regarde l'éléphant à droite » donnait un pivot DEVINÉ de
−90°, qui ne visait pas l'objet. Ici l'angle est CALCULÉ depuis la pose (x, y, cap) et la
position de l'objet ; le LLM ne fait plus que NOMMER.

Mutations du lot (doivent rougir) :
  - angle lu dans l'intention au lieu d'être calculé -> test_l_angle_de_l_intention_est_IGNORE
  - refus « no_pose » retiré (angle deviné sans cap) -> test_sans_pose_fraiche_aucun_angle_devine
  - tolérance « déjà face » retirée -> test_deja_face_ne_fait_pas_pivoter
  - garde « atteignable » appliquée à tourner_vers -> test_garde_se_tourner_vers_objet_lointain
Relecture adverse du 28/11 (une mutation par correction) :
  - B1/B2 : régime « sur place » remis (le pivot ne lève pas l'arrêt) ->
    test_node_lubie_le_pivot_tourne_vraiment[apres_un_stop_de_didier],
    test_node_c1_tourner_vers_de_david_sous_son_arret_meme_regle_que_tourner
  - C2 : garde de finitude retirée -> test_c2_pose_ou_cap_non_finis_no_pose ; garde de la norme
    du quaternion retirée -> test_c2_cap_odometrie_refuse_un_quaternion_abime,
    test_node_c2_quaternion_nul_no_pose_aucun_ordre ; « trop_pres » retiré ->
    test_c2_objet_sous_les_pieds_trop_pres
  - C3 : tolérance « deja_face » gravée EN DUR (10°), plus importée du module testé.
"""
import json
import math
import types

import pytest

from didier_rehearsal.director import cap_odometrie, decide_turn_to
from didier_rehearsal.goto import ARRIVED, GotoManeuver, parse_order
from didier_rehearsal.route import wrap_angle
from theatre_contrats import objets
from theatre_contrats.objets import Objet, Tableau

# Tolérance « déjà face » de la spec S2 §5, GRAVÉE (jamais importée : un test qui relit la
# constante du module la suit dans toutes ses dérives).
TOLERANCE_DEG = 10.0


def tableau(x, y, *, nom="elephant", repere="monde", atteignable=True, distance_m=4.0,
            en_vue=True):
    """`distance_m` / `en_vue` : un objet « ici » au sens du tableau (sinon toute garde le
    refuse « pas_ici », avant même la règle du lot)."""
    return Tableau(objets=(Objet(id="carte/" + nom, nom=nom, x=x, y=y, repere=repere,
                                 atteignable=atteignable, distance_m=distance_m,
                                 en_vue=en_vue),))


INTENT = {"cmd": "tourner_vers", "objet": "elephant", "id": "carte/elephant"}


# ---------------------------------------------------------------- angle CALCULÉ
@pytest.mark.parametrize("ox, oy, yaw_deg, attendu", [
    (3.0, 3.0, 0.0, 45.0),      # Didier cap 0 : l'objet est à +45° (sa GAUCHE)
    (3.0, -3.0, 0.0, -45.0),    # sa droite
    (-5.0, 0.0, 0.0, 180.0),    # pile derrière -> demi-tour
    (0.0, 5.0, 90.0, 0.0),      # il lui fait DÉJÀ face (cap 90 = +y)
    (5.0, 0.0, 180.0, 180.0),   # il lui tourne le dos -> demi-tour aussi
])
def test_angle_calcule_depuis_la_pose(ox, oy, yaw_deg, attendu):
    """|angle| est comparé : un demi-tour vaut +180 ou −180 selon le côté du wrap, c'est le
    MÊME pivot (route_driver intègre la rotation, cf. goto.TurnOrder)."""
    d = decide_turn_to(INTENT, tableau=tableau(ox, oy),
                       pose=(0.0, 0.0, math.radians(yaw_deg)), off_by_david=False)
    assert abs(d.angle_deg) == pytest.approx(abs(attendu), abs=0.05)
    if abs(attendu) not in (0.0, 180.0):
        assert math.copysign(1.0, d.angle_deg) == math.copysign(1.0, attendu)


def test_l_angle_de_l_intention_est_IGNORE():
    """Le LLM ne décide plus de l'angle : même s'il en met un, la régie calcule le sien."""
    intent = dict(INTENT, angle_deg=-90.0, sens="droite")
    d = decide_turn_to(intent, tableau=tableau(3.0, 3.0), pose=(0.0, 0.0, 0.0), off_by_david=False)
    assert d.effect == "accepted"
    assert d.angle_deg == pytest.approx(45.0, abs=0.05)   # et PAS -90


def test_ordre_identique_a_tourner():
    """Même chemin que « tourner » : route_goto reçoit {"turn_rad"}, rien de neuf."""
    d = decide_turn_to(INTENT, tableau=tableau(0.0, 1.0), pose=(0.0, 0.0, 0.0), off_by_david=False)
    assert d.effect == "accepted"
    assert json.loads(d.order)["turn_rad"] == pytest.approx(math.pi / 2)
    assert d.name == "pivot +90°"


# ---------------------------------------------------------------- refus, dans l'ordre
def test_objet_inconnu():
    d = decide_turn_to({"cmd": "tourner_vers", "id": "carte/zzz"}, tableau=tableau(1.0, 1.0),
                       pose=(0.0, 0.0, 0.0), off_by_david=False)
    assert d.effect == "unknown"


def test_objet_sans_position():
    d = decide_turn_to(INTENT, tableau=tableau(None, None), pose=(0.0, 0.0, 0.0), off_by_david=False)
    assert d.effect == "no_position"


def test_route_coupee_par_david_passe_avant_la_pose():
    d = decide_turn_to(INTENT, tableau=tableau(3.0, 3.0), pose=None, off_by_david=True)
    assert d.effect == "route_off_by_david"


def test_sans_pose_fraiche_aucun_angle_devine():
    """LE point du lot : sans cap frais, on ne devine RIEN (on refuse, on ne sature pas)."""
    d = decide_turn_to(INTENT, tableau=tableau(3.0, 3.0), pose=None, off_by_david=False)
    assert d.effect == "no_pose"
    assert d.order is None and d.angle_deg is None


def test_deja_face_ne_fait_pas_pivoter():
    """Sous la tolérance : aucun ordre (un pivot de 2° ne se voit pas et réveille le corps sûr)."""
    petit = math.radians(TOLERANCE_DEG - 1.0)
    d = decide_turn_to(INTENT, tableau=tableau(math.cos(petit) * 5, math.sin(petit) * 5),
                       pose=(0.0, 0.0, 0.0), off_by_david=False)
    assert d.effect == "deja_face"
    assert d.order is None


def test_juste_au_dela_de_la_tolerance_il_pivote():
    grand = math.radians(TOLERANCE_DEG + 1.0)
    d = decide_turn_to(INTENT, tableau=tableau(math.cos(grand) * 5, math.sin(grand) * 5),
                       pose=(0.0, 0.0, 0.0), off_by_david=False)
    assert d.effect == "accepted"


# ---------------------------------------------------------------- C2 : jamais de cap inventé
@pytest.mark.parametrize("pose", [
    (0.0, 0.0, math.nan), (math.nan, 0.0, 0.0), (0.0, math.inf, 0.0),
    (0.0, 0.0, None),          # cap refusé par cap_odometrie (quaternion abîmé)
])
def test_c2_pose_ou_cap_non_finis_no_pose(pose):
    """Avant : un cap NaN publiait {"turn_rad": NaN} (wrap_angle(NaN) = NaN)."""
    d = decide_turn_to(INTENT, tableau=tableau(3.0, 3.0), pose=pose, off_by_david=False)
    assert d.effect == "no_pose"
    assert d.order is None and d.angle_deg is None


def test_c2_objet_a_position_non_finie_no_position():
    d = decide_turn_to(INTENT, tableau=tableau(math.nan, 1.0), pose=(0.0, 0.0, 0.0), off_by_david=False)
    assert d.effect == "no_position" and d.order is None


@pytest.mark.parametrize("q", [
    (0.0, 0.0, 0.0, 0.0),                    # quaternion NUL : atan2(0, 1) donnait un cap de 0
    (0.0, 0.0, 0.0, 2.0),                    # norme 2
    (0.0, 0.0, math.nan, 1.0), (0.0, 0.0, 0.0, math.inf), (0.0, 0.0, 0.0, True),
])
def test_c2_cap_odometrie_refuse_un_quaternion_abime(q):
    assert cap_odometrie(*q) is None


def test_c2_cap_odometrie_d_un_quaternion_unitaire():
    demi = math.radians(90.0) / 2.0
    assert cap_odometrie(0.0, 0.0, math.sin(demi), math.cos(demi)) == pytest.approx(math.pi / 2)
    assert cap_odometrie(0.0, 0.0, 0.0, 1.0) == 0.0


@pytest.mark.parametrize("distance", [0.0, 0.05, 0.29])
def test_c2_objet_sous_les_pieds_trop_pres(distance):
    """Sous 0,3 m du centre, le cap vers l'objet tient au bruit de l'odométrie : refus DIT."""
    d = decide_turn_to(INTENT, tableau=tableau(distance, 0.0), pose=(0.0, 0.0, math.pi), off_by_david=False)
    assert d.effect == "trop_pres" and d.order is None


def test_c2_a_0_31_m_il_pivote():
    d = decide_turn_to(INTENT, tableau=tableau(0.31, 0.0), pose=(0.0, 0.0, math.pi), off_by_david=False)
    assert d.effect == "accepted"


# ---------------------------------------------------------------- garde de la bouche
def test_garde_se_tourner_vers_objet_lointain():
    """« Se tourner vers » ne DÉPLACE pas Didier : la borne « atteignable » (10 m) ne s'y
    applique pas — il peut regarder une grue qu'il n'irait pas voir."""
    t = tableau(30.0, 0.0, atteignable=False, distance_m=30.0, en_vue=True)
    assert objets.garde_geste(t, dict(INTENT)).effect is None
    # ... alors qu'« aller voir » le même objet reste refusé.
    assert objets.garde_geste(t, {"cmd": "aller_voir", "objet": "elephant"}).effect == "dropped"


def test_garde_objet_pas_ici_refuse_quand_meme():
    """On ne se tourne pas vers ce qu'on ne situe pas : « inconnu » reste un refus."""
    t = tableau(3.0, 3.0)
    assert objets.garde_geste(t, {"cmd": "tourner_vers", "objet": "zzz"}).effect == "unknown"


# ================================================================ node (rclpy simulé)
# Banc RÉUTILISÉ de test_director_node.py / test_director_node_goto.py.
from test.unit.test_director_node import (LUBIE, _cmd, _creer, _etat_route, _fader,  # noqa: E402
                                          _journal, _publie, _recevoir, _voice_moves, _voix,
                                          regisseur)  # noqa: F401
from test.unit.test_director_node_goto import _odom, _tableau  # noqa: E402


def _tourner_vers(noeud, objet, cap_deg=0.0, x=0.0, y=0.0):
    """Comme la bouche : le nom est résolu dans le tableau, l'id est joint."""
    r = _tableau(noeud).resoudre(objet)
    intent = {"cmd": "tourner_vers", "objet": objet, "origine": "david"}
    if r.objet is not None:
        intent["id"] = r.objet.id
    _odom(noeud, x, y, cap_deg=cap_deg)
    _recevoir(noeud, "rehearsal/chat_move", json.dumps(intent))
    return intent


def _ordres(noeud):
    return [json.loads(m) for m in _publie(noeud, "route_goto")]


def test_node_tourner_vers_publie_un_pivot_calcule(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _etat_route(n, "on")
    # Didier tourne le DOS au POI (cap 180) : un vrai pivot est nécessaire.
    _tourner_vers(n, n._pois[0].name, cap_deg=180.0)
    journal = [p for t, p in _journal(n) if t == "tourner_vers"]
    assert len(journal) == 1 and journal[0]["effect"] == "accepted"
    assert "angle_deg" in journal[0]           # l'angle CALCULÉ est tracé
    assert len(_ordres(n)) == 1 and "turn_rad" in _ordres(n)[0]


# Ce que le sélecteur publie pour l'arrêt d'une lubie (didier_jeu, test_selecteur.PIVOT_LUBIE),
# GRAVÉ ici : un pivot d'origine « didier », sans « stop » avant.
def PIVOT_LUBIE(noeud, poi):
    return {"cmd": "tourner_vers", "objet": poi, "id": "carte/" + poi, "origine": "didier"}


def _en_seance(noeud, fader="0.6"):
    """Route en marche, séance lancée, fader du boîtier à `fader` (vitesse en vigueur)."""
    _recevoir(noeud, "route", "on")
    _etat_route(noeud, "on")
    _cmd(noeud, "start")
    _fader(noeud, fader)


def _vitesse_route_driver(noeud, fader):
    """Le facteur que route_driver applique : la DERNIÈRE consigne route_speed vue sur le topic —
    celle du régisseur s'il en a publié une après le fader, sinon le fader."""
    publiees = _publie(noeud, "route_speed")
    return float(publiees[-1]) if publiees else float(fader)


def _jouer_le_pivot(ordre, vitesse, cap0):
    """Le VRAI GotoManeuver de route_driver, tické à 10 Hz avec `vitesse`, sur une pose qui suit
    ses consignes. -> (sorties, cap final)."""
    m = GotoManeuver(parse_order(ordre), 0)
    cap, sorties = cap0, []
    for i in range(1, 400):
        t_ms = i * 100
        m.update_pose(0.0, 0.0, cap, t_ms)
        out = m.tick(t_ms, vitesse)
        sorties.append(out)
        cap = wrap_angle(cap + out.ang * 0.1)
        if m.finished:
            break
    return m, sorties, cap


@pytest.mark.parametrize("apres_un_stop_de_didier", [False, True])
def test_node_lubie_le_pivot_tourne_vraiment(regisseur, monkeypatch, tmp_path, apres_un_stop_de_didier):
    """B1 (relecture adverse du 28/11) : la lubie envoyait « stop » puis un pivot « sur place » ;
    route_driver le tenait à facteur 0 (`held`) et RIEN ne tournait. Le pivot de la lubie est
    une manœuvre ordinaire : il part, tourne, et finit ARRIVÉ, face à l'objet. Même derrière un
    arrêt de Didier (une pause « regarde ça ») : il le lève, comme « tourner »."""
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _en_seance(n)
    _tableau(n)
    if apres_un_stop_de_didier:
        _voix(n, {"cmd": "stop", "origine": "didier"})
    _odom(n, 0.0, 0.0, cap_deg=180.0)            # dos au banc (5, 0) : demi-tour
    _voix(n, PIVOT_LUBIE(n, "banc"))
    assert [p["effect"] for t, p in _journal(n) if t == "tourner_vers"] == ["accepted"]
    ordre = _ordres(n)[-1]
    vitesse = _vitesse_route_driver(n, "0.6")
    assert vitesse == pytest.approx(0.6)
    m, sorties, cap = _jouer_le_pivot(ordre, vitesse, math.pi)
    assert sorties[0].reason == "ok" and abs(sorties[0].ang) > 0.0      # PAS « held »
    assert "held" not in {o.reason for o in sorties}
    assert m.phase == ARRIVED                                           # à l'arrêt...
    assert abs(math.degrees(cap)) < 6.0                                 # ... face au banc


def test_node_go_de_reprise_apres_le_pivot_rejoint_la_route(regisseur, monkeypatch, tmp_path):
    """B2 : le « go » de la reprise trouve le pivot ARRIVÉ -> « rejoin », la route repart. Un
    « go » reçu PENDANT le pivot est sans effet (« deja_en_marche ») : c'est pourquoi la reprise
    du sélecteur attend la fin du pivot (didier_jeu, test_s2c_la_reprise_attend_la_fin_du_pivot)
    — et il ne casse rien : le « go » suivant rejoint quand même."""
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _en_seance(n)
    _tableau(n)
    _odom(n, 0.0, 0.0, cap_deg=180.0)
    _voix(n, PIVOT_LUBIE(n, "banc"))
    _etat_route(n, "goto")
    _voix(n, {"cmd": "go", "origine": "didier"}, t=1005.0)             # pendant le pivot
    assert _publie(n, "route") == []                                   # rien ne part
    _etat_route(n, "arrived")
    _voix(n, {"cmd": "go", "origine": "didier"}, t=1010.0)             # la reprise, à l'arrivée
    assert [(m.get("reason") or m["effect"], m.get("rejoin", False)) for m in _voice_moves(n)] == [
        ("deja_en_marche", False), ("rejoin", True)]
    assert _publie(n, "route") == ["on"]                               # la route repart


def test_node_tourner_vers_de_didier_sous_un_arret_de_david_refuse(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _en_seance(n)
    _tableau(n)
    _voix(n, {"cmd": "stop", "origine": "david"})
    _odom(n, 0.0, 0.0, cap_deg=180.0)
    _voix(n, PIVOT_LUBIE(n, "banc"))
    assert [p for t, p in _journal(n) if t == "tourner_vers"] == [
        {"effect": "arret_de_david", "origine": "didier"}]
    assert _ordres(n) == ["cancel"]                                     # celui du stop, rien d'autre
    assert _publie(n, "route_speed") == ["0"]


def test_node_stop_de_david_pendant_le_pivot_l_annule(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _en_seance(n)
    _tableau(n)
    _odom(n, 0.0, 0.0, cap_deg=180.0)
    _voix(n, PIVOT_LUBIE(n, "banc"))
    _etat_route(n, "goto")
    _voix(n, {"cmd": "stop", "origine": "david"})
    assert _ordres(n)[-1] == "cancel"
    assert _publie(n, "route_speed") == ["0"]
    _etat_route(n, "off")
    assert [p for t, p in _journal(n) if t == "goto_cancelled"] == [{"name": "pivot -180°", "by": "stop"}]


def test_node_tourner_vers_de_didier_hors_seance_refuse(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _tableau(n)
    _odom(n, 0.0, 0.0, cap_deg=180.0)
    _voix(n, PIVOT_LUBIE(n, "banc"))
    assert [p["effect"] for t, p in _journal(n) if t == "tourner_vers"] == ["hors_seance"]
    assert _ordres(n) == []


@pytest.mark.parametrize("cmd", ["tourner", "tourner_vers"])
def test_node_c1_tourner_vers_de_david_sous_son_arret_meme_regle_que_tourner(regisseur, monkeypatch,
                                                                           tmp_path, cmd):
    """C1 : sous un arrêt vocal de David, son « tourne-toi vers le banc » était « accepted » mais
    MUET (retenu à facteur 0). Même règle que « tourner » : l'arrêt est levé, le pivot part."""
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _en_seance(n)
    _tableau(n)
    _voix(n, {"cmd": "stop", "origine": "david"})
    _odom(n, 0.0, 0.0, cap_deg=180.0)
    geste = ({"cmd": "tourner", "angle_deg": 180.0} if cmd == "tourner"
             else {"cmd": "tourner_vers", "objet": "banc", "id": "carte/banc"})
    _voix(n, dict(geste, origine="david"))
    assert [p["effect"] for t, p in _journal(n) if t == cmd] == ["accepted"]
    assert [p["by"] for t, p in _journal(n) if t == "voice_hold_released"] == [cmd]
    assert _publie(n, "route_speed") == ["0", "0.6"]                   # la vitesse d'avant l'arrêt
    assert abs(_ordres(n)[-1]["turn_rad"]) == pytest.approx(math.pi)


def _odom_brut(noeud, x, y, q):
    pose = types.SimpleNamespace(position=types.SimpleNamespace(x=x, y=y, z=0.0),
                                 orientation=types.SimpleNamespace(x=q[0], y=q[1], z=q[2], w=q[3]))
    _qos, callback = noeud.abonnements["ground_truth/odom"]
    callback(types.SimpleNamespace(pose=types.SimpleNamespace(pose=pose)))


@pytest.mark.parametrize("x, q", [(0.0, (0.0, 0.0, 0.0, 0.0)), (0.0, (0.0, 0.0, math.nan, 1.0)),
                                  (math.nan, (0.0, 0.0, 0.0, 1.0))])
def test_node_c2_quaternion_nul_no_pose_aucun_ordre(regisseur, monkeypatch, tmp_path, x, q):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _en_seance(n)
    _tableau(n)
    _odom_brut(n, x, 0.0, q)
    _voix(n, PIVOT_LUBIE(n, "banc"))
    assert [p["effect"] for t, p in _journal(n) if t == "tourner_vers"] == ["no_pose"]
    assert _ordres(n) == []


def test_node_tourner_vers_objet_inconnu_rien_ne_part(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _etat_route(n, "on")
    _odom(n, 0.0, 0.0)
    _recevoir(n, "rehearsal/chat_move",
              json.dumps({"cmd": "tourner_vers", "objet": "zzz", "id": "carte/zzz"}))
    assert [p["effect"] for t, p in _journal(n) if t == "tourner_vers"] == ["unknown"]
    assert _ordres(n) == []
