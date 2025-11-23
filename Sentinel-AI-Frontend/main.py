import sys
import os
import logging
from PyQt5.QtWidgets import QApplication, QStackedWidget
from PyQt5.QtGui import QIcon
from ui.views.signup_page import SignupPage
from ui.views.login_page import LoginPage
from ui.views.dashboard import DashboardPage

logging.basicConfig(level=logging.DEBUG)


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
        self.dashboard = DashboardPage(main_app=self, username=username)
        self.addWidget(self.dashboard)
        self.setCurrentWidget(self.dashboard)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("Sentinel AI")

    try:
        style_path = os.path.join("ui", "qss", "style.qss")
        with open(style_path, "r") as file:
            style = file.read()
            app.setStyleSheet(style)
    except FileNotFoundError:
        print("⚠️  Warning: style.qss not found. Running without styles.")
    except Exception as e:
        print(f"⚠️  Error loading stylesheet: {e}")

    window = MainApp()
    window.setWindowTitle("Sentinel AI")
    window.setFixedSize(1024, 768)  # Fixed size 1024x768

    try:
        window.setWindowIcon(QIcon("assets/icon.png"))
    except Exception as e:
        print("⚠️  Could not load icon:", e)

    # Center window on screen
    screen = app.primaryScreen().availableGeometry()
    x = (screen.width() - 1024) // 2
    y = (screen.height() - 768) // 2
    window.move(x, y)

    window.show()
    sys.exit(app.exec_())
