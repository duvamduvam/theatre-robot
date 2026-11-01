"""Logique PURE du suivi de personne aux ROUES — ZÉRO import ROS, testable.

Le robot suit une personne EN SE DÉPLAÇANT : rotation pour la garder au centre
de l'image, avance pour maintenir la distance (la HAUTEUR de silhouette dans
l'image sert de proxy de distance — caméra monoculaire, cf. dadou_vision_ros
vision/tracking/target_picker.py, topic /vision/person_box).

SÉCURITÉ (cf. CLAUDE.md — ce module commande les 50 kg du robot) :
 - Sortie UNIQUE : un couple (lin, ang) destiné à cmd_vel_follow, entrée du
   twist_mux à priorité 20 — STRUCTURELLEMENT sous la télécommande (100) et le
   web (50) : reprendre la main physique écrase toujours le suivi.
 - Démarre DÉSACTIVÉ (enabled=False). Toute désactivation publie UN zéro franc
   puis se tait (le twist_mux bascule sur les autres entrées, le twist_deadman
   aval inonde de zéros — double rempart).
 - Personne perdue (silence /vision/person_box > timeout_ms) -> zéro franc
   immédiat puis silence. PAS de « retour lent » comme le gaze : on ne roule
   pas vers une cible qu'on ne voit plus.
 - Marche ARRIÈRE INTERDITE par défaut (allow_reverse=False) : la caméra
   regarde devant, reculer c'est rouler en aveugle.
 - Plafonds ABSOLUS codés en dur (ABS_MAX_LIN/ANG) : mêmes valeurs que le
   plafond dur du pilotage web — des paramètres exotiques ne peuvent pas les
   dépasser.
 - direction_sign : sens azimut -> rotation INCONNU tant que le protocole
   caméra ne l'a pas tranché (même dette que le cou/gaze et que le sens
   gauche/droite des roues, cf. feuille de route). À valider EN SIM d'abord,
   puis protocole caméra roues hors sol AVANT tout usage au sol.

Découpage identique à robot.move.gaze_control (le modèle du genre) :
 - ICI : décision (deadzones, gains, slew, timeout, états), horloge en
   paramètre (now_ms) pour tester sans ROS ni sleep.
 - DANS le node (person_follower_node.py) : uniquement les I/O ROS.

États :
 - IDLE     : pas de cible. Silence total (aucune publication).
 - TRACKING : cible récente. Publie (lin, ang) À CHAQUE tick, zéros compris
   (contrairement au gaze anti-spam : le twist_mux et le deadman aval vivent
   d'un FLUX — un trou de publication ferait retomber l'arbitrage).
"""

from dataclasses import dataclass

# Plafonds ABSOLUS (garde-fou ultime, mêmes valeurs que le plafond dur du
# pilotage web, cf. robot_web drive_to_twist) : AUCUN paramètre ne peut les
# dépasser, ils bornent les paramètres eux-mêmes au constructeur.
ABS_MAX_LIN = 0.5   # m/s
ABS_MAX_ANG = 1.0   # rad/s

# États internes.
IDLE = "idle"
TRACKING = "tracking"


@dataclass(frozen=True)
class FollowConfig:
    """Réglages du suivi — dataclass gelée (même pattern que VadConfig côté
    dadou_vision_ros) : un seul objet à passer au node, valeurs documentées
    champ par champ ici, UNE fois."""

    # Sens azimut -> rotation. +1 suppose caméra montée droite, regardant
    # DEVANT : azimut +1 (personne au bord droit de l'image caméra) ->
    # rotation HORAIRE (ang négatif, convention REP-103 : +z = anti-horaire)
    # pour la recentrer. INCONNU tant que le protocole caméra n'a pas tranché,
    # inversable en un seul paramètre — même approche que gaze_control.
    direction_sign: int = 1
    # Sous ce seuil, la détection est ignorée ET ne rafraîchit pas le timeout
    # (comme le gaze) : des détections douteuses en série finissent en cible
    # perdue -> zéro. On ne déplace pas 50 kg sur un doute.
    confidence_min: float = 0.4
    # Zone morte d'azimut : personne « à peu près au centre » -> zéro rotation
    # (sinon le robot danserait en permanence sur le bruit de détection).
    az_deadzone: float = 0.15
    ang_gain: float = 0.8       # rad/s par unité d'azimut lissé
    max_ang: float = 0.6        # borné par ABS_MAX_ANG au constructeur
    # Hauteur de silhouette visée : 0.55 = la personne occupe 55 % de la
    # hauteur d'image à la distance de confort. height > target = trop proche,
    # height < target = trop loin.
    target_height: float = 0.55
    height_deadzone: float = 0.08
    lin_gain: float = 1.5       # m/s par unité d'erreur de hauteur
    max_lin: float = 0.25       # borné par ABS_MAX_LIN au constructeur
    # Marche arrière : interdite par défaut (caméra vers l'avant = recul
    # aveugle). Si un jour activée, elle reste bornée par max_lin.
    allow_reverse: bool = False
    # Second lissage local (la perception lisse déjà, mais elle arrive à
    # cadence variable ; ce lissage-ci est le nôtre, à notre cadence).
    ema_alpha: float = 0.4
    # Slew : variation MAX par tick des sorties (à 10 Hz, lin_slew=0.05 ->
    # 0,5 m/s² max). Protège la mécanique et évite les à-coups de masse.
    lin_slew: float = 0.05
    ang_slew: float = 0.15
    # Sans détection valide depuis ce délai -> cible perdue -> zéro franc.
    # 600 ms : ~10 frames perception manquées ; plus long laisserait rouler
    # vers une cible fantôme (le deadman roues 400 ms reste l'ultime rempart
    # en aval, sur le silence TOTAL de la chaîne, pas sur la cible).
    timeout_ms: int = 600


class FollowControl:
    """Logique de suivi aux roues. Instancier une fois, appeler :
     - update(...) à CHAQUE message /vision/person_box (~16 Hz variable) ;
     - tick(now_ms) à cadence FIXE (ex. 10 Hz) : renvoie (lin, ang) à publier
       sur cmd_vel_follow, ou None s'il ne faut RIEN publier (IDLE/désactivé).
    """

    def __init__(self, config: FollowConfig = FollowConfig(), *, enabled=False):
        self.config = config
        # Plafonds effectifs : les valeurs de config sont bornées par les
        # plafonds ABSOLUS — des paramètres exotiques ne passent pas.
        self.max_ang = min(abs(config.max_ang), ABS_MAX_ANG)
        self.max_lin = min(abs(config.max_lin), ABS_MAX_LIN)

        self.enabled = enabled
        # Zéro de sécurité en attente : hors de _reset() VOLONTAIREMENT — un
        # reset ne doit jamais annuler un zéro de sécurité pas encore publié.
        self._pending_stop = False
        self._reset()

    def _reset(self):
        """État neutre : plus aucune publication au prochain tick (hors zéro
        de sécurité en attente, géré séparément par _pending_stop)."""
        self.state = IDLE
        self.ema_azimuth = None
        self.ema_height = None
        self.last_update_ms = None
        # Sorties courantes (point de départ du slew).
        self.lin = 0.0
        self.ang = 0.0

    def set_enabled(self, enabled):
        """Active/désactive le suivi. Toute désactivation d'un suivi actif =
        reset complet + UN zéro franc publié au prochain tick (on ne laisse
        jamais le mux sur la dernière consigne non nulle — et un zéro de trop
        ne coûte rien si on était déjà à l'arrêt)."""
        was_enabled = self.enabled
        self.enabled = enabled
        if not enabled and was_enabled:
            self._reset()
            self._pending_stop = True

    def update(self, azimuth, height, confidence, now_ms):
        """À appeler à chaque message /vision/person_box.
        azimuth ∈ [-1..1] (+1 = bord droit image caméra), height ∈ [0..1]
        (hauteur de silhouette / hauteur d'image), confidence ∈ [0..1]."""
        if not self.enabled:
            return
        cfg = self.config
        if confidence < cfg.confidence_min:
            return
        if self.ema_azimuth is None:
            self.ema_azimuth = azimuth
            self.ema_height = height
        else:
            self.ema_azimuth = (cfg.ema_alpha * azimuth
                                + (1.0 - cfg.ema_alpha) * self.ema_azimuth)
            self.ema_height = (cfg.ema_alpha * height
                               + (1.0 - cfg.ema_alpha) * self.ema_height)
        self.last_update_ms = now_ms
        self.state = TRACKING

    def _target_outputs(self):
        """Consignes visées (avant slew) depuis l'état lissé courant."""
        cfg = self.config
        # Rotation : zéro dans la zone morte, sinon proportionnel à l'azimut.
        # Signe : azimut +1 (droite image) -> rotation horaire (ang < 0) pour
        # recentrer, d'où le « - » (modulé par direction_sign, cf. FollowConfig).
        if abs(self.ema_azimuth) <= cfg.az_deadzone:
            ang = 0.0
        else:
            ang = -cfg.direction_sign * cfg.ang_gain * self.ema_azimuth
        ang = max(-self.max_ang, min(self.max_ang, ang))

        # Avance : proportionnelle à l'erreur de distance (hauteur), zéro dans
        # la zone morte. err > 0 = personne trop loin -> avancer.
        err = cfg.target_height - self.ema_height
        if abs(err) <= cfg.height_deadzone:
            lin = 0.0
        else:
            lin = cfg.lin_gain * err
        floor = -self.max_lin if cfg.allow_reverse else 0.0
        lin = max(floor, min(self.max_lin, lin))
        return lin, ang

    def _slew(self, current, target, step):
        delta = target - current
        if abs(delta) <= step:
            return float(target)
        return current + (step if delta > 0 else -step)

    def tick(self, now_ms):
        """À appeler à cadence fixe. Renvoie (lin, ang) à publier, ou None."""
        # Zéro de sécurité en attente (désactivation en plein mouvement) :
        # publié UNE fois, même désactivé — c'est la seule publication
        # autorisée hors enabled.
        if self._pending_stop:
            self._pending_stop = False
            return (0.0, 0.0)

        if not self.enabled:
            return None

        if self.state == IDLE:
            return None

        # Cible perdue : zéro franc IMMÉDIAT (pas de slew — on arrête, on ne
        # « ralentit » pas vers une cible invisible), puis silence (IDLE).
        if (self.last_update_ms is None
                or now_ms - self.last_update_ms > self.config.timeout_ms):
            self._reset()
            return (0.0, 0.0)

        target_lin, target_ang = self._target_outputs()
        self.lin = self._slew(self.lin, target_lin, self.config.lin_slew)
        self.ang = self._slew(self.ang, target_ang, self.config.ang_slew)
        return (self.lin, self.ang)
