#!/usr/bin/env python3
"""Nivelle le volume phrase par phrase — remède au « volume parfois inégal ».

Mesuré le 26/08 : 14,9 dB d'écart entre phrases dans une synthèse clonée…
et 16,2 dB dans la prise HUMAINE de référence. Le TTS ne dérègle donc rien,
il reproduit fidèlement la dynamique naturelle de David. Mais Didier joue
DANS LA RUE et il EST la sono : une phrase 15 dB plus bas est perdue pour le
public. C'est un besoin de diffusion, pas un défaut de synthèse — donc ça se
traite en AVAL, ici, et jamais en abîmant le corpus.

Principe : découpe sur les silences, ramène chaque segment de parole à un RMS
cible, avec deux garde-fous —
  - gain plafonné (+12 dB) : sinon on remonte le bruit de fond et les
    respirations au niveau de la voix ;
  - transitions en fondu de 30 ms : un saut de gain net s'entend comme un clic.
On ne touche PAS aux silences (pas de pompage entre les phrases).
"""
import sys
import numpy as np, soundfile as sf

CIBLE_DB = -23.0
GAIN_MAX_DB = float(__import__("os").environ.get("GAIN_MAX_DB", 12.0))
SEUIL_DB = -50.0
FONDU_S = 0.03

def segments(a, fs):
    blk = int(0.05 * fs)
    rms = np.array([np.sqrt((a[i:i+blk]**2).mean()) for i in range(0, len(a)-blk, blk)])
    actif = 20*np.log10(rms + 1e-12) > SEUIL_DB
    out, debut, creux = [], None, 0
    for i, v in enumerate(actif):
        if v:
            if debut is None: debut = i
            creux = 0
        elif debut is not None:
            creux += 1
            if creux * 0.05 >= 0.30:
                out.append((debut*blk, (i-creux)*blk)); debut = None
    if debut is not None: out.append((debut*blk, len(a)))
    return out

def nivelle(src, dst):
    a, fs = sf.read(src)
    if a.ndim > 1: a = a[:, 0]
    b = a.copy()
    n_fondu = int(FONDU_S * fs)
    ecarts = []
    for d, f in segments(a, fs):
        r = np.sqrt((a[d:f]**2).mean())
        if r < 1e-6: continue
        g = 10**(CIBLE_DB/20) / r
        g = min(g, 10**(GAIN_MAX_DB/20))
        ecarts.append(20*np.log10(r))
        env = np.full(f-d, g)
        k = min(n_fondu, (f-d)//2)
        env[:k] = np.linspace(1.0, g, k)          # fondu depuis le gain unité
        env[-k:] = np.linspace(g, 1.0, k)
        b[d:f] = a[d:f] * env
    pic = np.abs(b).max()
    if pic > 0.89: b *= 0.89 / pic
    sf.write(dst, b, fs)
    print(f"{src} → {dst} : {len(ecarts)} segments, "
          f"écart AVANT {max(ecarts)-min(ecarts):.1f} dB")
    a2, _ = sf.read(dst)
    e2 = [20*np.log10(np.sqrt((a2[d:f]**2).mean())+1e-12) for d, f in segments(a2, fs)]
    print(f"   écart APRÈS : {max(e2)-min(e2):.1f} dB")

if __name__ == "__main__":
    nivelle(sys.argv[1], sys.argv[2])
