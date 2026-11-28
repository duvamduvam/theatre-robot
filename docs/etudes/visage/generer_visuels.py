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

import numpy as np
from PIL import Image

import maquette_glitchs as gl
import maquette_visage as m
import pictos as px

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



# =========================================================================================
# §12 — les trois mondes (27/11) : les 18 expressions restantes et les nouveaux pictogrammes.
# Les images « brutes » (pictos, yeux-symboles, glitchs) ne passent pas par les dessins
# paramétriques : elles sont rangées telles quelles dans IMAGES, zone « eye-brut »/« mouth-brut ».
# =========================================================================================


def brut(zone: str, nom: str, rgb) -> str:
    IMAGES[f"v2-{nom}"] = (zone + "-brut", np.asarray(rgb, np.uint8), False)
    return f"v2-{nom}.png"


def yeux_symbole(nom: str) -> tuple[str, str]:
    return (brut("eye", f"oeil-{nom}-g", px.oeil_symbole(nom)),
            brut("eye", f"oeil-{nom}-d", px.oeil_symbole(nom, miroir=True)))


def b_picto(nom: str, rgb) -> str:
    return brut("mouth", f"bouche-{nom}", rgb)


def yeux_de(nom_vocabulaire: str, nom_fichier: str) -> tuple[str, str]:
    v = V[nom_vocabulaire]
    return oeil_asym(nom_fichier, v.oeil_g, v.oeil_d)


# --- Lui --------------------------------------------------------------------------------
def _etourdi():
    sp, cr = yeux_symbole("spirale"), yeux_symbole("croix")
    o1, o2 = bch("etourdi", V["surprise"].bouche), bch("etourdi-2", bouche(V["surprise"].bouche, largeur=10, ouverture=5))
    return expression(2400, True, [(0.85, sp), (1.0, cr)], [(0.5, o1), (1.0, o2)])


def _ko():
    cr = yeux_symbole("croix")
    return expression(3000, False, [(1.0, cr)], [(1.0, bch("ko", V["triste"].bouche))])


def _etoiles():
    et = yeux_symbole("etoile")
    rit, rit2 = bch("etoiles", V["joie"].bouche), bch("etoiles-2", bouche(V["joie"].bouche, ouverture=5.5))
    return expression(1600, True, [(1.0, et)], [(0.5, rit), (1.0, rit2)])


def _idee():
    yeux = yeux_de("émerveillé", "idee")
    eteinte, allumee = b_picto("ampoule", px.ampoule(0)), b_picto("ampoule-on", px.ampoule(1))
    return expression(2500, False, [(1.0, yeux)], [(0.35, eteinte), (0.45, allumee), (0.55, eteinte), (1.0, allumee)])


def _hein():
    q = yeux_symbole("interro")
    return expression(2000, False, [(1.0, q)], [(1.0, bch("hein", V["réfléchit"].bouche))])


def _chante():
    yeux = oeil("chante", V["joie"].oeil_g)
    n1, n2 = b_picto("note", px.note(0)), b_picto("note-2", px.note(1))
    return expression(1000, True, [(1.0, yeux)], [(0.5, n1), (1.0, n2)])


def _ennui():
    e = yeux_symbole("ennui")
    o = V["repos"].oeil_g
    cote = oeil("ennui-cote", regard(paupiere(o, 0.45), -1.4))
    m1 = bch("ennui", V["réfléchit"].bouche)
    return expression(5000, True, [(0.6, e), (1.0, cote)], [(1.0, m1)])


def _bisou():
    c = oeil("coeur", V["amour"].oeil_g)
    b1, b2 = b_picto("bisou", px.bisou(0)), b_picto("bisou-2", px.bisou(1))
    return expression(1500, True, [(1.0, c)], [(0.6, b1), (1.0, b2)])


def _grand_amour():
    c = oeil("coeur", V["amour"].oeil_g)
    battu = oeil("coeur-battu", replace(V["amour"].oeil_g, couleur=tuple(int(x * 0.55) for x in V["amour"].oeil_g.couleur)))
    g, p = b_picto("grand-coeur", px.coeur(1)), b_picto("grand-coeur-petit", px.coeur(0))
    return expression(1200, True, [(0.15, c), (0.3, battu), (0.45, c), (1.0, battu)], [(0.15, g), (0.3, p), (0.45, g), (1.0, p)])


def _gros_mot():
    yeux = yeux_de("colère", "gros-mot")
    return expression(1800, False, [(1.0, yeux)], [(0.5, b_picto("gros-mot", px.mot("#!*", px.ROUGE))), (1.0, bch("gros-mot-moue", V["colère"].bouche))])


def _dodo_zzz():
    yeux = oeil("dodo", V["dodo"].oeil_g)
    z = [b_picto(f"zzz-{i}", px.zzz(t)) for i, t in enumerate((0.0, 0.4, 0.8))]
    return expression(3000, True, [(1.0, yeux)], [(0.33, z[0]), (0.66, z[1]), (1.0, z[2])])


# --- Sa machine ---------------------------------------------------------------------------
def _mise_a_jour():
    e = yeux_symbole("ennui")
    etapes = [b_picto(f"maj-{n}", px.mise_a_jour(n, 47)) for n in (3, 4, 5, 6)]
    return expression(8000, False, [(1.0, e)], [(0.4, etapes[0]), (0.65, etapes[1]), (0.85, etapes[2]), (1.0, etapes[3])])


def _404():
    cr = yeux_symbole("croix")
    a, b = b_picto("404", px.erreur_404()), b_picto("404-noir", np.zeros((16, 24, 3), np.uint8))
    return expression(2000, True, [(1.0, cr)], [(0.7, a), (1.0, b)])  # 404 qui clignote lentement


def _pas_de_reseau():
    q = yeux_symbole("interro")
    return expression(3000, True, [(1.0, q)], [(1.0, b_picto("wifi-barre", px.wifi(1, barre=True)))])


def _cherche_reseau():
    yeux = yeux_de("réfléchit", "cherche-reseau")
    w = [b_picto(f"wifi-{i}", px.wifi(t)) for i, t in enumerate((0.34, 0.67, 1.0))]
    return expression(1800, True, [(1.0, yeux)], [(0.33, w[0]), (0.66, w[1]), (1.0, w[2])])


def _batterie():
    yeux = oeil_asym("batterie", V["triste"].oeil_g, V["triste"].oeil_d)
    p, v = b_picto("batterie", px.batterie(0.15)), b_picto("batterie-vide", px.batterie(0.0))
    return expression(2000, True, [(1.0, yeux)], [(0.6, p), (1.0, v)])


def _patientez():
    e = yeux_symbole("ennui")
    s = [b_picto(f"sablier-{i}", px.sablier(t)) for i, t in enumerate((0.0, 0.35, 0.7, 1.0))]
    return expression(3200, True, [(1.0, e)], [(0.25, s[0]), (0.5, s[1]), (0.75, s[2]), (1.0, s[3])])


def _nuage():
    an = yeux_symbole("ange")
    n = [b_picto(f"nuage-{i}", px.nuage(t, fleche_haut=True)) for i, t in enumerate((0.0, 0.35, 0.7))]
    return expression(1500, True, [(1.0, an)], [(0.33, n[0]), (0.66, n[1]), (1.0, n[2])])


def _attention():
    ex = yeux_symbole("exclam")
    a, b = b_picto("attention", px.attention(1)), b_picto("attention-sombre", px.attention(0))
    return expression(1400, True, [(1.0, ex)], [(0.6, a), (1.0, b)])


def _fantome():
    cr = yeux_symbole("croix")
    f = [b_picto(f"fantome-{i}", px.fantome(t)) for i, t in enumerate((0.0, 0.3, 0.6))]
    return expression(2400, False, [(1.0, cr)], [(0.33, f[0]), (0.66, f[1]), (1.0, f[2])])


# Glitchs dessinés (en attendant le calque du §11) : tirés de la maquette, graine fixe,
# changements pleine face ≤ 3 par seconde (règle des 3 flashs).
def _glitch(nom, duree, effets, boucle=True):
    rng = np.random.default_rng(sum(map(ord, nom)))
    base = gl.zones(V["repos"])
    yeux_g, yeux_d, bouches = [], [], []
    for i, (fin, efs) in enumerate(effets):
        z = [x.copy() for x in base]
        for effet, ou, kw in efs:
            for k in ou:
                z[k] = effet(z[k], rng, **kw)
        yeux_g.append((fin, brut("eye", f"oeil-{nom}-{i}-g", z[0])))
        yeux_d.append((fin, brut("eye", f"oeil-{nom}-{i}-d", z[1])))
        bouches.append((fin, brut("mouth", f"bouche-{nom}-{i}", z[2])))
    return {"duration": duree, "loop": boucle, "left_eyes": piste(*yeux_g), "right_eyes": piste(*yeux_d), "mouths": piste(*bouches)}


def _fuzz():
    return _glitch("fuzz", 1000, [
        (0.5, [(gl.neige, (2,), {"n": 6}), (gl.couleurs_separees, (2,), {})]),
        (1.0, [(gl.ligne_decalee, (2,), {"lignes": 2, "dx": 2}), (gl.pixel_chaud, (0, 1), {"n": 1})]),
    ])


def _repos_glitch():
    return _glitch("repos-glitch", 7000, [
        (0.40, []), (0.42, [(gl.ligne_decalee, (0,), {"dx": 2})]), (0.70, []),
        (0.72, [(gl.couleurs_separees, (2,), {})]), (0.95, []), (0.97, [(gl.pixel_mort, (2,), {"n": 4})]), (1.0, []),
    ])


def _glitch_total():
    lourd = lambda dx: [(gl.ligne_decalee, (0, 1), {"dx": dx}), (gl.ligne_decalee, (2,), {"lignes": 2, "dx": dx + 1}),
                        (gl.couleurs_separees, (0, 1, 2), {"dx": 1}), (gl.neige, (0, 1, 2), {"n": 3})]
    return _glitch("glitch-total", 1400, [(0.25, lourd(1)), (0.5, lourd(3)), (0.75, lourd(2) + [(gl.derive, (0, 1, 2), {"tour": 0.28})]), (1.0, lourd(1))])


# --- Sa quête -----------------------------------------------------------------------------
def _boussole():
    sp = yeux_symbole("spirale")
    b = [b_picto(f"boussole-{i}", px.boussole(t)) for i, t in enumerate((0.0, 0.3, 0.55, 0.62, 0.9))]
    return expression(1500, True, [(1.0, sp)], [(0.2, b[0]), (0.4, b[1]), (0.6, b[2]), (0.8, b[3]), (1.0, b[4])])


def _fleche(sens, couleur, yeux_nom):
    def f():
        yeux = yeux_symbole("interro") if yeux_nom == "interro" else yeux_de(yeux_nom, f"fleche-{sens}")
        pleine = b_picto(f"fleche-{sens}", px.fleche(sens, couleur))
        vide = b_picto("vide", np.zeros((16, 24, 3), np.uint8))
        return expression(1500, True, [(1.0, yeux)], [(0.7, pleine), (1.0, vide)])
    return f


def _porte():
    et = yeux_symbole("etoile")
    f, o = b_picto("porte", px.porte(0)), b_picto("porte-ouverte", px.porte(1))
    return expression(3000, False, [(1.0, et)], [(0.4, f), (1.0, o)])


def _ange():
    an = yeux_symbole("ange")
    return expression(4000, True, [(1.0, an)], [(0.6, bch("ange", V["joie"].bouche)), (1.0, bch("ange-2", bouche(V["joie"].bouche, ouverture=2.5)))])


def _diable(parle=False):
    def f():
        d = yeux_symbole("diable")
        b = replace(V["malice"].bouche, couleur=px.ROUGE)
        if not parle:
            return expression(5000, True, [(1.0, d)], [(0.8, bch("diable", b)), (1.0, bch("diable-2", bouche(b, courbure=4.2)))])
        ouv = [bch(f"diable-parle-{i}", bouche(b, ouverture=h, courbure=1.4, largeur=18)) for i, h in enumerate((0.6, 2.6, 4.6, 6.0))]
        return expression(800, True, [(1.0, d)], [(0.12, ouv[1]), (0.3, ouv[3]), (0.4, ouv[0]), (0.58, ouv[2]), (0.7, ouv[1]), (0.82, ouv[0]), (1.0, ouv[2])])
    return f


def _signe(nom, image, yeux_nom):
    """Oui / non : un signe (coche, croix) plutôt qu'un mot, lisible de loin et sans langue."""
    def f():
        yeux = yeux_de(yeux_nom, f"signe-{nom}")
        return expression(1500, False, [(1.0, yeux)], [(1.0, b_picto(f"signe-{nom}", image()))])
    return f


# Anciennes expressions : le nom reste, le dessin passe au v2 (table §12.2).
ANIMATIONS.update({
    "speak": _parle, "speak loop": _parle, "voila": _etoiles, "bored": _ennui,
    "default red": _diable(), "repos braise": _diable(), "speak red": _diable(parle=True),
    "sexy": _bisou, "love": _grand_amour, "brain": _nuage, "upgrade": _mise_a_jour,
    "internet": _cherche_reseau, "warning": _attention, "scooby-doo": _fantome,
    "fuzz": _fuzz, "repos glitch": _repos_glitch, "glitch total": _glitch_total,
})
# Nouvelles expressions (noms sans accent, règle MOTIF_NOM_ENTREE).
ANIMATIONS.update({
    "etourdi": _etourdi, "ko": _ko, "etoiles": _etoiles, "idee": _idee, "hein": _hein,
    "chante": _chante, "ennui": _ennui, "bisou": _bisou, "grand amour": _grand_amour,
    "gros mot": _gros_mot, "zzz": _dodo_zzz,
    "mise a jour": _mise_a_jour, "404": _404, "pas de reseau": _pas_de_reseau,
    "cherche reseau": _cherche_reseau, "batterie": _batterie, "patientez": _patientez,
    "nuage": _nuage, "attention": _attention, "fantome": _fantome,
    "boussole": _boussole, "fleche droite": _fleche("droite", px.VERT, "émerveillé"),
    "fleche gauche": _fleche("gauche", px.AMBRE, "interro"), "tout droit": _fleche("haut", px.VERT, "joie"),
    "porte": _porte, "ange": _ange, "diable": _diable(), "oui": _signe("oui", px.coche, "joie"),
    "non": _signe("non", px.croix, "colère"),
})



# Le corps suit l'émotion (David, 27/11 ; étude §12.6) : champ `corps` de chaque expression,
# nom d'une entrée BOUCLÉE de robot_lights.json. Absent = le corps n'est pas touché (mires,
# glitchs et écran noir : les bugs joués posent leurs propres lumières).
CORPS = {
    "default": "default", "repos neon": "default",
    # lui
    "joie": "joie", "etoiles": "joie", "voila": "joie", "chante": "joie", "oui": "joie",
    "colere": "colere", "gros mot": "colere", "non": "colere",
    "tristesse": "triste", "ko": "triste", "batterie": "triste",
    "surprise": "surprise", "etourdi": "surprise", "hein": "surprise", "emerveille": "surprise",
    "amour neon": "amour", "love": "amour", "grand amour": "amour", "bisou": "amour", "sexy": "amour",
    "malice": "default", "dodo": "dodo", "zzz": "dodo", "ennui": "dodo", "bored": "dodo",
    "idee": "ange",
    # conversation
    "ecoute": "ecoute", "reflechit": "comet", "parle": "parle", "speak": "parle", "speak loop": "parle",
    # machine
    "mise a jour": "comet", "upgrade": "comet", "cherche reseau": "comet", "internet": "comet",
    "patientez": "comet", "nuage": "ange", "brain": "ange",
    "404": "alerte", "pas de reseau": "alerte", "attention": "alerte", "warning": "alerte",
    "fantome": "ange", "scooby-doo": "ange",
    # quête
    "boussole": "comet", "fleche droite": "comet", "fleche gauche": "comet", "tout droit": "comet",
    "porte": "ange", "ange": "ange",
    "diable": "devil", "default red": "devil", "repos braise": "devil", "speak red": "devil",
}

def ecrire_png(chemin: Path, rgb) -> None:
    Image.fromarray(rgb, "RGB").save(chemin, optimize=True)


def main() -> None:
    catalogue = json.loads(EXPRESSIONS.read_text(encoding="utf-8"))
    for nom, fabrique in ANIMATIONS.items():
        pistes = fabrique()
        entree = catalogue.get(nom, {"name": nom, "keys": []})
        entree.update(pistes)  # garde keys, default, follow audio…
        if nom in CORPS:
            entree["corps"] = CORPS[nom]
        catalogue[nom] = entree
    for nom, (zone, objet, miroir) in IMAGES.items():
        if zone.endswith("-brut"):  # picto, œil-symbole ou glitch : déjà une image
            zone, rgb = zone[:-5], objet
        else:
            rgb = m.dessiner_oeil(objet, miroir=miroir) if zone == "eye" else m.dessiner_bouche(objet)
        ecrire_png(VISUELS / zone / f"{nom}.png", rgb)
    EXPRESSIONS.write_text(json.dumps(catalogue, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"{len(ANIMATIONS)} expressions, {len(IMAGES)} images écrites")


if __name__ == "__main__":
    main()
