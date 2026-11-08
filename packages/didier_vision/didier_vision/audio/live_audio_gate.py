"""Gate « source audio vivante » (half-duplex ÉLARGI) — logique PURE, stdlib
UNIQUEMENT (dataclass/time), horloge injectée : même patron que
didier_vision.audio.vad (EnergyVad ne reçoit que des `float` déjà calculés, se teste
donc sans micro/temps réel — cf. son docstring).

QUOI : un demi-gate existe déjà (mic.stop() avant que Didier parle, cf.
       didier_vision.audio.mic.MicCapture.stop) — il couvre SA PROPRE voix, pas les
       trois autres sources qui peuvent rendre le châssis "vivant" pendant
       que le micro écoute (le robot EST l'enceinte, cf. hardware/
       overview.md §Echo). Ce module ferme ce trou-là :
         C2 queue acoustique (réverbération + tampon ALSA après drain())
         C3 acoustique inconnue (voix HF de David par la sono, salle, klaxon)
         C4 séquence de spectacle (piste audio d'une animation en cours)
       en OU avec C1 (déjà géré ailleurs). Un seul canal vivant suffit à
       bloquer — cf. dadou_robot_ros/docs/etude-declenchement-conversation.md
       §10.2 pour le tableau complet des quatre canaux.
POURQUOI stdlib pur + horloge injectée : ce module ne fait AUCUN calcul sur
       les octets (frame_rms/frame_peak restent dans didier_vision.audio.mic, avec
       numpy) — il ne reçoit que des float déjà calculés et un bool déjà
       décidé (show_audio), exactement comme EnergyVad.feed(level). Ça le
       rend testable en CI (aucune dépendance micro/numpy) et rejouable par
       vad_replay à travers le MÊME code que la prod.
POURQUOI le maintien (hold_s) : sans lui, le gate battrait EXACTEMENT au
       rythme de la parole de David (ouvert entre les syllabes, fermé
       pendant) et laisserait filtrer des fragments de phrase entre ses
       mots — le maintien couvre les pauses naturelles du langage parlé.
POURQUOI le sens de la dégradation est figé ici et nulle part ailleurs (cf.
       §10.6 de l'étude) : bloquer à tort coûte une réplique manquée ; ne PAS
       bloquer coûte une boucle audio (Didier s'entend, se répond, et sa
       réponse repart dans la sono). En cas de doute, ce module bloque —
       TOUTE optimisation qui inverserait ce sens (assouplir un seuil,
       raccourcir un maintien "pour gagner en réactivité") est un bug, pas
       une amélioration.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

# Logger stdlib (comme didier_vision.ai.conversation) : les transitions du gate
# sont la SEULE trace de ce qui se passe côté micro pendant une pause
# d'écoute — cf. §10.7 de l'étude, "le premier test micro réel s'est fait à
# l'aveugle faute de logs (11/07), on ne recommence pas". Journalisé ici, pas
# côté appelant : c'est ce module qui connaît le niveau et la cause exacts
# de la décision, pas ConversationEngine.
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveAudioGateConfig:
    """Valeurs par défaut = mesures du 26/08 sur la chaîne d'acquisition
    réelle du robot, PAS des constantes magiques — cf. dadou_robot_ros/docs/
    etude-declenchement-conversation.md §10.4 pour le détail des mesures et
    la justification du calcul (milieu géométrique, 11 dB de marge de chaque
    côté). ⚠️ À RECALIBRER si le gain micro change (carte, alias ALSA,
    réglage xvf_host) : ces chiffres sont adossés à une chaîne d'acquisition
    précise, et un étage qui change déplace la voix EN SILENCE (même piège
    que le seuil d'écrêtage de l'effet de prod, étude voix §2.1)."""

    # Seuil RMS (unités int16 linéaires, cf. didier_vision.audio.mic.frame_rms) au-
    # dessus duquel le niveau est considéré comme une source vivante dans le
    # châssis. 2800 = -21,4 dBFS, milieu géométrique EXACT entre "humain à
    # 3 m" (-32,4 dBFS) et "Didier par sa propre sono" (-10,4 dBFS) : 11,0 dB
    # de marge de chaque côté, le point qui maximise la marge sur les deux
    # erreurs possibles (rater un humain / prendre la sono pour un humain).
    loud_rms: float = 2800.0
    # Crête (cf. didier_vision.audio.mic.frame_peak) à partir de laquelle l'entrée
    # est considérée comme écrêtée (-0,2 dBFS, tout en haut de l'échelle
    # int16 = 32768) : l'entrée sature quand la sono passe fort, MÊME si le
    # RMS de la trame reste sous loud_rms (une syllabe forte isolée au
    # milieu d'un silence relatif) — bloque donc INDÉPENDAMMENT du niveau.
    clip_peak: float = 32000.0
    # Maintien (s) après la DERNIÈRE trame bruyante/écrêtée/de spectacle :
    # couvre les pauses entre les mots (cf. docstring de module POURQUOI le
    # maintien) — sans lui, le gate battrait au rythme de la parole de David.
    hold_s: float = 1.0
    # Queue acoustique (s) armée explicitement par arm_tail() après drain()
    # (C2, réverbération + tampon ALSA qui continue de sortir un peu après
    # que le player a rendu la main) — DISTINCT de hold_s : ce n'est pas une
    # réaction à une trame captée (le micro est encore coupé à ce moment-là),
    # c'est une anticipation posée AVANT même que le micro ne redémarre.
    tail_hold_s: float = 0.5


class LiveAudioGate:
    """Machine à seuil unique (un `hold_until`, pas d'état énuméré) : le gate
    est BLOQUÉ tant que l'horloge injectée n'a pas dépassé `hold_until`, et
    chaque condition vivante repousse cette échéance de `hold_s`. Pas de
    machine à états façon EnergyVad : ici il n'y a qu'un OUI/NON à chaque
    frame, jamais de transition à confirmer sur plusieurs trames."""

    def __init__(self, config: LiveAudioGateConfig, now=time.monotonic):
        self._config = config
        self._now = now
        # -inf : gate OUVERT par défaut à la construction (aucune source
        # vivante n'a encore été vue) — cohérent avec le comportement
        # historique (gate=None) tant qu'aucune trame bruyante n'est arrivée.
        self._hold_until = float("-inf")
        # Dernier état LOGUÉ (pas le dernier état réel) : sert uniquement à
        # ne journaliser QUE les transitions, jamais à 20-33 Hz en continu
        # (cf. §10.7 -- "un état qui bat à 33 Hz n'y a pas sa place", même
        # philosophie appliquée ici aux logs qu'à un hypothétique topic ROS).
        self._logged_blocked = False

    def feed(self, level: float, peak: float, show_audio: bool = False) -> bool:
        """Nourrit le gate avec UNE trame déjà mesurée. Retourne True si la
        trame doit être JETÉE (gate bloqué), False si elle peut atteindre la
        VAD.

        Ordre de priorité de la CAUSE journalisée (n'affecte PAS la
        décision, qui reste un OU strict des trois conditions) : écrêtage
        d'abord (le signe le plus sûr d'une sono vivante), puis niveau, puis
        spectacle -- reflète la fiabilité décroissante des trois heuristiques
        (cf. §10.2 : C4 > C3 en fiabilité, l'écrêtage de C3 étant lui-même
        plus sûr qu'un simple dépassement de seuil RMS)."""
        now = self._now()

        cause = None
        if peak >= self._config.clip_peak:
            cause = "écrêtage"
        elif level > self._config.loud_rms:
            cause = "niveau"
        elif show_audio:
            cause = "spectacle"

        if cause is not None:
            self._hold_until = now + self._config.hold_s

        blocked = now < self._hold_until
        if blocked != self._logged_blocked:
            if blocked:
                logger.info(
                    "Gate audio vivante : BLOQUÉ (niveau=%.0f, crête=%.0f, cause=%s)",
                    level, peak, cause or "maintien")
            else:
                logger.info("Gate audio vivante : rouvert.")
            self._logged_blocked = blocked
        return blocked

    def block_for(self, seconds: float) -> None:
        """Bloque explicitement pour `seconds` à partir de MAINTENANT — pose
        directement l'échéance (pas un max avec l'échéance courante) : les
        deux appelants (arm_tail ci-dessous) l'utilisent à un moment où
        `hold_until` ne reflète plus rien d'actuel (le micro était coupé
        pendant que Didier parlait, donc feed() n'a pas tourné depuis un
        moment — poser une valeur périmée en max() n'aurait aucun sens)."""
        now = self._now()
        self._hold_until = now + seconds
        blocked = now < self._hold_until
        if blocked != self._logged_blocked:
            # Message choisi d'après l'état ATTEINT, pas supposé bloqué : un
            # block_for(0) ou négatif (test, config dégénérée) rouvre le gate
            # et doit le DIRE — un log qui annonce "BLOQUÉ" alors que la
            # trame suivante passera est pire que pas de log du tout, c'est
            # une fausse piste de diagnostic sur le seul canal d'observation
            # dont on dispose pendant un protocole physique.
            if blocked:
                logger.info(
                    "Gate audio vivante : BLOQUÉ (%.1f s, cause=maintien manuel).", seconds)
            else:
                logger.info("Gate audio vivante : rouvert.")
            self._logged_blocked = blocked

    def arm_tail(self) -> None:
        """Arme la queue acoustique (C2) pour `tail_hold_s` — à appeler
        juste AVANT que le micro ne redémarre après que Didier a parlé
        (succès ET exception, cf. didier_vision.ai.conversation._speak_reply) :
        la réverbération et le tampon ALSA continuent de sortir un peu après
        que drain()/le player ont rendu la main, et le micro ne doit pas
        réécouter cette toute fin avant qu'elle ne soit retombée."""
        self.block_for(self._config.tail_hold_s)

    @property
    def blocked(self) -> bool:
        """État courant SANS consommer de nouvelle mesure (pour un appelant
        qui veut juste savoir où en est le gate, ex. diagnostic/tests) —
        n'avance ni ne journalise rien de nouveau, contrairement à feed()."""
        return self._now() < self._hold_until
