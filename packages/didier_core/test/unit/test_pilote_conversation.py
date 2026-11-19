"""Pilote de l'épreuve CONV (machines/sim/validate-conversation.sh) : QUAND part la phrase B.

Fumée du 19/11 08:36 (branche o0-o1-objets, CONV 6/7) : une lubie du sélecteur avait arrêté
Didier par un « hold » (route_speed 0, route_state reste on) ; le pilote comptait ce hold comme
« en marche » et a publié « Va voir la table basse » 3 s après le « repartir » du jeu — dans sa
période réfractaire déplacement (10 s) : demande refusée « trop_tot », B2 à C3 en cascade. Le
sélecteur avait raison ; le défaut était dans le pilote.

Le pilote est un python en « heredoc » du script : on en extrait les définitions (sans rien
lancer) et on rejoue faire_marcher sur une horloge et un monde factices. Valeurs GRAVÉES.
"""
import ast
import pathlib
import re
import sys
import types

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[4] / "machines" / "sim" / "validate-conversation.sh"


def _source_du_pilote() -> str:
    texte = SCRIPT.read_text(encoding="utf-8")
    m = re.search(r"python3 - \"\$CAP\" \"\$NS\" <<'EOF'\n(.*?)\nEOF\n", texte, re.S)
    assert m, "heredoc du pilote introuvable"
    return m.group(1)


def _charger_pilote(monkeypatch):
    """Définitions du pilote (imports, constantes, fonctions, classes), sans le programme."""
    garde = []
    for n in ast.parse(_source_du_pilote()).body:
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):
            break                                    # rclpy.init() : le programme commence ici
        garde.append(n)
    faux_rclpy = types.ModuleType("rclpy")
    faux_node = types.ModuleType("rclpy.node")
    faux_node.Node = object
    faux_msg = types.ModuleType("theatre_interfaces.msg")
    faux_msg.StringTime = object
    for nom, mod in {"rclpy": faux_rclpy, "rclpy.node": faux_node, "theatre_interfaces": types.ModuleType("t"),
                     "theatre_interfaces.msg": faux_msg}.items():
        monkeypatch.setitem(sys.modules, nom, mod)
    monkeypatch.setattr(sys, "argv", ["pilote", "/inexistant", "/didier"])
    ns = {"__name__": "pilote_conv"}
    exec(compile(ast.Module(body=garde, type_ignores=[]), str(SCRIPT), "exec"), ns)
    return ns


@pytest.mark.parametrize("etat_route, vitesse, attendu", [
    ("on", "1.0", True),
    ("on", "0.5", True),
    ("on", "0", False),          # hold d'une lubie ou du stop vocal
    ("on", "0.0", False),
    ("on", None, False),         # vitesse jamais vue
    ("on", "n'importe", False),
    ("off", "1.0", False),
    ("goto", "1.0", False),
    ("arrived", "1.0", False),
    (None, "1.0", False),
])
def test_en_marche_exige_route_on_et_vitesse_non_nulle(monkeypatch, etat_route, vitesse, attendu):
    assert _charger_pilote(monkeypatch)["en_marche"](etat_route, vitesse) is attendu


class Monde:
    """Horloge + état de route factices. route_state reste « on » de bout en bout (comme le 19/11) ;
    route_speed vaut 0 (hold) jusqu'à `reprise_t`, ou jusqu'au « go » console si `obeit_console`."""

    T0 = 1000.0                  # une horloge monotone ne vaut jamais 0

    def __init__(self, reprise_t, obeit_console):
        self.t = self.T0
        self.reprise_t = self.T0 + reprise_t
        self.obeit = obeit_console
        self.gos = []

    def monotonic(self):
        return self.t

    def etat(self, topic):
        if topic == "route_state":
            return "on"
        if topic == "route_speed":
            return "1.0" if self.t >= self.reprise_t else "0"
        raise AssertionError(topic)


def _rejouer(monkeypatch, monde, delai=150.0):
    ns = _charger_pilote(monkeypatch)
    faux_time = types.SimpleNamespace(monotonic=monde.monotonic, strftime=lambda f: "hh:mm:ss")
    ns["time"] = faux_time
    ns["etat"] = monde.etat
    ns["pose"] = lambda: (ns["TABLE"][0] - 8.0, ns["TABLE"][1])   # 8 m de la table : < DIST_B_M

    class Soi:
        def dormir(self, s):
            monde.t += s

        def console(self, cmd):
            monde.gos.append((round(monde.t - Monde.T0, 1), cmd))
            if monde.obeit and monde.t < monde.reprise_t:
                monde.reprise_t = monde.t + 0.5          # le régisseur relance la route

    ns["Pilote"].faire_marcher(Soi(), delai=delai)
    return ns


def test_un_hold_n_est_pas_en_marche_et_le_go_console_le_leve(monkeypatch):
    monde = Monde(reprise_t=1e9, obeit_console=True)
    ns = _rejouer(monkeypatch, monde)
    # Hold vu > 5 s -> UN « go » console (vers 5 s), route relancée 0,5 s après.
    assert [c for _, c in monde.gos] == ["go"]
    assert 4.9 <= monde.gos[0][0] <= 5.6
    # Phrase B autorisée seulement ≥ 11 s (EN_MARCHE_S) après la reprise EFFECTIVE (≈ 5,5 s).
    assert ns["EN_MARCHE_S"] == 11.0
    assert 16.4 <= monde.t - Monde.T0 <= 17.2
    assert ns["marques"]["dist_b"] == 8.0


def test_reprise_par_le_jeu_le_compte_repart_de_la_reprise(monkeypatch):
    # Le 19/11 : hold de 98 s, levé par le « repartir » du jeu ; la console n'y peut rien ici.
    monde = Monde(reprise_t=98.0, obeit_console=False)
    _rejouer(monkeypatch, monde)
    assert len(monde.gos) == 3                       # au plus 3 « go » console, jamais une salve
    assert 109.0 <= monde.t - Monde.T0 <= 109.6                # 98 + 11 s, et pas 11 s (l'ancien pilote)
