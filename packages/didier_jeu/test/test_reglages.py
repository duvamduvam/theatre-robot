"""config/reglages.yaml GRAVÉ en entier : changer un chiffre du modèle de
timing exige de toucher CE test (spec A1 §3, §8.7 ; étude §4.2)."""
import pytest

from conftest import donnees_reglages

ATTENDU = {
    "tick_s": 0.1,
    "hysteresis": {"marge": 0.15, "duree_s": 0.3},
    "changement": {"min_s": 2.0},
    "reaction": {"maintien_apres_s": 0.6},
    "engagement": {"seuil_rupture": 0.9},
    "offres": {"ttl_s": 3.0, "valeur": {"personne": 0.7, "objet": 0.8, "bouche": 0.9}},
    "pistes": {"perte_s": 0.6, "nouvelle_apres_s": 2.0, "confiance_min": 0.5},
    "pulsions": {
        "ennui": {"montee_par_s": 0.1, "plafond": 1.0},
        "curiosite": {"saut": 1.0, "retombee_par_s": 0.2},
        "lubie": {"par_poi": 0.5, "retombee_par_s": 0.05, "plafond": 1.0},
        "fatigue": {"par_deplacement": 0.3, "retombee_par_s": 0.05, "seuil_interdit": 0.8},
    },
    "refractaire_s": {"initiative_spontanee": 8.0, "arret_didier": 120.0, "expression": 8.0,
                      "regarder": 4.0, "deplacement": 10.0},
    "lubie": {"delai_refus_s": 3.0},
    "reprise": {"delai_s": 90.0},
    "superviseur": {"mode": "suppose", "silence_max_s": 1.0},
    "console": {"ignore_s": 30.0, "ordre_ttl_s": 10.0, "joue_avec_s": 30.0,
                "plus_lent_s": 60.0, "plus_lent_facteur": 2.0},
    "poids": {"offre": 1.0, "pulsion": 0.6, "metteur_en_scene": 0.8, "console": 1.5},
    "immobilite": {"base": 0.3, "pente_ennui": 0.3},
    "gains": {"regarder": 1.0, "accueil": 0.8, "spontanee": 1.0, "approcher": 0.7, "lubie": 1.0,
              "bouche": 1.0, "aller_voir": 1.0, "repartir": 2.0},
    "emplois": {"bonjour": "accueil", "random": "spontanee", "little move": "spontanee"},
    "durees_s": {"regarder": 3.0, "expression_defaut": 5.0, "expression_marge": 2.0,
                 "deplacement_max": 70.0, "deplacement_accuse": 3.0, "arret": 3.0, "relais": 2.0},
    "regard": {"demi_champ_deg": 30.0},
    "metteur_en_scene": {"ttl_s": 5.0, "mots_cles": {"approche": "approcher", "regarde": "regarder",
                                                     "salue": "accueil", "bonjour": "accueil",
                                                     "danse": "spontanee", "bouge": "spontanee"}},
}


def test_reglages_graves():
    assert donnees_reglages() == ATTENDU


def test_reglage_manquant_refuse():
    from didier_jeu.reglages import Reglages, ReglagesError
    data = donnees_reglages()
    del data["hysteresis"]["marge"]
    with pytest.raises(ReglagesError, match="hysteresis.marge"):
        Reglages(data)


def test_mode_superviseur_inconnu_refuse():
    from didier_jeu.reglages import Reglages, ReglagesError
    data = donnees_reglages()
    data["superviseur"]["mode"] = "absent"
    with pytest.raises(ReglagesError):
        Reglages(data)


def test_chaque_action_a_un_gain():
    from didier_jeu.scores import CATEGORIES
    assert set(CATEGORIES) <= set(ATTENDU["gains"])
