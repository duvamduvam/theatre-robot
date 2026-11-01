"""Audio manager action.

Responsibilities:
 - keep track of the current audio being played and its metadata (duration, background flag);
 - map high-level bus messages to JSON-defined audio sequences;
 - apply volume changes/fades through ALSA (`amixer`);
 - ensure the audio library playlists/index stay in sync with the filesystem.
"""

# pip3 install sound-player
# https://github.com/Krozark/sound-player/blob/master/example.py
import glob
import json
import logging
import os
import threading
import time
from _decimal import Decimal, ROUND_DOWN
from os.path import exists

from dadou_utils_ros.audios.sound_object import SoundObject
from dadou_utils_ros.misc import Misc
from dadou_utils_ros.utils.time_utils import TimeUtils
from robot.robot_static import AUDIO_DEVICE_ID, DEFAULT_VOLUME_LEVEL, TIME, JSON_AUDIOS_DATAS, \
    BACKGROUND
from dadou_utils_ros.utils_static import AUDIO, AUDIOS_DIRECTORY, KEY, STOP, NAME, JSON_AUDIOS, \
    EXPRESSION, FACE, DURATION
from robot.actions.abstract_json_actions import AbstractJsonActions

#TODO check : https://maelfabien.github.io/machinelearning/Speech8/#iv2a-noise-reduction

VOLUME_COMMAND = "amixer cset numid={} {}% &"
FONDU_TIME_STEP = 100
FONDU_STEP = 2


class AudioManager(AbstractJsonActions):

    # Constantes (immuables) : restent au niveau classe.
    silence = "audios/silence.wav"
    new_play_timeout = 2000

    def __init__(self, config, json_manager):
        super().__init__(config=config, json_manager=json_manager, json_file=config[JSON_AUDIOS], action_type=AUDIO)
        # État par instance (était au niveau classe = partagé, piège Python ;
        # playlist=[] surtout, mutable partagé entre toutes les instances).
        self.playlist = []
        self.current_audio = None
        self.current_audio_name = None
        self.start_time = 0
        self.fondu_last_time = 0
        self.stopping = False
        self.config = config
        self.json_manager = json_manager
        # `audios-data.json` stores metadata (duration/background flag) computed offline.
        self.recorded_audio_data = self.json_manager.open_json(self.config[JSON_AUDIOS_DATAS])

        self.volume_default = config[DEFAULT_VOLUME_LEVEL]
        self.volume = self.volume_default
        self.change_volume(self.volume_default)

    def index_audios(self):
        """Scan the audio directory and reconcile metadata (add/remove entries)."""
        audio_datas = []
        for subdir, dirs, files in os.walk(self.config[AUDIOS_DIRECTORY]):
            files.sort()
            for file in files:
                if ".wav" in file or ".mp3" in file:
                    path = os.path.join(subdir, file)
                    path = path.replace(self.config[AUDIOS_DIRECTORY], "")
                    audio_datas.append(path)

        #delete values not in audio directories
        to_delete = []
        for record_key, record_value in self.recorded_audio_data.items():
            if record_key not in audio_datas:
                logging.info("remove audio key {}".format(record_key))
                to_delete.append(record_key)

        for delete in to_delete:
            self.recorded_audio_data.pop(delete)

        #add new audio to file
        for audio_path in audio_datas:
            if not audio_path in self.recorded_audio_data:
                duration = SoundObject.get_duration(self.config[AUDIOS_DIRECTORY]+"/"+audio_path)
                logging.info("new audio {} with duration {}".format(audio_path, duration))
                self.recorded_audio_data[audio_path] = {DURATION: float(duration)}

        self.json_manager.write_json(self.recorded_audio_data, self.config[JSON_AUDIOS_DATAS])

    def get_audio_length(self):
        if self.current_audio_name and self.current_audio_name in self.recorded_audio_data:
            return self.recorded_audio_data[self.current_audio_name][DURATION]

    def is_background_sound(self):
        if (self.current_audio_name and self.current_audio_name in self.recorded_audio_data
                and BACKGROUND in self.recorded_audio_data[self.current_audio_name]):
            return self.recorded_audio_data[self.current_audio_name][BACKGROUND]

    def play_sound(self, audio):
        if exists(self.config[AUDIOS_DIRECTORY]+audio):
            if self.current_audio_name and audio in self.current_audio_name and not TimeUtils.is_time(self.start_time, self.new_play_timeout):
                return False
            if self.current_audio and not self.is_background_sound():
                self.current_audio.stop()

            if self.volume != self.volume_default:
                self.change_volume(self.volume_default)

            self.current_audio_name = audio
            self.current_audio = SoundObject(self.config[AUDIOS_DIRECTORY]+audio, duration=self.get_audio_length())
            self.current_audio.play(self.is_background_sound())
            self.start_time = TimeUtils.current_milli_time()

            return True
        else:
            logging.error("audio {} don't exist".format(self.config[AUDIOS_DIRECTORY]+audio))
            return False

    def stop_sound(self):
        if self.current_audio:
            logging.info("stop sound")
            self.current_audio.stop()
            self.current_audio_name = ""

    def stop_sound_fondu(self):
        if not self.volume <= 20:
            if TimeUtils.is_time(self.fondu_last_time, FONDU_TIME_STEP):
                self.stopping = True
                self.change_volume(self.volume)
                self.fondu_last_time = TimeUtils.current_milli_time()
                self.volume -= FONDU_STEP
        else:
            self.stop_sound()
            time.sleep(1)
            self.volume = self.volume_default
            self.change_volume(self.volume)

    def change_volume(self, volume):
        logging.info("change sound : {}".format(VOLUME_COMMAND.format(self.config[AUDIO_DEVICE_ID], volume)))
        if volume == self.volume_default:
            self.stopping = False
        os.system(VOLUME_COMMAND.format(self.config[AUDIO_DEVICE_ID], volume))
        self.volume = volume

    def process(self):
        if self.stopping:
            self.stop_sound_fondu()

    def update(self, msg):
        #TODO improve this part
        if msg and KEY in msg and msg[KEY] in self.sequences_key:
            logging.debug("number of thread : {}".format(threading.active_count()))
            audio_param = self.sequences_key[msg[KEY]]
            if audio_param:
                if audio_param and NAME in audio_param and audio_param[NAME] == STOP:
                    self.stop_sound()
                    logging.info("stop sound")
                    return
                if audio_param == self.current_audio_name and self.current_audio and self.current_audio.is_playing():
                    logging.debug("already playing {}".format(self.current_audio_name))
                    return
                else:
                    path = self.config[AUDIOS_DIRECTORY] + audio_param[NAME]
                    if not Misc.is_audio(path):
                        logging.error("{} is not audio file".format(path))
                        return
                    self.current_audio_name = audio_param[NAME]
                    self.play_sound(audio_param[NAME])

                    if EXPRESSION in audio_param:
                        face = audio_param[EXPRESSION]
                        duration = self.current_audio.duration * 1000
                        msg[DURATION] = duration
                        # La propagation expression->visage passait par GlobalReceiver (legacy) ;
                        # non câblée en mode ROS, il faudra un publisher face dans audio_node.
                        logging.warning("expression '{}' non propagée vers le visage (non câblé)".format(face))

        if msg and AUDIO in msg:
            if msg[AUDIO] == STOP:
                self.stop_sound_fondu()
                return
            if self.play_sound(msg[AUDIO]):
                self.current_audio_name = msg[AUDIO]
                if FACE in msg:
                    duration = self.current_audio.duration * 1000
                    msg[DURATION] = duration

        return msg

