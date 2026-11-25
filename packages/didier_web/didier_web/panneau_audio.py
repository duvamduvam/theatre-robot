"""Onglet « Audio » de la page scène (22/11) — logique 100 % PURE : le verdict d'un coup d'œil.

POURQUOI : en séance au banc PC, David ne savait jamais si son casque était branché, si le son
entrait et sortait ; il perdait du temps à le deviner. Ce module croise DEUX sources de faits,
sans rien supposer :
 - la veille audio de l'HÔTE (`machines/sim/banc-vision/audio_veille.py`, relayée par le pont) :
   micro et sortie RÉELLEMENT écrits dans asound-pc.conf, présents ou non dans PipeWire,
   coupés ou non, casque Bluetooth connecté ou non, niveau du micro mesuré en continu ;
 - la tête (topics ROS que le pont reçoit déjà) : `chat_state` (écoute / réfléchit / parle /
   off) et le dernier `chat_hearing` (ce qu'elle vient d'entendre, gardé ou jeté).
et en tire UN verdict (ok / attention / ko / attente), un message clair et l'action à faire.

Aucun import ROS ni aiohttp (même règle que web_protocol.py) : testé par
packages/didier_core/test/unit/test_panneau_audio.py, valeurs gravées.
"""

from __future__ import annotations

import math
from typing import Any

Json = dict[str, Any]   # un objet JSON (état de la veille, message rendu à la page)

# Plancher du vumètre : -70 dBFS = 0 %, 0 dBFS = 100 %. Le seuil de micro vivant de la veille
# (crête 30, mesuré le 18/11) tombe ainsi vers 9 % : visible, pas confondu avec zéro.
PLANCHER_DB = -70.0
PLEINE_ECHELLE = 32767
# Un tour entendu reste « Didier m'entend » ce temps-là (le tour suivant met des secondes à venir).
ENTENDU_FRAIS_S = 6.0

OK, ATTENTION, KO, ATTENTE = "ok", "attention", "ko", "attente"
_GRAVITE = {KO: 0, ATTENTE: 1, ATTENTION: 2}

COMMANDE_VEILLE = "python3 machines/sim/banc-vision/audio_veille.py"


def pourcent(crete: int | None) -> int | None:
    """Crête s16 -> 0..100 sur une échelle en dB (une voix et un souffle restent lisibles)."""
    if crete is None:
        return None
    if crete <= 0:
        return 0
    db = 20.0 * math.log10(min(crete, PLEINE_ECHELLE) / PLEINE_ECHELLE)
    return int(round(max(0.0, min(1.0, (db - PLANCHER_DB) / -PLANCHER_DB)) * 100))


def _probleme(niveau: str, message: str, action: str) -> Json:
    return {"niveau": niveau, "message": message, "action": action}


def _cote_absent(cote: Json, quoi: str) -> Json:
    """Micro ou sortie introuvable dans PipeWire : la cause la plus probable d'abord."""
    casque = cote.get("casque")
    if casque and not casque.get("connecte"):
        return _probleme(KO, f"casque « {casque['nom']} » déconnecté ({quoi} absent)",
                         "allume le casque (ou rapproche-le du PC), puis « Re-détecter »")
    if casque and quoi == "micro":
        return _probleme(KO, f"micro du casque « {casque['nom']} » absent (casque en écoute seule)",
                         "« Re-détecter » : il repasse le casque en mode casque + micro")
    return _probleme(KO, f"{quoi} « {cote.get('nom') or cote.get('conf')} » débranché",
                     "rebranche-le, puis « Re-détecter »")


def problemes(hote: Json | None, chat_state: str | None) -> list[Json]:
    """Tous les problèmes constatés, du plus grave au moins grave (ordre stable)."""
    if hote is None:
        return [_probleme(KO, "veille audio du banc injoignable : rien n'est vérifié",
                          f"relance la séance (seance-chantiers.sh) ou lance sur le PC : {COMMANDE_VEILLE}")]
    trouves = []
    redet = hote.get("redetection") or {}
    if redet.get("en_cours"):
        trouves.append(_probleme(ATTENTE, "re-détection du micro et de la sortie en cours…",
                                 "patiente quelques secondes"))
    micro, sortie = hote.get("micro"), hote.get("sortie")
    if micro is None or sortie is None:
        erreur = hote.get("erreur_sonde") or "première mesure pas encore faite"
        trouves.append(_probleme(KO, f"état du son illisible ({erreur})", "attends 2 s ; si ça dure, relance la veille"))
        return sorted(trouves, key=lambda p: _GRAVITE[p["niveau"]])
    if not micro.get("present"):
        trouves.append(_cote_absent(micro, "micro"))
    if not sortie.get("present"):
        trouves.append(_cote_absent(sortie, "sortie"))
    connectes = [c for c in hote.get("casques") or [] if c.get("connecte")]
    # 22/11 (vécu en séance) : M50 connecté, la tête écoutait le micro interne muet et le verdict
    # disait « micro coupé » — vrai mais trompeur. La vraie cause passe devant.
    casque_micro = next((c for c in connectes if c.get("micro_present")), None) or (connectes[0] if connectes else None)
    if (casque_micro and micro.get("present") and not micro.get("casque") and not micro.get("respeaker")):
        trouves.append(_probleme(KO, f"casque « {casque_micro['nom']} » connecté mais son micro n'est pas utilisé"
                                     f" (Didier écoute « {micro.get('nom')} »)",
                                 "« Re-détecter » : le micro du casque sera choisi"))
    casque_sortie = next((c for c in connectes if c.get("sortie_present")), None)
    if casque_sortie and sortie.get("present") and not sortie.get("casque"):
        trouves.append(_probleme(KO, f"casque « {casque_sortie['nom']} » connecté mais la voix de Didier n'y va pas"
                                     f" (elle sort sur « {sortie.get('nom')} »)",
                                 "« Re-détecter » : la sortie du casque sera choisie"))
    if micro.get("present") and micro.get("muet"):
        trouves.append(_probleme(KO, f"micro « {micro.get('nom')} » coupé (muet) dans le réglage son",
                                 "réactive-le : Paramètres > Son > Entrée (ou le bouton muet du casque)"))
    if sortie.get("present") and sortie.get("muet"):
        trouves.append(_probleme(KO, f"sortie « {sortie.get('nom')} » coupée (muette) dans le réglage son",
                                 "réactive-la : Paramètres > Son > Sortie"))
    niveau = hote.get("niveau") or {}
    if micro.get("present") and niveau.get("erreur"):
        trouves.append(_probleme(KO, niveau["erreur"], "« Re-détecter »"))
    elif micro.get("present") and niveau.get("muet_constate"):
        trouves.append(_probleme(ATTENTION, "micro plat depuis 3 s : aucun son n'entre",
                                 "parle dedans ; s'il reste plat : bouton muet du casque, puis « Re-détecter »"))
    if chat_state is None:
        trouves.append(_probleme(KO, "la tête ne dit rien (aucun état de conversation reçu)",
                                 "la tête est-elle lancée ? docker logs didier-sim-vision"))
    elif chat_state == "off":
        trouves.append(_probleme(ATTENTION, "Parole OFF : Didier n'écoute pas", "Parole → ON (colonne de gauche)"))
    if (not connectes and micro.get("present") and sortie.get("present")
            and not micro.get("casque") and not sortie.get("casque")):
        trouves.append(_probleme(ATTENTION, "pas de casque : le micro peut entendre Didier",
                                 "allume un casque Bluetooth, puis « Re-détecter »"))
    return sorted(trouves, key=lambda p: _GRAVITE[p["niveau"]])


# S0 (25/11) : énoncés jetés de suite à partir desquels on alerte (même valeur que JETES_ALERTE de
# la tête, didier_vision.ai.conversation) ; sous SON_PLAT de crête, l'énoncé était du silence
# (même seuil que le micro vivant de la veille, audio_banc.CRETE_VIVANT).
JETES_ALERTE = 3
SON_PLAT = 30


def probleme_enonces_jetes(entendu: Json | None) -> list[Json]:
    """Plusieurs énoncés de suite captés puis jetés « rien de compréhensible » (vécu le 24/11 : 5
    d'affilée, la page n'en disait rien). La crête du dernier départage les causes."""
    if not isinstance(entendu, dict):
        return []
    n = entendu.get("jetes_de_suite")
    if not isinstance(n, int) or n < JETES_ALERTE:
        return []
    crete = entendu.get("crete")
    if isinstance(crete, int) and crete < SON_PLAT:
        return [_probleme(KO, f"{n} phrases de suite jetées : le son capté est plat (crête {crete})",
                          "le micro ne transmet rien : bouton muet du casque, puis « Re-détecter »")]
    niveau = f" (crête {crete})" if isinstance(crete, int) else ""
    return [_probleme(KO, f"{n} phrases de suite jetées : du son arrive{niveau} mais rien n'est compris",
                      "parle près du micro ; si ça dure, « Re-détecter » (micro de casque en "
                      "mauvais mode, ou mauvais micro)")]


def temoins(chat_state: str | None, entendu: Json | None, entendu_il_y_a_s: float | None) -> Json:
    """« Didier m'entend » (un tour récent : gardé = oui, jeté = jeté) et « Didier parle »."""
    entend = "non"
    texte = None
    if isinstance(entendu, dict) and entendu_il_y_a_s is not None and entendu_il_y_a_s <= ENTENDU_FRAIS_S:
        entend = "oui" if entendu.get("verdict") == "gardé" else "jete"
        texte = entendu.get("entendu") if isinstance(entendu.get("entendu"), str) else None
    return {"entend": entend, "entendu": texte, "parle": chat_state == "speaking", "chat_state": chat_state}


def _resume_cote(cote: Json | None) -> Json | None:
    if cote is None:
        return None
    casque = cote.get("casque")
    return {"nom": cote.get("nom"), "present": bool(cote.get("present")), "muet": cote.get("muet"),
            "suit_ubuntu": bool(cote.get("suit_ubuntu")),
            "casque": casque.get("nom") if casque else None,
            "casque_connecte": casque.get("connecte") if casque else None}


def synthese(hote: Json | None, chat_state: str | None, entendu: Json | None,
             entendu_il_y_a_s: float | None) -> Json:
    """Tout ce que l'onglet affiche. `hote` = /etat de la veille (None = injoignable)."""
    liste = sorted(problemes(hote, chat_state) + probleme_enonces_jetes(entendu),
                   key=lambda p: _GRAVITE[p["niveau"]])
    if liste:
        verdict, message, action = liste[0]["niveau"], liste[0]["message"], liste[0]["action"]
    else:
        micro, sortie = (hote or {}).get("micro") or {}, (hote or {}).get("sortie") or {}
        verdict, message, action = OK, f"tout va bien : « {micro.get('nom')} » → « {sortie.get('nom')} »", ""
    niveau = (hote or {}).get("niveau") or {}
    entree = _resume_cote((hote or {}).get("micro"))
    if entree is not None:
        entree.update(pct=pourcent(niveau.get("crete")), pct_3s=pourcent(niveau.get("crete_3s")),
                      seuil_pct=pourcent(niveau.get("seuil_vivant")))
    return {
        "service": hote is not None,
        "verdict": verdict,
        "message": message,
        "action": action,
        "autres": [p["message"] for p in liste[1:]],
        "entree": entree,
        "sortie": _resume_cote((hote or {}).get("sortie")),
        "temoins": temoins(chat_state, entendu, entendu_il_y_a_s),
        "redetection": (hote or {}).get("redetection"),
        "derniere_action": (hote or {}).get("derniere_action"),
    }


def faut_rouvrir_micro(chat_state: str | None) -> bool:
    """Après une re-détection : la tête relit asound.conf à chaque arecord ; il suffit de couper
    puis rouvrir son micro (Parole OFF -> ON). Jamais si la parole était coupée ou la tête muette
    (on ne rallume pas ce que David a éteint)."""
    return chat_state in ("listening", "thinking", "speaking")


# Actions du message WebSocket {"type": "audio_banc", "action": ...} (writer seul, sim seule).
ACTIONS = frozenset({"tester", "redetecter"})
