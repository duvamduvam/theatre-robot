#!/usr/bin/env python3
"""Banc des voix Kyutai Pocket TTS pour Didier — de VRAIES voix nouvelles,
sans enregistrer personne.

QUOI : deux passes, sur la réplique « qui bafouille » (celle que David a
       retenue au banc des costumes du 01/11) :
  1. `catalogue` : les voix prédéfinies du modèle, en français (`french_24l`).
     Ce sont des états précalculés par Kyutai à partir de donneurs publics :
     pas la voix de David (il l'a exclu le 01/11 : « je ne veux pas ma voix »).
  2. `lourdes` : pour « des voix plus lourdes », on n'ajoute PAS un effet en
     sortie — on fabrique une RÉFÉRENCE grave (enregistrement d'origine d'une
     voix du catalogue, descendu de N demi-tons par rééchantillonnage) et on
     CLONE dessus. Le modèle génère alors nativement une voix grave, avec sa
     propre prosodie, sans artefact de pitch-shift sur la parole produite.
Usage : .venv/bin/python voix_kyutai.py [catalogue|lourdes] [voix...]
Sortie : sorties/kyutai/*.wav (hors git — dépôt public).

Piège : les voix du catalogue sont des locuteurs anglais/allemands/italiens…
  parlant français → accent possible. C'est à l'écoute de dire si c'est un
  défaut ou un caractère.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from scipy import signal

SORTIE = Path("sorties/kyutai")
TEXTE = ("Bonjour ! Je suis… euh… Didier. Le robot le plus… le plus "
         "intelligent. Du quartier. Non. Si ! Attendez. Je redémarre. "
         "Voilà. Tout va très bien. Enfin… presque.")
# Voix masculines du catalogue (noms lus dans pocket_tts/utils/utils.py,
# _ORIGINS_OF_PREDEFINED_VOICES) + estelle, la voix française de référence.
CATALOGUE = ["estelle", "marius", "javert", "jean", "charles", "paul", "george",
             "michael", "bill_boerst", "peter_yearsley", "stuart_bell",
             "juergen", "giovanni", "rafael", "daan"]


def f0_median(x: np.ndarray, sr: int) -> float:
    """Hauteur médiane (Hz) par autocorrélation sur les trames voisées —
    grossier mais suffisant pour CLASSER les voix du plus grave au plus aigu."""
    n, hop = int(0.04 * sr), int(0.01 * sr)
    lo, hi = int(sr / 300), int(sr / 60)
    rms_seuil = 0.3 * np.sqrt((x ** 2).mean())
    f0s = []
    for i in range(0, len(x) - n, hop):
        t = x[i:i + n] - x[i:i + n].mean()
        if np.sqrt((t ** 2).mean()) < rms_seuil:
            continue
        ac = np.correlate(t, t, "full")[n - 1:]
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] > 0.5 * ac[0]:
            f0s.append(sr / lag)
    return float(np.median(f0s)) if f0s else float("nan")


def ecrit(nom: str, a: np.ndarray, sr: int) -> None:
    pic = np.abs(a).max() or 1.0
    a = a * (10 ** (-20 / 20) / (np.sqrt((a ** 2).mean()) or 1.0))  # même sonie
    a = np.clip(a, -0.95, 0.95)
    sf.write(SORTIE / f"{nom}.wav", a, sr)
    print(f"  {nom:34s} {len(a) / sr:5.1f} s   F0 ≈ {f0_median(a, sr):5.0f} Hz")


def reference_grave(nom: str, demi_tons: float, sr_modele: int) -> torch.Tensor:
    """Enregistrement d'origine de la voix `nom`, descendu de `demi_tons`."""
    from pocket_tts.utils.utils import _ORIGINS_OF_PREDEFINED_VOICES
    from pocket_tts.utils.utils import download_if_necessary
    chemin = download_if_necessary(_ORIGINS_OF_PREDEFINED_VOICES[nom])
    x, sr = sf.read(chemin, always_2d=True)
    x = x.mean(axis=1)[: sr * 30]                      # mono, 30 s max
    x = signal.resample_poly(x, sr_modele, sr)          # au taux du modèle
    f = 2 ** (-demi_tons / 12)                         # < 1 → plus grave
    x = signal.resample_poly(x, 1000, int(round(1000 * f)))
    return torch.tensor(x, dtype=torch.float32)[None, :]


def main() -> None:
    from pocket_tts import TTSModel
    mode = sys.argv[1] if len(sys.argv) > 1 else "catalogue"
    choix = sys.argv[2:]
    SORTIE.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(7)  # rejouable
    m = TTSModel.load_model(language="french_24l")
    sr = m.sample_rate

    if mode == "catalogue":
        for nom in choix or CATALOGUE:
            etat = m.get_state_for_audio_prompt(nom)
            ecrit(f"cat-{nom}", m.generate_audio(etat, TEXTE).squeeze().numpy(), sr)
    elif mode == "lourdes":
        for nom in choix:
            for dt in (4, 7):
                etat = m.get_state_for_audio_prompt(reference_grave(nom, dt, sr))
                ecrit(f"lourd-{nom}-moins{dt}",
                      m.generate_audio(etat, TEXTE).squeeze().numpy(), sr)


if __name__ == "__main__":
    main()
