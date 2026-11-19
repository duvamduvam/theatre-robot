"""Transformation d'une consigne (spec A0 §5.2-5.3) — PUR.

`filtrer(v, w, canal, etat, params) → (v', w', motif)`, dans cet ordre :
1. consigne non finie → zéro, `consigne_invalide` ;
2. état global autre que ARME → zéro, motif = l'état ;
3. zone ARRET → zéro, `ARRET` ; puis PAUSE_DUREE → zéro, `PAUSE_DUREE` ;
4. mouvement vers une région non vue → zéro (`avant_aveugle`, `recul_aveugle`,
   `tour_aveugle`), sauf le tour toléré (autorisé ET avant vue) ;
5. plafonds du canal : k = min(1, v_max/|v|, w_max/|ω|), appliqué aux DEUX ;
6. zone RALENTI → les deux composantes × `facteur_ralenti`.

RÈGLE GRAVÉE : le filtre ne change jamais la courbure. Il met tout à zéro ou il
réduit v et ω du même facteur ; il ne supprime jamais une seule composante.

Écart à la lettre de la spec (plus strict, écrit) : dans le cas du tour toléré,
le plafond angulaire est min(w_max du canal, w_max_aveugle), pas w_max_aveugle
seul — un `w_max_aveugle` plus grand que le plafond du canal ne relâche rien.
`motif` vaut None quand la consigne passe (éventuellement réduite).
"""
import math
from collections.abc import Mapping
from dataclasses import dataclass

from didier_corps_sur.couverture import ARRIERE, AVANT, REGIONS
from didier_corps_sur.garde import ARME
from didier_corps_sur.zones import ARRET, RALENTI

CANAUX = ("anim", "follow", "web")
CONSIGNE_INVALIDE = "consigne_invalide"
AVANT_AVEUGLE = "avant_aveugle"
RECUL_AVEUGLE = "recul_aveugle"
TOUR_AVEUGLE = "tour_aveugle"
MOTIF_PAUSE = "PAUSE_DUREE"


@dataclass(frozen=True)
class Plafond:
    v_max: float
    w_max: float


@dataclass(frozen=True)
class ParametresFiltre:
    plafonds: Mapping[str, Plafond]
    facteur_ralenti: float
    w_max_aveugle: float
    angulaire_aveugle_autorise: bool


@dataclass(frozen=True)
class EtatFiltre:
    """Photographie de la situation au moment de filtrer. `vue` : {région: bool}
    (forme de `couverture.vue_de`) ; une région absente compte NON vue."""
    etat: str
    zone: str
    pause_duree: bool
    vue: Mapping[str, bool]


def filtrer(v: float, w: float, canal: str, etat: EtatFiltre,
            params: ParametresFiltre) -> tuple[float, float, str | None]:
    if canal not in params.plafonds:
        raise ValueError(f"filtre : canal inconnu {canal!r} (attendu parmi {sorted(params.plafonds)})")
    # 1. Seuls linear.x et angular.z sont lus (le nœud met les autres à zéro).
    if not (math.isfinite(v) and math.isfinite(w)):
        return 0.0, 0.0, CONSIGNE_INVALIDE
    # 2.
    if etat.etat != ARME:
        return 0.0, 0.0, etat.etat
    # 3.
    if etat.zone == ARRET:
        return 0.0, 0.0, ARRET
    if etat.pause_duree:
        return 0.0, 0.0, MOTIF_PAUSE
    if v == 0.0 and w == 0.0:
        return 0.0, 0.0, None
    # 4.
    vue = etat.vue
    if v > 0 and not vue.get(AVANT, False):
        return 0.0, 0.0, AVANT_AVEUGLE
    if v < 0 and not vue.get(ARRIERE, False):
        return 0.0, 0.0, RECUL_AVEUGLE
    plafond = params.plafonds[canal]
    w_max = plafond.w_max
    if w != 0 and not all(vue.get(r, False) for r in REGIONS):
        if params.angulaire_aveugle_autorise and vue.get(AVANT, False):
            w_max = min(w_max, params.w_max_aveugle)
        else:
            return 0.0, 0.0, TOUR_AVEUGLE
    # 5.
    k = 1.0
    if v != 0:
        k = min(k, plafond.v_max / abs(v))
    if w != 0:
        k = min(k, w_max / abs(w))
    v_sortie, w_sortie = v * k, w * k
    # 6. Un palier, pas une proportion (plancher PWM, étude §3.2).
    if etat.zone == RALENTI:
        v_sortie *= params.facteur_ralenti
        w_sortie *= params.facteur_ralenti
    return v_sortie, w_sortie, None
