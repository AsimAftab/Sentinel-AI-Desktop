#!/usr/bin/env python
"""
Sentinel AI Unified Launcher

This script launches both the backend voice assistant and frontend dashboard
from a single command with proper thread management and lifecycle control.

Usage:
    python launcher.py

The launcher will:
- Run the PyQt5 frontend on the main thread (Qt requirement)
- Run the backend voice assistant on a child thread
- Use event-based communication (NO monkey patching!)
- Monitor both components and handle graceful shutdown
- Display backend status in the frontend dashboard via EventBus
"""

import sys
import os
import signal
import atexit
from pathlib import Path

# Add integration module to path
sys.path.insert(0, str(Path(__file__).parent))

from integration.backend_runner_v2 import BackendRunner
from integration.event_bus import EventBus


class SentinelLauncher:
    """Main launcher class for Sentinel AI."""

    def __init__(self):
        self.backend_runner = None
        self.event_bus = EventBus()
        self.app = None
        self.shutting_down = False

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            print("\nReceived shutdown signal, cleaning up...")
            self.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def start_backend(self):
        """Start the backend voice assistant in a separate thread."""
        print("Starting backend voice assistant...")
        self.backend_runner = BackendRunner()
        self.backend_runner.start()
        print("Backend thread started")

    def start_frontend(self):
        """Start the frontend dashboard on the main thread."""
        print("Starting frontend dashboard...")

        # Add frontend to path
        frontend_path = Path(__file__).parent / "Sentinel-AI-Frontend"
        sys.path.insert(0, str(frontend_path))

        # No need for frontend enhancement - event system works directly!
        print("✅ Event-based communication active (no monkey patching)")

        # Import PyQt5 and frontend main
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtGui import QIcon

        # Create QApplication
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Sentinel AI")

        # Load frontend stylesheet
        try:
            style_path = frontend_path / "ui" / "qss" / "style.qss"
            with open(style_path, "r") as file:
                style = file.read()
                self.app.setStyleSheet(style)
        except FileNotFoundError:
            print("⚠️  Warning: style.qss not found. Running without styles.")
        except Exception as e:
            print(f"⚠️  Error loading stylesheet: {e}")

        # Import the MainApp class from frontend
        # We need to import this way to use the existing implementation
        import importlib.util
        spec = importlib.util.spec_from_file_location("frontend_main", frontend_path / "main.py")
        frontend_main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(frontend_main)

        # Create the main window using the frontend's MainApp class
        window = frontend_main.MainApp()
        window.setWindowTitle("Sentinel AI")
        window.setMinimumSize(800, 600)
        window.resize(1400, 1200)

        # Try to set icon
        try:
            icon_path = frontend_path / "assets" / "icon.png"
            if icon_path.exists():
                window.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            print("⚠️  Could not load icon:", e)

        # Center window on screen
        try:
            screen = self.app.primaryScreen().availableGeometry()
            x = (screen.width() - window.width()) // 2
            y = (screen.height() - window.height()) // 2
            window.move(x, y)
        except:
            pass

        # Override close event to shutdown backend
        original_close_event = window.closeEvent

        def enhanced_close_event(event):
            print("Frontend window closing, shutting down backend...")
            self.shutdown()
            if original_close_event:
                original_close_event(event)

        window.closeEvent = enhanced_close_event

        # Show window
        window.show()

        print("Frontend started")
        print("\n" + "="*60)
        print("Sentinel AI is now running!")
        print("="*60)
        print("Frontend: Dashboard UI")
        print("Backend: Voice Assistant")
        print("\nTo exit: Close the window or press Ctrl+C")
        print("="*60 + "\n")

        # Start Qt event loop (blocks until window is closed)
        exit_code = self.app.exec_()

        # Cleanup after event loop exits
        self.shutdown()
        return exit_code

    def shutdown(self):
        """Gracefully shutdown both frontend and backend."""
        if self.shutting_down:
            return

        self.shutting_down = True
        print("\nShutting down Sentinel AI...")

        # Stop backend
        if self.backend_runner and self.backend_runner.is_alive():
            print("Stopping backend voice assistant...")
            self.backend_runner.stop()
            self.backend_runner.join(timeout=5)

            if self.backend_runner.is_alive():
                print("Warning: Backend did not stop gracefully")

        # Clear event bus
        self.event_bus.clear()

        print("Shutdown complete")

    def run(self):
        """Main entry point - starts both components."""
        try:
            # Setup signal handlers
            self.setup_signal_handlers()

            # Register cleanup on exit
            atexit.register(self.shutdown)

            # Start backend in thread
            self.start_backend()

            # Start frontend on main thread (this blocks until window closes)
            exit_code = self.start_frontend()

            return exit_code

        except Exception as e:
            print(f"Fatal error: {e}")
            import traceback
            traceback.print_exc()
            self.shutdown()
            return 1


def main():
    """Entry point for the launcher."""
    # Check that we're in the right directory
    if not (Path("Sentinel-AI-Backend").exists() and Path("Sentinel-AI-Frontend").exists()):
        print("Error: launcher.py must be run from the project root directory")
        print("Expected directory structure:")
        print("  - Sentinel-AI-Backend/")
        print("  - Sentinel-AI-Frontend/")
        print("  - launcher.py")
        sys.exit(1)

    # Create and run launcher
    launcher = SentinelLauncher()
    exit_code = launcher.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
