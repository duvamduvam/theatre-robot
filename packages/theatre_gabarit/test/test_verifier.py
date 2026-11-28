"""Lot L3a (28/11) — `verifier_appareil` (spec L3 décision 6) et le squelette généré.

Un appareil COMPLET factice (« sono », le seul nom du registre) est posé dans un dossier
temporaire ; chaque cas casse UNE chose et grave le geste rendu. Puis le squelette est généré
par tools/nouvel_appareil.py (appareil jetable « essai ») : ses tests sont ROUGES, et la liste
des gestes est gravée en entier.
"""
import os
import pathlib
import subprocess
import sys

import pytest

from conftest import MONO, PKG
from theatre_gabarit.essais import Enregistreur, verifier_appareil

README_COMPLET = "".join(f"## {t}\n\ntexte\n\n" for t in (
    "Rôle", "Machine", "Topics", "Comportement", "Pilotes", "Simuler", "Tester", "Déployer"))
FICHIERS_COMPLETS = {
    "packages/sono_core/README.md": README_COMPLET,
    "packages/sono_core/sono_core/contrat.py": 'TOPICS = ("sono/etat", "sono/audio")\n',
    "packages/sono_core/sono_core/noeud.py": "def main():\n    pass\n\n\nif __name__ == '__main__':\n    main()\n",
    "machines/sono/machine.yml": "packages: [a]\nlaunch_cmd: x\nnoeuds_attendus: [/didier/sono]\nsentinelle_build: s\n",
    ".github/workflows/tests.yml": "jobs:\n  unit:\n    strategy:\n      matrix:\n        include:\n"
                                   "          - suite: sono_core\n            dir: packages/sono_core\n",
    "machines/sim/docker-compose.yml": "services:\n  monde:\n    image: m\n  sono:\n    image: s\n",
    "machines/sim/fumee/plan.toml": '[[epreuve]]\nid = "machines"\n\n[[epreuve]]\nid = "sono"\n',
}


def _poser(racine, fichiers):
    for chemin, texte in fichiers.items():
        f = racine / chemin
        f.parent.mkdir(parents=True, exist_ok=True)
        if texte is not None:
            f.write_text(texte, encoding="utf-8")


def _verifier(tmp_path, **changes):
    fichiers = dict(FICHIERS_COMPLETS, **{k.replace("__", "/"): v for k, v in changes.items()})
    _poser(tmp_path, {k: v for k, v in fichiers.items() if v is not None})
    return verifier_appareil(tmp_path / "packages" / "sono_core")


def test_appareil_complet_aucun_geste(tmp_path):
    assert _verifier(tmp_path) == []


CAS = {
    # 1. un titre manque
    "titre": ({"packages/sono_core/README.md": README_COMPLET.replace("## Pilotes", "## Pilote")},
              ["G7 README-contrat : titres « ## » attendus dans l'ordre Rôle · Machine · Topics · "
               "Comportement · Pilotes · Simuler · Tester · Déployer (Pilotes)"]),
    # 2. un trou du squelette subsiste
    "trou": ({"machines/sono/README.md": "APPAREIL : une ligne\n"},
             ["trou APPAREIL à remplir : machines/sono/README.md"]),
    # 3. un topic absolu, un topic absent de theatre_contrats.topics
    "topic": ({"packages/sono_core/sono_core/contrat.py": 'TOPICS = ("/sono/etat", "sono/klaxon")\n'},
              ["G2 contrat : topic '/sono/etat' absolu ou absent de theatre_contrats.topics",
               "G2 contrat : topic 'sono/klaxon' absolu ou absent de theatre_contrats.topics"]),
    # 5. machine.yml sans deux clés
    "machine": ({"machines/sono/machine.yml": "packages: [a]\nlaunch_cmd: x\n"},
                ["G8 machine : machine.yml sans noeuds_attendus, sentinelle_build"]),
    # 6. pas dans la matrice de la CI
    "ci": ({".github/workflows/tests.yml": "jobs:\n  unit:\n    strategy:\n      matrix:\n        include:\n"
                                          "          - suite: autre\n            dir: packages/autre\n"},
           ["G8 CI : ligne « suite: sono_core » absente de .github/workflows/tests.yml"]),
    # 7. pas de service dans le compose de la sim
    "compose": ({"machines/sim/docker-compose.yml": "services:\n  monde:\n    image: m\n"},
                ["G9 sim : service « sono » absent de machines/sim/docker-compose.yml"]),
    # 8. aucune épreuve
    "plan": ({"machines/sim/fumee/plan.toml": '[[epreuve]]\nid = "machines"\n'},
             ["G10 fumée : aucune épreuve id = « sono » dans machines/sim/fumee/plan.toml"]),
    # 9. une règle dans le nœud
    "noeud": ({"packages/sono_core/sono_core/noeud.py":
               "def main(x):\n    return 1 if x > 2 else 0\n\n\nif __name__ == '__main__':\n    main(0)\n"},
              ["G6 nœud : règle dans noeud.py (`if x > 2`) — elle va dans logique.py"]),
}


@pytest.mark.parametrize("cas", sorted(CAS))
def test_chaque_cause_rougit(tmp_path, cas):
    changes, attendu = CAS[cas]
    _poser(tmp_path, dict(FICHIERS_COMPLETS, **changes))
    assert verifier_appareil(tmp_path / "packages" / "sono_core") == attendu


def test_cause_4_hors_registre(tmp_path):
    """Même appareil complet, nommé « essai » : seul le registre manque."""
    fichiers = {k.replace("sono_core", "essai_core").replace("machines/sono/", "machines/essai/"): v
                for k, v in FICHIERS_COMPLETS.items()}
    fichiers[".github/workflows/tests.yml"] = fichiers[".github/workflows/tests.yml"].replace("sono", "essai")
    fichiers["machines/sim/docker-compose.yml"] = "services:\n  essai:\n    image: s\n"
    fichiers["machines/sim/fumee/plan.toml"] = '[[epreuve]]\nid = "essai"\n'
    _poser(tmp_path, fichiers)
    assert verifier_appareil(tmp_path / "packages" / "essai_core") == [
        "G2 contrat : « essai » absent de theatre_contrats.appareils.REGISTRE"]


def test_fichiers_absents_sont_des_gestes(tmp_path):
    (tmp_path / "packages" / "sono_core").mkdir(parents=True)
    assert verifier_appareil(tmp_path / "packages" / "sono_core")[:1] == ["G7 README-contrat : README.md absent"]
    assert verifier_appareil(tmp_path / "packages" / "sono_core")[-1] == "G6 nœud : noeud.py absent"


def test_enregistreur():
    e = Enregistreur(sante="absent")
    assert e.jouer("a.wav") is None and e.sante() == "absent"
    assert e.journal == [("jouer", ("a.wav",)), ("sante", ())]


# --- le squelette généré (appareil jetable « essai ») ---------------------------------------------
OUTIL = pathlib.Path(PKG) / "tools" / "nouvel_appareil.py"

GESTES_ESSAI = [
    "trou APPAREIL à remplir : packages/essai_core/README.md",
    "trou APPAREIL à remplir : packages/essai_core/config/essai.yaml",
    "trou APPAREIL à remplir : packages/essai_core/essai_core/contrat.py",
    "trou APPAREIL à remplir : packages/essai_core/essai_core/logique.py",
    "trou APPAREIL à remplir : packages/essai_core/essai_core/noeud.py",
    "trou APPAREIL à remplir : packages/essai_core/essai_core/pilotes/base.py",
    "trou APPAREIL à remplir : packages/essai_core/essai_core/pilotes/materiel.py",
    "trou APPAREIL à remplir : packages/essai_core/essai_core/pilotes/sim.py",
    "trou APPAREIL à remplir : packages/essai_core/essai_core/reglages.py",
    "trou APPAREIL à remplir : packages/essai_core/package.xml",
    "trou APPAREIL à remplir : packages/essai_core/setup.py",
    "trou APPAREIL à remplir : machines/essai/README.md",
    "trou APPAREIL à remplir : machines/essai/docker/Dockerfile",
    "trou APPAREIL à remplir : machines/essai/docker/arm/docker-compose-arm.yml",
    "trou APPAREIL à remplir : machines/essai/essai.yaml",
    "trou APPAREIL à remplir : machines/essai/machine.yml",
    "trou APPAREIL à remplir : machines/essai/packages-docker.txt",
    "trou APPAREIL à remplir : machines/essai/requirements.txt",
    "trou APPAREIL à remplir : machines/essai/rpi/asound.conf",
    "trou APPAREIL à remplir : machines/essai/rpi/project_bash",
    "trou APPAREIL à remplir : machines/essai/scripts/launch-ros-in-docker.sh",
    "trou APPAREIL à remplir : machines/sim/essai/entree.sh",
    "G2 contrat : topic 'essai/etat' absolu ou absent de theatre_contrats.topics",
    "G2 contrat : « essai » absent de theatre_contrats.appareils.REGISTRE",
    "G8 CI : ligne « suite: essai_core » absente de .github/workflows/tests.yml",
    "G9 sim : service « essai » absent de machines/sim/docker-compose.yml",
    "G10 fumée : aucune épreuve id = « essai » dans machines/sim/fumee/plan.toml",
]


@pytest.fixture
def racine_essai(tmp_path):
    """Une racine jetable : les deux packages communs en liens, rien d'autre (aucun fichier
    partagé : registre, CI, compose et plan sont ceux qui MANQUENT)."""
    (tmp_path / "packages").mkdir()
    for p in ("theatre_contrats", "theatre_gabarit"):
        os.symlink(MONO / "packages" / p, tmp_path / "packages" / p)
    sortie = subprocess.run([sys.executable, str(OUTIL), "essai", "--racine", str(tmp_path)],
                            capture_output=True, text=True, timeout=60)
    assert sortie.returncode == 0, sortie.stderr
    return tmp_path


def test_generateur_n_ecrit_que_les_trois_dossiers_de_l_appareil(racine_essai):
    ecrits = sorted(str(p.relative_to(racine_essai)) for p in racine_essai.rglob("*")
                    if p.is_file() and "theatre_" not in str(p.relative_to(racine_essai)))
    assert {e.split("/")[0] + "/" + e.split("/")[1] for e in ecrits} == {"packages/essai_core", "machines/essai",
                                                                         "machines/sim"}
    assert len(ecrits) == 33
    assert not any("appareil_gabarit" in (racine_essai / e).read_text(encoding="utf-8") for e in ecrits)


def test_generateur_refuse_d_ecraser(racine_essai):
    sortie = subprocess.run([sys.executable, str(OUTIL), "essai", "--racine", str(racine_essai)],
                            capture_output=True, text=True, timeout=60)
    assert sortie.returncode == 2
    assert "existe déjà : packages/essai_core, machines/essai, machines/sim/essai" in sortie.stderr
    for nom in ("Essai", "x", "essai_core", "1a"):
        assert subprocess.run([sys.executable, str(OUTIL), nom, "--racine", str(racine_essai)],
                              capture_output=True, timeout=60).returncode == 2


def test_squelette_genere_les_gestes_graves(racine_essai):
    assert verifier_appareil(racine_essai / "packages" / "essai_core") == GESTES_ESSAI


def test_squelette_genere_tests_rouges_pour_les_bonnes_raisons(racine_essai):
    """Les tests de l'appareil jetable : 5 rouges, chacun avec le geste à faire."""
    sortie = subprocess.run([sys.executable, "-m", "pytest", "-q", "-o", "addopts=", "-p", "no:cacheprovider",
                             "-rf"], cwd=racine_essai / "packages" / "essai_core",
                            capture_output=True, text=True, timeout=120)
    echecs = sorted(l.split(" - ")[0] for l in sortie.stdout.splitlines() if l.startswith("FAILED"))
    assert echecs == ["FAILED test/test_contrat_noeud.py::test_a_ecrire", "FAILED test/test_gabarit.py::test_gabarit",
                      "FAILED test/test_logique.py::test_a_ecrire", "FAILED test/test_pilotes.py::test_a_ecrire",
                      "FAILED test/test_reglages.py::test_a_ecrire"]
    for g in ("G3 à faire", "G4 à faire", "G5 à faire", "G6 à faire", "G10 fumée : aucune épreuve"):
        assert g in sortie.stdout
