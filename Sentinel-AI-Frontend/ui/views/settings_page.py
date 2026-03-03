import logging
import os

from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QMessageBox,
    QComboBox,
    QLineEdit,
    QFormLayout,
    QGroupBox,
    QScrollArea,
    QDoubleSpinBox,
    QCheckBox,
    QGridLayout,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont
import qtawesome as qta
from database.settings_service import SettingsService

logger = logging.getLogger(__name__)


class SettingsPage(QWidget):
    """Settings page for managing LLM provider configuration."""

    settings_saved = pyqtSignal()  # Signal emitted when settings are saved

    def __init__(self, main_app=None, username=None, user_id=None):
        super().__init__()
        self.main_app = main_app
        self.username = username
        self.fullname = username or "User"
        self.user_id = user_id
        self.settings_service = SettingsService()

        self.setObjectName("settingsPage")
        self._load_stylesheet()
        self._init_ui()
        self._load_settings()

    def _load_stylesheet(self):
        """Load settings page stylesheet."""
        qss_path = os.path.join(os.path.dirname(__file__), "..", "qss", "settings.qss")
        try:
            with open(qss_path, "r") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            logger.warning("Failed to load settings.qss: %s", e)

    def _init_ui(self):
        """Initialize the settings UI with modern dashboard-like design."""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== LEFT SIDEBAR =====
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)

        # ===== MAIN CONTENT AREA =====
        content_area = self._create_content_area()
        main_layout.addWidget(content_area)

        self.setLayout(main_layout)

    def _create_sidebar(self):
        """Create the left navigation sidebar."""
        sidebar = QFrame()
        sidebar.setObjectName("settingsSidebar")
        sidebar.setFixedWidth(200)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 24, 16, 24)
        sidebar_layout.setSpacing(24)
        sidebar_layout.setAlignment(Qt.AlignTop)

        # App branding
        app_title = QLabel("Sentinel-AI")
        app_title.setObjectName("sidebarAppTitle")
        sidebar_layout.addWidget(app_title)

        # Greeting
        greeting = QLabel(f"Hey, {self.fullname}! 👋")
        greeting.setObjectName("sidebarGreeting")
        sidebar_layout.addWidget(greeting)

        sidebar_layout.addSpacing(20)

        # Navigation menu
        nav_items = [("Dashboard", "fa5s.th-large", False), ("Settings", "fa5s.cog", True)]

        for label, icon_name, is_active in nav_items:
            btn = self._create_nav_button(label, icon_name, is_active)
            if label == "Dashboard":
                btn.clicked.connect(self._go_back)
            sidebar_layout.addWidget(btn)

        # Push everything down
        sidebar_layout.addStretch()

        # User profile card at bottom
        profile_card = self._create_profile_card()
        sidebar_layout.addWidget(profile_card)

        return sidebar

    def _create_nav_button(self, label, icon_name, is_active=False):
        """Create a navigation button with icon."""
        btn = QPushButton(f"  {label}")
        btn.setObjectName("settingsNavBtnActive" if is_active else "settingsNavBtn")
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

    def _create_profile_card(self):
        """Create user profile card at bottom of sidebar."""
        profile_card = QFrame()
        profile_card.setObjectName("settingsProfileCard")

        profile_layout = QHBoxLayout(profile_card)
        profile_layout.setContentsMargins(12, 12, 12, 12)
        profile_layout.setSpacing(10)

        # Avatar circle with first letter of name
        avatar_letter = self.fullname[0].upper() if self.fullname else "U"
        avatar = QLabel(avatar_letter)
        avatar.setObjectName("settingsAvatar")
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignCenter)
        profile_layout.addWidget(avatar)

        # Name and email in vertical layout
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel(self.fullname)
        name_label.setObjectName("settingsProfileName")
        name_label.setWordWrap(False)

        email_label = QLabel((self.username or "user") + "@sentinel.ai")
        email_label.setObjectName("settingsProfileEmail")
        email_label.setWordWrap(False)

        info_layout.addWidget(name_label)
        info_layout.addWidget(email_label)

        profile_layout.addLayout(info_layout)

        return profile_card

    def _create_content_area(self):
        """Create the main content area with settings content."""
        content_widget = QWidget()
        content_widget.setObjectName("settingsContentArea")

        # Create scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("settingsScrollArea")

        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(40, 30, 40, 30)
        content_layout.setSpacing(24)

        # Header section
        header_layout = QHBoxLayout()

        # Title and subtitle
        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)

        settings_title = QLabel("Settings")
        settings_title.setObjectName("settingsPageTitle")

        settings_subtitle = QLabel("Configure your LLM providers and preferences")
        settings_subtitle.setObjectName("settingsPageSubtitle")

        title_layout.addWidget(settings_title)
        title_layout.addWidget(settings_subtitle)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        content_layout.addLayout(header_layout)

        # LLM Provider Settings Group
        llm_group = self._create_llm_settings_group()
        content_layout.addWidget(llm_group)

        content_layout.addStretch()

        scroll.setWidget(content_widget)

        # Wrap scroll in a layout
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addWidget(scroll)

        return wrapper

    def _create_llm_settings_group(self):
        """Create LLM provider settings group with modern card styling."""
        group = QGroupBox("LLM Providers")
        group.setObjectName("settingsCardGroup")
        layout = QVBoxLayout()
        layout.setSpacing(20)

        # Primary Provider Section
        primary_section = QFrame()
        primary_section.setObjectName("settingsSection")
        primary_layout = QFormLayout()
        primary_layout.setSpacing(12)

        primary_label = QLabel("Primary Provider")
        primary_label.setObjectName("settingsSectionLabel")
        primary_layout.addRow(primary_label)

        self.primary_provider_combo = QComboBox()
        self.primary_provider_combo.addItems(
            ["Azure OpenAI", "Ollama (Local)", "OpenAI", "Zhipu AI (GLM)"]
        )
        self.primary_provider_combo.setObjectName("settingsInput")
        self.primary_provider_combo.currentTextChanged.connect(self._on_primary_provider_changed)
        primary_layout.addRow(self.primary_provider_combo)

        # Temperature
        temp_label = QLabel("Temperature")
        temp_label.setObjectName("settingsSectionLabel")
        primary_layout.addRow(temp_label)

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.0)
        self.temperature_spin.setObjectName("settingsInput")
        primary_layout.addRow(self.temperature_spin)

        # Fallback enabled
        self.fallback_enabled = QCheckBox("Enable Fallback Provider")
        self.fallback_enabled.setObjectName("settingsCheckbox")
        primary_layout.addRow(self.fallback_enabled)

        primary_section.setLayout(primary_layout)
        layout.addWidget(primary_section)

        # Provider Cards Grid
        providers_grid = QGridLayout()
        providers_grid.setSpacing(16)
        providers_grid.setHorizontalSpacing(16)

        # Azure OpenAI Card
        azure_card = self._create_provider_card("Azure OpenAI", "fa5b.microsoft")
        azure_card_layout = azure_card.layout()

        self.azure_enabled = QCheckBox("Enable Azure OpenAI")
        self.azure_enabled.setObjectName("settingsCheckbox")
        azure_card_layout.addRow(self.azure_enabled)

        self.azure_endpoint = QLineEdit()
        self.azure_endpoint.setPlaceholderText("https://your-resource.openai.azure.com/")
        self.azure_endpoint.setObjectName("settingsInput")
        azure_card_layout.addRow("Endpoint:", self.azure_endpoint)

        self.azure_api_key = QLineEdit()
        self.azure_api_key.setPlaceholderText("Enter your Azure OpenAI API key")
        self.azure_api_key.setEchoMode(QLineEdit.Password)
        self.azure_api_key.setObjectName("settingsInput")
        azure_card_layout.addRow("API Key:", self.azure_api_key)

        self.azure_deployment = QLineEdit()
        self.azure_deployment.setPlaceholderText("gpt-4")
        self.azure_deployment.setObjectName("settingsInput")
        azure_card_layout.addRow("Deployment:", self.azure_deployment)

        self.azure_api_version = QLineEdit()
        self.azure_api_version.setPlaceholderText("2024-02-15-preview")
        self.azure_api_version.setObjectName("settingsInput")
        azure_card_layout.addRow("API Version:", self.azure_api_version)

        providers_grid.addWidget(azure_card, 0, 0)

        # Ollama Card
        ollama_card = self._create_provider_card("Ollama (Local)", "fa5b.server")
        ollama_card_layout = ollama_card.layout()

        self.ollama_enabled = QCheckBox("Enable Ollama")
        self.ollama_enabled.setObjectName("settingsCheckbox")
        ollama_card_layout.addRow(self.ollama_enabled)

        self.ollama_model = QLineEdit()
        self.ollama_model.setPlaceholderText("qwen2.5")
        self.ollama_model.setObjectName("settingsInput")
        ollama_card_layout.addRow("Model:", self.ollama_model)

        self.ollama_base_url = QLineEdit()
        self.ollama_base_url.setPlaceholderText("http://localhost:11434")
        self.ollama_base_url.setObjectName("settingsInput")
        ollama_card_layout.addRow("Base URL:", self.ollama_base_url)

        self.ollama_timeout = QDoubleSpinBox()
        self.ollama_timeout.setRange(30.0, 300.0)
        self.ollama_timeout.setSingleStep(10.0)
        self.ollama_timeout.setValue(120.0)
        self.ollama_timeout.setObjectName("settingsInput")
        ollama_card_layout.addRow("Timeout (s):", self.ollama_timeout)

        providers_grid.addWidget(ollama_card, 0, 1)

        # OpenAI Card
        openai_card = self._create_provider_card("OpenAI", "fa5b.openai")
        openai_card_layout = openai_card.layout()

        self.openai_enabled = QCheckBox("Enable OpenAI")
        self.openai_enabled.setObjectName("settingsCheckbox")
        openai_card_layout.addRow(self.openai_enabled)

        self.openai_api_key = QLineEdit()
        self.openai_api_key.setPlaceholderText("sk-...")
        self.openai_api_key.setEchoMode(QLineEdit.Password)
        self.openai_api_key.setObjectName("settingsInput")
        openai_card_layout.addRow("API Key:", self.openai_api_key)

        self.openai_model = QLineEdit()
        self.openai_model.setPlaceholderText("gpt-4")
        self.openai_model.setObjectName("settingsInput")
        openai_card_layout.addRow("Model:", self.openai_model)

        providers_grid.addWidget(openai_card, 1, 0)

        # Zhipu AI (GLM) Card
        zhipu_card = self._create_provider_card("Zhipu AI (GLM)", "fa5s.robot")
        zhipu_card_layout = zhipu_card.layout()

        self.zhipu_enabled = QCheckBox("Enable Zhipu AI")
        self.zhipu_enabled.setObjectName("settingsCheckbox")
        zhipu_card_layout.addRow(self.zhipu_enabled)

        self.zhipu_api_key = QLineEdit()
        self.zhipu_api_key.setPlaceholderText("Enter your Zhipu AI API key")
        self.zhipu_api_key.setEchoMode(QLineEdit.Password)
        self.zhipu_api_key.setObjectName("settingsInput")
        zhipu_card_layout.addRow("API Key:", self.zhipu_api_key)

        self.zhipu_model = QLineEdit()
        self.zhipu_model.setPlaceholderText("glm-4-flash")
        self.zhipu_model.setObjectName("settingsInput")
        zhipu_card_layout.addRow("Model:", self.zhipu_model)

        self.zhipu_base_url = QLineEdit()
        self.zhipu_base_url.setPlaceholderText("https://api.z.ai/api/coding/paas/v4")
        self.zhipu_base_url.setObjectName("settingsInput")
        zhipu_card_layout.addRow("Base URL:", self.zhipu_base_url)

        providers_grid.addWidget(zhipu_card, 1, 1)

        layout.addLayout(providers_grid)

        # Agent Assignments Section
        agent_section = QGroupBox("Agent-Specific Providers (Optional)")
        agent_section.setObjectName("settingsCardGroup")
        agent_layout = QFormLayout()
        agent_layout.setSpacing(12)

        agents = [
            ("Browser", "fa5s.globe"),
            ("Music", "fa5s.music"),
            ("Meeting", "fa5s.video"),
            ("System", "fa5s.sliders-h"),
            ("Productivity", "fa5s.clock"),
            ("Notes", "fa5s.sticky-note"),
            ("Email", "fa5s.envelope"),
            ("Supervisor", "fa5s.sitemap"),
        ]

        for agent_name, icon_name in agents:
            agent_label = QLabel(f"{agent_name} Agent:")
            agent_label.setObjectName("settingsSectionLabel")
            agent_layout.addRow(agent_label)

            combo = QComboBox()
            combo.addItems(
                ["Use Primary", "Azure OpenAI", "Ollama (Local)", "OpenAI", "Zhipu AI (GLM)"]
            )
            combo.setObjectName("settingsInput")

            # Store reference for later access
            setattr(self, f"{agent_name.lower()}_provider", combo)
            agent_layout.addRow(combo)

        agent_section.setLayout(agent_layout)
        layout.addWidget(agent_section)

        # Save Button
        save_layout = QHBoxLayout()
        save_layout.addSpacing(40)

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setIcon(qta.icon("fa5s.save", color="#fff"))
        self.save_btn.setFixedHeight(45)
        self.save_btn.setMinimumWidth(200)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setObjectName("settingsSaveButton")
        self.save_btn.clicked.connect(self._save_settings)
        save_layout.addWidget(self.save_btn)

        save_layout.addStretch()
        layout.addLayout(save_layout)

        group.setLayout(layout)
        return group

    def _create_provider_card(self, title: str, icon_name: str):
        """Create a styled provider card."""
        card = QFrame()
        card.setObjectName("settingsProviderCard")

        card_layout = QFormLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()

        try:
            icon = qta.icon(icon_name, color="#3b82f6", scale_factor=1.0)
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(24, 24))
            header_layout.addWidget(icon_label)
        except:
            pass

        title_label = QLabel(title)
        title_label.setObjectName("settingsCardTitle")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        card_layout.addRow(header_layout)

        return card

    def _on_primary_provider_changed(self, provider):
        """Handle primary provider change — auto-enable the selected provider."""
        logger.info("Primary provider changed to: %s", provider)

        # Map display name to the corresponding enable checkbox
        checkbox_map = {
            "Azure OpenAI": self.azure_enabled,
            "Ollama (Local)": self.ollama_enabled,
            "OpenAI": self.openai_enabled,
            "Zhipu AI (GLM)": self.zhipu_enabled,
        }
        checkbox = checkbox_map.get(provider)
        if checkbox and not checkbox.isChecked():
            checkbox.setChecked(True)

    def _load_settings(self):
        """Load current settings from database."""
        if not self.user_id:
            return

        try:
            settings = self.settings_service.get_llm_settings(self.user_id)

            # Set primary provider
            provider_map = {
                "azure": "Azure OpenAI",
                "ollama": "Ollama (Local)",
                "openai": "OpenAI",
                "zhipu": "Zhipu AI (GLM)",
            }
            primary_provider = provider_map.get(
                settings.get("primary_provider", "azure"), "Azure OpenAI"
            )
            self.primary_provider_combo.setCurrentText(primary_provider)

            # Set temperature
            self.temperature_spin.setValue(settings.get("temperature", 0.0))

            # Set fallback enabled
            self.fallback_enabled.setChecked(settings.get("fallback_enabled", False))

            # Load provider settings
            providers = settings.get("providers", {})

            # Load Azure settings
            if "azure" in providers:
                azure = providers["azure"]
                self.azure_enabled.setChecked(azure.get("enabled", True))
                self.azure_endpoint.setText(azure.get("endpoint", ""))
                self.azure_api_key.setText(azure.get("api_key", ""))
                self.azure_deployment.setText(azure.get("deployment_name", ""))
                self.azure_api_version.setText(azure.get("api_version", ""))

            # Load Ollama settings
            if "ollama" in providers:
                ollama = providers["ollama"]
                self.ollama_enabled.setChecked(ollama.get("enabled", False))
                self.ollama_model.setText(ollama.get("model", "qwen2.5"))
                self.ollama_base_url.setText(ollama.get("base_url", "http://localhost:11434"))
                self.ollama_timeout.setValue(ollama.get("timeout", 120.0))

            # Load OpenAI settings
            if "openai" in providers:
                openai = providers["openai"]
                self.openai_enabled.setChecked(openai.get("enabled", False))
                self.openai_api_key.setText(openai.get("api_key", ""))
                self.openai_model.setText(openai.get("model", "gpt-4"))

            # Load Zhipu AI settings
            if "zhipu" in providers:
                zhipu = providers["zhipu"]
                self.zhipu_enabled.setChecked(zhipu.get("enabled", False))
                self.zhipu_api_key.setText(zhipu.get("api_key", ""))
                self.zhipu_model.setText(zhipu.get("model", "glm-4-flash"))
                self.zhipu_base_url.setText(
                    zhipu.get("base_url", "https://api.z.ai/api/coding/paas/v4")
                )

            # Load agent assignments
            agent_assignments = settings.get("agent_assignments", {})

            # Helper to set agent provider combo
            def set_agent_provider(combo, agent_name):
                assigned = agent_assignments.get(agent_name)
                if assigned:
                    combo.setCurrentText(provider_map.get(assigned, "Use Primary"))
                else:
                    combo.setCurrentText("Use Primary")

            set_agent_provider(self.browser_provider, "Browser")
            set_agent_provider(self.music_provider, "Music")
            set_agent_provider(self.meeting_provider, "Meeting")
            set_agent_provider(self.system_provider, "System")
            set_agent_provider(self.productivity_provider, "Productivity")
            set_agent_provider(self.notes_provider, "Notes")
            set_agent_provider(self.email_provider, "Email")
            set_agent_provider(self.supervisor_provider, "Supervisor")

        except Exception as e:
            logger.warning("Failed to load settings: %s", e)

    def _save_settings(self):
        """Save settings to database and update backend .env file."""
        if not self.user_id:
            QMessageBox.warning(self, "Error", "User ID not found. Cannot save settings.")
            return

        try:
            # Map UI provider name to backend provider name
            provider_map = {
                "Azure OpenAI": "azure",
                "Ollama (Local)": "ollama",
                "OpenAI": "openai",
                "Zhipu AI (GLM)": "zhipu",
            }
            primary_provider = provider_map[self.primary_provider_combo.currentText()]

            # Helper to get provider from combo (None for "Use Primary")
            def get_provider_from_combo(combo):
                text = combo.currentText()
                return provider_map.get(text) if text != "Use Primary" else None

            # Build settings object
            settings = {
                "primary_provider": primary_provider,
                "temperature": self.temperature_spin.value(),
                "fallback_enabled": self.fallback_enabled.isChecked(),
                "providers": {
                    "azure": {
                        "enabled": self.azure_enabled.isChecked(),
                        "endpoint": self.azure_endpoint.text().strip(),
                        "api_key": self.azure_api_key.text().strip(),
                        "deployment_name": self.azure_deployment.text().strip(),
                        "api_version": self.azure_api_version.text().strip(),
                    },
                    "ollama": {
                        "enabled": self.ollama_enabled.isChecked(),
                        "model": self.ollama_model.text().strip() or "qwen2.5",
                        "base_url": self.ollama_base_url.text().strip() or "http://localhost:11434",
                        "timeout": self.ollama_timeout.value(),
                    },
                    "openai": {
                        "enabled": self.openai_enabled.isChecked(),
                        "api_key": self.openai_api_key.text().strip(),
                        "model": self.openai_model.text().strip() or "gpt-4",
                    },
                    "zhipu": {
                        "enabled": self.zhipu_enabled.isChecked(),
                        "api_key": self.zhipu_api_key.text().strip(),
                        "model": self.zhipu_model.text().strip() or "glm-4-flash",
                        "base_url": self.zhipu_base_url.text().strip()
                        or "https://api.z.ai/api/coding/paas/v4",
                    },
                },
                "agent_assignments": {
                    "Browser": get_provider_from_combo(self.browser_provider),
                    "Music": get_provider_from_combo(self.music_provider),
                    "Meeting": get_provider_from_combo(self.meeting_provider),
                    "System": get_provider_from_combo(self.system_provider),
                    "Productivity": get_provider_from_combo(self.productivity_provider),
                    "Notes": get_provider_from_combo(self.notes_provider),
                    "Email": get_provider_from_combo(self.email_provider),
                    "Supervisor": get_provider_from_combo(self.supervisor_provider),
                },
            }

            enabled_providers = [
                name for name, cfg in settings["providers"].items() if cfg.get("enabled")
            ]
            if not enabled_providers:
                QMessageBox.warning(
                    self, "Validation Error", "Enable at least one LLM provider before saving."
                )
                return

            if not settings["providers"][primary_provider]["enabled"]:
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    f"Primary provider '{primary_provider}' must be enabled.",
                )
                return

            invalid_assignments = [
                f"{agent}: {provider}"
                for agent, provider in settings["agent_assignments"].items()
                if provider and not settings["providers"].get(provider, {}).get("enabled", False)
            ]
            if invalid_assignments:
                details = "\n".join(invalid_assignments)
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    "Some agent assignments point to disabled providers:\n\n" + details,
                )
                return

            # Save to database
            if not self.settings_service.update_llm_settings(self.user_id, settings):
                raise RuntimeError("Failed to persist settings to database.")

            # Update backend .env file
            self._update_backend_env(settings)

            QMessageBox.information(
                self,
                "Success",
                "Settings saved successfully!\n\nPlease restart the application for changes to take effect.",
            )
            self.settings_saved.emit()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings:\n\n{str(e)}")
            logger.error("Save settings error: %s", e)

    def _update_backend_env(self, settings):
        """Update backend .env file with new LLM settings."""
        try:
            backend_env_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "Sentinel-AI-Backend",
                ".env",
            )

            # Read existing .env file
            env_lines = []
            if os.path.exists(backend_env_path):
                with open(backend_env_path, "r") as f:
                    env_lines = f.readlines()

            # Get primary provider
            primary_provider = settings["primary_provider"]
            providers = settings["providers"]

            # Update LLM settings with primary provider
            updated_vars = {
                "LLM_PROVIDER": primary_provider,
                "LLM_TEMPERATURE": str(settings["temperature"]),
                "LLM_FALLBACK_ENABLED": str(settings["fallback_enabled"]),
            }

            # Update all provider settings in .env
            if "azure" in providers:
                azure = providers["azure"]
                updated_vars.update(
                    {
                        "AZURE_OPENAI_ENDPOINT": azure["endpoint"],
                        "AZURE_OPENAI_API_KEY": azure["api_key"],
                        "AZURE_OPENAI_DEPLOYMENT_NAME": azure["deployment_name"],
                        "AZURE_OPENAI_API_VERSION": azure["api_version"],
                        "AZURE_OPENAI_ENABLED": str(azure["enabled"]),
                    }
                )

            if "ollama" in providers:
                ollama = providers["ollama"]
                updated_vars.update(
                    {
                        "OLLAMA_MODEL": ollama["model"],
                        "OLLAMA_BASE_URL": ollama["base_url"],
                        "OLLAMA_TIMEOUT": str(ollama["timeout"]),
                        "OLLAMA_ENABLED": str(ollama["enabled"]),
                    }
                )

            if "openai" in providers:
                openai = providers["openai"]
                updated_vars.update(
                    {
                        "OPENAI_API_KEY": openai["api_key"],
                        "OPENAI_MODEL": openai["model"],
                        "OPENAI_ENABLED": str(openai["enabled"]),
                    }
                )

            if "zhipu" in providers:
                zhipu = providers["zhipu"]
                updated_vars.update(
                    {
                        "ZHIPU_API_KEY": zhipu["api_key"],
                        "ZHIPU_MODEL": zhipu["model"],
                        "ZHIPU_BASE_URL": zhipu["base_url"],
                        "ZHIPU_ENABLED": str(zhipu["enabled"]),
                    }
                )

            # Update agent assignments
            agent_assignments = settings.get("agent_assignments", {})
            for agent, provider in agent_assignments.items():
                if provider:
                    updated_vars[f"LLM_AGENT_{agent.upper()}"] = provider
                else:
                    updated_vars[f"LLM_AGENT_{agent.upper()}"] = ""

            # Update or append variables
            updated_keys = set()
            for i, line in enumerate(env_lines):
                for key, value in updated_vars.items():
                    if line.startswith(f"{key}="):
                        env_lines[i] = f"{key}={value}\n"
                        updated_keys.add(key)

            # Append new variables that weren't found
            for key, value in updated_vars.items():
                if key not in updated_keys:
                    env_lines.append(f"{key}={value}\n")

            # Write back to .env file
            with open(backend_env_path, "w") as f:
                f.writelines(env_lines)

            logger.info("Backend .env updated with %s as primary provider", primary_provider)

        except Exception as e:
            logger.warning("Failed to update backend .env: %s", e)
            raise

    def _go_back(self):
        """Navigate back to dashboard."""
        if self.main_app:
            self.main_app.show_dashboard_from_settings()
