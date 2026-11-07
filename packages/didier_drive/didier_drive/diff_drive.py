"""Cinématique différentielle : Twist ROS <-> consignes roues normalisées [-1, 1].

Convention REP 103 : x vers l'avant, z vers le haut, vitesse angulaire
positive = rotation anti-horaire (vers la gauche) vue de dessus.
C'est le pont entre le topic cmd_vel (geometry_msgs/Twist) et la
commande PWM des roues (paire [gauche, droite] dans [-1, 1]).
"""


class DiffDrive:

    def __init__(self, wheel_separation, max_wheel_speed):
        """wheel_separation en mètres, max_wheel_speed en m/s (vitesse roue à consigne 1.0)."""
        if wheel_separation <= 0 or max_wheel_speed <= 0:
            raise ValueError("wheel_separation et max_wheel_speed doivent être > 0")
        self.wheel_separation = wheel_separation
        self.max_wheel_speed = max_wheel_speed

    def twist_to_wheels(self, linear_x, angular_z):
        """(m/s, rad/s) -> (gauche, droite) dans [-1, 1].

        En cas de saturation, les deux consignes sont réduites du même facteur
        pour préserver le rayon de courbure demandé.
        """
        left = linear_x - angular_z * self.wheel_separation / 2
        right = linear_x + angular_z * self.wheel_separation / 2

        left /= self.max_wheel_speed
        right /= self.max_wheel_speed

        overshoot = max(abs(left), abs(right))
        if overshoot > 1.0:
            left /= overshoot
            right /= overshoot

        return left, right

    def wheels_to_twist(self, left, right):
        """(gauche, droite) dans [-1, 1] -> (linear_x m/s, angular_z rad/s).

        Inverse de twist_to_wheels, sans reconstruction de la saturation
        (une paire déjà saturée donne juste le Twist correspondant à cette
        paire, pas à la commande d'origine avant écrêtage).
        """
        linear_x = (left + right) / 2 * self.max_wheel_speed
        angular_z = (right - left) * self.max_wheel_speed / self.wheel_separation

        return linear_x, angular_z
