#!/usr/bin/env python3
"""Banc d'essai Pocket TTS — mesure ce qui décide, pas ce qui rassure.

Chantier voix, lot V0b (docs/etude-voix-didier.md §7). Ce script tourne sur le
PC ET sur le Pi 5 : c'est le même code qui produira les deux jeux de chiffres,
donc ils seront comparables. Le PC donne la référence x86 avant samedi, le Pi
donne la réponse.

CE QU'ON MESURE ET POURQUOI :

- **TTFA** (time to first audio) : le délai avant que le premier son sorte.
  C'est ce que le public ressent, et c'est CE chiffre qui fait qu'un robot
  paraît vif ou emprunté — pas le débit moyen. Mesuré sur le flux, comme en
  prod (le pipeline de conversation diffuse phrase par phrase).
- **RTF** (temps de génération / durée audio) : < 1 = plus rapide que la
  parole. En dessous de 1 il faut une marge, parce que le Pi fera AUSSI tourner
  la vision pendant ce temps.
- **Durée produite vs attendue** : détecte la COUPURE PRÉMATURÉE, le mode de
  défaillance documenté des modèles autorégressifs sur les énoncés longs. Une
  réponse de 25 s qui rend 8 s d'audio est un échec silencieux — rien ne plante,
  la phrase est juste tronquée. C'est pour ça qu'on compare, au lieu de se
  contenter d'écouter le début.

Le modèle est chargé UNE FOIS puis réutilisé : c'est ainsi que tourne la prod
(leçon déjà apprise sur piper, qui doit être in-process). Mesurer avec un
chargement par phrase gonflerait tout d'un facteur ridicule.

Usage :
    ./.venv/bin/python bench.py                        # français, voix Estelle
    ./.venv/bin/python bench.py --quantize             # int8, ce qu'on ferait sur le Pi
    ./.venv/bin/python bench.py --voice audio/reference.wav   # clonage de David
"""

import argparse
import csv
import re
import time
from pathlib import Path

import soundfile as sf
import torch

from pocket_tts import TTSModel
from pocket_tts.default_parameters import get_default_voice_for_language

ICI = Path(__file__).parent
SORTIES = ICI / "sorties"

# Débit de parole retenu pour estimer la durée ATTENDUE d'un texte. ~13 phonèmes
# par seconde en français courant donne ~2,5 mots/s en diction posée ; on prend
# une borne BASSE volontairement généreuse (2,2) pour ne signaler une troncature
# que lorsqu'elle est franche, et non parce que le modèle parle vite.
MOTS_PAR_SECONDE = 2.2
# En dessous de ce ratio (produit / attendu), on crie à la coupure.
SEUIL_TRONCATURE = 0.6


def charger_phrases(chemin: Path) -> list[tuple[str, str]]:
    """Lit phrases-v0.txt → [(titre, texte)]. Les lignes '#' sont des commentaires,
    sauf '## ' qui ouvre un item. Le dialogue en alternance est ignoré ici : il
    se monte à la main avec les prises de David."""
    items, titre, buf = [], None, []
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        # Fin des items : le bloc dialogue. Sans ce break, les lignes de
        # CONTINUATION des répliques [MACHINE] multi-lignes (qui ne commencent
        # ni par # ni par [) fuyaient dans le texte de l'item 6 — bug trouvé le
        # 26/08 par le contrôle ASR de complétude : les trois jeux de synthèse
        # finissaient par « …mais les gens répondent », une ligne du dialogue.
        if "DIALOGUE EN ALTERNANCE" in ligne:
            break
        if ligne.startswith("## "):
            if titre:
                items.append((titre, " ".join(buf).strip()))
            titre, buf = ligne[3:].strip(), []
        elif ligne.startswith("#") or ligne.startswith("["):
            continue
        elif titre and ligne.strip():
            buf.append(ligne.strip())
    if titre and buf:
        items.append((titre, " ".join(buf).strip()))
    return [(t, x) for t, x in items if x]


def slug(titre: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", titre.lower()).strip("-")[:40]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--language", default="french_24l",
                   help="français = 'french_24l' (variante 24 couches, NON distillée "
                        "et annoncée en preview par Kyutai — le '100M / 6x temps réel' "
                        "vaut pour l'anglais distillé, pas pour elle)")
    p.add_argument("--voice", default=None,
                   help="wav de référence à cloner ; défaut = voix intégrée (Estelle en FR)")
    p.add_argument("--quantize", action="store_true",
                   help="int8 — la configuration réaliste pour un Raspberry Pi")
    p.add_argument("--threads", type=int, default=None,
                   help="limite les cœurs torch (le Pi 5 en a 4, et la vision en veut)")
    p.add_argument("--phrases", type=Path, default=ICI / "phrases-v0.txt")
    p.add_argument("--csv", type=Path, default=ICI / "bench.csv")
    args = p.parse_args()

    if args.threads:
        torch.set_num_threads(args.threads)

    SORTIES.mkdir(exist_ok=True)
    phrases = charger_phrases(args.phrases)
    print(f"{len(phrases)} phrases — langue={args.language} quantize={args.quantize} "
          f"threads={torch.get_num_threads()}")

    t0 = time.perf_counter()
    modele = TTSModel.load_model(language=args.language, quantize=args.quantize)
    t_charge = time.perf_counter() - t0
    print(f"chargement du modèle : {t_charge:.1f} s")

    voix = args.voice or get_default_voice_for_language(args.language, None)
    etat = modele.get_state_for_audio_prompt(voix)
    print(f"voix : {voix}\n")

    lignes = []
    for titre, texte in phrases:
        mots = len(texte.split())
        attendu = mots / MOTS_PAR_SECONDE

        # On passe par le FLUX pour isoler le TTFA. generate_audio() ne le
        # permettrait pas : il ne rend la main qu'une fois tout produit.
        debut = time.perf_counter()
        ttfa, morceaux = None, []
        for bloc in modele.generate_audio_stream(etat, texte):
            if ttfa is None:
                ttfa = time.perf_counter() - debut
            morceaux.append(bloc)
        duree_calcul = time.perf_counter() - debut

        audio = torch.cat(morceaux, dim=-1).squeeze()
        duree_audio = audio.shape[-1] / modele.sample_rate
        rtf = duree_calcul / duree_audio if duree_audio else float("inf")
        ratio = duree_audio / attendu if attendu else 0.0

        nom = SORTIES / f"{slug(titre)}.wav"
        sf.write(nom, audio.cpu().numpy(), modele.sample_rate)

        alerte = "  ⚠️ TRONQUÉ ?" if ratio < SEUIL_TRONCATURE else ""
        print(f"{titre[:34]:<34} {duree_audio:5.1f}s (attendu ~{attendu:4.1f}s) "
              f"RTF={rtf:4.2f} TTFA={ttfa:5.2f}s{alerte}")

        lignes.append(dict(phrase=titre, mots=mots, duree_audio_s=round(duree_audio, 2),
                           duree_attendue_s=round(attendu, 2), ratio=round(ratio, 2),
                           calcul_s=round(duree_calcul, 2), rtf=round(rtf, 3),
                           ttfa_s=round(ttfa or 0, 3), fichier=nom.name))

    with args.csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0]))
        w.writeheader()
        w.writerows(lignes)

    rtfs = [l["rtf"] for l in lignes]
    print(f"\nRTF médian {sorted(rtfs)[len(rtfs) // 2]:.2f} — pire {max(rtfs):.2f}")
    print(f"CSV : {args.csv}   audio : {SORTIES}/")
    print("\n⚠️ Ce banc mesure le TEMPS, pas la QUALITÉ. Est-ce que c'est du bon "
          "français, est-ce que ça ressemble à David, est-ce que ça tient 25 s "
          "sans devenir monotone : ça s'écoute, et seul un humain peut le dire.")


if __name__ == "__main__":
    main()
