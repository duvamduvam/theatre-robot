"""États globaux, péremptions, réarmement, durée bornée (spec A0 §5.5-5.6) — PUR.

    DEMARRAGE ──(capteur sain sante_s, superviseur présent si exigé, e_stop faux)──► ARME
    ARME ──(capteur perdu | superviseur perdu | e_stop vrai)──► VERROU(cause)
    VERROU ──(rearmer ET plus aucune cause ET capteur sain depuis sante_s)──► ARME

Toutes les horloges sont celle du nœud (secondes, float), passées en argument
comme dans `TwistDeadman` : aucun appel à l'heure système ici. Chaque appel
réévalue les transitions à l'instant donné (un `e_stop` vrai verrouille dans le
même appel, sans attendre le tic).

Interprétations écrites (la spec ne les dit pas) :
- le réarmement exige qu'AUCUNE cause ne soit présente, pas seulement celle du
  verrou (réarmer sous `e_stop` vrai laisserait passer une consigne avant le
  tic suivant) ;
- en DEMARRAGE, la cause publiée est la première condition non remplie :
  `e_stop`, `capteur_absent` (capteur pas sain maintenant), `superviseur_absent`,
  puis `sante_en_cours` (capteur sain depuis moins de `sante_s`) ;
- PAUSE_DUREE est un drapeau à part (`pause_duree`), pas un état : l'état reste
  ARME, la zone publiée devient PAUSE_DUREE et `filtre` met zéro.
"""
import math
from dataclasses import dataclass

DEMARRAGE = "DEMARRAGE"
ARME = "ARME"
VERROU = "VERROU"
PAUSE_DUREE = "PAUSE_DUREE"

# Causes (§5.6).
E_STOP = "e_stop"
CAPTEUR_ABSENT = "capteur_absent"
CAPTEUR_PERDU = "capteur_perdu"
SUPERVISEUR_ABSENT = "superviseur_absent"
SUPERVISEUR_PERDU = "superviseur_perdu"
SANTE_EN_COURS = "sante_en_cours"

# Un canal est MUET s'il n'a rien reçu depuis plus que ce délai : c'est le
# `timeout` de chaque entrée de twist_mux (packages/didier_drive/config/
# twist_mux.yaml, 0,5 s) — un fait du mux, pas un réglage du corps sûr.
DELAI_MUX_S = 0.5


@dataclass(frozen=True)
class ParametresGarde:
    capteur_perime_s: float
    sante_s: float
    superviseur_exige: bool
    superviseur_perime_s: float
    duree_max_mouvement_s: float
    pause_s: float


class _Canal:
    """Mémoire d'un canal pour la durée bornée."""

    def __init__(self) -> None:
        self.sortie_t: float | None = None
        self.sortie_non_nulle = False
        self.entree_non_nulle_t: float | None = None
        self.entree_nulle_depuis: float | None = None


class Garde:

    def __init__(self, params: ParametresGarde):
        self.p = params
        self.etat = DEMARRAGE
        self.cause = CAPTEUR_ABSENT
        self._balayage_t: float | None = None
        self._sain_depuis: float | None = None
        self._battement_t: float | None = None
        # Jamais reçu = faux, comme le mux (aucune source avant W1).
        self._e_stop = False
        self._canaux: dict[str, _Canal] = {}
        self._mouvement_depuis: float | None = None
        self.pause_duree = False

    # --- capteur, superviseur, arrêt d'urgence -----------------------------------------

    def _capteur_sain(self, t: float) -> bool:
        return self._balayage_t is not None and t - self._balayage_t <= self.p.capteur_perime_s

    def _superviseur_present(self, t: float) -> bool:
        return self._battement_t is not None and t - self._battement_t <= self.p.superviseur_perime_s

    def superviseur_etat(self, t: float) -> str:
        if not self.p.superviseur_exige:
            return "non_exige"
        return "present" if self._superviseur_present(t) else "absent"

    def balayage_valide(self, t: float) -> str:
        """Un balayage VALIDE (§4.3) vient d'arriver : il nourrit le chien de garde."""
        if not self._capteur_sain(t):
            self._sain_depuis = t
        self._balayage_t = t
        return self.tic(t)

    def battement(self, t: float) -> str:
        self._battement_t = t
        return self.tic(t)

    def noter_e_stop(self, valeur: bool, t: float) -> str:
        self._e_stop = bool(valeur)
        return self.tic(t)

    def _sain_depuis_assez(self, t: float) -> bool:
        return self._sain_depuis is not None and t - self._sain_depuis >= self.p.sante_s

    def _causes(self, t: float) -> list[str]:
        """Causes présentes à l'instant t, dans l'ordre de priorité de publication."""
        causes = []
        if self._e_stop:
            causes.append(E_STOP)
        if not self._capteur_sain(t):
            causes.append(CAPTEUR_PERDU)
        if self.p.superviseur_exige and not self._superviseur_present(t):
            causes.append(SUPERVISEUR_PERDU)
        return causes

    def tic(self, t: float) -> str:
        """Réévalue péremptions et transitions (minuterie 20 Hz du nœud) → l'état."""
        if not self._capteur_sain(t):
            self._sain_depuis = None
        causes = self._causes(t)
        if self.etat == ARME and causes:
            self.etat, self.cause = VERROU, causes[0]
        elif self.etat == DEMARRAGE:
            if causes:
                self.cause = {CAPTEUR_PERDU: CAPTEUR_ABSENT,
                              SUPERVISEUR_PERDU: SUPERVISEUR_ABSENT}.get(causes[0], causes[0])
            elif not self._sain_depuis_assez(t):
                self.cause = SANTE_EN_COURS
            else:
                self.etat, self.cause = ARME, ""
        self._evaluer_duree(t)
        return self.etat

    def rearmer(self, t: float) -> tuple[bool, str]:
        """`corps_sur/rearmer` : (accepté, raison). Refusé (et à journaliser) tant
        qu'une cause est là ou que le capteur n'est pas sain depuis `sante_s`."""
        self.tic(t)
        if self.etat != VERROU:
            return False, f"rien à réarmer (état {self.etat})"
        causes = self._causes(t)
        if causes:
            return False, f"cause présente : {', '.join(causes)}"
        if not self._sain_depuis_assez(t):
            return False, f"capteur sain depuis moins de {self.p.sante_s} s"
        self.etat, self.cause = ARME, ""
        return True, "réarmé"

    # --- durée bornée (§5.5) -------------------------------------------------------------

    def _canal(self, canal: str) -> _Canal:
        return self._canaux.setdefault(canal, _Canal())

    def noter_entree(self, canal: str, t: float, nulle: bool) -> None:
        """Une consigne est arrivée sur `canal` (nulle = v et ω nuls)."""
        c = self._canal(canal)
        if nulle:
            if c.entree_nulle_depuis is None:
                c.entree_nulle_depuis = t
        else:
            c.entree_non_nulle_t = t
            c.entree_nulle_depuis = None
        self._evaluer_duree(t)

    def noter_sortie(self, canal: str, t: float, nulle: bool) -> None:
        """Le filtre a publié sur la sortie de `canal`."""
        c = self._canal(canal)
        c.sortie_t = t
        c.sortie_non_nulle = not nulle
        self._evaluer_duree(t)

    def _en_mouvement(self, t: float) -> bool:
        return any(c.sortie_non_nulle and c.sortie_t is not None and t - c.sortie_t <= DELAI_MUX_S
                   for c in self._canaux.values())

    def _calme_depuis(self, t: float) -> float | None:
        """Instant depuis lequel TOUTES les entrées sont nulles ou muettes, None
        si l'une d'elles est encore active."""
        depuis = -math.inf
        for c in self._canaux.values():
            debut = []
            if c.entree_nulle_depuis is not None:
                debut.append(c.entree_nulle_depuis)
            if c.entree_non_nulle_t is not None:
                muet_depuis = c.entree_non_nulle_t + DELAI_MUX_S
                if t >= muet_depuis:
                    debut.append(muet_depuis)
                elif c.entree_nulle_depuis is None:
                    return None
            depuis = max(depuis, min(debut) if debut else -math.inf)
        return depuis

    def _evaluer_duree(self, t: float) -> None:
        if self.p.duree_max_mouvement_s <= 0:
            self.pause_duree = False
            return
        if self.pause_duree:
            calme = self._calme_depuis(t)
            if calme is not None and t - calme >= self.p.pause_s:
                self.pause_duree = False
                self._mouvement_depuis = None
            return
        if not self._en_mouvement(t):
            self._mouvement_depuis = None
            return
        if self._mouvement_depuis is None:
            self._mouvement_depuis = t
        if t - self._mouvement_depuis > self.p.duree_max_mouvement_s:
            self.pause_duree = True
