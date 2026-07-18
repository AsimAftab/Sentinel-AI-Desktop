"""Speech capture + Groq Whisper transcription.

Capture: silero-VAD endpointing (32ms frames, 0.35s silence tail, 0.3s
pre-roll) — no ambient calibration, tighter than the legacy energy heuristic.
Falls back to speech_recognition's energy endpointing if VAD init fails.
Transcription: Groq whisper-large-v3-turbo over a persistent HTTP/2 client
(connection reuse saves a TLS handshake per turn).
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import time
import wave

import httpx

from ..config import get_secret

logger = logging.getLogger(__name__)

GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
STT_MODEL = os.environ.get("STT_MODEL", "whisper-large-v3-turbo")

SAMPLE_RATE = 16000
FRAME_SAMPLES = 512  # 32ms
PRE_ROLL_S = 0.3
START_PROB = 0.5
END_PROB = 0.35
TAIL_SILENCE_S = float(os.environ.get("STT_TAIL_SILENCE", "0.35"))

_vad = None
_vad_failed = False
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30, http2=False)
    return _client


def _pcm_to_wav(frames: list[bytes]) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"".join(frames))
    return buffer.getvalue()


def _capture_vad(timeout: float, phrase_limit: float) -> bytes | None:
    import numpy as np
    import pyaudio

    from .vad import SileroVAD

    global _vad
    if _vad is None:
        _vad = SileroVAD()
    _vad.reset()

    pa = pyaudio.PyAudio()
    stream = pa.open(
        rate=SAMPLE_RATE,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=FRAME_SAMPLES,
    )
    frame_s = FRAME_SAMPLES / SAMPLE_RATE
    pre_roll_frames = int(PRE_ROLL_S / frame_s)
    tail_frames = int(TAIL_SILENCE_S / frame_s)

    pre_roll: list[bytes] = []
    speech: list[bytes] = []
    silent_run = 0
    started = False
    deadline = time.monotonic() + timeout
    try:
        while True:
            pcm = stream.read(FRAME_SAMPLES, exception_on_overflow=False)
            prob = _vad.prob(np.frombuffer(pcm, dtype=np.int16))
            if not started:
                pre_roll.append(pcm)
                if len(pre_roll) > pre_roll_frames:
                    pre_roll.pop(0)
                if prob >= START_PROB:
                    started = True
                    speech = [*pre_roll]
                    speech_deadline = time.monotonic() + phrase_limit
                elif time.monotonic() > deadline:
                    return None
            else:
                speech.append(pcm)
                silent_run = silent_run + 1 if prob < END_PROB else 0
                if silent_run >= tail_frames or time.monotonic() > speech_deadline:
                    return _pcm_to_wav(speech)
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


def _capture_legacy(timeout: float, phrase_limit: float) -> bytes | None:
    """Energy-endpointed fallback via speech_recognition."""
    import speech_recognition as sr

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = int(os.environ.get("STT_ENERGY_THRESHOLD", "300"))
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = float(os.environ.get("STT_PAUSE_THRESHOLD", "0.5"))
    try:
        with sr.Microphone() as source:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        return audio.get_wav_data()
    except sr.WaitTimeoutError:
        return None
    except Exception:
        logger.exception("Legacy capture failed")
        return None


def _capture_blocking(timeout: float, phrase_limit: float) -> bytes | None:
    global _vad_failed
    if not _vad_failed:
        try:
            return _capture_vad(timeout, phrase_limit)
        except Exception:
            logger.exception("VAD capture failed; falling back to energy endpointing")
            _vad_failed = True
    return _capture_legacy(timeout, phrase_limit)


async def capture_utterance(timeout: float = 6.0, phrase_limit: float = 15.0) -> bytes | None:
    """Record one utterance from the default mic; None on silence/timeout."""
    return await asyncio.to_thread(_capture_blocking, timeout, phrase_limit)


async def transcribe(wav_bytes: bytes) -> str:
    """Transcribe WAV audio via Groq Whisper. Returns '' on failure."""
    api_key = get_secret("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY missing; cannot transcribe")
        return ""
    language = os.environ.get("STT_LANGUAGE", "en")
    start = time.perf_counter()
    try:
        response = await _get_client().post(
            GROQ_STT_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": ("audio.wav", wav_bytes, "audio/wav")},
            data={"model": STT_MODEL, "language": language, "temperature": "0"},
        )
        response.raise_for_status()
        text = response.json().get("text", "").strip()
        logger.info(
            "Transcribed in %.0fms: %r", (time.perf_counter() - start) * 1000, text[:120]
        )
        return text
    except Exception:
        logger.exception("Groq transcription failed")
        return ""
