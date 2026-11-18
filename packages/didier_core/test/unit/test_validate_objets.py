"""Verdicts de machines/sim/validate-objets.sh (lot O1) rejoués HORS sim sur des captures
fabriquées — revue O1 du 19/11 : l'épreuve E1d acceptait un CONTACT (arrêt à 1,2-1,8 m du centre
du banc, dont l'emprise vaut 1,1 m et Didier balaie 0,5 m). On exécute le bloc python de verdicts
TEL QU'IL EST dans le script (extrait du heredoc), sur une pose d'arrêt donnée.

Mutations (doivent rougir) :
  - E1d revenu à « 1,2 <= d <= 1,8 »          -> test_e1d_contact_echoue (1,55 m passerait)
  - tolérance élargie à ± 0,6 sans jeu minimal -> test_e1d_contact_echoue (le jeu ≥ 0,2 m est la vraie
    garde ; avec ± 0,3 autour de 2,1 il coïncide avec la borne basse, 1,8)
"""
import json
import math
import pathlib
import re
import subprocess
import sys

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[4] / "machines" / "sim" / "validate-objets.sh"
BANC = (36.2, 2.496)


def _bloc_verdicts() -> str:
    """Le SECOND heredoc python du script : celui qui relit les captures et rend les verdicts."""
    blocs = re.findall(r"<<'EOF'\n(.*?)\nEOF\n", SCRIPT.read_text(encoding="utf-8"), re.S)
    assert len(blocs) == 2, "validate-objets.sh : deux heredocs python attendus (pilote, verdicts)"
    return blocs[1]


def _verdict_e1d(tmp_path, distance_m):
    """Didier arrêté à `distance_m` du centre du banc, face à lui -> ligne E1d rendue."""
    cap = tmp_path / "cap"
    cap.mkdir()
    angle = math.radians(200.0)               # arrivée depuis le sud-ouest, comme en sim
    x, y = BANC[0] + distance_m * math.cos(angle), BANC[1] + distance_m * math.sin(angle)
    cap_deg = math.degrees(math.atan2(BANC[1] - y, BANC[0] - x))
    (cap / "pilote.json").write_text(json.dumps({"e1": 100.0, "e1_fin": 130.0, "e1_pose": [x, y, cap_deg],
                                                 "e1_tableau": {}, "gestes": []}), encoding="utf-8")
    (cap / "journal.jsonl").write_text("", encoding="utf-8")
    regie = tmp_path / "regie.jsonl"
    regie.write_text("", encoding="utf-8")
    script = tmp_path / "verdicts.py"
    script.write_text(_bloc_verdicts(), encoding="utf-8")
    out = subprocess.run([sys.executable, "-I", str(script), str(cap), "/didier", str(regie)],
                         capture_output=True, text=True, timeout=30)
    lignes = [l for l in out.stdout.splitlines() if "E1d" in l]
    assert len(lignes) == 1, out.stdout + out.stderr
    return lignes[0]


@pytest.mark.parametrize("distance_m", [1.2, 1.5, 1.6, 1.79])
def test_e1d_contact_echoue(tmp_path, distance_m):
    # 1,6 m = emprise 1,1 + Didier 0,5 : contact ; en dessous de 1,8 m, moins de 0,2 m de jeu.
    ligne = _verdict_e1d(tmp_path, distance_m)
    assert ligne.lstrip().startswith("❌"), ligne
    if distance_m <= 1.6:
        assert "CONTACT" in ligne


@pytest.mark.parametrize("distance_m", [1.81, 2.1, 2.39])
def test_e1d_arret_a_distance_de_jeu_reussit(tmp_path, distance_m):
    ligne = _verdict_e1d(tmp_path, distance_m)
    assert ligne.lstrip().startswith("✅"), ligne
