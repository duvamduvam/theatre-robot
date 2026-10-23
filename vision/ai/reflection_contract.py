"""Contrat des topics entre la PAROLE (chat_node) et la RÉFLEXION (reflection_node).

QUOI : noms de topics, formats JSON des payloads StringTime et constantes de
      péremption partagés par les deux nodes — UN seul endroit, importé des
      deux côtés (jamais de nom de topic recopié en dur dans un node).
      Module PUR (stdlib seule) : testable en CI sans ROS.
POURQUOI (cf. dadou_robot_ros/docs/etude-niveaux-reflexion.md) : la parole
      (Haiku 5.5 réflexion coupée, < 1 s au premier mot) ne doit JAMAIS
      attendre la réflexion (3-7 s). Les deux boucles ne se parlent que par
      ces messages asynchrones :

      reflection_node ──chat_situation──▶ chat_node   tableau de situation
                                                      (relu à chaque tour)
      reflection_node ──chat_prompt─────▶ chat_node   « prends la parole »
                                                      (tour spontané)
      chat_node ───────chat_reflect─────▶ reflection  demande de réflexion
                                                      (instruction complexe)
      chat_node ───────chat_transcript──▶ reflection  (EXISTANT, inchangé)
      reflection_node ──mission_state───▶ (console)   état de mission latché

DÉCODEURS : jamais d'exception — un payload invalide rend None, l'appelant
      logge le refus (même doctrine que le décodage StringTime commun :
      payload invalide = refus loggué, pas de perte silencieuse).
"""
from __future__ import annotations

import json
from typing import Optional

SITUATION_TOPIC = "chat_situation"
PROMPT_TOPIC = "chat_prompt"
REFLECT_TOPIC = "chat_reflect"
MISSION_STATE_TOPIC = "mission_state"

# Péremption CÔTÉ PAROLE du dernier tableau reçu. reflection_node le republie
# à SITUATION_REPUBLISH_S même sans changement : si la réflexion meurt, le
# tableau disparaît du prompt en SITUATION_TTL_S au plus — Didier parle alors
# comme avant (moins bien), jamais avec une vision du monde figée.
SITUATION_TTL_S = 5.0
SITUATION_REPUBLISH_S = 1.0

# Plafond du texte du tableau : chaque caractère est relu à CHAQUE réplique
# et rallonge le premier mot de la parole (~80 mots visés, étude §3).
SITUATION_MAX_CHARS = 700
# Plafonds des autres champs texte (une direction / une demande = une phrase).
DIRECTION_MAX_CHARS = 300
REFLECT_MAX_CHARS = 300


def _clean(value, max_chars: int) -> Optional[str]:
    """Chaîne rognée et tronquée à max_chars ; None si absente/vide/non-str."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    return value[:max_chars]


def _load_object(raw) -> Optional[dict]:
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def encode_situation(text: str, t_ms: int) -> str:
    """Payload de chat_situation : {"text": ..., "t_ms": ...}. Texte vide =
    tableau vide (la parole retire alors le bloc du prompt)."""
    return json.dumps({"text": (text or "")[:SITUATION_MAX_CHARS], "t_ms": int(t_ms)},
                      ensure_ascii=False)


def decode_situation(raw) -> Optional[str]:
    """Texte du tableau ("" = tableau vide, valide) ; None si payload invalide."""
    obj = _load_object(raw)
    if obj is None or not isinstance(obj.get("text"), str):
        return None
    return obj["text"].strip()[:SITUATION_MAX_CHARS]


def encode_prompt(direction: str, raison: str = "") -> str:
    """Payload de chat_prompt : {"direction": ..., "raison": ...}."""
    return json.dumps({"direction": (direction or "")[:DIRECTION_MAX_CHARS],
                       "raison": (raison or "")[:DIRECTION_MAX_CHARS]},
                      ensure_ascii=False)


def decode_prompt(raw) -> Optional[str]:
    """Direction de jeu du tour spontané ; None si invalide ou vide (un tour
    spontané sans direction n'a rien à faire avancer)."""
    obj = _load_object(raw)
    if obj is None:
        return None
    return _clean(obj.get("direction"), DIRECTION_MAX_CHARS)


def encode_reflect(demande: str) -> str:
    """Payload de chat_reflect : {"demande": ...}."""
    return json.dumps({"demande": (demande or "")[:REFLECT_MAX_CHARS]}, ensure_ascii=False)


def decode_reflect(raw) -> Optional[str]:
    """Demande de réflexion ; None si invalide ou vide."""
    obj = _load_object(raw)
    if obj is None:
        return None
    return _clean(obj.get("demande"), REFLECT_MAX_CHARS)
