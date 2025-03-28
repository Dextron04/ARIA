import whisper
import tempfile
import wave
import numpy as np

def save_audio_to_wav(audio_data, filename, samplerate=16000, channels=1):
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit audio
        wf.setframerate(samplerate)
        wf.writeframes((audio_data * 32767).astype(np.int16).tobytes())

def transcribe_stream(audio_stream):
    model = whisper.load_model("base")
    samplerate = 16000
    channels = 1
    while True:
        audio_data = audio_stream.read_chunk()
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmpfile:
            save_audio_to_wav(audio_data, tmpfile.name, samplerate, channels)
            result = model.transcribe(tmpfile.name)
            print("Transcription:", result['text'])
