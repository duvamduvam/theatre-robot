"""didier_rehearsal — salle de répétition simulée (SIM-ONLY).

Package AUTONOME au sens de didier_drive : aucun import de dadou_utils_ros ni de
robot_config/matériel ; la SEULE dépendance vers robot.* est le module PUR
didier_core.diagnostic.journal (format boîte noire partagé) — jamais l'inverse. Il n'est JAMAIS lancé par
didier_bringup (test anti-fuite : robot/tests/unit/test_rehearsal_contract.py).
Étude : docs/etude-repetition-simulee.md (§11 architecture, §12 variante retenue).
"""
