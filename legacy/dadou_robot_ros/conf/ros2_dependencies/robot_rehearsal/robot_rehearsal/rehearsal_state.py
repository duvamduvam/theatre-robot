"""État de séance exposé à la page scène (rehearsal/state) -- logique PURE.

Deux faits seulement, les deux déjà connus de David :
  - la séance : « attente » (pas encore démarrée), « en_cours », « terminee »
    (durée atteinte, stop ou abort) ;
  - l'arrêt vocal : Didier est retenu à l'arrêt par un « stop » dit à voix
    haute (route_speed 0 retenu), levé par un « go » en séance ou le fader.
    Sans ce badge, la page affichait « route en marche » devant un Didier figé.

INTERDIT ICI : toute info de panne ou de lubie (type, id, vitesse imposée,
panne active). La page ne doit jamais trahir le tirage (étude répétition
simulée §13.1) ; ce module n'a volontairement AUCUN accès au scénario.
"""
import json

SEANCE_ATTENTE = "attente"
SEANCE_EN_COURS = "en_cours"
SEANCE_TERMINEE = "terminee"


def rehearsal_state(started: bool, ended: bool, voice_hold: bool) -> str:
    """Payload JSON (chaîne) de rehearsal/state. `ended` prime sur `started`
    (une séance finie a été démarrée) ; l'ordre des clés est figé (comparaison
    de doublons par le node)."""
    if started and ended:
        seance = SEANCE_TERMINEE
    elif started:
        seance = SEANCE_EN_COURS
    else:
        seance = SEANCE_ATTENTE
    return json.dumps({"seance": seance, "arret_vocal": bool(voice_hold)})
