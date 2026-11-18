"""Tests du module personas (lot D3, atelier du 2026-07-13) — vérifie que
chaque variante embarque le contrat TECHNIQUE complet (c'est la contrepartie
du choix « textes versionnés au repo » : la CI garantit qu'aucune itération
d'écriture ne casse le pilotage du corps, cf. docstring de didier_vision.ai.personas)."""
import re

import pytest

from didier_vision.ai import personas
from didier_vision.vision_config import config


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
    # Marqueurs GRAVÉS du texte du §13.6 (titre, ressort de jeu, règle
    # d'écriture qui remplace l'effet audio) : une réécriture d'atelier peut
    # reformuler, mais pas perdre ces trois piliers sans que ça se voie.
    prompt = personas.compose_system_prompt("mauvaisefoi")
    assert "Ta personnalité du jour : DIDIER DE MAUVAISE FOI." in prompt
    assert "chaque panne est une fonctionnalité" in prompt
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


# --- Mouvement à la voix (lot I1, 22/10) ----------------------------------------

def test_sans_mouvement_le_prompt_est_inchange():
    # Le Pi ne pose pas CHAT_MOUVEMENT : son prompt doit rester EXACTEMENT
    # celui d'avant, partenaire ou non.
    assert personas.compose_system_prompt("bougon") == personas.compose_system_prompt("bougon", move=False)
    assert (personas.compose_system_prompt("naif", "David")
            == personas.compose_system_prompt("naif", "David", move=False))
    assert "Mouvement (répétition)" not in personas.compose_system_prompt("bougon", "David")


def test_mouvement_ajoute_en_dernier_apres_le_partenaire():
    prompt = personas.compose_system_prompt("mauvaisefoi", "David", move=True)
    # Texte GRAVÉ (spec I1) : la clé et ses deux seules valeurs.
    assert ('ajoutant au JSON de fin "marche": "go" ou "marche": "stop" '
            '(ex. {"emotion": "happy", "marche": "go"}).') in prompt
    assert prompt.index("Mouvement (répétition)") > prompt.index("Contexte de répétition")
    assert prompt.endswith("N'évoque jamais ce JSON à voix haute.\n")


def test_mouvement_sans_partenaire_suit_la_personnalite():
    prompt = personas.compose_system_prompt("bougon", move=True)
    assert "Contexte de répétition" not in prompt
    assert prompt.endswith(personas.PERSONAS["bougon"] + personas.MOVE_TEMPLATE)


# --- Demande de réflexion (lot P4 du metteur en scène, 23/10) -------------------
# Revue adversariale du 23/10 (I5) : REFLECT_TEMPLATE ne vit plus dans le
# system prompt (Didier promettait une réponse même réflexion morte) — il est
# accroché au tableau de situation frais par StreamingBrain(situation_suffix),
# cf. test_llm_stream.py.

def test_le_prompt_systeme_ne_promet_jamais_de_reflexion():
    for name in personas.persona_names():
        for partner in (None, "David"):
            for move in (False, True):
                prompt = personas.compose_system_prompt(name, partner, move=move)
                assert "Réflexion :" not in prompt
                assert "reflechir" not in prompt
    with pytest.raises(TypeError):
        personas.compose_system_prompt("bougon", reflect=True)


def test_texte_de_reflexion_grave():
    template = personas.REFLECT_TEMPLATE
    # Texte GRAVÉ (spec P4) : la clé et sa forme.
    assert ('ajoute au JSON de fin "reflechir": "<la demande en une phrase>". '
            "Tu reprendras la parole de toi-même quand tu auras la réponse.") in template
    assert template.startswith("\nRéflexion : un metteur en scène intérieur t'aide à "
                               "faire avancer l'histoire.")
    assert template.endswith("Sinon, n'ajoute PAS la clé \"reflechir\". "
                             "N'évoque jamais ce JSON à voix haute.\n")


# --- « Aller voir » (lot M1, 31/10, dadou_robot_ros/docs/spec-aller-voir.md) ---

def test_mouvement_apprend_la_cle_aller_voir():
    template = personas.MOVE_TEMPLATE
    # Textes GRAVÉS (spec §2.2) : la clé, sa valeur, ce que fait le corps,
    # et l'objet absent joué en personnage.
    assert '"aller_voir": "<nom exact d\'un objet que tu vois ou qui est autour de toi>"' in template
    assert "il y va, se tourne face à lui et s'arrête" in template
    # Lot O1 : un objet pas ici est DIT (et où il est), jamais visé.
    assert ("Un objet qui n'est pas autour de toi (plus loin, ou que tu ne connais pas) : tu ne le trouves "
            "pas ici, dis-le en personnage (et où il est, si tu le sais), sans la clé.") in template
    assert "de la liste" not in template
    # Les limites restantes du corps sont toujours dites (réduites au lot M2,
    # spec §7.2 : tourner, demi-tour et avancer sont des gestes du corps)…
    assert "Tu ne sais pas reculer, et tu ne contournes rien en un seul geste." in template
    # …mais plus l'interdit d'aller ailleurs, que la clé contredirait.
    assert "ni aller ailleurs" not in template
    assert template.endswith("N'évoque jamais ce JSON à voix haute.\n")


# --- « Ce qui t'entoure » (lot O1, 18/11) : la section écrite depuis le tableau des objets ---
from theatre_contrats.objets import Objet, Tableau  # noqa: E402

# La séance du 15/11, Didier à x = 14 cap +x : tableau écrit par didier_perception (valeurs
# gravées dans packages/didier_perception/test/test_tableau.py).
TABLE = Objet(id="carte/table_basse", nom="table_basse", desc="table très basse", x=17.8, y=2.1, distance_m=4.3,
              azimut_deg=28.9, cote="devant", en_vue=True, tour=True, atteignable=True)
POSTER = Objet(id="carte/poster_bizarre", nom="poster_bizarre", desc="poster_bizarre", x=22.4, y=-2.7,
               distance_m=8.8, azimut_deg=-17.8, cote="devant", en_vue=True, tour=True, atteignable=True)
POUBELLE = Objet(id="carte/poubelle_tri", nom="poubelle_tri", x=27.0, y=2.4, distance_m=13.2, azimut_deg=10.5,
                 cote="devant", en_vue=True, tour=True, atteignable=False)
CARROUSEL = Objet(id="carte/carrousel", nom="carrousel", desc="manège", x=13.2, y=-2.0, distance_m=2.2,
                  azimut_deg=-111.8, cote="droite", atteignable=True)
ELEPHANT = Objet(id="carte/elephant", nom="elephant", x=8.6, y=-1.4, distance_m=5.6, azimut_deg=-165.5,
                 cote="derriere", atteignable=True)
NEFS = Objet(id="carte/nefs", nom="nefs", x=4.0, y=2.0, distance_m=10.2, azimut_deg=168.7, cote="derriere")
BANC = Objet(id="carte/banc", nom="banc", desc="banc en bois", x=36.2, y=2.5, distance_m=22.3, azimut_deg=6.4,
             cote="devant", tour=True)
X14 = Tableau((CARROUSEL, TABLE, ELEPHANT, POSTER, NEFS, POUBELLE, BANC))


def test_entourage_seance_15_11_texte_grave():
    assert personas.entourage_prompt(X14) == (
        "Ce que tu vois devant toi : table_basse (table très basse) à 4 m, un peu à gauche; "
        "poster_bizarre à 9 m, un peu à droite; poubelle_tri à 13 m, un peu à gauche, trop loin pour y aller. "
        "Autour de toi, hors de ta vue : carrousel (manège) à 2 m sur ta droite; elephant à 6 m derrière toi. "
        "Tu peux faire le tour de : table_basse, poster_bizarre. "
        "Tu ne peux PAS faire le tour de : carrousel, elephant (eau, mur ou obstacle tout près) : si on te le "
        "demande, dis en personnage que c'est impossible, n'annonce jamais ce tour et n'ajoute pas la clé. "
        "Plus loin, tu ne les vois pas d'ici : nefs (à 10 m derrière toi); banc (à 22 m devant toi).")
    # Le banc n'est JAMAIS dit « là » : seulement dans le résumé lointain.
    assert "banc (banc en bois)" not in personas.entourage_prompt(X14)


def test_entourage_droit_devant_et_moins_d_un_metre():
    o = Objet(id="a", nom="plot", distance_m=0.6, azimut_deg=-4.9, cote="devant", en_vue=True, atteignable=True)
    assert personas.entourage_prompt(Tableau((o,))) == (
        "Ce que tu vois devant toi : plot à moins d'un mètre, droit devant. "
        "Tu ne peux PAS faire le tour de : plot" + personas.TOURS_REFUS)


def test_entourage_vide_ou_rien_autour():
    assert personas.entourage_prompt(Tableau()) == "" and personas.entourage_prompt(None) == ""
    assert personas.entourage_prompt(Tableau((BANC,))) == (
        "Aucun objet autour de toi en ce moment. Plus loin, tu ne les vois pas d'ici : banc (à 22 m devant toi).")


def test_entourage_plafonne_sans_couper_un_nom():
    # 40 objets en vue aux noms longs : plafond tenu, chaque nom cité ENTIER.
    vus = tuple(Objet(id=f"v{i}", nom=f"objet_au_nom_tres_long_numero_{i:02d}", desc="x" * 50,
                      distance_m=1.0 + i / 10, azimut_deg=0.0, cote="devant", en_vue=True, atteignable=True,
                      tour=True) for i in range(40))
    loin = tuple(Objet(id=f"l{i}", nom=f"lointain_{i:02d}", distance_m=30.0 + i, azimut_deg=0.0, cote="devant")
                 for i in range(20))
    texte = personas.entourage_prompt(Tableau(vus + loin))
    assert len(texte) <= personas.ENTOURAGE_MAX_CHARS == 900
    cites = re.findall(r"objet_au_nom_tres_long_numero_\d*", texte) + re.findall(r"lointain_\d*", texte)
    assert len(cites) >= 4 and all(re.fullmatch(r"\D+_\d\d", c) for c in cites)
    assert texte.endswith(".")
    assert (personas.ENTOURAGE_VUE_MAX, personas.ENTOURAGE_AUTOUR_MAX, personas.ENTOURAGE_LOIN_MAX) == (6, 4, 6)


# --- Gestes chiffrés (lot M2, 31/10, spec-aller-voir.md §7) ---

def test_mouvement_apprend_les_gestes_chiffres():
    template = personas.MOVE_TEMPLATE
    # Clés, unités et bornes GRAVÉES (contrat avec conversation.py et le
    # régisseur : TURN_MAX_DEG = 180, FORWARD_MAX_M = 5, + = gauche).
    assert '"tourner": <degrés, entre -180 et 180>' in template
    assert '"avancer": <mètres, plus que 0 et au plus 5>' in template
    assert '"regarder": <degrés>' in template
    assert "positifs vers ta GAUCHE, négatifs vers ta droite" in template
    # La caméra est au buste : la tête ne fait pas voir, le pivot si.
    assert "tourner la tête ne te montre pas ce qu'il y a de côté" in template
    assert "pour VOIR de côté ou derrière toi, il faut pivoter" in template


def test_mouvement_exemples_de_gestes_generaux():
    template = personas.MOVE_TEMPLATE
    # Les trois exemples de la décision de David, gravés.
    assert '« jette un œil sur ta droite » -> "tourner": -90' in template
    assert "tu en parleras à ta réplique suivante" in template
    # Exemple d'« avancer » corrigé le 01/11 (séance : il avançait mètre par
    # mètre) : « avance » seul = 3 m.
    assert '« avance » -> {"emotion": "happy", "avancer": 3}' in template
    assert "« avance un peu » -> 1" in template
    # Lot M4 (spec §9.4) : l'ancien « un geste à la fois, réplique après
    # réplique » est remplacé par l'enchaînement de la tâche.
    assert "(« va aux anneaux puis reviens »), fais le premier geste" in template
    # Des outils au choix, pas des cas figés.
    assert "des OUTILS que tu choisis librement" in template


def test_mouvement_ne_dit_plus_qu_il_ne_sait_pas_tourner():
    template = personas.MOVE_TEMPLATE
    assert "ni tourner" not in template
    assert "ni faire demi-tour" not in template
    assert "Tu ne sais pas reculer" in template


def test_mouvement_liste_toutes_les_cles_a_ne_pas_ajouter():
    assert personas.MOVE_TEMPLATE.endswith(
        '- Sinon, n\'ajoute PAS les clés "marche", "aller_voir", "faire_le_tour", "tourner", "avancer" '
        'ni "regarder". N\'évoque jamais ce JSON à voix haute.\n')


# --- « Faire le tour » (lot M3, 01/11, spec-aller-voir.md §8.2) ---

def test_mouvement_apprend_la_cle_faire_le_tour():
    template = personas.MOVE_TEMPLATE
    # 15/11 : seulement les objets de la liste des tours possibles.
    assert ('- "faire_le_tour": "<nom exact d\'un objet dont tu peux faire le tour>" '
            '(+ "sens": "gauche" ou "droite" si on te le précise) : faire le tour complet de cet '
            'objet puis t\'arrêter face à lui') in template
    assert ("Un objet dont on ne te dit pas que tu peux faire le tour : tu ne peux pas (eau, mur ou "
            "obstacle tout près), dis-le en personnage, sans la clé.") in template
    assert ("- Quand on te dit qu'un geste n'a PAS eu lieu, tu n'as pas bougé : dis-le en personnage, "
            "ne prétends jamais l'avoir fait.") in template
    assert ('« fais le tour des poubelles » -> {"emotion": "happy", '
            '"faire_le_tour": "poubelle_tri"}') in template
    # L'ancien exemple « impossible » est retiré : le geste existe.
    assert "fais le tour de la flaque" not in template
    assert template.endswith("N'évoque jamais ce JSON à voix haute.\n")


# --- Tâche en cours (lot M4, 01/11, spec-aller-voir.md §9.4) ---

def test_mouvement_tache_enchainee_jusqu_au_bout():
    template = personas.MOVE_TEMPLATE
    # Textes GRAVÉS : un geste de corps par réplique, la main redonnée à la
    # fin de chaque geste, et la tâche menée jusqu'au bout.
    assert "un seul geste de corps par réplique" in template
    assert ("à la fin de chaque geste on te redonne la main et tu enchaînes le suivant "
            "toi-même, jusqu'à dire que c'est fini.") in template
    assert ("Ce que tu annonces, tu le fais jusqu'au bout ; ne t'arrête que si on te "
            "le demande.") in template
    assert "réplique après réplique" not in template
    assert "un geste à la fois" not in template
    assert template.endswith("N'évoque jamais ce JSON à voix haute.\n")


def test_mouvement_gestes_a_la_mesure_de_la_demande():
    # Constat de séance (01/11) : « fais le tour complet » -> avancer 2 m,
    # « avance » -> 1 m. Consignes GRAVÉES.
    template = personas.MOVE_TEMPLATE
    assert ('Choisis des gestes À LA MESURE de la demande : pour aller vers un objet '
            'ou en faire le tour, utilise "aller_voir" ou "faire_le_tour" (un seul '
            'geste qui va jusqu\'au bout), jamais une suite de petits pas.') in template
    assert ('« avance » -> {"emotion": "happy", "avancer": 3} ; « avance un peu » -> 1 ; '
            '« avance encore » ou « continue » -> 3 à 5') in template


def test_aucune_expression_toute_faite():
    # 15/11, David : plus aucune formule fétiche. Les listes de tics sont
    # retirées de TOUTES les personnalités, et la règle l'interdit.
    for name in personas.PERSONAS:
        prompt = personas.compose_system_prompt(name)
        assert "fétiche" not in prompt.replace("pas de formule fétiche", "")
        assert "bon sang de boulon" not in prompt
        assert "Aucune expression toute faite" in prompt
