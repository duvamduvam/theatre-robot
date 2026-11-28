"""Réglages de l'appareil (geste G3) : YAML + bornes dures ; refus = ReglagesError lisible.

APPAREIL : les clés et leurs bornes (le fichier de la machine : machines/appareil_gabarit/appareil_gabarit.yaml).
"""
import yaml


class ReglagesError(ValueError):
    """Configuration refusée : le nœud sort en code 2."""


def charger(chemin):
    try:
        with open(chemin, encoding="utf-8") as f:
            brut = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as erreur:
        raise ReglagesError(f"réglages illisibles : {chemin} ({erreur})") from None
    return brut
