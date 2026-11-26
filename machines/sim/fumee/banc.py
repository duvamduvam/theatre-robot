"""Le banc (F1, 25/11) : la SEULE porte vers le système (classe Systeme, remplacée par un faux en
test), et les règles de fumee.sh reprises sans changement : flock, verrou « sim occupée », sim de
quelqu'un d'autre jamais touchée, profil d'énergie, autorité X, arbre de travail à nous.
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
CONTENEURS = ("didier-sim-monde", "didier-sim-robot", "didier-sim-vision", "didier-sim-telecommande")


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


def basculer_profil(sy: Systeme, etat: Path):
    """« performance » pendant la fumée, SUR SECTEUR seulement (22/11) ; rend le profil d'origine."""
    ppc = sy.env.get("FUMEE_POWERPROFILESCTL", "powerprofilesctl")
    if sy.env.get("FUMEE_PROFIL", "1") != "1":
        return None
    try:
        secteur = Path(sy.env.get("FUMEE_SECTEUR", "/sys/class/power_supply/ADP0/online")).read_text().strip()
    except OSError:
        secteur = ""
    rc, actuel = sy.sortie([ppc, "get"])
    actuel = actuel.strip()
    if secteur != "1" or rc != 0 or not actuel or actuel == "performance":
        journal(etat, "profil d'énergie inchangé (secteur {!r}, profil {!r})".format(secteur, actuel))
        return None
    if sy.sortie([ppc, "set", "performance"])[0] != 0:
        return None
    journal(etat, "profil d'énergie : {} -> performance (sur secteur)".format(actuel))
    return actuel


def restaurer_profil(sy: Systeme, etat: Path, origine) -> None:
    if origine and sy.sortie([sy.env.get("FUMEE_POWERPROFILESCTL", "powerprofilesctl"), "set", origine])[0] != 0:
        journal(etat, "ÉCHEC : profil d'énergie NON rendu ({}) — à remettre à la main".format(origine))


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
