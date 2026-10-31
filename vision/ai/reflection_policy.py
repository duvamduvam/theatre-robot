"""Politique de la réflexion : QUAND réfléchir, QUAND faire parler Didier.

QUOI : `ReflectionScheduler` décide à quel moment lancer un appel de
      réflexion (événements, battement de fond) ; `SpontaneousPolicy` décide si
      le résultat peut déclencher un tour de parole spontané. Modules PURS
      (stdlib seule, horloge injectée par `now_s`) : testables sans ROS.
POURQUOI (cf. dadou_robot_ros/docs/etude-niveaux-reflexion.md §4 et §10) :
      un appel coûte 4-7 s et de l'argent ; la scène doit rester vivante sans
      que Didier interrompe quelqu'un ni parle dans le vide. Chaque garde-fou
      est gravé par un test (et vérifié par mutation).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Ordre de priorité pour le libellé de raison d'un job.
_KINDS = ("david", "didier", "poi", "person_appeared", "instruction", "reflect")
# Événements qui déclenchent une réflexion à eux seuls ("didier" : non —
# sa propre parole ne justifie pas de réfléchir, et elle n'entretient pas
# non plus l'engagement, cf. _engaged).
_TRIGGERS = ("david", "poi", "person_appeared", "instruction")


@dataclass
class Job:
    deep: bool
    reason: str


class ReflectionScheduler:
    def __init__(self, min_interval_s: float = 4.0, heartbeat_s: float = 20.0,
                 debounce_s: float = 1.0, engaged_window_s: float = 60.0):
        self._min_interval_s = min_interval_s
        self._heartbeat_s = heartbeat_s
        self._debounce_s = debounce_s
        self._engaged_window_s = engaged_window_s
        self._pending: set = set()          # déclencheurs en attente
        self._reflect_pending = False
        self._last_start: Optional[float] = None
        self._last_david: Optional[float] = None
        self._last_person: Optional[float] = None

    def notify(self, kind: str, now_s: float) -> None:
        """Enregistre un événement. `kind` inconnu = ValueError (bug
        d'appelant : un événement perdu en silence serait pire)."""
        if kind not in _KINDS:
            raise ValueError(f"événement de réflexion inconnu : {kind!r}")
        if kind == "reflect":
            self._reflect_pending = True
            return
        if kind == "david":
            # Chaque nouvelle ligne repousse le debounce (laisser finir la
            # phrase) et entretient l'engagement (cf. _engaged).
            self._last_david = now_s
        if kind == "person_appeared":
            self._last_person = now_s
        if kind in _TRIGGERS:
            self._pending.add(kind)

    def person_seen(self, now_s: float) -> None:
        """Une personne est vue À CET INSTANT (appelé à chaque trame de
        suivi) : entretient l'engagement sans déclencher de réflexion."""
        self._last_person = now_s

    def _engaged(self, now_s: float) -> bool:
        """Engagé = David a parlé ou une personne a été vue depuis moins de
        engaged_window_s. Revue adversariale du 23/10 (I4) : une ligne
        "didier" ne compte PLUS — sinon boucle auto-entretenue : battement →
        tour spontané → ligne "didier" → engagement ré-armé → battement… (Didier
        parlait seul toutes les 20 s, 30 tours en 10 min devant une rue vide)."""
        for t in (self._last_david, self._last_person):
            if t is not None and now_s - t <= self._engaged_window_s:
                return True
        return False

    def _interval_ok(self, now_s: float) -> bool:
        return self._last_start is None or now_s - self._last_start >= self._min_interval_s

    def next_job(self, now_s: float, in_flight: bool) -> Optional[Job]:
        """Le prochain appel à lancer, ou None. Lancer un job consomme TOUS les
        événements en attente (il voit la transcription entière) ; ceux qui
        arrivent pendant un vol restent en attente → UNE seule relance après."""
        if in_flight:
            return None

        if self._reflect_pending:
            # Demande explicite de Didier : un acteur attend, on ignore
            # intervalle minimal et debounce.
            return self._start(now_s, deep=True, reason="reflect")

        if not self._interval_ok(now_s):
            return None

        triggers = set(self._pending)
        if "david" in triggers and (
                self._last_david is None or now_s - self._last_david < self._debounce_s):
            triggers.discard("david")
        if triggers:
            reason = "+".join(k for k in _KINDS if k in triggers)
            return self._start(now_s, deep=False, reason=reason)

        # Un « david » en cours de debounce n'est pas fini de parler : le
        # battement attendrait la fin de sa phrase lui aussi.
        if "david" not in self._pending and self._engaged(now_s) and (
                self._last_start is None or now_s - self._last_start >= self._heartbeat_s):
            return self._start(now_s, deep=False, reason="heartbeat")
        return None

    def _start(self, now_s: float, deep: bool, reason: str) -> Job:
        self._last_start = now_s
        self._pending.clear()
        self._reflect_pending = False
        return Job(deep=deep, reason=reason)


class DeepRequests:
    """Emplacement de la demande de réflexion profonde de Didier (clé
    "reflechir"), avec UN nouvel essai si le job échoue. Revue adversariale du
    23/10 (I5) : un appel profond en échec (réseau, JSON illisible) perdait la
    demande — or Didier a PROMIS « je reprends la parole quand j'ai la
    réponse » (personas.REFLECT_TEMPLATE) et David attend. Un seul nouvel
    essai : au-delà, l'erreur n'est plus un accroc, on abandonne (warning
    côté node) plutôt que de boucler sur un fournisseur en panne.
    Non thread-safe : le verrou est celui du node."""

    def __init__(self):
        self._demande: Optional[str] = None
        self._retry = False

    def submit(self, demande: str) -> None:
        """Nouvelle demande : REMPLACE celle en attente (un seul emplacement,
        la plus récente prime) et repart avec un essai neuf."""
        self._demande = demande
        self._retry = False

    def take(self) -> tuple:
        """(demande, est_un_nouvel_essai) et vide l'emplacement ; (None,
        False) si rien n'attend."""
        demande, retry = self._demande, self._retry
        self._demande, self._retry = None, False
        return demande, retry

    def failed(self, demande: Optional[str], was_retry: bool) -> bool:
        """Le job de `demande` a échoué. Vrai = remise en attente (l'appelant
        notifie "reflect" à l'ordonnanceur) ; faux = abandon : c'était déjà le
        nouvel essai, pas de demande, ou une demande PLUS RÉCENTE attend déjà
        (elle prime, cf. submit)."""
        if demande is None or was_retry or self._demande is not None:
            return False
        self._demande, self._retry = demande, True
        return True


class SpontaneousPolicy:
    """Autorise (ou non) un tour de parole spontané après une réflexion. Le
    contrôle « personne ne parle EN CE MOMENT » est refait côté parole (P3) :
    ici on évite seulement d'envoyer pour rien.
    Tient aussi la mémoire des objets déjà commentés EN MARCHE (une seule
    remarque par objet, décision de David du 31/10) : vidée par
    `reset_remarks` (restart de route), sinon valable la vie du node.
    Non thread-safe : le verrou est celui du node."""

    def __init__(self, min_silence_s: float = 4.0, min_gap_s: float = 12.0):
        self._min_silence_s = min_silence_s
        self._min_gap_s = min_gap_s
        self._remarked: set = set()     # objets déjà commentés en marche

    def already_remarked(self, poi: str) -> bool:
        return poi in self._remarked

    def reset_remarks(self) -> None:
        """Nouvelle traversée (route restart) : chaque objet redevient neuf."""
        self._remarked.clear()

    def allow(self, result_parler: bool, deep: bool, chat_state: str, now_s: float,
              last_transcript_s: Optional[float],
              last_spontaneous_s: Optional[float], *, moving: bool,
              passing_poi: Optional[str] = None) -> bool:
        """`moving` : Didier roule VRAIMENT (SituationBoard.moving : route on
        ET vitesse > 0). `passing_poi` : objet dont l'ENTRÉE a déclenché cette
        réflexion (None = autre déclencheur, battement compris).
        EFFET DE BORD : un tour accordé en marche CONSOMME l'objet (plus
        jamais de remarque en marche dessus) — l'appelant ne doit donc
        appeler allow() que s'il a de quoi envoyer."""
        if deep:
            # Réponse à une DEMANDE de Didier (clé "reflechir") : TOUJOURS
            # envoyée, quoi qu'en dise le LLM — Didier a promis « je reprends
            # la parole quand j'ai la réponse » (personas.REFLECT_TEMPLATE) et
            # David attend. Vu au banc ROS du 23/10 : parler=False rendu sur
            # une demande, la réponse se perdait. Ni état ni écart minimal ici :
            # la demande arrive souvent PENDANT la phrase d'accusé de réception
            # de Didier ; c'est le côté parole (emplacement unique, TTL 8 s,
            # 3 s de silence, jamais en pleine parole) qui choisit le moment.
            return True
        if not result_parler:
            return False
        if moving and (passing_poi is None or passing_poi in self._remarked):
            # Décision de David du 31/10 (dadou_robot_ros docs/etude-
            # interaction.md §10.2 « En marche ») : en roulant, Didier ne
            # parle de lui-même QUE pour une remarque sur l'objet qu'il
            # croise, une seule par objet. Lève la règle « micro à l'arrêt »
            # du 23/10 (revue I2/M3 : un « stop » crié pendant la réplique
            # était perdu) — l'écoute garde l'entend désormais (c392f12).
            # Battement, personne apparue, consigne : toujours muets en marche.
            return False
        if chat_state != "listening":
            return False
        if last_transcript_s is not None and now_s - last_transcript_s < self._min_silence_s:
            return False
        if last_spontaneous_s is not None and now_s - last_spontaneous_s < self._min_gap_s:
            return False
        if moving:
            self._remarked.add(passing_poi)
        return True
