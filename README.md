<h1 align="center">🛡️ Sentinel AI</h1>

<p align="center">
  <b>A voice-controlled desktop AI assistant.</b><br/>
  Say <i>"Sentinel"</i> — then just talk to your computer.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54" />
  <img src="https://img.shields.io/badge/LangGraph-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/PyQt5-41CD52?style=for-the-badge&logo=qt&logoColor=white" />
</p>

---

## What it is

Sentinel AI is a desktop assistant you drive with your voice. It listens for a
custom **"Sentinel"** wake word, transcribes what you say, routes the request to
whichever specialist agent can handle it, and acts on your machine — opening
pages, playing music, scheduling meetings, taking screenshots, controlling system
settings.

It is built as a **supervised multi-agent system** on LangGraph: a supervisor node
reads the request and delegates to one of five agents, each owning its own toolset.

## 🤖 The agents

| Agent | Purpose | Tools |
|---|---|---|
| 🌐 **Browser** | Web search, scraping, weather, news, translation, currency | 14 |
| 🎵 **Music** | Playback and discovery | 25+ |
| 📅 **Meeting** | Google Meet and Calendar management | 6 |
| ⚙️ **System** | Computer and OS control | 15 |
| ⏱️ **Productivity** | Time management and focus | 6 |

**5 agents · 66+ tools**, coordinated by a supervisor that picks the right one and
can chain several together for a single spoken request.

## 🎙️ How a request flows

```
"Sentinel"  ──►  wake word (Porcupine)
                      │
                 speech → text (Whisper / SpeechRecognition)
                      │
                 supervisor (LangGraph)  ──►  routes to agent
                      │
                 agent runs its tools  ──►  spoken + on-screen reply
```

## 🧱 Stack

- **Orchestration** — LangGraph + LangChain (supervisor / agent graph)
- **Models** — Anthropic Claude, with Ollama for local inference
- **Voice** — Porcupine wake word, Whisper + SpeechRecognition, PyAudio
- **Search** — Tavily
- **API** — FastAPI + Uvicorn
- **Desktop UI** — PyQt5

## 📁 Layout

This repo is the full system — backend and desktop frontend together.

```
Sentinel-AI-Backend/    FastAPI + LangGraph agent system, tools, wake word
Sentinel-AI-Frontend/   PyQt5 desktop client (auth, UI, services, database)
```

## 🚀 Getting started

```bash
# 1. Backend
cd Sentinel-AI-Backend
pip install -r requirements.txt
cp .env.example .env        # add your API keys
python main.py

# 2. Frontend (in a second terminal)
cd Sentinel-AI-Frontend
pip install -r requirements.txt
python main.py
```

You'll need API keys for your model provider and for Tavily (web search). See
`Sentinel-AI-Backend/.env.example` for the full list.

## 📚 Documentation

| Doc | What's in it |
|---|---|
| [AGENTS_OVERVIEW.md](AGENTS_OVERVIEW.md) | Every agent and all 66+ tools |
| [VOICE_COMMANDS.md](VOICE_COMMANDS.md) | What you can actually say |
| [SYSTEM_CONTROL_AGENT.md](SYSTEM_CONTROL_AGENT.md) | System control capabilities |
| [PRODUCTIVITY_AGENT.md](PRODUCTIVITY_AGENT.md) | Productivity agent |
| [SCREENSHOT_FEATURE.md](SCREENSHOT_FEATURE.md) | Screen capture |
| [MEETING_QUICKSTART.md](MEETING_QUICKSTART.md) · [GOOGLE_MEET_SETUP.md](GOOGLE_MEET_SETUP.md) | Meetings & Calendar setup |
| [ARCHITECTURE_DIAGRAM.txt](ARCHITECTURE_DIAGRAM.txt) | System architecture |

<!-- TODO (Asim): drop a short screen-recording GIF right here — a 10s clip of you
     saying "Sentinel, ..." and it acting will do more for this repo than any
     amount of README text. -->

---

<p align="center">Built by <a href="https://github.com/AsimAftab">Asim Aftab</a> · <a href="https://asimaftab.app">asimaftab.app</a></p>
