import sys
import os
import logging
from PyQt5.QtWidgets import QApplication, QStackedWidget
from PyQt5.QtGui import QIcon
from ui.views.signup_page import SignupPage
from ui.views.login_page import LoginPage
from ui.views.dashboard import DashboardPage
from ui.views.settings_page import SettingsPage

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class MainApp(QStackedWidget):
    def __init__(self):
        super().__init__()

        # Initialize pages with callback references
        self.signup_page = SignupPage(self.show_login)
        self.login_page = LoginPage(self.show_signup, self.show_dashboard)

        self.addWidget(self.login_page)
        self.addWidget(self.signup_page)

        self.setCurrentWidget(self.login_page)

    def show_login(self):
        # Reset login page state when returning from dashboard
        self.login_page.reset_page_state()
        self.setCurrentWidget(self.login_page)

    def show_signup(self):
        self.setCurrentWidget(self.signup_page)

    def show_dashboard(self, username):
        # Remove and delete old dashboard to prevent widget/timer accumulation
        if hasattr(self, "dashboard") and self.dashboard is not None:
            if hasattr(self.dashboard, "backend_status_timer"):
                self.dashboard.backend_status_timer.stop()
            self.removeWidget(self.dashboard)
            self.dashboard.deleteLater()
        self.dashboard = DashboardPage(main_app=self, username=username)
        self.addWidget(self.dashboard)
        self.setCurrentWidget(self.dashboard)

    def show_settings(self, username=None, user_id=None):
        """Show settings page with user information."""
        # Remove and delete old settings page to prevent widget accumulation
        if hasattr(self, "settings_page") and self.settings_page is not None:
            self.removeWidget(self.settings_page)
            self.settings_page.deleteLater()
        self.settings_page = SettingsPage(main_app=self, username=username, user_id=user_id)
        self.addWidget(self.settings_page)
        self.setCurrentWidget(self.settings_page)

    def show_dashboard_from_settings(self):
        """Return to dashboard from settings page."""
        if hasattr(self, "dashboard") and self.dashboard:
            self.setCurrentWidget(self.dashboard)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Sentinel AI")

    try:
        style_path = os.path.join("ui", "qss", "style.qss")
        with open(style_path, "r") as file:
            style = file.read()
            app.setStyleSheet(style)
    except FileNotFoundError:
        logger.warning("style.qss not found. Running without styles.")
    except Exception as e:
        logger.warning("Error loading stylesheet: %s", e)

    window = MainApp()
    window.setWindowTitle("Sentinel AI")
    window.setMinimumSize(800, 600)
    window.resize(1024, 768)

    try:
        window.setWindowIcon(QIcon("assets/icon.png"))
    except Exception as e:
        logger.warning("Could not load icon: %s", e)

    # Center window on screen
    screen = app.primaryScreen().availableGeometry()
    x = (screen.width() - window.width()) // 2
    y = (screen.height() - window.height()) // 2
    window.move(x, y)

    window.show()
    sys.exit(app.exec_())
