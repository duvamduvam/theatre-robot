#!/usr/bin/env python3
"""Cœurs réservés à la fumée — la sim seule sur quelques cœurs rapides, le reste du PC ailleurs.

POURQUOI (mesuré le 08/11, pic artificiel sur les 32 fils) : Gazebo avance sur UN fil ; sous un
pic de charge le RTF tombe à 0,76 (fumée rouge sans aucune régression). Épinglée sur 4 cœurs
rapides PARTAGÉS : 0,83. Sur 4 cœurs rapides RÉSERVÉS (rien d'autre dessus) : 0,987. David fait
tourner d'autres travaux à côté : la réservation ne vaut QUE pendant la fumée, puis tout est rendu.

COMMENT, sans sudo : le cpuset n'est pas délégué au gestionnaire systemd de l'utilisateur
(user@1000.service n'a que cpu/memory/pids). Deux leviers sans droits :
  - ses PROPRES processus : os.sched_setaffinity (même uid) ;
  - les AUTRES conteneurs Docker : `docker update --cpuset-cpus` (groupe docker).
Les processus root hors conteneur restent où ils sont (rares, peu chargés) — limite assumée.

État : un fichier JSON (origine des affinités et des cpusets) écrit AVANT de toucher quoi que ce
soit. `liberer` le relit et rend tout, y compris après une fumée tuée (relancer `liberer` à la
main suffit). Un PID n'est restauré que si son heure de démarrage n'a pas changé (PID réutilisé).

Sous-commandes : reserver | maintenir | liberer  (--coeurs 8-15 --etat <fichier> --sim <conteneur>)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


# --- Logique pure (testée) ------------------------------------------------------------------

def lire_liste(texte: str) -> set[int]:
    """« 0-7,16-31 » → {0..7, 16..31}. Vide → ensemble vide. Format du noyau et de Docker."""
    cpus: set[int] = set()
    for morceau in (texte or "").replace(" ", "").split(","):
        if not morceau:
            continue
        if "-" in morceau:
            debut, fin = morceau.split("-", 1)
            if int(debut) > int(fin):
                raise ValueError(f"plage inversée : {morceau!r}")
            cpus.update(range(int(debut), int(fin) + 1))
        else:
            cpus.add(int(morceau))
    return cpus


def ecrire_liste(cpus) -> str:
    """{0..7, 16..31} → « 0-7,16-31 » (plages compactes, triées)."""
    tries = sorted(set(cpus))
    plages, i = [], 0
    while i < len(tries):
        j = i
        while j + 1 < len(tries) and tries[j + 1] == tries[j] + 1:
            j += 1
        plages.append(str(tries[i]) if i == j else f"{tries[i]}-{tries[j]}")
        i = j + 1
    return ",".join(plages)


def hors_reserve(actuels: set[int], reserves: set[int], tous: set[int]) -> set[int]:
    """Où un processus/conteneur a le droit d'aller pendant la réservation : ses CPU actuels
    (ou tous si non contraint) moins les réservés. Si ça ne laisse RIEN (il était déjà confiné
    aux réservés), on ne le touche pas : mieux vaut un voisin qu'un processus sans CPU."""
    base = actuels or tous
    reste = base - reserves
    return reste if reste else base


# --- Accès au système -----------------------------------------------------------------------

def _debut_processus(pid: int) -> str | None:
    """Heure de démarrage (champ 22 de /proc/<pid>/stat) : distingue un PID réutilisé."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    return stat.rsplit(")", 1)[1].split()[19]


def _mes_processus():
    uid = os.getuid()
    for entree in Path("/proc").iterdir():
        if entree.name.isdigit():
            try:
                if entree.stat().st_uid == uid:
                    yield int(entree.name)
            except OSError:
                continue


def _docker(*args) -> str:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=True).stdout


def _conteneurs(sauf: str):
    for ligne in _docker("ps", "--format", "{{.ID}} {{.Names}}").splitlines():
        ident, nom = ligne.split(" ", 1)
        if nom != sauf:
            yield ident, nom


def _cpuset_conteneur(ident: str) -> str:
    return _docker("inspect", "-f", "{{.HostConfig.CpusetCpus}}", ident).strip()


def _lire_etat(fichier: Path) -> dict:
    if fichier.exists():
        return json.loads(fichier.read_text())
    return {"processus": {}, "conteneurs": {}}


def _ecrire_etat(fichier: Path, etat: dict) -> None:
    fichier.parent.mkdir(parents=True, exist_ok=True)
    provisoire = fichier.with_suffix(".tmp")
    provisoire.write_text(json.dumps(etat, indent=1))
    provisoire.replace(fichier)


def deplacer(reserves: set[int], fichier: Path, sim: str) -> tuple[int, int]:
    """Une passe : pousse hors des réservés ce qui n'y a pas encore été poussé. Idempotent —
    `reserver` et `maintenir` sont la même passe. L'origine est notée AVANT le déplacement."""
    tous = set(range(os.cpu_count() or 1))
    etat = _lire_etat(fichier)
    etat["reserves"] = ecrire_liste(reserves)
    n_proc = n_cont = 0
    moi = os.getpid()
    for pid in _mes_processus():
        if pid == moi:
            continue
        try:
            actuels = os.sched_getaffinity(pid)
        except OSError:
            continue
        cible = hors_reserve(actuels, reserves, tous)
        if cible == actuels:
            continue
        cle = str(pid)
        if cle not in etat["processus"]:
            etat["processus"][cle] = {"debut": _debut_processus(pid), "cpus": ecrire_liste(actuels)}
            _ecrire_etat(fichier, etat)
        try:
            os.sched_setaffinity(pid, cible)
            n_proc += 1
        except OSError:
            pass  # processus fini entre-temps, ou d'un autre uid (setuid) : on passe
    for ident, nom in _conteneurs(sauf=sim):
        actuel = _cpuset_conteneur(ident)
        cible = hors_reserve(lire_liste(actuel), reserves, tous)
        if cible == (lire_liste(actuel) or tous):
            continue
        if nom not in etat["conteneurs"]:
            etat["conteneurs"][nom] = actuel
            _ecrire_etat(fichier, etat)
        subprocess.run(["docker", "update", "--cpuset-cpus", ecrire_liste(cible), ident],
                       capture_output=True, check=False)
        n_cont += 1
    _ecrire_etat(fichier, etat)
    return n_proc, n_cont


def liberer(fichier: Path) -> tuple[int, int]:
    """Rend chaque affinité et chaque cpuset d'origine, puis efface l'état."""
    if not fichier.exists():
        return 0, 0
    etat = _lire_etat(fichier)
    tous = ecrire_liste(range(os.cpu_count() or 1))
    n_proc = n_cont = 0
    for cle, origine in etat.get("processus", {}).items():
        pid = int(cle)
        if _debut_processus(pid) != origine["debut"]:
            continue  # mort, ou PID réutilisé par un autre processus
        try:
            os.sched_setaffinity(pid, lire_liste(origine["cpus"]))
            n_proc += 1
        except OSError:
            pass
    for nom, cpuset in etat.get("conteneurs", {}).items():
        # cpuset d'origine vide = « pas de contrainte » : Docker n'accepte pas "" en update,
        # on rend donc tous les CPU, ce qui revient au même.
        r = subprocess.run(["docker", "update", "--cpuset-cpus", cpuset or tous, nom],
                           capture_output=True, check=False)
        n_cont += r.returncode == 0
    fichier.unlink()
    return n_proc, n_cont


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("commande", choices=("reserver", "maintenir", "liberer"))
    p.add_argument("--coeurs", default="8-15")
    p.add_argument("--etat", type=Path,
                   default=Path.home() / ".local/state/didier-fumee/coeurs.json")
    p.add_argument("--sim", default="dadou-sim-container")
    a = p.parse_args(argv)
    if a.commande == "liberer":
        n_proc, n_cont = liberer(a.etat)
        print(f"cœurs rendus : {n_proc} processus, {n_cont} conteneurs restaurés")
        return 0
    reserves = lire_liste(a.coeurs)
    if not reserves or not reserves < set(range(os.cpu_count() or 1)):
        print(f"--coeurs {a.coeurs!r} : il faut un sous-ensemble strict des CPU", file=sys.stderr)
        return 2
    n_proc, n_cont = deplacer(reserves, a.etat, a.sim)
    if a.commande == "reserver":
        print(f"cœurs {ecrire_liste(reserves)} réservés : {n_proc} processus et {n_cont} "
              f"conteneurs poussés ailleurs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
