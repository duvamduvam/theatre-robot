"""Horloge simulée décimée (21/11) : relais_horloge remplace le pont ros_gz pour /clock.

Mesuré le 21/11 (sim chantiers au repos) : le pont relayait /clock à ≈ 954 Hz ; chaque nœud Python
en use_sim_time y laissait 38 à 62 % d'un cœur. Le corps sûr, figé sous la charge, se verrouillait
(fumée 2026-11-21-1929, V-R3). Valeurs GRAVÉES ; la preuve en sim est la fumée.

Pourquoi 200 Hz (pas de 5 ms) : la plus petite minuterie sur horloge simulée est le tic du corps
sûr (50 ms) ; le chien de garde est à 0,30 s, le deadman à 0,40 s, la porte de l'étude à 200 ms.
Un pas de 5 ms leur ajoute au plus 5 ms ; 100 Hz en ajouterait 10, sans gain mesurable de plus.
"""
import ast
import pathlib
import re

import yaml

SIM = pathlib.Path(__file__).resolve().parents[3] / "didier_sim"
FREQUENCE_HZ = 200.0


def _noeud_relais():
    arbre = ast.parse((SIM / "launch" / "monde.launch.py").read_text(encoding="utf-8"))
    noeuds = [n for n in ast.walk(arbre) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "Node"]
    relais = [n for n in noeuds if any(k.arg == "executable" and ast.literal_eval(k.value) == "relais_horloge"
                                       for k in n.keywords)]
    assert len(relais) == 1
    return {k.arg: k.value for k in relais[0].keywords}


def test_le_relais_est_lance_a_200_hz_a_l_horloge_murale():
    kw = _noeud_relais()
    assert ast.literal_eval(kw["package"]) == "didier_sim"
    assert ast.literal_eval(kw["parameters"]) == [{"use_sim_time": False, "frequence_hz": FREQUENCE_HZ}]


def test_le_pont_ne_relaie_plus_clock():
    entrees = yaml.safe_load((SIM / "config" / "gz_bridge.yaml").read_text(encoding="utf-8"))
    assert all("clock" not in e["ros_topic_name"] and "clock" not in e["gz_topic_name"] for e in entrees)
    lidar = yaml.safe_load((SIM / "config" / "pont_lidar.yaml").read_text(encoding="utf-8"))
    assert all("clock" not in e["ros_topic_name"] for e in lidar)


def test_le_relais_cpp_graves():
    src = (SIM / "src" / "relais_horloge.cpp").read_text(encoding="utf-8")
    assert "constexpr double FREQUENCE_DEFAUT_HZ = 200.0;" in src
    assert 'gz_.Subscribe("/clock"' in src
    assert 'create_publisher<rosgraph_msgs::msg::Clock>("/clock", rclcpp::QoS(10).reliable())' in src
    # Décimation sur l'horloge SIMULÉE, temps du pas publié tel quel ; un recul passe tout de suite.
    assert "if (precedent >= 0 && t >= precedent && t - precedent < periode_ns_) {" in src
    # gz_ détruit le premier (dernier membre) : plus de rappel sur un éditeur détruit.
    membres = re.findall(r"^  (?:rclcpp|int64_t|std::atomic|gz::transport)\S*[^;(]* (\w+_)[{;]", src, re.M)
    assert membres[-1] == "gz_"


def test_le_relais_est_construit_et_installe():
    cmake = (SIM / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "add_executable(relais_horloge src/relais_horloge.cpp)" in cmake
    assert "install(TARGETS relais_horloge DESTINATION lib/${PROJECT_NAME})" in cmake
    # FACULTATIF : didier_sim se construit aussi dans le conteneur robot et sur le Pi, sans Gazebo
    # (21/11 : un find_package REQUIRED a cassé colcon dans le conteneur robot).
    assert "find_package(gz_transport_vendor QUIET)" in cmake
    assert "if(gz_transport_vendor_FOUND AND gz_msgs_vendor_FOUND)" in cmake
    assert "gz_transport_vendor REQUIRED" not in cmake
    xml = (SIM / "package.xml").read_text(encoding="utf-8")
    for dep in ("rclcpp", "rosgraph_msgs"):
        assert f"<depend>{dep}</depend>" in xml
    assert "<depend>gz_transport_vendor</depend>" not in xml and "<depend>gz_msgs_vendor</depend>" not in xml
