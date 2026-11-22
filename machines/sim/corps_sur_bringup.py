"""Contrôle de fumée : le corps sûr DU BRINGUP est-il armé ? (lot A0-4, 21/11)

Pourquoi : l'épreuve CS relance son PROPRE corps sûr (validate-corps-sur.sh), elle n'éprouve
jamais celui que lance drive.launch.py dans le conteneur robot. Fumée 2026-11-20-1707 : ce
corps sûr s'est verrouillé seul (`capteur_perdu`, 17:08:38, pendant validate-namespace) et l'est
resté ; edition n°7 a fini rouge sur « aucun cmd_vel non nul », sans que rien ne dise pourquoi.
Verrouiller était CORRECT : un défaut ne libère jamais les roues. Le trou était dans le banc.

Un nœud figé plus de 0,30 s (PC chargé) se verrouille ainsi alors que le lidar n'a jamais
cessé : expérience du 21/11, SIGSTOP du seul nœud, 3 verrous sur 5 entre 0,4 et 0,6 s, aucun sur
5 à 0,25 s ou moins (point ouvert du README du package, décision de David). Le banc ne change
RIEN au nœud. Il exige un nœud ARME avant chaque épreuve qui fait rouler Didier. Il réarme
un verrou `capteur_perdu`, et lui seul, au plus REARMEMENTS_MAX fois par épreuve (la borne de
l'épreuve CS : deux par passe). Chaque réarmement est dit sur la page. Le réarmement passe par le topic `corps_sur/rearmer`, le geste
de David : le nœud le refuse tant que le capteur n'est pas sain depuis `sante_s`.

    python3 corps_sur_bringup.py [--deja <réarmements déjà faits pour cette épreuve>]

Dernière ligne : `CORPS_SUR_BRINGUP <arme|rouge> rearmements=<total> <raison> etat=<json>`.
Code de sortie 0 si armé, 1 sinon. La décision est PURE (`decider`, testée sans ROS par
packages/didier_core/test/unit/test_corps_sur_bringup.py) ; rclpy n'est importé que par main().
"""
import argparse
import json
import sys
import time
from collections.abc import Callable
from typing import Any

# Réarmements spontanés tolérés avant une épreuve (même borne que VERROUS_SPONTANES_MAX de l'épreuve CS).
REARMEMENTS_MAX = 2
# Seule cause réarmée par le banc : le capteur vu muet, ce que produit un nœud figé par la charge.
# JAMAIS e_stop ni superviseur_perdu : ceux-là viennent d'un geste ou d'une panne, pas du PC.
CAUSE_REARMABLE = "capteur_perdu"
ATTENTE_ARME_S = 30.0       # du démarrage du nœud à ARME : ≈ 4 s mesurées (sonde du 21/11)
ATTENTE_REARME_S = 5.0      # sante_s = 1,0 s, plus la marge d'un PC chargé

ARME, REARMER, ROUGE, ATTENDRE = "arme", "rearmer", "rouge", "attendre"


def decider(etat: dict[str, Any] | None, deja: int, max_rearmements: int = REARMEMENTS_MAX) -> tuple[str, str]:
    """État latché `corps_sur/etat` (dict, None si rien reçu) -> (action, raison).

    ARME seulement si l'état est ARME sur le terrain `sim`. DEMARRAGE : attendre (le nœud arme
    seul quand le capteur est sain, l'appelant borne l'attente). VERROU `capteur_perdu` sous la
    borne : réarmer. Tout le reste : rouge.
    """
    if etat is None:
        return ATTENDRE, "aucun état latché reçu de corps_sur/etat"
    if etat.get("terrain") != "sim":
        return ROUGE, f"terrain {etat.get('terrain')!r} : ce n'est pas la configuration de la sim"
    nom, cause = etat.get("etat"), etat.get("cause")
    if nom == "ARME":
        return ARME, "armé"
    if nom == "DEMARRAGE":
        return ATTENDRE, f"DEMARRAGE {cause}"
    if nom == "VERROU" and cause == CAUSE_REARMABLE:
        if deja < max_rearmements:
            return REARMER, f"VERROU {cause} spontané (nœud figé par la charge du PC)"
        return ROUGE, f"VERROU {cause} : déjà {deja} réarmement(s) pour cette épreuve (borne {max_rearmements})"
    return ROUGE, f"{nom} {cause} : jamais réarmé par le banc"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deja", type=int, default=0)
    args = ap.parse_args()

    import rclpy
    from rclpy.parameter import Parameter
    from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
    from std_msgs.msg import Empty
    from theatre_interfaces.msg import StringTime

    rclpy.init()
    n = rclpy.create_node("fumee_corps_sur_bringup", namespace="/didier",
                          parameter_overrides=[Parameter("use_sim_time", value=True)])
    etat: dict[str, Any] = {}
    latche = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                        reliability=ReliabilityPolicy.RELIABLE)
    n.create_subscription(StringTime, "corps_sur/etat", lambda m: etat.update(json.loads(m.msg)), latche)
    rearmer = n.create_publisher(Empty, "corps_sur/rearmer", 10)

    def tourner_jusqua(cond: Callable[[], bool], delai: float) -> None:
        fin = time.monotonic() + delai
        while time.monotonic() < fin and not cond():
            rclpy.spin_once(n, timeout_sec=0.05)

    deja = args.deja
    fin = time.monotonic() + ATTENTE_ARME_S
    action, raison = ATTENDRE, ""
    while True:
        rclpy.spin_once(n, timeout_sec=0.1)    # au moins un tour : l'état peut changer
        action, raison = decider(etat or None, deja)
        if action == REARMER:
            deja += 1
            print(f"réarmement n° {deja} : {raison}", flush=True)
            # Apparié AVANT de publier : un message parti avant la découverte se perd (vu le 21/11).
            tourner_jusqua(lambda: rearmer.get_subscription_count() > 0, ATTENTE_REARME_S)
            # Republié toutes les 1,5 s : le nœud refuse tant que le capteur n'est pas sain depuis
            # sante_s (1 s) — c'est le geste de David qui rappuie, compté comme UN réarmement.
            fin_rearme = time.monotonic() + ATTENTE_REARME_S
            while etat.get("etat") != "ARME" and time.monotonic() < fin_rearme:
                rearmer.publish(Empty())
                tourner_jusqua(lambda: etat.get("etat") == "ARME", 1.5)
            action, raison = decider(etat, deja)
            if action != ARME:
                action, raison = ROUGE, f"réarmement refusé ou sans effet : {raison}"
            else:
                raison = f"réarmé après VERROU {CAUSE_REARMABLE} spontané"
            break
        if action != ATTENDRE or time.monotonic() >= fin:
            break
    if action == ATTENDRE:
        action, raison = ROUGE, f"pas armé après {ATTENTE_ARME_S:.0f} s : {raison}"
    print(f"CORPS_SUR_BRINGUP {action} rearmements={deja} {raison} "
          f"etat={json.dumps(etat or None, ensure_ascii=False)}", flush=True)
    n.destroy_node()
    rclpy.try_shutdown()
    return 0 if action == ARME else 1


if __name__ == "__main__":
    sys.exit(main())
