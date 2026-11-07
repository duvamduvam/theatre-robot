from dadou_utils_ros.singleton import SingletonMeta


class TimeSingleton(metaclass=SingletonMeta):

    audio_duration = 0
    audio_position = 0

    @staticmethod
    def get_percentage_pos():
        if TimeSingleton.audio_position != 0:
            return TimeSingleton.audio_position/TimeSingleton.audio_duration
        else:
            return 0


