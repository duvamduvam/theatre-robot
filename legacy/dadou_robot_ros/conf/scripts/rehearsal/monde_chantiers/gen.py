#!/usr/bin/env python3
"""Générateur de robot_sim/worlds/chantiers.sdf (lot R3, étude §13.2-13.3).

    python3 gen.py ../../../ros2_dependencies/robot_sim/worlds/chantiers.sdf

Le SDF livré est GÉNÉRÉ par ce script (poses des liens relatives à l'ancre de
chaque POI : illisibles à la main, c'est pour ça qu'on versionne le
générateur). anchors.py = la source des x/y/rayon des 30 POI (ordre §13.3,
règle rayon >= écart latéral + 1 m) ; config/chantiers.yaml et les tables de
robot/tests/unit/test_chantiers_world.py en sont des COPIES gravées : toute
retouche se fait ICI, puis on régénère et on recale YAML + test (sinon les
tests rougissent — c'est voulu). Vérification : le SDF du dépôt doit être
byte-identique à la sortie de ce script (fait le 14/10).

Repère chemin : s = abscisse curviligne le long de la marche, v = écart latéral
(+ = côté Loire). Repère monde DIRECT (x = marche, z vertical) : la droite du
marcheur est y < 0, d'où MIROIR=1 par défaut (la première version avait la
Loire en y > 0, une image miroir — MIROIR=0 la régénère, pour mémoire).
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import anchors as A  # noqa: E402

MIROIR = os.environ.get("MIROIR", "1") == "1"
A.SGN = -1 if MIROIR else 1
SGN = A.SGN
TH, COSA, SINA, C_X = A.TH, A.COSA, A.SINA, A.C_X
QUAI_YAW = -SGN * TH


def quai_world(d, v):
    """d = s - 70 (peut être négatif près de la coudée), v = écart latéral."""
    return (C_X + d * COSA + v * SINA, -SGN * d * SINA + SGN * v * COSA)


def fr(v):
    return fnum(v).replace('.', ',')


def heading(s):
    return 0.0 if s <= C_X else QUAI_YAW


def fnum(v):
    t = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if t in ("-0", "") else t


FRICTION = "<surface><friction><ode><mu>1.0</mu><mu2>1.0</mu2></ode></friction></surface>"


def geom_xml(g):
    kind, d = g
    if kind == "box":
        return f"<box><size>{fnum(d[0])} {fnum(d[1])} {fnum(d[2])}</size></box>"
    if kind == "cyl":
        return f"<cylinder><radius>{fnum(d[0])}</radius><length>{fnum(d[1])}</length></cylinder>"
    if kind == "sph":
        return f"<sphere><radius>{fnum(d[0])}</radius></sphere>"
    raise ValueError(kind)


def material(col, emi=False):
    amb = " ".join(f"{c * 0.7:.2f}" for c in col)
    dif = " ".join(f"{c:.2f}" for c in col)
    e = "<emissive>1 1 1 1</emissive>" if emi else ""
    return f"<material><ambient>{amb} 1</ambient><diffuse>{dif} 1</diffuse>{e}</material>"


class Model:
    def __init__(self, name, comment, s=None, va=None):
        self.name, self.comment, self.links = name, comment, []
        self.s, self.va = s, va
        if s is not None:
            x, y = A.world(s, va)
            self.x, self.y = round(x, 2), round(y, 2)   # = valeurs du YAML, exactement
            self.yaw = heading(s)
        else:
            self.x = self.y = self.yaw = 0.0

    # ---- ajout d'un lien en coordonnées CHEMIN (modèle ancré) ou MONDE (décor)
    def add(self, nm, geom, pos, rpy=(0, 0, 0), col=(0.7, 0.7, 0.7), coll=True, emi=False):
        assert nm not in [l[0] for l in self.links], (self.name, nm)
        if self.s is not None:
            du, v, z = pos
            pose = (du, SGN * (v - self.va), z) + tuple(rpy)
        else:
            pose = tuple(pos) + tuple(rpy)
        self.links.append((nm, geom, pose, col, coll, emi))

    def add_world(self, nm, geom, w, wyaw, col, coll=True):
        """Lien défini en coordonnées MONDE (x, y, z) + lacet, dans un modèle ancré."""
        dx, dy = w[0] - self.x, w[1] - self.y
        c, s_ = math.cos(self.yaw), math.sin(self.yaw)
        lx, ly = dx * c + dy * s_, -dx * s_ + dy * c
        self.links.append((nm, geom, (lx, ly, w[2], 0, 0, wyaw - self.yaw), col, coll, False))

    def box(self, nm, size, du, v, z, col, **kw):
        self.add(nm, ("box", size), (du, v, z), col=col, **kw)

    def cyl(self, nm, r, l, du, v, z, col, **kw):
        self.add(nm, ("cyl", (r, l)), (du, v, z), col=col, **kw)

    def sph(self, nm, r, du, v, z, col, **kw):
        self.add(nm, ("sph", (r,)), (du, v, z), col=col, **kw)

    def xml(self):
        out = []
        if self.comment:
            out.append("    <!-- " + self.comment.replace("--", "-") + " -->")
        out.append(f'    <model name="{self.name}">')
        out.append("      <static>true</static>")
        if self.s is not None:
            out.append(f"      <pose>{fnum(self.x)} {fnum(self.y)} 0 0 0 {fnum(self.yaw)}</pose>")
        for nm, geom, pose, col, coll, emi in self.links:
            g = geom_xml(geom)
            out.append(f'      <link name="{nm}">')
            out.append("        <pose>" + " ".join(fnum(p) for p in pose) + "</pose>")
            if coll:
                out.append(f'        <collision name="collision"><geometry>{g}</geometry>{FRICTION}</collision>')
            out.append(f'        <visual name="visual"><geometry>{g}</geometry>{material(col, emi)}</visual>')
            out.append("      </link>")
        out.append("    </model>")
        return "\n".join(out)


# --- décor en coordonnées monde, à partir de plages (x ou d) / v / z ----------
def mbox(m, nm, x0, x1, v0, v1, z0, z1, col, **kw):
    m.add(nm, ("box", (x1 - x0, v1 - v0, z1 - z0)), ((x0 + x1) / 2, SGN * (v0 + v1) / 2, (z0 + z1) / 2), col=col, **kw)


def qbox(m, nm, d0, d1, v0, v1, z0, z1, col, **kw):
    x, y = quai_world((d0 + d1) / 2, (v0 + v1) / 2)
    m.add(nm, ("box", (d1 - d0, v1 - v0, z1 - z0)), (x, y, (z0 + z1) / 2), (0, 0, QUAI_YAW), col=col, **kw)


# =============================================================================
# Ancres des 30 POI (anchors.py = source des x/y/radius ; ordre = §13.3)
# =============================================================================
POI = A.compute()
BY = {p["name"]: p for p in POI}
S = {p["name"]: p["s"] for p in POI}
S_LAST_WP = round(S["titan_grise"] - 1.5, 2)

M = {}   # nom -> Model


def obj(name, comment):
    p = BY[name]
    m = Model(name, comment, p["s"], p["va"])
    M[name] = m
    return m


def anchor_txt(name):
    p = BY[name]
    return f"ancre = POI ({fnum(p['x'])}, {fnum(p['y'])}), rayon {fnum(p['r'])}"


# couleurs
GRIS_P = (0.56, 0.58, 0.62); GRIS_F = (0.28, 0.29, 0.31); BOIS = (0.58, 0.38, 0.20)
BOIS_F = (0.32, 0.21, 0.11); ROUGE = (0.85, 0.12, 0.10); JAUNE = (0.95, 0.78, 0.08)
BLANC = (0.95, 0.95, 0.92); NOIR = (0.08, 0.08, 0.09); VERT = (0.15, 0.65, 0.25)
ORANGE = (1.0, 0.45, 0.05); BLEU = (0.15, 0.38, 0.80)

# ---- 1 nefs ------------------------------------------------------------------
m = obj("nefs", f"1. Les Nefs (départ) : hangar 30 x 12 x 10 côté bâtiments, toit bleu, face à v = -7 ; occupe x de 0 à 30. {anchor_txt('nefs')}. Liens exprimés dans le repère du modèle (x le long de la marche, y à gauche de la marche), décalés de l'ancre.")
m.box("hall", (30, 12, 8.4), 11, -13, 4.2, (0.80, 0.76, 0.68))
m.box("toit", (30.8, 12.8, 1.6), 11, -13, 9.2, BLEU)
m.box("porte", (6, 0.12, 5), 11, -6.94, 2.5, (0.20, 0.25, 0.30))
m.box("bandeau_vitres", (24, 0.1, 1.0), 11, -6.95, 6.4, (0.45, 0.62, 0.78), coll=False)

# ---- 2 elephant --------------------------------------------------------------
m = obj("elephant", f"2. L'Éléphant mécanique : boîte grise + 4 pieds + tête + oreilles + trompe, côté Loire (centre v = 2,9). {anchor_txt('elephant')}.")
vv = 2.9
m.box("corps", (2.4, 1.2, 1.2), 0, vv, 1.5, GRIS_P)
for i, (dx, dv) in enumerate([(0.85, 0.4), (0.85, -0.4), (-0.85, 0.4), (-0.85, -0.4)]):
    m.cyl(f"patte_{i + 1}", 0.17, 0.9, dx, vv + dv, 0.45, (0.45, 0.47, 0.50))
m.box("tete", (0.9, 0.9, 0.95), 1.5, vv, 1.85, GRIS_P)
for i, sg in enumerate((1, -1)):
    m.box(f"oreille_{i + 1}", (0.5, 0.08, 0.75), 1.25, vv + sg * 0.66, 1.9, (0.62, 0.55, 0.58))
m.add("trompe", ("cyl", (0.14, 1.3)), (2.1, vv, 0.95), (0, -0.35, 0), col=(0.50, 0.52, 0.56))

# ---- 3 carrousel -------------------------------------------------------------
m = obj("carrousel", f"3. Carrousel : plateau + 6 poteaux rayés + toit étagé (le cône est empilé : primitives seules), loin, côté Loire (centre v = 4,6). {anchor_txt('carrousel')}.")
vv = 4.6
m.cyl("plateau", 1.3, 0.3, 0, vv, 0.15, (0.92, 0.92, 0.90))
m.cyl("mat", 0.1, 2.2, 0, vv, 1.4, (0.85, 0.75, 0.2))
for k in range(6):
    a = math.radians(60 * k)
    m.cyl(f"poteau_{k + 1}", 0.05, 1.8, 1.1 * math.cos(a), vv + 1.1 * math.sin(a), 1.2, ROUGE if k % 2 == 0 else BLANC)
m.cyl("toit_1", 1.5, 0.18, 0, vv, 2.2, ROUGE)
m.cyl("toit_2", 1.05, 0.18, 0, vv, 2.38, BLANC)
m.cyl("toit_3", 0.6, 0.18, 0, vv, 2.56, ROUGE)
m.cyl("toit_pointe", 0.25, 0.3, 0, vv, 2.8, JAUNE)

# ---- 4 table_basse -----------------------------------------------------------
m = obj("table_basse", f"4. Table basse (30 cm) : le scandale d'urbanisme, côté bâtiments (centre v = -2,1). {anchor_txt('table_basse')}.")
vv = -2.1
m.box("plateau", (1.2, 0.6, 0.04), 0, vv, 0.30, BOIS)
for i, (dx, dv) in enumerate([(0.55, 0.25), (0.55, -0.25), (-0.55, 0.25), (-0.55, -0.25)]):
    m.box(f"pied_{i + 1}", (0.05, 0.05, 0.28), dx, vv + dv, 0.14, BOIS_F)
m.box("petition", (0.3, 0.22, 0.01), 0.2, vv, 0.325, BLANC, coll=False)

# ---- 5 poster_bizarre --------------------------------------------------------
m = obj("poster_bizarre", f"5. Poster bizarre : panneau violet, visage vert à lunettes (le chat qui juge), sur deux pieds, côté Loire (v = 2,7). {anchor_txt('poster_bizarre')}.")
vv = 2.7
for i, sg in enumerate((1, -1)):
    m.box(f"pied_{i + 1}", (0.06, 0.06, 0.7), sg * 0.45, vv, 0.35, (0.30, 0.30, 0.32))
m.box("panneau", (1.1, 0.05, 1.4), 0, vv, 1.2, (0.45, 0.12, 0.68))
m.box("visage", (0.62, 0.02, 0.6), 0, vv - 0.035, 1.25, (0.15, 0.78, 0.30), coll=False)
for i, sg in enumerate((1, -1)):
    m.box(f"oeil_{i + 1}", (0.14, 0.02, 0.14), sg * 0.16, vv - 0.055, 1.35, (1.0, 0.9, 0.1), coll=False)
m.box("lunettes", (0.6, 0.02, 0.04), 0, vv - 0.075, 1.35, NOIR, coll=False)

# ---- 6 poubelle_tri ----------------------------------------------------------
m = obj("poubelle_tri", f"6. Trois poubelles de tri (jaune, verte, grise), côté bâtiments (v = -2,4). {anchor_txt('poubelle_tri')}.")
vv = -2.4
for i, (dx, c, cl) in enumerate([(-0.75, (0.95, 0.80, 0.10), (0.70, 0.58, 0.05)), (0.0, (0.12, 0.60, 0.22), (0.08, 0.40, 0.14)), (0.75, (0.50, 0.52, 0.54), (0.32, 0.33, 0.35))]):
    m.cyl(f"bac_{i + 1}", 0.27, 0.9, dx, vv, 0.45, c)
    m.cyl(f"couvercle_{i + 1}", 0.285, 0.07, dx, vv, 0.935, cl)

# ---- 7 pigeon ----------------------------------------------------------------
m = obj("pigeon", f"7. Pigeon : sphère grise sur un pied, avec tête, bec et queue, côté Loire (v = 2,4). {anchor_txt('pigeon')}.")
vv = 2.4
m.cyl("pied", 0.04, 0.5, 0, vv, 0.25, (0.25, 0.25, 0.27))
m.sph("corps", 0.2, 0, vv, 0.7, (0.62, 0.63, 0.66))
m.sph("tete", 0.1, 0.17, vv, 0.88, (0.70, 0.70, 0.74))
m.box("bec", (0.08, 0.03, 0.03), 0.28, vv, 0.87, (1.0, 0.55, 0.1))
m.box("queue", (0.28, 0.12, 0.03), -0.28, vv, 0.68, (0.45, 0.45, 0.48))

# ---- 8 banc ------------------------------------------------------------------
m = obj("banc", f"8. Banc en bois (assise + dossier côté bâtiments), côté bâtiments (v = -2,4). {anchor_txt('banc')}.")
vv = -2.4
m.box("assise", (1.8, 0.45, 0.06), 0, vv, 0.45, (0.50, 0.33, 0.17))
m.box("dossier", (1.8, 0.05, 0.4), 0, vv - 0.22, 0.72, (0.50, 0.33, 0.17))
for i, sg in enumerate((1, -1)):
    m.box(f"pied_{i + 1}", (0.08, 0.4, 0.45), sg * 0.75, vv, 0.225, (0.30, 0.20, 0.10))

# ---- 9 flaque ----------------------------------------------------------------
m = obj("flaque", f"9. Flaque : deux disques bleu sombre POSÉS SUR le tracé, SANS collision (visuel à 1 mm du sol : Didier roule dedans). {anchor_txt('flaque')}.")
m.cyl("grande", 1.1, 0.002, 0, 0, 0.001, (0.05, 0.14, 0.38), coll=False)
m.cyl("petite", 0.7, 0.002, 0.5, 0.4, 0.002, (0.10, 0.24, 0.55), coll=False)

# ---- 10 terrasse -------------------------------------------------------------
m = obj("terrasse", f"10. Terrasse de café : 2 tables, 6 chaises, 2 parasols rouge et blanc, côté bâtiments (tables à v = -3,3). {anchor_txt('terrasse')}.")
for k, (tu, pc) in enumerate([(-1.0, ROUGE), (1.3, BLANC)]):
    m.cyl(f"table_{k + 1}", 0.38, 0.75, tu, -3.3, 0.375, (0.70, 0.55, 0.35))
    for j, (cu, cv) in enumerate([(tu - 0.5, -2.65), (tu + 0.5, -2.65), (tu, -3.95)]):
        m.box(f"chaise_{k + 1}_{j + 1}", (0.4, 0.4, 0.45), cu, cv, 0.225, (0.55, 0.20, 0.15))
    m.cyl(f"parasol_mat_{k + 1}", 0.03, 2.1, tu, -3.3, 1.05, (0.5, 0.5, 0.52))
    m.cyl(f"parasol_toile_{k + 1}", 1.0, 0.05, tu, -3.3, 2.12, pc)

# ---- 11 grue_jaune -----------------------------------------------------------
def crane(m, cu, cv, z0, leg_dx, leg_dv, leg_w, leg_h, braces, deck, cab, mast, jib, counter, c_main, c_dark, c_glass):
    """Portique 4 pieds + plateforme + cabine + mât + flèche inclinée + contre-flèche."""
    bw = 0.35
    for i, (sx, sv) in enumerate([(1, 1), (1, -1), (-1, 1), (-1, -1)]):
        m.box(f"pied_{i + 1}", (leg_w, leg_w, leg_h), cu + sx * leg_dx, cv + sv * leg_dv, z0 + leg_h / 2, c_main)
    for zl in braces:
        for sv in (1, -1):
            m.box(f"entretoise_u_{int(zl * 10)}_{'p' if sv > 0 else 'm'}", (2 * leg_dx - leg_w, bw, bw), cu, cv + sv * leg_dv, z0 + zl, c_dark)
        for sx in (1, -1):
            m.box(f"entretoise_v_{int(zl * 10)}_{'p' if sx > 0 else 'm'}", (bw, 2 * leg_dv - leg_w, bw), cu + sx * leg_dx, cv, z0 + zl, c_dark)
    dsu, dsv, dsh = deck
    m.box("plateforme", (dsu, dsv, dsh), cu, cv, z0 + leg_h + dsh / 2, c_dark)
    zt = z0 + leg_h + dsh
    cdu, cdv = cab
    m.box("cabine", (3.0, 3.0, 2.8), cu + cdu, cv + cdv, zt + 1.4, c_main)
    m.box("cabine_vitre", (0.05, 2.2, 1.2), cu + cdu + 1.53, cv + cdv, zt + 1.7, c_glass, coll=False)
    mw, mh, mdu = mast
    m.box("mat", (mw, mw, mh), cu + mdu, cv, zt + mh / 2, c_main)
    zh = zt + mh - 0.2
    L, pitch, direction = jib
    p = math.radians(pitch)
    if direction == "u":
        m.add("fleche", ("box", (L, 0.9, 0.9)), (cu + mdu + L / 2 * math.cos(p), cv, zh + L / 2 * math.sin(p)), (0, -p, 0), col=c_main)
        m.box("contre_fleche", (counter, 0.9, 0.9), cu + mdu - counter / 2 - 0.5, cv, zh, c_dark)
        m.box("contrepoids", (2.0, 1.6, 1.6), cu + mdu - counter - 0.8, cv, zh - 0.6, c_dark)
    else:   # flèche vers la Loire (+v)
        m.add("fleche", ("box", (L, 0.9, 0.9)), (cu + mdu, cv + L / 2 * math.cos(p), zh + L / 2 * math.sin(p)), (0, -p, SGN * math.pi / 2), col=c_main)
        m.box("contre_fleche", (0.9, counter, 0.9), cu + mdu, cv - counter / 2 - 0.5, zh, c_dark)
        m.box("contrepoids", (1.6, 2.0, 1.6), cu + mdu, cv - counter - 0.8, zh - 0.6, c_dark)
    return zh + (L / 2) * math.sin(p) * 2


m = obj("grue_jaune", f"11. Grue Titan JAUNE (décor) : jetée de béton dans la Loire + portique 4 pieds de 12 m + plateforme + cabine + mât + flèche inclinée (sommet ≈ 25 m), centre à x ≈ 52, v = 12 ; flèche vers l'avant. {anchor_txt('grue_jaune')}.")
m.box("jetee", (9.6, 10.0, 1.5), 2.0, 11.0, -0.75, (0.52, 0.50, 0.47))
H_JAUNE = crane(m, 2.0, 12.0, 0.0, 3.0, 3.0, 0.8, 12.0, (4.0, 8.0), (7.4, 7.4, 1.2), (-1.8, 0.0), (2.0, 4.0, 0.5), (22.0, 20.0, "u"), 7.0,
                (0.95, 0.76, 0.06), (0.85, 0.65, 0.05), (0.10, 0.15, 0.25))

# ---- 12 cale -----------------------------------------------------------------
m = obj("cale", f"12. Cale de lancement : plan incliné de 5 m qui plonge de z = 0 à z = -1 (l'eau), plus piédestal et bouteille de baptême, côté Loire. {anchor_txt('cale')}.")
alpha = math.atan(1 / 5.0)
roll = math.atan2(-math.sin(alpha), SGN * math.cos(alpha))
m.add("rampe", ("box", (3.2, 5.12, 0.3)), (0, 8.77, -0.647), (roll, 0, 0), col=(0.42, 0.38, 0.34))
m.box("piedestal", (0.35, 0.35, 0.9), 1.6, 5.3, 0.45, ROUGE)
m.cyl("bouteille", 0.06, 0.35, 1.6, 5.3, 1.075, (0.10, 0.50, 0.20))

# ---- 13 velo_cadenas ---------------------------------------------------------
m = obj("velo_cadenas", f"13. Vélo cadenassé : 2 roues, cadre rouge, guidon, selle et un cadenas jaune, côté bâtiments (v = -2,4). {anchor_txt('velo_cadenas')}.")
vv = -2.4
for i, sg in enumerate((1, -1)):
    m.add(f"roue_{i + 1}", ("cyl", (0.34, 0.05)), (sg * 0.55, vv, 0.34), (math.pi / 2, 0, 0), col=(0.10, 0.10, 0.10))
    m.add(f"jante_{i + 1}", ("cyl", (0.25, 0.056)), (sg * 0.55, vv, 0.34), (math.pi / 2, 0, 0), col=(0.70, 0.70, 0.72), coll=False)
CV = (0.85, 0.20, 0.10)
m.box("tube_haut", (0.8, 0.04, 0.04), 0.05, vv, 0.62, CV)
m.box("tube_selle", (0.04, 0.04, 0.55), -0.25, vv, 0.4, CV)
m.box("fourche", (0.04, 0.04, 0.55), 0.5, vv, 0.47, CV)
m.box("guidon", (0.06, 0.5, 0.04), 0.52, vv, 0.78, (0.2, 0.2, 0.22))
m.box("selle", (0.25, 0.12, 0.05), -0.3, vv, 0.7, (0.1, 0.1, 0.1))
m.box("cadenas", (0.1, 0.08, 0.12), 0.0, vv + 0.05, 0.5, JAUNE)

# ---- 14 panneau_info ---------------------------------------------------------
m = obj("panneau_info", f"14. Panneau d'information « site des Chantiers » : 2 pieds, plan blanc et point rouge « vous êtes ici », côté Loire (v = 2,7). {anchor_txt('panneau_info')}.")
vv = 2.7
for i, sg in enumerate((1, -1)):
    m.box(f"pied_{i + 1}", (0.08, 0.08, 1.2), sg * 0.55, vv, 0.6, (0.2, 0.2, 0.22))
m.box("panneau", (1.5, 0.06, 0.95), 0, vv, 1.45, (0.10, 0.22, 0.42))
m.box("plan", (1.3, 0.02, 0.75), 0, vv - 0.04, 1.45, (0.92, 0.92, 0.88), coll=False)
m.box("trace", (0.9, 0.02, 0.04), -0.05, vv - 0.06, 1.3, (0.15, 0.3, 0.8), coll=False)
m.box("vous_etes_ici", (0.1, 0.02, 0.1), 0.3, vv - 0.06, 1.5, ROUGE, coll=False)

# ---- 15 rails ----------------------------------------------------------------
m = obj("rails", f"15. Rails désaffectés : 2 rails + traverses en travers du tracé, SANS collision (visuel à 1-4 mm au-dessus du sol), juste avant la coudée. {anchor_txt('rails')}.")
for i, sg in enumerate((1, -1)):
    m.box(f"rail_{i + 1}", (0.07, 10, 0.004), sg * 0.7175, 0.5, 0.002, (0.55, 0.57, 0.60), coll=False)
for k in range(14):
    m.box(f"traverse_{k + 1:02d}", (2.0, 0.22, 0.003), 0, -4.2 + 0.7 * k, 0.0015, (0.30, 0.20, 0.14), coll=False)

# ---- 16 lampadaire -----------------------------------------------------------
m = obj("lampadaire", f"16. Lampadaire : socle + mât de 4 m + sphère lumineuse (émissive), côté bâtiments (v = -2,4). {anchor_txt('lampadaire')}.")
vv = -2.4
m.cyl("socle", 0.14, 0.3, 0, vv, 0.15, (0.12, 0.12, 0.14))
m.cyl("mat", 0.08, 4.0, 0, vv, 2.0, (0.17, 0.17, 0.19))
m.sph("globe", 0.3, 0, vv, 4.25, (1, 1, 1), emi=True)

# ---- 17 anneaux --------------------------------------------------------------
m = obj("anneaux", f"17. Anneaux de Buren : 3 anneaux verticaux (dodécagones de 12 boîtes, diamètre 2,4 m), plan perpendiculaire à la marche, sur le quai côté Loire (centres à v = 3,4). {anchor_txt('anneaux')}.")
Rr, N = 1.2, 12
Rm = Rr * math.cos(math.pi / N)
chord = 2 * Rr * math.sin(math.pi / N) * 1.05
for r_i, du in enumerate((-2.0, 0.0, 2.0)):
    for k in range(N):
        th = math.radians(15 + 30 * k)
        tv, tz = -math.sin(th), math.cos(th)            # tangente dans le plan (v, z)
        roll_k = math.atan2(tz, SGN * tv)
        m.add(f"anneau_{r_i + 1}_seg_{k + 1:02d}", ("box", (0.14, chord, 0.14)),
              (du, 3.4 + Rm * math.cos(th), 1.35 + Rm * math.sin(th)), (roll_k, 0, 0), col=(0.22, 0.24, 0.27))

# ---- 18 bollard --------------------------------------------------------------
m = obj("bollard", f"18. Bitte d'amarrage : 2 cylindres noirs courts à bande jaune au bord du quai, côté Loire (v = 5,2). {anchor_txt('bollard')}.")
for i, du in enumerate((0.0, 2.6)):
    m.cyl(f"fut_{i + 1}", 0.2, 0.55, du, 5.2, 0.275, NOIR)
    m.cyl(f"bande_{i + 1}", 0.205, 0.06, du, 5.2, 0.42, JAUNE)
    m.cyl(f"tete_{i + 1}", 0.24, 0.06, du, 5.2, 0.58, NOIR)

# ---- 19 loire (le plan d'eau) ------------------------------------------------
m = obj("loire", f"19. La Loire : deux grands plans d'eau bleus, surface à z = -1,0 (1 m sous les dalles), l'un le long du Mail, l'autre le long du quai ; collision oui, pour que la chute s'arrête. Ce modèle est le plan d'eau lui-même : ses liens sont les coordonnées monde moins l'ancre. {anchor_txt('loire')}.")
EAU = (0.12, 0.38, 0.62)
S_QUAI_FIN = round(S["titan_grise"] + 9.0 + 1.0, 2)           # fin des dalles du quai
d_fin = S_QUAI_FIN - C_X
xm = (-40 + 76) / 2
m.add_world("eau_mail", ("box", (116, 110, 0.5)), (xm, SGN * (6.3 + 55), -1.25), 0.0, EAU)
d0, d1 = -3.0, d_fin + 40.0
qx, qy = quai_world((d0 + d1) / 2, 6.3 + 55)
m.add_world("eau_quai", ("box", (d1 - d0, 110, 0.5)), (qx, qy, -1.25), QUAI_YAW, EAU)

# ---- 20 plot_chantier --------------------------------------------------------
m = obj("plot_chantier", f"20. Plot de chantier : socle noir + 3 étages de cylindres (cône empilé), orange à bande blanche, côté bâtiments (v = -2,3). {anchor_txt('plot_chantier')}.")
vv = -2.3
m.box("socle", (0.5, 0.5, 0.04), 0, vv, 0.02, NOIR)
m.cyl("etage_1", 0.2, 0.25, 0, vv, 0.165, ORANGE)
m.cyl("bande", 0.155, 0.12, 0, vv, 0.35, BLANC)
m.cyl("etage_2", 0.115, 0.25, 0, vv, 0.535, ORANGE)
m.cyl("pointe", 0.06, 0.12, 0, vv, 0.72, ORANGE)

# ---- 21 chien ----------------------------------------------------------------
m = obj("chien", f"21. Chien en plastique (Boulon) : corps orange, 4 pattes, tête sphère, museau, oreilles, queue, côté Loire (v = 2,4). {anchor_txt('chien')}.")
vv = 2.4
CC = (0.95, 0.50, 0.15)
m.box("corps", (0.75, 0.3, 0.34), 0, vv, 0.4, CC)
for i, (dx, dv) in enumerate([(0.28, 0.1), (0.28, -0.1), (-0.28, 0.1), (-0.28, -0.1)]):
    m.box(f"patte_{i + 1}", (0.08, 0.08, 0.23), dx, vv + dv, 0.115, (0.80, 0.38, 0.10))
m.sph("tete", 0.17, 0.5, vv, 0.62, CC)
m.box("museau", (0.14, 0.12, 0.1), 0.64, vv, 0.58, (0.20, 0.10, 0.05))
for i, sg in enumerate((1, -1)):
    m.box(f"oreille_{i + 1}", (0.08, 0.05, 0.14), 0.45, vv + sg * 0.14, 0.76, (0.80, 0.38, 0.10))
m.add("queue", ("box", (0.22, 0.04, 0.04)), (-0.45, vv, 0.55), (0, -0.6, 0), col=(0.80, 0.38, 0.10))

# ---- 22 caisse_bois ----------------------------------------------------------
m = obj("caisse_bois", f"22. Caisse en bois de la Cantine du Voyage : caisse, couvercle, 2 sangles, marquage rouge sur la face côté chemin, côté bâtiments (v = -2,6). {anchor_txt('caisse_bois')}.")
vv = -2.6
m.box("caisse", (0.95, 0.95, 0.7), 0, vv, 0.35, (0.68, 0.52, 0.30))
m.box("couvercle", (1.0, 1.0, 0.04), 0, vv, 0.72, (0.55, 0.40, 0.22))
for i, sg in enumerate((1, -1)):
    m.box(f"sangle_{i + 1}", (0.05, 0.99, 0.74), sg * 0.3, vv, 0.36, (0.30, 0.20, 0.10))
m.box("marquage", (0.5, 0.01, 0.2), 0, vv + 0.48, 0.4, ROUGE, coll=False)

# ---- 23 hangar_bananes -------------------------------------------------------
S_TAG = S["tag_mur"]
H_FIN = round(S_TAG - 3.0, 2)
H_DEB = round(H_FIN - 40.0, 2)
H_CTR = (H_DEB + H_FIN) / 2
du_h = H_CTR - S["hangar_bananes"]
m = obj("hangar_bananes", f"23. Hangar à Bananes : bâtiment 40 x 10 x 8 le long du quai côté bâtiments (face à v = -7, de s = {fnum(H_DEB)} à {fnum(H_FIN)}), 5 bars colorés sur la façade, la banane (cylindre jaune couché) sur le toit comme dans rue.sdf. {anchor_txt('hangar_bananes')}.")
m.box("corps", (40, 10, 8), du_h, -12, 4, (0.40, 0.42, 0.46))
m.box("toit", (40.6, 10.6, 0.4), du_h, -12, 8.2, (0.28, 0.30, 0.33))
m.add("banane", ("cyl", (0.8, 6.0)), (du_h, -12, 9.2), (0, math.pi / 2, 0), col=(1.0, 0.88, 0.05))
for k, (cl, off) in enumerate([((0.95, 0.50, 0.10), -15), ((0.10, 0.70, 0.70), -7.5), ((0.85, 0.15, 0.55), 0), ((0.30, 0.75, 0.25), 7.5), ((0.85, 0.15, 0.12), 15)]):
    m.box(f"bar_{k + 1}", (3.0, 0.4, 2.4), du_h + off, -6.8, 1.2, cl)
    m.box(f"enseigne_{k + 1}", (3.0, 0.1, 0.5), du_h + off, -6.85, 2.8, BLANC, coll=False)

# ---- 24 tas_de_sable ---------------------------------------------------------
m = obj("tas_de_sable", f"24. Tas de sable : deux demi-sphères beiges (centres à z = 0) + un seau rouge, côté Loire (v = 2,9). {anchor_txt('tas_de_sable')}.")
m.sph("tas", 0.75, 0, 2.9, 0.0, (0.85, 0.75, 0.50))
m.sph("petit_tas", 0.45, -0.7, 3.6, 0.0, (0.82, 0.72, 0.47))
m.cyl("seau", 0.12, 0.22, 0.9, 2.4, 0.11, ROUGE)

# ---- 25 horloge_arretee ------------------------------------------------------
m = obj("horloge_arretee", f"25. Horloge arrêtée : mât de 3 m + disque blanc cerclé de noir tourné vers le chemin, aiguilles figées à 3 h, côté bâtiments (v = -2,6). {anchor_txt('horloge_arretee')}.")
vv = -2.6
m.cyl("mat", 0.07, 3.0, 0, vv, 1.5, (0.17, 0.17, 0.19))
m.add("cadre", ("cyl", (0.62, 0.1)), (0, vv, 3.2), (math.pi / 2, 0, 0), col=(0.10, 0.10, 0.12))
m.add("cadran", ("cyl", (0.55, 0.12)), (0, vv, 3.2), (math.pi / 2, 0, 0), col=(0.96, 0.96, 0.92))
m.box("grande_aiguille", (0.04, 0.02, 0.42), 0, vv + 0.065, 3.4, NOIR, coll=False)
m.box("petite_aiguille", (0.3, 0.02, 0.04), 0.15, vv + 0.065, 3.2, NOIR, coll=False)

# ---- 26 bouche_incendie ------------------------------------------------------
m = obj("bouche_incendie", f"26. Bouche d'incendie : petit robot timide (corps rouge, chapeau, 2 buses, 2 yeux), côté Loire (v = 2,4). {anchor_txt('bouche_incendie')}.")
vv = 2.4
m.cyl("corps", 0.17, 0.65, 0, vv, 0.325, (0.80, 0.10, 0.08))
m.cyl("chapeau", 0.2, 0.08, 0, vv, 0.69, (0.60, 0.06, 0.05))
m.sph("sommet", 0.1, 0, vv, 0.78, (0.80, 0.10, 0.08))
for i, sg in enumerate((1, -1)):
    m.add(f"buse_{i + 1}", ("cyl", (0.06, 0.2)), (0, vv + sg * 0.2, 0.4), (math.pi / 2, 0, 0), col=JAUNE)
for i, sg in enumerate((1, -1)):
    m.sph(f"oeil_{i + 1}", 0.04, sg * 0.07, vv - 0.16, 0.5, BLANC, coll=False)

# ---- 27 pelouse --------------------------------------------------------------
m = obj("pelouse", f"27. Pelouse interdite : dalle verte de 3,6 x 3 SANS collision (flush, 8 mm) + panneau « interdit » rouge sur un pied, côté bâtiments (v de -4,3 à -1,3). {anchor_txt('pelouse')}.")
m.box("herbe", (3.6, 3.0, 0.008), 0, -2.8, 0.004, (0.22, 0.62, 0.20), coll=False)
m.box("pied_panneau", (0.05, 0.05, 0.8), 1.5, -4.6, 0.4, (0.3, 0.3, 0.32))
m.box("panneau", (0.4, 0.03, 0.3), 1.5, -4.6, 0.85, ROUGE)
m.box("barre", (0.3, 0.01, 0.06), 1.5, -4.585, 0.85, BLANC, coll=False)

# ---- 28 conteneur_rouge ------------------------------------------------------
m = obj("conteneur_rouge", f"28. Conteneur maritime rouge 3,2 x 1,3 x 1,4 avec nervures et portes, côté Loire (centre v = 3,4). {anchor_txt('conteneur_rouge')}.")
vv = 3.4
m.box("caisse", (3.2, 1.3, 1.4), 0, vv, 0.7, (0.72, 0.12, 0.10))
for k in range(8):
    m.box(f"nervure_{k + 1}", (0.06, 0.03, 1.3), -1.4 + 0.4 * k, vv - 0.665, 0.7, (0.55, 0.08, 0.07), coll=False)
m.box("portes", (0.04, 1.2, 1.3), 1.62, vv, 0.7, (0.50, 0.07, 0.06), coll=False)

# ---- 29 tag_mur --------------------------------------------------------------
m = obj("tag_mur", f"29. Graffiti : panneau mural magenta 3,4 x 2 avec taches cyan, jaune, verte et bande blanche, sur la façade côté bâtiments (face à v = -7). {anchor_txt('tag_mur')}.")
m.box("fond", (3.4, 0.06, 2.0), 0, -6.95, 1.5, (0.80, 0.12, 0.55))
m.box("tache_cyan", (1.4, 0.02, 1.0), -0.7, -6.91, 1.4, (0.10, 0.75, 0.90), coll=False)
m.box("tache_jaune", (1.0, 0.02, 1.2), 0.8, -6.91, 1.7, (1.0, 0.85, 0.10), coll=False)
m.box("tache_verte", (0.5, 0.02, 1.6), -1.4, -6.89, 1.6, (0.20, 0.80, 0.30), coll=False)
m.box("bande_blanche", (2.2, 0.02, 0.18), 0, -6.90, 0.8, (0.96, 0.96, 0.96), coll=False)

# ---- 30 titan_grise ----------------------------------------------------------
m = obj("titan_grise", f"30. Grue Titan GRISE (le but) : socle plein de 8 x 11,6 x 3 qui BARRE le quai à 2,5 m derrière le dernier waypoint (s = {fnum(S_LAST_WP)}), bandes de chantier sur sa face, portique 4 pieds gris, cabine, mât et flèche inclinée vers la Loire (sommet ≈ 25 m). {anchor_txt('titan_grise')} (1,5 m devant le dernier waypoint).")
m.box("socle", (8.0, 11.6, 3.0), 5.0, 0.0, 1.5, GRIS_F)
for i, vv in enumerate((-4.2, -1.4, 1.4, 4.2)):
    m.box(f"bande_{i + 1}", (0.04, 0.7, 3.0), 0.98, vv, 1.5, (0.95, 0.80, 0.05), coll=False)
H_TITAN = crane(m, 5.0, 0.0, 3.0, 3.0, 4.4, 1.2, 9.0, (4.5, 8.5), (9.6, 11.6, 1.6), (-1.5, -3.0), (2.4, 4.0, 0.0), (24.0, 18.0, "v"), 6.0,
                (0.58, 0.60, 0.63), (0.42, 0.44, 0.47), (0.20, 0.28, 0.35))

# =============================================================================
# Décor : esplanade, bordure, façades
# =============================================================================
MITRE = 6 * math.tan(TH / 2)
MAIL_X0, MAIL_X1 = -5.0, round(C_X + MITRE, 2)
Q_D0, Q_D1 = -round(MITRE, 2), round(d_fin, 2)
LARG = 6.0   # demi-largeur de l'esplanade

esp = Model("esplanade", "Esplanade (z surface = 0, épaisseur 0,12, friction 1.0, largeur 12 m) : bande béton gris clair sur le Mail (x de -5 à 71,9), bande dalles gris chaud sur le quai (coudée de 35°, rallongée de 1,89 m en amont pour fermer la mitre extérieure). Collision et visuel : la dalle du quai a son visuel 3 mm plus haut pour ne pas scintiller sur le recouvrement. Joints de dilatation = visuels seuls (repères de mouvement pour la caméra).")
mbox(esp, "mail_beton", MAIL_X0, MAIL_X1, -LARG, LARG, -0.12, 0.0, (0.70, 0.70, 0.68))
# dalle du quai : collision z de -0,12 à 0 ; visuel de -0,12 à +0,003 (voir ci-dessus)
xq, yq = quai_world((Q_D0 + Q_D1) / 2, 0)
LQ = Q_D1 - Q_D0
esp.links.append(("quai_dalles", ("box", (LQ, 2 * LARG, 0.12)), (xq, yq, -0.06, 0, 0, QUAI_YAW), (0.68, 0.64, 0.58), True, False))
QV = ("quai_dalles_visuel", ("box", (LQ, 2 * LARG, 0.123)), (xq, yq, -0.0585, 0, 0, QUAI_YAW), (0.68, 0.64, 0.58), False, False)
esp.links.append(QV)
for k in range(0, 12):
    x = 6.0 * k
    mbox(esp, f"joint_mail_{k + 1:02d}", x - 0.025, x + 0.025, -LARG, LARG, 0.0, 0.001, (0.50, 0.50, 0.48), coll=False)
nq = int((Q_D1 - 1.0) // 4)
for k in range(1, nq + 1):
    qbox(esp, f"joint_quai_{k:02d}", 4.0 * k - 0.02, 4.0 * k + 0.02, -LARG, LARG, 0.003, 0.005, (0.48, 0.44, 0.40), coll=False)
for sg, nm in ((-3.0, "m"), (3.0, "p")):
    qbox(esp, f"joint_quai_long_{nm}", 0.0, Q_D1, sg - 0.02, sg + 0.02, 0.003, 0.005, (0.48, 0.44, 0.40), coll=False)

bord = Model("bordure_quai", "Ressaut de quai côté Loire : lèvre de 30 cm de large et 12 cm de haut au bord des dalles (v de 6,0 à 6,3). Collision oui : Didier peut s'y bloquer ou la franchir de justesse, au-delà c'est 1 m de chute dans l'eau.")
mbox(bord, "bordure_mail", MAIL_X0, MAIL_X1 + 0.4, 6.0, 6.3, 0.0, 0.12, (0.82, 0.82, 0.80))
qbox(bord, "bordure_quai", Q_D0, Q_D1, 6.0, 6.3, 0.0, 0.12, (0.82, 0.82, 0.80))

fac = Model("facades", "Façades basses continues côté bâtiments (v de -12 à -7, hauteur 3,6 à 4,4) : sur le Mail de x = 30 aux abords de la coudée, puis sur le quai de s = 71 jusqu'au Hangar à Bananes, et du Hangar à la fin des dalles. Les deux alignements s'interpénètrent à l'angle intérieur de la coudée (fermeture visuelle voulue). Fenêtres = visuels seuls.")
PAL = [(0.88, 0.82, 0.68), (0.80, 0.62, 0.45), (0.84, 0.70, 0.72), (0.62, 0.70, 0.78), (0.85, 0.85, 0.78)]
HAUT = [4.0, 3.6, 4.4, 3.8, 4.2]
VITRE = (0.18, 0.22, 0.28)
n_f = 0


def facade_mail(x0, x1):
    global n_f
    mbox(fac, f"facade_{n_f + 1:02d}", x0, x1, -12, -7, -1.0, HAUT[n_f % 5], PAL[n_f % 5])
    mbox(fac, f"vitres_{n_f + 1:02d}", x0 + 0.5, x1 - 0.5, -7.04, -6.98, 1.0, 2.4, VITRE, coll=False)
    n_f += 1


def facade_quai(s0, s1):
    global n_f
    d0, d1 = s0 - C_X, s1 - C_X
    qbox(fac, f"facade_{n_f + 1:02d}", d0, d1, -12, -7, -1.0, HAUT[n_f % 5], PAL[n_f % 5])
    qbox(fac, f"vitres_{n_f + 1:02d}", d0 + 0.5, d1 - 0.5, -7.04, -6.98, 1.0, 2.4, VITRE, coll=False)
    n_f += 1


for x0, x1 in [(30, 41), (41, 52), (52, 60), (60, 68)]:
    facade_mail(x0, x1)
# quai avant le hangar : de s = 71 à H_DEB, par tronçons de ~10 m
pts = [71.0]
nseg = max(1, round((H_DEB - 71.0) / 10.0))
for i in range(1, nseg + 1):
    pts.append(round(71.0 + (H_DEB - 71.0) * i / nseg, 2))
for a, b in zip(pts, pts[1:]):
    facade_quai(a, b)
# après le hangar : jusqu'à la fin des dalles
pts = [H_FIN]
nseg = max(1, round((S_QUAI_FIN - H_FIN) / 10.0))
for i in range(1, nseg + 1):
    pts.append(round(H_FIN + (S_QUAI_FIN - H_FIN) * i / nseg, 2))
for a, b in zip(pts, pts[1:]):
    facade_quai(a, b)

# =============================================================================
# Waypoints
# =============================================================================
WP = [(float(s), 0.0) for s in (2, 10, 20, 30, 40, 50, 60, 70)]
n_q = 10
for i in range(1, n_q + 1):
    s = 70.0 + (S_LAST_WP - 70.0) * i / n_q
    x, y = quai_world(s - C_X, 0)
    WP.append((round(x, 2), round(y, 2)))
WP = [(round(x, 2), round(y, 2) + 0.0) for x, y in WP]

# =============================================================================
# Émission
# =============================================================================
if MIROIR:
    COTE_TXT, COUDE_TXT, BATI_TXT = "NÉGATIF", "positif", "y > 7"
    ATTENTION = ("Convention : Loire à DROITE d'un marcheur qui avance vers +x (repère direct, z vertical),\n"
                 "  donc côté y NÉGATIF ; bâtiments à gauche, y POSITIF. C'est l'IMAGE MIROIR du brief du lot R3, qui\n"
                 "  écrivait « Loire à droite = y positif » (vrai seulement dans un repère gauche).")
else:
    COTE_TXT, COUDE_TXT, BATI_TXT = "POSITIF", "négatif", "y < -7"
    ATTENTION = ("ATTENTION : dans un repère direct (z vertical), un marcheur qui avance vers +x a +y à sa\n"
                 "  GAUCHE. Le brief du lot R3 pose « Loire à droite = y positif » : c'est la convention\n"
                 "  suivie ici, à confirmer (l'image de la caméra montre la Loire à GAUCHE de Didier).")

HEAD = f"""<?xml version="1.0"?>
<!--
  Monde "chantiers" (répétition simulée, étude §13.2, §13.3, §13.10) : le trajet
  des Nefs de l'île de Nantes à la grue Titan grise, en deux tronçons : le Mail
  des Chantiers (béton, x de 0 à 70 le long de +x, y = 0) puis, après une
  COUDÉE de 35° vers y {COUDE_TXT}, le quai des Antilles (dalles, {fr(S_LAST_WP - 70)} m de plus).
  Boîtes/cylindres/sphères uniquement : pas de mesh, pas de Fuel, aucune
  dépendance réseau. Le rendu sert à une webcam de console, pas à un film.

  Repère : x le long du Mail, y en travers, z vertical (mètres). Côté Loire =
  y {COTE_TXT} (tout le long, à plus de 6 m du tracé), côté bâtiments = y de signe opposé ({BATI_TXT}).
  Didier est posé par le launch en (0, 0, 0.24), comme dans rue.sdf (la pose de spawn ne dépend
  pas du monde).
  {ATTENTION}

  Échelle : 1 247 m réels (routage OSM piéton, §13.10) comprimés en {fr(S_LAST_WP)} m de
  polyligne, soit ≈ 1:{str(round(1247 / S_LAST_WP, 1)).replace('.', ',')} (le 1:8,6 visé au départ supposait un espacement des
  30 POI plus serré que la règle « ≥ 4,5 m en x » sur la diagonale du quai).

  CONTRAT : le monde s'appelle "stage" ICI AUSSI. Le bridge (config/gz_bridge.yaml) et
  leds_sim_node ciblent /world/stage/material_color : renommer le monde casserait
  silencieusement le visage LED en sim. Seul le FICHIER change (argument `world:=chantiers`).

  Pas de ground plane : les dalles font le sol. Sortir des dalles côté bâtiments ou aux deux
  bouts = chute dans le vide (voulu, comme rue.sdf). Côté Loire, le ressaut de quai de 12 cm
  puis l'EAU, 1 m plus bas (z = -1,0, collision oui) : la chute s'arrête, la séance aussi.

  Les 30 modèles nommés comme les POI de config/chantiers.yaml (CONTRAT, testé par
  test_chantiers_world.py) sont, dans l'ordre de la marche : {", ".join(p["name"] for p in POI)}.
  La POSE de chaque modèle est l'ANCRE du POI (x, y du YAML, lacet = cap du chemin à cet
  endroit) ; les liens sont exprimés dans ce repère (x le long de la marche, y à gauche de la
  marche), décalés de l'ancre. Dans les commentaires, v = écart latéral au tracé, POSITIF côté
  Loire et négatif côté bâtiments, quel que soit le sens du monde (la mise en miroir ne change
  pas ces valeurs). Les ancres sont à ≤ rayon - 1 m du tracé (sinon un Didier qui suit la
  polyligne ne déclencherait jamais l'enter) ; les objets pleins sont à ≥ 1,7 m du tracé.
-->
<sdf version="1.10">
  <world name="stage">

    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>

    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <!-- Système Sensors : indispensable au rendu de la caméra embarquée
         (camera_link, cf. dadou_robot_gz.urdf.xacro) : sans lui aucune image
         n'est publiée. Le monde peut alors demander un moteur de rendu même en
         headless (ogre2 off-screen) : le retour vidéo du pont web fonctionne
         donc aussi sans GUI Gazebo. -->
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>

    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.9 0.9 0.85 1</diffuse>
      <specular>0.2 0.2 0.2 1</specular>
      <direction>-0.4 0.2 -0.9</direction>
    </light>
"""

parts = [HEAD, esp.xml(), "", bord.xml(), "", fac.xml(), ""]
for p in POI:
    parts.append(M[p["name"]].xml())
    parts.append("")
parts.append("  </world>\n</sdf>\n")
out_path = sys.argv[1]
with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(parts))

data = dict(
    miroir=MIROIR, waypoints=WP, pois=[dict(name=p["name"], x=p["x"], y=p["y"], radius=p["r"], s=p["s"], va=p["va"]) for p in POI],
    s_last_wp=S_LAST_WP, q_d0=Q_D0, q_d1=Q_D1, mail_x0=MAIL_X0, mail_x1=MAIL_X1,
    esp_quai=dict(cx=round(xq, 4), cy=round(yq, 4), length=round(LQ, 4), yaw=QUAI_YAW),
    h_jaune=H_JAUNE, h_titan=H_TITAN, hangar=(H_DEB, H_FIN),
)
# data.json = tables numériques pour recaler YAML/test (outil de bascule du
# 14/10, hors dépôt) : écrit SEULEMENT si GEN_DATA est posé, pour ne pas
# laisser un fichier généré dans l'arbre à chaque régénération.
if os.environ.get("GEN_DATA"):
    with open(os.path.join(HERE, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
print("OK", out_path, "waypoints", len(WP), "polyligne", S_LAST_WP, "hauteurs grues", round(H_JAUNE, 1), round(H_TITAN, 1))
