"""Garanties des bugs joués (lot I0, theatre_contrats.bugs_joues, étude improvisation §2.1) :
une séquence fautive par règle, message GRAVÉ ; l'inventaire RÉEL de data/ gravé ; une
séquence piégée déposée dans une copie du vrai dossier est refusée, les autres restent."""
import json
import os
import shutil

import pytest

from theatre_contrats import bugs_joues, donnees

MONO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA = os.path.join(MONO, "data")


def ecrire(racine, relatif, valeur):
    chemin = racine / relatif
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(valeur, indent=4))


@pytest.fixture
def data_dir(tmp_path):
    ecrire(tmp_path, "json/audios-prives.json", {"version": 1, "audios": {
        "court.wav": {"sha256": "0" * 64, "taille": 1, "duree_s": 3.0},
        "pile.wav": {"sha256": "0" * 64, "taille": 1, "duree_s": 4.0},
        "long.wav": {"sha256": "0" * 64, "taille": 1, "duree_s": 4.01},
        "chanson.mp3": {"sha256": "0" * 64, "taille": 1, "duree_s": None}}})
    expression = {"duration": 1000, "loop": True, "mouths": [], "left_eyes": [], "right_eyes": []}
    ecrire(tmp_path, "json/expressions.json", {"default": dict(expression, default=True),
                                               "off": dict(expression, default=True), "joie": expression})
    lumiere = {"duration": 1000, "loop": True, "keys": [], "sequences": {}}
    ecrire(tmp_path, "json/robot_lights.json", {"default": dict(lumiere, default=True),
                                                "default dark": dict(lumiere, default=True), "trip": lumiere})
    return tmp_path


BUG = {"keys": "", "duration": 4000, "types": ["bug-joue"], "classe": "V", "desc": "il se fige",
       "faces": [[0, "joie"]], "robot_lights": [[0, "trip"]]}


def erreurs(data_dir, **champs):
    sequence = {k: v for k, v in dict(BUG, **champs).items() if v is not None}
    return bugs_joues.verifier_bug_joue(sequence, donnees.charger_references(data_dir, "/nulle-part"))


def test_constantes_gravees():
    assert bugs_joues.DOSSIER == "bugs-joues"
    assert bugs_joues.TYPE == "bug-joue"
    assert bugs_joues.DUREE_MAX_MS == 15_000
    assert bugs_joues.SON_MAX_S == 4.0
    assert bugs_joues.PISTES_INTERDITES == ("wheels", "relay")
    assert bugs_joues.PISTES_PORTEUSES == ("neck", "left_arm", "right_arm")


def test_bug_conforme(data_dir):
    assert erreurs(data_dir) == []
    assert erreurs(data_dir, duration=15_000, audios=[[0, "pile.wav"]]) == []


@pytest.mark.parametrize("champs,attendu", [
    ({"wheels": [[0, [0.2, 0.2]], [1, [0, 0]]]}, ["piste wheels interdite dans un bug joué (même vide)"]),
    ({"wheels": []}, ["piste wheels interdite dans un bug joué (même vide)"]),
    ({"relay": [[0, "on"]]}, ["piste relay interdite dans un bug joué (même vide)"]),
    ({"duration": 15_001}, ["duration 15001 ms au-delà de 15000 ms (DUREE_MAX_MS) : au-delà, c'est une panne"]),
    ({"types": ["random"]}, ["types : 'bug-joue' absent (tout fichier de bugs-joues/ est un bug joué)"]),
    ({"classe": None}, ["classe None : attendue parmi ('V', 'M')"]),
    ({"classe": "X"}, ["classe 'X' : attendue parmi ('V', 'M')"]),
    ({"neck": [[0, 0.5]]}, ["piste neck dans un bug de classe V (cou et bras = classe M)"]),
    ({"left_arm": [[0, 0.5]]}, ["piste left_arm dans un bug de classe V (cou et bras = classe M)"]),
    ({"desc": None}, ["desc : texte non vide de 80 caractères au plus"]),
    ({"desc": " "}, ["desc : texte non vide de 80 caractères au plus"]),
    ({"desc": "x" * 81}, ["desc : texte non vide de 80 caractères au plus"]),
    ({"direction": 3}, ["direction : texte de 200 caractères au plus, ou absente"]),
    ({"audios": [[0, "long.wav"]]}, ["audios[0] : long.wav dure 4.01 s, au-delà de 4.0 s (SON_MAX_S)"]),
    ({"audios": [[0, "chanson.mp3"]]}, ["audios[0] : durée de chanson.mp3 inconnue au manifeste (wav attendu) : "
                                        "un bug joué ne cite que des sons de 4.0 s au plus"]),
    # Deux sons de 3 s collés (le second part à 0,75 × 4 s = 3 s) : 6 s de porte audio fermée.
    ({"audios": [[0, "court.wav"], [0.75, "court.wav"]]}, ["audios : 6 s de son d'affilée, au-delà de 4.0 s (SON_MAX_S)"]),
    ({"faces": [[0, "off"]]}, ["faces : « off » devient le repos (\"default\": true) et rien ne rejoue « default » "
                               "après lui — Didier resterait ainsi après le bug"]),
    ({"robot_lights": [[0, "default"], [0.5, "default dark"]]},
     ["robot_lights : « default dark » devient le repos (\"default\": true) et rien ne rejoue « default » "
      "après lui — Didier resterait ainsi après le bug"]),
])
def test_chaque_garantie_mord(data_dir, champs, attendu):
    assert erreurs(data_dir, **champs) == attendu


def test_le_repos_rejoue_et_les_sons_separes_passent(data_dir):
    assert erreurs(data_dir, faces=[[0, "off"], [0.5, "default"]]) == []
    # Deux sons de 3 s séparés d'une seconde : jamais plus de 3 s d'affilée.
    assert erreurs(data_dir, duration=8000, audios=[[0, "court.wav"], [0.5, "court.wav"]]) == []
    assert erreurs(data_dir, classe="M", neck=[[0, 0.5]]) == []


def test_le_contrat_general_applique_les_garanties(data_dir):
    """donnees.verifier_sequence juge un bug joué COMME un bug joué : l'écrivain du robot
    (data_edit) refuse donc une retouche qui ajouterait des roues à un bug."""
    refs = donnees.charger_references(data_dir, "/nulle-part")
    sequence = dict(BUG, wheels=[[0, [0.2, 0.2]], [1, [0, 0]]])
    assert "piste wheels interdite dans un bug joué (même vide)" in donnees.verifier_sequence(sequence, refs)
    # Une séquence ordinaire garde ses roues (aucune régression du contrat général).
    ordinaire = dict(sequence, types=["random"])
    del ordinaire["classe"], ordinaire["desc"]
    assert donnees.verifier_sequence(ordinaire, refs) == []


# ---------------------------------------------------------------- l'inventaire réel de data/
INVENTAIRE_22_11 = {
    # id : (classe, durée s, pistes) — les 6 bugs de classe V de l'étude §2.2.
    "begaiement": ("V", 4.0, ("audios", "faces", "robot_lights")),
    "ecran_noir": ("V", 4.0, ("faces", "robot_lights")),
    "faux_redemarrage": ("V", 12.0, ("audios", "faces", "robot_lights")),
    "glitch_visage": ("V", 3.0, ("faces", "robot_lights")),
    "lumieres_folles": ("V", 5.0, ("faces", "left_eye", "right_eye", "robot_lights")),
    "mise_a_jour": ("V", 8.0, ("audios", "faces", "robot_lights")),
}


def test_inventaire_reel_grave():
    inventaire = bugs_joues.lire(DATA, donnees.dossier_audios_prives())
    assert inventaire.refuses == ()
    assert {b.id: (b.classe, b.duree_s, b.pistes) for b in inventaire.acceptes} == INVENTAIRE_22_11
    assert all(b.chemin == "bugs-joues/{}.json".format(b.id) for b in inventaire.acceptes)
    # Aucun bug joué, accepté ou non, ne touche les roues ni un relais.
    assert not any(p in b.pistes for b in inventaire.acceptes for p in ("wheels", "relay"))


def _copie_des_donnees(tmp_path):
    """Les références et les séquences RÉELLES, copiées : seul le piège diffère."""
    racine = tmp_path / "data"
    (racine / "json").mkdir(parents=True)
    for fichier in ("expressions.json", "robot_lights.json", "audios-prives.json"):
        shutil.copy(os.path.join(DATA, "json", fichier), racine / "json" / fichier)
    shutil.copytree(os.path.join(DATA, "json", "sequences", "bugs-joues"),
                    racine / "json" / "sequences" / "bugs-joues")
    return racine


def test_sequence_piegee_refusee_au_chargement(tmp_path):
    racine = _copie_des_donnees(tmp_path)
    piege = json.loads((racine / "json/sequences/bugs-joues/glitch_visage.json").read_text())
    piege["wheels"] = [[0, [0.3, 0.3]], [0.5, [0, 0]]]
    ecrire(racine, "json/sequences/bugs-joues/piege.json", piege)
    # Un bug joué rangé ailleurs, et un homonyme d'un vrai bug : refusés aussi.
    ecrire(racine, "json/sequences/random/egare.json", dict(BUG, faces=[[0, "default"]], robot_lights=[]))
    ecrire(racine, "json/sequences/random/ecran_noir.json", {"keys": "", "duration": 1000, "types": ["random"]})
    inventaire = bugs_joues.lire(racine, "/nulle-part")
    assert dict(inventaire.refuses) == {
        "bugs-joues/ecran_noir.json": ("nom « ecran_noir » en double (bugs-joues/ecran_noir.json, "
                                       "random/ecran_noir.json) : animations_node n'en jouerait qu'un",),
        "bugs-joues/piege.json": ("piste wheels interdite dans un bug joué (même vide)",),
        "random/egare.json": ("type 'bug-joue' hors du dossier bugs-joues/",),
    }
    assert sorted(b.id for b in inventaire.acceptes) == sorted(set(INVENTAIRE_22_11) - {"ecran_noir"})


def test_fichier_illisible_refuse_sans_faire_tomber_les_autres(tmp_path):
    racine = _copie_des_donnees(tmp_path)
    (racine / "json/sequences/bugs-joues/casse.json").write_text("{")
    inventaire = bugs_joues.lire(racine, "/nulle-part")
    assert [c for c, _ in inventaire.refuses] == ["bugs-joues/casse.json"]
    assert len(inventaire.acceptes) == 6
