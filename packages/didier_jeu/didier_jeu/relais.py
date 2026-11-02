"""Le chemin d'ARRÊT VOCAL, réduit à l'essentiel — logique pure.

Verrou : qui a posé le stop ({"console", "bouche"}) ; un « go » de la
console (David) lève tout, un « go » de la bouche ne lève que le stop de la
bouche (revue A1, bloquant 1).

RelaisSeul : le mode DÉGRADÉ de jeu_node (revue A1, bloquant 2). Avec
`jeu:=true` le régisseur n'écoute plus la bouche : si le sélecteur ne peut
pas se construire (répertoire ou réglages illisibles), il démarre QUAND MÊME
et relaie stop/go (bouche et console), sans aucune initiative. Le chemin
d'arrêt vocal ne dépend JAMAIS d'un JSON de séquence ni d'un réglage.
"""

STOP, GO = "stop", "go"


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
