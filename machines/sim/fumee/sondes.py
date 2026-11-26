"""Sondes rclpy de la fumée (F1, 25/11), reprises TELLES QUELLES de fumee.sh. Exécutées DANS le
conteneur monde par `python3 - <sonde>`, le texte passé sur l'entrée standard : la révision testée
n'a pas besoin de contenir ce fichier. La CLI ros2 perd des messages sur ce PC (operations.md).
Jamais importé sur l'hôte (rclpy n'y est pas).
"""
import json
import os
import sys
import time

import rclpy


def noeuds():
    # Nœuds attendus des machine.yml robot ET vision (montés en lecture seule dans monde), graphe
    # vu en rclpy ; ≥ 5 s de découverte (3 s comptent trop peu, L2a).
    import yaml
    voulus = set()
    for m in ("robot", "vision"):
        with open("/home/ros2_ws/machines/%s/machine.yml" % m, encoding="utf-8") as f:
            voulus |= set(yaml.safe_load(f)["noeuds_attendus"])
    n = rclpy.create_node("fumee_noeuds")
    debut = time.monotonic()
    while time.monotonic() - debut < 8:
        rclpy.spin_once(n, timeout_sec=0.2)
    vus = {(ns.rstrip("/") + "/" + nom) for nom, ns in n.get_node_names_and_namespaces()}
    manque = sorted(voulus - vus)
    print("nœuds attendus : %d/%d%s" % (len(voulus) - len(manque), len(voulus),
                                        (" — manquent : " + " ".join(manque)) if manque else ""))
    return 1 if manque else 0


def rtf():
    # Facteur temps réel = temps simulé écoulé / temps mural écoulé, sur 20 s de /clock.
    from rclpy.qos import qos_profile_sensor_data
    from rosgraph_msgs.msg import Clock
    n = rclpy.create_node("fumee_rtf")
    ech = []
    n.create_subscription(Clock, "/clock", lambda m: ech.append(
        (time.monotonic(), m.clock.sec + m.clock.nanosec * 1e-9)), qos_profile_sensor_data)
    limite = time.monotonic() + 120          # attente du premier /clock
    while not ech and time.monotonic() < limite:
        rclpy.spin_once(n, timeout_sec=0.5)
    if not ech:
        print("RTF=0.000 messages=0")
        return 0
    debut = time.monotonic()
    while time.monotonic() - debut < 20:
        rclpy.spin_once(n, timeout_sec=0.5)
    (w0, s0), (w1, s1) = ech[0], ech[-1]
    print("RTF=%.3f messages=%d" % (((s1 - s0) / (w1 - w0)) if w1 > w0 else 0.0, len(ech)))
    return 0


def parle():
    # Joue « parle » 3 s et relève animation_state (latché des DEUX côtés : TRANSIENT_LOCAL +
    # reliable). Attendu : "" -> "parle" -> "". Abonnés de `animation` tous appariés avant
    # l'envoi, effet vérifié (3 envois au plus) : voir fumee.sh, jouer_parle.
    from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
    from theatre_interfaces.msg import StringTime
    ns = "/" + (os.environ.get("ROBOT_NAME") or "didier")
    n = rclpy.create_node("fumee_parle")
    etats = []

    def lu(m):
        try:
            e = json.loads(m.msg)
        except ValueError:
            e = "?" + m.msg
        if not etats or etats[-1] != e:      # « parle » est republié à chaque démarrage
            etats.append(e)
    qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE)
    n.create_subscription(StringTime, ns + "/animation_state", lu, qos)
    pub = n.create_publisher(StringTime, ns + "/animation", 10)

    def abonnes():
        return [i.node_name for i in n.get_subscriptions_info_by_topic(ns + "/animation")]
    limite = time.monotonic() + 40
    while time.monotonic() < limite and (not etats or "animations_node" not in abonnes()
                                         or pub.get_subscription_count() < len(abonnes())):
        rclpy.spin_once(n, timeout_sec=0.2)
    print("ABONNES=%s apparies=%d" % (json.dumps(sorted(abonnes())), pub.get_subscription_count()))
    m = StringTime()
    m.msg, m.time, m.anim = json.dumps("parle"), 3000, False
    for envoi in range(1, 4):
        pub.publish(m)
        fin_envoi = time.monotonic() + 5
        while time.monotonic() < fin_envoi and "parle" not in etats:
            rclpy.spin_once(n, timeout_sec=0.2)
        if "parle" in etats:
            break
    print("ENVOIS=%d" % envoi)
    limite = time.monotonic() + 20
    while time.monotonic() < limite and not (len(etats) >= 3 and etats[-1] == ""):
        rclpy.spin_once(n, timeout_sec=0.2)
    attendu, trouves = ["", "parle", ""], 0
    for e in etats:
        if trouves < 3 and e == attendu[trouves]:
            trouves += 1
    print("ETATS=%s" % json.dumps(etats))
    print("PARLE %d OK" % trouves)
    return 0


if __name__ == "__main__":
    rclpy.init()
    sys.exit({"noeuds": noeuds, "rtf": rtf, "parle": parle}[sys.argv[1]]())
