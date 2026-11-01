import time

from pydub import AudioSegment, playback


sound = AudioSegment.from_wav("/home/dadou/tmp/deploy/audios/gig.wav")

play_obj = playback._play_with_simpleaudio(sound)
# ... do stuff ...
time.sleep(5)
"""play_obj.stop()

## I recommend using simpleaudio directly though:
import simpleaudio
play_obj = simpleaudio.play_buffer(
    sound.raw_data,
    num_channels= sound.channels,
    bytes_per_sample= sound.sample_width,
    sample_rate= sound.frame_rate
)
# ... do stuff ...
play_obj.stop()
# or you could wait for it to finish playback
play_obj.wait_done()"""