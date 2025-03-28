import sounddevice as sd
import numpy as np
import queue

class AudioStream:
    def __init__(self, duration=5, samplerate=16000, channels=1):
        self.duration = duration
        self.samplerate = samplerate
        self.channels = channels
        self.audio_queue = queue.Queue()
        self.stream = sd.InputStream(
            channels=self.channels,
            samplerate=self.samplerate,
            callback=self.audio_callback
        )
    
    def audio_callback(self, indata, frames, time_info, status):
        if status:
            print(status)
        self.audio_queue.put(indata.copy())
    
    def start(self):
        self.stream.start()
    
    def stop_stream(self):
        self.stream.stop()
    
    def close(self):
        self.stream.close()
    
    def read_chunk(self):
        frames_needed = int(self.samplerate * self.duration)
        audio_frames = []
        while sum(chunk.shape[0] for chunk in audio_frames) < frames_needed:
            audio_frames.append(self.audio_queue.get())
        audio_data = np.concatenate(audio_frames, axis=0)
        # If we get extra frames, trim the array.
        if audio_data.shape[0] > frames_needed:
            audio_data = audio_data[:frames_needed]
        return audio_data

def get_audio_stream(duration=5, samplerate=16000, channels=1):
    audio_stream = AudioStream(duration=duration, samplerate=samplerate, channels=channels)
    audio_stream.start()
    return audio_stream
