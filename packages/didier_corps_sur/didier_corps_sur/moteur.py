"""Le corps sûr ASSEMBLÉ (spec A0 §3.3, §5) — PUR : ce que fait le nœud, sans rclpy.

`corps_sur_node.py` convertit les messages en appels et les retours en messages ; toute règle
vit ici ou dans les modules assemblés (geometrie, balayage, couverture, zones, garde, filtre,
reglages). Ce module s'ajoute aux sept de la spec (A0-4) pour tenir sa règle « le nœud n'a
aucun if de règle » (§6.1) : la séquence des appels, le zéro anticipé, l'état publié et les
diagnostics se testent ainsi sans ROS.

Horloge : celle du nœud (secondes, float), passée à chaque appel ; rien ici ne lit l'heure.

LE ZÉRO ANTICIPÉ (§3.3) : à l'instant où le corps passe en BLOCAGE (état global autre que ARME,
zone ARRET ou pause de durée), un Twist NUL part sur chaque canal ACTIF, sans attendre la
prochaine consigne de la source (jusqu'à 200 ms à 5 Hz). C'est la seule publication qui ne
répond pas à une entrée ; elle ne peut être que nulle.

Choix écrits ici (la spec ne les dit pas, tous dans le sens qui arrête) :
- un canal est ACTIF s'il a reçu une demande depuis moins de `FENETRE_ACTIF_S` = 1,0 s, le
  DOUBLE du délai du mux (0,5 s) : à la frontière, mieux vaut un zéro de trop (il ne peut que
  masquer une source plus basse, jamais la télécommande, prio 100) qu'un canal oublié ;
- le zéro anticipé part aussi quand le blocage naît pendant le traitement d'une demande : les
  AUTRES canaux actifs reçoivent leur zéro avant la sortie (nulle) de la demande en cours ;
- l'horodatage du balayage précédent ne fait que croître : un `stamp` qui recule (horloge
  remise à zéro, republieur fou) invalide les balayages jusqu'à le dépasser — le capteur est
  alors perdu, donc verrou (sûr).
"""
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass

from didier_corps_sur.balayage import Lecture, lire_balayage
from didier_corps_sur.couverture import RegionCouverte, calculer_couverture, vue_de
from didier_corps_sur.filtre import CANAUX, EtatFiltre, filtrer
from didier_corps_sur.garde import ARME, DELAI_MUX_S, PAUSE_DUREE, VERROU, DEMARRAGE, Garde
from didier_corps_sur.reglages import Reglages
from didier_corps_sur.zones import ARRET, Zones

# Pas de la grille de couverture (§5.2 : « au pas de 5 cm »).
PAS_COUVERTURE_M = 0.05
# Arrondi de `d_min_m` dans l'état publié (§5.7 : 5 cm, pour ne pas republier à chaque balayage).
ARRONDI_D_MIN_M = 0.05
FENETRE_ACTIF_S = 2 * DELAI_MUX_S

# Niveaux de diagnostic_msgs/DiagnosticStatus (OK, WARN, ERROR), sans importer ROS.
OK, WARN, ERROR = 0, 1, 2


@dataclass(frozen=True)
class Sortie:
    """Un Twist à publier sur la sortie `_sur` du canal (`motif` : pourquoi il est réduit à
    zéro, None s'il passe, éventuellement plafonné)."""
    canal: str
    v: float
    w: float
    motif: str | None


@dataclass(frozen=True)
class Diagnostic:
    niveau: int
    message: str
    valeurs: tuple[tuple[str, str], ...]


def arrondir_d_min(d: float) -> float | None:
    """`d_min_m` publié : arrondi à 5 cm ; None si aucun point valide (`inf`)."""
    if not math.isfinite(d):
        return None
    return round(round(d / ARRONDI_D_MIN_M) * ARRONDI_D_MIN_M, 2)


class CorpsSur:

    def __init__(self, reglages: Reglages):
        r = reglages
        self.reglages = r
        self.couverture: dict[str, RegionCouverte] = calculer_couverture(
            r.caisse, r.lidar, r.balayage.masques_deg, r.zones.marge_arret_m,
            PAS_COUVERTURE_M, r.part_aveugle_max)
        self.vue = vue_de(self.couverture)
        self.garde = Garde(r.garde)
        self.zones = Zones(r.zones)
        self._stamp_precedent: float | None = None
        self._lecture: Lecture | None = None
        self._balayage_recu_t: float | None = None
        self._entree_t: dict[str, float] = {}
        self._refus: dict[str, str] = {}
        # Au démarrage, le corps est bloqué (DEMARRAGE) : aucun zéro anticipé à émettre.
        self._bloque = True

    # --- état -------------------------------------------------------------------------------

    def bloque(self) -> bool:
        return self.garde.etat != ARME or self.zones.zone == ARRET or self.garde.pause_duree

    def _motif_blocage(self) -> str:
        if self.garde.etat != ARME:
            return self.garde.etat
        if self.zones.zone == ARRET:
            return ARRET
        return PAUSE_DUREE

    def _etat_filtre(self) -> EtatFiltre:
        return EtatFiltre(self.garde.etat, self.zones.zone, self.garde.pause_duree, self.vue)

    def _zeros_si_bascule(self, t: float, sauf: str | None = None) -> list[Sortie]:
        """Zéro anticipé : seulement au PASSAGE en blocage, sur les canaux actifs."""
        bloque = self.bloque()
        zeros = []
        if bloque and not self._bloque:
            motif = self._motif_blocage()
            for canal in CANAUX:
                t_entree = self._entree_t.get(canal)
                if canal != sauf and t_entree is not None and t - t_entree < FENETRE_ACTIF_S:
                    self.garde.noter_sortie(canal, t, True)
                    zeros.append(Sortie(canal, 0.0, 0.0, motif))
        self._bloque = bloque
        return zeros

    # --- entrées ----------------------------------------------------------------------------

    def balayage(self, t: float, stamp_s: float, angle_min: float, increment: float,
                 distances: Sequence[float]) -> list[Sortie]:
        """Un `LaserScan` reçu à l'instant t → les zéros anticipés à publier."""
        r = self.reglages
        lecture = lire_balayage(r.balayage, r.caisse, r.lidar, stamp_s, self._stamp_precedent, t,
                                angle_min, increment, list(distances))
        if self._stamp_precedent is None or stamp_s > self._stamp_precedent:
            self._stamp_precedent = stamp_s
        self._lecture = lecture
        self._balayage_recu_t = t
        self.zones.observer(lecture.d_min_m, lecture.valide)
        if lecture.valide:
            self.garde.balayage_valide(t)
        else:
            self.garde.tic(t)
        return self._zeros_si_bascule(t)

    def consigne(self, canal: str, t: float, v: float, w: float) -> list[Sortie]:
        """Une demande sur `canal` → les Twist à publier, DANS L'ORDRE : zéros anticipés des
        autres canaux, puis la sortie de ce canal (une sortie par entrée), puis un zéro si le
        blocage naissait après elle."""
        if canal not in CANAUX:
            raise ValueError(f"corps_sur : canal inconnu {canal!r}")
        self._entree_t[canal] = t
        self.garde.noter_entree(canal, t, v == 0.0 and w == 0.0)
        self.garde.tic(t)
        sorties = self._zeros_si_bascule(t, sauf=canal)
        v_sortie, w_sortie, motif = filtrer(v, w, canal, self._etat_filtre(), self.reglages.filtre)
        self.garde.noter_sortie(canal, t, v_sortie == 0.0 and w_sortie == 0.0)
        if motif is not None:
            self._refus[canal] = motif
        sorties.append(Sortie(canal, v_sortie, w_sortie, motif))
        return sorties + self._zeros_si_bascule(t)

    def e_stop(self, valeur: bool, t: float) -> list[Sortie]:
        self.garde.noter_e_stop(valeur, t)
        return self._zeros_si_bascule(t)

    def battement(self, t: float) -> list[Sortie]:
        self.garde.battement(t)
        return self._zeros_si_bascule(t)

    def tic(self, t: float) -> list[Sortie]:
        """Minuterie 20 Hz : péremptions (capteur, superviseur), durée bornée."""
        self.garde.tic(t)
        return self._zeros_si_bascule(t)

    def rearmer(self, t: float) -> tuple[bool, str]:
        """`corps_sur/rearmer` → (accepté, raison) ; un refus est à journaliser."""
        resultat = self.garde.rearmer(t)
        self._zeros_si_bascule(t)
        return resultat

    # --- sorties d'observation --------------------------------------------------------------

    def _temoin(self) -> str:
        temoin = self.reglages.balayage.temoin
        if not temoin.exige:
            return "non_exige"
        if self._lecture is not None and self._lecture.temoin_points >= temoin.points_min:
            return "ok"
        return "absent"

    def etat(self, t: float) -> dict[str, object]:
        """Le contenu de `corps_sur/etat` (§5.7)."""
        d_min = self._lecture.d_min_m if self._lecture is not None else math.inf
        return {
            "etat": self.garde.etat,
            "cause": self.garde.cause,
            "zone": PAUSE_DUREE if self.garde.pause_duree else self.zones.zone,
            "d_min_m": arrondir_d_min(d_min),
            "vue": dict(self.vue),
            "superviseur": self.garde.superviseur_etat(t),
            "temoin": self._temoin(),
            "terrain": self.reglages.terrain,
        }

    def etat_json(self, t: float) -> str:
        return json.dumps(self.etat(t), ensure_ascii=False)

    def diagnostic(self, t: float, duree_rappel_scan_max_s: float | None) -> Diagnostic:
        """`diagnostics` (1 Hz) : l'état plus la santé du capteur et les derniers refus (§5.7).
        ERROR en VERROU ; WARN en DEMARRAGE, et sur le terrain réel tant que le superviseur ou
        le témoin ne sont pas exigés (limite permanente, écrite aussi dans le YAML)."""
        etat = self.etat(t)
        limites = [nom for nom in ("superviseur", "temoin")
                   if self.reglages.terrain == "reel" and etat[nom] == "non_exige"]
        if self.garde.etat == VERROU:
            niveau = ERROR
        elif self.garde.etat == DEMARRAGE or limites:
            niveau = WARN
        else:
            niveau = OK
        message = f"{etat['etat']} {etat['cause']}".strip() + f", zone {etat['zone']}"
        if limites:
            message += " ; non exigé(s) : " + ", ".join(limites)
        lecture = self._lecture
        age = None if self._balayage_recu_t is None else t - self._balayage_recu_t
        valeurs = [(cle, json.dumps(etat[cle], ensure_ascii=False)) for cle in etat]
        valeurs += [
            ("age_dernier_balayage_s", "null" if age is None else f"{age:.3f}"),
            ("rayons", str(lecture.rayons) if lecture else "0"),
            ("points_valides", str(lecture.points_valides) if lecture else "0"),
            ("motifs_balayage", json.dumps(list(lecture.motifs) if lecture else ["aucun_balayage"])),
            ("duree_rappel_scan_max_ms",
             "null" if duree_rappel_scan_max_s is None else f"{duree_rappel_scan_max_s * 1000:.2f}"),
        ]
        valeurs += [(f"refus_{canal}", self._refus.get(canal, "")) for canal in CANAUX]
        return Diagnostic(niveau, message, tuple(valeurs))
