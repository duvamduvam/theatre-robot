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


# Variable d'environnement du BANC de répétition (docker-compose-x86.yml) :
# Didier peut demander à repartir / s'arrêter par la clé "marche" de son JSON
# de fin (lot I1 « mouvement à la voix », 22/10, cf. personas.MOVE_TEMPLATE).
# chat_node publie alors rehearsal/chat_move, consommé par le SEUL régisseur
# de la répétition simulée (domaine 43). Jamais posée sur le Pi : absente =
# aucun bloc de prompt, aucun publisher (comportement historique).
MOVE_ENV = "CHAT_MOUVEMENT"
_MOVE_TRUE = ("1", "true", "on", "oui")
_MOVE_FALSE = ("0", "false", "off", "non")


def move_enabled_from_env(environ=os.environ):
    """True ssi CHAT_MOUVEMENT vaut 1/true/on/oui (casse et espaces
    ignorés) ; 0/false/off/non, absente ou vide = False (« false » doit
    pouvoir couper le mouvement sur le banc). Toute AUTRE valeur = erreur
    EXPLICITE au démarrage (même patron que vad_config_from_env) : une
    faute de frappe ne doit pas désactiver le mouvement en silence."""
    raw = environ.get(MOVE_ENV, "").strip().lower()
    if not raw:
        return False
    if raw in _MOVE_TRUE:
        return True
    if raw in _MOVE_FALSE:
        return False
    raise ValueError(f"{MOVE_ENV}={raw!r} : attendu {'/'.join(_MOVE_TRUE)} (actif) "
                     f"ou {'/'.join(_MOVE_FALSE)} (coupé), ou absente")


# Domaine ROS de la SIMULATION : le seul où le mouvement à la voix a le droit
# d'exister (revue adversariale I1, 22/10). Même valeur que SIM_DOMAIN_ID de
# robot_rehearsal (dadou_robot_ros) ; 42 = le vrai robot.
MOVE_DOMAIN_ID = "43"


# Variable d'environnement du BANC PC : modèle whisper (faster-whisper).
# POURQUOI (22/10) : en séance au casque, « base » entendait « chat » pour
# « chien » et « groutitant » pour « grue Titan » ; « small » transcrit juste
# en ~1,2 s pour 6 s de parole sur le PC (32 cœurs, mesuré). Le Pi garde
# « base » (CPU bien plus faible) : la variable n'y est pas posée.
WHISPER_MODEL_ENV = "CHAT_WHISPER_MODEL"
_WHISPER_MODELS = ("tiny", "base", "small", "medium")


# Modèle LLM de la BOUCHE, surchargeable sur le banc (31/10, demande de David :
# « peut-on faire un essai avec Sonnet ? » — le 23/10 Sonnet avait été écarté
# pour la parole à cause de la latence, cf. étude niveaux-réflexion §10 ;
# l'essai sert à comparer compréhension ET temps au premier mot). Liste
# FERMÉE : un nom libre partirait tel quel chez OpenRouter et un nom faux
# rendrait Didier muet en pleine séance. Absente = défaut de config (Haiku).
LLM_MODEL_ENV = "CHAT_LLM_MODEL"
_LLM_MODELS = ("anthropic/claude-haiku-5.5", "anthropic/claude-sonnet-5.5")


def llm_model_from_env(environ=os.environ):
    """Modèle de la bouche : None si CHAT_LLM_MODEL est absente/vide (garder la
    config), sinon le nom s'il est dans la liste fermée ; ValueError sinon."""
    raw = environ.get(LLM_MODEL_ENV, "").strip().lower()
    if not raw:
        return None
    if raw not in _LLM_MODELS:
        raise ValueError(f"{LLM_MODEL_ENV}={raw!r} : attendu {' / '.join(_LLM_MODELS)}")
    return raw


def whisper_model_from_env(environ=os.environ):
    """Modèle whisper : "base" par défaut, sinon CHAT_WHISPER_MODEL s'il est
    dans la liste connue ; toute autre valeur = erreur EXPLICITE au
    démarrage (un nom inconnu déclencherait un téléchargement hasardeux)."""
    raw = environ.get(WHISPER_MODEL_ENV, "").strip().lower()
    if not raw:
        return "base"
    if raw not in _WHISPER_MODELS:
        raise ValueError(f"{WHISPER_MODEL_ENV}={raw!r} : attendu {'/'.join(_WHISPER_MODELS)}")
    return raw


# Variable d'environnement : branche la PAROLE sur le metteur en scène
# intérieur (reflection_node, étude dadou_robot_ros/docs/etude-niveaux-
# reflexion.md) — chat_node lit le tableau de situation, accepte les tours
# spontanés et peut demander une réflexion (clé "reflechir"). Pas de garde de
# domaine : rien de tout ça ne commande le corps (le mouvement reste derrière
# CHAT_MOUVEMENT, domaine 43). Absente = comportement historique.
REFLECTION_ENV = "CHAT_REFLEXION"


def reflection_enabled_from_env(environ=os.environ):
    """True ssi CHAT_REFLEXION vaut 1/true/on/oui ; False si absente/vide ou
    0/false/off/non ; ValueError sinon (même tolérance que CHAT_MOUVEMENT)."""
    raw = environ.get(REFLECTION_ENV, "").strip().lower()
    if raw == "" or raw in _MOVE_FALSE:
        return False
    if raw in _MOVE_TRUE:
        return True
    raise ValueError(f"{REFLECTION_ENV}={raw!r} : attendu {'/'.join(_MOVE_TRUE + _MOVE_FALSE)}")


def camera_is_partner_from_env(environ, partner):
    """True ssi la personne vue par la caméra EST le partenaire de jeu :
    ROS_DOMAIN_ID == MOVE_DOMAIN_ID (simulation) ET un partenaire défini.
    POURQUOI : en sim, person_tracker lit la webcam du PC devant laquelle se
    tient le comédien partenaire ; sans ça le metteur en scène intérieur le
    prend pour un passant inconnu et relance Didier vers lui (31/10). Sur le
    vrai robot (autre domaine, ou variable absente) : toujours False."""
    domain = environ.get("ROS_DOMAIN_ID", "").strip()
    return domain == MOVE_DOMAIN_ID and bool((partner or "").strip())


def chat_env_overrides(environ=os.environ):
    """Surcharges du BANC lues dans l'environnement (CHAT_VAD_FACTOR,
    CHAT_WHISPER_MODEL, CHAT_PARTENAIRE, CHAT_MOUVEMENT, CHAT_REFLEXION, CHAT_LLM_MODEL) -> (dict à fusionner
    dans `config`, warnings à journaliser).

    POURQUOI pas à l'import (revue adversariale I1, 22/10) : une valeur
    invalide levait pendant l'IMPORT de ce module — donc dans TOUS les nodes
    vision (person_tracker compris), pas seulement le chat. Ici, c'est
    chat_node qui l'appelle à son démarrage et transforme ValueError en
    échec de démarrage EXPLICITE ; `config` garde les défauts du robot.

    Mouvement à la voix : actif SEULEMENT si ROS_DOMAIN_ID vaut 43 (la
    simulation) — sinon forcé à False avec un warning, même si
    CHAT_MOUVEMENT est posé (une variable oubliée ne doit jamais rejoindre
    le domaine du vrai robot)."""
    overrides = {
        "chat_vad": vad_config_from_env(environ),
        "chat_whisper_model": whisper_model_from_env(environ),
        "chat_partner": partner_from_env(environ),
        "chat_reflection_enabled": reflection_enabled_from_env(environ),
    }
    llm_model = llm_model_from_env(environ)
    if llm_model is not None:
        overrides["chat_llm_model"] = llm_model
    warnings = []
    move = move_enabled_from_env(environ)
    domain = environ.get("ROS_DOMAIN_ID", "").strip()
    if move and domain != MOVE_DOMAIN_ID:
        warnings.append(
            f"{MOVE_ENV} IGNORÉ : ROS_DOMAIN_ID={domain!r}, le mouvement à la voix est "
            f"réservé au domaine {MOVE_DOMAIN_ID} (simulation) — mouvement=False")
        move = False
    overrides["chat_move_enabled"] = move
    return overrides, warnings


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
    # llm_stream.py). Claude Haiku 5.5 (bascule du 22/10/2026, banc OpenRouter
    # avec la vraie persona « bougon », 4 répliques par variante) : premier
    # token 0,62-1,20 s contre 0,91-1,38 s pour Haiku 4.5, coût par réplique
    # ~7× moindre, persona mieux tenue (reprend le lore du socle).
    "chat_llm_model": "anthropic/claude-haiku-5.5",
    "chat_llm_base_url": "https://openrouter.ai/api/v1",
    # ⚠️ RÉFLEXION COUPÉE, OBLIGATOIRE à partir de Haiku 5.5 : la réflexion
    # adaptative y est active par défaut et ses tokens comptent dans
    # max_tokens — au banc, 4 réponses sur 4 VIDES (200 tokens de réflexion,
    # zéro texte : Didier muet) ; effort "low" : encore 3 sur 4 vides et
    # premier token à 3,3-3,8 s. Une réplique scénique de 1-3 phrases n'a
    # rien à gagner à réfléchir. Paramètre OpenRouter (normalisé par lui vers
    # l'API Anthropic), passé tel quel en extra_body par StreamingBrain.
    "chat_llm_extra_body": {"reasoning": {"enabled": False}},
    # Budget de sortie : 200 suffisait à Haiku 4.5, mais le tokenizer de
    # Haiku 5.5 compte ~30 % de tokens de plus pour le même texte, et 1
    # réplique sur 4 du banc s'est fait couper à 200 en plein JSON d'émotion
    # (émotion perdue). 300 = marge sans ouvrir la porte aux tirades
    # (la longueur reste tenue par AI_REALTIME_RULES, pas par ce plafond).
    "chat_llm_max_tokens": 300,

    # STT local (vision/ai/stt.py, FasterWhisperStt) : "base" retenu comme
    # meilleur compromis précision/latence au 10/07. Repli documenté : "tiny"
    # si le Pi 5 peine en charge réelle sur une séquence de spectacle complète
    # (plus rapide, plus d'erreurs de transcription) — à arbitrer après un
    # test scénique en conditions réelles, pas en atelier.
    # Surchargeable au BANC par CHAT_WHISPER_MODEL (cf. chat_env_overrides,
    # appliqué au démarrage de chat_node, jamais à l'import).
    "chat_whisper_model": "base",

    # STT DISTANT (vision/ai/stt.py, OpenRouterStt + FallbackStt, 23/10) :
    # "openrouter" = Voxtral via OpenRouter, repli automatique sur le
    # faster-whisper local ci-dessus (toujours chargé) ; "local" = whisper
    # seul (comportement historique). Banc du 23/10 : Voxtral plus juste et
    # 0,5-1,8 s, contre 3,6-5,2 s pour whisper base sur la Pi 5.
    "chat_stt_backend": "openrouter",
    "chat_stt_remote_model": "mistralai/voxtral-mini-transcribe",
    # Au-delà, l'énoncé est retranscrit en local (le pire cas reste borné).
    "chat_stt_timeout_s": 4.0,

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
    # Défauts du ROBOT ici et pour les trois clés suivantes : l'environnement
    # n'est lu qu'au démarrage de chat_node (chat_env_overrides) — une
    # valeur invalide ne doit jamais faire échouer l'import de ce module.
    "chat_vad": VadConfig(),

    # Partenaire de scène connu (répétition seulement, cf. partner_from_env).
    "chat_partner": None,

    # Mouvement à la voix (répétition seulement, domaine 43 seulement, cf.
    # move_enabled_from_env et chat_env_overrides).
    "chat_move_enabled": False,

    # Parole branchée sur le metteur en scène intérieur (cf.
    # reflection_enabled_from_env et vision/ai/reflection_contract.py).
    "chat_reflection_enabled": False,

    # --- Metteur en scène intérieur (reflection_node) ---------------------
    # Étude dadou_robot_ros/docs/etude-niveaux-reflexion.md (23/10/2026) :
    # boucle LENTE, asynchrone, jamais sur le chemin de la parole. Chiffres
    # du banc du 23/10 (image 640×480) : Haiku 5.5 effort medium 5,9-6,8 s,
    # ~0,0003 $ l'appel ; Sonnet 5.5 effort medium 5,0-6,5 s, ~0,005 $.
    # Réflexion ordinaire (événements + battement de fond) : Haiku, peu cher.
    "reflection_model": "anthropic/claude-haiku-5.5",
    "reflection_extra_body": {"reasoning": {"effort": "medium"}},
    # Demande explicite de Didier (clé "reflechir" = instruction complexe de
    # David) : rare, c'est là que l'intelligence compte → Sonnet.
    "reflection_deep_model": "anthropic/claude-sonnet-5.5",
    "reflection_deep_extra_body": {"reasoning": {"effort": "medium"}},
    # ⚠️ La réflexion compte dans max_tokens (panne « Didier muet » du 22/10) :
    # budget LARGE, la sortie utile ne fait que ~150 tokens.
    "reflection_max_tokens": 3000,
    # Images de la caméra envoyées au LLM : DÉCIDÉ par David le 23/10 (oui,
    # y compris en rue). Seule une trame de moins de 3 s est jointe.
    "reflection_use_image": True,
    # But de la déambulation (note de création : ils cherchent le paradis).
    # Surchargé par paramètre ROS pour une répétition (ex. le Titan gris).
    "reflection_destination": "le paradis",

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
