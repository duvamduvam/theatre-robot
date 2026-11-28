"""Lot L3a (28/11) — la bibliothèque du gabarit (spec L3 décisions 2 et 4) : inventaire, choix du
pilote, battement, diagnostics, sha, launch. Valeurs GRAVÉES en littéral."""
import sys
import types

import pytest

from conftest import PKG
from theatre_gabarit import lancement, noeud, pilotes


def test_inventaire_des_quatre_modules():
    """Règle d'émergence : 4 modules, pas un de plus sans un 2e appareil qui en a besoin."""
    modules = sorted(p.name for p in (__import__("pathlib").Path(PKG) / "theatre_gabarit").glob("*.py"))
    assert modules == ["__init__.py", "essais.py", "lancement.py", "noeud.py", "pilotes.py"]


# --- pilotes.choisir ---------------------------------------------------------------------------
FABRIQUES = {"sim": lambda: "pilote-sim", "materiel": lambda: "pilote-materiel"}


@pytest.mark.parametrize("domaine", [42, "42", 0, None, "", "abc", True])
def test_sim_hors_domaine_43_refuse(domaine):
    with pytest.raises(pilotes.PiloteRefuse) as e:
        pilotes.choisir("sim", FABRIQUES, domaine)
    assert e.value.code_sortie == 2


@pytest.mark.parametrize("domaine", [43, "43", " 43\n"])
def test_sim_en_domaine_43_accepte(domaine):
    assert pilotes.choisir("sim", FABRIQUES, domaine) == "pilote-sim"


@pytest.mark.parametrize("domaine", [42, 43, None])
def test_materiel_partout(domaine):
    assert pilotes.choisir("materiel", FABRIQUES, domaine) == "pilote-materiel"


def test_pilote_inconnu_ou_sans_fabrique_refuse():
    with pytest.raises(pilotes.PiloteRefuse, match="pilote inconnu : 'gz'"):
        pilotes.choisir("gz", FABRIQUES, 43)
    with pytest.raises(pilotes.PiloteRefuse, match="sans fabrique"):
        pilotes.choisir("materiel", {"sim": FABRIQUES["sim"]}, 42)


def test_santes():
    assert (pilotes.OK, pilotes.ABSENT, pilotes.ERREUR) == ("ok", "absent", "erreur")
    assert pilotes.sante_valide("absent") and not pilotes.sante_valide("panne")


# --- noeud : battement, diagnostics, sha -------------------------------------------------------
def test_battement_a_deux_secondes():
    b = noeud.Battement()
    # (clé, instant) -> publier ? : 1re fois oui ; même clé avant 2,0 s non ; à 2,0 s oui ;
    # clé changée oui tout de suite ; puis le compteur repart de ce changement.
    suite = [("a", 0.0), ("a", 1.0), ("a", 1.99), ("a", 2.0), ("b", 2.1), ("b", 4.0), ("b", 4.2)]
    assert [b.a_publier(c, t) for c, t in suite] == [True, False, False, True, True, False, True]
    assert noeud.PERIODE_ETAT_S == 2.0 and noeud.PERIODE_TIC_S == 0.05


ORGANE_OK = {"nom": "audio", "type": "audio", "valeur": "", "debut_ms": None, "duree_ms": None,
             "sante": "ok"}


@pytest.mark.parametrize("organes, refus, t, attendu", [
    ([ORGANE_OK], None, 50_000, (0, "ok")),
    ([ORGANE_OK], {"code": "audio_inconnu", "detail": "x", "t_ms": 40_001}, 50_000,
     (1, "ordre refusé : audio_inconnu")),
    ([ORGANE_OK], {"code": "audio_inconnu", "detail": "x", "t_ms": 40_000}, 50_000, (0, "ok")),
    ([dict(ORGANE_OK, sante="absent"), {"nom": "cut_voice", "type": "relais", "valeur": False,
                                         "sante": "erreur"}],
     {"code": "x", "detail": "", "t_ms": 49_000}, 50_000, (2, "audio absent, cut_voice erreur")),
])
def test_niveau_diagnostic(organes, refus, t, attendu):
    assert noeud.niveau_diagnostic(organes, refus, t) == attendu


def test_lire_sha(tmp_path):
    assert noeud.lire_sha(str(tmp_path / "absent")) == "dev"
    (tmp_path / "vide").write_text("\n")
    assert noeud.lire_sha(str(tmp_path / "vide")) == "dev"
    (tmp_path / "DEPLOY_SHA").write_text("7caeecbc-dirty\n")
    assert noeud.lire_sha(str(tmp_path / "DEPLOY_SHA")) == "7caeecbc-dirty"
    assert noeud.chemin_sha("sono") == "/home/ros2_ws/src/sono/conf/DEPLOY_SHA"


def test_le_module_noeud_s_importe_sans_ros():
    src = (__import__("pathlib").Path(PKG) / "theatre_gabarit" / "noeud.py").read_text(encoding="utf-8")
    debut = src[:src.index("class Battement")]
    assert "import rclpy" not in debut and "from rclpy" not in debut
    assert "use_sim_time" not in src.replace("JAMAIS use_sim_time", "")


# --- lancement ----------------------------------------------------------------------------------
class _Trace:
    def __init__(self, *args, **kw):
        self.args, self.kw = args, kw

    def __eq__(self, autre):
        return type(self) is type(autre) and (self.args, self.kw) == (autre.args, autre.kw)

    def __repr__(self):
        return f"{type(self).__name__}{self.args}{self.kw}"


def _faux_launch(monkeypatch):
    noms = {"launch.actions": ("DeclareLaunchArgument", "GroupAction"),
            "launch.substitutions": ("EnvironmentVariable", "LaunchConfiguration"),
            "launch_ros.actions": ("Node", "PushRosNamespace")}
    classes = {}
    for module, cls in noms.items():
        m = types.ModuleType(module)
        for c in cls:
            classes[c] = type(c, (_Trace,), {})
            setattr(m, c, classes[c])
        monkeypatch.setitem(sys.modules, module, m)
    for racine in ("launch", "launch_ros"):
        monkeypatch.setitem(sys.modules, racine, types.ModuleType(racine))
    return types.SimpleNamespace(**classes)


def test_groupe_appareil_namespace_absolu_et_arguments(monkeypatch):
    f = _faux_launch(monkeypatch)
    entites = lancement.groupe_appareil("sono_core", "sono_node", "sono",
                                        lancement.config_defaut("sono", "sono"))
    arguments = {e.args[0]: e.kw["default_value"] for e in entites[:3]}
    assert arguments == {"robot_name": f.EnvironmentVariable("ROBOT_NAME", default_value="didier"),
                         "pilote": "materiel",
                         "config": "/home/ros2_ws/src/sono/conf/sono.yaml"}
    (groupe,) = entites[3:]
    ns, node = groupe.args[0]
    assert ns == f.PushRosNamespace(["/", f.LaunchConfiguration("robot_name")])
    assert node == f.Node(package="sono_core", executable="sono_node", name="sono", output="screen",
                          parameters=[{"pilote": f.LaunchConfiguration("pilote"),
                                       "config": f.LaunchConfiguration("config")}])
