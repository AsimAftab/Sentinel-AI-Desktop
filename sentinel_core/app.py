"""FastAPI application: REST for settings/history, WebSocket for the event stream.

WebSocket protocol (JSON):
  client → {"type": "chat", "text": "...", "session_id": "..."?}
  server → Event.to_wire() dicts (see events.py); a "ready" event with the
           session_id is sent on connect.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from . import __version__
from .config import PROVIDER_KEY_ENV, Settings, set_secret
from .events import Event, EventType
from .service import ChatService
from .store import Store

logger = logging.getLogger(__name__)


class Hub:
    """Fan-out of events to every connected WebSocket (voice events, notably)."""

    def __init__(self):
        self._connections: set[WebSocket] = set()

    def add(self, ws: WebSocket) -> None:
        self._connections.add(ws)

    def remove(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    async def broadcast(self, event: Event) -> None:
        payload = event.to_wire()
        for ws in list(self._connections):
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001 — a dead socket must not break the pipeline
                self._connections.discard(ws)


def load_settings(store: Store) -> Settings:
    return Settings.from_env().apply_overrides(store.get_settings_overrides())


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = Store()
    app.state.store = store
    app.state.chat = ChatService(load_settings(store), store)
    app.state.hub = Hub()
    app.state.voice = None
    pruned = store.prune_memory()
    if pruned:
        logger.info("Pruned %d expired memory rows", pruned)
    logger.info("Sentinel Core %s ready", __version__)
    yield
    if app.state.voice is not None:
        await app.state.voice.stop()
    await app.state.chat.aclose()
    store.close()


app = FastAPI(title="Sentinel Core", version=__version__, lifespan=lifespan)

# The desktop app's webview calls us cross-origin (vite dev server / tauri://).
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    text: str
    session_id: str | None = None


class SettingsUpdate(BaseModel):
    overrides: dict


class SecretUpdate(BaseModel):
    name: str
    value: str


def _redacted_settings(app: FastAPI) -> dict:
    settings: Settings = app.state.chat.llm.settings
    data = settings.model_dump()
    data.pop("tavily_api_key", None)
    return data


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": __version__,
        "providers": app.state.chat.llm.validate(),
    }


@app.get("/settings")
async def get_settings():
    return _redacted_settings(app)


@app.put("/settings")
async def put_settings(update: SettingsUpdate):
    store: Store = app.state.store
    store.save_settings_overrides(update.overrides)
    await app.state.chat.reload(load_settings(store))
    return _redacted_settings(app)


@app.post("/settings/reload")
async def reload_settings():
    await app.state.chat.reload(load_settings(app.state.store))
    return {"reloaded": True}


@app.post("/secrets")
async def put_secret(update: SecretUpdate):
    allowed = set(PROVIDER_KEY_ENV.values()) | {
        "TAVILY_API_KEY",
        "ELEVENLABS_API_KEY",
        "PORCUPINE_KEY",
        "SPOTIPY_CLIENT_ID",
        "SPOTIPY_CLIENT_SECRET",
        "SPOTIPY_REDIRECT_URI",
    }
    if update.name not in allowed:
        raise HTTPException(400, f"Unknown secret name: {update.name}")
    set_secret(update.name, update.value)
    await app.state.chat.reload(load_settings(app.state.store))
    return {"saved": update.name}


@app.post("/voice/start")
async def voice_start():
    if app.state.voice is not None and app.state.voice.running:
        return {"running": True, "state": app.state.voice.state}
    try:
        from .voice.pipeline import VoicePipeline
    except Exception as exc:  # noqa: BLE001 — missing audio deps/hardware
        raise HTTPException(500, f"Voice dependencies unavailable: {exc}") from exc
    pipeline = VoicePipeline(app.state.chat, app.state.store, app.state.hub.broadcast)
    try:
        await pipeline.start()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Could not start voice pipeline: {exc}") from exc
    app.state.voice = pipeline
    return {"running": True, "state": pipeline.state}


@app.post("/voice/stop")
async def voice_stop():
    if app.state.voice is not None:
        await app.state.voice.stop()
    return {"running": False}


@app.get("/voice/status")
async def voice_status():
    voice = app.state.voice
    return {"running": bool(voice and voice.running), "state": voice.state if voice else "idle"}


@app.get("/sessions/{session_id}/messages")
async def session_messages(session_id: str):
    return app.state.store.get_messages(session_id, limit=200)


@app.post("/chat")
async def chat(request: ChatRequest):
    """Non-streaming convenience endpoint (the WebSocket is the primary path)."""
    store: Store = app.state.store
    session_id = request.session_id or store.start_session()

    async def _noop(event: Event) -> None:
        return None

    text = await app.state.chat.run_turn(session_id, request.text, _noop)
    return {"session_id": session_id, "response": text}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    store: Store = app.state.store
    hub: Hub = app.state.hub
    hub.add(ws)
    session_id = store.start_session()

    async def emit(event: Event) -> None:
        await ws.send_json(event.to_wire())

    await emit(Event(type=EventType.READY, session_id=session_id, data={"version": __version__}))
    try:
        while True:
            message = await ws.receive_json()
            if message.get("type") == "chat" and message.get("text"):
                sid = message.get("session_id") or session_id
                await app.state.chat.run_turn(sid, message["text"], emit)
            else:
                await emit(
                    Event(
                        type=EventType.ERROR,
                        session_id=session_id,
                        data={"message": f"Unknown message: {message}"},
                    )
                )
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(ws)
        store.end_session(session_id)
