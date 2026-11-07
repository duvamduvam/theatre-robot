"""« Regarder » (topic `look`, lot M2, docs/spec-aller-voir.md §7.1) — logique
PURE (robot.move.gaze_control) puis node gaze_follower avec rclpy SIMULÉ.
Contrat chiffré (décision de David du 31/10) : {"angle_deg", "hold_ms"},
+ = gauche ; compat {"dir"}. Valeurs GRAVÉES à la main (règle du 14/09 : un
test qui recalcule l'attendu avec la fonction testée ne teste rien) :
  course du cou : gain 20 × 180/99 = 36,36° ;
  +20° (gauche) -> azimut −0,55 -> cou 50 − 11 = 39, yeux (gain 49, miroir)
                   50 + 26,95 -> 77 ;
  −20° (droite) -> cou 61, yeux 23 ;   ±90° -> saturé : cou 30 / 70 ;
  sim  : consigne 61 -> (61/99 − 0,5) × π = 0,364932 rad.

Passe de mutation du lot M2 (chaque ligne doit rougir) :
  - update() qui écoute les personnes pendant la tenue -> test_personnes_ignorees_puis_reprise_du_suivi
  - tenue comptée dès l'ordre (pas dès l'arrivée) -> test_tenue_comptee_depuis_l_arrivee
  - set_enabled(False) qui tue le geste -> test_desactiver_le_suivi_ne_coupe_pas_le_geste
  - bornes de tenue retirées -> test_parse_look_tenue_bornee
  - signe de l'angle inversé (+ = droite) -> test_consignes_gravees_cou_et_yeux
  - saturation de l'angle retirée -> test_angle_au_dela_de_la_course_sature
  - garde « animation a la main » retirée de _on_look -> test_node_look_ignore_pendant_une_animation
  - cancel_look retiré de _on_animation_state -> test_node_animation_coupe_le_geste_en_vol
"""
import importlib
import json
import sys
import types

import pytest

from robot.move.gaze_control import (LOOK, LOST, TRACKING, GazeControl, look_course_deg,
                                     parse_look)

COURSE = 20 * 180 / 99      # course du cou au gain validé (36,36°)


# --- décodage --------------------------------------------------------------------

def test_course_du_cou_en_degres():
    assert round(look_course_deg(20), 4) == 36.3636


@pytest.mark.parametrize("raw, attendu", [
    ('{"angle_deg": 20, "hold_ms": 3000}', (-0.55, 3000, False)),
    ('{"angle_deg": -20}', (0.55, 4000, False)),                # tenue absente -> défaut
    ('{"angle_deg": 0, "dir": "gauche"}', (0.0, 4000, False)),  # angle_deg fait foi
    ('{"dir": "droite", "hold_ms": 3000}', (1.0, 3000, False)), # compat : course pleine
    ('{"dir": " Gauche "}', (-1.0, 4000, False)),
    ('"devant"', (0.0, 4000, False)),                           # nom seul, JSON
    ("droite", (1.0, 4000, False)),                             # nom seul, brut
])
def test_parse_look_valide(raw, attendu):
    o = parse_look(raw, COURSE)
    assert (round(o.azimuth, 6), o.hold_ms, o.saturated) == attendu


@pytest.mark.parametrize("angle, azimut", [(90, -1.0), (-90, 1.0), (36.3, -0.99825)])
def test_angle_au_dela_de_la_course_sature(angle, azimut):
    o = parse_look(json.dumps({"angle_deg": angle}), COURSE)
    assert (round(o.azimuth, 5), o.saturated) == (azimut, abs(angle) > 36.37)


@pytest.mark.parametrize("hold, attendu", [
    (200, 1000), (1000, 1000), (8000, 8000), (99999, 8000),        # bornes
    ('"3000"', 4000), ("true", 4000), ("NaN", 4000), ("null", 4000),  # illisible -> défaut
])
def test_parse_look_tenue_bornee(hold, attendu):
    assert parse_look('{"angle_deg": 10, "hold_ms": %s}' % hold, COURSE).hold_ms == attendu


@pytest.mark.parametrize("raw", ['{"dir": "haut"}', '{"hold_ms": 3000}', "42", "[1]", "", '{"dir": 1}',
                                 '{"angle_deg": "20"}', '{"angle_deg": true}', '{"angle_deg": NaN}',
                                 '{"angle_deg": null, "dir": "gauche"}'])
def test_parse_look_refuse(raw):
    assert parse_look(raw, COURSE) is None


# --- logique pure ------------------------------------------------------------------

def _cou(**kw):
    params = dict(center=50, gain=20, direction_sign=1, slew_max=1000, slew_return=1000,
                  ema_alpha=1.0, enabled=False)
    params.update(kw)
    return GazeControl(**params)


def _ordre(angle):
    return parse_look(json.dumps({"angle_deg": angle}), COURSE).azimuth


def test_consignes_gravees_cou_et_yeux():
    for angle, attendu in ((20, 39), (-20, 61), (90, 30), (-90, 70)):
        cou = _cou()
        cou.look(_ordre(angle), 1000, 0)
        assert cou.tick(0) == attendu
    for angle, attendu in ((20, 77), (-20, 23), (90, 99), (-90, 1)):
        yeux = _cou(gain=49, direction_sign=-1)
        yeux.look(_ordre(angle), 1000, 0)
        assert yeux.tick(0) == attendu


def test_azimut_hors_bornes_sans_effet_ceinture():
    cou = _cou()
    cou.look(-3.0, 1000, 0)
    assert cou.tick(0) == 30


def test_devant_publie_le_centre_meme_depuis_le_repos():
    cou = _cou()
    cou.look(0.0, 1000, 0)
    assert cou.tick(0) == 50


def test_suivi_off_tenue_puis_retour_au_centre_puis_silence():
    cou = _cou()
    cou.look(1.0, 1000, 0)
    assert cou.tick(0) == 70                    # arrivée : tenue jusqu'à 1000
    assert cou.tick(500) is None and cou.tick(999) is None
    assert cou.tick(1000) == 50                 # fin de tenue -> centre (slew_return 1000)
    assert cou.looking is False
    assert cou.tick(1100) is None               # suivi OFF : silence


def test_tenue_comptee_depuis_l_arrivee():
    cou = _cou(slew_max=7, slew_return=1)
    cou.look(1.0, 1000, 0)
    assert cou.tick(0) == 57
    assert cou.tick(100) == 64
    assert cou.tick(200) == 70                  # arrivée à 200 -> tenue jusqu'à 1200
    assert cou.tick(1100) is None
    assert cou.tick(1200) == 69                 # retour LENT (slew_return 1)


def test_personnes_ignorees_puis_reprise_du_suivi():
    cou = _cou(enabled=True, slew_return=1)
    cou.update(1.0, 0.0, 1.0, 0)                # suivait quelqu'un à droite
    cou.look(-1.0, 2000, 0)
    assert cou.tick(0) == 30
    cou.update(1.0, 0.0, 1.0, 100)              # la personne est IGNORÉE
    assert cou.tick(200) is None and cou.state == LOOK
    assert cou.tick(2000) == 31                 # fin de tenue : retour lent
    assert cou.state == LOST and cou.looking is True
    cou.update(-0.5, 0.0, 1.0, 2050)            # détection fraîche : le suivi reprend
    assert cou.state == TRACKING and cou.looking is False
    assert cou.tick(2100) == 40                 # 50 + 20 × (−0,5), EMA réamorcée


def test_desactiver_le_suivi_ne_coupe_pas_le_geste():
    cou = _cou(enabled=True)
    cou.look(1.0, 1000, 0)
    assert cou.tick(0) == 70
    cou.set_enabled(False)                      # gaze off, ou repos animation_state republié
    assert cou.state == LOOK and cou.tick(100) is None
    assert cou.tick(1000) == 50                 # le geste va au bout


def test_cancel_look_reset_complet():
    cou = _cou()
    cou.look(1.0, 8000, 0)
    assert cou.tick(0) == 70
    cou.cancel_look()
    assert cou.looking is False and cou.position == 50.0
    assert cou.tick(100) is None


def test_nouvel_ordre_remplace_le_precedent():
    cou = _cou()
    cou.look(1.0, 8000, 0)
    assert cou.tick(0) == 70
    cou.look(-1.0, 1000, 100)
    assert cou.tick(100) == 30


# --- node, rclpy simulé ---------------------------------------------------------------

class _StringTime:
    def __init__(self, msg="", time=0, anim=False):
        self.msg, self.time = msg, time


class _Float64:
    def __init__(self, data=0.0):
        self.data = data


class _Publieur:
    def __init__(self, journal, topic):
        self.journal, self.topic = journal, topic

    def publish(self, msg):
        self.journal.append((self.topic, round(msg.data, 6) if isinstance(msg, _Float64) else msg.msg))


class _Logs:
    def __init__(self):
        self.lignes = []

    def info(self, texte):
        self.lignes.append(texte)

    warn = warning = error = info


class _NodeFactice:
    imposes = {}

    def __init__(self, _nom):
        self.params, self.publies, self.abonnements = {}, [], {}
        self.logs = _Logs()

    def declare_parameter(self, nom, defaut):
        self.params[nom] = self.imposes.get(nom, defaut)

    def get_parameter(self, nom):
        return types.SimpleNamespace(value=self.params[nom])

    def create_publisher(self, _type, topic, _qos):
        return _Publieur(self.publies, topic)

    def create_subscription(self, _type, topic, callback, _qos):
        self.abonnements[topic] = callback

    def create_timer(self, _periode, _callback):
        pass

    def get_logger(self):
        return self.logs


def _module(nom, **attributs):
    module = types.ModuleType(nom)
    module.__dict__.update(attributs)
    return module


@pytest.fixture
def fabrique(monkeypatch):
    faux = {
        "rclpy": _module("rclpy"),
        "rclpy.node": _module("rclpy.node", Node=_NodeFactice),
        "rclpy.qos": _module("rclpy.qos", QoSProfile=lambda **kw: kw,
                             DurabilityPolicy=types.SimpleNamespace(TRANSIENT_LOCAL="TRANSIENT_LOCAL")),
        "theatre_interfaces": _module("theatre_interfaces"),
        "theatre_interfaces.msg": _module("theatre_interfaces.msg", StringTime=_StringTime),
        "geometry_msgs": _module("geometry_msgs"),
        "geometry_msgs.msg": _module("geometry_msgs.msg", PointStamped=object),
        "std_msgs": _module("std_msgs"),
        "std_msgs.msg": _module("std_msgs.msg", Float64=_Float64),
    }
    for nom, module in faux.items():
        monkeypatch.setitem(sys.modules, nom, module)
    monkeypatch.delitem(sys.modules, "robot.nodes.gaze_follower_node", raising=False)
    module = importlib.import_module("robot.nodes.gaze_follower_node")
    horloge = {"ms": 0}
    monkeypatch.setattr(module, "_now_ms", lambda: horloge["ms"])

    def creer(**imposes):
        monkeypatch.setattr(_NodeFactice, "imposes", imposes)
        noeud = module.GazeFollowerNode()
        noeud.horloge = horloge
        return noeud

    yield creer
    sys.modules.pop("robot.nodes.gaze_follower_node", None)


def _recevoir(noeud, topic, texte, time=0):
    noeud.abonnements[topic](_StringTime(msg=texte, time=time))


def _ticks(noeud, debut, fin):
    for ms in range(debut, fin, 100):
        noeud.horloge["ms"] = ms
        noeud._on_tick()


def _dernier(noeud, topic):
    valeurs = [v for t, v in noeud.publies if t == topic]
    return valeurs[-1] if valeurs else None


def test_node_robot_cou_et_yeux(fabrique):
    n = fabrique()                                   # mode robot, suivi OFF (défaut)
    _recevoir(n, "look", json.dumps({"angle_deg": -20, "hold_ms": 1000}))   # 20° à droite
    _ticks(n, 0, 800)                                # cou 1,5/tick : arrivé à 700 ; yeux 8/tick : à 300
    assert (_dernier(n, "neck"), _dernier(n, "left_eye"), _dernier(n, "right_eye")) == ("61", "23", "23")
    _ticks(n, 800, 1400)
    assert _dernier(n, "left_eye") == "26"           # yeux : tenue finie à 1300, retour 3/tick
    n.publies.clear()
    _ticks(n, 1400, 1700)                            # tenue du cou jusqu'à 1700
    assert [v for t, v in n.publies if t == "neck"] == []
    _ticks(n, 1700, 4000)
    assert _dernier(n, "neck") == "50"               # retour au centre, suivi OFF


def test_node_sim_cou_en_radians(fabrique):
    n = fabrique(output_mode="sim")
    _recevoir(n, "look", json.dumps({"angle_deg": -20, "hold_ms": 1000}))
    _ticks(n, 0, 1500)
    # Relatif depuis L1b : /<robot>/neck/position une fois namespacé.
    assert _dernier(n, "neck/position") == 0.364932
    assert {t for t, _ in n.publies} == {"neck/position"}   # pas d'yeux en sim


def test_node_direction_inconnue_rien(fabrique):
    n = fabrique()
    _recevoir(n, "look", json.dumps({"dir": "haut"}))
    _ticks(n, 0, 500)
    assert n.publies == [] and any("illisible" in l for l in n.logs.lignes)


def test_node_angle_sature_journalise(fabrique):
    n = fabrique()
    _recevoir(n, "look", json.dumps({"angle_deg": 90, "hold_ms": 1000}))
    _ticks(n, 0, 1500)
    assert _dernier(n, "neck") == "30"               # course max du cou, pas 90°
    assert any("saturé" in l for l in n.logs.lignes)


def test_node_look_ignore_pendant_une_animation(fabrique):
    n = fabrique()
    _recevoir(n, "animation_state", json.dumps("parle"), time=5000)
    _recevoir(n, "look", json.dumps({"dir": "droite"}))
    _ticks(n, 0, 1000)
    assert n.publies == []


def test_node_animation_coupe_le_geste_en_vol(fabrique):
    n = fabrique()
    _recevoir(n, "look", json.dumps({"dir": "droite", "hold_ms": 8000}))
    _ticks(n, 0, 300)
    _recevoir(n, "animation_state", json.dumps("parle"), time=5000)
    n.publies.clear()
    _ticks(n, 300, 3000)
    assert n.publies == []                            # silence : la séquence a la main


def test_node_repos_republie_ne_coupe_pas_le_geste(fabrique):
    n = fabrique()
    _recevoir(n, "look", json.dumps({"dir": "gauche", "hold_ms": 1000}))   # compat : course pleine
    _ticks(n, 0, 300)
    _recevoir(n, "animation_state", json.dumps(""))  # repos republié
    _ticks(n, 300, 1500)
    assert _dernier(n, "neck") == "30"


# --- revue M2 (31/10) : payloads hostiles, gaze off, flux de look -------------------
# Mutations (doivent rougir) :
#  - parse_look sans le filet d'exceptions -> test_parse_look_payload_hostile_refuse
#  - _on_look sans except Exception -> test_node_look_ne_meurt_jamais
#  - refus gain <= 0 retiré -> test_node_gain_nul_refuse_au_demarrage
#  - cancel_look retiré de « gaze off » -> test_node_gaze_off_coupe_le_geste
#  - limiteur sans coupure de tenue -> test_node_flux_de_look_rend_la_main_au_suivi
#  - limiteur qui ne compte pas -> test_governor_trois_rearmements_puis_verrou_4_s

@pytest.mark.parametrize("raw", [
    '{"angle_deg": 1%s}' % ("0" * 400),                      # OverflowError (isfinite)
    '{"angle_deg": 10, "hold_ms": 1%s}' % ("0" * 400),       # OverflowError (tenue)
    "[" * 100000 + "]" * 100000,                             # RecursionError (json)
    '{"dir": ' + "[" * 100000 + "]" * 100000 + "}",
])
def test_parse_look_payload_hostile_refuse(raw):
    assert parse_look(raw, COURSE) is None


def test_parse_look_course_nulle_refuse():
    assert parse_look('{"angle_deg": 10}', 0.0) is None


def test_governor_trois_rearmements_puis_verrou_4_s():
    from robot.move.gaze_control import LookGovernor
    g = LookGovernor()
    assert [g.decide(True, t) for t in (0, 1, 2)] == ["ok", "ok", "ok"]   # 3 réarmements
    assert g.decide(True, 3) == "limit"                                   # 4e : refusé
    assert g.decide(True, 4002) == "locked" and g.decide(False, 4002) == "locked"
    assert g.decide(True, 4003) == "ok"                                   # verrou levé à 3 + 4000
    h = LookGovernor()
    for t in range(10):
        assert h.decide(False, t) == "ok"          # chaîne finie à chaque fois : jamais de verrou


def test_end_hold_retour_lent():
    cou = _cou(slew_return=1)
    cou.look(1.0, 8000, 0)
    assert cou.tick(0) == 70
    cou.end_hold()
    assert cou.state == LOST and cou.tick(100) == 69


def test_node_look_ne_meurt_jamais(fabrique, monkeypatch):
    n = fabrique()
    module = sys.modules["robot.nodes.gaze_follower_node"]

    def explose(*_a):
        raise KeyError("bug")
    monkeypatch.setattr(module, "parse_look", explose)
    _recevoir(n, "look", '{"angle_deg": 10}')                # ne lève pas
    assert any("KeyError" in l for l in n.logs.lignes)


@pytest.mark.parametrize("raw", ['{"angle_deg": 1%s}' % ("0" * 400), "[" * 100000 + "]" * 100000])
def test_node_payload_hostile_refuse_journalise(fabrique, raw):
    n = fabrique()
    _recevoir(n, "look", raw)
    _ticks(n, 0, 300)
    assert n.publies == [] and any("illisible" in l for l in n.logs.lignes)


@pytest.mark.parametrize("gain", [0, -5])
def test_node_gain_nul_refuse_au_demarrage(fabrique, gain):
    with pytest.raises(ValueError) as exc:
        fabrique(gain=gain)
    assert "gain > 0" in str(exc.value)


def test_node_gaze_off_coupe_le_geste(fabrique):
    n = fabrique()
    _recevoir(n, "gaze", "on")
    _recevoir(n, "look", json.dumps({"angle_deg": 30, "hold_ms": 8000}))
    _ticks(n, 0, 300)
    assert n.gaze.looking is True
    _recevoir(n, "gaze", "off")
    n.publies.clear()
    _ticks(n, 300, 3000)
    assert n.gaze.looking is False and n.publies == []


def test_node_flux_de_look_rend_la_main_au_suivi(fabrique):
    n = fabrique()
    for k, angle in enumerate((30, -30, 30, -30)):            # 1 ordre + 3 réarmements
        _recevoir(n, "look", json.dumps({"angle_deg": angle, "hold_ms": 8000}))
        _ticks(n, k * 500, (k + 1) * 500)
    _recevoir(n, "look", json.dumps({"angle_deg": 30, "hold_ms": 8000}))   # 5e à 2000 ms : refusé
    assert n.gaze.state == LOST                                # tenue coupée : retour au centre
    _ticks(n, 2000, 2500)
    _recevoir(n, "look", json.dumps({"angle_deg": 30, "hold_ms": 8000}))   # verrou jusqu'à 6000
    assert n.gaze.state != LOOK
    assert sum("trop de réarmements" in l for l in n.logs.lignes) == 1
