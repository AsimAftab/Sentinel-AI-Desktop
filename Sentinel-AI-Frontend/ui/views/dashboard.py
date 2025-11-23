from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QMessageBox, QGridLayout, QSizePolicy, QScrollArea
)
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QPixmap, QFont
import qtawesome as qta
import os
from auth.session_manager import SessionManager
from database.user_service import UserService


class DashboardPage(QWidget):
    def __init__(self, main_app=None, username=None):
        super().__init__()

        try:
            self._initialize_dashboard(main_app, username)
        except Exception as e:
            import traceback
            print("=" * 60)
            print("❌ DASHBOARD INITIALIZATION ERROR:")
            print("=" * 60)
            traceback.print_exc()
            print("=" * 60)
            QMessageBox.critical(self, "Dashboard Error", f"Failed to load dashboard:\n\n{str(e)}")
            if main_app:
                main_app.show_login()

    def _initialize_dashboard(self, main_app=None, username=None):
        """Main initialization logic (wrapped for error handling)"""
        self.main_app = main_app
        self.username = username or "User"

        # Check if user is logged in using SessionManager
        if not SessionManager.is_logged_in(self.username):
            QMessageBox.critical(self, "Access Denied", "Your session has expired or you're not logged in.")
            if self.main_app:
                self.main_app.show_login()
            return

        self.setObjectName("dashboardPage")
        qss_path = os.path.join(os.path.dirname(__file__), "..", "qss", "dashboard.qss")
        try:
            with open(qss_path, "r") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print(f"Failed to load dashboard.qss: {e}")

        # Fetch user_id from MongoDB
        self.user_id = None
        try:
            user_service = UserService()
            db_user = user_service.get_user_by_username(self.username)
            if db_user and '_id' in db_user:
                self.user_id = str(db_user['_id'])
                print(f"✅ Dashboard: Fetched user_id: {self.user_id}")
        except Exception as e:
            print(f"⚠️ Dashboard: Failed to fetch user_id: {e}")

        # Define services list (will be used for dynamic counts)
        self.services = [
            ("Google Workspace", "Gmail, Drive, Calendar, and more", "fa5b.google", True),  # Only this is connected
            ("Zoom", "Video conferencing and meetings", "fa5s.video", False),
            ("Slack", "Team messaging and collaboration", "fa5b.slack", False),
            ("Microsoft Teams", "Chat, meetings, and collaboration", "fa5b.microsoft", False),
            ("YouTube Music", "Music streaming and playlists", "fa5b.youtube", False),
            ("Spotify", "Music and podcast streaming", "fa5b.spotify", False)
        ]

        # Backend status tracking
        self.backend_status = "Backend Not Connected"
        self.backend_color = "#6b7280"  # Gray for not connected
        self.comm_bus = None  # Initialize to None

        # Try to get backend status from communication bus (optional)
        try:
            import sys
            # Calculate integration path relative to project root
            # dashboard.py is at: Sentinel-AI-Frontend/ui/views/dashboard.py
            # integration is at: integration/ (sibling of Sentinel-AI-Frontend)

            # Get the project root (3 levels up from dashboard.py)
            current_file_dir = os.path.dirname(os.path.abspath(__file__))  # .../ui/views
            frontend_dir = os.path.dirname(os.path.dirname(current_file_dir))  # .../Sentinel-AI-Frontend
            project_root = os.path.dirname(frontend_dir)  # .../Sentinel-AI-Desktop
            integration_path = os.path.join(project_root, "integration")

            print(f"🔍 Looking for communication.py at: {integration_path}")

            if os.path.exists(integration_path):
                if integration_path not in sys.path:
                    sys.path.insert(0, integration_path)
                    print(f"✅ Added to sys.path: {integration_path}")

                from communication import CommunicationBus, BackendStatus
                self.comm_bus = CommunicationBus()

                # DON'T assume status - wait for backend to report it
                self.backend_status = "Connecting to backend..."
                self.backend_color = "#f59e0b"  # Orange (waiting for status)

                # Set up timer for status updates
                self.backend_status_timer = QTimer()
                self.backend_status_timer.timeout.connect(self.update_backend_status)
                self.backend_status_timer.start(100)  # Check every 100ms (faster initially)

                # Do an immediate status check
                QTimer.singleShot(10, self.update_backend_status)

                print("✅ Dashboard: Connected to backend communication bus - waiting for status...")
            else:
                print(f"⚠️ Integration path not found: {integration_path}")
                self.comm_bus = None

        except ImportError as e:
            print(f"ℹ️ Backend communication not available (import error): {e}")
            import traceback
            traceback.print_exc()
            self.comm_bus = None
        except Exception as e:
            print(f"⚠️ Could not connect to backend communication bus: {e}")
            import traceback
            traceback.print_exc()
            self.comm_bus = None

        # Main horizontal layout (sidebar + content)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== LEFT SIDEBAR =====
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)

        # ===== MAIN CONTENT AREA =====
        content_area = self.create_content_area()
        main_layout.addWidget(content_area)

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
        greeting = QLabel(f"Hey, {self.username}! 👋")
        greeting.setObjectName("greeting")
        sidebar_layout.addWidget(greeting)

        sidebar_layout.addSpacing(20)

        # Navigation menu
        nav_items = [
            ("Dashboard", "fa5s.th-large", True),
            ("Home", "fa5s.home", False),
            ("Settings", "fa5s.cog", False)
        ]

        for label, icon_name, is_active in nav_items:
            btn = self.create_nav_button(label, icon_name, is_active)
            sidebar_layout.addWidget(btn)

        # Push everything down
        sidebar_layout.addStretch()

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
            icon = qta.icon(icon_name, color='#ffffff' if is_active else '#94a3b8', scale_factor=0.9)
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

        # Add logout button (clickable)
        profile_card.mousePressEvent = lambda event: self.logout_user()
        profile_card.setCursor(Qt.PointingHandCursor)

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
            ("Connected Services", str(connected_services), True)
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
            icon = qta.icon(icon_name, color='#475569', scale_factor=1.2)
            pixmap = icon.pixmap(28, 28)
            icon_label.setPixmap(pixmap)
        except Exception as e:
            print(f"Icon error for {service_name}: {e}")
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
        card_layout.addWidget(action_btn)

        return card

    def update_backend_status(self):
        """Update backend status from communication bus"""
        if not self.comm_bus:
            return

        try:
            from communication import MessageType, BackendStatus

            # Check for messages from backend
            message = self.comm_bus.get_frontend_message()
            if not message:
                return

            if message.type == MessageType.STATUS_UPDATE:
                # Update status based on backend status
                status_map = {
                    BackendStatus.STARTING: ("Starting...", "#f59e0b"),  # Orange
                    BackendStatus.READY: ("Ready", "#10b981"),  # Green
                    BackendStatus.LISTENING: ("Listening for 'Sentinel'", "#10b981"),  # Green
                    BackendStatus.PROCESSING: ("Processing...", "#3b82f6"),  # Blue
                    BackendStatus.ERROR: ("Error", "#ef4444"),  # Red
                    BackendStatus.STOPPED: ("Stopped", "#6b7280"),  # Gray
                }

                if message.status in status_map:
                    self.backend_status, self.backend_color = status_map[message.status]
                    self.status_badge.setText(f"● {self.backend_status}")
                    self.status_badge.setStyleSheet(f"""
                        background-color: {self.backend_color}20;
                        color: {self.backend_color};
                        border-radius: 20px;
                        padding: 6px 14px;
                        font-size: 12px;
                        font-weight: 500;
                    """)

            elif message.type == MessageType.WAKE_WORD_DETECTED:
                self.backend_status = "Wake word detected!"
                self.backend_color = "#8b5cf6"  # Purple
                self.status_badge.setText(f"● {self.backend_status}")
                self.status_badge.setStyleSheet(f"""
                    background-color: {self.backend_color}20;
                    color: {self.backend_color};
                    border-radius: 20px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: 500;
                """)

            elif message.type == MessageType.COMMAND_RECEIVED:
                self.backend_status = f"Command: {message.data or 'processing'}"
                self.backend_color = "#3b82f6"  # Blue
                self.status_badge.setText(f"● {self.backend_status}")

        except Exception as e:
            print(f"⚠️ Error updating backend status: {e}")

    def logout_user(self):
        """Handle user logout"""
        # Stop backend status timer if active
        if hasattr(self, 'backend_status_timer'):
            self.backend_status_timer.stop()

        if self.username:
            SessionManager.delete_session(self.username)
        if self.main_app:
            self.main_app.show_login()
