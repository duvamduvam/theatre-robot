#!/usr/bin/env python3
"""Cœurs réservés à la fumée — la sim seule sur quelques cœurs rapides, le reste du PC ailleurs.

POURQUOI (mesuré le 08/11, pic artificiel sur les 32 fils) : Gazebo avance sur UN fil ; sous un
pic de charge le RTF tombe à 0,76 (fumée rouge sans aucune régression). Épinglée sur 4 cœurs
rapides PARTAGÉS : 0,83. Sur 4 cœurs rapides RÉSERVÉS (rien d'autre dessus) : 0,987. David fait
tourner d'autres travaux à côté : la réservation ne vaut QUE pendant la fumée, puis tout est rendu.

COMMENT, sans sudo : le cpuset n'est pas délégué au gestionnaire systemd de l'utilisateur
(user@1000.service n'a que cpu/memory/pids). Deux leviers sans droits :
  - ses PROPRES processus : os.sched_setaffinity (même uid), FIL PAR FIL — l'affinité est celle
    d'un fil (TID), pas d'un processus : sched_setaffinity(pid) ne déplace que le fil principal.
    Jusqu'au 16/11 seuls les fils principaux partaient ; les autres (navigateur, IDE, modèles
    locaux, compilations) restaient sur les cœurs réservés — RTF retombé à 0,69-0,73 sous
    charge le 15/11. Chaque fil de /proc/<pid>/task/ est donc déplacé (et noté) ;
  - les AUTRES conteneurs Docker : `docker update --cpuset-cpus` (groupe docker).
Les processus root hors conteneur restent où ils sont (rares, peu chargés) — limite assumée.

État : un fichier JSON (origine des affinités et des cpusets) écrit AVANT de toucher quoi que ce
soit. `liberer` le relit et rend tout, y compris après une fumée tuée (relancer `liberer` à la
main suffit). Un PID n'est restauré que si son heure de démarrage n'a pas changé (PID réutilisé).

Sous-commandes : reserver | maintenir | liberer  (--coeurs 8-15 --etat <fichier> --sim <conteneur>…)
`--sim` est répétable (L2b) : la sim multi-conteneurs en compte quatre, aucun n'est poussé ailleurs.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Les conteneurs de la sim multi-conteneurs (L2b), jamais poussés hors des cœurs réservés.
CONTENEURS_SIM = ("didier-sim-monde", "didier-sim-robot", "didier-sim-vision", "didier-sim-telecommande")


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


def taches(pid: int) -> list[int]:
    """Les fils (TID) d'un processus, /proc/<pid>/task/ ; [] s'il est mort entre-temps."""
    try:
        return sorted(int(t.name) for t in Path(f"/proc/{pid}/task").iterdir() if t.name.isdigit())
    except OSError:
        return []


def _mes_taches():
    """Chaque FIL de chacun de mes processus (cf. COMMENT : l'affinité est par fil)."""
    uid = os.getuid()
    for entree in Path("/proc").iterdir():
        if entree.name.isdigit():
            try:
                if entree.stat().st_uid != uid:
                    continue
            except OSError:
                continue
            yield from taches(int(entree.name))


def _docker(*args) -> str:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=True).stdout


def _conteneurs(sauf):
    """Les conteneurs vivants, sauf ceux de la sim (`sauf` : un nom ou une collection de noms)."""
    exclus = {sauf} if isinstance(sauf, str) else set(sauf)
    for ligne in _docker("ps", "--format", "{{.ID}} {{.Names}}").splitlines():
        ident, nom = ligne.split(" ", 1)
        if nom not in exclus:
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


def deplacer(reserves: set[int], fichier: Path, sim, pids=None,
             avec_conteneurs: bool = True) -> tuple[int, int]:
    """Une passe : pousse hors des réservés ce qui n'y a pas encore été poussé. Idempotent —
    `reserver` et `maintenir` sont la même passe. L'origine est notée AVANT le déplacement.

    `pids` / `avec_conteneurs` : bornes pour les TESTS (des fils jetables, aucun
    conteneur). Leçon du 08/11 : un test qui laissait la valeur par défaut a déplacé toute la
    session de David, et une mutation (libération neutralisée) ne l'a jamais rendue.
    Les « pids » sont des TID (un par fil) ; la clé « processus » de l'état les garde (format
    inchangé : un TID se restaure comme un PID). Origines notées en UNE écriture avant tout
    déplacement (des milliers de fils : une écriture par fil coûterait O(n²))."""
    tous = set(range(os.cpu_count() or 1))
    etat = _lire_etat(fichier)
    etat["reserves"] = ecrire_liste(reserves)
    n_proc = n_cont = 0
    moi = set(taches(os.getpid())) or {os.getpid()}
    a_deplacer = []
    for tid in (_mes_taches() if pids is None else pids):
        if tid in moi:
            continue
        try:
            actuels = os.sched_getaffinity(tid)
        except OSError:
            continue
        cible = hors_reserve(actuels, reserves, tous)
        if cible == actuels:
            continue
        cle = str(tid)
        if cle not in etat["processus"]:
            etat["processus"][cle] = {"debut": _debut_processus(tid), "cpus": ecrire_liste(actuels)}
        a_deplacer.append((tid, cible))
    if a_deplacer:
        _ecrire_etat(fichier, etat)   # l'origine AVANT le déplacement
    for tid, cible in a_deplacer:
        try:
            os.sched_setaffinity(tid, cible)
            n_proc += 1
        except OSError:
            pass  # fil fini entre-temps, ou d'un autre uid (setuid) : on passe
    for ident, nom in (_conteneurs(sauf=sim) if avec_conteneurs else ()):
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


def est_heritier(actuels: set[int], reserves: set[int], tous: set[int]) -> bool:
    """Un processus NÉ pendant la réservation hérite de l'affinité réduite de son parent : il
    n'est pas dans l'état (personne ne l'a déplacé) mais porte exactement « tous moins les
    réservés ». Vu le 08/11 : 15 processus restés privés de cœurs après la fumée."""
    return bool(reserves) and actuels == tous - reserves


def liberer(fichier: Path, pids=None) -> tuple[int, int]:
    """Rend chaque affinité et chaque cpuset d'origine, élargit les héritiers (cf. est_heritier),
    puis efface l'état. `pids` : borne pour les tests (cf. deplacer)."""
    if not fichier.exists():
        return 0, 0
    etat = _lire_etat(fichier)
    tous_cpus = set(range(os.cpu_count() or 1))
    tous = ecrire_liste(tous_cpus)
    reserves = lire_liste(etat.get("reserves", ""))
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
    connus = set(etat.get("processus", {}))
    for pid in (_mes_taches() if pids is None else pids):
        if str(pid) in connus:
            continue
        try:
            if est_heritier(os.sched_getaffinity(pid), reserves, tous_cpus):
                os.sched_setaffinity(pid, tous_cpus)
                n_proc += 1
        except OSError:
            continue
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
    # Répétable (L2b) : un --sim par conteneur de la sim ; sans --sim, les quatre de la sim
    # multi-conteneurs (machines/sim/docker-compose.yml).
    p.add_argument("--sim", action="append", default=None)
    a = p.parse_args(argv)
    if a.sim is None:
        a.sim = list(CONTENEURS_SIM)
    if a.commande == "liberer":
        n_proc, n_cont = liberer(a.etat)
        print(f"cœurs rendus : {n_proc} fils (threads), {n_cont} conteneurs restaurés")
        return 0
    reserves = lire_liste(a.coeurs)
    if not reserves or not reserves < set(range(os.cpu_count() or 1)):
        print(f"--coeurs {a.coeurs!r} : il faut un sous-ensemble strict des CPU", file=sys.stderr)
        return 2
    n_proc, n_cont = deplacer(reserves, a.etat, a.sim)
    if a.commande == "reserver":
        print(f"cœurs {ecrire_liste(reserves)} réservés : {n_proc} fils (threads) et {n_cont} "
              f"conteneurs poussés ailleurs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
