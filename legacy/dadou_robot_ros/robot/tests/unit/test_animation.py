"""Scénarios d'émission d'animation, portés sur Track.emissions.

Historiquement testait la classe Animation (supprimée : fusionnée dans Track).
AnimationManager construit désormais chaque piste avec Track.emissions(piste,
duration, now) où `piste` est déjà extraite du dict d'animation
(current_animation.get(clé)) — d'où le passage direct d'une liste de keyframes.

Différence assumée avec l'ancien Animation : is_time utilisait `>` strict (le
keyframe sortait au tick SUIVANT le seuil) ; Track.poll utilise `>=` (il sort
au tick où le seuil est atteint). Tolérance explicite du refactoring.
"""

from robot.sequences.track import Track

T0 = 1_000_000


def test_keyframes_fire_at_fraction_of_duration():
    track = Track.emissions([[0, 0.1], [0.5, 0.9], [1, 0.5]], 1000, T0)

    assert track.poll(T0) == 0.1            # premier keyframe (départ immédiat)
    assert track.poll(T0 + 400) is None     # avant 50 % de 1000 ms
    assert track.poll(T0 + 502) == 0.9      # keyframe à 50 %
    assert track.poll(T0 + 1002) == 0.5     # keyframe final à 100 %
    assert track.poll(T0 + 2000) is None    # plus rien après le dernier (sans boucle)


def test_first_keyframe_waits_for_start_delay():
    track = Track.emissions([[0.5, 0.9]], 1000, T0)

    assert track.poll(T0 + 100) is None     # 0.5 × 1000 ms pas encore atteint
    assert track.poll(T0 + 501) == 0.9
    assert track.poll(T0 + 5000) is None     # piste épuisée


def test_empty_track_has_no_data():
    # Piste absente (clé non fournie par le JSON) ou vide -> has_data False.
    # L'extraction par clé vit maintenant dans AnimationManager (.get) : Track
    # reçoit directement None ou [].
    assert Track.emissions(None, 1000, T0).has_data is False
    assert Track.emissions([], 1000, T0).has_data is False


def test_wheels_values_pass_through():
    track = Track.emissions([[0, [0.6, -0.6]], [1, [0, 0]]], 30000, T0)

    assert track.poll(T0) == [0.6, -0.6]
    assert track.poll(T0 + 30001) == [0, 0]
