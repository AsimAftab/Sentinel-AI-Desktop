"""
Backend thread runner - executes backend using event-based communication.
NO MONKEY PATCHING - Backend emits events directly.
"""

import sys
import os
import threading
import traceback
import logging
from pathlib import Path
from .event_bus import EventBus, EventType, BackendStatus


class LogStreamHandler(logging.Handler):
    """Custom logging handler that streams logs to frontend via EventBus."""

    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self.setLevel(logging.DEBUG)

    def emit(self, record):
        try:
            log_entry = self.format(record)
            self.event_bus.emit(EventType.LOG_MESSAGE, data=log_entry)
        except Exception:
            self.handleError(record)


class StdoutCapture:
    """Captures stdout/stderr and sends to frontend via EventBus."""

    def __init__(self, original_stream, event_bus):
        self.original_stream = original_stream
        self.event_bus = event_bus

    def write(self, text):
        # Write to original stream (console)
        if self.original_stream:
            self.original_stream.write(text)
            self.original_stream.flush()

        # Send to frontend if not empty/whitespace
        if text.strip():
            self.event_bus.emit(EventType.LOG_MESSAGE, data=text.rstrip())

    def flush(self):
        if self.original_stream:
            self.original_stream.flush()


class BackendRunner:
    """
    Manages backend execution in a separate thread.
    Uses event-based communication - NO MONKEY PATCHING.
    """

    def __init__(self):
        self.thread = None
        self.event_bus = EventBus()
        self.running = False
        self.backend_path = None

    def start(self):
        """Start backend in a separate thread."""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_backend, daemon=True, name="SentinelBackend")
        self.thread.start()

    def _run_backend(self):
        """Execute backend code in thread."""
        try:
            # Notify frontend that backend is starting
            self.event_bus.emit(
                EventType.BACKEND_STARTING,
                status=BackendStatus.STARTING
            )

            # Add backend to path
            self.backend_path = Path(__file__).parent.parent / "Sentinel-AI-Backend"
            if str(self.backend_path) not in sys.path:
                sys.path.insert(0, str(self.backend_path))

            # Add project root to path so backend can import integration package
            project_root = Path(__file__).parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))

            # Also add integration folder directly for fallback imports
            integration_path = Path(__file__).parent
            if str(integration_path) not in sys.path:
                sys.path.insert(0, str(integration_path))

            # Import dotenv first
            from dotenv import load_dotenv

            # Load .env from backend directory BEFORE changing directory
            env_file = self.backend_path / ".env"
            print(f"Loading .env from: {env_file}")
            load_dotenv(dotenv_path=env_file)

            # Verify TAVILY_API_KEY
            tavily_key = os.getenv("TAVILY_API_KEY")
            if not tavily_key:
                error_msg = f"TAVILY_API_KEY not found in {env_file}"
                print(f"ERROR: {error_msg}")
                raise RuntimeError(error_msg)

            print(f"[OK] TAVILY_API_KEY loaded successfully")

            # Change to backend directory (needed for other file references)
            original_cwd = os.getcwd()
            os.chdir(self.backend_path)

            # Setup log streaming to frontend
            log_handler = LogStreamHandler(self.event_bus)
            log_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            ))
            logging.getLogger().addHandler(log_handler)

            # Capture stdout and stderr (print statements)
            sys.stdout = StdoutCapture(sys.stdout, self.event_bus)
            sys.stderr = StdoutCapture(sys.stderr, self.event_bus)

            print(f"[OK] Event-based communication initialized (no monkey patching!)")

            # Import the orchestrator
            from src.utils.orchestrator import run_sentinel_agent  # type: ignore

            # Notify ready
            self.event_bus.emit(
                EventType.BACKEND_READY,
                status=BackendStatus.READY
            )

            # Execute backend orchestrator (this will block until stopped)
            # The orchestrator now emits events directly
            run_sentinel_agent()

        except Exception as e:
            error_msg = f"Backend error: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)  # Print to console for debugging
            self.event_bus.emit(
                EventType.BACKEND_ERROR,
                status=BackendStatus.ERROR,
                error=error_msg
            )
        finally:
            # Restore original directory
            try:
                os.chdir(original_cwd)
            except:
                pass

            self.running = False
            self.event_bus.emit(
                EventType.BACKEND_STOPPED,
                status=BackendStatus.STOPPED
            )

    def stop(self):
        """Request backend shutdown."""
        self.running = False
        self.event_bus.emit(
            EventType.BACKEND_STOPPED,
            status=BackendStatus.STOPPED
        )

    def is_alive(self):
        """Check if backend thread is alive."""
        return self.thread and self.thread.is_alive()

    def join(self, timeout=None):
        """Wait for backend thread to finish."""
        if self.thread:
            self.thread.join(timeout)
