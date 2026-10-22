"""Tests du module personas (lot D3, atelier du 2026-07-13) — vérifie que
chaque variante embarque le contrat TECHNIQUE complet (c'est la contrepartie
du choix « textes versionnés au repo » : la CI garantit qu'aucune itération
d'écriture ne casse le pilotage du corps, cf. docstring de vision.ai.personas)."""
import pytest

from vision.ai import personas
from vision.vision_config import config


def test_persona_par_defaut_de_la_config_est_une_variante_connue():
    # La personnalité de démarrage vit dans la config (source unique des
    # défauts, cf. _chat_wiring) — ce test garantit qu'elle pointe toujours
    # vers une variante réellement écrite dans ce module.
    assert config["chat_persona"] in personas.PERSONAS


def test_persona_names_trie_et_complet():
    # Liste GRAVÉE (et triée) : "mauvaisefoi" ajoutée au lot R3 « Chantiers »
    # (2026-10-14, dadou_robot_ros/docs/etude-repetition-simulee.md §13.6) —
    # c'est aussi la liste des boutons de la page « scène » côté robot.
    assert personas.persona_names() == ["bougon", "mauvaisefoi", "naif", "vantard"]


@pytest.mark.parametrize("name", ["bougon", "naif", "vantard", "mauvaisefoi"])
def test_chaque_variante_embarque_le_contrat_technique(name):
    # Le contrat qui pilote le corps doit survivre à TOUTE itération
    # d'écriture : JSON d'émotion (visage), didascalies (gestes), interdiction
    # d'emoji (TTS). On teste des MARQUEURS du contrat, pas le texte exact —
    # les prompts techniques ont le droit d'être reformulés tant que ces
    # invariants y restent.
    prompt = personas.compose_system_prompt(name)
    assert '{"emotion"' in prompt          # contrat JSON d'émotion (ai_static)
    assert "*sourit*" in prompt            # vocabulaire didascalies (ai_static)
    assert "emoji" in prompt               # interdiction emoji = prononçabilité TTS
    assert "Didier" in prompt


@pytest.mark.parametrize("name", ["bougon", "naif", "vantard", "mauvaisefoi"])
def test_chaque_variante_embarque_socle_et_personnalite(name):
    prompt = personas.compose_system_prompt(name)
    # Socle : robot assumé + interdiction de sortir du personnage.
    assert "Tu es un robot et tu l'assumes" in prompt
    assert "Tu ne quittes JAMAIS ton personnage" in prompt
    # La personnalité du jour est bien la bonne : le texte INTÉGRAL de la
    # variante figure dans le prompt composé (pas un jeu sur la casse du
    # titre — « naif » vs « NAÏF » a déjà piégé une première version de ce
    # test, la clé ASCII ne matche pas le titre accentué).
    assert personas.PERSONAS[name] in prompt


def test_les_quatre_variantes_sont_distinctes():
    prompts = {name: personas.compose_system_prompt(name) for name in personas.PERSONAS}
    assert len(set(prompts.values())) == 4


def test_mauvaisefoi_porte_le_texte_de_la_spec():
    # Marqueurs GRAVÉS du texte du §13.6 (titre, ressort de jeu, tics, règle
    # d'écriture qui remplace l'effet audio) : une réécriture d'atelier peut
    # reformuler, mais pas perdre ces quatre piliers sans que ça se voie.
    prompt = personas.compose_system_prompt("mauvaisefoi")
    assert "Ta personnalité du jour : DIDIER DE MAUVAISE FOI." in prompt
    assert "chaque panne est une fonctionnalité" in prompt
    assert "« c'est une fonctionnalité »" in prompt
    assert "un texte qui bafouille sonne décalé sans aucun effet audio." in prompt


def test_nom_inconnu_leve_valueerror_avec_la_liste():
    with pytest.raises(ValueError) as excinfo:
        personas.compose_system_prompt("grincheux")
    # Le message doit lister les variantes disponibles : c'est lui que le
    # node logge quand la console envoie un nom inconnu (diagnostic direct).
    assert "bougon" in str(excinfo.value)


# --- Partenaire connu (répétition, 22/10) -------------------------------------

def test_sans_partenaire_le_prompt_est_inchange():
    # Le Pi ne pose pas CHAT_PARTENAIRE : son prompt doit rester EXACTEMENT
    # celui d'avant (aucun bloc de répétition qui fuirait en rue).
    assert personas.compose_system_prompt("bougon") == personas.compose_system_prompt("bougon", None)
    assert "Contexte de répétition" not in personas.compose_system_prompt("bougon", "")


def test_partenaire_connu_ajoute_en_dernier_avec_son_prenom():
    prompt = personas.compose_system_prompt("mauvaisefoi", "David")
    assert "C'est David, qui t'a construit" in prompt
    assert "ne lui demande jamais son nom" in prompt
    # EN DERNIER : il doit primer sur « essaie de connaître le nom de ton
    # interlocuteur » (ai_static) et suivre la personnalité du jour.
    assert prompt.index("Contexte de répétition") > prompt.index(personas.PERSONAS["mauvaisefoi"])
    assert prompt.endswith("ta personnalité du jour avec David.\n")
