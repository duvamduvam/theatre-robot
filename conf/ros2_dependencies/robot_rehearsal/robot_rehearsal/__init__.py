"""robot_rehearsal — salle de répétition simulée (SIM-ONLY).

Package AUTONOME au sens de robot_drive : aucun import de robot.* ni de
dadou_utils_ros, stdlib seulement côté logique pure. Il n'est JAMAIS lancé par
robot_bringup (test anti-fuite : robot/tests/unit/test_rehearsal_contract.py).
Étude : docs/etude-repetition-simulee.md (§11 architecture, §12 variante retenue).
"""
