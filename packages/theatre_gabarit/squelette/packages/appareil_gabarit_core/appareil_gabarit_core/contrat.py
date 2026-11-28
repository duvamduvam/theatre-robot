"""Contrat du nœud appareil_gabarit : noms, types, QoS (spec L3 décision 3, geste G2).

Tout nom vient de theatre_contrats (topics.py + appareils.REGISTRE) : le nœud n'en code aucun.
APPAREIL : ajouter l'appareil au REGISTRE et ses topics à topics.py (+ inventaire gravé), puis
remplacer les littéraux ci-dessous par les constantes de theatre_contrats.topics.
"""
NOM_APPAREIL = "appareil_gabarit"
NOM_NOEUD = "appareil_gabarit"
ETAT = "appareil_gabarit/etat"
# Tous les topics de l'appareil (vérifiés par verifier_appareil : relatifs, dans theatre_contrats).
TOPICS = (ETAT,)
