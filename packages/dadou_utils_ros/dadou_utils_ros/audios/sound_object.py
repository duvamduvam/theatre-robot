import logging
import os
from enum import IntEnum
from multiprocessing import Process
from timeit import default_timer
import simpleaudio as sa
from playsound import playsound

from pydub import AudioSegment, playback

from dadou_utils_ros.audios.time_singleton import TimeSingleton
from dadou_utils_ros.utils.time_utils import TimeUtils
#sudo apt-get install mpg123

class State(IntEnum):
    PLAY = 1
    STOP = 2
    PAUSE = 3
    LOOP = 4


class SoundObject:

    starting_time = 0
    current_state = State.STOP

    audio_process = None
    audio_background_process = None

    def __init__(self, audio, datas={}, duration=None):
        self.audio = audio
        logging.info('load sound ' + audio)
        #self.audio_segment = AudioSegment.from_mp3(audio_folder+audio_name)
        #TODO fix from mp3
        self.duration = duration
        self.play_obj = None
        self.pause_duration = 0
        self.pause_time = 0

    @staticmethod
    def get_duration(audio):
        return int(AudioSegment.from_mp3(audio).duration_seconds * 1000)

    def play(self, background_sound=False):
        if self.current_state.value == State.PAUSE.value:
            self.resume()
        elif self.current_state.value == State.STOP.value:
            #sound_object = sa.WaveObject.from_wave_file(self.audio)
            #self.play_obj = sound_object.play()
            #self.play_obj.wait_done()
            #elf.play_obj = sa.play_buffer(self.audio, 2, 2, 44100) #play(self.audio_segment)
            #if self.audio_process:
            #    self.stop()

            process = Process(name="playsound", target=self.lunch_play_process)
            process.start()  # Inititialize Process

            if background_sound:
                self.audio_background_process = process
            else:
                self.audio_process = process

            self.current_state = State.PLAY
            self.starting_time = default_timer()

            #TimeSingleton.audio_length = len(self.audio_segment)
        #self.current_position = 0

        """self.play_obj = simpleaudio.play_buffer(
            self.audio_segment.raw_data,
            num_channels=self.audio_segment.channels,
            bytes_per_sample=self.audio_segment.sample_width,
            sample_rate=self.audio_segment.frame_rate
        )"""

    def lunch_play_process(self):
        #playsound(self.audio)
        os.system("mpg123 -o alsa:hw:0,0 -q {}".format(self.audio))

    def is_playing(self):
        return default_timer() < (self.starting_time+self.duration)

    def stop(self):
        if self.audio_process:
            self.audio_process.terminate()
        if self.audio_background_process:
            self.audio_background_process.terminate()
        self.audio_process, self.audio_background_process = (None, None)
        self.current_state = State.STOP

    def pause(self):
        if self.current_state.value == State.PLAY.value:
            self.pause_duration = default_timer() - self.starting_time
            self.pause_time = default_timer()
            self.stop()
            logging.info('pause playing at {}'.format(str(self.pause_duration)))
            self.current_state = State.PAUSE

    def resume(self):
        self.starting_time += default_timer() - self.pause_time
        self.play_from(self.pause_duration)
        self.current_state = State.PLAY

    def play_from(self, start_time):
        audio_split = self.audio_segment[start_time*1000:]
        self.play_obj = playback._play_with_simpleaudio(audio_split)
        self.current_state = State.PLAY
        """self.play_obj = simpleaudio.play_buffer(
            audio_split.raw_data,
            num_channels=audio_split.channels,
            bytes_per_sample=audio_split.sample_width,
            sample_rate=audio_split.frame_rate
        )"""

    #def get_duration(self):
    #    TimeSingleton.audio_duration = self.audio_segment.duration_seconds
    #    logging.info('duration : {}'.format(str(TimeSingleton.audio_duration)))
    #    return round(TimeSingleton.audio_duration, 2)

    #def is_playing(self):
    #    return self.play_obj.is_playing()

    def display_time(self):
        if self.is_playing():
            TimeSingleton.audio_position = default_timer() - self.starting_time
            return TimeUtils.formatted_time(TimeSingleton.audio_position)
        else:
            return 0

    def get_audio_data_display(self, width):
        max_frame = 4500000000
        #for i in range(int(audio.frame_count())):
        #    frame_value = int.from_bytes(audio.get_frame(i), 'little')
        #    if frame_value > max_frame:
        #        max_frame = abs(frame_value)

        nb_frames_pixel = self.audio_segment.frame_count()/width
        display_data = []
        for i in range(width):
            base = i*nb_frames_pixel
            total_for_pixel = 0
            for j in range(int(nb_frames_pixel)):
                total_for_pixel += int.from_bytes(self.audio_segment.get_frame(int(base+j)), 'little')
            average = total_for_pixel / nb_frames_pixel
            display_data.append(average/max_frame)
            #display_data.append(int.from_bytes(audio.get_frame(int(base)), 'little') / max_frame)

        return display_data




