"""Décodage commun des StringTime entrants.

Le payload d'un StringTime est du JSON encodé en chaîne : un nom d'expression
se publie AVEC guillemets imbriqués ({msg: '\"calib\"'}), un objet en JSON
normal. Jusqu'ici, un payload malformé levait JSONDecodeError, avalée par le
except générique des nodes : le message disparaissait SANS TRACE exploitable
(vécu le 2026-07-10 : des heures de mires « affichées » jamais appliquées).
Ici : erreur ERROR explicite avec le topic et le payload reçu, retour None.
"""
import json
import logging


def decode(ros_msg, topic):
    """Retourne la valeur JSON du payload, ou None (avec log explicite)."""
    try:
        return json.loads(ros_msg.msg)
    except (json.JSONDecodeError, TypeError):
        logging.error("payload invalide sur '%s' (JSON attendu, ex. '\"nom\"' avec "
                      "guillemets) : %r", topic, ros_msg.msg)
        return None
