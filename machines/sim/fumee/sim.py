"""La sim d'une épreuve (F1, 25/11), reprise de demarrer_sim, lancer_corps, exiger_corps_sur_arme,
noter_verrous_pendant, recolter et arreter_sim de fumee.sh. Une sim n'est relancée que si l'épreuve
en demande une autre (spec §3) ; celle de quelqu'un d'autre n'est jamais touchée (banc.py).
"""
import gzip
import re
import shutil
import tarfile
from pathlib import Path

from .banc import CONTENEURS
from .gardiens import ATTENTE_RTF_S, Arret

SERVICES = ("monde", "robot", "vision", "telecommande")
ROS = "source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && "
SONDES = (Path(__file__).with_name("sondes.py")).read_text(encoding="utf-8")


def dans(service):
    return "didier-sim-" + service


class Sim:
    def __init__(self, f):
        self.f, self.sy = f, f.sy
        self.vivante, self.cle, self.servie, self.sondee, self.tete = False, None, False, False, False
        self.demarrages = 0

    def _log(self, nom, texte):
        with open(self.f.tmp / nom, "a", encoding="utf-8") as sortie:
            sortie.write(texte.rstrip("\n") + "\n")

    def compose(self, *args, env=None):
        tete = ["-f", "docker-compose.tete.yml"] if self.tete else []
        return self.sy.sortie(["docker", "compose", "-f", "docker-compose.yml", *tete, *args],
                              cwd=self.f.arbre / "machines" / "sim", env=env)

    def ros(self, service, commande, entree=None):
        return self.sy.sortie(["docker", "exec", *(["-i"] if entree else []), dans(service),
                               "bash", "-c", ROS + commande], entree=entree)

    def sonde(self, nom):
        return self.ros("monde", "python3 - " + nom, entree=SONDES)

    def processus(self, motif):
        return self.sy.sortie(["docker", "exec", dans("monde"), "pgrep", "-f", motif])[0] == 0

    def attendre(self, motif, voulu, delai):
        fin = self.sy.horloge() + delai
        while self.sy.horloge() < fin:
            if self.processus(motif) == voulu:
                return True
            self.f.pause(2)
        return False

    # --- Démarrage ---------------------------------------------------------------------------
    def preparer(self, ep, sonder=True):
        """La sim de l'épreuve, prête et sondée ; None si prête, sinon le résultat (rouge/invalide)."""
        neuve = bool((ep.sim or {}).get("neuve")) and self.servie
        if not self.vivante or self.cle != ep.cle_sim or neuve:
            self.arreter(ep.id)
            cause = self.demarrer(ep)
            if cause:
                self.arreter(ep.id)
                return {"id": ep.id, "statut": "rouge", "journal": "demarrage.log",
                        "detail": "la sim (monde {}) n'a pas démarré : {}".format(ep.cle_sim[0], cause)}
        if sonder and not self.sondee:
            r = self.sonder(ep.id)
            if r["statut"] != "vert":
                self.arreter(ep.id)
                return r
        return None

    def demarrer(self, ep):
        monde, regie, jeu, self.tete = ep.cle_sim
        self.vivante, self.cle, self.servie, self.sondee = True, ep.cle_sim, False, False  # à nous dès le `up`
        self.demarrages += 1
        journaux = Path(self.sy.env.get("DIDIER_SIM_JOURNAUX", Path.home() / "tmp/didier/sim"))
        for d in ("log", "log-vision", "log-telecommande"):
            (journaux / d).mkdir(parents=True, exist_ok=True)
        rc, texte = self.compose("up", "-d", env={"ROBOT_NAME": "didier", "HEADLESS": "true", "WORLD": monde,
                                                   "DIDIER_SIM_JOURNAUX": str(journaux), "REHEARSAL": "true",
                                                   "FACE": "true", "WEB_DRIVE": "false", "DATA_EDIT": "true"})
        self._log("demarrage.log", "=== {} : up (monde {}, tête {})\n{}".format(ep.id, monde, self.tete, texte))
        if rc != 0:
            return "docker compose up a échoué (code {})".format(rc)
        self.f.epingler(CONTENEURS)
        for c in CONTENEURS:   # 42 = le vrai Didier : jamais
            domaine = self.sy.sortie(["docker", "exec", c, "printenv", "ROS_DOMAIN_ID"])[1].strip()
            if domaine != "43":
                raise Arret("ROS_DOMAIN_ID={} dans {} (43 exigé) : fumée arrêtée".format(domaine or "?", c))
        cause = self.attendre_pret()
        if cause:
            return cause
        if regie and not self.lancer_corps(regie, jeu):
            return "chaîne roues absente, ou régisseur (monde) / regard (robot) non démarrés"
        return None

    def attendre_pret(self):
        """colcon fini sans échec ×4, pont gz ET Gazebo vivants, nœuds attendus vus ; sinon la cause."""
        delai = int(self.sy.env.get("FUMEE_DELAI_DEMARRAGE", "600"))
        fin, pont, finis = self.sy.horloge() + delai, False, 0
        while self.sy.horloge() < fin:
            vivants = self.sy.sortie(["docker", "ps", "--format", "{{.Names}}"])[1].split()
            finis = 0
            for s in SERVICES:
                if dans(s) not in vivants:
                    return "le conteneur {} s'est arrêté".format(dans(s))
                # Journal capturé ENTIER puis lu : jamais de tube vers grep -q (SIGPIPE, 16/11).
                journal = self.sy.sortie(["docker", "logs", dans(s)])[1]
                if re.search(r"Failed +<<<|packages? failed", journal):
                    self._log("demarrage.log", journal[-20000:])
                    return "colcon build a échoué dans {}".format(dans(s))
                finis += bool(re.search(r"Summary: [0-9]+ packages? finished", journal))
            if not pont and self.processus("parameter_bridge"):
                self.f.pause(15)   # le monde se charge avant toute mesure
                if not self.processus("gz sim"):
                    return "Gazebo (gz sim) absent au démarrage (autorité X, GPU ?)"
                pont = True
            if pont and finis == len(SERVICES):
                rc, texte = self.sonde("noeuds")
                self._log("demarrage.log", texte)
                if rc == 0:
                    return None
            self.f.pause(5)
        return "sim incomplète après {} s (pont gz : {}, colcon fini : {}/4)".format(delai, pont, finis)

    def sonder(self, ident):
        """Sonde du temps réel (20 s) ; sous le seuil, une seconde 2 min plus tard (spec §4)."""
        for essai in (1, 2):
            rc, texte = self.sonde("rtf")
            self._log("rtf.log", "=== {} (essai {})\n{}".format(ident, essai, texte))
            lu = re.findall(r"RTF=([0-9.]+)", texte)
            rtf = float(lu[-1]) if lu else 0.0
            if self.f.rtf is None:
                self.f.rtf = rtf
            r = {"id": ident, "obtenu": "{:.3f}".format(rtf), "journal": "rtf.log"}
            if "messages=0" in texte:
                return {**r, "statut": "rouge", "detail": "aucun message sur /clock en 120 s : Gazebo ne publie rien"}
            if rtf >= self.f.rtf_min:
                self.sondee = True
                return {**r, "statut": "vert", "detail": "seuil {}".format(self.f.rtf_min)}
            if essai == 1:
                self.f.pause(ATTENTE_RTF_S)
        return {**r, "statut": "invalide", "detail": "invalide : temps réel {:.3f} < {} deux fois, à 2 min "
                                                     "d'écart (PC trop occupé)".format(rtf, self.f.rtf_min)}

    def lancer_corps(self, regie, jeu):
        """Régisseur (monde) + regard (robot) ; la chaîne roues tourne déjà (vrai bringup)."""
        self.attendre("lib/didier_rehearsal/director", False, 30)
        if not self.attendre("/twist_deadman( |$)", True, 30):
            return False
        self.sy.sortie(["docker", "exec", "-d", dans("monde"), "bash", "-c", ROS + "ros2 launch didier_rehearsal "
                        "rehearsal.launch.py route:=chantiers scenario:={}{}".format(regie, " jeu:=true" if jeu else "")])
        self.sy.sortie(["docker", "exec", "-d", dans("robot"), "bash", "-c",
                        ROS + "ros2 run didier_core gaze_follower --ros-args -r __ns:=/didier"])
        if not (self.attendre("lib/didier_rehearsal/director", True, 60) and self.attendre("gaze_follower", True, 60)):
            return False
        self.f.pause(20)   # les nœuds s'apparient avant que le script ne les sonde
        return True

    # --- Corps sûr du bringup (A0-4) ----------------------------------------------------------
    def corps_sur_arme(self, ident):
        """None si ARMÉ (corps_sur_bringup.py réarme un capteur_perdu spontané, ≤ 2 fois), sinon rouge."""
        rc, texte = self.ros("monde", "python3 /home/ros2_ws/machines/sim/corps_sur_bringup.py")
        self._log("corps-sur-bringup.log", "avant {} (code {})\n{}".format(ident, rc, texte))
        ligne = ([l for l in texte.splitlines() if l.startswith("CORPS_SUR_BRINGUP ")] or [""])[-1]
        n = int((re.findall(r" rearmements=([0-9]+) ", ligne) or ["0"])[-1])
        if n:
            self.f.notes.append("corps sûr du bringup RÉARMÉ {} fois avant {} : VERROU capteur_perdu "
                                "spontané (corps-sur-bringup.log)".format(n, ident))
        if rc == 0 and ligne.startswith("CORPS_SUR_BRINGUP arme "):
            return None
        return {"id": ident, "statut": "rouge", "duree_s": 0, "journal": "corps-sur-bringup.log",
                "detail": "corps sûr du bringup NON ARMÉ avant l'épreuve : " + (ligne or "aucune réponse, code {}".format(rc))}

    def verrous(self):
        """(entrées en VERROU du corps sûr du bringup, dernière cause) lues au journal du robot."""
        n, avant, cause = 0, False, ""
        for l in self.sy.sortie(["docker", "logs", dans("robot")])[1].splitlines():
            if "didier.corps_sur]: état : " in l:
                v = '"etat": "VERROU"' in l
                n, avant = n + (v and not avant), v
                cause = (re.findall(r'"etat": "VERROU", "cause": "[a-z_]*"', l) or [cause])[-1]
        return n, cause

    # --- Récolte et arrêt -------------------------------------------------------------------
    def copier_captures(self, ident, dossier):
        d = self.f.jdir / ("captures-" + ident)
        if self.sy.sortie(["docker", "exec", dans("monde"), "test", "-d", dossier])[0] != 0:
            return
        if self.sy.sortie(["docker", "cp", dans("monde") + ":" + dossier, str(d)])[0] != 0:
            self.f.notes.append("captures de {} non copiées ({})".format(ident, dossier))
            return
        for p in [p for p in d.rglob("*") if p.suffix in (".json", ".jsonl") and p.stat().st_size > 65536]:
            with open(p, "rb") as src, gzip.open(str(p) + ".gz", "wb", 9) as dst:
                shutil.copyfileobj(src, dst)
            p.unlink()

    def recolter(self, nom):
        """Journaux copiés hors conteneurs AVANT l'arrêt (ils meurent avec eux) ; > 1 Mo : 3000 lignes."""
        if dans("monde") not in self.sy.sortie(["docker", "ps", "--format", "{{.Names}}"])[1].split():
            self.f.notes.append("journaux non récoltés ({}) : monde n'est plus en marche".format(nom))
            return
        d = self.f.tmp / ("recolte-" + nom)
        d.mkdir(parents=True, exist_ok=True)
        for s in SERVICES:
            (d / (s + "-docker.log")).write_text(self.sy.sortie(["docker", "logs", dans(s)])[1], encoding="utf-8")
        for s, cible in (("monde", "ros2_ws-log"), ("vision", "vision-log"), ("telecommande", "telecommande-log")):
            self.sy.sortie(["docker", "cp", dans(s) + ":/home/ros2_ws/log", str(d / cible)])
        self.sy.sortie(["docker", "exec", dans("monde"), "bash", "-c",
                        "mkdir -p /tmp/fumee-recolte && cp /tmp/validate-*.log /tmp/fumee-recolte/ 2>/dev/null"])
        self.sy.sortie(["docker", "cp", dans("monde") + ":/tmp/fumee-recolte", str(d / "tmp")])
        for p in [p for p in d.rglob("*") if p.is_file() and p.stat().st_size > 1 << 20]:
            p.write_text("".join(p.read_text(errors="replace").splitlines(keepends=True)[-3000:]))
            with open(d / "TRONQUE.txt", "a") as t:
                t.write("tronqué (3000 dernières lignes) : {}\n".format(p.relative_to(d)))
        with tarfile.open(self.f.jdir / "conteneur-{}.tar.gz".format(nom), "w:gz") as tar:
            tar.add(d, arcname=".")
        shutil.rmtree(d, ignore_errors=True)

    def arreter_sans_recolte(self):
        """Arrêt sur interruption (SIGTERM) : la sim et rien d'autre, tout de suite."""
        if not self.vivante:
            return
        self.compose("down", "-t", "5")
        for c in CONTENEURS:
            self.sy.sortie(["docker", "rm", "-f", c])
        self.vivante = False

    def arreter(self, nom):
        """Seulement NOTRE sim (vivante = lancée par cette fumée), après récolte."""
        if not self.vivante:
            return
        self.recolter(nom)
        self.compose("down", "-t", "20")
        for c in CONTENEURS:
            self.sy.sortie(["docker", "rm", "-f", c])
        self.vivante = False
