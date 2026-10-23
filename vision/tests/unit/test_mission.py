"""Tests de vision/ai/mission.py — valeurs attendues gravées en dur."""
from vision.ai.mission import (CRITERIA, INDICATION_MAX_CHARS, NOM_MAX_CHARS,
                               SIGNALEMENT_MAX_CHARS, VALEUR_MAX_CHARS, MissionState)


def _love(par="Marie", valeur="un câlin"):
    return {"critere_valide": {"critere": "love", "valeur": valeur, "par": par}}


def test_criteres_gravés():
    assert CRITERIA == ("love", "tenderness", "friendship", "speed", "strong")


def test_résumé_initial_gravé():
    state = MissionState("le paradis")
    assert state.summary() == (
        "Mission : trouver le paradis. Restent : love, tenderness, friendship, speed, strong.")


def test_critere_valide_une_seule_fois():
    state = MissionState("le paradis")
    assert state.apply(_love()) == ["critère love validé (« un câlin », par Marie, guide n°1)"]
    # Une seconde validation (autre valeur, autre personne) ne réécrit RIEN.
    assert state.apply(_love(par="Paul", valeur="une claque")) == []
    assert state.criteres["love"] == {"valeur": "un câlin", "par": "Marie", "guide": 1}
    assert [g["nom"] for g in state.guides] == ["Marie"]


def test_critere_inconnu_ou_incomplet_ignore():
    state = MissionState("x")
    for bad in ({"critere": "courage", "valeur": "v", "par": "p"},
                {"critere": "love", "valeur": "", "par": "p"},
                {"critere": "love", "valeur": "v", "par": None},
                {"critere": "love", "valeur": 3, "par": "p"},
                "love", None):
        assert state.apply({"critere_valide": bad}) == []
    assert state.criteres["love"] is None and state.guides == []


def test_cles_inconnues_et_update_invalide_sans_exception():
    state = MissionState("x")
    assert state.apply({"n_importe_quoi": 1, "indication": None, "guide": None}) == []
    assert state.apply(None) == []
    assert state.apply("texte") == []


def test_validation_par_guide_existant_reutilise_son_numero():
    state = MissionState("x")
    state.apply({"guide": {"nom": "Marie", "signalement": "manteau rouge"}})
    state.apply({"guide": {"nom": "Paul", "signalement": ""}})
    state.apply(_love(par="paul"))  # insensible à la casse
    assert state.criteres["love"]["guide"] == 2
    assert len(state.guides) == 2


def test_guide_sans_doublon_et_nom_vide_refuse():
    state = MissionState("x")
    assert state.apply({"guide": {"nom": "Marie", "signalement": "rouge"}}) == ["guide : Marie (n°1)"]
    assert state.apply({"guide": {"nom": "MARIE", "signalement": "autre"}}) == []
    assert state.apply({"guide": {"nom": "  ", "signalement": "x"}}) == []
    assert state.apply({"guide": {"signalement": "x"}}) == []
    assert state.guides == [{"nom": "Marie", "signalement": "rouge", "guide": 1}]


def test_indication_remplace_la_precedente():
    state = MissionState("x")
    assert state.apply({"indication": "tout droit"}) == ["indication : tout droit"]
    state.apply({"indication": "à gauche"})
    assert state.indication == "à gauche"
    state.apply({"indication": ""})
    assert state.indication == "à gauche"


def test_résumé_gravé_avec_toutes_les_sections():
    state = MissionState("le paradis")
    state.apply(_love())
    state.apply({"indication": "tout droit après le pont"})
    assert state.summary() == (
        "Mission : trouver le paradis. Critères validés : love (« un câlin », par Marie, "
        "guide n°1). Restent : tenderness, friendship, speed, strong. "
        "Dernière indication : tout droit après le pont. Guides : Marie.")


def test_complete_et_conclusion():
    state = MissionState("le paradis")
    assert not state.complete()
    for name in CRITERIA:
        state.apply({"critere_valide": {"critere": name, "valeur": "v" + name, "par": "Marie"}})
    assert state.complete()
    assert state.summary() == (
        "Mission : trouver le paradis. Critères validés : "
        "love (« vlove », par Marie, guide n°1); "
        "tenderness (« vtenderness », par Marie, guide n°1); "
        "friendship (« vfriendship », par Marie, guide n°1); "
        "speed (« vspeed », par Marie, guide n°1); "
        "strong (« vstrong », par Marie, guide n°1). Guides : Marie. "
        "Les cinq critères sont réunis : le paradis, c'est ici, maintenant, avec ces gens-là.")


def test_conclusion_porte_la_destination_de_l_instance():
    # Revue adversariale du 23/10 (M4) : « le paradis » était écrit en dur —
    # une quête du Titan concluait sur le paradis.
    state = MissionState("le Titan")
    for name in CRITERIA:
        state.apply({"critere_valide": {"critere": name, "valeur": "v", "par": "Marie"}})
    assert state.summary().endswith(
        "Les cinq critères sont réunis : le Titan, c'est ici, maintenant, avec ces gens-là.")
    assert "paradis" not in state.summary()


def test_aller_retour_dict():
    state = MissionState("le Titan")
    state.apply(_love())
    state.apply({"guide": {"nom": "Paul", "signalement": "casquette"}})
    state.apply({"indication": "au pont"})
    copie = MissionState.from_dict(state.to_dict())
    assert copie.to_dict() == state.to_dict()
    assert copie.summary() == state.summary()
    # Le compteur de guide survit : le prochain guide est le n°3.
    copie.apply({"guide": {"nom": "Zoé", "signalement": ""}})
    assert copie.guides[-1]["guide"] == 3


def test_to_dict_forme_gravée():
    state = MissionState("le Titan")
    state.apply(_love())
    assert state.to_dict() == {
        "destination": "le Titan",
        "criteres": {"love": {"valeur": "un câlin", "par": "Marie", "guide": 1},
                     "tenderness": None, "friendship": None, "speed": None, "strong": None},
        "guides": [{"nom": "Marie", "signalement": "", "guide": 1}],
        "indication": None,
        "next_guide": 2,
    }


def test_indication_terminee_par_un_point_sans_doublon():
    m = MissionState("le paradis")
    m.apply({"indication": "Près de la boulangerie."})
    assert m.summary() == ("Mission : trouver le paradis. Restent : love, tenderness, "
                           "friendship, speed, strong. Dernière indication : Près de la boulangerie.")


def test_plafonds_gravés():
    assert (VALEUR_MAX_CHARS, INDICATION_MAX_CHARS, NOM_MAX_CHARS,
            SIGNALEMENT_MAX_CHARS) == (60, 160, 40, 80)


def test_champs_longs_tronques():
    # Revue adversariale du 23/10 (I6) : un passant qui dicte un long texte le
    # faisait recopier tel quel dans la mission relue à chaque réplique.
    state = MissionState("x")
    changes = state.apply({
        "critere_valide": {"critere": "love", "valeur": "v" * 100, "par": "P" * 100},
        "indication": "i" * 300,
        "guide": {"nom": "N" * 100, "signalement": "s" * 200},
    })
    assert state.criteres["love"] == {"valeur": "v" * 60, "par": "P" * 40, "guide": 1}
    assert state.indication == "i" * 160
    assert state.guides == [{"nom": "P" * 40, "signalement": "", "guide": 1},
                            {"nom": "N" * 40, "signalement": "s" * 80, "guide": 2}]
    assert len(changes) == 3
    # Rognage APRÈS troncature : jamais d'espace final laissé par la coupe.
    state.apply({"indication": "a" * 159 + "   bbb"})
    assert state.indication == "a" * 159
