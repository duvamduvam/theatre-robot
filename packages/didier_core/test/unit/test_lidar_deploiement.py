"""Lot A0-6 (spec A0 §9) : le pilote du lidar arrive sur le Pi sans aucun geste.

Valeurs GRAVÉES : identifiants de l'adaptateur relevés au banc le 23/11/2026 (`udevadm info`,
Pi 4 hors robot), commit épinglé de sllidar_ros2 (spec §9). Un changement de lidar = ce test
et la règle, dans le même commit.
"""
import pathlib
import re

import yaml

MONO = pathlib.Path(__file__).resolve().parents[4]
ROBOT = MONO / "machines" / "robot"
REGLE = ROBOT / "udev" / "99-didier-lidar.rules"
COMMIT = "34300099fadfc772965962dec837bf436706188f"


def _lignes_actives(chemin):
    return [l for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]


def test_la_regle_udev_vise_cet_adaptateur_et_pas_tout_cp210x():
    (regle,) = _lignes_actives(REGLE)
    assert regle == ('SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", '
                     'ATTRS{serial}=="6a08780ca81df111a44fc9e40f0f12f8", SYMLINK+="didier-lidar", '
                     'GROUP="dialout", MODE="0660"')


def test_la_regle_est_posee_par_ansible_dans_rules_d():
    machine = yaml.safe_load((ROBOT / "machine.yml").read_text(encoding="utf-8"))
    assert {"source": "{{ machines_dir }}/robot/udev/99-didier-lidar.rules",
            "dest": "/etc/udev/rules.d/99-didier-lidar.rules"} in machine["fichiers_etc"]
    # Le pilote n'est PAS un nœud exigé (sans capteur il meurt et se relance), le corps sûr oui.
    assert "/didier/lidar_node" not in machine["noeuds_attendus"]
    assert "/didier/corps_sur" in machine["noeuds_attendus"]


def test_le_role_recharge_udev_quand_une_regle_change():
    taches = yaml.safe_load((MONO / "deploy/roles/config-hote/tasks/main.yml").read_text(encoding="utf-8"))
    (copie,) = [t for t in taches if t["name"] == "Copy versioned /etc files"]
    assert copie["register"] == "fichiers_etc_copies"
    (recharge,) = [t for t in taches if t["name"] == "Reload udev after a rule change"]
    assert "udevadm control --reload-rules" in recharge["ansible.builtin.shell"]
    assert "udevadm trigger" in recharge["ansible.builtin.shell"]
    assert "^/etc/udev/rules.d/" in recharge["when"]
    assert taches.index(recharge) == taches.index(copie) + 1


def test_l_image_compile_le_pilote_au_commit_epingle_hors_du_workspace():
    dockerfile = (ROBOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
    assert f"ARG SLLIDAR_COMMIT={COMMIT}" in dockerfile
    assert "git clone --quiet https://github.com/Slamtec/sllidar_ros2.git /opt/lidar_ws/src/sllidar_ros2" in dockerfile
    assert "checkout --quiet ${SLLIDAR_COMMIT}" in dockerfile
    # Avant toute copie du dépôt : un commit de code ne refait pas cette couche.
    assert dockerfile.index("SLLIDAR_COMMIT=") < dockerfile.index("COPY --from=conf . ")
    assert re.search(r"^git$", (ROBOT / "packages-docker.txt").read_text(encoding="utf-8"), re.M)


def test_le_script_source_le_pilote_avant_le_workspace_de_didier():
    script = (ROBOT / "scripts" / "launch-ros-in-docker.sh").read_text(encoding="utf-8")
    assert script.index("source /opt/lidar_ws/install/setup.sh") < script.index("source /home/ros2_ws/install/setup.bash")
    assert script.index("source /opt/ros/${ROS_DISTRO}/setup.sh") < script.index("source /opt/lidar_ws/install/setup.sh")
