# SUMI-Ears: Voice-to-Text Module (Phase 1)

![ChatGPT Image Mar 28, 2025, 01_21_32 AM](https://github.com/user-attachments/assets/b048d12f-506e-416a-bd91-6d7d863997a7)

**SUMI-Ears** is the first building block of the SUMI voice assistant — designed to listen to live audio and transcribe it in real-time.

---

### Features:

- Captures microphone input live
- Uses `whisper` for accurate transcription
- Modular and reusable for future projects (like smart assistants or voice notes)
- Attempted integration with Qwen2-Audio model (requires significant computational resources)

---

### Setup:

```bash
git clone https://github.com/Dextron04/SUMI.git
cd sumi-ears
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Requirements:

- Python 3.8+
- PyTorch
- Transformers
- Whisper
- Librosa
- Other dependencies listed in requirements.txt

### Note on Model Selection:

The project initially attempted to use the Qwen2-Audio-7B-Instruct model, but due to its large size (7B parameters) and high memory requirements, it may not be suitable for all hardware configurations. The project currently uses Whisper as the primary transcription model.

### Development Status:

- [x] Basic project structure
- [x] Whisper integration
- [x] Qwen2 model integration attempt
- [ ] Real-time audio processing
- [ ] Performance optimization
- [ ] User interface development

---

### License:

MIT License
