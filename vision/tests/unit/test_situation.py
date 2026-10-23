"""Tests de vision/ai/situation.py — textes et seuils gravés en dur."""
from vision.ai.reflection_contract import SITUATION_MAX_CHARS
from vision.ai.situation import (SituationBoard, decode_poi_event, decode_speed,
                                 decode_transcript_line)


def _board_with_person(azimuth, height, now=100.0):
    board = SituationBoard()
    board.update_person(azimuth, height, 0.9, now)
    return board


def test_positions_gravees():
    # Frontières : -0,33 et +0,33 exclus des côtés.
    cases = [(-0.34, "à ta gauche"), (-0.33, "devant toi"), (0.0, "devant toi"),
             (0.33, "devant toi"), (0.34, "à ta droite"), (1.0, "à ta droite")]
    for azimuth, where in cases:
        text = _board_with_person(azimuth, 0.5).perception_text(100.0)
        assert text == f"Une personne est {where}, à quelques pas.", azimuth


def test_distances_gravees():
    cases = [(0.61, "tout près"), (0.6, "à quelques pas"), (0.3, "à quelques pas"),
             (0.29, "loin"), (0.0, "loin")]
    for height, dist in cases:
        text = _board_with_person(0.0, height).perception_text(100.0)
        assert text == f"Une personne est devant toi, {dist}.", height


def test_personne_perimee_apres_2_s():
    board = _board_with_person(0.0, 0.5, now=100.0)
    assert board.perception_text(102.0).startswith("Une personne est")
    assert board.perception_text(102.1) == "Personne en vue."


def test_route_et_poi():
    board = SituationBoard()
    assert board.perception_text(0.0) == "Personne en vue."
    board.set_route("on")
    # Revue adversariale du 23/10 (I2/M3) : route "on" à vitesse INCONNUE ne
    # dit plus « Tu marches. » (phrase omise) ; il faut une vitesse > 0.
    assert board.perception_text(0.0) == "Personne en vue."
    board.set_speed(0.5)
    assert board.perception_text(0.0) == "Personne en vue. Tu marches."
    board.set_route("off")
    assert board.perception_text(0.0) == "Personne en vue. Tu es arrêté."
    board.set_route("n'importe quoi")  # état inconnu : phrase omise
    assert board.perception_text(0.0) == "Personne en vue."
    board.set_poi("boulangerie", "enter", 10.0)
    assert board.perception_text(40.0) == "Personne en vue. Tu es devant : boulangerie."
    assert board.perception_text(40.1) == "Personne en vue."   # enter > 30 s
    board.set_poi("boulangerie", "exit", 20.0)
    assert board.perception_text(25.0) == "Personne en vue."   # exit depuis


def test_marche_exige_route_on_et_vitesse_positive():
    # Revue adversariale du 23/10 (I2/M3) : le régisseur arrête Didier par
    # route_speed 0 en laissant la route "on" — il se croyait en marche.
    board = SituationBoard()
    cas = [  # (route, vitesse, moving, phrase de route attendue)
        ("on", 0.5, True, " Tu marches."),
        ("on", 0.0, False, " Tu es arrêté."),
        ("on", None, True, ""),           # vitesse inconnue : omise du tableau, mais
                                          # comptée EN MARCHE pour la parole (prudence)
        ("off", 0.5, False, " Tu es arrêté."),
        ("off", None, False, " Tu es arrêté."),
        ("?", 0.0, False, " Tu es arrêté."),
        ("?", 0.5, False, ""),
    ]
    for route, speed, moving, phrase in cas:
        board.set_route(route)
        board.set_speed(speed)
        assert board.moving() is moving, (route, speed)
        assert board.perception_text(0.0) == "Personne en vue." + phrase, (route, speed)


def test_decode_speed_calque_sur_route_driver():
    # Même lecture que le consommateur réel (route_driver : JSON sinon brut,
    # float(), non fini refusé, borné à [0, 1]).
    assert decode_speed("0.5") == 0.5
    assert decode_speed("1") == 1.0
    assert decode_speed("0") == 0.0
    assert decode_speed('"0.25"') == 0.25      # chaîne JSON
    assert decode_speed("1.7") == 1.0          # borné
    assert decode_speed("-0.1") == 0.0
    for bad in ("NaN", "Infinity", "nope", "", None, "[1]", "null"):
        assert decode_speed(bad) is None, bad


def test_poi_exit_dun_autre_poi_ne_masque_pas():
    board = SituationBoard()
    board.set_poi("pont", "enter", 10.0)
    board.set_poi("boulangerie", "enter", 12.0)
    board.set_poi("boulangerie", "exit", 13.0)
    assert board.perception_text(14.0) == "Personne en vue. Tu es devant : pont."


def test_compose_ordre_et_sections_gravees():
    board = _board_with_person(-0.5, 0.7, now=100.0)
    board.set_route("on")
    board.set_speed(0.5)
    board.set_reflection("Une dame en rouge sourit.", "Demande-lui le chemin.", 98.0)
    text = board.compose(100.0, "Mission : trouver le paradis.")
    assert text == (
        "[Perception] Une personne est à ta gauche, tout près. Tu marches.\n"
        "[Direction pour tes prochaines répliques] Demande-lui le chemin.\n"
        "[Mission] Mission : trouver le paradis.\n"
        "[Ce que tu as compris, il y a 2 s] Une dame en rouge sourit.")


def test_sections_perimees_omises():
    board = SituationBoard()
    board.set_reflection("Situation.", "Direction.", 0.0)
    assert "[Ce que tu as compris, il y a 30 s]" in board.compose(30.0, "")
    out = board.compose(30.1, "")
    assert "compris" not in out and "[Direction" in out
    assert "[Direction" in board.compose(60.0, "")
    assert board.compose(60.1, "") == "[Perception] Personne en vue."


def test_direction_nulle_ne_reinitialise_pas():
    board = SituationBoard()
    board.set_reflection("S1", "D1", 0.0)
    board.set_reflection("S2", None, 10.0)
    out = board.compose(10.0, "")
    assert "S2" in out and "S1" not in out and "D1" in out
    board.set_reflection(None, "", 11.0)
    assert "S2" in board.compose(11.0, "")


def test_plafonds_par_section_et_total():
    board = _board_with_person(0.0, 0.5, now=0.0)
    board.set_reflection("a" * 500, "b" * 500, 0.0)
    text = board.compose(0.0, "m" * 2000)
    lines = text.split("\n")
    # Ordre de PRIORITÉ (23/10) : perception, direction, mission, puis
    # « compris » dans le reste. Perception = 57 car. ; reste pour « compris » :
    # 700 - 57 - 220 - 260 - 3 sauts de ligne = 160 (< son plafond de 200).
    assert lines[0] == "[Perception] Une personne est devant toi, à quelques pas."
    assert len(lines[1]) == 220 and lines[1].startswith("[Direction") and lines[1].endswith("…")
    assert len(lines[2]) == 260 and lines[2].startswith("[Mission] mmm") and lines[2].endswith("…")
    assert len(lines[3]) == 160 and lines[3].startswith("[Ce que tu as compris")
    assert len(text) == 700 == SITUATION_MAX_CHARS


def test_perception_plafonnee_a_160():
    board = SituationBoard()
    board.set_poi("p" * 400, "enter", 0.0)
    line = board.compose(0.0, "").split("\n")[0]
    assert len(line) == 160 and line.endswith("…")


def test_decode_transcript_line():
    assert decode_transcript_line('{"role": "david", "text": " Salut ", "t_ms": 5}') == {
        "role": "david", "text": "Salut"}
    assert decode_transcript_line('{"role": "didier", "text": "Oui"}') == {
        "role": "didier", "text": "Oui"}
    for bad in ('{"role": "passant", "text": "x"}', '{"role": "david", "text": "  "}',
                '{"role": "david"}', "pas du json", "[1]", None, '"x"'):
        assert decode_transcript_line(bad) is None


def test_decode_poi_event():
    assert decode_poi_event('{"poi": "pont", "event": "enter", "distance": 1.5}') == ("pont", "enter")
    assert decode_poi_event('{"poi": "pont", "event": "exit"}') == ("pont", "exit")
    for bad in ('{"poi": "", "event": "enter"}', '{"poi": "pont", "event": "x"}',
                '{"event": "enter"}', "nope", "3", None):
        assert decode_poi_event(bad) is None


def test_compris_omis_faute_de_place_jamais_la_mission():
    # Perception + direction + mission pleines : « compris » se fait rogner,
    # la mission reste entière (défaut vu au banc réel du 23/10).
    board = _board_with_person(0.0, 0.5, now=0.0)
    board.set_reflection("a" * 500, "b" * 500, 0.0)
    text = board.compose(0.0, "Mission : trouver le paradis. Dernière indication : après le pont.")
    assert "[Mission] Mission : trouver le paradis. Dernière indication : après le pont." in text
