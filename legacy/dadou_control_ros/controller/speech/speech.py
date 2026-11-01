import speech_recognition as sr
from gtts import gTTS
from playsound import playsound

mic_name = "Logitech USB Headset: Audio (hw:2,0)"
sample_rate = 48000
chunk_size = 2048
r = sr.Recognizer()

mic_list = sr.Microphone.list_microphone_names()
device_id = None

for i, microphone_name in enumerate(mic_list):
    print(microphone_name+" id : "+str(i))
    if microphone_name == mic_name:
        print("found mic")
        device_id = i

with sr.Microphone(device_index=6, sample_rate=sample_rate,
                   chunk_size=chunk_size) as source:
    r.adjust_for_ambient_noise(source)
    print("Say Something")

    audio = r.listen(source)

    try:
        text = r.recognize_google(audio)
        print("you said: " + text)
        language = 'en'
        tld = 'co.in'

        # Passing the text and language to the engine,
        # here we have marked slow=False. Which tells
        # the module that the converted audio should
        # have a high speed
        myobj = gTTS(text=text, lang=language, slow=False, tld=tld)

        # Saving the converted audio in a mp3 file named
        # welcome
        myobj.save("input_speech.mp3")

        # Playing the converted file
        # os.system("mpg321 welcome.mp3")
        playsound("input_speech.mp3")

    except sr.UnknownValueError:
        print("Google Speech Recognition could not understand audio")

    except sr.RequestError as e:
        print("Could not request results from Google Speech Recognition service; {0}".format(e))