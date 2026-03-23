import speech_recognition as sr  # type: ignore
import numpy as np  # type: ignore
import io
import wave

class Transcriber:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.is_loaded = True
        print('[STT] SpeechRecognition ready (no torch needed)')

    def load_model(self, status_callback=None, model_size='base'):
        """Mark model ready; call optional status_callback with a status string."""
        self.is_loaded = True
        if callable(status_callback):
            status_callback('✅ Speech Recognition ready')
        print('[STT] Ready')

    def transcribe(self, audio_data, sample_rate=16000):
        try:
            # audio_data arrives as float32 from PyAudio; scale to int16 range
            audio_array = (np.array(audio_data, dtype=np.float32) * 32767).astype(np.int16)
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_array.tobytes())
            buf.seek(0)
            with sr.AudioFile(buf) as source:
                audio = self.recognizer.record(source)
            text = self.recognizer.recognize_google(audio)
            return text
        except sr.UnknownValueError:
            return ''
        except Exception as e:
            print(f'[STT] Error: {e}')
            return ''

    def transcribe_file(self, filepath):
        try:
            with sr.AudioFile(filepath) as source:
                audio = self.recognizer.record(source)
            return self.recognizer.recognize_google(audio)
        except Exception as e:
            print(f'[STT] File error: {e}')
            return ''
