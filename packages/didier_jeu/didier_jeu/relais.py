"""Le chemin d'ARRÊT VOCAL, réduit à l'essentiel — logique pure.

Ordres et propositions (lot S1, 25/11, docs/spec-S1-ordres-propositions.md) : chaque demande
de marche porte son ORIGINE (didier_rehearsal.contracts.lire_chat_move). Le verrou n'a plus
qu'une source, David : posé par un « stop » d'origine « david » (mot d'arrêt, console), levé
par un « go » d'origine « david » — à deux genres (R3 : la console n'est levée que par la
console, la voix aussi par la bouche). Un « stop » d'origine « didier » arrête toujours (un arrêt
n'est jamais refusé) mais ne verrouille jamais ; un « go » d'origine « didier » est ignoré
(seul le sélecteur relance ce que Didier a arrêté). Supprimé : la classe Verrou à deux sources
(console / bouche) de la revue A1 du 02/11.

RelaisSeul : le mode DÉGRADÉ de jeu_node (revue A1, bloquant 2). Avec
`jeu:=true` le régisseur n'écoute plus la bouche : si le sélecteur ne peut
pas se construire (répertoire ou réglages illisibles), il démarre QUAND MÊME
et relaie stop/go (bouche et console), sans aucune initiative. Le chemin
d'arrêt vocal ne dépend JAMAIS d'un JSON de séquence ni d'un réglage. Mêmes
règles d'origine ; un « stop » de Didier y est relayé SANS verrou NI reprise
(sens sûr : il reste arrêté jusqu'à un « go » de David). Une demande de GESTE
de la bouche y est refusée ET le chat le sait (réponse « dropped », code
« degrade » : Didier ne doit jamais affirmer un geste qui n'a pas eu lieu).
"""
from didier_rehearsal.contracts import (CHAT_MOVE_GO, CHAT_MOVE_ORIGINE_DAVID, CHAT_MOVE_ORIGINE_DIDIER,
                                       CHAT_MOVE_PAUSE, CHAT_MOVE_REPLY_JEU_REASONS, CHAT_MOVE_REPLY_NO_REPLY,
                                       CHAT_MOVE_STOP, lire_chat_move)

STOP, GO = CHAT_MOVE_STOP, CHAT_MOVE_GO
# « Regarde ça » de la bouche (lot « texte raccord », 18/11) : arrêt bref puis reprise par le
# sélecteur ; en mode dégradé, un simple stop (sens sûr : aucune reprise automatique).
PAUSE = CHAT_MOVE_PAUSE
DAVID, DIDIER = CHAT_MOVE_ORIGINE_DAVID, CHAT_MOVE_ORIGINE_DIDIER
# Genres du verrou de David (règle R3, 25/11) : la CONSOLE (STOP console, Route OFF), levée
# par un GO console seulement ; la VOIX (mot d'arrêt), levée aussi par un go de David en tour
# humain (la bouche).
VERROU_CONSOLE, VERROU_VOIX = "console", "voix"
# Troisième genre (seconde relecture, 26/11) : la Route OFF de David, levée quand la route revient
# à « on » (route_state) — jamais par un go vocal. Sans lui, OFF puis ON laissait un verrou
# « console » fantôme : Didier roulait mais refusait tout.
VERROU_ROUTE = "route"


def marche(cmd: str, origine: str) -> dict:
    """Payload de jeu/chat_move pour un ordre de marche (contrat lot S1)."""
    return {"cmd": cmd, "origine": origine}


def lire(valeur):
    """(demande, origine) d'un message de la bouche (contracts.lire_chat_move), origine
    inconnue tranchée ICI, une fois pour le sélecteur et le relais : un « stop » est lu
    « david » (il verrouille : un arrêt n'est jamais refusé), toute autre demande garde None
    (refusée par l'appelant)."""
    demande, origine = lire_chat_move(valeur)
    if origine is None and demande == STOP:
        origine = DAVID
    return demande, origine


def reponse_bouche(demande, effet: str, code, distance_m=None, cote=None) -> dict:
    """Payload de rehearsal/chat_move_reply émis par le JEU (contracts.
    CHAT_MOVE_REPLY_TOPIC) : la demande de la bouche telle quelle (le chat
    apparie par égalité), « dropped » + code connu, ou « no_reply ».
    `distance_m`, `cote` (codes « pas_ici » / « hors_atteinte », lu dans le tableau des
    objets) : ajoutés au payload s'ils sont connus."""
    if effet != CHAT_MOVE_REPLY_NO_REPLY and code not in CHAT_MOVE_REPLY_JEU_REASONS:
        raise ValueError(f"code de refus inconnu : {code!r}")
    out = {"demande": demande, "effect": effet, "reason": code, "source": "jeu"}
    if distance_m is not None:
        out["distance_m"] = distance_m
    if cote is not None:
        out["cote"] = cote
    return out


class RelaisSeul:
    """Même interface d'entrées que Selecteur ; ne fait QUE relayer stop/go."""

    def __init__(self, raison: str):
        self.raison = raison
        self.verrou = None          # None | VERROU_CONSOLE | VERROU_VOIX (mêmes règles que le sélecteur)
        self.sorties = []
        self._journal("degrade", f"le sélecteur n'a pas pu démarrer ({raison}) : il ne fait que "
                      "relayer stop et go, sans aucune initiative")

    def _journal(self, type_, pourquoi, **payload):
        payload["pourquoi"] = pourquoi
        self.sorties.append(("journal", type_, payload))

    def _relayer(self, valeur, source):
        demande, origine = lire(valeur)
        if demande == PAUSE:
            demande = STOP     # mode dégradé : la pause est un stop, sans reprise
        if demande == STOP:
            if origine == DAVID:
                self.verrou = VERROU_CONSOLE if source == "console" else (self.verrou or VERROU_VOIX)
            self.sorties.append(("chat_move", marche(STOP, origine)))
            self._journal("relais_stop", f"stop ({origine}) de {source} relayé (mode dégradé, aucune reprise)",
                          source=source, origine=origine)
        elif demande == GO:
            if origine != DAVID:
                self._journal("refus", f"« go » d'origine {origine!r} ignoré : seul un go de David le relance "
                              "(mode dégradé)", source=source, origine=origine)
                return
            if source != "console" and self.verrou == VERROU_CONSOLE:
                self._journal("refus", "« go » dit à Didier, mais David a arrêté à la console : seul un GO "
                              "console le relance (mode dégradé)", source=source, origine=origine)
                return
            self.verrou = None
            self.sorties.append(("chat_move", marche(GO, DAVID)))
            self._journal("relais_go", f"go de David ({source}) relayé (mode dégradé)", source=source,
                          origine=origine)
        else:
            if source == "bouche" and isinstance(demande, dict):
                self.sorties.append(("chat_move_reply", reponse_bouche(demande, "dropped", "degrade")))
            self._journal("refus", f"mode dégradé : demande de {source} ignorée ({valeur!r})", source=source)

    def sur_chat_move_bouche(self, valeur, now):
        self._relayer(valeur, "bouche")

    def sur_console(self, payload, now):
        # La console est David : ses ordres n'ont pas d'autre origine possible.
        cmd = payload.get("cmd") if isinstance(payload, dict) else None
        if cmd is not None:
            self._relayer(marche(cmd, DAVID), "console")

    @property
    def verrou_david(self) -> bool:
        return self.verrou is not None

    def __getattr__(self, nom):
        # Toute autre entrée (person_box, poi_event, route_state…) est ignorée.
        if nom.startswith("sur_"):
            return lambda *a, **k: None
        raise AttributeError(nom)

    def tick(self, now):
        return None

    def intention(self, now):
        return {"action": "degrade", "cible": None, "verrou": self.verrou_david, "t_ms": int(now * 1000),
                "pourquoi": f"mode dégradé : relais stop/go seul ({self.raison})"}

    def vider_sorties(self):
        out, self.sorties = self.sorties, []
        return out
