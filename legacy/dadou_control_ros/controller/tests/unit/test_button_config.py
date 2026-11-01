"""Cohérence des mappings boutons -> commandes.

Ros2TkinterApp.publish() ne publie que les clés présentes dans PUBLISHER_LIST
et ignore silencieusement les autres : ce test garantit qu'aucune commande de
BUTTONS_LAYOUT ne vise un topic inconnu (sauf commandes locales assumées).
"""

from dadou_utils_ros.utils_static import DEFAULT, DURATION, MODE, NAME
from controller.control_static import CMD, DESIGNATE, FOLLOW, PLAYLIST, SELECT, START
from controller.buttons.button_config import BUTTONS_LAYOUT, INPUT_KEYS, KEYS_MAPPING
from controller.control_config import (
    PUBLISHER_LIST, IHR, IMR, IBR, MHR, MMR, MBR, AHR, AMR, ABR, OHR, OMR, OBR,
)

# Commandes traitées localement par la GUI, jamais publiées vers le robot.
LOCAL_COMMANDS = {PLAYLIST, DURATION, "mute"}
KNOWN_TARGETS = set(PUBLISHER_LIST) | LOCAL_COMMANDS


def all_buttons():
    for mode, layout in BUTTONS_LAYOUT.items():
        for button_id, entry in layout.items():
            yield mode, button_id, entry


def test_layout_entries_are_well_formed():
    for mode, button_id, entry in all_buttons():
        where = "{}[{}]".format(mode, button_id)
        assert entry == 0 or (isinstance(entry, dict) and NAME in entry and CMD in entry), \
            "{} : entrée invalide {!r}".format(where, entry)


def test_commands_target_known_topics():
    for mode, button_id, entry in all_buttons():
        if entry == 0:
            continue
        for command_key in entry[CMD]:
            assert command_key in KNOWN_TARGETS, \
                "{}[{}] '{}' : la clé '{}' n'est ni un topic publié ni une commande locale — " \
                "elle serait perdue silencieusement par publish()".format(
                    mode, button_id, entry[NAME], command_key)


def test_keyboard_mapping_points_to_existing_buttons():
    for key, button_id in KEYS_MAPPING.items():
        for mode, layout in BUTTONS_LAYOUT.items():
            assert button_id in layout, \
                "touche '{}' -> bouton {} absent du layout {}".format(key, button_id, mode)


# --- Boutons ajoutés le 2026-09-14 (voir docs/etude-identification-acteur.md
#     et docs/etude-suivi-personne.md du dépôt dadou_robot_ros) ------------------

def test_designate_button_is_wired():
    """IHR = « c'est moi ». Il a porté pendant longtemps le libellé mort
    "Inclino" avec une commande VIDE — un bouton câblé qui ne faisait rien.
    Ce test interdit le retour en arrière."""
    for mode, layout in BUTTONS_LAYOUT.items():
        entry = layout[IHR]
        assert entry[CMD], \
            "{}[IHR] : commande VIDE — c'est la régression 'Inclino'".format(mode)
        assert entry[CMD].get(DESIGNATE) == "on", \
            "{}[IHR] devrait publier {{'{}': 'on'}}, trouvé {!r}".format(
                mode, DESIGNATE, entry[CMD])


def test_designation_can_be_released():
    """« C'est moi » ne doit pas être une porte à SENS UNIQUE : sans
    relâchement, Didier resterait verrouillé sur David et ne pourrait plus
    regarder le public autrement qu'en ligne de commande."""
    layout = BUTTONS_LAYOUT[DEFAULT]
    assert layout[MODE][CMD].get(DESIGNATE) == "off", \
        "aucun bouton ne relâche la désignation : « c'est moi » est sans retour"


def test_follow_is_two_explicit_buttons_not_a_toggle():
    """Le suivi roues met 50 kg en mouvement tout seuls : on veut savoir ce
    qu'un appui va faire SANS connaître l'état courant. Donc deux boutons
    distincts, jamais une bascule."""
    layout = BUTTONS_LAYOUT[DEFAULT]
    assert layout[START][CMD].get(FOLLOW) == "on"
    assert layout[SELECT][CMD].get(FOLLOW) == "off"


def test_follow_is_not_reachable_from_the_glove():
    """DÉCISION du 14/09, pas un oubli : le suivi aux roues reste SIM-ONLY tant
    que le test scénique au sol et le protocole caméra roues hors sol n'ont pas
    eu lieu. Il n'a donc rien à faire à portée de pouce pendant un spectacle —
    le gant ne doit pas pouvoir le déclencher.

    Si ce test casse parce que quelqu'un a déplacé « suis-moi » sur le gant :
    vérifier d'abord que les deux étapes ci-dessus sont FAITES, puis supprimer
    ce test en l'expliquant au commit. Ne pas le contourner."""
    glove_ids = [button_id for row in INPUT_KEYS for button_id in row]
    glove_ids += [IHR, IMR, IBR, MHR, MMR, MBR, AHR, AMR, ABR, OHR, OMR, OBR]
    for mode, layout in BUTTONS_LAYOUT.items():
        for button_id in glove_ids:
            entry = layout.get(button_id)
            if not isinstance(entry, dict):
                continue
            assert FOLLOW not in entry[CMD], \
                "{}[{}] '{}' déclenche le suivi roues depuis le GANT".format(
                    mode, button_id, entry[NAME])
