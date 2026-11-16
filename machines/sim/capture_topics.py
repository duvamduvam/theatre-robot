#!/usr/bin/env python3
"""Enregistreur rclpy des épreuves de la sim — remplace les captures `ros2 topic echo` en CLI.

POURQUOI (lot fiabilité des épreuves, 16/11) : « une épreuve rouge doit vouloir dire un vrai défaut
de Didier, jamais un raté de mesure » (David). La CLI ros2 lancée en arrière-plan se fait découvrir
en 2 à 4 s sur le PC de David (erreurs multicast, ~50 conteneurs), lit en best-effort par défaut et
perd des messages sous charge : le 15/11, V-R3 a rougi à 20/21 sur « une consigne chat_instruction
par lubie démarrée » sans que rien ne dise si Didier ou la capture était en tort.

CE QUE FAIT CET OUTIL, en un seul processus par épreuve, lancé AVANT l'épreuve :
  - s'abonne à une liste de topics, TYPE et QoS EXPLICITES (reliable, KEEP_LAST profond,
    transient_local seulement pour un topic latché — sinon l'historique d'avant l'épreuve
    fausserait les comptes) ;
  - mode `journal` : chaque message, une ligne JSONL horodatée (`journal.jsonl`), écrite et
    VIDÉE (flush) aussitôt — un arrêt brutal ne perd que la ligne en cours ;
  - mode `dernier` : seule la dernière valeur, remplacée atomiquement dans `dernier/<topic>.json`
    (lectures ponctuelles : position, vitesse, état latché) — pas de flot énorme sur disque ;
  - écrit la sentinelle `PRET` quand CHAQUE abonnement est apparié à au moins un éditeur et à
    tous ceux que le graphe connaît (Subscription.get_publisher_count) : l'épreuve attend ce
    fichier avant de démarrer (fin de la course au démarrage). Pas prêt dans le délai : `ECHEC`
    (ce qui manque) et code 3 — le banc est faux, pas Didier ;
  - SIGTERM/SIGINT (ou mort du shell parent) : arrêt propre, fichiers fermés, `FIN` (compte par
    topic) écrit en dernier.

Sous-commandes (les quatre dernières n'importent pas rclpy) :
  enregistrer   --dossier D --journal NOM=TYPE[,latche] … --dernier NOM=TYPE[,latche] …
  attendre-pret --dossier D --pid PID --delai S      0 prêt ; 1 enregistreur mort ou ECHEC ; 2 délai
  lire          --dossier D --topic NOM --champ a.b [--apres EPOCH|--tout-age] [--valeur V] --delai S
  extraire      --dossier D --topic NOM --champ a.b  une valeur par ligne, comme `--field` de la CLI
  verifier-fin  --dossier D                          0 si FIN écrit (arrêt propre, tout vidé)

Monté dans le conteneur `monde` (/home/ros2_ws/capture_topics.py), utilisé par captures.sh.
Tests (sans ROS) : packages/didier_core/test/unit/test_capture_topics.py.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import NamedTuple

JOURNAL = "journal.jsonl"
DERNIER = "dernier"
PRET = "PRET"
ECHEC = "ECHEC"
FIN = "FIN"
PROFONDEUR = 1000          # KEEP_LAST : aucun rejet même si l'écriture prend du retard
PERIODE_DERNIER_S = 0.02   # un fichier `dernier` au plus toutes les 20 ms par topic (odom ~ 50 Hz)
MODES = ("journal", "dernier")


# --- Logique pure (testée sans ROS) ---------------------------------------------------------

class Spec(NamedTuple):
    """Un topic à enregistrer : nom ABSOLU (la CLI comme rclpy, sans namespace ici), type
    `pkg/msg/Type`, latché (transient_local) ou non, mode journal|dernier."""
    nom: str
    type: str
    mode: str
    latche: bool = False


def lire_spec(texte: str, mode: str) -> Spec:
    """« /didier/route_state=theatre_interfaces/msg/StringTime,latche » → Spec."""
    if mode not in MODES:
        raise ValueError(f"mode inconnu : {mode!r}")
    nom, egal, reste = texte.partition("=")
    options = reste.split(",")
    type_, options = options[0], options[1:]
    if not egal or not nom.startswith("/") or type_.count("/") != 2:
        raise ValueError(f"spec invalide : {texte!r} (attendu /topic=pkg/msg/Type[,latche])")
    inconnues = [o for o in options if o != "latche"]
    if inconnues:
        raise ValueError(f"option inconnue dans {texte!r} : {inconnues}")
    return Spec(nom=nom, type=type_, mode=mode, latche="latche" in options)


def nom_fichier(topic: str) -> str:
    """/didier/rehearsal/chat_fault → didier__rehearsal__chat_fault.json (un fichier par topic)."""
    return topic.strip("/").replace("/", "__") + ".json"


def ligne_jsonl(topic: str, stamp: float, payload) -> str:
    """Une ligne du journal : réception (epoch, s, à la µs), topic, message entier."""
    return json.dumps({"stamp": round(stamp, 6), "topic": topic, "payload": payload},
                      ensure_ascii=False) + "\n"


def champ(payload, chemin: str):
    """payload["pose"]["pose"]["position"]["x"] pour « pose.pose.position.x » ; KeyError sinon."""
    valeur = payload
    for cle in chemin.split("."):
        valeur = valeur[cle]
    return valeur


def texte_valeur(valeur) -> str:
    """Comme `ros2 topic echo --field` : une chaîne brute telle quelle, un nombre en clair, un
    composé en JSON compact (une seule ligne)."""
    if isinstance(valeur, str):
        return valeur
    if isinstance(valeur, bool):
        return "true" if valeur else "false"
    if isinstance(valeur, (int, float)):
        return repr(valeur)
    return json.dumps(valeur, ensure_ascii=False, sort_keys=True)


def ecrire_atomique(fichier: Path, texte: str) -> None:
    provisoire = fichier.with_name(fichier.name + ".tmp")
    provisoire.write_text(texte, encoding="utf-8")
    provisoire.replace(fichier)


class Enregistreur:
    """La partie fichiers de l'enregistreur, sans ROS : journal vidé à chaque ligne, dernières
    valeurs (au plus une écriture par PERIODE_DERNIER_S et par topic, la dernière n'est jamais
    perdue : `vider_derniers` l'écrit à l'arrêt), sentinelles PRET / ECHEC / FIN."""

    def __init__(self, dossier: Path, horloge=time.time):
        self.dossier = Path(dossier)
        self.horloge = horloge
        (self.dossier / DERNIER).mkdir(parents=True, exist_ok=True)
        for sentinelle in (PRET, ECHEC, FIN):
            (self.dossier / sentinelle).unlink(missing_ok=True)
        self._journal = open(self.dossier / JOURNAL, "a", encoding="utf-8")
        self.comptes: dict[str, int] = {}
        self._en_attente: dict[str, tuple] = {}   # topic -> (stamp, message brut, convertir)
        self._derniere_ecriture: dict[str, float] = {}
        self.ferme = False

    def journal(self, topic: str, payload, stamp: float | None = None) -> None:
        self._journal.write(ligne_jsonl(topic, self.horloge() if stamp is None else stamp, payload))
        self._journal.flush()
        self.comptes[topic] = self.comptes.get(topic, 0) + 1

    def dernier(self, topic: str, message, convertir=lambda m: m, stamp: float | None = None) -> None:
        """Note la valeur (conversion différée : seule celle écrite est convertie)."""
        self._en_attente[topic] = (self.horloge() if stamp is None else stamp, message, convertir)
        self.comptes[topic] = self.comptes.get(topic, 0) + 1
        self.vider_derniers(force=False)

    def vider_derniers(self, force: bool = True) -> None:
        maintenant = time.monotonic()
        for topic in list(self._en_attente):
            if not force and maintenant - self._derniere_ecriture.get(topic, -1e9) < PERIODE_DERNIER_S:
                continue
            stamp, message, convertir = self._en_attente.pop(topic)
            ecrire_atomique(self.dossier / DERNIER / nom_fichier(topic),
                            json.dumps({"stamp": round(stamp, 6), "topic": topic,
                                        "payload": convertir(message)}, ensure_ascii=False))
            self._derniere_ecriture[topic] = maintenant

    def marquer_pret(self, etat: dict) -> None:
        ecrire_atomique(self.dossier / PRET, json.dumps({"stamp": round(self.horloge(), 6),
                                                         "topics": etat}, sort_keys=True) + "\n")

    def marquer_echec(self, etat: dict, raison: str) -> None:
        ecrire_atomique(self.dossier / ECHEC, json.dumps({"raison": raison, "topics": etat},
                                                         sort_keys=True, ensure_ascii=False) + "\n")

    def fermer(self) -> None:
        """Idempotent : vide les dernières valeurs, ferme le journal, PUIS écrit FIN (FIN présent =
        tout ce qui a été reçu est sur disque)."""
        if self.ferme:
            return
        self.ferme = True
        self.vider_derniers(force=True)
        self._journal.flush()
        os.fsync(self._journal.fileno())
        self._journal.close()
        ecrire_atomique(self.dossier / FIN, json.dumps({"stamp": round(self.horloge(), 6),
                                                        "comptes": self.comptes}, sort_keys=True) + "\n")


class Arret:
    """Drapeau levé par SIGTERM / SIGINT : la boucle finit son tour puis ferme proprement."""

    def __init__(self):
        self.demande = False

    def installer(self) -> None:
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._lever)

    def _lever(self, _signum, _frame) -> None:
        self.demande = True


def boucle(enregistreur: Enregistreur, tourner_une_fois, arret: Arret) -> None:
    """Tourne jusqu'au signal, puis ferme (même si tourner_une_fois lève)."""
    try:
        while not arret.demande:
            tourner_une_fois()
            enregistreur.vider_derniers(force=False)
    finally:
        enregistreur.fermer()


def etat_pret(appariements: dict) -> tuple[bool, list]:
    """appariements : topic -> (éditeurs appariés, éditeurs connus du graphe). Prêt si chaque
    topic a au moins un éditeur apparié et autant que le graphe en connaît."""
    manquants = [t for t, (apparies, connus) in sorted(appariements.items())
                 if apparies < max(1, connus)]
    return not manquants, manquants


def attendre_pret(dossier: Path, pid: int, delai: float, pas: float = 0.1) -> int:
    """0 = PRET ; 1 = ECHEC écrit ou enregistreur mort ; 2 = délai dépassé."""
    fin = time.monotonic() + delai
    while True:
        if (dossier / PRET).exists():
            return 0
        if (dossier / ECHEC).exists() or not _vivant(pid):
            return 1
        if time.monotonic() >= fin:
            return 2
        time.sleep(pas)


def _vivant(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # Un zombie (fils mort pas encore attendu par le shell) répond à kill 0 : on lit son état.
    try:
        etat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except OSError:
        return False
    return etat != "Z"


def lire_dernier(dossier: Path, topic: str, chemin: str, apres: float | None, valeur: str | None,
                 delai: float, pas: float = 0.05) -> str | None:
    """Valeur du champ dans la dernière valeur reçue, reçue APRÈS `apres` (None = n'importe quand,
    pour un état latché) et, si `valeur` est donnée, égale à elle. Attend jusqu'à `delai` s ; rend
    None si rien ne convient (la dernière lue, même non conforme, n'est PAS rendue : l'appelant
    décide)."""
    fichier = Path(dossier) / DERNIER / nom_fichier(topic)
    fin = time.monotonic() + delai
    while True:
        try:
            donnee = json.loads(fichier.read_text(encoding="utf-8"))
            if apres is None or donnee["stamp"] >= apres:
                texte = texte_valeur(champ(donnee["payload"], chemin))
                if valeur is None or texte == valeur:
                    return texte
        except (OSError, ValueError, KeyError, TypeError):
            pass
        if time.monotonic() >= fin:
            return None
        time.sleep(pas)


def extraire(dossier: Path, topic: str, chemin: str):
    """Les valeurs du champ, dans l'ordre de réception, pour un topic du journal."""
    with open(Path(dossier) / JOURNAL, encoding="utf-8") as f:
        for ligne in f:
            donnee = json.loads(ligne)
            if donnee["topic"] == topic:
                yield texte_valeur(champ(donnee["payload"], chemin))


# --- Partie ROS (dans le conteneur seulement) ----------------------------------------------

def enregistrer(dossier: Path, specs: list[Spec], delai_pret: float) -> int:
    import rclpy
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
    from rclpy.signals import SignalHandlerOptions
    from rosidl_runtime_py import message_to_ordereddict
    from rosidl_runtime_py.utilities import get_message

    def en_dict(message):
        return json.loads(json.dumps(message_to_ordereddict(message)))

    arret = Arret()
    arret.installer()   # nos gestionnaires, pas ceux de rclpy (sinon KeyboardInterrupt en plein vol)
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    noeud = rclpy.create_node("capture_topics_%d" % os.getpid())
    enr = Enregistreur(dossier)
    abonnements = {}
    for spec in specs:
        qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=PROFONDEUR,
                         reliability=ReliabilityPolicy.RELIABLE,
                         durability=(DurabilityPolicy.TRANSIENT_LOCAL if spec.latche
                                     else DurabilityPolicy.VOLATILE))
        if spec.mode == "journal":
            rappel = (lambda s: lambda m: enr.journal(s.nom, en_dict(m)))(spec)
        else:
            rappel = (lambda s: lambda m: enr.dernier(s.nom, m, en_dict))(spec)
        abonnements[spec.nom] = noeud.create_subscription(get_message(spec.type), spec.nom, rappel, qos)

    def appariements():
        return {nom: (sub.get_publisher_count(), noeud.count_publishers(nom))
                for nom, sub in abonnements.items()}

    fin = time.monotonic() + delai_pret
    pret, manquants = etat_pret(appariements())
    while not pret and not arret.demande and time.monotonic() < fin:
        rclpy.spin_once(noeud, timeout_sec=0.1)
        pret, manquants = etat_pret(appariements())
    etat = {nom: {"apparies": a, "editeurs": c} for nom, (a, c) in appariements().items()}
    if not pret:
        enr.marquer_echec(etat, "non apparié(s) en %.0f s : %s" % (delai_pret, " ".join(manquants)))
        print("capture_topics : PAS PRÊT — non apparié(s) : %s" % " ".join(manquants), flush=True)
        enr.fermer()
        noeud.destroy_node()
        rclpy.shutdown()
        return 3
    enr.marquer_pret(etat)
    print("capture_topics : PRÊT — %s" % json.dumps(etat, sort_keys=True), flush=True)
    parent = os.getppid()

    def tourner():
        rclpy.spin_once(noeud, timeout_sec=PERIODE_DERNIER_S)
        if os.getppid() != parent:   # l'épreuve est morte sans nous arrêter : pas d'orphelin
            arret.demande = True
    boucle(enr, tourner, arret)
    print("capture_topics : arrêt propre — %s" % json.dumps(enr.comptes, sort_keys=True), flush=True)
    noeud.destroy_node()
    rclpy.shutdown()
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sous = p.add_subparsers(dest="commande", required=True)
    e = sous.add_parser("enregistrer")
    e.add_argument("--dossier", type=Path, required=True)
    e.add_argument("--journal", action="append", default=[])
    e.add_argument("--dernier", action="append", default=[])
    e.add_argument("--delai-pret", type=float, default=45.0)
    a = sous.add_parser("attendre-pret")
    a.add_argument("--dossier", type=Path, required=True)
    a.add_argument("--pid", type=int, required=True)
    a.add_argument("--delai", type=float, default=60.0)
    lu = sous.add_parser("lire")
    lu.add_argument("--dossier", type=Path, required=True)
    lu.add_argument("--topic", required=True)
    lu.add_argument("--champ", required=True)
    quand = lu.add_mutually_exclusive_group()
    quand.add_argument("--apres", type=float, default=None, help="epoch ; défaut : maintenant")
    quand.add_argument("--tout-age", action="store_true", help="état latché : n'importe quelle réception")
    lu.add_argument("--valeur", default=None)
    lu.add_argument("--delai", type=float, default=4.0)
    x = sous.add_parser("extraire")
    x.add_argument("--dossier", type=Path, required=True)
    x.add_argument("--topic", required=True)
    x.add_argument("--champ", required=True)
    v = sous.add_parser("verifier-fin")
    v.add_argument("--dossier", type=Path, required=True)
    args = p.parse_args(argv)

    if args.commande == "enregistrer":
        specs = [lire_spec(t, "journal") for t in args.journal] + [lire_spec(t, "dernier") for t in args.dernier]
        if not specs:
            p.error("au moins un --journal ou --dernier")
        return enregistrer(args.dossier, specs, args.delai_pret)
    if args.commande == "attendre-pret":
        return attendre_pret(args.dossier, args.pid, args.delai)
    if args.commande == "lire":
        apres = None if args.tout_age else (time.time() if args.apres is None else args.apres)
        texte = lire_dernier(args.dossier, args.topic, args.champ, apres, args.valeur, args.delai)
        if texte is None:
            return 1
        print(texte)
        return 0
    if args.commande == "extraire":
        for texte in extraire(args.dossier, args.topic, args.champ):
            print(texte)
        return 0
    return 0 if (args.dossier / FIN).exists() else 1


if __name__ == "__main__":
    sys.exit(main())
