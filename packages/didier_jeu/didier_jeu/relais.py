"""Le chemin d'ARRÊT VOCAL, réduit à l'essentiel — logique pure.

Verrou : qui a posé le stop ({"console", "bouche"}) ; un « go » de la
console (David) lève tout, un « go » de la bouche ne lève que le stop de la
bouche (revue A1, bloquant 1).

RelaisSeul : le mode DÉGRADÉ de jeu_node (revue A1, bloquant 2). Avec
`jeu:=true` le régisseur n'écoute plus la bouche : si le sélecteur ne peut
pas se construire (répertoire ou réglages illisibles), il démarre QUAND MÊME
et relaie stop/go (bouche et console), sans aucune initiative. Le chemin
d'arrêt vocal ne dépend JAMAIS d'un JSON de séquence ni d'un réglage. Une
demande de GESTE de la bouche y est refusée ET le chat le sait (réponse
« dropped », code « degrade » : Didier ne doit jamais affirmer un geste
qui n'a pas eu lieu).
"""
from didier_rehearsal.contracts import CHAT_MOVE_PAUSE, CHAT_MOVE_REPLY_JEU_REASONS, CHAT_MOVE_REPLY_NO_REPLY

STOP, GO = "stop", "go"
# « Regarde ça » de la bouche (lot « texte raccord », 18/11) : arrêt bref puis reprise par le
# sélecteur ; en mode dégradé, un simple stop (sens sûr : aucune reprise automatique).
PAUSE = CHAT_MOVE_PAUSE


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


class Verrou:
    def __init__(self):
        self.sources = set()

    @property
    def actif(self) -> bool:
        return bool(self.sources)

    def poser(self, source: str) -> None:
        self.sources.add(source)

    def lever(self, source: str) -> bool:
        """False si refusé (la bouche ne lève pas un stop de David)."""
        if source != "console" and "console" in self.sources:
            return False
        if source == "console":
            self.sources.clear()
        else:
            self.sources.discard(source)
        return True


class RelaisSeul:
    """Même interface d'entrées que Selecteur ; ne fait QUE relayer stop/go."""

    def __init__(self, raison: str):
        self.raison = raison
        self.verrou = Verrou()
        self.sorties = []
        self._journal("degrade", f"le sélecteur n'a pas pu démarrer ({raison}) : il ne fait que "
                      "relayer stop et go, sans aucune initiative")

    def _journal(self, type_, pourquoi, **payload):
        payload["pourquoi"] = pourquoi
        self.sorties.append(("journal", type_, payload))

    def _relayer(self, valeur, source):
        if valeur == PAUSE:
            valeur = STOP      # mode dégradé : la pause est un stop, sans reprise
        if valeur == STOP:
            self.verrou.poser(source)
            self.sorties.append(("chat_move", STOP))
            self._journal("relais_stop", f"stop de {source} relayé (mode dégradé)", source=source)
        elif valeur == GO:
            if not self.verrou.lever(source):
                self._journal("refus", "la bouche dit « go » mais c'est David qui a arrêté : "
                              "seul un go de la console le relance", source=source)
                return
            self.sorties.append(("chat_move", GO))
            self._journal("relais_go", f"go de {source} relayé (mode dégradé)", source=source)
        else:
            if source == "bouche" and isinstance(valeur, dict):
                self.sorties.append(("chat_move_reply", reponse_bouche(valeur, "dropped", "degrade")))
            self._journal("refus", f"mode dégradé : demande de {source} ignorée ({valeur!r})", source=source)

    def sur_chat_move_bouche(self, valeur, now):
        self._relayer(valeur, "bouche")

    def sur_console(self, payload, now):
        cmd = payload.get("cmd") if isinstance(payload, dict) else None
        if cmd is not None:
            self._relayer(cmd, "console")

    def __getattr__(self, nom):
        # Toute autre entrée (person_box, poi_event, route_state…) est ignorée.
        if nom.startswith("sur_"):
            return lambda *a, **k: None
        raise AttributeError(nom)

    def tick(self, now):
        return None

    def intention(self, now):
        return {"action": "degrade", "cible": None, "verrou": self.verrou.actif, "t_ms": int(now * 1000),
                "pourquoi": f"mode dégradé : relais stop/go seul ({self.raison})"}

    def vider_sorties(self):
        out, self.sorties = self.sorties, []
        return out
