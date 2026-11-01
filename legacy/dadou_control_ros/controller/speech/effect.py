import numpy as np
from pydub import AudioSegment
from numpy.random import uniform
filename = 'je-suis-pas-sourd.wav'
sound = AudioSegment.from_file(filename, format=filename[-3:])

octaves = 0.5
for octaves in np.linspace(-1,1,21):
    new_sample_rate = int(sound.frame_rate * (2.0 ** octaves))
    hipitch_sound = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
    hipitch_sound = hipitch_sound.set_frame_rate(44100)
#export / save pitch changed sound
    hipitch_sound.export(f"octave_{octaves}.wav", format="wav")

