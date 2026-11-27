"""Lot S2b (`docs/spec-S2-le-corps-raconte.md` §3) — « demander d'abord, parler ensuite ».

POURQUOI. Séance du 26/11 : David fait STOP console, dit « allez, go », et Didier répond
« Ça y est, je fonce vers la grue ! » — alors que le sélecteur venait de REFUSER ce go. La
cause n'était pas le LLM mais l'ORDRE des opérations : le LLM écrivait sa réplique, la
demande de mouvement partait APRÈS (clé du JSON de fin). La bouche ne pouvait pas savoir.

CE QUE FAIT CE MODULE. Il lit la PREMIÈRE ligne de l'appel 1. Si c'est `GESTE {json}`, le
tour est un tour de geste : rien n'est dit, la demande part au corps, et la réplique est
produite par un second appel qui connaît la réponse. Sinon, c'est une réplique ordinaire,
jouée telle quelle (un seul appel : latence inchangée, cf. §3 « Latence »).

Module PUR (aucun ROS, aucun réseau) : tout est testable sans sim.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Marqueur de la première ligne (cf. personas.GESTE_DABORD_TEMPLATE). Tolérant à la casse et
# aux espaces : le LLM écrit parfois « Geste {…} » ou « GESTE: {…} ». Jamais tolérant sur la
# POSITION (première ligne) — une ligne « GESTE » au milieu d'une réplique est du texte.
_MARQUEUR = re.compile(r"^\s*geste\s*:?\s*(\{.*)$", re.IGNORECASE | re.DOTALL)

# Clés de mouvement acceptées sur cette ligne (mêmes clés que le JSON de fin, cf.
# conversation.MOVE_KEYS + "tourner_vers" du lot S2c). Une ligne GESTE qui n'en porte
# AUCUNE est ignorée (repli sûr : on la traite comme une réplique).
CLES_GESTE = ("marche", "aller_voir", "faire_le_tour", "tourner", "avancer", "tourner_vers")

# Longueur maximale de la ligne lue (un LLM qui part en boucle ne doit pas nous faire
# charger 100 ko de JSON).
LIGNE_MAX_CHARS = 2000


def coupe_premiere_ligne(texte: str):
    """-> (première ligne, reste). Sans saut de ligne : (texte, "")."""
    if not isinstance(texte, str):
        return "", ""
    i = texte.find("\n")
    if i < 0:
        return texte, ""
    return texte[:i], texte[i + 1:]


def lire_ligne_geste(premiere_ligne) -> Optional[dict]:
    """Première ligne de l'appel 1 -> dict des clés de geste, ou None si ce n'en est pas une.

    None (= réplique ordinaire) dans TOUS les cas douteux : pas le marqueur, JSON illisible,
    JSON qui n'est pas un objet, aucune clé de geste connue. Le repli sûr est « c'est une
    réplique » : au pire Didier parle comme avant (comportement du 26/11), jamais un geste
    inventé à partir d'une ligne mal lue.
    """
    if not isinstance(premiere_ligne, str) or len(premiere_ligne) > LIGNE_MAX_CHARS:
        return None
    m = _MARQUEUR.match(premiere_ligne)
    if m is None:
        return None
    brut = m.group(1).strip()
    try:
        params = json.loads(brut)
    except (ValueError, TypeError):
        # Le LLM a écrit « GESTE {aller_voir: banc} » ou a coupé son JSON.
        logger.warning("Ligne GESTE illisible, traitée comme une réplique : %r", brut[:200])
        return None
    if not isinstance(params, dict):
        logger.warning("Ligne GESTE qui n'est pas un objet JSON, ignorée : %r", brut[:200])
        return None
    if not any(cle in params for cle in CLES_GESTE):
        logger.warning("Ligne GESTE sans clé de mouvement connue, ignorée : %r", brut[:200])
        return None
    return params


# --------------------------------------------------------------------------------------
# Appel 2 (§3) : la réponse du corps, en clair, avant que la bouche parle.
# --------------------------------------------------------------------------------------

# Délai de garde (§3) : au-delà, la bouche parle quand même, en sachant qu'elle n'a pas de
# réponse — JAMAIS en prétendant que le geste est parti. Le sélecteur répond en ~20 ms.
ATTENTE_CORPS_S = 0.5

# Une phrase gravée par raison de refus (vocabulaire de theatre_contrats.corps_etat :
# RAISONS_GESTE, enrichi des refus propres à la bouche). Elles sont données AU LLM, pas
# dites telles quelles : il les rejoue en personnage.
REFUS_PHRASES = {
    "arrete": "tu es arrêté par David, et seul son GO à la console te relance",
    "arret_de_david": "tu es arrêté par David, et seul son GO à la console te relance",
    "corps_sur": "ta sécurité te retient : tu ne peux pas avancer là",
    "hors_seance": "la séance n'est pas lancée : tu ne peux pas bouger",
    "sans_superviseur": "personne ne te surveille : tu ne peux pas bouger",
    "pas_ici": "cet objet n'est pas ici",
    "hors_atteinte": "cet objet est trop loin pour un seul geste",
    "unknown": "tu ne connais pas cet objet ici",
    "no_position": "tu ne sais pas où il est",
    "no_tour": "il n'y a pas la place d'en faire le tour",
    "no_pose": "tu ne sais pas où tu es",
    "invalid": "la demande est incompréhensible",
    "sans_reponse": "ton corps n'a pas répondu : tu ne sais pas s'il a bougé",
}
REFUS_INCONNU = "ton corps a refusé, pour une raison que tu ne connais pas"

ACCEPTE_PHRASE = "il accepte, tu t'y mets"

# Raison posée quand le corps n'a pas répondu dans ATTENTE_CORPS_S (§3).
SANS_REPONSE = "sans_reponse"


def phrase_reponse_corps(reponse) -> str:
    """Réponse du corps (contrat `rehearsal/chat_move_reply`) -> phrase en clair pour l'appel 2.

    `None` (aucune réponse dans le délai) -> la phrase « sans_reponse ». Le repli n'est JAMAIS
    « accepté » : sans nouvelle du corps, la bouche doit douter, pas affirmer.
    """
    if not isinstance(reponse, dict):
        return REFUS_PHRASES[SANS_REPONSE]
    effet = reponse.get("effect")
    if effet == "accepted":
        return ACCEPTE_PHRASE
    raison = reponse.get("reason")
    if isinstance(raison, str) and raison in REFUS_PHRASES:
        return REFUS_PHRASES[raison]
    return REFUS_INCONNU


def consigne_appel_2(reponse, phrase_corps: Optional[str] = None) -> str:
    """Message système court de l'appel 2 (§3) : la réponse du corps en clair, puis l'état du
    corps à jour (`corps/etat.phrase`), puis la consigne de cohérence."""
    from .personas import CORPS_CONSIGNE, CORPS_REPONSE_PREFIX

    texte = CORPS_REPONSE_PREFIX + phrase_reponse_corps(reponse) + "."
    if isinstance(phrase_corps, str) and phrase_corps.strip():
        texte += " " + phrase_corps.strip()
    return texte + CORPS_CONSIGNE
