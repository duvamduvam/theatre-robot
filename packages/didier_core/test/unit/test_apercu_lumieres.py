"""Aperçu des bandes LED de la page scène (lot I0, didier_web.apercu_lumieres + static/lumieres.js).

Le modèle du pont doit dire ce que le VRAI Lights (didier_core.actions.lights) afficherait pour
une suite de messages `robot_lights` : valeurs GRAVÉES, relevées à la main dans les vraies
données (robot_lights.json, lights_base.json, colors.json) et dans le vrai code (repos sur
"stop", durée de message qui borne l'entrée sans changer le minutage des briques, boucle).
Le dessin des pixels (lumieres.js) est joué par node quand il est installé.
"""
import json
import os
import pathlib
import shutil
import subprocess

import pytest

from didier_web import apercu_lumieres, lecture_donnees, web_protocol
from didier_web.apercu_lumieres import Apercu, EtatLumieres, activations, charger

MONO = pathlib.Path(__file__).resolve().parents[4]
JSON = MONO / "data" / "json"
LUMIERES_JS = MONO / "packages" / "didier_web" / "static" / "lumieres.js"


@pytest.fixture(scope="module")
def tables():
    return charger(JSON)


def etat(tables, t0=1000.0):
    return EtatLumieres(tables[0], tables[1], t0)


def vu(e, now):
    i = e.instant(now)
    return (i["sequence"], i["brique"], i["methode"], i["rgb"], i["depuis_ms"])


def test_bandes_gravees():
    # La zone « corps » du ruban : LIGHTS_START_LED 513 -> LIGHTS_END_LED 673 (robot_config).
    from didier_core.robot_config import config
    from didier_core.robot_static import LIGHTS_END_LED, LIGHTS_START_LED
    assert apercu_lumieres.BANDES == ({"nom": "corps", "leds": 160},)
    assert config[LIGHTS_END_LED] - config[LIGHTS_START_LED] == 160


def test_briques_resolues_sur_les_vraies_donnees(tables):
    _, briques = tables
    assert briques["chase me"] == {"methode": "chase", "rgb": (0, 255, 255)}
    assert briques["pulse green"] == {"methode": "pulse", "rgb": (0, 255, 0)}
    assert briques["pulse red"] == {"methode": "pulse", "rgb": (255, 0, 0)}
    assert briques["sea colorcycle"] == {"methode": "color_cycle", "rgb": (180, 0, 255)}
    assert briques["rainbow"] == {"methode": "rainbow", "rgb": None}
    assert briques["off"] == {"methode": "solid", "rgb": (0, 0, 0)}


def test_activations_de_track_frames(tables):
    lumieres, _ = tables
    # trip : 50 s, 5 briques jusqu'à 0,2 / 0,4 / 0,6 / 0,8 / 1.
    assert activations(lumieres["trip"]) == [(0.0, "sea colorcycle"), (10000.0, "rainbow"), (20000.0, "love"),
                                             (30000.0, "rainbow_comet"), (40000.0, "rainbow_chase")]
    # scan : rainbow « jusqu'à 0 % » -> la pulsation verte prend la main tout de suite.
    assert activations(lumieres["scan"]) == [(0.0, "rainbow"), (0.0, "pulse green")]


def test_demarrage_sur_default(tables):
    assert vu(etat(tables), 1000) == ("default", "chase me", "chase", [0, 255, 255], 0)


def test_scan_avec_duree_de_message_puis_repos(tables):
    e = etat(tables)
    e.recevoir("scan", 8000, 2000)
    assert vu(e, 2010) == ("scan", "pulse green", "pulse", [0, 255, 0], 10)
    assert vu(e, 10000) == ("scan", "pulse green", "pulse", [0, 255, 0], 8000)   # 8000 ms pile : encore
    assert vu(e, 10001) == ("default", "chase me", "chase", [0, 255, 255], 1)    # échue -> repos


def test_scan_sans_duree_suit_le_json(tables):
    e = etat(tables)
    e.recevoir("scan", 0, 0)
    assert vu(e, 23999)[:2] == ("scan", "pulse green")
    assert vu(e, 24001)[:2] == ("default", "chase me")


def test_entree_bouclee_ignore_la_fin_et_reboucle(tables):
    """trip est bouclé : la durée de message (3 s, celle du bug) ne l'arrête pas — c'est le
    « stop » de fin de séquence qui ramène le repos. Les briques suivent les 50 s du JSON."""
    e = etat(tables)
    e.recevoir("trip", 3000, 0)
    assert vu(e, 2000)[:3] == ("trip", "sea colorcycle", "color_cycle")
    assert vu(e, 9999)[:2] == ("trip", "sea colorcycle")
    assert vu(e, 10000)[:3] == ("trip", "rainbow", "rainbow")
    assert vu(e, 50005) == ("trip", "sea colorcycle", "color_cycle", [180, 0, 255], 5)   # cycle 2
    e.recevoir("stop", 0, 50010)
    assert vu(e, 50020)[:2] == ("default", "chase me")


def test_stop_ramene_le_repos_qui_suit_le_dernier_marque_default(tables):
    e = etat(tables)
    e.recevoir("default dark", 0, 0)
    assert vu(e, 10)[:4] == ("default dark", "chase me dark", "chase", [180, 0, 255])
    e.recevoir("trip", 0, 100)
    e.recevoir("stop", 0, 200)
    assert e.instant(300)["repos"] == "default dark"
    assert vu(e, 300)[:2] == ("default dark", "chase me dark")


def test_luminosite_et_nom_inconnu_ne_changent_pas_l_animation(tables):
    e = etat(tables)
    e.recevoir("speak", 4000, 0)
    e.recevoir({"brightness": 0.3}, 0, 100)
    e.recevoir("n-existe-pas", 0, 200)
    e.recevoir({"brightness": "fort"}, 0, 300)
    i = e.instant(500)
    assert (i["sequence"], i["brique"], i["rgb"], i["luminosite"]) == ("speak", "pulse", [0, 0, 255], 0.3)
    # speak : 500 ms au JSON, 4000 ms par le message -> la pulsation bleue tient 4 s.
    assert vu(e, 4000)[:2] == ("speak", "pulse")
    assert vu(e, 4001)[:2] == ("default", "chase me")


def test_off_est_du_noir_et_non_une_couleur_inconnue(tables):
    e = etat(tables)
    e.recevoir("off", 4000, 0)
    assert vu(e, 3000) == ("off", "off", "solid", [0, 0, 0], 3000)
    # Sans entrée « default » dans la table, rien ne joue au départ (rien n'est inventé).
    assert EtatLumieres({"x": {"duration": 10, "loop": True, "sequences": {"off": 1}}}, tables[1], 0).instant(0)[
        "sequence"] is None


def test_apercu_relit_les_fichiers_modifies(tmp_path):
    for nom in apercu_lumieres.FICHIERS:
        shutil.copy(JSON / nom, tmp_path / nom)
    a = Apercu(tmp_path, 0)
    a.recevoir("nouvelle", 0, 10)
    assert a.instant(20)["sequence"] == "default"            # inconnue : ignorée
    lumieres = json.loads((tmp_path / "robot_lights.json").read_text())
    lumieres["nouvelle"] = {"loop": True, "duration": 1000, "sequences": {"solid red": 1}}
    (tmp_path / "robot_lights.json").write_text(json.dumps(lumieres))
    a.recevoir("nouvelle", 0, 30)
    i = a.instant(40)
    assert (i["sequence"], i["brique"], i["rgb"]) == ("nouvelle", "solid red", [255, 0, 0])
    assert i["bandes"] == [{"nom": "corps", "leds": 160}]


def test_fichiers_absents_aperçu_vide_sans_exception(tmp_path):
    a = Apercu(tmp_path, 0)
    a.recevoir("trip", 0, 1)
    assert a.instant(2)["sequence"] is None


def test_messages_du_pont():
    assert web_protocol.build_lumieres({"sequence": "trip"}) == {"type": "lumieres", "lumieres": {"sequence": "trip"}}
    assert "lumieres" not in web_protocol.build_state({}, [], 0, False)
    assert web_protocol.build_state({}, [], 0, False, lumieres={"a": 1})["lumieres"] == {"a": 1}


def test_bugs_joues_pour_la_page():
    from theatre_contrats.donnees import dossier_audios_prives
    page = lecture_donnees.bugs_joues(MONO / "data", dossier_audios_prives())
    assert page["refuses"] == []
    assert [b["id"] for b in page["acceptes"]] == ["begaiement", "ecran_noir", "faux_redemarrage",
                                                    "glitch_visage", "lumieres_folles", "mise_a_jour"]
    assert page["acceptes"][1] == {"id": "ecran_noir", "desc": "tout s'éteint, puis il sursaute", "classe": "V",
                                   "duree_s": 4.0, "direction": "tu ne t'es rendu compte de rien",
                                   "pistes": ["faces", "robot_lights"]}


# ---------------------------------------------------------------- lumieres.js, joué par node
def _pixels(appels):
    """Résultats de lumPixels(...) pour chaque appel, calculés par le VRAI lumieres.js."""
    script = (LUMIERES_JS.read_text(encoding="utf-8")
              + "\nconsole.log(JSON.stringify(" + json.dumps(appels) + ".map(a => lumPixels(...a))));")
    sortie = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(sortie.stdout)


NOEUD = shutil.which("node")


@pytest.mark.skipif(NOEUD is None, reason="node absent : dessin JS non joué")
def test_dessin_des_methodes_grave():
    C, N = [0, 255, 255], [0, 0, 0]
    chase0, chase1, blink0, blink1, cycle0, cycle1, cycle2, pulse0, pulse5, solid, inconnue = _pixels([
        ["chase", C, 0, 10], ["chase", C, 100, 10], ["blink", C, 0, 2], ["blink", C, 500, 2],
        ["color_cycle", [1, 2, 3], 0, 1], ["color_cycle", None, 500, 1], ["color_cycle", None, 1000, 1],
        ["pulse", [0, 255, 0], 0, 1], ["pulse", [0, 255, 0], 500, 1], ["solid", [255, 0, 0], 0, 2],
        [None, None, 0, 2]])
    assert chase0 == [C, C, C, N, N, N, N, N, N, C]      # 3 allumées, 6 éteintes
    assert chase1 == [N, C, C, C, N, N, N, N, N, N]      # un pas de 0,1 s plus tard : décalé d'une LED
    assert blink0 == [C, C] and blink1 == [N, N]
    # color_cycle ignore la couleur de la brique : magenta, orange, turquoise (lights_animations.py).
    assert (cycle0, cycle1, cycle2) == ([[255, 0, 20]], [[255, 40, 0]], [[0, 255, 40]])
    assert pulse0 == [N] and pulse5 == [[0, 255, 0]]     # respiration : noir à 0, pleine à 500 ms
    assert solid == [[255, 0, 0], [255, 0, 0]]
    assert inconnue == [N, N]


@pytest.mark.skipif(NOEUD is None, reason="node absent : dessin JS non joué")
def test_toutes_les_methodes_du_contrat_se_dessinent():
    from theatre_contrats.donnees import METHODES_LUMIERE
    resultats = _pixels([[m, [10, 20, 30], 1234, 160] for m in METHODES_LUMIERE])
    for methode, pixels in zip(METHODES_LUMIERE, resultats):
        assert len(pixels) == 160 and all(len(p) == 3 and all(0 <= c <= 255 for c in p) for p in pixels), methode
        assert any(p != [0, 0, 0] for p in pixels), "{} : rien d'allumé à 1234 ms".format(methode)
