"""Contrats du node, lus dans les VRAIS fichiers (le node lui-même importe
rclpy : il n'est jamais importé sur l'hôte)."""
import ast
import pathlib
import re

import pytest

PKG = pathlib.Path(__file__).resolve().parents[1]
MONO = PKG.parents[1]
LEGACY = MONO / "legacy"
NODE = PKG / "didier_jeu" / "jeu_node.py"


def _sources():
    return {p.name: p.read_text(encoding="utf-8") for p in sorted((PKG / "didier_jeu").glob("*.py"))}


def test_aucun_twist_dans_le_package():
    """SÉCURITÉ (spec §1) : le sélecteur n'a AUCUN éditeur de Twist ; il
    demande au régisseur. Aucun module ne mentionne Twist ni un cmd_vel."""
    for nom, src in _sources().items():
        code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
        assert "Twist" not in re.sub(r'""".*?"""', "", code, flags=re.S), nom
        assert "cmd_vel" not in code, nom


def test_garde_fou_domaine_avant_rclpy_init():
    """T7 : refus hors 43 AVANT rclpy.init (rien n'est créé sur le domaine 42)."""
    tree = ast.parse(NODE.read_text(encoding="utf-8"))
    main = next(f for f in tree.body if isinstance(f, ast.FunctionDef) and f.name == "main")
    appels = [ast.unparse(n.value.func) for n in main.body
              if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)]
    assert appels[0] == "check_domain"
    src = ast.unparse(main)
    assert src.index("check_domain(os.environ)") < src.index("rclpy.init(")
    assert "from robot_rehearsal.contracts import" in NODE.read_text(encoding="utf-8")


def test_garde_fou_domaine_refuse_hors_43():
    """Le test existant de robot_rehearsal, réutilisé sur la fonction importée par le node."""
    from robot_rehearsal.contracts import SIM_DOMAIN_ID, check_domain
    assert SIM_DOMAIN_ID == 43
    assert check_domain({"ROS_DOMAIN_ID": "43"}) == 43
    for env in ({}, {"ROS_DOMAIN_ID": "42"}, {"ROS_DOMAIN_ID": "0"}, {"ROS_DOMAIN_ID": "abc"}):
        with pytest.raises(RuntimeError) as exc:
            check_domain(env)
        # Message hérité de robot_rehearsal (« robot_rehearsal refuse de démarrer ») :
        # connu, assumé — une seule définition du garde-fou.
        assert "42 est le vrai robot" in str(exc.value)


def test_topic_look_egal_a_celui_de_gaze_follower():
    src = (LEGACY / "dadou_robot_ros" / "robot" / "nodes" / "gaze_follower_node.py").read_text(encoding="utf-8")
    assert re.search(r'^LOOK_TOPIC = "look"$', src, re.M)
    assert re.search(r'^LOOK_TOPIC = "look"$', NODE.read_text(encoding="utf-8"), re.M)


def test_topics_de_la_reflexion_egaux_au_contrat_vision():
    src = (LEGACY / "dadou_vision_ros" / "vision" / "ai" / "reflection_contract.py").read_text(encoding="utf-8")
    node = NODE.read_text(encoding="utf-8")
    for nom, valeur in (("SITUATION_TOPIC", "chat_situation"), ("MISSION_STATE_TOPIC", "mission_state")):
        assert f'{nom} = "{valeur}"' in src and f'{nom} = "{valeur}"' in node


def test_le_regisseur_ecoute_ce_que_le_selecteur_publie():
    from robot_rehearsal import contracts
    from theatre_contrats import topics
    launch = (MONO / "packages" / "robot_rehearsal" / "launch" / "rehearsal.launch.py").read_text(encoding="utf-8")
    assert f'("{contracts.CHAT_MOVE_TOPIC}", "{topics.JEU_CHAT_MOVE}")' in launch


def test_import_robot_limite_au_journal_pur():
    """Seule dépendance vers robot.* : robot.diagnostic.journal (pur, stdlib)."""
    for nom, src in _sources().items():
        for m in re.finditer(r"^\s*(?:from|import)\s+(robot\.[\w.]*|robot)\b", src, re.M):
            assert m.group(1) == "robot.diagnostic.journal", (nom, m.group(0))


def test_modules_purs_sans_ros():
    """Toute la logique s'importe sans ROS (seul jeu_node importe rclpy, dans main)."""
    for nom, src in _sources().items():
        if nom == "jeu_node.py":
            continue
        assert "rclpy" not in src, nom


def test_topic_de_la_parole_entendue_egal_a_celui_de_chat_node():
    src = (LEGACY / "dadou_vision_ros" / "vision" / "nodes" / "chat_node.py").read_text(encoding="utf-8")
    assert re.search(r'^CHAT_TRANSCRIPT_TOPIC = "chat_transcript"$', src, re.M)
    assert re.search(r'^TRANSCRIPT_TOPIC = "chat_transcript"$', NODE.read_text(encoding="utf-8"), re.M)
