"""Le SCORE (ce qui est choisi) — spec A1 §3 point 5, poids §8.7.

score(action) = (Σ considération × poids) × gain(action) × facteur réfractaire
considérations dans [0, 1] :
  offre     : valeur × fraîcheur de l'offre dominante qui sert l'action ;
  pulsion   : la jauge servie (curiosité -> regard/approche, ennui -> expression
              spontanée, lubie -> arrêt réclamé) ;
  console   : 1 si l'ordre macro en cours (ou « joue avec ») vise cette action / cette cible.
facteur réfractaire : 0 avant la fin de la période réfractaire de la
catégorie de l'action, 1 après ; et 0 pour une initiative SPONTANÉE (ni
offre, ni console) moins de refractaire_s.initiative_spontanee après la
précédente. Un ORDRE de David (console « va là » / « reviens ») n'y est jamais
soumis (lot S1, 25/11 : fini le « trop tôt » opposé à un ordre).
Supprimés au lot S1 : la considération « metteur en scène » (mots-clés, cf.
selecteur) et la pression de route (la reprise ne passe plus par le score).
« rien » (l'immobilité) est candidat aussi : immobilite.base − pente × ennui.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from didier_jeu import phrases
from didier_jeu.offres import Offre

RIEN = "rien"
# Catégories réfractaires de chaque action (reglages refractaire_s.<catégorie>).
# « arret_didier » (revue A1, point 11) : tout arrêt de route causé par Didier
# — lubie, approche de sa propre initiative — au plus un par 120 s. Un ORDRE de
# David (considération console) n'est jamais un arrêt de Didier : il n'y est pas
# soumis. DÉCISION DE DAVID (15/11) : une demande de GESTE de la bouche non plus
# — elle vient toujours d'un humain (un tour spontané ne bouge jamais Didier,
# B1) ; sinon une tâche (« va voir l'éléphant, puis fais le tour du banc ») ne
# pouvait pas enchaîner deux gestes à moins de 2 min. Lot S1 (25/11) : c'est un
# ORDRE, exécuté sans score ; sa catégorie « deplacement » ne sert plus qu'à faire
# attendre les initiatives de Didier après lui.
ARRET_DIDIER = "arret_didier"
CATEGORIES = {
    "regarder": ("regarder",),
    "accueil": ("expression",),
    "spontanee": ("expression",),
    "approcher": ("deplacement", ARRET_DIDIER),
    "aller_voir": ("deplacement",),
    "bouche": ("deplacement",),
    "repartir": ("deplacement",),
    "lubie": (ARRET_DIDIER,),
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
    def categories(self) -> tuple:
        return CATEGORIES.get(self.action, ())

    def cle(self) -> str:
        """Identité pour l'hystérésis : même action, même cible. (Les gestes de la
        bouche, ordres sans score depuis le lot S1, n'y passent plus.)"""
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
    # {"action", "cible", "cmd", "ordre"?} : biais de l'ordre en cours (ordre=True) ou de « joue avec »
    console: Optional[Dict] = None
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
                     f"rien ne le pousse (immobilité {phrases.n(total)}) → {phrases.action(RIEN)}", False)
    poids = {k: reglages.get(f"poids.{k}") for k in ("offre", "pulsion", "console")}
    cons = {
        "offre": c.offre.valeur * c.offre.fraicheur(ctx.now) if c.offre is not None else 0.0,
        "pulsion": ctx.jauges.get(c.pulsion, 0.0) if c.pulsion else 0.0,
        "console": 1.0 if _vise_console(c, ctx.console) else 0.0,
    }
    spontanee = cons["offre"] == 0.0 and cons["console"] == 0.0
    ordre = bool(cons["console"]) and bool(ctx.console.get("ordre"))
    facteur, raison_ref = 1.0, ""
    for cat in c.categories:
        if ordre or (cat == ARRET_DIDIER and cons["console"]):
            continue   # ordre de David : jamais « trop tôt » (S1), jamais un arrêt de Didier
        if cat in ctx.derniers:
            periode = reglages.get(f"refractaire_s.{cat}") * ctx.tempo
            if ctx.now - ctx.derniers[cat] < periode - 1e-6:
                facteur, raison_ref = 0.0, f" (trop tôt : déjà fait il y a moins de {periode:g} s)"
    if spontanee and ctx.derniere_spontanee is not None:
        periode = reglages.get("refractaire_s.initiative_spontanee") * ctx.tempo
        if ctx.now - ctx.derniere_spontanee < periode - 1e-6:
            facteur, raison_ref = 0.0, f" (trop tôt : initiative il y a moins de {periode:g} s)"
    gain = reglages.gain(c.action)
    somme = sum(cons[k] * poids[k] for k in cons)
    total = somme * gain * facteur
    # Phrase lisible par David (revue A1, point 6) : raisons -> action.
    termes = []
    if cons["console"]:
        termes.append(f"David : {ctx.console.get('cmd') or 'consigne'}")
    if cons["offre"]:
        termes.append(phrases.offre(c.offre, cons["offre"]))
    if cons["pulsion"]:
        termes.append(phrases.pulsion(c.pulsion, cons["pulsion"]))
    pourquoi = " + ".join(termes) or "aucune raison"
    pourquoi += f" → {phrases.action(c.action, c.cible, c.detail)}" + raison_ref
    return Score(c, total, {k: round(v, 3) for k, v in cons.items()}, pourquoi, spontanee)


def classer(candidats: List[Candidat], ctx: Contexte, reglages) -> List[Score]:
    """Scores triés du meilleur au moins bon ; à égalité, ordre d'entrée
    (déterministe : le sélecteur construit les candidats dans un ordre fixe)."""
    scores = [score(c, ctx, reglages) for c in candidats]
    return sorted(scores, key=lambda s: -s.total)
