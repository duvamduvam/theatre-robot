"""python3 -m fumee (depuis machines/sim/) — le programme de fumée, lot F1 (25/11).

    python3 -m fumee [--rev <branche|sha|#PR>] [--epreuves a1,objets | --tout | --reprendre]
                     [--hors-ligne] [--minuterie] [--forcer-verrou] [--essai]

Codes : 0 vert (ou reporté, ou pas due) ; 1 rouge ; 2 refus ; 3 invalide. Spec :
docs/spec-F1-programme-fumee.md ; mode d'emploi : docs/operations.md, « Fumée automatique ».
« Et dodo » (extinction) reste dans fumee.sh : ce programme n'éteint JAMAIS le PC.
"""
import argparse
import os
import shutil
import signal
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from . import banc, plan as plans, rapport
from .banc import Refus, Systeme
from .epreuve import Contexte, derouler
from .gardiens import RTF_MIN

ICI = Path(__file__).resolve().parents[1]   # machines/sim du programme
DEPOT_DEFAUT = "/home/dadou/Nextcloud/dev/didier/python/theatre-robot"
CODES = {"vert": 0, "rouge": 1, "invalide": 3}


def options(argv):
    p = argparse.ArgumentParser(prog="python3 -m fumee", description=__doc__.splitlines()[0])
    p.add_argument("--rev", default="origin/main", help="branche, sha ou #PR (défaut origin/main à jour)")
    choix = p.add_mutually_exclusive_group()
    choix.add_argument("--epreuves", help="ids séparés par des virgules (le socle image, demarrage, rtf est ajouté)")
    choix.add_argument("--tout", action="store_true", help="tout le plan (défaut)")
    choix.add_argument("--reprendre", action="store_true",
                       help="reprend la dernière fumée de CETTE révision : vertes gardées, le reste rejoué")
    p.add_argument("--hors-ligne", action="store_true", help="aussi détecté seul (DNS de github.com)")
    p.add_argument("--minuterie", action="store_true", help="seulement si due ; banc pas sain = reporté sans page")
    p.add_argument("--forcer-verrou", action="store_true", help="passe outre ~/tmp/didier/sim-occupee")
    p.add_argument("--essai", action="store_true", help="jamais référence, jamais commitée")
    o = p.parse_args(argv)
    if o.minuterie and o.forcer_verrou:
        p.error("--forcer-verrou ne vaut que pour une fumée lancée à la main")
    return o


def main(argv=None, sy=None) -> int:
    o, sy = options(argv), sy or Systeme()
    env, maintenant = sy.env, datetime.now().astimezone()
    depot = Path(env.get("FUMEE_DEPOT", DEPOT_DEFAUT))
    # 26/11 (1re vraie fumée F1) : un ESSAI (ou une sélection d'épreuves) avait écrit sa page et
    # son historique dans docs/fumee du checkout de David. Ses pages vont désormais hors du dépôt ;
    # seule une fumée de référence écrit dans docs/fumee (et seule elle peut y être commitée).
    essai = o.essai or bool(o.epreuves)
    sortie_defaut = (Path.home() / "tmp/didier/fumee-essais") if essai else depot / "docs" / "fumee"
    sortie = Path(env.get("FUMEE_SORTIE", sortie_defaut))
    etat = Path(env.get("FUMEE_ETAT", Path.home() / ".local/state/didier-fumee"))
    brut = Path(env.get("FUMEE_BRUT", Path.home() / "tmp/didier/fumee-brut"))
    arbre = Path(env.get("FUMEE_ARBRE", Path.home() / "tmp/didier/fumee-arbre"))
    occupee = Path(env.get("FUMEE_SIM_OCCUPEE", Path.home() / "tmp/didier/sim-occupee"))
    rtf_min = float(env.get("FUMEE_RTF_MIN", RTF_MIN))
    etat.mkdir(parents=True, exist_ok=True)
    # SIGTERM (systemctl stop) : le ménage se fait dans `finally`, SANS récolte des journaux
    # (26/11 : la récolte, longue, était tuée par systemd avant le `down` — 4 conteneurs et le
    # verrou restaient en place). Lancer de préférence avec `-p KillMode=mixed` (operations.md).
    interrompu = []
    signal.signal(signal.SIGTERM, lambda *_: (interrompu.append(True), sys.exit(143)))
    try:
        le_plan = plans.lire()
        choisis = plans.choisir(le_plan, o.epreuves.split(",") if o.epreuves else None)
        verrou = banc.prendre_flock(etat, 0 if o.minuterie else float(env.get("FUMEE_VERROU_ATTENTE", "60")))
    except plans.PlanInvalide as erreur:
        print("fumée : " + str(erreur), file=sys.stderr)
        return 2
    except Refus as refus:
        return 0 if o.minuterie else _refus(etat, refus)
    hors_ligne = o.hors_ligne or not sy.joignable("github.com")
    raison = "lancée à la main" + (" (hors ligne)" if hors_ligne else "")
    if o.minuterie:
        rc, ligne = sy.sortie(["python3", str(ICI / "fumee_page.py"), "due", "--sortie", str(sortie), "--depot", str(depot)])
        if rc != 0:
            return 0 if rc == 1 else _refus(etat, Refus("décision « due ? » en erreur : " + ligne.strip()))
        raison = "due : " + ligne.split("\t")[1]
    tmp, contenu_verrou, profil, f = Path(tempfile.mkdtemp(prefix="didier-fumee.")), None, None, None
    try:
        charge = float(Path("/proc/loadavg").read_text().split()[0])
        if o.minuterie and charge > float(env.get("FUMEE_CHARGE_MAX", (os.cpu_count() or 1) * 0.5)):
            raise Refus("charge trop haute ({})".format(charge))
        notes = []
        contenu_verrou = banc.verrou_sim(occupee, o.forcer_verrou, notes)
        banc.conteneurs_libres(sy)
        sha, branche = banc.preparer_arbre(sy, depot, arbre, o.rev, hors_ligne)
        # 26/11 : le plan (valeurs attendues comprises) est celui de la RÉVISION TESTÉE, pas celui du
        # checkout d'où le programme tourne (A1 attendait 14 sur main, 17 dans la branche S1 testée).
        plan_rev = arbre / "machines" / "sim" / "fumee" / "plan.toml"
        if plan_rev.is_file():
            try:
                le_plan = plans.lire(plan_rev)
                choisis = plans.choisir(le_plan, o.epreuves.split(",") if o.epreuves else None)
            except plans.PlanInvalide as erreur:
                raise Refus("plan de la révision testée : {}".format(erreur)) from None
        gardees, reprise = {}, None
        if o.reprendre:
            reprise = rapport.a_reprendre(brut, sha)
            if reprise is None:
                raise Refus("rien à reprendre pour ce sha ({}) : aucune fumée de cette révision dans {}".format(sha[:7], brut))
            gardees = {e["id"]: e for e in reprise["epreuves"] if e["statut"] == "vert" and e["id"] not in plans.SOCLE}
            a_rejouer = [e.id for e in le_plan if e.id not in gardees and e.id not in plans.SOCLE]
            if not a_rejouer:
                raise Refus("rien à reprendre : la fumée {} de ce sha est toute verte".format(reprise["id"]))
            choisis = plans.choisir(le_plan, a_rejouer)
            notes.append("reprise de la fumée {} : {} épreuves gardées".format(reprise["id"], len(gardees)))
        ident = maintenant.strftime("%Y-%m-%d-%H%M") + ("" if not (brut / maintenant.strftime("%Y-%m-%d-%H%M")).exists()
                                                       else maintenant.strftime("%S"))
        jdir = brut / ident
        jdir.mkdir(parents=True)
        f = Contexte(sy, arbre, ICI, tmp, jdir, ident, etat, hors_ligne, rtf_min)
        f.notes += notes
        banc.autorite_x(sy, etat, f.notes)
        profil = banc.basculer_profil(sy, etat)
        avant = sy.sortie(["git", "-C", str(arbre), "status", "--porcelain"])[1]
        banc.journal(etat, "début fumée {} sur {} ({}) — {}".format(ident, sha[:7], o.rev, raison))
        resultats = derouler(f, choisis)
        f.sim.arreter("fin")
        if o.minuterie and any(r["id"] == "rtf" and r["statut"] == "invalide" for r in resultats):
            shutil.rmtree(jdir, ignore_errors=True)
            raise Refus("temps réel trop bas (RTF {}) : PC trop occupé".format(f.rtf))
        if sy.sortie(["git", "-C", str(arbre), "status", "--porcelain"])[1] != avant:
            f.notes.append("l'arbre de travail de la fumée a changé PENDANT la fumée (résidu d'un script ?)")
        if sy.sortie(["systemctl", "is-system-running"])[1].strip() == "stopping":   # lecture SEULE
            f.notes.append("le PC s'éteignait à la fin de la fumée : la dernière épreuve en a souffert")
        if reprise:
            resultats = rapport.fusionner(le_plan, gardees, resultats)
        partielle = [r["id"] for r in resultats] != [e.id for e in le_plan]
        if partielle:   # une sélection ne dit rien du reste : jamais la « dernière verte »
            f.notes.append("fumée partielle ({}) : marquée essai, jamais référence".format(
                ", ".join(r["id"] for r in resultats if r["id"] not in plans.SOCLE)))
        meta = {"sha": sha[:7], "sha_complet": sha, "sale": False, "branche": branche,
                "mode": "minuterie" if o.minuterie else "force", "raison": raison,
                "debut": maintenant.isoformat(timespec="seconds"),
                "fin": datetime.now().astimezone().isoformat(timespec="seconds"),
                "duree_s": int((datetime.now().astimezone() - maintenant).total_seconds()), "rtf": f.rtf,
                "rtf_min": rtf_min, "charge_1min": charge, "nb_coeurs": os.cpu_count(),
                "essai": o.essai or partielle or env.get("FUMEE_ESSAI") == "1" or rtf_min != RTF_MIN,
                "image_reconstruite": f.image_reconstruite, "coeurs_reserves": f.coeurs or "aucun",
                "programme": "fumee F1", "hors_ligne": hors_ligne, "reprise_de": reprise and reprise["id"]}
        res = rapport.finaliser(f, sortie, brut, meta, resultats)
        quoi = (rapport.commiter(sy, depot, res) if env.get("FUMEE_COMMIT", "1") == "1" and sortie == sortie_defaut
                else "page non commitée (FUMEE_COMMIT ou FUMEE_SORTIE)")
        banc.journal(etat, "fin fumée {} : {}, page {}, {}".format(ident, res["verdict"], res["page"], quoi))
        print("[fumée] {} — page {}/{}, brut {} ; {}".format(res["verdict"], sortie, res["page"], jdir, quoi))
        return CODES[res["verdict"]]
    except Refus as refus:
        if o.minuterie:
            banc.journal(etat, "reporté : {}".format(refus))
            return 0
        return _refus(etat, refus)
    finally:
        if f is not None:
            if interrompu:
                f.sim.arreter_sans_recolte()
            else:
                f.sim.arreter("fin")   # idempotent : journaux récoltés avant l'arrêt
            f.liberer_coeurs()
        banc.restaurer_profil(sy, etat, profil)
        banc.liberer_verrou_sim(occupee, contenu_verrou)
        shutil.rmtree(tmp, ignore_errors=True)
        os.close(verrou)


def _refus(etat, refus) -> int:
    banc.journal(etat, "refus : {}".format(refus))
    print("fumée : REFUS — {}".format(refus), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
