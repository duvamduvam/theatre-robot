"""Cœurs réservés à la fumée (08/11) — conf/scripts/coeurs_reserves.py.

Valeurs GRAVÉES (jamais recalculées avec la fonction testée). La partie système est éprouvée
sur un VRAI processus jetable de l'utilisateur (sched_setaffinity, sans droits) avec un faux
`docker` en tête du PATH : aucun conteneur réel n'est touché.
"""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys

import pytest

# L1e-4c (11/11) : coeurs_reserves.py suit fumee.sh dans machines/sim/.
SCRIPTS = pathlib.Path(__file__).resolve().parents[4] / "machines" / "sim"
_spec = importlib.util.spec_from_file_location("coeurs_reserves", SCRIPTS / "coeurs_reserves.py")
cr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cr)

TOUS = set(range(32))


@pytest.mark.parametrize("texte,attendu", [
    ("8-15", {8, 9, 10, 11, 12, 13, 14, 15}),
    ("0-1,4,30-31", {0, 1, 4, 30, 31}),
    (" 3 , 5 ", {3, 5}),
    ("", set()),
])
def test_lire_liste(texte, attendu):
    assert cr.lire_liste(texte) == attendu


def test_lire_liste_refuse_une_plage_inversee():
    with pytest.raises(ValueError):
        cr.lire_liste("15-8")


@pytest.mark.parametrize("cpus,attendu", [
    (set(range(0, 8)) | set(range(16, 32)), "0-7,16-31"),
    ({0, 1, 4, 30, 31}, "0-1,4,30-31"),
    ({7}, "7"),
])
def test_ecrire_liste(cpus, attendu):
    assert cr.ecrire_liste(cpus) == attendu


def test_hors_reserve_cas_du_pc_de_david():
    reserves = set(range(8, 16))
    # Non contraint (tous les CPU) → tout sauf 8-15.
    assert cr.ecrire_liste(cr.hors_reserve(TOUS, reserves, TOUS)) == "0-7,16-31"
    # Cpuset Docker vide = non contraint.
    assert cr.ecrire_liste(cr.hors_reserve(set(), reserves, TOUS)) == "0-7,16-31"
    # Déjà épinglé ailleurs : inchangé.
    assert cr.hors_reserve({20, 21}, reserves, TOUS) == {20, 21}
    # Chevauchement : on retire seulement la part réservée.
    assert cr.hors_reserve({6, 7, 8, 9}, reserves, TOUS) == {6, 7}
    # Confiné aux réservés : on ne le prive pas de tout CPU, il reste où il est.
    assert cr.hors_reserve({10, 11}, reserves, TOUS) == {10, 11}


@pytest.fixture
def faux_docker(tmp_path, monkeypatch):
    """`docker` factice : aucun conteneur, journal des appels (prouve qu'on ne touche à rien)."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    appels = tmp_path / "docker.log"
    (bin_ / "docker").write_text(f'#!/bin/sh\necho "$@" >> {appels}\n')
    (bin_ / "docker").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_}:{os.environ['PATH']}")
    return appels


@pytest.mark.skipif(len(os.sched_getaffinity(0)) < 4, reason="il faut au moins 4 CPU")
def test_reserver_puis_liberer_un_vrai_processus(tmp_path):
    """Sur UN processus jetable seulement (pids=[...], aucun conteneur) : jamais la session de
    l'utilisateur — le 08/11, la version « tous mes processus » de ce test, mutée, a laissé
    toute la session de David privée de 2 CPU."""
    cpus = sorted(os.sched_getaffinity(0))
    reserves = {cpus[1], cpus[2]}
    etat = tmp_path / "coeurs.json"
    moi_avant = os.sched_getaffinity(0)
    jetable = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        avant = os.sched_getaffinity(jetable.pid)
        assert cr.deplacer(reserves, etat, "sim", pids=[jetable.pid], avec_conteneurs=False) == (1, 0)
        pendant = os.sched_getaffinity(jetable.pid)
        assert pendant.isdisjoint(reserves) and pendant == avant - reserves
        note = json.loads(etat.read_text())["processus"]
        assert list(note) == [str(jetable.pid)]           # lui, et personne d'autre
        assert cr.lire_liste(note[str(jetable.pid)]["cpus"]) == avant
        # Une 2e passe ne réécrit pas l'origine avec l'affinité déjà réduite.
        assert cr.deplacer(reserves, etat, "sim", pids=[jetable.pid], avec_conteneurs=False) == (0, 0)
        assert cr.lire_liste(json.loads(etat.read_text())["processus"][str(jetable.pid)]["cpus"]) == avant
        assert cr.liberer(etat, pids=[jetable.pid]) == (1, 0)
        assert os.sched_getaffinity(jetable.pid) == avant
        assert not etat.exists()
    finally:
        jetable.kill()
        # Garde-fou : le processus de test lui-même n'a jamais bougé.
        assert os.sched_getaffinity(0) == moi_avant


def test_est_heritier_valeurs_gravees():
    reserves = set(range(8, 16))
    assert cr.est_heritier(set(range(0, 8)) | set(range(16, 32)), reserves, TOUS) is True
    assert cr.est_heritier(TOUS, reserves, TOUS) is False            # jamais réduit
    assert cr.est_heritier({20, 21}, reserves, TOUS) is False        # épinglé par quelqu'un d'autre
    assert cr.est_heritier(set(range(0, 8)) | set(range(16, 32)), set(), TOUS) is False


@pytest.mark.skipif(len(os.sched_getaffinity(0)) < 4, reason="il faut au moins 4 CPU")
def test_liberer_elargit_un_processus_ne_pendant_la_reservation(tmp_path):
    """Né PENDANT la réservation (affinité héritée, absent de l'état) : rendu à tous les CPU."""
    tous = set(range(os.cpu_count()))
    if os.sched_getaffinity(0) != tous:
        pytest.skip("le processus de test doit voir tous les CPU")
    reserves = {1, 2}
    etat = tmp_path / "coeurs.json"
    etat.write_text(json.dumps({"reserves": "1-2", "processus": {}, "conteneurs": {}}))
    jetable = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        os.sched_setaffinity(jetable.pid, tous - reserves)   # ce qu'il aurait hérité
        assert cr.liberer(etat, pids=[jetable.pid]) == (1, 0)
        assert os.sched_getaffinity(jetable.pid) == tous
    finally:
        jetable.kill()


def test_liberer_sans_etat_ne_fait_rien(tmp_path):
    assert cr.liberer(tmp_path / "absent.json") == (0, 0)


def test_refuse_de_reserver_tous_les_cpu(tmp_path, faux_docker):
    n = os.cpu_count()
    assert cr.main(["reserver", "--coeurs", f"0-{n - 1}", "--etat", str(tmp_path / "e.json")]) == 2


def test_fumee_rend_les_coeurs_dans_terminer():
    """La libération doit être dans terminer() (trap EXIT) : une fumée rouge, reportée ou
    interrompue rend quand même le PC à David."""
    sh = (SCRIPTS / "fumee.sh").read_text(encoding="utf-8")
    corps = sh[sh.index("\nterminer() {"):sh.index("\ntrap terminer EXIT")]
    assert "liberer_coeurs" in corps
    assert 'COEURS="${FUMEE_COEURS-8-15}"' in sh
    # L'épinglage passe par demarrer_sim : chaque sim (chantiers puis A1) est épinglée.
    demarrer = sh[sh.index("\ndemarrer_sim() {"):sh.index("\nrechauffer_cli() {")]
    assert "epingler_sim" in demarrer
