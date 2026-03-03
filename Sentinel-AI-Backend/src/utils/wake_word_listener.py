# src/utils/wake_word_listener.py

import pvporcupine
import pyaudio
import struct
import threading
from src.utils.log_config import get_logger

logger = get_logger("wakeword")


class WakeWordListener:
    def __init__(self, keyword_paths, access_key, sensitivities=None):
        # Normalize keyword_paths to a list
        if isinstance(keyword_paths, str):
            keyword_paths = [keyword_paths]

        # Normalize sensitivities: default to 0.7 for each path, repeat float for all paths
        if sensitivities is None:
            sensitivities = [0.7] * len(keyword_paths)
        elif isinstance(sensitivities, (int, float)):
            sensitivities = [float(sensitivities)] * len(keyword_paths)

        self.porcupine = pvporcupine.create(
            access_key=access_key, keyword_paths=keyword_paths, sensitivities=sensitivities
        )
        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(
            rate=self.porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self.porcupine.frame_length,
        )
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._listen)

    def start(self):
        self._wake_event.clear()
        self._stop_event.clear()
        self._thread.start()

    def _listen(self):
        while not self._stop_event.is_set():
            pcm = self.stream.read(self.porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
            result = self.porcupine.process(pcm)
            if result >= 0:
                logger.info("Wake word detected!")
                self._wake_event.set()

    def wait_for_wake_word(self, timeout=None):
        """Block until wake word detected. Returns True if detected, False on timeout."""
        detected = self._wake_event.wait(timeout=timeout)
        if detected:
            self._wake_event.clear()
        return detected

    def stop(self):
        self._stop_event.set()
        self._thread.join()
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()
        self.porcupine.delete()
