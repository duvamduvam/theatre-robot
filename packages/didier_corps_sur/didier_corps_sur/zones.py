"""Zones LIBRE / RALENTI / ARRET avec hystérésis (spec A0 §5.1) — PUR.

Entrée IMMÉDIATE (un seul point, un seul balayage), sortie RETARDÉE : on quitte
ARRET quand `d_min ≥ marge_arret + hysteresis` pendant `balayages_de_sortie`
balayages VALIDES de suite ; même règle pour quitter RALENTI (marge_ralenti +
hysteresis). Un faux arrêt est une gêne, un arrêt manqué un accident.

Interprétations écrites (la spec ne les dit pas) :
- un balayage INVALIDE peut faire ENTRER en ARRET/RALENTI (l'obstacle vu, même
  sur un balayage trop vieux, est plus sûr que rien) mais ne compte jamais pour
  en SORTIR : il remet les compteurs de sortie à zéro (« de suite ») ;
- avant le premier balayage, la zone vaut ARRET ; le premier balayage VALIDE la
  fixe directement (aucune sortie retardée : rien n'a encore été vu).
L'arrêt de zone n'est PAS un verrou : Didier repart seul quand la voie se libère.
"""
from dataclasses import dataclass

LIBRE = "LIBRE"
RALENTI = "RALENTI"
ARRET = "ARRET"


@dataclass(frozen=True)
class ParametresZones:
    marge_arret_m: float
    marge_ralenti_m: float
    hysteresis_m: float
    balayages_de_sortie: int


class Zones:

    def __init__(self, params: ParametresZones):
        self.p = params
        self._zone: str | None = None
        # Balayages valides de suite au-delà de chaque seuil de sortie.
        self._sortie_arret = 0
        self._sortie_ralenti = 0

    @property
    def zone(self) -> str:
        return ARRET if self._zone is None else self._zone

    def _brute(self, d_min: float) -> str:
        if d_min < self.p.marge_arret_m:
            return ARRET
        if d_min < self.p.marge_ralenti_m:
            return RALENTI
        return LIBRE

    def observer(self, d_min: float, valide: bool = True) -> str:
        """Un balayage de plus (d_min = plus petite distance à la caisse des
        points valides, `inf` si aucun) → la zone."""
        brute = self._brute(d_min)
        if valide and d_min >= self.p.marge_arret_m + self.p.hysteresis_m:
            self._sortie_arret += 1
        else:
            self._sortie_arret = 0
        if valide and d_min >= self.p.marge_ralenti_m + self.p.hysteresis_m:
            self._sortie_ralenti += 1
        else:
            self._sortie_ralenti = 0

        if self._zone is None:
            if valide or brute == ARRET:
                self._zone = brute
            return self.zone
        # Entrée immédiate vers plus sévère.
        if brute == ARRET:
            self._zone = ARRET
        elif brute == RALENTI and self._zone == LIBRE:
            self._zone = RALENTI
        # Sortie retardée.
        n = self.p.balayages_de_sortie
        if self._zone == ARRET and self._sortie_arret >= n:
            self._zone = LIBRE if self._sortie_ralenti >= n else RALENTI
        elif self._zone == RALENTI and self._sortie_ralenti >= n:
            self._zone = LIBRE
        return self._zone
