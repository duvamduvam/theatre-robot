"""Tableau de situation — composition du texte relu par la parole à chaque tour.

QUOI : `SituationBoard` agrège ce que la boucle 0 sait SANS LLM (personne vue,
      état de route, point d'intérêt) et ce que la réflexion a compris
      (situation, direction de jeu), plus le résumé de mission, en un court
      texte daté et plafonné. Module PUR (stdlib seule). Contient aussi les
      décodeurs tolérants des payloads reçus par reflection_node (testables
      sans ROS).
POURQUOI (cf. dadou_robot_ros/docs/etude-niveaux-reflexion.md §3) : chaque
      caractère est relu à CHAQUE réplique et rallonge le premier mot de la
      parole — d'où les plafonds par section et le plafond total
      (reflection_contract.SITUATION_MAX_CHARS). Chaque section a sa propre
      péremption : une vieille vision du monde est pire qu'aucune.
PIÈGE azimut : `person_box.x` vaut +1 au bord DROIT de l'image
      (target_picker._azimuth, pas de miroir). « À ta gauche/droite » suppose
      donc une image NON miroir ET une caméra orientée comme Didier — À
      VÉRIFIER EN SÉANCE (un sens inversé ferait regarder Didier du mauvais
      côté dans ses répliques).
"""
from __future__ import annotations

import json
import math
from typing import Optional

from vision.ai.reflection_contract import SITUATION_MAX_CHARS

# Plafonds PAR SECTION, en-tête compris (le total ne doit jamais dépasser
# SITUATION_MAX_CHARS).
PERCEPTION_MAX_CHARS = 160
COMPRIS_MAX_CHARS = 200  # plafond ; en pratique le RESTE du budget (cf. compose)
DIRECTION_SECTION_MAX_CHARS = 220
MISSION_MAX_CHARS = 260

# Péremptions (secondes) de chaque source.
PERSON_FRESH_S = 2.0       # au-delà : « Personne en vue. »
POI_FRESH_S = 30.0         # « Tu es devant : … » tant que l'enter est récent
COMPRIS_FRESH_S = 30.0
DIRECTION_FRESH_S = 60.0

# Seuils de position (azimut) et de distance (hauteur de silhouette [0..1],
# proxy de distance — cf. target_picker).
AZIMUTH_SIDE = 0.33
HEIGHT_CLOSE = 0.6
HEIGHT_MEDIUM = 0.3


def _cap(text: str, max_chars: int) -> str:
    """Tronque à max_chars en finissant par « … » (jamais de coupe muette)."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 1].rstrip() + "…"


class SituationBoard:
    """Tableau de situation. Non thread-safe : le verrou est celui du node."""

    def __init__(self):
        self._person: Optional[tuple] = None   # (azimut, hauteur, confiance, t)
        self._route: Optional[str] = None
        self._speed: Optional[float] = None    # route_speed ; None = inconnue
        self._poi_in: dict = {}                # poi -> heure de l'enter
        self._situation: Optional[str] = None
        self._situation_t = 0.0
        self._direction: Optional[str] = None
        self._direction_t = 0.0

    # -- alimentation (boucle 0, sans LLM) -----------------------------------

    def update_person(self, azimuth: float, height: float, confidence: float,
                      now_s: float) -> None:
        self._person = (azimuth, height, confidence, now_s)

    def set_route(self, state: str) -> None:
        """`"on"` = Didier marche, `"off"` = arrêté ; toute autre valeur =
        état inconnu (la phrase est omise plutôt que devinée)."""
        self._route = state if state in ("on", "off") else None

    def set_speed(self, speed: Optional[float]) -> None:
        """Facteur de vitesse de route (topic `route_speed`, 0..1) ; None =
        inconnue (valeur initiale : jamais reçue)."""
        self._speed = speed

    def moving(self) -> bool:
        """Didier roule VRAIMENT : route "on" ET vitesse > 0. Revue
        adversariale du 23/10 (I2/M3) : route "on" seule ne suffit pas — le
        régisseur arrête Didier par route_speed 0 en laissant la route "on"
        (lubie, « stop » vocal), et Didier se croyait en marche.
        Route "on" + vitesse INCONNUE = considéré EN MARCHE (révisé le 23/10) :
        route_speed est volatile, un reflection_node démarré après la dernière
        consigne ne la connaît pas — le doute doit priver de tours spontanés
        (règle « micro à l'arrêt »), pas en accorder. Ce n'est qu'une règle de
        PAROLE : le tableau, lui, ne dit rien de la route tant que la vitesse
        est inconnue (cf. perception_text)."""
        return self._route == "on" and (self._speed is None or self._speed > 0)

    def set_poi(self, poi: str, event: str, now_s: float) -> None:
        if event == "enter":
            self._poi_in[poi] = now_s
        elif event == "exit":
            self._poi_in.pop(poi, None)

    # -- alimentation (réflexion) --------------------------------------------

    def set_reflection(self, situation: Optional[str], direction: Optional[str],
                       now_s: float) -> None:
        """Chaque champ vide/None est IGNORÉ et garde sa valeur (et son
        heure) : la réflexion rend `direction: null` pour « rien ne change »,
        ça ne doit pas effacer la direction en cours."""
        if situation and situation.strip():
            self._situation = situation.strip()
            self._situation_t = now_s
        if direction and direction.strip():
            self._direction = direction.strip()
            self._direction_t = now_s

    def reset_understanding(self) -> None:
        """Efface le « compris » et la direction de jeu, PAS la perception ni
        la route (faits du monde, valables quel que soit le personnage).
        POURQUOI : au changement de persona, la réflexion déduite des
        répliques de l'ancien personnage serait réinjectée à chaque réplique
        du nouveau (vécu en sim le 2026-10-31 : « naif » restait râleur)."""
        self._situation = None
        self._situation_t = 0.0
        self._direction = None
        self._direction_t = 0.0

    # -- lecture -------------------------------------------------------------

    def perception_text(self, now_s: float) -> str:
        """Perception de la boucle 0 en clair, sans en-tête (aussi donnée au
        LLM de réflexion)."""
        parts = []
        person = self._person
        if person is not None and now_s - person[3] <= PERSON_FRESH_S:
            azimuth, height = person[0], person[1]
            if azimuth < -AZIMUTH_SIDE:
                where = "à ta gauche"
            elif azimuth > AZIMUTH_SIDE:
                where = "à ta droite"
            else:
                where = "devant toi"
            if height > HEIGHT_CLOSE:
                dist = "tout près"
            elif height >= HEIGHT_MEDIUM:
                dist = "à quelques pas"
            else:
                dist = "loin"
            parts.append(f"Une personne est {where}, {dist}.")
        else:
            parts.append("Personne en vue.")
        # « Tu marches. » seulement si Didier roule vraiment (cf. moving) ;
        # « Tu es arrêté. » sur route off OU vitesse nulle ; route "on" à
        # vitesse inconnue (ou route inconnue) : phrase omise plutôt que devinée.
        if self._route == "on" and self._speed is not None and self._speed > 0:
            # Pas self.moving() : lui compte la vitesse inconnue comme une
            # marche (prudence de PAROLE) ; le tableau, lui, ne devine pas.
            parts.append("Tu marches.")
        elif self._route == "off" or self._speed == 0:
            parts.append("Tu es arrêté.")
        recent = [(t, poi) for poi, t in self._poi_in.items() if now_s - t <= POI_FRESH_S]
        if recent:
            parts.append(f"Tu es devant : {max(recent)[1]}.")
        return " ".join(parts)

    def compose(self, now_s: float, mission_summary: str) -> str:
        """Texte du tableau (sections vides omises, "" si tout est vide).
        Ordre = PRIORITÉ : perception, direction, mission, puis « compris »
        dans le reste du budget. POURQUOI cet ordre (banc réel du 23/10) :
        direction et mission font avancer l'histoire ; « compris » répète en
        partie la perception — c'est elle qui se fait rogner quand la place
        manque, jamais la mission (elle était coupée en pleine indication)."""
        sections = []
        perception = self.perception_text(now_s)
        # Toujours présente (« Personne en vue. » est une information : Didier
        # sait qu'il joue seul) — donc le tableau n'est "" que si la
        # perception elle-même est vide, jamais en pratique.
        if perception:
            sections.append(_cap("[Perception] " + perception, PERCEPTION_MAX_CHARS))
        if self._direction and now_s - self._direction_t <= DIRECTION_FRESH_S:
            sections.append(_cap("[Direction pour tes prochaines répliques] " + self._direction,
                                 DIRECTION_SECTION_MAX_CHARS))
        if mission_summary and mission_summary.strip():
            sections.append(_cap("[Mission] " + mission_summary.strip(), MISSION_MAX_CHARS))
        if self._situation and now_s - self._situation_t <= COMPRIS_FRESH_S:
            age = int(round(now_s - self._situation_t))
            header = f"[Ce que tu as compris, il y a {age} s] "
            budget = min(COMPRIS_MAX_CHARS,
                         SITUATION_MAX_CHARS - len("\n".join(sections)) - (1 if sections else 0))
            # Moins de place que l'en-tête + quelques mots : on omet plutôt
            # que d'envoyer un en-tête vide de sens.
            if budget > len(header) + 10:
                sections.append(_cap(header + self._situation, budget))
        return "\n".join(sections)[:SITUATION_MAX_CHARS]


def persona_changed(current: Optional[str], incoming: str) -> bool:
    """Un `persona_state` reçu est-il un VRAI changement de personnage ?
    Non si `incoming` est vide, identique à la courante, ou si `current` est
    inconnue (premier message, typiquement le latché reçu au démarrage : il
    ne dit pas que quoi que ce soit a changé, le transcript est alors sain)."""
    return bool(incoming) and current is not None and incoming != current


# -- décodeurs des payloads reçus (tolérants : None = refus, jamais d'exception)

def decode_transcript_line(raw) -> Optional[dict]:
    """Payload de `chat_transcript` -> {"role", "text"} ; None si invalide,
    rôle autre que david/didier ou texte vide."""
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict):
        return None
    role, text = obj.get("role"), obj.get("text")
    if role not in ("david", "didier") or not isinstance(text, str) or not text.strip():
        return None
    return {"role": role, "text": text.strip()}


def decode_speed(raw) -> Optional[float]:
    """Payload de `route_speed` (json.dumps(float), 0..1) -> facteur ; None
    si illisible (l'appelant l'IGNORE et garde la vitesse connue). Calqué sur
    le consommateur réel, route_driver (dadou_robot_ros robot_rehearsal,
    _decode + Route.set_speed) : JSON si possible sinon brut, float(),
    non fini refusé, borné à [0, 1] — le tableau doit dire ce que Didier
    FAIT, pas ce qu'un décodeur plus strict croirait (un "0.5" brut ou
    hors bornes le fait bel et bien rouler)."""
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        value = raw
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return min(1.0, max(0.0, value))


def decode_poi_event(raw) -> Optional[tuple]:
    """Payload de `rehearsal/poi_event` -> (poi, event) ; None si invalide."""
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict):
        return None
    poi, event = obj.get("poi"), obj.get("event")
    if not isinstance(poi, str) or not poi or event not in ("enter", "exit"):
        return None
    return poi, event
