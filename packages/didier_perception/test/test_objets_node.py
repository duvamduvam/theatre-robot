"""objets_node : littéraux gravés avec la régie, contrat du nœud (aucun Twist), cap 2D."""
import math
import pathlib
import types

from didier_perception import objets_node
from didier_rehearsal import contracts

NODE = pathlib.Path(objets_node.__file__).read_text(encoding="utf-8")


def test_litteraux_graves_avec_la_regie():
    assert objets_node.CARTE_TOPIC == contracts.OBJECTS_TOPIC == "rehearsal/objects"
    assert objets_node.ODOM_TOPIC == contracts.ODOM_TOPIC == "ground_truth/odom"
    assert (objets_node.POSE_TTL_S, objets_node.PERIODE_S) == (1.0, 1.0)


def test_publie_latche_et_jamais_de_twist():
    assert "self.create_publisher(StringTime, topics.SCENE_OBJETS, qos.latched())" in NODE
    assert "self.create_subscription(StringTime, CARTE_TOPIC, self._on_carte, qos.latched())" in NODE
    assert "Twist" not in NODE.replace("aucun Twist", "")


def test_cap_depuis_quaternion():
    q = types.SimpleNamespace(x=0.0, y=0.0, z=math.sin(math.radians(25) / 2), w=math.cos(math.radians(25) / 2))
    assert abs(math.degrees(objets_node.cap_depuis_quaternion(q)) - 25.0) < 1e-9
