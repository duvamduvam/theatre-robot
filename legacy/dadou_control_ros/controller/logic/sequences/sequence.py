class Sequence:
    audio_path = None
    audio_length = None

    lights_positions = []
    face_positions = []
    neck_positions = []
    wheel_positions = []


    def __init__(self, name):
        self.name = name


class NeckPosition:
    def __init__(self, time, position):
        self.time = time
        self.position = position


class WheelPosition:
    def __init__(self, time, left, right):
        self.time = time
        self.left = left
        self.right = right


class LightPosition:
    def __init__(self, time, duration, mode):
        self.time = time
        self.duration = duration
        self.mode = mode

