"""Le banc (F1, 25/11) : la SEULE porte vers le système (classe Systeme, remplacée par un faux en
test), et les règles de fumee.sh reprises sans changement : flock, verrou « sim occupée », sim de
quelqu'un d'autre jamais touchée, profil d'énergie (réglage « auto » depuis le 28/11), autorité X,
arbre de travail à nous.
"""
import fcntl
import os
import signal
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path

PEREMPTION_SIM_OCCUPEE_S = 6 * 3600   # au-delà, un sim-occupee oublié ne bloque plus (jamais effacé)
COMPOSE = Path(__file__).resolve().parents[1] / "docker-compose.yml"


def services_du_compose(chemin=COMPOSE):
    """Les services du compose de la sim, dans l'ordre du fichier (lot L3a, spec L3 décision 21).

    Lecture en stdlib, sans PyYAML (le programme tourne sur l'hôte, hors venv) : les clés à deux
    espaces sous `services:`, jusqu'à la prochaine clé de premier niveau. Le compose est écrit
    à la main et gravé par test_arborescence.py ; ce lecteur n'a pas à comprendre plus."""
    services, dedans = [], False
    for brute in Path(chemin).read_text(encoding="utf-8").splitlines():
        ligne = brute.split(" #")[0].rstrip()          # commentaire de fin de ligne retiré
        if not ligne.strip() or ligne.lstrip().startswith("#"):
            continue
        if not ligne[0].isspace():
            dedans = ligne == "services:"
        elif dedans and ligne.startswith("  ") and not ligne[2].isspace() and ligne.endswith(":"):
            services.append(ligne.strip()[:-1])
    return tuple(services)


# Un conteneur par service, `didier-sim-<service>` : ajouter un service au compose suffit (L3b, sono).
CONTENEURS = tuple("didier-sim-" + s for s in services_du_compose())


class Refus(Exception):
    """Précondition non remplie : rien n'est lancé, code 2 (ou 0 « reporté » en minuterie)."""


class Systeme:
    """Docker, git, sensors, horloge : tout appel système passe par ici (spec §7)."""

    def __init__(self, env=None):
        self.env = dict(os.environ if env is None else env)

    def sortie(self, cmd, entree=None, cwd=None, env=None, delai=None):
        try:
            p = subprocess.run(cmd, input=entree, cwd=cwd, env={**self.env, **(env or {})},
                               capture_output=True, text=True, timeout=delai)
        except (OSError, subprocess.TimeoutExpired) as erreur:
            return 124, str(erreur)
        return p.returncode, p.stdout + p.stderr

    def lancer(self, cmd, journal):
        # Session à part : tuer l'épreuve tue tout son groupe (timeout, docker exec).
        with open(journal, "w", encoding="utf-8") as f:
            return subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, env=self.env,
                                    start_new_session=True)

    def tuer(self, proc):
        for sig, attente in ((signal.SIGTERM, 15), (signal.SIGKILL, 5)):
            try:
                os.killpg(proc.pid, sig)
                proc.wait(attente)
                return
            except (ProcessLookupError, subprocess.TimeoutExpired):
                continue

    def temperature(self):
        """Paquet CPU en °C ; FUMEE_THERMOMETRE=<fichier> (un nombre) le remplace (essai §8)."""
        faux = self.env.get("FUMEE_THERMOMETRE")
        if faux:
            try:
                return float(Path(faux).read_text().strip())
            except (OSError, ValueError):
                return None
        rc, texte = self.sortie(["sensors"], delai=10)
        valeurs = [float(l.split("+", 1)[1].split("°", 1)[0]) for l in texte.splitlines()
                   if l.startswith(("Package id", "Tctl:")) and "+" in l] if rc == 0 else []
        return max(valeurs) if valeurs else None

    def joignable(self, hote):
        try:
            socket.getaddrinfo(hote, 443)
            return True
        except OSError:
            return False

    def dormir(self, secondes):
        time.sleep(secondes)

    def horloge(self):
        return time.monotonic()


def journal(etat: Path, texte: str) -> None:
    """Une ligne datée dans <etat>/journal.log, partagé avec fumee.sh (borné à 2000 lignes)."""
    f = etat / "journal.log"
    with open(f, "a", encoding="utf-8") as sortie:
        sortie.write("{} {}\n".format(datetime.now().astimezone().isoformat(timespec="seconds"), texte))
    lignes = f.read_text(encoding="utf-8").splitlines(keepends=True)
    if len(lignes) > 2000:
        f.write_text("".join(lignes[-1500:]), encoding="utf-8")


def prendre_flock(etat: Path, attente_s: float):
    """Jamais deux fumées à la fois (même fichier que fumee.sh) ; rend le descripteur à garder."""
    fd = os.open(etat / "verrou", os.O_WRONLY | os.O_CREAT, 0o644)
    fin = time.monotonic() + attente_s
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.monotonic() >= fin:
                os.close(fd)
                raise Refus("une autre fumée tient le verrou ({}/verrou)".format(etat)) from None
            time.sleep(1)


def verrou_sim(chemin: Path, forcer: bool, notes: list, maintenant=None):
    """Règle du 18/11 : « fumee … » = reste (le flock est à nous), retiré ; périmé (6 h) : ignoré ;
    sinon refus, sauf --forcer-verrou (noté). Pose ensuite « fumee HH:MM » si absent (O_EXCL)."""
    maintenant = maintenant or time.time()
    if chemin.exists():
        qui = "".join(c for c in (chemin.read_text(errors="replace").splitlines() or [""])[0] if c.isprintable())[:80]
        age = maintenant - chemin.stat().st_mtime
        if qui.startswith("fumee "):
            chemin.unlink(missing_ok=True)
        elif age >= PEREMPTION_SIM_OCCUPEE_S:
            notes.append("verrou « sim occupée » de « {} » périmé ({} h) : ignoré, pas effacé".format(qui, int(age // 3600)))
        elif forcer:
            notes.append("verrou « sim occupée » de « {} » outrepassé (--forcer-verrou)".format(qui))
        else:
            raise Refus("la sim est réservée par « {} » ({}, posé il y a {} min) ; --forcer-verrou si "
                        "tu sais qu'elle est finie".format(qui, chemin, int(age // 60)))
    if chemin.exists():
        return None
    chemin.parent.mkdir(parents=True, exist_ok=True)
    contenu = "fumee {}\n".format(datetime.now().strftime("%H:%M"))
    try:
        with open(chemin, "x", encoding="utf-8") as f:
            f.write(contenu)
    except FileExistsError:
        return None   # posé par quelqu'un dans la même seconde : le sien gagne
    return contenu


def liberer_verrou_sim(chemin: Path, contenu) -> None:
    """Ne retire que NOTRE ligne, intacte."""
    try:
        if contenu and chemin.read_text(encoding="utf-8") == contenu:
            chemin.unlink()
    except OSError:
        pass


def conteneurs_libres(sy: Systeme) -> None:
    """Un conteneur de la sim vivant = la sim de quelqu'un : refus, JAMAIS tué. Arrêté = reste
    (PC éteint pendant une fumée) : retiré par `docker rm` SANS -f (refuse s'il tourne)."""
    _, noms = sy.sortie(["docker", "ps", "-a", "--format", "{{.Names}}"])
    for nom in CONTENEURS:
        if nom not in noms.split():
            continue
        _, etat = sy.sortie(["docker", "inspect", "-f", "{{.State.Status}}", nom])
        if etat.strip() in ("exited", "dead", "created") and sy.sortie(["docker", "rm", nom])[0] == 0:
            continue
        raise Refus("le conteneur {} existe déjà ({}) : c'est une sim à toi, je ne la touche pas".format(nom, etat.strip()))


def autorite_x(sy: Systeme, etat: Path, notes: list) -> None:
    """Gazebo exige une autorité X valide même headless (segfault sinon, vécu le 07/11)."""
    sy.env.setdefault("DISPLAY", ":0")
    if sy.env.get("XAUTHORITY") and Path(sy.env["XAUTHORITY"]).is_file():
        return
    sessions = sorted(Path("/run/user/{}".format(os.getuid())).glob(".mutter-Xwaylandauth.*"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
    if sessions:
        sy.env["XAUTHORITY"] = str(sessions[0])
        return
    vide = etat / "xauthority-vide"
    vide.touch()
    sy.env["XAUTHORITY"] = str(vide)
    notes.append("aucune autorité X de session trouvée : Gazebo risque de ne pas démarrer")


MODES_PROFIL = ("auto", "balanced", "performance", "aucun")


class ProfilEnergie:
    """Profil d'énergie pendant la fumée (22/11, réglage « auto » du 28/11) : la courbe des
    ventilateurs du portable suit le profil de power-profiles-daemon. « auto » : `balanced` au
    départ, `performance` seulement quand le paquet CPU chauffe (≥ chaud_c), retour à `balanced`
    sous frais_c (hystérésis, seuils dans plan.toml [profil]). `balanced` / `performance` : profil
    fixe toute la fumée ; `aucun` : rien touché. SUR SECTEUR seulement (sur batterie on ne vide pas
    le pack pour un test). Jamais bloquant : `powerprofilesctl` absent ou en échec = réglage
    désactivé, une ligne au journal, la fumée continue. Le profil d'origine est rendu à la fin."""

    def __init__(self, sy: Systeme, etat: Path, mode: str, chaud_c: float, frais_c: float, notes=None):
        self.sy, self.etat, self.mode, self.chaud_c, self.frais_c = sy, etat, mode, chaud_c, frais_c
        self.ppc = sy.env.get("FUMEE_POWERPROFILESCTL", "powerprofilesctl")
        self.notes = notes if notes is not None else []   # celles de la page (Contexte.notes)
        self.origine = self.actuel = None   # origine non None = CETTE fumée a changé le profil
        self.actif = False                  # vrai = « auto » régule

    def _set(self, profil) -> bool:
        rc, texte = self.sy.sortie([self.ppc, "set", profil], delai=10)
        if rc != 0:
            journal(self.etat, "profil d'énergie : « {} set {} » a échoué ({}) : réglage désactivé, "
                               "profil laissé à {}".format(self.ppc, profil, texte.strip()[:120], self.actuel))
        return rc == 0

    def _noter(self, temperature, avant, apres, pourquoi) -> None:
        """Une bascule : journal de la fumée, sortie et page (heure, température, profils)."""
        t = "?" if temperature is None else "{:g} °C".format(round(temperature, 1))
        texte = "profil d'énergie {} : {} -> {} ({}, {})".format(
            datetime.now().strftime("%H:%M:%S"), avant, apres, t, pourquoi)
        journal(self.etat, texte)
        self.notes.append(texte)
        print("[fumée] " + texte, flush=True)

    def demarrer(self) -> None:
        if self.mode == "aucun":
            journal(self.etat, "profil d'énergie : réglage coupé (--profil aucun ou FUMEE_PROFIL=0)")
            return
        try:
            secteur = Path(self.sy.env.get("FUMEE_SECTEUR", "/sys/class/power_supply/ADP0/online")).read_text().strip()
        except OSError:
            secteur = ""
        if secteur != "1":
            journal(self.etat, "profil d'énergie : pas sur secteur ({!r}), profil inchangé".format(secteur))
            return
        rc, actuel = self.sy.sortie([self.ppc, "get"], delai=10)
        actuel = actuel.strip()
        if rc != 0 or not actuel:
            journal(self.etat, "profil d'énergie : « {} get » a échoué ({}) : réglage désactivé, profil "
                               "inchangé".format(self.ppc, actuel[:120] or "rien lu"))
            return
        self.actuel = actuel
        voulu = "balanced" if self.mode == "auto" else self.mode
        if voulu != actuel:
            # Mémorisée AVANT le set : un SIGTERM entre les deux rend quand même le profil d'origine.
            self.origine = actuel
            if not self._set(voulu):
                return
            self.actuel = voulu
            self._noter(self.sy.temperature(), actuel, voulu, "départ, réglage {}".format(self.mode))
        else:
            journal(self.etat, "profil d'énergie : déjà {} (réglage {})".format(actuel, self.mode))
        self.actif = self.mode == "auto"

    def sonder(self, temperature) -> None:
        """Appelé à chaque pause de la fumée, avec la température que les gardiens viennent de lire."""
        if not self.actif or temperature is None:
            return
        if self.actuel != "performance" and temperature >= self.chaud_c:
            voulu, pourquoi = "performance", "≥ {:g} °C".format(self.chaud_c)
        elif self.actuel == "performance" and temperature < self.frais_c:
            voulu, pourquoi = "balanced", "< {:g} °C".format(self.frais_c)
        else:
            return
        if self.origine is None:
            self.origine = self.actuel
        if not self._set(voulu):
            self.actif = False
            return
        self._noter(temperature, self.actuel, voulu, pourquoi)
        self.actuel = voulu

    def restaurer(self) -> None:
        """Idempotent : ne rend que ce que CETTE fumée a changé (verte, rouge, invalide, SIGTERM)."""
        self.actif = False
        if self.origine is None:
            return
        origine, self.origine = self.origine, None
        if origine == self.actuel:
            journal(self.etat, "profil d'énergie : {} (celui d'origine), rien à rendre".format(origine))
        elif self.sy.sortie([self.ppc, "set", origine], delai=10)[0] == 0:
            journal(self.etat, "profil d'énergie rendu : {} -> {}".format(self.actuel, origine))
            self.actuel = origine
        else:
            journal(self.etat, "ÉCHEC : profil d'énergie NON rendu ({}) — à remettre à la main".format(origine))


def preparer_arbre(sy: Systeme, depot: Path, arbre: Path, rev: str, hors_ligne: bool):
    """La révision testée dans NOTRE arbre de travail (worktree git, recréé si absent), jamais le
    checkout de David. Rend (sha complet, branche affichée)."""
    if arbre.resolve() == depot.resolve() or depot.resolve() in arbre.resolve().parents:
        raise Refus("l'arbre de la fumée ne peut pas être le checkout de David ({})".format(arbre))
    git = ["git", "-C", str(depot)]
    cible = rev
    if not hors_ligne:
        if rev.startswith("#"):
            if sy.sortie(git + ["fetch", "-q", "origin", "pull/{}/head".format(rev[1:])])[0] != 0:
                raise Refus("PR {} introuvable sur origin".format(rev))
            cible = "FETCH_HEAD"
        else:
            sy.sortie(git + ["fetch", "-q", "origin"])
    rc, sha = sy.sortie(git + ["rev-parse", "--verify", "-q", cible + "^{commit}"])
    if rc != 0:
        raise Refus("révision {} inconnue du dépôt{}".format(rev, " (hors ligne : elle doit être locale)" if hors_ligne else ""))
    sha = sha.strip()
    if not (arbre / ".git").exists():
        if arbre.exists() and any(arbre.iterdir()):
            raise Refus("{} existe et n'est pas un arbre de la fumée : je n'y touche pas".format(arbre))
        sy.sortie(git + ["worktree", "prune"])
        if sy.sortie(git + ["worktree", "add", "--detach", str(arbre), sha])[0] != 0:
            raise Refus("impossible de créer l'arbre de travail {}".format(arbre))
    # Arbre à nous : il est remis exactement sur la révision (résidus d'une fumée tuée compris).
    for cmd in (["checkout", "-q", "--detach", "--force", sha], ["clean", "-fdq"]):
        if sy.sortie(["git", "-C", str(arbre)] + cmd)[0] != 0:
            raise Refus("arbre {} : git {} a échoué".format(arbre, cmd[0]))
    branche = {"origin/main": "main", "main": "main"}.get(rev, rev)
    return sha, branche
