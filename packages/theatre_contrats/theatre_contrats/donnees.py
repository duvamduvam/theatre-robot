"""Contrat des DONNÉES du robot (lot L1d, 12/11) : un seul juge pour ce qui entre dans `data/`.

Avant L1d, les contrats de séquence, d'expression et de lumière n'existaient que dans quatre
tests de didier_core : « valider avec les mêmes contrats que les tests » exigeait de les
EXTRAIRE ici, pas de les recopier. Ce module est lu par les tests de `data/` (donc par ce
qui arrive par git), par l'écrivain du robot (`didier_web.data_edit`) et, demain, par le
rapatriement et la télécommande. Spec : docs/spec-L1-contrats-donnees.md, « L1d —
conception détaillée », décisions 3, 4, 7 et 7 bis.

Python PUR, stdlib seulement (ni imageio, ni didier_core, ni ROS) : la taille d'une image se
lit dans l'en-tête PNG. Chaque `verifier_*` rend TOUTES les erreurs trouvées (liste vide =
conforme) ; il ne lève jamais sur une donnée fautive.

`data_dir` désigne partout la racine des données, celle qui porte `json/` et `medias/`
(`data/` du dépôt, `/home/ros2_ws/src/robot` dans les conteneurs).
"""
import hashlib
import json
import math
import os
import re
import struct
import zlib

# ---------------------------------------------------------------- familles éditables (décision 3)
# kind -> cible, relative à data_dir. Hors liste : relais, audios, colors.json, visuals.json,
# playlists. Pas de suppression, pas de renommage, pas de création de dossier.
KINDS = {
    "sequence": "json/sequences/<dossier>/<nom>.json",
    "expression": "json/expressions.json",
    "lumiere": "json/robot_lights.json",
    "brique": "json/lights_base.json",
    "image": "medias/visuals/<zone>/<nom>.png",
}
# Les trois familles qui sont des ENTRÉES d'un fichier à plusieurs entrées.
FICHIERS_A_ENTREES = {
    "expression": "json/expressions.json",
    "lumiere": "json/robot_lights.json",
    "brique": "json/lights_base.json",
}
DOSSIER_SEQUENCES = "json/sequences"
DOSSIER_VISUELS = "medias/visuals"
DOSSIER_AUDIOS = "medias/audios"
FICHIER_COULEURS = "json/colors.json"

# Noms (décision 3) : l'espace est en usage dans les noms d'entrées (« chase me »), pas
# dans les noms de fichiers. Comparés par re.fullmatch (un « $ » laisserait passer un \n final).
MOTIF_NOM_ENTREE = r"[a-z0-9][a-z0-9 _-]{0,63}"
MOTIF_NOM_FICHIER = r"[a-z0-9][a-z0-9_-]{0,63}"

# ---------------------------------------------------------------- séquences
PISTES_SERVOS = ("neck", "left_arm", "right_arm", "left_eye", "right_eye")
AUTRES_PISTES = ("audios", "faces", "wheels", "robot_lights")
COMMANDES_SERVO = ("up", "down", "stop")
# Sentinelle de commande audio (utils_static.STOP) : AudioManager.update() l'intercepte
# avant toute lecture de fichier, ce n'est pas un nom de fichier.
COMMANDE_AUDIO_STOP = "stop"
MOTIF_FICHIER_AUDIO = re.compile(r".+\.(mp3|wav)$", re.IGNORECASE)

# Bornes roues (décision 7, faits relevés le 12/11 au soir). Les consignes sont SANS unité :
# ces bornes disent « pas plus que ce qui a déjà été écrit », pas « sûr en m/s ». Elles
# n'autorisent aucun roulage au sol (verrou refonte électrique + protocole caméra).
VITESSE_ROUES_MAX = 0.89        # plus forte consigne relevée (eternel-show/seq1) ; 54 % de PWM
TENUE_ROUES_MAX_MS = 60_000     # plus longue tenue relevée : 55,8 s (trip)
DUREE_ROUES_MAX_MS = 300_000    # plus longue séquence à roues relevée (appel-eternel-life2)

# ---------------------------------------------------------------- expressions et images
# (largeur, hauteur) : bouche 24x16 (MOUTH_WIDTH/HEIGHT d'image_mapping.py), œil 8x8 (MATRIX).
ZONES_IMAGE = {"mouth": (24, 16), "eye": (8, 8)}
PISTES_VISAGE = {"mouths": "mouth", "left_eyes": "eye", "right_eyes": "eye"}
TAILLE_IMAGE_MAX = 16_384       # max relevé 12 460 octets
SIGNATURE_PNG = b"\x89PNG\r\n\x1a\n"

# ---------------------------------------------------------------- lumières
# Méthodes de brique de LightsAnimations (celles qui prennent `params`) : un test de
# didier_core grave l'égalité avec la classe (elle importe adafruit à la construction,
# ce module ne peut pas l'importer). lights_methods.json ne peut PAS servir de référence :
# ses noms (colorcycle) ne sont pas ceux des briques (color_cycle).
METHODES_LUMIERE = (
    "blink", "chase", "color_cycle", "comet", "default", "fade_red", "pulse", "rainbow",
    "rainbow_chase", "rainbow_comet", "rainbow_sparkle", "random", "solid", "sparkle",
    "sparkle_pulse",
)

# ---------------------------------------------------------------- registre des validations sim
FICHIER_REGISTRE = "json/validations-sim.json"
VERSION_REGISTRE = 1
FAMILLES_REJOUEES = ("sequence", "expression", "lumiere")


# ================================================================ outils
def est_nombre(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def est_nombre_fini(v):
    return est_nombre(v) and math.isfinite(v)


def json_canonique(valeur):
    """La forme canonique de L1d, partout (sha, comparaisons) : clés triées, sans espaces."""
    return json.dumps(valeur, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_octets(octets):
    return hashlib.sha256(octets).hexdigest()


def sha256_entree(entree):
    """sha256 du JSON canonique d'une entrée (expression, lumière, brique) : c'est ce que
    l'éditeur charge et rend en `base_sha256` — deux retouches d'entrées différentes du
    même fichier ne se gênent pas."""
    return sha256_octets(json_canonique(entree).encode("utf-8"))


def serialiser(contenu):
    """Octets écrits sur disque pour un fichier JSON (décision 8 c) : ordre des clés conservé."""
    return (json.dumps(contenu, indent=4, ensure_ascii=False) + "\n").encode("utf-8")


def poser_entree(fichier, nom, entree):
    """Nouveau dict : `entree` posée sous `nom` ; ordre des autres entrées conservé, une
    entrée neuve va en fin. Le dict reçu n'est pas modifié."""
    resultat = dict(fichier)
    resultat[nom] = entree
    return resultat


def nom_valide(kind, name):
    """Forme du nom propre à chaque kind (décision 3). Ne regarde pas le disque."""
    if not isinstance(name, str):
        return False
    if kind in FICHIERS_A_ENTREES:
        return re.fullmatch(MOTIF_NOM_ENTREE, name) is not None
    if kind in ("sequence", "image"):
        morceaux = name.split("/")
        if len(morceaux) != 2:
            return False
        tete, nom = morceaux
        if kind == "image" and tete not in ZONES_IMAGE:
            return False
        return all(re.fullmatch(MOTIF_NOM_FICHIER, m) is not None for m in (tete, nom))
    return False


def _lire_json(chemin, defaut):
    if not os.path.isfile(chemin):
        return defaut
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def charger_references(data_dir):
    """Ce que les contrats consultent : les fichiers référencés et les dossiers d'assets.

    Fichier absent = dict vide (toute référence vers lui sera une faute) ; fichier
    illisible = l'exception de json.load remonte (c'est le robot qui est cassé, pas la
    donnée examinée). `audios_verifiables` est faux si medias/audios/ n'existe pas : seul
    le format du nom est alors vérifié (même tolérance que l'ancien test).
    """
    d = str(data_dir)
    return {
        "data_dir": d,
        "expressions": _lire_json(os.path.join(d, FICHIERS_A_ENTREES["expression"]), {}),
        "robot_lights": _lire_json(os.path.join(d, FICHIERS_A_ENTREES["lumiere"]), {}),
        "lights_base": _lire_json(os.path.join(d, FICHIERS_A_ENTREES["brique"]), {}),
        "colors": _lire_json(os.path.join(d, FICHIER_COULEURS), {}),
        "audios_verifiables": os.path.isdir(os.path.join(d, DOSSIER_AUDIOS)),
    }


def _verifier_temps(ou, keyframe, precedent, erreurs):
    """Règle commune des pistes : [t, valeur], t nombre dans [0, 1], croissant au sens large.
    Rend le nouveau t précédent (inchangé si le keyframe est inexploitable)."""
    t = keyframe[0]
    if not (est_nombre(t) and 0 <= t <= 1):
        erreurs.append("{} : temps hors [0,1] : {!r}".format(ou, t))
        return precedent
    if t < precedent:
        erreurs.append("{} : keyframes non triés (t={} après t={})".format(ou, t, precedent))
    return t


def _est_keyframe(keyframe):
    return isinstance(keyframe, list) and len(keyframe) == 2


# ================================================================ séquences
def verifier_sequence(sequence, references):
    """Contrat d'une séquence (anciens test_sequences_json.py + test_sequences_assets.py)
    plus les bornes roues de la décision 7 — le seul durcissement."""
    if not isinstance(sequence, dict):
        return ["séquence : objet JSON attendu, reçu {}".format(type(sequence).__name__)]
    erreurs = []
    if not isinstance(sequence.get("keys"), str):
        erreurs.append("champ 'keys' (str) obligatoire")
    duree = sequence.get("duration")
    duree_ok = est_nombre(duree) and duree > 0
    if not duree_ok:
        erreurs.append("champ 'duration' (ms > 0) obligatoire")

    for piste in PISTES_SERVOS + AUTRES_PISTES:
        if piste not in sequence:
            continue
        valeurs = sequence[piste]
        if not isinstance(valeurs, list):
            erreurs.append("piste {} : liste attendue".format(piste))
            continue
        precedent = -1
        for i, keyframe in enumerate(valeurs):
            ou = "{}[{}]".format(piste, i)
            if not _est_keyframe(keyframe):
                erreurs.append("{} : keyframe [t, valeur] attendu, reçu {!r}".format(ou, keyframe))
                continue
            precedent = _verifier_temps(ou, keyframe, precedent, erreurs)
            _verifier_valeur(piste, ou, keyframe[1], references, erreurs)
        if piste == "wheels":
            _verifier_bornes_roues(valeurs, duree if duree_ok else None, erreurs)
    return erreurs


def _verifier_valeur(piste, ou, valeur, references, erreurs):
    if piste in PISTES_SERVOS:
        if est_nombre(valeur):
            if not 0 <= valeur <= 1:
                erreurs.append("{} : position servo hors [0,1] : {!r}".format(ou, valeur))
        elif isinstance(valeur, str):
            if valeur not in COMMANDES_SERVO:
                erreurs.append("{} : commande servo inconnue : {!r}".format(ou, valeur))
        elif not (isinstance(valeur, dict) and "mode" in valeur):
            erreurs.append("{} : valeur servo invalide : {!r}".format(ou, valeur))
    elif piste == "wheels":
        # Décision 7 : plus de commande texte ni de dict dans une piste roues de séquence.
        if not (isinstance(valeur, list) and len(valeur) == 2
                and all(est_nombre_fini(v) for v in valeur)):
            erreurs.append("{} : consigne roues [gauche, droite] (deux nombres) attendue, "
                           "reçu {!r}".format(ou, valeur))
        elif any(abs(v) > VITESSE_ROUES_MAX for v in valeur):
            erreurs.append("{} : consigne roues {!r} au-delà de {} (VITESSE_ROUES_MAX)".format(
                ou, valeur, VITESSE_ROUES_MAX))
    elif piste == "faces":
        if not isinstance(valeur, str) or valeur not in references["expressions"]:
            erreurs.append("{} : référence l'expression inconnue {!r}".format(ou, valeur))
    elif piste == "robot_lights":
        if not isinstance(valeur, str) or valeur not in references["robot_lights"]:
            erreurs.append("{} : référence la séquence lumière inconnue {!r}".format(ou, valeur))
    elif piste == "audios":
        if valeur == COMMANDE_AUDIO_STOP:
            return
        if not (isinstance(valeur, str) and MOTIF_FICHIER_AUDIO.match(valeur)):
            erreurs.append("{} : {!r} n'a pas la forme nom.mp3/nom.wav (ni la sentinelle "
                           "'stop')".format(ou, valeur))
        elif references["audios_verifiables"] and not os.path.isfile(
                os.path.join(references["data_dir"], DOSSIER_AUDIOS, valeur)):
            erreurs.append("{} : fichier audio introuvable : {}/{}".format(ou, DOSSIER_AUDIOS, valeur))


def _consigne_nulle(valeur):
    return isinstance(valeur, list) and len(valeur) == 2 and all(
        est_nombre(v) and v == 0 for v in valeur)


def _verifier_bornes_roues(piste, duree, erreurs):
    """Bornes de la décision 7 qui portent sur la piste ENTIÈRE (la consigne de chaque
    image est vérifiée image par image). Une piste vide ne porte aucune borne."""
    images = [k for k in piste if _est_keyframe(k) and est_nombre(k[0])]
    if not piste:
        return
    if duree is not None and duree > DUREE_ROUES_MAX_MS:
        erreurs.append("wheels : duration {} ms au-delà de {} ms (DUREE_ROUES_MAX_MS)".format(
            duree, DUREE_ROUES_MAX_MS))
    if not _consigne_nulle(piste[-1][1] if _est_keyframe(piste[-1]) else None):
        erreurs.append("wheels : la dernière image doit valoir [0, 0] (arrêt final), "
                       "reçu {!r}".format(piste[-1]))
    if duree is None:
        return
    for i, (t, valeur) in enumerate(images):
        if _consigne_nulle(valeur) or not (isinstance(valeur, list) and len(valeur) == 2
                                           and all(est_nombre(v) for v in valeur)):
            continue
        suivante = images[i + 1][0] if i + 1 < len(images) else 1
        tenue = (suivante - t) * duree
        if tenue > TENUE_ROUES_MAX_MS:
            erreurs.append("wheels[{}] : consigne {!r} tenue {:g} ms, au-delà de {} ms "
                           "(TENUE_ROUES_MAX_MS)".format(i, valeur, tenue, TENUE_ROUES_MAX_MS))


# ================================================================ expressions
def taille_png(octets):
    """(largeur, hauteur) lues dans l'IHDR, ou None si ce n'est pas un PNG."""
    if len(octets) < 24 or octets[:8] != SIGNATURE_PNG or octets[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", octets[16:24])


def verifier_expression(nom, expression, references):
    """Contrat d'une entrée d'expressions.json (ancien test_expressions_json.py)."""
    if not isinstance(expression, dict):
        return ["{} : objet JSON attendu".format(nom)]
    erreurs = []
    # `name` est injecté par le chargeur (AbstractJsonActions) : optionnel, mais cohérent.
    if "name" in expression and expression["name"] != nom:
        erreurs.append("{} : champ name {!r} != clé {!r}".format(nom, expression["name"], nom))
    if not (est_nombre(expression.get("duration")) and expression["duration"] > 0):
        erreurs.append("{} : champ 'duration' (nombre > 0) obligatoire".format(nom))
    if not isinstance(expression.get("loop"), bool):
        erreurs.append("{} : champ 'loop' (bool) obligatoire".format(nom))
    for piste, zone in PISTES_VISAGE.items():
        if piste not in expression:
            erreurs.append("{} : piste '{}' obligatoire".format(nom, piste))
            continue
        valeurs = expression[piste]
        # Liste VIDE autorisée : « ne pas toucher cet actionneur » (Track.frames).
        if not isinstance(valeurs, list):
            erreurs.append("{} : piste {} : liste attendue".format(nom, piste))
            continue
        precedent = -1
        for i, keyframe in enumerate(valeurs):
            ou = "{} : {}[{}]".format(nom, piste, i)
            if not _est_keyframe(keyframe):
                erreurs.append("{} : keyframe [t, fichier] attendu, reçu {!r}".format(ou, keyframe))
                continue
            precedent = _verifier_temps(ou, keyframe, precedent, erreurs)
            _verifier_visuel(ou, zone, keyframe[1], references, erreurs)
    return erreurs


def _verifier_visuel(ou, zone, fichier, references, erreurs):
    if not isinstance(fichier, str) or not fichier or "/" in fichier or fichier.startswith("."):
        erreurs.append("{} : nom de fichier attendu, reçu {!r}".format(ou, fichier))
        return
    relatif = "{}/{}/{}".format(DOSSIER_VISUELS, zone, fichier)
    chemin = os.path.join(references["data_dir"], relatif)
    if not os.path.isfile(chemin):
        erreurs.append("{} : visuel introuvable : {}".format(ou, relatif))
        return
    with open(chemin, "rb") as f:
        taille = taille_png(f.read(24))
    attendu = ZONES_IMAGE[zone]
    if taille != attendu:
        # ImageMapping refuse en silence une image de mauvaise taille : visage figé.
        erreurs.append("{} : {} fait {}, attendu {}x{} (ImageMapping refuserait ce visuel en "
                       "silence)".format(ou, fichier, "{}x{}".format(*taille) if taille else
                                         "un format non PNG", *attendu))


# ================================================================ lumières et briques
def verifier_lumiere(nom, lumiere, references):
    """Contrat d'une entrée de robot_lights.json (ancien test_lights_json.py) : `sequences`
    est un dict ORDONNÉ {brique: fraction}, pas une liste de keyframes."""
    if not isinstance(lumiere, dict):
        return ["séquence lumière '{}' : objet JSON attendu".format(nom)]
    ou = "séquence lumière '{}'".format(nom)
    erreurs = []
    if not (est_nombre(lumiere.get("duration")) and lumiere["duration"] > 0):
        erreurs.append("{} : champ 'duration' (nombre > 0) obligatoire".format(ou))
    if not isinstance(lumiere.get("loop"), bool):
        erreurs.append("{} : champ 'loop' (bool) obligatoire".format(ou))
    if "keys" in lumiere:
        cles = lumiere["keys"]
        if not (cles == "None" or (isinstance(cles, list) and all(isinstance(c, str) for c in cles))):
            erreurs.append("{} : 'keys' = liste de chaînes ou \"None\", reçu {!r}".format(ou, cles))
    briques = lumiere.get("sequences")
    if not isinstance(briques, dict):
        erreurs.append("{} : champ 'sequences' (dict {{brique: t}}) obligatoire".format(ou))
        return erreurs
    precedent = -1
    for brique, t in briques.items():
        ici = "{} -> brique '{}'".format(ou, brique)
        if brique not in references["lights_base"]:
            erreurs.append("{} : brique inconnue de {}".format(ici, FICHIERS_A_ENTREES["brique"]))
        if not (est_nombre(t) and 0 <= t <= 1):
            erreurs.append("{} : t hors [0,1] : {!r}".format(ici, t))
            continue
        if t < precedent:
            erreurs.append("{} : briques non triées (t={} après t={})".format(ici, t, precedent))
        precedent = t
    return erreurs


def verifier_brique(nom, brique, references):
    """Contrat d'une entrée de lights_base.json : méthode connue, couleur connue, et tout
    autre champ est un nombre (speed, period, max_intensity, min_intensity)."""
    if not isinstance(brique, dict):
        return ["brique '{}' : objet JSON attendu".format(nom)]
    ou = "brique '{}'".format(nom)
    erreurs = []
    methode = brique.get("method")
    if "method" not in brique:
        erreurs.append("{} : champ 'method' obligatoire".format(ou))
    elif not isinstance(methode, str):
        erreurs.append("{} : 'method' doit être une chaîne".format(ou))
    elif methode not in METHODES_LUMIERE:
        erreurs.append("{} : méthode '{}' absente de LightsAnimations".format(ou, methode))
    if "color" in brique and (not isinstance(brique["color"], str)
                              or brique["color"] not in references["colors"]):
        erreurs.append("{} : couleur {!r} absente de {}".format(ou, brique["color"], FICHIER_COULEURS))
    for champ, valeur in brique.items():
        if champ not in ("method", "color") and not est_nombre_fini(valeur):
            erreurs.append("{} : champ '{}' : nombre attendu, reçu {!r}".format(ou, champ, valeur))
    return erreurs


# ================================================================ images (strict pour ce qui ENTRE)
def verifier_image(zone, octets):
    """Contrat d'une image qui ENTRE (décision 4) : PNG, CRC justes, taille de la zone, RVB
    8 bits non entrelacé (le format de 106 des 127 images), données de la longueur exacte.
    Aucune contrainte de palette : le code n'en a pas (pixels posés tels quels)."""
    if zone not in ZONES_IMAGE:
        return ["image : zone inconnue {!r} (attendu : {})".format(zone, ", ".join(ZONES_IMAGE))]
    if not isinstance(octets, (bytes, bytearray)):
        return ["image : octets attendus"]
    if len(octets) > TAILLE_IMAGE_MAX:
        return ["image : {} octets, au-delà de {} (TAILLE_IMAGE_MAX)".format(len(octets), TAILLE_IMAGE_MAX)]
    if octets[:8] != SIGNATURE_PNG:
        return ["image : signature PNG absente"]
    blocs, erreur = _blocs_png(octets)
    if erreur:
        return [erreur]
    if not blocs or blocs[0][0] != b"IHDR" or len(blocs[0][1]) != 13:
        return ["image : le premier bloc doit être IHDR (13 octets)"]
    if blocs[-1][0] != b"IEND":
        return ["image : bloc IEND final absent"]
    largeur, hauteur, profondeur, couleur, compression, filtre, entrelacement = struct.unpack(
        ">IIBBBBB", blocs[0][1])
    erreurs = []
    attendu = ZONES_IMAGE[zone]
    if (largeur, hauteur) != attendu:
        erreurs.append("image : {}x{}, attendu {}x{} pour la zone {}".format(
            largeur, hauteur, attendu[0], attendu[1], zone))
    if (profondeur, couleur) != (8, 2):
        erreurs.append("image : RVB 8 bits attendu (profondeur {}, type de couleur {})".format(
            profondeur, couleur))
    if (compression, filtre) != (0, 0):
        erreurs.append("image : compression/filtre PNG inconnus ({}, {})".format(compression, filtre))
    if entrelacement != 0:
        erreurs.append("image : PNG entrelacé refusé")
    if erreurs:
        return erreurs
    donnees = b"".join(d for t, d in blocs if t == b"IDAT")
    longueur = hauteur * (1 + largeur * 3)
    try:
        # max_length : une bombe de décompression s'arrête à un octet de trop.
        decompresseur = zlib.decompressobj()
        brut = decompresseur.decompress(donnees, longueur + 1)
    except zlib.error:
        return ["image : données IDAT illisibles (zlib)"]
    if len(brut) != longueur or not decompresseur.eof:
        return ["image : données IDAT de {} octets{}, attendu {}".format(
            len(brut), " ou plus" if len(brut) > longueur else "", longueur)]
    return []


def _blocs_png(octets):
    """[(type, données)] des blocs, CRC vérifiés ; (blocs, message d'erreur ou None)."""
    blocs, pos = [], 8
    while pos < len(octets):
        if pos + 12 > len(octets):
            return blocs, "image : bloc tronqué à l'octet {}".format(pos)
        longueur, = struct.unpack(">I", octets[pos:pos + 4])
        type_bloc = octets[pos + 4:pos + 8]
        fin = pos + 8 + longueur
        if fin + 4 > len(octets):
            return blocs, "image : bloc {!r} tronqué".format(type_bloc.decode("latin-1"))
        donnees = octets[pos + 8:fin]
        crc, = struct.unpack(">I", octets[fin:fin + 4])
        if zlib.crc32(type_bloc + donnees) & 0xFFFFFFFF != crc:
            return blocs, "image : CRC faux sur le bloc {!r}".format(type_bloc.decode("latin-1"))
        blocs.append((type_bloc, donnees))
        pos = fin + 4
        if type_bloc == b"IEND":
            break
    if pos != len(octets):
        return blocs, "image : octets après IEND"
    return blocs, None


# ================================================================ empreintes (décision 7 bis)
def _en_float(valeur):
    """Nombres convertis en float : `1` et `1.0` (formatage à la main) ont la même empreinte."""
    if isinstance(valeur, bool) or valeur is None or isinstance(valeur, str):
        return valeur
    if isinstance(valeur, (int, float)):
        return float(valeur)
    if isinstance(valeur, list):
        return [_en_float(v) for v in valeur]
    if isinstance(valeur, dict):
        return {k: _en_float(v) for k, v in valeur.items()}
    return valeur


def empreinte(valeur):
    """sha256 du JSON canonique, nombres en float."""
    return sha256_octets(json_canonique(_en_float(valeur)).encode("utf-8"))


def empreinte_roues(sequence):
    """Empreinte de {duration, wheels} d'une séquence à piste roues NON vide, sinon None :
    la validation à l'œil ne porte que sur la trajectoire."""
    if not isinstance(sequence, dict) or not sequence.get("wheels"):
        return None
    return empreinte({"duration": sequence.get("duration"), "wheels": sequence["wheels"]})


def empreinte_contenu(kind, nom, data_dir):
    """Empreinte de ce que le rejeu en sim doit avoir vu, ou None si l'élément est absent.

    séquence : le fichier ; expression : l'entrée + le sha256 de chaque image référencée ;
    lumière : l'entrée + les briques référencées. Une image ou une brique retouchée périme
    donc ce qui la montre ; une expression retouchée ne périme PAS les séquences qui la
    citent (pas de cascade).
    """
    d = str(data_dir)
    if kind == "sequence":
        chemin = os.path.join(d, DOSSIER_SEQUENCES, nom + ".json")
        if not os.path.isfile(chemin):
            return None
        return empreinte(_lire_json(chemin, None))
    if kind == "expression":
        entree = _lire_json(os.path.join(d, FICHIERS_A_ENTREES["expression"]), {}).get(nom)
        if entree is None:
            return None
        images = {}
        for piste, zone in PISTES_VISAGE.items():
            for keyframe in entree.get(piste) or []:
                if _est_keyframe(keyframe) and isinstance(keyframe[1], str):
                    relatif = "{}/{}".format(zone, keyframe[1])
                    chemin = os.path.join(d, DOSSIER_VISUELS, relatif)
                    images[relatif] = None
                    if os.path.isfile(chemin):
                        with open(chemin, "rb") as f:
                            images[relatif] = sha256_octets(f.read())
        return empreinte({"entree": entree, "images": images})
    if kind == "lumiere":
        entree = _lire_json(os.path.join(d, FICHIERS_A_ENTREES["lumiere"]), {}).get(nom)
        if entree is None:
            return None
        base = _lire_json(os.path.join(d, FICHIERS_A_ENTREES["brique"]), {})
        sequences = entree.get("sequences")
        briques = {b: base.get(b) for b in (sequences if isinstance(sequences, dict) else {})}
        return empreinte({"entree": entree, "briques": briques})
    raise ValueError("kind sans empreinte de rejeu : {!r}".format(kind))


# ================================================================ registre (LECTURE seule ici)
def registre_vide():
    return {"version": VERSION_REGISTRE, "sequence": {}, "expression": {}, "lumiere": {}}


def lire_registre(data_dir):
    """Registre `json/validations-sim.json` ; absent = vide (tout est « à faire »).
    Il ne s'écrit qu'en sim (L1d-2) : ce module ne fait que le lire."""
    registre = _lire_json(os.path.join(str(data_dir), FICHIER_REGISTRE), None)
    if registre is None:
        return registre_vide()
    for famille in FAMILLES_REJOUEES:
        registre.setdefault(famille, {})
    return registre


def elements(data_dir):
    """[(kind, nom)] de tout ce que la porte sim surveille, triés."""
    d = str(data_dir)
    resultat = []
    racine = os.path.join(d, DOSSIER_SEQUENCES)
    for dossier, _, fichiers in os.walk(racine):
        for f in fichiers:
            if f.endswith(".json"):
                relatif = os.path.relpath(os.path.join(dossier, f), racine)
                resultat.append(("sequence", relatif[:-len(".json")].replace(os.sep, "/")))
    for kind in ("expression", "lumiere"):
        for nom in _lire_json(os.path.join(d, FICHIERS_A_ENTREES[kind]), {}):
            resultat.append((kind, nom))
    return sorted(resultat)


def a_rejouer(data_dir, registre=None):
    """[(kind, nom)] dont le tampon `rejeu` n'égale pas l'empreinte actuelle."""
    registre = lire_registre(data_dir) if registre is None else registre
    return [(kind, nom) for kind, nom in elements(data_dir)
            if registre[kind].get(nom, {}).get("rejeu") != empreinte_contenu(kind, nom, data_dir)]


def roues_validees(registre, nom, sequence):
    """Vrai si la piste roues de `sequence` (nommée `<dossier>/<nom>`) n'a rien à valider,
    ou si son empreinte est celle validée au registre (sim ou héritée)."""
    attendu = empreinte_roues(sequence)
    return attendu is None or registre.get("sequence", {}).get(nom, {}).get("roues") == attendu


def roues_a_valider(data_dir, registre=None):
    """Noms des séquences dont la piste roues n'est pas validée pour le robot."""
    registre = lire_registre(data_dir) if registre is None else registre
    a_valider = []
    for kind, nom in elements(data_dir):
        if kind != "sequence":
            continue
        sequence = _lire_json(os.path.join(str(data_dir), DOSSIER_SEQUENCES, nom + ".json"), None)
        if not roues_validees(registre, nom, sequence):
            a_valider.append(nom)
    return a_valider


# ================================================================ rechargement à chaud (décision 9)
def verdict_a_recharger(brut, kinds):
    """(kind, name) si le verdict `brut` (msg de data_edit_result) dit qu'un élément d'un des
    `kinds` vient d'être écrit, sinon None. Le message ne porte aucun contenu : un verdict
    forgé ne fait que relire un fichier ; le nom est revalidé ici."""
    try:
        verdict = json.loads(brut)
    except (TypeError, ValueError):
        return None
    if not isinstance(verdict, dict) or verdict.get("ok") is not True:
        return None
    kind, name = verdict.get("kind"), verdict.get("name")
    if kind not in kinds or not nom_valide(kind, name):
        return None
    return kind, name
