"""Logique PURE du suivi du regard (gaze) — ZÉRO import ROS, entièrement testable.

Le robot suit une personne DU REGARD : ce module ne pilote QUE le cou (servo
`neck`, rotation panoramique autour de l'axe vertical). Il NE TOUCHE JAMAIS les
roues — aucune sortie ici ne concerne wheels/cmd_vel/e_stop (règle de sécurité
non négociable : télécommande > autonome, le regard ne déplace pas 50 kg).

Découpage volontaire (même philosophie que didier_drive) :
 - ICI : toute la logique de décision (mapping, lissage, slew, timeout, états),
   avec l'horloge passée en paramètre (now_ms) pour être testée sans ROS ni sleep.
 - DANS le node (gaze_follower_node.py) : uniquement les entrées/sorties ROS.

État machine :
 - IDLE    : pas de cible, cou au centre, on ne publie RIEN (le servo_node loggue
             chaque message reçu — inonder le topic au repos = spam de logs).
 - TRACKING: cible récente, on converge vers l'angle visé (slew rapide).
 - LOST    : cible perdue depuis > timeout → retour LENT au centre (slew réduit),
             puis IDLE une fois centré.
 - LOOK    : consigne IMPOSÉE par le topic `look` (« regarder », lot M2,
             docs/spec-aller-voir.md §7.1) : on rejoint l'angle (slew de
             suivi), on la TIENT hold_ms en ignorant les personnes, puis LOST
             (retour lent au centre) — une détection valide y reprend le suivi
             s'il est actif. Seul état qui publie AUSSI suivi désactivé : un
             « regarde à droite » n'exige pas le gaze ON.
"""

import math
from dataclasses import dataclass

from theatre_contrats import stringtime

# Bornes matérielles de la consigne servo (voir robot/actions/servo.py :
# INPUT_MIN=0, INPUT_MAX=99, mappés 0->0°, 99->max_pos=180°). On ne sort JAMAIS
# de cette plage, même si des paramètres exotiques sont passés (garde-fou méca).
CONSIGNE_MIN = 0
CONSIGNE_MAX = 99

# États internes.
IDLE = "idle"
TRACKING = "tracking"
LOST = "lost"
LOOK = "look"

# « Regarder » (topic `look`, spec-aller-voir.md §7.1) : geste CHIFFRÉ
# {"angle_deg": a, "hold_ms": h}, a > 0 = GAUCHE (convention ROS, comme le
# pivot). L'angle est converti en azimut ÉQUIVALENT (celui d'une personne vue
# sous cet angle) : la consigne passe par le MÊME mapping que le suivi
# (centre + sens × gain × azimut), donc par les sens et gains VALIDÉS au
# protocole du 12/07 — cou ET yeux (miroir) regardent du bon côté sans
# nouveau réglage. Échelle : celle du COU, dont la course utile du suivi
# (± gain consignes) vaut gain × 180/99 degrés (servo 0-99 -> 0-180°) :
# gain 20 -> ±36,4°. Le cou atteint donc l'angle demandé ; au-delà de sa
# course, saturé (journalisé par le node). Les yeux, eux, font ce qu'ils font
# pour une personne sous cet angle (gain propre, ils dardent).
# Convention de l'azimut : +1 = bord DROIT de l'image = « à ta droite »
# (caméra au buste, regard vers l'avant, cf. spec-metteur-en-scene.md) ;
# d'où azimut = −angle / course.
# Compat (premier contrat) : direction nommée -> azimut, course pleine.
LOOK_DIR_AZIMUTH = {"gauche": -1.0, "droite": 1.0, "devant": 0.0}
# Tenue, bornée CÔTÉ CONSOMMATEUR (le producteur est un LLM) : défaut si
# absente ou illisible, puis bornes.
LOOK_HOLD_DEFAULT_MS = 4000
LOOK_HOLD_MIN_MS = 1000
LOOK_HOLD_MAX_MS = 8000
# Un flux de `look` ne doit pas couper le suivi indéfiniment (revue M2) : au
# plus LOOK_MAX_REARMS réarmements de suite sans retour au suivi / au repos ;
# au-delà, la tenue en cours est coupée et tout `look` ignoré LOOK_LOCKOUT_MS.
LOOK_MAX_REARMS = 3
LOOK_LOCKOUT_MS = 4000


def consigne_to_radians(consigne):
    """Convertit une consigne servo 0-99 en radians pour le joint `neck` de l'URDF.

    Chaîne de correspondance (documentée pour la revue) :
      - servo.py mappe 0-99 -> 0..180° matériel (max_pos=180, centre 50 -> ~90°) ;
      - dans l'URDF (dadou_robot.urdf.xacro) le joint `neck` est CENTRÉ :
        lower=-pi/2, upper=+pi/2. Donc 0° matériel = -pi/2, 90° = 0, 180° = +pi/2.
    D'où : rad = (consigne/99 - 0.5) * pi
      - consigne 0  -> -pi/2 (-1.5708)
      - consigne 50 -> +0.0159 rad (quasi 0 ; 50 n'est pas exactement le milieu
        de 0-99 qui vaut 49.5 — quirk hérité du "centre=50" de servo.py, négligeable)
      - consigne 99 -> +pi/2 (+1.5708)
    """
    return (consigne / 99.0 - 0.5) * math.pi


def _bounded_hold(hold_ms):
    """Tenue lue tolérante : nombre fini -> borné [MIN, MAX] ; absent, booléen,
    texte, NaN -> défaut. Jamais d'exception, jamais de tenue infinie."""
    if isinstance(hold_ms, bool) or not isinstance(hold_ms, (int, float)) or not math.isfinite(hold_ms):
        return LOOK_HOLD_DEFAULT_MS
    return int(max(LOOK_HOLD_MIN_MS, min(LOOK_HOLD_MAX_MS, hold_ms)))


def look_course_deg(gain):
    """Course utile du cou en degrés : ± gain consignes, servo 0-99 -> 0-180°."""
    return gain * 180.0 / 99.0


@dataclass(frozen=True)
class LookOrder:
    azimuth: float      # azimut équivalent, borné [-1, 1]
    hold_ms: int        # tenue bornée [LOOK_HOLD_MIN_MS, LOOK_HOLD_MAX_MS]
    saturated: bool     # angle demandé au-delà de la course (saturé)


def parse_look(raw, course_deg):
    """Payload du topic `look` (StringTime) -> LookOrder, ou None (refus : jamais
    d'angle deviné). Contrat : JSON {"angle_deg": nombre fini, "hold_ms"} ;
    si "angle_deg" est présent il fait foi (illisible -> refus, pas de repli
    sur "dir"). Compat : {"dir": "gauche"|"droite"|"devant"}, ou le nom seul
    (JSON ou brut, salve de test à la main) — casse et blancs ignorés. Tenue
    absente ou illisible -> défaut. `course_deg` : look_course_deg(gain du cou).
    JAMAIS d'exception (revue M2 : un payload hostile tuait le node de PROD) :
    entier JSON géant (OverflowError de math.isfinite / de la division),
    imbrication profonde (RecursionError de json), course nulle -> refus."""
    try:
        return _parse_look(raw, course_deg)
    except (ValueError, TypeError, OverflowError, RecursionError, ZeroDivisionError):
        return None


def _parse_look(raw, course_deg):
    value = stringtime.decode_or_raw(raw, "look")
    if isinstance(value, dict):
        hold_ms = value.get("hold_ms")
        if "angle_deg" in value:
            angle = value["angle_deg"]
            if isinstance(angle, bool) or not isinstance(angle, (int, float)) or not math.isfinite(angle):
                return None
            raw_az = -angle / course_deg
            return LookOrder(max(-1.0, min(1.0, raw_az)), _bounded_hold(hold_ms), abs(raw_az) > 1.0)
        direction = value.get("dir")
    else:
        direction, hold_ms = value, None
    if not isinstance(direction, str):
        return None
    direction = direction.strip().lower()
    if direction not in LOOK_DIR_AZIMUTH:
        return None
    return LookOrder(LOOK_DIR_AZIMUTH[direction], _bounded_hold(hold_ms), False)


class LookGovernor:
    """Limiteur des réarmements de `look` (revue M2) — commun au cou et aux
    yeux (le node l'interroge une fois par ordre). decide() -> "ok" (ordre
    joué), "limit" (plus de LOOK_MAX_REARMS réarmements de suite : ordre
    refusé, le node COUPE la tenue en cours, verrou LOOK_LOCKOUT_MS) ou
    "locked" (verrou en cours : ignoré). `looking` : un geste a-t-il encore la
    main (tenue OU retour) ? Non -> la chaîne est finie, compteur remis à 0."""

    def __init__(self, max_rearms=LOOK_MAX_REARMS, lockout_ms=LOOK_LOCKOUT_MS):
        self.max_rearms = max_rearms
        self.lockout_ms = lockout_ms
        self._rearms = 0
        self._locked_until_ms = None

    def decide(self, looking, now_ms):
        if self._locked_until_ms is not None and now_ms < self._locked_until_ms:
            return "locked"
        if not looking:
            self._rearms = 0
            return "ok"
        self._rearms += 1
        if self._rearms > self.max_rearms:
            self._rearms = 0
            self._locked_until_ms = now_ms + self.lockout_ms
            return "limit"
        return "ok"


class GazeControl:
    """Logique de suivi du regard. Instancier une fois, appeler :
     - update(...) à CHAQUE message /vision/person reçu (cadence variable ~16 Hz) ;
     - tick(now_ms) à cadence FIXE (ex. 10 Hz) : renvoie la consigne cou 0-99 à
       publier, ou None s'il n'y a rien à publier (consigne inchangée / IDLE) ;
     - look(azimuth, hold_ms, now_ms) sur ordre `look` (cf. parse_look) ; cancel_look() quand
       une animation prend la main (le node le fait, cf. arbitrage).
    """

    def __init__(self, center=50, gain=20, direction_sign=1, confidence_min=0.4,
                 ema_alpha=0.4, slew_max=3, slew_return=1, timeout_ms=1500,
                 enabled=False):
        # center=50 : position de repos du cou (regard droit devant).
        self.center = center
        # gain=20 : amplitude MAX de balayage (±20 autour du centre -> [30,70]),
        # soit ~±0.64 rad (~±37°) via le mapping ci-dessus.
        #
        # ⚠️ NE PAS AUGMENTER CE GAIN (constat du 2026-09-14). Le commentaire
        # d'origine le disait « conservateur pour une première », ce qui invitait
        # à le monter. C'était écrit en croyant la caméra montée sur la tête :
        # en boucle FERMÉE, le gain n'est qu'une vitesse de convergence, la
        # boucle corrige. Or la caméra est FIXE SUR LE BUSTE (établi par David) :
        # le gaze est en boucle OUVERTE, donc ce gain EST L'ÉTALONNAGE qui
        # convertit un azimut d'image en angle réel de cou.
        # Et il tombe juste, par chance : azimut ±1 = bord d'image = ±38,5°
        # (champ webcam ≈77°, cf. docs/hardware/overview.md) ; gain=20 = ±37°.
        # Les deux coïncident à ~1,5° près. Monter le gain ferait pointer la
        # tête À CÔTÉ de la personne, systématiquement et sans rien pour le
        # rattraper. Si la webcam est un jour remplacée, ce gain doit être
        # RECALCULÉ sur le nouveau champ : gain ≈ 99 × (demi-FOV_deg / 180).
        # (Reste une non-linéarité de second ordre : un objectif sténopé donne
        # x_normalisé ∝ tan(θ), pas θ — le mapping linéaire sous-estime d'environ
        # 3° à mi-champ. Négligeable ici, à revoir si on passe en grand angle.)
        self.gain = gain
        # direction_sign=+1 : sens azimut -> cou. INCONNU MÉCANIQUEMENT tant que le
        # protocole caméra ne l'a pas tranché (même dette que le sens gauche/droite
        # des roues, cf. CLAUDE.md « Prochaines étapes »). +1 suppose : azimut +1
        # (personne au bord DROIT de l'image caméra) -> cou vers les consignes hautes.
        # À inverser en un seul paramètre si la caméra montre l'inverse.
        self.direction_sign = direction_sign
        # confidence_min=0.4 : sous ce seuil, la détection est jugée trop douteuse
        # pour bouger la tête (~plusieurs kg en haut du robot). Message ignoré, et
        # surtout il ne rafraîchit PAS le timeout -> une suite de détections faibles
        # finit par déclencher le retour au centre (LOST).
        self.confidence_min = confidence_min
        # Lissage EMA de l'azimut : amortit le bruit de la détection avant mapping.
        self.ema_alpha = ema_alpha
        # slew_max : variation MAX de consigne par tick en suivi (le servo saute
        # sinon instantanément à l'angle -> à-coups sur la mécanique de tête).
        self.slew_max = slew_max
        # slew_return : slew RÉDUIT pour le retour au centre en LOST (mouvement doux,
        # non urgent : plus personne à regarder).
        self.slew_return = slew_return
        # timeout_ms : sans détection valide depuis ce délai -> état LOST.
        self.timeout_ms = timeout_ms

        self.enabled = enabled
        self._reset()

    def _reset(self):
        """Remet toute la machine à l'état neutre (repos, plus aucune publication).
        Appelé au démarrage, sur désactivation, et sur "off" (reset complet exigé)."""
        self.position = float(self.center)   # position courante (float, slew continu)
        self.ema = None                       # azimut lissé (None = jamais vu)
        self.state = IDLE
        self.last_update_ms = None            # dernière détection VALIDE reçue
        self.last_published = None            # dernière consigne (int) réellement publiée
        # « Regarder » : actif de l'ordre jusqu'au retour au centre (LOOK puis
        # LOST) ou jusqu'à ce qu'une détection reprenne la main.
        self._look_active = False
        self._look_target = None              # consigne visée (float)
        self._look_hold_ms = 0
        self._look_until_ms = None            # fin de tenue, armée À L'ARRIVÉE sur la cible

    @property
    def looking(self):
        """Un « regarder » a-t-il la main (tenue ou retour au centre) ?"""
        return self._look_active

    def set_enabled(self, enabled):
        """Active/désactive le suivi. Désactivation = reset COMPLET de l'état
        (le node démarre désactivé : télécommande > autonome, toujours) — SAUF
        pendant un « regarder », qui va au bout (tenue bornée puis retour au
        centre) : désactiver le SUIVI n'annule pas un geste demandé, et
        _apply_enabled est rappelé à chaque message animation_state (un repos
        republié tuerait sinon le geste en vol). Seul cancel_look() le coupe."""
        self.enabled = enabled
        if not enabled and not self._look_active:
            self._reset()

    def look(self, azimuth, hold_ms, now_ms):
        """Ordre « regarder » (azimut équivalent et hold_ms déjà bornés par
        parse_look). Consigne = mapping du suivi sur l'azimut équivalent, bornée
        à la course du suivi (ceinture : azimut hors [-1, 1] sans effet). Un nouvel ordre remplace le précédent. La tenue
        court À PARTIR DE L'ARRIVÉE sur la consigne (« la TIENT hold_ms ») :
        trajet borné par le slew, donc durée totale bornée."""
        raw = self.center + self.direction_sign * self.gain * azimuth
        self._look_target = max(self.center - self.gain, min(self.center + self.gain, raw))
        self._look_hold_ms = int(hold_ms)
        self._look_until_ms = None
        self._look_active = True
        self.state = LOOK
        # La personne d'avant est oubliée : la reprise du suivi repartira d'une
        # détection FRAÎCHE (même règle que la sortie de LOST).
        self.ema = None
        self.last_update_ms = None

    def end_hold(self):
        """Coupe la TENUE (limiteur de réarmements) : retour lent au centre tout
        de suite, interrompu par une détection si le suivi est actif."""
        if self.state == LOOK:
            self.state = LOST

    def cancel_look(self):
        """Une animation prend la main : le geste tombe, reset complet (même
        contrat que set_enabled(False) hors geste — la reprise ré-émettra)."""
        if self._look_active:
            self._reset()

    def update(self, azimuth, elevation, confidence, now_ms):
        """À appeler à chaque message /vision/person.
        azimuth ∈ [-1..1] (+1 = bord droit image caméra), elevation ∈ [-1..1]
        (IGNORÉE : le cou ne fait que le panoramique, pas de joint de tilt pour
        l'instant), confidence ∈ [0..1]."""
        if not self.enabled:
            return
        # « Regarder » en tenue : les personnes sont IGNORÉES (spec §7.1).
        if self.state == LOOK:
            return
        # Détection trop peu sûre : on l'ignore ENTIÈREMENT (ni mouvement, ni
        # rafraîchissement du timeout) -> z=0.2 ne bouge pas la tête.
        if confidence < self.confidence_min:
            return
        # Pendant le retour au centre d'un « regarder » : la personne reprend
        # la main, le geste est fini.
        self._look_active = False
        # Lissage EMA (premier échantillon : on initialise directement dessus).
        if self.ema is None:
            self.ema = azimuth
        else:
            self.ema = self.ema_alpha * azimuth + (1.0 - self.ema_alpha) * self.ema
        self.last_update_ms = now_ms
        # (Ré)acquisition : depuis IDLE ou LOST on repart en suivi, en gardant la
        # position courante du cou (continuité du mouvement si on ré-attrape la cible).
        self.state = TRACKING

    def _target_tracking(self):
        """Consigne visée en suivi : centre + sens * gain * azimut_lissé, bornée
        à [centre-gain, centre+gain]."""
        raw = self.center + self.direction_sign * self.gain * self.ema
        low = self.center - self.gain
        high = self.center + self.gain
        return max(low, min(high, raw))

    def _slew_toward(self, target, step):
        """Rapproche self.position de target d'au plus `step` (protection méca)."""
        delta = target - self.position
        if abs(delta) <= step:
            self.position = float(target)
        elif delta > 0:
            self.position += step
        else:
            self.position -= step

    def tick(self, now_ms):
        """À appeler à cadence fixe. Renvoie la consigne 0-99 à publier, ou None."""
        # Désactivé : rien à publier et état réinitialisé (contrat de sécurité).
        # Exception unique : un « regarder » en cours va au bout (borné).
        if not self.enabled and not self._look_active:
            self._reset()
            return None

        # Au repos absolu (jamais de cible, ou déjà recentré) : silence total.
        if self.state == IDLE:
            return None

        # Fin de tenue du « regarder » -> LOST : retour lent au centre, qu'une
        # détection valide interrompt (reprise du suivi s'il est actif).
        if self.state == LOOK and self._look_until_ms is not None and now_ms >= self._look_until_ms:
            self.state = LOST

        # Bascule TRACKING -> LOST si la cible n'a pas été rafraîchie à temps.
        if self.state == TRACKING and self.last_update_ms is not None:
            if now_ms - self.last_update_ms > self.timeout_ms:
                self.state = LOST

        if self.state == LOOK:
            # Même slew que le suivi : ni rampe ni amorti nouveaux.
            self._slew_toward(self._look_target, self.slew_max)
            if self._look_until_ms is None and self.position == float(self._look_target):
                self._look_until_ms = now_ms + self._look_hold_ms
        elif self.state == TRACKING:
            self._slew_toward(self._target_tracking(), self.slew_max)
        else:  # LOST : retour lent au centre.
            self._slew_toward(self.center, self.slew_return)
            if self.position == float(self.center):
                # Centré : on repassera IDLE, mais on laisse cette itération publier
                # la consigne centre finale (le cou doit finir droit devant).
                self.state = IDLE
                # On oublie l'azimut lissé : une PROCHAINE détection réamorcera l'EMA
                # à sa propre valeur (ré-acquisition franche, sans traîner l'ancienne
                # cible — sinon le cou repart d'abord vers l'ancien côté).
                self.ema = None
                # Geste « regarder » terminé (centré) : suivi désactivé, le
                # prochain tick réinitialise et se tait.
                self._look_active = False

        # Consigne entière bornée aux limites servo (garde-fou méca).
        out = int(round(self.position))
        out = max(CONSIGNE_MIN, min(CONSIGNE_MAX, out))

        # Anti-spam : on ne republie que si la consigne a CHANGÉ (le servo_node
        # loggue chaque message ; à cible fixe et cou convergé -> plus rien).
        if out == self.last_published:
            return None
        self.last_published = out
        return out
