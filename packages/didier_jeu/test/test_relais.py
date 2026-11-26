"""Mode dégradé (revue A1, bloquant 2) : le chemin d'arrêt vocal ne dépend
jamais d'un JSON de séquence — RelaisSeul relaie stop/go, rien d'autre. Lot S1 :
mêmes règles d'origine que le sélecteur (verrou de David seul, go de Didier ignoré,
stop de Didier relayé sans verrou ni reprise)."""
import ast
import pathlib


def test_relais_seul_relaie_stop_et_go_sans_initiative():
    from didier_jeu.relais import RelaisSeul
    r = RelaisSeul("RepertoireError('séquence illisible')")
    debut = r.vider_sorties()
    assert [s[1] for s in debut if s[0] == "journal"] == ["degrade"]
    r.sur_chat_move_bouche("stop", 1.0)
    r.sur_person_box(0.2, 0.3, 0.9, 1.1)                    # ignoré
    r.sur_poi_event({"poi": "x", "event": "enter"}, 1.2)    # ignoré
    r.sur_chat_move_bouche({"cmd": "avancer", "metres": 1.0}, 1.3)
    assert r.tick(2.0) is None
    r.sur_chat_move_bouche("go", 3.0)
    out = r.vider_sorties()
    assert [s[1] for s in out if s[0] == "chat_move"] == [{"cmd": "stop", "origine": "david"},
                                                          {"cmd": "go", "origine": "david"}]
    assert r.intention(3.0)["action"] == "degrade"


def test_relais_seul_go_de_didier_ignore_stop_de_didier_sans_verrou():
    from didier_jeu.relais import RelaisSeul
    r = RelaisSeul("x")
    r.vider_sorties()
    r.sur_chat_move_bouche({"cmd": "stop", "origine": "didier"}, 1.0)
    assert r.verrou_david is False                      # relayé, sans verrou (ni reprise : aucun go seul)
    r.sur_console({"cmd": "stop"}, 2.0)
    r.sur_chat_move_bouche({"cmd": "go", "origine": "didier"}, 3.0)
    assert r.verrou_david is True                       # le go de Didier ne lève rien
    r.sur_console({"cmd": "go"}, 4.0)
    assert [s[1] for s in r.vider_sorties() if s[0] == "chat_move"] == [
        {"cmd": "stop", "origine": "didier"}, {"cmd": "stop", "origine": "david"}, {"cmd": "go", "origine": "david"}]
    assert r.verrou_david is False


def test_jeu_node_replie_en_relais_seul_sur_erreur_de_chargement():
    src = (pathlib.Path(__file__).resolve().parents[1] / "didier_jeu" / "jeu_node.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    essais = [n for n in ast.walk(tree) if isinstance(n, ast.Try)
              and "Selecteur(" in ast.unparse(n.body[-2] if len(n.body) > 1 else n.body[0])
              or isinstance(n, ast.Try) and any("Selecteur(" in ast.unparse(b) for b in n.body)]
    assert len(essais) == 1
    gestion = essais[0].handlers[0]
    assert ast.unparse(gestion.type) == "Exception"            # TOUTE erreur de chargement
    assert "RelaisSeul(" in ast.unparse(gestion)
    # Le chargement des séquences est DANS l'essai (sinon il tuerait le relais).
    assert any("candidates(" in ast.unparse(b) for b in essais[0].body)


def test_relais_seul_go_de_la_bouche_ne_leve_pas_un_stop_de_david():
    """Test d'origine (revue A1, B2) rétabli sur les règles S1 : en mode dégradé aussi, un STOP
    de la console n'est levé que par la console ; un mot d'arrêt l'est par la bouche."""
    from didier_jeu.relais import RelaisSeul
    r = RelaisSeul("x")
    r.vider_sorties()
    r.sur_console({"cmd": "stop"}, 1.0)
    r.sur_chat_move_bouche("go", 2.0)                        # « en route » dit à Didier : refusé
    assert r.verrou == "console"
    r.sur_console({"cmd": "go"}, 3.0)
    r.sur_chat_move_bouche("stop", 4.0)                      # mot d'arrêt : verrou « voix »
    r.sur_chat_move_bouche("go", 5.0)                        # levé par la bouche
    assert [s[1] for s in r.vider_sorties() if s[0] == "chat_move"] == [
        {"cmd": "stop", "origine": "david"}, {"cmd": "go", "origine": "david"},
        {"cmd": "stop", "origine": "david"}, {"cmd": "go", "origine": "david"}]
    assert r.verrou is None
