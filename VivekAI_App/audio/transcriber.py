"""
VivekAI_App - Whisper Transcriber
High-accuracy speech-to-text using OpenAI Whisper
"""

import whisper
import numpy as np
import noisereduce as nr
import threading
import config

class Transcriber:
    def __init__(self):
        self.model = None
        self.model_lock = threading.Lock()
        self.loaded = False

    def load_model(self, progress_callback=None):
        """Load Whisper model (call in background thread)"""
        if progress_callback:
            progress_callback("Loading Whisper model... please wait")
        with self.model_lock:
            self.model = whisper.load_model(config.WHISPER_MODEL)
            self.loaded = True
        if progress_callback:
            progress_callback("Whisper model loaded!")

    def transcribe(self, audio_chunk, sample_rate):
        """
        Transcribe audio with maximum accuracy settings
        Returns: cleaned transcript string
        """
        if not self.loaded or self.model is None:
            return ""

        try:
            # Step 1: Noise reduction
            cleaned_audio = self._reduce_noise(audio_chunk, sample_rate)

            # Step 2: Normalize audio
            normalized = self._normalize_audio(cleaned_audio)

            # Step 3: Ensure correct sample rate
            if sample_rate != 16000:
                normalized = self._resample(normalized, sample_rate, 16000)

            # Step 4: Transcribe with high accuracy settings
            with self.model_lock:
                result = self.model.transcribe(
                    normalized,
                    language=config.WHISPER_LANGUAGE,
                    task="transcribe",
                    beam_size=config.WHISPER_BEAM_SIZE,
                    best_of=config.WHISPER_BEST_OF,
                    temperature=config.WHISPER_TEMPERATURE,
                    word_timestamps=config.WHISPER_WORD_TIMESTAMPS,
                    condition_on_previous_text=True,
                    no_speech_threshold=0.6,
                    compression_ratio_threshold=2.4,
                    fp16=False
                )

            text = result.get("text", "").strip()

            # Step 5: Filter out noise/gibberish
            if self._is_valid_transcript(text):
                return text
            return ""

        except Exception as e:
            print(f"Transcription error: {e}")
            return ""

    def _reduce_noise(self, audio, sr):
        """Apply noise reduction"""
        try:
            reduced = nr.reduce_noise(
                y=audio,
                sr=sr,
                stationary=False,
                prop_decrease=0.75
            )
            return reduced
        except:
            return audio

    def _normalize_audio(self, audio):
        """Normalize audio to [-1, 1] range"""
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            return audio / max_val
        return audio

    def _resample(self, audio, orig_sr, target_sr):
        """Resample audio to target sample rate"""
        try:
            import librosa
            return librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr)
        except:
            return audio

    def _is_valid_transcript(self, text):
        """Filter out empty or meaningless transcripts"""
        if not text or len(text.strip()) < 3:
            return False
        # Filter common Whisper hallucinations
        hallucinations = [
            "thank you", "thanks for watching", "subscribe",
            "www.", ".com", "[music]", "[applause]"
        ]
        text_lower = text.lower().strip()
        for h in hallucinations:
            if text_lower == h:
                return False
        return True
