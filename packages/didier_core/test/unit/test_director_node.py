"""Node `director` (didier_rehearsal.director_node) avec rclpy SIMULÉ — même
procédé que le pont web (test_web_protocol.py, fixture `pont`) : rclpy et
theatre_interfaces remplacés par des modules factices dans sys.modules ; tout le
reste est RÉEL (yaml, didier_core.diagnostic.journal, scenario, director, route,
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
import pathlib
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


# --- rclpy & theatre_interfaces factices ----------------------------------------------

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
        self.qos_publieurs = {}   # topic -> QoS demandée à create_publisher
        self.abonnements = {}   # topic -> (qos, callback)
        self.logs = _Logs()

    def declare_parameter(self, nom, defaut):
        self.params[nom] = self.imposes.get(nom, defaut)

    def get_parameter(self, nom):
        return types.SimpleNamespace(value=self.params[nom])

    def create_publisher(self, _type, topic, qos):
        self.publishers[topic] = _Publieur()
        self.qos_publieurs[topic] = qos
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



# A0-4 (22/11) : configuration du corps sûr de la sim, celle que rehearsal.launch.py passe au régisseur.
CONF_CORPS_SUR_SIM = str(pathlib.Path(__file__).resolve().parents[4] / "machines" / "sim" / "robot" / "corps_sur.yaml")

class _QoS:
    def __init__(self, depth=10, durability="VOLATILE"):
        self.depth = depth
        self.durability = durability


class _Horloge:
    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
        return self.t

    def time(self):
        # Horloge murale (epoch) figée : t_ms de rehearsal/journal est gravé en dur.
        return 1700000000.5


def _module(nom, **attributs):
    module = types.ModuleType(nom)
    module.__dict__.update(attributs)
    return module


@pytest.fixture
def regisseur(monkeypatch):
    """Le module director_node importé avec rclpy & theatre_interfaces simulés ;
    retiré de sys.modules à la fin pour ne rien laisser derrière."""
    faux = {
        "rclpy": _module("rclpy"),
        "rclpy.node": _module("rclpy.node", Node=_NodeFactice),
        "rclpy.qos": _module("rclpy.qos", QoSProfile=_QoS,
                             DurabilityPolicy=types.SimpleNamespace(TRANSIENT_LOCAL="TRANSIENT_LOCAL")),
        "theatre_interfaces": _module("theatre_interfaces"),
        "theatre_interfaces.msg": _module("theatre_interfaces.msg", StringTime=_StringTime),
        # Lot M1 « aller voir » : le régisseur lit la pose (borne de distance).
        "nav_msgs": _module("nav_msgs"),
        "nav_msgs.msg": _module("nav_msgs.msg", Odometry=object),
    }
    for nom, module in faux.items():
        monkeypatch.setitem(sys.modules, nom, module)
    monkeypatch.delitem(sys.modules, "didier_rehearsal.director_node", raising=False)
    module = importlib.import_module("didier_rehearsal.director_node")
    yield module
    sys.modules.pop("didier_rehearsal.director_node", None)


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
               "journal_dir": str(tmp_path / "journal"),
               # A0-4 : le VRAI fichier du corps sûr de la sim (garde d'« aller voir »).
               "corps_sur_config": CONF_CORPS_SUR_SIM}
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


# --- (h) Lot I1 (22/10) : mouvement à la voix (rehearsal/chat_move) -----------------
# Règles révisées par la revue adversariale I1 (D1-D6). Mutations listées dans
# le rapport du lot ; la logique pure : test_director.py.

KILL_SANS_RELANCE = {"id": "reboot", "type": "kill", "t": 5, "process": "route_driver", "reenable": False}


def _voix(noeud, cmd, t=None):
    """Ordre de marche publié par chat_node (contrat : json.dumps)."""
    if t is not None:
        noeud.horloge.t = t
    _recevoir(noeud, "rehearsal/chat_move", json.dumps(cmd))


def _etat_route(noeud, etat, cause=None):
    """État latché de route_driver, précédé de sa cause si donnée (même
    ordre que route_driver : cause d'abord)."""
    if cause is not None:
        _recevoir(noeud, "route_state_cause", json.dumps(cause))
    _recevoir(noeud, "route_state", etat)


def _voice_moves(noeud):
    return [p for t, p in _journal(noeud) if t == "voice_move"]


def test_voix_abonnements_qos(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    qos, _callback = n.abonnements["rehearsal/chat_move"]
    assert qos == 10                               # pas de latch : un vieil ordre ne rejoue pas
    qos, _callback = n.abonnements["route_state_cause"]
    assert (qos.depth, qos.durability) == (1, "TRANSIENT_LOCAL")   # latché DES DEUX côtés


def test_s1_jeu_la_lubie_du_scenario_journalisee_fault_skip_raison_jeu(regisseur, monkeypatch, tmp_path):
    """Lot S1 (spec §3) : paramètre `jeu` (rehearsal.launch.py jeu:=true) -> la lubie du
    scénario ne part pas, le journal dit pourquoi ; rien n'est publié (ni consigne ni 0)."""
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE], jeu=True)
    _cmd(n, "start")
    _poi(n, "banc", "enter")
    assert [p for t, p in _journal(n) if t == "fault_skip"] == [
        {"id": "lubie_banc", "type": "lubie", "params": LUBIE_PARAMS, "text": LUBIE_BANC, "reason": "jeu"}]
    assert _publie(n, "route_speed") == [] and _publie(n, "chat_instruction") == []
    assert [p["jeu"] for t, p in _journal(n) if t == "scenario_loaded"] == [True]


def test_voix_go_ferme_la_lubie_et_rend_la_vitesse(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.7")
    _cmd(n, "start")
    _poi(n, "banc", "enter")
    _echos(n)
    _voix(n, "go", t=1010.0)
    assert _publie(n, "route_speed") == ["0", "0.7"]          # rendue, contrairement au fader
    assert _publie(n, "chat_instruction")[1:] == ['""']       # consigne levée
    assert _voice_moves(n) == [{"cmd": "go", "origine": "david", "effect": "close_lubie"}]
    assert [p for t, p in _journal(n) if t == "fault_stop"] == [
        {"id": "lubie_banc", "type": "lubie", "params": LUBIE_PARAMS, "text": LUBIE_BANC,
         "closed_by": "voix"}]
    assert n.director.status() == {"lubie_banc": "done"}


def test_voix_non_regression_le_fader_ferme_toujours_sans_rendre(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.5")
    _cmd(n, "start")
    _poi(n, "banc", "enter")
    _echos(n)
    _fader(n, "0.8")
    assert _publie(n, "route_speed") == ["0"]
    assert [p["closed_by"] for t, p in _journal(n) if t == "fault_stop"] == ["fader"]


def test_voix_stop_puis_go_rend_la_vitesse_d_avant(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.6")
    _recevoir(n, "route", "on")
    _cmd(n, "start")
    _voix(n, "stop", t=1001.0)
    _echos(n)                                      # notre « 0 » revient : pas le fader
    _fader(n, "0.62")                              # ré-émission du boîtier : arrêt maintenu
    _voix(n, "stop", t=1001.5)                     # 2e stop : 0 republié, 0.6 reste retenu
    _voix(n, "go", t=1005.0)
    assert _publie(n, "route_speed") == ["0", "0", "0.6"]
    assert _voice_moves(n) == [{"cmd": "stop", "origine": "david", "effect": "hold"},
                               {"cmd": "stop", "origine": "david", "effect": "hold"},
                               {"cmd": "go", "origine": "david", "effect": "resume"}]
    _voix(n, "go", t=1008.0)
    assert _voice_moves(n)[-1] == {"cmd": "go", "origine": "david", "effect": "ignored", "reason": "deja_en_marche"}
    assert _publie(n, "route_speed") == ["0", "0", "0.6"]


def test_voix_batterie_active_sa_valeur_est_la_vitesse_en_vigueur(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [BATTERIE])
    _fader(n, "0.9")
    _recevoir(n, "route", "on")
    _cmd(n, "start")
    _tick_a(n, 1200.0)                             # batterie 0.4 active
    _echos(n)
    _voix(n, "stop", t=1201.0)
    _echos(n)
    _voix(n, "go", t=1202.0)
    assert _publie(n, "route_speed") == ["0.4", "0", "0.4"]   # jamais le fader 0.9


def test_voix_stop_puis_fader_aucune_republication(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.6")
    _cmd(n, "start")
    _voix(n, "stop", t=1001.0)
    _echos(n)
    _fader(n, "0.9")                               # David pousse le fader : il est maître
    assert _journal(n)[-1] == ("voice_hold_released", {"by": "fader", "value": 0.9})
    _recevoir(n, "route", "on")                    # (la route roule)
    _voix(n, "go", t=1005.0)
    assert _publie(n, "route_speed") == ["0"]      # rien rendu, jamais
    assert _voice_moves(n)[-1] == {"cmd": "go", "origine": "david", "effect": "ignored", "reason": "deja_en_marche"}


def test_voix_rebond_2_s_sur_go_seulement(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _recevoir(n, "route", "on")
    _cmd(n, "start")
    _voix(n, "stop", t=1001.0)
    _voix(n, "stop", t=1001.1)
    _voix(n, "go", t=1003.0)
    _voix(n, "go", t=1004.0)
    assert [m.get("reason", m["effect"]) for m in _voice_moves(n)] == ["hold", "hold", "resume", "rebond"]
    assert _publie(n, "route_speed") == ["0", "0", "0.5"]


def test_voix_hors_seance_un_stop_n_est_jamais_ignore(regisseur, monkeypatch, tmp_path):
    """Lot S1, règle R1 : hors séance comme en séance, un « stop » s'applique quelle que soit
    son origine ; un « go » de Didier ne lève que l'arrêt de Didier, celui de David tout."""
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE], speed=0.4)
    _voix(n, {"cmd": "stop", "origine": "didier"}, t=1000.0)
    assert _publie(n, "route_speed") == ["0"]               # appliqué hors séance
    _voix(n, {"cmd": "go", "origine": "didier"}, t=1003.0)  # lève SON arrêt
    assert _publie(n, "route_speed") == ["0", "0.4"]
    _voix(n, "stop", t=1006.0)                               # mot d'arrêt : David
    _voix(n, {"cmd": "go", "origine": "didier"}, t=1009.0)
    assert _publie(n, "route_speed") == ["0", "0.4", "0"]   # le go de Didier ne lève pas celui de David
    _voix(n, {"cmd": "go", "origine": "david"}, t=1012.0)
    assert _publie(n, "route_speed") == ["0", "0.4", "0", "0.4"]
    assert _voice_moves(n) == [
        {"cmd": "stop", "origine": "didier", "effect": "hold"},
        {"cmd": "go", "origine": "didier", "effect": "resume"},
        {"cmd": "stop", "origine": "david", "effect": "hold"},
        {"cmd": "go", "origine": "didier", "effect": "ignored", "reason": "arret_de_david"},
        {"cmd": "go", "origine": "david", "effect": "resume"}]


def test_s1_m2_stop_en_seance_fin_de_seance_go_de_david_il_repart(regisseur, monkeypatch, tmp_path):
    """M2 (relecture adverse du 25/11) : la fin de séance GARDE l'arrêt vocal ; le « go » de
    David qui suit rend la vitesse retenue. Avant : levé en silence, le go tombait
    « deja_en_marche » et Didier restait planté à vitesse 0."""
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE], duration_s=100)
    _recevoir(n, "route", "on"); _etat_route(n, "on")
    _cmd(n, "start")
    _voix(n, "stop", t=1001.0)
    _tick_a(n, 1100.0)                                       # fin par durée
    assert _publie(n, "route_speed") == ["0"]
    assert not any(t == "voice_hold_released" for t, _ in _journal(n))
    _voix(n, {"cmd": "go", "origine": "didier"}, t=1101.0)   # arrêt de David : refusé
    _voix(n, "go", t=1104.0)
    assert _publie(n, "route_speed") == ["0", "0.5"]
    assert [m.get("reason", m["effect"]) for m in _voice_moves(n)] == ["hold", "arret_de_david", "resume"]


def test_s1_geste_de_didier_refuse_hors_seance_celui_de_david_passe(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _voix(n, {"cmd": "avancer", "metres": 1.0, "origine": "didier"}, t=1000.0)
    assert [p for t, p in _journal(n) if t == "avancer"] == [{"effect": "hors_seance", "origine": "didier"}]
    assert [json.loads(m) for m in _publie(n, "rehearsal/chat_move_reply")] == [
        {"demande": {"cmd": "avancer", "metres": 1.0, "origine": "didier"}, "effect": "hors_seance",
         "reason": None, "name": None, "source": "director"}]
    assert _publie(n, "route_goto") == []
    _voix(n, {"cmd": "avancer", "metres": 1.0, "origine": "david"}, t=1001.0)
    assert [p.get("effect") for t, p in _journal(n) if t == "avancer"][-1] != "hors_seance"


def test_voix_invalide_et_illisible_journalises(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _recevoir(n, "route", "on")
    _cmd(n, "start")
    _recevoir(n, "rehearsal/chat_move", "go")      # brut toléré
    _recevoir(n, "rehearsal/chat_move", '"recule"')
    _recevoir(n, "rehearsal/chat_move", "{pas du json")
    _recevoir(n, "rehearsal/chat_move", '"GO"')    # lot S1 : casse normalisée (sens sûr pour un stop)
    assert _voice_moves(n) == [{"cmd": "go", "origine": "david", "effect": "ignored", "reason": "deja_en_marche"},
                               {"cmd": "recule", "origine": "david", "effect": "ignored", "reason": "invalide"},
                               {"cmd": "{pas du json", "origine": "david", "effect": "ignored", "reason": "invalide"},
                               {"cmd": "go", "origine": "david", "effect": "ignored", "reason": "rebond"}]
    assert _publie(n, "route") == [] and _publie(n, "route_speed") == []


def test_voix_go_apres_kill_sans_relance_relance_la_route(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [KILL_SANS_RELANCE])
    monkeypatch.setattr(regisseur, "apply", lambda op, process: [4242])
    _etat_route(n, "off", cause="boot")            # démarrage de route_driver
    _recevoir(n, "route", "on"); _etat_route(n, "on")   # la route roulait
    _cmd(n, "start")
    _tick_a(n, 1005.0)                             # kill, reenable: false -> pas de relance auto
    _etat_route(n, "off", cause="boot")            # route_driver respawné ÉTEINT
    _voix(n, "go", t=1010.0)
    assert _publie(n, "route") == ["on"]           # 1er envoi tout de suite
    assert _voice_moves(n) == [{"cmd": "go", "origine": "david", "effect": "relaunch"}]
    for t in (1010.2, 1010.5, 1011.0, 1011.5):
        _tick_a(n, t)
    assert _publie(n, "route") == ["on", "on", "on"]   # salve de 3, pas un de plus
    assert "voice_relaunch_confirmed" not in _types(n)  # pas avant l'état latché
    _etat_route(n, "on")
    assert _journal(n)[-1] == ("voice_relaunch_confirmed", {})


def test_voix_go_route_jamais_lancee_la_lance(regisseur, monkeypatch, tmp_path):
    """Accepté par David (revue I1, D1) : au démarrage la cause est « boot »,
    « go » lance donc une route que personne n'a encore lancée."""
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _etat_route(n, "off", cause="boot")
    _cmd(n, "start")
    _voix(n, "go", t=1001.0)
    assert _voice_moves(n) == [{"cmd": "go", "origine": "david", "effect": "relaunch"}]
    assert _publie(n, "route") == ["on"]


def test_voix_cause_jamais_recue_refus(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _etat_route(n, "off")                          # état sans cause (route_driver ancien, latch perdu)
    _cmd(n, "start")
    _voix(n, "go", t=1001.0)
    assert _voice_moves(n) == [{"cmd": "go", "origine": "david", "effect": "ignored", "reason": "cause_inconnue"}]
    assert _publie(n, "route") == []


@pytest.mark.parametrize("off", ["off", '"off"', "false", "0", '"0"'])
def test_voix_off_de_david_sous_tout_format_jamais_relance(regisseur, monkeypatch, tmp_path, off):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _etat_route(n, "off", cause="boot"); _recevoir(n, "route", "on"); _etat_route(n, "on")
    _cmd(n, "start")
    _recevoir(n, "route", off); _etat_route(n, "off", cause="cmd")   # David coupe
    _voix(n, "go", t=1001.0)
    assert _voice_moves(n) == [{"cmd": "go", "origine": "david", "effect": "ignored", "reason": "route_off_par_david"}]
    _tick_a(n, 1002.0)
    assert _publie(n, "route") == []


def test_voix_off_rate_par_le_regisseur_la_cause_suffit(regisseur, monkeypatch, tmp_path):
    """Revue I1 (D1) : le `off` de David n'a PAS été vu sur `route` (perdu,
    régisseur relancé) — la cause latchée « cmd » refuse quand même."""
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _etat_route(n, "off", cause="cmd")
    _cmd(n, "start")
    _voix(n, "go", t=1001.0)
    assert _voice_moves(n) == [{"cmd": "go", "origine": "david", "effect": "ignored", "reason": "route_off_par_david"}]


def test_voix_off_vu_puis_reboot_toujours_refuse(regisseur, monkeypatch, tmp_path):
    """Ceinture : un `off` VU sur `route` tient même si un reboot redit « boot »."""
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _etat_route(n, "off", cause="boot"); _recevoir(n, "route", "on"); _etat_route(n, "on")
    _cmd(n, "start")
    _recevoir(n, "route", "false"); _etat_route(n, "off", cause="cmd")
    _etat_route(n, "off", cause="boot")            # reboot de route_driver
    _voix(n, "go", t=1005.0)
    assert _voice_moves(n) == [{"cmd": "go", "origine": "david", "effect": "ignored", "reason": "route_off_par_david"}]


def test_voix_relance_sans_confirmation_expire(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _etat_route(n, "off", cause="boot")
    _cmd(n, "start")
    _voix(n, "go", t=1001.0)
    _tick_a(n, 1004.0)
    assert _journal(n)[-1] == ("voice_relaunch_expired", {})


def test_voix_off_de_david_pendant_la_salve_l_annule(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _etat_route(n, "off", cause="boot")
    _cmd(n, "start")
    _voix(n, "go", t=1001.0)
    _recevoir(n, "route", "0")                     # format numérique accepté par route_driver
    assert _journal(n)[-1] == ("voice_relaunch_cancelled", {"by": "route_off"})
    _tick_a(n, 1001.5)
    _tick_a(n, 1002.0)
    assert _publie(n, "route") == ["on"]           # le seul parti avant le `off`


@pytest.mark.parametrize("cmd", ["stop", "abort"])
def test_voix_abort_garde_l_arret_le_go_de_david_rend_la_vitesse(regisseur, monkeypatch, tmp_path, cmd):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.6")
    _cmd(n, "start")
    _voix(n, "stop", t=1001.0)
    _cmd(n, cmd)
    assert _publie(n, "route_speed") == ["0"]      # Didier reste à l'arrêt…
    assert not any(t == "voice_hold_released" for t, _ in _journal(n))   # …et l'arrêt est GARDÉ (M2)
    _cmd(n, "start")
    _voix(n, "go", t=1005.0)
    assert _publie(n, "route_speed") == ["0", "0.6"]


def test_voix_fin_de_seance_garde_l_arret_sans_republier(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE], duration_s=100)
    _cmd(n, "start")
    _voix(n, "stop", t=1001.0)
    _tick_a(n, 1100.0)                             # fin par durée
    assert n.voice.hold_before == 0.5 and n.voice.hold_origine == "david"   # M2 : gardé
    assert _publie(n, "route_speed") == ["0"]


def test_voix_fin_de_seance_annule_la_salve_en_vol(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE], duration_s=100)
    _etat_route(n, "off", cause="boot")
    _cmd(n, "start")
    _voix(n, "go", t=1099.6)                       # relance : 1er « on »
    _tick_a(n, 1100.0)                             # fin par durée, salve pas finie
    assert ("voice_relaunch_cancelled", {"by": "fin"}) in _journal(n)
    _tick_a(n, 1100.5)
    _tick_a(n, 1101.0)
    assert _publie(n, "route") == ["on"]           # plus aucun « on » après la fin


class _PublieurCasse(_Publieur):
    def publish(self, msg):
        raise RuntimeError("DDS (test)")


def test_voix_echec_de_publication_du_0_ne_pose_pas_d_arret_fantome(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _recevoir(n, "route", "on")
    _cmd(n, "start")
    sain = n.pub_speed
    n.pub_speed = _PublieurCasse()
    _voix(n, "stop", t=1001.0)                     # le « 0 » ne part pas
    assert any(niveau == "error" and "chat_move" in texte for niveau, texte in n.logs.lignes)
    n.pub_speed = sain
    _voix(n, "go", t=1005.0)                       # aucun arrêt fantôme à « rendre »
    assert _voice_moves(n)[-1] == {"cmd": "go", "origine": "david", "effect": "ignored", "reason": "deja_en_marche"}
    assert _publie(n, "route_speed") == []


def test_voix_echec_d_un_0_repete_garde_l_arret_deja_pose(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.6")
    _recevoir(n, "route", "on")
    _cmd(n, "start")
    _voix(n, "stop", t=1001.0)
    sain = n.pub_speed
    n.pub_speed = _PublieurCasse()
    _voix(n, "stop", t=1002.0)                     # 2e « 0 » perdu : l'arrêt du 1er tient
    n.pub_speed = sain
    _voix(n, "go", t=1005.0)
    assert _publie(n, "route_speed") == ["0", "0.6"]


def test_voix_callback_qui_leve_ne_tue_pas_le_node(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _cmd(n, "start")

    def casse(_cmd):
        raise RuntimeError("panne (test)")

    monkeypatch.setattr(n, "_voice_move", casse)
    _voix(n, "go")                                 # ne lève pas
    assert any(niveau == "error" and "chat_move" in texte for niveau, texte in n.logs.lignes)


# --- (i) Défaut trouvé en sim le 22/10 : RÈGLE GÉNÉRALE de l'arrêt vocal ---------
# Tant qu'un arrêt vocal est posé, le régisseur ne publie JAMAIS de vitesse non
# nulle, sauf par « go » (voix) ou levée au fader (David).

def _faults(noeud, kind):
    return [p for t, p in _journal(noeud) if t == f"fault_{kind}"]


def test_sim_22_10_lubie_stop_puis_stop_voix_puis_fin_par_duree(regisseur, monkeypatch, tmp_path):
    """Séquence EXACTE vécue (journal du 22/10) : lubie stop → « stop » →
    la lubie finit par sa DURÉE → Didier repartait. Il doit rester arrêté
    jusqu'au « go », qui rend la vitesse en vigueur."""
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.6")
    _recevoir(n, "route", "on")
    _cmd(n, "start")
    _poi(n, "banc", "enter")                       # lubie stop : 0
    _echos(n)
    _voix(n, "stop", t=1033.0)                     # 0 republié, arrêt vocal posé
    _echos(n)
    _tick_a(n, 1061.0)                             # fin de la lubie par sa durée
    assert _publie(n, "route_speed") == ["0", "0"]          # AUCUNE vitesse rendue
    assert _publie(n, "chat_instruction")[1:] == ['""']     # la consigne, elle, est levée
    assert n.director.status() == {"lubie_banc": "done"}
    _voix(n, "go", t=1063.0)
    assert _voice_moves(n)[-1] == {"cmd": "go", "origine": "david", "effect": "resume"}
    assert _publie(n, "route_speed") == ["0", "0", "0.6"]


def test_lubie_stop_qui_demarre_pendant_l_arret_le_garde(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.6")
    _recevoir(n, "route", "on")
    _cmd(n, "start")
    _voix(n, "stop", t=1001.0)
    _echos(n)
    _fader(n, "0.63")                              # ré-émission sous le seuil : en vigueur 0.63
    _poi(n, "banc", "enter")                       # la lubie publie son 0
    assert _publie(n, "route_speed") == ["0", "0"]
    assert n.voice.hold_before == 0.6              # l'arrêt vocal N'EST PAS levé
    assert n._speed_before_lubie == 0.6            # référence du fader = vitesse RETENUE, pas 0.63
    _echos(n)
    _tick_a(n, 1061.0)                             # fin par durée : rien rendu
    assert _publie(n, "route_speed") == ["0", "0"]


def test_go_pendant_lubie_et_arret_une_seule_publication(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.6")
    _recevoir(n, "route", "on")
    _cmd(n, "start")
    _poi(n, "banc", "enter")
    _echos(n)
    _voix(n, "stop", t=1010.0)
    _echos(n)
    _voix(n, "go", t=1012.0)                       # ferme la lubie ET lève l'arrêt
    assert _publie(n, "route_speed") == ["0", "0", "0.6"]   # UNE seule vitesse
    assert [p["closed_by"] for p in _faults(n, "stop")] == ["voix"]
    assert n.voice.hold_before is None and n.director.status() == {"lubie_banc": "done"}


def test_fader_pendant_lubie_et_arret_leve_les_deux_sans_publier(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.6")
    _cmd(n, "start")
    _poi(n, "banc", "enter")
    _echos(n)
    _voix(n, "stop", t=1010.0)
    _echos(n)
    _fader(n, "0.9")                               # David : geste au-delà du seuil
    assert n.voice.hold_before is None
    assert [p["closed_by"] for p in _faults(n, "stop")] == ["fader"]
    assert _publie(n, "route_speed") == ["0", "0"]          # rien publié par nous


def test_batterie_pendant_l_arret_rien_publie_et_journalisee(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [BATTERIE])
    _fader(n, "0.9")
    _recevoir(n, "route", "on")
    _cmd(n, "start")
    _voix(n, "stop", t=1001.0)
    _echos(n)
    _tick_a(n, 1200.0)                             # début de la batterie : rien publié
    assert _publie(n, "route_speed") == ["0"]
    assert _faults(n, "start")[-1]["suppressed_by"] == "voice_hold"
    assert n.director.status() == {"batterie": "active"}    # active logiquement
    _voix(n, "go", t=1201.0)                       # plafond = la batterie (D2)
    assert _publie(n, "route_speed") == ["0", "0.4"]


def test_fin_de_batterie_pendant_l_arret_rien_publie(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [BATTERIE])
    _fader(n, "0.9")
    _recevoir(n, "route", "on")
    _cmd(n, "start")
    _tick_a(n, 1200.0)                             # batterie 0.4 publiée
    _echos(n)
    _voix(n, "stop", t=1201.0)                     # retenue 0.4
    _echos(n)
    _tick_a(n, 1210.0)                             # fin de batterie : rien publié
    assert _publie(n, "route_speed") == ["0.4", "0"]
    assert "suppressed_by" not in _faults(n, "start")[-1]
    assert _faults(n, "stop")[-1]["suppressed_by"] == "voice_hold"
    _voix(n, "go", t=1212.0)                       # min(retenue 0.4, en vigueur 0.9)
    assert _publie(n, "route_speed") == ["0.4", "0", "0.4"]


def test_abort_pendant_lubie_et_arret_la_lubie_rend_sa_vitesse(regisseur, monkeypatch, tmp_path):
    """Lot S1, M2 : l'abort GARDE l'arrêt vocal ; la lubie révoquée ne rend donc RIEN (règle
    générale : jamais de vitesse non nulle sous un arrêt vocal). Le « go » de David rend la
    vitesse ensuite. (Avant : arrêt levé sans republier, puis la lubie rendait 0,6.)"""
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.6")
    _cmd(n, "start")
    _poi(n, "banc", "enter")
    _echos(n)
    _voix(n, "stop", t=1010.0)
    _cmd(n, "abort")
    assert _publie(n, "route_speed") == ["0", "0"]
    _voix(n, "go", t=1013.0)
    assert _publie(n, "route_speed") == ["0", "0", "0.6"]


# --- rehearsal/journal : le journal en direct, pour le panneau « Coulisses » (18/11) ---

def test_journal_en_direct_publie_chaque_evenement(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    # VOLATILE depth 10 (qos entier = défaut ROS) : jamais latché, un vieil événement
    # ne rejoue pas à l'ouverture de la page.
    assert n.qos_publieurs["rehearsal/journal"] == 10
    n.log("essai_type", {"a": "é", "b": 1})
    assert _publie(n, "rehearsal/journal")[-1] == (
        '{"type": "essai_type", "payload": {"a": "é", "b": 1}, "t_ms": 1700000000500}')
    # Et le JSONL du débrief reste écrit comme avant.
    assert _journal(n)[-1] == ("essai_type", {"a": "é", "b": 1})
    _cmd(n, "start")
    assert _publie(n, "rehearsal/journal")[-1] == (
        '{"type": "scenario_start", "payload": {"name": "essai", "seed": 0}, "t_ms": 1700000000500}')


def test_journal_en_direct_une_erreur_de_publication_ne_tue_pas_le_regisseur(
        regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])

    def casse(_msg):
        raise RuntimeError("publication impossible")
    n.pub_journal.publish = casse
    n.log("essai_type", {"x": 1})                  # ne doit pas lever
    assert _journal(n)[-1] == ("essai_type", {"x": 1})   # le JSONL est écrit quand même
    assert ("error", "rehearsal/journal : RuntimeError('publication impossible')") in n.logs.lignes
    _cmd(n, "start")                               # le régisseur reste vivant
    assert _publie(n, "rehearsal/state")[-1] == SEANCE_EN_COURS


# --- (i) rehearsal/state : séance + arrêt vocal pour la page scène (31/10) ----------

SEANCE_ATTENTE = '{"seance": "attente", "arret_vocal": false}'
SEANCE_EN_COURS = '{"seance": "en_cours", "arret_vocal": false}'
SEANCE_EN_COURS_ARRETEE = '{"seance": "en_cours", "arret_vocal": true}'
SEANCE_TERMINEE = '{"seance": "terminee", "arret_vocal": false}'


def test_etat_seance_latche_et_publie_au_demarrage(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    # TRANSIENT_LOCAL depth 1 : une page ouverte APRÈS le START voit l'état courant.
    qos = n.qos_publieurs["rehearsal/state"]
    assert (qos.depth, qos.durability) == (1, "TRANSIENT_LOCAL")
    assert _publie(n, "rehearsal/state") == [SEANCE_ATTENTE]


def test_etat_seance_start_fin_par_duree_et_rejeu(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE], duration_s=100)
    _cmd(n, "start")
    _cmd(n, "start")                               # déjà démarrée : rien de nouveau
    _tick_a(n, 1100.0)                             # fin par durée
    _cmd(n, "start")                               # rejeu
    assert _publie(n, "rehearsal/state") == [SEANCE_ATTENTE, SEANCE_EN_COURS, SEANCE_TERMINEE,
                                             SEANCE_EN_COURS]


@pytest.mark.parametrize("cmd", ["stop", "abort"])
def test_etat_seance_stop_et_abort_terminent(regisseur, monkeypatch, tmp_path, cmd):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _cmd(n, cmd)                                   # avant START : inerte, rien publié
    assert _publie(n, "rehearsal/state") == [SEANCE_ATTENTE]
    _cmd(n, "start")
    _cmd(n, cmd)
    assert _publie(n, "rehearsal/state") == [SEANCE_ATTENTE, SEANCE_EN_COURS, SEANCE_TERMINEE]


def test_etat_arret_vocal_pose_par_stop_leve_par_go(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.6")
    _cmd(n, "start")
    _voix(n, "stop", t=1001.0)
    _voix(n, "stop", t=1001.5)                     # 2e stop : même état, pas de doublon
    _voix(n, "go", t=1005.0)
    assert _publie(n, "rehearsal/state") == [SEANCE_ATTENTE, SEANCE_EN_COURS,
                                             SEANCE_EN_COURS_ARRETEE, SEANCE_EN_COURS]


def test_etat_arret_vocal_pose_hors_seance_puis_go_ignore(regisseur, monkeypatch, tmp_path):
    """Le cas du 31/10 : « stop » de David hors séance retient Didier ; un « go » de Didier
    (lot S1 : celui de David, lui, s'applique) est ignoré -- la page doit pouvoir l'afficher."""
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.6")
    _voix(n, "stop", t=1001.0)
    _voix(n, {"cmd": "go", "origine": "didier"}, t=1005.0)
    assert _publie(n, "rehearsal/state") == [SEANCE_ATTENTE,
                                             '{"seance": "attente", "arret_vocal": true}']


def test_etat_arret_vocal_leve_par_le_fader(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE])
    _fader(n, "0.6")
    _cmd(n, "start")
    _voix(n, "stop", t=1001.0)
    _echos(n)                                      # écho de notre « 0 » : pas un geste de David
    _fader(n, "0.2")                               # geste de David
    assert _publie(n, "rehearsal/state")[-2:] == [SEANCE_EN_COURS_ARRETEE, SEANCE_EN_COURS]


def test_etat_arret_vocal_garde_par_abort(regisseur, monkeypatch, tmp_path):
    # Lot S1, M2 : l'arrêt vocal survit à l'abort — la page le montre toujours.
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE], duration_s=100)
    _cmd(n, "start")
    _voix(n, "stop", t=1001.0)
    _cmd(n, "abort")
    assert _publie(n, "rehearsal/state")[-2:] == [SEANCE_EN_COURS_ARRETEE,
                                                  '{"seance": "terminee", "arret_vocal": true}']


def test_etat_arret_vocal_garde_par_la_fin_de_seance(regisseur, monkeypatch, tmp_path):
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE], duration_s=100)
    _cmd(n, "start")
    _voix(n, "stop", t=1001.0)
    _tick_a(n, 1100.0)                             # fin par durée
    assert _publie(n, "rehearsal/state")[-2:] == [SEANCE_EN_COURS_ARRETEE,
                                                  '{"seance": "terminee", "arret_vocal": true}']


def test_etat_ne_trahit_jamais_le_tirage(regisseur, monkeypatch, tmp_path):
    """Une lubie (stop=true) puis une batterie démarrent et finissent : l'état
    publié ne bouge pas, et aucun message n'en cite la panne."""
    n = _creer(regisseur, monkeypatch, tmp_path, [LUBIE, BATTERIE])
    _cmd(n, "start")
    _poi(n, "banc", "enter")                       # lubie : route_speed 0, consigne posée
    _tick_a(n, 1200.0)                             # batterie démarre
    _tick_a(n, 1211.0)                             # batterie finie
    assert _publie(n, "rehearsal/state") == [SEANCE_ATTENTE, SEANCE_EN_COURS]
    for texte in _publie(n, "rehearsal/state"):
        assert sorted(json.loads(texte)) == ["arret_vocal", "seance"]


def test_sans_corps_sur_le_regisseur_refuse_de_demarrer(regisseur, monkeypatch, tmp_path):
    """A0-4 : jamais de standoff deviné — configuration du corps sûr absente ou refusée = refus."""
    with pytest.raises(RuntimeError, match="corps_sur_config manquant"):
        _creer(regisseur, monkeypatch, tmp_path, [], corps_sur_config="")
    faux = tmp_path / "corps_sur.yaml"
    faux.write_text("terrain: sim\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="corps sûr illisible"):
        _creer(regisseur, monkeypatch, tmp_path, [], corps_sur_config=str(faux))
