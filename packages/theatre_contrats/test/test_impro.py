"""Contrat de l'improvisation (lot I0, theatre_contrats.impro) : sorties de fil GRAVÉES en
littéral, chaque décodeur nourri de payloads hostiles (il ne lève jamais, il rend le sens sûr)."""
import pytest

from theatre_contrats import impro


# ---------------------------------------------------------------- jeu/impro
def test_commande_encodee_en_json_chaine():
    assert impro.encoder_commande("on") == '"on"'
    assert impro.encoder_commande("off") == '"off"'
    with pytest.raises(ValueError):
        impro.encoder_commande("ON")


@pytest.mark.parametrize("brut,attendu", [
    ('"on"', "on"), ('"off"', "off"), ("on", "on"), ("off", "off"),   # JSON ou tapé à la main
    (" ON ", "on"), ('"Off"', "off"),
    ('"marche"', None), ("true", None), ("null", None), ("", None), ("[", None),
    ('{"impro": "on"}', None), (None, None), (b'"on"', None),
])
def test_commande_decodee(brut, attendu):
    assert impro.decoder_commande(brut) == attendu


# ---------------------------------------------------------------- jeu/impro_state
def test_etat_encode_grave():
    assert impro.encoder_etat("off", "demarrage", 0) == '{"impro": "off", "cause": "demarrage", "t_ms": 0}'
    assert impro.encoder_etat("on", "cmd", 1234) == '{"impro": "on", "cause": "cmd", "t_ms": 1234}'


@pytest.mark.parametrize("args", [("on", "inconnue", 0), ("allume", "cmd", 0), ("on", "cmd", -1),
                                  ("on", "cmd", 1.5), ("on", "cmd", True)])
def test_etat_encodeur_refuse(args):
    with pytest.raises(ValueError):
        impro.encoder_etat(*args)


def test_les_causes_et_etats_graves():
    assert impro.CAUSES == ("demarrage", "cmd", "stop_contenus", "sans_superviseur", "e_stop")
    assert impro.ETATS == ("on", "off")


def test_etat_decode_aller_retour():
    e = impro.decoder_etat(impro.encoder_etat("on", "cmd", 99))
    assert e == impro.EtatImpro("on", "cmd", 99)
    assert impro.impro_allumee(e) is True
    assert impro.impro_allumee(impro.decoder_etat('{"impro": "off", "cause": "e_stop", "t_ms": 5}')) is False


@pytest.mark.parametrize("brut", [
    "", "on", '"on"', "[]", '{"impro": "on"}', '{"impro": "on", "cause": "cmd"}',
    '{"impro": "on", "cause": "panne", "t_ms": 1}', '{"impro": "ON", "cause": "cmd", "t_ms": 1}',
    '{"impro": "on", "cause": "cmd", "t_ms": -3}', '{"impro": "on", "cause": "cmd", "t_ms": true}',
    '{"impro": "on", "cause": "cmd", "t_ms": 1.0}', "[" * 100_000,
])
def test_etat_illisible_se_lit_eteint(brut):
    assert impro.decoder_etat(brut) is None
    assert impro.impro_allumee(impro.decoder_etat(brut)) is False


# ---------------------------------------------------------------- jeu/proposition
def test_proposition_encodee_gravee():
    assert impro.encoder_proposition("mise_a_jour", None, " il a dit qu'il était fatigué ") == (
        '{"quoi": "mise_a_jour", "cible": null, "pourquoi": "il a dit qu\'il était fatigué"}')
    assert impro.encoder_proposition("lubie", "banc", "x") == '{"quoi": "lubie", "cible": "banc", "pourquoi": "x"}'
    with pytest.raises(ValueError):
        impro.encoder_proposition("", None, "x")
    with pytest.raises(ValueError):
        impro.encoder_proposition("a" * 65, None, "x")


def test_proposition_decodee_et_bornee():
    p = impro.decoder_proposition('{"quoi": " ecran_noir ", "cible": 12, "pourquoi": "' + "m" * 300 + '"}')
    assert p == impro.Proposition(quoi="ecran_noir", cible=None, pourquoi="m" * 120)
    assert impro.decoder_proposition('{"quoi": "lubie", "cible": "banc"}') == impro.Proposition("lubie", "banc", "")


@pytest.mark.parametrize("brut", ["", "null", '"ecran_noir"', "{}", '{"quoi": ""}', '{"quoi": 3}',
                                  '{"quoi": "' + "a" * 65 + '"}', '{"cible": "banc"}'])
def test_proposition_sans_quoi_valide_rien_a_peser(brut):
    assert impro.decoder_proposition(brut) is None


# ---------------------------------------------------------------- jeu/repertoire
def E(ident, genre="bug", dispo=True, dans_s=0.0, desc="d"):
    return impro.EntreeRepertoire(ident, genre, desc, dispo, dans_s)


def test_repertoire_encode_grave():
    assert impro.encoder_repertoire([E("ecran_noir", desc="tout s'éteint"), E("banc", "lubie", False, 42.25)]) == (
        '[{"id": "ecran_noir", "genre": "bug", "desc": "tout s\'éteint", "dispo": true, "dans_s": 0.0}, '
        '{"id": "banc", "genre": "lubie", "desc": "d", "dispo": false, "dans_s": 42.2}]')


def test_repertoire_borne_a_12_et_sans_doublon():
    assert impro.REPERTOIRE_MAX == 12
    assert impro.GENRES == ("bug", "lubie", "expression", "regard")
    impro.encoder_repertoire([E("b{}".format(i)) for i in range(12)])
    with pytest.raises(ValueError):
        impro.encoder_repertoire([E("b{}".format(i)) for i in range(13)])
    with pytest.raises(ValueError):
        impro.encoder_repertoire([E("a"), E("a")])
    with pytest.raises(ValueError):
        impro.encoder_repertoire([E("a", genre="danse")])


def test_repertoire_decode_ecarte_les_fautives():
    brut = ('[{"id": "a", "genre": "bug", "desc": "x", "dispo": true, "dans_s": 0},'
            ' {"id": "b", "genre": "danse", "dispo": true, "dans_s": 0},'
            ' {"id": "c", "genre": "bug", "dispo": "oui", "dans_s": 0},'
            ' {"id": "d", "genre": "bug", "dispo": false, "dans_s": -1},'
            ' {"id": "a", "genre": "lubie", "dispo": true, "dans_s": 0},'
            ' {"id": "e", "genre": "regard", "dispo": false, "dans_s": 1e400},'
            ' 7,'
            ' {"id": "f", "genre": "expression", "dispo": false, "dans_s": 3.5}]')
    assert impro.decoder_repertoire(brut) == [E("a", desc="x"), E("f", "expression", False, 3.5, desc="")]
    assert impro.decoder_repertoire("{") == []
    assert impro.decoder_repertoire('{"id": "a"}') == []
    lignes = ",".join('{{"id": "b{}", "genre": "bug", "dispo": true, "dans_s": 0}}'.format(i) for i in range(20))
    assert [e.id for e in impro.decoder_repertoire("[" + lignes + "]")] == ["b{}".format(i) for i in range(12)]


def test_refus_de_proposition():
    rep = [E("ecran_noir"), E("mise_a_jour", dispo=False, dans_s=120)]
    assert impro.refus_proposition(impro.Proposition("ecran_noir", None, ""), rep) is None
    assert impro.refus_proposition(impro.Proposition("mise_a_jour", None, ""), rep) == "indisponible"
    assert impro.refus_proposition(impro.Proposition("moon-walk", None, ""), rep) == "inconnu"
    assert impro.refus_proposition(impro.Proposition("ecran_noir", None, ""), []) == "inconnu"
