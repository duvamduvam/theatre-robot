"""Répertoire : filtre des séquences GRAVÉ sur les VRAIS fichiers (spec §8.4) et
vocabulaire de déplacements (« composé par David », valeurs du 02/11)."""
import pytest

from conftest import DEPLACEMENTS_YAML, SEQUENCES

# Les séquences jouables par le sélecteur au 02/11 : clé `types`, hors bugs/,
# SANS piste roues. Une séquence ajoutée/retirée dans json/ fait rougir ici.
JOUABLES = [
    "eternel-short/appel-eternel-life.json",
    "eternel-show/appel-eternel-life.json", "eternel-show/bon-attend.json",
    "eternel-show/c-est-qui-le-con.json", "eternel-show/internet.json",
    "eternel-show/little-move.json", "eternel-show/little-neck.json",
    "eternel-show/little-neck2.json", "eternel-show/neck-side-to-side.json",
    "eternel-show/t-es-sur.json", "eternel-show/upload-cerveau.json", "eternel-show/warning.json",
    "random/aurore.json", "random/michel-sardou.json", "random/pour-votre-securite.json",
    "random/quand-on-voit.json", "random/quoi-ma-geule.json", "videos/eye-left.json",
]


def test_filtre_des_sequences_grave():
    from didier_jeu.repertoire import candidates
    assert [s.chemin for s in candidates(SEQUENCES)] == JOUABLES


def test_aucune_jouable_n_a_de_roues_ni_ne_vient_de_bugs():
    from didier_jeu.repertoire import candidates, lire_sequences
    toutes = {s.chemin: s for s in lire_sequences(SEQUENCES)}
    # Le filtre MORD sur les vrais fichiers : ces séquences ont `types` mais sont exclues.
    assert toutes["eternel-show/pas-un-jouet.json"].roues          # bonjour + roues
    assert toutes["eternel-show/little-move2.json"].roues          # little move + roues
    assert toutes["eternel-short/appel-eternel-life2.json"].roues  # types [] + roues
    assert toutes["bugs/bug1.json"].a_types                         # type bug
    noms = [s.chemin for s in candidates(SEQUENCES)]
    for exclue in ("eternel-show/pas-un-jouet.json", "eternel-show/little-move2.json",
                   "eternel-short/appel-eternel-life2.json", "bugs/bug1.json"):
        assert exclue not in noms
    assert not any(s.roues for s in candidates(SEQUENCES))


def _ecrire(dossier, chemin, data):
    import json
    f = dossier / chemin
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data), encoding="utf-8")


def test_filtre_grave_sur_un_repertoire_construit(tmp_path):
    """Chaque règle du filtre, sur des fichiers écrits ici (valeurs en dur)."""
    from didier_jeu.repertoire import candidates
    _ecrire(tmp_path, "a/jouable.json", {"types": ["random"], "duration": 1000, "faces": [[1, "x.png"]]})
    _ecrire(tmp_path, "a/roues.json", {"types": ["random"], "wheels": [[1, {"x": 1}]]})
    _ecrire(tmp_path, "a/roues_vides.json", {"types": ["random"], "wheels": []})     # piste vide : aucun mouvement
    _ecrire(tmp_path, "a/sans_types.json", {"duration": 1000})
    _ecrire(tmp_path, "a/types_vides.json", {"types": []})
    _ecrire(tmp_path, "bugs/panne.json", {"types": ["random"]})
    assert [s.chemin for s in candidates(tmp_path)] == ["a/jouable.json", "a/roues_vides.json", "a/types_vides.json"]


def test_doublon_jouable_refuse_doublon_sans_emploi_liste(tmp_path):
    import pytest as _pt
    from didier_jeu.repertoire import RepertoireError, candidates, par_emploi
    emplois = {"random": "spontanee"}
    _ecrire(tmp_path, "a/muet.json", {"types": []})
    _ecrire(tmp_path, "b/muet.json", {"types": []})
    pools, sans, doublons = par_emploi(candidates(tmp_path), emplois)
    assert pools == {} and sans == ["muet"] and doublons == ["muet"]
    _ecrire(tmp_path, "a/joue.json", {"types": ["random"]})
    _ecrire(tmp_path, "b/joue.json", {"types": []})
    with _pt.raises(RepertoireError, match="joue"):
        par_emploi(candidates(tmp_path), emplois)


def test_emplois_grave():
    from conftest import donnees_reglages
    from didier_jeu.repertoire import candidates, par_emploi
    pools, sans_emploi, doublons = par_emploi(candidates(SEQUENCES), donnees_reglages()["emplois"])
    assert {k: [s.nom for s in v] for k, v in pools.items()} == {
        "accueil": ["bon-attend", "t-es-sur"],
        "spontanee": ["c-est-qui-le-con", "little-move", "little-neck", "little-neck2",
                      "neck-side-to-side", "aurore", "michel-sardou", "pour-votre-securite",
                      "quand-on-voit", "quoi-ma-geule", "eye-left"],
    }
    # types [] : chargées mais sans emploi (journalisées au démarrage).
    assert sans_emploi == ["appel-eternel-life", "internet", "upload-cerveau", "warning"]
    # Homonymes SANS emploi (eternel-short/ et eternel-show/) : listés, pas refusés.
    assert doublons == ["appel-eternel-life"]


def test_vocabulaire_de_deplacements_grave():
    from didier_jeu.repertoire import charger_deplacements
    assert charger_deplacements(DEPLACEMENTS_YAML) == {
        "approcher": {"cmd": "avancer", "metres": 1.0},
        "se_tourner_vers": {"cmd": "tourner"},
        "aller_voir": {"cmd": "aller_voir"},
        "faire_le_tour": {"cmd": "tour_de"},
    }


def test_commandes_regisseur_egales_au_contrat():
    from robot_rehearsal import contracts
    from didier_jeu.repertoire import COMMANDES_REGISSEUR
    assert set(COMMANDES_REGISSEUR) == {contracts.CHAT_MOVE_GOTO_CMD, contracts.CHAT_MOVE_TOUR_CMD,
                                        contracts.CHAT_MOVE_TURN_CMD, contracts.CHAT_MOVE_FORWARD_CMD}


def test_reculer_refuse_comme_le_regisseur():
    """Le régisseur refuse un avancer négatif (FORWARD_MIN_M) : un verbe
    « reculer » ne ferait que des refus — il est refusé au chargement."""
    from robot_rehearsal import contracts
    from didier_jeu.repertoire import RepertoireError, valider_deplacements
    assert contracts.FORWARD_MIN_M == 0.1
    with pytest.raises(RepertoireError):
        valider_deplacements({"reculer": {"cmd": "avancer", "metres": -1.0}})
    with pytest.raises(RepertoireError):
        valider_deplacements({"danser": {"cmd": "valser"}})


def test_commande_et_payload_animation():
    from didier_jeu.repertoire import Sequence, charger_deplacements, commande, payload_animation
    d = charger_deplacements(DEPLACEMENTS_YAML)
    assert commande(d, "aller_voir", objet="anneaux") == {"cmd": "aller_voir", "objet": "anneaux"}
    assert commande(d, "se_tourner_vers", angle_deg=-12.0) == {"cmd": "tourner", "angle_deg": -12.0}
    assert payload_animation(Sequence("aurore", ("random",), 7.0, "r/aurore.json", False, True)) == '"aurore"'
