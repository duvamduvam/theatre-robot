#!/usr/bin/env python3
"""Pupitre d'enregistrement du corpus voix — lot V3 (docs/etude-voix-didier.md §7).

Enregistre la voix de David EN PERSONNAGE sur la Scarlett (micro statique,
48 V), prise par prise, avec contrôle qualité immédiat de chaque prise. Trois
modes :

    .venv/bin/python enregistre.py gain      # vumètre continu pour régler le gain
    .venv/bin/python enregistre.py prise X   # enregistre la prise nommée X (Entrée = stop)
    .venv/bin/python enregistre.py bilan     # tableau de toutes les prises + verdicts

CE QUE L'OUTIL IMPOSE, ET POURQUOI :

- **La Scarlett, jamais le ReSpeaker.** Mesuré le 26/08 : le DSP du ReSpeaker
  (suppression de bruit, AGC, beamforming) cuit du traitement dans le signal —
  18 dB d'écart constatés sur un même bruit face à un micro nu. Un corpus de
  clonage doit être SEC : tout traitement irréversible à la prise est perdu.
- **La carte est trouvée par sa DESCRIPTION (« Scarlett »), pas par son index
  ni par son nom ALSA.** Son nom de carte est le générique « USB » : cibler
  `CARD=USB` casserait au premier périphérique branché avant elle.
- **S32_LE 48 kHz mono.** La Scarlett expose ses 24 bits utiles dans les MSB
  d'un mot 32 bits (S32 = S24 aligné à gauche) : numpy les lit sans décodage
  3-octets. On sous-échantillonnera VERS les cibles (22,05 k pour piper,
  16 k pour référence zero-shot) — jamais l'inverse : la source reste riche.
- **Contrôle auto après CHAQUE prise** (crête, saturation, plancher de bruit) :
  une prise ratée se refait dans la minute, pas le lendemain quand le
  personnage et la pièce ont changé.

Verdicts (cibles corpus, pas cibles broadcast) :
  crête > -1 dBFS        → SATURÉE, à refaire (l'écrêtage ne se répare pas)
  crête < -20 dBFS       → TROP FAIBLE (on remonterait le bruit en normalisant)
  plancher > -45 dBFS    → PIÈCE/CHAÎNE BRUYANTE (ventilo, ronflement… vérifier)
  sinon                  → OK (idéal : crêtes -12…-3, plancher < -55)

⚠️ Les wav restent dans audio/ qui est GITIGNORÉ — le dépôt est public, un
échantillon de voix suffit à la cloner. Ne jamais forcer avec git add -f.
"""

import re
import select
import signal
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
AUDIO = HERE / "audio"

RATE = 48_000
FMT = "S32_LE"          # 24 bits utiles alignés MSB — voir l'en-tête
BLOCK_S = 0.1           # granularité d'analyse : 100 ms
FULL = float(2**31)     # pleine échelle S32

db = lambda v: 20 * np.log10(max(float(v), 1e-12))


def carte_scarlett():
    """Numéro de carte ALSA de la Scarlett, trouvée par sa description.

    /proc/asound/cards contient « Focusrite Scarlett 4i4 USB » dans la ligne
    de description ; le NOM de carte, lui, n'est que « USB » (générique,
    dépend de l'ordre de branchement) — c'est pour ça qu'on ne cible ni
    l'index ni CARD=USB.
    """
    cards = Path("/proc/asound/cards").read_text()
    for m in re.finditer(r"^\s*(\d+)\s+\[\S+\s*\]:\s+\S+ - (.+)$", cards, re.M):
        if "scarlett" in m.group(2).lower():
            return int(m.group(1))
    sys.exit("Scarlett introuvable dans /proc/asound/cards — branchée ? allumée ?")


def pcm_device():
    # plughw et pas hw : le plug extrait le canal 1 (micro) des canaux
    # d'entrée de la carte quand on demande -c 1.
    return f"plughw:{carte_scarlett()},0"


def _arecord(dest, extra=()):
    return subprocess.Popen(
        ["arecord", "-q", "-D", pcm_device(), "-f", FMT, "-r", str(RATE), "-c", "1",
         *extra, str(dest)],
        stdout=subprocess.PIPE if dest == "-" else None,
    )


# ---------------------------------------------------------------- mode gain

def mode_gain():
    """Vumètre : barre + crête tenue en dBFS, jusqu'à Ctrl-C.

    Le vumètre d'arecord (-V) n'affiche qu'un pourcentage ; pour régler un
    gain on veut des dBFS et une crête tenue (le geste de réglage : parler
    fort en personnage, viser des crêtes à -12…-6, jamais toucher -1).
    """
    proc = _arecord("-", extra=("-t", "raw"))
    blk = int(RATE * BLOCK_S) * 4          # 4 octets par échantillon S32
    peak_hold, hold_until = -120.0, 0.0
    print("Règle le gain Scarlett : crêtes cibles -12…-6 dBFS (Ctrl-C pour finir)")
    try:
        while True:
            data = proc.stdout.read(blk)
            if not data:
                break
            a = np.frombuffer(data, dtype=np.int32).astype(np.float64) / FULL
            pk = db(np.abs(a).max())
            now = time.monotonic()
            if pk >= peak_hold or now > hold_until:
                peak_hold, hold_until = pk, now + 2.0
            n = max(0, min(60, int((pk + 60))))          # échelle -60…0 dBFS
            bar = "#" * n + "-" * (60 - n)
            flag = "  !!! SATURE !!!" if pk > -1.0 else ""
            print(f"\r[{bar}] {pk:6.1f} dBFS  (tenue {peak_hold:6.1f}){flag}  ",
                  end="", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        proc.send_signal(signal.SIGINT)
        proc.wait()
        print()


# --------------------------------------------------------------- mode prise

def analyse(path):
    """Mesures d'une prise. Statistique par blocs de 100 ms, pas RMS global :
    un RMS global ment dès qu'un clic survient (mesuré le 26/08 — le clic d'un
    interrupteur a dominé 12 s de silence de 40 dB)."""
    with wave.open(str(path)) as w:
        assert w.getsampwidth() == 4, f"{path} n'est pas du S32 — pas une prise de cet outil ?"
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int32)
    a = a.astype(np.float64) / FULL
    a -= a.mean()                                        # offset DC éventuel
    blk = int(RATE * BLOCK_S)
    r = np.array([np.sqrt((a[i:i + blk] ** 2).mean())
                  for i in range(0, len(a) - blk, blk)])
    peak = db(np.abs(a).max())
    sat = int((np.abs(a) >= (32700 / 32768)).sum())      # même seuil que les mesures Pi
    return {
        "duree": len(a) / RATE,
        "crete": peak,
        "sature": sat,
        # plancher = percentile 10 des blocs : le fond de pièce ENTRE les mots
        "plancher": db(np.percentile(r, 10)) if len(r) else -120.0,
        "voix": db(np.percentile(r, 90)) if len(r) else -120.0,
    }


def verdict(m):
    if m["crete"] > -1.0 or m["sature"]:
        return "SATURÉE — à refaire (baisser le gain)"
    if m["crete"] < -20.0:
        return "TROP FAIBLE — monter le gain"
    if m["plancher"] > -45.0:
        return "BRUYANTE — vérifier pièce/chaîne (ventilo ? ronflement ?)"
    return "OK"


def mode_prise(nom):
    AUDIO.mkdir(exist_ok=True)
    # p1, p2, … par prise du même nom : rien n'est jamais écrasé, le tri se
    # fait à l'écoute (la meilleure prise gagne, les autres restent).
    n = 1 + max((int(m.group(1)) for f in AUDIO.glob(f"{nom}-p*.wav")
                 if (m := re.search(r"-p(\d+)\.wav$", f.name))), default=0)
    dest = AUDIO / f"{nom}-p{n}.wav"
    print(f"── prise {dest.name} — JOUER, pas lire (personnage, énergie de rue)")
    print("   Entrée pour arrêter…")
    proc = _arecord(dest)
    t0 = time.monotonic()
    try:
        while proc.poll() is None:
            # select : affiche le chrono sans bloquer sur stdin
            if select.select([sys.stdin], [], [], 0.5)[0]:
                sys.stdin.readline()
                break
            print(f"\r   ● {time.monotonic() - t0:5.1f} s", end="", flush=True)
    finally:
        # SIGINT et pas kill : arecord finalise l'en-tête WAV sur SIGINT,
        # un kill laisserait un fichier à l'en-tête faux (durée 0).
        proc.send_signal(signal.SIGINT)
        proc.wait()
    print()
    m = analyse(dest)
    print(f"   {m['duree']:.1f} s | crête {m['crete']:.1f} dBFS | voix (p90) "
          f"{m['voix']:.1f} | plancher {m['plancher']:.1f} | saturés {m['sature']}")
    print(f"   → {verdict(m)}")


# --------------------------------------------------------------- mode bilan

def mode_bilan():
    prises = sorted(AUDIO.glob("*.wav"))
    if not prises:
        print("aucune prise dans audio/")
        return
    tot = 0.0
    print(f"{'prise':<32} {'durée':>7} {'crête':>7} {'plancher':>9}  verdict")
    for p in prises:
        m = analyse(p)
        tot += m["duree"]
        print(f"{p.name:<32} {m['duree']:>6.1f}s {m['crete']:>6.1f} "
              f"{m['plancher']:>8.1f}  {verdict(m)}")
    print(f"\ntotal : {tot / 60:.1f} min "
          f"(palier minimal V3 : quelques minutes ; zero-shot : ≥ 10 s propres)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "gain":
        mode_gain()
    elif mode == "prise" and len(sys.argv) > 2:
        mode_prise(re.sub(r"[^a-z0-9-]", "-", sys.argv[2].lower()))
    elif mode == "bilan":
        mode_bilan()
    else:
        sys.exit(__doc__.split("\n\n")[1])
