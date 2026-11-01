"""Tests unitaires du moteur temporel unifié Track (robot/sequences/track.py).

L'horloge n'est PAS interne à Track : chaque poll reçoit `now_ms` en argument,
donc les tests pilotent le temps sans monkeypatch. On couvre les deux
constructeurs (emissions = émettre à t ; frames = afficher jusqu'à t), la boucle
avec rebobinage multiple, la piste vide, la piste à une frame en boucle, et le
cas « deux activations dans la même fenêtre » (une seule sort par poll).
"""

from robot.sequences.track import Track

T0 = 1_000_000


# --- emissions : la keyframe [t, v] émet v à t×duration ---

def test_emissions_fire_at_fraction_of_duration():
    track = Track.emissions([[0, 0.1], [0.5, 0.9], [1, 0.5]], 1000, T0)

    assert track.poll(T0) == 0.1            # t=0 : sort dès le premier poll (>=)
    assert track.poll(T0 + 400) is None     # avant 50 %
    assert track.poll(T0 + 500) == 0.9      # exactement 500 ms -> atteint
    assert track.poll(T0 + 1000) == 0.5     # keyframe final à 100 %
    assert track.poll(T0 + 5000) is None    # pas de boucle : piste épuisée


def test_emissions_pass_through_list_values():
    track = Track.emissions([[0, [0.6, -0.6]], [1, [0, 0]]], 30000, T0)

    assert track.poll(T0) == [0.6, -0.6]
    assert track.poll(T0 + 30000) == [0, 0]


# --- frames : la keyframe [t, v] affiche v JUSQU'À t×duration ---

def test_frames_activate_until_t():
    # v0 dès 0, v1 à t0×d, v2 à t1×d.
    track = Track.frames([[0.2, "a"], [0.5, "b"], [1.0, "c"]], 1000, False, T0)

    assert track.poll(T0) == "a"            # v0 immédiat
    assert track.poll(T0 + 100) is None     # avant t0×d = 200
    assert track.poll(T0 + 200) == "b"      # t0×d
    assert track.poll(T0 + 499) is None
    assert track.poll(T0 + 500) == "c"      # t1×d
    assert track.poll(T0 + 5000) is None    # loop False : plus rien


def test_frames_loop_rewinds_each_cycle():
    track = Track.frames([[0.2, "a"], [0.5, "b"], [1.0, "c"]], 1000, True, T0)

    assert track.poll(T0) == "a"
    assert track.poll(T0 + 200) == "b"
    assert track.poll(T0 + 500) == "c"
    assert track.poll(T0 + 900) is None     # dernière frame tenue jusqu'à d
    assert track.poll(T0 + 1000) == "a"     # rebobinage à 1 cycle
    assert track.poll(T0 + 1200) == "b"


def test_frames_loop_wrap_multiple_cycles():
    # Un poll très tardif rebobine d'autant de cycles que nécessaire et ne sort
    # qu'UNE activation (l'activation 0 du cycle courant).
    track = Track.frames([[1.0, "x"]], 1000, True, T0)

    assert track.poll(T0) == "x"
    assert track.poll(T0 + 500) is None
    # 3 cycles écoulés d'un coup : start avance de 3000, une seule émission.
    assert track.poll(T0 + 3001) == "x"
    assert track.poll(T0 + 3500) is None


def test_single_frame_loop_reemits_every_cycle():
    track = Track.frames([[1.0, "solo"]], 2000, True, T0)

    assert track.poll(T0) == "solo"
    assert track.poll(T0 + 1000) is None
    assert track.poll(T0 + 2000) == "solo"  # réémission au cycle suivant
    assert track.poll(T0 + 4000) == "solo"


# --- pistes vides ---

def test_empty_track_has_no_data():
    assert Track.emissions(None, 1000, T0).has_data is False
    assert Track.emissions([], 1000, T0).has_data is False
    assert Track.frames(None, 1000, True, T0).has_data is False
    assert Track.emissions(None, 1000, T0).poll(T0 + 10_000) is None


# --- deux activations dans la même fenêtre : deux polls ---

def test_two_activations_same_window_need_two_polls():
    track = Track.emissions([[0.1, "a"], [0.2, "b"]], 1000, T0)

    # À T0+300 les deux instants (100, 200) sont dépassés, mais un seul sort par
    # poll (au tick 10 Hz, deux keyframes rapprochées sortent sur deux ticks).
    assert track.poll(T0 + 300) == "a"
    assert track.poll(T0 + 300) == "b"
    assert track.poll(T0 + 300) is None
