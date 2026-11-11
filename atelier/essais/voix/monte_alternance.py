#!/usr/bin/env python3
"""Monte le dialogue en alternance David réel / machine clonée — banc V0.

Produit sorties/alternance-david-machine.wav : les répliques [DAVID] sont les
PRISES RÉELLES de la séance du 26/08 (SM58, voix sèche), les répliques
[MACHINE] sont synthétisées par Pocket TTS avec le clone zero-shot de la
référence 60 s. C'est LE test de l'étude (§7 V0) : la rupture de personnage
ne s'entend qu'en juxtaposition — un extrait isolé passe toujours.

Choix gravés ici :
- égalisation en RMS par réplique (l'étude : « normaliser en sonie avant
  d'écoute, sinon on compare des volumes ») — RMS suffit pour un banc ;
- trim des silences des prises réelles (seuil -45 dBFS par blocs de 50 ms,
  marge 150 ms) : les prises font 12 s pour 2 s de parole ;
- tout à 24 kHz (le taux de sortie de Pocket TTS), resample propre
  scipy.resample_poly (48k → 24k = facteur entier, pas d'artefact) ;
- 600 ms de silence entre répliques : le rythme d'un vrai échange.
"""
import numpy as np, soundfile as sf, glob, re
from pathlib import Path
from scipy.signal import resample_poly
from pocket_tts import TTSModel

FS = 24_000
db = lambda v: 20*np.log10(max(float(v), 1e-12))

def derniere_prise(nom):
    """La prise -pN la plus récente d'un nom donné (rien n'est écrasé à la
    prise, donc le dernier numéro est la version retenue)."""
    c = sorted(glob.glob(f"audio/{nom}-p*.wav"),
               key=lambda f: int(re.search(r"-p(\d+)\.wav$", f).group(1)))
    return c[-1]

def charge_prise(nom):
    a, fs = sf.read(derniere_prise(nom))
    if a.ndim > 1: a = a[:, 0]
    if fs != FS: a = resample_poly(a, FS, fs)
    # trim : du premier au dernier bloc de 50 ms au-dessus de -45 dBFS
    blk = FS // 20
    rms = np.array([np.sqrt((a[i:i+blk]**2).mean()) for i in range(0, len(a)-blk, blk)])
    actifs = np.where(20*np.log10(rms + 1e-12) > -45)[0]
    if not len(actifs): raise SystemExit(f"{nom} : aucune parole détectée ?")
    d = max(0, actifs[0]*blk - 3*blk); f = min(len(a), (actifs[-1]+1)*blk + 3*blk)
    return a[d:f]

def egalise(a, cible_db=-23.0):
    r = np.sqrt((a**2).mean())
    return a * (10**(cible_db/20) / max(r, 1e-12))

REPLIQUES_MACHINE = [
    "Je ne suis jamais parti. C'est vous qui bougez tout le temps.",
    "Non. Ça m'occupe. J'ai peu de distractions, ici.",
    "Je ne sais pas si c'est le mot. Disons que quand la rue est vide, je "
    "compte les pavés. Quand elle est pleine, je compte les gens. Ça revient "
    "un peu au même, mais les gens répondent.",
    "Vous répondez lentement. Mais vous répondez.",
]

print("chargement du modèle + état de voix (référence 60 s)…")
modele = TTSModel.load_model(language="french_24l")
etat = modele.get_state_for_audio_prompt("audio/reference-p1.wav")
assert modele.sample_rate == FS, f"taux inattendu : {modele.sample_rate}"

gap = np.zeros(int(0.6 * FS))
montage = []
for i, texte in enumerate(REPLIQUES_MACHINE, 1):
    david = egalise(charge_prise(f"dialogue-{i}"))
    machine = egalise(modele.generate_audio(etat, texte).squeeze().cpu().numpy())
    montage += [david, gap, machine, gap]
    print(f"  réplique {i} : David {len(david)/FS:.1f} s + machine {len(machine)/FS:.1f} s")

out = np.concatenate(montage)
pic = np.abs(out).max()
if pic > 0.89: out *= 0.89 / pic          # garde-fou anti-écrêtage après égalisation
sf.write("sorties/alternance-david-machine.wav", out, FS)
print(f"→ sorties/alternance-david-machine.wav ({len(out)/FS:.1f} s)")
