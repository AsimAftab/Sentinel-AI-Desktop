"""openWakeWord wake-word listener (no API key, Apache-2.0, ONNX on CPU).

Replaces Porcupine, whose free tier was discontinued 2026-06-30. Default
wake phrase is the pretrained "Hey Jarvis" model; set WAKEWORD_MODEL to a
custom-trained .onnx (e.g. "sentinel") to change it.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

import numpy as np

from ..config import data_dir

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_LENGTH = 1280  # 80ms — openWakeWord's expected chunk
REFRACTORY_S = 2.0  # ignore re-triggers right after a detection
DEFAULT_MODEL = "hey_jarvis_v0.1"


def _models_dir() -> Path:
    path = data_dir() / "wakeword-models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_model() -> str:
    """Custom model beats default: WAKEWORD_MODEL env, else any user-dropped
    .onnx in data_dir/wakeword-models (e.g. a Colab-trained sentinel.onnx),
    else the downloaded pretrained "Hey Jarvis"."""
    override = os.environ.get("WAKEWORD_MODEL")
    if override:
        if not Path(override).exists():
            raise FileNotFoundError(f"WAKEWORD_MODEL not found: {override}")
        return override

    # openWakeWord's feature-extraction models share this folder — not wake words.
    infrastructure = {DEFAULT_MODEL, "embedding_model", "melspectrogram", "silero_vad"}
    custom = sorted(f for f in _models_dir().glob("*.onnx") if f.stem not in infrastructure)
    if custom:
        logger.info("Using custom wake-word model: %s", custom[0].name)
        return str(custom[0])

    import openwakeword.utils

    target = _models_dir()
    model_file = target / f"{DEFAULT_MODEL}.onnx"
    if not model_file.exists():
        logger.info("Downloading openWakeWord models to %s", target)
        openwakeword.utils.download_models(
            model_names=[DEFAULT_MODEL], target_directory=str(target)
        )
    return str(model_file)


class WakeWordListener:
    """Continuously listens on its own thread; ``wait(timeout)`` consumes detections."""

    def __init__(self, threshold: float | None = None):
        import pyaudio
        from openwakeword.model import Model

        if threshold is None:
            threshold = float(os.environ.get("WAKE_WORD_SENSITIVITY", "0.5"))
        self._threshold = threshold
        model_path = _resolve_model()
        # Feature-extraction models (melspectrogram/embedding) ship with the
        # package; download once if missing.
        try:
            self._model = Model(wakeword_models=[model_path], inference_framework="onnx")
        except Exception:
            import openwakeword.utils

            openwakeword.utils.download_models(model_names=[DEFAULT_MODEL])
            self._model = Model(wakeword_models=[model_path], inference_framework="onnx")
        self._model_name = next(iter(self._model.models))
        logger.info("Wake model %r ready (threshold %.2f)", self._model_name, threshold)

        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=FRAME_LENGTH,
        )
        self._detected = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._listen, daemon=True, name="wakeword")
        self._thread.start()

    def _listen(self) -> None:
        last_hit = 0.0
        while not self._stop.is_set():
            try:
                pcm = self._stream.read(FRAME_LENGTH, exception_on_overflow=False)
                frame = np.frombuffer(pcm, dtype=np.int16)
                score = self._model.predict(frame)[self._model_name]
                if score >= self._threshold and (time.monotonic() - last_hit) > REFRACTORY_S:
                    last_hit = time.monotonic()
                    logger.info("Wake word detected (score %.2f)", score)
                    self._detected.set()
            except Exception:
                if not self._stop.is_set():
                    logger.exception("Wake listener read failed")
                return

    def wait(self, timeout: float | None = None) -> bool:
        """Block up to ``timeout`` for a detection; consumes it when seen."""
        if self._detected.wait(timeout=timeout):
            self._detected.clear()
            return True
        return False

    def clear(self) -> None:
        self._detected.clear()

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
        try:
            self._stream.stop_stream()
            self._stream.close()
        finally:
            self._pa.terminate()
