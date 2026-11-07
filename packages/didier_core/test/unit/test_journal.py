"""Journal JSONL (didier_core.diagnostic.journal) — format unique boîte noire /
répétition. Valeurs gravées. Mutation (2026-10-08) : retirer le contrôle
d'ordre monotone -> test_ordre_monotone_impose ; accepter un champ manquant ->
test_champ_manquant_refuse."""
import pytest

from didier_core.diagnostic.journal import Event, JournalError, make_event, parse_line, parse_lines


def test_ligne_stable_et_triee():
    ev = make_event(1500, "director", "fault_start", {"id": "f1", "type": "pause"},
                    t_wall="2026-10-08T08:00:00.000+00:00")
    assert ev.to_line() == ('{"payload": {"id": "f1", "type": "pause"}, "source": "director", '
                            '"t_mono_ms": 1500, "t_wall": "2026-10-08T08:00:00.000+00:00", '
                            '"type": "fault_start"}')


def test_aller_retour():
    ev = make_event(42, "relay", "op", {"op": "drop", "p": 0.5}, t_wall="x")
    assert parse_line(ev.to_line()) == ev


@pytest.mark.parametrize("bad, fragment", [
    ('{"t_wall": "x", "source": "s", "type": "t", "payload": {}}', "t_mono_ms"),
    ('{"t_mono_ms": 1, "t_wall": "x", "type": "t", "payload": {}}', "source"),
    ('{"t_mono_ms": 1, "t_wall": "x", "source": "s", "type": "t", "payload": []}', "payload"),
    ('pas du json', "illisible"),
    ('[1, 2]', "objet"),
])
def test_champ_manquant_refuse(bad, fragment):
    with pytest.raises(JournalError) as exc:
        parse_line(bad)
    assert fragment in str(exc.value)


def test_make_event_valide_les_types():
    with pytest.raises(JournalError):
        make_event(True, "s", "t")
    with pytest.raises(JournalError):
        make_event(1, "", "t")
    with pytest.raises(JournalError):
        make_event(1, "s", "t", payload="non")


def test_ordre_monotone_impose():
    a = make_event(10, "s", "t", t_wall="x").to_line()
    b = make_event(20, "s", "t", t_wall="x").to_line()
    assert [e.t_mono_ms for e in parse_lines([a, "", b])] == [10, 20]
    with pytest.raises(JournalError) as exc:
        parse_lines([b, a])
    assert "ligne 2" in str(exc.value)


# --- revue adversariale du 2026-10-08 ---------------------------------------

def test_t_wall_doit_etre_une_chaine():
    for bad in ('{"t_mono_ms": 1, "t_wall": null, "source": "s", "type": "t", "payload": {}}',
                '{"t_mono_ms": 1, "t_wall": 123, "source": "s", "type": "t", "payload": {}}',
                '{"t_mono_ms": 1, "t_wall": "", "source": "s", "type": "t", "payload": {}}'):
        with pytest.raises(JournalError) as exc:
            parse_line(bad)
        assert "t_wall" in str(exc.value)


def test_egalite_de_temps_acceptee():
    a = make_event(10, "s", "t", t_wall="x").to_line()
    assert len(parse_lines([a, a])) == 2


def test_writer_monotone():
    from didier_core.diagnostic.journal import JournalWriter
    class Sink:
        def __init__(self): self.lines = []; self.flushed = 0
        def write(self, s): self.lines.append(s)
        def flush(self): self.flushed += 1
    sink = Sink(); w = JournalWriter(sink)
    w.append(make_event(5, "s", "t", t_wall="x")); w.append(make_event(5, "s", "t", t_wall="x"))
    with pytest.raises(JournalError):
        w.append(make_event(4, "s", "t", t_wall="x"))
    assert len(sink.lines) == 2 and sink.flushed == 2
