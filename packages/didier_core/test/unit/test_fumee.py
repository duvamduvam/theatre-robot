"""Lot F — fumée nocturne : décision « due ? », pages, et garde-fous de fumee.sh.

Tout est hôte (ni ROS, ni Docker, ni Gazebo) : le vrai fumee.sh est lancé avec un
faux `docker` en tête du PATH, ce qui prouve ses sorties « rien à faire » et
« reporté » sans jamais toucher à une sim. Les valeurs attendues sont GRAVÉES
dans les tests (jamais recalculées avec la fonction testée). La preuve en sim est
la fumée elle-même (docs/fumee/).
"""
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

# L1e-4c (11/11) : la fumée et les scripts de la sim vivent dans machines/sim/ du mono-dépôt.
SCRIPTS = pathlib.Path(__file__).resolve().parents[4] / "machines" / "sim"
FUMEE_SH = SCRIPTS / "fumee.sh"
FUMEE_PY = SCRIPTS / "fumee_page.py"

_spec = importlib.util.spec_from_file_location("fumee_page", FUMEE_PY)
fp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fp)

CET = timezone(timedelta(hours=1))
MAINTENANT = datetime(2026, 11, 10, 12, 0, tzinfo=CET)


def vert(sha="abc1234", jours_avant=2.0, essai=False):
    fin = MAINTENANT - timedelta(days=jours_avant)
    return {"id": "x", "sha": sha, "sha_complet": sha + "0" * 33, "verdict": "vert",
            "fin": fin.isoformat(), "essai": essai}


# --- decider : les cinq situations, valeurs gravées ----------------------------

def test_aucune_fumee_verte_est_due():
    due, raison, depuis = fp.decider(None, None, None, MAINTENANT)
    assert due is True
    assert raison == "aucune fumée verte connue"
    assert depuis == MAINTENANT


def test_main_inchangee_et_recente_n_est_pas_due():
    due, raison, depuis = fp.decider(vert(jours_avant=2), 0, None, MAINTENANT)
    assert (due, depuis) == (False, None)
    assert raison == "dernière fumée verte abc1234 = code de main, moins de 7 jours"


def test_un_commit_apres_la_verte_la_rend_due_depuis_ce_commit():
    commit = MAINTENANT - timedelta(hours=5)
    due, raison, depuis = fp.decider(vert(jours_avant=1), 3, commit, MAINTENANT)
    assert due is True
    assert raison == "3 commit(s) de code dans main depuis la dernière fumée verte (abc1234)"
    assert depuis == commit


def test_sept_jours_sans_fumee_la_rendent_due_meme_sans_commit():
    due, raison, depuis = fp.decider(vert(jours_avant=8), 0, None, MAINTENANT)
    assert due is True
    assert raison == "7 jours sans fumée verte (dernière : 2026-11-02)"
    assert depuis == datetime(2026, 11, 9, 12, 0, tzinfo=CET)


def test_la_frontiere_des_sept_jours():
    assert fp.decider(vert(jours_avant=7), 0, None, MAINTENANT)[0] is True      # 7 j pile : due
    assert fp.decider(vert(jours_avant=6.9), 0, None, MAINTENANT)[0] is False   # 6,9 j : pas due


def test_sha_inconnu_de_main_est_du_par_prudence():
    due, raison, _ = fp.decider(vert(), None, None, MAINTENANT)
    assert due is True
    assert raison == "le sha de la dernière fumée verte (abc1234) est inconnu de main"


def test_rappel_au_dela_de_deux_jours_seulement():
    assert fp.rappel_necessaire(MAINTENANT - timedelta(days=3), MAINTENANT) is True
    assert fp.rappel_necessaire(MAINTENANT - timedelta(days=1), MAINTENANT) is False
    assert fp.rappel_necessaire(MAINTENANT - timedelta(days=2), MAINTENANT) is False   # strictement plus de 2 j
    assert fp.rappel_necessaire(None, MAINTENANT) is False


def test_dernier_vert_ignore_les_rouges_et_les_essais():
    rouge = dict(vert("rouge11"), verdict="rouge", fin="2026-11-09T10:00:00+01:00")
    essai = dict(vert("essai22", essai=True), fin="2026-11-09T11:00:00+01:00")
    ancien = dict(vert("ancien3"), fin="2026-11-01T10:00:00+01:00")
    assert fp.dernier_vert([ancien, rouge, essai])["sha"] == "ancien3"
    assert fp.dernier_vert([rouge, essai]) is None
    assert fp.dernier_vert([]) is None


# --- compteurs et verdict ---------------------------------------------------------

@pytest.mark.parametrize("ok,attendu,ko,statut", [
    (21, 21, 0, "vert"), (20, 21, 1, "rouge"), (21, 21, 1, "rouge"), (18, 21, 3, "rouge"),
    (14, 14, 0, "vert"), (5, 5, 0, "vert"), (0, 4, 0, "rouge"), (22, 21, 0, "rouge"),
])
def test_un_compteur_n_est_vert_qu_a_la_valeur_gravee(ok, attendu, ko, statut):
    assert fp.statut_compteur(ok, attendu, ko) == statut


def test_ordre_canonique_des_epreuves():
    assert [i for i, _ in fp.EPREUVES] == [
        "image", "demarrage", "rtf", "namespace", "catalogue", "parle", "chantiers", "a1"]


def test_verdict_global_premier_rouge_bloque():
    tout_vert = [{"id": i, "statut": "vert"} for i, _ in fp.EPREUVES]
    assert fp.verdict_global(tout_vert) == ("vert", None)
    coupee = tout_vert[:2] + [{"id": "rtf", "statut": "rouge"}]
    assert fp.verdict_global(coupee) == ("rouge", "rtf")
    assert fp.verdict_global(tout_vert[:5]) == ("rouge", None)     # interrompue : jamais « vert »


def test_completer_marque_non_lancees_les_suivantes():
    complet = fp.completer_epreuves([{"id": "image", "statut": "vert"}, {"id": "rtf", "statut": "rouge"}])
    assert [(e["id"], e["statut"]) for e in complet] == [
        ("image", "vert"), ("demarrage", "non_lance"), ("rtf", "rouge"), ("namespace", "non_lance"),
        ("catalogue", "non_lance"), ("parle", "non_lance"), ("chantiers", "non_lance"), ("a1", "non_lance")]


# --- git : les commits de docs/fumee ne rendent pas une fumée due ------------------

def _git(depot, *args):
    return subprocess.run(["git", "-C", str(depot), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def depot(tmp_path):
    d = tmp_path / "depot"
    d.mkdir()
    _git(d, "init", "-q", "-b", "main")
    _git(d, "config", "user.email", "t@t")
    _git(d, "config", "user.name", "t")
    _git(d, "config", "commit.gpgsign", "false")
    return d


def _commit(depot, chemin, message):
    f = depot / chemin
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(message, encoding="utf-8")
    _git(depot, "add", "--", chemin)
    _git(depot, "commit", "-q", "-m", message)
    return _git(depot, "rev-parse", "HEAD")


def test_les_commits_de_docs_fumee_ne_comptent_pas(depot):
    sha_teste = _commit(depot, "packages/code.txt", "code 1")
    _commit(depot, "docs/fumee/2026-11-07.html", "page de la fumée")      # le commit de la fumée elle-même
    n, premier = fp.commits_apres_sha(str(depot), sha_teste)
    assert (n, premier) == (0, None)
    _commit(depot, "packages/code.txt", "code 2")
    _commit(depot, "docs/fumee/index.html", "index")
    _commit(depot, "deploy/autre.txt", "autre")
    n, premier = fp.commits_apres_sha(str(depot), sha_teste)
    assert n == 2
    assert isinstance(premier, datetime)


def test_sha_absent_du_depot_donne_none(depot):
    _commit(depot, "packages/code.txt", "code 1")
    assert fp.commits_apres_sha(str(depot), "0123456789abcdef0123456789abcdef01234567") == (None, None)


# --- Règle du 10/11 : chemins TESTÉS seulement, et un rouge n'est rejoué qu'une fois ------

def test_liste_des_chemins_testes_gravee():
    # L1e-4c : les conf/ legacy du robot et de la vision sont devenues machines/ (déjà listé).
    assert fp.CHEMINS_TESTES == (
        "packages/", "data/", "deploy/", "machines/",
        "legacy/dadou_robot_ros/json/", "legacy/dadou_robot_ros/medias/", "legacy/dadou_robot_ros/db/")
    assert fp.ROUGES_MAX_PAR_CODE == 2


@pytest.mark.parametrize("chemin,compte", [
    ("packages/didier_jeu/x.py", 1), ("data/x.json", 1), ("deploy/hosts", 1), ("machines/robot.yml", 1),
    ("machines/sim/fumee.sh", 1), ("machines/vision/v.yaml", 1), ("legacy/dadou_robot_ros/json/a.json", 1),
    ("legacy/dadou_robot_ros/medias/a.png", 1), ("legacy/dadou_robot_ros/db/a.db", 1),
    # L1e-4c : les anciennes conf/ de legacy ne sont plus des chemins testés.
    ("legacy/dadou_robot_ros/conf/scripts/fumee.sh", 0), ("legacy/dadou_vision_ros/conf/v.yaml", 0),
    # la doc, même dans legacy/, ne déclenche rien (vécu le 08/11 : 14 commits d'étude du torse)
    ("docs/etude-torse.md", 0), ("docs/chantiers.md", 0), ("README.md", 0),
    ("CLAUDE.md", 0), ("legacy/dadou_vision_ros/README.md", 0), ("docs/fumee/index.html", 0),
    ("packagesX/faux.py", 0),
])
def test_seul_un_commit_sur_un_chemin_teste_compte(depot, chemin, compte):
    sha_vert = _commit(depot, "packages/code.txt", "code 1")
    _commit(depot, chemin, "modif")
    n, premier = fp.commits_apres_sha(str(depot), sha_vert)
    assert n == compte
    assert (premier is None) == (compte == 0)


def test_sha_de_code_saute_les_commits_de_doc(depot):
    code = _commit(depot, "packages/code.txt", "code 1")
    _commit(depot, "docs/etude.md", "étude")
    doc2 = _commit(depot, "README.md", "readme")
    assert fp.sha_de_code(str(depot), doc2) == code
    assert fp.sha_de_code(str(depot), "main") == code
    autre = _commit(depot, "deploy/hosts", "hôtes")
    assert fp.sha_de_code(str(depot), "main") == autre


def test_sha_de_code_sans_aucun_commit_de_code_est_none(depot):
    _commit(depot, "docs/etude.md", "étude")
    assert fp.sha_de_code(str(depot), "main") is None


def test_un_rouge_est_due_pour_une_confirmation():
    commit = MAINTENANT - timedelta(hours=5)
    due, raison, depuis = fp.decider(vert(jours_avant=1), 3, commit, MAINTENANT,
                                     rouges_meme_code=1, sha_code="def5678" + "0" * 33)
    assert due is True
    assert raison == ("relance de confirmation du rouge sur le code def5678 ; "
                      "3 commit(s) de code dans main depuis la dernière fumée verte (abc1234)")
    assert depuis == commit


@pytest.mark.parametrize("rouges", [2, 3, 9])
def test_deux_rouges_sur_le_meme_code_bloquent(rouges):
    commit = MAINTENANT - timedelta(hours=5)
    due, raison, depuis = fp.decider(vert(jours_avant=1), 3, commit, MAINTENANT,
                                     rouges_meme_code=rouges, sha_code="def5678" + "0" * 33)
    assert due is False
    assert raison == ("bloquée : {} fumées rouges sur le code def5678, plus de relance tant qu'aucun "
                      "commit de code n'arrive (3 commit(s) de code dans main depuis la dernière "
                      "fumée verte (abc1234))").format(rouges)
    assert depuis == commit          # gardé : c'est lui qui fait partir le rappel « > 2 jours »


def test_le_blocage_l_emporte_aussi_sur_les_sept_jours_et_sans_verte():
    due, raison, depuis = fp.decider(vert(jours_avant=10), 0, None, MAINTENANT,
                                     rouges_meme_code=2, sha_code="def5678")
    assert (due, depuis) == (False, datetime(2026, 11, 7, 12, 0, tzinfo=CET))
    assert raison.startswith("bloquée : 2 fumées rouges sur le code def5678")
    due, raison, depuis = fp.decider(None, None, None, MAINTENANT, rouges_meme_code=2, sha_code="def5678")
    assert (due, depuis) == (False, MAINTENANT)
    due, _, _ = fp.decider(None, None, None, MAINTENANT, rouges_meme_code=1, sha_code="def5678")
    assert due is True


def test_rien_de_du_reste_pas_du_meme_avec_des_rouges():
    """Des rouges sans rien de dû (ex. vieux rouges d'un code devenu vert) : pas due, pas bloquée."""
    due, _, depuis = fp.decider(vert(jours_avant=1), 0, None, MAINTENANT, rouges_meme_code=5, sha_code="x")
    assert (due, depuis) == (False, None)


def _res(sha_complet, verdict, fin, essai=False):
    return {"sha": sha_complet[:7], "sha_complet": sha_complet, "verdict": verdict, "fin": fin, "essai": essai}


def test_rouges_sur_code_compte_par_sha_de_code(depot):
    """Un commit de doc après un rouge ne change pas le code : le rouge suivant est le même code."""
    a = _commit(depot, "packages/code.txt", "code A")
    b = _commit(depot, "packages/code.txt", "code B")
    c_doc = _commit(depot, "docs/etude.md", "doc après B")
    verte = _res(a, "vert", "2026-11-08T21:00:00+01:00")
    resultats = [_res(a, "rouge", "2026-11-08T20:00:00+01:00"),            # AVANT la verte : ignoré
                 verte,
                 _res(b, "rouge", "2026-11-08T23:00:00+01:00"),
                 _res(b, "rouge", "2026-11-08T23:30:00+01:00", essai=True),  # essai provoqué : ignoré
                 _res(c_doc, "rouge", "2026-11-09T00:00:00+01:00"),
                 _res("f" * 40, "rouge", "2026-11-09T01:00:00+01:00")]      # sha inconnu : ignoré
    assert fp.rouges_sur_code(str(depot), resultats, verte, b) == 2
    assert fp.rouges_sur_code(str(depot), resultats, verte, a) == 0
    assert fp.rouges_sur_code(str(depot), resultats, None, a) == 1         # sans verte : tout compte
    assert fp.rouges_sur_code(str(depot), resultats, verte, None) == 0


def _ecrire_resultat(depot, ident, res):
    d = depot / "docs" / "fumee" / "journaux" / ident
    d.mkdir(parents=True, exist_ok=True)
    (d / "resultat.json").write_text(json.dumps(res), encoding="utf-8")


def _due(depot, maintenant):
    return subprocess.run(["python3", str(FUMEE_PY), "due", "--sortie", str(depot / "docs" / "fumee"),
                           "--depot", str(depot), "--maintenant", maintenant.isoformat()],
                          capture_output=True, text=True)


def test_cli_due_rouge_puis_confirmation_puis_blocage_puis_nouveau_code(depot):
    """Le scénario du 08/11 rejoué : un rouge, UNE confirmation, puis silence jusqu'au code suivant."""
    ici = datetime.now().astimezone()          # les commits portent l'heure réelle
    a = _commit(depot, "packages/code.txt", "code A")
    _ecrire_resultat(depot, "2026-11-09-2100", _res(a, "vert", (ici - timedelta(hours=3)).isoformat()))
    b = _commit(depot, "packages/code.txt", "code B")
    p = _due(depot, ici)
    assert p.returncode == 0 and p.stdout.startswith("due\t1 commit(s) de code dans main")
    _ecrire_resultat(depot, "2026-11-09-2300", _res(b, "rouge", (ici - timedelta(hours=2)).isoformat()))
    p = _due(depot, ici)
    assert p.returncode == 0
    assert p.stdout.startswith("due\trelance de confirmation du rouge sur le code {} ; ".format(b[:7]))
    _commit(depot, "docs/etude.md", "doc")              # la doc ne débloque rien
    _ecrire_resultat(depot, "2026-11-09-2330", _res(b, "rouge", (ici - timedelta(hours=1)).isoformat()))
    p = _due(depot, ici)
    assert p.returncode == 1
    etat, raison, depuis, rappel = p.stdout.rstrip("\n").split("\t")
    assert etat == "bloquee" and raison.startswith("bloquée : 2 fumées rouges sur le code " + b[:7])
    assert depuis != "" and rappel == "non"
    assert _due(depot, ici + timedelta(days=3)).stdout.rstrip("\n").split("\t")[3] == "oui"
    _commit(depot, "packages/code.txt", "code C")       # nouveau code : de nouveau due
    p = _due(depot, ici)
    assert p.returncode == 0 and p.stdout.startswith("due\t2 commit(s) de code dans main")


def test_cli_doc_seule_apres_la_verte_n_est_pas_due(depot):
    ici = datetime.now().astimezone()
    a = _commit(depot, "packages/code.txt", "code A")
    _ecrire_resultat(depot, "2026-11-09-2100", _res(a, "vert", (ici - timedelta(hours=3)).isoformat()))
    for i in range(14):
        _commit(depot, "docs/etude-torse.md", "étude {}".format(i))
    p = _due(depot, ici)
    assert p.returncode == 1
    assert p.stdout == "pas_due\tdernière fumée verte {} = code de main, moins de 7 jours\t\tnon\n".format(a[:7])


# --- pages -------------------------------------------------------------------------

def resultat(epreuves, verdict="vert", **plus):
    base = {"version": 1, "id": "2026-11-07-2130", "sha": "9c937d0", "sha_complet": "9c937d0" + "0" * 33,
            "sale": False, "branche": "main", "mode": "force", "raison": "lancée à la main (force)",
            "debut": "2026-11-07T21:30:00+01:00", "fin": "2026-11-07T22:10:00+01:00", "duree_s": 2400,
            "rtf": 0.97, "rtf_min": 0.8, "charge_1min": 1.7, "nb_coeurs": 32, "essai": False,
            "image_reconstruite": False, "notes": [], "epreuves": epreuves, "verdict": verdict,
            "bloquant": None, "page": "2026-11-07.html"}
    base.update(plus)
    return base


def test_page_verte_porte_sha_rtf_et_compteurs():
    tout = [{"id": "image", "statut": "vert", "detail": "inchangée"},
            {"id": "demarrage", "statut": "vert"},
            {"id": "rtf", "statut": "vert", "obtenu": "0.97"},
            {"id": "namespace", "statut": "vert", "ok": 5, "attendu": 5, "ko": 0, "journal": "namespace.log"},
            {"id": "catalogue", "statut": "vert", "ok": 4, "attendu": 4, "ko": 0},
            {"id": "parle", "statut": "vert", "ok": 3, "attendu": 3, "ko": 0},
            {"id": "chantiers", "statut": "vert", "ok": 21, "attendu": 21, "ko": 0, "duree_s": 585},
            {"id": "a1", "statut": "vert", "ok": 14, "attendu": 14, "ko": 0}]
    page = fp.rendre_page(resultat(tout))
    assert "<code>9c937d0</code>" in page
    assert "07/11/2026 à 21:30" in page
    assert "Durée 40 min 00 s" in page
    assert "<strong>0.97</strong> (seuil 0.8)" in page
    assert "21 / 21 OK, 0 KO" in page and "14 / 14 OK, 0 KO" in page and "5 / 5 OK, 0 KO" in page
    assert "Toutes les épreuves sont vertes, aux valeurs gravées." in page
    assert 'href="journaux/2026-11-07-2130/namespace.log"' in page
    assert "9 min 45 s" in page
    assert "non lancée" not in page


def test_page_rouge_dit_ou_et_ce_qui_n_a_pas_ete_lance():
    epreuves = [{"id": "image", "statut": "vert"}, {"id": "demarrage", "statut": "vert"},
                {"id": "rtf", "statut": "rouge", "obtenu": "0.49", "detail": "RTF 0.49 < 0.8"}]
    page = fp.rendre_page(resultat(epreuves, verdict="rouge", bloquant="rtf", rtf=0.49))
    assert "ROUGE à l&#x27;épreuve « Sonde du facteur temps réel (20 s) » : les suivantes n&#x27;ont pas été lancées." in page
    assert page.count("non lancée") == 5
    assert "RTF 0.49 &lt; 0.8" in page                      # échappé


def test_page_n_injecte_pas_de_html_et_signale_essai_et_arbre_sale():
    epreuves = [{"id": "rtf", "statut": "rouge", "detail": "<script>alert(1)</script>"}]
    page = fp.rendre_page(resultat(epreuves, verdict="rouge", essai=True, sale=True, sha="9c937d0-dirty",
                                   notes=["note <b>grasse</b>"]))
    assert "<script>" not in page and "<b>grasse</b>" not in page
    assert "essai provoqué" in page
    assert "arbre modifié au départ" in page
    assert "<code>9c937d0-dirty</code>" in page


def test_finaliser_ecrit_resultat_page_et_sommaire(tmp_path):
    sortie, jsonl = tmp_path / "docs-fumee", tmp_path / "epreuves.jsonl"
    for args in (["image", "--statut", "vert"], ["demarrage", "--statut", "vert"],
                 ["rtf", "--statut", "rouge", "--obtenu", "0.49", "--duree", "22"],
                 ["namespace", "--ok", "5", "--attendu", "5", "--ko", "0", "--duree", "60", "--journal", "namespace.log"]):
        assert fp.main(["epreuve", "--jsonl", str(jsonl), "--id", *args]) == 0

    def finaliser(id_fumee, fin):
        return fp.main(["finaliser", "--jsonl", str(jsonl), "--sortie", str(sortie), "--id", id_fumee,
                        "--meta", "sha=9c937d0", "--meta", "sha_complet=" + "9" * 40, "--meta", "sale=0",
                        "--meta", "branche=main", "--meta", "mode=force", "--meta", "raison=essai",
                        "--meta", "debut=2026-11-07T21:30:00+01:00", "--meta", "fin=" + fin,
                        "--meta", "duree_s=120", "--meta", "rtf=0.49", "--meta", "rtf_min=0.8",
                        "--meta", "charge_1min=1.7", "--meta", "nb_coeurs=32", "--meta", "essai=0",
                        "--meta", "image_reconstruite=0", "--note", "une note"])

    assert finaliser("2026-11-07-2130", "2026-11-07T21:32:00+01:00") == 0
    res = json.loads((sortie / "journaux" / "2026-11-07-2130" / "resultat.json").read_text(encoding="utf-8"))
    assert res["verdict"] == "rouge" and res["bloquant"] == "rtf"
    assert res["page"] == "2026-11-07.html" and res["rtf"] == 0.49 and res["duree_s"] == 120
    assert res["sale"] is False and res["notes"] == ["une note"]
    assert (sortie / "2026-11-07.html").exists()
    # Une 2e fumée le même jour ne doit pas écraser la page de la première.
    assert finaliser("2026-11-07-2300", "2026-11-07T23:02:00+01:00") == 0
    res2 = json.loads((sortie / "journaux" / "2026-11-07-2300" / "resultat.json").read_text(encoding="utf-8"))
    assert res2["page"] == "2026-11-07-2.html"
    index = (sortie / "index.html").read_text(encoding="utf-8")
    assert index.index("2026-11-07-2.html") < index.index('href="2026-11-07.html"')     # la plus récente en tête


# --- fumee.sh lui-même : contrat gravé et garde-fous ----------------------------------

def _lire_sh():
    return FUMEE_SH.read_text(encoding="utf-8")


def test_valeurs_attendues_gravees_en_tete_du_script():
    src = _lire_sh()
    gravees = dict(re.findall(r"^(ATTENDU_[A-Z0-9]+)=(\d+)", src, re.M))
    assert gravees == {"ATTENDU_NAMESPACE": "5", "ATTENDU_CATALOGUE": "4", "ATTENDU_PARLE": "3",
                       "ATTENDU_CHANTIERS": "21", "ATTENDU_A1": "14"}
    assert re.search(r"^RTF_MIN_DEFAUT=0\.8$", src, re.M)


def test_les_compteurs_gravees_sont_ceux_des_scripts_de_verification():
    """Le chiffre gravé vaut le nombre de verdict() réellement présents dans le script lancé."""
    ns = (SCRIPTS / "validate-namespace.sh").read_text(encoding="utf-8")
    cat = (SCRIPTS / "validate-catalogue.sh").read_text(encoding="utf-8")
    assert len(re.findall(r'verdict "\$\(', ns)) == 5
    assert len(re.findall(r'verdict "\$\(', cat)) == 4


def test_garde_fous_presents_dans_le_script():
    src = _lire_sh()
    assert "set -euo pipefail" in src
    assert "ROS_DOMAIN_ID=43" in src and "ROS_DOMAIN_ID=42" not in src
    assert "trap terminer EXIT" in src
    assert "flock" in src
    assert "FUMEE_DRY_POWEROFF" in src
    assert "git -C \"$DEPOT\" commit" in src and "-- docs/fumee" in src
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))   # hors commentaires
    assert not re.search(r"git [^\n]*\badd (-A|\.)", code)             # jamais add . ni add -A
    assert not re.search(r"git [^\n]*commit [^\n]*(-a\b|--all)", code)  # jamais commit -a
    assert "ros2 topic" not in src       # la CLI ros2 perd des messages : rclpy dans le conteneur


def test_syntaxe_bash():
    subprocess.run(["bash", "-n", str(FUMEE_SH)], check=True)


@pytest.fixture
def banc(tmp_path):
    """Un dépôt vert à jour + un faux docker qui journalise ses appels."""
    if shutil.which("git") is None:
        pytest.skip("git absent")
    depot = tmp_path / "depot"
    depot.mkdir()
    _git(depot, "init", "-q", "-b", "main")
    _git(depot, "config", "user.email", "t@t")
    _git(depot, "config", "user.name", "t")
    _git(depot, "config", "commit.gpgsign", "false")
    sha = _commit(depot, "packages/code.txt", "code 1")
    res = vert(sha[:7])
    res.update(sha_complet=sha, fin=datetime.now().astimezone().isoformat(), id="2026-11-07-2130")
    dossier = depot / "docs" / "fumee" / "journaux" / "2026-11-07-2130"
    dossier.mkdir(parents=True)
    (dossier / "resultat.json").write_text(json.dumps(res), encoding="utf-8")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    faux = bin_ / "docker"
    faux.write_text('#!/bin/bash\necho "$@" >>"$FAUX_DOCKER_APPELS"\n'
                    'if [ "$1" = ps ]; then printf "%s" "${FAUX_DOCKER_PS:-}"; fi\n'
                    'if [ "$1" = inspect ]; then echo running; fi\nexit 0\n', encoding="utf-8")
    faux.chmod(0o755)
    notif = bin_ / "notify-send"       # fausse notification : on lit ce qu'elle aurait affiché
    notif.write_text('#!/bin/bash\necho "$@" >>"$FAUX_NOTIFS"\n', encoding="utf-8")
    notif.chmod(0o755)
    env = dict(os.environ, PATH=str(bin_) + os.pathsep + os.environ["PATH"], FUMEE_DEPOT=str(depot),
               FUMEE_ETAT=str(tmp_path / "etat"), FAUX_DOCKER_APPELS=str(tmp_path / "appels.txt"),
               FAUX_NOTIFS=str(tmp_path / "notifs.txt"), FUMEE_DRY_POWEROFF="1")
    (tmp_path / "appels.txt").write_text("", encoding="utf-8")
    return depot, env, tmp_path


def _lancer(env, *args):
    return subprocess.run([str(FUMEE_SH), *args], env=env, capture_output=True, text=True, timeout=60)


def _journal(tmp):
    j = tmp / "etat" / "journal.log"
    return j.read_text(encoding="utf-8") if j.exists() else ""


def test_si_due_main_a_jour_ne_fait_rien_du_tout(banc):
    _, env, tmp = banc
    p = _lancer(env, "--si-due")
    assert p.returncode == 0 and p.stdout == ""
    assert _journal(tmp) == ""                                  # silence : pas de ligne toutes les 30 min
    assert (tmp / "appels.txt").read_text(encoding="utf-8") == ""      # docker jamais appelé


def test_si_due_apres_un_commit_mais_pc_charge_reporte_sans_lancer_la_sim(banc):
    depot, env, tmp = banc
    _commit(depot, "packages/code.txt", "code 2")
    # Charge max forcée à -1 : le PC est toujours « trop chargé ».
    p = subprocess.run([str(FUMEE_SH), "--si-due"], env=dict(env, FUMEE_CHARGE_MAX="-1"),
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0
    assert "reporté : charge trop haute" in _journal(tmp)
    appels = (tmp / "appels.txt").read_text(encoding="utf-8")
    assert "compose" not in appels and "rm" not in appels.split()      # aucune sim lancée ni retirée
    assert not (depot / "docs" / "fumee" / "journaux" / "2026-11-07-2130" / "x").exists()


def test_rappel_apres_deux_jours_de_report_une_fois_par_demi_journee(banc):
    """Due depuis > 2 jours et toujours reportée : notification + ligne RAPPEL, pas de harcèlement."""
    depot, env, tmp = banc
    f = next((depot / "docs" / "fumee" / "journaux").glob("*/resultat.json"))
    res = json.loads(f.read_text(encoding="utf-8"))
    res["fin"] = (datetime.now().astimezone() - timedelta(days=10)).isoformat()    # due depuis 3 jours
    f.write_text(json.dumps(res), encoding="utf-8")
    env = dict(env, FUMEE_CHARGE_MAX="-1")
    for _ in range(2):
        assert subprocess.run([str(FUMEE_SH), "--si-due"], env=env, capture_output=True, text=True,
                              timeout=60).returncode == 0
    assert _journal(tmp).count("RAPPEL : une fumée est due depuis") == 1
    assert _journal(tmp).count("reporté : charge trop haute") == 2
    notifs = (tmp / "notifs.txt").read_text(encoding="utf-8").splitlines()
    assert len(notifs) == 1 and notifs[0].startswith("Didier : fumée en retard")


def test_pas_de_rappel_tant_que_la_fumee_est_due_depuis_moins_de_deux_jours(banc):
    depot, env, tmp = banc
    _commit(depot, "packages/code.txt", "code 2")          # due depuis l'instant, pas depuis 2 jours
    p = subprocess.run([str(FUMEE_SH), "--si-due"], env=dict(env, FUMEE_CHARGE_MAX="-1"),
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0 and "RAPPEL" not in _journal(tmp)
    assert not (tmp / "notifs.txt").exists()


def _bloquer(depot, jours_vert):
    """Verte il y a `jours_vert` jours, puis un commit de code et DEUX rouges sur lui."""
    f = next((depot / "docs" / "fumee" / "journaux").glob("*/resultat.json"))
    res = json.loads(f.read_text(encoding="utf-8"))
    ici = datetime.now().astimezone()
    res["fin"] = (ici - timedelta(days=jours_vert)).isoformat()
    f.write_text(json.dumps(res), encoding="utf-8")
    b = _commit(depot, "packages/code.txt", "code 2")
    for i, h in enumerate((2, 1)):
        _ecrire_resultat(depot, "2026-11-09-23{}0".format(i), _res(b, "rouge", (ici - timedelta(hours=h)).isoformat()))


def test_si_due_bloquee_ne_lance_rien_et_rappelle_apres_deux_jours(banc):
    """Rouge confirmé sur ce code et due depuis > 2 jours (7 j sans verte) : rappel, jamais de sim."""
    depot, env, tmp = banc
    _bloquer(depot, jours_vert=10)
    for _ in range(2):
        p = _lancer(env, "--si-due")
        assert p.returncode == 0 and p.stdout == ""
    j = _journal(tmp)
    assert j.count("RAPPEL : une fumée est due depuis") == 1 and "et reste bloquée : 2 fumées rouges sur le code" in j
    assert "reporté" not in j and "début fumée" not in j
    assert (tmp / "appels.txt").read_text(encoding="utf-8") == ""          # docker jamais appelé
    notifs = (tmp / "notifs.txt").read_text(encoding="utf-8").splitlines()
    assert len(notifs) == 1 and notifs[0].startswith("Didier : fumée rouge confirmée")


def test_si_due_bloquee_recente_est_silencieuse(banc):
    depot, env, tmp = banc
    _bloquer(depot, jours_vert=1)
    p = _lancer(env, "--si-due")
    assert p.returncode == 0 and p.stdout == "" and _journal(tmp) == ""
    assert (tmp / "appels.txt").read_text(encoding="utf-8") == ""
    assert not (tmp / "notifs.txt").exists()


def test_si_due_ne_touche_jamais_a_la_sim_de_quelqu_un(banc):
    depot, env, tmp = banc
    _commit(depot, "packages/code.txt", "code 2")
    env = dict(env, FAUX_DOCKER_PS="dadou-sim-container\n")
    p = _lancer(env, "--si-due")
    assert p.returncode == 0
    assert "reporté : conteneur dadou-sim-container déjà présent" in _journal(tmp)
    appels = (tmp / "appels.txt").read_text(encoding="utf-8").splitlines()
    assert not [a for a in appels if a.startswith(("rm", "compose", "stop", "kill", "exec"))]


def test_et_dodo_refuse_et_n_eteint_pas_si_une_sim_existe(banc):
    _, env, tmp = banc
    env = dict(env, FAUX_DOCKER_PS="dadou-sim-container\n")
    p = _lancer(env, "--et-dodo")
    assert p.returncode == 2
    assert "REFUS" in p.stdout
    assert "poweroff" not in p.stdout.lower()


def test_argument_inconnu_refuse(banc):
    _, env, _ = banc
    p = _lancer(env, "--nimporte-quoi")
    assert p.returncode == 2 and "argument inconnu" in p.stderr


# --- Garde-fou d'extinction (incident du 07/11 : un --et-dodo lancé « à blanc » a éteint le PC) ----

def _corps_dodo():
    m = re.search(r"^dodo\(\) \{\n.*?^\}\n", _lire_sh(), re.M | re.S)
    assert m, "dodo() introuvable"
    return m.group(0)


def test_dodo_teste_les_deux_terminaux_avant_le_poweroff():
    corps = _corps_dodo()
    appels = [m.start() for m in re.finditer(r"^\s*systemctl poweroff$", corps, re.M)]   # l'appel réel, pas l'echo
    assert len(appels) == 1
    assert corps.index("[ ! -t 0 ] || [ ! -t 1 ]") < appels[0]


def _lancer_dodo(tmp_path, dry):
    """dodo() isolée, avec un FAUX systemctl en tête du PATH et stdin/stdout sans terminal."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    faux = bin_ / "systemctl"
    faux.write_text('#!/bin/bash\necho "$@" >>"$FAUX_SYSTEMCTL"\n', encoding="utf-8")
    faux.chmod(0o755)
    appels = tmp_path / "systemctl.txt"
    appels.write_text("", encoding="utf-8")
    script = 'journal() { :; }\ndit() { echo "$*"; }\n' + _corps_dodo() + "\ndodo\n"
    env = dict(os.environ, PATH=str(bin_) + os.pathsep + os.environ["PATH"], FAUX_SYSTEMCTL=str(appels),
               FUMEE_DODO_DELAI="0")
    if dry:
        env["FUMEE_DRY_POWEROFF"] = "1"
    else:
        env.pop("FUMEE_DRY_POWEROFF", None)
    p = subprocess.run(["bash", "-c", script], env=env, stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=30)
    return p, appels.read_text(encoding="utf-8")


def test_dodo_sans_terminal_n_appelle_jamais_systemctl(tmp_path):
    p, appels = _lancer_dodo(tmp_path, dry=False)
    assert p.returncode == 0
    assert "je n'éteins PAS" in p.stdout
    assert appels == ""


def test_dodo_a_blanc_n_appelle_pas_systemctl(tmp_path):
    p, appels = _lancer_dodo(tmp_path, dry=True)
    assert "DRY-RUN" in p.stdout and appels == ""
