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
import time
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
        "image", "demarrage", "rtf", "namespace", "catalogue", "parle", "edition", "machines", "chantiers", "a1",
        "objets", "conversation"]


def test_seule_la_conversation_est_facultative():
    assert fp.FACULTATIVES == frozenset({"conversation"})


def test_conversation_non_lancee_faute_de_cle_ne_rougit_pas():
    """16/11 : sans clé Anthropic, CONV est « non lancée » par la fumée (`facultative`) — vert ;
    la même non lancée SANS ce drapeau (fumée interrompue avant) reste rouge, et un rouge reste rouge."""
    avant = [{"id": i, "statut": "vert"} for i, _ in fp.EPREUVES if i != "conversation"]
    assert fp.verdict_global(avant + [{"id": "conversation", "statut": "non_lance", "facultative": True}]) \
        == ("vert", None)
    assert fp.verdict_global(avant) == ("rouge", None)
    assert fp.verdict_global(avant + [{"id": "conversation", "statut": "rouge", "facultative": True}]) \
        == ("rouge", "conversation")
    # Le drapeau ne vaut que pour une épreuve déclarée facultative.
    assert fp.verdict_global([e for e in avant if e["id"] != "a1"]
                             + [{"id": "a1", "statut": "non_lance", "facultative": True},
                                {"id": "conversation", "statut": "vert"}]) == ("rouge", None)


def test_epreuve_facultative_refusee_hors_liste(tmp_path):
    jsonl = tmp_path / "e.jsonl"
    assert fp.main(["epreuve", "--jsonl", str(jsonl), "--id", "conversation", "--statut", "non_lance",
                    "--facultative", "--detail", "non lancée (pas de clé)"]) == 0
    assert json.loads(jsonl.read_text()) == {"id": "conversation", "statut": "non_lance",
                                             "detail": "non lancée (pas de clé)", "facultative": True}
    with pytest.raises(SystemExit):
        fp.main(["epreuve", "--jsonl", str(jsonl), "--id", "a1", "--statut", "non_lance", "--facultative"])


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
        ("catalogue", "non_lance"), ("parle", "non_lance"), ("edition", "non_lance"), ("machines", "non_lance"),
        ("chantiers", "non_lance"), ("a1", "non_lance"), ("objets", "non_lance"), ("conversation", "non_lance")]


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
    """Une fumée passée = une ligne de docs/fumee/historique.jsonl (16/11 : plus de journaux/)."""
    fp.ajouter_historique(depot / "docs" / "fumee", dict(res, id=ident))


def _reecrire_fin_du_vert(depot, fin):
    """La verte du banc, relue dans l'historique, réécrite avec une autre fin (la dernière ligne
    d'un id gagne)."""
    res = next(r for r in fp.lire_resultats(depot / "docs" / "fumee") if r["verdict"] == "vert")
    fp.ajouter_historique(depot / "docs" / "fumee", dict(res, fin=fin))


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
            {"id": "edition", "statut": "vert", "ok": 12, "attendu": 12, "ko": 0},
            {"id": "machines", "statut": "vert", "ok": 5, "attendu": 5, "ko": 0},
            {"id": "chantiers", "statut": "vert", "ok": 21, "attendu": 21, "ko": 0, "duree_s": 585},
            {"id": "a1", "statut": "vert", "ok": 14, "attendu": 14, "ko": 0},
            {"id": "objets", "statut": "vert", "ok": 12, "attendu": 12, "ko": 0},
            {"id": "conversation", "statut": "vert", "ok": 13, "attendu": 13, "ko": 0}]
    page = fp.rendre_page(resultat(tout))
    assert "<code>9c937d0</code>" in page
    assert "07/11/2026 à 21:30" in page
    assert "Durée 40 min 00 s" in page
    assert "<strong>0.97</strong> (seuil 0.8)" in page
    assert "21 / 21 OK, 0 KO" in page and "14 / 14 OK, 0 KO" in page and "5 / 5 OK, 0 KO" in page
    assert "Toutes les épreuves sont vertes, aux valeurs gravées." in page
    # 16/11 : plus de lien vers des journaux versionnés — le nom du fichier et le dossier LOCAL.
    assert "<code>namespace.log</code>" in page and 'href="journaux/' not in page
    assert "<code>~/tmp/didier-fumee/2026-11-07-2130/</code>" in page
    assert "9 min 45 s" in page
    assert "non lancée" not in page


def test_page_rouge_dit_ou_et_ce_qui_n_a_pas_ete_lance():
    epreuves = [{"id": "image", "statut": "vert"}, {"id": "demarrage", "statut": "vert"},
                {"id": "rtf", "statut": "rouge", "obtenu": "0.49", "detail": "RTF 0.49 < 0.8"}]
    page = fp.rendre_page(resultat(epreuves, verdict="rouge", bloquant="rtf", rtf=0.49))
    assert "ROUGE à l&#x27;épreuve « Sonde du facteur temps réel (20 s) » : les suivantes n&#x27;ont pas été lancées." in page
    # namespace, catalogue, parle, edition (L1d), machines (L2b), chantiers, a1, objets (O1), conversation
    assert page.count("non lancée") == 9
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
    sortie, jsonl, brut = tmp_path / "docs-fumee", tmp_path / "epreuves.jsonl", tmp_path / "brut"
    for args in (["image", "--statut", "vert"], ["demarrage", "--statut", "vert"],
                 ["rtf", "--statut", "rouge", "--obtenu", "0.49", "--duree", "22"],
                 ["namespace", "--ok", "5", "--attendu", "5", "--ko", "0", "--duree", "60", "--journal", "namespace.log"]):
        assert fp.main(["epreuve", "--jsonl", str(jsonl), "--id", *args]) == 0

    def finaliser(id_fumee, fin):
        return fp.main(["finaliser", "--jsonl", str(jsonl), "--sortie", str(sortie), "--id", id_fumee,
                        "--brut", str(brut), "--brut-affiche", "~/brut",
                        "--meta", "sha=9c937d0", "--meta", "sha_complet=" + "9" * 40, "--meta", "sale=0",
                        "--meta", "branche=main", "--meta", "mode=force", "--meta", "raison=essai",
                        "--meta", "debut=2026-11-07T21:30:00+01:00", "--meta", "fin=" + fin,
                        "--meta", "duree_s=120", "--meta", "rtf=0.49", "--meta", "rtf_min=0.8",
                        "--meta", "charge_1min=1.7", "--meta", "nb_coeurs=32", "--meta", "essai=0",
                        "--meta", "image_reconstruite=0", "--note", "une note"])

    assert finaliser("2026-11-07-2130", "2026-11-07T21:32:00+01:00") == 0
    res = json.loads((brut / "2026-11-07-2130" / "resultat.json").read_text(encoding="utf-8"))
    assert res["verdict"] == "rouge" and res["bloquant"] == "rtf"
    assert res["page"] == "2026-11-07.html" and res["rtf"] == 0.49 and res["duree_s"] == 120
    assert res["sale"] is False and res["notes"] == ["une note"]
    assert (sortie / "2026-11-07.html").exists()
    # Une 2e fumée le même jour ne doit pas écraser la page de la première.
    assert finaliser("2026-11-07-2300", "2026-11-07T23:02:00+01:00") == 0
    res2 = json.loads((brut / "2026-11-07-2300" / "resultat.json").read_text(encoding="utf-8"))
    assert res2["page"] == "2026-11-07-2.html"
    index = (sortie / "index.html").read_text(encoding="utf-8")
    assert index.index("2026-11-07-2.html") < index.index('href="2026-11-07.html"')     # la plus récente en tête
    # Dans la sortie VERSIONNÉE : pages, index, historique — aucun journal brut.
    assert sorted(p.name for p in sortie.iterdir()) == ["2026-11-07-2.html", "2026-11-07.html",
                                                        "historique.jsonl", "index.html"]
    lignes = (sortie / "historique.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(l)["id"] for l in lignes] == ["2026-11-07-2130", "2026-11-07-2300"]
    assert "<code>~/brut/2026-11-07-2130/</code>" in (sortie / "2026-11-07.html").read_text(encoding="utf-8")


# --- fumee.sh lui-même : contrat gravé et garde-fous ----------------------------------

def _lire_sh():
    return FUMEE_SH.read_text(encoding="utf-8")


def test_valeurs_attendues_gravees_en_tete_du_script():
    src = _lire_sh()
    gravees = dict(re.findall(r"^(ATTENDU_[A-Z0-9]+)=(\d+)", src, re.M))
    assert gravees == {"ATTENDU_NAMESPACE": "5", "ATTENDU_CATALOGUE": "4", "ATTENDU_PARLE": "3",
                       "ATTENDU_EDITION": "13", "ATTENDU_MACHINES": "5", "ATTENDU_CHANTIERS": "21",
                       "ATTENDU_A1": "14", "ATTENDU_OBJETS": "13", "ATTENDU_CONVERSATION": "13"}
    assert re.search(r"^RTF_MIN_DEFAUT=0\.8$", src, re.M)


def test_les_compteurs_gravees_sont_ceux_des_scripts_de_verification():
    """Le chiffre gravé vaut le nombre de verdict() réellement présents dans le script lancé."""
    ns = (SCRIPTS / "validate-namespace.sh").read_text(encoding="utf-8")
    cat = (SCRIPTS / "validate-catalogue.sh").read_text(encoding="utf-8")
    assert len(re.findall(r'verdict "\$\(', ns)) == 5
    assert len(re.findall(r'verdict "\$\(', cat)) == 4
    # validate-data-edit.sh : épreuves numérotées « verdict(…, "N. … ») » dans son python.
    edition = (SCRIPTS / "validate-data-edit.sh").read_text(encoding="utf-8")
    assert re.findall(r'"(\d+)\. \S', edition) == [str(n) for n in range(1, 14)]
    # validate-machines.sh (L2b) : M1-M4 et M6, un verdict() chacun.
    machines = (SCRIPTS / "validate-machines.sh").read_text(encoding="utf-8")
    assert re.findall(r'^verdict\([^,]+, "(M\d)', machines, re.M) == ["M1", "M2", "M3", "M4", "M6"]
    # validate-objets.sh (O1) : E1a-e, E2a-e, E4a-c, un verdict() chacun (13 ; E2e = la garde de
    # la bouche éprouvée en sim, revue O1 du 19/11).
    objets_ = (SCRIPTS / "validate-objets.sh").read_text(encoding="utf-8")
    assert re.findall(r'f?"(E\d[a-e]) ', objets_) == ["E1a", "E1b", "E1c", "E1d", "E1e", "E2a", "E2b", "E2c",
                                                      "E2d", "E2e", "E4a", "E4b", "E4c"]
    # validate-conversation.sh (CONV, 16/11) : 13 verdict() étiquetés, dans cet ordre.
    conv = (SCRIPTS / "validate-conversation.sh").read_text(encoding="utf-8")
    assert re.findall(r'^verdict\(.*?\n?\s*f?"([PTABC]\d) ', conv, re.M | re.S) == [
        "P1", "T0", "A1", "A2", "A3", "B1", "B2", "B3", "B4", "B5", "C1", "C2", "C3"]


def test_validate_namespace_lit_le_graphe_sans_demon_et_avec_reprises():
    """Fumées du 19/11 07:50 et 07:52 : « bridge gz namespacé » KO (0 publisher lu PAR LE DÉMON)
    alors que le pont avait créé ground_truth/odom ; même image verte 2 min plus tard. Toute
    lecture du graphe du script passe sans démon, et le contrôle du pont a ses reprises."""
    ns = (SCRIPTS / "validate-namespace.sh").read_text(encoding="utf-8")
    code = "\n".join(l for l in ns.splitlines() if not l.lstrip().startswith("#"))
    lectures = re.findall(r"ros2 (?:topic|node|param) (?:list|info|get)[^\n|]*", code)
    assert len(lectures) == 4                       # topic list, node list, param get, topic info
    assert all("--no-daemon" in l for l in lectures), lectures
    pont = code[code.index("compte() {"):code.index('verdict "$([ "${pub_odom')]
    assert "for essai in 1 2 3 4; do" in pont and "break" in pont


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
    fp.ajouter_historique(depot / "docs" / "fumee", res)
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
               FAUX_NOTIFS=str(tmp_path / "notifs.txt"), FUMEE_DRY_POWEROFF="1",
               FUMEE_PLAGES=str(tmp_path / "aucune-plage"),   # jamais le fichier réel du PC
               # Jamais le brut réel du PC non plus : sans cette variable, les essais
               # écrivaient leurs fausses fumées rouges dans ~/tmp/didier-fumee (vu le 17/11 :
               # quatre « main, démarrage rouge » aux sha inexistants dans le vrai brut).
               FUMEE_BRUT=str(tmp_path / "brut"),
               # Ni le vrai verrou « sim occupée » (18/11) : posé par un agent pendant SA sim, il
               # aurait fait reporter ces essais — et un essai ne doit jamais le retirer.
               FUMEE_SIM_OCCUPEE=str(tmp_path / "sim-occupee"))
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
    assert not (depot / "docs" / "fumee" / "journaux").exists()          # rien de brut dans le dépôt


@pytest.mark.parametrize("maintenant, reporte", [
    ("1 08", True),    # lundi 8 h : dans la plage
    ("5 18", True),    # vendredi 18 h : dernière heure de la plage
    ("3 07", True),    # mercredi 7 h : l'heure AVANT la plage (la page tomberait dedans)
    ("2 19", False),   # mardi 19 h : FIN exclue
    ("1 06", False),   # lundi 6 h : plus d'une heure avant
    ("6 10", False),   # samedi : hors jours
    ("7 10", False),   # dimanche
])
def test_si_due_ne_demarre_pas_dans_une_plage_sans_commit(banc, maintenant, reporte):
    depot, env, tmp = banc
    _commit(depot, "packages/code.txt", "code 2")
    plages = tmp / "plages"
    plages.write_text("# commentaire ignoré\n1-5 8 19\n", encoding="utf-8")
    p = subprocess.run([str(FUMEE_SH), "--si-due"],
                       env=dict(env, FUMEE_PLAGES=str(plages), FUMEE_MAINTENANT=maintenant,
                                FUMEE_CHARGE_MAX="9999"),   # la charge du PC ne doit pas masquer la plage
                       capture_output=True, text=True, timeout=60)
    assert ("reporté : plage sans commit" in _journal(tmp)) is reporte
    if reporte:
        assert p.returncode == 0
        assert "compose" not in (tmp / "appels.txt").read_text(encoding="utf-8")   # aucune sim


def test_rappel_apres_deux_jours_de_report_une_fois_par_demi_journee(banc):
    """Due depuis > 2 jours et toujours reportée : notification + ligne RAPPEL, pas de harcèlement."""
    depot, env, tmp = banc
    _reecrire_fin_du_vert(depot, (datetime.now().astimezone() - timedelta(days=10)).isoformat())   # due depuis 3 jours
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
    ici = datetime.now().astimezone()
    _reecrire_fin_du_vert(depot, (ici - timedelta(days=jours_vert)).isoformat())
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
    env = dict(env, FAUX_DOCKER_PS="didier-sim-monde\n")
    p = _lancer(env, "--si-due")
    assert p.returncode == 0
    assert "reporté : conteneur didier-sim-monde déjà présent" in _journal(tmp)
    appels = (tmp / "appels.txt").read_text(encoding="utf-8").splitlines()
    assert not [a for a in appels if a.startswith(("rm", "compose", "stop", "kill", "exec"))]


@pytest.mark.parametrize("conteneur", ["didier-sim-monde", "didier-sim-robot", "didier-sim-vision",
                                       "didier-sim-telecommande"])
def test_si_due_ne_touche_a_aucun_des_quatre_conteneurs_de_la_sim(banc, conteneur):
    """L2b : chacun des quatre conteneurs de la sim multi-conteneurs, vivant, fait reporter."""
    depot, env, tmp = banc
    _commit(depot, "packages/code.txt", "code 2")
    env = dict(env, FAUX_DOCKER_PS=f"autre-chose\n{conteneur}\n")
    p = _lancer(env, "--si-due")
    assert p.returncode == 0
    assert f"reporté : conteneur {conteneur} déjà présent (running), pas touché" in _journal(tmp)
    appels = (tmp / "appels.txt").read_text(encoding="utf-8").splitlines()
    assert not [a for a in appels if a.startswith(("rm", "compose", "stop", "kill", "exec", "update"))]


def test_un_homonyme_partiel_n_est_pas_la_sim(banc):
    """Le nom doit être EXACT : un conteneur « didier-sim-monde-2 » n'est pas la sim. La fumée est
    due (commit) ; elle passe le contrôle des conteneurs puis reporte sur la charge (seuil 0)."""
    depot, env, tmp = banc
    _commit(depot, "packages/code.txt", "code 2")
    env = dict(env, FAUX_DOCKER_PS="didier-sim-monde-2\nxdidier-sim-robot\n", FUMEE_CHARGE_MAX="0")
    p = _lancer(env, "--si-due")
    assert p.returncode == 0
    assert "déjà présent" not in _journal(tmp)
    assert "reporté : charge trop haute" in _journal(tmp)


def test_les_conteneurs_de_la_fumee_sont_ceux_du_compose():
    import yaml
    src = _lire_sh()
    compose = yaml.safe_load((SCRIPTS / "docker-compose.yml").read_text(encoding="utf-8"))["services"]
    assert "CONTENEURS=(didier-sim-monde didier-sim-robot didier-sim-vision didier-sim-telecommande)" in src
    assert "SERVICES=(monde robot vision telecommande)" in src
    assert [compose[s]["container_name"] for s in ("monde", "robot", "vision", "telecommande")] == [
        "didier-sim-monde", "didier-sim-robot", "didier-sim-vision", "didier-sim-telecommande"]
    assert "IMAGES=(didier-sim/monde:local didier-sim/robot:local didier-sim/vision:local didier-sim/telecommande:local)" in src
    assert "DELAI_DEMARRAGE=600" in src
    # La chaîne roues tourne dans le bringup du robot : la fumée ne la lance plus.
    assert "drive.launch.py" not in "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))


def test_et_dodo_refuse_et_n_eteint_pas_si_une_sim_existe(banc):
    _, env, tmp = banc
    env = dict(env, FAUX_DOCKER_PS="didier-sim-robot\n")
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


def test_la_boucle_des_coeurs_ne_garde_pas_le_verrou_et_meurt_avec_ses_fils():
    """Défaut du 15/11 : le `sleep 15` orphelin de la boucle de maintien gardait le descripteur 9
    (verrou) jusqu'à 15 s après la fin ; la seconde de deux fumées enchaînées sortait sans rien
    faire. Un `maintenir` survivant repousserait aussi les processus APRÈS la libération."""
    sh = _lire_sh()
    epingler = sh[sh.index("\nepingler_sim() {"):sh.index("\nliberer_coeurs() {")]
    assert "    done ) 9>&- &\n" in epingler
    liberer = sh[sh.index("\nliberer_coeurs() {"):sh.index("\nnoeuds_attendus_vus() {")]
    assert 'enfants="$(pgrep -P "$MAINTIEN_PID"' in liberer
    assert liberer.index('kill "$MAINTIEN_PID"') < liberer.index("kill $enfants")
    assert liberer.index("kill $enfants") < liberer.index('"$COEURS_PY" liberer')
    assert "pkill -f" not in sh


def test_fumee_forcee_refuse_en_le_disant_si_le_verrou_est_tenu(banc):
    """Mode forcé : plus de sortie MUETTE en 0 quand une autre fumée tient le verrou."""
    depot, env, tmp = banc
    (tmp / "etat").mkdir(exist_ok=True)
    tenant = subprocess.Popen(["flock", str(tmp / "etat" / "verrou"), "sleep", "30"])
    try:
        for _ in range(50):
            if subprocess.run(["flock", "-n", str(tmp / "etat" / "verrou"), "true"]).returncode != 0:
                break
            time.sleep(0.1)
        r = _lancer(dict(env, FUMEE_VERROU_ATTENTE="1"))
        assert r.returncode == 2
        assert "REFUS : une autre fumée tient le verrou" in r.stdout
        assert "refus : verrou tenu par une autre fumée (mode force)" in _journal(tmp)
        assert (tmp / "appels.txt").read_text(encoding="utf-8") == ""     # docker jamais appelé
        # La minuterie, elle, reste silencieuse (le prochain passage réessaiera).
        r = _lancer(env, "--si-due")
        assert r.returncode == 0 and r.stdout == ""
    finally:
        tenant.kill()
        tenant.wait()


# --- Historique permanent et brut local (décision de David, 16/11) --------------------------

def test_ligne_historique_format_grave():
    """Une ligne par fumée, champs dans cet ordre, scores de TOUTES les épreuves (ordre canonique)."""
    epreuves = [{"id": "image", "statut": "vert"}, {"id": "demarrage", "statut": "vert"},
                {"id": "rtf", "statut": "vert", "obtenu": "0.998"},
                {"id": "namespace", "statut": "vert", "ok": 5, "attendu": 5, "ko": 0},
                {"id": "catalogue", "statut": "vert", "ok": 4, "attendu": 4, "ko": 0},
                {"id": "parle", "statut": "vert", "ok": 3, "attendu": 3, "ko": 0},
                {"id": "edition", "statut": "vert", "ok": 13, "attendu": 13, "ko": 0},
                {"id": "machines", "statut": "vert", "ok": 5, "attendu": 5, "ko": 0},
                {"id": "chantiers", "statut": "rouge", "ok": 20, "attendu": 21, "ko": 1}]
    res = resultat(epreuves, verdict="rouge", bloquant="chantiers", rtf=0.998, notes=["pas dans l'historique"])
    assert fp.ligne_historique(res) == (
        '{"id": "2026-11-07-2130", "debut": "2026-11-07T21:30:00+01:00", "fin": "2026-11-07T22:10:00+01:00", '
        '"sha": "9c937d0", "sha_complet": "9c937d0000000000000000000000000000000000", "branche": "main", '
        '"mode": "force", "essai": false, "verdict": "rouge", "bloquant": "chantiers", "rtf": 0.998, '
        '"duree_s": 2400, "page": "2026-11-07.html", "epreuves": {"image": "vert", "demarrage": "vert", '
        '"rtf": "vert 0.998", "namespace": "vert 5/5", "catalogue": "vert 4/4", "parle": "vert 3/3", '
        '"edition": "vert 13/13", "machines": "vert 5/5", "chantiers": "rouge 20/21 1KO", "a1": "non_lance", '
        '"objets": "non_lance", "conversation": "non_lance"}}\n')


def test_lire_resultats_lit_l_historique_derniere_ligne_gagnante(tmp_path):
    h = tmp_path / "historique.jsonl"
    h.write_text('{"id": "b", "fin": "2026-11-08T10:00:00+01:00", "verdict": "rouge"}\n'
                 "pas du json\n"
                 '{"id": "a", "fin": "2026-11-07T10:00:00+01:00", "verdict": "vert"}\n'
                 '{"id": "b", "fin": "2026-11-08T10:00:00+01:00", "verdict": "vert"}\n', encoding="utf-8")
    assert [(r["id"], r["verdict"]) for r in fp.lire_resultats(tmp_path)] == [("a", "vert"), ("b", "vert")]
    assert fp.lire_resultats(tmp_path / "absent") == []


@pytest.mark.parametrize("verdict, jours, traite, purge", [
    ("vert", 31, False, True),      # vert de plus de 30 jours : purgé
    ("vert", 29, False, False),     # vert récent : gardé
    ("rouge", 400, False, False),   # rouge : JAMAIS purgé automatiquement…
    ("rouge", 31, True, True),      # … sauf marqué TRAITE et plus de 30 jours
    ("rouge", 10, True, False),     # TRAITE mais récent : gardé
])
def test_regle_de_purge_gravee(verdict, jours, traite, purge):
    res = {"verdict": verdict, "fin": (MAINTENANT - timedelta(days=jours)).isoformat()}
    assert fp.a_purger(res, traite, MAINTENANT) is purge


def test_purger_le_brut_local(tmp_path):
    brut = tmp_path / "brut"
    for ident, verdict, jours, traite in [("vieux-vert", "vert", 40, False), ("vert-recent", "vert", 3, False),
                                          ("vieux-rouge", "rouge", 90, False), ("rouge-traite", "rouge", 40, True)]:
        d = brut / ident
        d.mkdir(parents=True)
        (d / "resultat.json").write_text(json.dumps(
            {"verdict": verdict, "fin": (MAINTENANT - timedelta(days=jours)).isoformat()}), encoding="utf-8")
        (d / "chantiers.log").write_text("x", encoding="utf-8")
        if traite:
            (d / "TRAITE").write_text("conclusion : docs/incidents/…\n", encoding="utf-8")
    (brut / "sans-resultat").mkdir()                         # interrompue avant finaliser : gardée
    assert fp.main(["purger", "--brut", str(brut), "--maintenant", MAINTENANT.isoformat()]) == 0
    assert sorted(p.name for p in brut.iterdir()) == ["sans-resultat", "vert-recent", "vieux-rouge"]


def test_amorcer_l_historique_depuis_les_anciens_journaux(tmp_path):
    anciens, sortie = tmp_path / "journaux", tmp_path / "docs-fumee"
    for ident, fin, verdict in [("2026-11-08-0100", "2026-11-08T01:40:00+01:00", "rouge"),
                                ("2026-11-07-2130", "2026-11-07T22:10:00+01:00", "vert")]:
        (anciens / ident).mkdir(parents=True)
        (anciens / ident / "resultat.json").write_text(json.dumps(
            resultat([{"id": "image", "statut": verdict}], verdict=verdict, id=ident, fin=fin)), encoding="utf-8")
    assert fp.main(["amorcer", "--sortie", str(sortie), "--depuis", str(anciens)]) == 0
    assert fp.main(["amorcer", "--sortie", str(sortie), "--depuis", str(anciens)]) == 0     # idempotent
    lignes = [json.loads(l) for l in (sortie / "historique.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [l["id"] for l in lignes] == ["2026-11-07-2130", "2026-11-08-0100"]               # par fin
    assert (sortie / "index.html").exists()


def test_fumee_sh_brut_local_purge_et_sim_hors_depot():
    sh = _lire_sh()
    assert 'BRUT="${FUMEE_BRUT:-$HOME/tmp/didier-fumee}"' in sh and 'JDIR="$BRUT/$ID"' in sh
    assert '"$PAGE_PY" purger --brut "$BRUT"' in sh
    assert '"$SORTIE/journaux' not in sh
    assert 'DIDIER_SIM_JOURNAUX="$JOURNAUX_SIM"' in sh


def test_le_depot_ignore_les_journaux_bruts():
    ignores = (SCRIPTS.parents[1] / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "docs/fumee/journaux/" in ignores


# --- Lecture des journaux docker sans tube sous pipefail (rouge CONV du 16/11 23:30) ----------

def _fonction_sh(nom):
    m = re.search(r"^%s\(\) \{.*?^\}\n" % re.escape(nom), _lire_sh(), re.M | re.S)
    assert m, "%s() introuvable dans fumee.sh" % nom
    return m.group(0)


def _faux_docker_bavard(tmp_path, entete):
    """Faux docker dont `logs` imite un chat_node sans micro : une ligne d'en-tête, puis ≈ 400 Ko."""
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    faux = bin_ / "docker"
    faux.write_text('#!/bin/bash\n[ "$1" = logs ] || exit 0\nprintf "%s\\n" "$FAUX_ENTETE"\n'
                    'for i in $(seq 4000); do printf "[chat-3] ALSA lib pcm.c:2721: Unknown PCM casque_mic'
                    ' xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\\n"; done\n', encoding="utf-8")
    faux.chmod(0o755)
    return dict(os.environ, PATH=str(bin_) + os.pathsep + os.environ["PATH"], FAUX_ENTETE=entete,
                TMP=str(tmp_path))


def test_le_faux_docker_reproduit_le_defaut_du_tube(tmp_path):
    """Témoin : l'ANCIEN motif (docker logs | grep -q sous pipefail) rate un Summary pourtant là."""
    env = _faux_docker_bavard(tmp_path, "Summary: 4 packages finished [10.1s]")
    p = subprocess.run(["bash", "-c", "set -o pipefail; docker logs c 2>&1 | grep -qE 'Summary: [0-9]+ packages? finished'"
                        " && echo compte || echo rate"], env=env, capture_output=True, text=True, timeout=30)
    assert p.stdout.strip() == "rate"


@pytest.mark.parametrize("entete, attendu", [
    ("Summary: 4 packages finished [10.1s]", "fini"),
    ("Summary: 3 packages finished [9.0s]\n1 package failed: didier_vision", "echec"),
    ("Failed   <<< didier_vision [2.1s, exited with code 1]", "echec"),
    ("Starting >>> didier_vision", "en_cours"),
])
def test_etat_colcon_juste_meme_avec_un_journal_enorme(tmp_path, entete, attendu):
    env = _faux_docker_bavard(tmp_path, entete)
    script = "set -euo pipefail\n" + _fonction_sh("etat_colcon") + 'etat_colcon didier-sim-vision\n'
    p = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=30)
    assert p.returncode == 0 and p.stdout.strip() == attendu


def test_aucun_tube_docker_vers_grep_q_dans_les_scripts_sous_pipefail():
    motif = re.compile(r"^(?!\s*#).*docker (?:logs|ps)\b[^\n|]*\|\s*grep -q", re.M)   # hors commentaires
    fautifs = []
    for sh in sorted(SCRIPTS.glob("*.sh")):
        src = sh.read_text(encoding="utf-8")
        if "pipefail" in src:
            fautifs += ["%s:%d" % (sh.name, src[:m.start()].count("\n") + 1) for m in motif.finditer(src)]
    assert fautifs == []


def test_extinction_du_pc_notee_par_simple_lecture_de_systemd():
    """17/11 00:39 : PC éteint au bouton pendant la relance A1, rouge lu « Gazebo mort »."""
    sh = _lire_sh()
    corps = sh[sh.index("\nterminer() {"):sh.index("\ntrap terminer EXIT")]
    assert "systemctl is-system-running" in corps
    assert re.findall(r"systemctl (\S+)", corps) == ["is-system-running"]    # lecture seule
    assert "etat_conteneur" in _fonction_sh("demarrer_sim")


# --- Verrou « sim occupée » des agents et de David (18/11) ---------------------------------
# ~/tmp/sim-occupee (« <qui> <heure> ») : la minuterie l'ignorait et pouvait lancer une fumée
# par-dessus la sim d'un agent ou une séance de David. Ici : chemin dans tmp_path (banc).

def _poser_verrou(tmp, contenu, age_s=0):
    v = tmp / "sim-occupee"
    v.write_text(contenu + "\n", encoding="utf-8")
    if age_s:
        t = time.time() - age_s
        os.utime(v, (t, t))
    return v


def test_peremption_du_verrou_gravee():
    assert "PEREMPTION_SIM_OCCUPEE_S=21600   # 6 h" in _lire_sh()


def test_si_due_reporte_tant_que_la_sim_est_reservee(banc):
    depot, env, tmp = banc
    _commit(depot, "packages/code.txt", "code 2")
    v = _poser_verrou(tmp, "david 21:00", age_s=3600)
    p = _lancer(env, "--si-due")
    assert p.returncode == 0
    assert "reporté : sim réservée par « david 21:00 » (" in _journal(tmp)
    assert (tmp / "appels.txt").read_text(encoding="utf-8") == ""      # docker jamais appelé
    assert v.read_text(encoding="utf-8") == "david 21:00\n"             # jamais touché


def test_si_due_reporte_encore_juste_avant_six_heures(banc):
    depot, env, tmp = banc
    _commit(depot, "packages/code.txt", "code 2")
    _poser_verrou(tmp, "fiab2 18:00", age_s=6 * 3600 - 120)
    assert _lancer(env, "--si-due").returncode == 0
    assert "reporté : sim réservée par « fiab2 18:00 »" in _journal(tmp)


def test_si_due_ignore_un_verrou_perime_sans_l_effacer(banc):
    """Au-delà de 6 h : ignoré (noté), la fumée passe à la garde suivante (charge, seuil -1)."""
    depot, env, tmp = banc
    _commit(depot, "packages/code.txt", "code 2")
    v = _poser_verrou(tmp, "fiab2 08:00", age_s=6 * 3600 + 120)
    p = _lancer(dict(env, FUMEE_CHARGE_MAX="-1"), "--si-due")
    assert p.returncode == 0
    j = _journal(tmp)
    assert "« fiab2 08:00 » PÉRIMÉ (âge " in j and "≥ 21600 s) : ignoré, pas effacé" in j
    assert "reporté : charge trop haute" in j
    assert "sim réservée" not in j
    assert v.read_text(encoding="utf-8") == "fiab2 08:00\n"


def test_si_due_pas_due_reste_muette_meme_avec_un_verrou(banc):
    _, env, tmp = banc
    _poser_verrou(tmp, "david 21:00")
    p = _lancer(env, "--si-due")
    assert p.returncode == 0 and p.stdout == "" and _journal(tmp) == ""


def test_fumee_forcee_refuse_poliment_si_la_sim_est_reservee(banc):
    _, env, tmp = banc
    v = _poser_verrou(tmp, "fiab2 00:45")
    p = _lancer(env)
    assert p.returncode == 2
    assert "REFUS : la sim est réservée par « fiab2 00:45 »" in p.stdout
    assert "--forcer-verrou" in p.stdout
    assert "refus : sim réservée par « fiab2 00:45 »" in _journal(tmp)
    assert (tmp / "appels.txt").read_text(encoding="utf-8") == ""
    assert v.read_text(encoding="utf-8") == "fiab2 00:45\n"


def test_et_dodo_refuse_et_n_eteint_pas_si_la_sim_est_reservee(banc):
    _, env, tmp = banc
    _poser_verrou(tmp, "david 23:10")
    p = _lancer(env, "--et-dodo")
    assert p.returncode == 2
    assert "REFUS : la sim est réservée par « david 23:10 »" in p.stdout
    assert "poweroff" not in p.stdout.lower()


def test_forcer_verrou_passe_outre_mais_pas_la_sim_vivante(banc):
    """--forcer-verrou lève le verrou de fichier SEUL : un conteneur vivant refuse toujours."""
    _, env, tmp = banc
    v = _poser_verrou(tmp, "fiab2 00:45")
    p = _lancer(dict(env, FAUX_DOCKER_PS="didier-sim-monde\n"), "--forcer-verrou")
    assert p.returncode == 2
    assert "verrou « fiab2 00:45 » outrepassé (--forcer-verrou)" in p.stdout
    assert "verrou " + str(v) + " « fiab2 00:45 » outrepassé (--forcer-verrou, mode force)" in _journal(tmp)
    assert "REFUS : le conteneur didier-sim-monde existe déjà" in p.stdout
    assert v.read_text(encoding="utf-8") == "fiab2 00:45\n"


def test_forcer_verrou_refuse_avec_la_minuterie(banc):
    _, env, _ = banc
    p = _lancer(env, "--si-due", "--forcer-verrou")
    assert p.returncode == 2
    assert "--forcer-verrou ne vaut que pour une fumée lancée à la main" in p.stderr


def test_un_verrou_fumee_reste_d_un_crash_est_retire(banc):
    """« fumee <heure> » au départ : le flock est à nous, c'est le reste d'une fumée finie."""
    depot, env, tmp = banc
    _commit(depot, "packages/code.txt", "code 2")
    v = _poser_verrou(tmp, "fumee 01:30", age_s=600)
    p = _lancer(dict(env, FUMEE_CHARGE_MAX="-1"), "--si-due")
    assert p.returncode == 0
    assert not v.exists()
    j = _journal(tmp)
    assert "reste retiré : verrou " + str(v) + " « fumee 01:30 » d'une fumée finie" in j
    assert "reporté : charge trop haute" in j


def _fonctions_verrou():
    sh = _lire_sh()
    return sh[sh.index("\nposer_verrou_sim() {"):sh.index("\ndodo() {")]


def _bash_verrou(tmp, script):
    return subprocess.run(["bash", "-c", "set -euo pipefail\nSIM_OCCUPEE=" + str(tmp / "d" / "sim-occupee")
                           + "\nVERROU_SIM_A_NOUS=0\n" + _fonctions_verrou() + "\n" + script],
                          capture_output=True, text=True, timeout=10)


def test_la_fumee_pose_son_verrou_et_le_retire(tmp_path):
    p = _bash_verrou(tmp_path, 'poser_verrou_sim; cat "$SIM_OCCUPEE"; liberer_verrou_sim; '
                               '[ ! -e "$SIM_OCCUPEE" ] && echo retire; liberer_verrou_sim; echo idempotent')
    assert p.returncode == 0, p.stderr
    lignes = p.stdout.splitlines()
    assert re.fullmatch(r"fumee \d\d:\d\d", lignes[0])
    assert lignes[1:] == ["retire", "idempotent"]


def test_la_fumee_ne_pose_rien_par_dessus_un_autre_et_ne_retire_pas_le_sien(tmp_path):
    (tmp_path / "d").mkdir()
    v = tmp_path / "d" / "sim-occupee"
    v.write_text("david 22:00\n", encoding="utf-8")
    p = _bash_verrou(tmp_path, "poser_verrou_sim; liberer_verrou_sim; echo $VERROU_SIM_A_NOUS")
    assert p.returncode == 0, p.stderr
    assert p.stdout == "0\n"
    assert v.read_text(encoding="utf-8") == "david 22:00\n"


def test_la_fumee_ne_retire_pas_un_verrou_remplace_pendant_elle(tmp_path):
    p = _bash_verrou(tmp_path, 'poser_verrou_sim; echo "fiab2 03:00" >"$SIM_OCCUPEE"; liberer_verrou_sim; '
                               'cat "$SIM_OCCUPEE"')
    assert p.returncode == 0, p.stderr
    assert p.stdout == "fiab2 03:00\n"


def test_le_verrou_est_pose_juste_avant_le_deroule_et_libere_en_fin():
    sh = _lire_sh()
    assert "\nposer_verrou_sim\nderoule\n" in sh
    terminer = sh[sh.index("\nterminer() {"):sh.index("\ntrap terminer EXIT")]
    assert "  liberer_verrou_sim\n" in terminer


# --- Panne réseau pendant la reconstruction des images (18/11 10:36) -----------------------

def _fonction_reseau(nom):
    m = re.search(r"^" + nom + r"\(\) \{[^\n]*\n.*?^\}\n", _lire_sh(), re.M | re.S)
    assert m, nom + "() introuvable"
    return m.group(0)


JOURNAL_DNS_18_11 = (
    '#21 ERROR: failed to do request: Head "https://registry-1.docker.io/v2/library/ros/manifests/'
    'jazzy-ros-base": dial tcp: lookup registry-1.docker.io on 127.0.0.53:53: read udp '
    '127.0.0.1:59843->127.0.0.53:53: i/o timeout\n'
    'target monde: failed to solve: ros:jazzy-ros-base: failed to resolve source metadata\n')
JOURNAL_DOCKERFILE_FAUX = (
    '#9 [robot 4/9] RUN pip install -r /tmp/requirements.txt\n'
    '#9 ERROR: process "/bin/sh -c pip install -r /tmp/requirements.txt" did not complete '
    'successfully: exit code: 1\nfailed to solve: process did not complete successfully\n')


@pytest.mark.parametrize("journal, panne", [(JOURNAL_DNS_18_11, True), (JOURNAL_DOCKERFILE_FAUX, False)])
def test_panne_reseau_distinguee_d_un_dockerfile_casse(tmp_path, journal, panne):
    log = tmp_path / "image.log"
    log.write_text(journal, encoding="utf-8")
    p = subprocess.run(["bash", "-c", _fonction_reseau("panne_reseau_build") + 'panne_reseau_build "$1"', "_", str(log)])
    assert (p.returncode == 0) is panne


def _construire(tmp_path, reponses):
    """Joue construire_images() avec un faux docker dont chaque appel lit la réponse suivante."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    for i, (texte, code) in enumerate(reponses):
        (tmp_path / f"rep{i}").write_text(texte, encoding="utf-8")
        (tmp_path / f"code{i}").write_text(str(code), encoding="utf-8")
    faux = bin_ / "docker"
    faux.write_text('#!/bin/bash\nn=$(cat "$CPT" 2>/dev/null || echo 0); echo $((n+1)) >"$CPT"\n'
                    'cat "$REP/rep$n"; exit "$(cat "$REP/code$n")"\n', encoding="utf-8")
    faux.chmod(0o755)
    script = ("dit() { :; }\nDOCKER_DIR=\"$REP\"; COMPOSE=x\n" + _fonction_reseau("panne_reseau_build")
              + _fonction_reseau("construire_images") + "construire_images")
    env = dict(os.environ, PATH=str(bin_) + os.pathsep + os.environ["PATH"], CPT=str(tmp_path / "cpt"),
               REP=str(tmp_path), TMP=str(tmp_path), FUMEE_ATTENTE_RESEAU="0")
    p = subprocess.run(["bash", "-c", script], env=env)
    appels = int((tmp_path / "cpt").read_text())
    return p.returncode, appels


def test_une_coupure_dns_passagere_ne_rougit_pas(tmp_path):
    rc, appels = _construire(tmp_path, [(JOURNAL_DNS_18_11, 1), ("Built\n", 0)])
    assert (rc, appels) == (0, 2)


def test_un_dockerfile_casse_n_est_pas_reessaye(tmp_path):
    rc, appels = _construire(tmp_path, [(JOURNAL_DOCKERFILE_FAUX, 1), ("Built\n", 0)])
    assert (rc, appels) == (1, 1)


def test_une_panne_reseau_qui_dure_reste_un_echec(tmp_path):
    rc, appels = _construire(tmp_path, [(JOURNAL_DNS_18_11, 1), (JOURNAL_DNS_18_11, 1)])
    assert (rc, appels) == (1, 2)
