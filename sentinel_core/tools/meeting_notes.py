"""Meeting notes: record system audio (WASAPI loopback — what the user hears,
no microphone) and transcribe it to a saved text file via the existing STT.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import io
import logging
import re
import threading
import time
import wave

from langchain_core.tools import tool

from ..config import data_dir
from ..voice.stt import transcribe

logger = logging.getLogger(__name__)

CHUNK_FRAMES = 1024
MAX_MINUTES = 90
TARGET_RATE = 16000
SEGMENT_SECONDS = 8 * 60
TRANSCRIPT_PREVIEW_CHARS = 6000

_lock = threading.Lock()
_recorder: dict | None = None  # thread, stop, chunks, rate, channels, start, title, device


def _open_loopback():
    """Return (PyAudio, loopback device info) for the default output device."""
    import pyaudiowpatch as pyaudio

    pa = pyaudio.PyAudio()
    try:
        wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_out = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
        loopback = next(
            (
                lb
                for lb in pa.get_loopback_device_info_generator()
                if default_out["name"] in lb["name"]
            ),
            None,
        )
        if loopback is None:
            pa.terminate()
            raise RuntimeError(f"No loopback device found for output '{default_out['name']}'.")
        return pa, loopback
    except Exception:
        pa.terminate()
        raise


def _record_loop(rec: dict) -> None:
    """Daemon thread: read loopback audio chunks into memory until stopped."""
    import pyaudiowpatch as pyaudio

    pa, stream = rec["pa"], None
    try:
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=rec["channels"],
            rate=rec["rate"],
            frames_per_buffer=CHUNK_FRAMES,
            input=True,
            input_device_index=rec["device_index"],
        )
        deadline = time.monotonic() + MAX_MINUTES * 60
        while not rec["stop"].is_set() and time.monotonic() < deadline:
            rec["chunks"].append(stream.read(CHUNK_FRAMES, exception_on_overflow=False))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Meeting recording thread failed")
        rec["error"] = str(exc)
    finally:
        if stream is not None:
            stream.stop_stream()
            stream.close()
        pa.terminate()


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:40] or "meeting"


def _to_16k_mono(chunks: list[bytes], rate: int, channels: int):
    """Convert raw int16 PCM to 16 kHz mono int16 (crude decimation, fine for speech)."""
    import numpy as np

    audio = np.frombuffer(b"".join(chunks), dtype=np.int16)
    if channels > 1:
        audio = audio[: len(audio) - len(audio) % channels]
        audio = audio.reshape(-1, channels).mean(axis=1)
    step = max(1, int(rate / TARGET_RATE))
    return audio[::step].astype(np.int16)


def _wav_bytes(samples) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(TARGET_RATE)
        wav.writeframes(samples.tobytes())
    return buffer.getvalue()


@tool
def start_meeting_recording(title: str = "Meeting") -> str:
    """Start recording the system audio (whatever is playing through the
    speakers — a meeting, call, or video). No microphone is used. Stop later
    with stop_meeting_recording to get a transcript.

    Args:
        title: a name for the meeting, used in the transcript filename.
    """
    global _recorder
    with _lock:
        if _recorder is not None:
            return (
                f"Already recording '{_recorder['title']}' — stop it first "
                "with stop_meeting_recording."
            )
        try:
            pa, loopback = _open_loopback()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Could not open WASAPI loopback")
            return f"Cannot record system audio: {exc}"
        rec = {
            "pa": pa,
            "device_index": loopback["index"],
            "device": loopback["name"],
            "rate": int(loopback["defaultSampleRate"]),
            "channels": int(loopback["maxInputChannels"]) or 2,
            "chunks": [],
            "stop": threading.Event(),
            "start": time.monotonic(),
            "title": title.strip() or "Meeting",
            "error": None,
        }
        rec["thread"] = threading.Thread(target=_record_loop, args=(rec,), daemon=True)
        rec["thread"].start()
        _recorder = rec
        return (
            f"Recording '{rec['title']}' from system audio device "
            f"'{rec['device']}' ({rec['rate']} Hz). Auto-stops after {MAX_MINUTES} minutes."
        )


@tool
def meeting_recording_status() -> str:
    """Check whether a meeting recording is in progress, and for how long."""
    with _lock:
        if _recorder is None:
            return "Not recording."
        elapsed = (time.monotonic() - _recorder["start"]) / 60
        size_mb = sum(len(c) for c in _recorder["chunks"]) / (1024 * 1024)
        return (
            f"Recording '{_recorder['title']}': {elapsed:.1f} minutes elapsed, "
            f"about {size_mb:.1f} MB of audio captured."
        )


@tool
async def stop_meeting_recording() -> str:
    """Stop the meeting recording, transcribe the captured audio, and save
    the full transcript to a text file. Returns the transcript (or a preview
    if very long) and the file path.
    """
    global _recorder
    with _lock:
        rec = _recorder
        _recorder = None
    if rec is None:
        return "Not recording — start one first with start_meeting_recording."
    rec["stop"].set()
    await asyncio.to_thread(rec["thread"].join, 10)
    if rec["error"] and not rec["chunks"]:
        return f"Recording failed: {rec['error']}"
    if not rec["chunks"]:
        return "Recording stopped, but no audio was captured."

    frames = sum(len(c) for c in rec["chunks"]) // (2 * rec["channels"])
    minutes = frames / rec["rate"] / 60
    samples = await asyncio.to_thread(_to_16k_mono, rec["chunks"], rec["rate"], rec["channels"])

    parts = []
    segment = SEGMENT_SECONDS * TARGET_RATE
    for start in range(0, len(samples), segment):
        wav = _wav_bytes(samples[start : start + segment])
        text = await transcribe(wav)
        if text:
            parts.append(text)
    transcript = "\n".join(parts).strip()

    folder = data_dir() / "meetings"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    path = folder / f"{stamp}-{_slugify(rec['title'])}.txt"
    path.write_text(transcript, encoding="utf-8")

    if not transcript:
        return (
            f"Recording stopped ({minutes:.1f} minutes) but the audio contained no "
            f"recognizable speech. Empty transcript saved to {path}."
        )
    words = len(transcript.split())
    preview = transcript
    if len(preview) > TRANSCRIPT_PREVIEW_CHARS:
        preview = preview[:TRANSCRIPT_PREVIEW_CHARS] + "...[truncated, full text in file]"
    return f"Transcript saved to {path} ({minutes:.1f} minutes, {words} words):\n{preview}"


TOOLS = [start_meeting_recording, meeting_recording_status, stop_meeting_recording]
