"""Gardiens du banc (F1, 25/11, spec §4) : un gardien qui parle rend l'épreuve INVALIDE, jamais
rouge. On ne met plus la sim en pause (la pause figeait les horloges : faux rouges) : l'épreuve
est abandonnée, le PC refroidit, elle est rejouée.
"""
CHAUD_C = 85.0          # paquet CPU : l'épreuve en cours est abandonnée
FRAIS_C = 80.0          # on rejoue sous ce seuil
ARRET_C = 88.0          # arrêt immédiat de toute la fumée : jamais au-delà de 90 °C (règle de David)
ATTENTE_FRAIS_S = 20 * 60
PERIODE_S = 5           # interrogation des gardiens pendant une épreuve
REJEUX_MAX = 2
RTF_MIN = 0.8
ATTENTE_RTF_S = 120     # une seconde sonde 2 min après une première sous le seuil
NON_REJOUABLES = ("hors ligne", "temps réel", "panne réseau")   # rejouer n'y changerait rien


class Arret(Exception):
    """Arrêt immédiat de TOUTE la fumée (88 °C, domaine ROS ≠ 43) : sim arrêtée, page écrite."""


def chaleur(temperature):
    """None (sain), « chaud » (≥ 85 °C) ou « arret » (≥ 88 °C) ; sans thermomètre : sain."""
    if temperature is None:
        return None
    if temperature >= ARRET_C:
        return "arret"
    return "chaud" if temperature >= CHAUD_C else None


def refroidir(f) -> bool:
    """Attend le paquet sous 80 °C, au plus 20 min (pauses gardées) ; vrai s'il y est."""
    fin = f.sy.horloge() + ATTENTE_FRAIS_S
    while True:
        t = f.sy.temperature()
        if t is None or t < FRAIS_C:
            return True
        if f.sy.horloge() >= fin:
            return False
        f.pause(15)


def rejouable(resultat: dict) -> bool:
    detail = resultat.get("detail", "")
    return resultat["statut"] == "invalide" and not any(m in detail for m in NON_REJOUABLES)
