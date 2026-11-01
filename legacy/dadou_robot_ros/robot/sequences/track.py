"""Piste de keyframes temporisées — moteur temporel UNIQUE.

Ce module fusionne les deux anciennes classes qui lisaient le MÊME format JSON
`[t_rel 0..1, valeur]` avec deux sémantiques différentes :

- `Animation` (AnimationManager) : la keyframe `[t, v]` = « ÉMETTRE v à
  l'instant t×duration ». Pas de boucle. -> constructeur `Track.emissions`.
- `Sequence` (Face, Lights) : la keyframe `[t, v]` = « v AFFICHÉE JUSQU'À
  t×duration » (la première de 0 à t0). Boucle possible. -> `Track.frames`.

Les DEUX lectures du JSON sont faites par les constructeurs nommés ; la
mécanique temporelle (l'échéancier d'activations + poll) est unique.

Pourquoi un « échéancier d'activations » plutôt que la valeur courante :
`poll(now_ms)` émet la valeur UNE fois quand son instant est atteint (une
activation max par poll — au tick 10 Hz, deux activations rapprochées sortent
sur deux ticks, comme les anciennes classes qui n'avançaient que d'un cran par
appel). Pas d'horloge interne : `now_ms` est TOUJOURS passé par l'appelant
(testabilité — on pilote le temps depuis les tests).

Nuance historique importante : Face et Lights utilisaient tous deux `Sequence`
mais avec un décalage d'un cran DIFFÉRENT (Face dessinait la frame courante PUIS
avançait ; Lights avançait PUIS chargeait). Ils n'ont donc pas exactement la même
sémantique temporelle : `Track.frames` reproduit Lights (affichage jusqu'à t) ;
Face construit son propre échéancier (voir robot/actions/face.py, commenté).
"""


class Track:

    def __init__(self, activations_ms, duration_ms, loop, now_ms):
        # activations_ms : liste ordonnée de (instant_ms, valeur). L'instant est
        # relatif au début de la piste (0 = construction). duration_ms borne le
        # cycle quand loop=True.
        self._activations = list(activations_ms)
        self._duration_ms = duration_ms
        self._loop = loop
        self._start_ms = now_ms
        self._index = 0
        # Dernière valeur émise par poll — exposée par last_value (Lights lit
        # la brique en cours après le poll immédiat de chargement).
        self._last_value = None

    @classmethod
    def emissions(cls, keyframes, duration_ms, now_ms):
        """Lecture Animation : `[t, v]` = émettre v à t×duration. Sans boucle.

        keyframes absente/vide (piste non fournie par le JSON) -> aucune
        activation -> has_data False, poll toujours None (comme l'ancien
        Animation.has_data)."""
        activations = []
        if keyframes:
            for t, value in keyframes:
                activations.append((duration_ms * t, value))
        return cls(activations, duration_ms, False, now_ms)

    @classmethod
    def frames(cls, keyframes, duration_ms, loop, now_ms):
        """Lecture Sequence/Lights : `[t, v]` = v affichée JUSQU'À t×duration.

        Équivalence en temps d'activation : v0 s'active à 0, v1 à t0×duration,
        v2 à t1×duration, ... -> activations (0, v0), (t0×d, v1), ...,
        (t(n-2)×d, v(n-1)). La dernière frame reste affichée jusqu'à la fin du
        cycle (t(n-1)=1.0 en général) puis la piste reboucle si loop."""
        activations = []
        if keyframes:
            activations.append((0, keyframes[0][1]))
            for i in range(1, len(keyframes)):
                activations.append((duration_ms * keyframes[i - 1][0], keyframes[i][1]))
        return cls(activations, duration_ms, loop, now_ms)

    def poll(self, now_ms):
        """Valeur à émettre maintenant, ou None.

        Ordre : on purge d'abord l'activation en attente atteinte (une seule) ;
        une fois toutes les activations du cycle émises, si loop et le cycle est
        écoulé, on rebobine (start_ms += duration autant de fois que nécessaire,
        index remis à 0) et on réémet l'activation 0 du nouveau cycle si atteinte.

        Purger AVANT de rebobiner est nécessaire : une frame dont l'instant vaut
        exactement duration (cas fréquent, dernier keyframe t=1.0) doit sortir au
        poll où elapsed atteint duration, PAS être sautée par un rebobinage."""
        if not self._activations:
            return None

        if self._index < len(self._activations):
            instant, value = self._activations[self._index]
            if now_ms - self._start_ms >= instant:
                self._index += 1
                self._last_value = value
                return value
            return None

        # Toutes les activations du cycle courant ont été émises.
        if self._loop and self._duration_ms > 0 and now_ms - self._start_ms >= self._duration_ms:
            while now_ms - self._start_ms >= self._duration_ms:
                self._start_ms += self._duration_ms
            self._index = 0
            instant, value = self._activations[0]
            if now_ms - self._start_ms >= instant:
                self._index = 1
                self._last_value = value
                return value
        return None

    @property
    def last_value(self):
        """Dernière valeur émise par poll (None tant qu'aucune n'est sortie).
        Pour Lights : la brique LightAnimation en cours."""
        return self._last_value

    @property
    def has_data(self):
        return bool(self._activations)
