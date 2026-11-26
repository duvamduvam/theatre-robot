"""Le rapport (F1, 25/11) : resultat.json, page, historique — ceux de fumee_page.py, au même format
que fumee.sh (spec §1), plus le statut `invalide`. Commit de docs/fumee seulement, depuis le
checkout de main, jamais pour un essai.
"""
import importlib.util
import json
from datetime import datetime
from pathlib import Path

_spec = importlib.util.spec_from_file_location("fumee_page", Path(__file__).resolve().parents[1] / "fumee_page.py")
fp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fp)


def verdict(epreuves: list):
    """(verdict, premier rouge) sur les épreuves JOUÉES (spec §4) : une rouge = rouge ; sinon une
    invalide = invalide ; facultative non lancée = rien. fp.verdict_global complète avec toutes les
    épreuves de la page : une sélection (--epreuves) y serait « interrompue », donc rouge."""
    rouge = next((e["id"] for e in epreuves if e["statut"] == "rouge"), None)
    if rouge:
        return "rouge", rouge
    if any(e["statut"] == "invalide" for e in epreuves):
        return "invalide", None
    if any(e["statut"] == "non_lance" and not e.get("facultative") for e in epreuves):
        return "rouge", None   # non lancée sans rouge ni invalide avant : ne doit pas arriver
    return "vert", None


def fusionner(plan, gardees: dict, nouvelles: list) -> list:
    """--reprendre : les épreuves rejouées remplacent les gardées, dans l'ordre du plan."""
    par_id = {**gardees, **{r["id"]: r for r in nouvelles}}
    return [par_id[e.id] for e in plan if e.id in par_id]


def a_reprendre(brut: Path, sha_complet: str):
    """Le dernier resultat.json de CETTE révision dans le brut local, ou None."""
    trouves = []
    for f in brut.glob("*/resultat.json"):
        try:
            res = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if res.get("sha_complet") == sha_complet:
            trouves.append(res)
    return max(trouves, key=lambda r: r.get("fin") or "") if trouves else None


def finaliser(f, sortie: Path, brut: Path, meta: dict, epreuves: list) -> dict:
    """Écrit <brut>/<id>/resultat.json + journaux, la page, l'historique et le sommaire."""
    for log in sorted(f.tmp.glob("*.log")):   # journaux des épreuves, 2000 dernières lignes
        lignes = log.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        (f.jdir / log.name).write_text("".join(lignes[-2000:]), encoding="utf-8")
    res = {"version": fp.VERSION, "id": f.id, "notes": list(f.notes), **meta, "epreuves": epreuves}
    res["verdict"], res["bloquant"] = verdict(epreuves)
    res["page"] = fp.nom_de_page(sortie, f.id)
    res["brut"] = str(brut).replace(str(Path.home()), "~", 1)
    (f.jdir / "resultat.json").write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fp.ajouter_historique(sortie, res)
    (sortie / res["page"]).write_text(fp.rendre_page(res), encoding="utf-8")
    fp.ecrire_pages(sortie)
    fp.purger(brut, datetime.now().astimezone())
    return res


def commiter(sy, depot: Path, res: dict) -> str:
    """Le seul commit permis : pathspec docs/fumee dans le checkout de main (jamais -a ni add .)."""
    if res.get("essai") or res.get("branche") != "main":
        return "page non commitée (essai ou révision hors main)"
    rc, branche = sy.sortie(["git", "-C", str(depot), "rev-parse", "--abbrev-ref", "HEAD"])
    if branche.strip() != "main":
        return "page non commitée : le checkout {} est sur {}, pas sur main".format(depot, branche.strip())
    message = "Fumée {} : {} sur {} (RTF {})".format(res["id"], res["verdict"], res["sha"], res.get("rtf") or "n/a")
    for _ in range(3):   # un commit de David en même temps tient index.lock quelques secondes
        if sy.sortie(["git", "-C", str(depot), "add", "--", "docs/fumee"])[0] == 0 and sy.sortie(
                ["git", "-C", str(depot), "commit", "-q", "-m", message, "-m", "Page et historique de "
                 "docs/fumee ; commit automatique du programme de fumée (F1), docs/fumee seulement.",
                 "--", "docs/fumee"])[0] == 0:
            return "page commitée dans main"
        sy.dormir(5)
    return "ÉCHEC du commit de docs/fumee (3 essais) : page écrite, non commitée"
