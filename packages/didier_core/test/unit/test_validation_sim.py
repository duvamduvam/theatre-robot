"""Porte sim (lot L1d-2) : l'observateur didier_web.validation_sim, sans ROS, sur un dossier
jetable, horloge injectée (ms). Un tampon posé / refusé pour CHAQUE critère de la décision 7 bis,
bornes à leur valeur limite (0,95 × duration ; duration + 5 s ; 1 s après la fin pour les
roues ; min(duration, 10 s) pour une expression ou une lumière), codes GRAVÉS.
"""
import json
import os

import pytest

from didier_core.robot_config import config
from dadou_utils_ros.utils_static import LOGGING_FILE_NAME
from didier_web import validation_sim
from didier_web.validation_sim import Journal, Observateur
from theatre_contrats import donnees

SIM = {"ROS_DOMAIN_ID": "43"}
NOEUDS = ["animation_node", "face_sim_node", "leds_sim_node", "twist_deadman", "validation_sim_node"]
SANS_ROUES = {"keys": "S1", "duration": 4000, "neck": [[0, 0.5]]}
AVEC_ROUES = {"keys": "R1", "duration": 4000, "wheels": [[0.1, [0.2, 0.2]], [0.5, [0, 0]]]}
EXPRESSIONS = {"joie": {"duration": 2000, "loop": True, "mouths": [], "left_eyes": [], "right_eyes": []},
               "longue": {"duration": 60000, "loop": True, "mouths": [], "left_eyes": [], "right_eyes": []}}
LUMIERES = {"calme": {"duration": 1000, "loop": False, "sequences": {"bleu": 1}}}
LIGNE_INFO = "2026-11-12 20:35:29,559 face_sim_node Face update |100: INFO\x1b[32m ok\x1b[0m\n"
LIGNE_ERREUR = "2026-11-12 20:35:30,000 animation_node AnimationsNode cb |108: ERROR\x1b[31m boum\x1b[0m\n"
LIGNE_ERREUR_VISAGE = "2026-11-12 20:35:30,000 face_sim_node Face update |99: ERROR\x1b[31m boum\x1b[0m\n"


def ecrire(racine, relatif, valeur):
    chemin = os.path.join(str(racine), relatif)
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(valeur, f, indent=4)


@pytest.fixture
def banc(tmp_path):
    for relatif, valeur in (("json/sequences/essai/calme.json", SANS_ROUES),
                            ("json/sequences/essai/roule.json", AVEC_ROUES),
                            ("json/sequences/essai/double.json", SANS_ROUES),
                            ("json/sequences/autre/double.json", AVEC_ROUES),
                            ("json/expressions.json", EXPRESSIONS), ("json/robot_lights.json", LUMIERES),
                            ("json/lights_base.json", {"bleu": {"method": "chase", "color": "BLUE"}})):
        ecrire(tmp_path, relatif, valeur)
    journal = tmp_path / "robot.log"
    journal.write_text(LIGNE_INFO, encoding="utf-8")
    noeuds = list(NOEUDS)
    obs = Observateur(tmp_path, Journal(str(journal)), lambda: noeuds, SIM)
    return obs, tmp_path, journal, noeuds


def registre(racine):
    return donnees.lire_registre(racine)


def jouer(obs, nom, debut, fin):
    assert obs.etat_animation(debut, nom) == []
    return obs.etat_animation(fin, "")


def codes(verdicts):
    return [(v["kind"], v["name"], v["code"], v["ok"]) for v in verdicts]


# ================================================================ garde du domaine
@pytest.mark.parametrize("environ, attendu", [
    ({"ROS_DOMAIN_ID": "43"}, True), ({"ROS_DOMAIN_ID": "42"}, False), ({"ROS_DOMAIN_ID": ""}, False),
    ({"ROS_DOMAIN_ID": "quarante"}, False), ({}, False),
])
def test_domaine_autorise(environ, attendu):
    assert validation_sim.domaine_autorise(environ) is attendu


def test_observateur_refuse_hors_domaine_43(tmp_path):
    with pytest.raises(RuntimeError, match="ROS_DOMAIN_ID='42'"):
        Observateur(tmp_path, Journal(str(tmp_path / "x.log")), list, {"ROS_DOMAIN_ID": "42"})


def test_journal_du_robot_est_celui_de_la_config():
    assert validation_sim.JOURNAL_ROBOT == config[LOGGING_FILE_NAME] == "/home/ros2_ws/log/robot.log"


def test_codes_graves():
    assert validation_sim.CODES_REJEU == (
        "tamponnee", "deja_tamponnee", "interrompue", "trop_longue", "erreur_journal", "noeud_absent",
        "roues_sans_cmd_vel", "roues_non_arretees", "absente", "homonyme", "erreur_ecriture")
    assert validation_sim.CODES_ROUES == (
        "roues_validees", "deja_validees", "non_rejouee", "sans_roues", "absente", "nom_invalide",
        "payload_invalide", "erreur_ecriture")


# ================================================================ séquences : la fenêtre
@pytest.mark.parametrize("duree_jouee, code", [
    (3799, "interrompue"),   # < 0,95 × 4000
    (3800, "tamponnee"),     # = 0,95 × 4000
    (9000, "tamponnee"),     # = 4000 + 5000
    (9001, "trop_longue"),
])
def test_fenetre_de_jeu(banc, duree_jouee, code):
    obs, racine, _, _ = banc
    assert codes(jouer(obs, "calme", 1000, 1000 + duree_jouee)) == [("sequence", "essai/calme", code, code == "tamponnee")]
    rejeu = registre(racine)["sequence"].get("essai/calme", {}).get("rejeu")
    assert rejeu == (donnees.empreinte_contenu("sequence", "essai/calme", racine) if code == "tamponnee" else None)


def test_tampon_ecrit_au_format_grave_sans_temporaire(banc):
    obs, racine, _, _ = banc
    jouer(obs, "calme", 0, 4000)
    attendu = {"version": 1, "sequence": {"essai/calme": {
        "rejeu": donnees.empreinte_contenu("sequence", "essai/calme", racine)}}, "expression": {}, "lumiere": {}}
    assert (racine / "json/validations-sim.json").read_bytes() == donnees.serialiser_registre(attendu)
    assert os.listdir(racine / "json/backup/.tmp") == []


def test_relance_du_meme_nom_interrompt(banc):
    obs, racine, _, _ = banc
    assert obs.etat_animation(0, "calme") == []
    # Relancée à 3900 ms, DANS la fenêtre (≥ 0,95 × 4000) : seule la relance la disqualifie.
    assert codes(obs.etat_animation(3900, "calme")) == [("sequence", "essai/calme", "interrompue", False)]
    # La relance, elle, jouée jusqu'au bout, est tamponnée.
    assert codes(obs.etat_animation(7900, "")) == [("sequence", "essai/calme", "tamponnee", True)]


def test_empreinte_deja_au_registre_aucune_ecriture(banc):
    obs, racine, _, _ = banc
    jouer(obs, "calme", 0, 4000)
    chemin = racine / "json/validations-sim.json"
    os.utime(chemin, (1, 1))
    assert codes(jouer(obs, "calme", 10000, 14000)) == [("sequence", "essai/calme", "deja_tamponnee", True)]
    assert os.stat(chemin).st_mtime == 1


def test_tampon_rejeu_garde_le_tampon_roues(banc):
    obs, racine, _, _ = banc
    ecrire(racine, "json/validations-sim.json", {"version": 1, "sequence": {
        "essai/calme": {"rejeu": "ancien", "roues": "R", "origine_roues": "heritee"}}})
    jouer(obs, "calme", 0, 4000)
    assert registre(racine)["sequence"]["essai/calme"] == {
        "rejeu": donnees.empreinte_contenu("sequence", "essai/calme", racine), "roues": "R", "origine_roues": "heritee"}


def test_ecriture_retire_les_orphelines(banc):
    obs, racine, _, _ = banc
    ecrire(racine, "json/validations-sim.json", {"version": 1, "sequence": {"essai/effacee": {"rejeu": "x"}},
                                                  "expression": {"partie": {"rejeu": "y"}}, "lumiere": {}})
    jouer(obs, "calme", 0, 4000)
    assert registre(racine) == {"version": 1, "sequence": {"essai/calme": {
        "rejeu": donnees.empreinte_contenu("sequence", "essai/calme", racine)}}, "expression": {}, "lumiere": {}}


def test_sequence_absente_ou_homonyme_jamais_tamponnee(banc):
    obs, racine, _, _ = banc
    assert codes(obs.etat_animation(0, "inconnue")) == [("sequence", "inconnue", "absente", False)]
    v = obs.etat_animation(0, "double")
    assert codes(v) == [("sequence", "double", "homonyme", False)]
    assert v[0]["detail"] == ["même nom dans autre/double, essai/double"]
    assert obs.etat_animation(4000, "") == []
    assert not (racine / "json/validations-sim.json").exists()


# ================================================================ séquences : journal et nœuds
def test_erreur_au_journal_pendant_le_jeu(banc):
    obs, racine, journal, _ = banc
    assert obs.etat_animation(0, "calme") == []
    with open(journal, "a", encoding="utf-8") as f:
        f.write(LIGNE_ERREUR)
    v = obs.etat_animation(4000, "")
    assert codes(v) == [("sequence", "essai/calme", "erreur_journal", False)]
    assert v[0]["detail"] == [LIGNE_ERREUR.rstrip("\n")]
    assert not (racine / "json/validations-sim.json").exists()


def test_erreur_anterieure_au_depart_ignoree(banc):
    obs, _, journal, _ = banc
    with open(journal, "a", encoding="utf-8") as f:
        f.write(LIGNE_ERREUR)
    assert codes(jouer(obs, "calme", 0, 4000)) == [("sequence", "essai/calme", "tamponnee", True)]


def test_journal_tourne_pendant_le_jeu_relu_depuis_le_debut(banc):
    obs, _, journal, _ = banc
    with open(journal, "a", encoding="utf-8") as f:
        f.write(LIGNE_INFO * 10)
    assert obs.etat_animation(0, "calme") == []
    journal.write_text(LIGNE_ERREUR, encoding="utf-8")  # rotation : fichier neuf, plus court
    assert codes(obs.etat_animation(4000, "")) == [("sequence", "essai/calme", "erreur_journal", False)]


def test_noeud_disparu_pendant_le_jeu(banc):
    obs, _, _, noeuds = banc
    assert obs.etat_animation(0, "calme") == []
    noeuds.remove("face_sim_node")
    v = obs.etat_animation(4000, "")
    assert codes(v) == [("sequence", "essai/calme", "noeud_absent", False)]
    assert v[0]["detail"] == ["face_sim_node"]


# ================================================================ séquences à roues
def test_roues_arretees_une_seconde_apres_la_fin(banc):
    obs, racine, _, _ = banc
    assert obs.etat_animation(0, "roule") == []
    obs.cmd_vel(500, False)
    assert obs.etat_animation(4000, "") == []      # en attente du cmd_vel nul
    obs.cmd_vel(4400, True)
    assert obs.tic(4999) == []
    assert codes(obs.tic(5000)) == [("sequence", "essai/roule", "tamponnee", True)]
    assert registre(racine)["sequence"]["essai/roule"] == {
        "rejeu": donnees.empreinte_contenu("sequence", "essai/roule", racine)}  # roues : à l'œil, pas ici


def test_roues_encore_en_mouvement(banc):
    obs, _, _, _ = banc
    obs.etat_animation(0, "roule")
    obs.cmd_vel(500, True)
    obs.etat_animation(4000, "")
    obs.cmd_vel(4900, False)
    assert codes(obs.tic(5000)) == [("sequence", "essai/roule", "roues_non_arretees", False)]


def test_roues_sans_cmd_vel_pendant_le_jeu(banc):
    obs, _, _, _ = banc
    obs.cmd_vel(-100, True)   # reçu AVANT le départ : ne prouve pas que la chaîne tourne
    obs.etat_animation(0, "roule")
    obs.etat_animation(4000, "")
    assert codes(obs.tic(5000)) == [("sequence", "essai/roule", "roues_sans_cmd_vel", False)]


# ================================================================ expressions et lumières
def test_expression_tenue_jusqu_au_bout(banc):
    obs, racine, _, _ = banc
    assert obs.commande(0, "face", "joie") == []
    assert obs.tic(1999) == []
    assert codes(obs.tic(2000)) == [("expression", "joie", "tamponnee", True)]
    assert registre(racine)["expression"]["joie"] == {"rejeu": donnees.empreinte_contenu("expression", "joie", racine)}


def test_expression_longue_tenue_plafonnee_a_10_s(banc):
    obs, _, _, _ = banc
    obs.commande(0, "face", "longue")
    assert obs.tic(9999) == []
    assert codes(obs.tic(10000)) == [("expression", "longue", "tamponnee", True)]


def test_expression_coupee_par_une_autre_commande(banc):
    obs, racine, _, _ = banc
    obs.commande(0, "face", "joie")
    assert codes(obs.commande(500, "face", "stop")) == [("expression", "joie", "interrompue", False)]
    assert obs.tic(5000) == []
    assert not (racine / "json/validations-sim.json").exists()


def test_expression_erreur_du_visage_seulement(banc):
    obs, _, journal, _ = banc
    obs.commande(0, "face", "joie")
    with open(journal, "a", encoding="utf-8") as f:
        f.write(LIGNE_ERREUR)            # autre nœud : ne concerne pas le visage
    assert codes(obs.tic(2000)) == [("expression", "joie", "tamponnee", True)]
    obs.commande(3000, "face", "longue")
    with open(journal, "a", encoding="utf-8") as f:
        f.write(LIGNE_ERREUR_VISAGE)
    assert codes(obs.tic(13000)) == [("expression", "longue", "erreur_journal", False)]


def test_expression_sans_face_sim(banc):
    obs, _, _, noeuds = banc
    obs.commande(0, "face", "joie")
    noeuds.remove("face_sim_node")
    assert codes(obs.tic(2000)) == [("expression", "joie", "noeud_absent", False)]


def test_lumiere_tenue_avec_leds_sim(banc):
    obs, racine, _, noeuds = banc
    obs.commande(0, "robot_lights", "calme")
    assert codes(obs.tic(1000)) == [("lumiere", "calme", "tamponnee", True)]
    noeuds.remove("leds_sim_node")
    obs.commande(2000, "robot_lights", "calme")
    assert codes(obs.tic(3000)) == [("lumiere", "calme", "noeud_absent", False)]


def test_commande_inconnue_ignoree(banc):
    obs, _, _, _ = banc
    assert obs.commande(0, "face", "inconnue") == []
    assert obs.commande(0, "face", {"x": 1}) == []
    assert obs.tic(20000) == []


# ================================================================ validation à l'œil des roues
def valider(obs, nom, id_="v1"):
    return obs.valider_roues(json.dumps({"id": id_, "name": nom}))


def test_roues_refusees_sans_rejeu_puis_validees(banc):
    obs, racine, _, _ = banc
    v = valider(obs, "essai/roule")
    assert (v["id"], v["code"], v["ok"]) == ("v1", "non_rejouee", False)
    obs.etat_animation(0, "roule")
    obs.cmd_vel(500, False)
    obs.etat_animation(2000, "")          # interrompue : toujours pas rejouée
    assert valider(obs, "essai/roule")["code"] == "non_rejouee"
    obs.etat_animation(10000, "roule")
    obs.etat_animation(14000, "")
    obs.cmd_vel(14100, True)
    obs.tic(15000)
    assert valider(obs, "essai/roule")["code"] == "roues_validees"
    assert registre(racine)["sequence"]["essai/roule"] == {
        "rejeu": donnees.empreinte_contenu("sequence", "essai/roule", racine),
        "roues": donnees.empreinte_roues(AVEC_ROUES), "origine_roues": "sim"}
    assert valider(obs, "essai/roule")["code"] == "deja_validees"
    # Retouche après validation : la version actuelle n'a pas été rejouée.
    ecrire(racine, "json/sequences/essai/roule.json", {**AVEC_ROUES, "duration": 3000})
    assert valider(obs, "essai/roule")["code"] == "non_rejouee"


@pytest.mark.parametrize("brut, code", [
    ('{"id": "v1", "name": "essai/calme"}', "sans_roues"),
    ('{"id": "v1", "name": "essai/inconnue"}', "absente"),
    ('{"id": "v1", "name": "../x"}', "nom_invalide"),
    ('{"name": "essai/roule"}', "payload_invalide"),
    ('pas du json', "payload_invalide"),
])
def test_demandes_de_validation_refusees(banc, brut, code):
    obs, racine, _, _ = banc
    v = obs.valider_roues(brut)
    assert (v["code"], v["ok"]) == (code, False)
    assert not (racine / "json/validations-sim.json").exists()
