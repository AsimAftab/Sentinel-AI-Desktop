# database/settings_service.py
"""
User Settings Service - Manages user preferences in MongoDB.
"""

import logging
from config.database_config import DatabaseConfig
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _sanitize_input(value: str, field_name: str = "input") -> str:
    """Reject non-string inputs to prevent NoSQL injection via dicts/lists."""
    if not isinstance(value, str):
        raise ValueError(f"Invalid {field_name}: expected string, got {type(value).__name__}")
    return value


class SettingsService:
    """Service for managing user settings in MongoDB."""

    COLLECTION_NAME = "user_settings"

    def __init__(self):
        self.config = DatabaseConfig()

    def _get_settings_collection(self):
        """Return the settings collection using the shared connection pool."""
        client = self.config.get_client()
        db = client[self.config.MONGODB_DATABASE]
        return db[self.COLLECTION_NAME]

    def get_settings(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user settings from MongoDB."""
        try:
            user_id = _sanitize_input(user_id, "user_id")
            settings_collection = self._get_settings_collection()
            settings = settings_collection.find_one({"user_id": user_id})

            if settings:
                settings.pop("_id", None)
                return settings

            return self._get_default_settings(user_id)

        except Exception as e:
            logger.error("Error getting settings for user %s: %s", user_id, e)
            return self._get_default_settings(user_id)

    def update_settings(self, user_id: str, settings: Dict[str, Any]) -> bool:
        """Update user settings in MongoDB."""
        try:
            user_id = _sanitize_input(user_id, "user_id")
            settings_collection = self._get_settings_collection()
            settings["user_id"] = user_id

            result = settings_collection.update_one(
                {"user_id": user_id}, {"$set": settings}, upsert=True
            )
            return result.acknowledged

        except Exception as e:
            logger.error("Error updating settings for user %s: %s", user_id, e)
            return False

    def get_llm_settings(self, user_id: str) -> Dict[str, Any]:
        """Get LLM-specific settings with support for multiple providers."""
        settings = self.get_settings(user_id)
        if settings and "llm" in settings:
            return self._normalize_llm_settings(settings["llm"])

        # Default LLM settings with multiple provider support
        return {
            "primary_provider": "azure",
            "temperature": 0,
            "fallback_enabled": False,
            "providers": {
                "azure": {
                    "enabled": True,
                    "endpoint": "",
                    "api_version": "",
                    "deployment_name": "",
                    "api_key": "",
                },
                "ollama": {
                    "enabled": False,
                    "model": "qwen2.5",
                    "base_url": "http://localhost:11434",
                    "timeout": 120.0,
                },
                "openai": {
                    "enabled": False,
                    "api_key": "",
                    "model": "gpt-4",
                },
                "zhipu": {
                    "enabled": False,
                    "api_key": "",
                    "model": "glm-4-flash",
                    "base_url": "https://api.z.ai/api/coding/paas/v4",
                },
            },
            "agent_assignments": {
                "Browser": None,
                "Music": None,
                "Meeting": None,
                "System": None,
                "Productivity": None,
                "Notes": None,
                "Email": None,
                "Supervisor": None,
            },
        }

    def _normalize_llm_settings(self, llm_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize legacy or partial LLM settings into the current structure."""
        defaults = self._get_default_settings("temp_user")["llm"]
        normalized = {
            "primary_provider": defaults["primary_provider"],
            "temperature": defaults["temperature"],
            "fallback_enabled": defaults["fallback_enabled"],
            "providers": {
                "azure": defaults["providers"]["azure"].copy(),
                "ollama": defaults["providers"]["ollama"].copy(),
                "openai": defaults["providers"]["openai"].copy(),
                "zhipu": defaults["providers"]["zhipu"].copy(),
            },
            "agent_assignments": defaults["agent_assignments"].copy(),
        }

        if not isinstance(llm_settings, dict):
            return normalized

        if "primary_provider" in llm_settings:
            # New schema (or partially new): deep-merge with defaults
            normalized["primary_provider"] = llm_settings.get(
                "primary_provider", normalized["primary_provider"]
            )
            normalized["temperature"] = llm_settings.get("temperature", normalized["temperature"])
            normalized["fallback_enabled"] = llm_settings.get(
                "fallback_enabled", normalized["fallback_enabled"]
            )

            providers = llm_settings.get("providers", {})
            for provider_name in ["azure", "ollama", "openai", "zhipu"]:
                if isinstance(providers.get(provider_name), dict):
                    normalized["providers"][provider_name].update(providers[provider_name])

            assignments = llm_settings.get("agent_assignments", {})
            if isinstance(assignments, dict):
                for agent in normalized["agent_assignments"]:
                    normalized["agent_assignments"][agent] = assignments.get(
                        agent, normalized["agent_assignments"][agent]
                    )
            return normalized

        # Legacy schema fallback
        provider = str(llm_settings.get("provider", normalized["primary_provider"])).lower()
        if provider in ("azure", "ollama", "openai", "zhipu"):
            normalized["primary_provider"] = provider

        normalized["temperature"] = llm_settings.get("temperature", normalized["temperature"])
        normalized["fallback_enabled"] = llm_settings.get(
            "fallback_enabled", normalized["fallback_enabled"]
        )

        normalized["providers"]["azure"].update(
            {
                "enabled": llm_settings.get(
                    "azure_enabled", normalized["primary_provider"] == "azure"
                ),
                "endpoint": llm_settings.get(
                    "azure_endpoint", normalized["providers"]["azure"]["endpoint"]
                ),
                "api_key": llm_settings.get(
                    "azure_api_key", normalized["providers"]["azure"]["api_key"]
                ),
                "deployment_name": llm_settings.get(
                    "azure_deployment_name", normalized["providers"]["azure"]["deployment_name"]
                ),
                "api_version": llm_settings.get(
                    "azure_api_version", normalized["providers"]["azure"]["api_version"]
                ),
            }
        )

        normalized["providers"]["ollama"].update(
            {
                "enabled": llm_settings.get(
                    "ollama_enabled", normalized["primary_provider"] == "ollama"
                ),
                "model": llm_settings.get(
                    "ollama_model", normalized["providers"]["ollama"]["model"]
                ),
                "base_url": llm_settings.get(
                    "ollama_base_url", normalized["providers"]["ollama"]["base_url"]
                ),
                "timeout": llm_settings.get(
                    "ollama_timeout", normalized["providers"]["ollama"]["timeout"]
                ),
            }
        )

        normalized["providers"]["openai"].update(
            {
                "enabled": llm_settings.get(
                    "openai_enabled", normalized["primary_provider"] == "openai"
                ),
                "api_key": llm_settings.get(
                    "openai_api_key", normalized["providers"]["openai"]["api_key"]
                ),
                "model": llm_settings.get(
                    "openai_model", normalized["providers"]["openai"]["model"]
                ),
            }
        )

        return normalized

    def update_llm_settings(self, user_id: str, llm_settings: Dict[str, Any]) -> bool:
        """Update LLM-specific settings."""
        settings = self.get_settings(user_id) or {}
        settings["llm"] = llm_settings
        return self.update_settings(user_id, settings)

    def _get_default_settings(self, user_id: str) -> Dict[str, Any]:
        """Get default settings for a new user."""
        return {
            "user_id": user_id,
            "llm": {
                "primary_provider": "azure",
                "temperature": 0,
                "fallback_enabled": False,
                "providers": {
                    "azure": {
                        "enabled": True,
                        "endpoint": "",
                        "api_version": "",
                        "deployment_name": "",
                        "api_key": "",
                    },
                    "ollama": {
                        "enabled": False,
                        "model": "qwen2.5",
                        "base_url": "http://localhost:11434",
                        "timeout": 120.0,
                    },
                    "openai": {
                        "enabled": False,
                        "api_key": "",
                        "model": "gpt-4",
                    },
                    "zhipu": {
                        "enabled": False,
                        "api_key": "",
                        "model": "glm-4-flash",
                        "base_url": "https://api.z.ai/api/coding/paas/v4",
                    },
                },
                "agent_assignments": {
                    "Browser": None,
                    "Music": None,
                    "Meeting": None,
                    "System": None,
                    "Productivity": None,
                    "Notes": None,
                    "Email": None,
                    "Supervisor": None,
                },
            },
            "voice": {
                "tts_enabled": True,
                "voice_id": "EXAVITQu4vr4xnSDxMaL",  # Sarah
            },
        }
