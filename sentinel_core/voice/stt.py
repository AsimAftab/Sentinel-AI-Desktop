"""Speech capture + Groq Whisper transcription.

Capture uses speech_recognition's energy-based endpointing (proven in the
legacy app); transcription goes to Groq ``whisper-large-v3-turbo`` (~216x
real-time) instead of the legacy blocking Google STT.
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

from ..config import get_secret

logger = logging.getLogger(__name__)

GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
STT_MODEL = os.environ.get("STT_MODEL", "whisper-large-v3-turbo")


_recognizer = None


def _get_recognizer():
    """One shared Recognizer: ambient calibration runs once, not per capture."""
    global _recognizer
    import speech_recognition as sr

    if _recognizer is None:
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = int(os.environ.get("STT_ENERGY_THRESHOLD", "300"))
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = float(os.environ.get("STT_PAUSE_THRESHOLD", "0.5"))
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.4)
        _recognizer = recognizer
    return _recognizer


def _capture_blocking(timeout: float, phrase_limit: float) -> bytes | None:
    import speech_recognition as sr

    try:
        recognizer = _get_recognizer()
        with sr.Microphone() as source:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        return audio.get_wav_data()
    except sr.WaitTimeoutError:
        return None
    except Exception:
        logger.exception("Audio capture failed")
        return None


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
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                GROQ_STT_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                data={"model": STT_MODEL, "language": language, "temperature": "0"},
            )
            response.raise_for_status()
            text = response.json().get("text", "").strip()
            logger.info("Transcribed: %r", text[:120])
            return text
    except Exception:
        logger.exception("Groq transcription failed")
        return ""
