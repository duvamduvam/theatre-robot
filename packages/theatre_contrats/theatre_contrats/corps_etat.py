"""Contrat de l'ÉTAT DU CORPS (lot S2a, 27/11) — ce que le corps de Didier fait EN CE MOMENT, et pourquoi.

Spec : docs/spec-S2-le-corps-raconte.md §2. Vécu d'origine (séances des 24-26/11) : la bouche disait
« ça y est, je fonce vers la grue » après un go refusé, « la flaque est derrière moi » à tort, parlait
de la grue au banc — chacun devinait l'état du corps depuis SES abonnements (route_state, vitesse,
POI). Désormais : UN état, UN écrivain (le sélecteur de jeu, didier_jeu), des lecteurs (bouche,
réflexion, page scène, journal du jeu) qui lisent la même phrase.

Ce module porte ce que tout le monde doit lire PAREIL : les valeurs du contrat, la RÈGLE qui choisit
la marche et l'unique cause (`etablir`), le lieu (`ici_depuis`, depuis le tableau des objets), la
phrase (`composer`, textes GRAVÉS en test) et l'encodage du topic `corps/etat`
(topics.CORPS_ETAT). L'écrivain ne fait que rassembler les faits (`Faits`) ; il ne compose rien.

Encodage : StringTime LATCHÉ (qos.latched() des DEUX côtés, profondeur 1), msg = JSON
    {"v": 1, "t_ms": <horloge de l'écrivain>, "marche", "cause", "qui_relance", "repart_dans_s",
     "geste": null | {"demande", "etat", "raison", "parcouru_m"},
     "ici": {"sur": <nom> | null, "proches": [{"nom", "cote", "distance_m"}]}, "phrase"}
republié à chaque changement (`cle`) et AU PLUS TARD toutes les PERIODE_MAX_S : un lecteur qui
n'a rien reçu depuis PEREMPTION_S tient l'état pour INCONNU (`lire`), jamais pour le dernier vu.

Règles (spec §2, gravées par test) : jamais deux causes (un seul champ, choisi par priorité) ;
le corps sûr passe avant tout le reste ; une source qui manque -> état INCONNU (`marche: empeche`,
`cause: aucune`, « Tu ne sais pas où en est ton corps. ») — jamais un état deviné.

Interprétations écrites (S2a, 27/11 ; la spec ne les tranche pas, sens le plus sûr) :
- « source muette plus de 3 s » : `corps_sur/etat`, `route_state` et `rehearsal/state` ne sont
  publiés qu'au CHANGEMENT (latchés) — leur silence ne prouve rien. La péremption de 3 s porte donc
  sur `corps/etat` lui-même, chez ses lecteurs (`lire`) ; chez l'écrivain, une source JAMAIS reçue
  (ou illisible) rend l'état inconnu, et le tableau des objets garde sa propre péremption
  (objets.PEREMPTION_S, déjà appliquée par le sélecteur : `ici` vide) ;
- les noms d'objets n'ont pas d'article (« flaque », « grue_jaune ») : la phrase les cite entre
  guillemets (« Tu traverses : « flaque ». ») plutôt que d'inventer un genre (« le flaque ») ;
- `qui_relance` vaut null quand rien n'est à relancer (en route, en plein geste) ;
- `sur` : objet dont la distance au centre est ≤ son emprise + SUR_MARGE_M ; emprise inconnue -> 0
  (on ne prétend être sur un objet que de près) ; `proches` : à portée (objets.PORTEE_M), côté connu.
Python PUR, stdlib seulement.
"""
import json
import math
from dataclasses import dataclass
from typing import Optional, Tuple

from theatre_contrats import objets

VERSION = 1

# ---------------------------------------------------------------- valeurs du contrat
EN_ROUTE, ARRETE, GESTE, EMPECHE = "en_route", "arrete", "geste", "empeche"
MARCHES = (EN_ROUTE, ARRETE, GESTE, EMPECHE)

DAVID_STOP_VOIX = "david_stop_voix"
DAVID_STOP_CONSOLE = "david_stop_console"
DAVID_ROUTE_OFF = "david_route_off"
DIDIER_LUBIE = "didier_lubie"
DIDIER_PAUSE = "didier_pause"
DIDIER_STOP = "didier_stop"
GESTE_FINI = "geste_fini"
CORPS_SUR_VERROU = "corps_sur_verrou"
CORPS_SUR_ZONE = "corps_sur_zone"
SEANCE_NON_LANCEE = "seance_non_lancee"
AUCUNE = "aucune"
CAUSES = (DAVID_STOP_VOIX, DAVID_STOP_CONSOLE, DAVID_ROUTE_OFF, DIDIER_LUBIE, DIDIER_PAUSE, DIDIER_STOP,
          GESTE_FINI, CORPS_SUR_VERROU, CORPS_SUR_ZONE, SEANCE_NON_LANCEE, AUCUNE)
# Causes d'une REPRISE armée du sélecteur (Didier s'est arrêté de lui-même et repartira seul).
REPRISES = (DIDIER_LUBIE, DIDIER_PAUSE, DIDIER_STOP, GESTE_FINI)

QUI_DAVID_CONSOLE, QUI_DAVID, QUI_DIDIER, QUI_PERSONNE = "david_console", "david", "didier", "personne"
QUI_RELANCE = (QUI_DAVID_CONSOLE, QUI_DAVID, QUI_DIDIER, QUI_PERSONNE)

GESTE_EN_COURS, GESTE_ARRIVE, GESTE_ABANDONNE, GESTE_REFUSE = "en_cours", "arrive", "abandonne", "refuse"
GESTE_ETATS = (GESTE_EN_COURS, GESTE_ARRIVE, GESTE_ABANDONNE, GESTE_REFUSE)

# Genres du verrou de David (lot S1, R3) : littéraux GRAVÉS avec didier_jeu.relais (test du jeu).
VERROU_CONSOLE, VERROU_ROUTE, VERROU_VOIX = "console", "route", "voix"
VERROU_CAUSE = {VERROU_CONSOLE: (DAVID_STOP_CONSOLE, QUI_DAVID_CONSOLE),
                VERROU_ROUTE: (DAVID_ROUTE_OFF, QUI_DAVID_CONSOLE),
                VERROU_VOIX: (DAVID_STOP_VOIX, QUI_DAVID)}

# Corps sûr (`corps_sur/etat`, didier_corps_sur.moteur.etat) : littéraux GRAVÉS avec
# didier_corps_sur.garde et .zones (test qui relit les vrais fichiers). VERROU et DEMARRAGE : rien
# ne bouge tant qu'il n'est pas armé ; zone ARRET (obstacle trop près) ou PAUSE_DUREE (mouvement trop
# long) : il retient les roues, l'état restant ARME.
CORPS_SUR_ETATS = ("DEMARRAGE", "ARME", "VERROU")
CORPS_SUR_ETATS_VERROU = ("DEMARRAGE", "VERROU")
CORPS_SUR_ZONES = ("LIBRE", "RALENTI", "ARRET", "PAUSE_DUREE")
CORPS_SUR_ZONES_ARRET = ("ARRET", "PAUSE_DUREE")

# Chiffres du contrat (spec §2).
PHRASE_MAX_CHARS = 300
PHRASES_MAX = 3
PEREMPTION_S = 3.0          # lecteurs : plus rien reçu depuis -> INCONNU
PERIODE_MAX_S = 2.0         # écrivain : republication au plus tard
GESTE_MEMOIRE_S = 60.0      # le dernier geste fini reste dit pendant
SUR_MARGE_M = 0.5           # « sur » un objet : distance ≤ emprise + marge
PROCHES_MAX = 2

PHRASE_INCONNU = "Tu ne sais pas où en est ton corps."


# ---------------------------------------------------------------- formes
@dataclass(frozen=True)
class Proche:
    nom: str
    cote: str                       # objets.COTES
    distance_m: float


@dataclass(frozen=True)
class Ici:
    sur: Optional[str] = None
    proches: Tuple[Proche, ...] = ()


@dataclass(frozen=True)
class Geste:
    """Le dernier geste (spec §2) : `demande` = le payload chat_move tel qu'il est parti."""
    demande: object
    etat: str                       # GESTE_ETATS
    raison: Optional[str] = None
    parcouru_m: Optional[float] = None


@dataclass(frozen=True)
class CorpsSur:
    """Ce que le sélecteur retient de `corps_sur/etat`."""
    etat: str
    zone: Optional[str] = None
    cause: str = ""

    @property
    def verrouille(self) -> bool:
        """Rien ne bouge (VERROU, ou pas encore armé) : un ordre de David y est refusé « corps_sur »."""
        return self.etat in CORPS_SUR_ETATS_VERROU

    @property
    def retient(self) -> bool:
        return self.zone in CORPS_SUR_ZONES_ARRET


@dataclass(frozen=True)
class Faits:
    """Ce que l'écrivain sait, rassemblé tel quel (aucune déduction chez lui) :
    `route_state` None = jamais reçu ; `corps_sur` None = jamais reçu ou illisible ;
    `seance_connue` False = rehearsal/state jamais reçu ou illisible ; `verrou` = genre du verrou
    de David (VERROU_*) ou None ; `reprise` = cause de la reprise armée (REPRISES) ou None ;
    `geste_en_cours` = un déplacement engagé roule ou attend sa réponse."""
    route_state: Optional[str] = None
    corps_sur: Optional[CorpsSur] = None
    seance_connue: bool = False
    en_seance: bool = False
    arret_vocal: bool = False
    verrou: Optional[str] = None
    reprise: Optional[str] = None
    reprise_cible: Optional[str] = None
    repart_dans_s: Optional[float] = None
    geste_en_cours: bool = False
    geste: Optional[Geste] = None
    ici: Ici = Ici()


@dataclass(frozen=True)
class EtatCorps:
    marche: str
    cause: str
    qui_relance: Optional[str]
    repart_dans_s: Optional[float]
    geste: Optional[Geste]
    ici: Ici
    phrase: str

    def en_dict(self) -> dict:
        g = self.geste
        return {"marche": self.marche, "cause": self.cause, "qui_relance": self.qui_relance,
                "repart_dans_s": self.repart_dans_s,
                "geste": None if g is None else {"demande": g.demande, "etat": g.etat, "raison": g.raison,
                                                 "parcouru_m": g.parcouru_m},
                "ici": {"sur": self.ici.sur, "proches": [{"nom": p.nom, "cote": p.cote, "distance_m": p.distance_m}
                                                         for p in self.ici.proches]},
                "phrase": self.phrase}


INCONNU = EtatCorps(EMPECHE, AUCUNE, None, None, None, Ici(), PHRASE_INCONNU)


# ---------------------------------------------------------------- la règle
def etablir(f: Faits) -> EtatCorps:
    """Marche et UNIQUE cause, par priorité (spec §2) : source manquante -> INCONNU ; corps sûr
    (verrou, puis zone) ; verrou de David (son genre) ; geste en cours (un ordre de David peut
    partir sur une reprise armée : il roule, il n'attend plus) ; reprise armée ; hors séance et à
    l'arrêt ; en route ; sinon arrêté sans cause connue (seul un go de David le relance).
    ValueError sur un genre de verrou ou une reprise hors contrat (erreur de l'écrivain)."""
    if f.route_state is None or f.corps_sur is None or not f.seance_connue:
        return INCONNU
    repart = None
    if f.corps_sur.verrouille:
        marche, cause, qui = EMPECHE, CORPS_SUR_VERROU, QUI_PERSONNE
    elif f.corps_sur.retient:
        marche, cause, qui = EMPECHE, CORPS_SUR_ZONE, QUI_PERSONNE
    elif f.verrou is not None:
        if f.verrou not in VERROU_CAUSE:
            raise ValueError(f"genre de verrou hors contrat : {f.verrou!r}")
        marche, (cause, qui) = ARRETE, VERROU_CAUSE[f.verrou]
    elif f.geste_en_cours or f.route_state == "goto":
        marche, cause, qui = GESTE, AUCUNE, None
    elif f.reprise is not None:
        if f.reprise not in REPRISES:
            raise ValueError(f"cause de reprise hors contrat : {f.reprise!r}")
        marche, cause, qui = ARRETE, f.reprise, QUI_DIDIER
        repart = None if f.repart_dans_s is None else round(max(0.0, f.repart_dans_s), 1)
    elif f.route_state == "on" and not f.arret_vocal:
        marche, cause, qui = EN_ROUTE, AUCUNE, None
    elif not f.en_seance:
        marche, cause, qui = EMPECHE, SEANCE_NON_LANCEE, QUI_DAVID_CONSOLE
    else:
        marche, cause, qui = ARRETE, AUCUNE, QUI_DAVID
    phrase = composer(marche, cause, repart, f.geste, f.ici, f.reprise_cible)
    return EtatCorps(marche, cause, qui, repart, f.geste, f.ici, phrase)


def ici_depuis(tableau) -> Ici:
    """`ici` depuis un objets.Tableau (déjà PÉRIMÉ par son lecteur s'il le faut) : `sur` = le plus
    proche objet à moins de son emprise + SUR_MARGE_M ; `proches` = les PROCHES_MAX plus proches
    autres objets à portée dont le côté est connu. Rien n'est recalculé : distances et côtés sont
    ceux de l'écrivain du tableau."""
    connus = sorted((o for o in tableau.objets if o.distance_m is not None),
                    key=lambda o: (o.distance_m, o.id))
    sur = next((o for o in connus if o.distance_m <= (o.emprise_m or 0.0) + SUR_MARGE_M), None)
    proches = tuple(Proche(o.nom, o.cote, round(o.distance_m, 1)) for o in connus
                    if o is not sur and o.a_portee and o.cote in objets.COTES)[:PROCHES_MAX]
    return Ici(sur.nom if sur is not None else None, proches)


def cle(etat: EtatCorps) -> tuple:
    """Ce dont un CHANGEMENT republie tout de suite : tout sauf les nombres qui glissent (reste de
    la reprise, distances, parcours) — ceux-là suivent à la republication suivante (≤ 2 s)."""
    g = etat.geste
    return (etat.marche, etat.cause, etat.qui_relance,
            None if g is None else (json.dumps(g.demande, sort_keys=True, ensure_ascii=False), g.etat, g.raison),
            etat.ici.sur, tuple((p.nom, p.cote) for p in etat.ici.proches))


# ---------------------------------------------------------------- la phrase (textes gravés en test)
REPART = "Tu repars dans {n} s si personne ne parle."
REPART_SANS_DELAI = "Tu repartiras seul après un silence."
PHRASES_CAUSE = {
    DAVID_STOP_VOIX: ("Tu es arrêté : David t'a dit stop.", "Seul un go de David te relance."),
    DAVID_STOP_CONSOLE: ("Tu es arrêté : David t'a arrêté à la console.", "Seul son bouton GO te relance."),
    DAVID_ROUTE_OFF: ("Tu es arrêté : David a coupé ta route.", "Seul David la relance, sur la page."),
    DIDIER_LUBIE: ("Tu es arrêté, attiré par « {cible} » : c'est toi qui t'es arrêté.", REPART),
    DIDIER_PAUSE: ("Tu es arrêté pour regarder : c'est toi qui t'es arrêté.", REPART),
    DIDIER_STOP: ("Tu es arrêté : c'est toi qui t'es arrêté.", REPART),
    GESTE_FINI: ("Tu es arrêté : ton geste est fini.", REPART),
    CORPS_SUR_VERROU: ("Tu ne peux pas bouger : ton corps est verrouillé par sécurité.",
                       "Il faut le réarmer avant tout."),
    CORPS_SUR_ZONE: ("Tu ne peux pas avancer : ta sécurité te retient.", "Tu repars dès qu'elle te laisse."),
    SEANCE_NON_LANCEE: ("Tu ne peux pas bouger : la séance n'est pas lancée.",
                        "David peut la démarrer sur la page."),
}
PHRASE_EN_ROUTE = "Tu roules sur ta route."
PHRASE_GESTE = "Tu es en plein geste : {geste}."
PHRASE_GESTE_SANS_DEMANDE = "Tu es en pleine manœuvre."
PHRASE_ARRETE = ("Tu es arrêté.", "Seul un go de David te relance.")
# Raison d'un geste fini sans arriver (codes de chat_move_reply et de route_goto_result, et ceux du
# sélecteur : « annule », « sans_suite », « timeout ») ; inconnue -> RAISON_INCONNUE.
RAISONS_GESTE = {
    "corps_sur": "ton corps est verrouillé par sécurité",
    "arrete": "tu étais arrêté par David",
    "arret_de_david": "tu étais arrêté par David",
    "sans_superviseur": "personne ne te surveillait",
    "pas_ici": "ce n'est pas ici",
    "hors_atteinte": "c'est trop loin pour un seul geste",
    "hors_seance": "la séance n'était pas lancée",
    "sans_suite": "personne n'a donné suite",
    "annule": "on t'a arrêté en route",
    "cancelled": "on t'a arrêté en route",
    "unknown": "tu ne connais pas cet objet ici",
    "no_position": "tu ne sais pas où il est",
    "no_tour": "il n'y a pas la place d'en faire le tour",
    "too_far": "c'est trop loin",
    "no_pose": "tu ne savais pas où tu étais",
    "route_off_by_david": "David a coupé ta route",
    "invalid": "la demande était incompréhensible",
    "timeout": "il a duré trop longtemps",
    "stalled": "tu étais bloqué",
    "max_travel": "tu as fait trop de chemin sans arriver",
}
RAISON_INCONNUE = "pour une raison que tu ne connais pas"
COTES_TETE = {"devant": "devant toi", "gauche": "sur ta gauche", "droite": "sur ta droite",
              "derriere": "derrière toi"}


def nom_plat(nom) -> str:
    """Un nom d'objet en mots : « grue_jaune » -> « grue jaune » ; plafonné comme un nom du tableau
    (objets.NOM_MAX_CHARS) : il peut venir d'un autre processus (demande d'un geste)."""
    return str(nom).replace("_", " ").strip()[:objets.NOM_MAX_CHARS]


def nom_dit(nom) -> str:
    """Un nom d'objet tel que la phrase le cite, entre guillemets (pas d'article inventé)."""
    return f"« {nom_plat(nom)} »"


def _nombre(v) -> Optional[float]:
    return objets.nombre_fini(v)


def _metres(v: float) -> str:
    return f"{v:.1f}".replace(".", ",") + " m"


def geste_dit(demande) -> str:
    """La demande d'un geste en mots (« aller voir « banc » », « tourner de 90° à gauche ») ;
    "un geste" si elle est illisible (le payload vient d'un autre processus)."""
    if not isinstance(demande, dict):
        return "un geste"
    cmd, objet = demande.get("cmd"), demande.get("objet")
    if cmd == "aller_voir" and isinstance(objet, str):
        return f"aller voir {nom_dit(objet)}"
    if cmd == "tour_de" and isinstance(objet, str):
        return f"faire le tour de {nom_dit(objet)}"
    angle = _nombre(demande.get("angle_deg"))
    if cmd == "tourner" and angle is not None and angle != 0:
        return f"tourner de {abs(angle):g}° à {'gauche' if angle > 0 else 'droite'}"
    metres = _nombre(demande.get("metres"))
    if cmd == "avancer" and metres is not None:
        return f"avancer de {_metres(metres)}"
    return "un geste"


def _phrase_geste(g: Geste) -> Optional[str]:
    """Le dernier geste FINI en une phrase (le geste en cours est dit par la marche)."""
    quoi = f"Ton dernier geste ({geste_dit(g.demande)})"
    raison = RAISONS_GESTE.get(g.raison, RAISON_INCONNUE) if isinstance(g.raison, str) else RAISON_INCONNUE
    apres = "" if g.parcouru_m is None else f" après {_metres(g.parcouru_m)}"
    if g.etat == GESTE_ARRIVE:
        return f"{quoi} est fini : tu es arrivé{apres}."
    if g.etat == GESTE_ABANDONNE:
        return f"{quoi} a été abandonné{apres} : {raison}."
    if g.etat == GESTE_REFUSE:
        return f"{quoi} a été refusé, tu n'as pas bougé : {raison}."
    return None


def _phrases_ici(ici: Ici, en_mouvement: bool) -> list:
    out = []
    if ici.sur is not None:
        out.append(f"{'Tu traverses' if en_mouvement else 'Tu es dessus ou tout contre'} : {nom_dit(ici.sur)}.")
    morceaux = []
    for p in ici.proches:
        loin = "à moins d'un mètre" if p.distance_m < 1.0 else f"à {round(p.distance_m):d} m"
        morceaux.append(f"{COTES_TETE.get(p.cote, 'près de toi')} {loin} : {nom_dit(p.nom)}")
    if morceaux:
        texte = " ; ".join(morceaux)
        out.append(texte[0].upper() + texte[1:] + ".")
    return out


def composer(marche: str, cause: str, repart_dans_s: Optional[float] = None, geste: Optional[Geste] = None,
             ici: Ici = Ici(), reprise_cible: Optional[str] = None) -> str:
    """La phrase (spec §2) : une à PHRASES_MAX phrases, PHRASE_MAX_CHARS au plus. Ordre de
    priorité : l'état et sa cause, le dernier geste fini, l'objet sous Didier, les objets proches —
    ce qui déborde est retiré par la FIN, jamais coupé au milieu d'une phrase."""
    if marche not in MARCHES or cause not in CAUSES:
        raise ValueError(f"marche/cause hors contrat : {marche!r}/{cause!r}")
    if cause in PHRASES_CAUSE:
        n = None if repart_dans_s is None else max(0, round(repart_dans_s))
        cible = nom_plat(reprise_cible) if reprise_cible else "quelque chose"
        phrases = [p.replace("{cible}", cible) for p in PHRASES_CAUSE[cause]]
        if phrases[-1] == REPART:
            phrases[-1] = REPART_SANS_DELAI if n is None else REPART.format(n=n)
    elif marche == EN_ROUTE:
        phrases = [PHRASE_EN_ROUTE]
    elif marche == GESTE:
        en_cours = geste is not None and geste.etat == GESTE_EN_COURS
        phrases = [PHRASE_GESTE.format(geste=geste_dit(geste.demande)) if en_cours else PHRASE_GESTE_SANS_DEMANDE]
    else:
        phrases = list(PHRASE_ARRETE)
    if geste is not None and marche != GESTE:
        dit = _phrase_geste(geste)
        if dit is not None:
            phrases.append(dit)
    phrases += _phrases_ici(ici, marche in (EN_ROUTE, GESTE))
    phrases = phrases[:PHRASES_MAX]
    while len(phrases) > 1 and len(" ".join(phrases)) > PHRASE_MAX_CHARS:
        phrases.pop()
    texte = " ".join(phrases)
    return texte if len(texte) <= PHRASE_MAX_CHARS else texte[:PHRASE_MAX_CHARS - 1] + "…"


# ---------------------------------------------------------------- encodage
def encoder(etat: EtatCorps, t_ms: int) -> str:
    """Payload StringTime de `corps/etat` (forme en tête de module)."""
    return json.dumps(dict({"v": VERSION, "t_ms": int(t_ms)}, **etat.en_dict()), ensure_ascii=False)


def _geste_lu(d) -> Optional[Geste]:
    if not isinstance(d, dict) or d.get("etat") not in GESTE_ETATS:
        return None
    raison = d.get("raison") if isinstance(d.get("raison"), str) else None
    parcouru = _nombre(d.get("parcouru_m"))
    return Geste(d.get("demande"), d["etat"], raison, parcouru if parcouru is not None and parcouru >= 0 else None)


def _ici_lu(d) -> Ici:
    if not isinstance(d, dict):
        return Ici()
    sur = d.get("sur") if isinstance(d.get("sur"), str) and d.get("sur").strip() else None
    proches = []
    for p in d.get("proches") if isinstance(d.get("proches"), list) else []:
        if not isinstance(p, dict) or not isinstance(p.get("nom"), str) or p.get("cote") not in objets.COTES:
            continue
        dist = _nombre(p.get("distance_m"))
        if dist is not None and dist >= 0:
            proches.append(Proche(p["nom"][:objets.NOM_MAX_CHARS], p["cote"], dist))
    return Ici(sur[:objets.NOM_MAX_CHARS] if sur else None, tuple(proches[:PROCHES_MAX]))


def decoder(raw) -> EtatCorps:
    """Payload de `corps/etat` -> EtatCorps, TOLÉRANT : il ne lève jamais. Enveloppe, marche ou
    cause illisibles -> INCONNU (jamais un état deviné) ; champ facultatif faux -> sa valeur sûre
    (pas de geste, rien autour, pas de délai) ; phrase absente, trop longue ou vide -> recomposée
    depuis les champs lus."""
    try:
        v = json.loads(raw)
    except (ValueError, TypeError):
        return INCONNU
    if not isinstance(v, dict) or v.get("v") != VERSION or v.get("marche") not in MARCHES \
            or v.get("cause") not in CAUSES:
        return INCONNU
    qui = v.get("qui_relance") if v.get("qui_relance") in QUI_RELANCE else None
    repart = _nombre(v.get("repart_dans_s"))
    repart = repart if repart is not None and repart >= 0 else None
    geste, ici = _geste_lu(v.get("geste")), _ici_lu(v.get("ici"))
    phrase = v.get("phrase")
    if not isinstance(phrase, str) or not phrase.strip() or len(phrase) > PHRASE_MAX_CHARS:
        phrase = composer(v["marche"], v["cause"], repart, geste, ici)
    return EtatCorps(v["marche"], v["cause"], qui, repart, geste, ici, phrase)


def lire(raw, recu_t: Optional[float], now: float) -> EtatCorps:
    """Ce qu'un LECTEUR doit croire à `now` : le dernier `corps/etat` reçu à `recu_t` s'il a
    moins de PEREMPTION_S (l'écrivain republie au plus tard toutes les PERIODE_MAX_S), sinon
    INCONNU — un écrivain mort ou figé ne laisse jamais un vieil état passer pour l'actuel."""
    if raw is None or recu_t is None or now - recu_t > PEREMPTION_S:
        return INCONNU
    return decoder(raw)


def lire_corps_sur(payload) -> Optional[CorpsSur]:
    """`corps_sur/etat` (dict JSON du nœud corps_sur, déjà décodé) -> CorpsSur, ou None s'il est
    illisible (état hors contrat) : l'écrivain garde alors le précédent et le journalise."""
    if not isinstance(payload, dict) or payload.get("etat") not in CORPS_SUR_ETATS:
        return None
    zone = payload.get("zone") if payload.get("zone") in CORPS_SUR_ZONES else None
    cause = payload.get("cause") if isinstance(payload.get("cause"), str) else ""
    return CorpsSur(payload["etat"], zone, cause)
