"""Les OFFRES (Johnstone : tout événement est une offre, à prendre ou refuser).

Offre(kind, piste, valeur, t_naissance, ttl) : elle meurt par TTL, quand une
action la PREND, ou quand la console dit « ignore » sur sa cible. Les temps
sont en secondes (horloge monotone injectée : tests sans sleep).
"""
from dataclasses import dataclass, field
from typing import List, Optional

KINDS = ("personne", "objet", "bouche")


@dataclass
class Offre:
    kind: str                 # "personne" | "objet" | "bouche"
    piste: str                # id de piste, nom d'objet, ou "bouche"
    valeur: float             # [0, 1]
    t_naissance: float
    ttl: float
    payload: Optional[dict] = None   # bouche : la demande de chat_move telle quelle
    prise: bool = field(default=False)

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"offre : kind inconnu {self.kind!r}")

    def age(self, now: float) -> float:
        return max(0.0, now - self.t_naissance)

    def vivante(self, now: float) -> bool:
        return not self.prise and self.age(now) < self.ttl

    def fraicheur(self, now: float) -> float:
        """1 à la naissance, 0 à la mort (linéaire)."""
        if not self.vivante(now):
            return 0.0
        return 1.0 - self.age(now) / self.ttl

    def resume(self, now: float) -> dict:
        return {"kind": self.kind, "piste": self.piste, "valeur": self.valeur,
                "fraicheur": round(self.fraicheur(now), 2)}


class Offres:
    def __init__(self):
        self._offres: List[Offre] = []

    def naitre(self, offre: Offre) -> Offre:
        self._offres.append(offre)
        return offre

    def prendre(self, offre: Offre) -> None:
        offre.prise = True

    def tuer_cible(self, cible: str) -> int:
        """« ignore » : toutes les offres vivantes de la cible meurent."""
        n = 0
        for o in self._offres:
            if o.piste == cible and not o.prise:
                o.prise = True
                n += 1
        return n

    def vivantes(self, now: float) -> List[Offre]:
        self._offres = [o for o in self._offres if o.vivante(now)]
        return list(self._offres)
