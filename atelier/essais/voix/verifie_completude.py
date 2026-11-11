#!/usr/bin/env python3
"""Contrôle de complétude des synthèses clonées : l'ASR relit ce que le TTS a
dit, et on vérifie que la FIN du texte source y est. Détecte la coupure
prématurée (le mode de défaillance des modèles autorégressifs sur les énoncés
longs) sans attendre une écoute humaine. Whisper small : le but est de
reconnaître les derniers mots, pas de juger la diction."""
import glob, sys
from faster_whisper import WhisperModel

FINS = {  # derniers mots attendus (l'ASR peut varier l'orthographe : on
          # cherche le DERNIER mot significatif, pas la chaîne exacte)
    "1-salutation": "mords pas",
    "2-question": "cette rue",
    "3-sifflantes": "passe ici",
    "4-attaques": "cogne",
    "5-chiffres": "patience",
    "6-r-ponse": "longtemps que moi",
}
m = WhisperModel("small", device="cpu", compute_type="int8")
for dossier in sys.argv[1:]:
    print(f"── {dossier}")
    for prefixe, fin in FINS.items():
        fichiers = glob.glob(f"{dossier}/{prefixe}*.wav")
        if not fichiers:
            print(f"  {prefixe:<14} (absent)"); continue
        seg, _ = m.transcribe(fichiers[0], language="fr")
        texte = " ".join(s.text.strip() for s in seg)
        dernier = fin.split()[-1].lower()
        ok = dernier in texte.lower()[-80:]
        print(f"  {prefixe:<14} {'✅ complet' if ok else '⚠️ FIN ABSENTE'} — fin lue : « …{texte[-60:]} »")
