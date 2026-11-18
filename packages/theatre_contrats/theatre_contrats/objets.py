"""Contrat du TABLEAU DES OBJETS (lot O0, 18/11) — ce que Didier sait des objets EN CE MOMENT.

Étude : docs/etudes/etude-objets-vus-et-carte.md §6 (modèle cible), décisions de David du 18/11.
Panne d'origine (séance du 15/11, 21:29) : Didier vers x = 14 dit « le banc est là » et roule
22 m — la bouche, le sélecteur et la régie avaient chacun SA représentation des objets, sans
identifiant commun. Désormais : UN tableau, UN écrivain (`didier_perception/objets_node`),
quatre lecteurs (bouche, réflexion, sélecteur, régie) qui parlent du même objet par son `id`.

Ce module porte ce que tout le monde doit lire PAREIL : la forme d'un objet, l'encodage du
topic `scene/objets` (topics.SCENE_OBJETS), la clé de correspondance des noms
(`normaliser_nom`, LA seule du dépôt) et la résolution d'un nom dit (`resoudre`, §6.3). La
logique de l'ÉCRIVAIN (fusion des sources, noms uniques, péremption, champ de la caméra,
règle `atteignable`) vit dans `didier_perception.tableau` : les lecteurs ne recalculent
JAMAIS une distance, un azimut ni l'atteignabilité — ils lisent les champs.

Encodage : StringTime LATCHÉ (qos.latched() des DEUX côtés), msg = JSON
    {"v": 1, "t_ms": <horloge murale de l'écrivain>,
     "pose": {"repere", "x", "y", "cap_deg"} | null,
     "objets": [<objet>, …]}   trié par distance croissante (inconnue en dernier)
Pourquoi du JSON et pas un message typé (règle du 11/11, README) : le tableau est un ÉTAT
SÉMANTIQUE (noms, descriptions, sources) destiné à des modèles de langage et au sélecteur, de
même nature que `rehearsal/objects` ; les MESURES (pose, et demain lidar et caméra) restent
typées en amont de l'écrivain. Un message typé imposerait de reconstruire theatre_interfaces
partout pour un état que personne ne trace. À rouvrir si un outil doit le tracer.

Un objet (§6.2) : {"id", "nom", "desc", "alias", "sources", "repere", "x", "y", "sigma_m",
"azimut_deg", "distance_m", "cote", "en_vue", "vu_il_y_a_s", "tour", "atteignable"} ;
`x`, `y`, `azimut_deg`, `distance_m`, `cote`, `vu_il_y_a_s` peuvent valoir null (position
tombée, pose inconnue, jamais vu). Python PUR, stdlib seulement.
"""
import json
import math
import unicodedata
from dataclasses import dataclass, field
from typing import Optional, Tuple

VERSION = 1
SOURCES = ("carte", "vu")
# monde = carte (sim, lieu préparé) ; odom = vu, robot doté d'une odométrie ; robot = vu, robot
# SANS odométrie (position relative au robot tant qu'il ne bouge pas — jamais une cible).
REPERES = ("monde", "odom", "robot")
COTES = ("devant", "gauche", "droite", "derriere")
# Portée d'un déplacement vers un objet (m) : la borne posée le 15/11, désormais À UN SEUL
# ENDROIT (§6.5) — l'écrivain s'en sert pour `atteignable`, `resoudre` pour « à portée ».
PORTEE_M = 10.0

# Statuts de `resoudre` (§6.3).
ICI = "ici"            # en vue ou à portée : on peut en parler comme de « celui-là »
PAS_ICI = "pas_ici"    # connu (carte, ou vu plus tôt) mais ni en vue ni à portée
INCONNU = "inconnu"

# Plafonds du décodeur : le tableau part au LLM, un écrivain fou ne doit pas le noyer.
OBJETS_MAX = 64
NOM_MAX_CHARS = 40
DESC_MAX_CHARS = 60

# Articles retirés EN TÊTE par normaliser_nom (« les anneaux », « l'eau ») — jamais au milieu.
ARTICLES = frozenset(("le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "au", "aux"))


def normaliser_nom(texte) -> str:
    """Clé de correspondance d'un nom d'objet : minuscules, sans accents, ponctuation et `_` en
    espaces, articles de tête retirés. « Les Anneaux ! » -> "anneaux" ; "table_basse" ->
    "table basse" ; « l'eau » -> "eau". Non-chaîne -> "" (le texte vient souvent d'un LLM).
    LA clé du dépôt : route.normalize_name (régie) et stage.normalize_object_name (bouche) en
    sont des alias depuis O0 — deux copies avaient fini « gravées des deux côtés »."""
    if not isinstance(texte, str):
        return ""
    decompose = unicodedata.normalize("NFKD", texte.lower())
    plat = "".join(c for c in decompose if not unicodedata.combining(c))
    mots = "".join(c if c.isalnum() else " " for c in plat).split()
    while mots and mots[0] in ARTICLES:
        mots.pop(0)
    return " ".join(mots)


def cote(azimut_deg: float) -> str:
    """Côté d'un azimut RELATIF (°, + = gauche, REP 103) : devant si |a| ≤ 45, gauche jusqu'à
    135, droite jusqu'à −135, derrière sinon. Le même découpage pour l'écrivain et les phrases."""
    if abs(azimut_deg) <= 45.0:
        return "devant"
    if 45.0 < azimut_deg <= 135.0:
        return "gauche"
    if -135.0 <= azimut_deg < -45.0:
        return "droite"
    return "derriere"


@dataclass(frozen=True)
class Objet:
    id: str
    nom: str
    desc: str = ""
    alias: Tuple[str, ...] = ()
    sources: Tuple[str, ...] = ("carte",)
    repere: str = "monde"
    x: Optional[float] = None
    y: Optional[float] = None
    sigma_m: float = 0.0
    azimut_deg: Optional[float] = None
    distance_m: Optional[float] = None
    cote: Optional[str] = None
    en_vue: bool = False
    vu_il_y_a_s: Optional[float] = None
    tour: bool = False
    atteignable: bool = False

    @property
    def a_portee(self) -> bool:
        """À portée d'un déplacement (distance connue ≤ PORTEE_M), qu'il soit en vue ou non."""
        return self.distance_m is not None and self.distance_m <= PORTEE_M

    @property
    def ici(self) -> bool:
        return self.en_vue or self.a_portee

    def cles(self) -> frozenset:
        """Clés normalisées par lesquelles on peut le désigner (nom + alias)."""
        return frozenset(k for k in (normaliser_nom(t) for t in (self.nom,) + self.alias) if k)

    def en_dict(self) -> dict:
        return {"id": self.id, "nom": self.nom, "desc": self.desc, "alias": list(self.alias),
                "sources": list(self.sources), "repere": self.repere, "x": self.x, "y": self.y,
                "sigma_m": self.sigma_m, "azimut_deg": self.azimut_deg, "distance_m": self.distance_m,
                "cote": self.cote, "en_vue": self.en_vue, "vu_il_y_a_s": self.vu_il_y_a_s,
                "tour": self.tour, "atteignable": self.atteignable}


@dataclass(frozen=True)
class Pose:
    repere: str
    x: float
    y: float
    cap_deg: float


@dataclass(frozen=True)
class Resolution:
    statut: str                       # ICI | PAS_ICI | INCONNU
    objet: Optional[Objet] = None


@dataclass(frozen=True)
class Tableau:
    objets: Tuple[Objet, ...] = ()
    pose: Optional[Pose] = None
    t_ms: int = 0
    rejetes: int = 0                  # objets illisibles écartés au décodage (journalisés par le lecteur)
    _par_id: dict = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self):
        self._par_id.update({o.id: o for o in self.objets})

    def par_id(self, id_) -> Optional[Objet]:
        return self._par_id.get(id_) if isinstance(id_, str) else None

    def resoudre(self, texte) -> Resolution:
        return resoudre(self, texte)


VIDE = Tableau()


def resoudre(tableau: Tableau, texte) -> Resolution:
    """Règle UNIQUE « le banc dont on parle, c'est lequel ? » (§6.3, étapes 1, 3 et 4 ; l'étape 2,
    la désignation à la demande par la caméra, arrive avec O2) :
      1. correspondance normalisée EXACTE sur le nom et les alias (ou l'`id` tel quel), parmi les
         objets en vue ou à portée ; plusieurs -> le plus proche de l'axe du regard ;
      3. sinon, connu mais loin ou hors champ -> PAS_ICI avec le plus proche (sa distance et son
         côté sont dans l'objet : Didier peut le DIRE, il ne part pas) ;
      4. sinon INCONNU. Rien de flou : un nom mal compris n'est jamais deviné."""
    if isinstance(texte, str) and texte in tableau._par_id:
        o = tableau._par_id[texte]
        return Resolution(ICI if o.ici else PAS_ICI, o)
    cle = normaliser_nom(texte)
    if not cle:
        return Resolution(INCONNU)
    candidats = [o for o in tableau.objets if cle in o.cles()]
    if not candidats:
        return Resolution(INCONNU)
    ici = [o for o in candidats if o.ici]
    if ici:
        return Resolution(ICI, min(ici, key=lambda o: (abs(o.azimut_deg) if o.azimut_deg is not None
                                                        else 999.0, o.id)))
    return Resolution(PAS_ICI, min(candidats, key=lambda o: (o.distance_m if o.distance_m is not None
                                                             else math.inf, o.id)))


# ================================================================ encodage
def encoder(objets, pose: Optional[Pose], t_ms: int) -> str:
    """Payload StringTime de `scene/objets` (forme en tête de module). `objets` : Objet."""
    return json.dumps({"v": VERSION, "t_ms": int(t_ms),
                       "pose": None if pose is None else {"repere": pose.repere, "x": pose.x, "y": pose.y,
                                                          "cap_deg": pose.cap_deg},
                       "objets": [o.en_dict() for o in objets]}, ensure_ascii=False)


def _nombre(v) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def _texte(v, plafond) -> Optional[str]:
    return v.strip()[:plafond] if isinstance(v, str) and v.strip() else None


def _objet(d) -> Optional[Objet]:
    """dict du fil -> Objet, ou None si un champ OBLIGATOIRE est faux. Les champs facultatifs
    faux retombent sur leur valeur SÛRE (pas de position, pas en vue, pas atteignable)."""
    if not isinstance(d, dict):
        return None
    id_, nom = _texte(d.get("id"), 80), _texte(d.get("nom"), NOM_MAX_CHARS)
    sources = d.get("sources")
    if id_ is None or nom is None or d.get("repere") not in REPERES or not isinstance(sources, list) \
            or not sources or any(s not in SOURCES for s in sources):
        return None
    alias = d.get("alias")
    alias = tuple(a.strip()[:NOM_MAX_CHARS] for a in alias if isinstance(a, str) and a.strip()) \
        if isinstance(alias, list) else ()
    x, y = _nombre(d.get("x")), _nombre(d.get("y"))
    if x is None or y is None:
        x = y = None
    sigma = _nombre(d.get("sigma_m"))
    distance = _nombre(d.get("distance_m"))
    azimut = _nombre(d.get("azimut_deg"))
    if distance is None or distance < 0 or azimut is None:
        distance = azimut = None
    vu = _nombre(d.get("vu_il_y_a_s"))
    return Objet(id=id_, nom=nom, desc=_texte(d.get("desc"), DESC_MAX_CHARS) or "", alias=alias,
                 sources=tuple(sources), repere=d["repere"], x=x, y=y,
                 sigma_m=sigma if sigma is not None and sigma >= 0 else math.inf,
                 azimut_deg=azimut, distance_m=distance,
                 cote=d.get("cote") if d.get("cote") in COTES and distance is not None else None,
                 en_vue=d.get("en_vue") is True, vu_il_y_a_s=vu if vu is not None and vu >= 0 else None,
                 tour=d.get("tour") is True,
                 # Défaut SÛR : atteignable exige une position et une distance lisibles.
                 atteignable=d.get("atteignable") is True and x is not None and distance is not None)


def decoder(raw) -> Tableau:
    """Payload de `scene/objets` -> Tableau. ValueError si l'ENVELOPPE est fausse (le lecteur
    garde alors son tableau précédent et le journalise) ; un objet illisible est écarté et
    compté (`rejetes`), les autres passent. Ids en double : le premier gagne (compté)."""
    try:
        v = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"scene/objets illisible (objet JSON attendu) : {raw!r:.120}") from exc
    if not isinstance(v, dict) or v.get("v") != VERSION or not isinstance(v.get("objets"), list):
        raise ValueError(f"scene/objets : enveloppe v{VERSION} attendue : {raw!r:.120}")
    p = v.get("pose")
    pose = None
    if isinstance(p, dict) and p.get("repere") in REPERES:
        nombres = [_nombre(p.get(k)) for k in ("x", "y", "cap_deg")]
        if None not in nombres:
            pose = Pose(p["repere"], *nombres)
    objets, vus, rejetes = [], set(), 0
    for d in v["objets"][:OBJETS_MAX]:
        o = _objet(d)
        if o is None or o.id in vus:
            rejetes += 1
            continue
        vus.add(o.id)
        objets.append(o)
    rejetes += max(0, len(v["objets"]) - OBJETS_MAX)
    t_ms = v.get("t_ms") if isinstance(v.get("t_ms"), int) and not isinstance(v.get("t_ms"), bool) else 0
    return Tableau(tuple(objets), pose, t_ms, rejetes)


# ================================================================ phrases (bouche, réflexion, refus)
COTES_PHRASE = {"devant": "devant toi", "gauche": "sur ta gauche", "droite": "sur ta droite",
                "derriere": "derrière toi"}


def ou_dit(o: Objet) -> str:
    """« à 22 m devant toi » / « à moins d'un mètre sur ta gauche » ; "" sans distance connue."""
    if o.distance_m is None or o.cote is None:
        return ""
    loin = "à moins d'un mètre" if o.distance_m < 1.0 else f"à {round(o.distance_m):d} m"
    return f"{loin} {COTES_PHRASE[o.cote]}"
