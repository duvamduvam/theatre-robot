"""Contrats GELÉS du monde `chantiers` (didier_sim/worlds/chantiers.sdf) et de son
itinéraire (didier_rehearsal/config/chantiers.yaml) — lus dans les VRAIS fichiers.

POURQUOI ces tests : le monde est ~330 liens de primitives écrits à la main ou
presque ; personne ne le relira à l'œil après chaque retouche. Ils tiennent lieu
de vérification humaine sur ce qui casserait la séance sans bruit :
 - le contrat `stage` (bridge LED), les primitives seules, pas de ground plane ;
 - 30 modèles nommés EXACTEMENT comme les POI, dans l'ordre de la marche ;
 - le tracé reste sur les dalles (coudée de 35° incluse) et rien de plein ne le
   coupe : Didier (~0,6 m de large) passe partout, sauf devant la Titan qui BARRE ;
 - chaque POI est DÉCLENCHABLE : PoiWatcher exige d < rayon STRICTEMENT, donc un
   Didier qui suit la polyligne ne déclenche l'enter que si
   distance(centre, tracé) <= rayon - 1 m (marge sur l'écart latéral du suiveur) ;
 - la Loire d'un côté (eau 1 m plus bas derrière un ressaut de 12 cm), les bâtiments de
   l'autre ; le côté est LA seule orientation gravée (COTE_LOIRE), le reste en dérive.

Les valeurs sont GRAVÉES ici (pas recalculées par le code testé) : toute retouche
du monde ou de l'itinéraire doit être répercutée ici, en connaissance de cause.
Les helpers géométriques ont leurs propres tests : sans eux, un helper faux
validerait n'importe quel monde.
"""
import math
import pathlib
import xml.etree.ElementTree as ET

import pytest
import yaml

from didier_rehearsal.route import load_route

ROOT = pathlib.Path(__file__).resolve().parents[3]
PACKAGES = ROOT.parents[1] / "packages"          # packages/ du mono-dépôt (L1e-1)
SDF = PACKAGES / "didier_sim" / "worlds" / "chantiers.sdf"
YAML = PACKAGES / "didier_rehearsal" / "config" / "chantiers.yaml"

# ------------------------------------------------------------------ valeurs gravées

# ORIENTATION du monde (la SEULE information de côté ; les formules ci-dessous en dérivent).
# +1 : la Loire est du côté y POSITIF, soit à GAUCHE d'un marcheur qui avance vers +x (repère
#      direct, z vertical), et la coudée tourne vers y négatif. C'est la convention du brief du
#      lot R3 (« Loire à droite = y positif »), qui n'est vraie qu'en image miroir.
# -1 : monde renversé en y : Loire réellement à DROITE de la marche, coudée vers y positif.
# Renverser = changer cette constante ET les tables POIS / WAYPOINTS / QUAI_CENTRE (y -> -y).
COTE_LOIRE = -1

# Les 30 POI : (nom, x, y, rayon), ORDRE RÉEL de la marche (étude §13.3).
POIS = (
    ("nefs", 4.0, 2.0, 4),
    ("elephant", 8.6, -1.4, 2.5),
    ("carrousel", 13.2, -2.0, 4),
    ("table_basse", 17.8, 1.4, 2.5),
    ("poster_bizarre", 22.4, -1.4, 2.5),
    ("poubelle_tri", 27.0, 1.4, 2.5),
    ("pigeon", 31.6, -1.4, 2.5),
    ("banc", 36.2, 1.4, 2.5),
    ("flaque", 40.8, -0.0, 2.5),
    ("terrasse", 45.4, 1.9, 3),
    ("grue_jaune", 50.0, -2.0, 4),
    ("cale", 54.6, -1.9, 3),
    ("velo_cadenas", 59.2, 1.4, 2.5),
    ("panneau_info", 63.8, -1.4, 2.5),
    ("rails", 68.4, -0.0, 2.5),
    ("lampadaire", 73.01, 3.81, 2.5),
    ("anneaux", 78.42, 4.19, 2.5),
    ("bollard", 83.05, 7.43, 2.5),
    ("loire", 87.68, 10.67, 2.5),
    ("plot_chantier", 92.3, 17.32, 2.5),
    ("chien", 97.71, 17.7, 2.5),
    ("caisse_bois", 102.33, 24.35, 2.5),
    ("hangar_bananes", 106.96, 28.2, 3),
    ("tas_de_sable", 112.66, 28.16, 2.5),
    ("horloge_arretee", 117.28, 34.82, 2.5),
    ("bouche_incendie", 122.66, 35.16, 2.5),
    ("pelouse", 127.27, 42.42, 3),
    ("conteneur_rouge", 132.98, 42.39, 2.5),
    ("tag_mur", 137.6, 49.04, 2.5),
    ("titan_grise", 145.61, 52.94, 6),
)
NOMS = tuple(p[0] for p in POIS)

# Polyligne : le Mail le long de +x (y = 0) jusqu'à la coudée en (70, 0), puis le
# quai à -35° (vers y négatif, côté bâtiments ; la Loire reste à y positif).
WAYPOINTS = (
    (2.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0), (40.0, 0.0), (50.0, 0.0),
    (60.0, 0.0), (70.0, 0.0),
    (77.44, 5.21), (84.88, 10.42), (92.31, 15.62), (99.75, 20.83), (107.19, 26.04),
    (114.63, 31.25), (122.07, 36.46), (129.5, 41.66), (136.94, 46.87), (144.38, 52.08),
)
COUDEE = (70.0, 0.0)
COUDEE_DEG = 35.0
CAP_QUAI = math.radians(-COTE_LOIRE * COUDEE_DEG)      # cap du quai : s'éloigne de la Loire

# Dalles : largeur 12 m. Mail = x de -5 à 71.89 (rallongé de 6*tan(17.5°) = 1.89 m
# au-delà de la coudée pour fermer la mitre extérieure). Quai = abscisse d le long de
# la direction -35° à partir de la coudée, de -1.89 (mitre) à 102.3 (1 m derrière le
# socle de la Titan).
DALLE_LARGEUR = 12.0
MAIL_X = (-5.0, 71.89)
QUAI_D = (-1.89, 102.3)
QUAI_CENTRE = (111.126, 28.796)     # centre de la dalle du quai (z surface = 0)
QUAI_LONGUEUR = 104.19
RAYON_MIN_MARGE = 1.0                # rayon >= distance au tracé + 1 m
DEGAGEMENT_MIN = 1.5                 # tout objet plein à >= 1,5 m du tracé
ESPACEMENT_MIN = 4.5                 # entre centres consécutifs de POI
HAUTEUR_DIDIER = 1.0                 # au-dessus, rien ne gêne le passage

PLUGINS = {
    "gz-sim-physics-system": "gz::sim::systems::Physics",
    "gz-sim-user-commands-system": "gz::sim::systems::UserCommands",
    "gz-sim-scene-broadcaster-system": "gz::sim::systems::SceneBroadcaster",
    "gz-sim-sensors-system": "gz::sim::systems::Sensors",
}
DECOR = {"esplanade", "bordure_quai", "facades"}


# ------------------------------------------------------------------ géométrie pure

def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def hull(points):
    """Enveloppe convexe 2D (chaîne monotone), sens trigonométrique."""
    pts = sorted(set((round(x, 9), round(y, 9)) for x, y in points))
    if len(pts) <= 2:
        return pts
    bas, haut = [], []
    for p in pts:
        while len(bas) >= 2 and _cross(bas[-2], bas[-1], p) <= 0:
            bas.pop()
        bas.append(p)
    for p in reversed(pts):
        while len(haut) >= 2 and _cross(haut[-2], haut[-1], p) <= 0:
            haut.pop()
        haut.append(p)
    return bas[:-1] + haut[:-1]


def dist_point_segment(p, a, b):
    ab = (b[0] - a[0], b[1] - a[1])
    n2 = ab[0] ** 2 + ab[1] ** 2
    t = 0.0 if n2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / n2))
    return math.hypot(p[0] - (a[0] + t * ab[0]), p[1] - (a[1] + t * ab[1]))


def _se_croisent(a, b, c, d):
    d1, d2 = _cross(a, b, c), _cross(a, b, d)
    d3, d4 = _cross(c, d, a), _cross(c, d, b)
    return d1 * d2 < 0 and d3 * d4 < 0


def dist_segments(a, b, c, d):
    if _se_croisent(a, b, c, d):
        return 0.0
    return min(dist_point_segment(a, c, d), dist_point_segment(b, c, d),
               dist_point_segment(c, a, b), dist_point_segment(d, a, b))


def dans_polygone_convexe(p, poly):
    return len(poly) >= 3 and all(_cross(a, b, p) >= -1e-9 for a, b in zip(poly, poly[1:] + poly[:1]))


def dist_ligne_polygone(ligne, poly):
    """Distance minimale entre une polyligne et un polygone convexe (0 si elle le touche)."""
    if any(dans_polygone_convexe(p, poly) for p in ligne):
        return 0.0
    aretes = list(zip(poly, poly[1:] + poly[:1]))
    return min(dist_segments(a, b, c, d) for a, b in zip(ligne, ligne[1:]) for c, d in aretes)


def dist_ligne_point(ligne, p):
    return min(dist_point_segment(p, a, b) for a, b in zip(ligne, ligne[1:]))


def projeter(ligne, p):
    """(abscisse curviligne, côté signé, distance) de p sur la polyligne. Côté > 0 =
    à GAUCHE du sens de marche = côté +y sur le Mail = côté Loire."""
    best, cum = None, 0.0
    for a, b in zip(ligne, ligne[1:]):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        t = max(0.0, min(1.0, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / (L * L)))
        d = dist_point_segment(p, a, b)
        if best is None or d < best[2]:
            best = (cum + t * L, _cross(a, b, p) / L, d)
        cum += L
    return best


def longueur(ligne):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(ligne, ligne[1:]))


# ------------------------------------------------------------------ lecture du SDF

def _floats(texte, n=None):
    v = [float(t) for t in texte.split()]
    return v if n is None else (v + [0.0] * n)[:n]


def _pose(el):
    p = el.find("pose") if el is not None else None
    return _floats(p.text, 6) if p is not None else [0.0] * 6


def _rot(roll, pitch, yaw):
    cr, sr, cp, sp, cy, sy = math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    return [[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr]]


def _mul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _app(R, t, p):
    return tuple(sum(R[i][k] * p[k] for k in range(3)) + t[i] for i in range(3))


def _compose(parent, pose):
    Rp, tp = parent
    return _mul(Rp, _rot(*pose[3:])), _app(Rp, tp, pose[:3])


def _points_locaux(geometry):
    """Points échantillonnant la primitive, dans SON repère (axe z pour cylindre)."""
    box, cyl, sph = geometry.find("box"), geometry.find("cylinder"), geometry.find("sphere")
    if box is not None:
        sx, sy, sz = _floats(box.find("size").text, 3)
        return [(a * sx / 2, b * sy / 2, c * sz / 2) for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]
    if cyl is not None:
        r, l = float(cyl.find("radius").text), float(cyl.find("length").text)
        return [(r * math.cos(2 * math.pi * k / 24), r * math.sin(2 * math.pi * k / 24), z)
                for k in range(24) for z in (-l / 2, l / 2)]
    if sph is not None:
        r = float(sph.find("radius").text)
        return [(r * math.sin(math.pi * i / 6) * math.cos(2 * math.pi * k / 24),
                 r * math.sin(math.pi * i / 6) * math.sin(2 * math.pi * k / 24),
                 r * math.cos(math.pi * i / 6)) for i in range(7) for k in range(24)]
    raise AssertionError(f"primitive inconnue : {[c.tag for c in geometry]}")


class Forme:
    """Une collision (ou un visuel) dans le monde : points 3D échantillonnés."""
    def __init__(self, modele, lien, tag, pts3d, kind):
        self.modele, self.lien, self.tag, self.kind = modele, lien, tag, kind
        self.pts3d = pts3d
        self.poly = hull([(x, y) for x, y, _ in pts3d])
        zs = [z for _, _, z in pts3d]
        self.zmin, self.zmax = min(zs), max(zs)
        self.centre = (sum(p[0] for p in pts3d) / len(pts3d), sum(p[1] for p in pts3d) / len(pts3d))


def formes(racine, tag):
    out = []
    for model in racine.find("world").findall("model"):
        Rm, tm = _compose((_rot(0, 0, 0), (0, 0, 0)), _pose(model))
        for link in model.findall("link"):
            Rl, tl = _compose((Rm, tm), _pose(link))
            for el in link.findall(tag):
                Re, te = _compose((Rl, tl), _pose(el))
                geo = el.find("geometry")
                pts = [_app(Re, te, p) for p in _points_locaux(geo)]
                kind = next(c.tag for c in geo)
                out.append(Forme(model.get("name"), link.get("name"), tag, pts, kind))
    return out


@pytest.fixture(scope="module")
def sdf():
    return ET.parse(SDF).getroot()


@pytest.fixture(scope="module")
def collisions(sdf):
    return formes(sdf, "collision")


@pytest.fixture(scope="module")
def visuels(sdf):
    return formes(sdf, "visual")


@pytest.fixture(scope="module")
def route():
    with YAML.open(encoding="utf-8") as f:
        return load_route(yaml.safe_load(f))


TRACE = [(0.0, 0.0)] + list(WAYPOINTS)      # + la pose de spawn de Didier (0, 0)


def obstacles(collisions):
    """Collisions qui gênent un robot posé au sol : au-dessus de la dalle, sous 1 m."""
    return [c for c in collisions if c.zmax > 0.02 and c.zmin < HAUTEUR_DIDIER]


# ------------------------------------------------------------------ tests des helpers

def test_helper_hull_et_distances():
    carre = hull([(0, 0), (2, 0), (2, 2), (0, 2), (1, 1)])
    assert sorted(carre) == [(0, 0), (0, 2), (2, 0), (2, 2)]
    assert dist_point_segment((1, 1), (0, 0), (2, 0)) == pytest.approx(1.0)
    assert dist_point_segment((5, 0), (0, 0), (2, 0)) == pytest.approx(3.0)       # hors du segment : l'extrémité
    assert dist_segments((0, 0), (2, 0), (1, -1), (1, 1)) == 0.0                   # croisement
    assert dist_segments((0, 0), (2, 0), (0, 1), (2, 1)) == pytest.approx(1.0)    # parallèles
    ligne = [(0, 0), (10, 0)]
    assert dist_ligne_polygone(ligne, hull([(4, 1.2), (5, 1.2), (5, 2), (4, 2)])) == pytest.approx(1.2)
    assert dist_ligne_polygone(ligne, hull([(4, -1), (5, -1), (5, 1), (4, 1)])) == 0.0   # traversé
    assert dist_ligne_polygone([(4.5, 0), (4.6, 0)], hull([(4, -1), (5, -1), (5, 1), (4, 1)])) == 0.0   # ligne DANS le polygone
    assert dist_ligne_polygone([(0, 0), (1, 0)], hull([(3, -1), (4, -1), (4, 1), (3, 1)])) == pytest.approx(2.0)


def test_helper_projection_cote_signe_et_abscisse():
    ligne = [(0, 0), (10, 0), (20, -10)]
    s, cote, d = projeter(ligne, (5, 2))
    assert (s, cote, d) == (pytest.approx(5.0), pytest.approx(2.0), pytest.approx(2.0))   # +y = côté Loire = positif
    s, cote, _ = projeter(ligne, (5, -3))
    assert cote == pytest.approx(-3.0)
    s, _, d = projeter(ligne, (25, -15))                      # au-delà du bout : projection clampée
    assert s == pytest.approx(10 + math.hypot(10, 10)) and d == pytest.approx(math.hypot(5, 5))


def test_helper_formes_boite_cylindre_sphere_avec_rotations():
    def une(xml, tag="collision"):
        racine = ET.fromstring(f"<sdf><world>{xml}</world></sdf>")
        return formes(racine, tag)

    # boîte 2 x 1 x 0,5, lacet 90° : l'étendue en x devient 1 et celle en y 2.
    f = une('<model name="m"><link name="l"><pose>10 20 1 0 0 1.5707963</pose><collision name="c"><geometry>'
            '<box><size>2 1 0.5</size></box></geometry></collision></link></model>')[0]
    xs, ys = [p[0] for p in f.pts3d], [p[1] for p in f.pts3d]
    assert (min(xs), max(xs)) == (pytest.approx(9.5, abs=1e-4), pytest.approx(10.5, abs=1e-4))
    assert (min(ys), max(ys)) == (pytest.approx(19.0, abs=1e-4), pytest.approx(21.0, abs=1e-4))
    assert (f.zmin, f.zmax) == (pytest.approx(0.75), pytest.approx(1.25))
    # pose du MODÈLE composée avec celle du lien (décalage dans le repère tourné du modèle).
    f = une('<model name="m"><pose>100 0 0 0 0 1.5707963</pose><link name="l"><pose>2 0 0 0 0 0</pose><collision name="c">'
            '<geometry><box><size>1 1 1</size></box></geometry></collision></link></model>')[0]
    assert f.centre == pytest.approx((100.0, 2.0), abs=1e-4)             # +x du modèle pointe vers +y monde
    # cylindre couché (pitch 90°) de longueur 4 : s'étend de ±2 en x, ±rayon en y.
    f = une('<model name="m"><link name="l"><pose>0 0 1 0 1.5707963 0</pose><collision name="c"><geometry>'
            '<cylinder><radius>0.5</radius><length>4</length></cylinder></geometry></collision></link></model>')[0]
    xs, ys = [p[0] for p in f.pts3d], [p[1] for p in f.pts3d]
    assert max(xs) == pytest.approx(2.0, abs=1e-4) and max(ys) == pytest.approx(0.5, abs=1e-3)
    # sphère de rayon 0,75 centrée à z = 0 : empreinte de rayon ~0,75, z de -0,75 à 0,75.
    f = une('<model name="m"><link name="l"><collision name="c"><geometry><sphere><radius>0.75</radius></sphere>'
            '</geometry></collision></link></model>')[0]
    assert max(math.hypot(*p) for p in f.poly) == pytest.approx(0.75, abs=1e-6)
    assert (f.zmin, f.zmax) == (pytest.approx(-0.75), pytest.approx(0.75))


# ------------------------------------------------------------------ 1. le SDF et son contrat

def test_sdf_contrat_stage_plugins_et_primitives_seules(sdf):
    world = sdf.find("world")
    assert world.get("name") == "stage"          # CONTRAT bridge LED (/world/stage/material_color)
    plugins = {p.get("filename"): p.get("name") for p in world.findall("plugin")}
    assert plugins == PLUGINS
    sensors = next(p for p in world.findall("plugin") if p.get("filename") == "gz-sim-sensors-system")
    assert sensors.find("render_engine").text == "ogre2"
    # primitives seules, aucune dépendance réseau, pas de ground plane : le vide fait la chute.
    tags = {el.tag for el in sdf.iter()}
    assert tags.isdisjoint({"plane", "mesh", "heightmap", "uri", "include", "image", "polyline"})
    assert world.find("light").get("type") == "directional"


def test_sdf_modeles_statiques_et_friction_unitaire(sdf):
    for model in sdf.find("world").findall("model"):
        assert model.find("static").text.strip() == "true", model.get("name")
        assert model.findall("link"), model.get("name")
        for link in model.findall("link"):
            for col in link.findall("collision"):
                ode = col.find("surface/friction/ode")
                assert (ode.find("mu").text, ode.find("mu2").text) == ("1.0", "1.0"), (model.get("name"), link.get("name"))


def test_trente_modeles_nommes_comme_les_poi_dans_l_ordre(sdf):
    noms = [m.get("name") for m in sdf.find("world").findall("model")]
    for n in NOMS:
        assert noms.count(n) == 1, n                                    # exactement un modèle par POI
    assert len(NOMS) == 30 and len(set(NOMS)) == 30
    assert [n for n in noms if n in NOMS] == list(NOMS)                 # même ordre que la marche
    assert set(noms) - set(NOMS) == DECOR                               # et rien d'autre que le décor connu
    for m in sdf.find("world").findall("model"):
        assert len(m.findall("link")) >= 1, m.get("name")


# ------------------------------------------------------------------ 2. les dalles et le tracé

def test_dalles_gravees_dans_le_sdf(collisions):
    esp = {c.lien: c for c in collisions if c.modele == "esplanade"}
    assert set(esp) == {"mail_beton", "quai_dalles"}
    mail, quai = esp["mail_beton"], esp["quai_dalles"]
    for dalle in (mail, quai):
        assert dalle.zmax == pytest.approx(0.0, abs=1e-9)              # SURFACE à z = 0
        assert dalle.zmin == pytest.approx(-0.12, abs=1e-9)            # épaisseur 0,12
    xs = [p[0] for p in mail.pts3d]
    ys = [p[1] for p in mail.pts3d]
    assert (min(xs), max(xs)) == (pytest.approx(MAIL_X[0], abs=1e-3), pytest.approx(MAIL_X[1], abs=1e-3))
    assert (min(ys), max(ys)) == (pytest.approx(-6.0, abs=1e-6), pytest.approx(6.0, abs=1e-6))
    # dalle du quai : centre, longueur, largeur et cap gravés.
    assert quai.centre == pytest.approx(QUAI_CENTRE, abs=2e-3)
    u = (math.cos(CAP_QUAI), math.sin(CAP_QUAI))
    long_ = max(((p[0] - quai.centre[0]) * u[0] + (p[1] - quai.centre[1]) * u[1]) for p in quai.pts3d) * 2
    larg_ = max((-(p[0] - quai.centre[0]) * u[1] + (p[1] - quai.centre[1]) * u[0]) for p in quai.pts3d) * 2
    assert long_ == pytest.approx(QUAI_LONGUEUR, abs=2e-3) and larg_ == pytest.approx(DALLE_LARGEUR, abs=1e-3)
    # cohérence interne des constantes gravées (une coquille ici fausserait les tests suivants).
    d_mid = (QUAI_D[0] + QUAI_D[1]) / 2
    assert (COUDEE[0] + d_mid * u[0], COUDEE[1] + d_mid * u[1]) == pytest.approx(QUAI_CENTRE, abs=2e-3)
    assert QUAI_D[1] - QUAI_D[0] == pytest.approx(QUAI_LONGUEUR, abs=1e-6)
    assert MAIL_X[1] == pytest.approx(COUDEE[0] + 6 * math.tan(math.radians(COUDEE_DEG / 2)), abs=1e-2)   # mitre


def sur_les_dalles(p, marge):
    """Appartenance aux dalles, avec la géométrie GRAVÉE : le Mail tel quel, le quai par
    rotation inverse de la coudée (repère d = le long du quai, v = en travers)."""
    x, y = p
    if MAIL_X[0] <= x <= MAIL_X[1] and abs(y) <= DALLE_LARGEUR / 2 - marge:
        return True
    dx, dy = x - COUDEE[0], y - COUDEE[1]
    d = dx * math.cos(CAP_QUAI) + dy * math.sin(CAP_QUAI)        # le long du quai
    v = -dx * math.sin(CAP_QUAI) + dy * math.cos(CAP_QUAI)       # en travers
    return QUAI_D[0] <= d <= QUAI_D[1] and abs(v) <= DALLE_LARGEUR / 2 - marge


def test_helper_sur_les_dalles_refuse_le_vide():
    c = COTE_LOIRE
    assert sur_les_dalles((0, 0), 1.0) and sur_les_dalles((70, 0), 1.0) and sur_les_dalles((100, -21 * c), 1.0)
    assert not sur_les_dalles((30, 5.5 * c), 1.0)       # trop près du bord Loire
    assert not sur_les_dalles((30, -7 * c), 0.0)        # côté bâtiments : le vide
    assert not sur_les_dalles((100, 0), 0.0)            # dans l'eau, côté Loire du quai
    assert not sur_les_dalles((160, -60 * c), 0.0)      # au-delà du bout du quai
    assert not sur_les_dalles((-6, 0), 0.0)             # derrière le départ


def test_waypoints_dans_les_dalles_et_geometrie_du_trace(route):
    assert route.waypoints == WAYPOINTS                  # le YAML EST la polyligne gravée
    assert len(route.waypoints) == 18
    for p in route.waypoints:
        assert sur_les_dalles(p, 4.0), p                 # au cœur des dalles (>= 4 m de chaque bord)
    xs = [x for x, _ in route.waypoints]
    assert xs == sorted(xs)                              # on avance, jamais en arrière
    pas = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(route.waypoints, route.waypoints[1:])]
    assert all(8.0 <= d <= 10.0 for d in pas), pas       # un waypoint tous les 8-10 m
    # la coudée : un waypoint exactement sur le sommet, 35° vers y négatif.
    i = route.waypoints.index(COUDEE)
    a = math.atan2(route.waypoints[i][1] - route.waypoints[i - 1][1], route.waypoints[i][0] - route.waypoints[i - 1][0])
    b = math.atan2(route.waypoints[i + 1][1] - route.waypoints[i][1], route.waypoints[i + 1][0] - route.waypoints[i][0])
    assert a == pytest.approx(0.0) and math.degrees(b) == pytest.approx(-COTE_LOIRE * COUDEE_DEG, abs=0.2)
    assert longueur(route.waypoints) == pytest.approx(158.8, abs=0.1)
    # Didier est posé en (0, 0) par le launch : sur les dalles, à 2 m du premier waypoint.
    assert sur_les_dalles((0.0, 0.0), 4.0)


# ------------------------------------------------------------------ 3. les POI

def test_yaml_trente_poi_dans_l_ordre_avec_rayons_et_positions_gravees(route):
    assert tuple(p.name for p in route.pois) == NOMS
    for p, (nom, x, y, r) in zip(route.pois, POIS):
        assert (p.x, p.y, p.radius) == (pytest.approx(x, abs=5e-3), pytest.approx(y, abs=5e-3), pytest.approx(r)), nom
    # rayons du brief : 2,5 par défaut ; 3 terrasse/cale/pelouse/hangar ; 4 loin ; 6 la Titan.
    attendus = {n: 2.5 for n in NOMS}
    attendus.update(terrasse=3, cale=3, pelouse=3, hangar_bananes=3, nefs=4, grue_jaune=4, carrousel=4, titan_grise=6)
    assert {p.name: p.radius for p in route.pois} == attendus


def test_chaque_poi_est_declenchable_par_un_didier_qui_suit_le_trace(route):
    """PoiWatcher : enter si d < rayon (strict). Un suiveur qui passe pile sur la polyligne
    ne déclenche que si distance(centre, tracé) <= rayon - 1 m (marge sur son écart latéral)."""
    for p in route.pois:
        d = dist_ligne_point(route.waypoints, (p.x, p.y))
        assert d <= p.radius - RAYON_MIN_MARGE + 1e-9, f"{p.name} : {d:.2f} m du tracé pour un rayon de {p.radius}"
        assert d <= 4.0, p.name                          # et jamais loin du tracé
    # le but : la Titan se déclenche avant le dernier waypoint, qui est dans son rayon.
    titan = route.pois[-1]
    assert math.hypot(route.waypoints[-1][0] - titan.x, route.waypoints[-1][1] - titan.y) < titan.radius - RAYON_MIN_MARGE


def test_modele_sdf_a_la_position_du_poi(sdf, route):
    """La POSE d'un modèle EST l'ancre du POI (les liens, eux, sont décalés dans son repère)."""
    poses = {m.get("name"): _pose(m) for m in sdf.find("world").findall("model")}
    for p in route.pois:
        x, y, z = poses[p.name][:3]
        assert math.hypot(x - p.x, y - p.y) <= 0.5, p.name
        assert z == 0.0, p.name


def test_espacement_des_centres_consecutifs(route):
    pois = route.pois
    for a, b in zip(pois, pois[1:]):
        assert b.x - a.x >= ESPACEMENT_MIN, f"{a.name}->{b.name} en x : {b.x - a.x:.2f}"
        assert math.hypot(b.x - a.x, b.y - a.y) >= ESPACEMENT_MIN, (a.name, b.name)
        sa, sb = projeter(route.waypoints, (a.x, a.y))[0], projeter(route.waypoints, (b.x, b.y))[0]
        assert sb - sa >= ESPACEMENT_MIN, f"{a.name}->{b.name} le long du tracé : {sb - sa:.2f}"
    # la Titan (rayon 6) laisse de la place au POI qui la précède (rayon 2,5) : 8 m en x.
    assert pois[-1].x - pois[-2].x >= 8.0


def test_les_poi_sont_sur_le_cote_de_leur_objet(route):
    """Quinconce (en x < 70) et côtés imposés par l'étude : côté Loire (> 0 ci-dessous) pour
    l'éléphant, le carrousel, les anneaux, la cale, la grue jaune... ; côté bâtiments (< 0)
    pour les Nefs, le Hangar à Bananes, le tag... Mesuré par rapport au tracé et à COTE_LOIRE."""
    cote = {p.name: COTE_LOIRE * projeter(route.waypoints, (p.x, p.y))[1] for p in route.pois}    # > 0 : côté Loire
    for nom in ("elephant", "carrousel", "poster_bizarre", "pigeon", "grue_jaune", "cale", "panneau_info",
                "anneaux", "bollard", "loire", "chien", "tas_de_sable", "bouche_incendie", "conteneur_rouge"):
        assert cote[nom] > 0.5, nom
    for nom in ("nefs", "table_basse", "poubelle_tri", "banc", "terrasse", "velo_cadenas", "lampadaire",
                "plot_chantier", "caisse_bois", "hangar_bananes", "horloge_arretee", "pelouse", "tag_mur"):
        assert cote[nom] < -0.5, nom
    for nom in ("flaque", "rails", "titan_grise"):
        assert abs(cote[nom]) < 0.05, nom                # POI posés SUR le tracé (visuels sans collision, ou le but)


# ------------------------------------------------------------------ 4. dégagement du tracé

def test_aucun_objet_plein_a_moins_de_1_5_m_du_trace(collisions):
    obs = obstacles(collisions)
    assert len(obs) > 100                                 # le test n'est pas vide : tout le décor bas y passe
    pires = sorted(((dist_ligne_polygone(TRACE, o.poly), o.modele, o.lien) for o in obs))[:5]
    assert pires[0][0] >= DEGAGEMENT_MIN, f"trop près du tracé : {pires}"
    # et le test voit bien les objets proches (sinon un monde « vidé » passerait aussi).
    assert pires[0][0] < 2.5, pires


def test_flaque_rails_et_pelouse_sont_sans_collision_et_au_ras_du_sol(sdf, collisions, visuels):
    sans = {"flaque", "rails", "pelouse"}
    for nom in ("flaque", "rails"):
        assert not [c for c in collisions if c.modele == nom], nom
        vis = [v for v in visuels if v.modele == nom]
        assert vis and all(v.zmin >= -1e-9 and v.zmax <= 0.005 for v in vis), nom      # 1 à 5 mm au-dessus de la dalle
    assert not [c for c in collisions if c.modele == "pelouse" and c.lien == "herbe"]
    assert all(v.zmax <= 0.01 for v in visuels if v.modele == "pelouse" and v.lien == "herbe")
    # la flaque est bien SUR le tracé (c'est son but) : elle le coupe.
    assert all(dist_ligne_polygone(TRACE, v.poly) == 0.0 for v in visuels if v.modele == "flaque" and v.lien == "grande")
    assert sans <= set(NOMS)


def test_chaque_modele_poi_a_un_element_pres_du_trace(visuels):
    """Garde-fou contre un modèle dont les liens auraient dérivé loin de son ancre."""
    for nom in NOMS:
        d = min(dist_ligne_polygone(TRACE, v.poly) for v in visuels if v.modele == nom)
        assert d <= 8.0, f"{nom} : son élément le plus proche est à {d:.1f} m du tracé"


def test_la_titan_barre_le_quai_derriere_le_dernier_waypoint(collisions):
    dernier = WAYPOINTS[-1]
    socle = next(c for c in collisions if c.modele == "titan_grise" and c.lien == "socle")
    d = dist_ligne_polygone([dernier, (dernier[0] + 0.001, dernier[1])], socle.poly)
    assert 1.5 <= d <= 4.0, f"socle à {d:.2f} m du dernier waypoint : « au pied » = entre 1,5 et 4 m"
    u, n = (math.cos(CAP_QUAI), math.sin(CAP_QUAI)), (-math.sin(CAP_QUAI), math.cos(CAP_QUAI))
    for decalage in (-5.0, -3.0, 0.0, 3.0, 5.0):          # tout le travers du quai (12 m) est fermé
        depart = (dernier[0] + decalage * n[0], dernier[1] + decalage * n[1])
        fin = (depart[0] + 10 * u[0], depart[1] + 10 * u[1])
        assert dist_ligne_polygone([depart, fin], socle.poly) == 0.0, decalage
    assert socle.zmax >= 2.5 and (socle.zmax - socle.zmin) >= 2.5      # un vrai mur, pas un tapis


# ------------------------------------------------------------------ 5. Loire, ressaut, bâtiments, grues

def test_loire_cote_loire_ressaut_de_12_cm_et_eau_un_metre_plus_bas(collisions):
    bord = [c for c in collisions if c.modele == "bordure_quai"]
    assert {c.lien for c in bord} == {"bordure_mail", "bordure_quai"}
    for c in bord:
        assert (c.zmin, c.zmax) == (pytest.approx(0.0, abs=1e-9), pytest.approx(0.12, abs=1e-9))   # ressaut de 12 cm
        assert dist_ligne_polygone(TRACE, c.poly) == pytest.approx(6.0, abs=0.05)                    # au bord des dalles
        assert COTE_LOIRE * projeter(TRACE, c.centre)[1] > 0                                         # côté Loire
    eau = [c for c in collisions if c.modele == "loire"]
    assert {c.lien for c in eau} == {"eau_mail", "eau_quai"}
    for c in eau:
        assert c.zmax == pytest.approx(-1.0, abs=1e-9)                   # surface 1 m sous les dalles
        assert dist_ligne_polygone(TRACE, c.poly) == pytest.approx(6.3, abs=0.05)   # derrière le ressaut (6,0 + 0,3)
        assert c.zmin <= -1.4                                            # épaisse : la chute s'arrête
    # l'eau couvre tout le côté Loire, mailles comprises, et AUCUN point côté bâtiments.
    def sur_eau(p):
        return any(dans_polygone_convexe(p, c.poly) for c in eau)
    c = COTE_LOIRE
    u, n = (math.cos(CAP_QUAI), math.sin(CAP_QUAI)), (-math.sin(CAP_QUAI), math.cos(CAP_QUAI))   # n = à gauche de la marche
    for p in [(0, 10 * c), (35, 8 * c), (66, 7 * c), (72, 10 * c)] + [(COUDEE[0] + d * u[0] + 8 * c * n[0], COUDEE[1] + d * u[1] + 8 * c * n[1]) for d in (0, 10, 40, 80, 100)]:
        assert sur_eau(p), p
    for p in [(0, -10 * c), (35, -8 * c), (72, -10 * c)] + [(COUDEE[0] + d * u[0] - 8 * c * n[0], COUDEE[1] + d * u[1] - 8 * c * n[1]) for d in (10, 40, 80, 100)]:
        assert not sur_eau(p), p
    # chute possible côté Loire seulement : rien sous les dalles de l'autre côté (pas de ground plane).
    assert not [c for c in collisions if c.zmax < -0.5 and c.modele != "loire" and c.modele != "grue_jaune"]


def test_batiments_cote_batiments_et_loire_cote_loire_mesures_par_rapport_au_trace(collisions):
    def cote_min_max(modele, lien=None):
        lst = [c for c in collisions if c.modele == modele and (lien is None or c.lien == lien)]
        cotes = [COTE_LOIRE * projeter(TRACE, p)[1] for c in lst for p in c.poly]     # > 0 : côté Loire
        return min(cotes), max(cotes)

    lo, hi = cote_min_max("nefs", "hall")
    assert hi <= -6.9 and lo >= -19.1                   # hangar 12 m de profondeur, face à v = -7
    lo, hi = cote_min_max("hangar_bananes", "corps")
    assert hi <= -6.9 and lo >= -17.1
    lo, hi = cote_min_max("facades")
    assert hi <= -6.2                                    # toutes les façades derrière le bord gauche des dalles (à l'angle
    #                                                    intérieur de la coudée, le Mail est à 6,31 m du coin : c'est voulu)
    lo, hi = cote_min_max("tag_mur", "fond")
    assert hi <= -6.9 and lo >= -7.1                     # plaqué contre le mur
    lo, hi = cote_min_max("grue_jaune", "jetee")
    assert lo >= 5.9                                     # la jetée part du bord des dalles, dans l'eau
    lo, hi = cote_min_max("cale", "rampe")
    assert lo >= 6.2 and hi <= 12.0                      # la cale plonge côté Loire


def test_hauteurs_des_grues_vers_25_m(collisions):
    for nom in ("grue_jaune", "titan_grise"):
        haut = max(c.zmax for c in collisions if c.modele == nom)
        assert 23.5 <= haut <= 26.5, f"{nom} : {haut:.1f} m"
    # grue jaune sur sa jetée DANS l'eau, loin du tracé ; la grise est au bout du quai.
    jaune = [c for c in collisions if c.modele == "grue_jaune" and c.lien.startswith("pied_")]
    assert len(jaune) == 4 and all(c.zmax > 11.0 for c in jaune)
    assert all(COTE_LOIRE * projeter(TRACE, c.centre)[1] > 8.0 for c in jaune)
    titan = [c for c in collisions if c.modele == "titan_grise" and c.lien.startswith("pied_")]
    assert len(titan) == 4 and all(c.zmax > 11.0 for c in titan)


def test_les_anneaux_sont_trois_et_creux(collisions):
    """Trois anneaux de 12 segments chacun, aucun segment ne ferme le centre."""
    segs = [c for c in collisions if c.modele == "anneaux"]
    assert len(segs) == 36
    for r in range(1, 4):
        anneau = [c for c in segs if c.lien.startswith(f"anneau_{r}_")]
        assert len(anneau) == 12
        cy = sum(c.centre[0] for c in anneau) / 12, sum(c.centre[1] for c in anneau) / 12
        zc = sum((c.zmin + c.zmax) / 2 for c in anneau) / 12
        for c in anneau:
            rayon = math.hypot(math.hypot(c.centre[0] - cy[0], c.centre[1] - cy[1]), (c.zmin + c.zmax) / 2 - zc)
            assert 1.0 <= rayon <= 1.3, c.lien           # sur le cercle (R = 1,2), centre libre


# ------------------------------------------------------------------ 6. cohérence avec l'itinéraire

def test_yaml_brut_meme_ordre_que_la_route_validee(route):
    """Les champs de jeu (`lubie`, `fermeture`) ne sont PAS figés ici : ils appartiennent au
    régisseur (scenarios/chantiers.yaml, test_scenario). Seuls les noms sont un contrat commun."""
    brut = yaml.safe_load(YAML.read_text(encoding="utf-8"))
    assert [p["name"] for p in brut["pois"]] == list(NOMS)
    assert len(route.pois) == 30
