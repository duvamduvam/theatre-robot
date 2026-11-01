#!/usr/bin/env python3
"""Mesure F0 (hauteur) et régularité de niveau — pour trancher deux questions
posées par David le 26/08 : « c'est ma voix normale, pas la ventriloquie » et
« le volume est parfois inégal ».

F0 par autocorrélation sur trames voisées de 40 ms. On ne cherche pas la
précision d'un correcteur de hauteur : on veut savoir si le CLONE reproduit la
hauteur de la RÉFÉRENCE (auquel cas le clone est fidèle et c'est la référence
qui n'était pas en ventriloquie) ou s'il la ramène vers une voix moyenne.
"""
import sys
import numpy as np, soundfile as sf
from scipy.signal import resample_poly

FS = 16_000            # suffisant pour du F0 (plage 70-350 Hz)
def charge(p):
    a, fs = sf.read(p)
    if a.ndim > 1: a = a[:, 0]
    if fs != FS: a = resample_poly(a, FS, fs)
    return a - a.mean()

def f0_trames(a, fmin=70, fmax=350):
    N = int(0.04 * FS); hop = N // 2
    lo, hi = FS // fmax, FS // fmin
    out = []
    for i in range(0, len(a) - N, hop):
        x = a[i:i+N]
        e = np.sqrt((x**2).mean())
        if e < 10**(-45/20):          # trame trop faible = non voisée
            continue
        x = x - x.mean()
        r = np.correlate(x, x, "full")[N-1:]
        r /= (r[0] + 1e-12)
        seg = r[lo:hi]
        k = int(np.argmax(seg)) + lo
        if seg.max() > 0.35:          # seuil de périodicité = voisement
            out.append(FS / k)
    return np.array(out)

def niveaux_par_bloc(a, seuil_db=-50, min_gap=0.30):
    """Découpe sur les silences (les blocs sont séparés de 0,45 s) et rend le
    RMS de chaque bloc : c'est ça qu'on entend comme « volume inégal »."""
    blk = int(0.05 * FS)
    rms = np.array([np.sqrt((a[i:i+blk]**2).mean()) for i in range(0, len(a)-blk, blk)])
    actif = 20*np.log10(rms + 1e-12) > seuil_db
    blocs, debut = [], None
    creux = 0
    for i, v in enumerate(actif):
        if v:
            if debut is None: debut = i
            creux = 0
        elif debut is not None:
            creux += 1
            if creux * 0.05 >= min_gap:
                blocs.append((debut*blk, (i-creux)*blk)); debut = None
    if debut is not None: blocs.append((debut*blk, len(a)))
    return [(d/FS, f/FS, 20*np.log10(np.sqrt((a[d:f]**2).mean()) + 1e-12)) for d, f in blocs]

for p in sys.argv[1:]:
    a = charge(p)
    f = f0_trames(a)
    print(f"\n── {p}")
    if len(f):
        print(f"   F0 : médiane {np.median(f):5.1f} Hz | p10 {np.percentile(f,10):5.1f} "
              f"| p90 {np.percentile(f,90):5.1f} | étendue p90-p10 = {np.percentile(f,90)-np.percentile(f,10):4.1f} Hz")
    bl = niveaux_par_bloc(a)
    if len(bl) > 1:
        db = [b[2] for b in bl]
        print(f"   niveau par bloc ({len(bl)} blocs) : " + " ".join(f"{d:.0f}" for d in db))
        print(f"   → écart max entre blocs : {max(db)-min(db):4.1f} dB")
