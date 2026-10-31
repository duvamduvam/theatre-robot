"""Node `route_driver` × « aller voir » (lot M1, spec-aller-voir.md §2.3-§4)
avec rclpy SIMULÉ — même procédé que test_route_driver_node.py, mais Twist
et Vector3 factices ENREGISTRENT les consignes : c'est la sortie roues
(cmd_vel_follow), gravée ici.

Mutations du lot M1 (doivent rougir) :
  - _abandon_goto sans zéro immédiat -> test_cancel_zero_franc_dans_le_callback
  - route off qui n'abandonne pas la manœuvre -> test_route_off_abandonne_zero_et_cause_cmd
  - ceinture off_by_david retirée -> test_ordre_refuse_si_route_off_par_david
  - rejoin() non appelé au `route on` -> test_go_apres_arrivee_rejoint_le_waypoint_devant
Revue M1 (31/10) :
  - config de la manœuvre non plafonnée par la croisière -> test_manoeuvre_plafonnee_par_la_croisiere
  - ordre répété pour le même objet qui relance -> test_meme_objet_redemande_rien
  - zéro de facteur 0 non publié (créneau rendu) -> test_fader_a_zero_zero_publie_a_chaque_tick
"""
import importlib
import json
import math
import sys
import types

import pytest
import yaml

ROUTE = {"name": "essai", "waypoints": [[0.0, 0.0], [10.0, 0.0], [20.0, 0.0], [30.0, 0.0]], "pois": []}
ORDRE = json.dumps({"name": "anneaux", "x": 12.0, "y": 3.0, "standoff": 1.5})


class _Vector3:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


class _Twist:
    def __init__(self, linear=None, angular=None):
        self.linear = linear or _Vector3()
        self.angular = angular or _Vector3()


class _StringTime:
    def __init__(self, msg="", time=0, anim=False):
        self.msg = msg


class _QoS:
    def __init__(self, depth=10, durability="VOLATILE"):
        self.depth, self.durability = depth, durability


class _Publieur:
    def __init__(self, journal, topic):
        self.journal, self.topic = journal, topic

    def publish(self, msg):
        if isinstance(msg, _Twist):
            self.journal.append((self.topic, (round(msg.linear.x, 6), round(msg.angular.z, 6))))
        else:
            self.journal.append((self.topic, msg.msg))


class _Logs:
    def __init__(self):
        self.lignes = []

    def info(self, texte):
        self.lignes.append(texte)

    warning = error = info


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
def pilote(monkeypatch, tmp_path):
    faux = {
        "rclpy": _module("rclpy"),
        "rclpy.node": _module("rclpy.node", Node=_NodeFactice),
        "rclpy.qos": _module("rclpy.qos", QoSProfile=_QoS,
                             DurabilityPolicy=types.SimpleNamespace(TRANSIENT_LOCAL="TRANSIENT_LOCAL")),
        "robot_interfaces": _module("robot_interfaces"),
        "robot_interfaces.msg": _module("robot_interfaces.msg", StringTime=_StringTime),
        "geometry_msgs": _module("geometry_msgs"),
        "geometry_msgs.msg": _module("geometry_msgs.msg", Twist=_Twist, Vector3=_Vector3),
        "nav_msgs": _module("nav_msgs"),
        "nav_msgs.msg": _module("nav_msgs.msg", Odometry=object),
    }
    for nom, module in faux.items():
        monkeypatch.setitem(sys.modules, nom, module)
    monkeypatch.delitem(sys.modules, "robot_rehearsal.route_driver_node", raising=False)
    module = importlib.import_module("robot_rehearsal.route_driver_node")
    monkeypatch.setenv("ROS_DOMAIN_ID", "43")
    horloge = {"ms": 0}
    monkeypatch.setattr(module, "_now_ms", lambda: horloge["ms"])
    route = tmp_path / "route.yaml"
    route.write_text(yaml.safe_dump(ROUTE), encoding="utf-8")
    monkeypatch.setattr(_NodeFactice, "imposes", {"route_file": str(route), "speed": 1.0})
    noeud = module.RouteDriverNode()
    noeud.horloge = horloge
    yield noeud
    sys.modules.pop("robot_rehearsal.route_driver_node", None)


def _odom(noeud, x, y, yaw, ms):
    noeud.horloge["ms"] = ms
    pose = types.SimpleNamespace(
        position=types.SimpleNamespace(x=x, y=y, z=0.0),
        orientation=types.SimpleNamespace(x=0.0, y=0.0, z=math.sin(yaw / 2), w=math.cos(yaw / 2)))
    noeud.abonnements["/ground_truth/odom"](types.SimpleNamespace(pose=types.SimpleNamespace(pose=pose)))


def _recevoir(noeud, topic, texte):
    noeud.abonnements[topic](_StringTime(msg=texte))


def _tick(noeud, ms):
    noeud.horloge["ms"] = ms
    noeud._tick()


def _twists(noeud):
    return [p for t, p in noeud.publies if t == "cmd_vel_follow"]


def _etats(noeud):
    return [p for t, p in noeud.publies if t == "route_state"]


def _en_route_vers_l_objet(noeud):
    """Route ON, Didier à (5, 0) cap +x ; ordre vers (12, 3) : il pivote."""
    _recevoir(noeud, "route", "on")
    _odom(noeud, 5.0, 0.0, 0.0, 0)
    _tick(noeud, 10)
    noeud.publies.clear()
    _recevoir(noeud, "route_goto", ORDRE)
    _tick(noeud, 20)
    _tick(noeud, 30)


def test_ordre_suspend_le_suivi_et_publie_goto(pilote):
    _en_route_vers_l_objet(pilote)
    # zéro franc du suivi (il roulait à 0,05) PUIS pivot de la manœuvre ; état "goto"
    assert _twists(pilote) == [(0.0, 0.0), (0.0, 0.15), (0.0, 0.3)]
    assert _etats(pilote) == ["goto"]
    assert pilote.follower.enabled is False


def test_cancel_zero_franc_dans_le_callback(pilote):
    _en_route_vers_l_objet(pilote)
    pilote.publies.clear()
    _recevoir(pilote, "route_goto", json.dumps("cancel"))
    assert _twists(pilote) == [(0.0, 0.0)]          # AVANT tout tick
    assert _etats(pilote) == ["off"]
    _tick(pilote, 40)
    assert _twists(pilote) == [(0.0, 0.0)]          # puis silence


def test_route_off_abandonne_zero_et_cause_cmd(pilote):
    _en_route_vers_l_objet(pilote)
    pilote.publies.clear()
    _recevoir(pilote, "route", "off")
    assert pilote.publies == [
        ("route_goto_result", json.dumps({"name": "anneaux", "result": "aborted", "reason": "route_off",
                                          "travelled": 0.0})),
        ("cmd_vel_follow", (0.0, 0.0)), ("route_state_cause", '"cmd"'), ("route_state", "off")]
    assert pilote.goto is None


def test_ordre_refuse_si_route_off_par_david(pilote):
    _recevoir(pilote, "route", "off")
    _odom(pilote, 5.0, 0.0, 0.0, 0)
    pilote.publies.clear()
    _recevoir(pilote, "route_goto", ORDRE)
    _tick(pilote, 10)
    assert pilote.goto is None and pilote.publies == []


def test_ordre_accepte_route_off_au_boot(pilote):
    _odom(pilote, 5.0, 0.0, 0.0, 0)
    _recevoir(pilote, "route_goto", ORDRE)
    assert pilote.goto is not None and _etats(pilote)[-1] == "goto"


@pytest.mark.parametrize("ordre", ['{"name": "x", "x": 1}', '"n\'importe quoi"', "[1, 2]"])
def test_ordre_invalide_ignore(pilote, ordre):
    _recevoir(pilote, "route_goto", ordre)
    assert pilote.goto is None and _etats(pilote) == ["off"]


def test_go_apres_arrivee_rejoint_le_waypoint_devant(pilote):
    _recevoir(pilote, "route", "on")
    _odom(pilote, 25.0, 0.0, 0.0, 0)
    _tick(pilote, 10)
    assert pilote.follower.waypoint_index == 3
    # objet DÉPASSÉ en (12, 3) : on téléporte Didier devant lui, à distance de jeu, face à lui
    _recevoir(pilote, "route_goto", ORDRE)
    _odom(pilote, 12.0, 1.5, math.pi / 2, 20)
    _tick(pilote, 30)
    assert _etats(pilote)[-1] == "arrived" and pilote.goto is None
    _recevoir(pilote, "route", "on")
    assert _etats(pilote)[-1] == "on"
    assert pilote.follower.waypoint_index == 2      # pas l'ancien 3, qui est devant mais plus loin


def test_odometrie_perimee_pendant_la_manoeuvre_zero(pilote):
    _en_route_vers_l_objet(pilote)
    pilote.publies.clear()
    _tick(pilote, 700)                              # dernière pose à 0 ms
    assert _twists(pilote) == [(0.0, 0.0)]
    assert pilote.goto is not None                  # attend, n'abandonne pas


def test_delai_max_abandon_et_etat_off(pilote):
    _en_route_vers_l_objet(pilote)
    _odom(pilote, 5.0, 0.0, 0.0, 60015)
    pilote.publies.clear()
    _tick(pilote, 60021)                            # 60 s après l'ordre (reçu à 10 ms)
    assert _twists(pilote) == [(0.0, 0.0)] and _etats(pilote) == ["off"]
    assert any(l.startswith("goto_abort") and '"timeout"' in l for l in pilote.logs.lignes)


def test_manoeuvre_plafonnee_par_la_croisiere(pilote):
    assert (pilote.goto_config.max_lin, pilote.goto_config.max_ang) == (0.4, 0.6)   # croisière 0,4
    _odom(pilote, 0.0, 0.0, 0.0, 0)
    _recevoir(pilote, "route_goto", json.dumps({"name": "loin", "x": 30.0, "y": 0.0, "standoff": 1.5}))
    lins = []
    for k in range(1, 15):
        _odom(pilote, 0.0, 0.0, 0.0, k * 100 - 50)
        _tick(pilote, k * 100)
        lins.append(_twists(pilote)[-1][0])
    assert max(lins) == 0.4                         # pas 0,5


def test_manoeuvre_plafonnee_par_max_ang_du_node(monkeypatch, tmp_path, pilote):
    module = sys.modules["robot_rehearsal.route_driver_node"]
    monkeypatch.setattr(_NodeFactice, "imposes", dict(_NodeFactice.imposes, max_ang=0.3))
    assert module.RouteDriverNode().goto_config.max_ang == 0.3


def test_meme_objet_redemande_rien(pilote):
    _en_route_vers_l_objet(pilote)
    avant = pilote.goto
    pilote.publies.clear()
    _recevoir(pilote, "route_goto", ORDRE)
    assert pilote.goto is avant and pilote.publies == []   # ni zéro franc, ni état, ni délai remis
    _recevoir(pilote, "route_goto", json.dumps({"name": "flaque", "x": 3.0, "y": 3.0, "standoff": 1.5}))
    assert pilote.goto is not avant and pilote.goto.order.name == "flaque"


def test_fader_a_zero_zero_publie_a_chaque_tick(pilote):
    _recevoir(pilote, "route", "on")
    _odom(pilote, 0.0, 0.0, 1.6, 0)                 # de travers : pivoterait
    _recevoir(pilote, "route_speed", "0")
    _tick(pilote, 10)
    _tick(pilote, 20)
    assert _twists(pilote) == [(0.0, 0.0), (0.0, 0.0)]


def test_issue_publiee_avec_sa_raison(pilote):
    _odom(pilote, 12.0, 1.5, math.pi / 2, 0)
    _recevoir(pilote, "route_goto", ORDRE)
    _tick(pilote, 10)
    assert [p for t, p in pilote.publies if t == "route_goto_result"] == [
        json.dumps({"name": "anneaux", "result": "arrived", "reason": "arrived", "travelled": 0.0})]
