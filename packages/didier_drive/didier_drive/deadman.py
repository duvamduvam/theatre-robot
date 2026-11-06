"""Deadman logiciel sur le flux cmd_vel, indépendant de ROS.

Même philosophie que MOVE_TIMEOUT=400 dans robot/actions/wheels.py : si aucune
commande n'arrive pendant timeout_ms, on considère la source silencieuse et on
doit couper. L'horloge (now_ms) est passée en paramètre par l'appelant pour
rester testable sans monkeypatch.
"""


class TwistDeadman:

    def __init__(self, timeout_ms=400):
        self.timeout_ms = timeout_ms
        self.last_feed_ms = None

    def feed(self, now_ms):
        """Une commande vient d'arriver : on réarme le deadman."""
        self.last_feed_ms = now_ms

    def is_expired(self, now_ms) -> bool:
        """Vrai si aucune commande depuis plus de timeout_ms (ou jamais nourri)."""
        if self.last_feed_ms is None:
            return True
        return (now_ms - self.last_feed_ms) > self.timeout_ms
