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
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Add integration module to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
    from PyQt5.QtGui import QIcon
    from PyQt5.QtCore import QTimer
except ImportError:
    print(
        "ERROR: PyQt5 is not installed. Install with: pip install PyQt5",
        file=sys.stderr,
    )
    sys.exit(1)

from integration.backend_runner_v2 import BackendRunner
from integration.event_bus import EventBus


class SentinelLauncher:
    """Main launcher class for Sentinel AI."""

    def __init__(self):
        self.backend_runner = None
        self.event_bus = EventBus()
        self.app = None
        self.window = None
        self.tray_icon = None
        self.health_timer = None
        self.shutting_down = False

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            logger.info("Received shutdown signal, cleaning up...")
            self.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def start_backend(self):
        """Start the backend voice assistant in a separate thread."""
        logger.info("Starting backend voice assistant...")
        self.backend_runner = BackendRunner()
        self.backend_runner.start()
        logger.info("Backend thread started")

    def _setup_tray_icon(self, icon_path):
        """Setup system tray icon with context menu."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.info("System tray not available on this platform")
            return

        icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        self.tray_icon = QSystemTrayIcon(icon, self.app)
        self.tray_icon.setToolTip("Sentinel AI")

        # Context menu
        tray_menu = QMenu()
        show_action = QAction("Show", tray_menu)
        show_action.triggered.connect(self._show_window)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", tray_menu)
        quit_action.triggered.connect(self._quit_from_tray)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        """Handle tray icon double-click to show window."""
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_window()

    def _show_window(self):
        """Restore the main window from tray."""
        if self.window:
            self.window.showNormal()
            self.window.activateWindow()

    def _quit_from_tray(self):
        """Quit the application from tray menu."""
        self.shutdown()
        if self.app:
            self.app.quit()

    def _start_health_check(self):
        """Start a QTimer that checks backend health every 10 seconds."""
        self.health_timer = QTimer()
        self.health_timer.timeout.connect(self._check_backend_health)
        self.health_timer.start(10000)  # 10 seconds

    def _check_backend_health(self):
        """Check if backend thread is alive; restart if crashed."""
        if self.shutting_down:
            return
        if self.backend_runner and not self.backend_runner.is_alive():
            logger.warning("Backend thread died unexpectedly — restarting...")
            try:
                self.backend_runner = BackendRunner()
                self.backend_runner.start()
                logger.info("Backend restarted successfully")
            except Exception as e:
                logger.error("Failed to restart backend: %s", e)

    def start_frontend(self):
        """Start the frontend dashboard on the main thread."""
        logger.info("Starting frontend dashboard...")

        # Add frontend to path
        frontend_path = Path(__file__).parent / "Sentinel-AI-Frontend"
        sys.path.insert(0, str(frontend_path))

        # No need for frontend enhancement - event system works directly!
        logger.info("Event-based communication active")

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
            logger.warning("style.qss not found. Running without styles.")
        except Exception as e:
            logger.warning("Error loading stylesheet: %s", e)

        # Import the MainApp class from frontend
        # We need to import this way to use the existing implementation
        import importlib.util

        spec = importlib.util.spec_from_file_location("frontend_main", frontend_path / "main.py")
        frontend_main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(frontend_main)

        # Create the main window using the frontend's MainApp class
        self.window = frontend_main.MainApp()
        self.window.setWindowTitle("Sentinel AI")
        self.window.setMinimumSize(800, 600)
        self.window.resize(1400, 1200)

        # Try to set icon
        icon_path = frontend_path / "assets" / "icon.png"
        try:
            if icon_path.exists():
                self.window.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            logger.warning("Could not load icon: %s", e)

        # Center window on screen
        try:
            screen = self.app.primaryScreen().availableGeometry()
            x = (screen.width() - self.window.width()) // 2
            y = (screen.height() - self.window.height()) // 2
            self.window.move(x, y)
        except Exception:
            pass

        # Setup system tray icon
        self._setup_tray_icon(icon_path)

        # Override close event to minimize to tray (or shutdown if no tray)
        original_close_event = self.window.closeEvent

        def enhanced_close_event(event):
            if self.tray_icon and self.tray_icon.isVisible():
                # Minimize to tray instead of closing
                event.ignore()
                self.window.hide()
                self.tray_icon.showMessage(
                    "Sentinel AI",
                    "Application minimized to tray. Double-click to restore.",
                    QSystemTrayIcon.Information,
                    2000,
                )
            else:
                logger.info("Frontend window closing, shutting down backend...")
                self.shutdown()
                if original_close_event:
                    original_close_event(event)

        self.window.closeEvent = enhanced_close_event

        # Start backend health check timer
        self._start_health_check()

        # Show window
        self.window.show()

        logger.info("Frontend started")
        logger.info("Sentinel AI is now running!")
        logger.info("Frontend: Dashboard UI")
        logger.info("Backend: Voice Assistant")
        logger.info("To exit: Use tray icon > Quit, or press Ctrl+C")

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
        logger.info("Shutting down Sentinel AI...")

        # Stop health check timer
        if self.health_timer:
            self.health_timer.stop()
            self.health_timer = None

        # Hide tray icon
        if self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon = None

        # Stop backend
        if self.backend_runner and self.backend_runner.is_alive():
            logger.info("Stopping backend voice assistant...")
            self.backend_runner.stop()
            self.backend_runner.join(timeout=5)

            if self.backend_runner.is_alive():
                logger.warning("Backend did not stop gracefully")

        # Close MongoDB connection
        try:
            from config.database_config import DatabaseConfig
            DatabaseConfig.close()
            logger.info("MongoDB connection closed")
        except Exception:
            pass

        # Clear event bus
        self.event_bus.clear()

        logger.info("Shutdown complete")

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
            logger.critical("Fatal error: %s", e)
            logger.exception("Traceback:")
            self.shutdown()
            return 1


def main():
    """Entry point for the launcher."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    # Check that we're in the right directory
    if not (Path("Sentinel-AI-Backend").exists() and Path("Sentinel-AI-Frontend").exists()):
        logger.error("launcher.py must be run from the project root directory")
        logger.error("Expected directory structure: Sentinel-AI-Backend/, Sentinel-AI-Frontend/, launcher.py")
        sys.exit(1)

    # Create and run launcher
    launcher = SentinelLauncher()
    exit_code = launcher.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
