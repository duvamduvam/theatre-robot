"""Porte sim (lot L1d-2) : l'observateur qui pose les tampons du registre des validations.

Spec : docs/spec-L1-contrats-donnees.md, « L1d », décisions 7 bis et 7 ter. Rien de modifié
n'atteint le vrai robot sans avoir été joué en sim ; la porte ne doit pas être une corvée :
automatique pour tout, à l'œil pour les roues seulement.

L'observateur REGARDE ce qui se joue, quel que soit le déclencheur (page, régisseur, script),
et tamponne `rejeu` quand l'élément a été joué jusqu'au bout sans incident :
- séquence : `animation_state` passe au nom puis revient à "" entre 0,95 × `duration` et
  `duration` + 5 s ; aucune ligne ERROR/CRITICAL nouvelle dans le journal du robot (lu depuis
  l'offset noté au départ) ; les nœuds présents au départ toujours là ; piste roues : un
  `cmd_vel` reçu pendant le jeu et le dernier reçu nul 1 s après la fin ;
- expression : nom reçu sur `face`, `face_sim_node` vivant et sans erreur pendant
  min(`duration`, 10 s), sans autre commande sur `face` ;
- lumière : idem sur `robot_lights` avec `leds_sim_node`. Ce nœud journalise par ROS (/rosout),
  pas dans robot.log ; /rosout n'est pas écouté (règle gravée : aucun abonnement à un nom
  absolu, test_namespace_contract) — ses deux erreurs possibles (JSON invalide, séquence
  inconnue) dépendent du message, que l'observateur vérifie lui-même contre le disque.
Empreinte déjà au registre → aucune écriture (la fumée ne salit rien).

Validation à l'œil des roues (`valider_roues`) : acceptée seulement si le tampon `rejeu` de la
séquence égale son empreinte actuelle — on ne valide pas une trajectoire qu'on n'a pas vue.

Le registre ne s'écrit qu'en sim : `Observateur` refuse de se construire hors domaine 43.
Logique pure (horloge injectée, en millisecondes) ; le nœud ROS (validation_sim_node) ne fait
que brancher les topics. Testé sans ROS : packages/didier_core/test/unit/test_validation_sim.py.
"""
import json
import os
import re

from theatre_contrats import donnees

DOMAINE_SIM = 43

# Fenêtre d'un jeu complet (décision 7 bis).
FRACTION_MIN = 0.95
MARGE_FIN_MS = 5_000
ATTENTE_ARRET_ROUES_MS = 1_000
TENUE_MAX_MS = 10_000  # expression et lumière : min(duration, 10 s)

# Nœuds dont l'absence en fin de jeu empêche le tampon (s'ils étaient là au départ).
NOEUDS_SURVEILLES = ("animation_node", "face_sim_node", "leds_sim_node", "servos_sim_node",
                     "catalogue_node", "data_edit_node", "twist_deadman", "twist_mux", "wheels_bridge")
NOEUD_VISAGE = "face_sim_node"
NOEUD_LUMIERES = "leds_sim_node"

# Codes de verdict, GRAVÉS (test_validation_sim.py) ; ok = tamponnee, deja_tamponnee,
# roues_validees, deja_validees.
CODES_REJEU = ("tamponnee", "deja_tamponnee", "interrompue", "trop_longue", "erreur_journal",
               "noeud_absent", "roues_sans_cmd_vel", "roues_non_arretees", "absente", "homonyme",
               "erreur_ecriture")
CODES_ROUES = ("roues_validees", "deja_validees", "non_rejouee", "sans_roues", "absente",
               "nom_invalide", "payload_invalide", "erreur_ecriture")
CODES_OK = ("tamponnee", "deja_tamponnee", "roues_validees", "deja_validees")
DETAILS_MAX = 20
DETAIL_LONGUEUR_MAX = 300

# Ligne de niveau ERROR ou CRITICAL du journal du robot (format de LoggingConf :
# « … |<numéro de ligne>: ERROR<couleur> message »).
MOTIF_ERREUR = re.compile(r"\|\d+: (ERROR|CRITICAL)")

# Journal du robot : config[LOGGING_FILE_NAME] de didier_core (égalité gravée par test).
JOURNAL_ROBOT = "/home/ros2_ws/log/robot.log"


def domaine_autorise(environ):
    """Vrai seulement si ROS_DOMAIN_ID vaut 43 (simulation). Absent ou illisible = refusé."""
    try:
        return int(environ.get("ROS_DOMAIN_ID", "")) == DOMAINE_SIM
    except (TypeError, ValueError):
        return False


def verdict(kind, name, code, detail=(), id_demande=None):
    """Message publié sur `validation_sim` : {kind, name, ok, code, detail} (+ id d'une demande)."""
    v = {"kind": kind, "name": name, "ok": code in CODES_OK, "code": code,
         "detail": [str(d)[:DETAIL_LONGUEUR_MAX] for d in list(detail)[:DETAILS_MAX]]}
    if id_demande is not None:
        v["id"] = id_demande
    return v


# ================================================================ journal du robot
class Journal:
    """Lecture du journal du robot à partir d'un offset en OCTETS (il porte des accents).
    Fichier tourné (plus court que l'offset) : relu depuis le début."""

    def __init__(self, chemin):
        self.chemin = chemin

    def offset(self):
        try:
            return os.path.getsize(self.chemin)
        except OSError:
            return 0

    def erreurs_depuis(self, offset, filtre=None):
        """Lignes ERROR/CRITICAL écrites depuis `offset` (contenant `filtre` s'il est donné)."""
        try:
            with open(self.chemin, "rb") as f:
                f.seek(0, os.SEEK_END)
                if f.tell() < offset:
                    offset = 0
                f.seek(offset)
                texte = f.read().decode("utf-8", errors="replace")
        except OSError:
            return []
        return [ligne for ligne in texte.splitlines()
                if MOTIF_ERREUR.search(ligne) and (filtre is None or filtre in ligne)]


# ================================================================ registre (écriture, sim seulement)
def resoudre_sequence(data_dir, nom_nu):
    """Chemins `<dossier>/<nom>` des fichiers de séquence dont le nom nu est `nom_nu` : le
    chargeur du robot indexe par nom nu, `animation_state` ne porte que lui."""
    racine = os.path.join(str(data_dir), donnees.DOSSIER_SEQUENCES)
    return sorted(nom for kind, nom in donnees.elements(data_dir)
                  if kind == "sequence" and nom.split("/")[-1] == nom_nu
                  and os.path.isfile(os.path.join(racine, nom + ".json")))


def sans_orphelines(registre, data_dir):
    """Nouveau registre sans les entrées dont l'élément n'existe plus (effacé ou renommé par
    git) : retirer un tampon ne valide rien. Appliqué à chaque écriture de l'observateur."""
    orphelines = set(donnees.orphelines(data_dir, registre))
    resultat = json.loads(json.dumps(registre))
    for kind, nom in orphelines:
        del resultat[kind][nom]
    return resultat


def poser_rejeu(registre, kind, nom, empreinte):
    """Nouveau registre : tampon `rejeu` posé, les autres champs de l'entrée (roues) gardés."""
    resultat = json.loads(json.dumps(registre))
    entree = dict(resultat.setdefault(kind, {}).get(nom, {}))
    entree["rejeu"] = empreinte
    resultat[kind][nom] = entree
    return resultat


def poser_roues(registre, nom, empreinte_roues, origine):
    """Nouveau registre : tampon `roues` et son origine (`sim` ou `heritee`) posés."""
    resultat = json.loads(json.dumps(registre))
    entree = dict(resultat.setdefault("sequence", {}).get(nom, {}))
    entree["roues"] = empreinte_roues
    entree["origine_roues"] = origine
    resultat["sequence"][nom] = entree
    return resultat


def ecrire_registre(data_dir, registre):
    """Écriture atomique du registre (décision 7 bis) : temporaire sous json/backup/.tmp/
    (jamais à côté des fichiers lus par les chargeurs), fsync, os.replace, fsync du dossier,
    propriétaire de json/ (rien n'appartient à root dans l'arbre du PC)."""
    d = str(data_dir)
    cible = os.path.join(d, donnees.FICHIER_REGISTRE)
    json_dir = os.path.join(d, "json")
    tmp_dir = os.path.join(d, "json", "backup", ".tmp")
    proprietaire = os.stat(json_dir)
    crees = [p for p in (os.path.join(d, "json", "backup"), tmp_dir) if not os.path.isdir(p)]
    os.makedirs(tmp_dir, exist_ok=True)
    tmp = os.path.join(tmp_dir, "validations-sim.{}".format(os.getpid()))
    try:
        with open(tmp, "wb") as f:
            f.write(donnees.serialiser_registre(registre))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, cible)
        fd = os.open(json_dir, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    for chemin in crees + [cible]:
        try:
            os.chown(chemin, proprietaire.st_uid, proprietaire.st_gid)
        except (PermissionError, FileNotFoundError):
            pass


# ================================================================ l'observateur
class Observateur:
    """Suit ce qui se joue et rend des verdicts. Chaque méthode d'événement reçoit `t` (ms,
    horloge monotone du nœud) et rend la liste des verdicts produits (souvent vide).

    `journal` : un Journal ; `noeuds` : fonction sans argument rendant les noms (nus) des
    nœuds vivants ; `environ` : l'environnement du processus (garde du domaine)."""

    def __init__(self, data_dir, journal, noeuds, environ):
        if not domaine_autorise(environ):
            raise RuntimeError("validation_sim refuse de démarrer : ROS_DOMAIN_ID={!r}, le registre ne "
                               "s'écrit qu'en simulation ({})".format(environ.get("ROS_DOMAIN_ID"), DOMAINE_SIM))
        self.data_dir = str(data_dir)
        self.journal = journal
        self.noeuds = noeuds
        self.sequence = None     # jeu de séquence en cours
        self.fin_roues = None    # séquence à roues terminée, en attente du cmd_vel nul
        self.affichages = {}     # "face" / "robot_lights" -> affichage en cours
        self.dernier_cmd_vel = None  # (t, nul)

    # ------------------------------------------------------------ entrées brutes
    def cmd_vel(self, t, nul):
        self.dernier_cmd_vel = (t, bool(nul))
        return []

    # ------------------------------------------------------------ séquences
    def etat_animation(self, t, nom):
        verdicts = []
        if self.sequence is not None:
            jeu, self.sequence = self.sequence, None
            ecoule = t - jeu["t"]
            if nom:  # un autre départ (ou le même nom republié) coupe le jeu en cours
                verdicts.append(self._refus(jeu, "interrompue", "relancée ou remplacée par {!r} après {} ms"
                                            .format(nom, ecoule)))
            elif ecoule < FRACTION_MIN * jeu["duree"]:
                verdicts.append(self._refus(jeu, "interrompue", "arrêtée après {} ms sur {} ms".format(
                    ecoule, jeu["duree"])))
            elif ecoule > jeu["duree"] + MARGE_FIN_MS:
                verdicts.append(self._refus(jeu, "trop_longue", "finie après {} ms pour {} ms".format(
                    ecoule, jeu["duree"])))
            elif jeu["roues"]:
                jeu["fin"] = t
                self.fin_roues = jeu
            else:
                verdicts.append(self._conclure(jeu, t))
        if nom:
            verdicts += self._debut_sequence(t, nom)
        return verdicts

    def _debut_sequence(self, t, nom):
        chemins = resoudre_sequence(self.data_dir, nom)
        if not chemins:
            return [verdict("sequence", nom, "absente", ["aucun fichier json/sequences/*/{}.json".format(nom)])]
        if len(chemins) > 1:
            # Le chargeur n'en garde qu'un (ordre du système de fichiers) et animation_state ne dit
            # pas lequel : on ne tamponne pas ce qu'on ne sait pas avoir vu.
            return [verdict("sequence", nom, "homonyme", ["même nom dans {}".format(", ".join(chemins))])]
        chemin = chemins[0]
        with open(os.path.join(self.data_dir, donnees.DOSSIER_SEQUENCES, chemin + ".json"), encoding="utf-8") as f:
            sequence = json.load(f)
        self.sequence = {"kind": "sequence", "name": chemin, "t": t,
                         "duree": sequence.get("duration"),
                         "roues": bool(sequence.get("wheels")),
                         "empreinte": donnees.empreinte_contenu("sequence", chemin, self.data_dir),
                         "offset": self.journal.offset(),
                         "noeuds": self._noeuds_surveilles()}
        return []

    def _conclure(self, jeu, t):
        erreurs = self.journal.erreurs_depuis(jeu["offset"])
        if erreurs:
            return self._refus(jeu, "erreur_journal", erreurs)
        absents = sorted(set(jeu["noeuds"]) - set(self._noeuds_surveilles()))
        if absents:
            return self._refus(jeu, "noeud_absent", absents)
        if jeu["roues"]:
            if self.dernier_cmd_vel is None or self.dernier_cmd_vel[0] < jeu["t"]:
                return self._refus(jeu, "roues_sans_cmd_vel", ["aucun cmd_vel reçu pendant le jeu "
                                                               "(chaîne roues lancée ?)"])
            if not self.dernier_cmd_vel[1]:
                return self._refus(jeu, "roues_non_arretees", ["dernier cmd_vel non nul {} ms après la fin".format(
                    t - jeu["fin"])])
        return self._tamponner(jeu)

    # ------------------------------------------------------------ expressions et lumières
    def commande(self, t, topic, valeur):
        """Message reçu sur `face` ou `robot_lights` (valeur JSON décodée)."""
        verdicts = []
        en_cours = self.affichages.pop(topic, None)
        if en_cours is not None:
            verdicts.append(self._refus(en_cours, "interrompue", "autre commande {!r} après {} ms".format(
                valeur, t - en_cours["t"])))
        kind = "expression" if topic == "face" else "lumiere"
        if isinstance(valeur, str):
            fichier = donnees.FICHIERS_A_ENTREES[kind]
            with open(os.path.join(self.data_dir, fichier), encoding="utf-8") as f:
                entree = json.load(f).get(valeur)
            if isinstance(entree, dict):
                duree = entree.get("duration")
                tenue = min(duree, TENUE_MAX_MS) if donnees.est_nombre(duree) and duree > 0 else TENUE_MAX_MS
                noeud = NOEUD_VISAGE if kind == "expression" else NOEUD_LUMIERES
                self.affichages[topic] = {"kind": kind, "name": valeur, "t": t, "tenue": tenue, "noeud": noeud,
                                          "empreinte": donnees.empreinte_contenu(kind, valeur, self.data_dir),
                                          "offset": self.journal.offset()}
        return verdicts

    def _conclure_affichage(self, jeu, t):
        if jeu["noeud"] not in self.noeuds():
            return self._refus(jeu, "noeud_absent", [jeu["noeud"]])
        erreurs = self.journal.erreurs_depuis(jeu["offset"], filtre=jeu["noeud"])
        if erreurs:
            return self._refus(jeu, "erreur_journal", erreurs)
        return self._tamponner(jeu)

    # ------------------------------------------------------------ horloge
    def tic(self, t):
        """Appelé périodiquement : conclut ce qui a assez duré."""
        verdicts = []
        if self.fin_roues is not None and t - self.fin_roues["fin"] >= ATTENTE_ARRET_ROUES_MS:
            jeu, self.fin_roues = self.fin_roues, None
            verdicts.append(self._conclure(jeu, t))
        for topic in list(self.affichages):
            jeu = self.affichages[topic]
            if t - jeu["t"] >= jeu["tenue"]:
                del self.affichages[topic]
                verdicts.append(self._conclure_affichage(jeu, t))
        return verdicts

    # ------------------------------------------------------------ validation à l'œil des roues
    def valider_roues(self, brut):
        """Demande `{id, name}` reçue sur `validation_sim_demande` (bouton « Valider les roues
        pour le robot ») ; rend le verdict, avec l'id recopié."""
        try:
            demande = json.loads(brut)
        except (TypeError, ValueError):
            demande = None
        if not isinstance(demande, dict) or not isinstance(demande.get("id"), str):
            return verdict("sequence", None, "payload_invalide", ["objet JSON {id, name} attendu"])
        id_demande, nom = demande["id"], demande.get("name")
        if not donnees.nom_valide("sequence", nom):
            return verdict("sequence", nom, "nom_invalide", ["<dossier>/<nom> attendu"], id_demande)
        chemin = os.path.join(self.data_dir, donnees.DOSSIER_SEQUENCES, nom + ".json")
        if not os.path.isfile(chemin):
            return verdict("sequence", nom, "absente", [], id_demande)
        with open(chemin, encoding="utf-8") as f:
            sequence = json.load(f)
        roues = donnees.empreinte_roues(sequence)
        if roues is None:
            return verdict("sequence", nom, "sans_roues", ["piste wheels vide ou absente"], id_demande)
        registre = donnees.lire_registre(self.data_dir)
        entree = registre["sequence"].get(nom, {})
        if entree.get("rejeu") != donnees.empreinte_contenu("sequence", nom, self.data_dir):
            return verdict("sequence", nom, "non_rejouee",
                           ["la version actuelle n'a pas été jouée jusqu'au bout en sim"], id_demande)
        if entree.get("roues") == roues and entree.get("origine_roues") == "sim":
            return verdict("sequence", nom, "deja_validees", [], id_demande)
        try:
            ecrire_registre(self.data_dir, sans_orphelines(poser_roues(registre, nom, roues, "sim"), self.data_dir))
        except OSError as e:
            return verdict("sequence", nom, "erreur_ecriture", ["{} : {}".format(type(e).__name__, e)], id_demande)
        return verdict("sequence", nom, "roues_validees", [], id_demande)

    # ------------------------------------------------------------ outils
    def _noeuds_surveilles(self):
        presents = set(self.noeuds())
        return [n for n in NOEUDS_SURVEILLES if n in presents]

    def _refus(self, jeu, code, detail):
        if isinstance(detail, str):
            detail = [detail]
        return verdict(jeu["kind"], jeu["name"], code, detail)

    def _tamponner(self, jeu):
        """Tampon posé si l'empreinte du jeu n'y est pas déjà (registre relu : jamais d'écrasement
        d'une écriture faite entre-temps)."""
        registre = donnees.lire_registre(self.data_dir)
        if registre[jeu["kind"]].get(jeu["name"], {}).get("rejeu") == jeu["empreinte"]:
            return verdict(jeu["kind"], jeu["name"], "deja_tamponnee")
        try:
            ecrire_registre(self.data_dir, sans_orphelines(
                poser_rejeu(registre, jeu["kind"], jeu["name"], jeu["empreinte"]), self.data_dir))
        except OSError as e:
            return self._refus(jeu, "erreur_ecriture", "{} : {}".format(type(e).__name__, e))
        return verdict(jeu["kind"], jeu["name"], "tamponnee")
