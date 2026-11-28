"""Le ruban du corps suit l'émotion du visage (étude du visage §12.6, demande de David du 27/11).

Une expression de `expressions.json` peut porter un champ `corps` : le nom d'une entrée de
`robot_lights.json` (`joie` -> `joie`, `colere` -> `colere`…). Quand le visage change, le
corps prend cette lumière — SAUF si quelqu'un a commandé le corps explicitement.

Règle de priorité, la seule de ce module :
1. une **commande explicite** du corps (topic `robot_lights` : séquence, page scène,
   télécommande) garde la main jusqu'à ce qu'elle revienne au repos (fin de l'entrée,
   « stop », ou commande du repos lui-même) ;
2. sinon, le corps suit le **visage** : la lumière liée à l'expression en cours ;
3. une expression sans `corps` rend le corps au repos, s'il était tenu par le visage.

Logique PURE (stdlib, aucune horloge ni ROS) : le vrai robot (`lights_node`) et l'aperçu de
la page scène (`didier_web.apercu_lumieres`) appliquent la même règle, testée une fois.
"""
from typing import Optional

STOP = "stop"
REPOS = "default"


class CorpsSuitVisage:
    """Arbitre entre la lumière commandée et la lumière liée au visage.

    Chaque méthode rend le nom de la lumière à jouer maintenant, ou None s'il n'y a rien à
    changer. L'appelant joue ce nom comme un message `robot_lights` ordinaire.
    """

    def __init__(self, repos: str = REPOS) -> None:
        self.repos = repos
        self.explicite = False          # une commande explicite tient le corps
        self.lie: Optional[str] = None  # lumière actuellement posée par le visage
        self.corps_visage: Optional[str] = None  # lumière liée à l'expression en cours

    def commande(self, nom: object) -> None:
        """Message reçu sur `robot_lights`. Seul un NOM compte (la luminosité, un dict, ne
        change pas l'animation). Le repos ou « stop » libèrent le corps."""
        if not isinstance(nom, str):
            return
        self.explicite = nom not in (STOP, self.repos)
        self.lie = None

    def fin_commande(self) -> Optional[str]:
        """La lumière commandée est revenue au repos d'elle-même (fin d'une entrée non
        bouclée). Le corps reprend alors la lumière du visage en cours, s'il y en a une."""
        if not self.explicite:
            return None
        self.explicite = False
        return self._suivre()

    def visage(self, corps: Optional[str]) -> Optional[str]:
        """Le visage vient de changer d'expression ; `corps` est son champ (ou None)."""
        self.corps_visage = corps if isinstance(corps, str) and corps else None
        if self.explicite:
            return None
        return self._suivre()

    def _suivre(self) -> Optional[str]:
        if self.corps_visage is not None:
            if self.corps_visage == self.lie:
                return None
            self.lie = self.corps_visage
            return self.corps_visage
        if self.lie is not None:
            self.lie = None
            return STOP
        return None
