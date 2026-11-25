#!/usr/bin/env python3
"""Table de couverture des emplacements candidats du lidar (spec A0 §8.3), mesurée EN SIM.

Pour chaque pose : lance le SEUL conteneur `monde` de la sim (monde `stage`, plateau nu, sans
tête, domaine 43) avec DIDIER_LIDAR_POSE="x y z lacet" (lue par monde.launch.py, passée au
xacro gz), capture 100 balayages en espace dégagé (`mesurer_masques.py capturer`, exécuté
DANS le conteneur), arrête la sim, puis analyse sur le PC (`mesurer_masques.analyser` :
masques, témoin, régions vues) et écrit une table Markdown + le JSON brut.

    .venv/bin/python packages/didier_corps_sur/tools/couverture_poses.py --sortie ~/tmp/a0/couverture

Garde-fous (règles du PC de David) : refuse si un conteneur didier-sim-* existe, si la fumée
tourne, ou si ~/tmp/didier/sim-occupee existe sans être à nous ; pose « agent-A0 <heure> » dans ce
verrou pendant les mesures et le retire à la fin (un verrou « agent-A0 … » déjà posé par
l'agent qui l'appelle est respecté et laissé à son auteur) ; la sim lancée ici est toujours
arrêtée (finally).
La table sert à CHOISIR un emplacement, pas à percer : les cotes de l'URDF sont estimées.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
sys.path.insert(0, str(ICI))

import mesurer_masques  # noqa: E402

DEPOT = ICI.parents[2]
SIM = DEPOT / "machines" / "sim"
VERROU = Path.home() / "tmp" / "sim-occupee"
JOURNAUX = Path.home() / "tmp" / "a0" / "sim-journaux"
MONDE = "didier-sim-monde"
PREFIXE_VERROU = "agent-A0 "   # contenu du verrou « sim occupée » posé par le lot A0
SOL_Z = -0.23           # sol dans base_link (URDF : rayon roue 0,13 + demi-caisse 0,10)

# Poses candidates (x, y, z, lacet) dans base_link. Les deux premières = décision de David du
# 18/11 (face AVANT, spec §13) ; B et C = poses de la spec §8.3, pour mémoire.
POSES: List[Tuple[str, Tuple[float, float, float, float], str]] = [
    ("avant-25", (0.33, 0.0, 0.02, 0.0), "face avant, bas de caisse, plan à 25 cm (défaut de David)"),
    ("porte-45", (0.27, 0.0, 0.22, 0.0), "face avant, porte, plan à 45 cm (repli de David)"),
    ("B-sous-caisse", (0.10, 0.0, -0.13, 0.0), "sous la caisse entre les roues, plan à 10 cm (spec, pour mémoire)"),
    ("C-pont-avant", (0.20, 0.0, 0.14, 0.0), "dessus de caisse devant le torse, plan à 37 cm (spec, pour mémoire)"),
]


def sh(cmd: List[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, **kw)


def verifier_sim_libre() -> None:
    noms = sh(["docker", "ps", "-a", "--format", "{{.Names}}"]).stdout.split()
    occupes = [n for n in noms if n.startswith("didier-sim")]
    if occupes:
        raise SystemExit("REFUS : conteneurs de sim présents (%s) — pas les miens, je n'y touche pas" % ", ".join(occupes))
    if sh(["systemctl", "--user", "is-active", "didier-fumee.service"]).stdout.strip() in ("active", "activating"):
        raise SystemExit("REFUS : une fumée tourne")
    if VERROU.exists() and not VERROU.read_text(encoding="utf-8").startswith(PREFIXE_VERROU):
        raise SystemExit("REFUS : %s = %r" % (VERROU, VERROU.read_text(encoding="utf-8").strip()))


def compose(*args: str, env_pose: str = "") -> subprocess.CompletedProcess:
    env = dict(os.environ, ROBOT_NAME="didier", HEADLESS="true", WORLD="stage",
               DIDIER_SIM_JOURNAUX=str(JOURNAUX), DIDIER_LIDAR_POSE=env_pose)
    return sh(["docker", "compose", *args], cwd=SIM, env=env)


def attendre_colcon(delai_s: float = 600) -> None:
    t0 = time.monotonic()
    while time.monotonic() - t0 < delai_s:
        journal = sh(["docker", "logs", MONDE]).stdout + sh(["docker", "logs", MONDE]).stderr
        if "Failed   <<<" in journal or "Aborted  <<<" in journal:
            raise RuntimeError("colcon a échoué dans %s" % MONDE)
        if "Summary:" in journal:
            return
        time.sleep(5)
    raise RuntimeError("colcon pas fini en %.0f s" % delai_s)


def capturer_dans_le_conteneur(nombre: int) -> List[Dict]:
    script = (ICI / "mesurer_masques.py").read_text(encoding="utf-8")
    r = subprocess.run(
        ["docker", "exec", "-i", MONDE, "bash", "-c",
         "source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && "
         "python3 - capturer --nombre %d --topic /didier/scan --delai 240" % nombre],
        input=script, text=True, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("capture : %s" % r.stderr[-800:])
    return json.loads(r.stdout)


def mesurer_pose(nom: str, pose: Tuple[float, float, float, float], sortie: Path, nombre: int) -> Path:
    fichier = sortie / ("balayages-%s.json" % nom)
    env_pose = " ".join(str(v) for v in pose)
    print("[%s] %s : sim monde, DIDIER_LIDAR_POSE=%s" % (datetime.now().strftime("%H:%M:%S"), nom, env_pose), flush=True)
    try:
        r = compose("up", "-d", "monde", env_pose=env_pose)
        if r.returncode != 0:
            raise RuntimeError("compose up : %s" % r.stderr[-800:])
        attendre_colcon()
        time.sleep(20)                    # le robot se pose, gz rend ses premiers balayages
        balayages = capturer_dans_le_conteneur(nombre)
        fichier.write_text(json.dumps(balayages), encoding="utf-8")
        print("  %d balayages, %d rayons, frame %s" % (len(balayages), len(balayages[0]["ranges"]),
                                                       balayages[0].get("frame_id")), flush=True)
    finally:
        compose("down", "-t", "20")
    return fichier


def table_markdown(resultats: Dict[str, Dict]) -> str:
    def oui(b: bool) -> str:
        return "oui" if b else "**non**"
    lignes = ["| Pose | x ; y ; z (`base_link`) — plan | Secteurs masqués (`laser_frame`) | Champ libre | "
              "Part aveugle avant · arrière · flanc G · flanc D | Régions vues | Avancer | Reculer | Tourner | Témoin |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for nom, (pose, idee) in ((n, (p, i)) for n, p, i in POSES):
        if nom not in resultats:
            continue
        r = resultats[nom]
        cov = r["couverture"]
        vues = [k for k in ("avant", "arriere", "flanc_g", "flanc_d") if cov[k]["vue"]]
        tourner = "oui" if len(vues) == 4 else ("plafonné (maison seulement)" if cov["avant"]["vue"] else "**non**")
        t = r["temoin"]
        temoin = ("oui, %s° à %s m" % (t["secteur_deg"], t["distance_m"])) if t.get("exige") else "non"
        lignes.append("| %s — %s | %.2f ; %.2f ; %.2f — %.2f m | %s | %.0f° | %s | %s | %s | %s | %s | %s |" % (
            nom, idee, pose[0], pose[1], pose[2], pose[2] - SOL_Z,
            " ".join("[%g ; %g]" % (a, b) for a, b in r["masques_deg"]) or "aucun",
            r["champ_libre_deg"],
            " · ".join("%.0f %%" % (100 * cov[k]["part_aveugle"]) for k in ("avant", "arriere", "flanc_g", "flanc_d")),
            ", ".join(vues) or "aucune", oui(cov["avant"]["vue"]), oui(cov["arriere"]["vue"]), tourner, temoin))
    return "\n".join(lignes)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--sortie", type=Path, default=Path.home() / "tmp" / "a0" / "couverture")
    p.add_argument("--poses", nargs="*", help="noms à mesurer (défaut : toutes)")
    p.add_argument("--nombre", type=int, default=100)
    p.add_argument("--analyser-seulement", action="store_true", help="réutilise les JSON déjà capturés")
    args = p.parse_args()
    args.sortie.mkdir(parents=True, exist_ok=True)
    choisies = [x for x in POSES if not args.poses or x[0] in args.poses]

    if not args.analyser_seulement:
        verifier_sim_libre()
        for d in ("log", "log-vision", "log-telecommande"):
            (JOURNAUX / d).mkdir(parents=True, exist_ok=True)
        VERROU.parent.mkdir(parents=True, exist_ok=True)
        deja_pose = VERROU.exists()          # posé par l'appelant (même lot) : on le lui laisse
        if not deja_pose:
            VERROU.write_text("%s%s\n" % (PREFIXE_VERROU, datetime.now().strftime("%H:%M")), encoding="utf-8")
        try:
            for nom, pose, _ in choisies:
                mesurer_pose(nom, pose, args.sortie, args.nombre)
        finally:
            if not deja_pose and VERROU.exists() and VERROU.read_text(encoding="utf-8").startswith(PREFIXE_VERROU):
                VERROU.unlink()

    from didier_corps_sur import geometrie
    resultats: Dict[str, Dict] = {}
    for nom, pose, _ in choisies:
        fichier = args.sortie / ("balayages-%s.json" % nom)
        if not fichier.exists():
            continue
        res = mesurer_masques.analyser(mesurer_masques.charger(str(fichier)), geometrie.Caisse(),
                                       geometrie.PoseLidar(pose[0], pose[1], pose[3]))
        resultats[nom] = {"pose": pose, "masques_deg": res.masques_deg, "temoin": res.temoin,
                          "couverture": res.couverture, "champ_libre_deg": res.champ_libre_deg,
                          "rayons": res.rayons, "angles_auto_retour": res.angles_auto_retour,
                          "yaml": mesurer_masques.extrait_yaml(res)}
    (args.sortie / "couverture.json").write_text(json.dumps(resultats, indent=2, default=str), encoding="utf-8")
    table = table_markdown(resultats)
    (args.sortie / "table.md").write_text(table + "\n", encoding="utf-8")
    print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
