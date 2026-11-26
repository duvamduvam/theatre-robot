"""Une épreuve et son verdict (F1, 25/11, spec §3-4) : vert, rouge (compteur faux, banc sain) ou
invalide (un gardien a parlé). Une invalide est rejouée SEULE, deux fois au plus ; une rouge jamais.
Un rouge n'arrête plus la fumée : seules les épreuves `bloque = ["*"]` arrêtent ce qui suit.
"""
import re
import time
from pathlib import Path

from . import images
from .gardiens import PERIODE_S, REJEUX_MAX, Arret, chaleur, refroidir, rejouable
from .sim import Sim

SECRET_ANTHROPIC = Path.home() / ".config/didier/secrets.env"
SECRET_OPENROUTER = Path.home() / ".config/didier/vision-conf-secret"


class Contexte:
    """L'état d'UNE fumée ; `sy` est le seul accès au système (faux en test)."""

    def __init__(self, sy, arbre, ici, tmp, jdir, ident, etat, hors_ligne=False, rtf_min=0.8):
        self.sy, self.arbre, self.ici, self.tmp, self.jdir, self.id, self.etat = sy, arbre, ici, tmp, jdir, ident, etat
        self.hors_ligne, self.rtf_min, self.rtf, self.image_reconstruite = hors_ligne, rtf_min, None, False
        self.notes, self.coeurs, self._sims, self._maintenu = [], sy.env.get("FUMEE_COEURS", "8-15"), [], None
        self.sim = Sim(self)

    def _coeurs(self, action, *sims):
        cmd = ["python3", str(self.ici / "coeurs_reserves.py"), action, "--etat", str(self.etat / "coeurs.json")]
        return self.sy.sortie(cmd + (["--coeurs", self.coeurs] if action != "liberer" else []) +
                              [a for c in sims for a in ("--sim", c)])

    def epingler(self, conteneurs):
        """La sim sur les cœurs réservés (FUMEE_COEURS, vide = rien), le reste du PC ailleurs."""
        if not self.coeurs:
            return
        for c in conteneurs:
            if self.sy.sortie(["docker", "update", "--cpuset-cpus", self.coeurs, c])[0] != 0:
                self.notes.append("cœurs réservés : épinglage de {} refusé par docker".format(c))
                return
        if not self._sims:
            self._coeurs("liberer")   # reliquat d'une fumée tuée
            self._coeurs("reserver", *conteneurs)
        self._sims = list(conteneurs)

    def liberer_coeurs(self):
        if (self.etat / "coeurs.json").exists():
            self._coeurs("liberer")
        self._sims = []

    def pause(self, secondes):
        """Toute attente passe ici : 88 °C arrête la fumée ; les cœurs sont maintenus (15 s)."""
        if chaleur(self.sy.temperature()) == "arret":
            raise Arret("chaleur : paquet CPU ≥ 88 °C, fumée arrêtée (jamais au-delà de 90 °C)")
        self.sy.dormir(secondes)
        maintenant = self.sy.horloge()
        if self._sims and (self._maintenu is None or maintenant - self._maintenu >= 15):
            self._coeurs("maintenir", *self._sims)
            self._maintenu = maintenant


def verdict_script(texte, rc, ep, gardien=None) -> dict:
    """Verdict d'une épreuve script à partir de son journal (motif de la ligne « N OK, M KO »)."""
    r = {"id": ep.id, "attendu": ep.attendu, "ok": 0, "ko": 0, "journal": ep.id + ".log"}
    lignes = [l for l in texte.splitlines() if re.search(ep.motif, l)]
    compte = re.findall(r" ([0-9]+) OK, ([0-9]+) KO", lignes[-1]) if lignes else []
    if gardien:
        return {**r, "statut": "invalide", "detail": "invalide : " + gardien}
    if not compte and "mesure invalide" in texte.lower():
        return {**r, "statut": "invalide", "detail": "invalide : enregistreur des captures mort (MESURE INVALIDE, "
                                                     "code {}) — défaut du banc, pas de Didier".format(rc)}
    if not compte:
        return {**r, "statut": "rouge", "detail": "aucun compteur lu en fin de script (code {}) : précondition, "
                                                  "délai dépassé ou crash — voir le journal".format(rc)}
    ok, ko = (int(x) for x in compte[-1])
    r.update(ok=ok, ko=ko, statut="vert" if ok == ep.attendu and ko == 0 else "rouge")
    if rc != 0 and r["statut"] == "vert":
        r.update(statut="rouge", detail="compteur conforme mais code de retour {}".format(rc))
    return r


def executer_script(f, ep) -> dict:
    """Le script dans monde, gardiens interrogés toutes les 5 s ; chaud = l'épreuve est tuée."""
    journal, cap = f.tmp / (ep.id + ".log"), "/home/ros2_ws/log/captures/fumee-{}-{}".format(f.id, ep.id)
    proc = f.sy.lancer(["timeout", "-k", "15", str(ep.delai_s + 60), "docker", "exec", "-e", "CAPTURE_DIR=" + cap,
                        "didier-sim-monde", "timeout", "-k", "10", str(ep.delai_s), "bash",
                        "/home/ros2_ws/" + ep.script], journal)
    gardien = None
    try:
        while proc.poll() is None:
            t = f.sy.temperature()
            if chaleur(t) == "chaud":
                gardien = "chaleur : paquet CPU à {:.0f} °C pendant l'épreuve".format(t)
                break
            f.pause(PERIODE_S)
    finally:
        if proc.poll() is None:
            f.sy.tuer(proc)
    f.sim.copier_captures(ep.id, cap)
    return verdict_script(journal.read_text(encoding="utf-8", errors="replace"), proc.poll(), ep, gardien)


def tete_possible(f):
    """Prérequis de la tête (CONV) : sa raison de « non lancée », ou None. Présence seule des clés."""
    if f.hors_ligne or not f.sy.joignable("api.anthropic.com"):
        return "non lancée (hors ligne)"
    try:
        cle = any(l.startswith("ANTHROPIC_API_KEY=") and len(l) > 18 for l in SECRET_ANTHROPIC.read_text().splitlines())
    except OSError:
        cle = False
    return None if cle and SECRET_OPENROUTER.is_file() else "non lancée (pas de clé Anthropic ou OpenRouter)"


def une_fois(f, ep) -> dict:
    if ep.id == "image":
        return images.phase(f)
    if ep.id == "demarrage":
        return f.sim.preparer(ep, sonder=False) or {"id": ep.id, "statut": "vert", "journal": "demarrage.log",
                                                    "detail": "4 conteneurs, domaine 43 dans chacun, colcon ×4, nœuds "
                                                              "attendus, monde {}, headless".format(ep.cle_sim[0])}
    if ep.id == "rtf":
        return f.sim.preparer(ep, sonder=False) or f.sim.sonder(ep.id)
    if (ep.sim or {}).get("tete") and (raison := tete_possible(f)):
        return {"id": ep.id, "statut": "non_lance", "facultative": ep.facultative, "detail": raison}
    panne = f.sim.preparer(ep)
    if panne:
        return {**panne, "id": ep.id}
    f.sim.servie = True
    if ep.id == "parle":
        rc, texte = f.sim.sonde("parle")
        (f.tmp / "parle.log").write_text(texte, encoding="utf-8")
        ok = int((re.findall(r"^PARLE ([0-9]+) OK", texte, re.M) or ["0"])[-1])
        return {"id": ep.id, "ok": ok, "attendu": ep.attendu, "ko": ep.attendu - ok, "journal": "parle.log",
                "statut": "vert" if ok == ep.attendu else "rouge",
                "detail": (re.findall(r"^ETATS=.*$", texte, re.M) or [""])[-1]}
    if ep.corps_sur_arme:
        refus = f.sim.corps_sur_arme(ep.id)
        if refus:
            return refus
        avant = f.sim.verrous()[0]
    r = executer_script(f, ep)
    if ep.corps_sur_arme and (v := f.sim.verrous())[0] > avant:
        f.notes.append("{} : le corps sûr du bringup s'est verrouillé PENDANT l'épreuve ({})".format(ep.id, v[1]))
    if (ep.sim or {}).get("tete"):
        n = f.sy.sortie(["docker", "logs", "didier-sim-vision"])[1].count("bascule de secours")
        if n:
            f.notes.append("{} : {} bascule(s) de secours Anthropic → OpenRouter".format(ep.id, n))
    return r


def dit(texte: str) -> None:
    """Une ligne de progression datée sur la sortie (F1, 26/11 : la 1re fumée n'affichait rien
    avant la fin ; fumee.sh annonçait chaque étape). flush : le journal se lit en direct."""
    print("[fumée {}] {}".format(time.strftime("%H:%M:%S"), texte), flush=True)


def resume(r: dict) -> str:
    compte = " {}/{}".format(r["ok"], r["attendu"]) if "attendu" in r and "ok" in r else ""
    return "{}{}{}".format(r["statut"], compte, " — " + r["detail"] if r.get("detail") else "")


def jouer(f, ep) -> dict:
    """L'épreuve, rejouée seule si un gardien l'a invalidée : sim arrêtée, PC refroidi, sim neuve."""
    debut = f.sy.horloge()
    for essai in range(REJEUX_MAX + 1):
        # Avant un rejeu, toujours sous 80 °C ; avant le premier essai, seulement si le PC est chaud.
        if (essai or chaleur(f.sy.temperature())) and not refroidir(f):
            r = {"id": ep.id, "statut": "invalide", "detail": "invalide : chaleur, PC pas redescendu sous 80 °C en 20 min"}
            break
        dit("épreuve {}{}".format(ep.id, " (rejeu {})".format(essai) if essai else ""))
        r = une_fois(f, ep)
        dit("  {} : {}".format(ep.id, resume(r)))
        if not rejouable(r) or essai == REJEUX_MAX:
            break
        f.notes.append("{} invalide ({}) : rejouée seule ({}/{})".format(ep.id, r.get("detail"), essai + 1, REJEUX_MAX))
        f.sim.arreter(ep.id)
    if essai:
        r["detail"] = "{} — après {} rejeu(x)".format(r.get("detail") or r["statut"], essai)
    r.setdefault("duree_s", int(f.sy.horloge() - debut))
    return r


def derouler(f, plan) -> list:
    """Les résultats, dans l'ordre du plan. Un 88 °C ou un domaine ≠ 43 arrête tout (Arret)."""
    resultats, bloquees = [], {}
    for ep in plan:
        if ep.id in bloquees:
            dit("épreuve {} non lancée (« {} » n'est pas verte)".format(ep.id, bloquees[ep.id]))
            resultats.append({"id": ep.id, "statut": "non_lance",
                              "detail": "non lancée : « {} » n'est pas verte".format(bloquees[ep.id])})
            continue
        try:
            r = jouer(f, ep)
        except Arret as arret:
            f.notes.append(str(arret))
            resultats.append({"id": ep.id, "statut": "invalide", "detail": "invalide : " + str(arret)})
            bloquees = {e.id: ep.id for e in plan}
            continue
        resultats.append(r)
        if r["statut"] != "vert" and not (r["statut"] == "non_lance" and r.get("facultative")):
            vise = [e.id for e in plan if "*" in ep.bloque or e.id in ep.bloque]
            bloquees.update({i: ep.id for i in vise if i not in bloquees and i not in {x["id"] for x in resultats}})
    return resultats
