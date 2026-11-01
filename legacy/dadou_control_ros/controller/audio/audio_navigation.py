import logging
from enum import Enum
from timeit import default_timer

#from controller.control_factory import ControlFactory
from dadou_utils_ros.utils.time_utils import TimeUtils


class State(Enum):
    PLAY = 1
    STOP = 2
    PAUSE = 3
    LOOP = 4


class AudioNav:
    current_state = State.STOP
    current_position = 0
    starting_time = 0
    audio_length = 10000
    str_time = 0
    #sequence_management = ControlFactory().sequence_management

    def play(self):
        self.current_position = (default_timer() - self.starting_time) / self.audio_length
        logging.info('continue playing current pos {}'.format(self.current_position))

    def start(self):
        logging.info('start playing')
        self.starting_time = default_timer()
        self.current_position = 0
        self.current_state = State.PLAY

    def stop(self):
        #self.sequence_management.audio_segment.stop()  
        self.current_state = State.STOP

    def pause(self):
        self.current_state = State.PAUSE

    def is_playing(self):
        return self.current_state == State.PLAY

    def display_time(self):
        if self.is_playing():
            diff = default_timer() - self.starting_time
            return TimeUtils.formatted_time(diff)
        else:
            return 0





