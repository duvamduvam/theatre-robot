#!/usr/bin/env python3
"""Banc d'écoute des « costumes vocaux » de Didier — une même réplique,
déclinée en une douzaine de traitements, pour que David choisisse À L'OREILLE.

QUOI : synthétise la réplique avec la VRAIE voix de prod (`didier.onnx`, piper
       in-process comme vision/ai/tts_piper.py), puis applique chaque costume
       en numpy/scipy pur. Un WAV par costume dans sorties/costumes/.
POURQUOI : étude répétition simulée §10 (palette du 07/10, jamais codée) +
       idées « déglingos » du 01/11. On ÉCOUTE avant de coder quoi que ce soit
       dans vision/audio/effects.py : ce banc ne touche pas à la prod.

Exécution : dans le conteneur vision PC (piper + modèle + effects.py y sont) :
    docker cp costumes.py dadou-vision-x86-container:/tmp/
    docker exec dadou-vision-x86-container bash -c \
      'cd /tmp && PYTHONPATH=/home/ros2_ws/src/vision python3 costumes.py'
    docker cp dadou-vision-x86-container:/tmp/costumes sorties/

Pièges :
- Les décalages de hauteur sont faits par RÉÉCHANTILLONNAGE : hauteur et débit
  bougent ensemble (effet « disque/cassette »). Voulu ici, c'est le gag ; un
  vrai pitch-shift à débit constant (rubberband) serait un autre chantier.
- Aucune sortie audio ne va dans git (dépôt public — voir README).
"""
from __future__ import annotations

import io
import wave
from pathlib import Path

import numpy as np
from scipy import signal

VOIX = "/home/ros2_ws/src/vision/medias/voices/didier.onnx"
SORTIE = Path("costumes")
REPLIQUE = ("Bonjour ! Je suis Didier, le robot le plus intelligent du quartier. "
            "Attendez, je redémarre. Voilà ! Tout va très bien, merci.")
# Version écrite pour bafouiller : le texte pilote la prosodie (étude voix §5).
REPLIQUE_BAFOUILLE = ("Bonjour ! Je suis… euh… Didier. Le robot le plus… le plus "
                      "intelligent. Du quartier. Non. Si ! Attendez. Je redémarre. "
                      "Voilà. Tout va très bien. Enfin… presque.")
RNG = np.random.default_rng(7)  # graine fixe : banc rejouable à l'identique


# ── Synthèse ────────────────────────────────────────────────────────────────

def synthese(voice, texte: str) -> tuple[np.ndarray, int]:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        voice.synthesize_wav(texte, w)
    buf.seek(0)
    with wave.open(buf, "rb") as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return x.astype(np.float64) / 32768.0, sr


def ecrit(nom: str, x: np.ndarray, sr: int) -> None:
    # Normalisation en RMS (−20 dBFS), PAS en crête : tous les costumes à la
    # même sonie perçue, sinon l'oreille préfère systématiquement le plus fort
    # (mesuré : en crête, l'écrêteur historique sortait 11 dB au-dessus des
    # autres). Crêtes qui dépassent → limiteur doux tanh.
    rms = np.sqrt((x ** 2).mean()) or 1.0
    x = x * (10 ** (-20 / 20) / rms)
    x = np.where(np.abs(x) > 0.7, np.sign(x) * (0.7 + 0.2 * np.tanh((np.abs(x) - 0.7) / 0.2)), x)
    y = (x * 32767).astype(np.int16)
    with wave.open(str(SORTIE / f"{nom}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(y.tobytes())
    print(f"  {nom}.wav  {len(x) / sr:4.1f} s")


# ── Briques ─────────────────────────────────────────────────────────────────

def vitesse(x: np.ndarray, facteur: float) -> np.ndarray:
    """Réechantillonnage : facteur > 1 = plus vite ET plus aigu."""
    return signal.resample_poly(x, 1000, int(round(1000 * facteur)))


def vitesse_variable(x: np.ndarray, courbe: np.ndarray) -> np.ndarray:
    """Lecture à vitesse instantanée variable (courbe = facteur par échantillon
    de SORTIE, interpolée) — la tête de lecture avance de `facteur` à chaque pas."""
    pos = np.cumsum(courbe)
    pos = pos[pos < len(x) - 1]
    return np.interp(pos, np.arange(len(x)), x)


def reverb(x: np.ndarray, sr: int, taille: float = 1.0, mix: float = 0.3) -> np.ndarray:
    """Schroeder : 4 peignes parallèles + 2 passe-tout. Volontairement cheap."""
    queue = np.zeros(len(x) + int(sr * 1.5 * taille))
    xe = np.concatenate([x, np.zeros(len(queue) - len(x))])
    for ms, g in ((29.7, 0.80), (37.1, 0.78), (41.1, 0.76), (43.7, 0.74)):
        d = int(sr * ms * taille / 1000)
        a = np.zeros(d + 1); a[0] = 1; a[d] = -g
        queue += signal.lfilter([1], a, xe)
    for ms, g in ((5.0, 0.7), (1.7, 0.7)):
        d = int(sr * ms / 1000)
        b = np.zeros(d + 1); b[0] = -g; b[d] = 1
        a = np.zeros(d + 1); a[0] = 1; a[d] = -g
        queue = signal.lfilter(b, a, queue)
    return (1 - mix) * xe + mix * queue / 4


def compresse(x: np.ndarray, drive: float = 4.0) -> np.ndarray:
    return np.tanh(drive * x) / np.tanh(drive)


def passe_bande(x: np.ndarray, sr: int, bas: float, haut: float) -> np.ndarray:
    sos = signal.butter(4, [bas, haut], btype="band", fs=sr, output="sos")
    return signal.sosfilt(sos, x)


def notes(sr: int, freqs: list[float], duree: float, forme: str = "sin") -> np.ndarray:
    """Petite mélodie (jingle, musique d'attente) avec enveloppe par note."""
    n = int(sr * duree)
    t = np.arange(n) / sr
    env = np.minimum(1, t / 0.01) * np.exp(-t * 4)
    out = []
    for f in freqs:
        osc = np.sin(2 * np.pi * f * t) if forme == "sin" else signal.square(2 * np.pi * f * t) * 0.4
        out.append(osc * env)
    return np.concatenate(out) * 0.5


def silence(sr: int, s: float) -> np.ndarray:
    return np.zeros(int(sr * s))


def attaques(x: np.ndarray, sr: int, n: int) -> list[int]:
    """Indices des débuts de mots : l'énergie remonte après un creux."""
    fen = int(sr * 0.02)
    e = np.sqrt(np.convolve(x ** 2, np.ones(fen) / fen, mode="same"))
    seuil = 0.15 * e.max()
    actif = e > seuil
    debuts = np.flatnonzero(actif[1:] & ~actif[:-1]) + 1
    debuts = debuts[debuts > sr * 0.3]
    if len(debuts) <= n:
        return list(debuts)
    return sorted(RNG.choice(debuts, n, replace=False).tolist())


# ── Costumes ────────────────────────────────────────────────────────────────

def c_robot_historique(x, sr):
    # LE code de prod (chemin OpenAI historique), pas une imitation : mêmes
    # paramètres que vision/ai/tts.py (sample_rate=24000 passé en dur là-bas).
    from vision.audio.effects import apply_robotic_effect
    i16 = (np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes()
    y = apply_robotic_effect(i16, depth=0.7, rate_hz=35, sample_rate=24000)
    return np.frombuffer(y, dtype=np.int16).astype(np.float64) / 32768


def c_teleachat(x, sr):
    v = compresse(vitesse(x, 1.1), 5)
    jingle = notes(sr, [523, 659, 784], 0.16, "square")
    return np.concatenate([jingle, silence(sr, 0.1), reverb(v, sr, 0.5, 0.18)])


def c_hotline(x, sr):
    attente = np.concatenate([notes(sr, [392, 440, 494, 440, 392, 330], 0.3)])
    attente = passe_bande(attente, sr, 300, 3400)
    tel = passe_bande(compresse(x, 3), sr, 300, 3400)
    tel = tel + 0.01 * RNG.standard_normal(len(tel))
    return np.concatenate([attente, silence(sr, 0.3), tel])


def c_jouet_bug(x, sr):
    # Sous-échantillonnage 8 kHz par maintien + 5 bits (le « Speak & Spell »).
    pas = sr // 8000
    y = np.repeat(x[::pas], pas)[: len(x)]
    y = np.round(y * 16) / 16
    # Hachage en salves : quelques trous de 40-80 ms.
    for i in attaques(y, sr, 4):
        y[i + int(sr * 0.1): i + int(sr * 0.1) + int(sr * RNG.uniform(0.04, 0.08))] = 0
    return y


def c_amoureux(x, sr):
    # ≈ +2 demi-tons. Pas de « débit 0,85 » comme au §10 : par
    # rééchantillonnage, ralentir ferait redescendre la hauteur.
    v = vitesse(x, 1.12)
    # Vibrato 5 Hz par retard modulé (±4 ms).
    n = np.arange(len(v))
    retard = 0.004 * sr * (1 + np.sin(2 * np.pi * 5 * n / sr))
    v = np.interp(n - retard, n, v, left=0)
    return reverb(v, sr, 1.4, 0.4)


def c_dalek(x, sr):
    n = np.arange(len(x))
    return compresse(x * np.sin(2 * np.pi * 40 * n / sr), 2)


def c_begaiement(x, sr):
    """Deux mots qui bégaient (syllabe ×4) + un mot joué à l'envers."""
    morceaux, dernier = [], 0
    points = attaques(x, sr, 3)
    for k, i in enumerate(points):
        morceaux.append(x[dernier:i])
        if k < 2:
            syll = x[i: i + int(sr * 0.09)]
            morceaux += [syll, silence(sr, 0.02)] * 3
            dernier = i
        else:
            mot = x[i: i + int(sr * 0.35)]
            morceaux.append(mot[::-1])
            dernier = i + len(mot)
    morceaux.append(x[dernier:])
    return np.concatenate(morceaux)


def c_cassette(x, sr):
    """Normal, puis la fin s'effondre comme une bande qui cale."""
    n = len(x)
    courbe = np.ones(n * 2)
    debut = int(n * 0.72)
    chute = np.linspace(1.0, 0.25, len(courbe) - debut)
    courbe[debut:] = chute
    return vitesse_variable(x, courbe)


def c_chorale(x, sr):
    """Trois Didier désaccordés qui se marchent dessus."""
    voix = [x, vitesse(x, 1.025), vitesse(x, 0.975)]
    decal = [0, int(sr * 0.025), int(sr * 0.045)]
    n = max(len(v) + d for v, d in zip(voix, decal))
    out = np.zeros(n)
    for v, d, g in zip(voix, decal, (1.0, 0.7, 0.7)):
        out[d: d + len(v)] += g * v
    return out


def c_chanteur(x, sr, note_hz: float = 110.0):
    """Vocodeur à canaux : l'enveloppe spectrale de la voix sculpte une dent de
    scie fixe (+ un peu de bruit pour garder les consonnes)."""
    n = np.arange(len(x))
    porteuse = signal.sawtooth(2 * np.pi * note_hz * n / sr) + 0.15 * RNG.standard_normal(len(x))
    f, t, V = signal.stft(x, sr, nperseg=1024, noverlap=768)
    _, _, P = signal.stft(porteuse, sr, nperseg=1024, noverlap=768)
    env = np.abs(V)
    lisse = np.ones(9) / 9  # lissage en fréquence = enveloppe, pas la hauteur
    env = np.apply_along_axis(lambda c: np.convolve(c, lisse, mode="same"), 0, env)
    pn = np.abs(P) + 1e-9
    _, y = signal.istft(P / pn * env, sr, nperseg=1024, noverlap=768)
    return y[: len(x)]


def c_debit_fou(x, sr):
    """Accélère de plus en plus (enthousiasme qui s'emballe)."""
    courbe = np.linspace(0.85, 1.6, len(x))
    return vitesse_variable(x, courbe)


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    from piper import PiperVoice
    SORTIE.mkdir(exist_ok=True)
    voice = PiperVoice.load(VOIX)
    x, sr = synthese(voice, REPLIQUE)
    print(f"voix {VOIX} @ {sr} Hz")

    costumes = [
        ("00-sec-prod-actuelle", lambda x, sr: x),
        ("01-robot-historique", c_robot_historique),
        ("02-teleachat-80s", c_teleachat),
        ("03-hotline", c_hotline),
        ("04-jouet-qui-bugue", c_jouet_bug),
        ("05-amoureux", c_amoureux),
        ("06-dalek", c_dalek),
        ("07-begaiement-numerique", c_begaiement),
        ("08-cassette-qui-cale", c_cassette),
        ("09-chorale-de-didiers", c_chorale),
        ("10-robot-chanteur", c_chanteur),
        ("11-debit-qui-s-emballe", c_debit_fou),
    ]
    for nom, f in costumes:
        ecrit(nom, f(x, sr), sr)

    b, _ = synthese(voice, REPLIQUE_BAFOUILLE)
    ecrit("12-texte-qui-bafouille", b, sr)
    ecrit("13-bafouille-et-begaie", c_begaiement(b, sr), sr)


if __name__ == "__main__":
    main()
