"""VoicePipeline — the async loop replacing the legacy synchronous orchestrator.

wake word → capture → Groq Whisper → agent graph (streaming) → sentence-chunked
TTS that starts speaking before the full response exists, with barge-in: saying
the wake word while Sentinel is speaking cancels playback and listens again.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re

from ..events import Event, EventType
from ..service import ChatService, Emit
from ..store import Store
from .stt import capture_utterance, transcribe
from .tts import Speaker
from .wake import WakeWordListener

logger = logging.getLogger(__name__)

SENTENCE_END = re.compile(r"(?<=[.!?;])\s+")
MIN_CHUNK = 25  # don't send tiny fragments to TTS


def _split_ready(buffer: str) -> tuple[list[str], str]:
    """Split off complete sentences, keeping the trailing partial in the buffer."""
    parts = SENTENCE_END.split(buffer)
    if len(parts) <= 1:
        return [], buffer
    ready, remainder = parts[:-1], parts[-1]
    merged: list[str] = []
    acc = ""
    for part in ready:
        acc = f"{acc} {part}".strip()
        if len(acc) >= MIN_CHUNK:
            merged.append(acc)
            acc = ""
    if acc:
        remainder = f"{acc} {remainder}".strip()
    return merged, remainder


class VoicePipeline:
    def __init__(self, chat: ChatService, store: Store, broadcast: Emit):
        self.chat = chat
        self.store = store
        self.broadcast = broadcast
        self.state = "idle"
        self._task: asyncio.Task | None = None
        self._wake: WakeWordListener | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.running:
            return
        # Construct the wake listener eagerly so bad keys/devices fail the
        # /voice/start request instead of killing the background task silently.
        self._wake = await asyncio.to_thread(WakeWordListener)
        self._task = asyncio.create_task(self._run(), name="voice-pipeline")
        self._task.add_done_callback(self._log_crash)

    @staticmethod
    def _log_crash(task: asyncio.Task) -> None:
        if not task.cancelled() and task.exception() is not None:
            logger.error("Voice pipeline task died", exc_info=task.exception())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.state = "idle"

    async def _emit(self, type_: EventType, session_id: str, **data) -> None:
        await self.broadcast(Event(type=type_, session_id=session_id, data=data))

    async def _run(self) -> None:
        assert self._wake is not None
        wake = self._wake
        speaker = Speaker()
        session_id = self.store.start_session()
        # Opt-in: when off, every command requires the wake word again. When on,
        # ambient speech during the follow-up window gets treated as commands —
        # do not enable in noisy rooms until we have speaker filtering.
        continuous = os.environ.get("CONTINUOUS_LISTENING", "false").lower() in ("true", "1", "yes")
        logger.info("Voice pipeline started (session %s)", session_id[:8])
        try:
            while True:
                self.state = "listening_wake"
                await self._emit(EventType.LISTENING_FOR_WAKE_WORD, session_id)
                while not await asyncio.to_thread(wake.wait, 0.5):
                    pass
                await self._emit(EventType.WAKE_WORD_DETECTED, session_id)

                conversing = True
                first_capture = True
                while conversing:
                    self.state = "listening"
                    # Fire-and-forget: the chime plays while the mic is already
                    # opening, instead of delaying capture by its duration.
                    asyncio.create_task(speaker.chime())
                    await self._emit(EventType.LISTENING, session_id)
                    wav = await capture_utterance(timeout=6.0 if first_capture else 4.0)
                    first_capture = False
                    if wav is None:
                        break  # silence — back to wake word
                    self.state = "thinking"
                    text = await transcribe(wav)
                    await self._emit(EventType.TRANSCRIBED, session_id, text=text)
                    if not text:
                        break
                    await self._turn(session_id, text, wake, speaker)
                    conversing = continuous
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Voice pipeline crashed")
            await self._emit(EventType.ERROR, session_id, message="voice pipeline crashed")
        finally:
            self.state = "idle"
            await asyncio.to_thread(wake.close)
            speaker.close()
            self.store.end_session(session_id)
            logger.info("Voice pipeline stopped")

    async def _turn(
        self, session_id: str, text: str, wake: WakeWordListener, speaker: Speaker
    ) -> None:
        tts_enabled = os.environ.get("TTS_ENABLED", "true").lower() in ("true", "1", "yes")
        speaker.reset()
        wake.clear()
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        buffer = ""
        queued_any = False

        async def emit_and_chunk(event: Event) -> None:
            nonlocal buffer, queued_any
            await self.broadcast(event)
            if not tts_enabled:
                return
            if event.type == EventType.TOKEN:
                buffer += event.data.get("text", "")
                ready, buffer = _split_ready(buffer)  # noqa: F823 — nonlocal rebind
                for sentence in ready:
                    queue.put_nowait(sentence)
                    queued_any = True
            elif event.type in (EventType.RESPONSE, EventType.ERROR):
                if buffer.strip():
                    queue.put_nowait(buffer.strip())
                    buffer = ""
                    queued_any = True
                elif not queued_any and event.type == EventType.RESPONSE:
                    # Supervisor fast path: no tokens streamed — speak the full reply.
                    text = event.data.get("text", "")
                    if text:
                        queue.put_nowait(text)
                        queued_any = True

        async def speak_loop() -> None:
            spoke = False
            while True:
                sentence = await queue.get()
                if sentence is None:
                    break
                if speaker.cancelled:
                    continue  # drain silently after barge-in
                if not spoke:
                    self.state = "speaking"
                    await self._emit(EventType.SPEAKING, session_id)
                    spoke = True
                await speaker.speak(sentence)
            if spoke:
                await self._emit(
                    EventType.SPEECH_FINISHED, session_id, interrupted=speaker.cancelled
                )

        async def barge_watch() -> None:
            while await asyncio.to_thread(wake.wait, 0.3) is False:
                pass
            logger.info("Barge-in: cancelling speech")
            speaker.cancel()

        speak_task = asyncio.create_task(speak_loop())
        barge_task = asyncio.create_task(barge_watch())
        try:
            await self.chat.run_turn(session_id, text, emit_and_chunk)
        finally:
            queue.put_nowait(None)
            await speak_task
            barge_task.cancel()
