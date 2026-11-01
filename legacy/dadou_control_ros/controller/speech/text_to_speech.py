# Import the required module for text
# to speech conversion
from gtts import gTTS
from playsound import playsound
from pydub import AudioSegment

mytext = 'bonjour les petits coquins! On a bien tapé au fond ce week-end ? ah ah ah ah!'
# Language in which you want to convert
language = 'fr'
tld = "ca"

# Passing the text and language to the engine,
# here we have marked slow=False. Which tells
# the module that the converted audio should
# have a high speed
myobj = gTTS(text=mytext, lang=language, tld=tld, slow=True)

# Saving the converted audio in a mp3 file named
# welcome
myobj.save("welcome.mp3")

# Playing the converted file
#os.system("mpg321 welcome.mp3")

# convert wav to mp3
filename = 'welcome.wav'
sound = AudioSegment.from_mp3("welcome.mp3")
sound.export(filename, format="wav")


octaves = 0.4

sound = AudioSegment.from_file(filename, format=filename[-3:])
new_sample_rate = int(sound.frame_rate * (2.0 ** octaves))
hipitch_sound = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
hipitch_sound = hipitch_sound.set_frame_rate(44100)
#export / save pitch changed sound
hipitch_sound.export(f"octave_{octaves}.wav", format="wav")

playsound(f"octave_{octaves}.wav")

""" convert to wav

    y, sr = librosa.load("placeholder.mp3")
    data = librosa.resample(y, sr, SAMPLE_RATE)
    librosa.output.write_wav('placeholder.wav', data, SAMPLE_RATE)
    d, sr = sf.read('placeholder.wav')
    sf.write('placeholder.wav', d, sr)
"""