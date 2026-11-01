"""Géométrie des tours (lot M3, spec-aller-voir.md §8.1) : l'outil
tools/compute_tours.py, le fichier GÉNÉRÉ config/chantiers_tours.yaml et son
chargement (route.load_tours / tours_path) — valeurs GRAVÉES.

POURQUOI regénérer ici : le fichier est dérivé du monde Gazebo. Un monde
retouché sans regénération enverrait Didier tourner autour d'un centre faux,
sans bruit. Commande de regénération (depuis le package robot_rehearsal) :
    python3 tools/compute_tours.py ../robot_sim/worlds/chantiers.sdf config/chantiers.yaml \\
        > config/chantiers_tours.yaml

Passe de mutation du lot M3 (chaque ligne doit rougir) :
  - arrondi au 0,1 INFÉRIEUR -> test_poubelle_tri_valeurs_gravees, test_regles_sur_un_monde_jouet
  - dégagement 1,0 m retiré -> test_poubelle_tri_valeurs_gravees
  - obstacle mesuré en disque majorant (au lieu de l'emprise réelle) -> test_poubelle_tri_valeurs_gravees
  - garde « autre modèle près de l'anneau » retirée -> test_regles_sur_un_monde_jouet
  - retour à « emprise > 50 m = sol » (bordure, façades écartées) -> test_quels_poi_ont_un_tour,
    test_sol_liste_explicite
  - cylindre couché pris à son seul rayon -> test_regles_sur_un_monde_jouet
  - POI inconnu accepté par load_tours -> test_load_tours_refus
"""
import importlib.util
import math
import pathlib

import pytest
import yaml

from robot_rehearsal.route import RouteError, Tour, load_route, load_tours, tours_path

ROOT = pathlib.Path(__file__).resolve().parents[3]
PKG = ROOT / "conf" / "ros2_dependencies" / "robot_rehearsal"
SDF = ROOT / "conf" / "ros2_dependencies" / "robot_sim" / "worlds" / "chantiers.sdf"
ITINERAIRE = PKG / "config" / "chantiers.yaml"
TOURS = PKG / "config" / "chantiers_tours.yaml"


def _outil():
    spec = importlib.util.spec_from_file_location("compute_tours", PKG / "tools" / "compute_tours.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# POI SANS tour, et pourquoi (relevé du 01/11) :
#  - rayon de tour > 6 m : nefs (hall 30 × 12), grue_jaune, loire, hangar_bananes, titan_grise ;
#  - aucune collision : flaque, rails (visuels seuls, rien à contourner) ;
#  - un AUTRE objet près de l'anneau : elephant <-> carrousel, cale (grue), pelouse et
#    tag_mur (hangar) ;
#  - la BORDURE DE QUAI (chute dans la Loire derrière) près de l'anneau : anneaux, bollard,
#    tas_de_sable, conteneur_rouge ; une FAÇADE : terrasse (tranché le 01/11 : seul
#    l'esplanade est du sol, cf. compute_tours.GROUND_MODELS).
SANS_TOUR = {"nefs", "elephant", "carrousel", "flaque", "grue_jaune", "cale", "rails", "loire",
             "hangar_bananes", "pelouse", "tag_mur", "titan_grise",
             "terrasse", "anneaux", "bollard", "tas_de_sable", "conteneur_rouge"}


def test_fichier_genere_a_jour():
    assert _outil().render(_outil().compute_tours(SDF, ITINERAIRE)) == TOURS.read_text(encoding="utf-8")


def test_fichier_porte_l_entete_genere():
    assert TOURS.read_text(encoding="utf-8").startswith("# GÉNÉRÉ — ne pas éditer.")


def test_poubelle_tri_valeurs_gravees():
    # Trois bacs (r 0,27, couvercles r 0,285) à x = −0,75 / 0 / +0,75, y = +1 de
    # l'ancre (27 ; 1,4) : centre (27 ; 2,4), rayon objet 0,75 + 0,285 = 1,035,
    # + 1,0 = 2,035 -> 2,1. Le hall des Nefs (y ≥ 7) est à 1,9 m de l'anneau.
    # Gravé sur le FICHIER et sur la sortie de l'OUTIL (une mutation de l'outil
    # ne se voit pas dans le fichier déjà généré).
    tours = yaml.safe_load(TOURS.read_text(encoding="utf-8"))
    assert tours["poubelle_tri"] == {"x": 27.0, "y": 2.4, "rayon": 2.1}
    assert _outil().compute_tours(SDF, ITINERAIRE).get("poubelle_tri") == {"x": 27.0, "y": 2.4, "rayon": 2.1}


def test_quels_poi_ont_un_tour():
    route = yaml.safe_load(ITINERAIRE.read_text(encoding="utf-8"))
    tours = yaml.safe_load(TOURS.read_text(encoding="utf-8"))
    assert {p["name"] for p in route["pois"]} - set(tours) == SANS_TOUR
    assert len(tours) == 13
    assert {n: t["rayon"] for n, t in tours.items()} == {
        "table_basse": 1.7, "poster_bizarre": 1.6, "poubelle_tri": 2.1, "pigeon": 1.5, "banc": 2.1,
        "velo_cadenas": 1.9, "panneau_info": 1.8, "lampadaire": 1.5, "plot_chantier": 1.5,
        "chien": 1.7, "caisse_bois": 1.8, "horloge_arretee": 1.7, "bouche_incendie": 1.5}
    # Ceux-là ne sont PAS refusés par la taille : sur l'outil, ils ont un rayon ≤ 6
    # et seuls la bordure de quai / les façades les bloquent.
    outil = _outil()
    formes = outil.model_shapes(SDF)
    for nom, bloqueur in (("terrasse", "facades"), ("anneaux", "bordure_quai"), ("bollard", "bordure_quai"),
                          ("tas_de_sable", "bordure_quai"), ("conteneur_rouge", "bordure_quai")):
        cx, cy, r = outil.tour_of(nom, formes)
        assert r <= 6.0 and bloqueur in outil.blockers(nom, cx, cy, r, formes), nom


def test_fichier_reel_se_charge():
    route = load_route(yaml.safe_load(ITINERAIRE.read_text(encoding="utf-8")))
    tours = load_tours(yaml.safe_load(TOURS.read_text(encoding="utf-8")), route.pois)
    assert tours["poubelle_tri"] == Tour(27.0, 2.4, 2.1)
    assert tours_path(str(ITINERAIRE)) == str(TOURS)


# --- règles sur un monde jouet ---------------------------------------------------------

def _monde(tmp_path, modeles):
    sdf = tmp_path / "jouet.sdf"
    sdf.write_text("<sdf version='1.9'><world name='w'>" + "".join(modeles) + "</world></sdf>", encoding="utf-8")
    route = tmp_path / "jouet.yaml"
    route.write_text(yaml.safe_dump({"name": "j", "waypoints": [[0, 0], [1, 0]],
                                     "pois": [{"name": "objet", "x": 0, "y": 0, "radius": 2}]}), encoding="utf-8")
    return _outil().compute_tours(sdf, route)


def _modele(nom, pose, geometrie, lien="0 0 0 0 0 0"):
    return (f"<model name='{nom}'><pose>{pose}</pose><link name='l'><pose>{lien}</pose>"
            f"<collision name='c'><geometry>{geometrie}</geometry></collision></link></model>")


CYL = "<cylinder><radius>0.5</radius><length>1</length></cylinder>"


def test_regles_sur_un_monde_jouet(tmp_path):
    # Cylindre r 0,5 : 0,5 + 1,0 = 1,5 (plancher atteint pile).
    assert _monde(tmp_path, [_modele("objet", "3 4 0 0 0 0", CYL)]) == {"objet": {"x": 3.0, "y": 4.0, "rayon": 1.5}}
    # r 0,51 -> 1,51 -> arrondi SUPÉRIEUR 1,6.
    cyl = "<cylinder><radius>0.51</radius><length>1</length></cylinder>"
    assert _monde(tmp_path, [_modele("objet", "0 0 0 0 0 0", cyl)])["objet"]["rayon"] == 1.6
    # Cylindre COUCHÉ (r 0,1, long 2) : sphère englobante √(0,1² + 1²) = 1,005 -> 2,005 -> 2,1.
    couche = "<cylinder><radius>0.1</radius><length>2</length></cylinder>"
    assert _monde(tmp_path, [_modele("objet", "0 0 0 0 0 0", couche, lien="0 0 0.5 1.570796 0 0")]
                  )["objet"]["rayon"] == 2.1
    # Rayon objet > 5 m -> tour > 6 m : pas de tour.
    gros = "<cylinder><radius>5.1</radius><length>1</length></cylinder>"
    assert _monde(tmp_path, [_modele("objet", "0 0 0 0 0 0", gros)]) == {}
    # Mur (boîte 4 × 0,2) dont le bord est à 2,6 m du centre : anneau [0,9 ; 2,1],
    # écart 0,5 -> toléré ; à 2,5 m (écart 0,4) -> refus.
    mur = "<box><size>4 0.2 1</size></box>"
    assert "objet" in _monde(tmp_path, [_modele("objet", "0 0 0 0 0 0", CYL), _modele("mur", "0 2.7 0 0 0 0", mur)])
    assert _monde(tmp_path, [_modele("objet", "0 0 0 0 0 0", CYL), _modele("mur", "0 2.6 0 0 0 0", mur)]) == {}


def test_sol_liste_explicite(tmp_path):
    # Seul le modèle nommé dans GROUND_MODELS (esplanade) est ignoré sous l'anneau ;
    # un GRAND modèle hors liste (bordure, façade) reste un obstacle.
    assert _outil().GROUND_MODELS == frozenset({"esplanade"})
    sol = "<box><size>60 60 0.1</size></box>"
    assert "objet" in _monde(tmp_path, [_modele("objet", "0 0 0 0 0 0", CYL),
                                        _modele("esplanade", "0 0 -0.05 0 0 0", sol)])
    assert _monde(tmp_path, [_modele("objet", "0 0 0 0 0 0", CYL), _modele("grand", "0 0 -0.05 0 0 0", sol)]) == {}
    # Bordure de 60 m dont le bord est à 2,4 m du centre (écart 0,3 à l'anneau) : bloque.
    bordure = "<box><size>60 0.3 0.12</size></box>"
    assert _monde(tmp_path, [_modele("objet", "0 0 0 0 0 0", CYL), _modele("bordure_quai", "0 2.55 0 0 0 0", bordure)]) == {}


def test_entete_et_tri_du_rendu():
    texte = _outil().render({"b": {"x": 1.0, "y": 2.0, "rayon": 1.5}, "a": {"x": 0.0, "y": 0.0, "rayon": 2.0}})
    assert texte.splitlines()[3:] == ["a: {rayon: 2.0, x: 0.0, y: 0.0}", "b: {rayon: 1.5, x: 1.0, y: 2.0}"]
    assert _outil().render({}).endswith("{}\n")


# --- chargement ----------------------------------------------------------------------

POIS = load_route({"name": "r", "waypoints": [[0, 0], [1, 0]],
                   "pois": [{"name": "banc", "x": 5, "y": 0, "radius": 1}]}).pois


def test_tours_path_frere():
    assert tours_path("/share/config/chantiers.yaml") == "/share/config/chantiers_tours.yaml"
    assert tours_path("rue.yaml") == "rue_tours.yaml"


def test_load_tours_vide():
    assert load_tours(None, POIS) == {}
    assert load_tours({}, POIS) == {}


@pytest.mark.parametrize("data, fragment", [
    ({"inconnu": {"x": 0, "y": 0, "rayon": 2}}, "POI inconnu"),
    ({"banc": {"x": 0, "y": 0, "rayon": 1.4}}, "rayon"),
    ({"banc": {"x": 0, "y": 0, "rayon": 6.1}}, "rayon"),
    ({"banc": {"x": math.nan, "y": 0, "rayon": 2}}, "banc.x"),
    ({"banc": {"x": 0, "rayon": 2}}, "banc.y"),
    ({"banc": [0, 0, 2]}, "banc"),
    ([1, 2], "dictionnaire"),
])
def test_load_tours_refus(data, fragment):
    with pytest.raises(RouteError) as exc:
        load_tours(data, POIS)
    assert fragment in str(exc.value)
