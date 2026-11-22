"""Pose le visage « v2 » (étude docs/etudes/etude-visage.md, choix de David du 22/11/2026)
dans les DONNÉES du robot, en attendant le moteur paramétrique (lot V1).

Ce que fait ce script :
- dessine chaque image avec la maquette (maquette_visage.py) et l'écrit en PNG RVB 8 bits
  sous data/medias/visuals/{eye,mouth}/, préfixe « v2- » (les anciennes images restent :
  leur retrait est le lot V5) ;
- réécrit les pistes des expressions listées dans ANIMATIONS, dans data/json/expressions.json.
  Les NOMS ne changent pas (conversation, télécommande, séquences et page scène les appellent),
  les autres champs (keys, default, follow audio…) sont conservés.

Rejouable : relancé, il réécrit à l'identique. Lancer depuis la racine du dépôt :
    .venv/bin/python docs/etudes/visage/generer_visuels.py
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from PIL import Image

import maquette_visage as m

RACINE = m.RACINE
VISUELS = RACINE / "data/medias/visuals"
EXPRESSIONS = RACINE / "data/json/expressions.json"

V = m.VOCABULAIRE


# --- Variantes d'œil (calques que le moteur V1 fera seul ; ici, figés en images) -----------
def regard(o: m.Oeil, dx: float, dy: float = 0.0) -> m.Oeil:
    return replace(o, regard=(o.regard[0] + dx, o.regard[1] + dy))


def paupiere(o: m.Oeil, fermeture: float) -> m.Oeil:
    """Œil à demi ou complètement fermé. Fermé = un trait de 2 LED en bas de l'œil, jamais
    du noir : un œil noir fait disparaître le visage pendant le clignement."""
    if fermeture >= 1.0:
        return replace(o, hauteur=1.8, arrondi=0.6, pupille=0, paupiere_haut=0, paupiere_bas=0,
                       arc_bas=0, pente_haut=0, regard=(0.0, 0.0))
    return replace(o, paupiere_haut=max(o.paupiere_haut, fermeture))


def bouche(b: m.Bouche, **champs) -> m.Bouche:
    return replace(b, **champs)


# --- Les images : nom -> (zone, objet dessiné, miroir) --------------------------------------
# Œil droit = miroir de l'œil gauche (pentes de paupière et regard symétriques).
IMAGES: dict[str, tuple[str, object, bool]] = {}


def oeil(nom: str, o: m.Oeil) -> tuple[str, str]:
    """Déclare la paire gauche/droite d'un œil, rend leurs noms de fichier."""
    IMAGES[f"v2-oeil-{nom}-g"] = ("eye", o, False)
    IMAGES[f"v2-oeil-{nom}-d"] = ("eye", o, True)
    return f"v2-oeil-{nom}-g.png", f"v2-oeil-{nom}-d.png"


def oeil_asym(nom: str, og: m.Oeil, od: m.Oeil) -> tuple[str, str]:
    IMAGES[f"v2-oeil-{nom}-g"] = ("eye", og, False)
    IMAGES[f"v2-oeil-{nom}-d"] = ("eye", od, True)
    return f"v2-oeil-{nom}-g.png", f"v2-oeil-{nom}-d.png"


def bch(nom: str, b: m.Bouche) -> str:
    IMAGES[f"v2-bouche-{nom}"] = ("mouth", b, False)
    return f"v2-bouche-{nom}.png"


def piste(*cles):
    """[(fin relative, fichier), …] -> keyframes du format existant."""
    return [[round(t, 3), f] for t, f in cles]


def expression(duree, boucle, yeux, bouches):
    """yeux : [(t, (gauche, droit))] ; bouches : [(t, fichier)]."""
    return {
        "duration": duree, "loop": boucle,
        "left_eyes": piste(*[(t, p[0]) for t, p in yeux]),
        "right_eyes": piste(*[(t, p[1]) for t, p in yeux]),
        "mouths": piste(*bouches),
    }


def _repos():
    o, b = V["repos"].oeil_g, V["repos"].bouche
    centre, mi, ferme = oeil("repos", o), oeil("repos-mi", paupiere(o, 0.55)), oeil("repos-ferme", paupiere(o, 1.0))
    gauche, droite = oeil("repos-g", regard(o, -1.25)), oeil("repos-d", regard(o, 1.25))
    haut = oeil("repos-h", regard(o, 0.4, -1.0))
    calme = bch("repos", b)
    # 6 s : clignement vers 1,8 s, coup d'œil à gauche, à droite, en haut, double clignement.
    # Une image = jusqu'à t (sémantique de Face) ; un clignement = 3 images, ~200 ms.
    return expression(6000, True, [
        (0.30, centre), (0.31, mi), (0.325, ferme), (0.34, mi),
        (0.50, centre), (0.62, gauche), (0.66, centre), (0.78, droite), (0.86, haut),
        (0.93, centre), (0.94, mi), (0.955, ferme), (0.965, mi), (0.975, centre),
        (0.985, ferme), (1.0, mi),
    ], [(1.0, calme)])


def _joie():
    o, b = V["joie"].oeil_g, V["joie"].bouche
    yeux, yeux_plus = oeil("joie", o), oeil("joie-plus", replace(o, arc_bas=3.2, paupiere_bas=0.24))
    rit, rit_fort = bch("joie", b), bch("joie-rire", bouche(b, ouverture=5.5, courbure=6.0))
    return expression(2000, True, [(0.55, yeux), (1.0, yeux_plus)],
                      [(0.3, rit), (0.4, rit_fort), (0.5, rit), (0.6, rit_fort), (1.0, rit)])


def _colere():
    o, b = V["colère"].oeil_g, V["colère"].bouche
    yeux, plisses = oeil("colere", o), oeil("colere-plisse", replace(o, paupiere_haut=0.35))
    moue, gronde = bch("colere", b), bch("colere-gronde", bouche(b, ouverture=1.6, courbure=-3.8))
    return expression(900, True, [(0.5, yeux), (1.0, plisses)], [(0.5, moue), (1.0, gronde)])


def _tristesse():
    o, b = V["triste"].oeil_g, V["triste"].bouche
    bas, mi, ferme = oeil("triste", o), oeil("triste-mi", paupiere(o, 0.6)), oeil("triste-ferme", paupiere(o, 1.0))
    cote = oeil("triste-cote", regard(o, -1.0))
    moue, tremble = bch("triste", b), bch("triste-tremble", bouche(b, courbure=-4.4, largeur=16))
    # Clignement LENT (fatigue) et regard qui fuit sur le côté.
    return expression(4500, True, [
        (0.40, bas), (0.44, mi), (0.52, ferme), (0.58, mi), (0.75, bas), (0.92, cote), (1.0, bas),
    ], [(0.6, moue), (0.68, tremble), (0.76, moue), (0.84, tremble), (1.0, moue)])


def _surprise():
    o, b = V["surprise"].oeil_g, V["surprise"].bouche
    d1 = oeil("surprise-1", replace(o, largeur=6.4, hauteur=6.6, arrondi=2.4))
    d2 = oeil("surprise", o)
    b1, b2, b3 = (bch(f"surprise-{i}", bouche(b, largeur=w, ouverture=h)) for i, (w, h) in
                  enumerate([(8, 3), (10, 5), (12, 7)], 1))
    return expression(2500, False, [(0.12, d1), (1.0, d2)], [(0.1, b1), (0.22, b2), (1.0, b3)])


def _reflechit():
    v = V["réfléchit"]
    hg = oeil_asym("reflechit-hg", regard(v.oeil_g, -2.0, 0.0), regard(v.oeil_d, 0.0, 0.0))
    hc = oeil_asym("reflechit-hc", v.oeil_g, v.oeil_d)
    hd = oeil_asym("reflechit-hd", regard(v.oeil_g, 0.4, -0.3), regard(v.oeil_d, -0.4, -0.3))
    b = v.bouche
    hm, hm2 = bch("reflechit", b), bch("reflechit-cote", bouche(b, courbure=-1.2, largeur=10))
    return expression(1600, True, [(0.33, hg), (0.66, hc), (1.0, hd)], [(0.5, hm), (1.0, hm2)])


def _parle():
    o, b = V["parle"].oeil_g, V["parle"].bouche
    yeux, cote = oeil("parle", o), oeil("parle-d", regard(o, 0.8))
    ouvertures = [("ferme", 0.6, 20), ("petit", 2.4, 19), ("moyen", 4.2, 18), ("grand", 6.0, 16)]
    f = {n: bch(f"parle-{n}", bouche(b, ouverture=h, largeur=w)) for n, h, w in ouvertures}
    # 800 ms, rythme IRRÉGULIER (petit-grand-ferme-moyen-petit-ferme) : en attendant le volume réel.
    return expression(800, True, [(0.5, yeux), (1.0, cote)], [
        (0.12, f["petit"]), (0.3, f["grand"]), (0.4, f["ferme"]), (0.58, f["moyen"]),
        (0.7, f["petit"]), (0.82, f["ferme"]), (1.0, f["moyen"]),
    ])


def _amour():
    o, b = V["amour"].oeil_g, V["amour"].bouche
    coeur = oeil("coeur", o)
    battu = oeil("coeur-battu", replace(o, couleur=tuple(int(c * 0.55) for c in o.couleur)))
    sourit, sourit2 = bch("amour", b), bch("amour-plus", bouche(b, courbure=4.6, largeur=20))
    # Battement : deux coups rapprochés, une pause.
    return expression(1800, True, [(0.12, coeur), (0.2, battu), (0.32, coeur), (0.4, battu), (1.0, coeur)],
                      [(0.32, sourit2), (1.0, sourit)])


def _ecoute():
    o, b = V["écoute"].oeil_g, V["écoute"].bouche
    yeux, mi, ferme = oeil("ecoute", o), oeil("ecoute-mi", paupiere(o, 0.55)), oeil("ecoute-ferme", paupiere(o, 1.0))
    penche = oeil("ecoute-penche", regard(o, -0.6, -0.4))
    return expression(4000, True, [(0.45, yeux), (0.47, mi), (0.5, ferme), (0.53, mi), (0.8, yeux), (1.0, penche)],
                      [(1.0, bch("ecoute", b))])


def _emerveille():
    o, b = V["émerveillé"].oeil_g, V["émerveillé"].bouche
    yeux, brille = oeil("emerveille", o), oeil("emerveille-brille", replace(o, pupille=1.8))
    return expression(1500, True, [(0.5, yeux), (1.0, brille)],
                      [(0.5, bch("emerveille", b)), (1.0, bch("emerveille-plus", bouche(b, ouverture=6.5)))])


def _malice():
    v = V["malice"]
    yeux = oeil_asym("malice", v.oeil_g, v.oeil_d)
    clin = oeil_asym("malice-clin", v.oeil_g, paupiere(v.oeil_d, 1.0))
    b = v.bouche
    return expression(3000, False, [(0.55, yeux), (0.75, clin), (1.0, yeux)],
                      [(0.55, bch("malice", b)), (1.0, bch("malice-plus", bouche(b, courbure=4.2, largeur=21)))])


def _dodo():
    o, b = V["dodo"].oeil_g, V["dodo"].bouche
    yeux = oeil("dodo", o)
    respire = bch("dodo", b)
    souffle = bch("dodo-souffle", bouche(b, ouverture=0.6, largeur=6))
    return expression(4000, True, [(1.0, yeux)], [(0.5, respire), (1.0, souffle)])


# Nom d'expression (inchangé ou nouveau, sans accent) -> fabrique de pistes.
ANIMATIONS = {
    "default": _repos, "repos neon": _repos, "joie": _joie, "colere": _colere,
    "tristesse": _tristesse, "surprise": _surprise, "reflechit": _reflechit, "parle": _parle,
    "amour neon": _amour, "ecoute": _ecoute, "emerveille": _emerveille, "malice": _malice,
    "dodo": _dodo,
}


def ecrire_png(chemin: Path, rgb) -> None:
    Image.fromarray(rgb, "RGB").save(chemin, optimize=True)


def main() -> None:
    catalogue = json.loads(EXPRESSIONS.read_text(encoding="utf-8"))
    for nom, fabrique in ANIMATIONS.items():
        pistes = fabrique()
        entree = catalogue.get(nom, {"name": nom, "keys": []})
        entree.update(pistes)  # garde keys, default, follow audio…
        catalogue[nom] = entree
    for nom, (zone, objet, miroir) in IMAGES.items():
        rgb = m.dessiner_oeil(objet, miroir=miroir) if zone == "eye" else m.dessiner_bouche(objet)
        ecrire_png(VISUELS / zone / f"{nom}.png", rgb)
    EXPRESSIONS.write_text(json.dumps(catalogue, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"{len(ANIMATIONS)} expressions, {len(IMAGES)} images écrites")


if __name__ == "__main__":
    main()
