"""`NoeudAppareil` : la plomberie ROS commune à tout appareil (spec L3 décisions 2, 4, 10).

Ce que fait le nœud de tout appareil, écrit UNE fois :
- état latché (`<appareil>/etat`, enveloppe theatre_contrats.appareils, qos.latched()) publié à
  chaque changement et au plus tard toutes les PERIODE_ETAT_S (2 s) — règle `Battement` ;
- `diagnostics` à 1 Hz : OK / WARN (un ordre refusé depuis moins de REFUS_RECENT_S) / ERROR (un
  organe `absent` ou `erreur`) — règle `niveau_diagnostic`, lue sur l'enveloppe seule ;
- lecture du sha déployé (`conf/DEPLOY_SHA`, "dev" si absent : sim) — `lire_sha` ;
- arrêt propre : SIGINT/SIGTERM -> pilotes au repos AVANT de sortir (code 0) ; exception dans
  un rappel -> pilotes au repos, puis sortie code 1 ; pilote refusé -> sortie code 2.

Composition, pas héritage : `NoeudAppareil` TIENT un nœud rclpy (`self.ros`), l'appareil n'en
dérive pas (pas de classe mère riche, spec L3 décision 1). Le nœud mince de l'appareil ne fait
que brancher : `abonner(topic, rappel)` puis `tourner()` ; aucune règle.

Les parties pures (Battement, niveau_diagnostic, lire_sha) n'importent rien de ROS : rclpy, les
messages et theatre_contrats.qos sont importés À L'APPEL (le module s'importe sur le PC).
Un appareil n'utilise JAMAIS use_sim_time : il vit hors de Gazebo, horloge murale.
"""
import json
import os
import pathlib
import sys
import time
from typing import Any, Callable, Mapping

from theatre_contrats import appareils, stringtime
from theatre_gabarit import pilotes as _pilotes

PERIODE_ETAT_S = 2.0
PERIODE_DIAGNOSTIC_S = 1.0
PERIODE_TIC_S = 0.05            # 20 Hz (spec L3 décision 13)
REFUS_RECENT_S = 10.0
DIAGNOSTICS = "diagnostics"
# Niveaux de diagnostic_msgs/DiagnosticStatus (OK=0, WARN=1, ERROR=2).
OK, WARN, ERROR = 0, 1, 2
CODE_SORTIE_EXCEPTION = 1


def chemin_sha(projet: str) -> str:
    """Convention des Pi (avant L2e) : ~/ros2_ws/src/<projet>/conf/DEPLOY_SHA, vu du conteneur."""
    return f"/home/ros2_ws/src/{projet}/conf/DEPLOY_SHA"


def lire_sha(chemin: str) -> str:
    """Sha écrit par Ansible (variable `sha_deploye`) ; absent, vide ou illisible -> "dev"."""
    try:
        contenu = pathlib.Path(chemin).read_text(encoding="utf-8").strip()
    except OSError:
        return appareils.SHA_DEV
    return contenu or appareils.SHA_DEV


class Battement:
    """Publier l'état si son contenu a changé, ou si PERIODE_ETAT_S s'est écoulée depuis la
    dernière publication. Horloge passée en argument (secondes)."""

    def __init__(self, periode_s: float = PERIODE_ETAT_S) -> None:
        self.periode_s = periode_s
        self._cle: Any = None
        self._t_s: float | None = None

    def a_publier(self, cle: Any, maintenant_s: float) -> bool:
        du = self._t_s is None or cle != self._cle or maintenant_s - self._t_s >= self.periode_s
        if du:
            self._cle, self._t_s = cle, maintenant_s
        return du


def niveau_diagnostic(organes: list, refus: Mapping | None, maintenant_ms: int) -> tuple:
    """(niveau, message) d'après l'enveloppe : ERROR > WARN > OK."""
    malades = [f"{o['nom']} {o['sante']}" for o in organes if o["sante"] != _pilotes.OK]
    if malades:
        return ERROR, ", ".join(malades)
    if refus is not None and maintenant_ms - refus["t_ms"] < REFUS_RECENT_S * 1000:
        return WARN, f"ordre refusé : {refus['code']}"
    return OK, "ok"


def maintenant_ms() -> int:
    return int(time.time() * 1000)


class NoeudAppareil:
    """Le nœud ROS d'un appareil. `fabriques` = {"sim": …, "materiel": …} ; le pilote construit
    est `self.pilote`. Puis `demarrer(etat, au_repos, tic)` : `etat(t_ms)` rend (organes, refus)
    de la logique, `au_repos()` met les pilotes au repos, `tic(t_ms)` avance la logique."""

    def __init__(self, nom_noeud: str, appareil: str, fabriques: Mapping[str, Callable[[], Any]]) -> None:
        import rclpy
        from theatre_interfaces.msg import StringTime
        self._StringTime = StringTime
        if not rclpy.ok():
            rclpy.init()
        self.ros = rclpy.create_node(nom_noeud)
        self.appareil = appareil
        self.ros.declare_parameter("pilote", _pilotes.MATERIEL)
        self.ros.declare_parameter("config", "")
        self.ros.declare_parameter("sha_fichier", chemin_sha(appareil))
        self.nom_pilote = self.ros.get_parameter("pilote").value
        try:
            self.pilote = _pilotes.choisir(self.nom_pilote, fabriques, os.environ.get("ROS_DOMAIN_ID"))
        except _pilotes.PiloteRefuse as refus:
            self.ros.get_logger().error(str(refus))
            sys.exit(refus.code_sortie)
        self.config = self.ros.get_parameter("config").value
        self.sha = lire_sha(self.ros.get_parameter("sha_fichier").value)
        self._battement = Battement()
        self._etat: Callable[[int], tuple] = lambda _t: ([], None)
        self._au_repos: Callable[[], None] = lambda: None

    def demarrer(self, etat: Callable[[int], tuple], au_repos: Callable[[], None],
                 tic: Callable[[int], None]) -> None:
        """Pilotes au repos AVANT la première publication, puis timers (tic 20 Hz, diag 1 Hz)."""
        from diagnostic_msgs.msg import DiagnosticArray
        from theatre_contrats import qos
        self._etat, self._au_repos = etat, au_repos
        self._au_repos()
        self._pub_etat = self.ros.create_publisher(
            self._StringTime, appareils.REGISTRE[self.appareil]["etat"], qos.latched())
        self._pub_diag = self.ros.create_publisher(DiagnosticArray, DIAGNOSTICS, 10)
        self._tic = tic
        self.ros.create_timer(PERIODE_TIC_S, self._sur_tic)
        self.ros.create_timer(PERIODE_DIAGNOSTIC_S, self._publier_diagnostic)
        self.publier()

    def abonner(self, topic: str, rappel: Callable[[Any, int], None]) -> None:
        """Ordre StringTime (qos.volatile(10)) : `rappel(valeur décodée, t_ms)`, puis état publié.
        Valeur décodée par stringtime.decode_or_raw (JSON, ou la chaîne brute)."""
        from theatre_contrats import qos

        def _sur_message(msg: Any) -> None:
            t = maintenant_ms()
            rappel(stringtime.decode_or_raw(msg.msg, topic), t)
            self.publier(t)
        self.ros.create_subscription(self._StringTime, topic, _sur_message, qos.volatile(10))

    def _sur_tic(self) -> None:
        t = maintenant_ms()
        self._tic(t)
        self.publier(t)

    def publier(self, t_ms: int | None = None) -> None:
        t = maintenant_ms() if t_ms is None else t_ms
        organes, refus = self._etat(t)
        if not self._battement.a_publier(json.dumps([organes, refus]), t / 1000.0):
            return
        texte = appareils.encoder_etat(self.appareil, self.nom_pilote, self.sha, t, organes, refus)
        self._pub_etat.publish(self._StringTime(msg=texte, time=0, anim=False))

    def _publier_diagnostic(self) -> None:
        from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
        t = maintenant_ms()
        organes, refus = self._etat(t)
        niveau, message = niveau_diagnostic(organes, refus, t)
        statut = DiagnosticStatus(level=bytes([niveau]), name=self.appareil, message=message,
                                  hardware_id=self.appareil)
        tableau = DiagnosticArray(status=[statut])
        tableau.header.stamp = self.ros.get_clock().now().to_msg()
        self._pub_diag.publish(tableau)

    def tourner(self) -> None:
        """spin jusqu'à SIGINT/SIGTERM (sortie 0) ou une exception (sortie 1) ; pilotes au repos
        AVANT de sortir dans les deux cas."""
        import rclpy
        from rclpy.executors import ExternalShutdownException
        code = 0
        try:
            rclpy.spin(self.ros)
        except (KeyboardInterrupt, ExternalShutdownException):
            pass
        except Exception as erreur:  # noqa: BLE001 — toute exception d'un rappel : repos, puis 1
            self.ros.get_logger().error(f"exception, pilotes au repos puis sortie : {erreur!r}")
            code = CODE_SORTIE_EXCEPTION
        finally:
            self._au_repos()
            self.ros.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
        sys.exit(code)
