import time
import simpleaudio
from pydub import generators, AudioSegment
from pydub.playback import _play_with_simpleaudio

# 5 seconds of A 440
#sound = generators.Sine(440).to_audio_segment(duration=5000)

##### using pydub's helper function:
audio_segement = AudioSegment.from_wav("/home/dadou/tmp/deploy/audios/gig.wav")
playback = _play_with_simpleaudio(audio_segement)

# end playback after 3 seconds
time.sleep(10)
playback.stop()

##### using simpleaudio directly:
data = audio_segement.raw_data[5000:]
playback = simpleaudio.play_buffer(
    data,
    num_channels=audio_segement.channels,
    bytes_per_sample=audio_segement.sample_width,
    sample_rate=audio_segement.frame_rate
)

# end playback after 3 seconds
time.sleep(3)
playback.stop()