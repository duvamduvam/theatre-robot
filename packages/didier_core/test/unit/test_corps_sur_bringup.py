"""Contrôle « corps sûr DU BRINGUP armé » de la fumée (A0-4, 21/11) : machines/sim/corps_sur_bringup.py
et son branchement dans fumee.sh.

Fumée 2026-11-20-1707 : le corps sûr du bringup s'est verrouillé seul (capteur_perdu, nœud figé
par la charge) pendant validate-namespace ; edition n°7 est tombée sur « aucun cmd_vel non nul »
sans que rien ne dise pourquoi. Valeurs GRAVÉES, jamais recalculées avec la fonction testée.
Hôte seul : ni ROS ni Docker (rclpy n'est importé que par main()).
"""
import importlib.util
import pathlib
import re
import subprocess

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[4] / "machines" / "sim"
FUMEE_SH = SCRIPTS / "fumee.sh"

_spec = importlib.util.spec_from_file_location("corps_sur_bringup", SCRIPTS / "corps_sur_bringup.py")
csb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(csb)


def etat(nom, cause="", terrain="sim"):
    return {"etat": nom, "cause": cause, "zone": "LIBRE", "d_min_m": 6.6, "terrain": terrain}


def test_bornes_gravees():
    assert csb.REARMEMENTS_MAX == 2
    assert csb.CAUSE_REARMABLE == "capteur_perdu"


@pytest.mark.parametrize("e, deja, action", [
    (etat("ARME"), 0, "arme"),
    (etat("ARME"), 2, "arme"),
    # Le nœud arme seul quand le capteur est sain : on attend (l'appelant borne l'attente).
    (etat("DEMARRAGE", "capteur_absent"), 0, "attendre"),
    (etat("DEMARRAGE", "sante_en_cours"), 0, "attendre"),
    (None, 0, "attendre"),
    # Le verrou spontané de la fumée 1707 : réarmé, deux fois au plus par épreuve.
    (etat("VERROU", "capteur_perdu"), 0, "rearmer"),
    (etat("VERROU", "capteur_perdu"), 1, "rearmer"),
    (etat("VERROU", "capteur_perdu"), 2, "rouge"),
    (etat("VERROU", "capteur_perdu"), 3, "rouge"),
    # JAMAIS réarmés par le banc : un geste ou une panne, pas la charge du PC.
    (etat("VERROU", "e_stop"), 0, "rouge"),
    (etat("VERROU", "superviseur_perdu"), 0, "rouge"),
    # Armé, mais pas la configuration de la sim : rouge.
    (etat("ARME", terrain="reel"), 0, "rouge"),
    (etat("VERROU", "capteur_perdu", terrain="reel"), 0, "rouge"),
    ({"etat": "ARME", "cause": ""}, 0, "rouge"),
])
def test_decider(e, deja, action):
    assert csb.decider(e, deja)[0] == action


# --- branchement dans fumee.sh -----------------------------------------------------------------

def corps_de(fonction):
    src = FUMEE_SH.read_text(encoding="utf-8")
    m = re.search(rf"^{fonction}\(\) \{{[^\n]*\n(.*?)^\}}", src, re.M | re.S)
    assert m, fonction
    return m.group(1)


# Toute épreuve qui fait rouler Didier (chaîne roues du bringup), et la phase qui la lance.
EPREUVES_ROULANTES = [("phase_simples", "edition"), ("phase_chantiers", "chantiers"), ("phase_a1", "a1"),
                      ("phase_objets", "objets"), ("phase_conversation", "conversation")]


@pytest.mark.parametrize("phase, epreuve", EPREUVES_ROULANTES)
def test_chaque_epreuve_roulante_exige_le_corps_sur_arme_juste_avant(phase, epreuve):
    corps = corps_de(phase)
    garde = corps.index(f"exiger_corps_sur_arme {epreuve} || return 1")
    lance = corps.index(f"lancer_validation {epreuve} ")
    assert garde < lance
    # Rien qui lance un processus ROS entre la garde et l'épreuve (seulement le relevé des verrous).
    entre = [l.strip() for l in corps[garde:lance].splitlines()[1:] if l.strip()]
    assert entre == ['local verrous; verrous="$(entrees_verrou)"']
    assert f'noter_verrous_pendant {epreuve} "$verrous"' in corps[lance:]


def test_le_corps_sur_n_est_pas_exige_avant_les_epreuves_qui_ne_roulent_pas():
    corps = corps_de("phase_simples")
    assert corps.index("exiger_corps_sur_arme edition") > corps.index("lancer_validation catalogue ")
    assert "exiger_corps_sur_arme" not in corps_de("phase_corps_sur")   # CS relance son propre nœud


def test_la_garde_rougit_l_epreuve_et_dit_l_etat():
    corps = corps_de("exiger_corps_sur_arme")
    assert "python3 /home/ros2_ws/machines/sim/corps_sur_bringup.py\"" in corps
    assert '[[ "$ligne" == "CORPS_SUR_BRINGUP arme "* ]] && return 0' in corps
    assert 'epreuve "$1" --statut rouge' in corps
    assert "NOTES+=(" in corps            # un réarmement est dit sur la page


JOURNAL_ROBOT = """\
[corps_sur_node-16] [INFO] [1] [didier.corps_sur]: configuration /home/ros2_ws/sim/corps_sur.yaml : terrain sim
[corps_sur_node-16] [INFO] [2] [didier.corps_sur]: état : {"etat": "DEMARRAGE", "cause": "capteur_absent"}
[corps_sur_node-16] [INFO] [3] [didier.corps_sur]: état : {"etat": "ARME", "cause": ""}
[corps_sur_node-16] [INFO] [4] [didier.corps_sur]: état : {"etat": "VERROU", "cause": "capteur_perdu", "d_min_m": 6.6}
[corps_sur_node-16] [INFO] [5] [didier.corps_sur]: état : {"etat": "VERROU", "cause": "capteur_perdu", "d_min_m": 6.55}
[face_sim-1] du bruit "etat": "VERROU" hors du corps sûr
[corps_sur_node-16] [INFO] [6] [didier.corps_sur]: réarmement accepté : réarmé
[corps_sur_node-16] [INFO] [7] [didier.corps_sur]: état : {"etat": "ARME", "cause": ""}
[corps_sur_node-16] [INFO] [8] [didier.corps_sur]: état : {"etat": "VERROU", "cause": "e_stop"}
"""


def test_entrees_verrou_compte_les_entrees_pas_les_lignes(tmp_path):
    """Deux ENTRÉES en VERROU (4 et 8) ; la ligne 5 (d_min qui bouge) et le bruit ne comptent pas."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    journal = tmp_path / "robot.log"
    journal.write_text(JOURNAL_ROBOT, encoding="utf-8")
    faux = bin_ / "docker"
    faux.write_text(f'#!/bin/bash\n[ "$1 $2" = "logs didier-sim-robot" ] && cat {journal}\n', encoding="utf-8")
    faux.chmod(0o755)
    script = ('conteneur_de() { echo "didier-sim-$1"; }\n' + "entrees_verrou() {\n"
              + corps_de("entrees_verrou") + "}\nentrees_verrou\n")
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                       env={"PATH": f"{bin_}:/usr/bin:/bin", "TMP": str(tmp_path)})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "2"
