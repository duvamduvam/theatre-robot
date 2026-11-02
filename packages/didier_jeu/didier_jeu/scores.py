"""Le SCORE (ce qui est choisi) — spec A1 §3 point 5, poids §8.7.

score(action) = (Σ considération × poids) × gain(action) × facteur réfractaire
considérations dans [0, 1] :
  offre     : valeur × fraîcheur de l'offre dominante qui sert l'action ;
  pulsion   : la jauge servie (curiosité -> regard/approche, ennui -> expression
              spontanée, lubie -> arrêt réclamé, pression de route -> repartir) ;
  metteur   : 1 si l'indication fraîche du metteur en scène (mot-clé) désigne
              cette action ;
  console   : 1 si l'ordre macro en cours vise cette action / cette cible.
facteur réfractaire : 0 avant la fin de la période réfractaire de la
catégorie de l'action, 1 après ; et 0 pour une initiative SPONTANÉE (ni
offre, ni console) moins de refractaire_s.initiative_spontanee après la
précédente.
« rien » (l'immobilité) est candidat aussi : immobilite.base − pente × ennui.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from didier_jeu.offres import Offre

RIEN = "rien"
# Catégorie réfractaire de chaque action (reglages refractaire_s.<catégorie>).
CATEGORIES = {
    "regarder": "regarder",
    "accueil": "expression",
    "spontanee": "expression",
    "approcher": "deplacement",
    "aller_voir": "deplacement",
    "bouche": "deplacement",
    "repartir": "deplacement",
    "lubie": "arret_didier",
}
# Actions qui font bouger les ROUES (via le régisseur) : soumises à la
# fatigue, au superviseur, au verrou d'arrêt vocal.
DEPLACEMENTS = frozenset({"approcher", "aller_voir", "bouche", "repartir"})


@dataclass
class Candidat:
    action: str
    cible: Optional[str] = None
    offre: Optional[Offre] = None
    pulsion: Optional[str] = None          # nom de la jauge servie
    detail: Dict = field(default_factory=dict)

    @property
    def deplacement(self) -> bool:
        return self.action in DEPLACEMENTS

    @property
    def categorie(self) -> Optional[str]:
        return CATEGORIES.get(self.action)

    def cle(self) -> str:
        """Identité pour l'hystérésis : même action, même cible."""
        return f"{self.action}:{self.cible or ''}"


@dataclass
class Score:
    candidat: Candidat
    total: float
    considerations: Dict[str, float]
    pourquoi: str
    spontanee: bool


@dataclass
class Contexte:
    """Ce que le score lit du monde, figé pour un tick."""
    now: float
    jauges: Dict[str, float]               # pulsions (ennui, curiosite, lubie, fatigue, pression_route)
    metteur: Optional[str] = None          # action désignée par le metteur en scène (fraîche)
    console: Optional[Dict] = None         # {"action": ..., "cible": ...} biais de l'ordre en cours
    derniers: Dict[str, float] = field(default_factory=dict)   # catégorie -> t de la dernière action
    derniere_spontanee: Optional[float] = None
    tempo: float = 1.0                     # « plus lent » : réfractaires × tempo


def _vise_console(c: Candidat, console: Optional[Dict]) -> bool:
    if not console:
        return False
    action, cible = console.get("action"), console.get("cible")
    if action is not None and action != c.action:
        return False
    return cible is None or cible == c.cible


def score(c: Candidat, ctx: Contexte, reglages) -> Score:
    if c.action == RIEN:
        base = reglages.get("immobilite.base")
        pente = reglages.get("immobilite.pente_ennui")
        total = base - pente * ctx.jauges.get("ennui", 0.0)
        return Score(c, total, {"immobilite": round(total, 3)},
                     f"immobilité {base} − {pente}×ennui {ctx.jauges.get('ennui', 0.0):.2f}", False)
    poids = {k: reglages.get(f"poids.{k}") for k in ("offre", "pulsion", "metteur_en_scene", "console")}
    cons = {
        "offre": c.offre.valeur * c.offre.fraicheur(ctx.now) if c.offre is not None else 0.0,
        "pulsion": ctx.jauges.get(c.pulsion, 0.0) if c.pulsion else 0.0,
        "metteur_en_scene": 1.0 if ctx.metteur == c.action else 0.0,
        "console": 1.0 if _vise_console(c, ctx.console) else 0.0,
    }
    spontanee = cons["offre"] == 0.0 and cons["console"] == 0.0
    facteur, raison_ref = 1.0, ""
    cat = c.categorie
    if cat is not None and cat in ctx.derniers:
        periode = reglages.get(f"refractaire_s.{cat}") * ctx.tempo
        if ctx.now - ctx.derniers[cat] < periode - 1e-6:
            facteur, raison_ref = 0.0, f" ; réfractaire {cat} {periode:g} s"
    if spontanee and ctx.derniere_spontanee is not None:
        periode = reglages.get("refractaire_s.initiative_spontanee") * ctx.tempo
        if ctx.now - ctx.derniere_spontanee < periode - 1e-6:
            facteur, raison_ref = 0.0, f" ; réfractaire initiative spontanée {periode:g} s"
    gain = reglages.gain(c.action)
    somme = sum(cons[k] * poids[k] for k in cons)
    total = somme * gain * facteur
    termes = []
    if cons["offre"]:
        termes.append(f"offre:{c.offre.kind} {c.offre.piste} {cons['offre']:.2f}")
    if cons["pulsion"]:
        termes.append(f"{c.pulsion} {cons['pulsion']:.2f}")
    if cons["metteur_en_scene"]:
        termes.append("metteur en scène")
    if cons["console"]:
        termes.append("console")
    pourquoi = " + ".join(termes) or "aucune considération"
    pourquoi += f" ; gain {gain:g}" + raison_ref
    return Score(c, total, {k: round(v, 3) for k, v in cons.items()}, pourquoi, spontanee)


def classer(candidats: List[Candidat], ctx: Contexte, reglages) -> List[Score]:
    """Scores triés du meilleur au moins bon ; à égalité, ordre d'entrée
    (déterministe : le sélecteur construit les candidats dans un ordre fixe)."""
    scores = [score(c, ctx, reglages) for c in candidats]
    return sorted(scores, key=lambda s: -s.total)
