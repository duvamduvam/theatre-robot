"""Le contrat Action est STRUCTUREL : toute action des nodes doit implémenter
update() et process(). Avant, c'était une convention de nommage silencieuse —
une classe incomplète ne cassait qu'au runtime, sur le robot."""
import unittest

from robot.actions.action import Action


class TestContratAction(unittest.TestCase):

    def test_toutes_les_actions_du_systeme_sont_des_actions(self):
        from robot.actions.abstract_json_actions import AbstractJsonActions
        from robot.actions.servo import Servo
        from robot.actions.wheels import Wheels
        from robot.sequences.animation_manager import AnimationManager
        for cls in (AbstractJsonActions, Servo, Wheels, AnimationManager):
            self.assertTrue(issubclass(cls, Action), cls.__name__)

    def test_action_incomplete_ne_s_instancie_pas(self):
        class Incomplete(Action):
            def update(self, msg):
                return msg
            # process() manquant volontairement

        with self.assertRaises(TypeError):
            Incomplete()


if __name__ == "__main__":
    unittest.main()
