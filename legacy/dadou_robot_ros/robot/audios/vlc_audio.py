# Imports matériels différés (pattern wheels.py) : le module doit s'importer sans les libs Pi.
# pip3 install sound-player
# https://github.com/Krozark/sound-player/blob/master/example.py
import logging


#from sound_player import Sound, Playlist, SoundPlayer


class VlCAudio:

    silence = "audios/silence.wav"

    def __init__(self):
        # vlc (python-vlc) et le lecteur ne sont pas installés hors machine son :
        # import et construction du MediaPlayer différés à l'instanciation.
        # L'ancien attribut de classe `player = vlc.MediaPlayer(silence)` était
        # évalué À L'IMPORT du module -> le module devenait inimportable sans vlc.
        import vlc
        self.vlc = vlc
        self.player = vlc.MediaPlayer(self.silence)

    def play_sounds(self, audios):
        self.player.stop()
        for audio in audios:
            logging.info("enqueue: " + audio.get_path())
            self.player = self.vlc.MediaPlayer(audio.get_path())
            #for s in range(int(audio.get_time())):
            #    self.player.enqueue(Sound(self.silence), 1)
        self.player.play()

    def stop_sound(self):
        self.player.stop()

    def process(self, key):
        if key:
            logging.info("process: ")
            #audio_sequence = self.json_manager.get_audio_seq(key)
            #if audio_sequence:
            #    logging.info("play new audio")
            #    audios = []
            #    for audio_seq in audio_sequence[SEQUENCE]:
            #        audio_path = self.json_manager.get_audio_path_by_name(audio_seq[NAME])
            #        logging.debug("audios name : " + audio_seq[NAME] + " path : " + audio_path)
            #        audios.append(PathTime(audio_path, audio_seq[DELAY]))
            #
            #    self.play_sounds(audios)

