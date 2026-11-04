"""Logique « republie seulement si changé » de catalogue_node (L1c).

Le nœud lui-même (rclpy) n'est pas importé sur l'hôte : la décision vit dans
web_catalog.next_publication, pure. Les valeurs attendues sont GRAVÉES.
"""
import json

from robot_web.web_catalog import build_catalog, next_publication


def test_premiere_publication_toujours_faite():
    assert next_publication(None, '{"faces": []}') == '{"faces": []}'


def test_identique_ne_republie_pas():
    assert next_publication('{"faces": []}', '{"faces": []}') is None


def test_changement_republie_le_nouveau_json():
    assert next_publication('{"faces": []}', '{"faces": ["joie"]}') == '{"faces": ["joie"]}'


def test_catalogue_deterministe_donc_stable_entre_deux_periodes(tmp_path):
    # Si build_catalog n'était pas déterministe, le nœud republierait à chaque période.
    (tmp_path / "expressions.json").write_text('{"b": 1, "a": 2}')
    premier = json.dumps(build_catalog(tmp_path))
    assert next_publication(premier, json.dumps(build_catalog(tmp_path))) is None


def test_nouvelle_sequence_republie_puis_sa_suppression_aussi(tmp_path):
    seq = tmp_path / "sequences" / "tmp"
    seq.mkdir(parents=True)
    avant = json.dumps(build_catalog(tmp_path))
    (seq / "nouvelle.json").write_text("{}")
    pendant = next_publication(avant, json.dumps(build_catalog(tmp_path)))
    assert pendant is not None and '"nouvelle"' in pendant
    (seq / "nouvelle.json").unlink()
    assert next_publication(pendant, json.dumps(build_catalog(tmp_path))) == avant
