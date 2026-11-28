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


# --- relecture adverse du 28/11 : decoder_etat ne lève jamais, bornes -------------------------
def test_decoder_recursion_ne_leve_pas():
    assert ap.decoder_etat("[" * 20000) is None
    assert ap.decoder_etat(b"[" * 20000) is None


def test_decoder_taille_bornee_a_64_ko():
    assert ap.TAILLE_MAX_OCTETS == 65536
    marge = 65536 - len(ENVELOPPE_DECISION_10)
    juste = ENVELOPPE_DECISION_10[:-1] + " " * marge + "}"           # 65 536 octets : lu
    assert len(juste) == 65536 and ap.decoder_etat(juste) is not None
    assert ap.decoder_etat(juste[:-1] + " }") is None                 # 65 537 : refusé


def test_decoder_nombre_d_organes_borne_a_16():
    relais = [{"nom": f"r{i}", "type": "relais", "valeur": False, "sante": "ok"} for i in range(17)]
    base = ap.decoder_etat(ENVELOPPE_DECISION_10)
    assert ap.decoder_etat(dict(base, organes=relais[:16])) is not None
    assert ap.decoder_etat(dict(base, organes=relais)) is None
    with pytest.raises(ValueError):
        ap.encoder_etat("sono", "sim", "dev", 1, relais)


@pytest.mark.parametrize("v", [True, 1.0, "1"])
def test_decoder_version_entier_strict(v):
    assert ap.decoder_etat(dict(ap.decoder_etat(ENVELOPPE_DECISION_10), v=v)) is None


def test_decoder_appareil_du_topic():
    assert ap.decoder_etat(ENVELOPPE_DECISION_10, "sono") is not None
    assert ap.decoder_etat(ENVELOPPE_DECISION_10, "lumieres") is None


def test_noms_d_appareil_reserves():
    assert ap.PREFIXES_RESERVES == ("cmd_vel", "route", "wheels", "chat", "rehearsal", "e_stop")
    assert ap.espaces_reserves() >= {"corps_sur", "jeu", "vision", "scene", "corps", "superviseur",
                                     "audio", "face", "wheels", "cmd_vel_web_sur", "deploy_sha"}
    assert "sono" not in ap.espaces_reserves()
    for nom in ("corps_sur", "jeu", "cmd_vel", "cmd_vel_web", "route", "route_speed", "wheels_bridge",
                "chat_move", "rehearsal", "e_stop", "audio", "relay"):
        assert ap.nom_reserve(nom), nom
    # « lights » est DÉJÀ un topic (lumières de scène, topics.LIGHTS) : réservé.
    assert ap.nom_reserve("lights")
    for nom in ("sono", "lumieres", "essai", "fumee"):
        assert not ap.nom_reserve(nom), nom


# --- relecture adverse de L3a (28/11, avant L3b) ----------------------------------------------
def test_espaces_reserves_graves_et_independants_du_registre(monkeypatch):
    assert len(ap.ESPACES_RESERVES) == 33 and "sono" not in ap.ESPACES_RESERVES
    # Inscrire `corps_sur` ou `jeu` au registre ne les rend PAS admissibles (le trou d'avant).
    monkeypatch.setitem(ap.REGISTRE, "corps_sur", {"etat": "corps_sur/etat", "ordres": {}})
    monkeypatch.setitem(ap.REGISTRE, "jeu", {"etat": "jeu/journal", "ordres": {}})
    assert ap.nom_reserve("corps_sur") and ap.nom_reserve("jeu")
    assert "corps_sur" in ap.espaces_reserves() and "jeu" in ap.espaces_reserves()


def test_tout_espace_de_topics_hors_registre_est_reserve():
    """Un nouvel espace de topics dans topics.py sans entrée dans ESPACES_RESERVES = rouge."""
    from theatre_contrats import topics
    du_registre = set(ap.topics_etat()) | set(ap.topics_ordres())
    espaces = {v.split("/")[0] for k, v in vars(topics).items()
               if k.isupper() and isinstance(v, str) and v not in du_registre}
    assert espaces - ap.ESPACES_RESERVES == set()
    for nom in ap.REGISTRE:            # un appareil inscrit n'est jamais un nom réservé
        assert not ap.nom_reserve(nom), nom


def test_bornes_par_champ_gravees():
    assert (ap.TEXTE_MAX, ap.NOM_MAX) == (512, 64)


def _base():
    return ap.decoder_etat(ENVELOPPE_REPOS_REFUS)


@pytest.mark.parametrize("champ,limite", [("valeur", 512), ("nom", 64)])
def test_decoder_dict_organe_audio_borne(champ, limite):
    d = _base()
    d["organes"][0][champ] = "a" * limite
    assert ap.decoder_etat(d) is not None
    d["organes"][0][champ] = "a" * (limite + 1)
    assert ap.decoder_etat(d) is None


def test_decoder_dict_nom_de_relais_borne():
    d = _base()
    d["organes"][1]["nom"] = "r" * 65
    assert ap.decoder_etat(d) is None


def test_decoder_dict_sha_et_detail_bornes():
    assert ap.decoder_etat(dict(_base(), sha="f" * 64)) is not None
    assert ap.decoder_etat(dict(_base(), sha="f" * 65)) is None
    assert ap.decoder_etat(dict(_base(), refus={"code": "x", "detail": "d" * 512, "t_ms": 1})) is not None
    assert ap.decoder_etat(dict(_base(), refus={"code": "x", "detail": "d" * 513, "t_ms": 1})) is None


def test_decoder_dict_taille_totale_bornee():
    """Les champs non bornés un à un (`code`, `appareil`) : la borne totale de 64 ko les tient."""
    long_ = 65536 - len(ENVELOPPE_REPOS_REFUS) + len("audio_absent")
    juste = dict(_base(), refus={"code": "c" * long_, "detail": "a/b.mp3", "t_ms": 4})
    assert ap.decoder_etat(juste) is not None
    trop = dict(_base(), refus={"code": "c" * (long_ + 1), "detail": "a/b.mp3", "t_ms": 4})
    assert ap.decoder_etat(trop) is None


def test_encoder_refuse_un_champ_trop_long():
    with pytest.raises(ValueError):
        ap.encoder_etat("sono", "sim", "s" * 65, 1, [])
    with pytest.raises(ValueError):
        ap.encoder_etat("sono", "sim", "dev", 1, [], ap.refus("x", "d" * 513, 1))
