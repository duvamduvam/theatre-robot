#!/usr/bin/env python3
"""Schéma SVG du tronc de Didier v2, solution A de docs/etude-tronc.md §10.4 :
colonne FIXE + cardan + 2 moteurs réversibles (un par axe, courroie 1:3) +
4 ressorts de centrage qui annulent la gravité.

Génère docs/pictures/tronc-v2-moteurs.svg et imprime le dimensionnement.
Les cotes du concept et les outils de dessin viennent de schema_tronc_v2.py
(même dossier) : une seule copie des cotes du concept triangle.

Usage : python3 docs/outils/schema_tronc_v2_moteurs.py
"""
import math
from pathlib import Path

from schema_tronc_v2 import (
    ANNEAU_BRAS, ANNEAU_R_EXT, ANNEAU_VISAGE, CARDAN_D, CARDAN_Z, COUL, CORPS_H,
    CORPS_R, DOME_APLAT, PLATEAU_EP, PLATEAU_R, PLATEAU_Z, RAYON_SOMMETS, ROUE_D,
    TUBE_EXT_D, Svg, pts, rot,
)

SORTIE = Path(__file__).resolve().parent.parent / "pictures" / "tronc-v2-moteurs.svg"

Z_CORPS = 705.0            # bas du corps (P["susp_z_haut"]), inchangé
Z_COLONNE_BAS = 450.0      # le tube repose sur l'embase du caisson (colonne_suspension)

# --- Hypothèses de dimensionnement (À REFAIRE au bilan de masse de la v2) ----
MASSE = 20.0               # kg au-dessus du cardan (haut de la fourchette 10-20)
H_CDG = 0.35               # m, centre de gravité au-dessus du cardan
ANGLE_MAX = 15.0           # ° (butées mécaniques à ±17°)
VITESSE_CIBLE = 120.0      # °/s en pointe (§10.1 : humain détendu 60-104 °/s)
ACCEL_CIBLE = 20.0         # rad/s² (sursaut / rebond sur petits angles)
# 1:4 et pas 1:3 : à 1:3 il faut 22 N·m au moteur, collé aux 23,7 de crête du
# GO-M8010-6. La vitesse reste large (8,4 rad/s demandés pour 30 disponibles).
REDUCTION = 4.0            # courroie HTD (silencieuse, déjà retenue pour les anneaux)

# Ressorts de centrage : 4 ressorts de compression en croix entre un plateau
# FIXE sur la colonne et le dessous du corps. Raideur angulaire visée un peu
# AU-DESSUS de m·g·h : le buste devient passivement stable (coupure = retour
# au centre), et le moteur ne paie plus que la différence + l'accélération.
MARGE_RESSORTS = 1.2
R_RESSORTS = 130.0         # mm du centre
Z_PLATEAU_RESSORTS = 600.0 # plateau fixe, sous le cardan
R_BUTEES = 175.0           # butées caoutchouc à ±17°



def dimensionnement():
    g = 9.81
    mgh = MASSE * g * H_CDG                                   # N·m/rad
    k_theta = MARGE_RESSORTS * mgh
    k_ressort = k_theta / (2 * (R_RESSORTS / 1000) ** 2)      # N/m, 2 ressorts actifs par axe
    th = math.radians(ANGLE_MAX)
    residuel = k_theta * th - mgh * math.sin(th)              # N·m tenu par le moteur à 15°
    # Inertie autour du cardan : cylindre plein (r, h) + transport au CdG
    r, h = CORPS_R / 1000, CORPS_H / 1000
    inertie = MASSE * (3 * r ** 2 + h ** 2) / 12 + MASSE * H_CDG ** 2
    pointe_joint = inertie * ACCEL_CIBLE + residuel
    return {
        "mgh": mgh, "k_theta": k_theta, "k_ressort_N_mm": k_ressort / 1000,
        "fleche_15": R_RESSORTS * math.sin(th), "residuel": residuel,
        "inertie": inertie, "pointe_joint": pointe_joint,
        "pointe_moteur": pointe_joint / REDUCTION,
        "vitesse_moteur": math.radians(VITESSE_CIBLE) * REDUCTION,
    }


def vue_cote(svg, ox, oy, k):
    """Élévation de côté, avant à droite (+X). Le corps est dessiné plein au
    neutre et en fantôme penché de 15° en avant."""
    def P(x, z):
        return (ox + x * k, oy - z * k)

    svg.add(f'<line x1="{ox - 330 * k}" y1="{oy}" x2="{ox + 560 * k}" y2="{oy}" '
            'stroke="#999" stroke-width="2"/>')
    for x, op in ((RAYON_SOMMETS, 1.0), (RAYON_SOMMETS * math.cos(math.radians(120)), 0.85)):
        cx, cy = P(x, ROUE_D / 2)
        svg.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{ROUE_D / 2 * k:.1f}" '
                f'fill="{COUL["roues"]}" opacity="{op}"/>')
        svg.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{40 * k:.1f}" fill="#555"/>')
        x0, y0 = P(x - 12, PLATEAU_Z)
        svg.add(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{24 * k:.1f}" '
                f'height="{(PLATEAU_Z - ROUE_D / 2) * k:.1f}" fill="{COUL["fourches"]}"/>')
    x0, y0 = P(-PLATEAU_R / 2, PLATEAU_Z + PLATEAU_EP)
    svg.add(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{PLATEAU_R * 1.5 * k:.1f}" '
            f'height="{PLATEAU_EP * k:.1f}" fill="{COUL["chassis"]}" rx="3"/>')
    tx, ty = P(-120, PLATEAU_Z + 22)
    svg.add(f'<text x="{tx:.1f}" y="{ty:.1f}" font-size="12" fill="#fff">'
            'caisson + batterie 48 V</text>')

    # Colonne FIXE (plus de fourreau télescopique : la hauteur n'est plus pilotée)
    x0, y0 = P(-TUBE_EXT_D / 2, CARDAN_Z - 30)
    svg.add(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{TUBE_EXT_D * k:.1f}" '
            f'height="{(CARDAN_Z - 30 - Z_COLONNE_BAS) * k:.1f}" fill="{COUL["colonne"]}"/>')

    def corps(tangage, fantome):
        def Q(x, z):
            p = rot((x, 0.0, z), tangage, 0.0)
            return P(p[0], p[2])
        contour = [Q(-230, Z_CORPS - 15), Q(230, Z_CORPS - 15), Q(230, Z_CORPS),
                   Q(CORPS_R, Z_CORPS), Q(CORPS_R, Z_CORPS + CORPS_H)]
        for i in range(0, 181, 10):
            a = math.radians(i)
            contour.append(Q(CORPS_R * math.cos(a),
                             Z_CORPS + CORPS_H + CORPS_R * DOME_APLAT * math.sin(a)))
        contour += [Q(-CORPS_R, Z_CORPS), Q(-230, Z_CORPS)]
        if fantome:
            svg.add(f'<polygon points="{pts(contour)}" fill="none" stroke="{COUL["verin"]}" '
                    'stroke-width="1.6" stroke-dasharray="7 5"/>')
            return
        svg.add(f'<polygon points="{pts(contour)}" fill="{COUL["corps"]}" stroke="#9a937f"/>')
        for z0, hh, nom in ((*ANNEAU_BRAS, "anneau bras"), (*ANNEAU_VISAGE, "anneau visage")):
            poly = [Q(-ANNEAU_R_EXT, z0), Q(ANNEAU_R_EXT, z0),
                    Q(ANNEAU_R_EXT, z0 + hh), Q(-ANNEAU_R_EXT, z0 + hh)]
            svg.add(f'<polygon points="{pts(poly)}" fill="{COUL["anneau"]}" opacity="0.85"/>')
            tx, ty = Q(-ANNEAU_R_EXT + 12, z0 + hh / 2 - 5)
            svg.add(f'<text x="{tx:.1f}" y="{ty:.1f}" font-size="12" fill="#fff">{nom}</text>')
        poly = [Q(ANNEAU_R_EXT, 1125), Q(ANNEAU_R_EXT + 12, 1125),
                Q(ANNEAU_R_EXT + 12, 1235), Q(ANNEAU_R_EXT, 1235)]
        svg.add(f'<polygon points="{pts(poly)}" fill="#e0b400"/>')
        svg.add(f'<polyline points="{pts([Q(0, 990), Q(0, 770), Q(200, 770)])}" fill="none" '
                'stroke="#5f6f7d" stroke-width="9" stroke-linecap="round" opacity="0.55"/>')
        # Respiration (option) : panneau de poitrine soulevé par un petit servo à came
        pa, pb = Q(CORPS_R, 780), Q(CORPS_R, 900)
        svg.add(f'<line x1="{pa[0]:.1f}" y1="{pa[1]:.1f}" x2="{pb[0]:.1f}" y2="{pb[1]:.1f}" '
                'stroke="#4f8f6a" stroke-width="6" stroke-dasharray="4 3"/>')

    corps(0.0, False)
    corps(15.0, True)
    mecanique_cardan(svg, P, k)

    def etiquette(x, z, texte, dx=0, dy=0, ancre="start", coul=None):
        tx, ty = P(x, z)
        svg.add(f'<text x="{tx + dx:.1f}" y="{ty + dy:.1f}" font-size="13" '
                f'text-anchor="{ancre}" fill="{coul or COUL["texte"]}">{texte}</text>')

    etiquette(TUBE_EXT_D / 2 + 8, 465, "◀ colonne FIXE")
    etiquette(CORPS_R, 840, "respiration (option) :", dx=14, coul="#4f8f6a")
    etiquette(CORPS_R, 840, "panneau + petit servo", dx=14, dy=16, coul="#4f8f6a")
    etiquette(330, 1300, "fantôme : penché de 15° en avant")
    etiquette(260, 640, "détail ▶", coul="#666")
    tx, ty = P(560, 0)
    svg.add(f'<text x="{tx - 4:.1f}" y="{ty - 8:.1f}" font-size="12" text-anchor="end" '
            'fill="#666">avant →</text>')


def ressort(svg, a, b, largeur, spires=7, coul="#2f6fae", ep=2.2):
    """Ressort en zigzag entre a et b (points écran)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    pts_r = [a]
    n = spires * 2
    for i in range(1, n):
        t = i / n
        s = largeur / 2 * (1 if i % 2 else -1)
        pts_r.append((a[0] + ux * L * t + nx * s, a[1] + uy * L * t + ny * s))
    pts_r.append(b)
    svg.add(f'<polyline points="{pts(pts_r)}" fill="none" stroke="{coul}" '
            f'stroke-width="{ep}" stroke-linejoin="round"/>')


def mecanique_cardan(svg, P, k):
    """Plateau de ressorts, ressorts, butées, cardan, moteurs + courroies.
    Même dessin pour la vue d'ensemble et le zoom (étiquettes posées à part)."""
    # Plateau de ressorts FIXE (sur la colonne) et butées caoutchouc
    x0, y0 = P(-R_BUTEES - 20, Z_PLATEAU_RESSORTS)
    svg.add(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{(2 * R_BUTEES + 40) * k:.1f}" '
            f'height="{12 * k:.1f}" fill="{COUL["colonne"]}"/>')
    for sx in (-1, 1):
        bx, by = P(sx * R_BUTEES - 12, Z_PLATEAU_RESSORTS + 52)
        svg.add(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{24 * k:.1f}" height="{40 * k:.1f}" '
                'fill="#222" rx="3"/>')
        # 2 ressorts visibles (avant/arrière) ; les 2 latéraux sont derrière l'axe
        a = P(sx * R_RESSORTS, Z_PLATEAU_RESSORTS)
        b = P(sx * R_RESSORTS, Z_CORPS - 15)
        ressort(svg, a, b, 30 * k, ep=max(1.2, 3 * k))
    # Cardan
    cx, cy = P(0, CARDAN_Z)
    svg.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{CARDAN_D / 2 * k:.1f}" fill="#444" '
            'stroke="#fff" stroke-width="1.5"/>')
    # Axe de tangage (Y) vu en bout : grande poulie entraînée par M2 (porté par le corps)
    svg.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{36 * k:.1f}" fill="none" '
            f'stroke="#e08a1e" stroke-width="{max(1.5, 4 * k):.1f}"/>')
    svg.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{7 * k:.1f}" fill="#fff"/>')
    m2 = P(-110, CARDAN_Z + 42)       # M2 sous la plaque du corps, à l'arrière
    r_m2, r_p2 = 48 * k, 12 * k
    for s in (-1, 1):                 # brins de courroie (tangentes approchées)
        svg.add(f'<line x1="{m2[0]:.1f}" y1="{m2[1] + s * r_p2:.1f}" x2="{cx:.1f}" '
                f'y2="{cy + s * 36 * k:.1f}" stroke="#e08a1e" stroke-width="{max(1.2, 3 * k):.1f}"/>')
    svg.add(f'<circle cx="{m2[0]:.1f}" cy="{m2[1]:.1f}" r="{r_m2:.1f}" fill="#2d5d8a" '
            'stroke="#fff" stroke-width="1"/>')
    svg.add(f'<text x="{m2[0]:.1f}" y="{m2[1] + 4:.1f}" font-size="{max(9, 30 * k):.0f}" '
            'fill="#fff" text-anchor="middle" font-weight="bold">M2</text>')
    # M1 roulis (axe X) : moteur couché sur une console de la colonne, vu de côté
    a = P(25, Z_PLATEAU_RESSORTS - 10)   # sous le plateau : au-dessus, les ressorts
    svg.add(f'<rect x="{a[0]:.1f}" y="{a[1]:.1f}" width="{105 * k:.1f}" height="{70 * k:.1f}" '
            'fill="#2d5d8a" stroke="#fff" stroke-width="1" rx="4"/>')
    svg.add(f'<text x="{a[0] + 52 * k:.1f}" y="{a[1] + 40 * k:.1f}" '
            f'font-size="{max(9, 30 * k):.0f}" fill="#fff" text-anchor="middle" '
            'font-weight="bold">M1</text>')
    # courroie de M1 : plan perpendiculaire à X, vue par la tranche
    t1, t2 = P(25, Z_PLATEAU_RESSORTS - 45), P(25, CARDAN_Z)
    svg.add(f'<line x1="{t1[0]:.1f}" y1="{t1[1]:.1f}" x2="{t2[0]:.1f}" y2="{t2[1]:.1f}" '
            f'stroke="#e08a1e" stroke-width="{max(2, 8 * k):.1f}"/>')


def main():
    d = dimensionnement()
    for cle, val in d.items():
        print(f"{cle:16s} {val:8.2f}")

    svg = Svg(1500, 1000)
    svg.add('<rect width="100%" height="100%" fill="#fff"/>')
    svg.add('<text x="30" y="42" font-size="24" font-weight="bold">Didier v2 — tronc '
            'articulé : 2 moteurs rapides + ressorts de centrage</text>')
    svg.add('<text x="30" y="68" font-size="14" fill="#555">Solution A de docs/etude-tronc.md '
            '§10.4 · concept « robot triangle » · 2026-10-25 · schéma de principe, '
            'dimensionnement à refaire au bilan de masse</text>')
    svg.add('<text x="30" y="108" font-size="16" font-weight="bold">Élévation de côté</text>')
    vue_cote(svg, ox=250, oy=950, k=0.58)

    # Zoom sur le cardan (même dessin que la vue d'ensemble, échelle ×2,4)
    svg.add('<text x="790" y="108" font-size="16" font-weight="bold">Détail : cardan, '
            'moteurs, ressorts</text>')
    kz, ozx = 1.2, 1110
    z_bas = 470.0

    def Pzc(x, z):
        """Zoom : la tranche z470-790 remplit l'encadré."""
        return (ozx + x * kz, 505 - (z - z_bas) * kz)
    svg.add('<rect x="790" y="120" width="680" height="400" fill="#fafafa" stroke="#ddd"/>')
    x0, y0 = Pzc(-TUBE_EXT_D / 2, CARDAN_Z - 30)
    svg.add(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{TUBE_EXT_D * kz:.1f}" '
            f'height="{(CARDAN_Z - 30 - z_bas) * kz:.1f}" fill="{COUL["colonne"]}"/>')
    x0, y0 = Pzc(-230, Z_CORPS)
    svg.add(f'<rect x="{x0:.1f}" y="{y0 - 60 * kz:.1f}" width="{460 * kz:.1f}" '
            f'height="{(60 + 15) * kz:.1f}" fill="{COUL["corps"]}" stroke="#9a937f"/>')
    tx, ty = Pzc(-222, Z_CORPS + 8)
    svg.add(f'<text x="{tx:.1f}" y="{ty:.1f}" font-size="12" fill="#6b6553">bas du corps</text>')
    mecanique_cardan(svg, Pzc, kz)
    for x, z, ancre, lignes_e in (
            (75, 758, "start", ("M2 (à gauche) : tangage, fixé au corps", f"courroie 1:{REDUCTION:.0f} → axe Y")),
            (145, 575, "start", ("M1 roulis, sur la colonne", f"courroie 1:{REDUCTION:.0f} → axe X")),
            (-225, 585, "start", ("▲ plateau fixe : 4 ressorts", "de centrage (r130), butées ±17°")),
            (55, 655, "start", ("cardan",))):
        tx, ty = Pzc(x, z)
        for i, t in enumerate(lignes_e):
            svg.add(f'<text x="{tx:.1f}" y="{ty + i * 15:.1f}" font-size="12.5" '
                    f'text-anchor="{ancre}" fill="{COUL["texte"]}">{t}</text>')

    # Chiffres
    x, y = 790, 560
    lignes = [
        ("Dimensionnement (hypothèses : 20 kg, CdG à 35 cm)", True),
        (f"• gravité : m·g·h = {d['mgh']:.0f} N·m/rad (le buste veut tomber)", False),
        (f"• ressorts : {d['k_theta']:.0f} N·m/rad = ×{MARGE_RESSORTS} → stable seul ;"
         f" ~{d['k_ressort_N_mm']:.1f} N/mm chacun à r{R_RESSORTS:.0f}", False),
        (f"• à 15°, le moteur ne tient plus que {d['residuel']:.1f} N·m", False),
        (f"• inertie ≈ {d['inertie']:.1f} kg·m² → {ACCEL_CIBLE:.0f} rad/s² ="
         f" {d['pointe_joint']:.0f} N·m de pointe à l'axe", False),
        (f"• courroie 1:{REDUCTION:.0f} → {d['pointe_moteur']:.0f} N·m et"
         f" {d['vitesse_moteur']:.1f} rad/s au moteur pour {VITESSE_CIBLE:.0f} °/s", False),
        ("Moteurs candidats (lus le 25/10)", True),
        (f"• Unitree GO-M8010-6 : 23,7 N·m crête (marge ×{23.7 / d['pointe_moteur']:.1f}),"
         " 30 rad/s, 313,95 €", False),
        ("• Robstride 03 : 60 N·m crête (large), A$509 — vitesse non lue", False),
        ("Sécurité", True),
        ("• coupure : les ressorts ramènent au centre (sans frein, sans logiciel)", False),
        ("• choc : le moteur réversible cède au lieu de casser une vis", False),
        ("• butées caoutchouc ±17° ; jupe anti-pincement sous le corps", False),
        ("Ce que ça simplifie dans le concept", True),
        ("• plus de vérins ni de colonne télescopique : 2 actionneurs au lieu de 3", False),
        ("• l'enveloppe basse des bras (z≈672, imposée par les vérins) disparaît", False),
    ]
    for i, (t, gras) in enumerate(lignes):
        poids = ' font-weight="bold"' if gras else ""
        svg.add(f'<text x="{x}" y="{y + i * 24}" font-size="14"{poids}>{t}</text>')

    SORTIE.write_text(svg.rendu(), encoding="utf-8")
    print(f"écrit : {SORTIE}")


if __name__ == "__main__":
    main()
