"""
Backend thread runner - executes backend in a separate thread without modifying its code.
"""

import sys
import os
import threading
import traceback
import logging
from pathlib import Path
from .communication import CommunicationBus, Message, MessageType, BackendStatus


# Store original working directory
_original_cwd = os.getcwd()


class LogStreamHandler(logging.Handler):
    """Custom logging handler that streams logs to frontend via CommunicationBus."""
    
    def __init__(self, comm_bus):
        super().__init__()
        self.comm_bus = comm_bus
        self.setLevel(logging.DEBUG)
        
    def emit(self, record):
        try:
            log_entry = self.format(record)
            self.comm_bus.send_to_frontend(
                Message(MessageType.LOG, data=log_entry)
            )
        except Exception:
            self.handleError(record)


class StdoutCapture:
    """Captures stdout/stderr and sends to frontend via CommunicationBus."""
    
    def __init__(self, original_stream, comm_bus):
        self.original_stream = original_stream
        self.comm_bus = comm_bus
        
    def write(self, text):
        # Write to original stream (console)
        if self.original_stream:
            self.original_stream.write(text)
            self.original_stream.flush()
        
        # Send to frontend if not empty/whitespace
        if text.strip():
            self.comm_bus.send_to_frontend(
                Message(MessageType.LOG, data=text.rstrip())
            )
    
    def flush(self):
        if self.original_stream:
            self.original_stream.flush()


class BackendRunner:
    """Manages backend execution in a separate thread."""

    def __init__(self):
        self.thread = None
        self.comm_bus = CommunicationBus()
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
            self.comm_bus.send_to_frontend(
                Message(MessageType.STATUS_UPDATE, status=BackendStatus.STARTING)
            )

            # Add backend to path
            self.backend_path = Path(__file__).parent.parent / "Sentinel-AI-Backend"
            sys.path.insert(0, str(self.backend_path))

            # Import dotenv first
            from dotenv import load_dotenv

            # Load .env from backend directory BEFORE changing directory
            env_file = self.backend_path / ".env"
            print(f"Loading .env from: {env_file}")
            load_dotenv(dotenv_path=env_file)

            # Verify TAVILY_API_KEY
            tavily_key = os.getenv("TAVILY_API_KEY")
            if not tavily_key:
                print(f"ERROR: TAVILY_API_KEY not found!")
                print(f"Checked .env file at: {env_file}")
                print(f"File exists: {env_file.exists()}")
                raise RuntimeError("TAVILY_API_KEY not found in .env file")

            print(f"[OK] TAVILY_API_KEY loaded successfully")

            # Change to backend directory (needed for other file references)
            original_cwd = os.getcwd()
            os.chdir(self.backend_path)

            # Setup log streaming to frontend
            log_handler = LogStreamHandler(self.comm_bus)
            log_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            ))
            logging.getLogger().addHandler(log_handler)
            
            # Capture stdout and stderr (print statements)
            sys.stdout = StdoutCapture(sys.stdout, self.comm_bus)
            sys.stderr = StdoutCapture(sys.stderr, self.comm_bus)
            
            print(f"[OK] Log streaming to frontend enabled (logging + stdout/stderr)")

            # Import and patch backend modules to inject status updates
            self._patch_backend_modules()

            # Import the orchestrator
            from src.utils.orchestrator import run_sentinel_agent

            # Notify ready
            self.comm_bus.send_to_frontend(
                Message(MessageType.STATUS_UPDATE, status=BackendStatus.READY)
            )

            # Execute backend orchestrator (this will block until stopped)
            run_sentinel_agent()

        except Exception as e:
            error_msg = f"Backend error: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)  # Print to console for debugging
            self.comm_bus.send_to_frontend(
                Message(MessageType.ERROR, status=BackendStatus.ERROR, error=error_msg)
            )
        finally:
            # Restore original directory
            try:
                os.chdir(original_cwd)
            except:
                pass

            self.running = False
            self.comm_bus.send_to_frontend(
                Message(MessageType.STATUS_UPDATE, status=BackendStatus.STOPPED)
            )

    def _patch_backend_modules(self):
        """
        Monkey-patch backend modules to inject status updates.
        This doesn't modify the source files, just the runtime behavior.
        """
        try:
            # Try to import and patch backend modules
            # If imports fail, backend will still run without status updates

            try:
                from src.utils import wake_word_listener

                # Patch wake word listener to send status updates
                if hasattr(wake_word_listener, 'WakeWordListener'):
                    original_wait = wake_word_listener.WakeWordListener.wait_for_wake_word
                    comm_bus = self.comm_bus

                    def patched_wait(self):
                        comm_bus.send_to_frontend(
                            Message(MessageType.STATUS_UPDATE, status=BackendStatus.LISTENING)
                        )
                        result = original_wait(self)
                        if result:
                            comm_bus.send_to_frontend(
                                Message(MessageType.WAKE_WORD_DETECTED, data="Wake word detected")
                            )
                        return result

                    wake_word_listener.WakeWordListener.wait_for_wake_word = patched_wait
                    print("[OK] Patched wake_word_listener")
            except Exception as e:
                print(f"[WARNING] Could not patch wake_word_listener: {e}")

            try:
                from src.utils import speech_recognizer

                if hasattr(speech_recognizer, 'SpeechRecognizer'):
                    original_listen = speech_recognizer.SpeechRecognizer.listen_command
                    comm_bus = self.comm_bus

                    def patched_listen(self, *args, **kwargs):
                        comm_bus.send_to_frontend(
                            Message(MessageType.STATUS_UPDATE, status=BackendStatus.PROCESSING)
                        )
                        result = original_listen(self, *args, **kwargs)
                        if result:
                            comm_bus.send_to_frontend(
                                Message(MessageType.COMMAND_RECEIVED, data=result)
                            )
                        return result

                    speech_recognizer.SpeechRecognizer.listen_command = patched_listen
                    print("[OK] Patched speech_recognizer")
            except Exception as e:
                print(f"[WARNING] Could not patch speech_recognizer: {e}")

            try:
                from src.utils import langgraph_router

                if hasattr(langgraph_router, 'route_to_langgraph'):
                    original_route = langgraph_router.route_to_langgraph
                    comm_bus = self.comm_bus

                    def patched_route(command):
                        response = original_route(command)
                        comm_bus.send_to_frontend(
                            Message(MessageType.RESPONSE_GENERATED, data=response)
                        )
                        return response

                    langgraph_router.route_to_langgraph = patched_route
                    print("[OK] Patched langgraph_router")
            except Exception as e:
                print(f"[WARNING] Could not patch langgraph_router: {e}")

        except Exception as e:
            # If patching fails completely, backend will still run without status updates
            print(f"Warning: Could not patch backend modules: {e}")

    def stop(self):
        """Request backend shutdown."""
        self.running = False
        self.comm_bus.send_to_frontend(
            Message(MessageType.STATUS_UPDATE, status=BackendStatus.STOPPED)
        )

    def is_alive(self):
        """Check if backend thread is alive."""
        return self.thread and self.thread.is_alive()

    def join(self, timeout=None):
        """Wait for backend thread to finish."""
        if self.thread:
            self.thread.join(timeout)
