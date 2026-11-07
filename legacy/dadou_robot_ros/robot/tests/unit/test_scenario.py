"""Scénario de pannes (didier_rehearsal.scenario) — validation à refus explicite,
expansion déterministe par graine. Valeurs gravées : random.Random(42)
.uniform(0, 90) = 57.548 puis .uniform(0, 100) = 2.501 ; Random(7).uniform(0, 90)
= 29.145 (calculées UNE fois hors de la fonction testée, le 2026-10-08).
Mutation : retirer une borne de validation -> test_refus ; ne pas trier ->
test_timeline_triee ; ignorer la graine -> test_graine_deterministe.

Lot R3 (2026-10-14) — tirages calculés UNE fois avec random.Random directement :
Random(0).random() x5 = 0.8444, 0.758, 0.4206, 0.2589, 0.5113 (p=0.5 garde les
rangs 2 et 3) ; Random(1) x5 = 0.1344, 0.8474, 0.7638, 0.2551, 0.4954 (garde
0, 3, 4) ; Random(0).uniform(0, 90) = 75.998 PUIS .random() = 0.758.

Revue adversariale R3 (2026-10-14) : cible propre `chat:phantom`, durée 0
refusée pour un chat hors phantom, « p = 1 consomme un tirage » gravé —
mutations listées dans le rapport du lot."""
import pytest

from didier_rehearsal.scenario import ScenarioError, load_scenario

BASE = {"name": "demo", "seed": 42, "duration_s": 100.0}


def _sc(*faults, **over):
    d = dict(BASE); d.update(over); d["faults"] = list(faults); return d


def test_graine_deterministe():
    a = {"type": "pause", "process": "face_sim", "t": "random", "duration_s": 10.0}
    b = {"type": "instruction", "text": "tu boudes", "t": "random"}
    sc = load_scenario(_sc(a, b))
    assert [(f.id, f.t_s) for f in sc.faults] == [("f1", 2.501), ("f0", 57.548)]
    assert load_scenario(_sc(a, b)) == sc                       # rejouable
    sc7 = load_scenario(_sc(a, b), seed=7)
    assert sc7.seed == 7 and sc7.faults[-1].t_s == 29.145         # la graine en argument écrase


def test_timeline_triee_et_cibles():
    sc = load_scenario(_sc(
        {"id": "b", "type": "speed", "value": 0.3, "t": 50, "duration_s": 20},
        {"id": "a", "type": "relay", "relay": "cmd_vel_follow", "op": "drop", "p": 0.5, "t": 10, "duration_s": 5},
        {"id": "k", "type": "kill", "process": "route_driver", "t": 10},
    ))
    assert [f.id for f in sc.faults] == ["a", "k", "b"]
    assert sc.faults[0].target == "relay:cmd_vel_follow"
    assert sc.faults[0].params == {"relay": "cmd_vel_follow", "op": "drop", "p": 0.5}
    assert sc.faults[1].params == {"process": "route_driver", "reenable": True}
    assert sc.faults[2].params == {"value": 0.3, "restore": 1.0}


@pytest.mark.parametrize("fault, fragment", [
    ({"type": "pause", "process": "twist_deadman", "t": 0, "duration_s": 1}, "process"),
    ({"type": "pause", "process": "face_sim", "t": 0, "duration_s": 31}, "maximum 30"),
    ({"type": "kill", "process": "route_driver", "t": 0, "duration_s": 5}, "ponctuelle"),
    ({"type": "relay", "relay": "cmd_vel", "op": "zero", "t": 0, "duration_s": 1}, "relay"),
    ({"type": "relay", "relay": "cmd_vel_follow", "op": "pass", "t": 0, "duration_s": 1}, "op"),
    ({"type": "relay", "relay": "cmd_vel_follow", "op": "delay", "t": 0, "duration_s": 1}, "delay_ms"),
    ({"type": "relay", "relay": "cmd_vel_follow", "op": "drop", "p": 1.5, "t": 0, "duration_s": 1}, "p"),
    ({"type": "speed", "value": 2, "t": 0, "duration_s": 1}, "value"),
    ({"type": "instruction", "text": "  ", "t": 0}, "text"),
    ({"type": "explosion", "t": 0}, "type"),
    ({"type": "pause", "process": "face_sim", "t": -1, "duration_s": 1}, ".t"),
    ({"type": "pause", "process": "face_sim", "t": 101, "duration_s": 1}, ".t"),
    ({"type": "pause", "process": "face_sim", "t": 0, "duration_s": 1, "bonus": 1}, "inconnues"),
])
def test_refus(fault, fragment):
    with pytest.raises(ScenarioError) as exc:
        load_scenario(_sc(fault))
    assert fragment in str(exc.value)


def test_refus_racine():
    with pytest.raises(ScenarioError):
        load_scenario(_sc(duration_s=0.5))
    with pytest.raises(ScenarioError):
        load_scenario(_sc(name=""))
    with pytest.raises(ScenarioError):
        load_scenario(_sc(seed="42"))
    with pytest.raises(ScenarioError) as exc:
        load_scenario(_sc({"id": "x", "type": "instruction", "text": "a", "t": 0},
                          {"id": "x", "type": "instruction", "text": "b", "t": 1}))
    assert "double" in str(exc.value)


def test_scenario_vide_valide():
    sc = load_scenario(_sc())
    assert sc.faults == () and sc.seed == 42


# --- Lot R3 : déclencheur POI, tirage p, lubie, chat, instruction bornée ---------

def _lubie(fid, poi, **kw):
    d = {"id": fid, "type": "lubie", "t": "poi", "poi": poi, "duration_s": 60}
    d.update(kw)
    return d


def test_declencheur_poi_apres_les_temporelles_trie_par_poi_puis_id():
    sc = load_scenario(_sc(
        _lubie("z", "banc"),
        {"id": "k", "type": "kill", "process": "route_driver", "t": "poi", "poi": "anneaux"},
        {"id": "s", "type": "speed", "value": 0.4, "t": 90, "duration_s": 5},
        _lubie("a", "banc"),
    ))
    assert [f.id for f in sc.faults] == ["s", "k", "a", "z"]
    k = sc.faults[1]
    assert (k.t_s, k.trigger_poi, k.draw_p, k.target) == (None, "anneaux", 1.0, "process:route_driver")
    assert sc.faults[0].trigger_poi is None and sc.faults[0].t_s == 90.0
    assert sc.undrawn == ()


def test_lubie_params_par_defaut_et_cible_speed():
    sc = load_scenario(_sc(_lubie("l", "banc", p=0.4)), seed=1)   # Random(1) : 0.1344 < 0.4
    f = sc.faults[0]
    assert f.params == {"poi": "banc", "text": None, "stop": True, "restore": 1.0}
    assert (f.type, f.target, f.duration_s, f.draw_p) == ("lubie", "speed", 60.0, 0.4)
    # à un instant fixe : pas de déclencheur, le `poi` reste la source du texte
    g = load_scenario(_sc({"id": "m", "type": "lubie", "poi": "banc", "t": 12, "duration_s": 30,
                           "text": "tu boudes", "stop": False, "restore": 0.5})).faults[0]
    assert (g.t_s, g.trigger_poi) == (12.0, None)
    assert g.params == {"poi": "banc", "text": "tu boudes", "stop": False, "restore": 0.5}


def test_tirage_p_grave_par_graine():
    lubies = [_lubie(f"l{i}", f"poi{i}", p=0.5) for i in range(5)]
    sc0 = load_scenario(_sc(*lubies), seed=0)
    assert [f.id for f in sc0.faults] == ["l2", "l3"]
    assert sc0.undrawn == ("l0", "l1", "l4")
    sc1 = load_scenario(_sc(*lubies), seed=1)
    assert [f.id for f in sc1.faults] == ["l0", "l3", "l4"]
    assert sc1.undrawn == ("l1", "l2")
    assert load_scenario(_sc(*lubies), seed=0) == sc0          # rejouable


def test_tirage_poi_apres_les_random():
    """La lubie est AVANT le t: random dans le fichier, mais tirée APRÈS : le
    random garde son instant historique (75.998 = 1er tirage de la graine 0)
    et la lubie reçoit le 2e (0.758 < 0.8 -> gardée ; tirée en premier, elle
    aurait reçu 0.8444 et serait écartée)."""
    sc = load_scenario(_sc(_lubie("l", "banc", p=0.8),
                           {"id": "r", "type": "pause", "process": "face_sim", "t": "random", "duration_s": 10}),
                       seed=0)
    assert [(f.id, f.t_s) for f in sc.faults] == [("r", 75.998), ("l", None)]
    assert sc.undrawn == ()


def test_tirage_p_bornes():
    toujours = load_scenario(_sc(*[_lubie(f"a{i}", "x", p=1.0) for i in range(20)]), seed=3)
    assert len(toujours.faults) == 20 and toujours.undrawn == ()
    jamais = load_scenario(_sc(*[_lubie(f"b{i}", "x", p=0.0) for i in range(20)]), seed=3)
    assert jamais.faults == () and len(jamais.undrawn) == 20


def test_chat_params_graves():
    sc = load_scenario(_sc(
        {"id": "d", "type": "chat", "op": "delay", "params": {"delay_ms": 6000}, "t": 0, "duration_s": 40},
        {"id": "g", "type": "chat", "op": "garble", "t": 1, "duration_s": 30},
        {"id": "h", "type": "chat", "op": "garble", "params": {"texts": ["Astérix"]}, "t": 2, "duration_s": 30},
        {"id": "f", "type": "chat", "op": "phantom", "params": {"text": "Amara.org"}, "t": 3},
        {"id": "m", "type": "chat", "op": "mute", "t": 4, "duration_s": 60},
    ))
    assert [(f.id, f.params, f.target) for f in sc.faults] == [
        ("d", {"op": "delay", "params": {"delay_ms": 6000}}, "chat"),
        ("g", {"op": "garble", "params": {}}, "chat"),
        ("h", {"op": "garble", "params": {"texts": ["Astérix"]}}, "chat"),
        ("f", {"op": "phantom", "params": {"text": "Amara.org"}}, "chat:phantom"),   # cible propre (revue R3)
        ("m", {"op": "mute", "params": {}}, "chat"),
    ]


def test_bornes_de_duree_r3_acceptees():
    sc = load_scenario(_sc(
        {"id": "i", "type": "instruction", "text": "boude", "t": 0, "duration_s": 120},
        {"id": "i0", "type": "instruction", "text": "ponctuelle", "t": 0},
        _lubie("l", "banc", duration_s=120),
        {"id": "c", "type": "chat", "op": "deaf", "t": 0, "duration_s": 60},
    ))
    assert {f.id: f.duration_s for f in sc.faults} == {"i": 120.0, "i0": 0.0, "l": 120.0, "c": 60.0}


@pytest.mark.parametrize("fault, fragment", [
    # déclencheur POI
    ({"type": "kill", "process": "route_driver", "t": "poi"}, ".poi : nom de POI"),
    ({"type": "kill", "process": "route_driver", "t": "poi", "poi": ""}, ".poi : nom de POI"),
    ({"type": "lubie", "poi": "banc", "t": 0, "duration_s": 5, "p": 0.5}, "réservé aux déclencheurs"),
    ({"type": "pause", "process": "face_sim", "t": 0, "duration_s": 5, "p": 0.5}, "réservé aux déclencheurs"),
    ({"type": "lubie", "poi": "banc", "t": "poi", "duration_s": 5, "p": 1.5}, ".p : <= 1.0"),
    ({"type": "lubie", "poi": "banc", "t": "poi", "duration_s": 5, "p": -0.1}, ".p : >= 0.0"),
    ({"type": "relay", "relay": "cmd_vel_follow", "op": "drop", "p": 0.5, "t": "poi", "poi": "banc",
      "duration_s": 5}, "ambigu"),
    ({"type": "pause", "process": "face_sim", "t": 0, "duration_s": 5, "poi": "banc"}, "inconnues"),
    # lubie
    ({"type": "lubie", "t": 0, "duration_s": 5}, ".poi : nom de POI"),
    ({"type": "lubie", "poi": "banc", "t": 0, "duration_s": 5, "text": "  "}, ".text"),
    ({"type": "lubie", "poi": "banc", "t": 0, "duration_s": 5, "stop": "oui"}, ".stop"),
    ({"type": "lubie", "poi": "banc", "t": 0, "duration_s": 5, "restore": 2}, ".restore"),
    ({"type": "lubie", "poi": "banc", "t": 0, "duration_s": 120.5}, "maximum 120"),
    ({"type": "lubie", "poi": "banc", "t": 0, "duration_s": 5, "bonus": 1}, "inconnues"),
    # chat
    ({"type": "chat", "op": "pass", "t": 0, "duration_s": 5}, ".op"),
    ({"type": "chat", "op": "explose", "t": 0, "duration_s": 5}, ".op"),
    ({"type": "chat", "op": "delay", "t": 0, "duration_s": 5}, "delay_ms"),
    ({"type": "chat", "op": "delay", "params": {"delay_ms": 0}, "t": 0, "duration_s": 5}, "delay_ms"),
    ({"type": "chat", "op": "delay", "params": {"delay_ms": 1.5}, "t": 0, "duration_s": 5}, "delay_ms"),
    ({"type": "chat", "op": "delay", "params": {"delay_ms": True}, "t": 0, "duration_s": 5}, "delay_ms"),
    ({"type": "chat", "op": "garble", "params": {"texts": []}, "t": 0, "duration_s": 5}, "texts"),
    ({"type": "chat", "op": "garble", "params": {"texts": ["a", ""]}, "t": 0, "duration_s": 5}, "texts"),
    ({"type": "chat", "op": "phantom", "t": 0}, ".text"),
    ({"type": "chat", "op": "phantom", "params": {"text": "x"}, "t": 0, "duration_s": 1}, "ponctuelle"),
    ({"type": "chat", "op": "deaf", "params": {"delay_ms": 5}, "t": 0, "duration_s": 5}, "inconnues"),
    ({"type": "chat", "op": "deaf", "params": [1], "t": 0, "duration_s": 5}, "dictionnaire"),
    ({"type": "chat", "op": "mute", "t": 0, "duration_s": 60.5}, "maximum 60"),
    # instruction bornée
    ({"type": "instruction", "text": "boude", "t": 0, "duration_s": 120.5}, "maximum 120"),
])
def test_refus_r3(fault, fragment):
    with pytest.raises(ScenarioError) as exc:
        load_scenario(_sc(fault))
    assert fragment in str(exc.value)
    assert "faults[0]" in str(exc.value)                         # OÙ, toujours


def test_references_a_l_itineraire():
    pois = {"banc": "Un banc : tu veux t'asseoir.", "flaque": ""}
    ok = load_scenario(_sc(_lubie("a", "banc"),
                           _lubie("b", "flaque", text="tu refuses de passer"),
                           {"id": "k", "type": "kill", "process": "route_driver", "t": "poi", "poi": "flaque"}),
                       pois=pois)
    assert [f.id for f in ok.faults] == ["a", "b", "k"]        # (poi, id) : banc < flaque
    for fault, fragment in [
        (_lubie("x", "statue"), "« statue » absent de l'itinéraire"),
        ({"id": "x", "type": "lubie", "poi": "statue", "t": 0, "duration_s": 5}, "« statue » absent"),
        ({"id": "x", "type": "kill", "process": "route_driver", "t": "poi", "poi": "statue"}, "« statue » absent"),
        (_lubie("x", "flaque"), "pas de champ lubie"),
        # écarté par le tirage (p = 0) : vérifié QUAND MÊME, la graine ne décide pas du refus
        (_lubie("x", "statue", p=0.0), "« statue » absent"),
    ]:
        with pytest.raises(ScenarioError) as exc:
            load_scenario(_sc(fault), pois=pois)
        assert fragment in str(exc.value)
    # sans itinéraire fourni : aucune vérification (contrats, tests)
    assert load_scenario(_sc(_lubie("x", "statue"))).faults[0].trigger_poi == "statue"


# --- Revue adversariale R3 (2026-10-14) ---------------------------------------------

def test_tirage_p_1_consomme_quand_meme_un_tirage():
    """Random(0) : 0.8444 (l0), 0.758 (l1), 0.4206 (l2 : < 0.5 -> gardée).
    Si un p = 1 sautait son tirage, l2 recevrait 0.8444 et serait écartée :
    passer un p à 1 décalerait les tirages de tous les suivants."""
    sc = load_scenario(_sc(_lubie("l0", "a", p=1.0), _lubie("l1", "b", p=1.0),
                           _lubie("l2", "c", p=0.5)), seed=0)
    assert [f.id for f in sc.faults] == ["l0", "l1", "l2"]
    assert sc.undrawn == ()


@pytest.mark.parametrize("raw", [
    {"type": "chat", "op": "delay", "params": {"delay_ms": 6000}, "t": 0},          # durée absente = 0
    {"type": "chat", "op": "garble", "t": 0, "duration_s": 0},
    {"type": "chat", "op": "deaf", "t": 0, "duration_s": 0.0},
    {"type": "chat", "op": "mute", "t": "random", "duration_s": 0},
])
def test_chat_duree_zero_refusee_hors_phantom(raw):
    """0 côté chat_node = SON plafond de 60 s, pas « ponctuel » : refusé."""
    with pytest.raises(ScenarioError) as exc:
        load_scenario(_sc(raw))
    assert f"faults[0].duration_s : 0 refusé pour chat {raw['op']}" in str(exc.value)


def test_phantom_ponctuel_sur_sa_propre_cible():
    sc = load_scenario(_sc(
        {"id": "p", "type": "chat", "op": "phantom", "params": {"text": "Amara.org"}, "t": 0},
        {"id": "g", "type": "chat", "op": "garble", "t": 1, "duration_s": 30},
    ))
    assert [(f.id, f.duration_s, f.target) for f in sc.faults] == [
        ("p", 0.0, "chat:phantom"), ("g", 30.0, "chat")]
