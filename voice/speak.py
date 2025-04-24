import pyttsx3
from TTS.api import TTS
import os

os.environ["NO_MECAB"] = "1"
tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False, gpu=False)


engine = pyttsx3.init()
engine.setProperty('rate', 180)
engine.setProperty('volume', 1)

def speak(text: str):
    print("🎙️ SUMI says:", text)
    tts.tts_to_file(
        text=text,
        file_path="sumi_output.wav"
    )
    os.system("afplay sumi_output.wav")

