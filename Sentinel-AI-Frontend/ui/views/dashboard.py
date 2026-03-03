import logging

from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QMessageBox,
    QGridLayout,
    QSizePolicy,
    QScrollArea,
    QProgressDialog,
)
from PyQt5.QtCore import Qt, QSize, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QFont

logger = logging.getLogger(__name__)


class OAuthThread(QThread):
    """Background thread for OAuth service connection — keeps Qt UI responsive."""

    finished = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, service_manager, internal_name):
        super().__init__()
        self.service_manager = service_manager
        self.internal_name = internal_name

    def run(self):
        try:
            future = self.service_manager.connect(self.internal_name)
            success, message = future.result()
            self.finished.emit(success, message)
        except Exception as e:
            self.finished.emit(False, str(e))


import qtawesome as qta
import os
from auth.session_manager import SessionManager
from database.user_service import UserService
from services.service_manager import ServiceManager
from services.token_store import TokenStore
from utils.user_context_writer import UserContextWriter


class DashboardPage(QWidget):
    def __init__(self, main_app=None, username=None):
        super().__init__()

        try:
            self._initialize_dashboard(main_app, username)
        except Exception as e:
            import traceback

            logger.error("Dashboard initialization error", exc_info=True)
            QMessageBox.critical(self, "Dashboard Error", f"Failed to load dashboard:\n\n{str(e)}")
            if main_app:
                main_app.show_login()

    def _initialize_dashboard(self, main_app=None, username=None):
        """Main initialization logic (wrapped for error handling)"""
        self.main_app = main_app
        self.username = username or "User"

        # Check if user is logged in using SessionManager
        if not SessionManager.is_logged_in(self.username):
            QMessageBox.critical(
                self, "Access Denied", "Your session has expired or you're not logged in."
            )
            if self.main_app:
                self.main_app.show_login()
            return

        self.setObjectName("dashboardPage")
        qss_path = os.path.join(os.path.dirname(__file__), "..", "qss", "dashboard.qss")
        try:
            with open(qss_path, "r") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            logger.warning("Failed to load dashboard.qss: %s", e)

        # Fetch user_id from MongoDB
        self.user_id = None
        self.fullname = None
        try:
            user_service = UserService()
            db_user = user_service.get_user_by_username(self.username)
            if db_user and "_id" in db_user:
                self.user_id = str(db_user["_id"])
                self.fullname = db_user.get("fullname", self.username)
                logger.info("Dashboard: Fetched user_id: %s", self.user_id)
        except Exception as e:
            logger.warning("Dashboard: Failed to fetch user_id: %s", e)

        # Initialize service manager, token store, and user context writer
        self.service_manager = ServiceManager()
        self.token_store = TokenStore()
        self.user_context_writer = UserContextWriter()

        # Map service display names to internal service names
        self.service_name_map = {
            "Google Workspace": "GMeet",
            "Zoom": "Zoom",
            "Slack": "Slack",
            "Microsoft Teams": "Teams",
            "YouTube Music": "YouTubeMusic",
            "Spotify": "Spotify",
        }

        # Define services list with metadata (display_name, description, icon)
        # Connection status will be loaded dynamically from MongoDB
        self.service_definitions = [
            ("Google Workspace", "Gmail, Gmeet, Calendar, and more", "fa5b.google"),
            ("Zoom", "Video conferencing and meetings", "fa5s.video"),
            ("Slack", "Team messaging and collaboration", "fa5b.slack"),
            ("Microsoft Teams", "Chat, meetings, and collaboration", "fa5b.microsoft"),
            ("YouTube Music", "Music streaming and playlists", "fa5b.youtube"),
            ("Spotify", "Music and podcast streaming", "fa5b.spotify"),
        ]

        # Load actual service connection status from MongoDB
        self.services = self._load_service_status()

        # Update user_context.json on dashboard load
        self._update_user_context()

        # Backend status tracking
        self.backend_status = "Backend Not Connected"
        self.backend_color = "#6b7280"  # Gray for not connected
        self.event_bus = None  # Initialize to None

        # Try to get backend status from event bus (optional)
        try:
            import sys
            # Calculate integration path relative to project root
            # dashboard.py is at: Sentinel-AI-Frontend/ui/views/dashboard.py
            # integration is at: integration/ (sibling of Sentinel-AI-Frontend)

            # Get the project root (3 levels up from dashboard.py)
            current_file_dir = os.path.dirname(os.path.abspath(__file__))  # .../ui/views
            frontend_dir = os.path.dirname(
                os.path.dirname(current_file_dir)
            )  # .../Sentinel-AI-Frontend
            project_root = os.path.dirname(frontend_dir)  # .../Sentinel-AI-Desktop
            integration_path = os.path.join(project_root, "integration")

            logger.debug("Looking for event_bus.py at: %s", integration_path)

            if os.path.exists(integration_path):
                if integration_path not in sys.path:
                    sys.path.insert(0, integration_path)
                    logger.debug("Added to sys.path: %s", integration_path)

                # Add project root to path for integration package import
                if str(project_root) not in sys.path:
                    sys.path.insert(0, str(project_root))

                # Import from integration package
                try:
                    from integration.event_bus import EventBus, BackendStatus, EventType
                except ImportError:
                    # Fallback: direct import if integration is in sys.path
                    from event_bus import EventBus, BackendStatus, EventType  # type: ignore

                self.event_bus = EventBus()

                # DON'T assume status - wait for backend to report it
                self.backend_status = "Connecting to backend..."
                self.backend_color = "#f59e0b"  # Orange (waiting for status)

                # Prefer zero-latency Qt signal bridge when available
                self._qt_bridge = None
                try:
                    from integration.event_bus import QtEventBridge
                    self._qt_bridge = QtEventBridge()
                    self._qt_bridge.event_received.connect(self._handle_event)
                    self.event_bus.set_qt_bridge(self._qt_bridge)
                    logger.info("Dashboard: Using Qt signal bridge for instant event delivery")
                except (ImportError, Exception) as e:
                    logger.debug("Qt signal bridge unavailable, falling back to polling: %s", e)

                # Fallback QTimer polling (only active if Qt bridge is not available)
                self.backend_status_timer = QTimer()
                self.backend_status_timer.timeout.connect(self.update_backend_status)
                if self._qt_bridge is None:
                    self._idle_poll_count = 0
                    self._max_idle_polls = 20
                    self.backend_status_timer.start(100)
                    QTimer.singleShot(10, self.update_backend_status)

                logger.info(
                    "Dashboard: Connected to backend communication bus - waiting for status..."
                )
            else:
                logger.warning("Integration path not found: %s", integration_path)
                self.comm_bus = None

        except ImportError as e:
            logger.info("Backend communication not available (import error): %s", e, exc_info=True)
            self.comm_bus = None
        except Exception as e:
            logger.warning("Could not connect to backend communication bus: %s", e, exc_info=True)
            self.comm_bus = None

        # Main horizontal layout (sidebar + content)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== LEFT SIDEBAR =====
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)

        # ===== MAIN CONTENT AREA =====
        self._content_area = self.create_content_area()
        main_layout.addWidget(self._content_area)

    def _load_service_status(self):
        """Load actual service connection status from MongoDB."""
        services_with_status = []

        for display_name, description, icon in self.service_definitions:
            # Get internal service name
            internal_name = self.service_name_map.get(display_name, display_name)

            # Check if token exists in MongoDB for this user
            is_connected = False
            if self.user_id:
                try:
                    result = self.token_store.get_token(internal_name, self.user_id)
                    is_connected = result.get("ok", False)
                    if is_connected:
                        logger.info("Service '%s' (%s) is connected", display_name, internal_name)
                except Exception as e:
                    logger.warning("Error checking connection for %s: %s", display_name, e)

            services_with_status.append((display_name, description, icon, is_connected))

        return services_with_status

    def _update_user_context(self):
        """Update user_context.json with current user information."""
        if self.user_id and self.username:
            additional_data = {}
            if self.fullname:
                additional_data["fullname"] = self.fullname
            self.user_context_writer.write_user_context(
                self.user_id, self.username, additional_data
            )

    def _refresh_dashboard(self):
        """Reload service status and refresh only the content area (sidebar unchanged)."""
        logger.info("Refreshing dashboard content...")

        # Reload service status from MongoDB
        self.services = self._load_service_status()

        # Replace only the content area — sidebar is untouched (no flicker, no DB re-queries)
        layout = self.layout()
        old_content = self._content_area
        self._content_area = self.create_content_area()
        layout.addWidget(self._content_area)

        # Schedule old content deletion after Qt processes the layout update
        old_content.deleteLater()

        logger.info("Dashboard content refreshed")

    def create_sidebar(self):
        """Create the left navigation sidebar"""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 24, 16, 24)
        sidebar_layout.setSpacing(24)
        sidebar_layout.setAlignment(Qt.AlignTop)

        # App branding
        app_title = QLabel("Sentinel-AI")
        app_title.setObjectName("appTitle")
        sidebar_layout.addWidget(app_title)

        # Greeting
        greeting = QLabel(f"Hey, {self.fullname}! 👋")
        greeting.setObjectName("greeting")
        sidebar_layout.addWidget(greeting)

        sidebar_layout.addSpacing(20)

        # Navigation menu
        nav_items = [
            ("Dashboard", "fa5s.th-large", True),
            ("Home", "fa5s.home", False),
            ("Settings", "fa5s.cog", False),
        ]

        for label, icon_name, is_active in nav_items:
            btn = self.create_nav_button(label, icon_name, is_active)
            # Connect button click to appropriate handler
            if label == "Settings":
                btn.clicked.connect(self.show_settings)
            elif label == "Home":
                btn.clicked.connect(self.show_home)
            elif label == "Dashboard":
                btn.clicked.connect(self.show_dashboard)
            sidebar_layout.addWidget(btn)

        # Push everything down
        sidebar_layout.addStretch()

        # Logout button (above profile card)
        logout_btn = QPushButton("  Logout")
        logout_btn.setObjectName("logoutBtn")
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.setFixedHeight(40)
        try:
            logout_icon = qta.icon("fa5s.sign-out-alt", color="#ef4444", scale_factor=0.9)
            logout_btn.setIcon(logout_icon)
            logout_btn.setIconSize(QSize(16, 16))
        except:
            pass
        logout_btn.clicked.connect(self.logout_user)
        sidebar_layout.addWidget(logout_btn)

        sidebar_layout.addSpacing(12)

        # User profile card at bottom
        profile_card = self.create_profile_card()
        sidebar_layout.addWidget(profile_card)

        return sidebar

    def create_nav_button(self, label, icon_name, is_active=False):
        """Create a navigation button with icon"""
        btn = QPushButton(f"  {label}")
        btn.setObjectName("navBtnActive" if is_active else "navBtn")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(40)

        try:
            icon = qta.icon(
                icon_name, color="#ffffff" if is_active else "#94a3b8", scale_factor=0.9
            )
            btn.setIcon(icon)
            btn.setIconSize(QSize(16, 16))
        except:
            pass

        return btn

    def create_profile_card(self):
        """Create user profile card at bottom of sidebar"""
        profile_card = QFrame()
        profile_card.setObjectName("profileCard")

        profile_layout = QHBoxLayout(profile_card)
        profile_layout.setContentsMargins(12, 12, 12, 12)
        profile_layout.setSpacing(10)

        # Get user data from database
        try:
            user_service = UserService()
            user_data = user_service.get_user_by_username(self.username)
            fullname = user_data.get("fullname", self.username) if user_data else self.username
            email = user_data.get("email", "user@example.com") if user_data else "user@example.com"
        except:
            fullname = self.username
            email = "user@example.com"

        # Avatar circle with first letter of name
        avatar_letter = fullname[0].upper() if fullname else "U"
        avatar = QLabel(avatar_letter)
        avatar.setObjectName("avatar")
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignCenter)
        profile_layout.addWidget(avatar)

        # Name and email in vertical layout
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel(fullname)
        name_label.setObjectName("profileName")
        name_label.setWordWrap(False)

        email_label = QLabel(email)
        email_label.setObjectName("profileEmail")
        email_label.setWordWrap(False)

        info_layout.addWidget(name_label)
        info_layout.addWidget(email_label)

        profile_layout.addLayout(info_layout)

        return profile_card

    def create_content_area(self):
        """Create the main content area with dashboard content"""
        content_widget = QWidget()
        content_widget.setObjectName("contentArea")

        # Create scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("scrollArea")

        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(40, 30, 40, 30)
        content_layout.setSpacing(24)

        # Header section
        header_layout = QHBoxLayout()

        # Title and subtitle
        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)

        dashboard_title = QLabel("Dashboard")
        dashboard_title.setObjectName("dashboardTitle")

        dashboard_subtitle = QLabel("Manage and monitor your connected services")
        dashboard_subtitle.setObjectName("dashboardSubtitle")

        title_layout.addWidget(dashboard_title)
        title_layout.addWidget(dashboard_subtitle)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # Status badge (dynamic, will be updated by timer)
        self.status_badge = QLabel(f"● {self.backend_status}")
        self.status_badge.setObjectName("statusBadge")
        self.status_badge.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Apply initial styling based on color
        self.status_badge.setStyleSheet(f"""
            background-color: {self.backend_color}20;
            color: {self.backend_color};
            border-radius: 20px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 500;
        """)

        header_layout.addWidget(self.status_badge)

        content_layout.addLayout(header_layout)

        # Stats cards row - 2 cards (DYNAMIC)
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)

        # Calculate dynamic values
        total_services = len(self.services)
        connected_services = sum(1 for _, _, _, is_active in self.services if is_active)

        stats_data = [
            ("Total Services", str(total_services), False),
            ("Connected Services", str(connected_services), True),
        ]

        for title, value, is_green in stats_data:
            card = self.create_stat_card(title, value, is_green)
            stats_layout.addWidget(card)

        # Add stretch to left-align the cards
        stats_layout.addStretch()

        content_layout.addLayout(stats_layout)

        # Communication section
        comm_label = QLabel("Communication")
        comm_label.setObjectName("sectionTitle")
        content_layout.addWidget(comm_label)

        # Service cards grid (DYNAMIC - uses self.services)
        service_grid = QGridLayout()
        service_grid.setSpacing(16)
        service_grid.setHorizontalSpacing(16)
        service_grid.setVerticalSpacing(16)

        # Use the dynamic services list
        row, col = 0, 0
        for service_name, description, icon_name, is_active in self.services:
            card = self.create_service_card(service_name, description, icon_name, is_active)
            service_grid.addWidget(card, row, col)
            col += 1
            if col > 2:  # 3 columns
                col = 0
                row += 1

        content_layout.addLayout(service_grid)
        content_layout.addStretch()

        scroll.setWidget(content_widget)

        # Wrap scroll in a layout
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addWidget(scroll)

        return wrapper

    def create_stat_card(self, title, value, is_green=False):
        """Create a statistics card"""
        card = QFrame()
        card.setObjectName("statCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card.setFixedHeight(90)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("statTitle")

        value_label = QLabel(value)
        value_label.setObjectName("statValueGreen" if is_green else "statValue")

        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)

        return card

    def create_service_card(self, service_name, description, icon_name, is_active=False):
        """Create a service integration card"""
        card = QFrame()
        card.setObjectName("serviceCardActive" if is_active else "serviceCard")
        card.setMinimumSize(180, 200)
        card.setMaximumWidth(240)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(12)

        # Icon and badge row
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        # Icon container
        icon_container = QFrame()
        icon_container.setObjectName("iconContainer")
        icon_container.setFixedSize(48, 48)

        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignCenter)

        # Icon
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        try:
            icon = qta.icon(icon_name, color="#475569", scale_factor=1.2)
            pixmap = icon.pixmap(28, 28)
            icon_label.setPixmap(pixmap)
        except Exception as e:
            logger.debug("Icon error for %s: %s", service_name, e)
            icon_label.setText("●")
            icon_label.setStyleSheet("color: #475569; font-size: 24px;")

        icon_layout.addWidget(icon_label)
        top_row.addWidget(icon_container, alignment=Qt.AlignLeft)
        top_row.addStretch()

        # Active badge (if active)
        if is_active:
            badge = QLabel("Active")
            badge.setObjectName("activeBadge")
            top_row.addWidget(badge)

        card_layout.addLayout(top_row)

        # Service name
        name_label = QLabel(service_name)
        name_label.setObjectName("serviceName")
        name_label.setWordWrap(True)
        card_layout.addWidget(name_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setObjectName("serviceDescription")
        desc_label.setWordWrap(True)
        card_layout.addWidget(desc_label)

        card_layout.addStretch()

        # Connect/Disconnect button
        btn_text = "Disconnect" if is_active else "Connect"
        action_btn = QPushButton(btn_text)
        action_btn.setObjectName("disconnectBtn" if is_active else "connectBtn")
        action_btn.setCursor(Qt.PointingHandCursor)
        action_btn.setFixedHeight(36)

        # Wire up click handler
        if is_active:
            action_btn.clicked.connect(lambda: self._handle_disconnect(service_name))
        else:
            action_btn.clicked.connect(lambda: self._handle_connect(service_name))

        card_layout.addWidget(action_btn)

        return card

    def _handle_connect(self, service_display_name):
        """Handle service connection request."""
        # Get internal service name
        internal_name = self.service_name_map.get(service_display_name, service_display_name)

        logger.info("Connecting to %s (%s)...", service_display_name, internal_name)

        # Check if service is registered in ServiceManager
        if internal_name not in self.service_manager.list_services():
            QMessageBox.warning(
                self,
                "Service Not Available",
                f"{service_display_name} integration is not yet implemented.\n\n"
                f"Currently only Google Workspace is supported.",
            )
            return

        # Show progress dialog (OAuth flow can take a while)
        progress = QProgressDialog(
            f"Connecting to {service_display_name}...\n\nA browser window will open for authentication.",
            None,  # No cancel button
            0,
            0,  # Indeterminate progress
            self,
        )
        progress.setWindowTitle("Authenticating")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        try:
            # Call ServiceManager to connect (runs in background thread)
            # But we need to pass user_id to service
            # So we need to re-register the service with user_id
            if internal_name == "GMeet":
                from services.meet_service import MeetService

                self.service_manager.register_service("GMeet", MeetService(user_id=self.user_id))
            elif internal_name == "Spotify":
                from services.spotify_service import SpotifyService

                self.service_manager.register_service(
                    "Spotify", SpotifyService(user_id=self.user_id)
                )

            # Run OAuth in a background QThread — never blocks the Qt event loop
            self._oauth_thread = OAuthThread(self.service_manager, internal_name)
            self._oauth_thread.finished.connect(
                lambda ok, msg: self._on_oauth_done(service_display_name, progress, ok, msg)
            )
            self._oauth_thread.start()
            # Return immediately; _on_oauth_done handles the result when ready

        except Exception as e:
            progress.close()
            logger.error("Error starting OAuth for %s: %s", service_display_name, e, exc_info=True)
            QMessageBox.critical(
                self,
                "Connection Error",
                f"An error occurred while connecting to {service_display_name}:\n\n{str(e)}",
            )

    def _on_oauth_done(self, service_display_name: str, progress, success: bool, message: str):
        """Called on the Qt main thread when OAuth completes."""
        progress.close()
        if success:
            logger.info("Connected to %s: %s", service_display_name, message)
            self._update_user_context()
            QMessageBox.information(
                self,
                "Connection Successful",
                f"Successfully connected to {service_display_name}!\n\n{message}",
            )
            self._refresh_dashboard()
        else:
            logger.error("Failed to connect to %s: %s", service_display_name, message)
            QMessageBox.warning(
                self,
                "Connection Failed",
                f"Failed to connect to {service_display_name}.\n\n{message}",
            )

    def _handle_disconnect(self, service_display_name):
        """Handle service disconnection request."""
        # Get internal service name
        internal_name = self.service_name_map.get(service_display_name, service_display_name)

        # Confirm disconnection
        reply = QMessageBox.question(
            self,
            "Confirm Disconnect",
            f"Are you sure you want to disconnect from {service_display_name}?\n\n"
            f"This will remove your stored credentials.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.No:
            return

        logger.info("Disconnecting from %s (%s)...", service_display_name, internal_name)

        try:
            # Delete token from MongoDB
            if self.user_id:
                result = self.token_store.delete_token(internal_name, self.user_id)
                if result.get("ok"):
                    deleted_count = result.get("deleted_count", 0)
                    logger.info(
                        "Deleted %d tokens from MongoDB for %s", deleted_count, service_display_name
                    )

                    # Also delete the token.json file to force OAuth on reconnect
                    # dashboard.py is at: Sentinel-AI-Frontend/ui/views/dashboard.py
                    # We need to go up 3 levels to get to Sentinel-AI-Frontend/
                    current_file_dir = os.path.dirname(os.path.abspath(__file__))  # .../ui/views
                    ui_dir = os.path.dirname(current_file_dir)  # .../ui
                    frontend_dir = os.path.dirname(ui_dir)  # .../Sentinel-AI-Frontend
                    token_path = os.path.join(frontend_dir, "token.json")

                    logger.debug("Looking for token.json at: %s", token_path)

                    if os.path.exists(token_path):
                        try:
                            os.remove(token_path)
                            logger.info("Deleted token.json file at %s", token_path)
                        except Exception as e:
                            logger.warning("Could not delete token.json: %s", e)
                    else:
                        logger.info(
                            "No token.json file found at %s (already deleted or never existed)", token_path
                        )

                    # Update user_context.json
                    self._update_user_context()

                    QMessageBox.information(
                        self,
                        "Disconnected",
                        f"Successfully disconnected from {service_display_name}.",
                    )

                    # Refresh dashboard
                    self._refresh_dashboard()
                else:
                    error = result.get("error", "Unknown error")
                    QMessageBox.warning(
                        self,
                        "Disconnect Failed",
                        f"Failed to disconnect from {service_display_name}:\n\n{error}",
                    )
            else:
                QMessageBox.warning(self, "Error", "User ID not available. Cannot disconnect.")

        except Exception as e:
            logger.error("Error disconnecting from %s: %s", service_display_name, e, exc_info=True)
            QMessageBox.critical(
                self, "Disconnect Error", f"An error occurred while disconnecting:\n\n{str(e)}"
            )

    # ---- Status-map shared by both signal and polling paths ----
    _STATUS_MAP = None  # Lazily populated to avoid import at class-body time

    @classmethod
    def _get_status_map(cls):
        if cls._STATUS_MAP is None:
            try:
                from integration.event_bus import BackendStatus
            except ImportError:
                from event_bus import BackendStatus  # type: ignore
            cls._STATUS_MAP = {
                BackendStatus.STARTING: ("Starting...", "#f59e0b"),
                BackendStatus.READY: ("Ready", "#10b981"),
                BackendStatus.LISTENING: ("Listening for 'Sentinel'", "#10b981"),
                BackendStatus.WAKE_WORD_DETECTED: ("Wake word detected!", "#8b5cf6"),
                BackendStatus.PROCESSING: ("Processing...", "#3b82f6"),
                BackendStatus.SPEAKING: ("Speaking...", "#06b6d4"),
                BackendStatus.ERROR: ("Error", "#ef4444"),
                BackendStatus.STOPPED: ("Stopped", "#6b7280"),
            }
        return cls._STATUS_MAP

    def _apply_status(self, text, color):
        """Apply a status string + color to the badge widget."""
        self.backend_status = text
        self.backend_color = color
        self.status_badge.setText(f"● {text}")
        self.status_badge.setStyleSheet(
            f"background-color: {color}20; color: {color};"
            "border-radius: 20px; padding: 6px 14px; font-size: 12px; font-weight: 500;"
        )

    def _handle_event(self, event):
        """Slot connected to QtEventBridge.event_received (instant delivery)."""
        try:
            from integration.event_bus import EventType
        except ImportError:
            from event_bus import EventType  # type: ignore

        try:
            status_map = self._get_status_map()
            if event.status and event.status in status_map:
                self._apply_status(*status_map[event.status])
            elif event.type == EventType.COMMAND_RECEIVED:
                self._apply_status(f"Command: {event.data or 'processing'}", "#3b82f6")
        except Exception as e:
            logger.warning("Error handling backend event: %s", e)

    def update_backend_status(self):
        """Fallback polling path — only used when Qt signal bridge is unavailable."""
        if not self.event_bus:
            return

        try:
            event = self.event_bus.get_event()
            if not event:
                self._idle_poll_count += 1
                if self._idle_poll_count >= self._max_idle_polls:
                    self.backend_status_timer.setInterval(1000)
                return

            self._idle_poll_count = 0
            self.backend_status_timer.setInterval(100)
            self._handle_event(event)

        except Exception as e:
            logger.warning("Error updating backend status: %s", e)

    def logout_user(self):
        """Handle user logout"""
        # Disconnect Qt signal bridge if active
        if hasattr(self, "_qt_bridge") and self._qt_bridge is not None:
            try:
                self._qt_bridge.event_received.disconnect(self._handle_event)
            except (TypeError, RuntimeError):
                pass
            if self.event_bus:
                self.event_bus.set_qt_bridge(None)
            self._qt_bridge = None

        # Stop fallback polling timer if active
        if hasattr(self, "backend_status_timer"):
            self.backend_status_timer.stop()

        if self.username:
            SessionManager.delete_session(self.username)
        if self.main_app:
            self.main_app.show_login()

    def show_settings(self):
        """Navigate to settings page"""
        # Disconnect Qt signal bridge and stop timer
        if hasattr(self, "_qt_bridge") and self._qt_bridge is not None:
            try:
                self._qt_bridge.event_received.disconnect(self._handle_event)
            except (TypeError, RuntimeError):
                pass
            if self.event_bus:
                self.event_bus.set_qt_bridge(None)
            self._qt_bridge = None
        if hasattr(self, "backend_status_timer"):
            self.backend_status_timer.stop()

        if self.main_app:
            self.main_app.show_settings(username=self.username, user_id=self.user_id)

    def show_home(self):
        """Navigate to home (same as dashboard)"""
        # This is currently the same as dashboard
        # Can be expanded to show a different home view in the future
        pass

    def show_dashboard(self):
        """Refresh dashboard view"""
        # Currently on dashboard, can be used to refresh
        self._refresh_dashboard()
