"""Streaming, interruptible text-to-speech.

Primary: ElevenLabs streamed as raw PCM and played chunk-by-chunk through
PyAudio, so cancellation (barge-in) takes effect within one chunk (~50ms).
Fallback: offline pyttsx3 (coarse cancellation).
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading

import httpx

from ..config import get_secret

logger = logging.getLogger(__name__)

ELEVEN_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")  # Sarah
ELEVEN_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5")
PCM_RATE = 22050

# Persistent client: connection reuse trims a TLS handshake off every sentence.
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30)
    return _client


class Speaker:
    """One PyAudio output stream reused across sentences; cancel() stops mid-chunk."""

    def __init__(self):
        self._cancel = asyncio.Event()
        self._pa = None
        self._stream = None
        self._pyttsx_engine = None
        self._lock = threading.Lock()

    def _output_stream(self):
        import pyaudio

        if self._pa is None:
            self._pa = pyaudio.PyAudio()
        if self._stream is None:
            self._stream = self._pa.open(
                format=pyaudio.paInt16, channels=1, rate=PCM_RATE, output=True
            )
        return self._stream

    def cancel(self) -> None:
        self._cancel.set()
        engine = self._pyttsx_engine
        if engine is not None:
            try:
                engine.stop()
            except Exception:  # noqa: BLE001
                pass

    def reset(self) -> None:
        self._cancel.clear()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    async def chime(self) -> None:
        """Short two-tone 'I'm listening' cue played through the PCM stream."""
        import numpy as np

        try:
            stream = self._output_stream()
            tone = np.concatenate(
                [
                    np.sin(2 * np.pi * freq * np.arange(int(PCM_RATE * 0.09)) / PCM_RATE)
                    for freq in (880, 1320)
                ]
            )
            fade = np.minimum(1, np.linspace(0, 8, tone.size))  # soften attack
            pcm = (tone * fade * fade[::-1] * 12000).astype("int16").tobytes()
            await asyncio.to_thread(stream.write, pcm)
        except Exception:  # noqa: BLE001 — a failed chime must never break the loop
            logger.debug("chime failed", exc_info=True)

    async def speak(self, text: str) -> bool:
        """Speak one chunk of text. Returns False if cancelled or failed."""
        text = text.strip()
        if not text or self._cancel.is_set():
            return False
        api_key = get_secret("ELEVENLABS_API_KEY")
        if api_key:
            try:
                return await self._speak_elevenlabs(text, api_key)
            except Exception:
                logger.exception("ElevenLabs TTS failed; falling back to pyttsx3")
        return await asyncio.to_thread(self._speak_pyttsx3, text)

    async def _speak_elevenlabs(self, text: str, api_key: str) -> bool:
        url = (
            f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE}/stream"
            f"?output_format=pcm_{PCM_RATE}"
        )
        stream = self._output_stream()
        async with _get_client().stream(
            "POST",
            url,
            headers={"xi-api-key": api_key},
            json={"text": text, "model_id": ELEVEN_MODEL},
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(chunk_size=2048):
                if self._cancel.is_set():
                    return False
                # PyAudio write blocks briefly; run off-loop to keep events flowing.
                await asyncio.to_thread(stream.write, chunk)
        return not self._cancel.is_set()

    def _speak_pyttsx3(self, text: str) -> bool:
        with self._lock:
            try:
                import pyttsx3

                engine = pyttsx3.init()
                engine.setProperty("rate", int(os.environ.get("TTS_FALLBACK_RATE", "180")))
                self._pyttsx_engine = engine
                engine.say(text)
                engine.runAndWait()
                return not self._cancel.is_set()
            except Exception:
                logger.exception("pyttsx3 fallback failed")
                return False
            finally:
                self._pyttsx_engine = None

    def close(self) -> None:
        self.cancel()
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
            if self._pa is not None:
                self._pa.terminate()
        except Exception:  # noqa: BLE001
            pass
        self._stream = None
        self._pa = None
