"""Enregistreur des épreuves de la sim (lot fiabilité des épreuves, 16/11) — machines/sim/capture_topics.py
et captures.sh.

Tout ce qui se teste SANS ROS : format des lignes, sentinelles PRET / ECHEC / FIN, lecture
ponctuelle (fraîcheur, valeur attendue), extraction au format de `ros2 topic echo --field`, arrêt
propre sur SIGTERM (rien de perdu), et la bibliothèque bash (trap EXIT de l'épreuve GARDÉ — celui
de validate-catalogue efface un dossier temporaire de data/). Valeurs attendues GRAVÉES.
"""
import importlib.util
import json
import os
import pathlib
import re
import signal
import subprocess
import sys
import textwrap
import time

import pytest

SIM = pathlib.Path(__file__).resolve().parents[4] / "machines" / "sim"
_spec = importlib.util.spec_from_file_location("capture_topics", SIM / "capture_topics.py")
ct = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ct)


# --- Format ------------------------------------------------------------------------------

def test_lire_spec_valeurs_gravees():
    assert ct.lire_spec("/didier/route_speed=theatre_interfaces/msg/StringTime", "journal") == \
        ct.Spec("/didier/route_speed", "theatre_interfaces/msg/StringTime", "journal", False)
    assert ct.lire_spec("/didier/route_state=theatre_interfaces/msg/StringTime,latche", "dernier") == \
        ct.Spec("/didier/route_state", "theatre_interfaces/msg/StringTime", "dernier", True)


@pytest.mark.parametrize("texte", [
    "didier/route_speed=theatre_interfaces/msg/StringTime",     # nom relatif : la CLI le mettait à la racine
    "/didier/route_speed",                                       # pas de type
    "/didier/route_speed=StringTime",                            # type incomplet
    "/didier/route_speed=theatre_interfaces/msg/StringTime,best_effort",   # option inconnue
])
def test_lire_spec_refuse(texte):
    with pytest.raises(ValueError):
        ct.lire_spec(texte, "journal")


def test_lire_spec_refuse_un_mode_inconnu():
    with pytest.raises(ValueError):
        ct.lire_spec("/a/b=p/msg/T", "tout")


def test_nom_fichier_grave():
    assert ct.nom_fichier("/didier/rehearsal/chat_fault") == "didier__rehearsal__chat_fault.json"
    assert ct.nom_fichier("/clock") == "clock.json"


def test_ligne_jsonl_gravee():
    assert ct.ligne_jsonl("/didier/route_speed", 1763312345.1234567, {"msg": "0", "time": 0, "anim": False}) == \
        '{"stamp": 1763312345.123457, "topic": "/didier/route_speed", ' \
        '"payload": {"msg": "0", "time": 0, "anim": false}}\n'


def test_ligne_jsonl_garde_les_accents_et_les_guillemets():
    ligne = ct.ligne_jsonl("/didier/chat_instruction", 1.0, {"msg": '"Un vélo cadenassé"'})
    assert ligne == '{"stamp": 1.0, "topic": "/didier/chat_instruction", "payload": {"msg": "\\"Un vélo cadenassé\\""}}\n'


@pytest.mark.parametrize("valeur,texte", [
    ('"Tu vois"', '"Tu vois"'),          # chaîne brute, comme --field msg
    ("", ""),
    (0.25, "0.25"),
    (-0.0, "-0.0"),
    (3, "3"),
    (True, "true"),
    ({"x": 1, "a": [1, 2]}, '{"a": [1, 2], "x": 1}'),
])
def test_texte_valeur(valeur, texte):
    assert ct.texte_valeur(valeur) == texte


def test_champ_chemin_pointe():
    odom = {"pose": {"pose": {"position": {"x": 12.5, "y": 0.0}}}}
    assert ct.champ(odom, "pose.pose.position.x") == 12.5
    with pytest.raises(KeyError):
        ct.champ(odom, "pose.twist")


# --- Enregistreur (fichiers) ----------------------------------------------------------------

class Horloge:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def test_journal_vide_a_chaque_ligne(tmp_path):
    enr = ct.Enregistreur(tmp_path, horloge=Horloge(1000.0))
    enr.journal("/didier/route_speed", {"msg": "0"})
    # Lu AVANT fermer() : la ligne est déjà sur disque (flush à chaque message).
    assert (tmp_path / "journal.jsonl").read_text(encoding="utf-8") == \
        '{"stamp": 1000.0, "topic": "/didier/route_speed", "payload": {"msg": "0"}}\n'
    enr.fermer()


def test_sentinelles_pret_echec_fin(tmp_path):
    h = Horloge(1000.0)
    enr = ct.Enregistreur(tmp_path, horloge=h)
    assert not (tmp_path / "PRET").exists()
    enr.marquer_pret({"/didier/route_speed": {"apparies": 1, "editeurs": 1}})
    assert (tmp_path / "PRET").read_text(encoding="utf-8") == \
        '{"stamp": 1000.0, "topics": {"/didier/route_speed": {"apparies": 1, "editeurs": 1}}}\n'
    enr.journal("/a", {"msg": "1"})
    enr.journal("/a", {"msg": "2"})
    enr.dernier("/b", {"x": 1})
    h.t = 1001.5
    enr.fermer()
    assert (tmp_path / "FIN").read_text(encoding="utf-8") == '{"comptes": {"/a": 2, "/b": 1}, "stamp": 1001.5}\n'
    enr.fermer()   # idempotent
    assert ct.main(["verifier-fin", "--dossier", str(tmp_path)]) == 0


def test_un_nouvel_enregistreur_efface_les_sentinelles_d_avant(tmp_path):
    for nom in ("PRET", "ECHEC", "FIN"):
        (tmp_path / nom).write_text("vieux", encoding="utf-8")
    ct.Enregistreur(tmp_path)
    assert not [n for n in ("PRET", "ECHEC", "FIN") if (tmp_path / n).exists()]
    assert ct.main(["verifier-fin", "--dossier", str(tmp_path)]) == 1


def test_echec_dit_ce_qui_manque(tmp_path):
    enr = ct.Enregistreur(tmp_path)
    enr.marquer_echec({"/didier/x": {"apparies": 0, "editeurs": 1}}, "non apparié(s) en 45 s : /didier/x")
    assert json.loads((tmp_path / "ECHEC").read_text(encoding="utf-8")) == \
        {"raison": "non apparié(s) en 45 s : /didier/x", "topics": {"/didier/x": {"apparies": 0, "editeurs": 1}}}


def test_dernier_n_ecrit_qu_au_plus_une_fois_par_periode_mais_ne_perd_jamais_la_derniere(tmp_path):
    convertis = []
    enr = ct.Enregistreur(tmp_path, horloge=Horloge(5.0))
    conv = lambda m: convertis.append(m) or {"x": m}
    enr.dernier("/didier/ground_truth/odom", 1, conv)
    enr.dernier("/didier/ground_truth/odom", 2, conv)   # dans la période : en attente, pas converti
    enr.dernier("/didier/ground_truth/odom", 3, conv)
    assert convertis == [1]
    enr.fermer()                                         # l'attente est écrite à l'arrêt
    assert convertis == [1, 3]
    assert json.loads((tmp_path / "dernier" / "didier__ground_truth__odom.json").read_text(encoding="utf-8")) == \
        {"stamp": 5.0, "topic": "/didier/ground_truth/odom", "payload": {"x": 3}}


def test_etat_pret_exige_un_editeur_apparie_et_tous_ceux_du_graphe():
    assert ct.etat_pret({"/a": (1, 1), "/b": (2, 2)}) == (True, [])
    assert ct.etat_pret({"/a": (1, 1), "/b": (1, 2)}) == (False, ["/b"])     # découverte inachevée
    assert ct.etat_pret({"/a": (0, 0)}) == (False, ["/a"])                   # aucun éditeur : le banc est faux
    assert ct.etat_pret({"/b": (0, 1), "/a": (0, 0)}) == (False, ["/a", "/b"])


# --- Lecture ponctuelle et extraction ----------------------------------------------------------

def _dernier(dossier, topic, stamp, payload):
    (dossier / "dernier").mkdir(parents=True, exist_ok=True)
    (dossier / "dernier" / ct.nom_fichier(topic)).write_text(
        json.dumps({"stamp": stamp, "topic": topic, "payload": payload}), encoding="utf-8")


def test_lire_rend_une_valeur_recue_apres_l_appel_seulement(tmp_path):
    _dernier(tmp_path, "/didier/cmd_vel_follow", 100.0, {"linear": {"x": 0.4}})
    assert ct.lire_dernier(tmp_path, "/didier/cmd_vel_follow", "linear.x", 99.0, None, 0) == "0.4"
    t0 = time.monotonic()
    assert ct.lire_dernier(tmp_path, "/didier/cmd_vel_follow", "linear.x", 101.0, None, 0.2) is None   # périmée
    assert time.monotonic() - t0 >= 0.2                                                                # a attendu


def test_lire_un_etat_latche_a_tout_age_et_attend_la_valeur(tmp_path):
    _dernier(tmp_path, "/didier/route_state", 1.0, {"msg": "off"})
    assert ct.lire_dernier(tmp_path, "/didier/route_state", "msg", None, None, 0) == "off"
    assert ct.lire_dernier(tmp_path, "/didier/route_state", "msg", None, "on", 0.1) is None
    assert ct.lire_dernier(tmp_path, "/didier/route_state", "msg", None, "off", 0) == "off"


def test_lire_sans_fichier_ou_champ_absent_rend_none(tmp_path):
    assert ct.lire_dernier(tmp_path, "/didier/absent", "msg", None, None, 0) is None
    _dernier(tmp_path, "/didier/x", 1.0, {"msg": "a"})
    assert ct.lire_dernier(tmp_path, "/didier/x", "data", None, None, 0) is None


def test_lire_en_ligne_de_commande(tmp_path, capsys):
    _dernier(tmp_path, "/didier/ground_truth/odom", time.time() + 60, {"pose": {"pose": {"position": {"x": 131.25}}}})
    assert ct.main(["lire", "--dossier", str(tmp_path), "--topic", "/didier/ground_truth/odom",
                    "--champ", "pose.pose.position.x", "--delai", "0"]) == 0
    assert capsys.readouterr().out == "131.25\n"
    assert ct.main(["lire", "--dossier", str(tmp_path), "--topic", "/didier/ground_truth/odom",
                    "--champ", "pose.pose.position.x", "--delai", "0", "--apres", str(time.time() + 120)]) == 1


def test_extraire_donne_les_memes_lignes_que_la_cli_et_les_memes_comptes_v_r3(tmp_path):
    """Les comptes de V-R3 (grep inchangés) sur l'extraction d'un journal : valeurs gravées.
    3 lubies (3 consignes posées, 3 levées), 2 pannes chat + 2 pass, 2 route_speed « 0 »."""
    enr = ct.Enregistreur(tmp_path)
    I, F, S = "/didier/chat_instruction", "/didier/rehearsal/chat_fault", "/didier/route_speed"
    for topic, msg in [(S, "1.0"), (I, '"Le grand hangar est ton usine natale."'), (S, "0"), (S, "0.6"),
                       (F, '{"op": "delay", "params": {"delay_ms": 6000}, "until_ms": 40000}'),
                       (I, '""'), (I, '"Trois poubelles de tri."'), (S, "0"), (S, "0.0"), (I, '""'),
                       (F, '{"op": "pass", "params": {}, "until_ms": null}'), (I, '"Un vélo cadenassé."'),
                       (F, '{"op": "mute", "params": {}, "until_ms": 20000}'), (I, '""'),
                       (F, '{"op": "pass", "params": {}, "until_ms": null}'), (S, "0.9")]:
        enr.journal(topic, {"msg": msg, "time": 0, "anim": False})
    enr.fermer()
    for topic, nom in [(I, "instruction.txt"), (F, "chat_fault.txt"), (S, "route_speed.txt")]:
        (tmp_path / nom).write_text("".join(t + "\n" for t in ct.extraire(tmp_path, topic, "msg")), encoding="utf-8")
    assert (tmp_path / "route_speed.txt").read_text(encoding="utf-8") == "1.0\n0\n0.6\n0\n0.0\n0.9\n"

    def sh(commande):
        return subprocess.run(["bash", "-c", commande], cwd=tmp_path, capture_output=True, text=True).stdout.strip()
    # Les commandes de validate-rehearsal-chantiers.sh, telles quelles.
    assert sh("grep -c '^0$' route_speed.txt") == "2"
    assert sh("""grep '^"' instruction.txt | grep -vc '^""$'""") == "3"
    assert sh("""grep -c '^""$' instruction.txt""") == "3"
    assert sh("""grep -c '"op": "pass"' chat_fault.txt""") == "2"
    assert sh("""grep -c '"op": "' chat_fault.txt""") == "4"


# --- Attente de PRÊT et arrêt sur signal -----------------------------------------------------

def test_attendre_pret(tmp_path):
    assert ct.attendre_pret(tmp_path, os.getpid(), 0.2) == 2           # vivant, rien : délai
    (tmp_path / "ECHEC").write_text("{}", encoding="utf-8")
    assert ct.attendre_pret(tmp_path, os.getpid(), 5) == 1             # échec écrit : tout de suite
    (tmp_path / "ECHEC").unlink()
    mort = subprocess.Popen([sys.executable, "-c", "pass"])
    mort.wait()
    assert ct.attendre_pret(tmp_path, mort.pid, 5) == 1                # enregistreur mort
    (tmp_path / "PRET").write_text("{}", encoding="utf-8")
    assert ct.attendre_pret(tmp_path, os.getpid(), 0) == 0


def test_un_zombie_n_est_pas_vivant():
    zombie = subprocess.Popen([sys.executable, "-c", "pass"])
    for _ in range(100):                     # mort, pas encore attendu : zombie
        if not ct._vivant(zombie.pid):
            break
        time.sleep(0.05)
    assert ct._vivant(zombie.pid) is False
    zombie.wait()
    assert ct._vivant(os.getpid()) is True


FAUX_ENREGISTREUR = textwrap.dedent("""
    # Faux `enregistrer` (sans ROS) : la boucle et l'arrêt VRAIS de capture_topics.py, un message
    # « reçu » toutes les 10 ms ; toute autre sous-commande = la vraie.
    import importlib.util, sys, time
    spec = importlib.util.spec_from_file_location("ct", {chemin!r})
    ct = importlib.util.module_from_spec(spec); spec.loader.exec_module(ct)
    if sys.argv[1] != "enregistrer":
        sys.exit(ct.main(sys.argv[1:]))
    dossier = sys.argv[sys.argv.index("--dossier") + 1]
    arret = ct.Arret(); arret.installer()
    enr = ct.Enregistreur(dossier)
    enr.marquer_pret({{}})
    n = [0]
    def tourner():
        n[0] += 1
        enr.journal("/didier/route_speed", {{"msg": str(n[0])}})
        time.sleep(0.01)
    ct.boucle(enr, tourner, arret)
""")


@pytest.fixture
def faux_enregistreur(tmp_path):
    f = tmp_path / "faux_capture_topics.py"
    f.write_text(FAUX_ENREGISTREUR.format(chemin=str(SIM / "capture_topics.py")), encoding="utf-8")
    return f


def test_sigterm_arret_propre_rien_de_perdu(tmp_path, faux_enregistreur):
    dossier = tmp_path / "cap"
    proc = subprocess.Popen([sys.executable, str(faux_enregistreur), "enregistrer", "--dossier", str(dossier)])
    assert ct.attendre_pret(dossier, proc.pid, 10) == 0
    time.sleep(0.3)
    proc.send_signal(signal.SIGTERM)
    assert proc.wait(timeout=10) == 0
    lignes = (dossier / "journal.jsonl").read_text(encoding="utf-8").splitlines()
    fin = json.loads((dossier / "FIN").read_text(encoding="utf-8"))
    assert len(lignes) >= 5
    assert fin["comptes"] == {"/didier/route_speed": len(lignes)}         # tout ce qui est compté est écrit
    assert [json.loads(l)["payload"]["msg"] for l in lignes] == [str(i) for i in range(1, len(lignes) + 1)]


def _bash(script, env_extra, cwd):
    env = dict(os.environ, **env_extra)
    return subprocess.run(["bash", "-c", script], env=env, cwd=cwd, capture_output=True, text=True, timeout=60)


def test_captures_sh_garde_le_trap_de_l_epreuve_et_arrete_l_enregistreur(tmp_path, faux_enregistreur):
    """validate-catalogue.sh pose `trap 'rm -rf "$TMP_DIR"' EXIT` AVANT capture_demarrer : le
    trap doit survivre (sinon un résidu dans data/, monté depuis l'arbre, serait versionné)."""
    cap = tmp_path / "cap"
    r = _bash(f"""
        trap 'echo NETTOYAGE-DE-L-EPREUVE' EXIT
        source {SIM / 'captures.sh'}
        capture_demarrer essai --journal /didier/route_speed=theatre_interfaces/msg/StringTime
        sleep 0.2
        echo "PID=$CAP_PID"
        exit 0
    """, {"CAPTURE_PY": str(faux_enregistreur), "CAPTURE_DIR": str(cap)}, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"  captures : {cap} (enregistreur prêt" in r.stdout
    assert r.stdout.rstrip().endswith("NETTOYAGE-DE-L-EPREUVE")
    pid = int(re.search(r"PID=(\d+)", r.stdout).group(1))
    assert not ct._vivant(pid)                                     # pas d'orphelin
    assert (cap / "FIN").exists()


def test_captures_sh_arreter_signale_un_enregistreur_mort(tmp_path, faux_enregistreur):
    r = _bash(f"""
        source {SIM / 'captures.sh'}
        capture_demarrer essai --journal /didier/route_speed=theatre_interfaces/msg/StringTime
        kill -KILL $CAP_PID; sleep 0.2
        capture_arreter && echo VALIDE || echo INVALIDE
    """, {"CAPTURE_PY": str(faux_enregistreur), "CAPTURE_DIR": str(tmp_path / "cap")}, tmp_path)
    assert "MESURE INVALIDE" in r.stdout and r.stdout.rstrip().endswith("INVALIDE")


def test_captures_sh_pas_pret_est_une_precondition(tmp_path):
    faux = tmp_path / "jamais_pret.py"
    faux.write_text(textwrap.dedent(f"""
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location("ct", {str(SIM / 'capture_topics.py')!r})
        ct = importlib.util.module_from_spec(spec); spec.loader.exec_module(ct)
        if sys.argv[1] != "enregistrer":
            sys.exit(ct.main(sys.argv[1:]))
        enr = ct.Enregistreur(sys.argv[sys.argv.index("--dossier") + 1])
        enr.marquer_echec({{"/didier/x": {{"apparies": 0, "editeurs": 0}}}}, "non apparié(s) en 45 s : /didier/x")
        enr.fermer(); sys.exit(3)
    """), encoding="utf-8")
    r = _bash(f"""
        source {SIM / 'captures.sh'}
        capture_demarrer essai --journal /didier/x=theatre_interfaces/msg/StringTime
        echo NE-DOIT-PAS-CONTINUER
    """, {"CAPTURE_PY": str(faux), "CAPTURE_DIR": str(tmp_path / "cap")}, tmp_path)
    assert r.returncode == 2
    assert "PRÉCONDITION : l'enregistreur des captures n'est pas prêt" in r.stdout
    assert "non apparié(s) en 45 s : /didier/x" in r.stdout
    assert "NE-DOIT-PAS-CONTINUER" not in r.stdout


# --- Contrat des épreuves ---------------------------------------------------------------------

def _code(p):
    """Lignes de code d'un script bash, hors commentaires."""
    return [l for l in p.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#")]


def test_aucune_epreuve_ne_mesure_avec_la_cli_echo():
    """Plus aucun `ros2 topic echo` dans le CODE des épreuves de la sim (les commentaires qui
    racontent pourquoi restent)."""
    fautes = [f"{p.name}: {l.strip()}" for p in sorted(SIM.glob("validate-*.sh")) for l in _code(p)
              if "ros2 topic echo" in l]
    assert fautes == []


@pytest.mark.parametrize("script,epreuve", [
    ("validate-rehearsal-chantiers.sh", "vr3"), ("validate-rehearsal-faults.sh", "vr2"),
    ("validate-rehearsal-route.sh", "vr1"), ("validate-catalogue.sh", "catalogue")])
def test_les_epreuves_sourcent_la_bibliotheque_et_la_demarrent(script, epreuve):
    code = "\n".join(_code(SIM / script))
    assert "source /home/ros2_ws/captures.sh" in code
    assert f"capture_demarrer {epreuve} " in code
    assert "capture_arreter ||" in code                    # enregistreur mort = mesure invalide, pas un verdict


def test_v_r3_garde_ses_21_verdicts_et_ses_captures():
    src = (SIM / "validate-rehearsal-chantiers.sh").read_text(encoding="utf-8")
    assert len(re.findall(r'^verdict "', src, re.M)) == 21
    for topic in ("$NS/chat_instruction=theatre_interfaces/msg/StringTime",
                  "$NS/rehearsal/chat_fault=theatre_interfaces/msg/StringTime",
                  "$NS/route_speed=theatre_interfaces/msg/StringTime"):
        assert f"--journal {topic}" in src
    assert "--dernier $NS/route_state=theatre_interfaces/msg/StringTime,latche" in src
    # Les captures sont arrêtées (FIN) AVANT d'être relues.
    assert src.index("capture_arreter ||") < src.index("capture_extraire $NS/chat_instruction msg")


def test_compose_monte_l_enregistreur_dans_monde_en_lecture_seule():
    compose = (SIM / "docker-compose.yml").read_text(encoding="utf-8")
    assert "      - ./capture_topics.py:/home/ros2_ws/capture_topics.py:ro\n" in compose
    assert "      - ./captures.sh:/home/ros2_ws/captures.sh:ro\n" in compose


def test_la_fumee_donne_un_dossier_de_captures_et_le_copie_dans_ses_journaux():
    sh = (SIM / "fumee.sh").read_text(encoding="utf-8")
    corps = sh[sh.index("\nlancer_validation() {"):sh.index("\nlancer_corps() {")]
    assert 'docker exec -e CAPTURE_DIR="$cap"' in corps
    assert 'copier_captures "$id" "$cap"' in corps
    assert "vr3-capture" not in sh and "vja1" not in sh
