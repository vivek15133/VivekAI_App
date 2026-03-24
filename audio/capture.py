"""
VivekAI_App - Audio Capture
Captures microphone and system audio
"""

import pyaudio  # type: ignore
import numpy as np  # type: ignore
import threading
import queue
import config  # type: ignore
from typing import Optional

class AudioCapture:
    def __init__(self, callback):
        self.callback = callback
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.running = False
        self.buffer = []
        self.buffer_lock = threading.Lock()
        self.chunk_size = 1024
        self.sample_rate = config.AUDIO_SAMPLE_RATE
        self.chunk_seconds = config.AUDIO_CHUNK_SECONDS
        self.processor_thread: Optional[threading.Thread] = None

    def _get_input_device(self):
        """Get best available input device - default to system mic for reliability"""
        return None  # Use default system microphone

    def start(self):
        self.running = True
        device_index = self._get_input_device()
        self.stream = self.audio.open(
            format=pyaudio.paFloat32,
            channels=config.AUDIO_CHANNELS,
            rate=self.sample_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=self.chunk_size,
            stream_callback=self._audio_callback
        )
        if self.stream:
            self.stream.start_stream()  # type: ignore
        # Start buffer processor
        self.processor_thread = threading.Thread(target=self._process_buffer, daemon=True)
        self.processor_thread.start()  # type: ignore

    def _audio_callback(self, in_data, frame_count, time_info, status):
        audio_data = np.frombuffer(in_data, dtype=np.float32)
        with self.buffer_lock:
            self.buffer.append(audio_data)
        return (None, pyaudio.paContinue)

    def _process_buffer(self):
        frames_needed = int(self.sample_rate * self.chunk_seconds / self.chunk_size)
        while self.running:
            with self.buffer_lock:
                if len(self.buffer) >= frames_needed:
                    chunk = np.concatenate(self.buffer[:frames_needed])  # type: ignore
                    self.buffer = self.buffer[frames_needed:]  # type: ignore
                    # Check if there's actual sound (VAD)
                    if self._has_voice(chunk):
                        self.callback(chunk, self.sample_rate)
            threading.Event().wait(0.1)

    def _has_voice(self, audio_chunk):
        """Simple energy-based VAD"""
        energy = np.sqrt(np.mean(audio_chunk**2))
        return energy > config.SILENCE_THRESHOLD

    def stop(self):
        self.running = False
        if self.stream:
            self.stream.stop_stream()  # type: ignore
            self.stream.close()  # type: ignore
        self.audio.terminate()  # type: ignore

    def get_device_list(self):
        """Return list of available input devices"""
        devices = []
        for i in range(self.audio.get_device_count()):
            dev = self.audio.get_device_info_by_index(i)
            if dev['maxInputChannels'] > 0:
                devices.append((i, dev['name']))
        return devices
