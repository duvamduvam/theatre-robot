"""Lot L3a (28/11) — tuile « Appareils » de la page scène : jugement pur (didier_web.panneau_appareils).

Spec docs/spec-L3-gabarit-sono.md décisions 18-19. Valeurs GRAVÉES (jamais recalculées avec la
fonction testée) : la ligne rendue est le contrat de la tuile ; fraîcheur à 4,9 / 5,1 s.
"""

import pytest

from didier_web import panneau_appareils as pap

ETAT_SIM = {"v": 1, "appareil": "sono", "pilote": "sim", "sha": "dev", "t_ms": 1764300000000,
            "organes": [{"nom": "audio", "type": "audio", "valeur": "bugs-joues/begaiement.wav",
                         "debut_ms": 1764299999500, "duree_ms": 2160, "sante": "ok"},
                        {"nom": "cut_voice", "type": "relais", "valeur": True, "sante": "ok"}],
            "refus": None}

ETAT_MATERIEL = {"v": 1, "appareil": "sono", "pilote": "materiel", "sha": "0123456789abcdef-dirty",
                 "t_ms": 5,
                 "organes": [{"nom": "audio", "type": "audio", "valeur": "", "debut_ms": None,
                              "duree_ms": None, "sante": "erreur"},
                             {"nom": "cut_voice", "type": "relais", "valeur": False, "sante": "absent"}],
                 "refus": {"code": "audio_absent", "detail": "a/b.mp3", "t_ms": 4}}

LIGNE_SIM = {
    "appareil": "sono", "presence": "vue", "presence_texte": "", "pilote": "sim",
    "pilote_texte": "simulé", "version": {"sha": "dev", "differente": False, "texte": ""},
    "organes": [
        {"nom": "audio", "type": "audio", "actif": True, "texte": "bugs-joues/begaiement.wav",
         "valeur": "bugs-joues/begaiement.wav", "debut_ms": 1764299999500, "duree_ms": 2160,
         "barre": False, "sante_texte": "", "topic_ordre": "sono/audio"},
        {"nom": "cut_voice", "type": "relais", "actif": True, "texte": "cut_voice", "valeur": True,
         "debut_ms": None, "duree_ms": None, "barre": False, "sante_texte": "",
         "topic_ordre": "sono/relais"}],
    "refus_texte": None,
}


def test_ligne_sim_gravee():
    assert pap.lignes({"sono/etat": {"msg": ETAT_SIM, "age_s": 0.3}}) == [LIGNE_SIM]


def test_ligne_materiel_sante_refus_version():
    (l,) = pap.lignes({"sono/etat": {"msg": ETAT_MATERIEL, "age_s": 1.0},
                       "deploy_sha": {"msg": "fedcba9876543210", "age_s": 9.0}})
    assert l["pilote_texte"] == "matériel"
    assert l["version"] == {"sha": "0123456-dirty", "differente": True,
                            "texte": "version différente du robot"}
    assert [(o["texte"], o["actif"], o["barre"], o["sante_texte"]) for o in l["organes"]] == [
        ("silence", False, True, "erreur"), ("cut_voice", False, True, "absent")]
    assert l["refus_texte"] == "refusé : audio_absent — a/b.mp3"


@pytest.mark.parametrize("age, presence, texte", [
    (4.9, "vue", ""), (5.1, "muette", "muette"), (None, "muette", "muette")])
def test_fraicheur_a_cinq_secondes(age, presence, texte):
    (l,) = pap.lignes({"sono/etat": {"msg": ETAT_SIM, "age_s": age}})
    assert (l["presence"], l["presence_texte"]) == (presence, texte)


def test_jamais_vue_et_illisible():
    vide = {"appareil": "sono", "pilote": None, "pilote_texte": "", "version": None,
            "organes": [], "refus_texte": None}
    assert pap.lignes({}) == [dict(vide, presence="jamais_vue", presence_texte="jamais vue")]
    assert pap.lignes({"sono/etat": {"msg": "pas une enveloppe", "age_s": 0.1}}) == [
        dict(vide, presence="illisible", presence_texte="état illisible")]


@pytest.mark.parametrize("sha, robot, differente", [
    ("abc1234", "abc1234", False),     # même version
    ("abc1234", "def5678", True),      # différente
    ("dev", "def5678", False),         # appareil en sim : jamais « différente »
    ("abc1234", "dev", False),         # robot en sim
    ("abc1234", None, False),          # robot jamais vu
])
def test_version_differente_du_robot(sha, robot, differente):
    topics = {"sono/etat": {"msg": dict(ETAT_SIM, sha=sha), "age_s": 0.0}}
    if robot is not None:
        topics["deploy_sha"] = {"msg": robot, "age_s": 0.0}
    assert pap.lignes(topics)[0]["version"]["differente"] is differente


def test_sha_court():
    assert pap.sha_court("7caeecbc1234") == "7caeecb"
    assert pap.sha_court("7caeecbc1234-dirty") == "7caeecb-dirty"
    assert pap.sha_court("dev") == "dev"
