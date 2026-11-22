"""Nœud corps_sur (spec A0 §3, §6) — MINCE : abonnements, publications, minuterie 20 Hz.

AUCUNE règle ici (§6.1) : chaque message devient un appel à `moteur.CorpsSur`, chaque retour un
message. Noms, types et QoS viennent de `contrat` (gravés par test/test_contrat_node.py).

    ros2 run didier_corps_sur corps_sur_node --ros-args -r __ns:=/didier -p config:=<yaml>

Sûr par construction (§3.1) : le nœud est EN LIGNE devant twist_mux. Mort, figé ou pas lancé, il
ne publie plus rien sur les sorties `_sur` : le mux se tait, le deadman met zéro en 400 ms.
Configuration absente ou refusée (`reglages`) : erreur lisible et sortie, AUCUNE sortie publiée.
Une exception pendant un rappel : zéro sur les trois sorties, puis sortie en erreur — jamais de
relance automatique (respawn faux dans drive.launch.py : un redémarrage effacerait un verrou).
"""
import os
import sys
import time
from typing import Any

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import Twist
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rosidl_runtime_py.utilities import get_message
from theatre_interfaces.msg import StringTime

from didier_corps_sur import contrat
from didier_corps_sur.moteur import CorpsSur, Sortie
from didier_corps_sur.reglages import ReglagesError, charger_reglages


def _qos(nom: str) -> QoSProfile:
    q = contrat.QOS[nom]
    return QoSProfile(
        depth=q.profondeur,
        reliability=ReliabilityPolicy.RELIABLE if q.fiable else ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.TRANSIENT_LOCAL if q.latche else DurabilityPolicy.VOLATILE)


class CorpsSurNode(Node):

    def __init__(self) -> None:
        super().__init__(contrat.NOM_NOEUD)
        self.declare_parameter("config", contrat.CONFIG_DEFAUT)
        chemin = str(self.get_parameter("config").value)
        # Lève ReglagesError (fichier absent, borne dure franchie, invariant du pivot violé) :
        # main() le dit et sort AVANT toute publication.
        reglages = charger_reglages(chemin, os.environ.get("ROS_DOMAIN_ID"))
        self.corps = CorpsSur(reglages)
        self.get_logger().info(
            f"configuration {chemin} : terrain {reglages.terrain}, vue {self.corps.vue}, "
            f"superviseur exigé {reglages.garde.superviseur_exige}, "
            f"témoin exigé {reglages.balayage.temoin.exige}")

        self._sorties = {canal: self.create_publisher(Twist, nom, _qos(nom))
                         for canal, nom in contrat.SORTIES.items()}
        self._etat_pub = self.create_publisher(StringTime, contrat.ETAT, _qos(contrat.ETAT))
        self._diag_pub = self.create_publisher(DiagnosticArray, contrat.DIAGNOSTICS,
                                               _qos(contrat.DIAGNOSTICS))
        self._etat_publie: str | None = None
        self._rappel_scan_max_s: float | None = None
        self._tics = 0

        for canal, nom in contrat.ENTREES.items():
            self.create_subscription(Twist, nom, self._rappel_consigne(canal), _qos(nom))
        self.create_subscription(get_message(contrat.TYPES[contrat.SCAN]), contrat.SCAN,
                                 self._sur_scan, _qos(contrat.SCAN))
        self.create_subscription(get_message(contrat.TYPES[contrat.E_STOP]), contrat.E_STOP,
                                 self._sur_e_stop, _qos(contrat.E_STOP))
        self.create_subscription(get_message(contrat.TYPES[contrat.BATTEMENT]), contrat.BATTEMENT,
                                 self._sur_battement, _qos(contrat.BATTEMENT))
        self.create_subscription(get_message(contrat.TYPES[contrat.REARMER]), contrat.REARMER,
                                 self._sur_rearmer, _qos(contrat.REARMER))
        self.create_timer(contrat.PERIODE_TIC_S, self._sur_tic)
        self._publier_etat()

    # --- conversions ------------------------------------------------------------------------

    def _maintenant(self) -> float:
        return float(self.get_clock().now().nanoseconds) * 1e-9

    def _publier(self, sorties: list[Sortie]) -> None:
        for s in sorties:
            twist = Twist()                 # les quatre composantes non lues restent à zéro
            twist.linear.x = s.v
            twist.angular.z = s.w
            self._sorties[s.canal].publish(twist)

    def zero_partout(self) -> None:
        """Dernier geste avant de mourir sur une exception : zéro sur les trois sorties."""
        for pub in self._sorties.values():
            pub.publish(Twist())

    def _publier_etat(self) -> None:
        texte = self.corps.etat_json(self._maintenant())
        if texte == self._etat_publie:
            return
        self._etat_publie = texte
        msg = StringTime()
        msg.msg = texte
        msg.time = self.get_clock().now().nanoseconds // 1_000_000
        msg.anim = False
        self._etat_pub.publish(msg)
        self.get_logger().info(f"état : {texte}")

    def _publier_diagnostic(self) -> None:
        d = self.corps.diagnostic(self._maintenant(), self._rappel_scan_max_s)
        self._rappel_scan_max_s = None
        status = DiagnosticStatus()
        status.level = bytes([d.niveau])
        status.name = f"{self.get_namespace().rstrip('/')}/{contrat.NOM_NOEUD}"
        status.message = d.message
        status.hardware_id = "corps_sur"
        status.values = [KeyValue(key=k, value=v) for k, v in d.valeurs]
        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()
        array.status = [status]
        self._diag_pub.publish(array)

    # --- rappels ----------------------------------------------------------------------------

    def _rappel_consigne(self, canal: str) -> Any:
        def rappel(msg: Twist) -> None:
            self._publier(self.corps.consigne(canal, self._maintenant(), msg.linear.x, msg.angular.z))
            self._publier_etat()
        return rappel

    def _sur_scan(self, msg: Any) -> None:
        debut = time.perf_counter()
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self._publier(self.corps.balayage(self._maintenant(), stamp, msg.angle_min,
                                          msg.angle_increment, msg.ranges))
        duree = time.perf_counter() - debut
        self._rappel_scan_max_s = max(duree, self._rappel_scan_max_s or 0.0)
        self._publier_etat()

    def _sur_e_stop(self, msg: Any) -> None:
        self._publier(self.corps.e_stop(bool(msg.data), self._maintenant()))
        self._publier_etat()

    def _sur_battement(self, _msg: Any) -> None:
        self._publier(self.corps.battement(self._maintenant()))
        self._publier_etat()

    def _sur_rearmer(self, _msg: Any) -> None:
        accepte, raison = self.corps.rearmer(self._maintenant())
        # UN site d'appel par sévérité : rclpy refuse qu'une même ligne journalise tantôt en info,
        # tantôt en warning (ValueError « Logger severity cannot be changed between calls »). Le
        # 21/11 en sim, un refus après un réarmement accepté a ainsi TUÉ le nœud (zéro et sortie).
        if accepte:
            self.get_logger().info(f"réarmement accepté : {raison}")
        else:
            self.get_logger().warning(f"réarmement REFUSÉ : {raison}")
        self._publier_etat()

    def _sur_tic(self) -> None:
        self._publier(self.corps.tic(self._maintenant()))
        self._publier_etat()
        self._tics += 1
        if self._tics % contrat.TICS_PAR_DIAGNOSTIC == 0:
            self._publier_diagnostic()


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    try:
        noeud = CorpsSurNode()
    except ReglagesError as e:
        # Plus aucune sortie : aucun mouvement autonome tant que la configuration est refusée.
        print(f"corps_sur : configuration REFUSÉE, le nœud s'arrête — {e}", file=sys.stderr, flush=True)
        rclpy.try_shutdown()
        sys.exit(2)
    code = 0
    try:
        rclpy.spin(noeud)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception as e:  # noqa: BLE001 — tout défaut ARRÊTE : zéro, journal, sortie en erreur
        noeud.get_logger().fatal(f"exception, zéro sur les trois sorties et arrêt : {e!r}")
        try:
            noeud.zero_partout()
        finally:
            code = 1
    finally:
        noeud.destroy_node()
        rclpy.try_shutdown()
    sys.exit(code)


if __name__ == "__main__":
    main()
