"""PISTES de personnes à partir de vision/person_box (A1 : perception scriptée).

Une seule boîte par message (le contrat actuel ne porte qu'UNE personne) :
x = azimut [-1, 1] (+1 = bord DROIT de l'image), y = hauteur de silhouette
[0, 1] (proxy de distance), z = confiance [0, 1] ; le silence = perdue.

Identifiant STABLE et hystérésis d'apparition : une redétection moins de
`nouvelle_apres_s` après la perte reprend la MÊME piste (personne revue en
bord de champ) — seule une détection après ce délai fait NAÎTRE une piste
(et donc une offre et un saut de curiosité). Les ids sont p1, p2, … dans
l'ordre des naissances (déterministe).
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Piste:
    id: str
    azimut: float
    hauteur: float
    t_vu: float


class Pistes:
    def __init__(self, perte_s: float, nouvelle_apres_s: float, confiance_min: float):
        self.perte_s = perte_s
        self.nouvelle_apres_s = nouvelle_apres_s
        self.confiance_min = confiance_min
        self._courante: Optional[Piste] = None
        self._n = 0

    def courante(self, now: float) -> Optional[Piste]:
        """La piste vue il y a moins de perte_s, sinon None."""
        p = self._courante
        if p is not None and now - p.t_vu <= self.perte_s:
            return p
        return None

    def update(self, azimut: float, hauteur: float, confiance: float, now: float) -> Optional[str]:
        """Une boîte -> id de la piste NÉE (None si piste existante ou boîte ignorée)."""
        if confiance < self.confiance_min:
            return None
        p = self._courante
        if p is not None and now - p.t_vu <= self.perte_s + self.nouvelle_apres_s:
            # Vue en continu, ou perdue depuis moins de nouvelle_apres_s : même piste.
            p.azimut, p.hauteur, p.t_vu = azimut, hauteur, now
            return None
        self._n += 1
        self._courante = Piste(f"p{self._n}", azimut, hauteur, now)
        return self._courante.id
