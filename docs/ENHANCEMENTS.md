# ENHANCEMENTS.md — Sentinel AI Desktop Technical Roadmap

> **Last Updated:** 2026-03-04
> **Scope:** Full-stack audit of Backend, Frontend, and Integration Layer

---

## Executive Summary

| Category | Count | Status |
|----------|-------|--------|
| Critical Bugs | 8 | ✅ All complete |
| Security Vulnerabilities | 7 | ✅ All complete |
| Performance Optimizations | 12 | ✅ All complete |
| Backend Enhancements | 18 | Partial |
| Frontend Enhancements | 14 | Partial |
| Integration Enhancements | 9 | Partial |
| New Agents Proposed | 6 | 2/6 complete (Notes, Email) |
| New Tools Proposed | 20+ | Partial |
| Architecture Improvements | 8 | ✅ All complete |
| DevOps Gaps | 6 | Partial (ruff/pyright done) |

**Total actionable items: ~100+**

---

## 1. CRITICAL BUGS

### BUG-1: Supervisor routing validation logic evaluates incorrectly
- **Severity:** Critical
- **File:** `Sentinel-AI-Backend/src/graph/graph_builder.py:259`
- **Issue:** `not result or not result in [...]` — the `not` binds to `result` first, producing `not result` (a bool), then checks if that bool is `in` the list. This means any valid non-empty string passes the first check, and the `in` check compares `False in ["Browser", ...]` which is always `True`.
- **Impact:** Invalid supervisor outputs may not default to FINISH as intended; unexpected routing behavior.
- **Fix:**
  ```python
  # Current (broken)
  if not result or not result in ["Browser", "Music", "Meeting", "System", "Productivity", "FINISH"]:

  # Fixed
  if not result or result not in ["Browser", "Music", "Meeting", "System", "Productivity", "FINISH"]:
  ```

### BUG-2: Memory sessions never cleaned on crash (orphaned MongoDB docs)
- **Severity:** Critical
- **File:** `Sentinel-AI-Backend/src/utils/orchestrator.py:146-162`
- **Issue:** `memory.start_session()` is called at line 146, but if the conversation loop crashes or `KeyboardInterrupt` fires before `memory.end_session()`, the session remains open in MongoDB indefinitely. The `except KeyboardInterrupt` at line 220 does not call `memory.end_session()`.
- **Impact:** Orphaned session documents accumulate in MongoDB, polluting memory context for future agents.
- **Fix:** Wrap the conversation loop in `try/finally` and call `memory.end_session()` in the `finally` block. Also add cleanup in the `KeyboardInterrupt` handler.

### BUG-3: Message type mismatch — agents return tuples, router expects strings
- **Severity:** Critical
- **File:** `Sentinel-AI-Backend/src/graph/graph_builder.py:213, 274-288`
- **Issue:** Agent nodes return `{"messages": [("ai", f"({agent_name} agent): {output}")]}` (a tuple), but the `router()` function at line 274 does `next_agent = state['messages'][-1]` and checks `if "Browser" in next_agent`. The `in` operator on a tuple checks membership, not substring — it works accidentally because the supervisor returns plain strings like `"Browser"`, but agent response tuples could confuse downstream routing if agents are chained.
- **Impact:** Fragile; works by coincidence. Any change to message format will break routing silently.
- **Fix:** Use `HumanMessage`/`AIMessage` objects consistently. In the router, extract `.content` from the last message rather than relying on `in` operator on raw state.

### BUG-4: Spotify plays on wrong device (first device, not active)
- **Severity:** High
- **File:** `Sentinel-AI-Backend/src/tools/music_tools.py:52-61`
- **Issue:** When no active device is found, the code falls back to `devices['devices'][0]['id']` — the first device in the list, which may be a phone, TV, or inactive device.
- **Impact:** Music plays on unexpected device; user confusion.
- **Fix:** Prompt the user to select a device, or transfer playback to the selected device before playing. At minimum, warn which device will be used.

### BUG-5: Global browser instance not thread-safe (race condition)
- **Severity:** High
- **File:** `Sentinel-AI-Backend/src/tools/playwright_music_tools.py:8-11`
- **Issue:** `_browser`, `_context`, `_page` are global mutable variables accessed without any thread lock. If two agent calls invoke `_get_browser()` simultaneously, a race condition can cause duplicate browser instances or crashes.
- **Impact:** Browser resource corruption, crashes, or resource leaks.
- **Fix:** Add `threading.Lock()` around `_get_browser()` and `_close_browser()`.

### BUG-6: Global timer/alarm counters not thread-safe (ID collision)
- **Severity:** High
- **File:** `Sentinel-AI-Backend/src/tools/productivity_tools.py:13-14`
- **Issue:** `timer_id_counter` and `alarm_id_counter` are global integers incremented without locks at lines 85-86 and 180-181. Concurrent timer/alarm creation could produce duplicate IDs.
- **Impact:** Timer/alarm ID collisions; wrong timer cancelled.
- **Fix:** Use `threading.Lock()` or `itertools.count()` for atomic ID generation.

### BUG-7: Path traversal vulnerability in file download tool
- **Severity:** Critical (Security)
- **File:** `Sentinel-AI-Backend/src/tools/browser_tools.py:249-276`
- **Issue:** The `download_file()` tool constructs `filepath = os.path.join(downloads_dir, filename)` where `filename` comes from user input or URL parsing. A filename like `../../etc/cron.d/malicious` would write outside the downloads directory.
- **Impact:** Arbitrary file write on the host system.
- **Fix:** Sanitize filename — strip path separators, use `os.path.basename()`, and validate the resolved path is within the downloads directory:
  ```python
  filename = os.path.basename(filename)
  filepath = os.path.join(downloads_dir, filename)
  if not os.path.abspath(filepath).startswith(os.path.abspath(downloads_dir)):
      return "Error: Invalid filename"
  ```

### BUG-8: No LLM provider validation on startup
- **Severity:** High
- **File:** `Sentinel-AI-Backend/src/utils/llm_config.py:32-78`
- **Issue:** If no LLM provider is enabled and fallback is disabled, `get_llm()` raises `ValueError` at runtime when the first agent tries to use it. There's no startup validation to catch this early.
- **Impact:** Application starts, appears ready, then crashes on first voice command with an opaque error.
- **Fix:** Add validation in `__init__()` that at least one provider is enabled, or that the primary provider has valid credentials. Log a clear error and exit early.

---

## 2. SECURITY VULNERABILITIES

### SEC-1: Weak password hashing — SHA-256 with password-derived salt
- **Severity:** Critical
- **File:** `Sentinel-AI-Frontend/auth/keyring_auth.py:22-25`
- **Issue:** The salt is derived from the password itself (`hashlib.sha256(password.encode()).hexdigest()[:16]`), making it deterministic. Identical passwords produce identical hashes. SHA-256 is also too fast for password hashing — vulnerable to brute force.
- **Impact:** Passwords can be cracked with rainbow tables or GPU brute force.
- **Fix:** Use `bcrypt`, `argon2`, or `scrypt` with random salts (consistent with `user_service.py` which already uses bcrypt).

### SEC-2: Two different hashing algorithms (SHA-256 vs bcrypt)
- **Severity:** High
- **File:** `Sentinel-AI-Frontend/auth/keyring_auth.py` vs `Sentinel-AI-Frontend/database/user_service.py:24`
- **Issue:** `keyring_auth.py` uses SHA-256, while `user_service.py` uses bcrypt. A user registered via one path cannot authenticate via the other.
- **Impact:** Authentication inconsistency; potential lockout or bypass.
- **Fix:** Standardize on bcrypt everywhere. Migrate existing SHA-256 hashes with a one-time migration or dual-check during login.

### SEC-3: No CSRF/state parameter in OAuth flows
- **Severity:** High
- **File:** `Sentinel-AI-Frontend/services/spotify_service.py`
- **Issue:** The Spotify OAuth flow uses a local HTTP callback server but doesn't validate a `state` parameter. An attacker could redirect the user to a malicious auth code.
- **Impact:** OAuth token theft via CSRF attack.
- **Fix:** Generate a random `state` parameter before auth, pass it in the auth URL, and verify it in the callback.

### SEC-4: Path traversal in `download_file()` (same as BUG-7)
- **Severity:** Critical
- **File:** `Sentinel-AI-Backend/src/tools/browser_tools.py:249-276`
- **Details:** See BUG-7.

### SEC-5: Error messages expose full Python tracebacks
- **Severity:** High
- **Files:**
  - `Sentinel-AI-Backend/src/tools/meeting_tools.py:183-193` — `traceback.format_exc()` included in return value
  - `Sentinel-AI-Frontend/services/meet_service.py:81-83` — traceback in error return
- **Impact:** Internal file paths, library versions, and code structure leaked to users/LLM agents.
- **Fix:** Log full tracebacks server-side; return generic user-friendly error messages.

### SEC-6: No rate limiting on any API calls
- **Severity:** Medium
- **Files:** All tool files, `user_service.py`, `meet_service.py`
- **Issue:** No rate limiting on Spotify API, Google Calendar API, Tavily API, or authentication attempts.
- **Impact:** API abuse, credential brute-forcing, quota exhaustion.
- **Fix:** Add rate limiting decorators or middleware. For auth, lock out after N failed attempts.

### SEC-7: OAuth tokens stored unencrypted on disk
- **Severity:** Medium
- **Files:** `Sentinel-AI-Frontend/services/meet_service.py`, `Sentinel-AI-Frontend/services/token_store.py`
- **Issue:** OAuth tokens stored as plain JSON in MongoDB and `token.json` on disk. Also stored in `token_store.py` without encryption.
- **Impact:** Token theft if database or filesystem is compromised.
- **Fix:** Encrypt tokens at rest using the system keyring or a derived encryption key. Consider DPAPI on Windows.

---

## 3. PERFORMANCE OPTIMIZATIONS

### PERF-1: New MongoClient per database operation (frontend)
- **Severity:** Critical
- **Files:**
  - `Sentinel-AI-Frontend/database/user_service.py:14` — new client per `save_user()` and `get_user_by_username()`
  - `Sentinel-AI-Frontend/database/settings_service.py:23, 46` — new client per `get_settings()` and `update_settings()`
- **Impact:** Creates and destroys TCP connections for every DB call. Dashboard init makes 3+ DB calls = 3+ connections. 100s of connections per session.
- **Fix:** Create a shared singleton `MongoClient` in `DatabaseConfig` or a connection pool module. Reuse across all services.

### PERF-2: TTS blocks entire conversation loop
- **Severity:** High
- **File:** `Sentinel-AI-Backend/src/utils/orchestrator.py:171`
- **Issue:** `tts.speak(response, blocking=True)` blocks the main conversation loop. During 5-10 second speech output, the system cannot listen for commands or process events.
- **Impact:** 5+ second delays; feels unresponsive.
- **Fix:** Run TTS in a separate thread. Use `blocking=False` and a callback or event to signal completion.

### PERF-3: Frontend polls event bus every 100ms (wastes CPU on idle)
- **Severity:** Medium
- **File:** `Sentinel-AI-Frontend/ui/views/dashboard.py:143`
- **Issue:** `QTimer` fires every 100ms to check for backend events. When idle, this produces ~36,000 unnecessary polls per hour.
- **Impact:** Wasted CPU cycles; battery drain on laptops.
- **Fix:** Use adaptive polling — start at 100ms when active, back off to 1000ms or more after N empty polls. Or replace polling with a signal-based approach using `QThread` + signals.

### PERF-4: Synchronous tool execution (all blocking)
- **Severity:** Medium
- **Files:** All tool files under `src/tools/`
- **Issue:** Every tool (Spotify API, web scraping, Google Calendar) runs synchronously. The agent thread blocks while waiting for HTTP responses.
- **Impact:** Agent responses take 3-15 seconds depending on tool latency.
- **Fix:** Use `asyncio` with `aiohttp` for HTTP-based tools. LangGraph supports async agents.

### PERF-5: Memory context queried per agent call (redundant MongoDB queries)
- **Severity:** Medium
- **File:** `Sentinel-AI-Backend/src/graph/graph_builder.py:160-165`
- **Issue:** `_memory.get_context_for_agent()` is called every time an agent node executes. Each call hits MongoDB. In a multi-agent conversation, this means 2-5 MongoDB queries per voice command.
- **Impact:** Added latency per agent invocation.
- **Fix:** Cache memory context per conversation turn. Query once at the supervisor level and pass context through state.

### PERF-6: Dashboard rebuilds entire widget tree on refresh
- **Severity:** Medium
- **File:** `Sentinel-AI-Frontend/ui/views/dashboard.py:212-236`
- **Issue:** `_refresh_dashboard()` destroys all widgets and rebuilds from scratch. This includes re-querying MongoDB for service status and user data.
- **Impact:** UI jank and flicker on refresh; unnecessary DB calls.
- **Fix:** Only update changed elements (status badges, card states). Use Qt's model/view pattern for service cards.

### PERF-7: Timer accumulation — new QTimer per dashboard visit
- **Severity:** Medium
- **File:** `Sentinel-AI-Frontend/ui/views/dashboard.py:141-143`
- **Issue:** Every `DashboardPage` instantiation (including from `show_dashboard()` in `main.py:36-38`) creates a new `QTimer`. Old dashboard pages and their timers are not cleaned up properly because `addWidget` keeps references.
- **Impact:** Memory leak; accumulated timers running simultaneously.
- **Fix:** Stop and delete existing timers in `DashboardPage` destructor. Better: reuse the same dashboard instance instead of creating new ones.

### PERF-8: Browser instances never cleaned up (playwright)
- **Severity:** Medium
- **File:** `Sentinel-AI-Backend/src/tools/playwright_music_tools.py:8-11, 14-27`
- **Issue:** The global `_browser` instance is created on first use but never cleaned up on application shutdown. The `close_music_browser()` tool exists but is only called if the agent decides to.
- **Impact:** Chromium process leak; consuming ~200MB+ RAM indefinitely.
- **Fix:** Register `_close_browser()` with `atexit` module. Add shutdown hook in the orchestrator.

### PERF-9: LLM instance cache uses single shared instance per provider
- **Severity:** Low
- **File:** `Sentinel-AI-Backend/src/utils/llm_config.py:174-177`
- **Issue:** All agents sharing the same provider use the same LLM instance. While LangChain LLMs are generally thread-safe, shared connection pools may bottleneck under concurrent agent calls.
- **Impact:** Potential blocking when multiple agents execute simultaneously.
- **Fix:** Consider per-agent instances or validate thread safety of the underlying HTTP client.

### PERF-10: Blocking service calls freeze UI
- **Severity:** High
- **File:** `Sentinel-AI-Frontend/ui/views/dashboard.py:627`
- **Issue:** `future.result()` is called on the main (UI) thread, blocking the entire Qt event loop until the OAuth flow completes. The progress dialog cannot update.
- **Impact:** Application appears frozen during service connection (5-30 seconds).
- **Fix:** Use `QThread` or `QRunnable` for the OAuth flow. Connect completion to a slot that updates the UI.

### PERF-11: No Spotify API timeout
- **Severity:** Medium
- **File:** `Sentinel-AI-Backend/src/tools/music_tools.py` (entire file)
- **Issue:** Spotify API calls via `spotipy` have no explicit timeout. If Spotify servers are slow, the tool blocks indefinitely.
- **Impact:** Agent thread hangs; no response to user.
- **Fix:** Configure `requests.Session` with timeout on the `spotipy` client, or wrap calls with `concurrent.futures.ThreadPoolExecutor` and timeout.

### PERF-12: Hardcoded `time.sleep()` instead of event waits
- **Severity:** Low
- **Files:**
  - `Sentinel-AI-Backend/src/tools/playwright_music_tools.py:87, 146, 161, 223, 309, 327`
  - `Sentinel-AI-Backend/src/tools/system_tools.py:690, 696-698, 700, 748, 768`
- **Issue:** Hardcoded `time.sleep()` calls for waiting on UI state changes. Too short = flaky; too long = unnecessary delay.
- **Impact:** Fragile timing that varies by system speed.
- **Fix:** Use Playwright's built-in `wait_for` methods (which already exist in some places). For system tools, poll the actual state rather than sleeping a fixed duration.

---

## 4. BACKEND ENHANCEMENTS

### 4.1 Voice Pipeline

| # | Enhancement | File | Severity |
|---|-------------|------|----------|
| 1 | Add wake word sensitivity configuration | `orchestrator.py` | Medium |
| 2 | Support multiple wake words | `wake_word_listener.py` | Low |
| 3 | Add voice activity detection (VAD) to reduce false triggers | `speech_recognizer.py` | Medium |
| 4 | Support continuous listening mode (no wake word required) | `orchestrator.py` | Low |
| 5 | Add speech-to-text language selection | `speech_recognizer.py` | Medium |
| 6 | Make `is_follow_up_question()` more robust — current keyword matching has false positives (any response with "?" triggers follow-up) | `orchestrator.py:40-76` | Medium |

### 4.2 Multi-Agent Graph

| # | Enhancement | File | Severity |
|---|-------------|------|----------|
| 1 | Add multi-agent collaboration (agents can call other agents) | `graph_builder.py` | Medium |
| 2 | Add agent timeout — currently no limit on agent execution time | `graph_builder.py:182` | High |
| 3 | Add retry logic for failed agent invocations | `graph_builder.py:146-213` | Medium |
| 4 | Support streaming responses (partial results while agent works) | `graph_builder.py` | Medium |
| 5 | Add agent execution metrics (success rate, avg duration) | `graph_builder.py:188-211` | Low |

### 4.3 LLM Configuration

| # | Enhancement | File | Severity |
|---|-------------|------|----------|
| 1 | Add per-agent temperature configuration | `llm_config.py` | Medium |
| 2 | Add LLM response caching for repeated queries | `llm_config.py` | Low |
| 3 | Add model parameter validation (check API keys on startup) | `llm_config.py:32-78` | High |
| 4 | Support streaming LLM responses for faster perceived latency | `llm_config.py` | Medium |

### 4.4 Agent Memory

| # | Enhancement | File | Severity |
|---|-------------|------|----------|
| 1 | Add session cleanup on crash (see BUG-2) | `agent_memory.py` | Critical |
| 2 | Add memory search/query by content (semantic search) | `agent_memory.py` | Low |
| 3 | Add long-term memory (persistent across 24h TTL) for user preferences | `agent_memory.py` | Medium |
| 4 | Cache `get_context_for_agent()` result per conversation turn | `agent_memory.py:376-438` | Medium |

### 4.5 Existing Tools (per-tool issues)

**Browser Tools** (`src/tools/browser_tools.py`):
| # | Issue | Line(s) | Severity |
|---|-------|---------|----------|
| 1 | Path traversal in `download_file()` (see BUG-7) | 249-276 | Critical |
| 2 | `get_currency_exchange()` uses deprecated `exchangerate.host` API | 449-477 | Medium |
| 3 | No timeout on `tavily_web_search()` (Tavily client handles it but no explicit limit) | 18-58 | Low |
| 4 | `scrape_webpage()` downloads entire page including images | 62-136 | Low |

**Music Tools** (`src/tools/music_tools.py`):
| # | Issue | Line(s) | Severity |
|---|-------|---------|----------|
| 1 | Spotify device selection falls back to first device (see BUG-4) | 52-60 | High |
| 2 | Bare `except:` in `play_music_smart()` and `play_mood_music()` | 397, 912 | Medium |
| 3 | YouTube scraping with hardcoded user-agent string | 431-433, 500-502 | Low |
| 4 | `play_youtube_music_direct()` opens TWO browser tabs unnecessarily | 577-590 | Low |
| 5 | No Spotify API timeout (see PERF-11) | Entire file | Medium |

**Playwright Music Tools** (`src/tools/playwright_music_tools.py`):
| # | Issue | Line(s) | Severity |
|---|-------|---------|----------|
| 1 | Global browser not thread-safe (see BUG-5) | 8-11 | High |
| 2 | Browser instance never cleaned up on shutdown (see PERF-8) | 14-27 | Medium |
| 3 | Hardcoded `time.sleep()` instead of proper waits | 87, 146, 161 | Low |
| 4 | Playwright instance leaks if `sync_playwright().start()` fails | 19 | Medium |

**Productivity Tools** (`src/tools/productivity_tools.py`):
| # | Issue | Line(s) | Severity |
|---|-------|---------|----------|
| 1 | Counter not thread-safe (see BUG-6) | 13-14 | High |
| 2 | Timer threads are daemon — may not fire if main thread exits | 97 | Medium |
| 3 | No persistence — all timers/alarms lost on restart | 10-14 | Medium |
| 4 | Windows-only (`winsound`) — no cross-platform sound | 7, 22 | Low |

**Meeting Tools** (`src/tools/meeting_tools.py`):
| # | Issue | Line(s) | Severity |
|---|-------|---------|----------|
| 1 | Full traceback exposed in error messages (see SEC-5) | 183-193 | High |
| 2 | `logging.basicConfig(level=logging.DEBUG)` overrides app-wide config | 21 | Medium |
| 3 | UTC timezone hardcoded — no user timezone support | 109, 119-120, 229-231 | Medium |
| 4 | `cancel_next_meeting()` cancels without confirmation from agent | 462-504 | Low |

**System Tools** (`src/tools/system_tools.py`):
| # | Issue | Line(s) | Severity |
|---|-------|---------|----------|
| 1 | UI automation (`pyautogui`) is fragile — depends on screen layout | 694-728, 747-781 | Medium |
| 2 | `open_application()` uses `shell=True` with user input — command injection risk | 400-406 | High |
| 3 | Bluetooth toggle relies on Tab count — breaks if UI changes | 694-698 | Medium |
| 4 | WiFi quick toggle uses hardcoded screen coordinates | 1037-1038 | Medium |

---

## 5. FRONTEND ENHANCEMENTS

### 5.1 Authentication & Security

| # | Enhancement | File | Severity |
|---|-------------|------|----------|
| 1 | Replace SHA-256 with bcrypt in keyring_auth (see SEC-1) | `auth/keyring_auth.py:22-25` | Critical |
| 2 | Unify hashing algorithm across keyring and MongoDB (see SEC-2) | `auth/keyring_auth.py`, `database/user_service.py` | High |
| 3 | Add account lockout after N failed login attempts | `auth/keyring_auth.py:147-174` | Medium |
| 4 | Add password complexity requirements (currently 6 chars minimum) | `auth/keyring_auth.py:44-46` | Medium |
| 5 | Add session token rotation on sensitive operations | `auth/keyring_auth.py:160-165` | Low |

### 5.2 Database Layer

| # | Enhancement | File | Severity |
|---|-------------|------|----------|
| 1 | Implement MongoClient connection pooling (see PERF-1) | `database/user_service.py`, `database/settings_service.py` | Critical |
| 2 | Add connection health checks and auto-reconnect | `database/user_service.py` | Medium |
| 3 | Add database operation timeout configuration | `database/user_service.py:14` | Medium |
| 4 | Add input validation/sanitization for MongoDB queries | `database/user_service.py`, `database/settings_service.py` | Medium |

### 5.3 Dashboard & UI/UX

| # | Enhancement | File | Severity |
|---|-------------|------|----------|
| 1 | Fix widget accumulation in QStackedWidget (see PERF-7) | `main.py:36-38, 42-48` | High |
| 2 | Replace blocking OAuth with async QThread (see PERF-10) | `ui/views/dashboard.py:627` | High |
| 3 | Add adaptive polling for event bus (see PERF-3) | `ui/views/dashboard.py:143` | Medium |
| 4 | Optimize `_refresh_dashboard()` to update only changed widgets (see PERF-6) | `ui/views/dashboard.py:212-236` | Medium |
| 5 | Add backend activity log panel (show commands, responses, errors) | `ui/views/dashboard.py` | Medium |
| 6 | Add system tray integration (minimize to tray, notifications) | `main.py` | Low |
| 7 | Make window resizable (currently fixed at 1024x768) | `main.py:72` | Low |

### 5.4 Services (OAuth, Spotify, Meet)

| # | Enhancement | File | Severity |
|---|-------------|------|----------|
| 1 | Add CSRF `state` parameter to Spotify OAuth (see SEC-3) | `services/spotify_service.py` | High |
| 2 | Fix thread safety in Spotify callback (race condition) | `services/spotify_service.py:60-62, 183` | High |
| 3 | Remove traceback from user-facing errors in meet_service | `services/meet_service.py:81-83` | High |
| 4 | Add OAuth token refresh retry with exponential backoff | `services/meet_service.py` | Medium |
| 5 | Close `TokenStore` MongoClient on application shutdown | `services/token_store.py:188-192` | Medium |

### 5.5 Settings Page

| # | Enhancement | File | Severity |
|---|-------------|------|----------|
| 1 | Fix new MongoClient per settings operation (see PERF-1) | `database/settings_service.py:23, 46` | Critical |
| 2 | Add LLM provider selection UI (Azure/Ollama/OpenAI) | `ui/views/settings_page.py` | Medium |
| 3 | Add wake word sensitivity slider | `ui/views/settings_page.py` | Low |
| 4 | Add TTS voice selection | `ui/views/settings_page.py` | Low |

---

## 6. INTEGRATION LAYER ENHANCEMENTS

### 6.1 Event Bus / Communication

| # | Enhancement | File | Severity |
|---|-------------|------|----------|
| 1 | Add thread lock to singleton creation (race condition) | `integration/communication.py:54-58` | High |
| 2 | Add queue size limits to prevent memory exhaustion | `integration/communication.py:64-65` | Medium |
| 3 | Replace bare `except:` blocks with specific exception handling | `integration/communication.py:80-81, 86-88, 95-96` | Medium |
| 4 | Replace polling with condition-variable event notification | `integration/communication.py` | Medium |

### 6.2 Launcher & Shutdown

| # | Enhancement | File | Severity |
|---|-------------|------|----------|
| 1 | Add graceful shutdown timeout (force-kill if backend doesn't stop) | `launcher.py` | Medium |
| 2 | Add crash recovery — restart backend thread if it dies | `launcher.py` | Medium |
| 3 | Handle `ImportError` for PyQt5 with clear error message | `launcher.py` | Low |

### 6.3 Thread Safety

| # | Enhancement | File | Severity |
|---|-------------|------|----------|
| 1 | Add lock to `BackendRunner.running` flag | `integration/backend_runner.py:74, 239` | Medium |
| 2 | Remove global `sys.stdout` replacement (affects all threads) | `integration/backend_runner.py:121-122` | High |

---

## 7. NEW AGENTS & TOOLS

### 7.1 Email Agent
- **Purpose:** Gmail API integration for send, read, draft, schedule emails
- **Tools:** `send_email`, `read_inbox`, `search_emails`, `draft_email`, `schedule_email`
- **Priority:** High (high-value daily use)
- **Dependencies:** Google API credentials (reuse existing OAuth infrastructure)

### 7.2 File Management Agent
- **Purpose:** Browse, read, create, search files on the local system
- **Tools:** `list_directory`, `read_file`, `create_file`, `search_files`, `open_file`
- **Priority:** Medium
- **Security:** Sandbox file access to user directories only

### 7.3 Notes/Knowledge Agent
- **Purpose:** MongoDB-backed persistent notes and knowledge base
- **Tools:** `create_note`, `search_notes`, `list_notes`, `delete_note`, `tag_note`
- **Priority:** Medium
- **Dependencies:** MongoDB (already available)

### 7.4 Code Execution Agent (sandboxed)
- **Purpose:** Execute Python/shell snippets in a sandboxed environment
- **Tools:** `run_python`, `run_shell`, `install_package`
- **Priority:** Low (security complexity)
- **Security:** Use `subprocess` with timeout, restricted permissions, no network access

### 7.5 Web Automation Agent
- **Purpose:** Playwright-based form filling, clicking, scraping for complex web tasks
- **Tools:** `fill_form`, `click_element`, `extract_data`, `navigate_to`, `take_web_screenshot`
- **Priority:** Medium
- **Dependencies:** Playwright (already installed)

### 7.6 New Tools for Existing Agents

**Browser Agent — New Tools:**
| Tool | Description | Priority |
|------|-------------|----------|
| `get_stock_price` | Real-time stock quotes | Medium |
| `search_reddit` | Reddit search and post reading | Low |
| `search_arxiv` | Academic paper search | Low |
| `search_wikipedia` | Wikipedia article summaries | Medium |
| `get_flight_prices` | Flight price lookup | Low |
| `search_recipes` | Recipe search with ingredients | Low |

**Music Agent — New Tools:**
| Tool | Description | Priority |
|------|-------------|----------|
| `search_podcasts` | Podcast search and playback | Medium |
| `play_karaoke` | Karaoke mode (lyrics display) | Low |
| `play_mood_radio` | Continuous mood-based radio | Low |
| `search_concerts` | Concert/event search | Low |

**System Agent — New Tools:**
| Tool | Description | Priority |
|------|-------------|----------|
| `get_network_status` | Network connection details | Medium |
| `get_battery_info` | Battery status and estimated time | Medium |
| `get_disk_usage` | Disk space information | Low |
| `list_processes_detailed` | Detailed process list with CPU/memory | Low |

**Productivity Agent — New Tools:**
| Tool | Description | Priority |
|------|-------------|----------|
| `start_pomodoro` | Pomodoro timer (25/5 cycles) | Medium |
| `enable_focus_mode` | Mute notifications, block distractions | Medium |
| `daily_standup` | Generate daily standup summary from memory | Low |
| `track_habit` | Simple habit tracking | Low |

---

## 8. ARCHITECTURE IMPROVEMENTS

### 8.1 Replace polling with condition-variable event bus ✅ COMPLETED
- **Current:** Frontend polls `comm_bus.get_frontend_message()` every 100ms via QTimer.
- **Proposed:** Use `threading.Condition` or `threading.Event` in the communication bus. Frontend listens on a `QThread` that blocks until notified.
- **Impact:** Eliminates 36K/hour unnecessary polls; instant event delivery.
- **Effort:** Medium
- **Resolution:** Implemented `QtEventBridge(QObject)` with `pyqtSignal` in `event_bus.py`. Dashboard receives events instantly via signal/slot — zero polling, zero CPU when idle. QTimer kept as fallback only.

### 8.2 Structured logging (replace all `print()`) ✅ COMPLETED
- **Current:** 100+ `print()` statements scattered across all files.
- **Proposed:** Use Python `logging` module with structured formatters. Add log levels (DEBUG, INFO, WARNING, ERROR). Support log file output.
- **Impact:** Debuggable, filterable logs; proper severity levels.
- **Effort:** Medium (systematic but straightforward)
- **Resolution:** Created `src/utils/log_config.py` with `configure_logging()` and `get_logger()`. Migrated ~220 print() calls across 28+ files to structured logging with appropriate levels.

### 8.3 Dependency injection ✅ COMPLETED
- **Current:** Singletons created via global functions (`get_agent_memory()`, `get_llm_config()`, `get_tts_instance()`).
- **Proposed:** Create a central `AppContext` or service container that initializes and provides dependencies. Easier testing and configuration.
- **Impact:** Testability, configuration flexibility.
- **Effort:** High
- **Resolution:** Created `src/utils/container.py` with `ServiceContainer` (thread-safe lazy properties for `llm_config`, `agent_memory`, `tts`, `event_bus`, `shutdown_event`). Existing singleton functions delegate to container. Orchestrator and backend runner use container for DI.

### 8.4 Centralized configuration management ✅ COMPLETED
- **Current:** `.env` files loaded independently in multiple modules (`graph_builder.py`, `llm_config.py`, `music_tools.py`, `browser_tools.py`).
- **Proposed:** Single config loader that validates all required variables at startup. Fail fast with clear error messages.
- **Impact:** No more runtime crashes from missing env vars.
- **Effort:** Medium
- **Resolution:** `LLMConfig` in `llm_config.py` validates all providers at startup with `_validate_config()`. Fail-fast with clear error messages for missing credentials. Accessed via `ServiceContainer` singleton.

### 8.5 Plugin-based agent registration ✅ COMPLETED
- **Current:** Agents hardcoded in `graph_builder.py` with manual wiring.
- **Proposed:** Agent registry that auto-discovers agents from a `plugins/` directory. Each agent defines its tools, prompt, and LLM requirements via a standard interface.
- **Impact:** Easy to add/remove agents without modifying core graph code.
- **Effort:** High
- **Resolution:** Created `src/graph/agent_registry.py` with `AgentDefinition` dataclass and `AGENT_REGISTRY` list. `graph_builder.py` auto-constructs nodes, edges, supervisor prompt, and router from registry. Adding an agent = one registry entry.

### 8.6 Async tool execution with `asyncio` ✅ COMPLETED
- **Current:** All tools are synchronous, blocking the agent thread.
- **Proposed:** Convert HTTP-based tools to async using `aiohttp`. LangGraph supports async agents via `create_react_agent` with async tools.
- **Impact:** 2-5x faster agent responses for IO-bound tools.
- **Effort:** High
- **Resolution:** All browser tools converted to async with `httpx.AsyncClient`. Agent nodes use `async def agent_node()` with `asyncio.wait_for(ainvoke())`. Router uses `graph.astream()` via `asyncio.run()`.

### 8.7 Per-agent LLM temperature configuration ✅ COMPLETED
- **Current:** Single global temperature for all agents.
- **Proposed:** Per-agent temperature via env vars or settings (e.g., Supervisor=0 for deterministic routing, Music=0.7 for creative responses).
- **Impact:** Better agent behavior tuning.
- **Effort:** Low
- **Resolution:** `LLMConfig` supports `LLM_AGENT_<NAME>_TEMPERATURE` env vars with per-agent caching. Falls back to global `LLM_TEMPERATURE`.

### 8.8 Graceful shutdown with `threading.Event` ✅ COMPLETED
- **Current:** Shutdown relies on daemon threads and `sys.exit()`.
- **Proposed:** Use `threading.Event` for cooperative shutdown. All threads check `shutdown_event.is_set()` in their loops.
- **Impact:** Clean resource cleanup, no orphaned processes.
- **Effort:** Medium
- **Resolution:** `orchestrator.py` accepts `shutdown_event` parameter, checks it in main loop. `wake_word_listener.py` supports `timeout` parameter. `backend_runner_v2.py` creates and passes `threading.Event`. Backend thread exits within ~1s of shutdown signal.

---

## 9. DEVOPS & QUALITY

### 9.1 Testing Infrastructure
- **Current State:** Zero test files. No `tests/` directory.
- **Proposed:**
  - Create `tests/` with `test_backend/`, `test_frontend/`, `test_integration/`
  - Add `pytest` and `pytest-asyncio` to dependencies
  - Write unit tests for: tool functions, agent routing, memory service, auth
  - Write integration tests for: graph execution, OAuth flows, event bus
  - Target: 60% coverage in Phase 1, 80% in Phase 2
- **Priority:** High

### 9.2 CI/CD Pipeline
- **Current State:** No GitHub Actions or any CI.
- **Proposed:**
  - GitHub Actions workflow for: lint, type check, test on push/PR
  - Separate jobs for backend and frontend
  - Environment secrets for API keys in CI
  - Automated release tagging
- **Priority:** High

### 9.3 Docker Support
- **Current State:** No containerization.
- **Proposed:**
  - `Dockerfile` for backend (headless mode without voice)
  - `docker-compose.yml` for backend + MongoDB
  - Frontend remains desktop app (not containerized)
- **Priority:** Low

### 9.4 Linting & Type Checking
- **Current State:** No linting, no type checking, no formatter.
- **Proposed:**
  - Add `ruff` (fast Python linter/formatter) or `black` + `flake8`
  - Add `mypy` for gradual type checking
  - Add `pre-commit` hooks for automated enforcement
  - Configuration in `pyproject.toml` (already exists)
- **Priority:** Medium

---

## 10. PRIORITIZED ROADMAP

### Phase 1: Stability & Security (1-2 weeks)
> Fix critical bugs and security vulnerabilities. Establish quality baseline.

| # | Item | Type | Effort |
|---|------|------|--------|
| 1 | Fix supervisor routing logic (BUG-1) | Bug Fix | 5 min |
| 2 | Fix path traversal in download_file (BUG-7/SEC-4) | Security | 15 min |
| 3 | Fix memory session cleanup on crash (BUG-2) | Bug Fix | 30 min |
| 4 | Replace SHA-256 with bcrypt in keyring_auth (SEC-1/SEC-2) | Security | 1 hr |
| 5 | Remove tracebacks from user-facing errors (SEC-5) | Security | 1 hr |
| 6 | Implement MongoClient connection pooling (PERF-1) | Performance | 2 hr |
| 7 | Add thread locks to global state (BUG-5, BUG-6) | Bug Fix | 1 hr |
| 8 | Add LLM provider validation on startup (BUG-8) | Bug Fix | 30 min |
| 9 | Fix command injection in open_application | Security | 30 min |
| 10 | Add `pytest` infrastructure + first tests | DevOps | 3 hr |

### Phase 2: Performance & UX (2-4 weeks)
> Optimize performance bottlenecks and improve user experience.

| # | Item | Type | Effort |
|---|------|------|--------|
| 1 | Non-blocking TTS (PERF-2) | Performance | 2 hr |
| 2 | Adaptive event bus polling (PERF-3) | Performance | 1 hr |
| 3 | Fix QStackedWidget widget accumulation (PERF-7) | Bug Fix | 2 hr |
| 4 | Replace blocking OAuth with QThread (PERF-10) | Performance | 3 hr |
| 5 | Add structured logging (replace print) | Architecture | 4 hr |
| 6 | Add CSRF state to OAuth flows (SEC-3) | Security | 1 hr |
| 7 | Add rate limiting on auth attempts (SEC-6) | Security | 1 hr |
| 8 | Add agent execution timeout | Enhancement | 1 hr |
| 9 | Register atexit cleanup for Playwright (PERF-8) | Bug Fix | 15 min |
| 10 | Add CI/CD pipeline (GitHub Actions) | DevOps | 3 hr |
| 11 | Add linting with ruff + pre-commit hooks | DevOps | 2 hr |
| 12 | Fix Spotify device selection logic (BUG-4) | Bug Fix | 1 hr |

### Phase 3: Features & Architecture (4-8 weeks)
> Add new capabilities and improve architecture.

| # | Item | Type | Effort |
|---|------|------|--------|
| 1 | Email Agent (Gmail integration) | New Feature | 1 week |
| 2 | Notes/Knowledge Agent | New Feature | 3 days |
| 3 | Plugin-based agent registration | Architecture | 1 week |
| 4 | Async tool execution | Architecture | 1 week |
| 5 | Condition-variable event bus | Architecture | 2 days |
| 6 | Centralized config management | Architecture | 2 days |
| 7 | Per-agent LLM temperature config | Enhancement | 2 hr |
| 8 | Settings page: LLM provider selection | Enhancement | 1 day |
| 9 | Long-term user preference memory | Enhancement | 2 days |
| 10 | Web Automation Agent | New Feature | 1 week |
| 11 | New browser tools (stocks, Wikipedia) | Enhancement | 2 days |
| 12 | New productivity tools (Pomodoro, focus mode) | Enhancement | 1 day |
| 13 | System tray integration | Enhancement | 1 day |
| 14 | 80% test coverage | DevOps | Ongoing |

---

## Appendix: File Index

| File | Issues | Section(s) |
|------|--------|------------|
| `Sentinel-AI-Backend/src/graph/graph_builder.py` | BUG-1, BUG-3, PERF-5 | 1, 4.2 |
| `Sentinel-AI-Backend/src/utils/orchestrator.py` | BUG-2, PERF-2 | 1, 4.1 |
| `Sentinel-AI-Backend/src/utils/llm_config.py` | BUG-8, PERF-9 | 1, 4.3 |
| `Sentinel-AI-Backend/src/utils/agent_memory.py` | PERF-5 | 4.4 |
| `Sentinel-AI-Backend/src/utils/text_to_speech.py` | PERF-2 | 3 |
| `Sentinel-AI-Backend/src/tools/browser_tools.py` | BUG-7, SEC-4 | 1, 2, 4.5 |
| `Sentinel-AI-Backend/src/tools/music_tools.py` | BUG-4, PERF-11 | 1, 3, 4.5 |
| `Sentinel-AI-Backend/src/tools/playwright_music_tools.py` | BUG-5, PERF-8, PERF-12 | 1, 3, 4.5 |
| `Sentinel-AI-Backend/src/tools/productivity_tools.py` | BUG-6 | 1, 4.5 |
| `Sentinel-AI-Backend/src/tools/meeting_tools.py` | SEC-5 | 2, 4.5 |
| `Sentinel-AI-Backend/src/tools/system_tools.py` | PERF-12 | 3, 4.5 |
| `Sentinel-AI-Frontend/auth/keyring_auth.py` | SEC-1, SEC-2 | 2, 5.1 |
| `Sentinel-AI-Frontend/database/user_service.py` | PERF-1, SEC-2 | 3, 5.2 |
| `Sentinel-AI-Frontend/database/settings_service.py` | PERF-1 | 3, 5.5 |
| `Sentinel-AI-Frontend/ui/views/dashboard.py` | PERF-3, PERF-6, PERF-7, PERF-10 | 3, 5.3 |
| `Sentinel-AI-Frontend/main.py` | PERF-7 | 3, 5.3 |
| `Sentinel-AI-Frontend/services/meet_service.py` | SEC-5, SEC-7 | 2, 5.4 |
| `Sentinel-AI-Frontend/services/token_store.py` | SEC-7 | 2, 5.4 |
| `Sentinel-AI-Frontend/services/spotify_service.py` | SEC-3, SEC-6 | 2, 5.4 |
| `integration/communication.py` | PERF-3 | 3, 6.1 |
| `integration/backend_runner.py` | — | 6.3 |
| `integration/frontend_enhancer.py` | — | 6.3 |
| `launcher.py` | — | 6.2 |
