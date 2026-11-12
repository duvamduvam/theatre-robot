"""Écrivain des données du robot (lot L1d, 12/11) : TOUTE écriture par le topic data_edit
passe par `traiter`, pure de ROS (stdlib + theatre_contrats), testée sur un dossier jetable.

Spec : docs/spec-L1-contrats-donnees.md, « L1d », décisions 2, 3, 6 et 8. Ordre des refus :
drapeau, taille, forme, kind, mode, nom, cible (dossier, existence, homonyme, conflit), clés,
contrat (theatre_contrats.donnees — jamais recopié ici), contenu inchangé, quota.

Ordre d'écriture (échec à une étape = `erreur_ecriture`, cible intacte) :
  (a) sauvegarde de l'ancien fichier sous json/backup/<AAAA-MM-JJ>/ (replace, et toute
      écriture dans un fichier à plusieurs entrées) ;
  (b) ligne au journal des éditions non rapatriées, fsync, AVANT l'écriture : un crash laisse
      au pire une ligne en trop, jamais une retouche inconnue du journal ;
  (c) contenu dans json/backup/.tmp/<id> (fsync) — JAMAIS sous sequences/ ni medias/visuals/,
      dont les chargeurs lisent tout fichier présent au démarrage ; une image passe par
      medias/.tmp/<id> (même montage que sa cible : os.replace ne traverse pas les montages) ;
  (d) os.replace vers la cible, fsync du dossier ;
  (e) fichiers et dossiers créés rendus au propriétaire de json/ (en sim le conteneur tourne
      en root dans l'arbre de travail du PC).
"""
import base64
import binascii
import json
import os
import re
import shutil
import stat

from theatre_contrats import donnees

TAILLE_MAX_DEMANDE = 131_072
MOTIF_ID = r"[A-Za-z0-9_-]{1,64}"
MOTIF_SHA = r"[0-9a-f]{64}"
CHAMPS_DEMANDE = ("id", "kind", "mode", "name", "content", "base_sha256")
MODES = ("create", "replace")

# Codes GRAVÉS du verdict (décision 2).
CODES = ("ok", "inchange", "edition_desactivee", "payload_invalide", "trop_gros", "kind_inconnu",
         "mode_inconnu", "nom_invalide", "dossier_absent", "existe_deja", "absent", "nom_en_double",
         "conflit", "cle_inconnue", "contrat", "quota_jour", "erreur_ecriture")
A_REJOUER_EN_SIM = "a_rejouer_en_sim"
ROUES_A_VALIDER_EN_SIM = "roues_a_valider_en_sim"
DETAILS_MAX = 20
DETAIL_LONGUEUR_MAX = 300

# Clés de premier niveau acceptées par kind (décision 6) : celles en usage le 12/11.
CLES_AUTORISEES = {
    "sequence": ("audio", "audio_name", "audio_path", "audios", "duration", "faces", "keys",
                 "left_arm", "left_eye", "lights", "loop", "neck", "right_arm", "right_eye",
                 "robot_lights", "types", "wheels"),
    "expression": ("name", "follow audio", "loop", "keys", "duration", "left_eyes", "right_eyes",
                   "mouths", "default"),
    "lumiere": ("loop", "duration", "keys", "sequences", "default"),
    "brique": ("method", "color", "speed", "period", "max_intensity", "min_intensity"),
}

DOSSIER_SAUVEGARDES = "json/backup"
JOURNAL = DOSSIER_SAUVEGARDES + "/EDITIONS-EN-ATTENTE.jsonl"
DOSSIER_TMP = DOSSIER_SAUVEGARDES + "/.tmp"
# Temporaire des IMAGES : medias/ est un AUTRE montage que json/ (sim et compose ARM) et
# os.replace ne traverse pas les montages (EXDEV, mesuré en sim le 12/11). Il vit donc sur le
# montage medias/, hors de medias/visuals/ que Face.load_visuals lit en entier.
DOSSIER_TMP_IMAGES = "medias/.tmp"
QUOTA_JOUR = 200
DOSSIERS_DATES_GARDES = 30
MOTIF_DOSSIER_DATE = r"\d{4}-\d{2}-\d{2}"


class Refus(Exception):
    """Refus d'une demande : `code` gravé + détails lisibles."""

    def __init__(self, code, *detail):
        super().__init__(code)
        self.code = code
        self.detail = list(detail)


# ================================================================ point d'entrée
def traiter(brut, data_dir, enabled, maintenant):
    """Juge puis écrit la demande `brut` (le champ msg reçu) ; rend le verdict (dict).

    `maintenant` (datetime) est injecté : nom de sauvegarde, journal et rotation en dépendent.
    """
    data_dir = str(data_dir)
    taille = len(brut.encode("utf-8")) if isinstance(brut, str) else 0
    demande = _decoder(brut) if isinstance(brut, str) and taille <= TAILLE_MAX_DEMANDE else None
    echo = _echo(demande)
    try:
        if not enabled:
            raise Refus("edition_desactivee", "édition désactivée sur ce robot (drapeau DATA_EDIT)")
        if not isinstance(brut, str) or taille > TAILLE_MAX_DEMANDE:
            raise Refus("trop_gros", "{} octets, maximum {}".format(taille, TAILLE_MAX_DEMANDE))
        demande = _valider_forme(demande)
        return _ecrire_si_conforme(demande, data_dir, maintenant)
    except Refus as refus:
        return verdict(echo, refus.code, refus.detail)


def verdict(echo, code, detail=(), sha256=None, sauvegarde=None, avertissements=()):
    """Le verdict publié sur data_edit_result (décision 2) ; id/kind/name/mode recopiés."""
    return {
        "id": echo.get("id"), "ok": code in ("ok", "inchange"), "code": code,
        "detail": [str(d)[:DETAIL_LONGUEUR_MAX] for d in detail][:DETAILS_MAX],
        "kind": echo.get("kind"), "name": echo.get("name"), "mode": echo.get("mode"),
        "sha256": sha256, "sauvegarde": sauvegarde, "avertissements": list(avertissements),
    }


def _decoder(brut):
    try:
        demande = json.loads(brut)
    except ValueError:
        return None
    return demande if isinstance(demande, dict) else None


def _echo(demande):
    """Champs recopiés dans le verdict, seulement s'ils sont des chaînes courtes."""
    if not isinstance(demande, dict):
        return {}
    return {k: demande[k] for k in ("id", "kind", "name", "mode")
            if isinstance(demande.get(k), str) and len(demande[k]) <= 200}


# ================================================================ forme de la demande
def _valider_forme(demande):
    if demande is None:
        raise Refus("payload_invalide", "objet JSON attendu")
    if not (isinstance(demande.get("id"), str) and re.fullmatch(MOTIF_ID, demande["id"])):
        raise Refus("payload_invalide", "id : 1 à 64 caractères [A-Za-z0-9_-] attendus")
    inconnus = sorted(set(demande) - set(CHAMPS_DEMANDE))
    if inconnus:
        raise Refus("payload_invalide", "champs inconnus : {}".format(", ".join(inconnus)))
    kind = demande.get("kind")
    if kind not in donnees.KINDS:
        raise Refus("kind_inconnu", "kind {!r} hors de {}".format(kind, ", ".join(donnees.KINDS)))
    if demande.get("mode") not in MODES:
        raise Refus("mode_inconnu", "mode {!r} hors de create, replace".format(demande.get("mode")))
    if not isinstance(demande.get("name"), str):
        raise Refus("payload_invalide", "name : chaîne attendue")
    if demande["mode"] == "replace":
        if not (isinstance(demande.get("base_sha256"), str)
                and re.fullmatch(MOTIF_SHA, demande["base_sha256"])):
            raise Refus("payload_invalide", "base_sha256 (64 hex minuscules) exigé en replace")
    elif "base_sha256" in demande:
        raise Refus("payload_invalide", "base_sha256 réservé au mode replace")
    contenu = demande.get("content")
    if kind == "image":
        if not isinstance(contenu, str):
            raise Refus("payload_invalide", "content : les octets du PNG en base64 attendus")
        try:
            demande = dict(demande, content=base64.b64decode(contenu, validate=True))
        except (binascii.Error, ValueError):
            raise Refus("payload_invalide", "content : base64 illisible")
    elif not isinstance(contenu, dict):
        raise Refus("payload_invalide", "content : objet JSON attendu")
    return demande


# ================================================================ cible, contrat, écriture
def _ecrire_si_conforme(demande, data_dir, maintenant):
    kind, mode, name, contenu = demande["kind"], demande["mode"], demande["name"], demande["content"]
    cible = _cible(kind, name, data_dir)
    _verifier_cible(kind, mode, name, cible, data_dir)

    if kind in donnees.FICHIERS_A_ENTREES:
        fichier = _lire_fichier_a_entrees(cible)
        actuel = fichier.get(name)
        present = name in fichier
    else:
        fichier = None
        present = os.path.isfile(cible)
        actuel = _lire_octets(cible) if present else None
    if mode == "create" and present:
        raise Refus("existe_deja", "{} existe déjà : mode replace".format(name))
    if mode == "replace" and not present:
        raise Refus("absent", "{} n'existe pas : mode create".format(name))
    if present:
        sha_actuel = (donnees.sha256_entree(actuel) if fichier is not None
                      else donnees.sha256_octets(actuel))
        if mode == "replace" and demande["base_sha256"] != sha_actuel:
            raise Refus("conflit", "le disque a changé depuis le chargement (sha {})".format(sha_actuel))

    if kind in CLES_AUTORISEES:
        inconnues = sorted(set(contenu) - set(CLES_AUTORISEES[kind]))
        if inconnues:
            raise Refus("cle_inconnue", "clés hors liste pour {} : {}".format(kind, ", ".join(inconnues)))
    erreurs = _contrat(kind, name, contenu, data_dir)
    if erreurs:
        raise Refus("contrat", *erreurs)

    if kind == "image":
        octets = contenu
        sha = donnees.sha256_octets(octets)
        inchange = present and octets == actuel
    elif fichier is not None:
        octets = donnees.serialiser(donnees.poser_entree(fichier, name, contenu))
        sha = donnees.sha256_entree(contenu)
        inchange = present and donnees.json_canonique(contenu) == donnees.json_canonique(actuel)
    else:
        octets = donnees.serialiser(contenu)
        sha = donnees.sha256_octets(octets)
        inchange = present and donnees.json_canonique(contenu) == _canonique_ou_none(actuel)
    if inchange:
        return verdict(demande, "inchange", sha256=sha_actuel)

    # Sauvegarde : en replace, et pour TOUTE écriture dans un fichier à plusieurs entrées.
    sauvegarder = present or fichier is not None
    sauvegarde = _ecrire(demande, cible, octets, sha, sauvegarder, data_dir, maintenant)
    return verdict(demande, "ok", sha256=sha, sauvegarde=sauvegarde,
                   avertissements=avertissements(kind, name, data_dir))


def _cible(kind, name, data_dir):
    if not donnees.nom_valide(kind, name):
        raise Refus("nom_invalide", "nom {!r} hors de la forme attendue pour {}".format(name, kind))
    if kind in donnees.FICHIERS_A_ENTREES:
        return os.path.join(data_dir, donnees.FICHIERS_A_ENTREES[kind])
    if kind == "sequence":
        return os.path.join(data_dir, donnees.DOSSIER_SEQUENCES, name + ".json")
    return os.path.join(data_dir, donnees.DOSSIER_VISUELS, name + ".png")


def _verifier_cible(kind, mode, name, cible, data_dir):
    """Chemin résolu strictement sous le dossier de la famille ; cible ni lien ni dossier ;
    dossier de séquence existant ; aucun homonyme que le chargeur confondrait."""
    if kind in donnees.FICHIERS_A_ENTREES:
        racine = os.path.join(data_dir, "json")
    elif kind == "sequence":
        racine = os.path.join(data_dir, donnees.DOSSIER_SEQUENCES)
    else:
        racine = os.path.join(data_dir, donnees.DOSSIER_VISUELS, name.split("/")[0])
    racine_reelle = os.path.realpath(racine)
    if os.path.commonpath([racine_reelle, os.path.realpath(cible)]) != racine_reelle \
            or os.path.realpath(cible) == racine_reelle:
        raise Refus("nom_invalide", "{} sort de {}".format(name, os.path.relpath(racine, data_dir)))
    if os.path.islink(cible) or os.path.isdir(cible):
        raise Refus("nom_invalide", "{} : la cible est un lien ou un dossier".format(name))
    if kind == "sequence":
        dossier = os.path.dirname(cible)
        if not os.path.isdir(dossier) or os.path.islink(dossier):
            raise Refus("dossier_absent", "dossier {} absent (une création de dossier passe par git)"
                        .format(name.split("/")[0]))
        _refuser_homonyme(os.path.join(data_dir, donnees.DOSSIER_SEQUENCES), cible,
                          os.path.basename(cible), "séquence")
    elif kind == "image":
        # Face indexe les images par nom de fichier NU, bouche et yeux dans le même dict.
        _refuser_homonyme(os.path.join(data_dir, donnees.DOSSIER_VISUELS), cible,
                          os.path.basename(cible), "image", sous=tuple(donnees.ZONES_IMAGE))


def _refuser_homonyme(racine, cible, nom_fichier, quoi, sous=("",)):
    for dossier_racine in (os.path.join(racine, s) for s in sous):
        for dossier, _, fichiers in os.walk(dossier_racine):
            chemin = os.path.join(dossier, nom_fichier)
            if nom_fichier in fichiers and os.path.realpath(chemin) != os.path.realpath(cible):
                raise Refus("nom_en_double", "une {} {} existe déjà dans {} (le chargeur indexe par "
                            "nom nu)".format(quoi, nom_fichier, os.path.relpath(dossier, racine)))


def _lire_fichier_a_entrees(chemin):
    try:
        with open(chemin, encoding="utf-8") as f:
            fichier = json.load(f)
    except (OSError, ValueError) as e:
        raise Refus("erreur_ecriture", "fichier {} illisible : {}".format(os.path.basename(chemin), e))
    if not isinstance(fichier, dict):
        raise Refus("erreur_ecriture", "fichier {} : objet JSON attendu".format(os.path.basename(chemin)))
    return fichier


def _canonique_ou_none(octets):
    """JSON canonique d'un fichier de séquence sur disque ; None s'il est illisible (une
    retouche le remplacera, ce n'est jamais « inchangé »)."""
    try:
        return donnees.json_canonique(json.loads(octets.decode("utf-8")))
    except ValueError:
        return None


def _lire_octets(chemin):
    with open(chemin, "rb") as f:
        return f.read()


def _contrat(kind, name, contenu, data_dir):
    if kind == "image":
        return donnees.verifier_image(name.split("/")[0], contenu)
    try:
        references = donnees.charger_references(data_dir)
    except (OSError, ValueError) as e:
        return ["références du robot illisibles : {}".format(e)]
    if kind == "sequence":
        return donnees.verifier_sequence(contenu, references)
    if kind == "expression":
        return donnees.verifier_expression(name, contenu, references)
    if kind == "lumiere":
        return donnees.verifier_lumiere(name, contenu, references)
    return donnees.verifier_brique(name, contenu, references)


def avertissements(kind, name, data_dir):
    """Ce que la porte sim (décision 7 bis) demandera avant que la retouche ne parte sur le
    robot : rejeu de ce qui a changé, ou de ce qui montre l'image / enchaîne la brique."""
    registre = donnees.lire_registre(data_dir)
    if kind in donnees.FAMILLES_REJOUEES:
        concernes = [(kind, name)]
    elif kind == "image":
        zone, nom = name.split("/")
        fichier = nom + ".png"
        expressions = donnees.charger_references(data_dir)["expressions"]
        concernes = [("expression", e) for e, valeur in expressions.items()
                     if any(isinstance(k, list) and len(k) == 2 and k[1] == fichier
                            for piste, z in donnees.PISTES_VISAGE.items() if z == zone
                            for k in (valeur.get(piste) or []))]
    else:
        lumieres = donnees.charger_references(data_dir)["robot_lights"]
        concernes = [("lumiere", l) for l, valeur in lumieres.items()
                     if isinstance(valeur.get("sequences"), dict) and name in valeur["sequences"]]
    resultat = []
    if any(registre[k].get(n, {}).get("rejeu") != donnees.empreinte_contenu(k, n, data_dir)
           for k, n in concernes):
        resultat.append(A_REJOUER_EN_SIM)
    if kind == "sequence":
        with open(os.path.join(data_dir, donnees.DOSSIER_SEQUENCES, name + ".json"), encoding="utf-8") as f:
            if not donnees.roues_validees(registre, name, json.load(f)):
                resultat.append(ROUES_A_VALIDER_EN_SIM)
    return resultat


def nom_sauvegarde(kind, name, maintenant, id_demande, extension):
    """`<kind>__<nom, « / » et espaces en « _ »>__<HHMMSS>__<id>.<ext>` (décision 8 a)."""
    return "{}__{}__{}__{}.{}".format(kind, re.sub(r"[/ ]", "_", name), maintenant.strftime("%H%M%S"),
                                      id_demande, extension)


def _ecrire(demande, cible, octets, sha, sauvegarder, data_dir, maintenant):
    """Étapes (a) à (e) ; rend le chemin de la sauvegarde relatif à data_dir, ou None."""
    kind, name, id_demande = demande["kind"], demande["name"], demande["id"]
    json_dir = os.path.join(data_dir, "json")
    racine = os.path.join(data_dir, DOSSIER_SAUVEGARDES)
    tmp_dir = os.path.join(data_dir, DOSSIER_TMP_IMAGES if kind == "image" else DOSSIER_TMP)
    proprietaire = os.stat(json_dir)
    crees = []
    sauvegarde = None
    tmp = os.path.join(tmp_dir, id_demande)
    try:
        crees += _creer_dossier(racine)
        # (a) sauvegarde
        if sauvegarder:
            jour = os.path.join(racine, maintenant.strftime("%Y-%m-%d"))
            if os.path.isdir(jour) and len(os.listdir(jour)) >= QUOTA_JOUR:
                raise Refus("quota_jour", "{} sauvegardes aujourd'hui (maximum {})".format(
                    len(os.listdir(jour)), QUOTA_JOUR))
            crees += _creer_dossier(jour)
            extension = "png" if kind == "image" else "json"
            chemin = os.path.join(jour, nom_sauvegarde(kind, name, maintenant, id_demande, extension))
            shutil.copyfile(cible, chemin)
            _fsync_fichier(chemin)
            crees.append(chemin)
            sauvegarde = os.path.relpath(chemin, data_dir)
            _tourner(racine)
        # (b) journal, AVANT l'écriture
        journal = os.path.join(data_dir, JOURNAL)
        if not os.path.exists(journal):
            crees.append(journal)
        ligne = {"t": maintenant.isoformat(timespec="seconds"), "id": id_demande, "kind": kind,
                 "name": name, "mode": demande["mode"], "sha256": sha, "sauvegarde": sauvegarde}
        with open(journal, "a", encoding="utf-8") as f:
            f.write(donnees.json_canonique(ligne) + "\n")
            f.flush()
            os.fsync(f.fileno())
        # (c) temporaire hors des dossiers lus par les chargeurs
        crees += _creer_dossier(tmp_dir)
        with open(tmp, "wb") as f:
            f.write(octets)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(cible):
            # Le fichier remplacé garde ses droits (un 755 suivi par git ne devient pas 644).
            os.chmod(tmp, stat.S_IMODE(os.stat(cible).st_mode))
        # (d) remplacement atomique
        os.replace(tmp, cible)
        _fsync_dossier(os.path.dirname(cible))
        crees.append(cible)
        # (e) propriétaire de json/
        for chemin in crees:
            try:
                os.chown(chemin, proprietaire.st_uid, proprietaire.st_gid)
            except (PermissionError, FileNotFoundError):
                pass
        return sauvegarde
    except OSError as e:
        raise Refus("erreur_ecriture", "{} : {}".format(type(e).__name__, e))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _creer_dossier(chemin):
    """Crée le dossier s'il manque ; rend [chemin] s'il vient d'être créé, [] sinon."""
    if os.path.isdir(chemin):
        return []
    os.makedirs(chemin)
    return [chemin]


def _fsync_fichier(chemin):
    with open(chemin, "rb") as f:
        os.fsync(f.fileno())


def _fsync_dossier(chemin):
    fd = os.open(chemin, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _tourner(racine):
    """Garde les DOSSIERS_DATES_GARDES dossiers datés les plus récents, efface les autres."""
    dates = sorted(d for d in os.listdir(racine)
                   if re.fullmatch(MOTIF_DOSSIER_DATE, d) and os.path.isdir(os.path.join(racine, d)))
    for ancien in dates[:-DOSSIERS_DATES_GARDES]:
        shutil.rmtree(os.path.join(racine, ancien))


def vider_tmp(data_dir):
    """Au démarrage du nœud : un temporaire laissé par un crash ne sert plus à rien."""
    total = 0
    for relatif in (DOSSIER_TMP, DOSSIER_TMP_IMAGES):
        tmp_dir = os.path.join(str(data_dir), relatif)
        if not os.path.isdir(tmp_dir):
            continue
        for nom in os.listdir(tmp_dir):
            chemin = os.path.join(tmp_dir, nom)
            if os.path.isdir(chemin) and not os.path.islink(chemin):
                shutil.rmtree(chemin)
            else:
                os.remove(chemin)
            total += 1
    return total
