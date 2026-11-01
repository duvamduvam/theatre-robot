from dadou_utils_ros.singleton import SingletonMeta


class StaticValue(metaclass=SingletonMeta):
    values = {}

    @staticmethod
    def get(key):
        if key in StaticValue.values:
            return StaticValue.values[key]


    @staticmethod
    def set(key, value):
        StaticValue.values[key] = value