"""Configuration UNIQUE de dadou_vision_ros.

Toutes les valeurs runtime (modèle GPT, voix TTS, chemins de données) et les
secrets (clé API...) passent par ce module : aucun autre fichier ne doit lire
`conf/secret` directement ni coder une valeur par défaut en dur.

`conf/secret` est gitignoré (dépôt GitHub PUBLIC) : voir `conf/secret.example`
pour le format attendu — une ligne `cle=valeur` par secret, commentaires `#`
et lignes vides ignorés. Le chargement est volontairement paresseux
(`get_secret` n'est appelé que par les classes qui en ont vraiment besoin,
au moment de l'usage) pour que les modules purs (parsing, config, db) restent
importables et testables même sans `conf/secret` sur la machine (CI).
"""
import os

from vision.audio.live_audio_gate import LiveAudioGateConfig
from vision.audio.vad import VadConfig

# Racine du dépôt : vision/vision_config.py -> vision/ -> racine.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_FILE = os.path.join(REPO_ROOT, "conf", "secret")


# Variable d'environnement du BANC PC (docker-compose-x86.yml) : facteur VAD
# (seuil = plancher de bruit × facteur). POURQUOI (22/10) : le micro d'un
# casque Bluetooth en HFP a un bruit de fond qui FLUCTUE (13 % des trames
# au-dessus de 1,3 × la médiane, mesuré) — la VAD ne voit jamais 600 ms de
# silence continu, croit la parole sans fin, coupe à max_utterance_ms et
# whisper reçoit 12 s de souffle (STT ''). Le ReSpeaker du robot a un plancher
# stable : le Pi garde la valeur par défaut validée, la variable n'y est pas posée.
VAD_FACTOR_ENV = "CHAT_VAD_FACTOR"


def vad_config_from_env(environ=os.environ):
    """VadConfig par défaut, sauf threshold_factor si CHAT_VAD_FACTOR est
    posée. Valeur invalide ou ≤ 1 = erreur EXPLICITE au démarrage (un facteur
    ≤ 1 déclencherait sur le bruit de fond lui-même — mieux vaut un crash
    clair qu'un Didier qui « entend des voix »)."""
    raw = environ.get(VAD_FACTOR_ENV, "").strip()
    if not raw:
        return VadConfig()
    try:
        factor = float(raw)
    except ValueError as exc:
        raise ValueError(f"{VAD_FACTOR_ENV}={raw!r} : nombre attendu") from exc
    if factor <= 1.0:
        raise ValueError(f"{VAD_FACTOR_ENV}={raw!r} : doit être > 1")
    return VadConfig(threshold_factor=factor)


# Variable d'environnement du BANC de répétition (docker-compose-x86.yml) :
# prénom du partenaire de scène que Didier CONNAÎT (cf. personas.
# PARTNER_TEMPLATE). Jamais posée sur le Pi : en rue, Didier ne sait pas qui
# lui parle. Vide = aucun partenaire (comportement historique).
PARTNER_ENV = "CHAT_PARTENAIRE"


def partner_from_env(environ=os.environ):
    """Prénom du partenaire connu, ou None si la variable est absente/vide."""
    return environ.get(PARTNER_ENV, "").strip() or None


def load_secrets(path):
    """Parse un fichier clé=valeur tolérant (commentaires '#', lignes vides).

    Lève une erreur explicite si le fichier est absent : mieux vaut un crash
    clair au démarrage (avec le chemin et la marche à suivre) qu'une clé vide
    qui échoue plus tard, silencieusement, sur un appel réseau.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(
            "Secret manquant : {}\n"
            "Copiez conf/secret.example vers conf/secret et renseignez vos "
            "clés (fichier gitignoré, jamais commité — dépôt GitHub public)."
            .format(path)
        )
    secrets = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            secrets[key.strip()] = value.strip()
    return secrets


def get_secret(key):
    """Retourne un secret par nom depuis conf/secret (erreur claire si absent/vide)."""
    secrets = load_secrets(SECRET_FILE)
    if not secrets.get(key):
        raise KeyError(
            "Clé '{}' absente ou vide dans {} (voir conf/secret.example)."
            .format(key, SECRET_FILE)
        )
    return secrets[key]


# --- Valeurs par défaut saines (aucune donnée sensible ici) --------------

config = {
    # Brique GPT (vision/ai/interactions.py)
    "gpt_model": "gpt-4o",
    "max_tokens": 70,
    "wake_up_word": "didier",

    # Brique TTS (vision/ai/tts.py)
    "gpt_voice": "alloy",
    "alsa_channel": 1,

    # Historique de conversation (vision/db/chat_db.py) — db/ gardé sur
    # disque (utile V2/streaming) mais gitignoré, jamais commité.
    "db_directory": os.path.join(REPO_ROOT, "db") + os.sep,
    "chat_db": "chat.db",

    # Captures caméra (vision/ai/camera.py)
    "pictures_folder": os.path.join(REPO_ROOT, "medias", "pictures") + os.sep,

    # --- Brique conversation temps réel (V2 streaming) ---------------------
    # Toutes les valeurs ci-dessous sont issues du proto validé le 10/07
    # (cf. CLAUDE.md) : mesures faites sur le Pi 5 réel, pas des choix
    # arbitraires — à réviser seulement après un nouveau test scénique si le
    # comportement observé le justifie.

    # Modèle LLM streamé (vision/ai/llm_stream.py, StreamingBrain), via
    # OpenRouter (client OpenAI officiel avec base_url personnalisé — cf.
    # llm_stream.py). Claude Haiku 4.5 : meilleur compromis latence/coût
    # mesuré pour des réponses courtes scéniques (AI_REALTIME_RULES impose
    # 1-3 phrases, pas besoin d'un modèle plus lourd).
    "chat_llm_model": "anthropic/claude-haiku-4.5",
    "chat_llm_base_url": "https://openrouter.ai/api/v1",

    # STT local (vision/ai/stt.py, FasterWhisperStt) : "base" retenu comme
    # meilleur compromis précision/latence au 10/07. Repli documenté : "tiny"
    # si le Pi 5 peine en charge réelle sur une séquence de spectacle complète
    # (plus rapide, plus d'erreurs de transcription) — à arbitrer après un
    # test scénique en conditions réelles, pas en atelier.
    "chat_whisper_model": "base",

    # Voix Piper de Didier (vision/ai/tts_piper.py) : modèle .onnx rangé dans
    # medias/voices/ comme les autres assets propres au personnage (cohérent
    # avec pictures_folder ci-dessus — medias/ = données du personnage,
    # conf/ = config/secrets). Le fichier n'est PAS encore présent dans le
    # dépôt au 10/07 (voix pas encore choisie/entraînée) : ce chemin est la
    # valeur par défaut que tts_piper.py utilisera dès que le modèle sera
    # déposé, pas une garantie qu'il existe déjà sur le disque.
    "chat_piper_voice": os.path.join(REPO_ROOT, "medias", "voices", "didier.onnx"),

    # Périphériques ALSA (alias définis dans /etc/asound.conf du Pi 5, cf.
    # proto validé du 10/07 — noms retenus tels quels, pas de nom de carte
    # brut type "hw:1,0" qui casserait au moindre changement de câblage USB).
    "chat_mic_device": "casque_mic",
    "chat_out_device": "mixette",

    # Durée de rafraîchissement (ms) de l'animation "parle" republiée à
    # chaque Sentence tant que le TTS streame (vision/ai/performance.py
    # speaking_start) : 15 s de marge large — une phrase TTS dure rarement
    # plus de quelques secondes, cette valeur ne sert qu'à ne jamais couper
    # l'animation par accident si le flux LLM ralentit ponctuellement.
    "chat_animation_refresh_ms": 15000,

    # Durée (s) de la piste de bips de réflexion (vision/audio/beeps.py),
    # jouée pendant le STT : 2,0 s mesurées comme la latence typique de
    # FasterWhisperStt "base" sur un énoncé court au 10/07 — assez pour
    # couvrir le silence perçu par le public sans que les bips ne s'arrêtent
    # avant la fin réelle du STT.
    "chat_beep_seconds": 2.0,

    # Amplitude (int16, cf. vision/audio/beeps.py build_thinking_beeps) des
    # bips de réflexion, RELATIVE à la voix de Didier — baissée le 2026-09-13
    # après écoute de David en séance (« baisse le niveau des bips, c'est
    # ennuyeux ») : 14000 (défaut historique de build_thinking_beeps, ≈ -7,4
    # dBFS) était fatigant au casque d'atelier. 5000 ≈ -16,3 dBFS, ~9 dB de
    # moins. ⚠️ Ce niveau dépend aussi du LIEU de diffusion : au casque
    # d'atelier le besoin n'est pas le même qu'en rue via la sono du robot, où
    # les bips servent à masquer la latence perçue du LLM — à réécouter lors
    # du protocole physique, ne pas retoucher cette valeur à l'aveugle avant.
    "chat_beep_amplitude": 5000,

    # VAD (vision/audio/vad.py) : instance VadConfig avec ses valeurs par
    # défaut déjà validées (cf. docstring de VadConfig) — un objet complet
    # plutôt que des clés de config éclatées, pour rester la source unique de
    # vérité si VadConfig gagne de nouveaux champs un jour.
    # Seul champ surchargeable : threshold_factor, par CHAT_VAD_FACTOR (cf.
    # vad_config_from_env) — réservé au BANC, jamais posé sur le Pi.
    "chat_vad": vad_config_from_env(),

    # Partenaire de scène connu (répétition seulement, cf. partner_from_env).
    "chat_partner": partner_from_env(),

    # Gate « source audio vivante » (vision/audio/live_audio_gate.py, lot du
    # 2026-08-30, half-duplex élargi) : instance LiveAudioGateConfig avec ses
    # valeurs par défaut déjà mesurées le 26/08 sur la chaîne d'acquisition
    # réelle (cf. docstring de LiveAudioGateConfig) — même patron que
    # "chat_vad" ci-dessus, un objet complet pour rester source unique de
    # vérité si la dataclass gagne un champ.
    "chat_live_audio_gate": LiveAudioGateConfig(),

    # Personnalité de Didier au démarrage (vision/ai/personas.py, lot D3 —
    # atelier du 2026-07-13) : « bougon » = la plus proche du registre
    # « gouaille de rue » déjà validé sur le proto du 10/07, les deux autres
    # variantes ("naif", "vantard") sont l'expérience à mener en conditions
    # réelles. Commutable à chaud via le topic `persona` (console web).
    "chat_persona": "bougon",
}

WAKE_UP_WORD = config["wake_up_word"]
