"""Les deux profils QoS du parc Didier.

- volatile(depth) : le défaut ROS (RELIABLE, VOLATILE) — équivalent à passer
  l'entier `depth` à create_publisher/create_subscription.
- latched() : TRANSIENT_LOCAL, depth 1 — le dernier message est rejoué à tout
  abonné qui arrive en retard (état d'animation, état de route, personnalité).
  PIÈGE payé le 2026-07-12 : il faut TRANSIENT_LOCAL DES DEUX CÔTÉS ; un
  abonné volatile ne reçoit jamais l'état latché.

rclpy est importé À L'APPEL, pas au chargement du module : theatre_contrats
doit rester importable sur le PC sans ROS.
"""


def volatile(depth=10):
    from rclpy.qos import QoSProfile
    return QoSProfile(depth=depth)


def latched():
    from rclpy.qos import DurabilityPolicy, QoSProfile
    return QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
