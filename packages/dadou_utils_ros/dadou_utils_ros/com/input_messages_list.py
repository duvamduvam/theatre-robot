import copy

from dadou_utils_ros.singleton import SingletonMeta


class InputMessagesList(metaclass=SingletonMeta):

    def __init__(self):
        self.messages = {}

    def add_msg(self, msg):
        self.messages.update(msg)

    def has_msg(self):
        return len(self.messages) != 0

    def pop_msg(self):
        msg = {}
        if self.has_msg():
            msg = copy.copy(self.messages)
            self.messages = {}
        return msg

