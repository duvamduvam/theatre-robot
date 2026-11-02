"""Aucun nom de topic n'est absolu : au lot L1b chaque robot aura son
namespace, et un nom en « /… » y échapperait (il viserait TOUS les robots)."""
from theatre_contrats import topics


def _noms_de_topics():
    return {nom: valeur for nom, valeur in vars(topics).items()
            if nom.isupper() and isinstance(valeur, str)}


def test_aucun_topic_absolu():
    absolus = {n: v for n, v in _noms_de_topics().items() if v.startswith("/")}
    assert absolus == {}


def test_topics_de_la_vision_graves():
    # Valeurs DE FIL : sans namespace, elles se résolvent en /vision/... comme
    # les anciens noms absolus (calibre-distance.sh, docs, `ros2 topic pub` à la main).
    assert topics.VISION_PERSON == "vision/person"
    assert topics.VISION_PERSON_BOX == "vision/person_box"
    assert topics.VISION_STATUS == "vision/status"


def test_nombre_de_topics_grave():
    # 10 organes + 6 StringTime hors organes + 3 perception.
    assert len(_noms_de_topics()) == 19
