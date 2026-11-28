"""Lot L3a (28/11) — contrat commun des appareils (theatre_contrats/appareils.py, spec-L3 décisions 9-10).

Le registre et l'enveloppe sont GRAVÉS en littéral (mémoire « graver la valeur attendue », 14/09) :
l'enveloppe attendue est la chaîne de la décision 10, au caractère près.
"""
import pytest

from theatre_contrats import appareils as ap

ENVELOPPE_DECISION_10 = (
    '{"v": 1, "appareil": "sono", "pilote": "sim", "sha": "dev", "t_ms": 1764300000000, '
    '"organes": [{"nom": "audio", "type": "audio", "valeur": "bugs-joues/begaiement.wav", '
    '"debut_ms": 1764299999500, "duree_ms": 2160, "sante": "ok"}, '
    '{"nom": "cut_voice", "type": "relais", "valeur": true, "sante": "ok"}], "refus": null}')

ENVELOPPE_REPOS_REFUS = (
    '{"v": 1, "appareil": "sono", "pilote": "materiel", "sha": "7caeecbc", "t_ms": 5, '
    '"organes": [{"nom": "audio", "type": "audio", "valeur": "", "debut_ms": null, '
    '"duree_ms": null, "sante": "erreur"}, '
    '{"nom": "cut_voice", "type": "relais", "valeur": false, "sante": "absent"}], '
    '"refus": {"code": "audio_absent", "detail": "a/b.mp3", "t_ms": 4}}')


def test_registre_grave():
    assert ap.REGISTRE == {"sono": {"etat": "sono/etat",
                                    "ordres": {"audio": "sono/audio", "relais": "sono/relais"}}}
    assert ap.TYPES_ORGANES == ("audio", "relais")
    assert ap.PILOTES == ("sim", "materiel")
    assert ap.SANTES == ("ok", "absent", "erreur")


def test_listes_derivees_du_registre():
    assert ap.topics_etat() == ("sono/etat",)
    assert ap.topics_ordres() == ("sono/audio", "sono/relais")
    assert ap.topics_ordres("audio") == ("sono/audio",)
    assert ap.topics_ordres("relais") == ("sono/relais",)
    assert ap.topics_ordres("lumiere") == ()


def test_enveloppe_de_la_decision_10_au_caractere_pres():
    brut = ap.encoder_etat(
        "sono", "sim", "dev", 1764300000000,
        [ap.organe_audio("audio", "bugs-joues/begaiement.wav", 1764299999500, 2160),
         ap.organe_relais("cut_voice", True)])
    assert brut == ENVELOPPE_DECISION_10


def test_enveloppe_repos_et_refus():
    brut = ap.encoder_etat("sono", "materiel", "7caeecbc", 5,
                           [ap.organe_audio("audio", sante="erreur"),
                            ap.organe_relais("cut_voice", sante="absent")],
                           ap.refus("audio_absent", "a/b.mp3", 4))
    assert brut == ENVELOPPE_REPOS_REFUS


def test_decoder_aller_retour():
    d = ap.decoder_etat(ENVELOPPE_DECISION_10)
    assert d["organes"][0]["duree_ms"] == 2160
    assert d["organes"][1] == {"nom": "cut_voice", "type": "relais", "valeur": True, "sante": "ok"}
    assert d["refus"] is None
    assert ap.decoder_etat(ENVELOPPE_REPOS_REFUS)["refus"] == {
        "code": "audio_absent", "detail": "a/b.mp3", "t_ms": 4}


@pytest.mark.parametrize("brut", [
    "pas du json",                                                         # 1. JSON cassé
    None,                                                                  # 2. rien
    ENVELOPPE_DECISION_10.replace('"v": 1', '"v": 2'),                     # 3. version inconnue
    ENVELOPPE_DECISION_10.replace('"pilote": "sim"', '"pilote": "gz"'),    # 4. pilote inconnu
    ENVELOPPE_DECISION_10.replace('"valeur": true', '"valeur": 1'),        # 5. relais non booléen
    ENVELOPPE_DECISION_10.replace('"type": "relais"', '"type": "moteur"'),  # 6. type d'organe inconnu
])
def test_decoder_six_illisibles_rendent_none(brut):
    assert ap.decoder_etat(brut) is None


@pytest.mark.parametrize("kw", [
    dict(pilote="gz"), dict(t_ms=True), dict(organes=[{"nom": "x"}]),
    dict(refus_={"code": "x"}), dict(appareil=""),
])
def test_encoder_refuse_une_forme_fausse(kw):
    base = dict(appareil="sono", pilote="sim", sha="dev", t_ms=1, organes=[])
    base.update(kw)
    with pytest.raises(ValueError):
        ap.encoder_etat(**base)
