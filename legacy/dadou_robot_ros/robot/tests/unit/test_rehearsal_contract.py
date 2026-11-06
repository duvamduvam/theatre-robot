"""Contrats GELÉS de la salle de répétition (robot_rehearsal) — lus dans les
VRAIS fichiers (package, itinéraire, launch de bringup), jamais des copies.

Trois garanties :
 1. plafonds durs IDENTIQUES à ceux du suivi de personne (même créneau du
    mux, mêmes 50 kg) ;
 2. ANTI-FUITE : le package sim-only n'est référencé nulle part dans le code
    embarqué (robot/, didier_bringup, didier_drive, didier_web) ;
 3. l'itinéraire livré (config/rue.yaml) est valide, reste sur le trottoir du
    monde rue.sdf, et ses POI sont exactement ceux attendus ;
 4. lot R3 « chantiers » : itinéraire (30 POI dans l'ordre de la marche, étude
    §13.3) et scénario (20 bugs du §13.5, 30 lubies) gravés, topics et bornes
    partagés avec chat_node gravés.
"""
import pathlib

import pytest
import yaml

from robot.move.follow_control import ABS_MAX_ANG as FOLLOW_MAX_ANG, ABS_MAX_LIN as FOLLOW_MAX_LIN
from robot_rehearsal import contracts
from robot_rehearsal.route import load_route

ROOT = pathlib.Path(__file__).resolve().parents[3]
PACKAGES = ROOT.parents[1] / "packages"          # packages/ du mono-dépôt (L1e-1)
PKG = PACKAGES / "robot_rehearsal"

# Géométrie du trottoir de rue.sdf (dupliquée depuis la spec du monde, étude
# §12 : trottoir 70 x 3 centré (30, 0) -> x ∈ [-5, 65], y ∈ [-1.5, 1.5]).
TROTTOIR_X = (-5.0, 65.0)
TROTTOIR_Y = (-1.5, 1.5)


def test_plafonds_identiques_au_suivi():
    assert contracts.ABS_MAX_LIN == FOLLOW_MAX_LIN == 0.5
    assert contracts.ABS_MAX_ANG == FOLLOW_MAX_ANG == 1.0


def test_sortie_sur_le_creneau_du_suivi_jamais_cmd_vel_final():
    assert contracts.CMD_VEL_TOPIC == "cmd_vel_follow"
    assert contracts.CMD_VEL_TOPIC != "cmd_vel"
    # RELATIF depuis L1b (namespace par robot) ; le topic gz reste absolu, cf. ci-dessous.
    assert contracts.ODOM_TOPIC == "ground_truth/odom"
    assert contracts.ROUTE_STATE_TOPIC == "route_state"
    # Revue I1 (22/10) : cause latchée de l'état, "boot" | "cmd".
    assert contracts.ROUTE_STATE_CAUSE_TOPIC == "route_state_cause"
    assert contracts.ROUTE_STATE_CAUSES == ("boot", "cmd")


def test_verite_terrain_declaree_dans_le_xacro_et_le_bridge():
    """Le topic de pose consommé par le cheminement doit exister de bout en
    bout : plugin OdometryPublisher dans le xacro gz ET entrée GZ_TO_ROS du
    bridge, avec le MÊME nom que le contrat côté ROS (relatif depuis L1b) et le
    nom gz du plugin (absolu, le monde gz ignore les namespaces ROS). Lu dans
    les vrais fichiers."""
    xacro = (PACKAGES / "didier_description" / "urdf"
             / "dadou_robot_gz.urdf.xacro").read_text(encoding="utf-8")
    assert "gz::sim::systems::OdometryPublisher" in xacro
    assert "<odom_topic>/ground_truth/odom</odom_topic>" in xacro
    bridge = yaml.safe_load((PACKAGES / "didier_sim" / "config"
                             / "gz_bridge.yaml").read_text(encoding="utf-8"))
    entries = [e for e in bridge if e["ros_topic_name"] == contracts.ODOM_TOPIC]
    assert len(entries) == 1
    assert entries[0]["ros_type_name"] == "nav_msgs/msg/Odometry"
    assert entries[0]["direction"] == "GZ_TO_ROS"
    assert entries[0]["gz_topic_name"] == "/ground_truth/odom"


def test_anti_fuite_aucune_reference_dans_le_code_embarque():
    zones = [
        ROOT / "robot",
        ROOT / "conf" / "ros2",
        PACKAGES / "didier_bringup",
        PACKAGES / "didier_drive",
        PACKAGES / "didier_web",
    ]
    fuites = []
    for zone in zones:
        for path in zone.rglob("*"):
            if not path.is_file() or path.suffix not in (".py", ".xml", ".yaml", ".yml", ".sh", ".txt", ".cfg"):
                continue
            if "tests" in path.parts:   # les tests ont le droit d'en parler
                continue
            if "robot_rehearsal" in path.read_text(encoding="utf-8", errors="ignore"):
                fuites.append(str(path.relative_to(ROOT)))
    assert fuites == [], f"robot_rehearsal référencé dans le code embarqué : {fuites}"


def test_itineraire_rue_valide_et_sur_le_trottoir():
    with (PKG / "config" / "rue.yaml").open(encoding="utf-8") as f:
        route = load_route(yaml.safe_load(f))
    assert route.name == "hangar-a-bananes"
    assert len(route.waypoints) == 10
    for x, y in route.waypoints:
        assert TROTTOIR_X[0] <= x <= TROTTOIR_X[1]
        assert TROTTOIR_Y[0] <= y <= TROTTOIR_Y[1]
    # Monotone en x : on va vers le hangar, jamais en arrière.
    xs = [x for x, _ in route.waypoints]
    assert xs == sorted(xs)
    assert tuple(p.name for p in route.pois) == (
        "lampadaire_1", "banc", "boulangerie", "lampadaire_2", "chien",
        "poubelle", "terrasse", "lampadaire_3", "hangar_bananes",
    )


def test_relais_jamais_sur_la_chaine_de_securite():
    """Aucun point de relais ne touche /cmd_vel final, la télécommande ni le
    web : un relais ne peut être posé que sur ce que rehearsal.launch.py lance."""
    for name, (amont, aval, typ) in contracts.RELAYS.items():
        assert aval == name
        assert amont == f"{name}_raw"
        assert aval not in ("cmd_vel", "cmd_vel_mux", "cmd_vel_remote", "cmd_vel_web", "e_stop", "wheels")
        assert typ in ("twist", "string_time")
    assert set(contracts.RELAY_OPS) == {"pass", "drop", "delay", "freeze", "zero"}
    assert contracts.HEARTBEAT_TIMEOUT_MS == 1000
    assert contracts.FAULT_MAX_DURATION_S["kill"] == 0.0 and contracts.FAULT_MAX_DURATION_S["pause"] == 30.0


def test_scenarios_livres_valides():
    """Chaque YAML de config/scenarios/ se charge (refus explicite sinon) et ne
    cible que des processus/relais des listes blanches — par construction."""
    from robot_rehearsal.scenario import load_scenario
    files = sorted((PKG / "config" / "scenarios").glob("*.yaml"))
    assert [f.name for f in files] == ["chantiers.yaml", "demo.yaml", "jeu-a1.yaml"]
    for f in files:
        sc = load_scenario(yaml.safe_load(f.read_text(encoding="utf-8")))
        # jeu-a1 (lot A1) est VIDE exprès : le sélecteur de jeu décide seul,
        # un tirage du régisseur ferait doublon avec ses lubies.
        if f.name == "jeu-a1.yaml":
            assert sc.faults == () and sc.duration_s == 3600.0, f.name
        else:
            assert sc.faults, f.name
    demo = load_scenario(yaml.safe_load((PKG / "config" / "scenarios" / "demo.yaml").read_text(encoding="utf-8")))
    # couverture : chaque type de panne au moins une fois dans la démo (V-R2 s'en sert)
    assert {f.type for f in demo.faults} == {"relay", "pause", "kill", "speed", "instruction"}


def test_import_robot_limite_au_journal_pur():
    """Seule dépendance vers robot.* autorisée : robot.diagnostic.journal (pur,
    stdlib). Tout autre import de robot.* (robot_config, matériel…) ferait
    dépendre la sim du robot réel — refusé."""
    import re
    for path in sorted((PKG / "robot_rehearsal").glob("*.py")):
        for m in re.finditer(r"^\s*(?:from|import)\s+(robot\.[\w.]*|robot)\b", path.read_text(encoding="utf-8"), re.M):
            assert m.group(1) == "robot.diagnostic.journal", (path.name, m.group(0))


def test_garde_fou_domaine():
    from robot_rehearsal.contracts import SIM_DOMAIN_ID, check_domain
    assert SIM_DOMAIN_ID == 43
    assert check_domain({"ROS_DOMAIN_ID": "43"}) == 43
    for env in ({}, {"ROS_DOMAIN_ID": "42"}, {"ROS_DOMAIN_ID": "0"}, {"ROS_DOMAIN_ID": "abc"}):
        with pytest.raises(RuntimeError) as exc:
            check_domain(env)
        assert "42 est le vrai robot" in str(exc.value)
    # Gravé COMPLET (lot R3 : instruction 0 -> 120, lubie 120, chat 60 — étude §13.4).
    assert contracts.FAULT_MAX_DURATION_S == {"relay": 60.0, "pause": 30.0, "kill": 0.0,
                                              "speed": 120.0, "instruction": 120.0,
                                              "lubie": 120.0, "chat": 60.0}


def test_launch_off_par_defaut():
    launch = (PKG / "launch" / "rehearsal.launch.py").read_text(encoding="utf-8")
    assert 'DeclareLaunchArgument("enabled", default_value="false"' in launch
    # le régisseur ne démarre un scénario que sur "start" (autostart false)
    assert 'DeclareLaunchArgument("autostart", default_value="false"' in launch
    # route_driver publie vers l'amont du relais (remap), jamais directement
    assert '("cmd_vel_follow", "cmd_vel_follow_raw")' in launch


# --- Lot R3 « chantiers » (étude §13) ---------------------------------------------

# Ordre RÉEL de la marche Nefs -> Mail -> quai des Antilles -> Titan (§13.3).
CHANTIERS_POI = (
    "nefs", "elephant", "carrousel", "table_basse", "poster_bizarre", "poubelle_tri",
    "pigeon", "banc", "flaque", "terrasse", "grue_jaune", "cale", "velo_cadenas",
    "panneau_info", "rails", "lampadaire", "anneaux", "bollard", "loire", "plot_chantier",
    "chien", "caisse_bois", "hangar_bananes", "tas_de_sable", "horloge_arretee",
    "bouche_incendie", "pelouse", "conteneur_rouge", "tag_mur", "titan_grise",
)

# Les 20 bugs du §13.5 : id -> (type, durée, params validés). Recopiés du tableau.
CHANTIERS_BUGS = {
    "liaison": ("pause", 5.0, {"process": "route_driver"}),
    "arret_net": ("relay", 6.0, {"relay": "cmd_vel_follow", "op": "zero"}),
    "pause_syndicale": ("relay", 4.0, {"relay": "cmd_vel_follow", "op": "freeze"}),
    "acoups": ("relay", 10.0, {"relay": "cmd_vel_follow", "op": "drop", "p": 0.7}),
    "retard": ("relay", 10.0, {"relay": "cmd_vel_follow", "op": "delay", "delay_ms": 1500}),
    "batterie": ("speed", 20.0, {"value": 0.4, "restore": 1.0}),
    "fader_mort": ("speed", 8.0, {"value": 0.0, "restore": 1.0}),
    "emballement": ("speed", 6.0, {"value": 1.0, "restore": 1.0}),
    "visage_fige": ("pause", 6.0, {"process": "face_sim"}),
    "ruban_noir": ("pause", 6.0, {"process": "leds_sim_node"}),
    "bras_en_greve": ("pause", 8.0, {"process": "servos_sim_node"}),
    "sequence_bloquee": ("pause", 8.0, {"process": "animations_node"}),
    "regard_fige": ("pause", 8.0, {"process": "gaze_follower"}),
    "reboot": ("kill", 0.0, {"process": "route_driver", "reenable": True}),
    "reboot_sans_reprise": ("kill", 0.0, {"process": "route_driver", "reenable": False}),
    "latence_pi": ("chat", 40.0, {"op": "delay", "params": {"delay_ms": 6000}}),
    "contresens": ("chat", 30.0, {"op": "garble", "params": {}}),
    "sourd": ("chat", 20.0, {"op": "deaf", "params": {}}),
    "muet": ("chat", 20.0, {"op": "mute", "params": {}}),
    "parle_au_bus": ("chat", 0.0, {"op": "phantom",
                                   "params": {"text": "Sous-titres réalisés par la communauté d'Amara.org"}}),
}


def _yaml(*parts):
    return yaml.safe_load((PKG.joinpath(*parts)).read_text(encoding="utf-8"))


def test_topics_et_ops_partages_avec_chat_node():
    assert contracts.INSTRUCTION_TOPIC == "chat_instruction"
    assert contracts.CHAT_FAULT_TOPIC == "rehearsal/chat_fault"
    assert contracts.CHAT_FAULT_OPS == ("pass", "delay", "garble", "deaf", "mute", "phantom")
    assert contracts.POI_EVENT_TOPIC == "rehearsal/poi_event"
    # Lot I1 : même littéral que CHAT_MOVE_TOPIC de chat_node (dépôt vision).
    assert contracts.CHAT_MOVE_TOPIC == "rehearsal/chat_move"


def test_itineraire_chantiers():
    route = load_route(_yaml("config", "chantiers.yaml"))
    assert route.name == "nefs-titan-grise"
    assert tuple(p.name for p in route.pois) == CHANTIERS_POI
    for p in route.pois:
        assert p.lubie.strip(), p.name                   # la consigne part telle quelle au chat
        assert p.fermeture.strip(), p.name
    # le but : la polyligne finit au pied de la Titan grise (dans son rayon)
    titan = route.pois[-1]
    x, y = route.waypoints[-1]
    assert titan.radius == 6.0 and (x - titan.x) ** 2 + (y - titan.y) ** 2 < titan.radius ** 2


def test_scenario_chantiers_20_bugs_et_30_lubies():
    from robot_rehearsal.scenario import load_scenario
    data = _yaml("config", "scenarios", "chantiers.yaml")
    assert (data["name"], data["seed"], data["duration_s"]) == ("chantiers", 0, 900)
    raw_bugs = [f for f in data["faults"] if f["type"] != "lubie"]
    raw_lubies = [f for f in data["faults"] if f["type"] == "lubie"]
    assert [f["id"] for f in raw_bugs] == list(CHANTIERS_BUGS)
    assert all(f["t"] == "random" for f in raw_bugs)
    assert len(raw_lubies) == 30
    # une lubie par POI, dans l'ordre de la marche, id = lubie_<poi>
    assert [f["poi"] for f in raw_lubies] == list(CHANTIERS_POI)
    for f in raw_lubies:
        assert f["id"] == f"lubie_{f['poi']}" and f["t"] == "poi" and "text" not in f
        if f["poi"] == "titan_grise":
            assert (f["p"], f["duration_s"], f["stop"]) == (1.0, 90, True)   # le final, toujours
        else:
            assert (f["p"], f["duration_s"]) == (0.4, 60)
    # chargé CONTRE l'itinéraire du même nom : chaque POI existe, chaque lubie a un texte
    route = load_route(_yaml("config", "chantiers.yaml"))
    sc = load_scenario(data, pois={p.name: p.lubie for p in route.pois})
    bugs = {f.id: (f.type, f.duration_s, f.params) for f in sc.faults if f.type != "lubie"}
    assert bugs == CHANTIERS_BUGS
    tirees = {f.id for f in sc.faults if f.type == "lubie"}
    assert tirees | set(sc.undrawn) == {f"lubie_{n}" for n in CHANTIERS_POI}
    assert not tirees & set(sc.undrawn)
    assert "lubie_titan_grise" in tirees


def test_launch_passe_l_itineraire_au_regisseur():
    launch = (PKG / "launch" / "rehearsal.launch.py").read_text(encoding="utf-8")
    director = launch.split('executable="director"')[1]
    assert '"route_file": route_file' in director


def test_launch_passe_la_vitesse_initiale_au_regisseur_et_seuil_du_fader():
    """Revue R3 (14/10) : le régisseur rend la vitesse du launch tant qu'aucun
    fader n'a parlé — la MÊME substitution que route_driver, sinon les deux
    divergent dès `speed:=0.3`. Seuil de fermeture au fader gravé."""
    launch = (PKG / "launch" / "rehearsal.launch.py").read_text(encoding="utf-8")
    route_driver, director = launch.split('executable="route_driver"')[1].split('executable="director"')
    attendu = '"speed": ParameterValue(LaunchConfiguration("speed"), value_type=float)'
    assert attendu in route_driver and attendu in director
    assert contracts.EXTERNAL_SPEED_DELTA == 0.05


def test_launch_jeu_remappe_le_regisseur_seulement_sur_demande():
    """Lot A1 (un seul décideur du corps) : jeu:=true remappe rehearsal/chat_move
    -> jeu/chat_move sur le régisseur, et SEULEMENT dans ce cas (défaut false :
    la séance Chantiers garde la bouche en direct). Littéraux du launch = les
    contrats (le launch n'importe pas les packages)."""
    import ast
    from theatre_contrats.topics import JEU_CHAT_MOVE
    src = (PKG / "launch" / "rehearsal.launch.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    # Défauts LITTÉRAUX seulement : robot_name (L1b) a pour défaut un appel
    # EnvironmentVariable("ROBOT_NAME"…), pas une constante.
    defaults = {c.args[0].value: c.keywords[0].value.value for c in ast.walk(tree)
                if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "DeclareLaunchArgument"
                and isinstance(c.keywords[0].value, ast.Constant)}
    assert defaults["jeu"] == "false"
    calls = [c for c in ast.walk(tree) if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "_director"]
    assert len(calls) == 2
    par_condition = {c.args[2].func.id: ast.literal_eval(c.args[3]) for c in calls}
    assert par_condition == {"UnlessCondition": [],
                             "IfCondition": [(contracts.CHAT_MOVE_TOPIC, JEU_CHAT_MOVE)]}


def test_launch_jeu_demarre_le_selecteur_sous_la_meme_condition():
    """Revue A1 (bloquant 2) : avec jeu:=true le régisseur n'écoute plus la
    bouche ; le launch démarre donc LUI-MÊME jeu_node (respawn), sous la même
    IfCondition que le remap — jamais de remap sans relais du « stop »."""
    import ast
    tree = ast.parse((PKG / "launch" / "rehearsal.launch.py").read_text(encoding="utf-8"))
    noeuds = [c for c in ast.walk(tree) if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "Node"
              and any(k.arg == "package" and getattr(k.value, "value", None) == "didier_jeu" for k in c.keywords)]
    assert len(noeuds) == 1
    kw = {k.arg: k.value for k in noeuds[0].keywords}
    assert ast.unparse(kw["condition"]) == 'IfCondition(LaunchConfiguration("jeu"))'.replace('"', "'")
    assert kw["executable"].value == "jeu_node"
    assert kw["respawn"].value is True and kw["respawn_delay"].value == 2.0
