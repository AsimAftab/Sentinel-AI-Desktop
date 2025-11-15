from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
import os
from auth.keyring_auth import KeyringAuthFixed
from database.user_service import UserService  # Add this import


class SignupPage(QWidget):
    def __init__(self, switch_to_login=None):
        super().__init__()
        self.switch_to_login = switch_to_login

        # Use HBox layout for left-right division
        layout = QHBoxLayout(self)
        layout.setContentsMargins(80, 40, 80, 40)
        layout.setSpacing(20)

        # Left side - image section inside a box
        image_box = QFrame(self)
        image_box.setObjectName("imageBox")
        image_box.setFrameShape(QFrame.StyledPanel)
        image_box.setLineWidth(0)

        image_label = QLabel(image_box)
        image_label.setObjectName("imageLabel")
        image_path = os.path.join("ui", "assests", "image.png")
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            image_label.setPixmap(pixmap.scaled(500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            # Fallback with a modern icon/text
            image_label.setText("🛡️\n\nSentinel AI\n\nJoin the Future of Security")
            image_label.setStyleSheet("""
                color: #a78bfa;
                font-size: 18px;
                font-weight: 600;
                text-align: center;
                padding: 40px;
            """)
        image_label.setAlignment(Qt.AlignCenter)
        image_box.setLayout(QVBoxLayout())
        image_box.layout().addWidget(image_label)
        image_box.layout().setContentsMargins(20, 20, 20, 20)

        layout.addWidget(image_box, 1)  # Stretch factor to take up remaining space

        # Right side - signup form section
        form_layout = QVBoxLayout()
        form_layout.setAlignment(Qt.AlignCenter)
        form_layout.setSpacing(15)

        # Add a subtitle above the main title
        subtitle_label = QLabel("SENTINEL AI")
        subtitle_label.setStyleSheet("""
            color: #6b7280;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 2px;
        """)
        subtitle_label.setAlignment(Qt.AlignCenter)

        self.titleLabel = QLabel("Create Account")
        self.titleLabel.setObjectName("titleLabel")
        self.titleLabel.setAlignment(Qt.AlignCenter)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")

        self.fullname_input = QLineEdit()
        self.fullname_input.setPlaceholderText("Full Name")

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Phone Number")

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email Address")

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Password")

        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input.setPlaceholderText("Confirm Password")

        self.signup_btn = QPushButton("Sign Up")
        self.signup_btn.setObjectName("signupBtn")
        self.signup_btn.clicked.connect(self.validate_signup)

        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setObjectName("line")

        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setObjectName("line")

        or_label = QLabel("OR")
        or_label.setObjectName("orLabel")

        or_divider = QHBoxLayout()
        or_divider.addWidget(line1)
        or_divider.addWidget(or_label)
        or_divider.addWidget(line2)

        self.login_btn = QPushButton("Already have an account?")
        self.login_btn.setObjectName("loginBtn")
        if switch_to_login:
            self.login_btn.clicked.connect(switch_to_login)

        # Add widgets to form layout
        form_layout.addWidget(subtitle_label)
        form_layout.addWidget(self.titleLabel)
        form_layout.addSpacing(10)
        form_layout.addWidget(self.username_input)
        form_layout.addWidget(self.fullname_input)
        form_layout.addWidget(self.phone_input)
        form_layout.addWidget(self.email_input)
        form_layout.addWidget(self.password_input)
        form_layout.addWidget(self.confirm_password_input)
        form_layout.addSpacing(10)
        form_layout.addWidget(self.signup_btn)
        form_layout.addSpacing(15)
        form_layout.addLayout(or_divider)
        form_layout.addSpacing(15)
        form_layout.addWidget(self.login_btn)

        # Add form layout to the right side of the main layout
        layout.addLayout(form_layout, 2)  # Stretch factor to take more space on the right

    def validate_signup(self):
        username = self.username_input.text().strip()
        fullname = self.fullname_input.text().strip()
        phone = self.phone_input.text().strip()
        email = self.email_input.text().strip()
        password = self.password_input.text().strip()
        confirm_password = self.confirm_password_input.text().strip()

        if not all([username, fullname, phone, email, password, confirm_password]):
            QMessageBox.warning(self, "Input Error", "Please fill in all fields.")
            return

        if password != confirm_password:
            QMessageBox.warning(self, "Input Error", "Passwords do not match.")
            return

        try:
            # Register with KeyringAuth (local storage)
            success, message = KeyringAuthFixed.register_user(username, fullname, phone, email, password)

            if not success:
                QMessageBox.warning(self, "Signup Failed", message)
                return

            # Save to MongoDB Atlas
            user_service = UserService()
            mongo_success, mongo_message = user_service.save_user(username, fullname, phone, email, password)
            
            if not mongo_success:
                QMessageBox.warning(self, "Database Warning", 
                                  f"Account created locally but database save failed: {mongo_message}")
            else:
                print(f"✅ User saved to MongoDB: {mongo_message}")

            QMessageBox.information(self, "Signup Successful", "Account created successfully! Please log in.")
            if self.switch_to_login:
                self.switch_to_login()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred during signup: {str(e)}")