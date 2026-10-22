"""Node `route_driver` (robot_rehearsal.route_driver_node) avec rclpy SIMULÉ —
même procédé que test_director_node.py : rclpy, robot_interfaces,
geometry_msgs et nav_msgs remplacés par des modules factices ; tout le reste
est RÉEL (yaml, route, contracts).

Revue adversariale I1 (22/10, décision D1) : la CAUSE latchée de l'état de
la route (`route_state_cause`, "boot" | "cmd") est ce qui interdit au
régisseur de relancer à la voix contre un `off` de David — quel que soit le
format de ce `off`. Gravé ici, côté producteur."""
import importlib
import json
import sys
import types

import pytest
import yaml

ROUTE = {"name": "essai", "waypoints": [[0.0, 0.0], [20.0, 0.0]], "pois": []}


class _Publieur:
    def __init__(self, journal, topic):
        self.journal = journal
        self.topic = topic

    def publish(self, msg):
        self.journal.append((self.topic, msg.msg if hasattr(msg, "msg") else msg))


class _Logs:
    def info(self, _texte):
        pass

    warning = error = info


class _NodeFactice:
    imposes = {}

    def __init__(self, _nom):
        self.params = {}
        self.publies = []         # [(topic, payload)] dans l'ordre, tous topics confondus
        self.qos_pub = {}
        self.abonnements = {}

    def declare_parameter(self, nom, defaut):
        self.params[nom] = self.imposes.get(nom, defaut)

    def get_parameter(self, nom):
        return types.SimpleNamespace(value=self.params[nom])

    def create_publisher(self, _type, topic, qos):
        self.qos_pub[topic] = qos
        return _Publieur(self.publies, topic)

    def create_subscription(self, _type, topic, callback, _qos):
        self.abonnements[topic] = callback

    def create_timer(self, _periode, _callback):
        pass

    def get_logger(self):
        return _Logs()


class _StringTime:
    def __init__(self, msg="", time=0, anim=False):
        self.msg = msg


class _QoS:
    def __init__(self, depth=10, durability="VOLATILE"):
        self.depth = depth
        self.durability = durability


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
        "geometry_msgs.msg": _module("geometry_msgs.msg", Twist=object, Vector3=object),
        "nav_msgs": _module("nav_msgs"),
        "nav_msgs.msg": _module("nav_msgs.msg", Odometry=object),
    }
    for nom, module in faux.items():
        monkeypatch.setitem(sys.modules, nom, module)
    monkeypatch.delitem(sys.modules, "robot_rehearsal.route_driver_node", raising=False)
    module = importlib.import_module("robot_rehearsal.route_driver_node")
    monkeypatch.setenv("ROS_DOMAIN_ID", "43")
    route = tmp_path / "route.yaml"
    route.write_text(yaml.safe_dump(ROUTE), encoding="utf-8")
    monkeypatch.setattr(_NodeFactice, "imposes", {"route_file": str(route)})
    yield module.RouteDriverNode()
    sys.modules.pop("robot_rehearsal.route_driver_node", None)


def _etat(noeud):
    return [(t, p) for t, p in noeud.publies if t in ("route_state", "route_state_cause")]


def test_au_demarrage_cause_boot_puis_etat_off_latches(pilote):
    assert _etat(pilote) == [("route_state_cause", '"boot"'), ("route_state", "off")]
    for topic in ("route_state", "route_state_cause"):
        assert (pilote.qos_pub[topic].depth, pilote.qos_pub[topic].durability) == (1, "TRANSIENT_LOCAL")


@pytest.mark.parametrize("off", ["off", '"off"', "false", "0", '"0"'])
def test_chaque_extinction_par_commande_publie_cause_cmd(pilote, off):
    pilote.publies.clear()
    pilote.abonnements["route"](_StringTime(msg="on"))
    assert _etat(pilote) == [("route_state", "on")]          # « on » : la cause ne bouge pas
    pilote.abonnements["route"](_StringTime(msg=off))
    pilote.abonnements["route"](_StringTime(msg=off))         # À CHAQUE extinction, même répétée
    assert _etat(pilote)[1:] == [("route_state_cause", '"cmd"'), ("route_state", "off")] * 2


@pytest.mark.parametrize("autre", ["restart", "OFF", "2", "n'importe quoi"])
def test_commande_non_extinction_ne_publie_aucune_cause(pilote, autre):
    pilote.publies.clear()
    pilote.abonnements["route"](_StringTime(msg=autre))
    assert _etat(pilote) == []
