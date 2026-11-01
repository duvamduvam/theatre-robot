#!/usr/bin/env python3
"""Schéma SVG du tronc articulé de Didier v2 (concept « robot triangle »).

Génère docs/pictures/tronc-v2-verins.svg : élévation de côté (pose neutre +
fantôme penché), vue de dessus (implantation des 3 vérins) et détail de
l'ancrage bas (étage élastique en série). Imprime aussi la cinématique.

Les cotes sont DUPLIQUÉES depuis le concept (convention des sous-ensembles :
copie + renvoi vers la source) :
  ~/Nextcloud/dev/didier/plans/concepts/triangle-3roues/robot_triangle.py (dict P)
  ~/Nextcloud/dev/didier/plans/concepts/triangle-3roues/colonne_suspension.py
À revérifier si ces scripts changent. Seul écart VOULU : l'ancrage bas des
vérins monte de z445 à Z_ANCRAGE_BAS (voir plus bas, pourquoi).

Usage : python3 docs/outils/schema_tronc_v2.py
"""
import math
from pathlib import Path

SORTIE = Path(__file__).resolve().parent.parent / "pictures" / "tronc-v2-verins.svg"

# --- Cotes du concept (mm, repère robot : sol z=0, avant = +X) ---------------
ROUE_D = 320.0            # P["roue_diametre"]
ROUE_L = 90.0             # P["roue_largeur"]
RAYON_SOMMETS = 370.0     # P["rayon_sommets"] (contrainte porte 83)
PLATEAU_Z = 380.0         # P["plateau_z"]
PLATEAU_EP = 60.0         # P["plateau_epaisseur"]
PLATEAU_R = 420.0         # P["plateau_rayon_triangle"]
AZ_VERINS = (0.0, 120.0, 240.0)   # P["azimuts_suspensions"]
R_ANCRAGE_BAS = 405.0     # P["susp_rayon_bas"]
R_ANCRAGE_HAUT = 215.0    # P["susp_rayon_haut"]
Z_ANCRAGE_HAUT = 705.0    # P["susp_z_haut"] = bas du corps
TUBE_EXT_D, TUBE_EXT_Z = 90.0, (450.0, 610.0)  # colonne_suspension (tube Ø90×3)
FOURREAU_D = 80.0         # colonne_suspension (fourreau Ø80×3, course ±40)
COURSE_HAUTEUR = 40.0     # colonne_suspension : ±40 mm
CARDAN_D = 110.0          # P["cardan_diametre"]
CARDAN_Z = 697.5          # milieu de l'enveloppe nominale z690-705 du croisillon
CORPS_R = 210.0           # P["corps_rayon"]
CORPS_H = 550.0           # P["corps_hauteur"]
DOME_APLAT = 0.45         # P["dome_aplatissement"]
ANNEAU_R_EXT = 210.0 + 22.0 + 14.0   # corps + jeu galets + paroi virole
ANNEAU_BRAS = (940.0, 100.0)         # P["anneau_bras_z"], hauteur
ANNEAU_VISAGE = (1105.0, 150.0)      # P["anneau_visage_z"], hauteur

# --- Vérin retenu (lu le 2026-10-25 sur verinelectrique.fr, modèle 0041502-2)
VERIN_RENTRE = 235.0      # entraxe des œils, tige rentrée
VERIN_SORTI = 335.0       # entraxe des œils, tige sortie (course 100)
VERIN_TIGE_D = 20.0
# Étage élastique EN SÉRIE à l'ancrage bas (exigence du plan-de-route §6
# « CHOCS » : un vérin autobloquant n'a aucune compliance, il se fait marteler
# par les seuils et les appuis). Longueur = hypothèse d'encombrement, pièce
# NON choisie (silentbloc ou ressort précontraint).
SEA_L = 25.0

# Pourquoi l'ancrage bas monte : entre (r405, z445) et (r215, z705) il y a
# 322 mm, soit le vérin presque à fond (335). La géométrie n'est pas linéaire
# (le vérin s'allonge plus qu'il ne raccourcit pour un même angle) : on règle
# donc l'ancrage pour que la plage consommée à ±15° soit CENTRÉE dans la
# course — voir calibrer_ancrage(). Point de départ : milieu de course.
# (La version 150 mm, 285/435, a été essayée : son ancrage tomberait à z370,
# sous le dessus du caisson à z440 — elle ne loge pas.)
ANGLE_DIMENSIONNANT = 15.0
Z_ANCRAGE_BAS = Z_ANCRAGE_HAUT - math.sqrt(
    ((VERIN_RENTRE + VERIN_SORTI) / 2.0 + SEA_L) ** 2
    - (R_ANCRAGE_BAS - R_ANCRAGE_HAUT) ** 2)
ENTRAXE_NEUTRE = None  # fixé par calibrer_ancrage()


# --- Cinématique ---------------------------------------------------------------
def rot(p, tangage, roulis):
    """Tourne p autour du centre du cardan : tangage autour de Y (positif =
    penché en AVANT, vers +X), puis roulis autour de X (positif = vers +Y)."""
    x, y, z = p[0], p[1], p[2] - CARDAN_Z
    t = math.radians(tangage)
    x, z = x * math.cos(t) + z * math.sin(t), -x * math.sin(t) + z * math.cos(t)
    r = math.radians(roulis)
    y, z = y * math.cos(r) + z * math.sin(r), -y * math.sin(r) + z * math.cos(r)
    return (x, y, z + CARDAN_Z)


def polaire(r, az, z):
    a = math.radians(az)
    return (r * math.cos(a), r * math.sin(a), z)


def longueurs_verins(tangage=0.0, roulis=0.0, dz=0.0):
    """Longueur de VÉRIN seul (étage élastique déduit) pour chaque azimut."""
    out = []
    for az in AZ_VERINS:
        bas = polaire(R_ANCRAGE_BAS, az, Z_ANCRAGE_BAS)
        haut = rot(polaire(R_ANCRAGE_HAUT, az, Z_ANCRAGE_HAUT), tangage, roulis)
        haut = (haut[0], haut[1], haut[2] + dz)
        out.append(math.dist(bas, haut) - SEA_L)
    return out


def calibrer_ancrage():
    """Ajuste Z_ANCRAGE_BAS pour centrer la plage ±ANGLE_DIMENSIONNANT dans
    la course (point fixe : quelques itérations suffisent)."""
    global Z_ANCRAGE_BAS, ENTRAXE_NEUTRE
    milieu = (VERIN_RENTRE + VERIN_SORTI) / 2.0
    for _ in range(20):
        _, lo, hi = cinematique(ANGLE_DIMENSIONNANT)[0]
        Z_ANCRAGE_BAS += ((lo + hi) / 2.0 - milieu) * 0.9   # trop long => monter l'ancrage bas
    ENTRAXE_NEUTRE = longueurs_verins()[0] + SEA_L


def cinematique(*angles):
    """Course consommée sur les poses extrêmes (sans et avec hauteur)."""
    lignes = []
    for ang in angles or (10.0, 15.0):
        tous = []
        for tg, rl in ((ang, 0), (-ang, 0), (0, ang), (0, -ang),
                       (ang * 0.7, ang * 0.7), (-ang * 0.7, -ang * 0.7)):
            tous += longueurs_verins(tg, rl)
        lignes.append((ang, min(tous), max(tous)))
    return lignes


# --- Dessin --------------------------------------------------------------------
COUL = {  # palette du concept (robot_triangle.py COULEURS) + accents
    "roues": "#2b2b2b", "fourches": "#8a8a8a", "chassis": "#c0902f",
    "verin": "#a63d3d", "colonne": "#6a6a6a", "corps": "#d8d2c4",
    "anneau": "#7a8b99", "sea": "#1f6f50", "texte": "#222", "cote": "#3a5fa8",
}


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.el = w, h, []

    def add(self, s):
        self.el.append(s)

    def rendu(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" '
                f'height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
                'font-family="DejaVu Sans, Arial, sans-serif">\n'
                + "\n".join(self.el) + "\n</svg>\n")


def pts(liste):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in liste)


def vue_cote(svg, ox, oy, k):
    """Élévation de côté, avant à droite. (ox, oy) = projection du point
    robot (0, sol). k = px/mm."""
    def P(x, z):
        return (ox + x * k, oy - z * k)

    # Sol
    svg.add(f'<line x1="{ox - 330 * k}" y1="{oy}" x2="{ox + 560 * k}" y2="{oy}" '
            'stroke="#999" stroke-width="2"/>')
    # Roues : avant (az 0) en x=370, les deux arrière superposées en x=-185
    for x, op in ((RAYON_SOMMETS, 1.0), (RAYON_SOMMETS * math.cos(math.radians(120)), 0.85)):
        cx, cy = P(x, ROUE_D / 2)
        svg.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{ROUE_D / 2 * k:.1f}" '
                f'fill="{COUL["roues"]}" opacity="{op}"/>')
        svg.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{40 * k:.1f}" fill="#555"/>')
        # fourche + arbre de direction jusqu'au plateau
        x0, y0 = P(x - 12, PLATEAU_Z)
        svg.add(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{24 * k:.1f}" '
                f'height="{(PLATEAU_Z - ROUE_D / 2) * k:.1f}" fill="{COUL["fourches"]}"/>')
    # Caisson : en vue de côté, de l'arête arrière (apothème 210) à la pointe avant
    x0, y0 = P(-PLATEAU_R / 2, PLATEAU_Z + PLATEAU_EP)
    svg.add(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{PLATEAU_R * 1.5 * k:.1f}" '
            f'height="{PLATEAU_EP * k:.1f}" fill="{COUL["chassis"]}" rx="3"/>')
    tx, ty = P(-120, PLATEAU_Z + 22)
    svg.add(f'<text x="{tx:.1f}" y="{ty:.1f}" font-size="12" fill="#fff">'
            'caisson + batterie 48 V</text>')

    # Colonne télescopique (fixe en bas) + fourreau (monte avec le corps)
    x0, y0 = P(-TUBE_EXT_D / 2, TUBE_EXT_Z[1])
    svg.add(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{TUBE_EXT_D * k:.1f}" '
            f'height="{(TUBE_EXT_Z[1] - TUBE_EXT_Z[0]) * k:.1f}" fill="{COUL["colonne"]}"/>')
    x0, y0 = P(-FOURREAU_D / 2, CARDAN_Z - 25)
    svg.add(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{FOURREAU_D * k:.1f}" '
            f'height="{(CARDAN_Z - 25 - 560) * k:.1f}" fill="#8d8d8d"/>')

    def haut_du_corps(tangage, style):
        """Corps + dôme + anneaux, tournés autour du cardan (contour seul si fantôme)."""
        def Q(x, z):
            p = rot((x, 0.0, z), tangage, 0.0)
            return P(p[0], p[2])
        fantome = style == "fantome"
        # anneau de reprise + cylindre + dôme (polyligne)
        contour = [Q(-230, Z_ANCRAGE_HAUT - 15), Q(230, Z_ANCRAGE_HAUT - 15),
                   Q(230, Z_ANCRAGE_HAUT), Q(CORPS_R, Z_ANCRAGE_HAUT),
                   Q(CORPS_R, Z_ANCRAGE_HAUT + CORPS_H)]
        for i in range(0, 181, 10):
            a = math.radians(i)
            contour.append(Q(CORPS_R * math.cos(a),
                             Z_ANCRAGE_HAUT + CORPS_H + CORPS_R * DOME_APLAT * math.sin(a)))
        contour += [Q(-CORPS_R, Z_ANCRAGE_HAUT), Q(-230, Z_ANCRAGE_HAUT)]
        if fantome:
            svg.add(f'<polygon points="{pts(contour)}" fill="none" stroke="{COUL["verin"]}" '
                    'stroke-width="1.6" stroke-dasharray="7 5"/>')
            return
        svg.add(f'<polygon points="{pts(contour)}" fill="{COUL["corps"]}" stroke="#9a937f"/>')
        for z0, h, nom in ((*ANNEAU_BRAS, "anneau bras"), (*ANNEAU_VISAGE, "anneau visage")):
            poly = [Q(-ANNEAU_R_EXT, z0), Q(ANNEAU_R_EXT, z0),
                    Q(ANNEAU_R_EXT, z0 + h), Q(-ANNEAU_R_EXT, z0 + h)]
            svg.add(f'<polygon points="{pts(poly)}" fill="{COUL["anneau"]}" opacity="0.85"/>')
            tx, ty = Q(-ANNEAU_R_EXT + 12, z0 + h / 2 - 5)
            svg.add(f'<text x="{tx:.1f}" y="{ty:.1f}" font-size="12" fill="#fff">{nom}</text>')
        # visage LED (avant = +X) et bras (épaules à az 90/270 : de profil, ils
        # tombent sur l'axe ; l'avant-bras pointe vers l'avant)
        poly = [Q(ANNEAU_R_EXT, 1125), Q(ANNEAU_R_EXT + 12, 1125),
                Q(ANNEAU_R_EXT + 12, 1235), Q(ANNEAU_R_EXT, 1235)]
        svg.add(f'<polygon points="{pts(poly)}" fill="#e0b400"/>')
        epaule, coude, poignet = Q(0, 990), Q(0, 770), Q(200, 770)
        svg.add(f'<polyline points="{pts([epaule, coude, poignet])}" fill="none" '
                'stroke="#5f6f7d" stroke-width="9" stroke-linecap="round" opacity="0.55"/>')

    haut_du_corps(0.0, "plein")
    haut_du_corps(15.0, "fantome")

    # Cardan (sur le dessin, par-dessus le corps : c'est la pièce clé)
    cx, cy = P(0, CARDAN_Z)
    svg.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{CARDAN_D / 2 * k:.1f}" '
            f'fill="#444" stroke="#fff" stroke-width="1.5"/>')
    svg.add(f'<line x1="{cx - 22 * k:.1f}" y1="{cy:.1f}" x2="{cx + 22 * k:.1f}" '
            f'y2="{cy:.1f}" stroke="#fff" stroke-width="2"/>')
    svg.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{9 * k:.1f}" fill="#fff"/>')

    # Vérins (pose neutre) : az 0 dans le plan, az 120/240 projetés (x = -0,5 r)
    for az in AZ_VERINS:
        bas = polaire(R_ANCRAGE_BAS, az, Z_ANCRAGE_BAS)
        haut = polaire(R_ANCRAGE_HAUT, az, Z_ANCRAGE_HAUT)
        dessiner_verin(svg, P(bas[0], bas[2]), P(haut[0], haut[2]), k,
                       opacite=1.0 if az == 0 else 0.6)

    # Cotes et repères
    def etiquette(x, z, texte, dx=0, dy=0, ancre="start"):
        tx, ty = P(x, z)
        svg.add(f'<text x="{tx + dx:.1f}" y="{ty + dy:.1f}" font-size="13" '
                f'text-anchor="{ancre}" fill="{COUL["texte"]}">{texte}</text>')

    # à droite de la colonne : à gauche, le vérin arrière projeté occupe la place
    etiquette(CARDAN_D / 2 + 8, CARDAN_Z - 30, "◀ cardan Ø110")
    etiquette(TUBE_EXT_D / 2 + 8, 540, "◀ colonne ±40")
    etiquette(R_ANCRAGE_BAS, Z_ANCRAGE_BAS, "vérin 24 V course 100", dx=14, dy=-42)
    etiquette(R_ANCRAGE_BAS, Z_ANCRAGE_BAS, "+ étage élastique", dx=14, dy=-26)
    etiquette(R_ANCRAGE_BAS, Z_ANCRAGE_BAS, f"ancrage bas z{Z_ANCRAGE_BAS:.0f} (était 445)",
              dx=14, dy=16)
    etiquette(330, 1300, "fantôme : penché de 15° en avant", dx=0)
    tx, ty = P(560, 0)
    svg.add(f'<text x="{tx - 4:.1f}" y="{ty - 8:.1f}" font-size="12" text-anchor="end" '
            'fill="#666">avant →</text>')
    # cote de hauteur totale
    x1, y1 = P(-330, 0)
    x2, y2 = P(-330, 1368)
    svg.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{COUL["cote"]}" '
            'stroke-width="1" marker-start="url(#fl)" marker-end="url(#fl)"/>')
    svg.add(f'<text x="{x1 - 8}" y="{(y1 + y2) / 2}" font-size="12" fill="{COUL["cote"]}" '
            f'transform="rotate(-90 {x1 - 8} {(y1 + y2) / 2})" text-anchor="middle">'
            '1 368 mm</text>')


def dessiner_verin(svg, bas, haut, k, opacite=1.0):
    """Étage élastique (vert) puis tube puis tige (rouge), œils aux bouts."""
    dx, dy = haut[0] - bas[0], haut[1] - bas[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    mm = L / (ENTRAXE_NEUTRE * k) if L else 1.0   # < 1 sur les vérins vus en biais

    def le_long(d_mm):
        d = d_mm * k * mm
        return (bas[0] + ux * d, bas[1] + uy * d)

    a, b = le_long(0), le_long(SEA_L)
    c = le_long(SEA_L + 150)              # tube : ~150 mm de corps (silhouette)
    g = f'<g opacity="{opacite}">'
    g += (f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" '
          f'stroke="{COUL["sea"]}" stroke-width="{30 * k:.1f}" stroke-linecap="round"/>')
    g += (f'<line x1="{b[0]:.1f}" y1="{b[1]:.1f}" x2="{c[0]:.1f}" y2="{c[1]:.1f}" '
          f'stroke="{COUL["verin"]}" stroke-width="{45 * k:.1f}"/>')
    g += (f'<line x1="{c[0]:.1f}" y1="{c[1]:.1f}" x2="{haut[0]:.1f}" y2="{haut[1]:.1f}" '
          f'stroke="#c9c9c9" stroke-width="{VERIN_TIGE_D * k:.1f}"/>')
    for p in (bas, haut):
        g += (f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{8 * k:.1f}" fill="#fff" '
              'stroke="#333" stroke-width="1.5"/>')
    svg.add(g + "</g>")


def vue_dessus(svg, ox, oy, k):
    """Vue de dessus, avant vers la DROITE (+X), +Y vers le haut."""
    def P(x, y):
        return (ox + x * k, oy - y * k)

    tri = [P(*polaire(PLATEAU_R, az, 0)[:2]) for az in AZ_VERINS]
    svg.add(f'<polygon points="{pts(tri)}" fill="{COUL["chassis"]}" opacity="0.35" '
            f'stroke="{COUL["chassis"]}"/>')
    cx, cy = P(0, 0)
    svg.add(f'<circle cx="{cx}" cy="{cy}" r="{CORPS_R * k:.1f}" fill="none" '
            'stroke="#9a937f" stroke-dasharray="5 4"/>')
    svg.add(f'<circle cx="{cx}" cy="{cy}" r="{CARDAN_D / 2 * k:.1f}" fill="#444"/>')
    for az, nom in zip(AZ_VERINS, ("V0 avant", "V120 arrière-gauche", "V240 arrière-droit")):
        b = P(*polaire(R_ANCRAGE_BAS, az, 0)[:2])
        h = P(*polaire(R_ANCRAGE_HAUT, az, 0)[:2])
        svg.add(f'<line x1="{b[0]:.1f}" y1="{b[1]:.1f}" x2="{h[0]:.1f}" y2="{h[1]:.1f}" '
                f'stroke="{COUL["verin"]}" stroke-width="{45 * k:.1f}" stroke-linecap="round"/>')
        r = P(*polaire(RAYON_SOMMETS, az, 0)[:2])
        a = math.radians(az)
        # roue (rectangle orienté radialement, simple repère)
        svg.add(f'<rect x="{r[0] - ROUE_L / 2 * k:.1f}" y="{r[1] - ROUE_D / 2 * k:.1f}" '
                f'width="{ROUE_L * k:.1f}" height="{ROUE_D * k:.1f}" fill="{COUL["roues"]}" '
                f'opacity="0.55" transform="rotate({-az:.0f} {r[0]:.1f} {r[1]:.1f})"/>')
        t = P(*polaire(PLATEAU_R + 70, az, 0)[:2])
        ancre = "start" if math.cos(a) > 0.1 else "end"
        svg.add(f'<text x="{t[0]:.1f}" y="{t[1] + 4:.1f}" font-size="13" '
                f'text-anchor="{ancre}" fill="{COUL["verin"]}" font-weight="bold">{nom}</text>')
    t = P(PLATEAU_R + 10, -60)
    svg.add(f'<text x="{t[0]:.1f}" y="{t[1]:.1f}" font-size="12" fill="#666">avant →</text>')


def detail_ancrage(svg, x, y):
    """Encadré : la chaîne mécanique de l'ancrage bas, du caisson au corps."""
    w, h = 400, 150
    svg.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#fafafa" stroke="#ccc"/>')
    svg.add(f'<text x="{x + 12}" y="{y + 22}" font-size="14" font-weight="bold">'
            'Ancrage bas (×3) — étage élastique en série</text>')
    yy = y + 75
    blocs = [("chape\ncaisson", COUL["chassis"], 70), ("silentbloc /\nressort", COUL["sea"], 90),
             ("œil Ø6 +\nvérin", COUL["verin"], 110), ("rotule\nhaute", "#555", 70)]
    xx = x + 14
    for nom, coul, bw in blocs:
        svg.add(f'<rect x="{xx}" y="{yy - 22}" width="{bw}" height="44" rx="6" fill="{coul}"/>')
        for i, ligne in enumerate(nom.split("\n")):
            svg.add(f'<text x="{xx + bw / 2}" y="{yy - 4 + i * 15}" font-size="11.5" '
                    f'fill="#fff" text-anchor="middle">{ligne}</text>')
        xx += bw + 8
    svg.add(f'<text x="{x + 12}" y="{y + h - 28}" font-size="11.5" fill="#444">'
            'Le vérin autobloquant n\'a aucune souplesse : le choc (seuil, appui)'
            '</text>')
    svg.add(f'<text x="{x + 12}" y="{y + h - 12}" font-size="11.5" fill="#444">'
            'est pris par l\'élastique, pas par la vis (plan-de-route §6 « CHOCS »).</text>')


def main():
    calibrer_ancrage()
    cin = cinematique()
    neutre = longueurs_verins()
    print(f"ancrage bas : z{Z_ANCRAGE_BAS:.1f} (concept : z445)")
    print(f"vérin au neutre : {neutre[0]:.1f} mm (milieu de course = "
          f"{(VERIN_RENTRE + VERIN_SORTI) / 2:.0f})")
    for ang, lo, hi in cin:
        print(f"±{ang:.0f}° (tangage, roulis, diagonale) : vérin de {lo:.1f} à {hi:.1f} mm"
              f" — butées {VERIN_RENTRE:.0f}/{VERIN_SORTI:.0f}")
    marges = {ang: min(lo - VERIN_RENTRE, VERIN_SORTI - hi) for ang, lo, hi in cin}
    for ang, m in marges.items():
        print(f"course restante à ±{ang:.0f}° (pour la hauteur ou la respiration) : ±{m:.1f} mm")

    svg = Svg(1500, 980)
    svg.add('<defs><marker id="fl" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" '
            'markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
            f'fill="{COUL["cote"]}"/></marker></defs>')
    svg.add('<rect width="100%" height="100%" fill="#fff"/>')
    svg.add('<text x="30" y="42" font-size="24" font-weight="bold">Didier v2 — tronc '
            'articulé par 3 vérins électriques</text>')
    svg.add('<text x="30" y="68" font-size="14" fill="#555">Concept « robot triangle » '
            '(plans/concepts/triangle-3roues) · étude docs/etude-tronc.md · 2026-10-25 · '
            'schéma de principe, cotes du concept</text>')

    svg.add('<text x="30" y="108" font-size="16" font-weight="bold">Élévation de côté</text>')
    vue_cote(svg, ox=250, oy=930, k=0.58)

    svg.add('<text x="860" y="108" font-size="16" font-weight="bold">Vue de dessus</text>')
    vue_dessus(svg, ox=1075, oy=310, k=0.36)

    # Pilotage et chiffres clés
    x, y = 860, 500
    lignes = [
        ("Pilotage : 3 vérins = 3 mouvements", True),
        ("• hauteur : les 3 ensemble (±40 sur la colonne)", False),
        ("• tangage : V0 contre V120 + V240", False),
        ("• roulis : V120 contre V240", False),
        ("Vérin : 24 V, course 100, 300 N à 40 mm/s,", False),
        ("  potentiomètre 10 kΩ, autobloquant, IP65", False),
        (f"Au neutre : {neutre[0]:.0f} mm (course 235 → 335)", False),
        (f"±15° : de {cin[1][1]:.0f} à {cin[1][2]:.0f} mm → reste ±{marges[15.0]:.0f} mm", False),
        (f"±10° : de {cin[0][1]:.0f} à {cin[0][2]:.0f} mm → reste ±{marges[10.0]:.0f} mm", False),
        ("  (la marge sert à la hauteur ou à la respiration)", False),
    ]
    for i, (t, gras) in enumerate(lignes):
        svg.add(f'<text x="{x}" y="{y + i * 21}" font-size="14"'
                f'{" font-weight=\"bold\"" if gras else ""}>{t}</text>')
    detail_ancrage(svg, 860, 720)

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(svg.rendu(), encoding="utf-8")
    print(f"écrit : {SORTIE}")


if __name__ == "__main__":
    main()
