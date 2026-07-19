<h1 align="center">🛡️ Sentinel AI</h1>

<p align="center">
  <b>A voice-controlled desktop AI assistant for Windows.</b><br/>
  Say the wake word — then just talk to your computer.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/LangGraph-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white" />
  <img src="https://img.shields.io/badge/Tauri-24C8D8?style=for-the-badge&logo=tauri&logoColor=white" />
  <img src="https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB" />
  <img src="https://img.shields.io/badge/Groq-F55036?style=for-the-badge&logoColor=white" />
</p>

---

## What it is

Sentinel AI is a desktop assistant you drive by voice or chat. It listens for a
wake word ("Hey Jarvis" by default, custom models supported), transcribes your
speech with **Groq Whisper** at ~216× real-time, routes the request through a
**LangGraph supervisor** to a specialist agent, acts on your machine, and
**speaks the answer back** — starting before the full response is even
generated, and interruptible mid-sentence by saying the wake word again.

Everything is **local-first**: conversation history, notes, and settings live
in SQLite on your machine; API keys live in the Windows Credential Manager. No
accounts, no cloud database.

## 🤖 The agents

| Agent | Purpose | Tools |
|---|---|---|
| 🌐 **Browser** | Web search (Tavily), weather, news, translation, stocks, Wikipedia | 13 |
| 🖱️ **BrowserActions** | Drives a real Edge window: click, type, fill forms, multi-step web tasks (Playwright MCP) | 24 |
| 🎵 **Music** | Spotify playback and discovery | 9 |
| 📅 **Meeting** | Google Meet and Calendar | 5 |
| ✉️ **Email** | Gmail: read, search, draft, send | 5 |
| 📝 **Notes** | Local notes (SQLite) | 6 |
| ⏰ **Productivity** | Reminders, timers, and recurring routines (morning briefings) | 7 |
| 📄 **Documents** | Q&A over your PDFs/Word/text files with source citations (local RAG) | 3 |
| 🧠 **Memory** | Permanent facts, meaning-based recall of past conversations | 3 |
| 👁️ **Screen** | Sees your screen: describe, read errors, summarize (vision model) | 1 |
| 🖥️ **Computer** | Operates app windows via accessibility: click buttons by name, type into fields | 4 |
| 🎧 **MeetingNotes** | Records what plays on your PC → transcript file + summary | 3 |
| 💻 **Coder** | Answers questions / makes changes in your code projects via Claude Code | 2 |
| 💬 **Messenger** | Telegram: send messages to your phone, read replies | 3 |
| 📁 **Files** | Browse, tree view, find, open, and read files; Downloads/Documents/etc. | 8 |
| ⚙️ **System** | Volume, brightness, WiFi/Bluetooth, apps, workspaces, clipboard, wallpaper, windows, media keys, screenshots, power | 27 |

The System agent's tools come from **[`mcp-windows/`](mcp-windows/)** — a
standalone [MCP](https://modelcontextprotocol.io) server built on real OS APIs
(no UI automation hacks) that also works in Claude Desktop or any MCP client.

## 🧠 Multi-provider brain

Bring your own model: **Groq** (default), **Cerebras**, Azure OpenAI, OpenAI,
Ollama (fully local), or Zhipu AI — switchable live from Settings with no
restart, with per-agent assignment and automatic fallback. Groq's free tier is
enough to run everything, including speech-to-text.

## 🎙️ How a request flows

```
"Hey Jarvis"  ──►  wake word (openWakeWord, on-device)
                        │  chime
                   speech → text (Groq Whisper large-v3-turbo)
                        │
                   supervisor (LangGraph, structured routing)
                        │
                   agent runs its tools ──► supervisor ──► reply
                        │
                   streaming TTS (ElevenLabs, barge-in aware)
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│  app/ — Tauri 2 + React desktop app             │
│  chat · voice toggle · live agent trace ·       │
│  settings · activity log                        │
└──────────────┬──────────────────────────────────┘
               │ WebSocket (events/streaming) + REST
┌──────────────▼──────────────────────────────────┐
│  sentinel_core/ — async FastAPI service         │
│  voice pipeline · LangGraph agents · SQLite ·   │
│  keyring secrets · live settings reload         │
└──────┬──────────────────────────┬───────────────┘
       │ MCP (stdio)              │ HTTPS
┌──────▼───────────┐   ┌──────────▼────────────────┐
│  mcp-windows/    │   │  Groq · Cerebras · Spotify│
│  Windows control │   │  Google · Tavily · Eleven │
└──────────────────┘   └───────────────────────────┘
```

## 🚀 Getting started

### Run from source

Requirements: Windows 11, [uv](https://docs.astral.sh/uv/), Node 20+, Rust (for the app shell).

```bash
# 1. Core service
uv run --group core python -m sentinel_core

# 2. Desktop app (second terminal)
cd app && npm install && npm run tauri dev
```

On first launch, open **Settings** and paste an API key — a free
[Groq key](https://console.groq.com/keys) unlocks chat, all agents, and
speech-to-text. Add an [ElevenLabs](https://elevenlabs.io) key for premium
voices (offline TTS is the fallback). Keys go straight to the Windows
Credential Manager — never to files.

### Build the installer

See [`packaging/README.md`](packaging/README.md) — three steps produce a
self-contained NSIS installer (~120 MB); the target machine needs no Python,
Node, or Rust.

## 🎙️ Voice tips

- Speak after the **chime**; say the wake word during playback to interrupt
- Custom wake word: train one in ~1 hour (free) with
  [openWakeWord's Colab notebook](https://colab.research.google.com/github/dscripka/openWakeWord/blob/main/notebooks/automatic_model_training.ipynb),
  then point `WAKEWORD_MODEL` at the `.onnx`
- `CONTINUOUS_LISTENING=true` enables follow-ups without repeating the wake
  word (off by default — it will treat ambient speech as commands)

## 🗺️ Roadmap

- [ ] Auto-update (Tauri updater + GitHub Releases)
- [ ] Custom "Sentinel" wake-word model
- [ ] Streaming STT (sub-1.5s voice turns)
- [ ] Crash reporting

## 📚 More

- [`CLAUDE.md`](CLAUDE.md) / [`AGENTS.md`](AGENTS.md) — contributor guides
- [`REBUILD_PLAN.md`](REBUILD_PLAN.md) — the v2 rebuild plan and audit
- [`mcp-windows/README.md`](mcp-windows/README.md) — the Windows MCP server, incl. Claude Desktop setup
- [`docs/`](docs/) — historical design docs from the v1 prototype
