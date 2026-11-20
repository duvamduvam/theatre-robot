"""didier_vision.ai.raccord — contrôles déterministes du texte (lot « texte raccord », 18/11).

Phrases GRAVÉES : celles de la séance du 18/11 21:35 (la lettre sur le banc) et des variantes
voisines ; chaque motif a au moins un exemple qui le prend, et les négations qui ne doivent PAS s'y
prendre. Un motif retiré ou affaibli fait rougir sa ligne (paramétrage = un cas par phrase).
"""
import pytest

from didier_vision.ai import raccord


def test_constantes_gravees():
    assert raccord.CONTROLE_ESSAIS_MAX == 2
    assert raccord.REPLI_REFUS == "Non, je n'ai pas pu : je n'ai pas bougé d'ici."
    assert raccord.CORRECTION.format(extrait="je vois") == (
        "ATTENTION : ta réplique précédente disait « je vois » : c'est FAUX, elle n'a pas été dite. Le "
        "geste n'a pas eu lieu : tu n'as rien vu, rien trouvé, rien fait de plus, tu n'as pas bougé. "
        "Refais ta réplique sans prétendre avoir vu, trouvé, lu ni fait quoi que ce soit, et sans "
        "annoncer que tu y vas.")
    # Le repli lui-même ne prétend rien (sinon le contrôle se contredirait).
    assert raccord.pretention(raccord.REPLI_REFUS) is None


def test_aplatir():
    assert raccord.aplatir("  Je l’aperçois,   LÀ-BAS ! ") == "je l'apercois, la-bas !"
    assert raccord.aplatir(None) == ""


@pytest.mark.parametrize("phrase, extrait", [
    # LA réplique de la séance du 18/11 21:35.
    ("Je vois bien une enveloppe posée dessus.", "je vois"),
    ("Ah, je la vois, ta lettre !", "je la vois"),
    ("Je l’aperçois d'ici.", "je l'apercois"),
    ("J'ai vu une enveloppe rouge.", "j'ai vu"),
    ("J'ai trouvé ta lettre, David.", "j'ai trouve"),
    ("Je l'ai lue : c'est une facture.", "je l'ai lue"),
    ("Il y a bien une lettre, oui.", "y a bien"),
    # Banc réel du 19/11 (Haiku 5.5, continuation d'échec) : deux formes qui passaient.
    ("Ah, ouais, y a bien un truc blanc.", "y a bien"),
    ("Il y a même un mot qui dépasse, ou alors c'est une feuille mouillée.", "y a meme"),
    ("Bon, je vais aller jeter un œil à ce banc.", "je vais aller"),
    ("Elle est bien là, ta lettre.", "elle est bien la"),
    ("J'y suis !", "j'y suis"),
    ("Me voilà devant le banc.", "me voila"),
    ("Nous y voilà.", "nous y voila"),
    ("Je suis arrivé au banc.", "je suis arrive"),
    ("J'ai fait le tour de l'éléphant.", "j'ai fait"),
    ("C'est fait, chef.", "c'est fait"),
    ("Je cherche la lettre.", "je cherche"),
    ("Je lis l'enveloppe : « pour Didier ».", "je lis"),
    ("J'ouvre l'enveloppe.", "j'ouvre"),
    ("Je m'approche du banc.", "je m'approche"),
    ("J'y vais tout de suite.", "j'y vais"),
    ("Je vais voir ça de plus près.", "je vais voir"),
    ("Allons-y !", "allons-y"),
])
def test_pretention_reconnue(phrase, extrait):
    assert raccord.pretention(phrase) == extrait


@pytest.mark.parametrize("phrase", [
    "Une lettre ? D'ici je ne vois pas le banc, il est bien trop loin.",
    "Je n'ai pas vu de lettre, je n'ai pas bougé d'ici.",
    "Le banc est à vingt mètres : je ne peux pas y aller d'un seul geste.",
    "Raté ! Mes roues refusent d'aller si loin.",
    "Il n'y a même pas de banc ici.",
    "Y a même pas une lettre, tu me fais marcher.",
    "Non, je n'ai pas pu : je n'ai pas bougé d'ici.",
    "",
])
def test_pas_de_pretention(phrase):
    assert raccord.pretention(phrase) is None


def test_premier_extrait_du_texte_gagne():
    assert raccord.pretention("Allons-y ! Je vois la lettre.") == "allons-y"


@pytest.mark.parametrize("direction, geste", [
    # Les directions de la séance du 18/11 21:35.
    ("Didier cherche la lettre sur le banc.", "cherche"),
    ("Didier lit l'enveloppe à voix haute.", "lit"),
    ("Qu'il aille voir le banc.", "aille voir"),
    ("Va voir le banc et raconte.", "va voir"),
    ("Didier va vers la flaque.", "va vers"),
    ("Il ouvre l'enveloppe avec emphase.", "ouvre"),
    ("Didier prend la lettre et la montre.", "prend la lettre"),
    ("Il ramasse le papier.", "ramasse"),
    ("Il fouille sous le banc.", "fouille"),
    ("Qu'il fasse le tour de la grue.", "fasse le tour"),
    ("Didier fait le tour du banc.", "fait le tour"),
    ("Didier rejoint David près des anneaux.", "rejoint"),
    ("Il avance vers le pigeon.", "avance vers"),
])
def test_geste_impossible(direction, geste):
    assert raccord.geste_impossible(direction) == geste


@pytest.mark.parametrize("direction", [
    "Didier s'émerveille de la lettre imaginaire et demande à David ce qu'elle dit.",
    "Il regarde le banc de loin et s'étonne.",
    "Il salue la passante et lui demande si ça va.",
    "Didier danse sur place, ravi.",
    "Il s'approche du passant pour lui parler.",    # « approche » : mot-clé du sélecteur, permis
    "Didier demande comment va le pigeon.",
    "Il rêve de dormir dans un lit de boulons.",
    "Il fait avancer l'histoire en posant une question.",
])
def test_direction_jouable(direction):
    assert raccord.geste_impossible(direction) is None
