"""Silero VAD (ONNX) — precise end-of-speech detection for capture.

Uses the silero_vad.onnx that openWakeWord downloads alongside its models.
Supports both the v4 (h/c state) and v5 (single state tensor) graph layouts.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from ..config import data_dir

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_SAMPLES = 512  # 32ms — silero's expected frame at 16k


def model_path() -> Path:
    return data_dir() / "wakeword-models" / "silero_vad.onnx"


class SileroVAD:
    def __init__(self):
        import onnxruntime as ort

        path = model_path()
        if not path.exists():
            raise FileNotFoundError(f"silero_vad.onnx not found at {path}")
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        self._session = ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])
        input_names = {i.name for i in self._session.get_inputs()}
        self._v5 = "state" in input_names
        self.reset()

    def reset(self) -> None:
        if self._v5:
            self._state = np.zeros((2, 1, 128), dtype=np.float32)
        else:
            self._h = np.zeros((2, 1, 64), dtype=np.float32)
            self._c = np.zeros((2, 1, 64), dtype=np.float32)

    def prob(self, frame_int16: np.ndarray) -> float:
        """Speech probability for one 512-sample int16 frame."""
        audio = (frame_int16.astype(np.float32) / 32768.0).reshape(1, -1)
        sr = np.array(SAMPLE_RATE, dtype=np.int64)
        if self._v5:
            out, self._state = self._session.run(
                None, {"input": audio, "state": self._state, "sr": sr}
            )
        else:
            out, self._h, self._c = self._session.run(
                None, {"input": audio, "h": self._h, "c": self._c, "sr": sr}
            )
        return float(out.reshape(-1)[0])
