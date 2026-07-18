# Repository Guidelines

## Project Structure & Module Organization
- `launcher.py`: unified entry point that starts backend + frontend together.
- `integration/`: thread-safe bridge (event bus, backend runner, status widget); keep cross-component orchestration here.
- `Sentinel-AI-Backend/`: voice assistant + LangGraph agents.
- `Sentinel-AI-Backend/src/tools/`: tool implementations (browser, music, meeting, system, productivity).
- `Sentinel-AI-Frontend/`: PyQt5 desktop UI.
- `Sentinel-AI-Frontend/ui/views/`: screens (`login_page.py`, `signup_page.py`, `dashboard.py`, `settings_page.py`).
- `Sentinel-AI-Frontend/devTest/` and root `test_threading.py`: utility test scripts.

## Build, Test, and Development Commands
- `python setup_launcher.py`: install backend/frontend dependencies.
- `python launcher.py`: run the integrated desktop app (recommended flow).
- `cd Sentinel-AI-Backend; python main.py`: run backend only.
- `cd Sentinel-AI-Frontend; python main.py`: run frontend only.
- `python test_threading.py`: quick threading/event sanity check.
- `cd Sentinel-AI-Frontend; python devTest/test_atlas_connection.py`: verify MongoDB Atlas connectivity.

## Coding Style & Naming Conventions
- Use Python with 4-space indentation and PEP 8 spacing.
- Prefer `snake_case` for functions/modules, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants/env keys.
- Keep component boundaries clear: avoid backend/frontend edits when an integration-layer change is sufficient.
- Follow existing file patterns (e.g., service modules in `services/`, UI pages in `ui/views/`, tools in `src/tools/`).

## Testing Guidelines
- No single formal test suite is configured; use targeted script-based checks.
- Add focused verification scripts near the relevant component (`devTest/` or feature folder).
- Name tests descriptively (`test_<feature>.py`) and keep setup explicit (required `.env` keys, credentials).
- Before PRs, run the launcher path and any changed component standalone.

## Commit & Pull Request Guidelines
- Recent history favors short, imperative summaries (examples: `Added MongoDB as agent memory`, `Fixed the Google Meet Service`, `UI: Dashboard`).
- Keep commits scoped to one logical change and mention affected area (`backend`, `frontend`, `integration`).
- PRs should include: purpose, key changes, manual test steps, env/config updates, and UI screenshots when views are modified.
- Link related issues/tasks and note any follow-up work explicitly.

## Security & Configuration Tips
- Never commit `.env`, OAuth credentials, or API keys.
- Backend and frontend each require their own `.env`; document new variables in both code comments and PR description.
