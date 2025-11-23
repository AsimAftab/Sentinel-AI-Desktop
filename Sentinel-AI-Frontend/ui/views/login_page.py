from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFrame, QMessageBox, QCheckBox, QAction, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QSize
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter
from PyQt5.QtSvg import QSvgWidget
import qtawesome as qta
import os

# Import your database and session managers
from auth.keyring_auth import KeyringAuthFixed
from auth.session_manager import SessionManager
from utils.user_context_writer import UserContextWriter
from database.user_service import UserService


# Helper class to make labels (like "Sign up") clickable
class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


# Custom Checkbox with checkmark overlay
class CheckBoxWithIcon(QCheckBox):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        try:
            self.check_icon = qta.icon('fa5s.check', color='white', scale_factor=0.65)
        except:
            self.check_icon = None

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isChecked() and self.check_icon:
            painter = QPainter(self)
            check_pixmap = self.check_icon.pixmap(12, 12)
            painter.drawPixmap(4, 6, check_pixmap)
            painter.end()


class LoginPage(QWidget):
    def __init__(self, switch_to_signup=None, switch_to_dashboard=None):
        super().__init__()
        self.switch_to_signup = switch_to_signup
        self.switch_to_dashboard = switch_to_dashboard
        self.password_visible = False

        # Main Layout centered on screen
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.setContentsMargins(20, 30, 20, 20)
        main_layout.setSpacing(8)

        # --- 1. HEADER SECTION ---
        # Lock Icon using Container.svg
        self.icon_container = QWidget()
        self.icon_container.setFixedSize(64, 64)
        icon_layout = QVBoxLayout(self.icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignCenter)

        try:
            # Try to load the SVG file using absolute path
            svg_path = os.path.join(os.path.dirname(__file__), "..", "assests", "Container.svg")
            svg_path = os.path.normpath(svg_path)
            self.svg_widget = QSvgWidget(svg_path)
            self.svg_widget.setFixedSize(64, 64)
            icon_layout.addWidget(self.svg_widget)
        except Exception as e:
            # Fallback to QtAwesome if SVG loading fails
            try:
                self.icon_label = QLabel()
                self.icon_label.setAlignment(Qt.AlignCenter)
                lock_icon = qta.icon('fa5s.lock', color='#fbbf24', scale_factor=1.8)
                pixmap = lock_icon.pixmap(60, 60)
                self.icon_label.setPixmap(pixmap)
                icon_layout.addWidget(self.icon_label)
            except:
                # Final fallback to emoji
                self.icon_label = QLabel("🔒")
                self.icon_label.setStyleSheet("font-size: 50px; color: #fbbf24; background: transparent;")
                self.icon_label.setAlignment(Qt.AlignCenter)
                icon_layout.addWidget(self.icon_label)
            print(f"SVG loading error: {e}")

        # App Title & Subtitle
        self.app_title = QLabel("Sentinel-AI")
        self.app_title.setObjectName("headerTitle")
        self.app_title.setAlignment(Qt.AlignCenter)

        self.app_subtitle = QLabel("Secure Access Portal")
        self.app_subtitle.setObjectName("headerSubtitle")
        self.app_subtitle.setAlignment(Qt.AlignCenter)

        # Add widgets to main layout with explicit center alignment for the icon
        main_layout.addWidget(self.icon_container, 0, Qt.AlignHCenter)
        main_layout.addWidget(self.app_title)
        main_layout.addWidget(self.app_subtitle)
        main_layout.addSpacing(25)

        # --- 2. LOGIN CARD ---
        self.card = QFrame()
        self.card.setObjectName("loginCard")
        # Make card responsive with max and min width instead of fixed width
        self.card.setMaximumWidth(450)
        self.card.setMinimumWidth(300)

        # Add subtle shadow effect to card
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 4)
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(35, 35, 35, 35)
        card_layout.setSpacing(12)

        # Card Header
        self.card_title = QLabel("Welcome Back")
        self.card_title.setObjectName("cardTitle")
        self.card_title.setAlignment(Qt.AlignLeft)

        self.card_subtitle = QLabel("Enter your credentials to access your dashboard")
        self.card_subtitle.setObjectName("cardSubtitle")
        self.card_subtitle.setWordWrap(True)
        self.card_subtitle.setAlignment(Qt.AlignLeft)

        # Username Field with Icon
        lbl_user = QLabel("Username")
        lbl_user.setObjectName("inputLabel")

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        self.username_input.setFixedHeight(46)
        self.username_input.setObjectName("usernameInput")
        # Reduce gap between icon and placeholder text
        self.username_input.setTextMargins(5, 0, 0, 0)

        # Add user icon using QtAwesome
        try:
            user_icon = qta.icon('fa5s.user', color='#64748b', scale_factor=0.9)
            user_action = QAction(user_icon, "", self.username_input)
            self.username_input.addAction(user_action, QLineEdit.LeadingPosition)
        except Exception as e:
            print(f"User icon error: {e}")

        # Add validation hint label
        self.username_hint = QLabel("")
        self.username_hint.setObjectName("validationHint")
        self.username_hint.hide()

        # Password Field with Icon
        lbl_pass = QLabel("Password")
        lbl_pass.setObjectName("inputLabel")

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setFixedHeight(46)
        self.password_input.setObjectName("passwordInput")
        # Reduce gap between icon and placeholder text
        self.password_input.setTextMargins(5, 0, 0, 0)

        # Add lock icon using QtAwesome
        try:
            lock_icon = qta.icon('fa5s.lock', color='#64748b', scale_factor=0.9)
            lock_action = QAction(lock_icon, "", self.password_input)
            self.password_input.addAction(lock_action, QLineEdit.LeadingPosition)
        except Exception as e:
            print(f"Lock icon error: {e}")

        # Add eye icon for password visibility toggle
        try:
            self.eye_icon = qta.icon('fa5s.eye', color='#64748b', scale_factor=0.9)
            self.eye_off_icon = qta.icon('fa5s.eye-slash', color='#64748b', scale_factor=0.9)
            self.eye_action = QAction(self.eye_icon, "", self.password_input)
            self.eye_action.triggered.connect(self.toggle_password_visibility)
            self.password_input.addAction(self.eye_action, QLineEdit.TrailingPosition)
        except Exception as e:
            print(f"Eye icon error: {e}")

        # Add validation hint label
        self.password_hint = QLabel("")
        self.password_hint.setObjectName("validationHint")
        self.password_hint.hide()

        # Connect Enter key to login for both inputs
        self.username_input.returnPressed.connect(self.validate_login)
        self.password_input.returnPressed.connect(self.validate_login)

        # Options Row (Remember Me / Forgot Password)
        options_layout = QHBoxLayout()
        options_layout.setSpacing(0)

        # Enhanced Remember Me checkbox with checkmark icon (square style to match signup)
        self.remember_checkbox = CheckBoxWithIcon("Remember me")
        self.remember_checkbox.setFixedHeight(24)
        self.remember_checkbox.setCursor(Qt.PointingHandCursor)
        self.remember_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
                color: #64748b;
                font-size: 14px;
            }
            QCheckBox:hover {
                color: #475569;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #cbd5e1;
                background-color: #ffffff;
            }
            QCheckBox::indicator:hover {
                border-color: #3b82f6;
                background-color: #eff6ff;
            }
            QCheckBox::indicator:checked {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #2563eb;
                border-color: #2563eb;
            }
        """)

        self.forgot_label = ClickableLabel("Forgot password?")
        self.forgot_label.setObjectName("forgotPassword")
        self.forgot_label.setCursor(Qt.PointingHandCursor)
        self.forgot_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.forgot_label.setToolTip("Reset your password")

        options_layout.addWidget(self.remember_checkbox)
        options_layout.addStretch()
        options_layout.addWidget(self.forgot_label)

        # Sign In Button
        self.login_btn = QPushButton("Sign In")
        self.login_btn.setObjectName("loginBtn")
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setFixedHeight(48)
        self.login_btn.clicked.connect(self.validate_login)
        self.login_btn.setDefault(True)  # Makes Enter key trigger this button

        # Sign Up Link section
        signup_layout = QHBoxLayout()
        signup_layout.setAlignment(Qt.AlignCenter)
        signup_layout.setSpacing(5)

        signup_text = QLabel("Don't have an account?")
        signup_text.setObjectName("signupText")

        self.signup_link = ClickableLabel("Sign up")
        self.signup_link.setObjectName("signupLink")
        self.signup_link.setCursor(Qt.PointingHandCursor)
        self.signup_link.setToolTip("Create a new account")

        # Connect the signup link click to the switcher function
        if self.switch_to_signup:
            self.signup_link.clicked.connect(self.switch_to_signup)

        signup_layout.addWidget(signup_text)
        signup_layout.addWidget(self.signup_link)

        # Add all elements to card layout
        card_layout.addWidget(self.card_title)
        card_layout.addWidget(self.card_subtitle)
        card_layout.addSpacing(12)
        card_layout.addWidget(lbl_user)
        card_layout.addWidget(self.username_input)
        card_layout.addWidget(self.username_hint)
        card_layout.addSpacing(6)
        card_layout.addWidget(lbl_pass)
        card_layout.addWidget(self.password_input)
        card_layout.addWidget(self.password_hint)
        card_layout.addSpacing(4)
        card_layout.addLayout(options_layout)
        card_layout.addSpacing(12)
        card_layout.addWidget(self.login_btn)
        card_layout.addSpacing(15)
        card_layout.addLayout(signup_layout)

        main_layout.addWidget(self.card)
        main_layout.addStretch()

        # --- 3. FOOTER ---
        self.footer = QLabel("© 2025 Sentinel-AI. All rights reserved.")
        self.footer.setObjectName("footerText")
        self.footer.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.footer)

        # Set focus to username field on load
        self.username_input.setFocus()

    def toggle_password_visibility(self):
        """Toggle password visibility on eye icon click"""
        try:
            if self.password_visible:
                self.password_input.setEchoMode(QLineEdit.Password)
                self.password_visible = False
                self.eye_action.setIcon(self.eye_icon)
            else:
                self.password_input.setEchoMode(QLineEdit.Normal)
                self.password_visible = True
                self.eye_action.setIcon(self.eye_off_icon)
        except Exception as e:
            print(f"Toggle visibility error: {e}")

    def show_validation_hint(self, field, message, is_error=True):
        """Show validation hint below input field"""
        if field == "username":
            hint_label = self.username_hint
        else:
            hint_label = self.password_hint

        hint_label.setText(message)
        hint_label.setStyleSheet(
            f"color: {'#ef4444' if is_error else '#22c55e'}; "
            f"font-size: 12px; margin-top: 4px;"
        )
        hint_label.show()

    def hide_validation_hints(self):
        """Hide all validation hints"""
        self.username_hint.hide()
        self.password_hint.hide()

    def validate_login(self):
        """
        Validates user credentials against MongoDB and manages session.
        Enhanced with better UX feedback.
        """
        self.hide_validation_hints()

        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        # Client-side validation
        if not username:
            self.show_validation_hint("username", "⚠ Username is required")
            self.username_input.setFocus()
            return

        if not password:
            self.show_validation_hint("password", "⚠ Password is required")
            self.password_input.setFocus()
            return

        # Disable button and show loading state
        self.login_btn.setEnabled(False)
        self.login_btn.setText("Signing in...")
        self.login_btn.setCursor(Qt.WaitCursor)

        try:
            # Authenticate user using KeyringAuthFixed
            success, message, user_data = KeyringAuthFixed.authenticate_user(username, password)

            if not success:
                self.show_validation_hint("password", f"⚠ {message}")
                self.password_input.clear()
                self.password_input.setFocus()
                self.reset_login_button()
                return

            # Fetch user from MongoDB to get real _id
            try:
                user_service = UserService()
                db_user = user_service.get_user_by_username(username)

                if db_user and '_id' in db_user:
                    user_id = str(db_user['_id'])
                    print(f"✅ Fetched user_id from MongoDB: {user_id}")
                else:
                    # Fallback if DB user not found (shouldn't happen)
                    user_id = username  # Use username as fallback
                    print(f"⚠️ User not found in MongoDB, using username as fallback")

                # Write user context for backend
                context_writer = UserContextWriter()
                context_writer.write_user_context(
                    user_id=user_id,
                    username=username,
                    additional_data={'fullname': user_data.get('fullname')}
                )
            except Exception as e:
                print(f"⚠️ Failed to write user context: {e}")

            # Show success feedback
            self.login_btn.setText("✓ Success!")
            self.login_btn.setStyleSheet("""
                QPushButton {
                    background-color: #22c55e;
                    border-color: #22c55e;
                }
            """)

            # Redirect to dashboard
            if self.switch_to_dashboard:
                self.switch_to_dashboard(username)
            else:
                QMessageBox.information(
                    self,
                    "Login Successful",
                    f"Welcome back, {user_data.get('fullname', username)}!"
                )

        except Exception as e:
            # Handle unexpected errors
            QMessageBox.critical(
                self,
                "Connection Error",
                f"Unable to connect to the server. Please try again.\n\nError: {str(e)}"
            )
            self.reset_login_button()

    def reset_login_button(self):
        """Reset login button to default state"""
        self.login_btn.setEnabled(True)
        self.login_btn.setText("Sign In")
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setStyleSheet("")  # Reset to default stylesheet

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        # Escape key to clear fields
        if event.key() == Qt.Key_Escape:
            self.username_input.clear()
            self.password_input.clear()
            self.hide_validation_hints()
            self.username_input.setFocus()
        super().keyPressEvent(event)
