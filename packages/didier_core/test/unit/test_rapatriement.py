"""Rapatriement des éditions du robot vers data/ du PC (lot L1d-4, deploy/rapatrier_editions.py),
sans Ansible ni Pi : le « Pi » et le « PC » sont deux dossiers jetables ; le journal et les
fichiers du « Pi » sont écrits par le VRAI écrivain (didier_web.data_edit.traiter).

Valeurs GRAVÉES (octets exacts et sha256 en littéral, calculés hors du module). Le cas central :
une entrée commitée sur le PC et pas encore déployée survit au rapatriement d'une AUTRE entrée du
même fichier (spec L1d, décision 13 — tirer le fichier entier l'écraserait).

Mutations jouées (chacune rougit au moins un test) :
  - fichier à entrées rapatrié EN ENTIER au lieu de l'entrée -> test_l_entree_non_deployee_du_pc_survit
  - entrées du journal ignorées (rien de reporté) -> test_seule_l_entree_du_journal_change
  - nom du journal non revalidé -> test_un_nom_forge_est_refuse_avant_tout_chemin
  - restauration sautée sur tests rouges -> test_tests_rouges_remettent_data_a_l_identique
  - refus git ignoré -> test_preparer_refuse_une_cible_modifiee_dans_git
"""
import base64
import datetime
import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess

import pytest

from didier_web.data_edit import traiter
from theatre_contrats import donnees
from test.unit.test_data_edit import BOUCHE_NOIRE, BOUCHE_ROUGE, OEIL

MONO = pathlib.Path(__file__).resolve().parents[4]
_spec = importlib.util.spec_from_file_location("rapatrier_editions", MONO / "deploy" / "rapatrier_editions.py")
rapatriement = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rapatriement)

MAINTENANT = datetime.datetime(2026, 11, 13, 21, 5, 7)

EXPRESSIONS_PC = {
    "joie": {"duration": 2000, "loop": True, "mouths": [[1, "neutre.png"]], "left_eyes": [], "right_eyes": []},
    "colere": {"duration": 1000, "loop": False, "mouths": [], "left_eyes": [[1, "rond.png"]], "right_eyes": []},
    # Commitée sur le PC, PAS encore déployée : absente du Pi.
    "surprise": {"duration": 500, "loop": False, "mouths": [], "left_eyes": [], "right_eyes": [[1, "rond.png"]]},
}
SEQUENCE = {"duration": 1000, "keys": "a", "neck": [[0, 0.5], [1, 0.37]]}
JOIE_RETOUCHEE = {"duration": 3000, "loop": True, "mouths": [[1, "neutre.png"]], "left_eyes": [], "right_eyes": []}

# Octets GRAVÉS d'expressions.json du PC après rapatriement de `joie` seule : ordre conservé,
# `surprise` (PC seul) intacte, json.dumps(indent=4) + "\n".
EXPRESSIONS_ATTENDUES = (
    '{\n    "joie": {\n        "duration": 3000,\n        "loop": true,\n        "mouths": [\n'
    '            [\n                1,\n                "neutre.png"\n            ]\n        ],\n'
    '        "left_eyes": [],\n        "right_eyes": []\n    },\n    "colere": {\n'
    '        "duration": 1000,\n        "loop": false,\n        "mouths": [],\n        "left_eyes": [\n'
    '            [\n                1,\n                "rond.png"\n            ]\n        ],\n'
    '        "right_eyes": []\n    },\n    "surprise": {\n        "duration": 500,\n'
    '        "loop": false,\n        "mouths": [],\n        "left_eyes": [],\n        "right_eyes": [\n'
    '            [\n                1,\n                "rond.png"\n            ]\n        ]\n    }\n}\n'
).encode("utf-8")
SHA_EXPRESSIONS_ATTENDUES = "30843496f647f9f524210e4c32e7742e95c6c3b1a9e8b61958117ce5d1702cd0"


def demande(kind, mode, name, content, id_, **autres):
    d = {"id": id_, "kind": kind, "mode": mode, "name": name, "content": content}
    d.update(autres)
    return json.dumps(d)


@pytest.fixture
def pi(tmp_path):
    """Un « Pi » déployé : mêmes données que le PC, sauf `surprise` (pas encore déployée)."""
    racine = tmp_path / "pi"
    _remplir(racine, {k: v for k, v in EXPRESSIONS_PC.items() if k != "surprise"})
    return racine


@pytest.fixture
def pc(tmp_path):
    racine = tmp_path / "pc"
    _remplir(racine, EXPRESSIONS_PC)
    return racine


def _remplir(racine, expressions):
    for dossier in ("json/sequences/essai", "medias/audios", "medias/visuals/mouth", "medias/visuals/eye"):
        (racine / dossier).mkdir(parents=True)
    (racine / "medias/visuals/mouth/neutre.png").write_bytes(BOUCHE_NOIRE)
    (racine / "medias/visuals/eye/rond.png").write_bytes(OEIL)
    for relatif, valeur in (("json/expressions.json", expressions),
                            ("json/robot_lights.json", {}), ("json/lights_base.json", {}),
                            ("json/colors.json", {"BLUE": [0, 0, 255]})):
        (racine / relatif).write_text(json.dumps(valeur, indent=4), encoding="utf-8")


def _editer_sur_le_pi(pi):
    """Trois retouches par le VRAI écrivain : une séquence créée, une expression remplacée,
    une image créée. Rend le texte du journal."""
    joie = EXPRESSIONS_PC["joie"]
    sha_joie = donnees.sha256_entree(joie)
    for brut in (demande("sequence", "create", "essai/retouche", SEQUENCE, "s1"),
                 demande("expression", "replace", "joie", JOIE_RETOUCHEE, "e1", base_sha256=sha_joie),
                 demande("image", "create", "mouth/rouge", base64.b64encode(BOUCHE_ROUGE).decode(), "i1")):
        verdict = traiter(brut, pi, True, MAINTENANT)
        assert verdict["code"] == "ok", verdict
    return (pi / "json/backup/EDITIONS-EN-ATTENTE.jsonl").read_text(encoding="utf-8")


def _tirer(pi, lignes, dossier):
    """Ce que fait la tâche `fetch` du playbook : les fichiers nommés, même disposition."""
    for relatif in rapatriement.fichiers_a_tirer(lignes):
        source = pi / relatif
        if source.is_file():
            (dossier / relatif).parent.mkdir(parents=True, exist_ok=True)
            (dossier / relatif).write_bytes(source.read_bytes())
    return dossier


# ================================================================ journal et cibles
def test_les_fichiers_a_tirer_sont_ceux_du_journal_dans_l_ordre(pi):
    lignes = rapatriement.lire_journal(_editer_sur_le_pi(pi))
    assert rapatriement.fichiers_a_tirer(lignes) == [
        "json/sequences/essai/retouche.json", "json/expressions.json", "medias/visuals/mouth/rouge.png"]


def test_une_entree_retouchee_deux_fois_n_est_tiree_qu_une_fois():
    lignes = rapatriement.lire_journal(
        '{"kind":"brique","name":"bleu","sha256":"a"}\n{"kind":"lumiere","name":"calme","sha256":"b"}\n'
        '{"kind":"brique","name":"bleu","sha256":"c"}\n')
    assert rapatriement.elements(lignes) == [("brique", "bleu", "c"), ("lumiere", "calme", "b")]
    assert rapatriement.fichiers_a_tirer(lignes) == ["json/lights_base.json", "json/robot_lights.json"]


@pytest.mark.parametrize("ligne, message", [
    ('{"kind":"sequence","name":"../x/y"}', "journal, ligne 1 : nom '../x/y' hors forme pour sequence"),
    ('{"kind":"image","name":"autre/x"}', "journal, ligne 1 : nom 'autre/x' hors forme pour image"),
    ('{"kind":"relais","name":"x"}', "journal, ligne 1 : kind 'relais' inconnu"),
    ('pas du json', "journal, ligne 1 : JSON illisible"),
    ('[1]', "journal, ligne 1 : objet attendu"),
])
def test_un_nom_forge_est_refuse_avant_tout_chemin(ligne, message):
    with pytest.raises(rapatriement.Refus) as refus:
        rapatriement.lire_journal(ligne + "\n")
    assert str(refus.value) == message


def test_noms_des_copies_rapatriees_graves():
    assert rapatriement.nom_rapatrie("sequence", "essai/retouche") == "essai__retouche__rapatrie.json"
    assert rapatriement.nom_rapatrie("image", "mouth/rouge") == "mouth__rouge__rapatrie.png"
    assert rapatriement.nom_rapatrie("lumiere", "chase me") == "lumiere__chase_me__rapatrie.json"


# ================================================================ report dans data/
def test_l_entree_non_deployee_du_pc_survit(pi, pc, tmp_path):
    lignes = rapatriement.lire_journal(_editer_sur_le_pi(pi))
    rapatriement.reporter(lignes, _tirer(pi, lignes, tmp_path / "tire"), pc)
    octets = (pc / "json/expressions.json").read_bytes()
    assert octets == EXPRESSIONS_ATTENDUES
    assert hashlib.sha256(octets).hexdigest() == SHA_EXPRESSIONS_ATTENDUES


def test_seule_l_entree_du_journal_change(pi, pc, tmp_path):
    lignes = rapatriement.lire_journal(_editer_sur_le_pi(pi))
    rapatriement.reporter(lignes, _tirer(pi, lignes, tmp_path / "tire"), pc)
    apres = json.loads((pc / "json/expressions.json").read_text(encoding="utf-8"))
    assert list(apres) == ["joie", "colere", "surprise"]
    assert apres["joie"] == JOIE_RETOUCHEE
    assert apres["colere"] == EXPRESSIONS_PC["colere"]
    assert apres["surprise"] == EXPRESSIONS_PC["surprise"]


def test_sequence_et_image_arrivent_a_l_octet(pi, pc, tmp_path):
    lignes = rapatriement.lire_journal(_editer_sur_le_pi(pi))
    _, rapatries, messages = rapatriement.reporter(lignes, _tirer(pi, lignes, tmp_path / "tire"), pc)
    sequence = (pc / "json/sequences/essai/retouche.json").read_bytes()
    assert sequence == (pi / "json/sequences/essai/retouche.json").read_bytes()
    assert sequence == (b'{\n    "duration": 1000,\n    "keys": "a",\n    "neck": [\n'
                        b'        [\n            0,\n            0.5\n        ],\n        [\n            1,\n'
                        b'            0.37\n        ]\n    ]\n}\n')
    assert (pc / "medias/visuals/mouth/rouge.png").read_bytes() == BOUCHE_ROUGE
    assert [nom for nom, _ in rapatries] == ["essai__retouche__rapatrie.json", "expression__joie__rapatrie.json",
                                            "mouth__rouge__rapatrie.png"]
    assert messages == ["rapatriée : sequence essai/retouche", "rapatriée : expression joie",
                        "rapatriée : image mouth/rouge"]


def test_un_element_absent_du_pi_est_ignore_et_dit(pc, tmp_path):
    lignes = rapatriement.lire_journal('{"kind":"sequence","name":"essai/perdue","sha256":"x"}\n'
                                       '{"kind":"expression","name":"inconnue","sha256":"y"}\n')
    tire = tmp_path / "tire"
    (tire / "json").mkdir(parents=True)
    (tire / "json/expressions.json").write_text("{}", encoding="utf-8")
    avant = (pc / "json/expressions.json").read_bytes()
    originaux, rapatries, messages = rapatriement.reporter(lignes, tire, pc)
    assert messages == ["ignorée (absente du Pi) : sequence essai/perdue",
                        "ignorée (absente du Pi) : expression inconnue"]
    assert rapatries == [] and originaux == {}
    assert not (pc / "json/sequences/essai/perdue.json").exists()
    assert (pc / "json/expressions.json").read_bytes() == avant


def test_un_sha_different_du_journal_est_dit(pi, pc, tmp_path):
    lignes = [dict(l, sha256="0" * 64) if l["kind"] == "image" else l
              for l in rapatriement.lire_journal(_editer_sur_le_pi(pi))]
    _, _, messages = rapatriement.reporter(lignes, _tirer(pi, lignes, tmp_path / "tire"), pc)
    assert ("le Pi porte une autre version que la dernière journalisée : image mouth/rouge "
            "(rapatriée telle qu'elle est sur le Pi)") in messages


def test_un_dossier_absent_du_pc_est_refuse(pi, pc, tmp_path):
    lignes = rapatriement.lire_journal(_editer_sur_le_pi(pi))
    (pc / "json/sequences/essai").rmdir()
    with pytest.raises(rapatriement.Refus) as refus:
        rapatriement.reporter(lignes, _tirer(pi, lignes, tmp_path / "tire"), pc)
    assert str(refus.value) == ("sequence essai/retouche : dossier json/sequences/essai absent du PC "
                                "(une création de dossier passe par git)")


# ================================================================ tests de data/ et restauration
def _empreinte_arbre(racine):
    return {str(p.relative_to(racine)): p.read_bytes() for p in sorted(racine.rglob("*")) if p.is_file()}


def test_tests_rouges_remettent_data_a_l_identique(pi, pc, tmp_path):
    lignes = rapatriement.lire_journal(_editer_sur_le_pi(pi))
    avant = _empreinte_arbre(pc)
    with pytest.raises(rapatriement.Refus) as refus:
        rapatriement.appliquer(lignes, _tirer(pi, lignes, tmp_path / "tire"), pc, tmp_path / "sortie",
                               lancer=lambda: 1, maintenant=MAINTENANT)
    assert str(refus.value).startswith("tests de data/ ROUGES sur les retouches du robot : data/ est remis")
    assert _empreinte_arbre(pc) == avant
    assert not (tmp_path / "sortie").exists()


def test_tests_verts_preparent_les_copies_et_le_resultat(pi, pc, tmp_path):
    lignes = rapatriement.lire_journal(_editer_sur_le_pi(pi))
    appels = []
    resultat = rapatriement.appliquer(lignes, _tirer(pi, lignes, tmp_path / "tire"), pc, tmp_path / "sortie",
                                      lancer=lambda: appels.append(1) or 0, maintenant=MAINTENANT)
    assert appels == [1]
    assert (resultat["date"], resultat["heure"]) == ("2026-11-13", "210507")
    assert sorted(os.listdir(tmp_path / "sortie/rapatries")) == [
        "essai__retouche__rapatrie.json", "expression__joie__rapatrie.json", "mouth__rouge__rapatrie.png"]
    assert (tmp_path / "sortie/rapatries/expression__joie__rapatrie.json").read_bytes() == (
        b'{\n    "duration": 3000,\n    "loop": true,\n    "mouths": [\n        [\n            1,\n'
        b'            "neutre.png"\n        ]\n    ],\n    "left_eyes": [],\n    "right_eyes": []\n}\n')
    # Rien n'a été rejoué en sim dans ce PC jetable : la porte sim n'arrête pas, elle compte.
    assert "à rejouer en sim : sequence essai/retouche" in resultat["non_validees"]
    assert json.loads((tmp_path / "sortie/resultat.json").read_text(encoding="utf-8")) == resultat


def test_les_tests_lances_sont_les_cinq_de_data():
    assert rapatriement.TESTS_DONNEES == (
        "test/unit/test_sequences_json.py", "test/unit/test_sequences_assets.py",
        "test/unit/test_expressions_json.py", "test/unit/test_lights_json.py",
        "test/unit/test_visuels_png.py")
    for relatif in rapatriement.TESTS_DONNEES:
        assert (MONO / rapatriement.PACKAGE_TESTS / relatif).is_file(), relatif
    assert "test/unit/test_validations_sim.py" not in rapatriement.TESTS_DONNEES


# ================================================================ refus git (avant tout tirage)
def test_preparer_refuse_une_cible_modifiee_dans_git(pc, tmp_path, capsys):
    subprocess.run(["git", "init", "-q", str(pc)], check=True)
    subprocess.run(["git", "-C", str(pc), "add", "."], check=True)
    subprocess.run(["git", "-C", str(pc), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"],
                   check=True)
    journal = tmp_path / "journal.jsonl"
    journal.write_text('{"kind":"expression","name":"joie","sha256":"x"}\n', encoding="utf-8")
    argv = ["preparer", "--journal", str(journal), "--depot", str(pc), "--data-dir", str(pc)]
    assert rapatriement.main(argv) == 0
    assert capsys.readouterr().out == "json/expressions.json\n"
    (pc / "json/expressions.json").write_text("{}", encoding="utf-8")
    assert rapatriement.main(argv) == 1
    assert capsys.readouterr().out == (
        "REFUS : modification(s) locale(s) non commitée(s) sur un fichier visé — rien n'est copié ; "
        "commiter ou annuler d'abord :\n   M json/expressions.json\n")
