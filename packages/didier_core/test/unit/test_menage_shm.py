"""Ménage SHM Fast DDS de la sim (18/11) : machines/sim/menage-shm.sh, lancé en tête des entrées
de `monde` et de `robot`. Le vrai script tourne ici sur un dossier jetable (MENAGE_SHM_DIR dans
tmp_path, JAMAIS /dev/shm) avec un faux `fastdds`. Valeurs GRAVÉES.

Défaut corrigé : un port SHM de 0 octet (créateur tué par un `docker compose down`) bloquait SANS
FIN, dans rmw_create_node, le participant qui tirait ce port — un nœud du robot manquant à chaque
démarrage de la sim (fumées du 18/11 01:04 et 01:14, 5 démarrages sur 5 au banc).
"""
import os
import pathlib
import subprocess
import time

import yaml

MONO = pathlib.Path(__file__).resolve().parents[4]
SIM = MONO / "machines" / "sim"
MENAGE = SIM / "menage-shm.sh"


def _fichier(d, nom, contenu=b"", age_s=0):
    p = d / nom
    p.write_bytes(contenu)
    if age_s:
        t = time.time() - age_s
        os.utime(p, (t, t))
    return p


def _lancer(tmp_path, shm, fastdds=True):
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    env = dict(os.environ, MENAGE_SHM_DIR=str(shm), MENAGE_FASTDDS=str(bin_ / "fastdds"))
    if fastdds:
        faux = bin_ / "fastdds"
        faux.write_text('#!/bin/bash\necho "$@" >>"' + str(tmp_path / "appels.txt") + '"\n'
                        'printf "shm.clean:\\n0 ports in use\\n3 zombie ports cleaned\\n"\n', encoding="utf-8")
        faux.chmod(0o755)
    return subprocess.run(["bash", str(MENAGE)], env=env, capture_output=True, text=True, timeout=30)


def test_seuls_les_ports_vides_de_plus_d_une_minute_sont_retires(tmp_path):
    shm = tmp_path / "shm"
    shm.mkdir()
    poison = _fichier(shm, "fastrtps_port18175", age_s=3600)
    garde = [
        _fichier(shm, "fastrtps_port18177", age_s=5),                      # vide mais RÉCENT
        _fichier(shm, "fastrtps_port7020", b"x" * 64, age_s=3600),          # vieux mais dimensionné
        _fichier(shm, "fastrtps_port7020_el", age_s=3600),                  # verrou : vide par nature
        _fichier(shm, "sem.fastrtps_port18175_mutex", b"s" * 32, age_s=3600),
        _fichier(shm, "jack_db-0", age_s=3600),                             # pas à nous
        _fichier(shm, "fastrtps_0123abcd", age_s=3600),                     # segment (fastdds s'en charge)
    ]
    p = _lancer(tmp_path, shm)
    assert p.returncode == 0, p.stderr
    assert not poison.exists()
    assert all(g.exists() for g in garde)
    lignes = p.stdout.splitlines()
    assert lignes[0].startswith("ménage SHM : port vide retiré fastrtps_port18175 (créé ")
    assert lignes[1] == ("ménage SHM : 1 port(s) vide(s) retiré(s) ; fastdds shm clean : "
                         "shm.clean: 0 ports in use 3 zombie ports cleaned ")
    assert (tmp_path / "appels.txt").read_text(encoding="utf-8") == "shm clean\n"


def test_rien_a_retirer_et_fastdds_absent_ne_fait_pas_echouer(tmp_path):
    shm = tmp_path / "shm"
    shm.mkdir()
    p = _lancer(tmp_path, shm, fastdds=False)
    assert p.returncode == 0
    assert p.stdout == "ménage SHM : 0 port(s) vide(s) retiré(s) ; fastdds introuvable, zombies non nettoyés\n"


def test_dossier_absent_ne_fait_pas_echouer(tmp_path):
    p = _lancer(tmp_path, tmp_path / "absent")
    assert p.returncode == 0
    assert p.stdout.startswith("ménage SHM : 0 port(s) vide(s) retiré(s) ; ")


def _avant(texte, a, b):
    return texte.index(a) < texte.index(b)


def test_l_entree_du_robot_fait_le_menage_apres_le_refus_43_et_avant_tout_noeud():
    s = (SIM / "robot" / "entree.sh").read_text(encoding="utf-8")
    appel = "\nbash /home/ros2_ws/sim/menage-shm.sh\n"
    assert appel in s
    assert _avant(s, "exit 2\nfi\n", appel)
    assert _avant(s, appel, "ros2 launch")
    assert _avant(s, appel, "launch-ros-in-docker.sh")


def test_l_entree_du_monde_fait_le_menage_apres_le_refus_43_et_avant_colcon():
    s = (SIM / "monde" / "entree.sh").read_text(encoding="utf-8")
    appel = "\nbash /home/ros2_ws/machines/sim/menage-shm.sh\n"
    assert appel in s
    assert _avant(s, "exit 2\nfi\n", appel)
    assert _avant(s, appel, "colcon build")
    assert _avant(s, appel, "ros2 launch")


def test_le_script_est_monte_en_lecture_seule_la_ou_les_entrees_l_appellent():
    services = yaml.safe_load((SIM / "docker-compose.yml").read_text(encoding="utf-8"))["services"]
    assert "./menage-shm.sh:/home/ros2_ws/sim/menage-shm.sh:ro" in services["robot"]["volumes"]
    assert "..:/home/ros2_ws/machines:ro" in services["monde"]["volumes"]   # machines/sim/menage-shm.sh


def test_sans_variable_fastdds_est_cherche_dans_l_installation_ros(tmp_path):
    """L'entrée du robot appelle le ménage avant de charger ROS : fastdds n'est pas dans le PATH
    (vu en sim le 18/11 : « fastdds introuvable » côté robot)."""
    shm = tmp_path / "shm"
    shm.mkdir()
    ros = tmp_path / "opt" / "ros" / "essai" / "bin"
    ros.mkdir(parents=True)
    faux = ros / "fastdds"
    faux.write_text('#!/bin/bash\necho "zombies : $@"\n', encoding="utf-8")
    faux.chmod(0o755)
    script = MENAGE.read_text(encoding="utf-8").replace('"/opt/ros/', '"' + str(tmp_path) + '/opt/ros/')
    env = {"PATH": "/usr/bin:/bin", "MENAGE_SHM_DIR": str(shm), "ROS_DISTRO": "essai"}
    p = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    assert p.stdout == "ménage SHM : 0 port(s) vide(s) retiré(s) ; fastdds shm clean : zombies : shm clean \n"
