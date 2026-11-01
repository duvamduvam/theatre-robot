#!/usr/bin/env python3
"""Génère une feuille millimétrée PDF à imprimer, pour photographier du matériel
avec une échelle lisible (mesurer une pièce a posteriori sur la photo).

Aucune dépendance : le PDF est écrit à la main (vectoriel, donc net à
n'importe quelle imprimante, contrairement à une image tramée).

Usage :
    python3 feuille-millimetree.py                       # A4 portrait + paysage
    python3 feuille-millimetree.py --format A3 --orientation paysage
    python3 feuille-millimetree.py --couleur gris        # au lieu du bleu

PIÈGE D'IMPRESSION : imprimer à *taille réelle / 100 %*, JAMAIS « ajuster à la
page » (le pilote réduit de ~4 % pour rentrer dans les marges, et le
millimétrage devient faux sans qu'on le voie). La barre témoin de 100 mm en bas
de page sert à vérifier au réglet avant de photographier quoi que ce soit.
"""

from __future__ import annotations

import argparse
from pathlib import Path

# --- Unités -----------------------------------------------------------------
# Le PDF raisonne en points typographiques (1 pt = 1/72 pouce). Tout le reste du
# script raisonne en millimètres : une seule conversion, au moment d'écrire.
MM = 72.0 / 25.4

# Formats papier en mm (largeur, hauteur) en portrait.
FORMATS = {
    "A5": (148.0, 210.0),
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
}

# Marge non imprimable : la plupart des imprimantes domestiques ne descendent
# pas sous ~5 mm. On prend 8 mm, puis on recale la grille sur un multiple de
# 10 mm pour que les graduations tombent rond.
MARGE_MM = 8.0

# Palettes (r, g, b) pour les traits 1 mm / 5 mm / 10 mm.
# Le bleu est le classique du papier millimétré : il se distingue bien du
# matériel photographié (souvent noir, gris ou métal) sans manger le contraste.
# Le 1 mm est volontairement TRÈS clair : trop appuyé, il noie le pas de 5 mm et
# la feuille devient illisible sur une photo.
PALETTES = {
    "bleu": ((0.80, 0.87, 0.95), (0.50, 0.66, 0.86), (0.13, 0.35, 0.66)),
    "gris": ((0.85, 0.85, 0.85), (0.60, 0.60, 0.60), (0.25, 0.25, 0.25)),
    # Noir pur, pour une imprimante monochrome : tout aplat non noir y passerait
    # au tramage (demi-teintes), qui hache les traits fins en pointillé sale.
    # La hiérarchie 1/5/10 mm ne repose alors QUE sur l'épaisseur.
    "noir": ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
}

# Un point d'imprimante thermique 203 dpi, en points PDF. En dessous de cette
# largeur, un trait n'est pas rendu de façon fiable : la thermique ne sait pas
# chauffer un demi-point.
PT_203DPI = 72.0 / 203.0

# Profils d'impression. Chacun fixe palette, épaisseurs de trait (en points PDF)
# et corps de texte, car ces trois réglages dépendent ensemble de la machine.
#   bureau    : laser/jet d'encre >= 600 dpi, couleur.
#   thermique : thermique directe 203 dpi monochrome (Xprinter P83 & co.).
#               Épaisseurs = multiples EXACTS du point machine, sinon le pilote
#               arrondit et le pas de 1 mm devient irrégulier à l'œil.
PROFILS = {
    "bureau": {
        "couleur": "bleu",
        "epaisseurs": (0.18, 0.4, 0.7),
        "corps_graduation": 5.0,
        "corps_texte": 6.0,
    },
    "thermique": {
        "couleur": "noir",
        "epaisseurs": (PT_203DPI, 2 * PT_203DPI, 3 * PT_203DPI),
        "corps_graduation": 7.0,   # 5 pt à 203 dpi = 14 px de haut : illisible
        "corps_texte": 7.5,
    },
}

# Côté des mires de coin, en mm.
MIRE_MM = 4.0

# Largeur d'un chiffre et hauteur des capitales en Helvetica, en em : sert à
# centrer les graduations sans table de métriques.
EM_CHIFFRE, EM_HAUTEUR = 0.556, 0.72


def flottant(valeur: float) -> str:
    """Formate un nombre pour le PDF (3 décimales, sans zéros inutiles)."""
    return f"{valeur:.3f}".rstrip("0").rstrip(".") or "0"


def echappe(texte: str) -> str:
    """Échappe une chaîne pour un littéral PDF ( ... ), encodé cp1252."""
    return texte.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def construit_page(largeur_mm: float, hauteur_mm: float, profil: dict) -> str:
    """Retourne le flux de contenu PDF d'une page millimétrée.

    Repère PDF : origine en bas à gauche, y vers le haut — c'est aussi le repère
    utilisé ici, donc les graduations verticales se lisent de bas en haut.
    """
    c_1mm, c_5mm, c_10mm = PALETTES[profil["couleur"]]
    ep_1mm, ep_5mm, ep_10mm = profil["epaisseurs"]
    corps_grad = profil["corps_graduation"]
    corps_texte = profil["corps_texte"]
    ops: list[str] = []

    # Zone quadrillée. Les graduations chiffrées vivent DANS les marges, autour
    # de la grille : il faut leur réserver leur encombrement, sinon elles sortent
    # de la zone imprimable et se font rogner au tirage (au plus 2 chiffres :
    # une grille de plus de 99 cm ne tient sur aucun format visé).
    # Autour de la grille vivent les graduations chiffrées et les mires : la
    # bordure doit loger le plus encombrant des deux, sinon l'un des deux sort de
    # la zone imprimable et se fait rogner au tirage (au plus 2 chiffres — une
    # grille de plus de 99 cm ne tient sur aucun format visé).
    bord_lat = max(1.4 + 2 * EM_CHIFFRE * corps_grad / MM, MIRE_MM)
    bord_haut = max(1.4 + EM_HAUTEUR * corps_grad / MM, MIRE_MM)

    # La grille n'a pas à commencer à un multiple de 10 mm du bord de page : ce
    # qui compte est qu'elle couvre un nombre ENTIER de centimètres, pour que ses
    # quatre bords tombent sur une graduation.
    # Arrondir la largeur au centimètre laisse un reliquat (jusqu'à 9 mm) : on le
    # partage entre les deux bords pour que la feuille soit centrée, plutôt que
    # de le laisser s'accumuler à droite.
    dispo = largeur_mm - 2 * (MARGE_MM + bord_lat)
    largeur_grille = int(dispo // 10) * 10
    x0 = MARGE_MM + bord_lat + (dispo - largeur_grille) / 2
    x1 = x0 + largeur_grille

    # Cartouche du bas (barre témoin + consignes). Les consignes tiennent à
    # droite de la barre sur A4/A3 ; sur un format étroit elles passent dessous,
    # ce qui demande une réserve plus haute — sinon elles sortiraient de la
    # feuille sans qu'on le voie au moment du tirage.
    a_droite = (x1 - (x0 + 104)) >= 72.0

    # Hauteur du cartouche, DÉDUITE des corps de texte : en la fixant en dur, le
    # profil thermique (qui écrit plus gros) débordait sous la marge basse sans
    # que rien ne le signale.
    h_grad = EM_HAUTEUR * corps_grad / MM       # hauteur des chiffres d'axe
    h_cart = EM_HAUTEUR * corps_texte / MM      # hauteur du texte de cartouche
    interligne = 1.5 * corps_texte / MM
    pile = h_cart + 2 * interligne              # 3 lignes empilées
    reserve = (2.2 + h_grad + pile + 0.5) if a_droite else (
        9.2 + h_grad + 2 * interligne + 0.5
    )

    # y0 doit être arrêté AVANT d'en déduire y1, sans quoi la hauteur de grille
    # perd son compte rond de centimètres et le bord haut ne tombe plus sur une
    # graduation (défaut corrigé après lecture du premier rendu).
    y0 = MARGE_MM + reserve
    y1 = y0 + int((hauteur_mm - MARGE_MM - bord_haut - y0) // 10) * 10

    def trace(groupes: list[tuple[float, float, float, float]],
              couleur: tuple[float, float, float], epaisseur: float) -> None:
        if not groupes:
            return
        r, v, b = couleur
        ops.append(f"{flottant(r)} {flottant(v)} {flottant(b)} RG")
        ops.append(f"{flottant(epaisseur)} w")
        for xa, ya, xb, yb in groupes:
            ops.append(
                f"{flottant(xa * MM)} {flottant(ya * MM)} m "
                f"{flottant(xb * MM)} {flottant(yb * MM)} l"
            )
        ops.append("S")

    # Trois passes, du plus clair au plus foncé : le trait fort doit être tracé
    # PAR-DESSUS le trait fin, sinon les fins bavent sur les décimétriques.
    for pas, couleur, epaisseur in (
        (1, c_1mm, ep_1mm),
        (5, c_5mm, ep_5mm),
        (10, c_10mm, ep_10mm),
    ):
        verticales = [
            (x0 + i, y0, x0 + i, y1)
            for i in range(0, int(x1 - x0) + 1, pas)
            # Une ligne appartient au pas le plus grand qui la contient : on
            # saute ici celles qui seront (re)tracées par une passe plus foncée.
            if pas == 10 or (x0 + i) % (pas * 5 if pas == 1 else 10) != 0
        ]
        horizontales = [
            (x0, y0 + i, x1, y0 + i)
            for i in range(0, int(y1 - y0) + 1, pas)
            if pas == 10 or (y0 + i) % (pas * 5 if pas == 1 else 10) != 0
        ]
        trace(verticales + horizontales, couleur, epaisseur)

    # --- Graduations chiffrées (en cm) --------------------------------------
    # Numéroter tous les cm rend la lecture directe sur la photo, sans compter
    # les carreaux. Origine (0,0) = coin bas-gauche de la grille.
    ops.append("BT")
    ops.append(f"/F1 {flottant(corps_grad)} Tf")
    r, v, b = c_10mm
    ops.append(f"{flottant(r)} {flottant(v)} {flottant(b)} rg")

    def etiquette(x_mm: float, y_mm: float, texte: str) -> None:
        ops.append(f"1 0 0 1 {flottant(x_mm * MM)} {flottant(y_mm * MM)} Tm")
        ops.append(f"({echappe(texte)}) Tj")

    # Encombrement d'une étiquette, en mm : déduit du corps de texte pour que
    # les centrages suivent automatiquement le profil (le thermique écrit gros).
    def largeur(texte: str) -> float:
        return len(texte) * EM_CHIFFRE * corps_grad / MM

    hauteur_txt = EM_HAUTEUR * corps_grad / MM
    marge_mire = 0.8  # jeu entre une étiquette d'extrémité et la mire de coin

    # Chaque étiquette est centrée sur sa graduation — SAUF aux extrémités, où
    # elle tomberait sous une mire de coin : là elle est poussée vers l'intérieur
    # de la grille. Sans ça, le « 0 » (l'origine, la graduation la plus utile)
    # disparaît sous le carré noir.
    largeur_cm, hauteur_cm = int(x1 - x0) // 10, int(y1 - y0) // 10
    for i in range(0, largeur_cm + 1):
        gx, lg = x0 + i * 10, largeur(str(i))
        if i == 0:
            x_txt = gx + marge_mire
        elif i == largeur_cm:
            x_txt = gx - marge_mire - lg
        else:
            x_txt = gx - lg / 2
        for y_txt in (y0 - 1.4 - hauteur_txt, y1 + 1.4):
            etiquette(x_txt, y_txt, str(i))
    for i in range(0, hauteur_cm + 1):
        gy = y0 + i * 10
        if i == 0:
            y_txt = gy + marge_mire
        elif i == hauteur_cm:
            y_txt = gy - marge_mire - hauteur_txt
        else:
            y_txt = gy - hauteur_txt / 2
        etiquette(x0 - 1.4 - largeur(str(i)), y_txt, str(i))
        etiquette(x1 + 1.4, y_txt, str(i))
    ops.append("ET")

    # --- Mires de coin -------------------------------------------------------
    # Quatre carrés noirs pleins aux angles de la grille, posés À L'EXTÉRIEUR
    # (leur coin intérieur EST le coin de grille) : ils donnent 4 points de
    # référence à distance connue pour redresser la perspective d'une photo
    # prise de biais, sans recouvrir un seul carreau.
    ops.append("0 0 0 rg")
    for cx, sx in ((x0, -1), (x1, 1)):
        for cy, sy in ((y0, -1), (y1, 1)):
            ops.append(
                f"{flottant(min(cx, cx + sx * MIRE_MM) * MM)} "
                f"{flottant(min(cy, cy + sy * MIRE_MM) * MM)} "
                f"{flottant(MIRE_MM * MM)} {flottant(MIRE_MM * MM)} re f"
            )

    # --- Cartouche bas de page : témoin d'échelle + consigne ----------------
    # Le texte tient à droite de la barre quand la largeur le permet, sinon
    # dessous. Dans les deux cas il reste sous la ligne de base des chiffres de
    # l'axe X (y0 - 1.4 - h_grad) et au-dessus de la marge basse.
    if a_droite:
        base = y0 - 2.2 - h_grad - h_cart
        ty = base - interligne + 0.5            # barre alignée sur la 2e ligne
    else:
        ty = y0 - 2.2 - h_grad - 3.0            # barre juste sous les chiffres
        base = ty - 4.0
    tx = (x0 + 104) if a_droite else x0

    ops.append("0 0 0 RG")
    ops.append("0.8 w")
    # Barre de 100 mm avec ses embouts : à mesurer au réglet après impression.
    ops.append(
        f"{flottant(x0 * MM)} {flottant(ty * MM)} m "
        f"{flottant((x0 + 100) * MM)} {flottant(ty * MM)} l S"
    )
    for x_emb in (x0, x0 + 50, x0 + 100):
        ops.append(
            f"{flottant(x_emb * MM)} {flottant((ty - 1.5) * MM)} m "
            f"{flottant(x_emb * MM)} {flottant((ty + 1.5) * MM)} l S"
        )
    ops.append("BT")
    ops.append(f"/F1 {flottant(corps_texte)} Tf")
    ops.append("0 0 0 rg")
    ops.append(f"1 0 0 1 {flottant(tx * MM)} {flottant(base * MM)} Tm")
    ops.append(
        f"({echappe('Témoin : cette barre doit mesurer 100 mm au réglet.')}) Tj"
    )
    ops.append(
        f"1 0 0 1 {flottant(tx * MM)} {flottant((base - interligne) * MM)} Tm"
    )
    ops.append(
        f"({echappe('Sinon : imprimer à 100 % (taille réelle), pas « ajuster à la page ».')}) Tj"
    )
    # Dimensions hors-tout de la grille : utile pour recaler une photo dont les
    # bords sont coupés, ou pour contrôler une correction de perspective.
    # En monochrome, le gris passerait au tramage : on reste en noir.
    ops.append("0 0 0 rg" if profil["couleur"] == "noir" else "0.45 0.45 0.45 rg")
    ops.append(
        f"1 0 0 1 {flottant(tx * MM)} {flottant((base - 2 * interligne) * MM)} Tm"
    )
    ops.append(
        f"({echappe(f'Grille {int(x1 - x0)} × {int(y1 - y0)} mm entre mires, pas de 1 mm.')}) Tj"
    )
    ops.append("ET")

    return "\n".join(ops)


def ecrit_pdf(chemin: Path, pages: list[tuple[float, float, str]]) -> None:
    """Écrit un PDF multi-pages.

    `pages` = liste de (largeur_mm, hauteur_mm, flux_de_contenu).

    PIÈGE : la table xref doit contenir l'offset EXACT de chaque objet en octets.
    On construit donc le fichier en bytes au fur et à mesure en relevant les
    positions ; toute écriture « en deux temps » désynchroniserait les offsets et
    produirait un PDF refusé par les visionneuses strictes.
    """
    objets: list[bytes] = []

    def ajoute(corps: str) -> int:
        objets.append(corps.encode("cp1252"))
        return len(objets)  # numéro d'objet (1-indexé)

    # Objet 1 = catalogue, objet 2 = arbre des pages : numéros réservés d'avance
    # car les pages doivent référencer leur parent (2) avant qu'il n'existe.
    objets.append(b"")  # placeholder catalogue
    objets.append(b"")  # placeholder pages
    police = ajoute(
        # WinAnsiEncoding (≡ cp1252) : sans elle, la police Type1 de base
        # utilise StandardEncoding, où les accents français n'existent pas.
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        "/Encoding /WinAnsiEncoding >>"
    )

    refs_pages: list[int] = []
    for largeur_mm, hauteur_mm, contenu in pages:
        flux = contenu.encode("cp1252")
        num_flux = ajoute(
            f"<< /Length {len(flux)} >>\nstream\n{contenu}\nendstream"
        )
        num_page = ajoute(
            "<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {flottant(largeur_mm * MM)} {flottant(hauteur_mm * MM)}] "
            f"/Resources << /Font << /F1 {police} 0 R >> >> "
            f"/Contents {num_flux} 0 R >>"
        )
        refs_pages.append(num_page)

    kids = " ".join(f"{n} 0 R" for n in refs_pages)
    objets[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objets[1] = (
        f"<< /Type /Pages /Count {len(refs_pages)} /Kids [{kids}] >>"
    ).encode("cp1252")

    sortie = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for numero, corps in enumerate(objets, start=1):
        offsets.append(len(sortie))
        sortie += f"{numero} 0 obj\n".encode("cp1252") + corps + b"\nendobj\n"

    depart_xref = len(sortie)
    sortie += f"xref\n0 {len(objets) + 1}\n".encode("cp1252")
    sortie += b"0000000000 65535 f \n"
    for offset in offsets:
        sortie += f"{offset:010d} 00000 n \n".encode("cp1252")
    sortie += (
        f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\n"
        f"startxref\n{depart_xref}\n%%EOF\n"
    ).encode("cp1252")

    chemin.write_bytes(sortie)


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--format", default="A4", choices=sorted(FORMATS))
    parseur.add_argument(
        "--orientation", default="les-deux",
        choices=("portrait", "paysage", "les-deux"),
    )
    parseur.add_argument(
        "--profil", default="bureau", choices=sorted(PROFILS),
        help="machine visée : bureau (>= 600 dpi couleur) ou thermique "
             "(203 dpi monochrome)",
    )
    parseur.add_argument(
        "--couleur", default=None, choices=sorted(PALETTES),
        help="force la palette (par défaut : celle du profil)",
    )
    parseur.add_argument(
        "--sortie", type=Path, default=None,
        help="chemin du PDF (défaut : à côté du script)",
    )
    args = parseur.parse_args()

    profil = dict(PROFILS[args.profil])
    if args.couleur:
        profil["couleur"] = args.couleur

    largeur, hauteur = FORMATS[args.format]
    orientations = (
        ["portrait", "paysage"] if args.orientation == "les-deux"
        else [args.orientation]
    )
    pages = [
        (largeur, hauteur, construit_page(largeur, hauteur, profil))
        if sens == "portrait"
        else (hauteur, largeur, construit_page(hauteur, largeur, profil))
        for sens in orientations
    ]

    suffixe = "" if args.profil == "bureau" else f"-{args.profil}"
    sortie = args.sortie or (
        Path(__file__).parent / f"feuille-millimetree-{args.format}{suffixe}.pdf"
    )
    ecrit_pdf(sortie, pages)
    print(
        f"{sortie} — {len(pages)} page(s), {args.format}, "
        f"profil {args.profil}, palette {profil['couleur']}"
    )


if __name__ == "__main__":
    main()
