"""Écrivain des données (lot L1d, didier_web.data_edit.traiter), sans ROS, sur un dossier
jetable, horloge injectée. Valeurs GRAVÉES : octets exacts écrits et leur sha256 en littéral
(calculés par hashlib hors du module), nom exact de la sauvegarde, ligne exacte du journal,
un cas par code de verdict (décision 2 de la spec L1d).
"""
import base64
import datetime
import json
import os
import struct
import zlib

import pytest

from didier_web import data_edit
from didier_web.data_edit import traiter

MAINTENANT = datetime.datetime(2026, 11, 12, 20, 30, 15)


def bloc(type_bloc, contenu):
    return (struct.pack(">I", len(contenu)) + type_bloc + contenu
            + struct.pack(">I", zlib.crc32(type_bloc + contenu) & 0xFFFFFFFF))


def png(largeur, hauteur, pixel=b"\x00\x00\x00"):
    ihdr = struct.pack(">IIBBBBB", largeur, hauteur, 8, 2, 0, 0, 0)
    lignes = b"".join(b"\x00" + pixel * largeur for _ in range(hauteur))
    return b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", ihdr) + bloc(b"IDAT", zlib.compress(lignes, 0)) + bloc(b"IEND", b"")


BOUCHE_NOIRE = png(24, 16)
BOUCHE_ROUGE = png(24, 16, b"\xff\x00\x00")
OEIL = png(8, 8)

EXPRESSIONS = {
    "joie": {"duration": 2000, "loop": True, "mouths": [[1, "neutre.png"]], "left_eyes": [], "right_eyes": []},
    "colere": {"duration": 1000, "loop": False, "mouths": [], "left_eyes": [[1, "rond.png"]], "right_eyes": []},
}
LUMIERES = {"calme": {"duration": 1000, "loop": False, "sequences": {"bleu": 1}}}
BRIQUES = {"bleu": {"method": "chase", "color": "BLUE"}, "rouge": {"method": "blink", "color": "BLUE"}}


@pytest.fixture
def data_dir(tmp_path):
    for dossier in ("json/sequences/essai", "json/sequences/autre", "medias/audios",
                    "medias/visuals/mouth", "medias/visuals/eye"):
        (tmp_path / dossier).mkdir(parents=True)
    (tmp_path / "medias/visuals/mouth/neutre.png").write_bytes(BOUCHE_NOIRE)
    (tmp_path / "medias/visuals/eye/rond.png").write_bytes(OEIL)
    for relatif, valeur in (("json/expressions.json", EXPRESSIONS), ("json/robot_lights.json", LUMIERES),
                            ("json/lights_base.json", BRIQUES), ("json/colors.json", {"BLUE": [0, 0, 255]})):
        (tmp_path / relatif).write_text(json.dumps(valeur, indent=4), encoding="utf-8")
    return tmp_path


def demande(kind, mode, name, content, id_="d1", **autres):
    d = {"id": id_, "kind": kind, "mode": mode, "name": name, "content": content}
    d.update(autres)
    return json.dumps(d)


def lancer(data_dir, brut, enabled=True, maintenant=MAINTENANT):
    return traiter(brut, data_dir, enabled, maintenant)


def arbre(racine, sous):
    base = os.path.join(racine, sous)
    return sorted(os.path.relpath(os.path.join(d, f), base) for d, _, fs in os.walk(base) for f in fs)


SEQUENCE = {"keys": "Z9", "duration": 4000, "neck": [[0, 0.5]]}
# json.dumps(SEQUENCE, indent=4, ensure_ascii=False) + "\n", GRAVÉ.
OCTETS_SEQUENCE = (b'{\n    "keys": "Z9",\n    "duration": 4000,\n    "neck": [\n        [\n'
                   b'            0,\n            0.5\n        ]\n    ]\n}\n')
# sha256 des octets ci-dessus (hashlib, hors module).
SHA_SEQUENCE = "95d6e83cf646a559ec91277f09b8487f4cb12d91aa6bbb19d30b054a25ca0ad5"


# ================================================================ écritures réussies, octets gravés
def test_create_sequence_octets_et_sha(data_dir):
    v = lancer(data_dir, demande("sequence", "create", "essai/bonjour", SEQUENCE))
    assert (data_dir / "json/sequences/essai/bonjour.json").read_bytes() == OCTETS_SEQUENCE
    assert v == {"id": "d1", "ok": True, "code": "ok", "detail": [], "kind": "sequence",
                 "name": "essai/bonjour", "mode": "create", "sha256": SHA_SEQUENCE, "sauvegarde": None,
                 "avertissements": ["a_rejouer_en_sim"]}
    # Journal : la ligne exacte (création = pas de sauvegarde).
    assert (data_dir / "json/backup/EDITIONS-EN-ATTENTE.jsonl").read_text(encoding="utf-8") == (
        '{"id":"d1","kind":"sequence","mode":"create","name":"essai/bonjour","sauvegarde":null,'
        '"sha256":"' + SHA_SEQUENCE + '","t":"2026-11-12T20:30:15"}\n')


def test_replace_sequence_sauvegarde_et_journal(data_dir):
    cible = data_dir / "json/sequences/essai/bonjour.json"
    cible.write_bytes(b'{"keys": "Z9", "duration": 4000, "neck": [[0, 0.2]]}')
    base = "556bbfad5ffa5204256c89e9d96d9fc4eec9c75e995b45c36c77a9eb24f2bbc3"
    v = lancer(data_dir, demande("sequence", "replace", "essai/bonjour", SEQUENCE, id_="r-2", base_sha256=base))
    assert v["code"] == "ok" and v["sha256"] == SHA_SEQUENCE
    assert v["sauvegarde"] == "json/backup/2026-11-12/sequence__essai_bonjour__203015__r-2.json"
    assert (data_dir / v["sauvegarde"]).read_bytes() == b'{"keys": "Z9", "duration": 4000, "neck": [[0, 0.2]]}'
    assert cible.read_bytes() == OCTETS_SEQUENCE
    assert (data_dir / "json/backup/EDITIONS-EN-ATTENTE.jsonl").read_text(encoding="utf-8") == (
        '{"id":"r-2","kind":"sequence","mode":"replace","name":"essai/bonjour",'
        '"sauvegarde":"json/backup/2026-11-12/sequence__essai_bonjour__203015__r-2.json",'
        '"sha256":"' + SHA_SEQUENCE + '","t":"2026-11-12T20:30:15"}\n')


def test_create_expression_entree_en_fin_et_voisines_intactes(data_dir):
    neuve = {"duration": 500, "loop": False, "mouths": [[1, "neutre.png"]], "left_eyes": [], "right_eyes": []}
    v = lancer(data_dir, demande("expression", "create", "l1d visage", neuve))
    assert v["code"] == "ok"
    assert v["sha256"] == "f98d1dad58021b79e389e4fe0dd68b0911dc0af1894766ca57e5e8fdd4bdf0ca"
    assert v["sauvegarde"] == "json/backup/2026-11-12/expression__l1d_visage__203015__d1.json"
    ecrit = (data_dir / "json/expressions.json").read_bytes()
    assert ecrit == json.dumps({**EXPRESSIONS, "l1d visage": neuve}, indent=4).encode() + b"\n"
    relu = json.loads(ecrit)
    assert list(relu) == ["joie", "colere", "l1d visage"]
    # Une entrée posée ne change pas les octets canoniques des voisines.
    for voisine in ("joie", "colere"):
        assert json.dumps(relu[voisine], sort_keys=True) == json.dumps(EXPRESSIONS[voisine], sort_keys=True)


def test_replace_lumiere_octets(data_dir):
    base = "ea36335022ce14bd8d4a532dacd9376f87650a3223a039b900bf3c9537e198d3"
    nouvelle = {"duration": 2000, "loop": True, "sequences": {"bleu": 0.5, "rouge": 1}}
    v = lancer(data_dir, demande("lumiere", "replace", "calme", nouvelle, base_sha256=base))
    assert v["code"] == "ok" and v["sha256"] == "8db7ac7770f28f8e50790a03402cdb022f02b94de71f14c32b2c10715f17ced6"
    assert (data_dir / "json/robot_lights.json").read_bytes() == (
        b'{\n    "calme": {\n        "duration": 2000,\n        "loop": true,\n        "sequences": {\n'
        b'            "bleu": 0.5,\n            "rouge": 1\n        }\n    }\n}\n')


def test_replace_brique_octets(data_dir):
    base = "e21dd1a21e163a8a597309681565ea267c0d0cf156af931dfc46fbd91fd63fab"
    v = lancer(data_dir, demande("brique", "replace", "rouge", {"method": "pulse", "color": "BLUE", "speed": 0.2},
                                 base_sha256=base))
    assert v["code"] == "ok" and v["sha256"] == "3798ee363507cc8fc87e1afbe061f16b53c5a85b65a94c7b46aa50aa6a6cb22c"
    assert v["avertissements"] == []  # aucune lumière n'enchaîne « rouge »
    assert json.loads((data_dir / "json/lights_base.json").read_bytes()) == {
        "bleu": BRIQUES["bleu"], "rouge": {"method": "pulse", "color": "BLUE", "speed": 0.2}}


def test_create_image_octets_tels_quels(data_dir):
    v = lancer(data_dir, demande("image", "create", "mouth/sourire", base64.b64encode(BOUCHE_ROUGE).decode()))
    assert v["code"] == "ok" and v["sha256"] == "8910a6c8c8cc88d6054aaa6f5379eeafc9e5daced4e761b86024939da248cdf7"
    assert v["avertissements"] == []  # aucune expression ne la montre encore
    assert (data_dir / "medias/visuals/mouth/sourire.png").read_bytes() == BOUCHE_ROUGE


def test_replace_image_perime_l_expression_qui_la_montre(data_dir):
    v = lancer(data_dir, demande("image", "replace", "mouth/neutre", base64.b64encode(BOUCHE_ROUGE).decode(),
                                 base_sha256="03ee5069491826cebda6c8a7c770a33b7feb9d38adb781f34ca0af3a21b99de3"))
    assert v["code"] == "ok"
    assert v["sauvegarde"] == "json/backup/2026-11-12/image__mouth_neutre__203015__d1.png"
    assert (data_dir / v["sauvegarde"]).read_bytes() == BOUCHE_NOIRE
    assert v["avertissements"] == ["a_rejouer_en_sim"]


def test_sequence_a_roues_avertit(data_dir):
    roues = {**SEQUENCE, "wheels": [[0.1, [0.2, 0.2]], [0.5, [0, 0]]]}
    v = lancer(data_dir, demande("sequence", "create", "essai/roues", roues))
    assert v["avertissements"] == ["a_rejouer_en_sim", "roues_a_valider_en_sim"]


# ================================================================ un cas par code
def test_inchange_ni_sauvegarde_ni_journal(data_dir):
    (data_dir / "json/sequences/essai/bonjour.json").write_bytes(OCTETS_SEQUENCE)
    v = lancer(data_dir, demande("sequence", "replace", "essai/bonjour", SEQUENCE, base_sha256=SHA_SEQUENCE))
    assert (v["code"], v["ok"], v["sha256"]) == ("inchange", True, SHA_SEQUENCE)
    assert not (data_dir / "json/backup").exists()


def test_edition_desactivee(data_dir):
    v = lancer(data_dir, demande("sequence", "create", "essai/bonjour", SEQUENCE), enabled=False)
    assert (v["id"], v["ok"], v["code"]) == ("d1", False, "edition_desactivee")
    assert not (data_dir / "json/sequences/essai/bonjour.json").exists()


@pytest.mark.parametrize("brut, detail", [
    ("pas du json", "objet JSON attendu"),
    ("[1, 2]", "objet JSON attendu"),
    (json.dumps({"id": "a b", "kind": "sequence"}), "id : 1 à 64 caractères [A-Za-z0-9_-] attendus"),
    (demande("sequence", "create", "essai/x", SEQUENCE, extra=1), "champs inconnus : extra"),
    (demande("sequence", "create", 3, SEQUENCE), "name : chaîne attendue"),
    (demande("sequence", "replace", "essai/x", SEQUENCE), "base_sha256 (64 hex minuscules) exigé en replace"),
    (demande("sequence", "create", "essai/x", SEQUENCE, base_sha256="0" * 64), "base_sha256 réservé au mode replace"),
    (demande("sequence", "create", "essai/x", [1]), "content : objet JSON attendu"),
    (demande("image", "create", "mouth/x", "%%%"), "content : base64 illisible"),
    (demande("image", "create", "mouth/x", {"a": 1}), "content : les octets du PNG en base64 attendus"),
])
def test_payload_invalide(data_dir, brut, detail):
    v = lancer(data_dir, brut)
    assert (v["code"], v["detail"]) == ("payload_invalide", [detail])


def test_trop_gros_avant_tout_decodage(data_dir):
    brut = " " * (data_edit.TAILLE_MAX_DEMANDE + 1)
    assert data_edit.TAILLE_MAX_DEMANDE == 131_072
    v = lancer(data_dir, brut)
    assert (v["code"], v["id"], v["detail"]) == ("trop_gros", None, ["131073 octets, maximum 131072"])
    assert lancer(data_dir, demande("sequence", "create", "essai/x", SEQUENCE, id_="t") + " " * 100)["code"] == "ok"


def test_kind_et_mode_inconnus(data_dir):
    assert lancer(data_dir, demande("relais", "create", "x", {}))["code"] == "kind_inconnu"
    assert lancer(data_dir, demande("sequence", "delete", "essai/x", {}))["code"] == "mode_inconnu"


@pytest.mark.parametrize("kind, name", [
    ("sequence", "../x/y"), ("sequence", "essai/../../x"), ("sequence", "bonjour"),
    ("image", "../mouth/x"), ("expression", "Joie"), ("image", "icons/x"),
])
def test_nom_invalide_rien_d_ecrit(data_dir, kind, name):
    avant = arbre(data_dir, "")
    contenu = base64.b64encode(BOUCHE_ROUGE).decode() if kind == "image" else SEQUENCE
    assert lancer(data_dir, demande(kind, "create", name, contenu))["code"] == "nom_invalide"
    assert arbre(data_dir, "") == avant


def test_lien_symbolique_refuse(data_dir):
    (data_dir / "json/sequences/essai/lien.json").symlink_to(data_dir / "json/colors.json")
    v = lancer(data_dir, demande("sequence", "replace", "essai/lien", SEQUENCE, base_sha256="0" * 64))
    assert v["code"] == "nom_invalide"


def test_dossier_absent(data_dir):
    v = lancer(data_dir, demande("sequence", "create", "nouveau/x", SEQUENCE))
    assert (v["code"], v["detail"]) == ("dossier_absent", ["dossier nouveau absent (une création de dossier passe par git)"])
    assert not (data_dir / "json/sequences/nouveau").exists()


def test_existe_deja_et_absent(data_dir):
    assert lancer(data_dir, demande("expression", "create", "joie", EXPRESSIONS["joie"]))["code"] == "existe_deja"
    assert lancer(data_dir, demande("sequence", "replace", "essai/absente", SEQUENCE,
                                    base_sha256="0" * 64))["code"] == "absent"


def test_nom_en_double_sequence_et_image(data_dir):
    (data_dir / "json/sequences/autre/bonjour.json").write_bytes(OCTETS_SEQUENCE)
    assert lancer(data_dir, demande("sequence", "create", "essai/bonjour", SEQUENCE))["code"] == "nom_en_double"
    v = lancer(data_dir, demande("image", "create", "mouth/rond", base64.b64encode(BOUCHE_ROUGE).decode()))
    assert v["code"] == "nom_en_double"


def test_conflit(data_dir):
    v = lancer(data_dir, demande("expression", "replace", "joie", EXPRESSIONS["joie"], base_sha256="0" * 64))
    assert v["code"] == "conflit"


def test_cle_inconnue(data_dir):
    v = lancer(data_dir, demande("sequence", "create", "essai/x", {**SEQUENCE, "vitesse": 2}))
    assert (v["code"], v["detail"]) == ("cle_inconnue", ["clés hors liste pour sequence : vitesse"])


def test_contrat_rien_d_ecrit(data_dir):
    avant = arbre(data_dir, "")
    v = lancer(data_dir, demande("sequence", "create", "essai/x", {**SEQUENCE, "faces": [[0, "inconnue"]]}))
    assert (v["code"], v["detail"]) == ("contrat", ["faces[0] : référence l'expression inconnue 'inconnue'"])
    assert arbre(data_dir, "") == avant


@pytest.mark.parametrize("wheels, detail", [
    ([[0.1, [0.95, 0.95]], [0.5, [0, 0]]], "wheels[0] : consigne roues [0.95, 0.95] au-delà de 0.89 (VITESSE_ROUES_MAX)"),
    ([[0.1, [0.2, 0.2]]], "wheels : la dernière image doit valoir [0, 0] (arrêt final), reçu [0.1, [0.2, 0.2]]"),
    ([[0.1, {"speed": 100}], [0.5, [0, 0]]],
     "wheels[0] : consigne roues [gauche, droite] (deux nombres) attendue, reçu {'speed': 100}"),
])
def test_roues_hors_bornes_refusees(data_dir, wheels, detail):
    v = lancer(data_dir, demande("sequence", "create", "essai/roues", {**SEQUENCE, "wheels": wheels}))
    assert (v["code"], v["detail"]) == ("contrat", [detail])
    assert arbre(data_dir, "json/sequences") == []


def test_image_hors_contrat_rien_sous_visuels(data_dir):
    avant = arbre(data_dir, "medias/visuals")
    v = lancer(data_dir, demande("image", "create", "eye/large", base64.b64encode(BOUCHE_ROUGE).decode()))
    assert (v["code"], v["detail"]) == ("contrat", ["image : 24x16, attendu 8x8 pour la zone eye"])
    v = lancer(data_dir, demande("image", "create", "mouth/texte", base64.b64encode(b"bonjour").decode()))
    assert (v["code"], v["detail"]) == ("contrat", ["image : signature PNG absente"])
    assert arbre(data_dir, "medias/visuals") == avant


def test_quota_jour(data_dir):
    jour = data_dir / "json/backup/2026-11-12"
    jour.mkdir(parents=True)
    for i in range(data_edit.QUOTA_JOUR):
        (jour / "s{}.json".format(i)).write_text("{}")
    v = lancer(data_dir, demande("lumiere", "create", "neuve", LUMIERES["calme"]))
    assert (v["code"], v["detail"]) == ("quota_jour", ["200 sauvegardes aujourd'hui (maximum 200)"])
    assert "neuve" not in json.loads((data_dir / "json/robot_lights.json").read_text())


def test_erreur_ecriture_cible_intacte_tmp_vide(data_dir, monkeypatch):
    avant = (data_dir / "json/expressions.json").read_bytes()

    def panne(*_):
        raise OSError("disque plein")
    monkeypatch.setattr(data_edit.os, "replace", panne)
    v = lancer(data_dir, demande("expression", "replace", "joie", {**EXPRESSIONS["joie"], "duration": 9},
                                 base_sha256="381ee37c835f5994afaeaae7af65dce4b17cedaf0c06186428c963691aacb63b"))
    assert (v["code"], v["detail"]) == ("erreur_ecriture", ["OSError : disque plein"])
    assert (data_dir / "json/expressions.json").read_bytes() == avant
    assert os.listdir(data_dir / "json/backup/.tmp") == []


def test_codes_graves():
    assert data_edit.CODES == (
        "ok", "inchange", "edition_desactivee", "payload_invalide", "trop_gros", "kind_inconnu",
        "mode_inconnu", "nom_invalide", "dossier_absent", "existe_deja", "absent", "nom_en_double",
        "conflit", "cle_inconnue", "contrat", "quota_jour", "erreur_ecriture")


# ================================================================ temporaire, rotation, propriétaire
def test_tmp_vide_apres_succes_et_temporaire_jamais_sous_sequences(data_dir, monkeypatch):
    vus = []
    vrai_replace = os.replace

    def espion(src, dst):
        vus.append(os.path.relpath(src, data_dir))
        vrai_replace(src, dst)
    monkeypatch.setattr(data_edit.os, "replace", espion)
    lancer(data_dir, demande("sequence", "create", "essai/x", SEQUENCE, id_="abc"))
    assert vus == ["json/backup/.tmp/abc"]
    assert os.listdir(data_dir / "json/backup/.tmp") == []


def test_rotation_a_31_dossiers_dates(data_dir):
    racine = data_dir / "json/backup"
    for jour in range(1, 31):  # 30 dossiers datés anciens ; l'écriture crée le 31e
        (racine / "2026-10-{:02d}".format(jour)).mkdir(parents=True)
    (racine / "notes").mkdir()  # ce qui n'est pas daté n'est jamais effacé
    lancer(data_dir, demande("lumiere", "create", "neuve", LUMIERES["calme"]))
    dates = sorted(r for r in os.listdir(racine) if r.startswith("2026-"))
    assert len(dates) == 30
    assert dates[0] == "2026-10-02" and dates[-1] == "2026-11-12"
    assert (racine / "notes").is_dir()


def test_vider_tmp(data_dir):
    tmp = data_dir / "json/backup/.tmp"
    tmp.mkdir(parents=True)
    (tmp / "vieux").write_text("x")
    assert data_edit.vider_tmp(data_dir) == 1
    assert os.listdir(tmp) == []
    assert data_edit.vider_tmp(data_dir / "inexistant") == 0


def test_temporaire_d_image_sur_le_montage_medias(data_dir, monkeypatch):
    # json/ et medias/ sont deux montages (sim, compose ARM) : os.replace de json/backup/.tmp
    # vers medias/visuals/ échoue en EXDEV (mesuré en sim le 12/11). Le temporaire d'une image
    # vit sur medias/, HORS de medias/visuals/ que Face.load_visuals lit en entier.
    vus = []
    vrai_replace = os.replace

    def espion(src, dst):
        vus.append(os.path.relpath(src, data_dir))
        vrai_replace(src, dst)
    monkeypatch.setattr(data_edit.os, "replace", espion)
    v = lancer(data_dir, demande("image", "create", "eye/clin", base64.b64encode(OEIL).decode(), id_="img"))
    assert v["code"] == "ok"
    assert vus == ["medias/.tmp/img"]
    assert os.listdir(data_dir / "medias/.tmp") == []


def test_droits_du_fichier_remplace_conserves(data_dir):
    # robot_lights.json est suivi en 755 : une retouche ne doit pas le rendre 644 (vu en sim).
    cible = data_dir / "json/robot_lights.json"
    os.chmod(cible, 0o755)
    lancer(data_dir, demande("lumiere", "create", "neuve", LUMIERES["calme"]))
    assert oct(os.stat(cible).st_mode & 0o777) == "0o755"


def test_vider_tmp_des_deux_temporaires(data_dir):
    for relatif in ("json/backup/.tmp", "medias/.tmp"):
        (data_dir / relatif).mkdir(parents=True)
        (data_dir / relatif / "vieux").write_text("x")
    assert data_edit.vider_tmp(data_dir) == 2
