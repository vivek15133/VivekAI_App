"""
VivekAI_App - Audio Capture
Captures microphone and system audio
"""

import pyaudio
import numpy as np
import threading
import queue
import config

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

    def _get_input_device(self):
        """Get best available input device"""
        device_index = None
        for i in range(self.audio.get_device_count()):
            dev = self.audio.get_device_info_by_index(i)
            # Prefer VB-Audio Virtual Cable for system audio
            if 'CABLE' in dev['name'].upper() or 'VB-AUDIO' in dev['name'].upper():
                device_index = i
                break
        return device_index  # None = default mic

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
        self.stream.start_stream()
        # Start buffer processor
        self.processor_thread = threading.Thread(target=self._process_buffer, daemon=True)
        self.processor_thread.start()

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
                    chunk = np.concatenate(self.buffer[:frames_needed])
                    self.buffer = self.buffer[frames_needed:]
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
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()

    def get_device_list(self):
        """Return list of available input devices"""
        devices = []
        for i in range(self.audio.get_device_count()):
            dev = self.audio.get_device_info_by_index(i)
            if dev['maxInputChannels'] > 0:
                devices.append((i, dev['name']))
        return devices
