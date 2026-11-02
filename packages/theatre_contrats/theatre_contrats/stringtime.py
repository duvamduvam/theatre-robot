"""LE codec des StringTime du parc Didier (robot_interfaces/msg/StringTime :
msg = payload JSON en chaîne, time = durée en ms, anim = vient d'une séquence).

Le payload est du JSON ENCODÉ EN CHAÎNE : un nom d'expression se publie AVEC
guillemets imbriqués ({msg: '\"calib\"'}), un objet en JSON normal, l'arrêt
d'animation en booléen JSON ('false').

Trois façons de lire, une par comportement existant — chaque site d'appel
garde EXACTEMENT le sien (lot L1a : aucun décodeur ne change de comportement,
les tests d'équivalence le prouvent) :

- decode / decode_payload : STRICT. Payload invalide = None + log ERROR avec le
  topic et le payload (vécu le 2026-07-10 : un JSONDecodeError avalé par le
  except générique d'un node a fait perdre des heures de mires « affichées »
  jamais appliquées). Copie bit à bit de robot/nodes/payload.py : n'attrape
  QUE JSONDecodeError et TypeError — un entier JSON de plus de 4300 chiffres
  lève ValueError (pas JSONDecodeError) et PROPAGE, comme avant.
- decode_or_raw : TOLÉRANT. Payload invalide = la chaîne brute (log DEBUG),
  pour les commandes tapées à la main (`on`/`off` sans guillemets). Attrape
  ValueError et TypeError, comme les sites gaze/follow/route/director.
  RecursionError (imbrication hostile) PROPAGE : c'est à l'appelant de s'en
  garder s'il le faut (gaze_control le fait).
- loads : l'analyse nue, qui lève comme json.loads. Pour les sites qui ont
  leur PROPRE traitement de l'échec (warning + return, strip du brut, KeyError
  dans le même try…) : ils gardent leur except tel quel.

Python pur : aucun import ROS (encode prend le type de message en paramètre).
"""
import json
import logging


def loads(raw):
    """Analyse d'un payload StringTime ; lève exactement comme json.loads."""
    return json.loads(raw)


def decode_payload(raw, topic):
    """STRICT sur la chaîne : valeur JSON, ou None (avec log ERROR explicite)."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logging.error("payload invalide sur '%s' (JSON attendu, ex. '\"nom\"' avec "
                      "guillemets) : %r", topic, raw)
        return None


def decode(ros_msg, topic):
    """STRICT sur un message : valeur JSON de ros_msg.msg, ou None (avec log)."""
    return decode_payload(ros_msg.msg, topic)


def decode_or_raw(raw, topic=""):
    """TOLÉRANT sur la chaîne : valeur JSON, sinon `raw` lui-même (log DEBUG)."""
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        logging.debug("payload non JSON sur '%s', pris brut : %r", topic, raw)
        return raw


def encode(value, time_ms=0, anim=False, msg_type=None):
    """Champs d'un StringTime : msg = json.dumps(valeur NUE) — "joie" -> '"joie"',
    False -> 'false', jamais de ré-emballage {topic: valeur} sur le fil.
    Sans msg_type : dict {msg, time, anim} (tests, outils sans ROS) ; avec
    msg_type (robot_interfaces.msg.StringTime) : le message construit."""
    fields = {"msg": json.dumps(value), "time": int(time_ms), "anim": bool(anim)}
    if msg_type is None:
        return fields
    return msg_type(**fields)
