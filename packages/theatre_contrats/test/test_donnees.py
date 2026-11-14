"""Contrat des données (lot L1d, theatre_contrats.donnees) : une donnée fautive par règle,
message attendu GRAVÉ ; bornes roues à leur valeur limite ; PNG d'essai construits octet par
octet ; empreintes en littéral.

Les données réelles de data/ sont jugées par les tests de didier_core (test_sequences_json.py
& co.), qui appellent ce même module : ici, on prouve que chaque règle MORD.
"""
import json
import struct
import zlib

import pytest

from theatre_contrats import donnees


# ---------------------------------------------------------------- fabrique de PNG, octet par octet
def bloc(type_bloc, contenu, crc=None):
    crc = zlib.crc32(type_bloc + contenu) & 0xFFFFFFFF if crc is None else crc
    return struct.pack(">I", len(contenu)) + type_bloc + contenu + struct.pack(">I", crc)


def png(largeur, hauteur, profondeur=8, couleur=2, entrelace=0, lignes=None, crc_idat=None,
        fin=b""):
    ihdr = struct.pack(">IIBBBBB", largeur, hauteur, profondeur, couleur, 0, 0, entrelace)
    canaux = {2: 3, 6: 4}[couleur] * profondeur // 8
    if lignes is None:  # filtre 0 + pixels noirs
        lignes = b"".join(b"\x00" + b"\x00" * largeur * canaux for _ in range(hauteur))
    return (b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", ihdr)
            + bloc(b"IDAT", zlib.compress(lignes), crc_idat) + bloc(b"IEND", b"") + fin)


BOUCHE = png(24, 16)
SHA_ID3 = "041149186b23a9502aea5a4e81bbc9620d2b4b76b4bad94e36c744abcf9d3771"   # sha256(b"ID3")
SHA_ID4 = "b2b4bad68e70a07d669b404d0f2340089f19e8af24c66ec9179020174aa08103"   # sha256(b"ID4")
OEIL = png(8, 8)


# ---------------------------------------------------------------- un data_dir minimal
@pytest.fixture
def data_dir(tmp_path):
    (tmp_path / "json" / "sequences" / "essai").mkdir(parents=True)
    (tmp_path / "medias" / "audios").mkdir(parents=True)
    (tmp_path / "medias" / "audios" / "bonjour.mp3").write_bytes(b"ID3")
    # Audios privés (14/11) : un audio cité doit figurer au manifeste. « change.mp3 » y est
    # inscrit mais son fichier diffère (sha de b"ID4"), « parti.mp3 » inscrit sans fichier.
    (tmp_path / "medias" / "audios" / "change.mp3").write_bytes(b"ID3")
    ecrire(tmp_path, "json/audios-prives.json", {"version": 1, "audios": {
        "bonjour.mp3": {"sha256": SHA_ID3, "taille": 3, "duree_s": None},
        "change.mp3": {"sha256": SHA_ID4, "taille": 3, "duree_s": None},
        "parti.mp3": {"sha256": SHA_ID3, "taille": 3, "duree_s": None}}})
    for zone, octets in (("mouth", BOUCHE), ("eye", OEIL)):
        (tmp_path / "medias" / "visuals" / zone).mkdir(parents=True)
        (tmp_path / "medias" / "visuals" / zone / "neutre.png").write_bytes(octets)
    (tmp_path / "medias" / "visuals" / "mouth" / "petite.png").write_bytes(OEIL)
    ecrire(tmp_path, "json/expressions.json", {"joie": EXPRESSION})
    ecrire(tmp_path, "json/robot_lights.json", {"calme": LUMIERE})
    ecrire(tmp_path, "json/lights_base.json", {"bleu": BRIQUE, "rouge": BRIQUE})
    ecrire(tmp_path, "json/colors.json", {"BLUE": [0, 0, 255]})
    return tmp_path


def ecrire(racine, relatif, valeur):
    chemin = racine / relatif
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(valeur, indent=4))


EXPRESSION = {"duration": 2000, "loop": True, "mouths": [[1, "neutre.png"]],
              "left_eyes": [[1, "neutre.png"]], "right_eyes": []}
LUMIERE = {"duration": 1000, "loop": False, "keys": ["B1"], "sequences": {"bleu": 0.5, "rouge": 1}}
BRIQUE = {"method": "chase", "color": "BLUE", "speed": 0.1}
SEQUENCE = {"keys": "Z9", "duration": 4000, "neck": [[0, 0.5], [1, "up"]],
            "faces": [[0, "joie"]], "robot_lights": [[0, "calme"]], "audios": [[0, "bonjour.mp3"], [1, "stop"]],
            "wheels": [[0.1, [0.2, 0.2]], [0.5, [0, 0]]]}


@pytest.fixture
def refs(data_dir):
    return donnees.charger_references(data_dir)


def avec(base, **champs):
    resultat = dict(base)
    resultat.update(champs)
    return resultat


# ================================================================ noms
@pytest.mark.parametrize("kind, name, attendu", [
    ("sequence", "essai/bonjour", True),
    ("sequence", "essai/bon-jour_2", True),
    ("sequence", "bonjour", False),
    ("sequence", "essai/sous/bonjour", False),
    ("sequence", "../x/y", False),
    ("sequence", "essai/../../x", False),
    ("sequence", "Essai/bonjour", False),
    ("sequence", "essai/bon jour", False),
    ("sequence", "essai/bonjour\n", False),
    ("sequence", "essai/" + "a" * 64, True),
    ("sequence", "essai/" + "a" * 65, False),
    ("expression", "chase me", True),
    ("expression", " chase", False),
    ("expression", "chase/me", False),
    ("lumiere", "default dark", True),
    ("brique", "rainbow_comet", True),
    ("image", "mouth/sourire", True),
    ("image", "eye/sourire", True),
    ("image", "icons/sourire", False),
    ("image", "mouth/sourire.png", False),
    ("relais", "x", False),
    ("sequence", None, False),
])
def test_nom_valide(kind, name, attendu):
    assert donnees.nom_valide(kind, name) is attendu


def test_kinds_graves():
    assert donnees.KINDS == {
        "sequence": "json/sequences/<dossier>/<nom>.json",
        "expression": "json/expressions.json",
        "lumiere": "json/robot_lights.json",
        "brique": "json/lights_base.json",
        "image": "medias/visuals/<zone>/<nom>.png",
    }


# ================================================================ séquences
def test_sequence_conforme(refs):
    assert donnees.verifier_sequence(SEQUENCE, refs) == []


@pytest.mark.parametrize("sequence, erreurs", [
    ({**SEQUENCE, "keys": 3}, ["champ 'keys' (str) obligatoire"]),
    ({**SEQUENCE, "duration": 0}, ["champ 'duration' (ms > 0) obligatoire"]),
    ({**SEQUENCE, "neck": {"a": 1}}, ["piste neck : liste attendue"]),
    ({**SEQUENCE, "neck": [[0, 0.5, 1]]}, ["neck[0] : keyframe [t, valeur] attendu, reçu [0, 0.5, 1]"]),
    ({**SEQUENCE, "neck": [[1.5, 0.5]]}, ["neck[0] : temps hors [0,1] : 1.5"]),
    ({**SEQUENCE, "neck": [[0.5, 0.5], [0.2, 0.5]]}, ["neck[1] : keyframes non triés (t=0.2 après t=0.5)"]),
    ({**SEQUENCE, "neck": [[0, 1.2]]}, ["neck[0] : position servo hors [0,1] : 1.2"]),
    ({**SEQUENCE, "neck": [[0, "left"]]}, ["neck[0] : commande servo inconnue : 'left'"]),
    ({**SEQUENCE, "neck": [[0, {"vitesse": 1}]]}, ["neck[0] : valeur servo invalide : {'vitesse': 1}"]),
    ({**SEQUENCE, "faces": [[0, "triste"]]}, ["faces[0] : référence l'expression inconnue 'triste'"]),
    ({**SEQUENCE, "robot_lights": [[0, "fete"]]},
     ["robot_lights[0] : référence la séquence lumière inconnue 'fete'"]),
    ({**SEQUENCE, "audios": [[0, "bonjour.ogg"]]},
     ["audios[0] : 'bonjour.ogg' n'a pas la forme nom.mp3/nom.wav (ni la sentinelle 'stop')"]),
    ({**SEQUENCE, "audios": [[0, "absent.mp3"]]},
     ["audios[0] : fichier audio introuvable au manifeste json/audios-prives.json : absent.mp3"]),
    ({**SEQUENCE, "audios": [[0, "parti.mp3"]]},
     ["audios[0] : fichier audio introuvable : medias/audios/parti.mp3"]),
    ({**SEQUENCE, "audios": [[0, "change.mp3"]]},
     ["audios[0] : fichier audio introuvable tel qu'au manifeste (sha256 différent) : "
      "medias/audios/change.mp3"]),
])
def test_sequence_une_faute_par_regle(refs, sequence, erreurs):
    assert donnees.verifier_sequence(sequence, refs) == erreurs


def test_sequence_pas_un_objet(refs):
    assert donnees.verifier_sequence([], refs) == ["séquence : objet JSON attendu, reçu list"]


def test_sans_dossier_audios_seule_l_inscription_au_manifeste_est_jugee(data_dir, tmp_path):
    # Audios privés (14/11) : c'est le cas de la CI GitHub, sans le dossier privé. Un audio
    # inscrit passe (même sans fichier, même « changé ») ; un audio non inscrit reste une faute.
    refs = donnees.charger_references(data_dir, dossier_audios=tmp_path / "absent")
    assert refs["audios_verifiables"] is False
    for inscrit in ("bonjour.mp3", "parti.mp3", "change.mp3"):
        assert donnees.verifier_sequence({**SEQUENCE, "audios": [[0, inscrit]]}, refs) == []
    assert donnees.verifier_sequence({**SEQUENCE, "audios": [[0, "absent.mp3"]]}, refs) == [
        "audios[0] : fichier audio introuvable au manifeste json/audios-prives.json : absent.mp3"]


def test_sans_manifeste_tout_audio_cite_est_une_faute(data_dir):
    (data_dir / "json" / "audios-prives.json").unlink()
    refs = donnees.charger_references(data_dir)
    assert donnees.verifier_sequence({**SEQUENCE, "audios": [[0, "bonjour.mp3"]]}, refs) == [
        "audios[0] : fichier audio introuvable au manifeste json/audios-prives.json : bonjour.mp3"]


def test_dossier_audios_explicite(data_dir, tmp_path):
    # Les tests du dépôt jugent data/ avec le dossier PRIVÉ (hors data/) : c'est lui qui compte.
    prive = tmp_path / "prive"
    prive.mkdir()
    (prive / "parti.mp3").write_bytes(b"ID3")
    refs = donnees.charger_references(data_dir, dossier_audios=prive)
    assert donnees.verifier_sequence({**SEQUENCE, "audios": [[0, "parti.mp3"]]}, refs) == []
    assert donnees.verifier_sequence({**SEQUENCE, "audios": [[0, "bonjour.mp3"]]}, refs) == [
        "audios[0] : fichier audio introuvable : medias/audios/bonjour.mp3"]


def test_dossier_audios_prives_suit_la_variable(monkeypatch):
    monkeypatch.setenv("DIDIER_MEDIAS_PRIVES", "/srv/prives")
    assert donnees.dossier_audios_prives() == "/srv/prives/audios"
    monkeypatch.delenv("DIDIER_MEDIAS_PRIVES")
    assert donnees.dossier_audios_prives().endswith("/Nextcloud/dev/didier/medias-prives/audios")


# ---------------------------------------------------------------- bornes roues (décision 7)
def roues(wheels, duration=4000):
    return {"keys": "Z9", "duration": duration, "wheels": wheels}


def test_bornes_roues_gravees():
    assert (donnees.VITESSE_ROUES_MAX, donnees.TENUE_ROUES_MAX_MS, donnees.DUREE_ROUES_MAX_MS) == (
        0.89, 60_000, 300_000)


@pytest.mark.parametrize("consigne", [[0.89, -0.89], [-0.89, 0.0]])
def test_consigne_a_la_limite_passe(refs, consigne):
    assert donnees.verifier_sequence(roues([[0, consigne], [0.5, [0, 0]]]), refs) == []


def test_consigne_au_dela_refusee(refs):
    assert donnees.verifier_sequence(roues([[0, [0.9, 0.2]], [0.5, [0, 0]]]), refs) == [
        "wheels[0] : consigne roues [0.9, 0.2] au-delà de 0.89 (VITESSE_ROUES_MAX)"]


def test_consigne_095_refusee(refs):
    # Épreuve 6 de validate-data-edit.sh : même message.
    assert donnees.verifier_sequence(roues([[0.1, [0.95, 0.95]], [0.5, [0, 0]]]), refs) == [
        "wheels[0] : consigne roues [0.95, 0.95] au-delà de 0.89 (VITESSE_ROUES_MAX)"]


@pytest.mark.parametrize("valeur", ["forward", {"speed": 100}, [0.2], [0.2, "0.2"], [True, 0],
                                    [float("nan"), 0], [float("inf"), 0]])
def test_forme_roues_refusee(refs, valeur):
    erreurs = donnees.verifier_sequence(roues([[0.1, valeur], [0.5, [0, 0]]]), refs)
    assert erreurs == ["wheels[0] : consigne roues [gauche, droite] (deux nombres) attendue, "
                       "reçu {!r}".format(valeur)]


def test_arret_final_exige(refs):
    assert donnees.verifier_sequence(roues([[0.1, [0.2, 0.2]]]), refs) == [
        "wheels : la dernière image doit valoir [0, 0] (arrêt final), reçu [0.1, [0.2, 0.2]]"]


def test_arret_final_a_nimporte_quelle_fraction(refs):
    assert donnees.verifier_sequence(roues([[0.1, [0.2, 0.2]], [0.75, [0, 0]]]), refs) == []
    assert donnees.verifier_sequence(roues([[1, [0.2, 0.2]], [1, [0.0, 0.0]]]), refs) == []


def test_tenue_a_la_limite_passe(refs):
    # 0,5 × 120 000 ms = 60 000 ms tout juste.
    assert donnees.verifier_sequence(roues([[0, [0.2, 0.2]], [0.5, [0, 0]]], 120_000), refs) == []


def test_tenue_au_dela_refusee(refs):
    # (0,5 − 0) × 120 002 = 60 001 ms.
    assert donnees.verifier_sequence(roues([[0, [0.2, 0.2]], [0.5, [0, 0]]], 120_002), refs) == [
        "wheels[0] : consigne [0.2, 0.2] tenue 60001 ms, au-delà de 60000 ms (TENUE_ROUES_MAX_MS)"]


def test_tenue_de_la_derniere_image_court_jusqua_1(refs):
    # La dernière image non nulle compte jusqu'à 1 (l'arrêt final est AUSSI exigé).
    erreurs = donnees.verifier_sequence(roues([[0, [0, 0]], [0.5, [0.2, 0.2]]], 120_002), refs)
    assert "wheels[1] : consigne [0.2, 0.2] tenue 60001 ms, au-delà de 60000 ms (TENUE_ROUES_MAX_MS)" in erreurs


def test_image_nulle_peut_durer(refs):
    assert donnees.verifier_sequence(roues([[0, [0, 0]], [1, [0, 0]]], 300_000), refs) == []


def test_duree_a_la_limite_passe(refs):
    assert donnees.verifier_sequence(roues([[0.9, [0.1, 0.1]], [1, [0, 0]]], 300_000), refs) == []


def test_duree_au_dela_refusee(refs):
    assert donnees.verifier_sequence(roues([[0.9, [0.1, 0.1]], [1, [0, 0]]], 300_001), refs) == [
        "wheels : duration 300001 ms au-delà de 300000 ms (DUREE_ROUES_MAX_MS)"]


def test_duree_sans_roues_non_bornee(refs):
    assert donnees.verifier_sequence({"keys": "Z9", "duration": 600_000, "wheels": []}, refs) == []


# ================================================================ expressions
def test_expression_conforme(refs):
    assert donnees.verifier_expression("joie", EXPRESSION, refs) == []


@pytest.mark.parametrize("expression, erreurs", [
    (avec(EXPRESSION, name="autre"), ["joie : champ name 'autre' != clé 'joie'"]),
    (avec(EXPRESSION, duration=-1), ["joie : champ 'duration' (nombre > 0) obligatoire"]),
    (avec(EXPRESSION, loop=1), ["joie : champ 'loop' (bool) obligatoire"]),
    ({k: v for k, v in EXPRESSION.items() if k != "right_eyes"}, ["joie : piste 'right_eyes' obligatoire"]),
    (avec(EXPRESSION, mouths="neutre.png"), ["joie : piste mouths : liste attendue"]),
    (avec(EXPRESSION, mouths=[["neutre.png"]]),
     ["joie : mouths[0] : keyframe [t, fichier] attendu, reçu ['neutre.png']"]),
    (avec(EXPRESSION, mouths=[[2, "neutre.png"]]), ["joie : mouths[0] : temps hors [0,1] : 2"]),
    (avec(EXPRESSION, mouths=[[0.5, "neutre.png"], [0.1, "neutre.png"]]),
     ["joie : mouths[1] : keyframes non triés (t=0.1 après t=0.5)"]),
    (avec(EXPRESSION, mouths=[[1, 7]]), ["joie : mouths[0] : nom de fichier attendu, reçu 7"]),
    (avec(EXPRESSION, mouths=[[1, "../eye/neutre.png"]]),
     ["joie : mouths[0] : nom de fichier attendu, reçu '../eye/neutre.png'"]),
    (avec(EXPRESSION, mouths=[[1, "absente.png"]]),
     ["joie : mouths[0] : visuel introuvable : medias/visuals/mouth/absente.png"]),
    (avec(EXPRESSION, mouths=[[1, "petite.png"]]),
     ["joie : mouths[0] : petite.png fait 8x8, attendu 24x16 (ImageMapping refuserait ce visuel en silence)"]),
])
def test_expression_une_faute_par_regle(refs, expression, erreurs):
    assert donnees.verifier_expression("joie", expression, refs) == erreurs


def test_expression_oeil_a_la_taille_de_la_bouche_refuse(data_dir, refs):
    (data_dir / "medias" / "visuals" / "eye" / "large.png").write_bytes(BOUCHE)
    assert donnees.verifier_expression("joie", avec(EXPRESSION, left_eyes=[[1, "large.png"]]), refs) == [
        "joie : left_eyes[0] : large.png fait 24x16, attendu 8x8 (ImageMapping refuserait ce visuel en silence)"]


# ================================================================ lumières et briques
def test_lumiere_conforme(refs):
    assert donnees.verifier_lumiere("calme", LUMIERE, refs) == []
    assert donnees.verifier_lumiere("calme", avec(LUMIERE, keys="None"), refs) == []


@pytest.mark.parametrize("lumiere, erreurs", [
    (avec(LUMIERE, duration=0), ["séquence lumière 'calme' : champ 'duration' (nombre > 0) obligatoire"]),
    (avec(LUMIERE, loop="non"), ["séquence lumière 'calme' : champ 'loop' (bool) obligatoire"]),
    (avec(LUMIERE, keys="B1"), ["séquence lumière 'calme' : 'keys' = liste de chaînes ou \"None\", reçu 'B1'"]),
    (avec(LUMIERE, keys=[1]), ["séquence lumière 'calme' : 'keys' = liste de chaînes ou \"None\", reçu [1]"]),
    (avec(LUMIERE, sequences=[["bleu", 1]]),
     ["séquence lumière 'calme' : champ 'sequences' (dict {brique: t}) obligatoire"]),
    (avec(LUMIERE, sequences={"vert": 1}),
     ["séquence lumière 'calme' -> brique 'vert' : brique inconnue de json/lights_base.json"]),
    (avec(LUMIERE, sequences={"bleu": 2}), ["séquence lumière 'calme' -> brique 'bleu' : t hors [0,1] : 2"]),
    (avec(LUMIERE, sequences={"bleu": 0.8, "rouge": 0.2}),
     ["séquence lumière 'calme' -> brique 'rouge' : briques non triées (t=0.2 après t=0.8)"]),
])
def test_lumiere_une_faute_par_regle(refs, lumiere, erreurs):
    assert donnees.verifier_lumiere("calme", lumiere, refs) == erreurs


def test_brique_conforme(refs):
    assert donnees.verifier_brique("bleu", BRIQUE, refs) == []
    assert donnees.verifier_brique("arc", {"method": "rainbow"}, refs) == []


@pytest.mark.parametrize("brique, erreurs", [
    ({"color": "BLUE"}, ["brique 'bleu' : champ 'method' obligatoire"]),
    ({"method": 3}, ["brique 'bleu' : 'method' doit être une chaîne"]),
    ({"method": "colorcycle"}, ["brique 'bleu' : méthode 'colorcycle' absente de LightsAnimations"]),
    ({"method": "chase", "color": "VERT"}, ["brique 'bleu' : couleur 'VERT' absente de json/colors.json"]),
    ({"method": "chase", "speed": "vite"}, ["brique 'bleu' : champ 'speed' : nombre attendu, reçu 'vite'"]),
])
def test_brique_une_faute_par_regle(refs, brique, erreurs):
    assert donnees.verifier_brique("bleu", brique, refs) == erreurs


def test_methodes_lumiere_gravees():
    # L'égalité avec LightsAnimations est gravée côté didier_core (test_lights_json.py).
    assert donnees.METHODES_LUMIERE == (
        "blink", "chase", "color_cycle", "comet", "default", "fade_red", "pulse", "rainbow",
        "rainbow_chase", "rainbow_comet", "rainbow_sparkle", "random", "solid", "sparkle",
        "sparkle_pulse")


# ================================================================ images
def test_images_conformes():
    assert donnees.verifier_image("mouth", BOUCHE) == []
    assert donnees.verifier_image("eye", OEIL) == []


@pytest.mark.parametrize("zone, octets, erreurs", [
    ("icons", BOUCHE, ["image : zone inconnue 'icons' (attendu : mouth, eye)"]),
    ("mouth", OEIL, ["image : 8x8, attendu 24x16 pour la zone mouth"]),
    ("eye", BOUCHE, ["image : 24x16, attendu 8x8 pour la zone eye"]),
    ("mouth", b"GIF89a" + b"\x00" * 40, ["image : signature PNG absente"]),
    ("mouth", BOUCHE + b"\x00" * 16_384, ["image : 16459 octets, au-delà de 16384 (TAILLE_IMAGE_MAX)"]),
    ("mouth", png(24, 16, crc_idat=0), ["image : CRC faux sur le bloc 'IDAT'"]),
    ("mouth", png(24, 16, profondeur=16), ["image : RVB 8 bits attendu (profondeur 16, type de couleur 2)"]),
    ("mouth", png(24, 16, couleur=6), ["image : RVB 8 bits attendu (profondeur 8, type de couleur 6)"]),
    ("mouth", png(24, 16, entrelace=1), ["image : PNG entrelacé refusé"]),
    ("mouth", png(24, 16, lignes=b"\x00" * 100), ["image : données IDAT de 100 octets, attendu 1168"]),
    ("mouth", png(24, 16, lignes=b"\x00" * 2000), ["image : données IDAT de 1169 octets ou plus, attendu 1168"]),
    ("mouth", png(24, 16, fin=b"\x00"), ["image : octets après IEND"]),
    ("mouth", BOUCHE[:-12], ["image : bloc IEND final absent"]),
    ("mouth", BOUCHE[:40], ["image : bloc tronqué à l'octet 33"]),
    ("mouth", BOUCHE[:50], ["image : bloc 'IDAT' tronqué"]),
])
def test_image_une_faute_par_regle(zone, octets, erreurs):
    assert donnees.verifier_image(zone, octets) == erreurs


def test_taille_png():
    assert donnees.taille_png(BOUCHE) == (24, 16)
    assert donnees.taille_png(b"pas un png") is None


# ================================================================ outils de l'écrivain
def test_json_canonique_et_sha_entree():
    assert donnees.json_canonique({"b": 1, "a": "é"}) == '{"a":"é","b":1}'
    # sha256 de '{"method":"chase"}' (UTF-8), en littéral (calculé par hashlib, hors module).
    assert donnees.sha256_entree({"method": "chase"}) == \
        "0ca81ee32e505affa64d6bf9b8ea8595d210d8b14f8006af867148e780090074"


def test_serialiser_garde_l_ordre_des_cles():
    assert donnees.serialiser({"b": 1, "a": "é"}) == '{\n    "b": 1,\n    "a": "é"\n}\n'.encode("utf-8")


def test_poser_entree_garde_l_ordre_et_ne_mute_pas():
    fichier = {"a": 1, "b": 2, "c": 3}
    assert list(donnees.poser_entree(fichier, "b", 9).items()) == [("a", 1), ("b", 9), ("c", 3)]
    assert list(donnees.poser_entree(fichier, "z", 0).items()) == [("a", 1), ("b", 2), ("c", 3), ("z", 0)]
    assert fichier == {"a": 1, "b": 2, "c": 3}


# ================================================================ empreintes et registre
def test_empreinte_roues_en_litteral():
    # sha256 (hashlib, hors module) du JSON canonique en float :
    # {"duration":4000.0,"wheels":[[0.1,[0.2,0.2]],[0.5,[0.0,0.0]]]}
    attendu = "ebba32b0d20bf3cb34fcc1efd3a1076d716e60b27ef2d88f0b6daa1a8108642b"
    assert donnees.empreinte_roues(roues([[0.1, [0.2, 0.2]], [0.5, [0, 0]]])) == attendu
    # Entiers et flottants : même empreinte (une remise en forme à la main ne périme rien).
    assert donnees.empreinte_roues(roues([[0.1, [0.2, 0.2]], [0.5, [0.0, 0.0]]], 4000.0)) == attendu


def test_empreinte_roues_none_sans_piste():
    assert donnees.empreinte_roues({"keys": "a", "duration": 1, "wheels": []}) is None
    assert donnees.empreinte_roues({"keys": "a", "duration": 1}) is None


def test_empreintes_de_contenu_en_litteral(data_dir):
    ecrire(data_dir, "json/sequences/essai/bonjour.json", SEQUENCE)
    assert donnees.empreinte_contenu("sequence", "essai/bonjour", data_dir) == \
        "73058751170d38c8462438b879d9b5007cc2641a5ea7101956ebba1ba0f11e5c"
    assert donnees.empreinte_contenu("expression", "joie", data_dir) == \
        "518ebd2647b300c7e21ccf72bfdd9bf03939116b0daa7582b32fab1c3b7c94aa"
    assert donnees.empreinte_contenu("lumiere", "calme", data_dir) == \
        "8f748808592a7c7dbb7438d95f898d0d2611df382daed7c7cb93e836d150b8d2"
    assert donnees.empreinte_contenu("sequence", "essai/absente", data_dir) is None
    assert donnees.empreinte_contenu("expression", "absente", data_dir) is None


def test_image_retouchee_perime_l_expression_qui_la_montre(data_dir):
    avant = donnees.empreinte_contenu("expression", "joie", data_dir)
    rouge = b"\x00" + b"\x01" * 72 + b"\x00" * 73 * 15
    (data_dir / "medias" / "visuals" / "mouth" / "neutre.png").write_bytes(png(24, 16, lignes=rouge))
    assert donnees.empreinte_contenu("expression", "joie", data_dir) != avant


def test_brique_retouchee_perime_la_lumiere_qui_l_enchaine(data_dir):
    avant = donnees.empreinte_contenu("lumiere", "calme", data_dir)
    ecrire(data_dir, "json/lights_base.json", {"bleu": {"method": "blink"}, "rouge": BRIQUE})
    assert donnees.empreinte_contenu("lumiere", "calme", data_dir) != avant


def test_registre_absent_tout_est_a_faire(data_dir):
    ecrire(data_dir, "json/sequences/essai/bonjour.json", SEQUENCE)
    assert donnees.lire_registre(data_dir) == {"version": 1, "sequence": {}, "expression": {}, "lumiere": {}}
    assert donnees.a_rejouer(data_dir) == [
        ("expression", "joie"), ("lumiere", "calme"), ("sequence", "essai/bonjour")]
    assert donnees.roues_a_valider(data_dir) == ["essai/bonjour"]


def test_registre_a_jour_rien_a_faire(data_dir):
    ecrire(data_dir, "json/sequences/essai/bonjour.json", SEQUENCE)
    registre = {"version": 1, "sequence": {"essai/bonjour": {
        "rejeu": donnees.empreinte_contenu("sequence", "essai/bonjour", data_dir),
        "roues": donnees.empreinte_roues(SEQUENCE), "origine_roues": "sim"}},
        "expression": {"joie": {"rejeu": donnees.empreinte_contenu("expression", "joie", data_dir)}},
        "lumiere": {"calme": {"rejeu": donnees.empreinte_contenu("lumiere", "calme", data_dir)}}}
    ecrire(data_dir, "json/validations-sim.json", registre)
    assert donnees.a_rejouer(data_dir) == []
    assert donnees.roues_a_valider(data_dir) == []
    assert donnees.roues_validees(registre, "essai/bonjour", SEQUENCE) is True
    retouche = {**SEQUENCE, "wheels": [[0.1, [0.3, 0.3]], [0.5, [0, 0]]]}
    assert donnees.roues_validees(registre, "essai/bonjour", retouche) is False
    # Un homonyme dans un autre dossier n'hérite pas de la validation.
    assert donnees.roues_validees(registre, "autre/bonjour", SEQUENCE) is False
    assert donnees.roues_validees({}, "autre/bonjour", {"keys": "a", "duration": 1}) is True


def test_serialisation_du_registre_gravee():
    # indent=1, clés triées, accents en clair, saut de ligne final : GRAVÉ octet par octet.
    registre = {"version": 1, "sequence": {"b/z": {"rejeu": "r", "roues": None}},
                "lumiere": {"été": {"rejeu": "x"}}, "expression": {}}
    assert donnees.serialiser_registre(registre) == (
        b'{\n "expression": {},\n "lumiere": {\n  "\xc3\xa9t\xc3\xa9": {\n   "rejeu": "x"\n  }\n },\n'
        b' "sequence": {\n  "b/z": {\n   "rejeu": "r",\n   "roues": null\n  }\n },\n "version": 1\n}\n')


def test_orphelines(data_dir):
    ecrire(data_dir, "json/sequences/essai/bonjour.json", SEQUENCE)
    registre = {"version": 1, "sequence": {"essai/bonjour": {}, "essai/effacee": {"rejeu": "x"}},
                "expression": {"joie": {}, "partie": {}}, "lumiere": {}}
    assert donnees.orphelines(data_dir, registre) == [("expression", "partie"), ("sequence", "essai/effacee")]


def test_non_validees_et_ligne_de_commande(data_dir, capsys):
    ecrire(data_dir, "json/sequences/essai/bonjour.json", SEQUENCE)
    attendu = ["à rejouer en sim : expression joie", "à rejouer en sim : lumiere calme",
               "à rejouer en sim : sequence essai/bonjour", "roues à valider en sim : sequence essai/bonjour"]
    assert donnees.non_validees(data_dir) == attendu
    assert donnees.main(["non-validees", str(data_dir)]) == 1
    assert capsys.readouterr().out == "\n".join(attendu) + "\n4 élément(s) non validé(s) en sim\n"
    registre = {"version": 1, "sequence": {"essai/bonjour": {
        "rejeu": donnees.empreinte_contenu("sequence", "essai/bonjour", data_dir),
        "roues": donnees.empreinte_roues(SEQUENCE), "origine_roues": "heritee"}},
        "expression": {"joie": {"rejeu": donnees.empreinte_contenu("expression", "joie", data_dir)}},
        "lumiere": {"calme": {"rejeu": donnees.empreinte_contenu("lumiere", "calme", data_dir)}}}
    ecrire(data_dir, "json/validations-sim.json", registre)
    assert donnees.main(["non-validees", str(data_dir)]) == 0
    assert capsys.readouterr().out == "0 élément(s) non validé(s) en sim\n"
    assert donnees.main(["autre-chose", str(data_dir)]) == 2


# ================================================================ audios privés (manifeste)
def wav_d_une_seconde(chemin):
    import wave
    with wave.open(str(chemin), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(8000)
        w.writeframes(b"\x80" * 8000)


@pytest.fixture
def prive(tmp_path):
    """Un dossier privé : un mp3, un wav d'une seconde dans un dossier caché, un non-audio."""
    racine = tmp_path / "prive"
    (racine / "speak" / ".attachments").mkdir(parents=True)
    (racine / "bonjour.mp3").write_bytes(b"ID3")
    wav_d_une_seconde(racine / "speak" / ".attachments" / "aie.wav")
    (racine / "speak" / "Readme.md").write_text("pas un audio")
    return racine


SHA_WAV = "dd9165ab3909873fc83f23fb627ce58f8ad2623d8847dbfcecb8df034ac46131"   # sha256sum du wav ci-dessus


def test_manifeste_construit_depuis_le_dossier(prive):
    assert donnees.lister_audios(prive) == ["bonjour.mp3", "speak/.attachments/aie.wav"]
    assert donnees.construire_manifeste(prive) == {"version": 1, "audios": {
        "bonjour.mp3": {"sha256": SHA_ID3, "taille": 3, "duree_s": None},
        "speak/.attachments/aie.wav": {"sha256": SHA_WAV, "taille": 8044, "duree_s": 1.0}}}


def test_duree_wav_illisible():
    assert donnees.duree_wav("/nulle/part.wav") is None


def test_ecarts_audios():
    manifeste = {"a.mp3": {"sha256": SHA_ID3}, "b.mp3": {"sha256": SHA_ID3}, "c.mp3": {"sha256": SHA_ID3}}
    sommes = {"a.mp3": SHA_ID3, "b.mp3": SHA_ID4, "d.mp3": SHA_ID3}
    assert donnees.ecarts_audios(manifeste, sommes) == (
        ["audio différent du manifeste (sha256) : b.mp3", "audio absent : c.mp3"], ["d.mp3"])


def test_lire_sommes():
    texte = "{}  ./song/a b.mp3\n{}  c.wav\n\n".format(SHA_ID3, SHA_ID4)
    assert donnees.lire_sommes(texte) == {"song/a b.mp3": SHA_ID3, "c.wav": SHA_ID4}
    for illisible in ("\\{}  ./a\\nb.mp3".format(SHA_ID3), "pas-un-sha  ./a.mp3", SHA_ID3):
        with pytest.raises(ValueError):
            donnees.lire_sommes(illisible)


def test_lignes_de_commande_des_audios(data_dir, prive, capsys, monkeypatch):
    # manifeste-audios écrit json/audios-prives.json au format gravé (indent=1, clés triées).
    assert donnees.main(["manifeste-audios", str(data_dir), str(prive)]) == 0
    assert capsys.readouterr().out == "2 audio(s) au manifeste json/audios-prives.json\n"
    octets = (data_dir / "json" / "audios-prives.json").read_bytes()
    assert octets.startswith(b'{\n "audios": {\n  "bonjour.mp3": {\n   "duree_s": null,\n')
    assert octets == donnees.serialiser_manifeste(donnees.construire_manifeste(prive))
    # verifier-audios : conforme, puis un fichier hors manifeste et un fichier changé.
    assert donnees.main(["verifier-audios", str(data_dir), str(prive)]) == 0
    capsys.readouterr()
    (prive / "nouveau.mp3").write_bytes(b"ID3")
    (prive / "bonjour.mp3").write_bytes(b"ID4")
    assert donnees.main(["verifier-audios", str(data_dir), str(prive)]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "audio différent du manifeste (sha256) : bonjour.mp3",
        "hors manifeste (régénérer : manifeste-audios) : nouveau.mp3",
        "{} : 2 faute(s), 0 fichier(s) hors manifeste".format(prive)]
    assert donnees.main(["verifier-audios", str(data_dir), str(prive / "absent")]) == 1
    assert capsys.readouterr().err == "dossier des audios absent : {}\n".format(prive / "absent")
    # verifier-sommes : la sortie sha256sum d'un Pi sur stdin ; hors manifeste = signalé seulement.
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("{}  ./bonjour.mp3\n{}  ./speak/.attachments/aie.wav\n"
                                                 "{}  ./vieux.mp3\n".format(SHA_ID3, SHA_WAV, SHA_ID4)))
    assert donnees.main(["verifier-sommes", str(data_dir)]) == 0
    sortie = capsys.readouterr()
    assert sortie.out == "audios reçus : 0 faute(s), 1 fichier(s) hors manifeste\n"
    assert sortie.err == "en trop (hors manifeste) : vieux.mp3\n"
    monkeypatch.setattr("sys.stdin", io.StringIO("{}  ./bonjour.mp3\n".format(SHA_ID4)))
    assert donnees.main(["verifier-sommes", str(data_dir)]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "audio différent du manifeste (sha256) : bonjour.mp3", "audio absent : speak/.attachments/aie.wav",
        "audios reçus : 2 faute(s), 0 fichier(s) hors manifeste"]
    assert donnees.main(["verifier-sommes"]) == 2


# ================================================================ rechargement à chaud
@pytest.mark.parametrize("brut, attendu", [
    ('{"ok": true, "kind": "sequence", "name": "essai/bonjour"}', ("sequence", "essai/bonjour")),
    ('{"ok": true, "kind": "image", "name": "mouth/sourire"}', None),
    ('{"ok": false, "kind": "sequence", "name": "essai/bonjour"}', None),
    ('{"ok": "true", "kind": "sequence", "name": "essai/bonjour"}', None),
    ('{"ok": true, "kind": "sequence", "name": "../../etc/passwd"}', None),
    ('pas du json', None),
    ('[1]', None),
])
def test_verdict_a_recharger(brut, attendu):
    assert donnees.verdict_a_recharger(brut, ("sequence",)) == attendu
