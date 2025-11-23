from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFrame, QMessageBox, QCheckBox, QAction, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter
from PyQt5.QtSvg import QSvgWidget
import qtawesome as qta
import re
import os

# Import authentication and database managers
from auth.keyring_auth import KeyringAuthFixed
from database.user_service import UserService


# Helper class to make labels clickable
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


class SignupPage(QWidget):
    def __init__(self, switch_to_login=None):
        super().__init__()
        self.switch_to_login = switch_to_login
        self.password_visible = False
        self.confirm_password_visible = False

        # Main Layout centered on screen
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(0)

        # Add stretch before card to center it vertically
        main_layout.addStretch()

        # --- 1. SIGNUP CARD ---
        self.card = QFrame()
        self.card.setObjectName("signupCard")
        self.card.setMaximumWidth(480)
        self.card.setMinimumWidth(320)

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
        self.card_title = QLabel("Create Account")
        self.card_title.setObjectName("cardTitle")
        self.card_title.setAlignment(Qt.AlignLeft)

        self.card_subtitle = QLabel("Sign up to get started with Sentinel AI")
        self.card_subtitle.setObjectName("cardSubtitle")
        self.card_subtitle.setWordWrap(True)
        self.card_subtitle.setAlignment(Qt.AlignLeft)

        # Full Name Field with Icon
        lbl_fullname = QLabel("Full Name")
        lbl_fullname.setObjectName("inputLabel")

        self.fullname_input = QLineEdit()
        self.fullname_input.setPlaceholderText("Enter your full name")
        self.fullname_input.setFixedHeight(46)
        self.fullname_input.setObjectName("fullnameInput")
        self.fullname_input.setTextMargins(5, 0, 0, 0)

        try:
            user_icon = qta.icon('fa5s.user', color='#64748b', scale_factor=0.9)
            user_action = QAction(user_icon, "", self.fullname_input)
            self.fullname_input.addAction(user_action, QLineEdit.LeadingPosition)
        except Exception as e:
            print(f"User icon error: {e}")

        self.fullname_hint = QLabel("")
        self.fullname_hint.setObjectName("validationHint")
        self.fullname_hint.hide()

        # Username Field with Icon
        lbl_username = QLabel("Username")
        lbl_username.setObjectName("inputLabel")

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Choose a username")
        self.username_input.setFixedHeight(46)
        self.username_input.setObjectName("usernameInput")
        self.username_input.setTextMargins(5, 0, 0, 0)

        try:
            user_icon2 = qta.icon('fa5s.user-circle', color='#64748b', scale_factor=0.9)
            user_action2 = QAction(user_icon2, "", self.username_input)
            self.username_input.addAction(user_action2, QLineEdit.LeadingPosition)
        except Exception as e:
            print(f"User icon error: {e}")

        self.username_hint = QLabel("")
        self.username_hint.setObjectName("validationHint")
        self.username_hint.hide()

        # Phone Field with Icon
        lbl_phone = QLabel("Phone Number")
        lbl_phone.setObjectName("inputLabel")

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Enter your phone number")
        self.phone_input.setFixedHeight(46)
        self.phone_input.setObjectName("phoneInput")
        self.phone_input.setTextMargins(5, 0, 0, 0)

        try:
            phone_icon = qta.icon('fa5s.phone', color='#64748b', scale_factor=0.9)
            phone_action = QAction(phone_icon, "", self.phone_input)
            self.phone_input.addAction(phone_action, QLineEdit.LeadingPosition)
        except Exception as e:
            print(f"Phone icon error: {e}")

        self.phone_hint = QLabel("")
        self.phone_hint.setObjectName("validationHint")
        self.phone_hint.hide()

        # Email Field with Icon
        lbl_email = QLabel("Email Address")
        lbl_email.setObjectName("inputLabel")

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Enter your email address")
        self.email_input.setFixedHeight(46)
        self.email_input.setObjectName("emailInput")
        self.email_input.setTextMargins(5, 0, 0, 0)

        try:
            email_icon = qta.icon('fa5s.envelope', color='#64748b', scale_factor=0.9)
            email_action = QAction(email_icon, "", self.email_input)
            self.email_input.addAction(email_action, QLineEdit.LeadingPosition)
        except Exception as e:
            print(f"Email icon error: {e}")

        self.email_hint = QLabel("")
        self.email_hint.setObjectName("validationHint")
        self.email_hint.hide()

        # Password Field with Icon
        lbl_password = QLabel("Password")
        lbl_password.setObjectName("inputLabel")

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Create a password (min. 6 characters)")
        self.password_input.setFixedHeight(46)
        self.password_input.setObjectName("passwordInput")
        self.password_input.setTextMargins(5, 0, 0, 0)

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

        self.password_hint = QLabel("")
        self.password_hint.setObjectName("validationHint")
        self.password_hint.hide()

        # Confirm Password Field with Icon
        lbl_confirm = QLabel("Confirm Password")
        lbl_confirm.setObjectName("inputLabel")

        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input.setPlaceholderText("Confirm your password")
        self.confirm_password_input.setFixedHeight(46)
        self.confirm_password_input.setObjectName("confirmPasswordInput")
        self.confirm_password_input.setTextMargins(5, 0, 0, 0)

        try:
            lock_icon2 = qta.icon('fa5s.lock', color='#64748b', scale_factor=0.9)
            lock_action2 = QAction(lock_icon2, "", self.confirm_password_input)
            self.confirm_password_input.addAction(lock_action2, QLineEdit.LeadingPosition)
        except Exception as e:
            print(f"Lock icon error: {e}")

        # Add eye icon for confirm password visibility toggle
        try:
            self.confirm_eye_action = QAction(self.eye_icon, "", self.confirm_password_input)
            self.confirm_eye_action.triggered.connect(self.toggle_confirm_password_visibility)
            self.confirm_password_input.addAction(self.confirm_eye_action, QLineEdit.TrailingPosition)
        except Exception as e:
            print(f"Eye icon error: {e}")

        self.confirm_password_hint = QLabel("")
        self.confirm_password_hint.setObjectName("validationHint")
        self.confirm_password_hint.hide()

        # Connect Enter key to signup
        self.confirm_password_input.returnPressed.connect(self.validate_signup)

        # Terms & Conditions Checkbox
        self.terms_checkbox = CheckBoxWithIcon("I agree to the Terms & Conditions")
        self.terms_checkbox.setFixedHeight(24)
        self.terms_checkbox.setCursor(Qt.PointingHandCursor)
        self.terms_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
                color: #94a3b8;
                font-size: 13px;
            }
            QCheckBox:hover {
                color: #cbd5e1;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1.5px solid #334155;
                background-color: #0f1623;
            }
            QCheckBox::indicator:hover {
                border-color: #475569;
                background-color: #151b2d;
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

        # Create Account Button
        self.signup_btn = QPushButton("Create Account")
        self.signup_btn.setObjectName("signupBtn")
        self.signup_btn.setCursor(Qt.PointingHandCursor)
        self.signup_btn.setFixedHeight(48)
        self.signup_btn.clicked.connect(self.validate_signup)
        self.signup_btn.setDefault(True)

        # Already have account section
        signin_layout = QHBoxLayout()
        signin_layout.setAlignment(Qt.AlignCenter)
        signin_layout.setSpacing(5)

        signin_text = QLabel("Already have an account?")
        signin_text.setObjectName("signupText")

        self.signin_link = ClickableLabel("Sign in")
        self.signin_link.setObjectName("signupLink")
        self.signin_link.setCursor(Qt.PointingHandCursor)
        self.signin_link.setToolTip("Sign in to your account")

        if self.switch_to_login:
            self.signin_link.clicked.connect(self.switch_to_login)

        signin_layout.addWidget(signin_text)
        signin_layout.addWidget(self.signin_link)

        # Add all elements to card layout
        card_layout.addWidget(self.card_title)
        card_layout.addWidget(self.card_subtitle)
        card_layout.addSpacing(12)
        card_layout.addWidget(lbl_fullname)
        card_layout.addWidget(self.fullname_input)
        card_layout.addWidget(self.fullname_hint)
        card_layout.addSpacing(6)
        card_layout.addWidget(lbl_username)
        card_layout.addWidget(self.username_input)
        card_layout.addWidget(self.username_hint)
        card_layout.addSpacing(6)
        card_layout.addWidget(lbl_phone)
        card_layout.addWidget(self.phone_input)
        card_layout.addWidget(self.phone_hint)
        card_layout.addSpacing(6)
        card_layout.addWidget(lbl_email)
        card_layout.addWidget(self.email_input)
        card_layout.addWidget(self.email_hint)
        card_layout.addSpacing(6)
        card_layout.addWidget(lbl_password)
        card_layout.addWidget(self.password_input)
        card_layout.addWidget(self.password_hint)
        card_layout.addSpacing(6)
        card_layout.addWidget(lbl_confirm)
        card_layout.addWidget(self.confirm_password_input)
        card_layout.addWidget(self.confirm_password_hint)
        card_layout.addSpacing(8)
        card_layout.addWidget(self.terms_checkbox)
        card_layout.addSpacing(12)
        card_layout.addWidget(self.signup_btn)
        card_layout.addSpacing(15)
        card_layout.addLayout(signin_layout)

        # Create horizontal layout to center card horizontally
        card_container = QHBoxLayout()
        card_container.addStretch()
        card_container.addWidget(self.card)
        card_container.addStretch()

        # Add card container to main layout
        main_layout.addLayout(card_container)

        # Add stretch after card to center it vertically
        main_layout.addStretch()

        # Set focus to fullname field on load
        self.fullname_input.setFocus()

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

    def toggle_confirm_password_visibility(self):
        """Toggle confirm password visibility on eye icon click"""
        try:
            if self.confirm_password_visible:
                self.confirm_password_input.setEchoMode(QLineEdit.Password)
                self.confirm_password_visible = False
                self.confirm_eye_action.setIcon(self.eye_icon)
            else:
                self.confirm_password_input.setEchoMode(QLineEdit.Normal)
                self.confirm_password_visible = True
                self.confirm_eye_action.setIcon(self.eye_off_icon)
        except Exception as e:
            print(f"Toggle visibility error: {e}")

    def show_validation_hint(self, field, message, is_error=True):
        """Show validation hint below input field"""
        hints = {
            "fullname": self.fullname_hint,
            "username": self.username_hint,
            "phone": self.phone_hint,
            "email": self.email_hint,
            "password": self.password_hint,
            "confirm_password": self.confirm_password_hint
        }

        hint_label = hints.get(field)
        if hint_label:
            hint_label.setText(message)
            hint_label.setStyleSheet(
                f"color: {'#ef4444' if is_error else '#22c55e'}; "
                f"font-size: 12px; margin-top: 4px;"
            )
            hint_label.show()

    def hide_validation_hints(self):
        """Hide all validation hints"""
        self.fullname_hint.hide()
        self.username_hint.hide()
        self.phone_hint.hide()
        self.email_hint.hide()
        self.password_hint.hide()
        self.confirm_password_hint.hide()

    def validate_signup(self):
        """Validate and process signup form with enhanced UX"""
        self.hide_validation_hints()

        fullname = self.fullname_input.text().strip()
        username = self.username_input.text().strip()
        phone = self.phone_input.text().strip()
        email = self.email_input.text().strip()
        password = self.password_input.text().strip()
        confirm_password = self.confirm_password_input.text().strip()

        # Client-side validation
        if not fullname:
            self.show_validation_hint("fullname", "⚠ Full name is required")
            self.fullname_input.setFocus()
            return

        if not username:
            self.show_validation_hint("username", "⚠ Username is required")
            self.username_input.setFocus()
            return

        if not phone:
            self.show_validation_hint("phone", "⚠ Phone number is required")
            self.phone_input.setFocus()
            return

        if not email:
            self.show_validation_hint("email", "⚠ Email is required")
            self.email_input.setFocus()
            return

        # Validate email format
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            self.show_validation_hint("email", "⚠ Invalid email format")
            self.email_input.setFocus()
            return

        if not password:
            self.show_validation_hint("password", "⚠ Password is required")
            self.password_input.setFocus()
            return

        # Check password length
        if len(password) < 6:
            self.show_validation_hint("password", "⚠ Password must be at least 6 characters")
            self.password_input.setFocus()
            return

        if not confirm_password:
            self.show_validation_hint("confirm_password", "⚠ Please confirm your password")
            self.confirm_password_input.setFocus()
            return

        # Check if passwords match
        if password != confirm_password:
            self.show_validation_hint("confirm_password", "⚠ Passwords do not match")
            self.confirm_password_input.clear()
            self.confirm_password_input.setFocus()
            return

        # Check terms and conditions
        if not self.terms_checkbox.isChecked():
            QMessageBox.warning(self, "Terms Required", "Please agree to the Terms & Conditions.")
            return

        # Disable button and show loading state
        self.signup_btn.setEnabled(False)
        self.signup_btn.setText("Creating account...")
        self.signup_btn.setCursor(Qt.WaitCursor)

        try:
            # Register with KeyringAuth (local storage)
            success, message = KeyringAuthFixed.register_user(username, fullname, phone, email, password)

            if not success:
                self.show_validation_hint("username", f"⚠ {message}")
                self.reset_signup_button()
                return

            # Save to MongoDB Atlas
            user_service = UserService()
            mongo_success, mongo_message = user_service.save_user(username, fullname, phone, email, password)

            if not mongo_success:
                print(f"⚠️ Database Warning: {mongo_message}")
            else:
                print(f"✅ User saved to MongoDB: {mongo_message}")

            # Show success feedback
            self.signup_btn.setText("✓ Account created!")
            self.signup_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #10b981, stop:1 #22c55e);
                }
            """)

            QMessageBox.information(self, "Success", "Account created successfully! Please sign in.")

            # Redirect to login
            if self.switch_to_login:
                self.switch_to_login()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"An error occurred during signup: {str(e)}"
            )
            self.reset_signup_button()

    def reset_signup_button(self):
        """Reset signup button to default state"""
        self.signup_btn.setEnabled(True)
        self.signup_btn.setText("Create Account")
        self.signup_btn.setCursor(Qt.PointingHandCursor)
        self.signup_btn.setStyleSheet("")

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == Qt.Key_Escape:
            self.fullname_input.clear()
            self.username_input.clear()
            self.phone_input.clear()
            self.email_input.clear()
            self.password_input.clear()
            self.confirm_password_input.clear()
            self.hide_validation_hints()
            self.fullname_input.setFocus()
        super().keyPressEvent(event)
