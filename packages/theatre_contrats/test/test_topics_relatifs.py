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


def test_topics_du_jeu_graves():
    # Lot A1 (sélecteur de jeu) : valeurs DE FIL, partagées avec la page scène
    # (didier_web) et le remap du régisseur (rehearsal.launch.py jeu:=true).
    assert topics.JEU_CONSOLE == "jeu/console"
    assert topics.JEU_INTENTION == "jeu/intention"
    assert topics.JEU_CHAT_MOVE == "jeu/chat_move"
    assert topics.JEU_JOURNAL == "jeu/journal"


def test_topics_catalogue_graves():
    # Lot L1c : valeurs DE FIL, lues par la page scène (deploy_sha), la
    # télécommande et validate-catalogue.sh.
    assert topics.CATALOGUE == "catalogue"
    assert topics.DEPLOY_SHA == "deploy_sha"


def test_topics_edition_graves():
    # Lot L1d : valeurs DE FIL, partagées avec la page scène (L1d-3), le rechargement à
    # chaud des nœuds du robot et validate-data-edit.sh.
    assert topics.DATA_EDIT == "data_edit"
    assert topics.DATA_EDIT_RESULT == "data_edit_result"


def test_topics_porte_sim_graves():
    # Lot L1d-2 : valeurs DE FIL, partagées avec la page scène (L1d-3), l'observateur
    # validation_sim_node, animations_node (refus) et machines/sim/rejouer-modifiees.sh.
    assert topics.VALIDATION_SIM == "validation_sim"
    assert topics.VALIDATION_SIM_DEMANDE == "validation_sim_demande"
    assert topics.ROUES_REFUSEES == "roues_refusees"


def test_nombre_de_topics_grave():
    # 10 organes + 6 StringTime hors organes + 3 perception + 4 jeu (lot A1)
    # + 2 catalogue/version (lot L1c) + 2 édition (lot L1d) + 3 porte sim (lot L1d-2).
    assert len(_noms_de_topics()) == 30
