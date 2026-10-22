"""Node `director` (robot_rehearsal.director_node) avec rclpy SIMULÉ — même
procédé que le pont web (test_web_protocol.py, fixture `pont`) : rclpy et
robot_interfaces remplacés par des modules factices dans sys.modules ; tout le
reste est RÉEL (yaml, robot.diagnostic.journal, scenario, director, route,
process_faults). Aucun skip : le node n'importe rien d'autre.

Horloge : le `time` du module est remplacé (monotonic piloté par le test) ;
`find_pids` est neutralisé (jamais de pgrep). Le journal JSONL est relu sur
disque : c'est la frise du débrief, ce qu'il dit est gravé ici.

Le factice ne renvoie pas au node ses propres publications : `_echos()` le
fait explicitement (un vrai node ROS les reçoit — c'est tout le piège de la
fermeture au fader).

Revue adversariale R3 (2026-10-14) — mutations listées dans le rapport du lot.
"""
import importlib
import json
import sys
import types

import pytest
import yaml

LUBIE_BANC = "Un banc : tu veux t'asseoir. Tu n'as pas de fesses, ça t'inquiète."
ROUTE = {"name": "essai", "waypoints": [[0.0, 0.0], [20.0, 0.0]],
         "pois": [{"name": "banc", "x": 5.0, "y": 0.0, "radius": 1.0, "lubie": LUBIE_BANC},
                  {"name": "flaque", "x": 12.0, "y": 0.0, "radius": 1.0, "lubie": "Une flaque : ça rouille."}]}
# Lubie SANS text : la consigne vient du champ `lubie` du POI de l'itinéraire.
LUBIE = {"id": "lubie_banc", "type": "lubie", "t": "poi", "poi": "banc", "duration_s": 60}
LUBIE_PARAMS = {"poi": "banc", "text": None, "stop": True, "restore": 1.0}
BATTERIE = {"id": "batterie", "type": "speed", "value": 0.4, "t": 200, "duration_s": 10}


# --- rclpy & robot_interfaces factices ----------------------------------------------

class _Publieur:
    def __init__(self):
        self.messages = []
        self.livres = 0   # nombre de messages déjà renvoyés en écho (_echos)

    def publish(self, msg):
        self.messages.append(msg)

    def get_subscription_count(self):
        # Personne d'abonné à `route` : la relance après kill ne part jamais,
        # et find_pids (pgrep) n'est même pas appelé (court-circuit du node).
        return 0


class _Logs:
    def __init__(self):
        self.lignes = []

    def info(self, texte):
        self.lignes.append(("info", texte))

    def warning(self, texte):
        self.lignes.append(("warning", texte))

    def error(self, texte):
        self.lignes.append(("error", texte))


class _NodeFactice:
    imposes = {}   # nom de paramètre -> valeur, posé par le test AVANT la construction

    def __init__(self, nom):
        self.params = {}
        self.publishers = {}
        self.abonnements = {}   # topic -> (qos, callback)
        self.logs = _Logs()

    def declare_parameter(self, nom, defaut):
        self.params[nom] = self.imposes.get(nom, defaut)

    def get_parameter(self, nom):
        return types.SimpleNamespace(value=self.params[nom])

    def create_publisher(self, _type, topic, _qos):
        self.publishers[topic] = _Publieur()
        return self.publishers[topic]

    def create_subscription(self, _type, topic, callback, qos):
        self.abonnements[topic] = (qos, callback)

    def create_timer(self, _periode, _callback):
        pass   # les tests appellent _tick() eux-mêmes, horloge en main

    def get_logger(self):
        return self.logs


class _StringTime:
    def __init__(self, msg="", time=0, anim=False):
        self.msg = msg
        self.time = time
        self.anim = anim


class _QoS:
    def __init__(self, depth=10, durability="VOLATILE"):
        self.depth = depth
        self.durability = durability


class _Horloge:
    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
        return self.t


def _module(nom, **attributs):
    module = types.ModuleType(nom)
    module.__dict__.update(attributs)
    return module


@pytest.fixture
def regisseur(monkeypatch):
    """Le module director_node importé avec rclpy & robot_interfaces simulés ;
    retiré de sys.modules à la fin pour ne rien laisser derrière."""
    faux = {
        "rclpy": _module("rclpy"),
        "rclpy.node": _module("rclpy.node", Node=_NodeFactice),
        "rclpy.qos": _module("rclpy.qos", QoSProfile=_QoS,
                             DurabilityPolicy=types.SimpleNamespace(TRANSIENT_LOCAL="TRANSIENT_LOCAL")),
        "robot_interfaces": _module("robot_interfaces"),
        "robot_interfaces.msg": _module("robot_interfaces.msg", StringTime=_StringTime),
    }
    for nom, module in faux.items():
        monkeypatch.setitem(sys.modules, nom, module)
    monkeypatch.delitem(sys.modules, "robot_rehearsal.director_node", raising=False)
    module = importlib.import_module("robot_rehearsal.director_node")
    yield module
    sys.modules.pop("robot_rehearsal.director_node", None)


def _creer(regisseur, monkeypatch, tmp_path, faults, *, duration_s=300, **params):
    monkeypatch.setenv("ROS_DOMAIN_ID", "43")
    horloge = _Horloge()
    monkeypatch.setattr(regisseur, "time", horloge)
    monkeypatch.setattr(regisseur, "find_pids", lambda _process: [])
    route = tmp_path / "route.yaml"
    route.write_text(yaml.safe_dump(ROUTE, allow_unicode=True), encoding="utf-8")
    scenario = tmp_path / "scenario.yaml"
    scenario.write_text(yaml.safe_dump({"name": "essai", "seed": 0, "duration_s": duration_s,
                                        "faults": faults}, allow_unicode=True), encoding="utf-8")
    imposes = {"scenario_file": str(scenario), "route_file": str(route),
               "journal_dir": str(tmp_path / "journal")}
    imposes.update(params)
    monkeypatch.setattr(_NodeFactice, "imposes", imposes)
    noeud = regisseur.DirectorNode()
    noeud.horloge = horloge
    return noeud


# --- outils de test -----------------------------------------------------------------

def _recevoir(noeud, topic, texte):
    _qos, callback = noeud.abonnements[topic]
    callback(_StringTime(msg=texte))


def _cmd(noeud, cmd):
    _recevoir(noeud, "rehearsal/cmd", cmd)


def _poi(noeud, poi, event):
    _recevoir(noeud, "rehearsal/poi_event", json.dumps({"poi": poi, "event": event, "distance": 1.2}))


def _fader(noeud, texte):
    """Consigne route_speed EXTERNE (fader du boîtier, page scène)."""
    _recevoir(noeud, "route_speed", texte)


def _echos(noeud):
    """Renvoie au régisseur l'écho de SES publications route_speed pas encore
    renvoyées — ce qu'un vrai node ROS reçoit par son propre abonnement."""
    pub = noeud.publishers["route_speed"]
    for msg in pub.messages[pub.livres:]:
        _fader(noeud, msg.msg)
    pub.livres = len(pub.messages)


def _publie(noeud, topic):
    return [m.msg for m in noeud.publishers[topic].messages]


def _journal(noeud):
    with open(noeud.journal_path, encoding="utf-8") as f:
        return [(e["type"], e["payload"]) for e in map(json.loads, f)]


def _types(noeud):
    return [t for t, _p in _journal(noeud)]


def _tick_a(noeud, t):
    noeud.horloge.t = t
    noeud._tick()


# --- (a) lubie sans text : la lubie du POI, chaque topic sur SON publisher ------------

def test_lubie_sans_text_publie_la_lubie_du_poi_et_arrete_didier(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _cmd(n, "start")
    _poi(n, "banc", "enter")
    assert _publie(n, "chat_instruction") == ['"Un banc : tu veux t\'asseoir. Tu n\'as pas de fesses, ça t\'inquiète."']
    assert _publie(n, "route_speed") == ["0"]
    for autre in ("rehearsal/chat_fault", "rehearsal/relay_cmd", "route"):
        assert _publie(n, autre) == [], autre
    assert [p for t, p in _journal(n) if t == "fault_start"] == [
        {"id": "lubie_banc", "type": "lubie", "params": LUBIE_PARAMS, "text": LUBIE_BANC}]


# --- (b) seul « enter » déclenche ----------------------------------------------------

def test_seul_enter_declenche(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _cmd(n, "start")
    _poi(n, "banc", "exit")
    assert _publie(n, "chat_instruction") == [] and _publie(n, "route_speed") == []
    assert n.director.status() == {"lubie_banc": "pending"}
    assert _journal(n)[-1] == ("poi_exit", {"poi": "banc", "distance": 1.2})
    _poi(n, "banc", "enter")
    assert _publie(n, "route_speed") == ["0"]


# --- (c) STOP / abort avant START : rien n'est sauté ---------------------------------

@pytest.mark.parametrize("cmd", ["stop", "abort"])
def test_stop_avant_start_ne_saute_rien(regisseur, monkeypatch, tmp_path, cmd):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _cmd(n, cmd)
    assert n.director.status() == {"lubie_banc": "pending"}
    _cmd(n, "start")
    _poi(n, "banc", "enter")
    assert _publie(n, "route_speed") == ["0"]
    assert n.director.status() == {"lubie_banc": "active"}
    assert "fault_skip" not in _types(n) and "scenario_end" not in _types(n)


# --- (d) START après la fin : la séance est rejouée ----------------------------------

def test_start_apres_la_fin_rejoue_la_seance(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE], duration_s=100)
    _cmd(n, "start")                               # t0 = 1000
    _tick_a(n, 1100.0)                             # durée atteinte : fin, lubie jamais atteinte
    assert n.director.ended and n.director.status() == {"lubie_banc": "skipped"}
    _cmd(n, "start")
    assert _journal(n)[-2:] == [("scenario_reset", {"reason": "restart"}),
                                ("scenario_start", {"name": "essai", "seed": 0})]
    assert (n.director.started, n.director.ended) == (True, False)
    assert n.director.status() == {"lubie_banc": "pending"}   # même timeline, rejouable
    _tick_a(n, 1101.0)
    _poi(n, "banc", "enter")
    assert _publie(n, "route_speed") == ["0"]
    # déjà démarrée et pas finie : warning, pas de reset
    _cmd(n, "start")
    assert _types(n).count("scenario_reset") == 1 and _types(n).count("scenario_start") == 2
    assert ("warning", "scénario déjà démarré") in n.logs.lignes


# --- (e) fermeture d'une lubie au fader ------------------------------------------------

def test_fader_bouge_pendant_la_lubie_la_ferme_sans_rendre_de_vitesse(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.5")                               # le boîtier a parlé avant la lubie
    _cmd(n, "start")
    _poi(n, "banc", "enter")
    _echos(n)                                      # NOTRE « 0 » revient : ce n'est pas le fader
    for texte in ("0.5", "0.5", "0.53", "0.55", "0.45"):   # ré-émissions + jitter ≤ 0,05
        _fader(n, texte)
    assert n.director.status() == {"lubie_banc": "active"}
    assert "fault_stop" not in _types(n)
    _fader(n, "0.8")                               # David pousse le fader
    assert [p for t, p in _journal(n) if t == "fault_stop"] == [
        {"id": "lubie_banc", "type": "lubie", "params": LUBIE_PARAMS, "text": LUBIE_BANC,
         "closed_by": "fader"}]
    assert _publie(n, "chat_instruction")[1:] == ['""']    # consigne levée
    assert _publie(n, "route_speed") == ["0"]               # rien rendu : David vient de fixer 0.8
    assert n.director.status() == {"lubie_banc": "done"}
    _tick_a(n, 1061.0)                             # l'échéance d'origine ne rejoue rien
    assert _types(n).count("fault_stop") == 1 and _publie(n, "route_speed") == ["0"]


def test_fader_sans_consigne_externe_prealable_reference_vitesse_du_launch(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE], speed=0.4)
    _cmd(n, "start")
    _poi(n, "banc", "enter")
    _echos(n)
    _fader(n, "0.42")                              # 0,02 de la vitesse du launch : jitter
    assert n.director.status() == {"lubie_banc": "active"}
    _fader(n, "0.3")
    assert n.director.status() == {"lubie_banc": "done"}
    assert [p.get("closed_by") for t, p in _journal(n) if t == "fault_stop"] == ["fader"]


def test_fader_ne_ferme_pas_une_lubie_sans_stop(regisseur, monkeypatch, tmp_path):
    """Seule une lubie stop=true (qui a PRIS la vitesse) se ferme au fader —
    même juste après une lubie stop=true : sa référence ne doit pas survivre."""
    sans_stop = {"id": "lubie_flaque", "type": "lubie", "t": "poi", "poi": "flaque",
                 "duration_s": 60, "stop": False}
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE, sans_stop])
    _fader(n, "0.5")
    _cmd(n, "start")
    _poi(n, "banc", "enter")
    _echos(n)
    _tick_a(n, 1060.0)                             # la lubie stop=true expire
    _echos(n)
    _poi(n, "flaque", "enter")
    _fader(n, "0.9")
    assert n.director.status() == {"lubie_banc": "done", "lubie_flaque": "active"}
    assert _publie(n, "route_speed") == ["0", "0.5"]   # stop=false : jamais prise, jamais rendue


def test_fader_ne_ferme_pas_une_batterie(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [BATTERIE])
    _fader(n, "0.5")
    _cmd(n, "start")
    _tick_a(n, 1200.0)
    _echos(n)
    _fader(n, "0.9")
    assert n.director.status() == {"batterie": "active"}
    assert "fault_stop" not in _types(n)


# --- (f) restore = la vitesse EN VIGUEUR, jamais le restore figé du scénario ----------

def test_restore_rend_la_derniere_vitesse_externe(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE, BATTERIE])
    _fader(n, "0.7")
    _cmd(n, "start")                               # t0 = 1000
    _poi(n, "banc", "enter")
    _echos(n)
    _fader(n, "0.72")                              # jitter : ne ferme pas, mais c'est la DERNIÈRE
    _tick_a(n, 1060.0)                             # échéance de la lubie
    assert _publie(n, "route_speed") == ["0", "0.72"]
    assert _publie(n, "chat_instruction")[1:] == ['""']
    assert "closed_by" not in [p for t, p in _journal(n) if t == "fault_stop"][0]
    _echos(n)
    _tick_a(n, 1200.0)                             # batterie : 0.4…
    _echos(n)
    _tick_a(n, 1210.0)                             # …puis la vitesse en vigueur, pas restore 1.0
    assert _publie(n, "route_speed") == ["0", "0.72", "0.4", "0.72"]


def test_restore_sans_fader_rend_la_vitesse_du_launch(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE], speed=0.25)
    _cmd(n, "start")
    _poi(n, "banc", "enter")
    _echos(n)
    _tick_a(n, 1060.0)
    assert _publie(n, "route_speed") == ["0", "0.25"]


# --- (g) POI franchi hors séance : journalisé, pas mémorisé ---------------------------

def test_poi_hors_seance_journalise_poi_enter_ignored(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE], duration_s=100)
    _poi(n, "banc", "enter")
    assert _journal(n)[-1] == ("poi_enter_ignored", {"poi": "banc", "reason": "before_start"})
    assert "poi_enter" not in _types(n)
    _cmd(n, "start")                               # pas de mémorisation de l'enter d'avant
    assert _publie(n, "chat_instruction") == [] and n.director.status() == {"lubie_banc": "pending"}
    _tick_a(n, 1100.0)                             # fin
    _poi(n, "banc", "enter")
    assert _journal(n)[-1] == ("poi_enter_ignored", {"poi": "banc", "reason": "ended"})
    assert _publie(n, "chat_instruction") == []
