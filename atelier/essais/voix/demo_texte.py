#!/usr/bin/env python3
"""Synthétise un texte INÉDIT avec le clone de David — preuve que la voix est
générée et non recollée depuis les prises.

Génère BLOC PAR BLOC (séparés par une ligne vide) comme le fera la prod, qui
diffuse phrase par phrase : ça borne la dérive des modèles autorégressifs et
donne un TTFA court. Un bloc raté ne contamine pas les suivants.
"""
import sys, time
import numpy as np, soundfile as sf
from pathlib import Path
from pocket_tts import TTSModel

voix = sys.argv[1] if len(sys.argv) > 1 else "audio/reference-p1-15s.wav"
quant = "--quantize" in sys.argv
sortie = Path("sorties/demo-texte-inedit.wav")

blocs = [b.strip().replace("\n", " ") for b in
         Path("texte-demo-2min.txt").read_text(encoding="utf-8").split("\n\n")
         if b.strip() and not b.startswith("#")]
print(f"{len(blocs)} blocs, voix={voix}, quantize={quant}")

m = TTSModel.load_model(language="french_24l", quantize=quant)
etat = m.get_state_for_audio_prompt(voix)
gap = np.zeros(int(0.45 * m.sample_rate))       # respiration entre blocs

morceaux, t0 = [], time.perf_counter()
for i, b in enumerate(blocs, 1):
    a = m.generate_audio(etat, b).squeeze().cpu().numpy()
    morceaux += [a, gap]
    print(f"  bloc {i}/{len(blocs)} : {len(a)/m.sample_rate:5.1f} s "
          f"({len(b.split())} mots)")
out = np.concatenate(morceaux)
duree = len(out) / m.sample_rate
calcul = time.perf_counter() - t0
pic = np.abs(out).max()
if pic > 0.89: out *= 0.89 / pic
sf.write(sortie, out, m.sample_rate)
print(f"→ {sortie} : {duree:.1f} s audio en {calcul:.1f} s (RTF {calcul/duree:.2f})")
