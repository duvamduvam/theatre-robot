"""Briques pures du sélecteur, valeurs GRAVÉES en dur (pas recalculées avec
la fonction testée). Mutations prouvées en fin de fichier."""
import pytest

from conftest import fabriquer


# ------------------------------------------------------------------ offres
def test_offre_ttl_fraicheur_prise():
    from didier_jeu.offres import Offre, Offres
    o = Offre("personne", "p1", 0.7, 10.0, 3.0)
    assert o.fraicheur(10.0) == 1.0
    assert o.fraicheur(11.5) == pytest.approx(0.5)
    assert o.vivante(12.99) and not o.vivante(13.0)       # TTL 3 s
    offres = Offres()
    offres.naitre(o)
    offres.naitre(Offre("objet", "anneaux", 0.8, 10.0, 3.0))
    assert offres.tuer_cible("p1") == 1                    # « ignore »
    assert [x.piste for x in offres.vivantes(10.1)] == ["anneaux"]
    with pytest.raises(ValueError):
        Offre("chien", "x", 1.0, 0.0, 3.0)


# ------------------------------------------------------------------ pistes
def test_piste_hysteresis_d_apparition():
    from didier_jeu.pistes import Pistes
    p = Pistes(perte_s=0.6, nouvelle_apres_s=2.0, confiance_min=0.5)
    assert p.update(0.2, 0.3, 0.9, 0.0) == "p1"            # naissance
    assert p.update(0.25, 0.3, 0.9, 0.1) is None           # même piste
    assert p.courante(0.7) is not None and p.courante(0.71) is None   # perdue après 0,6 s
    assert p.update(0.3, 0.3, 0.9, 2.5) is None            # redétectée 2,4 s après le dernier vu (< 0,6 + 2)
    assert p.update(0.3, 0.3, 0.2, 2.6) is None            # confiance 0,2 < 0,5 : ignorée
    assert p.update(0.3, 0.3, 0.9, 5.2) == "p2"            # silence 2,7 s > 0,6 + 2 : nouvelle


# ------------------------------------------------------------------ pulsions
def test_pulsions_valeurs_gravees():
    s = fabriquer()
    pu = s.pulsions
    pu.avancer(5.0, calme=True)
    assert pu.ennui == pytest.approx(0.5)                   # +0,1 / s
    pu.avancer(10.0, calme=True)
    assert pu.ennui == 1.0                                  # plafond
    pu.sur_action(deplacement=False)
    assert pu.ennui == 0.0                                  # 0 à toute action
    pu.sur_piste_nee()
    assert pu.curiosite == 1.0
    pu.avancer(2.0, calme=False)
    assert pu.curiosite == pytest.approx(0.6)               # −0,2 / s
    pu.sur_poi()
    assert pu.lubie == 0.5
    pu.sur_poi(); pu.sur_poi()
    assert pu.lubie == 1.0                                  # +0,5 par POI, plafond 1
    pu.avancer(4.0, calme=False)
    assert pu.lubie == pytest.approx(0.8)                   # −0,05 / s
    pu.sur_action(deplacement=True); pu.sur_action(deplacement=True)
    assert pu.fatigue == pytest.approx(0.6) and not pu.deplacement_interdit()
    pu.sur_action(deplacement=True)
    assert pu.fatigue == pytest.approx(0.9) and pu.deplacement_interdit()   # > 0,8
    pu.avancer(2.0, calme=False)
    assert pu.fatigue == pytest.approx(0.8) and not pu.deplacement_interdit()  # −0,05 / s


# ------------------------------------------------------------------ score
def test_score_poids_et_immobilite():
    from didier_jeu.offres import Offre
    from didier_jeu.scores import Candidat, Contexte, score
    s = fabriquer()
    ctx = Contexte(now=0.0, jauges={"ennui": 0.5, "curiosite": 1.0})
    assert score(Candidat("rien"), ctx, s.r).total == pytest.approx(0.15)        # 0,3 − 0,3 × 0,5
    o = Offre("personne", "p1", 0.7, 0.0, 3.0)
    # offre 0,7 × 1,0 + curiosité 1 × 0,6 = 1,3 ; gain regarder 1,0
    assert score(Candidat("regarder", "p1", o, "curiosite"), ctx, s.r).total == pytest.approx(1.3)
    # gain accueil 0,8 -> 1,04 ; approcher 0,7 -> 0,91 : regarder domine de plus de 15 %
    assert score(Candidat("accueil", "p1", o, "curiosite"), ctx, s.r).total == pytest.approx(1.04)
    assert score(Candidat("approcher", "p1", o, "curiosite"), ctx, s.r).total == pytest.approx(0.91)
    # metteur en scène 0,8 et console 1,5
    ctx2 = Contexte(now=0.0, jauges={}, metteur={"action": "regarder", "mot": "regarde"},
                   console={"action": None, "cible": "p1", "cmd": "joue_avec"})
    assert score(Candidat("regarder", "p1"), ctx2, s.r).total == pytest.approx(2.3)


def test_refractaire_facteur_zero_puis_un():
    from didier_jeu.scores import Candidat, Contexte, score
    s = fabriquer()
    c = Candidat("spontanee", None, None, "ennui")
    avant = Contexte(now=7.9, jauges={"ennui": 1.0}, derniere_spontanee=0.0)
    apres = Contexte(now=8.0, jauges={"ennui": 1.0}, derniere_spontanee=0.0)
    assert score(c, avant, s.r).total == 0.0                       # < 8 s : 0
    assert score(c, apres, s.r).total == pytest.approx(0.6)        # >= 8 s : 1
    lent = Contexte(now=15.9, jauges={"ennui": 1.0}, derniere_spontanee=0.0, tempo=2.0)
    assert score(c, lent, s.r).total == 0.0                        # « plus lent » : 16 s
    lubie = Candidat("lubie", "x", None, "lubie")
    assert score(lubie, Contexte(now=119.0, jauges={"lubie": 1.0}, derniers={"arret_didier": 0.0}), s.r).total == 0.0


# ------------------------------------------------------------------ arbre
def test_arbre_ordre_des_priorites_grave():
    import py_trees
    from didier_jeu import arbre
    racine = fabriquer().arbre
    assert isinstance(racine, py_trees.composites.Selector)
    assert [c.name for c in racine.children] == ["arret_vocal", "superviseur_absent", "ordre_macro",
                                                 "engagee", "choisir"]
    # Permissions par branche : (déplacement permis, interrompt l'action engagée).
    feuilles = {c.name: (c.children[1] if c.children else c) for c in racine.children}
    assert {n: (f.deplacement_permis, f.interrompt) for n, f in feuilles.items()} == {
        "arret_vocal": (False, False), "superviseur_absent": (False, False),
        "ordre_macro": (True, True), "engagee": (True, False), "choisir": (True, False)}
    assert arbre.BRANCHES == tuple(c.name for c in racine.children)


# ------------------------------------------------------------------ journal
def test_journal_pourquoi_obligatoire(tmp_path):
    from robot.diagnostic.journal import JournalError, parse_lines
    from didier_jeu.journal import Journal
    j = Journal(tmp_path)
    ligne = j.ecrire(5, "decision", {"action": "regarder", "pourquoi": "offre:personne p1 0.70"})
    with pytest.raises(JournalError):
        j.ecrire(6, "decision", {"action": "rien"})
    with pytest.raises(JournalError):
        j.ecrire(7, "decision", {"pourquoi": "   "})
    j.fermer()
    evs = parse_lines(j.chemin.read_text(encoding="utf-8").splitlines())
    assert [(e.source, e.type, e.payload["pourquoi"]) for e in evs] == [
        ("didier_jeu", "decision", "offre:personne p1 0.70")]
    assert ligne == evs[0].to_line()
    assert j.chemin.name.endswith("_jeu.jsonl")


def test_angle_vers():
    import math
    from didier_jeu.selecteur import angle_vers
    assert angle_vers((0.0, 0.0, 0.0), (1.0, 1.0)) == pytest.approx(45.0)        # + = gauche
    assert angle_vers((0.0, 0.0, 0.0), (1.0, -1.0)) == pytest.approx(-45.0)
    assert angle_vers((0.0, 0.0, math.pi / 2), (-1.0, 0.0)) == pytest.approx(90.0)
    assert angle_vers((0.0, 0.0, math.pi), (1.0, 0.1)) == pytest.approx(-174.29, abs=0.01)


def test_ligne_sans_pourquoi_marquee_et_comptee_jamais_avalee():
    from didier_jeu.journal import POURQUOI_ABSENT, marquer_sans_pourquoi
    c = {"sans_pourquoi": 0}
    assert marquer_sans_pourquoi({"pourquoi": "ok"}, c) == {"pourquoi": "ok"}
    assert marquer_sans_pourquoi({"action": "x"}, c) == {"action": "x", "pourquoi": POURQUOI_ABSENT,
                                                         "bug_sans_pourquoi": 1}
    assert marquer_sans_pourquoi({"pourquoi": " "}, c)["bug_sans_pourquoi"] == 2
    assert POURQUOI_ABSENT == "(absent — bug)"
