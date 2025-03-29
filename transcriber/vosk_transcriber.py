import sounddevice as sd
import queue
import vosk
import json

# Load Vosk model (ensure it's downloaded)
MODEL_PATH = "models/vosk-model-en-us-0.42-gigaspeech"
model = vosk.Model(MODEL_PATH)
rec = vosk.KaldiRecognizer(model, 16000)

# Queue to handle real-time audio streaming
q = queue.Queue()

def audio_callback(indata, frames, time, status):
    """Puts live audio input into a queue for processing."""
    if status:
        print(status, flush=True)
    q.put(bytes(indata))

def start_transcription():
    """Handles real-time speech-to-text processing."""
    with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                           channels=1, callback=audio_callback):
        print("Listening...")
        while True:
            data = q.get()
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                print("Live transcription:", result["text"])
