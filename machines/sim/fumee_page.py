#!/usr/bin/env python3
"""Lot F — fumée nocturne : décision « due ? » et pages HTML (stdlib seulement).

Appelé par fumee.sh ; testé sur l'hôte (packages/didier_core/test/unit/test_fumee.py). Aucune
dépendance : le script tourne sous une minuterie systemd, sans venv.

Deux endroits depuis le 16/11 (décision de David : les journaux bruts n'ont rien à faire ni
sur GitHub ni sur Nextcloud) :
  - `<sortie>` (docs/fumee/, VERSIONNÉ) : les pages HTML, `index.html` et **`historique.jsonl`**,
    une ligne par fumée, gardée pour toujours — c'est lui que lisent la décision « due ? », le
    « dernier vert » et le sommaire, et lui qui montre les tendances (épreuve instable, sim qui
    ralentit). Format d'une ligne : `ligne_historique` (gravé par test_fumee.py).
  - `<brut>` (LOCAL, défaut ~/tmp/didier-fumee/) : un dossier `<id>/` par
    fumée, `resultat.json` complet + journaux et captures copiés hors conteneur ;
    `<id>` = AAAA-MM-JJ-HHMM (heure locale du début). Purge (`purger`, à la fin de chaque
    fumée) : VERT au-delà de 30 jours ; un ROUGE n'est JAMAIS purgé tant que son dossier ne
    porte pas le marqueur `TRAITE` (la conclusion du rouge va dans docs/incidents/).

Format de `resultat.json` (version 1) :
    id          str   AAAA-MM-JJ-HHMM
    sha         str   sha court testé, suffixé « -dirty » si l'arbre était sale
    sha_complet str   sha entier de HEAD (sans suffixe) : c'est LUI qui sert à
                      la décision « due ? »
    sale        bool  arbre de travail modifié au départ (hors docs/fumee)
    branche     str   branche du checkout testé (attendu : main)
    mode        str   « si-due » | « force » | « et-dodo »
    raison      str   pourquoi la fumée a eu lieu (due : …, ou lancée à la main)
    debut, fin  str   ISO 8601 avec fuseau
    duree_s     int
    rtf         float|null   facteur temps réel mesuré (sonde 20 s)
    rtf_min     float        seuil (0,8) sous lequel la suite n'est pas fiable
    charge_1min float        load average 1 min au départ
    nb_coeurs   int
    essai       bool  vrai si un seuil a été forcé (essai provoqué) : une telle
                      fumée n'est JAMAIS prise pour la « dernière verte »
    image_reconstruite bool
    notes       [str] observations non bloquantes (arbre modifié pendant la
                      fumée, journal tronqué…)
    epreuves    [ {id, statut, ok, attendu, ko, obtenu, detail, duree_s, journal} ]
                statut : « vert » | « rouge » | « non_lance ». Les épreuves
                absentes sont complétées en « non_lance » par la page.
    verdict     « vert » (toutes vertes) | « rouge »
    bloquant    id de la première épreuve rouge, ou null
    page        nom du fichier HTML (relatif à <sortie>)

Sous-commandes : due, dernier-vert, epreuve, finaliser, pages, purger, amorcer (voir --help).
"""
import argparse
import html
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

VERSION = 1
SEUIL_JOURS = 7        # décision 2 : 7 jours sans fumée verte = due (dérive de l'environnement)
RAPPEL_JOURS = 2       # décision 2 : due depuis plus de 2 jours = on prévient David

# Chemins TESTÉS par la fumée (règle décidée le 10/11) : seul un commit qui touche l'un
# d'eux rend une fumée due. Avant, tout commit comptait — le 08/11, 14 commits de DOC
# (étude du torse) ont lancé des sims de 35 min pour rien. docs/ n'y est pas (pas plus que
# docs/fumee, nos propres pages). Les trois dossiers de données de legacy/dadou_robot_ros
# restent listés tant qu'ils existent sur main (un chemin absent ne fait simplement rien).
# L1e-4c (11/11) : les conf/ du robot et de la vision sont dans machines/ (déjà listé) ; leurs
# anciens chemins legacy ne déclenchent plus rien.
CHEMINS_TESTES = (
    "packages/",
    "data/",
    "deploy/",
    "machines/",
    "legacy/dadou_robot_ros/json/",
    "legacy/dadou_robot_ros/medias/",
    "legacy/dadou_robot_ros/db/",
)
# Après un rouge sur un « sha de code » (dernier commit touchant un chemin testé) : UNE
# relance de confirmation, puis plus rien sur ce même code (le 08/11 un rouge a été rejoué
# toutes les 30 min). 2 = le rouge d'origine + sa confirmation.
ROUGES_MAX_PAR_CODE = 2

# Ordre et noms des épreuves (décision 3). Le script shell n'envoie que les id.
EPREUVES = [
    ("image", "Images sim ×4 (reconstruites seulement si un Dockerfile/compose a changé)"),
    ("demarrage", "Sim headless, 4 conteneurs : domaine 43, colcon ×4, nœuds attendus"),
    ("rtf", "Sonde du facteur temps réel (20 s)"),
    ("namespace", "validate-namespace.sh"),
    ("catalogue", "validate-catalogue.sh"),
    ("parle", "Animation « parle » (animation_state \"\" → \"parle\" → \"\")"),
    ("edition", "validate-data-edit.sh (édition à travers le robot, L1d)"),
    ("machines", "validate-machines.sh (les machines de la sim, vues depuis le monde, L2b)"),
    ("corps_sur", "Sim relancée (monde stage), validate-corps-sur.sh (CS : corps sûr, lot A0-4)"),
    ("chantiers", "Sim relancée (monde chantiers), régisseur + regard (chaîne roues du bringup), puis "
                  "validate-rehearsal-chantiers.sh (V-R3)"),
    ("a1", "Sim relancée, validate-jeu-a1.sh (A1)"),
    ("objets", "Sim relancée, validate-objets.sh (OBJ : tableau des objets, lot O1)"),
    ("conversation", "Sim relancée avec la tête (Claude Haiku, Anthropic direct), validate-conversation.sh (CONV)"),
]
# Épreuves FACULTATIVES (16/11) : « non lancée » faute d'un prérequis hors dépôt (la clé
# Anthropic de David pour CONV) ne rougit pas la fumée — seul un vrai rouge le fait.
FACULTATIVES = frozenset({"conversation"})
NOMS = dict(EPREUVES)
HISTORIQUE = "historique.jsonl"
PURGE_JOURS = 30       # brut d'une fumée VERTE (ou d'un rouge marqué TRAITE) gardé 30 jours
MARQUEUR_TRAITE = "TRAITE"
# Champs d'une ligne d'historique, dans cet ordre (gravé) : de quoi décider « due ? » (sha_complet,
# verdict, essai, fin), retrouver la page, et suivre les tendances (score de chaque épreuve, RTF).
CHAMPS_HISTORIQUE = ("id", "debut", "fin", "sha", "sha_complet", "branche", "mode", "essai",
                     "verdict", "bloquant", "rtf", "duree_s", "page", "epreuves")


# --------------------------------------------------------------------------
# Lecture des résultats et décision « due ? »
# --------------------------------------------------------------------------

def score(e: dict) -> str:
    """Score d'UNE épreuve, en clair : « vert 21/21 », « rouge 20/21 1KO », « vert 0.998 »,
    « vert », « non_lance »."""
    texte = e.get("statut", "non_lance")
    if e.get("attendu") is not None:
        texte += " {}/{}".format(e.get("ok", 0), e["attendu"])
        if e.get("ko"):
            texte += " {}KO".format(e["ko"])
    elif e.get("obtenu") is not None:
        texte += " {}".format(e["obtenu"])
    return texte


def ligne_historique(res: dict) -> str:
    """La ligne d'historique d'une fumée (JSON compact, champs dans l'ordre de CHAMPS_HISTORIQUE,
    épreuves dans l'ordre canonique, toujours complètes)."""
    ligne = {cle: res.get(cle) for cle in CHAMPS_HISTORIQUE if cle != "epreuves"}
    ligne["essai"] = bool(res.get("essai"))
    epreuves = res.get("epreuves", [])
    # Une ligne déjà résumée (relue dans l'historique) garde ses scores tels quels.
    ligne["epreuves"] = dict(epreuves) if isinstance(epreuves, dict) else \
        {e["id"]: score(e) for e in completer_epreuves(epreuves)}
    return json.dumps(ligne, ensure_ascii=False) + "\n"


def lire_resultats(sortie: Path) -> list:
    """Les lignes de <sortie>/historique.jsonl, du plus ancien au plus récent (par « fin »). Une
    ligne illisible est ignorée (elle ne doit pas empêcher les fumées suivantes) ; un même id
    écrit deux fois : la dernière ligne gagne."""
    par_id = {}
    try:
        lignes = (sortie / HISTORIQUE).read_text(encoding="utf-8").splitlines()
    except OSError:
        lignes = []
    for texte in lignes:
        try:
            r = json.loads(texte)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("id"):
            par_id[r["id"]] = r
    return sorted(par_id.values(), key=lambda r: r.get("fin") or "")


def ajouter_historique(sortie: Path, res: dict) -> None:
    sortie.mkdir(parents=True, exist_ok=True)
    with open(sortie / HISTORIQUE, "a", encoding="utf-8") as f:
        f.write(ligne_historique(res))


def dernier_vert(resultats: list):
    """La dernière fumée verte NON provoquée, ou None."""
    verts = [r for r in resultats if r.get("verdict") == "vert" and not r.get("essai")]
    return verts[-1] if verts else None


def decider(vert, commits_apres, premier_commit_apres, maintenant, max_jours=SEUIL_JOURS,
            rouges_meme_code=0, sha_code=None):
    """Une fumée est-elle due ? -> (due, raison, depuis).

    vert                  dernier resultat.json vert (dict) ou None
    commits_apres         nombre de commits de main après vert["sha_complet"] touchant un
                          chemin de CHEMINS_TESTES, ou None si ce sha est inconnu du dépôt
    premier_commit_apres  datetime du plus ancien de ces commits, ou None
    maintenant            datetime (avec fuseau)
    rouges_meme_code      fumées ROUGES (hors essais) après la dernière verte dont le sha
                          de code est celui de main aujourd'hui
    sha_code              ce sha de code (pour la raison), ou None
    depuis                datetime depuis lequel elle est due (None si rien n'est dû)

    BLOQUÉE = due par les règles ci-dessus mais déjà rouge ROUGES_MAX_PAR_CODE fois sur ce
    code : due=False, et `depuis` reste renseigné pour que le rappel « > 2 jours » parte.
    """
    raisons, depuis = [], []
    if vert is None:
        raisons.append("aucune fumée verte connue")
        depuis.append(maintenant)
    else:
        fin = datetime.fromisoformat(vert["fin"])
        if commits_apres is None:
            raisons.append("le sha de la dernière fumée verte ({}) est inconnu de main".format(vert["sha"]))
            depuis.append(maintenant)
        elif commits_apres > 0:
            raisons.append("{} commit(s) de code dans main depuis la dernière fumée verte ({})".format(
                commits_apres, vert["sha"]))
            depuis.append(premier_commit_apres or maintenant)
        if maintenant - fin >= timedelta(days=max_jours):
            raisons.append("{} jours sans fumée verte (dernière : {})".format(max_jours, fin.date().isoformat()))
            depuis.append(fin + timedelta(days=max_jours))
        if not raisons:
            return False, "dernière fumée verte {} = code de main, moins de {} jours".format(
                vert["sha"], max_jours), None
    raison, depuis = " ; ".join(raisons), min(depuis)
    code = (sha_code or "?")[:7]
    if rouges_meme_code >= ROUGES_MAX_PAR_CODE:
        return False, "bloquée : {} fumées rouges sur le code {}, plus de relance tant qu'aucun commit " \
                      "de code n'arrive ({})".format(rouges_meme_code, code, raison), depuis
    if rouges_meme_code == 1:
        return True, "relance de confirmation du rouge sur le code {} ; {}".format(code, raison), depuis
    return True, raison, depuis


def rappel_necessaire(depuis, maintenant, jours=RAPPEL_JOURS) -> bool:
    """Décision 2 : due depuis plus de 2 jours (et donc toujours reportée) -> prévenir."""
    return depuis is not None and maintenant - depuis > timedelta(days=jours)


def _git(depot: str, *args: str):
    p = subprocess.run(["git", "-C", depot, *args], capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


def commits_apres_sha(depot: str, sha: str):
    """(nombre, date du plus ancien) des commits de main après `sha` touchant CHEMINS_TESTES.

    (None, None) si `sha` n'existe pas dans le dépôt (réécriture d'historique, clone récent).
    """
    code, _ = _git(depot, "cat-file", "-e", sha + "^{commit}")
    if code != 0:
        return None, None
    code, sortie = _git(depot, "log", "--reverse", "--format=%cI", "{}..main".format(sha),
                        "--", *CHEMINS_TESTES)
    if code != 0:
        return None, None
    dates = [ligne for ligne in sortie.splitlines() if ligne]
    return len(dates), (datetime.fromisoformat(dates[0]) if dates else None)


def sha_de_code(depot: str, rev: str):
    """Le « sha de code » de `rev` : son dernier commit touchant CHEMINS_TESTES, ou None."""
    code, sortie = _git(depot, "log", "-1", "--format=%H", rev, "--", *CHEMINS_TESTES)
    return sortie if code == 0 and sortie else None


def rouges_sur_code(depot: str, resultats: list, vert, code_main):
    """Fumées rouges (hors essais) APRÈS la dernière verte dont le sha de code est `code_main`."""
    if code_main is None:
        return 0
    borne = datetime.fromisoformat(vert["fin"]) if vert is not None else None
    n = 0
    for r in resultats:
        if r.get("verdict") != "rouge" or r.get("essai") or not r.get("fin"):
            continue
        if borne is not None and datetime.fromisoformat(r["fin"]) <= borne:
            continue
        if r.get("sha_complet") and sha_de_code(depot, r["sha_complet"]) == code_main:
            n += 1
    return n


# --------------------------------------------------------------------------
# Épreuves
# --------------------------------------------------------------------------

def statut_compteur(ok, attendu, ko) -> str:
    """vert seulement si le compteur ATTEINT la valeur gravée et sans aucun KO."""
    return "vert" if (ok == attendu and not ko) else "rouge"


def completer_epreuves(epreuves: list) -> list:
    """Épreuves dans l'ordre canonique ; celles qui n'ont pas eu lieu -> non_lance."""
    par_id = {e["id"]: e for e in epreuves}
    complet = [par_id.get(i, {"id": i, "statut": "non_lance"}) for i, _ in EPREUVES]
    complet += [e for e in epreuves if e["id"] not in NOMS]   # id inconnu : on ne perd rien
    return complet


def verdict_global(epreuves: list):
    """(verdict, premier id rouge) ; une épreuve non lancée sans rouge avant = rouge — sauf une
    FACULTATIVE déclarée non lancée par la fumée elle-même (`facultative`, ex. pas de clé)."""
    for e in completer_epreuves(epreuves):
        if e["statut"] == "non_lance" and e.get("facultative") and e["id"] in FACULTATIVES:
            continue
        if e["statut"] != "vert":
            return "rouge", (e["id"] if e["statut"] == "rouge" else None)
    return "vert", None


# --------------------------------------------------------------------------
# Rendu HTML — même feuille de style que docs/veille/ (variables, cartes, pastilles)
# --------------------------------------------------------------------------

CSS = """  :root { --fond:#fbfaf7; --texte:#1f2328; --doux:#5b636b; --trait:#e3e0d8;
          --vert:#1a7f37; --rouge:#cf222e; --orange:#9a6700; --gris:#57606a; --lien:#0b5cad; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--fond); color:var(--texte);
         font:16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
  main { max-width:860px; margin:0 auto; padding:2rem 1.25rem 4rem; }
  header p { color:var(--doux); margin:.2rem 0; }
  h1 { font-size:1.7rem; margin:0 0 .3rem; }
  h2 { font-size:1.25rem; margin:2.2rem 0 .8rem; padding-bottom:.3rem; border-bottom:2px solid var(--trait); }
  a { color:var(--lien); }
  .bandeau { background:#fff; border:1px solid var(--trait); border-left:5px solid var(--gris);
             border-radius:6px; padding:.8rem 1.1rem; margin:1rem 0; }
  .bandeau.b-vert { border-left-color:var(--vert); } .bandeau.b-rouge { border-left-color:var(--rouge); }
  .carte { background:#fff; border:1px solid var(--trait); border-radius:6px; padding:.8rem 1rem; margin:.7rem 0; }
  .carte h3 { margin:0 0 .3rem; font-size:1rem; }
  .meta { font-size:.85rem; color:var(--doux); margin:.2rem 0; }
  .verdict { display:inline-block; font-size:.75rem; font-weight:600; text-transform:uppercase;
             letter-spacing:.03em; padding:.1rem .5rem; border-radius:99px; color:#fff; margin-left:.4rem; vertical-align:middle; }
  .vert { background:var(--vert); } .rouge { background:var(--rouge); }
  .orange { background:var(--orange); } .non_lance { background:var(--gris); }
  table { border-collapse:collapse; width:100%; } th, td { text-align:left; padding:.35rem .5rem; border-bottom:1px solid var(--trait); }
  .doux { color:var(--doux); }
  footer { margin-top:3rem; font-size:.85rem; color:var(--doux); border-top:1px solid var(--trait); padding-top:1rem; }"""


def _e(valeur) -> str:
    return html.escape("" if valeur is None else str(valeur))


def _pastille(statut: str) -> str:
    libelle = {"vert": "vert", "rouge": "rouge", "non_lance": "non lancée"}.get(statut, statut)
    return '<span class="verdict {}">{}</span>'.format(_e(statut), _e(libelle))


def _duree(secondes) -> str:
    if secondes is None:
        return ""
    minutes, sec = divmod(int(secondes), 60)
    return "{} min {:02d} s".format(minutes, sec) if minutes else "{} s".format(sec)


def _debut_lisible(res: dict) -> str:
    return datetime.fromisoformat(res["debut"]).strftime("%d/%m/%Y à %H:%M")


def _squelette(titre: str, corps: str) -> str:
    return ('<!DOCTYPE html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<title>{}</title>\n<style>\n{}\n</style>\n</head>\n<body>\n<main>\n{}\n</main>\n</body>\n</html>\n'
            ).format(_e(titre), CSS, corps)


def rendre_page(res: dict) -> str:
    """La page d'UNE fumée, à partir de son resultat.json."""
    verdict = res.get("verdict", "rouge")
    epreuves = completer_epreuves(res.get("epreuves", []))
    bloquant = res.get("bloquant")
    if verdict == "vert":
        phrase = "Toutes les épreuves sont vertes, aux valeurs gravées."
    elif bloquant:
        phrase = "ROUGE à l'épreuve « {} » : les suivantes n'ont pas été lancées.".format(
            NOMS.get(bloquant, bloquant))
    else:
        phrase = "ROUGE : fumée incomplète (interrompue avant la fin)."
    lignes = []
    for e in epreuves:
        compteur = ""
        if e.get("attendu") is not None:
            compteur = "{} / {} OK, {} KO".format(e.get("ok", 0), e["attendu"], e.get("ko", 0))
        elif e.get("obtenu") is not None:
            compteur = str(e["obtenu"])
        journal = "<code>{}</code>".format(_e(e["journal"])) if e.get("journal") else ""
        lignes.append(
            "<tr><td>{nom}</td><td>{pastille}</td><td>{compteur}</td><td>{duree}</td><td>{journal}</td></tr>"
            "{detail}".format(
                nom=_e(NOMS.get(e["id"], e["id"])), pastille=_pastille(e["statut"]),
                compteur=_e(compteur), duree=_e(_duree(e.get("duree_s"))), journal=journal,
                detail=('<tr><td colspan="5" class="meta">{}</td></tr>'.format(_e(e["detail"]))
                        if e.get("detail") else "")))
    notes = ""
    if res.get("notes"):
        notes = "<h2>Notes</h2><ul>{}</ul>".format("".join("<li>{}</li>".format(_e(n)) for n in res["notes"]))
    essai = ('<p class="meta"><span class="verdict orange">essai provoqué</span> seuil forcé : cette fumée '
             "n'entre jamais dans la décision « due ? ».</p>") if res.get("essai") else ""
    rtf = "{:.2f}".format(res["rtf"]) if res.get("rtf") is not None else "non mesuré"
    corps = """<header>
  <h1>Fumée nocturne — Didier</h1>
  <p><strong>{debut}</strong> · sha testé <code>{sha}</code> (branche {branche}){sale}</p>
  <p>Durée {duree} · mode {mode} · {raison}</p>
</header>
{essai}
<div class="bandeau b-{verdict}"><strong>{pastille}</strong> {phrase}</div>

<p class="meta">Facteur temps réel (sonde 20 s) : <strong>{rtf}</strong> (seuil {rtf_min}) ·
charge 1 min au départ : <strong>{charge}</strong> sur {coeurs} cœurs ·
image sim reconstruite : {image}</p>

<h2>Épreuves</h2>
<table>
<tr><th>Épreuve</th><th>Résultat</th><th>Compteur</th><th>Durée</th><th>Journal</th></tr>
{lignes}
</table>
{notes}
<h2>Journaux</h2>
<p>Bruts, sur le PC de la fumée seulement (ni dans git ni sur Nextcloud) : <code>{brut}/{id}/</code>
(<code>resultat.json</code>, journaux, captures). Vert : purgé après {purge} jours ; rouge : gardé
tant que le dossier ne porte pas le marqueur <code>TRAITE</code>. Résumé permanent :
<code>historique.jsonl</code>.</p>

<footer>Généré par <code>machines/sim/fumee.sh</code> (lot F, zéro token) · <a href="index.html">toutes les fumées</a></footer>""".format(
        debut=_e(_debut_lisible(res)), sha=_e(res.get("sha")), branche=_e(res.get("branche")),
        sale=" — <strong>arbre modifié au départ</strong>" if res.get("sale") else "",
        duree=_e(_duree(res.get("duree_s"))), mode=_e(res.get("mode")), raison=_e(res.get("raison")),
        essai=essai, verdict=_e(verdict), pastille=_pastille(verdict), phrase=_e(phrase),
        rtf=_e(rtf), rtf_min=_e(res.get("rtf_min")), charge=_e(res.get("charge_1min")),
        coeurs=_e(res.get("nb_coeurs")), image="oui" if res.get("image_reconstruite") else "non",
        lignes="\n".join(lignes), notes=notes, id=_e(res["id"]),
        brut=_e(res.get("brut") or "~/tmp/didier-fumee"), purge=PURGE_JOURS)
    return _squelette("Fumée Didier — {} — {}".format(_debut_lisible(res), verdict), corps)


def rendre_index(resultats: list) -> str:
    """Le sommaire : la plus récente en tête."""
    if resultats:
        lignes = []
        for r in sorted(resultats, key=lambda x: x.get("fin", ""), reverse=True):
            rtf = "{:.2f}".format(r["rtf"]) if r.get("rtf") is not None else "—"
            essai = ' <span class="verdict orange">essai</span>' if r.get("essai") else ""
            lignes.append(
                '<tr><td><a href="{page}">{debut}</a></td><td>{pastille}{essai}</td><td><code>{sha}</code></td>'
                "<td>{rtf}</td><td>{duree}</td></tr>".format(
                    page=_e(r.get("page")), debut=_e(_debut_lisible(r)), pastille=_pastille(r.get("verdict", "rouge")),
                    essai=essai, sha=_e(r.get("sha")), rtf=_e(rtf), duree=_e(_duree(r.get("duree_s")))))
        tableau = ("<table>\n<tr><th>Date</th><th>Verdict</th><th>Sha testé</th><th>RTF</th><th>Durée</th></tr>\n"
                   + "\n".join(lignes) + "\n</table>")
    else:
        tableau = '<p class="doux">Aucune fumée pour l\'instant.</p>'
    corps = ("<h1>Fumée nocturne — Didier</h1>\n"
             '<p class="doux">La plus récente en tête. Comment ça décide et comment lire une page : '
             "<code>docs/operations.md</code>, section « Fumée automatique ».</p>\n"
             + tableau + "\n")
    return _squelette("Fumée nocturne Didier — sommaire", corps)


def ecrire_pages(sortie: Path, brut: Path | None = None) -> None:
    """Régénère le sommaire (depuis l'historique) et les pages dont le resultat.json complet est
    encore dans le brut local (les autres pages, versionnées, restent telles quelles)."""
    resultats = lire_resultats(sortie)
    if brut is not None:
        for r in resultats:
            complet = brut / r["id"] / "resultat.json"
            if r.get("page") and complet.exists():
                (sortie / r["page"]).write_text(
                    rendre_page(json.loads(complet.read_text(encoding="utf-8"))), encoding="utf-8")
    (sortie / "index.html").write_text(rendre_index(resultats), encoding="utf-8")


def a_purger(res, traite: bool, maintenant, jours=PURGE_JOURS) -> bool:
    """Le brut d'une fumée part-il ? VERT au-delà de `jours` ; ROUGE (ou tout ce qui n'est pas
    vert, illisible compris) seulement s'il est marqué TRAITE et au-delà de `jours`."""
    if not res or not res.get("fin"):
        return False
    try:
        age = maintenant - datetime.fromisoformat(res["fin"])
    except ValueError:
        return False
    if age <= timedelta(days=jours):
        return False
    return res.get("verdict") == "vert" or traite


def purger(brut: Path, maintenant, jours=PURGE_JOURS) -> list:
    """Applique a_purger à chaque <brut>/<id>/ ; rend les id supprimés."""
    partis = []
    if not brut.is_dir():
        return partis
    for dossier in sorted(p for p in brut.iterdir() if p.is_dir()):
        try:
            res = json.loads((dossier / "resultat.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue   # sans resultat.json lisible : on ne sait pas, on garde
        if a_purger(res, (dossier / MARQUEUR_TRAITE).exists(), maintenant, jours):
            shutil.rmtree(dossier)
            partis.append(dossier.name)
    return partis


def nom_de_page(sortie: Path, id_fumee: str) -> str:
    """AAAA-MM-JJ.html, puis AAAA-MM-JJ-2.html, -3… si plusieurs le même jour."""
    jour = id_fumee[:10]
    pris = {r.get("page") for r in lire_resultats(sortie) if r.get("id") != id_fumee}
    candidat, n = "{}.html".format(jour), 1
    while candidat in pris:
        n += 1
        candidat = "{}-{}.html".format(jour, n)
    return candidat


# --------------------------------------------------------------------------
# Sous-commandes (appelées par fumee.sh)
# --------------------------------------------------------------------------

def _maintenant(texte):
    return datetime.fromisoformat(texte) if texte else datetime.now().astimezone()


def cmd_due(args) -> int:
    sortie, maintenant = Path(args.sortie), _maintenant(args.maintenant)
    resultats = lire_resultats(sortie)
    vert = dernier_vert(resultats)
    nombre, premier = (None, None)
    if vert is not None:
        nombre, premier = commits_apres_sha(args.depot, vert["sha_complet"])
    code_main = sha_de_code(args.depot, "main")
    due, raison, depuis = decider(vert, nombre, premier, maintenant,
                                  rouges_meme_code=rouges_sur_code(args.depot, resultats, vert, code_main),
                                  sha_code=code_main)
    # Une seule ligne, champs séparés par des tabulations : état, raison, depuis, rappel.
    # « bloquee » (code 1, rien n'est lancé) garde son `depuis` : fumee.sh fait partir le rappel.
    etat = "due" if due else ("bloquee" if depuis else "pas_due")
    print("\t".join([etat, raison, depuis.isoformat() if depuis else "",
                     "oui" if rappel_necessaire(depuis, maintenant) else "non"]))
    return 0 if due else 1


def cmd_dernier_vert(args) -> int:
    vert = dernier_vert(lire_resultats(Path(args.sortie)))
    if vert is not None:
        print(vert["sha_complet"])
    return 0


def cmd_epreuve(args) -> int:
    """Ajoute une épreuve (une ligne JSON) au fichier de travail de la fumée en cours."""
    e = {"id": args.id}
    if args.attendu is not None:
        e.update(ok=args.ok or 0, attendu=args.attendu, ko=args.ko or 0)
        e["statut"] = args.statut or statut_compteur(e["ok"], e["attendu"], e["ko"])
    else:
        if not args.statut:
            sys.exit("epreuve : --statut ou --attendu est requis")
        e["statut"] = args.statut
    for cle, val in (("obtenu", args.obtenu), ("detail", args.detail), ("duree_s", args.duree),
                     ("journal", args.journal)):
        if val is not None:
            e[cle] = val
    if args.facultative:
        if args.id not in FACULTATIVES:
            sys.exit(f"epreuve : {args.id!r} n'est pas une épreuve facultative ({sorted(FACULTATIVES)})")
        e["facultative"] = True
    with open(args.jsonl, "a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return 0


def _convertir(cle: str, texte: str):
    if cle in ("rtf", "rtf_min", "charge_1min"):
        return float(texte) if texte not in ("", "null") else None
    if cle in ("duree_s", "nb_coeurs"):
        return int(texte)
    if cle in ("sale", "essai", "image_reconstruite"):
        return texte == "1"
    return texte


def cmd_finaliser(args) -> int:
    """Assemble resultat.json, écrit la page et le sommaire ; imprime le nom de la page."""
    sortie = Path(args.sortie)
    epreuves = []
    if Path(args.jsonl).exists():
        epreuves = [json.loads(l) for l in Path(args.jsonl).read_text(encoding="utf-8").splitlines() if l.strip()]
    res = {"version": VERSION, "id": args.id, "notes": [n for n in args.note or []]}
    for paire in args.meta or []:
        cle, _, val = paire.partition("=")
        res[cle] = _convertir(cle, val)
    res["epreuves"] = epreuves
    res["verdict"], res["bloquant"] = verdict_global(epreuves)
    res["page"] = nom_de_page(sortie, args.id)
    brut = Path(args.brut)
    res["brut"] = args.brut_affiche or str(brut)
    dossier = brut / args.id
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "resultat.json").write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ajouter_historique(sortie, res)
    (sortie / res["page"]).write_text(rendre_page(res), encoding="utf-8")
    ecrire_pages(sortie)
    print(res["page"])
    return 0


def cmd_pages(args) -> int:
    ecrire_pages(Path(args.sortie), Path(args.brut) if args.brut else None)
    return 0


def cmd_purger(args) -> int:
    for ident in purger(Path(args.brut), _maintenant(args.maintenant), args.jours):
        print("purgé : {}".format(ident))
    return 0


def cmd_amorcer(args) -> int:
    """Amorce historique.jsonl depuis d'anciens <dossier>/*/resultat.json (journaux versionnés
    jusqu'au 16/11) ; un id déjà présent n'est pas réécrit."""
    sortie = Path(args.sortie)
    connus = {r["id"] for r in lire_resultats(sortie)}
    anciens = []
    for f in Path(args.depuis).glob("*/resultat.json"):
        try:
            anciens.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    n = 0
    for res in sorted(anciens, key=lambda r: r.get("fin") or ""):
        if res.get("id") and res["id"] not in connus:
            ajouter_historique(sortie, res)
            n += 1
    ecrire_pages(sortie)
    print("{} fumée(s) ajoutée(s) à l'historique".format(n))
    return 0


def construire_parseur() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("due", help="une fumée est-elle due ? (code 0 = due, 1 = pas due)")
    s.add_argument("--sortie", required=True)
    s.add_argument("--depot", required=True)
    s.add_argument("--maintenant", help="ISO 8601 (tests)")
    s.set_defaults(fn=cmd_due)
    s = sub.add_parser("dernier-vert", help="sha complet de la dernière fumée verte")
    s.add_argument("--sortie", required=True)
    s.set_defaults(fn=cmd_dernier_vert)
    s = sub.add_parser("epreuve", help="ajoute une épreuve au fichier de travail")
    s.add_argument("--jsonl", required=True)
    s.add_argument("--id", required=True)
    s.add_argument("--statut", choices=["vert", "rouge", "non_lance"])
    s.add_argument("--ok", type=int)
    s.add_argument("--attendu", type=int)
    s.add_argument("--ko", type=int)
    s.add_argument("--obtenu")
    s.add_argument("--detail")
    s.add_argument("--duree", type=int)
    s.add_argument("--journal")
    s.add_argument("--facultative", action="store_true",
                   help="épreuve de FACULTATIVES non lancée faute de prérequis : ne rougit pas la fumée")
    s.set_defaults(fn=cmd_epreuve)
    s = sub.add_parser("finaliser", help="écrit resultat.json + page + sommaire")
    s.add_argument("--jsonl", required=True)
    s.add_argument("--sortie", required=True)
    s.add_argument("--id", required=True)
    s.add_argument("--brut", required=True, help="dossier LOCAL des journaux bruts (<brut>/<id>/)")
    s.add_argument("--brut-affiche", help="ce chemin, tel qu'affiché sur la page (~ au lieu du HOME)")
    s.add_argument("--meta", action="append", help="clé=valeur (sha, mode, rtf…)")
    s.add_argument("--note", action="append")
    s.set_defaults(fn=cmd_finaliser)
    s = sub.add_parser("pages", help="régénère le sommaire (et les pages encore dans le brut)")
    s.add_argument("--sortie", required=True)
    s.add_argument("--brut")
    s.set_defaults(fn=cmd_pages)
    s = sub.add_parser("purger", help="supprime le brut des vertes > 30 j (rouges : seulement si TRAITE)")
    s.add_argument("--brut", required=True)
    s.add_argument("--jours", type=int, default=PURGE_JOURS)
    s.add_argument("--maintenant", help="ISO 8601 (tests)")
    s.set_defaults(fn=cmd_purger)
    s = sub.add_parser("amorcer", help="amorce historique.jsonl depuis d'anciens resultat.json")
    s.add_argument("--sortie", required=True)
    s.add_argument("--depuis", required=True)
    s.set_defaults(fn=cmd_amorcer)
    return p


def main(argv=None) -> int:
    args = construire_parseur().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
