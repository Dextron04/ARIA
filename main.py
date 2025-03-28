from audio_input.mic_stream import get_audio_stream
from transcriber.whisper_transcriber import transcribe_stream

if __name__ == "__main__":
    print(">> SUMI-Ears: Using AirPods for input and output")
    
    # Create and start the audio stream.
    # Adjust parameters like duration, samplerate, and channels as needed.
    audio_stream = get_audio_stream(duration=5, samplerate=16000, channels=1)
    
    try:
        # This function will continuously read audio chunks and transcribe them.
        transcribe_stream(audio_stream)
    except KeyboardInterrupt:
        print("\n>> Stopping SUMI-Ears...")
    finally:
        # Stop and close the audio stream to free system resources.
        audio_stream.stop_stream()
        audio_stream.close()
