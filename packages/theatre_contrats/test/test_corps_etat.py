"""Lot S2a (27/11) — contrat `corps/etat` (theatre_contrats/corps_etat.py, spec-S2 §2, §7 tests 1 et 2).

Phrases GRAVÉES à la main, une par cause (11) : un test qui recomposerait l'attendu avec `composer`
ne testerait rien (mémoire « graver la valeur attendue », 14/09).
"""
import itertools
import json
import pathlib
import re

import pytest

from theatre_contrats import corps_etat as ce
from theatre_contrats.objets import Objet, Tableau

MONO = pathlib.Path(__file__).resolve().parents[3]
ARME = ce.CorpsSur("ARME", "LIBRE")


def faits(**k):
    """Une séance en cours, route en marche, corps sûr armé et libre ; `k` change un fait."""
    base = dict(route_state="on", corps_sur=ARME, seance_connue=True, en_seance=True)
    base.update(k)
    return ce.Faits(**base)


AV_GRUE = {"cmd": "aller_voir", "objet": "grue_jaune", "id": "carte/grue_jaune", "origine": "david"}
AV_BANC = {"cmd": "aller_voir", "objet": "banc", "id": "carte/banc", "origine": "david"}


# ---------------------------------------------------------------- 1. une phrase gravée par cause
@pytest.mark.parametrize("f, marche, cause, qui, phrase", [
    (faits(verrou="voix"), "arrete", "david_stop_voix", "david",
     "Tu es arrêté : David t'a dit stop. Seul un go de David te relance."),
    (faits(verrou="console"), "arrete", "david_stop_console", "david_console",
     "Tu es arrêté : David t'a arrêté à la console. Seul son bouton GO te relance."),
    (faits(verrou="route", route_state="off"), "arrete", "david_route_off", "david_console",
     "Tu es arrêté : David a coupé ta route. Seul David la relance, sur la page."),
    (faits(reprise="didier_lubie", reprise_cible="banc", repart_dans_s=12.0, arret_vocal=True), "arrete",
     "didier_lubie", "didier",
     "Tu es arrêté, attiré par « banc » : c'est toi qui t'es arrêté. Tu repars dans 12 s si personne ne parle."),
    (faits(reprise="didier_pause", repart_dans_s=23.4), "arrete", "didier_pause", "didier",
     "Tu es arrêté pour regarder : c'est toi qui t'es arrêté. Tu repars dans 23 s si personne ne parle."),
    (faits(reprise="didier_stop", repart_dans_s=17.1), "arrete", "didier_stop", "didier",
     "Tu es arrêté : c'est toi qui t'es arrêté. Tu repars dans 17 s si personne ne parle."),
    (faits(reprise="geste_fini", repart_dans_s=9.6, route_state="arrived"), "arrete", "geste_fini", "didier",
     "Tu es arrêté : ton geste est fini. Tu repars dans 10 s si personne ne parle."),
    (faits(corps_sur=ce.CorpsSur("VERROU", "LIBRE", "capteur_perdu")), "empeche", "corps_sur_verrou", "personne",
     "Tu ne peux pas bouger : ton corps est verrouillé par sécurité. Il faut le réarmer avant tout."),
    (faits(corps_sur=ce.CorpsSur("ARME", "ARRET")), "empeche", "corps_sur_zone", "personne",
     "Tu ne peux pas avancer : ta sécurité te retient. Tu repars dès qu'elle te laisse."),
    (faits(en_seance=False, route_state="off"), "empeche", "seance_non_lancee", "david_console",
     "Tu ne peux pas bouger : la séance n'est pas lancée. David peut la démarrer sur la page."),
    (faits(), "en_route", "aucune", None, "Tu roules sur ta route."),
], ids=lambda v: v if isinstance(v, str) and v in ce.CAUSES else None)
def test_1_une_phrase_gravee_par_cause(f, marche, cause, qui, phrase):
    e = ce.etablir(f)
    assert (e.marche, e.cause, e.qui_relance, e.phrase) == (marche, cause, qui, phrase)


def test_1_les_onze_causes_sont_couvertes():
    assert len(ce.CAUSES) == 11
    assert ce.CAUSES == ("david_stop_voix", "david_stop_console", "david_route_off", "didier_lubie", "didier_pause",
                         "didier_stop", "geste_fini", "corps_sur_verrou", "corps_sur_zone", "seance_non_lancee",
                         "aucune")
    assert ce.MARCHES == ("en_route", "arrete", "geste", "empeche")
    assert ce.QUI_RELANCE == ("david_console", "david", "didier", "personne")


def test_1_exemples_de_la_spec_aux_guillemets_pres():
    """Les exemples de la spec §2 (« la flaque », « le banc ») : les noms du tableau n'ont pas
    d'article — la phrase les cite entre guillemets, sans inventer de genre."""
    ici = ce.Ici("flaque", (ce.Proche("banc", "devant", 6.2),))
    assert ce.etablir(faits(ici=ici)).phrase == \
        "Tu roules sur ta route. Tu traverses : « flaque ». Devant toi à 6 m : « banc »."
    abandon = ce.Geste(AV_GRUE, "abandonne", "corps_sur", 0.0)
    assert ce.etablir(faits(corps_sur=ce.CorpsSur("VERROU"), geste=abandon)).phrase == (
        "Tu ne peux pas bouger : ton corps est verrouillé par sécurité. Il faut le réarmer avant tout. "
        "Ton dernier geste (aller voir « grue jaune ») a été abandonné après 0,0 m : ton corps est verrouillé "
        "par sécurité.")
    refus = ce.Geste(AV_BANC, "refuse", "arrete", 0.0)
    assert ce.etablir(faits(verrou="console", geste=refus)).phrase == (
        "Tu es arrêté : David t'a arrêté à la console. Seul son bouton GO te relance. Ton dernier geste (aller "
        "voir « banc ») a été refusé, tu n'as pas bougé : tu étais arrêté par David.")


def test_1_marche_geste_et_arret_sans_cause_connue():
    en_cours = ce.Geste(AV_BANC, "en_cours")
    e = ce.etablir(faits(geste_en_cours=True, geste=en_cours))
    assert (e.marche, e.cause, e.qui_relance, e.phrase) == ("geste", "aucune", None,
                                                           "Tu es en plein geste : aller voir « banc ».")
    # Arrêté en séance sans verrou ni reprise (arrêt vocal au régisseur, route coupée au boot) :
    # personne ne le relancera de lui-même — seul un go de David.
    e = ce.etablir(faits(arret_vocal=True))
    assert (e.marche, e.cause, e.qui_relance, e.phrase) == ("arrete", "aucune", "david",
                                                           "Tu es arrêté. Seul un go de David te relance.")
    arrive = ce.Geste({"cmd": "tourner", "angle_deg": -90.0, "origine": "david"}, "arrive", None, 0.0)
    assert ce.etablir(faits(route_state="off", geste=arrive)).phrase == (
        "Tu es arrêté. Seul un go de David te relance. Ton dernier geste (tourner de 90° à droite) est fini : "
        "tu es arrivé après 0,0 m.")


def test_1_geste_en_cours_passe_devant_une_reprise_armee():
    """Un ordre de David parti pendant qu'une reprise attendait : il roule, il n'attend plus."""
    e = ce.etablir(faits(reprise="didier_stop", repart_dans_s=8.0, geste_en_cours=True,
                         geste=ce.Geste(AV_BANC, "en_cours")))
    assert (e.marche, e.cause) == ("geste", "aucune")


# ---------------------------------------------------------------- 1. corps sûr prioritaire, jamais deux causes
def test_1_corps_sur_passe_avant_tout_le_reste():
    tout = dict(verrou="console", reprise="didier_lubie", reprise_cible="banc", repart_dans_s=5.0,
                geste_en_cours=True, en_seance=False)
    e = ce.etablir(faits(corps_sur=ce.CorpsSur("VERROU", "ARRET", "e_stop"), **tout))
    assert (e.marche, e.cause, e.qui_relance) == ("empeche", "corps_sur_verrou", "personne")
    e = ce.etablir(faits(corps_sur=ce.CorpsSur("DEMARRAGE", "LIBRE", "sante_en_cours"), **tout))
    assert e.cause == "corps_sur_verrou"
    e = ce.etablir(faits(corps_sur=ce.CorpsSur("ARME", "PAUSE_DUREE"), **tout))
    assert (e.marche, e.cause) == ("empeche", "corps_sur_zone")
    # RALENTI ne retient pas : il roule (plus lentement), le verrou de David reprend la main.
    e = ce.etablir(faits(corps_sur=ce.CorpsSur("ARME", "RALENTI"), **tout))
    assert e.cause == "david_stop_console"


def test_1_jamais_deux_causes_sur_toutes_les_combinaisons():
    """Toute combinaison de faits donne UNE cause du contrat, et la phrase n'en dit qu'une."""
    corps = [ARME, ce.CorpsSur("VERROU"), ce.CorpsSur("ARME", "ARRET"), ce.CorpsSur("ARME", "RALENTI")]
    n = 0
    for cs, verrou, reprise, route, seance, geste, vocal in itertools.product(
            corps, (None, "console", "route", "voix"), (None,) + ce.REPRISES, ("on", "off", "goto", "arrived"),
            (True, False), (False, True), (False, True)):
        e = ce.etablir(faits(corps_sur=cs, verrou=verrou, reprise=reprise, repart_dans_s=3.0, route_state=route,
                             en_seance=seance, geste_en_cours=geste, arret_vocal=vocal))
        assert e.cause in ce.CAUSES and e.marche in ce.MARCHES
        dites = [c for c, p in ce.PHRASES_CAUSE.items() if p[0].split("{")[0] in e.phrase]
        assert dites == ([e.cause] if e.cause in ce.PHRASES_CAUSE else []), (e.cause, e.phrase)
        n += 1
    assert n == 4 * 4 * 5 * 4 * 2 * 2 * 2


# ---------------------------------------------------------------- 1. état inconnu
@pytest.mark.parametrize("manque", [dict(route_state=None), dict(corps_sur=None), dict(seance_connue=False)])
def test_1_une_source_jamais_recue_rend_l_etat_inconnu(manque):
    e = ce.etablir(faits(verrou="console", **manque))
    assert e == ce.INCONNU
    assert (e.marche, e.cause, e.qui_relance, e.phrase) == ("empeche", "aucune", None,
                                                           "Tu ne sais pas où en est ton corps.")


def test_1_source_muette_plus_de_3_s_etat_inconnu():
    """Le lecteur de corps/etat : reçu à 10,0 s, cru jusqu'à 13,0 s, INCONNU au-delà."""
    raw = ce.encoder(ce.etablir(faits(verrou="voix")), 10000)
    assert ce.lire(raw, 10.0, 13.0).cause == "david_stop_voix"
    assert ce.lire(raw, 10.0, 13.01) == ce.INCONNU
    assert ce.lire(None, None, 0.0) == ce.INCONNU
    assert (ce.PEREMPTION_S, ce.PERIODE_MAX_S, ce.GESTE_MEMOIRE_S) == (3.0, 2.0, 60.0)


# ---------------------------------------------------------------- 1. plafond de 300 caractères
def test_1_plafond_de_300_caracteres_par_phrases_entieres():
    long_ = "x" * 40
    ici = ce.Ici(long_, (ce.Proche(long_, "devant", 4.0), ce.Proche(long_ + "y", "gauche", 5.0)))
    geste = ce.Geste({"cmd": "tour_de", "objet": long_ * 20}, "abandonne", "max_travel", 12.25)
    e = ce.etablir(faits(verrou="console", geste=geste, ici=ici))
    assert e.phrase == ("Tu es arrêté : David t'a arrêté à la console. Seul son bouton GO te relance. Ton dernier "
                        f"geste (faire le tour de « {long_} ») a été abandonné après 12,2 m : tu as fait trop de "
                        "chemin sans arriver.")
    assert len(e.phrase) <= 300


def test_1_une_phrase_qui_deborde_est_retiree_entiere():
    """Sept proches (hors contrat : `ici_depuis` en garde deux) : la seconde phrase déborde -> retirée."""
    ici = ce.Ici(None, tuple(ce.Proche("y" * 40, "devant", float(i)) for i in range(2, 9)))
    assert ce.composer("en_route", "aucune", ici=ici) == "Tu roules sur ta route."


def test_1_garde_ultime_une_seule_phrase_coupee_a_300(monkeypatch):
    """Inatteignable avec les textes gravés et des noms plafonnés à 40 : la borne tient quand même."""
    monkeypatch.setattr(ce, "PHRASE_EN_ROUTE", "z" * 400)
    texte = ce.composer("en_route", "aucune")
    assert len(texte) == 300 and texte == "z" * 299 + "…"


# ---------------------------------------------------------------- 2. ici
def _objet(nom, distance, azimut, cote, emprise=None, en_vue=True):
    return Objet(id=f"carte/{nom}", nom=nom, x=0.0, y=0.0, distance_m=distance, azimut_deg=azimut, cote=cote,
                 emprise_m=emprise, en_vue=en_vue)


def test_2_objet_sous_didier():
    t = Tableau((_objet("flaque", 0.8, 0.0, "devant", emprise=1.0), _objet("banc", 6.2, 4.0, "devant")))
    assert ce.ici_depuis(t) == ce.Ici("flaque", (ce.Proche("banc", "devant", 6.2),))


def test_2_objet_derriere():
    t = Tableau((_objet("banc", 3.04, 171.0, "derriere", emprise=1.1),))
    ici = ce.ici_depuis(t)
    assert ici == ce.Ici(None, (ce.Proche("banc", "derriere", 3.0),))
    assert ce.etablir(faits(ici=ici)).phrase == "Tu roules sur ta route. Derrière toi à 3 m : « banc »."
    # À l'arrêt : « dessus ou tout contre », jamais « tu traverses ».
    sous = ce.ici_depuis(Tableau((_objet("flaque", 1.2, 0.0, "devant", emprise=0.9),)))
    assert ce.etablir(faits(verrou="voix", ici=sous)).phrase == (
        "Tu es arrêté : David t'a dit stop. Seul un go de David te relance. Tu es dessus ou tout contre : « flaque ».")


def test_2_aucun_objet():
    assert ce.ici_depuis(Tableau()) == ce.Ici(None, ())
    assert ce.etablir(faits(ici=ce.ici_depuis(Tableau()))).phrase == "Tu roules sur ta route."


def test_2_emprise_inconnue_portee_et_deux_proches_au_plus():
    t = Tableau((_objet("pigeon", 0.4, 0.0, "devant"),                 # emprise inconnue : 0 + 0,5 -> dessus
                 _objet("poteau", 0.6, 90.0, "gauche"),                 # 0,6 > 0,5 : pas dessus
                 _objet("banc", 4.0, -60.0, "droite"), _objet("grue", 9.9, 0.0, "devant"),
                 _objet("loin", 10.5, 0.0, "devant"),                   # au-delà de la portée (10 m)
                 Objet(id="carte/sans", nom="sans", x=1.0, y=1.0)))     # distance inconnue
    assert ce.ici_depuis(t) == ce.Ici("pigeon", (ce.Proche("poteau", "gauche", 0.6), ce.Proche("banc", "droite", 4.0)))
    assert ce.etablir(faits(ici=ce.ici_depuis(t))).phrase == (
        "Tu roules sur ta route. Tu traverses : « pigeon ». Sur ta gauche à moins d'un mètre : « poteau » ; sur ta "
        "droite à 4 m : « banc ».")


# ---------------------------------------------------------------- encodage
def test_encodage_aller_retour():
    e = ce.etablir(faits(reprise="didier_lubie", reprise_cible="banc", repart_dans_s=12.04, arret_vocal=True,
                         geste=ce.Geste(AV_BANC, "refuse", "pas_ici", 0.0),
                         ici=ce.Ici("flaque", (ce.Proche("banc", "devant", 6.2),))))
    v = json.loads(ce.encoder(e, 1234))
    assert v == {"v": 1, "t_ms": 1234, "marche": "arrete", "cause": "didier_lubie", "qui_relance": "didier",
                 "repart_dans_s": 12.0,
                 "geste": {"demande": AV_BANC, "etat": "refuse", "raison": "pas_ici", "parcouru_m": 0.0},
                 "ici": {"sur": "flaque", "proches": [{"nom": "banc", "cote": "devant", "distance_m": 6.2}]},
                 # Trois phrases au plus : le dernier geste passe avant ce qui l'entoure (ici retiré).
                 "phrase": "Tu es arrêté, attiré par « banc » : c'est toi qui t'es arrêté. Tu repars dans 12 s si "
                           "personne ne parle. Ton dernier geste (aller voir « banc ») a été refusé, tu n'as pas "
                           "bougé : ce n'est pas ici."}
    assert ce.decoder(ce.encoder(e, 1234)) == e


@pytest.mark.parametrize("raw", ["", "pas du json", "[]", json.dumps({"v": 2, "marche": "arrete", "cause": "aucune"}),
                                 json.dumps({"v": 1, "marche": "vole", "cause": "aucune"}),
                                 json.dumps({"v": 1, "marche": "arrete", "cause": "lune"}), None, 12])
def test_decodeur_tolerant_illisible_inconnu(raw):
    assert ce.decoder(raw) == ce.INCONNU


def test_decodeur_tolerant_champs_faux_valeur_sure():
    raw = json.dumps({"v": 1, "marche": "arrete", "cause": "didier_stop", "qui_relance": "le pape",
                      "repart_dans_s": 10 ** 400, "geste": {"etat": "vole"},
                      "ici": {"sur": 3, "proches": [{"nom": "banc", "cote": "dessous", "distance_m": 1.0},
                                                    {"nom": "grue", "cote": "gauche", "distance_m": float("nan")},
                                                    {"nom": "pigeon", "cote": "gauche", "distance_m": 2.0}]},
                      "phrase": "x" * 301})
    e = ce.decoder(raw)
    assert (e.qui_relance, e.repart_dans_s, e.geste, e.ici) == (None, None, None,
                                                                ce.Ici(None, (ce.Proche("pigeon", "gauche", 2.0),)))
    # Phrase trop longue : recomposée depuis les champs lus.
    assert e.phrase == ("Tu es arrêté : c'est toi qui t'es arrêté. Tu repartiras seul après un silence. "
                        "Sur ta gauche à 2 m : « pigeon ».")


def test_cle_ignore_les_nombres_qui_glissent():
    a = ce.etablir(faits(reprise="didier_stop", repart_dans_s=12.0, ici=ce.Ici(None, (ce.Proche("banc", "devant", 6.2),))))
    b = ce.etablir(faits(reprise="didier_stop", repart_dans_s=11.0, ici=ce.Ici(None, (ce.Proche("banc", "devant", 5.1),))))
    c = ce.etablir(faits(reprise="didier_stop", repart_dans_s=11.0, ici=ce.Ici(None, (ce.Proche("banc", "gauche", 5.1),))))
    assert ce.cle(a) == ce.cle(b) != ce.cle(c)


# ---------------------------------------------------------------- corps sûr : lecture et littéraux
def test_lire_corps_sur():
    assert ce.lire_corps_sur({"etat": "VERROU", "cause": "e_stop", "zone": "LIBRE", "d_min_m": 3.2}) == \
        ce.CorpsSur("VERROU", "LIBRE", "e_stop")
    assert ce.lire_corps_sur({"etat": "ARME", "cause": "", "zone": "ARRET"}).retient is True
    assert ce.lire_corps_sur({"etat": "ARME", "zone": "SOUS_LA_MER"}) == ce.CorpsSur("ARME", None, "")
    for faux in ({"etat": "PANIQUE"}, "VERROU", None, []):
        assert ce.lire_corps_sur(faux) is None


def test_litteraux_du_corps_sur_egaux_a_ceux_du_noeud():
    """Lus dans les VRAIS fichiers de didier_corps_sur (il n'est pas importé ici)."""
    garde = (MONO / "packages" / "didier_corps_sur" / "didier_corps_sur" / "garde.py").read_text(encoding="utf-8")
    zones = (MONO / "packages" / "didier_corps_sur" / "didier_corps_sur" / "zones.py").read_text(encoding="utf-8")
    for nom in ce.CORPS_SUR_ETATS + ("PAUSE_DUREE",):
        assert re.search(rf'^{nom} = "{nom}"$', garde, re.M), nom
    for nom in ("LIBRE", "RALENTI", "ARRET"):
        assert re.search(rf'^{nom} = "{nom}"$', zones, re.M), nom
    assert ce.CORPS_SUR_ZONES == ("LIBRE", "RALENTI", "ARRET", "PAUSE_DUREE")
