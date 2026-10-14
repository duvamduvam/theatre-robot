#!/usr/bin/env python3
"""Node 'chat' : micro -> écoute -> LLM streamé -> voix + expressions (V2).

QUOI : node FIN (I/O + câblage ROS seulement) — construit les vraies briques
       V1-V6 (mic/vad/stt/brain/tts/player/bips) et les injecte dans
       vision.ai.conversation.ConversationEngine, qui porte TOUTE la logique
       d'un tour de conversation (déjà testée sans ROS, cf.
       vision/tests/unit/test_conversation.py). Même pattern que
       vision/nodes/person_tracker_node.py : classe d'erreur de démarrage
       dédiée (ChatStartupError -> SystemExit(1) sans crash-loop), paramètres
       ROS déclarés avec défauts (ici lus depuis vision_config.config via
       vision.nodes._chat_wiring.default_chat_parameters, pas dupliqués en
       dur), piège logger rclpy documenté ci-dessous.
POURQUOI ConversationEngine.run_forever tourne dans un THREAD dédié plutôt
       que d'être appelé depuis un timer rclpy : run_once() est bloquant de
       bout en bout (lecture micro frame par frame, transcription STT,
       streaming LLM) — l'exécuter depuis un callback timer gèlerait le
       spinner rclpy (plus aucun autre callback/topic traité pendant tout un
       tour de parole). Le thread est démon (cf. AudioPlayer, même pattern
       déjà en place dans vision.audio.playback) : il ne doit jamais empêcher
       l'arrêt du process si stop_event n'était pas honoré à temps, mais
       destroy_node() reste la voie normale d'arrêt propre (stop_event.set()
       + mic.stop() pour débloquer un read_frame() en cours + join borné).
POURQUOI publish() ne connaît QUE le topic/payload/durée (RosMessage, cf.
       vision.ai.performance) et jamais la logique métier : ce node réutilise
       les topics FACE/ANIMATION EXISTANTS du robot (zéro nouveau topic, cf.
       ARCHITECTURE.md "V2 : émotions et parole via les topics EXISTANTS du
       robot — zéro modif côté robot") — un publisher StringTime par topic,
       choisi par message.topic au moment de publier.
POURQUOI le gate `vision.ai.arbitration` (ajouté 2026-07-12, étude
       d'arbitrage des actionneurs côté robot,
       dadou_robot_ros/docs/etude-arbitrage-actionneurs.md §3/§5/§6) : sans
       lui, le chat écrase le visage d'une séquence de spectacle en cours au
       moindre bruit de salle (S1), et peut la TUER via son stop d'animation
       — speaking_stop() publie animation=False, qui déclenche un arrêt
       GLOBAL côté animations_node, pas seulement l'arrêt de "parle" (S2).
       Le node s'abonne donc en plus à ANIMATION_STATE (StringTime latché,
       publié par animations_node : nom de la séquence en cours, "" au
       repos) et retient le dernier état vu ; _publish() consulte
       arbitration.allow_message() avant chaque publication et retient un
       message si une séquence de spectacle a la main.
POURQUOI CHAT_STATE_TOPIC est un nouveau topic (seule exception au "zéro
       nouveau topic" ci-dessus, lot D0 outillage du chantier "conversation en
       déambulation", dadou_robot_ros/docs/etude-declenchement-conversation.md
       §6.1/§6.2/§7) : c'est de l'ÉTAT (ce que le chat observe de lui-même),
       pas une commande d'actionneur -- rien à quoi le vocabulaire
       FACE/ANIMATION du robot puisse correspondre. Publié en QoS TRANSIENT_
       LOCAL (même piège documenté qu'ANIMATION_STATE plus bas) et SANS passer
       par l'arbitrage (_publish_state, à la différence de _publish) : un état
       n'entre jamais en conflit avec une séquence de spectacle.
POURQUOI le gate `vision.audio.live_audio_gate` (lot du 2026-08-30, gate
       « source audio vivante », dadou_robot_ros/docs/
       etude-declenchement-conversation.md §10) : le node construit le gate
       depuis la config (source unique de vérité, cf. vision_config.py) et
       lui fournit `show_audio_active` -- un CALLABLE, PAS un bool figé, qui
       RÉUTILISE arbitration.effective_state déjà câblé pour l'arbitrage
       amont (ne pas le dupliquer : c'est lui qui porte la péremption
       deadman évitant de rester sourd pour toujours si animations_node
       meurt). La DÉCISION elle-même est déléguée à
       arbitration.show_audio_live, qui porte ses deux exclusions et leur
       pourquoi -- "parle" (l'animation du chat lui-même : blocage
       circulaire) et None (topic jamais reçu : surdité définitive et
       silencieuse). Ces règles ne sont écrites qu'à cet endroit-là.
POURQUOI `diag_port` (lot du 2026-09-13, demande de David en séance -- « un
       indicateur pour voir si ma voix passe », « la conversation n'est pas
       fluide du tout ») : serveur de diagnostic web (vumètre temps réel +
       latences par tour), OFF par défaut (0) -- AUCUN thread/socket créé, ni
       aucun coût ajouté aux callbacks `on_meter`/`on_timing` de
       ConversationEngine tant qu'il n'est pas explicitement demandé (cf.
       clause de réversibilité de vision.ai.conversation). PIÈGE DEUX (en fait
       TROIS) BOUCLES D'ÉVÉNEMENTS : ce node a DÉJÀ rclpy.spin (thread
       principal, cf. main()) ET le thread dédié de run_forever ci-dessus --
       aiohttp a besoin de SA PROPRE boucle asyncio, qui ne peut vivre dans
       AUCUN des deux (bloquants tous les deux, incompatibles avec asyncio).
       `DiagServer` le lance donc dans un TROISIÈME thread daemon, avec
       `asyncio.new_event_loop()` + `AppRunner`/`TCPSite` (PAS `web.run_app` :
       il tente d'installer des handlers de signal, qui ne fonctionnent QUE
       dans le thread principal -- ça planterait ici). Même motif que
       dadou_robot_ros/conf/ros2_dependencies/robot_web/robot_web/
       web_bridge_node.py et robot/nodes/face_sim_node.py, à ceci près que
       CES DEUX nodes-là hébergent aiohttp dans leur thread PRINCIPAL (rclpy.
       spin y est le thread secondaire) -- chat_node ne peut pas faire pareil,
       son thread principal est déjà pris par rclpy.spin (cf. main()).
       `_DiagState` (état partagé) est écrit par le thread de conversation
       (callbacks on_meter/on_timing/on_state, cadence des trames) et lu par
       le thread aiohttp (rendu SSE, ~10 Hz) : protégé par un threading.Lock
       (PAS asyncio.Lock, mêmes raisons que web_bridge_node.py) ; AUCUN I/O ni
       encodage JSON dans les callbacks eux-mêmes (juste un rangement de
       valeurs), l'encodage se fait côté HTTP, à la cadence d'affichage.
POURQUOI les topics de RÉGIE (lot R3 « Chantiers », 2026-10-14, spec fermée
       dadou_robot_ros/docs/etude-repetition-simulee.md §13.6) : CHAT_TEXT,
       CHAT_INSTRUCTION et CHAT_FAULT sont décodés ici (vision.ai.stage, pur)
       et rangés dans un StageState partagé avec ConversationEngine -- ÉCRIT
       par les callbacks (thread rclpy.spin), LU par le thread de
       conversation : StageState porte son propre verrou (cf. sa docstring,
       pourquoi l'argument « affectation atomique sous le GIL » d'
       _animation_state ne suffit pas là). CHAT_TRANSCRIPT est publié depuis
       le thread de conversation (callback on_transcript), comme _publish.
"""
import asyncio
import json
import logging
import os
import threading
import time

import rclpy
from aiohttp import web
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from robot_interfaces.msg import StringTime

from dadou_utils_ros.utils_static import ANIMATION, ANIMATION_STATE, FACE

from vision.ai import arbitration, personas, stage
from vision.ai.conversation import ConversationEngine
from vision.ai.llm_stream import StreamingBrain
from vision.ai.performance import RosMessage
from vision.ai.stt import FasterWhisperStt
from vision.ai.tts_piper import PiperTts
from vision.audio.beeps import build_thinking_beeps
from vision.audio.live_audio_gate import LiveAudioGate, LiveAudioGateConfig
from vision.audio.mic import MicCapture
from vision.audio.playback import AudioPlayer
from vision.audio.vad import EnergyVad
from vision.nodes._chat_wiring import (decode_persona_command, default_chat_parameters,
                                       ros_message_to_string_time_kwargs)
from vision.vision_config import config, get_secret

# Durée d'une trame micro (ms) : DOIT être identique côté MicCapture (qui
# découpe le flux arecord en trames de cette taille) et côté EnergyVad (qui
# compte le temps écoulé en additionnant frame_ms à chaque feed()) — un écart
# entre les deux désynchroniserait toute la temporisation du VAD
# (calibration_ms, end_silence_ms...) sans qu'aucune erreur ne soit levée
# (juste un VAD qui déclenche trop tôt/tard). 30 ms = valeur du proto validé
# le 10/07 (cf. CLAUDE.md), reprise telle quelle (pas de paramètre ROS dédié :
# aucune raison scénique d'y toucher, contrairement à refresh_ms/beep_seconds).
MIC_FRAME_MS = 30

# Fréquence d'échantillonnage du flux micro (Hz) : idem, valeur du proto
# validé, pas exposée en paramètre ROS (faster-whisper/l'EnergyVad n'ont pas
# de contrainte particulière à ce sujet, 16 kHz suffit largement pour de la
# voix humaine).
MIC_SAMPLE_RATE = 16000

# Fréquence d'échantillonnage des bips de réflexion (vision.audio.beeps) :
# DOIT être la même valeur passée à build_thinking_beeps() ET à
# ConversationEngine(beeps_rate=...) — c'est ce taux qui permet à
# AudioPlayer.play_async_raw() de jouer le wav écrit par
# write_wav_tempfile(beeps_pcm, beeps_rate) sans le déformer.
BEEPS_SAMPLE_RATE = 22050

# Nom de la clé de secret OpenRouter (vision.vision_config.get_secret) :
# vérifié explicitement AU DÉMARRAGE (cf. __init__) même si StreamingBrain ne
# le lit que paresseusement au premier appel réel — mieux vaut un échec de
# démarrage clair (conf/secret manquant) qu'un plantage silencieux du premier
# tour de conversation en pleine scène.
LLM_API_KEY_NAME = "openrouter_key"

# Délai (s) laissé au thread de conversation pour honorer stop_event avant de
# continuer l'arrêt du node : run_once() peut être bloqué en plein STT/TTS au
# moment du SIGINT — ce n'est qu'une borne de politesse (le thread est démon,
# cf. docstring de module), pas une garantie d'arrêt immédiat.
SHUTDOWN_JOIN_TIMEOUT_S = 5.0

# Topic d'activation du mode interactif ("on"/"off") — même contrat que le
# topic `gaze` de gaze_follower côté robot (dadou_robot_ros) : StringTime,
# valeur json ou brute tolérée. Permet à la régie de couper/relancer la
# conversation EN COURS DE SPECTACLE sans tuer le node (le modèle whisper et
# la voix Piper restent chargés — la reprise est instantanée).
CHAT_CMD_TOPIC = "chat"

# Topic de changement de personnalité à chaud (lot D3, atelier persona du
# 2026-07-13 — cf. vision.ai.personas et dadou_robot_ros/docs/
# etude-declenchement-conversation.md §5.4) : payload = nom de variante
# ("bougon"/"naif"/"vantard"/"mauvaisefoi"), même souplesse de décodage que le toggle
# `chat` (JSON ou brut, cf. _chat_wiring.decode_persona_command). Consommé
# depuis la console web (whitelist technique) et, à terme, la télécommande.
PERSONA_TOPIC = "persona"

# Topic d'état de la personnalité ACTIVE (2026-07-13, surbrillance console) :
# latché comme chat_state, publie le nom réellement en vigueur (y compris le
# défaut au démarrage) — la console surligne depuis CET état, pas depuis le
# dernier clic (un clic refusé/dédupliqué ne doit pas s'afficher actif).
PERSONA_STATE_TOPIC = "persona_state"

# Topic d'état du chat (lot D0 outillage, cf. dadou_robot_ros/docs/
# etude-declenchement-conversation.md §6.1/§6.2) — expose listening/thinking/
# speaking/off pour la régie, le télédiagnostic et le futur engagement_node
# (qui doit savoir si le chat écoute encore pour tenir IN_CONVERSATION).
# Locale ici, PAS dans dadou_utils_ros : même choix que CHAT_CMD_TOPIC
# ci-dessus (ce topic n'a de sens que côté chat, aucune raison de le
# mutualiser dans la lib partagée).
CHAT_STATE_TOPIC = "chat_state"

# --- Topics de RÉGIE du chat (lot R3, cf. docstring de module) -------------
# Texte « entendu » SANS micro ni STT (clavier de la régie, page « scène » du
# pont web) : prod-générique -- sur un vrai spectacle, la régie peut souffler
# une réplique à Didier quand le micro ne passe plus (bruit, panne). Payload
# JSON string ou brut ; coupe une écoute en cours (sondage du moteur, cf. _on_chat_text).
CHAT_TEXT_TOPIC = "chat_text"

# Consigne de jeu courante (texte ; "" = levée), injectée comme second message
# system à chaque tour : prod-générique aussi -- la régie peut diriger
# Didier en direct (« tu boudes », « tu es pressé »). Péremption locale
# 120 s (vision.ai.stage.INSTRUCTION_TTL_S) si la levée se perd.
CHAT_INSTRUCTION_TOPIC = "chat_instruction"

# Panne de conversation injectée par le régisseur de la répétition simulée
# (robot_rehearsal, dadou_robot_ros) : le nom `rehearsal/…` EST le contrat de
# ce régisseur (§13.4 point 3, mêmes chaînes gravées dans les tests des deux
# dépôts). Consommé aussi en prod, SANS effet tant que personne ne publie --
# le régisseur ne tourne qu'en domaine 43 (sim) et n'entre jamais dans le
# bringup. Plafond local 60 s (vision.ai.stage.FAULT_MAX_S).
CHAT_FAULT_TOPIC = "rehearsal/chat_fault"

# La conversation telle qu'elle a eu lieu, ligne par ligne : JSON {"role":
# "david"|"didier", "text", "t_ms"} (vision.ai.stage.encode_transcript).
# Jamais les consignes ni les pannes (David ignore le tirage, §13.1). Pas
# latché : c'est un FLUX (la page l'affiche au fil de l'eau), pas un état.
CHAT_TRANSCRIPT_TOPIC = "chat_transcript"


# --- Serveur de diagnostic web (vumètre + latences, cf. docstring de module
# POURQUOI `diag_port`) -----------------------------------------------------

# Cadence du flux SSE /events (cf. spec du lot -- "~10 Hz") : largement
# suffisant pour l'œil humain sur un vumètre, pas besoin de coller à la
# cadence des trames (30 ms, cf. _DiagState.on_meter) qui, elle, reste interne.
DIAG_EVENTS_PERIOD_S = 0.1


class _DiagState:
    """État partagé du serveur de diagnostic. ÉCRIT par le thread de
    conversation (callbacks on_meter/on_timing/on_state, cadence des trames
    pour le premier) et LU par le thread aiohttp (rendu SSE, cf.
    DIAG_EVENTS_PERIOD_S) -- protégé par un threading.Lock, PAS un
    asyncio.Lock (cf. docstring de module PIÈGE DEUX BOUCLES : les
    producteurs ne sont pas dans la boucle asyncio). Aucun I/O ni encodage
    JSON dans les callbacks eux-mêmes (cf. spec du lot) : juste un rangement
    de valeurs, l'encodage se fait dans `snapshot` côté handler HTTP."""

    def __init__(self, vad: EnergyVad, gate_config: LiveAudioGateConfig):
        self._lock = threading.Lock()
        # Références VIVANTES vers les objets réellement construits par
        # ChatNode (cf. spec : "JAMAIS des constantes recopiées") -- lues à
        # chaque snapshot, pas figées ici : vad.threshold passe de None à une
        # valeur ~1 s après le démarrage (fin de calibration), la page doit
        # refléter ce changement sans redémarrer le node.
        self._vad = vad
        self._gate_config = gate_config
        # Dernière trame vue (mise à jour à la cadence des trames, ~30 ms) :
        # valeurs neutres tant qu'aucune trame n'est encore passée.
        self._level = 0.0
        self._peak = 0.0
        self._blocked = False
        self._in_speech = False
        # État courant (listening/thinking/speaking/off), alimenté par un
        # callback CÂBLÉ EN PLUS de ChatNode._publish_state (cf. son
        # commentaire) -- "listening" en dur : le mode interactif démarre
        # toujours activé (même valeur que initial_state du moteur).
        self._chat_state = "listening"
        # Dernier tour TERMINÉ (dict on_timing, cf. vision.ai.conversation) :
        # None tant qu'aucun tour n'a encore atteint le STT.
        self._timing = None

    def on_meter(self, level: float, peak: float, blocked: bool, in_speech: bool) -> None:
        """Callback `on_meter` de ConversationEngine (cadence des trames,
        30 ms) : DOIT rester le moins coûteux possible (cf. spec) -- pas de
        json.dumps ici, juste un rangement sous verrou."""
        with self._lock:
            self._level = level
            self._peak = peak
            self._blocked = blocked
            self._in_speech = in_speech

    def on_timing(self, timing: dict) -> None:
        """Callback `on_timing` de ConversationEngine (une fois par tour)."""
        with self._lock:
            self._timing = timing

    def on_state(self, state: str) -> None:
        """Câblé EN PLUS de ChatNode._publish_state (pas un remplacement) :
        ne publie rien sur ROS, alimente seulement la page de diagnostic."""
        with self._lock:
            self._chat_state = state

    def snapshot(self) -> dict:
        """Copie protégée de l'état courant, ENRICHIE des seuils EFFECTIFS
        lus en direct sur les objets réellement construits (cf. docstring de
        classe) -- `vad_threshold` reste None tant que la calibration
        initiale (~1 s) n'est pas terminée, la page l'affiche tel quel."""
        with self._lock:
            return {
                "level": self._level,
                "peak": self._peak,
                "blocked": self._blocked,
                "in_speech": self._in_speech,
                "chat_state": self._chat_state,
                "timing": self._timing,
                "vad_threshold": self._vad.threshold,
                "gate_loud_rms": self._gate_config.loud_rms,
                "gate_clip_peak": self._gate_config.clip_peak,
            }


# Page HTML AUTONOME (pas de CDN -- même contrainte que le reste du parc, cf.
# robot_web/static et face_sim_node._INDEX_HTML : le robot n'a pas toujours de
# réseau). Vumètre en échelle LOGARITHMIQUE (dBFS) : un vumètre linéaire en
# unités int16 est illisible, la parole vit tout en bas de l'échelle -- cf.
# spec du lot. FLOOR_DB (JS) : tout ce qui est plus bas est écrasé à 0% de
# barre (le silence absolu n'a pas besoin de résolution visuelle).
_DIAG_INDEX_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Didier — diagnostic conversation</title>
<style>
  body { background:#111; color:#ddd; font-family: sans-serif; margin: 2em; }
  h1 { font-size: 1.3em; color:#fff; }
  .bloc { margin-bottom: 2em; }
  .meter-wrap { position: relative; height: 32px; background:#222;
                border: 1px solid #444; margin-top: 1.5em; }
  .meter-bar { position: absolute; top:0; left:0; height:100%;
               background:#2a2; transition: width 0.08s linear; }
  .meter-bar.speech { background:#29d; }
  .meter-bar.blocked { background:#a22; }
  .marker { position: absolute; top:0; bottom:0; width:2px; background:#fd0; }
  .marker-label { position: absolute; top:-1.4em; font-size:0.75em; color:#fd0;
                  white-space: nowrap; transform: translateX(-50%); }
  table { border-collapse: collapse; }
  td { padding: 2px 12px 2px 0; }
  td.label { color:#888; }
  #clip { font-weight: bold; color:#555; }
  #clip.on { color:#f44; }
</style>
</head>
<body>
<h1>Didier — diagnostic conversation</h1>

<div class="bloc">
  <div class="meter-wrap" id="meter-wrap">
    <div class="meter-bar" id="meter-bar"></div>
    <div class="marker" id="marker-vad" style="display:none"></div>
    <div class="marker-label" id="marker-vad-label" style="display:none"></div>
    <div class="marker" id="marker-gate"></div>
    <div class="marker-label" id="marker-gate-label"></div>
  </div>
  <p>niveau : <span id="level-db">--</span> — crête : <span id="peak-db">--</span>
     — <span id="clip">écrêtage</span></p>
</div>

<div class="bloc">
  <table>
    <tr><td class="label">état</td><td id="chat_state">--</td></tr>
    <tr><td class="label">dernier texte STT</td><td id="stt_text">--</td></tr>
    <tr><td class="label">STT</td><td id="stt_ms">--</td></tr>
    <tr><td class="label">1re réplique (LLM)</td><td id="llm_first_ms">--</td></tr>
    <tr><td class="label">1er son</td><td id="audio_first_ms">--</td></tr>
    <tr><td class="label">latence totale perçue</td><td id="total_ms">--</td></tr>
  </table>
</div>

<script>
const FLOOR_DB = -60;  // plancher d'affichage (cf. commentaire Python ci-dessus)
function toDb(value) {
  return value > 0 ? 20 * Math.log10(value / 32768) : FLOOR_DB;
}
function pct(db) {
  return Math.min(100, Math.max(0, (db - FLOOR_DB) / (0 - FLOOR_DB) * 100));
}
function fmtDb(db) {
  return (db <= FLOOR_DB ? "< " + FLOOR_DB : db.toFixed(1)) + " dBFS";
}
function fmtMs(value) {
  return (value === null || value === undefined) ? "—" : Math.round(value) + " ms";
}
function placeMarker(marker, label, text, db) {
  const p = pct(db) + "%";
  marker.style.left = p;
  label.style.left = p;
  label.textContent = text;
}

const bar = document.getElementById("meter-bar");
const markerVad = document.getElementById("marker-vad");
const markerVadLabel = document.getElementById("marker-vad-label");
const markerGate = document.getElementById("marker-gate");
const markerGateLabel = document.getElementById("marker-gate-label");
const clip = document.getElementById("clip");

new EventSource("/events").onmessage = (evt) => {
  const data = JSON.parse(evt.data);
  const levelDb = toDb(data.level);

  bar.style.width = pct(levelDb) + "%";
  // Priorité d'affichage : ROUGE (bloqué par le gate) > BLEU (VAD en parole)
  // > VERT (par défaut) -- cf. spec du lot.
  bar.classList.toggle("blocked", data.blocked);
  bar.classList.toggle("speech", data.in_speech && !data.blocked);

  document.getElementById("level-db").textContent = fmtDb(levelDb);
  document.getElementById("peak-db").textContent = fmtDb(toDb(data.peak));
  clip.classList.toggle("on", data.peak >= data.gate_clip_peak);

  if (data.vad_threshold === null || data.vad_threshold === undefined) {
    markerVad.style.display = "none";
    markerVadLabel.style.display = "none";
  } else {
    markerVad.style.display = "";
    markerVadLabel.style.display = "";
    placeMarker(markerVad, markerVadLabel,
                "VAD (" + toDb(data.vad_threshold).toFixed(1) + " dBFS)",
                toDb(data.vad_threshold));
  }
  placeMarker(markerGate, markerGateLabel,
              "gate (" + toDb(data.gate_loud_rms).toFixed(1) + " dBFS)",
              toDb(data.gate_loud_rms));

  document.getElementById("chat_state").textContent = data.chat_state;

  const timing = data.timing;
  document.getElementById("stt_text").textContent = timing ? (timing.stt_text || "—") : "--";
  document.getElementById("stt_ms").textContent = timing ? fmtMs(timing.stt_ms) : "--";
  document.getElementById("llm_first_ms").textContent = timing ? fmtMs(timing.llm_first_ms) : "--";
  document.getElementById("audio_first_ms").textContent = timing ? fmtMs(timing.audio_first_ms) : "--";
  document.getElementById("total_ms").textContent = timing ? fmtMs(timing.total_ms) : "--";
};
</script>
</body>
</html>
"""


async def _diag_index_handler(_request: web.Request) -> web.Response:
    return web.Response(text=_DIAG_INDEX_HTML, content_type="text/html")


async def _diag_events_handler(request: web.Request) -> web.StreamResponse:
    """GET /events : flux Server-Sent Events (~10 Hz, cf. DIAG_EVENTS_PERIOD_S).
    SSE plutôt que WebSocket (cf. spec du lot) : ce flux est UNIDIRECTIONNEL
    (le navigateur ne pilote rien, il observe) -- EventSource est trivial côté
    navigateur (reconnexion automatique intégrée, aucun framing à gérer), et
    il n'y a aucun handshake bidirectionnel à maintenir contrairement à un
    WebSocket, inutilement complexe pour un simple flux de lecture seule.
    Chaque client est INDÉPENDANT (sa propre boucle d'envoi) ; déconnexion
    propre (onglet fermé) avalée, même motif que /video et /stream côté
    robot_web/face_sim_node."""
    state: _DiagState = request.app["state"]
    resp = web.StreamResponse(status=200, headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    })
    await resp.prepare(request)
    try:
        while True:
            await resp.write(f"data: {json.dumps(state.snapshot())}\n\n".encode())
            await asyncio.sleep(DIAG_EVENTS_PERIOD_S)
    except (ConnectionResetError, asyncio.CancelledError):
        pass  # client parti (onglet fermé) : normal, rien à logger
    return resp


def _build_diag_app(state: _DiagState) -> web.Application:
    app = web.Application()
    app["state"] = state
    app.router.add_get("/", _diag_index_handler)
    app.router.add_get("/events", _diag_events_handler)
    return app


class DiagServer:
    """Troisième boucle d'événements du node (cf. docstring de module POURQUOI
    `diag_port`) : thread daemon dédié, avec SA PROPRE boucle asyncio.
    AppRunner/TCPSite plutôt que `web.run_app` (cf. docstring de module --
    `run_app` tente d'installer des handlers de signal, qui ne fonctionnent
    QUE dans le thread principal : ça planterait ici). Aucun arrêt propre
    exposé (pas demandé par la spec, même tolérance que le thread rclpy.spin
    de robot_web/face_sim_node) : le thread daemon meurt avec le process."""

    def __init__(self, port: int, state: _DiagState):
        self._port = port
        self._state = state
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runner = web.AppRunner(_build_diag_app(self._state))
        loop.run_until_complete(runner.setup())
        loop.run_until_complete(
            web.TCPSite(runner, host="0.0.0.0", port=self._port).start())
        loop.run_forever()


class ChatStartupError(RuntimeError):
    """Levée quand le node ne peut pas démarrer proprement (secret, voix
    Piper, modèle STT... manquants ou invalides). Différencie un échec de
    démarrage EXPLICITE (déjà loggé via self.get_logger().error(...) avant
    d'être levée) d'un crash Python générique — main() l'attrape
    spécifiquement pour sortir proprement plutôt que de laisser une trace de
    crash-loop silencieuse (même pattern que
    person_tracker_node.PersonTrackerStartupError)."""


class ChatNode(Node):
    def __init__(self):
        super().__init__("chat")

        # Paramètres ROS déclarés avec défauts (issus de vision_config.config
        # via _chat_wiring.default_chat_parameters — jamais dupliqués en
        # dur ici) : modifiables par YAML/CLI sans toucher au code, ex.
        # `ros2 run vision chat --ros-args -p whisper_model:=tiny`.
        defaults = default_chat_parameters()
        self.declare_parameter("llm_model", defaults["llm_model"])
        self.declare_parameter("llm_base_url", defaults["llm_base_url"])
        self.declare_parameter("whisper_model", defaults["whisper_model"])
        self.declare_parameter("piper_voice", defaults["piper_voice"])
        self.declare_parameter("mic_device", defaults["mic_device"])
        self.declare_parameter("out_device", defaults["out_device"])
        self.declare_parameter("refresh_ms", defaults["refresh_ms"])
        self.declare_parameter("beep_seconds", defaults["beep_seconds"])
        self.declare_parameter("beep_amplitude", defaults["beep_amplitude"])
        self.declare_parameter("persona", defaults["persona"])
        # Paramètre TECHNIQUE (pas dans vision_config -- pas une variable de
        # personnage, cf. les autres ci-dessus) : serveur de diagnostic web
        # (vumètre + latences par tour, cf. docstring de module POURQUOI
        # `diag_port`). 0 = DÉSACTIVÉ (défaut) -- même philosophie que
        # `web_port`/`drive_enabled` côté robot_web/web_bridge_node.py, un
        # toggle d'exploitation qui n'a pas sa place dans le socle de config
        # partagé du personnage (default_chat_parameters ci-dessus).
        self.declare_parameter("diag_port", 0)

        llm_model = self.get_parameter("llm_model").value
        llm_base_url = self.get_parameter("llm_base_url").value
        whisper_model = self.get_parameter("whisper_model").value
        piper_voice = self.get_parameter("piper_voice").value
        mic_device = self.get_parameter("mic_device").value
        out_device = self.get_parameter("out_device").value
        refresh_ms = int(self.get_parameter("refresh_ms").value)
        beep_seconds = float(self.get_parameter("beep_seconds").value)
        beep_amplitude = int(self.get_parameter("beep_amplitude").value)
        persona_name = str(self.get_parameter("persona").value)
        diag_port = int(self.get_parameter("diag_port").value)

        # --- Personnalité de démarrage : validée ICI, échec de démarrage
        # EXPLICITE sur un nom inconnu (une faute de frappe dans un launch/
        # YAML doit se voir tout de suite, pas au premier tour de parole
        # avec un Didier sans personnage) -------------------------------------
        try:
            persona_prompt = personas.compose_system_prompt(persona_name)
        except ValueError as exc:
            self.get_logger().error(f"Paramètre persona invalide : {exc}")
            raise ChatStartupError("personnalité inconnue") from exc

        # --- Secret LLM : vérifié ICI, pas laissé au premier appel paresseux
        # de StreamingBrain (cf. constante LLM_API_KEY_NAME) ------------------
        try:
            get_secret(LLM_API_KEY_NAME)
        except (KeyError, FileNotFoundError) as exc:
            # PIÈGE (rclpy) : RcutilsLogger n'est PAS le module logging
            # stdlib — .error()/.info() ne prennent qu'UNE chaîne déjà
            # formatée, pas de style printf %s/args variadiques (ça lève un
            # TypeError). On formate donc systématiquement avec des
            # f-strings, jamais de virgule d'argument séparé.
            self.get_logger().error(
                f"Secret LLM manquant ({LLM_API_KEY_NAME}) : {exc} — copiez "
                "conf/secret.example vers conf/secret et renseignez la clé "
                "OpenRouter avant de démarrer le node chat."
            )
            raise ChatStartupError("secret LLM manquant") from exc

        # --- Micro + VAD -------------------------------------------------
        # Construction pure (aucun subprocess lancé avant mic.start(), aucune
        # I/O bloquante ici) : peu de raisons d'échouer, mais on protège quand
        # même par cohérence avec le reste du constructeur (une régression
        # future dans MicCapture.__init__ resterait un échec de DÉMARRAGE
        # propre, pas un crash Python nu).
        try:
            mic = MicCapture(mic_device, sample_rate=MIC_SAMPLE_RATE, frame_ms=MIC_FRAME_MS)
            vad = EnergyVad(config["chat_vad"], frame_ms=MIC_FRAME_MS)
            # Gate « source audio vivante » (cf. docstring de module POURQUOI) :
            # construit ICI, avec micro/VAD, même philosophie de construction
            # pure protégée par le même try/except (peu de raisons d'échouer,
            # mais un échec resterait un échec de DÉMARRAGE propre).
            # gate_config gardé à part (pas juste passé inline) : le serveur
            # de diagnostic (cf. plus bas, DiagState) doit lire les seuils
            # EFFECTIFS depuis CET objet réellement construit, jamais depuis
            # une constante recopiée (cf. spec du lot diag_port, 2026-09-13).
            gate_config = config["chat_live_audio_gate"]
            gate = LiveAudioGate(gate_config)
        except Exception as exc:  # noqa: BLE001 - log explicite avant de propager
            self.get_logger().error(f"Échec d'initialisation micro/VAD : {exc}")
            raise ChatStartupError("échec init micro/VAD") from exc

        # --- Diagnostic web (vumètre + latences, cf. docstring de module
        # POURQUOI `diag_port`) : self._diag EXISTE TOUJOURS (None si
        # désactivé) -- construit ICI (juste après vad/gate_config, dont il a
        # besoin pour les seuils effectifs) et AVANT ConversationEngine, dont
        # le constructeur appelle déjà on_state("listening") via
        # initial_state (cf. plus bas) : self._diag doit être un attribut
        # valide (None ou DiagState) avant ce premier appel à _publish_state.
        self._diag = _DiagState(vad, gate_config) if diag_port > 0 else None

        # --- STT (faster-whisper local) -----------------------------------
        try:
            stt = FasterWhisperStt(model_name=whisper_model)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(
                f"STT indisponible (modèle faster-whisper={whisper_model!r}) : "
                f"{exc} — vérifiez que faster-whisper est installé (conf/"
                "requirements.txt) et que le modèle a été préchargé dans "
                "l'image (Dockerfile-arm, pour un fonctionnement hors ligne)."
            )
            raise ChatStartupError("échec init STT") from exc

        # --- Cerveau LLM streamé (OpenRouter) -----------------------------
        try:
            # system_prompt = contrat technique + socle + personnalité (lot
            # D3, cf. vision.ai.personas — realtime_instructions() seul ne
            # portait aucun personnage), recomposé à chaud par _on_persona.
            brain = StreamingBrain(
                model=llm_model, base_url=llm_base_url,
                api_key_name=LLM_API_KEY_NAME, system_prompt=persona_prompt,
            )
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(
                f"Échec d'initialisation du cerveau LLM (modèle={llm_model!r}, "
                f"base_url={llm_base_url!r}) : {exc}"
            )
            raise ChatStartupError("échec init StreamingBrain") from exc

        # --- TTS Piper (voix locale de Didier) ----------------------------
        # Piper attend DEUX fichiers : le modèle .onnx et son config .json à
        # côté (PiperVoice.load, config_path par défaut = f"{model_path}.json")
        # — on vérifie les deux explicitement pour un message d'erreur qui
        # pointe la VRAIE cause (l'un des deux manquant) plutôt qu'une
        # exception onnxruntime opaque plus loin.
        if not os.path.isfile(piper_voice) or not os.path.isfile(f"{piper_voice}.json"):
            self.get_logger().error(
                f"Voix Piper absente : {piper_voice} (+ .json) — téléchargez "
                "la voix fr_FR-siwis-medium (.onnx + .json) vers ce chemin, "
                "cf. Dockerfile-arm (censé le faire au build) et le paramètre "
                "ROS piper_voice."
            )
            raise ChatStartupError(f"voix Piper introuvable : {piper_voice}")

        try:
            tts = PiperTts(piper_voice)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f"Échec de chargement de la voix Piper ({piper_voice}) : {exc}")
            raise ChatStartupError("échec init PiperTts") from exc

        # --- Lecture audio + bips de réflexion ----------------------------
        try:
            player = AudioPlayer(out_device)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f"Échec d'initialisation du lecteur audio ({out_device}) : {exc}")
            raise ChatStartupError("échec init AudioPlayer") from exc

        # amplitude=beep_amplitude (paramètre ROS, cf. config["chat_beep_amplitude"]
        # POURQUOI) : NE PAS laisser le défaut de build_thinking_beeps (14000,
        # jugé fatigant par David en séance le 2026-09-13) — il ne devait être
        # réglable qu'en éditant le code avant ce lot.
        beeps_pcm = build_thinking_beeps(
            beep_seconds, sample_rate=BEEPS_SAMPLE_RATE, amplitude=beep_amplitude)

        # --- Publishers StringTime : un par topic réutilisé côté robot ----
        # PIÈGE (vécu, 2026-07-11) : ne JAMAIS nommer cet attribut
        # `self._publishers` — rclpy.node.Node tient déjà une liste interne
        # de ce nom, et l'écraser par un dict fait planter
        # super().destroy_node() (`self._publishers[0]` -> KeyError: 0),
        # interrompant le nettoyage à l'arrêt.
        self._string_time_pubs = {
            FACE: self.create_publisher(StringTime, FACE, 10),
            ANIMATION: self.create_publisher(StringTime, ANIMATION, 10),
        }

        # --- Publisher d'état du chat (lot D0 outillage) -------------------
        # QoS TRANSIENT_LOCAL : MÊME motif que l'abonnement à ANIMATION_STATE
        # plus bas -- piège déjà vécu sur ce topic-là : sans durability
        # partagée des DEUX côtés, un abonné qui démarre APRÈS le premier
        # changement d'état (régie/télédiagnostic lancés après coup, ou
        # futur engagement_node) ne recevrait jamais l'état courant avant la
        # PROCHAINE transition -- potentiellement jamais. depth=1 : seul
        # l'état COURANT compte, pas un historique.
        self._chat_state_pub = self.create_publisher(
            StringTime, CHAT_STATE_TOPIC,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        # Même QoS latchée pour la personnalité active (cf. PERSONA_STATE_TOPIC).
        self._persona_state_pub = self.create_publisher(
            StringTime, PERSONA_STATE_TOPIC,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        # Transcript (cf. CHAT_TRANSCRIPT_TOPIC) : QoS VOLATILE depth=10 --
        # un flux de lignes, pas un état (un abonné tardif n'a pas à recevoir
        # une réplique d'il y a dix minutes comme si elle venait d'être dite).
        self._transcript_pub = self.create_publisher(StringTime, CHAT_TRANSCRIPT_TOPIC, 10)

        # --- Régie du chat (cf. docstring de module POURQUOI les topics de
        # RÉGIE) : créé AVANT ConversationEngine, qui le reçoit en kwarg.
        self._stage = stage.StageState()

        # --- Orchestrateur (logique déjà testée hors ROS) ------------------
        self._engine = ConversationEngine(
            mic=mic, vad=vad, stt=stt, brain=brain, tts=tts, player=player,
            publish=self._publish, beeps_pcm=beeps_pcm, beeps_rate=BEEPS_SAMPLE_RATE,
            refresh_ms=refresh_ms, on_state=self._publish_state,
            # État initial émis par le MOTEUR à la construction (publisher
            # chat_state créé juste au-dessus) : un abonné tardif trouve une
            # valeur latchée même avant le premier tour. "listening" en dur :
            # le mode interactif démarre TOUJOURS activé (cf. self._enabled
            # ci-dessous, lancer le node = vouloir la conversation).
            initial_state="listening",
            # Gate « source audio vivante » (cf. docstring de module) :
            # show_audio_active est une méthode LIÉE, pas un bool calculé ici
            # -- self._animation_state/_animation_expiry n'existent pas
            # encore à cet instant précis (affectés plus bas dans ce
            # constructeur), mais seule la RÉFÉRENCE à la méthode est stockée
            # ici ; elle n'est APPELÉE que depuis le thread de conversation,
            # démarré en tout dernier dans ce __init__, bien après que ces
            # attributs existent.
            gate=gate, show_audio_active=self._show_audio_active,
            # Vumètre + latences (cf. docstring de module POURQUOI
            # `diag_port`) : None si self._diag est None (diag désactivé) --
            # ConversationEngine traite déjà None comme "comportement
            # historique inchangé", aucune condition à dupliquer ici.
            on_meter=self._diag.on_meter if self._diag is not None else None,
            on_timing=self._diag.on_timing if self._diag is not None else None,
            # Régie (cf. docstring de module) : toujours câblée -- sans
            # publication sur ses topics, StageState reste vide et chaque tour
            # se déroule comme avant (seules les lignes du transcript
            # s'ajoutent ; le backoff micro mort garde sa durée, en sondant).
            stage=self._stage, on_transcript=self._publish_transcript,
        )
        self._mic = mic
        self._player = player
        # Gardé pour le changement de personnalité à chaud (_on_persona ->
        # brain.reconfigure) ; persona courant mémorisé pour dédupliquer
        # (re-cliquer le bouton déjà actif sur la console ne doit pas
        # réinitialiser la session de conversation en cours).
        self._brain = brain
        self._persona = persona_name
        # État initial de la personnalité publié tout de suite (latché) : un
        # abonné tardif (console) doit voir le défaut « bougon » actif dès le
        # démarrage, pas attendre le premier changement.
        self._publish_persona_state()

        # --- Mode interactif : ON au démarrage (lancer le node = vouloir la
        # conversation), basculable à chaud via le topic CHAT_CMD_TOPIC -----
        self._enabled = threading.Event()
        self._enabled.set()
        self.create_subscription(StringTime, CHAT_CMD_TOPIC, self._on_chat_cmd, 10)
        self.create_subscription(StringTime, PERSONA_TOPIC, self._on_persona, 10)
        self.create_subscription(StringTime, CHAT_TEXT_TOPIC, self._on_chat_text, 10)
        self.create_subscription(
            StringTime, CHAT_INSTRUCTION_TOPIC, self._on_chat_instruction, 10)
        self.create_subscription(StringTime, CHAT_FAULT_TOPIC, self._on_chat_fault, 10)

        # --- Arbitrage amont (2026-07-12, cf. docstring de module POURQUOI) :
        # None = jamais reçu (topic ANIMATION_STATE absent ou robot pas encore
        # démarré) -- distinct de "" (repos), cf. vision.ai.arbitration : ces
        # deux valeurs déclenchent des règles différentes dans allow_message.
        # ÉCRITE par _on_animation_state, qui tourne dans le thread rclpy.spin
        # (callback ROS) ; LUE par _publish, appelé par le thread DÉDIÉ de
        # ConversationEngine.run_forever (cf. docstring de module, POURQUOI du
        # thread) -- donc bien deux threads différents. Aucun verrou n'est
        # nécessaire malgré tout : l'affectation d'une référence str/None est
        # une opération atomique sous le GIL CPython, et _publish ne fait
        # qu'une LECTURE simple (jamais de lecture-puis-modification) -- la
        # pire chose qui puisse arriver est de lire l'état juste avant ou
        # juste après une transition, jamais une valeur corrompue.
        self._animation_state = None
        # Échéance de PÉREMPTION de l'état actif (garde-fou façon deadman,
        # cf. arbitration.state_expiry) : si animations_node meurt en pleine
        # séquence, le "" de fin n'arrive jamais — sans échéance le chat
        # resterait muet pour toujours. Deux attributs écrits séparément par
        # le callback : une lecture « déchirée » (état neuf + échéance
        # ancienne ou l'inverse) reste bénigne — au pire un message retenu ou
        # laissé passer À l'instant d'une transition, jamais un état corrompu.
        self._animation_expiry = 0.0
        # QoS TRANSIENT_LOCAL : DOIT correspondre à celle du publisher côté
        # animations_node (dadou_robot_ros, depth=1 + durability
        # TRANSIENT_LOCAL) -- sans ça, un chat_node démarré EN COURS de
        # spectacle n'obtiendrait l'état courant qu'à la PROCHAINE transition
        # (donc potentiellement jamais avant la fin de la séquence en cours).
        self.create_subscription(
            StringTime, ANIMATION_STATE, self._on_animation_state,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))

        # --- Thread de conversation (cf. docstring de module POURQUOI) ----
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._engine.run_forever,
            args=(self._stop_event, self._enabled), daemon=True,
        )
        self._thread.start()

        # --- Serveur de diagnostic (cf. docstring de module POURQUOI
        # `diag_port`) : démarré EN TOUT DERNIER, une fois tout le reste du
        # node opérationnel (self._diag, s'il existe, est déjà câblé dans
        # ConversationEngine/_publish_state depuis plus haut) -- None si
        # diag_port=0, aucun thread/socket créé dans ce cas (cf. clause OFF
        # par défaut).
        self._diag_server = DiagServer(diag_port, self._diag) if self._diag is not None else None
        if self._diag_server is not None:
            self._diag_server.start()

        self.get_logger().info(
            f"chat démarré (llm_model={llm_model}, whisper_model={whisper_model}, "
            f"mic_device={mic_device}, out_device={out_device}, "
            f"persona={persona_name}) -> topics {FACE}/{ANIMATION}, toggle sur "
            f"'{CHAT_CMD_TOPIC}' (on/off), persona sur '{PERSONA_TOPIC}' "
            f"({'/'.join(personas.persona_names())}), état publié sur "
            f"'{CHAT_STATE_TOPIC}' (latché), régie sur '{CHAT_TEXT_TOPIC}'/"
            f"'{CHAT_INSTRUCTION_TOPIC}'/'{CHAT_FAULT_TOPIC}', transcript sur "
            f"'{CHAT_TRANSCRIPT_TOPIC}'"
            + (f", diagnostic sur http://0.0.0.0:{diag_port}" if diag_port > 0 else "")
        )

    def _on_chat_cmd(self, ros_msg):
        """Active/désactive le mode interactif — même contrat que le topic
        `gaze` de gaze_follower (dadou_robot_ros) : "on"/"off", json ou brut."""
        raw = ros_msg.msg
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            value = raw
        if value in ("on", True, 1, "1"):
            self._enabled.set()
            self.get_logger().info("chat ON : mode interactif activé")
        elif value in ("off", False, 0, "0"):
            self._enabled.clear()
            # Interrompt une ÉCOUTE en cours : read_frame() bloquant retourne
            # None dès que le subprocess arecord meurt, la boucle run_forever
            # voit alors enabled baissé et se met en attente. Une RÉPLIQUE en
            # cours n'est PAS coupée (choix scénique : Didier finit sa
            # phrase, cf. ConversationEngine.run_forever) — le micro qu'on
            # stoppe ici est de toute façon déjà coupé pendant qu'il parle
            # (anti-larsen).
            self._mic.stop()
            self.get_logger().info("chat OFF : mode interactif désactivé (micro coupé)")
        else:
            self.get_logger().warning(f"commande chat inconnue : {raw!r}")

    def _on_persona(self, ros_msg):
        """Changement de personnalité à chaud (lot D3, cf. vision.ai.personas) :
        recompose le system prompt et ouvre une NOUVELLE session de
        conversation (brain.reconfigure — garder l'historique de l'ancien
        personnage donnerait un Didier schizophrène). Nom inconnu = warning
        avec la liste des variantes, jamais un crash (même philosophie que la
        commande chat inconnue ci-dessus). Tourne dans le thread rclpy.spin
        pendant que le thread de conversation peut être en plein tour :
        bénin, cf. docstring de StreamingBrain.reconfigure (pire cas = la
        réplique en cours consignée dans la nouvelle session)."""
        name = decode_persona_command(ros_msg.msg)
        if name == self._persona:
            # Re-clic du bouton déjà actif sur la console : ne PAS réinitialiser
            # la session en cours pour rien.
            self.get_logger().info(f"persona {name!r} déjà active — rien à faire")
            return
        try:
            prompt = personas.compose_system_prompt(name)
        except ValueError as exc:
            self.get_logger().warning(f"commande persona refusée : {exc}")
            return
        self._brain.reconfigure(prompt)
        self._persona = name
        self._publish_persona_state()
        self.get_logger().info(
            f"persona changée : {name!r} (nouvelle session de conversation)")

    def _publish_persona_state(self) -> None:
        """Publie la personnalité ACTIVE sur PERSONA_STATE_TOPIC (latché) —
        msg brut comme chat_state (pas de json.dumps : contrat simple, un
        abonné lit `msg` directement)."""
        self._persona_state_pub.publish(
            StringTime(msg=self._persona, time=0, anim=False))

    def _on_chat_text(self, ros_msg):
        """Texte tapé par la régie (cf. CHAT_TEXT_TOPIC) : SEULEMENT enfilé.

        PAS de mic.stop() ici (décision du 2026-10-14) : MicCapture n'est pas
        sûr entre threads -- son stop() appelé depuis CE thread (rclpy.spin)
        pendant que le thread de conversation lit ou arrête le micro laisse
        une fenêtre où `self._process` passe à None entre un test et son
        usage (AttributeError : thread de conversation mort = Didier sourd
        en silence, ou callback qui fait tomber rclpy.spin). La course
        existe déjà pour le toggle OFF ; on ne l'élargit pas à chaque texte
        tapé. Inutile de toute façon : ConversationEngine sonde la file à
        CHAQUE trame micro (30 ms), interrompt l'écoute lui-même et arrête
        le micro depuis SON thread. Pendant que Didier parle, le texte
        attend le tour suivant ; chat OFF, il attend la reprise."""
        try:
            self._stage.push_text(stage.decode_text_payload(ros_msg.msg))
        except ValueError as exc:
            self.get_logger().warning(f"chat_text refusé : {exc} ({ros_msg.msg!r})")
            return
        self.get_logger().info("chat_text reçu : servi au prochain tour (écoute interrompue)")

    def _on_chat_instruction(self, ros_msg):
        """Consigne de jeu (cf. CHAT_INSTRUCTION_TOPIC) : "" = levée.
        Journalisée ici (log du node, que David ne voit pas pendant la
        séance) -- jamais dans le transcript."""
        text = stage.decode_text_payload(ros_msg.msg)
        self._stage.set_instruction(text, time.monotonic())
        if text:
            self.get_logger().info(f"consigne posée : {text!r}")
        else:
            self.get_logger().info("consigne levée")

    def _on_chat_fault(self, ros_msg):
        """Panne de conversation (cf. CHAT_FAULT_TOPIC) : décodée et validée
        par vision.ai.stage (ValueError -> warning, jamais un crash du
        callback ; un ordre refusé ne change pas la panne en cours)."""
        try:
            op, params, until_ms = stage.decode_fault_command(ros_msg.msg)
            self._stage.set_fault(op, params, until_ms, time.monotonic())
        except ValueError as exc:
            self.get_logger().warning(f"{CHAT_FAULT_TOPIC} refusé : {exc}")
            return
        if op == "phantom":
            # Ponctuel (cf. StageState.set_fault) : pas de durée à annoncer.
            self.get_logger().info(f"panne chat phantom : énoncé fantôme enfilé {params['text']!r}")
        elif op == "pass":
            self.get_logger().info("panne chat levée (pass)")
        else:
            self.get_logger().info(
                f"panne chat : {op} {params} pour "
                f"{stage.fault_duration_s(until_ms):.1f} s (until_ms={until_ms!r}, "
                f"plafond {stage.FAULT_MAX_S:.0f} s)")

    def _publish_transcript(self, role: str, text: str) -> None:
        """Callback `on_transcript` de ConversationEngine (thread de
        conversation, comme _publish). t_ms = horloge MURALE (epoch, ms) :
        la ligne voyage vers la page « scène » du Pi robot et le journal du
        régisseur -- une horloge monotone ne voudrait rien dire hors de ce
        process. PAS d'arbitrage : ce n'est pas un actionneur."""
        payload = stage.encode_transcript(role, text, int(time.time() * 1000))
        self._transcript_pub.publish(StringTime(msg=payload, time=0, anim=False))

    def _on_animation_state(self, ros_msg):
        """Callback du topic ANIMATION_STATE (latché, publié par
        animations_node côté robot) : mémorise le nom de la séquence en
        cours ("" au repos) via vision.ai.arbitration.parse_animation_state
        (logique de décodage testée hors ROS). Affectation d'un str sur
        self._animation_state : pas de verrou nécessaire (cf. commentaire
        du constructeur) -- ce callback tourne dans le thread rclpy.spin,
        _publish() (appelé par le thread de conversation) ne fait qu'une
        LECTURE de la référence courante, jamais de lecture-modification."""
        state = arbitration.parse_animation_state(ros_msg.msg)
        if state:
            # ros_msg.time = remaining_ms au (re)démarrage (contrat
            # animations_node, republié à chaque relance de séquence même à
            # nom identique) : arme la péremption façon deadman. Échéance
            # écrite AVANT l'état (une lecture croisée reste bénigne, cf.
            # commentaire du constructeur).
            self._animation_expiry = arbitration.state_expiry(
                int(ros_msg.time), time.monotonic())
        self._animation_state = state

    def _show_audio_active(self) -> bool:
        """Callback `show_audio_active` injecté dans ConversationEngine (cf.
        vision.audio.live_audio_gate, canal C4 « séquence de spectacle ») :
        appelé PAR LE THREAD de conversation à chaque frame micro tant que le
        gate est câblé -- RÉUTILISE arbitration.effective_state (même calcul
        que _publish ci-dessous, même péremption deadman) plutôt que de le
        dupliquer, cf. docstring de module POURQUOI.

        Ce node ne fait ici QUE deux choses : appliquer la péremption
        (effective_state, comme _publish) et déléguer la DÉCISION à
        arbitration.show_audio_live — laquelle porte les deux exclusions
        ("parle" et None) et leur pourquoi, au même endroit que la doctrine
        jumelle d'allow_message. Aucune règle ne doit être réécrite ici :
        c'est le genre de duplication qui diverge en silence."""
        state = arbitration.effective_state(
            self._animation_state, self._animation_expiry, time.monotonic())
        return arbitration.show_audio_live(state)

    def _publish(self, message: RosMessage) -> None:
        """Callback injecté dans ConversationEngine : traduit un RosMessage en
        StringTime (cf. vision.nodes._chat_wiring.ros_message_to_string_time_kwargs,
        la seule partie testable sans ROS de cette méthode) et publie sur le
        publisher correspondant à message.topic -- SAUF si l'arbitrage amont
        retient le message (une séquence de spectacle a la main, cf.
        vision.ai.arbitration et docstring de module)."""
        # Péremption appliquée à la LECTURE (cf. arbitration.effective_state) :
        # un état actif dont l'échéance est dépassée est traité comme le repos
        # (animations_node probablement mort en pleine séquence).
        state = arbitration.effective_state(
            self._animation_state, self._animation_expiry, time.monotonic())
        if not arbitration.allow_message(message.topic, message.payload, state):
            # PIÈGE rclpy documenté en tête de fichier : f-strings uniquement,
            # jamais de %s variadique (RcutilsLogger n'est pas le logging stdlib).
            self.get_logger().info(
                f"message {message.topic} retenu : la séquence "
                f"'{state}' a la main (arbitrage amont)"
            )
            return

        publisher = self._string_time_pubs.get(message.topic)
        if publisher is None:
            # Ne devrait jamais arriver (vision.ai.performance ne produit que
            # des RosMessage sur FACE/ANIMATION) : on log plutôt que de
            # planter le thread de conversation pour une seule publication
            # ratée — le spectacle continue (même philosophie défensive que
            # ConversationEngine._speak_reply).
            self.get_logger().warning(f"Topic inconnu, message ignoré : {message.topic}")
            return
        publisher.publish(StringTime(**ros_message_to_string_time_kwargs(message)))

    def _publish_state(self, state: str) -> None:
        """Callback `on_state` injecté dans ConversationEngine : publie l'état
        (listening/thinking/speaking/off) tel quel sur CHAT_STATE_TOPIC.
        PAS d'arbitrage ici (contrairement à _publish ci-dessus) : c'est un
        topic d'ÉTAT (ce que le chat OBSERVE de lui-même), pas un actionneur
        qui pourrait entrer en conflit avec une séquence de spectacle -- rien
        à retenir. msg=state BRUT (pas de json.dumps, contrairement à
        FACE/ANIMATION) : ce topic n'a pas le même contrat que ceux
        d'animations_node, une chaîne simple suffit à un abonné qui lit
        `msg` directement.

        Alimente AUSSI la page de diagnostic (cf. docstring de module
        POURQUOI `diag_port`) si elle est active -- ConversationEngine ne
        porte qu'UN SEUL callback `on_state` (pas une liste d'abonnés), c'est
        donc ICI qu'on relaie vers `_DiagState.on_state`, pas en ajoutant un
        second kwarg au moteur pour ce qui reste un simple relais local."""
        self._chat_state_pub.publish(StringTime(msg=state, time=0, anim=False))
        if self._diag is not None:
            self._diag.on_state(state)

    def destroy_node(self):
        # Arrêt propre : stop_event débloque la boucle run_forever DÈS que le
        # tour en cours se termine ; mic.stop() coupe le subprocess arecord
        # tout de suite, ce qui fait échouer le read_frame() bloquant en
        # cours (retourne None) si le node est arrêté EN PLEIN tour d'écoute
        # — sans ça, le thread pourrait rester bloqué indéfiniment sur un
        # micro qui n'a plus de raison de parler.
        stop_event = getattr(self, "_stop_event", None)
        if stop_event is not None:
            stop_event.set()

        mic = getattr(self, "_mic", None)
        if mic is not None:
            mic.stop()

        player = getattr(self, "_player", None)
        if player is not None:
            player.stop()

        thread = getattr(self, "_thread", None)
        if thread is not None:
            thread.join(timeout=SHUTDOWN_JOIN_TIMEOUT_S)

        super().destroy_node()


def main(args=None):
    # ConversationEngine (brique pure, sans dépendance rclpy) journalise via
    # le logging STDLIB — sans handler configuré, ces logs sont INVISIBLES
    # (niveau WARNING par défaut, aucun handler) : le premier test micro réel
    # (2026-07-11) s'est déroulé à l'aveugle à cause de ça. Racine à WARNING
    # pour ne pas hériter du bruit INFO des libs HTTP (httpx/openai), INFO
    # ciblé sur vision.* uniquement (tours de conversation : STT, répliques,
    # abandons).
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )
    logging.getLogger("vision").setLevel(logging.INFO)

    rclpy.init(args=args)
    try:
        node = ChatNode()
    except ChatStartupError:
        # Déjà loggé en détail dans __init__ (get_logger().error avant la
        # levée) : ici on se contente de sortir proprement, contexte ROS
        # fermé, code de retour non nul pour que systemd/docker sachent que
        # ça n'a pas tourné (mais SANS boucle de crash bruyante : un seul
        # message clair, pas une pile d'exception) — même pattern que
        # person_tracker_node.main().
        rclpy.try_shutdown()
        raise SystemExit(1)

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        # SIGINT (Ctrl-C, pkill -INT) ou arrêt du contexte par rclpy : c'est
        # le chemin d'arrêt NORMAL, pas une erreur — sans ce except, la pile
        # d'exception polluerait le log à chaque arrêt de spectacle.
        pass
    finally:
        node.destroy_node()
        # try_shutdown (PAS shutdown) : en Jazzy, le handler SIGINT de rclpy
        # a souvent DÉJÀ fermé le contexte quand on arrive ici — shutdown()
        # lèverait « rcl_shutdown already called » (constaté au premier test
        # du toggle, 2026-07-11).
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
