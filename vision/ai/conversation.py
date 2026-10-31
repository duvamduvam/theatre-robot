"""Orchestrateur d'un tour de conversation (V7) — colle les briques V1-V6
ensemble : micro -> VAD -> STT -> LLM streamé -> parseur de jeu -> TTS ->
lecture, avec publication des messages ROS (face/animation) au bon moment.

QUOI : ConversationEngine ne fait AUCUN I/O lui-même — tout (mic/vad/stt/
       brain/tts/player/publish) est injecté au constructeur. Ce module reste
       donc testable avec des fakes purs (cf. test_conversation.py), même si
       ce n'est pas un module "pur" au sens strict des lots V1-V5 (il
       ORCHESTRE des effets de bord, il ne les produit pas lui-même).
POURQUOI aucun thread supplémentaire créé ici : AudioPlayer a déjà le sien
       (lecture séquentielle en tâche de fond, cf. vision.audio.playback) ;
       run_once() est de toute façon bloquant sur la boucle d'écoute micro
       (read_frame) — ajouter un thread ici n'apporterait rien, juste de la
       complexité de synchronisation en plus. SEULE EXCEPTION (31/10) :
       l'écoute GARDE pendant une réplique (cf. ÉCOUTE GARDE plus bas) — le
       thread de conversation est alors pris par le LLM/TTS/drain, l'arrêt
       vocal ne peut venir que d'ailleurs.

DÉCISION (le déroulé du proto laissait un choix implicite à trancher) :
       thinking() est publié JUSTE APRÈS speech_end, AVANT même de savoir si
       le STT renverra du texte exploitable — donc thinking() part MÊME SI
       le tour est ensuite abandonné (STT vide/trop court). Choix VOLONTAIRE
       (pas un oubli) : le visage "reflechit" est une réaction honnête au
       fait que le STT est réellement en train de tourner (calcul bloquant
       en cours), pas une promesse qu'une réponse va suivre — le spectateur
       voit le robot "y penser", ce qui reste cohérent même si l'énoncé
       capté était en fait trop court pour être exploité. cf.
       test_conversation.py::test_stt_inexploitable_publie_thinking_puis_idle
       pour le test qui fige ce choix.

       CORRECTIF du 2026-07-12 (étude d'arbitrage des actionneurs, scénario
       S1 côté robot, cf. dadou_robot_ros/docs/etude-arbitrage-actionneurs.md
       §3/§5.1) : la « limite connue acceptée » ci-dessus (le visage restait
       coincé sur "reflechit" après un tour abandonné, faute de rattrapage)
       est CORRIGÉE — la condition documentée à l'époque ("à revisiter si ça
       se voit mal sur scène") était remplie, constaté sur le vrai robot.
       run_once() publie désormais idle() (retour au neutre) dans la branche
       STT inexploitable, AVANT de relancer le micro. thinking() reste publié
       dès speech_end SANS changement (réaction honnête toujours voulue) :
       seule la SORTIE d'un tour abandonné change, pas son entrée.

       ÉLARGISSEMENT du 2026-08-30 (gate « source audio vivante », half-
       duplex élargi, cf. dadou_robot_ros/docs/
       etude-declenchement-conversation.md §10) : deux kwargs OPTIONNELS
       `gate` et `show_audio_active` (défaut None = comportement HISTORIQUE
       inchangé à l'octet près, clause de réversibilité du lot). Quand ils
       sont fournis, `_listen_for_utterance` jette toute trame bruyante/
       écrêtée/de spectacle AVANT qu'elle n'atteigne la VAD, et
       `_speak_reply` arme une queue acoustique (`arm_tail`) avant de
       relancer le micro, dans ses DEUX sorties (succès et exception).

       OBSERVABILITÉ (2026-09-13, demande de David en séance -- « un
       indicateur pour voir si ma voix passe », « la conversation n'est pas
       fluide du tout ») : deux kwargs OPTIONNELS de plus, `on_meter` et
       `on_timing` (défaut None = comportement HISTORIQUE inchangé à l'octet
       près, MÊME clause de réversibilité que `gate`/`show_audio_active`
       ci-dessus). `on_meter` est nourri à la cadence des trames (30 ms) par
       `_listen_for_utterance` -- niveau/crête/blocage gate/état VAD, de quoi
       dessiner un vumètre web temps réel (cf. vision/nodes/chat_node.py,
       paramètre `diag_port`). `on_timing` est nourri une fois par tour par
       `run_once`/`_speak_reply` -- durées STT/latence LLM/latence premier
       son/latence totale perçue, pour comprendre OÙ part le temps d'un tour.
       Les DEUX callbacks tournent dans le thread de conversation et NE
       DOIVENT JAMAIS le faire dérailler : un vumètre qui plante ne doit
       jamais rendre Didier muet, cf. `_notify_meter`/`_notify_timing`.

       CORRECTIF du 2026-09-13 (David, en séance : « la bouche n'est pas
       raccord avec la parole » -- pas une demande de synchronisation
       labiale, juste « recaler la fin »/faire cesser le mouvement à la fin
       de la réplique) : MÊME défaut que le CORRECTIF du 2026-07-12
       ci-dessus, jamais porté sur le chemin NOMINAL de `_speak_reply`.
       Mécanisme : l'expression "parle" (json/expressions.json,
       dadou_robot_ros) a `"loop": true` -- Face la rejoue indéfiniment tant
       qu'AUCUN autre message n'arrive sur le topic face. `speaking_stop()`
       coupe la SÉQUENCE de servos (topic animation) mais ne publie RIEN sur
       le topic face ; `self._perf.emotion(emotion_params)` renvoie une liste
       VIDE dès que le LLM n'a pas émis de JSON d'émotion final exploitable
       (cas courant) -- résultat : la bouche continuait de s'agiter pendant
       toute la pause d'écoute suivante, sans qu'aucun message face ne
       vienne jamais l'arrêter. `_speak_reply` publie désormais idle() (visage
       neutre) en RATTRAPAGE si `emotion(...)` n'a rien produit (chemin
       nominal), et de façon INCONDITIONNELLE sur le chemin d'erreur LLM/TTS
       (une panne ne laisse jamais un `emotion_params` de fin fiable) --
       toujours APRÈS `speaking_stop()`, jamais avant.

       RÉGIE (2026-10-14, lot R3 « Chantiers », dadou_robot_ros/docs/
       etude-repetition-simulee.md §13.6) : deux kwargs OPTIONNELS de plus,
       `stage` (vision.ai.stage.StageState) et `on_transcript` -- défaut None
       = comportement HISTORIQUE inchangé, MÊME clause de réversibilité que
       ci-dessus (les tests existants restent verts sans y toucher). Avec
       `stage` : un texte TAPÉ par la régie est servi comme un énoncé entendu
       (ni micro ni STT, au début du tour ou en interrompant l'écoute), la
       PANNE courante est appliquée au texte compris (deaf = tour abandonné,
       garble = contresens, delay = sommeil avant le LLM, mute = répliques
       non synthétisées), et la CONSIGNE courante part au LLM comme second
       message system. `on_transcript(role, texte)` reçoit ce que Didier a
       compris ("david", après garble) et chaque phrase qu'il dit ("didier")
       -- jamais les consignes ni les pannes (David ignore le tirage).

       MOUVEMENT (2026-10-22, lot I1 « mouvement à la voix », dadou_robot_ros/
       docs/etude-repetition-simulee.md §13.11) : kwarg OPTIONNEL `on_move`,
       défaut None = comportement HISTORIQUE inchangé (même clause de
       réversibilité). Branché, il reçoit "go" ou "stop" quand le JSON de fin
       porte la clé "marche" (cf. personas.MOVE_TEMPLATE) ; toute autre valeur
       est ignorée (warning). Depuis le 2026-10-31 (lot M1 « Aller voir »,
       dadou_robot_ros/docs/spec-aller-voir.md §2.2) : la clé "aller_voir"
       lui passe le dict {"cmd": "aller_voir", "objet": …} (cf. _notify_move
       pour la préséance stop > aller_voir > go). Pendant une panne `mute`,
       l'ordre part quand même. Cette brique ne sait RIEN du mouvement : chat_node publie,
       le régisseur de la répétition décide.
       Lot M2 (31/10, même spec §7, GESTES CHIFFRÉS — décision de David :
       des outils généraux plutôt que des cas figés) : la clé "tourner"
       (pivot sur place, degrés signés, + = gauche) lui passe {"cmd":
       "tourner", "angle_deg": …}, la clé "avancer" (mètres, jamais en
       arrière) {"cmd": "avancer", "metres": …} — mises en mouvement,
       préséance stop > aller_voir > tourner > avancer > go. Et kwarg
       OPTIONNEL `on_look` (défaut None = la clé "regarder" n'est pas lue) :
       la clé "regarder" (degrés, + = gauche, 0 = devant ; tête seule, la
       caméra reste au buste) lui passe {"angle_deg": …, "hold_ms":
       LOOK_HOLD_MS} — PAS une mise en mouvement : permise en tour spontané,
       hors verrou de la garde, et émise EN PLUS d'un geste de mouvement.

       METTEUR EN SCÈNE INTÉRIEUR (2026-10-23, lot P, dadou_robot_ros/docs/
       spec-metteur-en-scene.md, étude etude-niveaux-reflexion.md) : la
       bouche (ce moteur) ne pense pas, elle LIT ce que la réflexion
       (reflection_node, autre process) a compris — jamais elle ne l'attend.
       Quatre ajouts, tous inertes tant que rien n'est branché/publié :
       - ARRÊT D'URGENCE vocal (vision.ai.emergency) : sur ce que le STT a
         VRAIMENT produit, AVANT les pannes deaf/garble et le LLM —
         on_move("stop") part dès la fin du STT, puis le tour continue
         (Didier joue l'arrêt en personnage).
       - TABLEAU DE SITUATION (StageState.situation, TTL) : relu à chaque
         tour, envoyé comme message system (llm_stream.SITUATION_PREFIX).
       - TOUR SPONTANÉ (StageState.pop_prompt) : servi pendant une écoute
         SILENCIEUSE d'au moins SPONTANEOUS_MIN_SILENCE_S — jamais pendant
         que quelqu'un parle (in_speech), jamais pendant que Didier parle ni
         chat OFF (le micro est coupé : aucune trame, aucun sondage), jamais
         moins de SPONTANEOUS_MIN_GAP_S après le précédent. Il n'émet
         JAMAIS "go" (seul un humain remet Didier en route) ; tout énoncé de
         David vide l'emplacement (direction devenue caduque).
       - DEMANDE DE RÉFLEXION : clé "reflechir" du JSON de fin ->
         `on_reflect(texte)` (kwarg optionnel, None = rien).

       ÉCOUTE GARDE (2026-10-31, constaté en répétition simulée : « Stop ! »
       crié pendant une réplique n'était JAMAIS entendu — micro coupé
       anti-larsen — et la route continuait d'avancer) : pendant une réplique
       (normale ET spontanée) et dès la fin du STT (_reply_with_stage : panne
       delay et attente du LLM comprises, revue du 31/10 I3), le micro reste
       ouvert dans une écoute réduite à l'URGENCE — décision de David :
       Didier n'est interruptible QUE par un mot d'arrêt, toute autre parole
       reste ignorée comme avant. Critère LÂCHE ici
       (vision.ai.emergency.contains_stop_word, I1) : la tranche contient
       aussi l'écho de Didier, que le critère strict de l'écoute normale
       refuserait. Jamais armée chat OFF ; un OFF en pleine réplique la ferme
       et recoupe le micro (I4). Active SEULEMENT si `on_move` ET `guard_vad` sont
       branchés (chat_node : uniquement quand le mouvement à la voix l'est,
       donc en simulation) ; sinon micro coupé pendant la réplique, comportement
       historique à l'octet près. Mécanique (cf. _ReplyGuard) :
       - un thread LECTEUR (micro -> VAD de garde, seuil REPRIS de l'écoute
         normale, cf. EnergyVad.adopt_threshold) découpe des tranches de
         parole plafonnées à GUARD_SEGMENT_MAX_S ;
       - un thread STT les transcrit (MÊME STT que l'écoute normale, avec son
         repli ; appels sérialisés par `_stt_lock` : FallbackStt n'est pas
         sûr entre threads) ;
       - urgence -> on_move("stop") D'ABORD, puis AudioPlayer.interrupt(), et
         le thread de conversation abandonne le flux LLM à l'événement suivant
         (visage idle, ligne transcript "david", AUCUN appel LLM : Didier se
         tait, il ne joue pas l'arrêt) ;
       - les pannes de régie (deaf/garble/mute) ne s'appliquent PAS à
         l'écoute garde (revue I3 du 23/10 : une panne simule
         l'incompréhension, jamais la surdité à l'urgence) ;
       - fin de réplique : la garde est FERMÉE (jeton sous verrou) avant de
         rendre le micro. Effets SÉPARÉS (revue du 31/10, B1) : un mot d'arrêt
         capté avant la fermeture — tranche en cours comprise — émet ENCORE
         "stop" même transcrit après coup (idempotent, sens sûr : le "go" de
         la réplique est souvent déjà parti) ; seule l'INTERRUPTION (son,
         réplique) est limitée à la réplique courante. Un "go" ultérieur
         attend que ces stops tardifs soient jugés (GUARD_LATE_GO_WAIT_S) ;
       - file STT bornée (GUARD_QUEUE_MAX, I2) : les tranches récentes
         d'abord ; la garde ne touche pas `last_source` du STT (m1).
       ÉCHO : Didier s'entend dans le micro. Seconde revue du 31/10
       (important 1) : un mot d'arrêt qu'il a LUI-MÊME prononcé dans la
       réplique en cours (forme normalisée exacte) est ignoré par la garde —
       sinon « d'accord, je m'arrête » coupait sa réplique, et un « stop » de
       son écho suivait son propre "go". Faux négatif ACCEPTÉ et testé :
       David qui crie la même forme que Didier vient de dire n'est pas
       entendu par la garde. Faux positifs restants, sens sûr : l'écho d'une
       forme qu'il n'a pas dite dans la réplique (STT qui transforme un mot).
       Coût : son écho déclenche aussi des transcriptions (une par tranche)
       pendant qu'il parle. Première réplique avant toute calibration de
       l'écoute normale : seuil PLANCHER de la config (EnergyVad.floor_threshold),
       jamais une calibration sur sa propre voix (mineur 4). Ce n'est PAS un arrêt de sécurité (cf. vision.ai.emergency) : le
       deadman et la télécommande restent les arrêts effectifs.
"""
from __future__ import annotations

import logging
import math
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Union

from vision.ai import performance
from vision.ai.emergency import is_emergency_stop, normalized_words, stop_words_in
from vision.ai.stage import ROLE_DAVID, ROLE_DIDIER, StageState, garble_text
from vision.ai.stream_parser import Didascalie, Emotion, Sentence, StreamPerformanceParser

# Logger stdlib (PAS le logger rclpy : ce module reste sans dépendance ROS,
# cf. docstring — le node chat configure le niveau/format dans son main()).
# Les tours de conversation sont journalisés ici (STT, répliques, abandons) :
# indispensable pour suivre un protocole physique en direct — le premier test
# micro réel (2026-07-11) s'est fait à l'aveugle faute de ces logs.
logger = logging.getLogger(__name__)

# Attente (s) par défaut avant de retenter un tour quand le flux micro est
# mort : sans elle, run_forever repart IMMÉDIATEMENT dans run_once -> un
# périphérique indisponible (arecord orphelin, câble débranché) devient une
# boucle serrée qui respawne arecord en continu (~200 % CPU constatés au
# premier test réel, 2026-07-11). 0,5 s suffit : assez court pour reprendre
# vite quand le micro revient, assez long pour que la boucle soit inoffensive.
DEAD_MIC_BACKOFF_S = 0.5

# Pas de sondage (s) de la file des textes tapés pendant l'attente « micro
# mort » (cf. _wait_dead_mic_backoff) : un texte de la régie doit être servi
# même quand le micro est HS (banc sans micro, carte débranchée) — attendre
# le backoff à l'aveugle le retarderait pour rien. 50 ms : imperceptible
# pour la régie, négligeable en CPU.
STAGE_POLL_S = 0.05

# Silence d'écoute minimal (s) avant de servir un tour spontané : compté
# depuis le DÉBUT de l'écoute (le micro vient d'être rouvert). Sans lui,
# Didier enchaînerait sa relance juste après sa propre réplique, sans laisser
# à David le temps de répondre — c'est une relance, pas une interruption.
SPONTANEOUS_MIN_SILENCE_S = 3.0

# Écart minimal (s) entre deux tours spontanés SERVIS, mesuré côté PAROLE.
# Revue adversariale du 23/10 (M5) : le seul garde-fou de fréquence vivait
# dans reflection_node (SpontaneousPolicy, 12 s) — un autre éditeur de
# chat_prompt, ou un node relancé (état perdu), faisait enchaîner Didier
# relance sur relance. Trop tôt, la direction n'est PAS consommée : elle
# reste dans l'emplacement et se périme (PROMPT_TTL_S) si l'écart n'est pas
# atteint à temps.
SPONTANEOUS_MIN_GAP_S = 10.0

# Texte « user » d'un tour spontané (texte fixé par la spec P3). Il entre dans
# ChatDB comme tour user : VOULU — Haiku 5.5 exige l'alternance user/assistant
# (pas de prefill assistant), et l'historique garde trace du silence.
SPONTANEOUS_USER_TEXT = "(Silence. Personne ne te parle : c'est à toi de relancer la scène.)"

# Plafond (s) d'une tranche de l'écoute garde (cf. docstring de module ÉCOUTE
# GARDE) : un « Stop ! » est court ; sans plafond, l'écho continu de Didier
# (VAD jamais revenue au silence) ne serait transcrit qu'en fin de réplique —
# trop tard. Au plafond, la tranche part au STT telle quelle et la suivante
# commence par le pré-roll (~450 ms de CHEVAUCHEMENT) : un mot à cheval sur la
# coupure se retrouve entier dans la tranche suivante.
GUARD_SEGMENT_MAX_S = 2.5

# Attente maximale (s) de la fin du thread lecteur de l'écoute garde, à la
# fermeture : mic.stop() le débloque (EOF d'arecord) en une trame (~30 ms) ;
# au-delà, il est déclaré fuyant (warning) — il pourrait encore lire le micro.
GUARD_JOIN_TIMEOUT_S = 1.0

# Tranches en ATTENTE de STT gardées au plus (revue du 31/10, I2) : quand le
# STT est plus lent que la parole (écho continu de Didier), la plus ANCIENNE
# est remplacée — un écho vieux de 5 s n'a plus aucune valeur, le « Stop ! »
# qui compte est le plus récent.
GUARD_QUEUE_MAX = 2

# Pas de sondage (s) du thread STT de la garde (fin du lecteur + file vide =
# fin du thread) : imperceptible, négligeable en CPU.
GUARD_POLL_S = 0.05

# Attente maximale (s), avant d'émettre un "go", que l'écoute garde de la
# réplique PRÉCÉDENTE ait fini de juger ses dernières tranches (revue du 31/10,
# B1) : un « Stop ! » de fin de réplique transcrit en retard ne doit jamais
# partir APRÈS un "go" plus récent (il annulerait la nouvelle intention de
# David). Au-delà (STT bloqué), le "go" part : si le stop arrive ensuite,
# Didier s'arrête — sens sûr.
GUARD_LATE_GO_WAIT_S = 5.0

# Lot M2 (31/10, dadou_robot_ros/docs/spec-aller-voir.md §7) : GESTES
# CHIFFRÉS (décision de David : des outils généraux, pas des cas figés).
# Valeur attendue = NOMBRE JSON (int ou float fini ; un booléen n'en est pas
# un, même si bool hérite d'int en Python). Les mots ci-dessous sont tolérés
# pour la robustesse (le LLM écrit parfois "droite" au lieu de -60) ;
# normalisation strip + minuscules SEULEMENT ; "demi-tour" (tiret) et
# "demi tour" sont des graphies du MÊME mot, ajoutées le 31/10 (le LLM les
# écrira) ; "90" (chaîne) n'est pas 90 — aucun geste n'est deviné.
# Convention d'angle commune : degrés, + = GAUCHE (sens trigonométrique ROS).
LOOK_WORDS = {"gauche": 60, "droite": -60, "devant": 0}
TURN_WORDS = {"gauche": 90, "droite": -90, "demi_tour": 180, "demi-tour": 180, "demi tour": 180}
# Pivot borné à |a| <= TURN_MAX_DEG (au-delà = ignoré, jamais rogné).
TURN_MAX_DEG = 180
# Avancée bornée à 0 < m <= FORWARD_MAX_M : 0 ou négatif = ignoré (Didier ne
# recule pas), au-delà = ignoré (jamais rogné).
FORWARD_MAX_M = 5
# Durée de tenue du regard (ms) envoyée sur `look` (spec §7.1 ; le
# consommateur la borne lui-même à 1000-8000 ms).
LOOK_HOLD_MS = 4000


def _gesture_number(raw, words=None):
    """Valeur d'une clé de geste chiffré -> nombre, ou None si illisible :
    int/float fini tel quel (le type est GARDÉ : 90 reste 90, 1.5 reste 1.5),
    chaîne = mot de `words` après strip + minuscules, tout le reste (bool,
    nan/inf, chaîne inconnue ou numérique, liste…) -> None. Les BORNES sont
    à l'appelant (elles diffèrent par clé)."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return raw if math.isfinite(raw) else None
    if isinstance(raw, str) and words:
        return words.get(raw.strip().lower())
    return None

# Valeur sentinelle : le STT n'expose pas `last_source` (rien à restaurer).
_NO_SOURCE = object()


@dataclass(frozen=True)
class SpontaneousPrompt:
    """Troisième type de retour de _listen_for_utterance (avec bytes = énoncé
    et str = texte tapé) : une direction de tour spontané à servir. Une
    dataclass et pas une str : run_once distingue les cas par isinstance,
    une str serait confondue avec un texte tapé (servi comme parole de David)."""
    direction: str


class _ReplyGuard:
    """Écoute GARDE d'UNE réplique (cf. docstring de module ÉCOUTE GARDE) :
    créée, démarrée puis fermée par ConversationEngine, jamais réutilisée —
    une instance = un jeton de réplique. Deux threads démons : LECTEUR
    (read_frame -> VAD -> tranches) et STT (tranches -> texte -> mot
    d'arrêt), séparés pour que la lecture du micro ne s'arrête jamais pendant
    une transcription (sinon un « Stop ! » crié pendant que la tranche
    précédente — l'écho de Didier — se transcrit serait perdu).

    DEUX EFFETS SÉPARÉS (revue du 31/10, B1) : l'ORDRE "stop" part pour tout
    mot d'arrêt capté tant que la garde écoutait, même transcrit APRÈS la fin
    de la réplique (idempotent, sens sûr — le "go" de la réplique est souvent
    déjà parti) ; l'INTERRUPTION (son coupé, réplique abandonnée) ne vaut que
    pour la réplique courante. À la fermeture, la tranche en cours part au
    STT et le thread STT juge les tranches captées AVANT la fermeture, puis
    s'arrête.

    `lock` protège `closed` et l'ordre « stop émis PUIS interrupted levé » :
    ConversationEngine._notify_move le prend aussi avant d'émettre un "go"
    (sinon un "go" de fin de JSON, traité pile pendant l'urgence, pourrait
    partir APRÈS le stop et remettre Didier en route). Ordre des verrous,
    partout : `stt_lock` PUIS `lock` (jamais l'inverse : pas d'interblocage)."""

    def __init__(self, *, mic, vad, stt, stt_lock: threading.Lock,
                 emit_stop: Callable[[], None], interrupt_audio: Callable[[], None],
                 should_listen: Callable[[], bool]):
        self._mic = mic
        self._vad = vad
        self._stt = stt
        self._stt_lock = stt_lock
        self._emit_stop = emit_stop
        self._interrupt_audio = interrupt_audio
        # Chat ON ? (revue du 31/10, I4) : relu à CHAQUE trame — un OFF en
        # pleine réplique ferme l'écoute et recoupe le micro.
        self._should_listen = should_listen
        self.lock = threading.Lock()
        self.closed = False
        # Event (et pas bool) : lu SANS verrou à chaque événement par le
        # thread de conversation (cf. ConversationEngine._reply_interrupted).
        self.interrupted = threading.Event()
        # Texte entendu qui a interrompu la réplique (ligne transcript "david").
        self.heard: Optional[str] = None
        # Mots normalisés des phrases que CETTE réplique a déjà envoyées au
        # haut-parleur (cf. note_spoken) — sous `lock`.
        self._spoken: set = set()
        self._stop_reading = threading.Event()
        # Levé par le lecteur APRÈS sa dernière tranche : avec une file vide,
        # c'est le signal de fin du thread STT (pas de sentinelle dans une
        # file bornée — elle pourrait évincer une vraie tranche).
        self._reader_done = threading.Event()
        self._segments: "queue.Queue" = queue.Queue(maxsize=GUARD_QUEUE_MAX)
        # S16_LE mono : 2 octets par échantillon (cf. vision.audio.mic).
        self._cap_bytes = int(GUARD_SEGMENT_MAX_S * mic.sample_rate) * 2
        self._reader = threading.Thread(target=self._read_loop, daemon=True,
                                        name="ecoute-garde-micro")
        self._transcriber = threading.Thread(target=self._transcribe_loop, daemon=True,
                                             name="ecoute-garde-stt")

    def start(self) -> None:
        self._reader.start()
        self._transcriber.start()

    def close(self) -> None:
        """Ferme la garde (jeton) : plus d'INTERRUPTION possible de la
        réplique ; le lecteur s'arrête à la trame suivante (en envoyant sa
        tranche partielle), le thread STT finit les tranches déjà captées
        (non attendu ici : il peut durer des secondes) puis s'arrête."""
        with self.lock:
            self.closed = True
        self._stop_reading.set()

    def note_spoken(self, text: str) -> None:
        """Phrase de Didier enfilée pour lecture (thread de conversation,
        AVANT play() : son écho ne peut pas précéder cet appel)."""
        words = normalized_words(text)
        with self.lock:
            self._spoken |= words

    def join_reader(self, timeout: float) -> bool:
        """True si le lecteur est bien terminé (cf. GUARD_JOIN_TIMEOUT_S)."""
        self._reader.join(timeout)
        return not self._reader.is_alive()

    def join_transcriber(self, timeout: float) -> bool:
        """True si le thread STT est terminé (cf. GUARD_LATE_GO_WAIT_S)."""
        self._transcriber.join(timeout)
        return not self._transcriber.is_alive()

    def _push(self, segment: bytes) -> None:
        """Enfile une tranche ; file pleine = la plus ANCIENNE est jetée
        (cf. GUARD_QUEUE_MAX). Boucle : le thread STT peut vider la file
        entre deux essais."""
        while True:
            try:
                self._segments.put_nowait(segment)
                return
            except queue.Full:
                try:
                    self._segments.get_nowait()
                    logger.debug("Écoute garde : tranche ancienne jetée (STT en retard).")
                except queue.Empty:
                    pass

    def _read_loop(self) -> None:
        """Thread LECTEUR. Toute exception = écoute garde perdue pour CETTE
        réplique, jamais la réplique elle-même (log + fin du thread)."""
        try:
            self._read_frames()
        except Exception:
            if not self._stop_reading.is_set():
                logger.warning("Écoute garde : lecture micro en échec — arrêt vocal "
                               "indisponible jusqu'à la fin de la réplique.", exc_info=True)
        finally:
            self._reader_done.set()

    def _read_frames(self) -> None:
        """Même usage de la VAD que _listen_for_utterance (speech_start ->
        pré-roll, accumulation, speech_end), SANS gate ni vumètre (leur état
        appartient à l'écoute normale), plus le plafond GUARD_SEGMENT_MAX_S.
        Quelle que soit la sortie (fermeture, flux mort, chat OFF), la tranche
        EN COURS part au STT (B1) : « Stop ! » dit pile en fin de réplique."""
        segment = b""
        in_speech = False
        try:
            while not self._stop_reading.is_set():
                if not self._should_listen():
                    # Chat OFF en pleine réplique (I4) : la garde se ferme et
                    # rend le micro COUPÉ (chat_node l'a peut-être déjà coupé ;
                    # stop() est idempotent).
                    logger.info("Écoute garde : chat OFF pendant la réplique — micro coupé.")
                    self._stop_reading.set()
                    self._mic.stop()
                    return
                frame = self._mic.read_frame()
                if frame is None:
                    # Fin normale (fermeture : mic.stop() -> EOF) ou flux mort.
                    if not self._stop_reading.is_set():
                        logger.info("Écoute garde : flux micro terminé pendant la réplique — "
                                    "arrêt vocal indisponible jusqu'à sa fin.")
                    return
                event = self._vad.feed(self._mic.frame_rms(frame))
                if not in_speech:
                    if event is not None and event.kind == "speech_start":
                        in_speech = True
                        segment = self._mic.preroll()   # inclut déjà CETTE trame
                    continue
                segment += frame
                if event is not None and event.kind == "speech_end":
                    self._push(segment)
                    segment = b""
                    in_speech = False
                elif len(segment) >= self._cap_bytes:
                    # Plafond : la VAD reste en SPEECH, la tranche suivante
                    # repart du pré-roll (chevauchement, cf. GUARD_SEGMENT_MAX_S).
                    self._push(segment)
                    segment = self._mic.preroll()
        finally:
            if in_speech and segment:
                self._push(segment)

    def _transcribe_loop(self) -> None:
        """Thread STT : une tranche à la fois, la plus ancienne GARDÉE
        d'abord. S'arrête sur une urgence, ou quand le lecteur est fini et la
        file vide (toutes les tranches captées ont été jugées). Transcription
        ET décision sous `stt_lock` : le STT de garde attend le STT principal
        (I3), et un stop tardif part avant que le tour suivant ne transcrive."""
        while True:
            try:
                segment = self._segments.get(timeout=GUARD_POLL_S)
            except queue.Empty:
                if self._reader_done.is_set() and self._segments.empty():
                    return
                continue
            with self._stt_lock:
                try:
                    text = self._transcribe(segment)
                except Exception:
                    # Exigence : un STT en échec ne casse JAMAIS la réplique —
                    # la tranche est perdue, la garde continue sur les suivantes.
                    logger.warning("Écoute garde : STT en échec (tranche ignorée, la réplique "
                                   "continue).", exc_info=True)
                    continue
                if self._handle_text(text):
                    return

    def _transcribe(self, segment: bytes) -> str:
        """MÊME STT que l'écoute normale (avec son repli), sans toucher à sa
        source affichée (revue du 31/10, m1) : `last_source` (FallbackStt,
        page « Oreille de Didier ») décrit l'énoncé de DAVID du tour, pas une
        tranche de garde — sauvegardée puis restaurée, sous `stt_lock`."""
        saved = getattr(self._stt, "last_source", _NO_SOURCE)
        try:
            return self._stt.transcribe(segment, self._mic.sample_rate)
        finally:
            if saved is not _NO_SOURCE:
                self._stt.last_source = saved

    def _handle_text(self, text) -> bool:
        """Décide sur UN texte transcrit (appelé sous `stt_lock`) ; True =
        mot d'arrêt traité (fin du thread STT). Critère LÂCHE (un mot d'arrêt
        présent suffit, I1) : la tranche contient aussi l'écho de Didier.

        ÉCHO ÉCARTÉ (seconde revue du 31/10, important 1) : un mot d'arrêt
        déjà prononcé par Didier dans CETTE réplique ne compte pas — sur les
        tours de marche, le prompt le pousse à dire « je m'arrête » /
        « stop » (personas.MOVE_TEMPLATE) ; sans ce filtre, son propre écho
        coupait sa réplique et émettait un stop après son "go". Comparaison
        sur la forme normalisée EXACTE (vision.ai.emergency.normalized_words).
        FAUX NÉGATIF ACCEPTÉ : David qui crie « Stop ! » pendant une réplique
        où Didier a lui-même dit « stop » n'est PAS entendu par la garde (le
        deadman et la télécommande restent les arrêts effectifs) — mais
        « Arrêtez ! » l'est (autre forme)."""
        heard_stops = stop_words_in(text)
        if not heard_stops:
            if has_usable_text(text):
                logger.info("Écoute garde : %r ignoré (pas un mot d'arrêt).", text)
            return False
        with self.lock:
            if heard_stops <= self._spoken:
                logger.info("Écoute garde : %r ignoré — %s déjà dit par Didier dans cette "
                            "réplique (écho probable).", text, sorted(heard_stops))
                return False
            # L'ORDRE D'ABORD, avant toute autre chose (log, coupure du son) :
            # c'est lui qui arrête la route — y compris après la fin de la
            # réplique (B1 : idempotent, sens sûr).
            self._emit_stop()
            if self.closed:
                logger.warning("ARRÊT D'URGENCE vocal en fin de réplique (transcrit après "
                               "sa fin) : %r", text)
                return True
            logger.warning("ARRÊT D'URGENCE vocal pendant la réplique : %r", text)
            self.heard = text
            self.interrupted.set()
        self._stop_reading.set()
        try:
            self._interrupt_audio()
        except Exception:
            logger.exception("Écoute garde : coupure du son en échec (la réplique sera "
                             "quand même abandonnée).")
        return True


def has_usable_text(text: Optional[str]) -> bool:
    """Un texte STT est exploitable s'il contient au moins 2 caractères
    alphanumériques. POURQUOI pas un simple len(strip()) : whisper transcrit
    le bruit pur en ponctuation ("... ... ..."), qui passait l'ancien filtre
    et déclenchait un appel LLM payant + une réplique de Didier sans que
    personne n'ait parlé (constaté au premier test micro caméra, 2026-07-11)."""
    if not text:
        return False
    return sum(1 for ch in text if ch.isalnum()) >= 2


class ConversationEngine:
    """Un tour de conversation = un cycle écoute -> pensée -> parole complet.
    Toutes les dépendances (I/O réelles ou fakes de test) sont injectées."""

    def __init__(self, *, mic, vad, stt, brain, tts, player,
                 publish: Callable[[object], None],
                 perf=None,
                 beeps_pcm: bytes = b"", beeps_rate: int = 22050,
                 refresh_ms: int = 15000,
                 dead_mic_backoff_s: float = DEAD_MIC_BACKOFF_S,
                 on_state: Optional[Callable[[str], None]] = None,
                 initial_state: Optional[str] = None,
                 gate=None,
                 show_audio_active: Optional[Callable[[], bool]] = None,
                 on_meter: Optional[Callable[[float, float, bool, bool], None]] = None,
                 on_timing: Optional[Callable[[dict], None]] = None,
                 stage: Optional[StageState] = None,
                 on_transcript: Optional[Callable[[str, str], None]] = None,
                 on_move: Optional[Callable[[Union[str, dict]], None]] = None,
                 on_reflect: Optional[Callable[[str], None]] = None,
                 guard_vad=None,
                 on_look: Optional[Callable[[dict], None]] = None):
        self._mic = mic
        self._vad = vad
        # Écoute garde (cf. docstring de module ÉCOUTE GARDE) : une SECONDE
        # instance de VAD (même config que `vad`), jamais la même — elle est
        # nourrie depuis un autre thread, et la voix de Didier ne doit jamais
        # toucher l'état de l'écoute normale. None = pas d'écoute garde.
        self._guard_vad = guard_vad
        # Garde de la réplique EN COURS (None hors réplique ou garde inactive).
        self._guard: Optional[_ReplyGuard] = None
        # Dernière garde FERMÉE : son thread STT peut encore juger des tranches
        # de fin de réplique (B1) — un "go" attend qu'il ait fini (cf.
        # _notify_move, GUARD_LATE_GO_WAIT_S).
        self._closed_guard: Optional[_ReplyGuard] = None
        # Sérialise TOUS les appels STT (écoute normale + garde) : un STT de
        # garde peut encore tourner quand le tour suivant transcrit, et
        # FallbackStt (compteurs d'échecs, last_source) n'est pas sûr entre
        # threads. Coût : le STT du tour suivant peut attendre la fin d'une
        # tranche de garde en vol.
        self._stt_lock = threading.Lock()
        # Source STT du tour en cours (cf. run_once, _notify_timing).
        self._turn_stt_source: Optional[str] = None
        # Gate « source audio vivante » (half-duplex élargi, cf.
        # dadou_robot_ros/docs/etude-declenchement-conversation.md §10) :
        # None = comportement HISTORIQUE inchangé à l'octet près (clause de
        # réversibilité du lot, cf. §10.5 -- les tests existants restent
        # verts sans y toucher). `show_audio_active` est un CALLABLE (pas un
        # bool figé au constructeur) : il doit refléter l'état COURANT de
        # l'animation en cours à chaque frame, recalculé à la volée par
        # chat_node (cf. arbitration.effective_state, qui applique sa propre
        # péremption deadman) — un bool gelé à la construction serait faux
        # dès la première séquence de spectacle lancée après coup.
        self._gate = gate
        self._show_audio_active = show_audio_active
        # Vumètre web (2026-09-13, cf. docstring de module OBSERVABILITÉ) :
        # None = comportement HISTORIQUE inchangé (aucun coût -- cf.
        # _listen_for_utterance, frame_peak() n'est même pas calculé si ni
        # `on_meter` ni `gate` ne sont branchés) ; câblé par chat_node quand
        # `diag_port` > 0.
        self._on_meter = on_meter
        # Latences par tour (même lot) : None = comportement historique inchangé.
        self._on_timing = on_timing
        # Régie (lot R3, cf. docstring de module RÉGIE) : None = comportement
        # historique inchangé. Partagé avec chat_node, qui l'ÉCRIT depuis le
        # thread rclpy.spin — StageState porte son propre verrou.
        self._stage = stage
        # Transcript (même lot) : None = personne n'écoute.
        self._on_transcript = on_transcript
        # Mouvement à la voix (lot I1, cf. docstring de module MOUVEMENT) :
        # None = comportement historique STRICTEMENT inchangé (la clé
        # "marche" n'est même pas lue).
        self._on_move = on_move
        # Regard (lot M2, cf. docstring de module MOUVEMENT) : None = la clé
        # "regarder" n'est pas lue.
        self._on_look = on_look
        # Demande de réflexion (cf. docstring de module METTEUR EN SCÈNE) :
        # None = la clé "reflechir" n'est pas lue.
        self._on_reflect = on_reflect
        # Début du dernier tour spontané servi (horloge monotone), cf.
        # SPONTANEOUS_MIN_GAP_S ; None = aucun encore.
        self._last_spontaneous_at: Optional[float] = None
        self._stt = stt
        self._brain = brain
        self._tts = tts
        self._player = player
        self._publish = publish
        # Callback d'état optionnel (chat_node V2, lot D0 outillage) : expose
        # listening/thinking/speaking/off pour la régie, le télédiagnostic et
        # le futur engagement_node (cf. dadou_robot_ros/docs/
        # etude-declenchement-conversation.md §6.2 -- IN_CONVERSATION a besoin
        # de savoir si le chat écoute encore). None = personne n'écoute
        # (comportement actuel inchangé, cf. _set_state ci-dessous).
        self._on_state = on_state
        # Dédup interne (cf. _set_state) : None au départ, aucun état n'a
        # encore été vu.
        self._last_state: Optional[str] = None
        # perf par défaut = le MODULE vision.ai.performance lui-même (ses
        # fonctions thinking/speaking_start/... sont utilisées comme
        # namespace) — un fake de test fournit un objet avec les mêmes noms
        # de fonctions, sans avoir à mocker un module entier.
        self._perf = perf if perf is not None else performance
        self._refresh_ms = refresh_ms
        # Injectable pour les tests (0.0 = pas d'attente) — cf. constante
        # DEAD_MIC_BACKOFF_S pour le pourquoi de la valeur par défaut.
        self._dead_mic_backoff_s = dead_mic_backoff_s
        # Interrupteur de mode interactif, posé par run_forever (None tant
        # qu'on n'y est pas passé) : run_once s'en sert UNIQUEMENT pour
        # distinguer « micro mort » (incident -> warning + backoff + restart)
        # de « micro coupé volontairement par le toggle OFF » (silencieux,
        # pas de restart — le micro doit RESTER coupé pendant la pause).
        self._enabled: Optional[threading.Event] = None

        # La piste de bips est écrite en wav temporaire UNE SEULE FOIS ici
        # (pas à chaque tour) : son contenu ne change pas d'un tour à
        # l'autre, cf. vision.audio.playback.write_wav_tempfile. Import
        # différé (pas en tête de module) : conversation.py doit rester
        # important sans exiger que vision.audio.playback soit disponible
        # dans TOUS les contextes qui pourraient un jour importer ce module
        # (aucun aujourd'hui, mais évite d'ajouter un couplage silencieux) —
        # en pratique playback.py est pur stdlib+numpy, donc ceci reste sûr
        # même en CI minimal.
        self._beeps_path: Optional[str] = None
        if beeps_pcm:
            from vision.audio.playback import write_wav_tempfile
            self._beeps_path = write_wav_tempfile(beeps_pcm, beeps_rate)

        # État initial émis PAR LE MOTEUR à la construction (et non poussé de
        # l'extérieur en écrivant _last_state, ce qui violerait la frontière
        # de la brique pure) : un abonné ROS latché (chat_node publie en
        # TRANSIENT_LOCAL) doit trouver une valeur dès la souscription, MÊME
        # avant le premier tour — la dédup de _set_state absorbera ensuite le
        # "listening" que run_once() re-signalera au démarrage du thread.
        if initial_state is not None:
            self._set_state(initial_state)

    def _set_state(self, state: str) -> None:
        """Notifie `on_state` d'un changement d'état ("listening"/"thinking"/
        "speaking"/"off"), avec DÉDUPLICATION sur `_last_state` : nécessaire
        car certains points d'émission sont appelés en boucle (la pause
        toggle OFF de run_forever ré-attend à 0,2 s tant que le mode
        interactif reste désactivé ; "speaking" est réémis à chaque Sentence,
        cf. _handle_event) -- sans dédup, un abonné ROS recevrait un flot de
        messages identiques pour rien. try/except : `on_state` finira par
        publier sur un topic ROS (chat_node), un monde que cette brique pure
        ne connaît pas -- un callback qui plante ne doit JAMAIS interrompre un
        tour de conversation en cours, seulement perdre cette notification
        d'état (log warning pour ne pas le perdre en silence)."""
        if self._on_state is None or state == self._last_state:
            return
        self._last_state = state
        try:
            self._on_state(state)
        except Exception:
            logger.warning("Callback on_state en échec (état %r ignoré).", state, exc_info=True)

    def _notify_meter(self, level: float, peak: float, blocked: bool, in_speech: bool) -> None:
        """Notifie `on_meter` (vumètre web, cf. docstring de module
        OBSERVABILITÉ) pour LA TRAME courante -- appelé à la cadence des
        trames (30 ms) par `_listen_for_utterance`. try/except EN DEBUG (pas
        warning, contrairement à `_notify_timing` ci-dessous) : à cette
        cadence, un souci récurrent spammerait le journal pour rien ; le
        vumètre est un outil de confort, jamais un signal de sécurité, cf.
        docstring de module -- un plantage ne doit perdre QUE cette
        notification, jamais faire taire Didier."""
        if self._on_meter is None:
            return
        try:
            self._on_meter(level, peak, blocked, in_speech)
        except Exception:
            logger.debug("Callback on_meter en échec (trame ignorée).", exc_info=True)

    def _notify_timing(self, timing: dict) -> None:
        """Notifie `on_timing` (console de diagnostic web) UNE fois par tour
        qui a réellement atteint le STT (cf. run_once : les abandons AVANT le
        STT -- flux micro mort, coupure volontaire -- n'ont rien à mesurer et
        ne déclenchent jamais cet appel, cf. docstring de `run_once`).
        try/except EN WARNING (pas debug, contrairement à `_notify_meter`) :
        un tour, ça n'arrive pas à 33 Hz -- un warning par tour raté reste
        lisible et utile, sans spammer le journal."""
        if self._on_timing is None:
            return
        # Source du STT de CE tour (FallbackStt.last_source, lue sous
        # _stt_lock dans run_once) : la page « Oreille de Didier » ne doit
        # jamais afficher celle d'une tranche de l'écoute garde.
        timing = dict(timing, stt_source=self._turn_stt_source)
        try:
            self._on_timing(timing)
        except Exception:
            logger.warning("Callback on_timing en échec (mesure du tour perdue).", exc_info=True)

    def _notify_transcript(self, role: str, text: str) -> None:
        """Notifie `on_transcript` (topic chat_transcript, cf. docstring de
        module RÉGIE). Même garde que `_notify_timing` (warning, pas debug :
        une ligne de dialogue, ça n'arrive pas à 33 Hz) — une page de régie
        cassée ne doit jamais rendre Didier muet."""
        if self._on_transcript is None:
            return
        try:
            self._on_transcript(role, text)
        except Exception:
            logger.warning("Callback on_transcript en échec (ligne %r perdue).", role,
                           exc_info=True)

    def _notify_move(self, params, spontaneous: bool = False) -> None:
        """Clé "marche" du JSON de fin -> `on_move("go"|"stop")` (cf.
        docstring de module MOUVEMENT). Normalisée (str, strip, lower) : le
        LLM écrit parfois "Go" ou "stop ". Toute autre valeur ou type =
        ignorée avec un warning — jamais d'exception, jamais d'ordre deviné
        (« recule » n'est PAS un stop). Callback qui lève = tour préservé :
        un ordre perdu vaut mieux qu'un Didier muet.

        `spontaneous` (tour spontané, cf. _serve_prompt) : seul "stop" passe.
        Revue adversariale du 23/10 (B1, bloquant) : une direction du metteur
        en scène (« reprends la route ») faisait écrire "go" au LLM — Didier
        se remettait en marche sans qu'aucun humain l'ait demandé, y compris
        juste après un « stop » de David.

        Clé "aller_voir" (lot M1, 31/10, dadou_robot_ros/docs/
        spec-aller-voir.md §2.2) : chaîne non vide, rognée (la casse est
        GARDÉE : la résolution de l'objet est l'affaire du régisseur) ->
        `on_move({"cmd": "aller_voir", "objet": …})`, payload du contrat tel
        quel. Mêmes règles que "go" (c'est une MISE EN MOUVEMENT) : jamais en
        tour spontané, barrière des stops tardifs, verrou de la garde. Les
        deux clés dans la même réplique : "stop" gagne toujours (aller_voir
        jeté), sinon aller_voir gagne sur "go" (un seul ordre émis).

        Clés chiffrées (lot M2, 31/10, même spec §7.2, cf. _gesture_number) :
        "tourner" (degrés signés, + = gauche, |a| <= TURN_MAX_DEG, mots de
        TURN_WORDS) -> `on_move({"cmd": "tourner", "angle_deg": a})` ;
        "avancer" (mètres, 0 < m <= FORWARD_MAX_M, Didier ne recule pas) ->
        `on_move({"cmd": "avancer", "metres": m})`. Valeur illisible ou hors
        bornes = warning, clé ignorée (jamais rognée). Mises en mouvement
        comme aller_voir (mêmes règles). Préséance si plusieurs clés : stop
        > aller_voir > tourner > avancer > go — un seul ordre émis, les clés
        perdantes journalisées."""
        if self._on_move is None or not isinstance(params, dict):
            return
        cmd = None
        if "marche" in params:
            raw = params["marche"]
            cmd = raw.strip().lower() if isinstance(raw, str) else None
            if cmd not in ("go", "stop"):
                logger.warning("Clé \"marche\" ignorée : %r (attendu \"go\" ou \"stop\").", raw)
                cmd = None
        # Gestes valides, DANS L'ORDRE DE PRÉSÉANCE : (clé, valeur, intention).
        gestures = []
        if "aller_voir" in params:
            raw = params["aller_voir"]
            objet = raw.strip() if isinstance(raw, str) else None
            if objet:
                gestures.append(("aller_voir", objet, {"cmd": "aller_voir", "objet": objet}))
            else:
                logger.warning("Clé \"aller_voir\" ignorée : %r (attendu un nom d'objet).", raw)
        if "tourner" in params:
            raw = params["tourner"]
            angle = _gesture_number(raw, TURN_WORDS)
            if angle is not None and abs(angle) <= TURN_MAX_DEG:
                gestures.append(("tourner", angle, {"cmd": "tourner", "angle_deg": angle}))
            else:
                logger.warning("Clé \"tourner\" ignorée : %r (attendu des degrés signés, "
                               "|a| <= %d, ou \"gauche\"/\"droite\"/\"demi_tour\").",
                               raw, TURN_MAX_DEG)
        if "avancer" in params:
            raw = params["avancer"]
            metres = _gesture_number(raw)
            if metres is not None and 0 < metres <= FORWARD_MAX_M:
                gestures.append(("avancer", metres, {"cmd": "avancer", "metres": metres}))
            else:
                logger.warning("Clé \"avancer\" ignorée : %r (attendu des mètres, "
                               "0 < m <= %d : Didier ne recule pas).", raw, FORWARD_MAX_M)
        if cmd == "stop":
            for key, value, _intent in gestures:
                logger.warning("Clé \"%s\" : %r ignoré : la même réplique "
                               "demande \"stop\" (le stop gagne toujours).", key, value)
            self._emit_move("stop")
            return
        if gestures:
            key, value, intent = gestures[0]
            if cmd == "go":
                logger.info("Clé \"marche\" : go remplacé par %s %r.", key, value)
            for lost_key, lost_value, _intent in gestures[1:]:
                logger.info("Clé \"%s\" : %r remplacé par %s %r.",
                            lost_key, lost_value, key, value)
            if spontaneous:
                logger.warning("Clé \"%s\" : %r ignoré : tour spontané "
                               "(aucun humain ne l'a demandé).", key, value)
                return
            self._emit_start(intent, f"Clé \"{key}\" : {value!r}")
            return
        if cmd != "go":
            return
        if spontaneous:
            logger.warning("Clé \"marche\" : go ignoré : tour spontané "
                           "(aucun humain ne l'a demandé).")
            return
        self._emit_start("go", "Clé \"marche\" : go")

    def _emit_start(self, intent, label: str) -> None:
        """Émet un ordre de MISE EN MOUVEMENT ("go", aller_voir, tourner ou
        avancer) en
        respectant l'écoute garde (cf. docstring de module ÉCOUTE GARDE).
        `label` (« Clé "marche" : go ») ne sert qu'aux journaux."""
        # Un stop TARDIF de la réplique précédente (B1) doit partir AVANT cet
        # ordre : sinon il annulerait la nouvelle intention de David.
        closed = self._closed_guard
        if closed is not None and not closed.join_transcriber(GUARD_LATE_GO_WAIT_S):
            logger.warning("Écoute garde précédente encore en cours après %.0f s : %s "
                           "émis quand même (un stop tardif l'annulerait).",
                           GUARD_LATE_GO_WAIT_S, label)
        guard = self._guard
        if guard is None:
            self._emit_move(intent)
            return
        # Sous le verrou de la garde : l'urgence (stop émis PUIS interrupted
        # levé, atomiquement) et cet ordre ne peuvent pas se croiser — jamais
        # de mise en mouvement APRÈS un arrêt vocal de la même réplique.
        with guard.lock:
            if guard.interrupted.is_set():
                logger.warning("%s ignoré : réplique interrompue par un arrêt "
                               "d'urgence vocal.", label)
                return
            self._emit_move(intent)

    def _emit_move(self, cmd) -> None:
        """Seul point d'émission d'une intention de marche — partagé par la
        clé "marche" (fin de réplique), les clés "aller_voir", "tourner" et
        "avancer" (`cmd` est alors le dict du contrat) et l'arrêt d'urgence vocal (avant le LLM). `on_move` None = mouvement désactivé : rien, sans erreur.
        Callback qui lève = ordre perdu, JAMAIS le tour : une publication en
        échec ne doit pas rendre Didier muet (et le deadman reste l'arrêt
        effectif, cf. vision.ai.emergency)."""
        if self._on_move is None:
            return
        try:
            self._on_move(cmd)
        except Exception:
            logger.exception("Callback on_move en échec (ordre %r perdu).", cmd)

    def _notify_look(self, params) -> None:
        """Clé "regarder" du JSON de fin -> `on_look({"angle_deg": a,
        "hold_ms": LOOK_HOLD_MS})` (lot M2, dadou_robot_ros/docs/
        spec-aller-voir.md §7.1). Degrés, + = gauche, 0 = devant, ou un mot
        de LOOK_WORDS (cf. _gesture_number) ; illisible = warning, rien
        d'émis. AUCUNE borne ici : la course utile du cou est l'affaire du
        consommateur (gaze_follower_node), qui la connaît. Tête seule (cou +
        yeux, aucun déplacement) : permise en tour spontané, émise en plus
        d'un geste de mouvement, et NI barrière NI verrou de la garde — un
        arrêt vocal n'a pas à figer le regard. Callback qui lève = regard
        perdu, jamais le tour (même garde que _emit_move)."""
        if self._on_look is None or not isinstance(params, dict) or "regarder" not in params:
            return
        raw = params["regarder"]
        angle = _gesture_number(raw, LOOK_WORDS)
        if angle is None:
            logger.warning("Clé \"regarder\" ignorée : %r (attendu des degrés, "
                           "+ = gauche, ou \"gauche\"/\"droite\"/\"devant\").", raw)
            return
        payload = {"angle_deg": angle, "hold_ms": LOOK_HOLD_MS}
        try:
            self._on_look(payload)
        except Exception:
            logger.exception("Callback on_look en échec (regard %r perdu).", payload)

    def _notify_reflect(self, params) -> None:
        """Clé "reflechir" du JSON de fin -> `on_reflect(demande)` (cf.
        personas.REFLECT_TEMPLATE). Seule une chaîne non vide passe (rognée) ;
        tout autre type est ignoré en silence — la clé est facultative et le
        LLM n'a rien d'autre à y mettre. Même garde que _emit_move."""
        if self._on_reflect is None or not isinstance(params, dict):
            return
        demande = params.get("reflechir")
        if not isinstance(demande, str) or not demande.strip():
            return
        demande = demande.strip()
        logger.info("Demande de réflexion : %r", demande)
        try:
            self._on_reflect(demande)
        except Exception:
            logger.exception("Callback on_reflect en échec (demande %r perdue).", demande)

    def _publish_all(self, messages) -> None:
        """publish() ne prend qu'UN SEUL message à la fois (contrat du
        constructeur) ; les fonctions de vision.ai.performance renvoient des
        LISTES (parfois vides, ex: emotion(None)) — ce helper fait le pont,
        dans l'ordre, sans jamais publier quoi que ce soit pour une liste
        vide (une liste vide = "rien à jouer", pas une erreur)."""
        for message in messages:
            self._publish(message)

    def _handle_event(self, event, emotion_params, timing_marks: dict, mute: bool = False,
                      spontaneous: bool = False):
        """Traduit UN événement du parseur de flux (Sentence/Didascalie/
        Emotion) en effet de bord (publish + synthèse/lecture), et retourne
        les params d'émotion à retenir (inchangés sauf si `event` EST
        l'Emotion — un seul JSON d'émotion possible par tour, en toute fin de
        flux, cf. stream_parser.flush()).

        `timing_marks` (dict mutable {"first_sentence_at", "first_play_at"},
        cf. `_speak_reply`) : horodate le PREMIER événement de chaque sorte
        rencontré dans le tour, pour `on_timing` (docstring de module
        OBSERVABILITÉ) — jamais réécrit une fois posé (`if ... is None`), une
        réponse a en général plusieurs Sentence mais seule la latence du
        PREMIER son compte pour la latence perçue par le spectateur.

        `mute` (panne de régie, cf. docstring de module RÉGIE) : la Sentence
        n'est ni synthétisée ni jouée — tout le reste part normalement
        (transcript, bouche "parle", didascalies, émotion) : c'est le bug
        réel simulé, « texte sans voix » (audio muet en silence).

        `spontaneous` : tour spontané, transmis à _notify_move (jamais de "go")."""
        if isinstance(event, Sentence):
            if timing_marks["first_sentence_at"] is None:
                # Horodaté AVANT même la synthèse TTS qui suit (elle peut
                # prendre du temps) : c'est la latence "il réfléchit" telle
                # que vécue par le spectateur, cf. on_timing.
                timing_marks["first_sentence_at"] = time.monotonic()
            # Journalisée AVANT la synthèse : si le TTS plante, la trace dit
            # quand même ce que Didier ALLAIT dire (diagnostic en direct).
            logger.info("Didier : %s", event.text)
            self._notify_transcript(ROLE_DIDIER, event.text)
            # "speaking" : dédup absorbe la répétition à CHAQUE Sentence d'un
            # même tour (une réponse a en général plusieurs phrases).
            self._set_state("speaking")
            # speaking_start republié à CHAQUE Sentence (pas seulement la
            # première) : sert de rafraîchissement — cf. commentaire
            # chat_animation_refresh_ms dans vision_config.py, l'animation
            # "parle" doit rester active tant que le TTS streame encore.
            self._publish_all(self._perf.speaking_start(self._refresh_ms))
            if mute:
                return emotion_params
            pcm, sample_rate = self._tts.synthesize(event.text)
            if self._reply_interrupted():
                # Urgence tombée PENDANT la synthèse (bloquante) : cette phrase
                # ne doit pas partir au haut-parleur.
                return emotion_params
            guard = self._guard
            if guard is not None:
                # Mots de cette phrase notés AVANT play() : son écho dans le
                # micro ne doit pas passer pour un ordre (cf. _ReplyGuard).
                guard.note_spoken(event.text)
            # play() enfile : la synthèse de la Sentence SUIVANTE peut se
            # faire pendant que celle-ci joue encore (pipeline N/N+1 porté
            # par AudioPlayer, cf. vision.audio.playback).
            self._player.play(pcm, sample_rate)
            if timing_marks["first_play_at"] is None:
                # Premier son ENFILÉ pour lecture (cf. on_timing) — AudioPlayer
                # joue en tâche de fond, donc c'est une approximation par excès
                # du début RÉEL du son (léger délai de mise en file), largement
                # suffisant pour un diagnostic de latence perçue.
                timing_marks["first_play_at"] = time.monotonic()
            return emotion_params

        if isinstance(event, Didascalie):
            self._publish_all(self._perf.didascalie(event.action))
            return emotion_params

        if isinstance(event, Emotion):
            # Indépendant de `mute` : une panne de voix ne coupe pas les
            # jambes (seule la synthèse est muette, cf. ci-dessus) — ni la
            # tête : la demande de réflexion part aussi.
            self._notify_move(event.params, spontaneous)
            # Regard : tête seule, permis en tour spontané (aucun déplacement).
            self._notify_look(event.params)
            self._notify_reflect(event.params)
            return event.params

        return emotion_params

    def run_once(self) -> bool:
        """Un tour complet. Retourne True seulement si le tour a été mené
        jusqu'au bout (émotion publiée) ; False dans tous les cas
        d'abandon : flux micro mort, STT vide/trop court, ou erreur
        LLM/TTS (le spectacle continue, cf. docstring de module)."""
        # Texte tapé en attente (régie, cf. docstring de module RÉGIE) :
        # servi SANS démarrer le micro ni passer par le STT.
        # Source STT du tour (cf. _notify_timing) : None tant que le STT de CE
        # tour n'a pas tourné (texte tapé, tour spontané).
        self._turn_stt_source = None
        typed = self._stage.pop_text() if self._stage is not None else None
        if typed is not None:
            return self._serve_typed_text(typed)

        self._mic.start()
        self._set_state("listening")

        speech_bytes = self._listen_for_utterance()
        if isinstance(speech_bytes, str):
            # Texte tapé arrivé PENDANT l'écoute (cf. _listen_for_utterance,
            # qui a déjà coupé le micro et jeté l'énoncé partiel).
            return self._serve_typed_text(speech_bytes)
        if isinstance(speech_bytes, SpontaneousPrompt):
            # Direction du metteur en scène servie en plein silence (cf.
            # _listen_for_utterance, qui a déjà coupé le micro).
            return self._serve_prompt(speech_bytes.direction)
        if speech_bytes is None:
            if self._enabled is not None and not self._enabled.is_set():
                # Coupure VOLONTAIRE (toggle chat OFF pendant l'écoute, cf.
                # chat_node._on_chat_cmd qui fait mic.stop()) : pas un
                # incident — ni warning ni backoff ni restart, le micro doit
                # rester coupé pendant toute la pause.
                logger.info("Écoute interrompue (mode interactif désactivé).")
                return False
            # Flux micro mort en cours d'écoute : on retente un démarrage et
            # on abandonne CE tour (pas d'exception qui remonterait jusqu'à
            # run_forever — un souci matériel ponctuel ne doit pas arrêter la
            # boucle de conversation). Le log + le backoff sont indispensables :
            # sans eux, un micro durablement indisponible devient une boucle
            # serrée INVISIBLE qui respawne arecord en continu (cf. constante
            # DEAD_MIC_BACKOFF_S — vécu au premier test réel, 2026-07-11).
            logger.warning(
                "Flux micro mort en cours d'écoute — nouvel essai dans %.1f s.",
                self._dead_mic_backoff_s)
            if self._dead_mic_backoff_s > 0:
                if self._stage is None:
                    time.sleep(self._dead_mic_backoff_s)
                else:
                    self._wait_dead_mic_backoff()
            self._mic.start()
            return False

        # Horodatage de FIN D'ÉNONCÉ (speech_end, cf. on_timing/docstring de
        # module OBSERVABILITÉ) : point de départ de `total_ms` -- la latence
        # perçue par le spectateur commence au dernier mot prononcé, pas au
        # début du tour ni à la fin du STT qui suit.
        speech_end_at = time.monotonic()

        # Anti-larsen : le micro est coupé AVANT que Didier ne parle (cf.
        # vision.audio.mic.MicCapture.stop). thinking() est publié ICI, cf.
        # décision documentée en tête de module (avant même de savoir si le
        # STT renverra du texte exploitable).
        self._mic.stop()
        self._publish_all(self._perf.thinking())
        self._set_state("thinking")

        if self._beeps_path is not None:
            # Fire-and-forget : les bips jouent PENDANT le transcribe()
            # bloquant qui suit, cf. vision.audio.playback.play_async_raw.
            self._player.play_async_raw(self._beeps_path)

        # stt_ms mesuré autour de l'appel bloquant (cf. on_timing) : c'est la
        # durée RÉELLE payée par ce tour, pas une estimation.
        stt_started_at = time.monotonic()
        try:
            with self._stt_lock:
                text = self._stt.transcribe(speech_bytes, self._mic.sample_rate)
                # Lue SOUS le verrou, juste après : une tranche de garde ne peut
                # pas l'avoir changée (seconde revue du 31/10, mineur 2).
                self._turn_stt_source = getattr(self._stt, "last_source", None)
        except Exception:
            # Une erreur STT (vécu le 22/10 : PyAV 19 incompatible avec
            # faster-whisper → TypeError à CHAQUE transcription) ne doit pas
            # tuer run_forever : sans cette garde, le thread de conversation
            # mourait et Didier restait sourd jusqu'au redémarrage du node,
            # sans rien d'autre qu'une trace dans le log. Même philosophie
            # que l'erreur LLM/TTS de _speak_reply : on abandonne CE tour,
            # le spectacle continue.
            logging.exception("Erreur STT — tour abandonné, retour à l'écoute.")
            text = None
        stt_ms = (time.monotonic() - stt_started_at) * 1000

        if not has_usable_text(text):
            # Bruit ou énoncé trop court : PAS d'appel LLM (payant), retour à
            # l'écoute. Loggé en INFO : c'est la trace qui permet de régler le
            # VAD/gain micro quand Didier « entend des voix » sur scène.
            logger.info("Tour abandonné, STT inexploitable : %r", text)
            # abandoned=True, champs AVAL (après le STT) à None : ce tour n'a
            # jamais atteint le LLM/TTS, il n'y a rien de plus à mesurer (cf.
            # docstring de module OBSERVABILITÉ).
            self._notify_timing({
                "stt_ms": stt_ms, "llm_first_ms": None, "audio_first_ms": None,
                "total_ms": None, "stt_text": text, "abandoned": True,
            })
            # Rattrapage idle() AVANT de relancer le micro (cf. docstring de
            # module, correctif 2026-07-12) : sans ça, le visage restait
            # coincé sur "reflechit" (publié par thinking() ci-dessus) pour
            # tout le reste de la pause d'écoute suivante — visible sur scène.
            self._publish_all(self._perf.idle())
            self._mic.start()
            self._set_state("listening")
            return False

        logger.info("STT : %r", text)
        return self._reply_with_stage(text, stt_ms=stt_ms, speech_end_at=speech_end_at)

    def _wait_dead_mic_backoff(self) -> None:
        """Backoff « micro mort » quand la régie est branchée : même durée
        que le time.sleep historique, mais en SONDANT la file des textes
        tapés (pas de STAGE_POLL_S) — un texte arrivé pendant l'attente
        l'écourte, il sera servi dès le tour suivant (cf. run_once)."""
        deadline = time.monotonic() + self._dead_mic_backoff_s
        while not self._stage.has_text():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(STAGE_POLL_S, remaining))

    def _serve_typed_text(self, text: str) -> bool:
        """Un texte TAPÉ (régie ou phantom) est servi comme un énoncé entendu
        dont le STT aurait déjà tourné : mêmes réactions visibles que le
        chemin micro (thinking + bips, « il y pense »), sans micro ni STT.
        mic.stop() d'abord : le micro tourne peut-être depuis la fin du tour
        précédent (anti-larsen, comme le chemin micro avant thinking)."""
        self._mic.stop()
        self._publish_all(self._perf.thinking())
        self._set_state("thinking")
        if self._beeps_path is not None:
            self._player.play_async_raw(self._beeps_path)
        logger.info("Texte tapé : %r", text)
        return self._reply_with_stage(text)

    def _serve_prompt(self, direction: str) -> bool:
        """Tour SPONTANÉ : Didier relance la scène sur une direction du
        metteur en scène, sans que personne ne lui ait parlé. Visage
        "reflechit" et état "thinking" comme un tour normal, mais SANS bips :
        il ne « calcule » pas une réponse, il a une idée. Pas de ligne
        transcript "david" (David n'a rien dit) ; pas de panne deaf/garble
        (rien n'a été entendu) — seule `mute` s'applique (la voix est en
        panne, quoi qu'il dise). Jamais de "go" (B1, cf. _notify_move)."""
        self._last_spontaneous_at = time.monotonic()
        self._mic.stop()
        self._publish_all(self._perf.thinking())
        self._set_state("thinking")
        op, _params = (self._stage.fault(time.monotonic()) if self._stage is not None
                       else ("pass", {}))
        logger.info("Tour spontané, direction : %r", direction)
        return self._speak_reply(SPONTANEOUS_USER_TEXT, direction=direction,
                                 mute=(op == "mute"), spontaneous=True)

    def _reply_with_stage(self, text: str, *, stt_ms: float = 0.0,
                          speech_end_at: Optional[float] = None) -> bool:
        """Teste l'arrêt d'urgence sur l'énoncé ENTENDU, applique la PANNE de
        régie courante au texte compris (STT ou texte tapé), publie la ligne
        "david" du transcript, puis répond. Sans `stage` : panne "pass" ->
        appel _speak_reply strictement historique. La panne est lue UNE fois
        par tour (instantané) : une échéance qui tombe en pleine réplique ne
        la coupe pas à moitié."""
        if self._stage is not None:
            # Revue adversariale du 23/10 (I7) : David vient de parler — une
            # direction de tour spontané calculée AVANT cette réplique est
            # caduque (elle répondait à une scène qui n'existe plus).
            self._stage.clear_prompt()
        # stt_text du dict on_timing = ce que le STT a VRAIMENT produit (la
        # console de diagnostic dit la vérité technique, même sous garble).
        stt_text = text
        if is_emergency_stop(stt_text):
            # Arrêt d'urgence vocal (cf. docstring de module METTEUR EN
            # SCÈNE) : AVANT tout le reste — pannes, transcript, delay, LLM.
            # Sur stt_text, PAS sur le texte compris : revue adversariale du
            # 23/10 (I3) — une panne de régie (deaf, garble) simule
            # l'INCOMPRÉHENSION de la conversation, jamais la surdité à
            # l'urgence ; « Stop ! » crié pendant une panne deaf de 60 s ne
            # partait pas. Le tour continue ensuite normalement : le LLM joue
            # l'arrêt en personnage ; s'il ajoute aussi "marche": "stop", le
            # régisseur est idempotent.
            if self._on_move is None:
                # Mouvement à la voix désactivé (vrai robot : aucun régisseur)
                # — le dire dans le log, pour qu'un essai réel ne fasse jamais
                # croire que la voix arrête quoi que ce soit (le deadman et la
                # télécommande restent les arrêts effectifs).
                logger.warning("ARRÊT D'URGENCE vocal entendu mais NON transmis "
                               "(mouvement à la voix désactivé) : %r", stt_text)
            else:
                logger.warning("ARRÊT D'URGENCE vocal : %r", stt_text)
                self._emit_move("stop")
        # Écoute garde armée DÈS ICI (revue du 31/10, I3), pas seulement au
        # début de la réplique : la panne delay (jusqu'à 9 s) et l'attente du
        # LLM sont des phases où Didier roule sans écouter. Fermée par
        # _speak_reply, par la sortie deaf ci-dessous, ou sur exception.
        guard = self._start_reply_guard()
        try:
            return self._apply_fault_and_reply(text, stt_text, stt_ms, speech_end_at, guard)
        except Exception:
            self._stop_reply_guard(guard)
            raise

    def _apply_fault_and_reply(self, text: str, stt_text: str, stt_ms: float,
                               speech_end_at: Optional[float],
                               guard: Optional[_ReplyGuard]) -> bool:
        """Suite de _reply_with_stage, écoute garde déjà armée (ou None) :
        panne de régie, ligne "david", delay, puis réplique."""
        op, params = (self._stage.fault(time.monotonic()) if self._stage is not None
                      else ("pass", {}))
        if op == "deaf":
            # Énoncé jeté, comme un STT inexploitable (même sortie : idle()
            # avant de relancer le micro, cf. correctif du 2026-07-12) —
            # aucune ligne de transcript : Didier n'a rien entendu.
            logger.info("Tour abandonné, panne deaf : %r", text)
            self._notify_timing({
                "stt_ms": stt_ms, "llm_first_ms": None, "audio_first_ms": None,
                "total_ms": None, "stt_text": stt_text, "abandoned": True,
            })
            self._publish_all(self._perf.idle())
            # Garde fermée avant de rendre le micro à l'écoute normale.
            self._stop_reply_guard(guard)
            self._mic.start()
            self._set_state("listening")
            return False
        if op == "garble":
            text = garble_text(self._stage.rng, params.get("texts"))
            logger.info("Panne garble : %r compris comme %r", stt_text, text)
        self._notify_transcript(ROLE_DAVID, text)
        if op == "delay":
            # AVANT l'appel LLM : les bips jouent déjà (fire-and-forget), le
            # visage est sur "reflechit", l'état reste "thinking" — c'est la
            # latence du Pi 5 (4 à 9 s mesurées) rejouée telle quelle.
            logger.info("Panne delay : %d ms avant le LLM", params["delay_ms"])
            if guard is None:
                time.sleep(params["delay_ms"] / 1000)
            else:
                # Un arrêt vocal ÉCOURTE l'attente : la réplique sera
                # abandonnée dès l'entrée de _speak_reply, sans appel LLM.
                guard.interrupted.wait(timeout=params["delay_ms"] / 1000)
        return self._speak_reply(text, stt_ms=stt_ms, stt_text=stt_text,
                                 speech_end_at=speech_end_at, mute=(op == "mute"))

    def _listen_for_utterance(self) -> Union[bytes, str, SpontaneousPrompt, None]:
        """Boucle micro -> VAD jusqu'à détecter la fin d'un énoncé. Retourne
        les octets PCM accumulés depuis le pré-roll, ou None si le flux
        micro est mort avant la fin de l'énoncé — ou une `str` (régie) : un
        texte tapé arrivé pendant l'écoute, qui l'INTERROMPT — ou un
        SpontaneousPrompt (metteur en scène) : une direction servie pendant
        un silence (bytes, str et SpontaneousPrompt sont des types
        disjoints : run_once les distingue par isinstance)."""
        speech_bytes = b""
        in_speech = False
        # Début d'écoute : base du silence minimal du tour spontané.
        listen_started_at = time.monotonic()

        while True:
            frame = self._mic.read_frame()
            # Texte tapé (régie) : vérifié à CHAQUE trame — c'est CE sondage
            # qui interrompt l'écoute (chat_node n'arrête pas le micro depuis
            # son thread, cf. ChatNode._on_chat_text) — et aussi quand
            # read_frame() rend None : un texte en attente passe avant le
            # diagnostic « micro mort ». L'énoncé partiel est jeté et la VAD ramenée
            # en IDLE (même raison que le blocage du gate ci-dessous : sinon
            # elle attendrait la fin d'une phrase qu'on ne lui donne plus).
            typed = self._stage.pop_text() if self._stage is not None else None
            if typed is not None:
                self._mic.stop()
                self._vad.reset()
                return typed
            if frame is None:
                return None
            # Tour spontané : APRÈS le texte tapé (la régie passe d'abord) et
            # APRÈS le test de flux mort (chat OFF coupe le micro : pas de
            # trame, donc jamais de tour spontané — la direction se périme).
            # Jamais en pleine parole (in_speech) : David a la priorité.
            # pop_prompt n'est même pas appelé avant le silence minimal : la
            # direction attend, elle n'est pas consommée pour rien.
            # Jamais non plus pendant un son de SPECTACLE (show_audio_active,
            # le signal même qu'utilise le gate) : Didier parlerait par-dessus
            # sa propre séquence (décision du 23/10, revue du lot P).
            # Ni moins de SPONTANEOUS_MIN_GAP_S après le précédent (M5) : la
            # direction n'est pas consommée, elle attend ou se périme.
            show_audio_now = (self._show_audio_active() if self._show_audio_active
                              is not None else False)
            now = time.monotonic()
            gap_ok = (self._last_spontaneous_at is None
                      or now - self._last_spontaneous_at >= SPONTANEOUS_MIN_GAP_S)
            if (self._stage is not None and not in_speech and not show_audio_now and gap_ok
                    and now - listen_started_at >= SPONTANEOUS_MIN_SILENCE_S):
                direction = self._stage.pop_prompt(time.monotonic())
                if direction is not None:
                    self._mic.stop()
                    self._vad.reset()
                    return SpontaneousPrompt(direction)

            level = self._mic.frame_rms(frame)

            # frame_peak() n'est calculé QUE si un consommateur en a
            # effectivement besoin (gate OU vumètre web, cf. on_meter,
            # docstring de module OBSERVABILITÉ) : c'est un calcul numpy
            # (np.max(np.abs(...))) à la cadence des trames (30 ms) -- inutile
            # de le payer pour rien quand ni l'un ni l'autre n'est branché
            # (comportement historique : gate=None, on_meter=None).
            peak = (self._mic.frame_peak(frame)
                    if (self._gate is not None or self._on_meter is not None) else 0.0)

            blocked = False
            if self._gate is not None:
                # Gate évalué AVANT la VAD (cf. §10.5.1 de l'étude) : la VAD
                # ne doit JAMAIS voir une trame bruyante. Sa calibration est
                # à usage unique (médiane des 1000 premières ms) -- une sono
                # vivante pendant cette fenêtre empoisonnerait le seuil pour
                # toute la vie de l'instance, rendant Didier durablement
                # sourd à un humain sans que rien ne le signale.
                show_audio = (self._show_audio_active() if self._show_audio_active
                              is not None else False)
                blocked = self._gate.feed(level, peak, show_audio)

            # Vumètre web (cf. docstring de module OBSERVABILITÉ) : notifié
            # pour CHAQUE trame lue, bloquée ou non -- c'est justement le
            # blocage par le gate que David veut voir en direct ("ma voix
            # passe-t-elle ?"). `in_speech` reflète l'état AVANT le
            # traitement de CETTE trame (une trame de speech_start n'est donc
            # pas encore "en parole" à l'instant de cette notification).
            self._notify_meter(level, peak, blocked, in_speech)

            if blocked:
                # Trame bloquée : jetée avant la VAD. Un blocage en
                # pleine phrase jette l'énoncé PARTIEL (jamais de
                # recollage d'avant/après un trou de gate, cf. §10.5.2) ;
                # le pré-roll est purgé (§10.5.3, sinon la prochaine
                # phrase légitime démarrerait avec du bruit de sono dans
                # son pré-roll) ; la VAD est ramenée en IDLE (§10.5.4,
                # sans quoi une VAD restée en SPEECH attendrait son
                # end_silence_ms sur des trames qu'elle ne reçoit plus).
                speech_bytes = b""
                in_speech = False
                self._mic.purge_preroll()
                self._vad.reset()
                continue

            event = self._vad.feed(level)

            if not in_speech:
                # Tant que la parole n'a pas VRAIMENT commencé (VAD encore en
                # CALIBRATING/IDLE), on ne fait qu'alimenter la machine à
                # états — feed() renvoie None, la boucle continue.
                if event is not None and event.kind == "speech_start":
                    in_speech = True
                    # preroll() inclut déjà cette trame de déclenchement
                    # comme entrée la plus récente du ring buffer (cf.
                    # vision.audio.mic.MicCapture.read_frame/preroll) : pas
                    # besoin de la rajouter une seconde fois ici.
                    speech_bytes = self._mic.preroll()
                continue

            speech_bytes += frame
            if event is not None and event.kind == "speech_end":
                return speech_bytes

    def _speak_reply(self, text: str, *, stt_ms: float = 0.0, stt_text: str = "",
                      speech_end_at: Optional[float] = None, mute: bool = False,
                      direction: Optional[str] = None, spontaneous: bool = False) -> bool:
        """Génère et joue la réponse du LLM pour `text` déjà transcrit ;
        retourne True si le tour est allé jusqu'au bout, False sur erreur
        LLM/TTS (log + retour à l'écoute, le spectacle continue).

        `stt_ms`/`stt_text`/`speech_end_at` (cf. run_once, docstring de
        module OBSERVABILITÉ) : mesures du tour DÉJÀ prises en amont,
        transmises telles quelles pour composer le dict `on_timing` en fin de
        méthode — cette méthode n'a besoin de mesurer QUE ce qui se passe à
        partir d'ici (latence LLM, latence premier son).

        `mute` : panne de régie, transmise à _handle_event (cf. son docstring).

        `direction` : direction de jeu d'un tour spontané (cf. _serve_prompt),
        transmise au brain avec le tableau de situation — ignorée sans `stage`.

        `spontaneous` : tour spontané (cf. _serve_prompt) — la clé "marche"
        n'y transmet que "stop" (B1, cf. _notify_move)."""
        parser = StreamPerformanceParser()
        emotion_params = None
        # Horodatage de départ pour llm_first_ms/audio_first_ms (relatifs au
        # début de CETTE méthode, cf. docstring de module OBSERVABILITÉ) ;
        # timing_marks : dict mutable rempli par _handle_event, jamais réécrit
        # une fois un jalon posé (seul le PREMIER Sentence/son de la réponse
        # compte pour la latence perçue).
        reply_started_at = time.monotonic()
        timing_marks = {"first_sentence_at": None, "first_play_at": None}
        # Écoute garde (cf. docstring de module ÉCOUTE GARDE) : déjà armée par
        # _reply_with_stage (I3), sinon démarrée ici (tour spontané), AVANT
        # l'appel LLM. None = inactive (vrai robot) : micro coupé comme avant.
        guard = self._guard if self._guard is not None else self._start_reply_guard()
        if guard is not None and guard.interrupted.is_set():
            # « Stop ! » entendu pendant la panne delay / avant la réplique :
            # Didier se tait, AUCUN appel LLM.
            return self._finish_interrupted_reply(
                guard, stt_ms, stt_text, timing_marks, reply_started_at, speech_end_at)

        try:
            if self._stage is None:
                deltas = self._brain.stream_reply(text)
            else:
                # Consigne de jeu courante et tableau de situation (None si
                # absents, levés ou périmés, cf. StageState) relus à CHAQUE
                # tour, sur le MÊME instant.
                now = time.monotonic()
                deltas = self._brain.stream_reply(
                    text, extra_system=self._stage.instruction(now),
                    situation=self._stage.situation(now), direction=direction)
            # Urgence vérifiée avant CHAQUE événement : le thread de
            # conversation ne peut pas être interrompu en plein appel bloquant
            # (attente du delta LLM suivant, synthèse TTS) — il s'arrête au
            # premier point de contrôle qui suit (latence, cf. limites).
            for delta in deltas:
                for event in parser.feed(delta):
                    if self._reply_interrupted():
                        break
                    emotion_params = self._handle_event(
                        event, emotion_params, timing_marks, mute, spontaneous)
                if self._reply_interrupted():
                    break
            if self._reply_interrupted():
                self._close_stream(deltas)
            else:
                for event in parser.flush():
                    if self._reply_interrupted():
                        break
                    emotion_params = self._handle_event(
                        event, emotion_params, timing_marks, mute, spontaneous)
        except Exception:
            # Le spectacle continue : une panne LLM/TTS ponctuelle ne doit
            # jamais arrêter la conversation, seulement ce tour-ci.
            logging.exception(
                "Erreur pendant la génération/synthèse de la réponse — tour abandonné.")
            if guard is not None and guard.interrupted.is_set():
                # Panne APRÈS un arrêt vocal (revue du 31/10, m3) : même sortie
                # que l'interruption — interrupt() rejoué (un play() a pu
                # partir pendant la course), garde fermée, micro rendu.
                return self._finish_interrupted_reply(
                    guard, stt_ms, stt_text, timing_marks, reply_started_at, speech_end_at)
            self._publish_all(self._perf.speaking_stop())
            # Rattrapage visage (2026-09-13, "la bouche n'est pas raccord avec
            # la parole" -- David ; cf. DÉCISION/CORRECTIF en tête de module) :
            # speaking_stop() coupe la SÉQUENCE de servos (topic animation)
            # mais ne publie RIEN sur le topic face -- or l'expression "parle"
            # (json/expressions.json, dadou_robot_ros) a loop:true, Face la
            # rejoue donc indéfiniment tant qu'aucun AUTRE message face
            # n'arrive. Sur ce chemin d'erreur, emotion_params ne reflète
            # JAMAIS un état de fin fiable (la panne a coupé la génération
            # avant tout JSON d'émotion, ou en plein milieu) : idle()
            # INCONDITIONNEL ici, contrairement au chemin nominal ci-dessous
            # qui peut se permettre de retenir une émotion réellement conclue.
            self._publish_all(self._perf.idle())
            # Garde fermée AVANT de rendre le micro à l'écoute normale (jeton
            # périmé + lecteur arrêté : un seul lecteur du micro à la fois).
            self._stop_reply_guard(guard)
            if self._gate is not None:
                # Queue acoustique (C2) même sur ABANDON : le player peut
                # encore être en train de jouer ce qui était déjà enfilé
                # (aucun drain() sur ce chemin, cf. commentaire du test
                # test_erreur_llm_publie_quand_meme_speaking_stop) — la
                # réverbération/le tampon ALSA de CE résidu ne doit pas être
                # réécoutée dès la reprise du micro (§10.5, arm_tail avant
                # _mic.start() dans les DEUX sorties de _speak_reply).
                self._gate.arm_tail()
            self._mic.start()
            self._set_state("listening")
            # abandoned=True comme le cas STT inexploitable de run_once (même
            # sémantique : ce tour n'a pas produit de réponse) -- les jalons
            # aval restent None si la panne a eu lieu AVANT toute Sentence/
            # lecture (cas le plus courant, ex. erreur réseau LLM), mais
            # reflètent une valeur RÉELLE si la panne a frappé après coup
            # (ex. TTS en échec sur la 2e phrase, la 1re a bien été jouée) --
            # timing_marks porte déjà cette nuance, pas besoin de la
            # dupliquer ici.
            self._notify_timing(self._build_timing(
                stt_ms, stt_text, timing_marks, reply_started_at, speech_end_at, abandoned=True))
            return False

        if guard is not None and guard.interrupted.is_set():
            return self._finish_interrupted_reply(
                guard, stt_ms, stt_text, timing_marks, reply_started_at, speech_end_at)

        self._player.drain()
        # Garde fermée APRÈS le drain (la réplique entière est surveillée) et
        # AVANT le reste : un « Stop ! » de fin de réplique transcrit à partir
        # d'ici émet ENCORE l'ordre stop (B1, sens sûr) mais n'interrompt plus
        # rien — la réplique est finie.
        self._stop_reply_guard(guard)
        if guard is not None and guard.interrupted.is_set():
            # Urgence tombée PENDANT le drain (dernière phrase en cours) : même
            # sortie que ci-dessus (garde déjà fermée, fermeture idempotente).
            return self._finish_interrupted_reply(
                guard, stt_ms, stt_text, timing_marks, reply_started_at, speech_end_at)
        self._publish_all(self._perf.speaking_stop())
        # Rattrapage visage (2026-09-13, cf. DÉCISION/CORRECTIF en tête de
        # module pour le mécanisme complet) : self._perf.emotion(...) renvoie
        # une liste VIDE dès que le LLM n'a pas émis de JSON d'émotion final
        # (cas courant) ou une clé d'émotion inconnue du mapping -- dans ce
        # cas AUCUN message ne part sur le topic face, et l'expression "parle"
        # (loop:true côté robot) continue de s'agiter pendant toute l'écoute
        # suivante, speaking_stop() n'ayant coupé QUE la séquence de servos.
        # MÊME trou que celui corrigé le 2026-07-12 sur le chemin "STT
        # inexploitable" (rattrapage idle() avant de relancer le micro),
        # jamais porté jusqu'ici sur le chemin NOMINAL : on garantit
        # désormais qu'AU MOINS un message face part à la fin de CHAQUE
        # réplique -- l'émotion si le LLM en a conclu une exploitable, idle()
        # sinon (jamais les deux : une émotion fraîchement choisie ne doit pas
        # être écrasée par un neutre superflu).
        emotion_messages = self._perf.emotion(emotion_params)
        self._publish_all(emotion_messages if emotion_messages else self._perf.idle())
        if self._gate is not None:
            # Queue acoustique (C2) après un drain() réussi : cf. commentaire
            # ci-dessus, même raison, chemin nominal.
            self._gate.arm_tail()
        self._mic.start()
        self._set_state("listening")
        self._notify_timing(self._build_timing(
            stt_ms, stt_text, timing_marks, reply_started_at, speech_end_at, abandoned=False))
        return True

    def _reply_interrupted(self) -> bool:
        """Vrai si la réplique en cours a été interrompue par un arrêt vocal
        (cf. _ReplyGuard) — point de contrôle du thread de conversation."""
        guard = self._guard
        return guard is not None and guard.interrupted.is_set()

    def _start_reply_guard(self) -> Optional[_ReplyGuard]:
        """Démarre l'écoute garde de CETTE réplique, ou None si elle est
        inactive (pas de `on_move` ou pas de `guard_vad` : vrai robot, micro
        coupé comme avant). Le micro, coupé par l'appelant (anti-larsen),
        est rouvert ici. Tout échec = réplique SANS écoute garde, micro coupé
        (comportement historique), jamais une réplique perdue.
        Jamais armée chat OFF (revue du 31/10, I4) : le micro doit RESTER
        coupé pendant toute la pause (cf. run_forever)."""
        if self._on_move is None or self._guard_vad is None:
            return None
        if not self._chat_enabled():
            return None
        try:
            # Seuil de l'écoute normale (calibré sur le silence ambiant, cf.
            # EnergyVad.adopt_threshold) ; getattr : une VAD sans `threshold`
            # exposé (ou pas encore calibrée -> None) laisse la VAD de garde
            # sur son propre état. reset() : repart en IDLE (une réplique
            # précédente a pu la laisser en SPEECH).
            threshold = getattr(self._vad, "threshold", None)
            if threshold is None:
                # Écoute normale pas encore calibrée (1er tour tapé ou
                # spontané) : plancher prudent plutôt qu'une calibration sur
                # la voix de Didier (seconde revue du 31/10, mineur 4).
                threshold = getattr(self._guard_vad, "floor_threshold", None)
                if threshold is not None:
                    logger.info("Écoute garde : écoute normale non calibrée — seuil "
                                "plancher %.2f.", threshold)
            self._guard_vad.adopt_threshold(threshold)
            self._guard_vad.reset()
            guard = _ReplyGuard(mic=self._mic, vad=self._guard_vad, stt=self._stt,
                                stt_lock=self._stt_lock,
                                emit_stop=lambda: self._emit_move("stop"),
                                interrupt_audio=self._player.interrupt,
                                should_listen=self._chat_enabled)
            self._mic.start()
            guard.start()
        except Exception:
            logger.exception("Écoute garde impossible à démarrer — réplique SANS arrêt "
                             "vocal (micro coupé comme avant).")
            try:
                self._mic.stop()
            except Exception:
                logger.exception("Écoute garde : micro impossible à recouper.")
            return None
        self._guard = guard
        return guard

    def _chat_enabled(self) -> bool:
        """Mode interactif actif ? (`_enabled` None = hors run_forever, ex.
        tests de run_once : actif.) Lu depuis le thread lecteur de la garde."""
        return self._enabled is None or self._enabled.is_set()

    def _stop_reply_guard(self, guard: Optional[_ReplyGuard]) -> None:
        """Ferme l'écoute garde (idempotent, None = rien) : jeton fermé
        D'ABORD (plus d'interruption possible ; un mot d'arrêt des tranches
        déjà captées émet encore l'ordre, cf. _ReplyGuard B1), puis mic.stop() — qui débloque le
        lecteur (EOF d'arecord) ET rend le micro dans l'état historique de fin
        de réplique (coupé, l'appelant le relance) — puis attente bornée du
        lecteur, et purge du pré-roll (une trame lue par le lecteur pendant
        l'arrêt a pu y entrer après la purge de stop() : la voix de Didier ne
        doit jamais ouvrir le prochain énoncé). Jamais d'exception."""
        if guard is None or self._guard is not guard:
            return
        self._guard = None
        self._closed_guard = guard
        guard.close()
        try:
            self._mic.stop()
        except Exception:
            logger.exception("Écoute garde : arrêt du micro en échec.")
        if not guard.join_reader(GUARD_JOIN_TIMEOUT_S):
            logger.warning("Écoute garde : lecteur micro toujours actif après %.1f s "
                           "(thread fuyant).", GUARD_JOIN_TIMEOUT_S)
        try:
            self._mic.purge_preroll()
        except Exception:
            logger.exception("Écoute garde : purge du pré-roll en échec.")

    def _finish_interrupted_reply(self, guard: _ReplyGuard, stt_ms: float, stt_text: str,
                                  timing_marks: dict, reply_started_at: float,
                                  speech_end_at: Optional[float]) -> bool:
        """Sortie d'une réplique interrompue par un arrêt vocal (l'ordre
        "stop" est DÉJÀ parti, cf. _ReplyGuard._handle_text). Didier se tait :
        son coupé (interrupt() rejoué : un play() a pu être enfilé pendant la
        course), bouche arrêtée, visage NEUTRE (l'émotion de fin n'a pas été
        conclue), ligne "david" de ce qui a été entendu — comme le chemin
        normal —, PAS d'appel LLM (il ne joue pas l'arrêt ici), micro rendu.
        Retourne False : le tour n'est pas allé au bout (abandoned=True)."""
        try:
            self._player.interrupt()
        except Exception:
            logger.exception("Écoute garde : coupure du son en échec.")
        self._player.drain()
        self._stop_reply_guard(guard)
        self._publish_all(self._perf.speaking_stop())
        self._publish_all(self._perf.idle())
        self._notify_transcript(ROLE_DAVID, guard.heard)
        if self._gate is not None:
            # Queue acoustique (C2), comme les deux autres sorties.
            self._gate.arm_tail()
        self._mic.start()
        self._set_state("listening")
        self._notify_timing(self._build_timing(
            stt_ms, stt_text, timing_marks, reply_started_at, speech_end_at, abandoned=True))
        return False

    @staticmethod
    def _close_stream(deltas) -> None:
        """Abandonne le flux LLM (générateur) : close() libère la connexion
        HTTP sans attendre la fin de la génération. Best-effort."""
        close = getattr(deltas, "close", None)
        if close is None:
            return
        try:
            close()
        except Exception:
            logger.debug("Fermeture du flux LLM en échec (ignorée).", exc_info=True)

    @staticmethod
    def _build_timing(stt_ms: float, stt_text: str, timing_marks: dict,
                       reply_started_at: float, speech_end_at: Optional[float],
                       *, abandoned: bool) -> dict:
        """Assemble le dict `on_timing` (cf. docstring de constructeur) à
        partir des horodatages relevés pendant CE tour. Un jalon jamais
        atteint (Sentence/lecture jamais produites, ex. panne LLM avant tout
        texte) reste None plutôt qu'une durée fantaisiste -- la console de
        diagnostic doit pouvoir distinguer "pas encore mesuré" de "zéro
        seconde". `speech_end_at` peut être None (défaut du paramètre,
        n'arrive jamais en pratique via run_once, mais garde cette méthode
        appelable isolément dans les tests sans fournir cette valeur)."""
        def ms_since(started_at, mark_at):
            if mark_at is None or started_at is None:
                return None
            return (mark_at - started_at) * 1000

        return {
            "stt_ms": stt_ms,
            "llm_first_ms": ms_since(reply_started_at, timing_marks["first_sentence_at"]),
            "audio_first_ms": ms_since(reply_started_at, timing_marks["first_play_at"]),
            "total_ms": ms_since(speech_end_at, timing_marks["first_play_at"]),
            "stt_text": stt_text,
            "abandoned": abandoned,
        }

    def run_forever(self, stop_event: threading.Event,
                    enabled: Optional[threading.Event] = None) -> None:
        """Enchaîne les tours jusqu'à stop_event.set() (typiquement déclenché
        par le node ROS appelant à l'arrêt, cf. chat_node V2). Pas de thread
        créé ici, cf. docstring de module.

        `enabled` (optionnel) : interrupteur de MODE INTERACTIF piloté par
        l'appelant (topic `chat` "on"/"off" côté node). Quand il est baissé,
        aucun tour ne démarre — la boucle attend par petits pas (wait borné,
        PAS un wait() infini : il faut re-vérifier stop_event régulièrement
        pour que l'arrêt du node reste réactif même en pause). La bascule OFF
        en PLEIN tour ne coupe pas la réplique en cours (choix scénique :
        Didier finit sa phrase) — c'est le mic.stop() fait par l'appelant qui
        interrompt une ÉCOUTE en cours, cf. chat_node._on_chat_cmd."""
        self._enabled = enabled
        while not stop_event.is_set():
            if enabled is not None and not enabled.is_set():
                # mic.stop() idempotent À CHAQUE passage : certains chemins de
                # fin de tour redémarrent le micro (fin de réplique, STT
                # inexploitable) AVANT que la boucle ne voie le toggle baissé
                # — on garantit ici qu'en pause, le micro est TOUJOURS coupé,
                # quel que soit le chemin qui a rendu la main.
                self._mic.stop()
                # "off" : dédup absorbe la boucle d'attente (ré-émis à chaque
                # itération de 0,2 s tant que la pause dure) -- un seul
                # message part réellement vers on_state par pause.
                self._set_state("off")
                enabled.wait(timeout=0.2)
                continue
            self.run_once()
