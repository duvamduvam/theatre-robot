#!/usr/bin/env python3
"""Fabrique les 3 sons des bugs joués (lot I0, étude improvisation §2.3) — synthèse, rien d'enregistré.

    python3 sons_bugs_joues.py <dossier>            # bips + démarrage (stdlib seule)
    python3 sons_bugs_joues.py <dossier> --voix <didier.onnx>   # + bégaiement (Piper)

Les sons vont dans les AUDIOS PRIVÉS (`$DIDIER_MEDIAS_PRIVES/audios/bugs-joues/`, jamais dans le
dépôt public), puis au manifeste (`python3 -m theatre_contrats.donnees manifeste-audios data`) :
voir docs/operations.md § « Audios privés ». La voix de Didier (Piper fr_FR-siwis-medium) vit dans
l'image de la vision, d'où la commande documentée dans packages/didier_jeu/README.md (§ Bugs joués).

Format : WAV mono 16 bits, 22 050 Hz — le manifeste ne lit la durée que des wav, et la garantie
« son ≤ 4 s » des bugs joués (theatre_contrats.bugs_joues.SON_MAX_S) se juge sur cette durée.
Déterministe : mêmes octets à chaque fabrication (aucun aléa, aucune date dans le fichier).
"""
import argparse
import io
import math
import os
import struct
import wave

TAUX = 22_050
AMPLITUDE = 0.6          # marge sous la saturation (la mixette remonte le niveau)
FONDU_S = 0.005          # 5 ms d'attaque et de relâche : pas de claquement


def _enveloppe(i, n, fondu=int(FONDU_S * TAUX)):
    return min(1.0, i / fondu if fondu else 1.0, (n - 1 - i) / fondu if fondu else 1.0)


def bip(freq, duree_s, volume=1.0):
    n = int(duree_s * TAUX)
    return [volume * _enveloppe(i, n) * math.sin(2 * math.pi * freq * i / TAUX) for i in range(n)]


def silence(duree_s):
    return [0.0] * int(duree_s * TAUX)


def cloche(freq, duree_s, volume=1.0):
    """Note de cloche douce : fondamentale + octave, décroissance exponentielle."""
    n = int(duree_s * TAUX)
    return [volume * _enveloppe(i, n) * math.exp(-3.0 * i / n)
            * (0.75 * math.sin(2 * math.pi * freq * i / TAUX) + 0.25 * math.sin(4 * math.pi * freq * i / TAUX))
            for i in range(n)]


def balayage(f0, f1, duree_s, volume=1.0):
    """Montée de fréquence (ronflement de mise sous tension), phase continue."""
    n = int(duree_s * TAUX)
    echantillons, phase = [], 0.0
    for i in range(n):
        f = f0 + (f1 - f0) * i / n
        phase += 2 * math.pi * f / TAUX
        echantillons.append(volume * _enveloppe(i, n) * (i / n) * (0.7 * math.sin(phase) + 0.3 * math.sin(3 * phase)))
    return echantillons


def mixer(*pistes):
    n = max(len(p) for p in pistes)
    return [sum(p[i] for p in pistes if i < len(p)) for i in range(n)]


def bips_mise_a_jour():
    """« Mise à jour 3 sur 47 » : bips de progression réguliers, puis trois bips montants
    (3,2 s)."""
    sons = []
    for _ in range(5):
        sons += bip(880, 0.08) + silence(0.32)
    for f in (660, 880, 1320):
        sons += bip(f, 0.12) + silence(0.06)
    return sons + silence(0.25)


def demarrage():
    """Faux redémarrage : mise sous tension qui monte, puis accord de démarrage (3,6 s)."""
    monte = balayage(70, 420, 1.3, volume=0.8)
    accord = []
    for k, f in enumerate((523.25, 659.25, 783.99, 1046.5)):     # do mi sol do
        accord = mixer(accord, silence(0.12 * k) + cloche(f, 2.0, volume=0.35))
    return monte + silence(0.1) + accord


def _pcm_vers_flottants(pcm):
    n = len(pcm) // 2
    return [v / 32768.0 for v in struct.unpack("<{}h".format(n), pcm[:2 * n])]


def _reechantillonner(echantillons, taux_source):
    if taux_source == TAUX:
        return echantillons
    n = int(len(echantillons) * TAUX / taux_source)
    return [echantillons[min(len(echantillons) - 1, int(i * taux_source / TAUX))] for i in range(n)]


def _syllabe(echantillons, duree_s=0.26, seuil=0.04):
    """La première syllabe : depuis la première attaque au-dessus du seuil, duree_s."""
    debut = next((i for i, v in enumerate(echantillons) if abs(v) > seuil), 0)
    morceau = echantillons[debut:debut + int(duree_s * TAUX)]
    return [v * _enveloppe(i, len(morceau)) for i, v in enumerate(morceau)]


def begaiement(chemin_voix):
    """La voix de Didier bute sur « je » quatre fois, puis repart (≈ 2,2 s)."""
    from piper import PiperVoice   # image vision seulement
    voix = PiperVoice.load(chemin_voix)

    def dire(texte):
        tampon = io.BytesIO()
        with wave.open(tampon, "wb") as w:
            voix.synthesize_wav(texte, w)
        tampon.seek(0)
        with wave.open(tampon, "rb") as r:
            taux, pcm = r.getframerate(), r.readframes(r.getnframes())
        return _reechantillonner(_pcm_vers_flottants(pcm), taux)

    phrase = dire("Je suis là.")
    # « Je » dit SEUL : dans la phrase, la voyelle est trop courte pour être reconnue en boucle
    # (vérifié par transcription, 22/11).
    je = _syllabe(dire("Je"))
    sons = []
    for k in range(4):
        sons += je + silence(0.03 + 0.02 * k)     # coupure de plus en plus longue : ça cale
    # La phrase entière, normalisée à l'amplitude des bips.
    crete = max(1e-6, max(abs(v) for v in phrase))
    return [v / crete for v in sons + phrase]


def ecrire_wav(chemin, echantillons):
    crete = max(1e-6, max(abs(v) for v in echantillons))
    echelle = AMPLITUDE * 32767 / max(1.0, crete)
    donnees = struct.pack("<{}h".format(len(echantillons)),
                          *(int(max(-32767, min(32767, round(v * echelle)))) for v in echantillons))
    with wave.open(chemin, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAUX)
        w.writeframes(donnees)
    return len(echantillons) / TAUX


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dossier")
    parser.add_argument("--voix", help="modèle Piper de Didier (.onnx, son .json à côté)")
    args = parser.parse_args()
    os.makedirs(args.dossier, exist_ok=True)
    sons = {"bips-mise-a-jour.wav": bips_mise_a_jour, "demarrage.wav": demarrage}
    if args.voix:
        sons["begaiement.wav"] = lambda: begaiement(args.voix)
    for nom, fabrique in sons.items():
        duree = ecrire_wav(os.path.join(args.dossier, nom), fabrique())
        print("{} : {:.2f} s".format(nom, duree))


if __name__ == "__main__":
    main()
