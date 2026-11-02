"""Décodage commun des StringTime entrants — délègue au codec du parc.

Depuis le lot L1a (2026-11-02), le décodeur vit dans
theatre_contrats.stringtime (packages/theatre_contrats du mono-dépôt) ; ce
module garde sa signature pour les nodes du robot qui l'importent. Rappel du
contrat (inchangé) : payload JSON encodé en chaîne — un nom d'expression se
publie AVEC guillemets imbriqués ({msg: '\"calib\"'}) ; payload invalide =
log ERROR explicite avec le topic et le payload, retour None (vécu le
2026-07-10 : des heures de mires « affichées » jamais appliquées, l'erreur
étant avalée en silence par le except générique des nodes).
"""
from theatre_contrats import stringtime


def decode(ros_msg, topic):
    """Retourne la valeur JSON du payload, ou None (avec log explicite)."""
    return stringtime.decode(ros_msg, topic)
