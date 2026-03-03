# src/utils/llm_config.py
"""
LLM Configuration Manager - Loads LLM settings from MongoDB or environment variables.
Supports multiple LLM providers with primary provider selection and agent-specific assignments.
"""

import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

_log = logging.getLogger("llm_config")


class LLMConfig:
    """Manages LLM provider configuration with multiple provider support."""

    # Default configuration
    DEFAULT_PROVIDER = "azure"
    DEFAULT_TEMPERATURE = 0

    # Supported providers
    PROVIDERS = {
        "azure": "Azure OpenAI",
        "ollama": "Ollama (Local)",
        "openai": "OpenAI",
        "zhipu": "Zhipu AI (GLM)",
    }

    def __init__(self):
        self.config = self._load_config()
        self._llm_instances = {}  # Cache for LLM instances
        self._validate_config()

    def _validate_config(self):
        """Validate that at least one LLM provider is enabled and configured. Fail fast."""
        enabled = self.get_enabled_providers()
        if not enabled:
            raise RuntimeError(
                "No LLM provider is enabled. Please configure at least one provider in your .env file.\n"
                "  - For Azure: set AZURE_OPENAI_ENABLED=true and provide endpoint/key/deployment\n"
                "  - For OpenAI: set OPENAI_ENABLED=true and provide OPENAI_API_KEY\n"
                "  - For Ollama: set OLLAMA_ENABLED=true and ensure Ollama is running\n"
                "  - For Zhipu AI: set ZHIPU_ENABLED=true and provide ZHIPU_API_KEY"
            )

        primary = self.config["primary_provider"]
        primary_cfg = self.config["providers"].get(primary, {})

        # Validate primary provider has required credentials
        if primary == "azure":
            missing = [
                k
                for k in ("endpoint", "api_key", "deployment_name", "api_version")
                if not primary_cfg.get(k)
            ]
            if missing:
                raise RuntimeError(
                    f"Azure OpenAI is the primary provider but is missing required config: {missing}.\n"
                    "Please set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, "
                    "AZURE_OPENAI_DEPLOYMENT_NAME, and AZURE_OPENAI_API_VERSION in your .env file."
                )
        elif primary == "openai":
            if not primary_cfg.get("api_key"):
                raise RuntimeError(
                    "OpenAI is the primary provider but OPENAI_API_KEY is not set in your .env file."
                )
        elif primary == "ollama":
            if not primary_cfg.get("base_url"):
                raise RuntimeError(
                    "Ollama is the primary provider but OLLAMA_BASE_URL is not configured."
                )
        elif primary == "zhipu":
            if not primary_cfg.get("api_key"):
                raise RuntimeError(
                    "Zhipu AI is the primary provider but ZHIPU_API_KEY is not set in your .env file."
                )

    def _load_config(self) -> Dict[str, Any]:
        """Load LLM configuration from environment variables."""
        provider = (
            self._normalize_provider(os.getenv("LLM_PROVIDER", self.DEFAULT_PROVIDER))
            or self.DEFAULT_PROVIDER
        )
        fallback_enabled = os.getenv("LLM_FALLBACK_ENABLED", "false").lower() == "true"

        config = {
            "primary_provider": provider,
            "temperature": float(os.getenv("LLM_TEMPERATURE", str(self.DEFAULT_TEMPERATURE))),
            "fallback_enabled": fallback_enabled,
            "providers": {
                "azure": {
                    "enabled": os.getenv("AZURE_OPENAI_ENABLED", "true").lower() == "true",
                    "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
                    "api_version": os.getenv("AZURE_OPENAI_API_VERSION"),
                    "deployment_name": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                    "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
                },
                "ollama": {
                    "enabled": os.getenv("OLLAMA_ENABLED", "false").lower() == "true",
                    "model": os.getenv("OLLAMA_MODEL", "qwen2.5"),
                    "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                    "timeout": float(os.getenv("OLLAMA_TIMEOUT", "120.0")),
                },
                "openai": {
                    "enabled": os.getenv("OPENAI_ENABLED", "false").lower() == "true",
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "model": os.getenv("OPENAI_MODEL", "gpt-4"),
                },
                "zhipu": {
                    "enabled": os.getenv("ZHIPU_ENABLED", "false").lower() == "true",
                    "api_key": os.getenv("ZHIPU_API_KEY"),
                    "model": os.getenv("ZHIPU_MODEL", "glm-4-flash"),
                    "base_url": os.getenv(
                        "ZHIPU_BASE_URL", "https://api.z.ai/api/coding/paas/v4"
                    ),
                },
            },
            "agent_assignments": {
                "Browser": self._normalize_provider(os.getenv("LLM_AGENT_BROWSER", "")),
                "Music": self._normalize_provider(os.getenv("LLM_AGENT_MUSIC", "")),
                "Meeting": self._normalize_provider(os.getenv("LLM_AGENT_MEETING", "")),
                "System": self._normalize_provider(os.getenv("LLM_AGENT_SYSTEM", "")),
                "Productivity": self._normalize_provider(os.getenv("LLM_AGENT_PRODUCTIVITY", "")),
                "Notes": self._normalize_provider(os.getenv("LLM_AGENT_NOTES", "")),
                "Email": self._normalize_provider(os.getenv("LLM_AGENT_EMAIL", "")),
                "Supervisor": self._normalize_provider(os.getenv("LLM_AGENT_SUPERVISOR", "")),
            },
            # Per-agent temperature overrides (fall back to global LLM_TEMPERATURE if not set)
            "agent_temperatures": {
                "Browser": self._parse_temperature(os.getenv("LLM_AGENT_BROWSER_TEMPERATURE", "")),
                "Music": self._parse_temperature(os.getenv("LLM_AGENT_MUSIC_TEMPERATURE", "")),
                "Meeting": self._parse_temperature(os.getenv("LLM_AGENT_MEETING_TEMPERATURE", "")),
                "System": self._parse_temperature(os.getenv("LLM_AGENT_SYSTEM_TEMPERATURE", "")),
                "Productivity": self._parse_temperature(
                    os.getenv("LLM_AGENT_PRODUCTIVITY_TEMPERATURE", "")
                ),
                "Notes": self._parse_temperature(os.getenv("LLM_AGENT_NOTES_TEMPERATURE", "")),
                "Email": self._parse_temperature(os.getenv("LLM_AGENT_EMAIL_TEMPERATURE", "")),
                "Supervisor": self._parse_temperature(
                    os.getenv("LLM_AGENT_SUPERVISOR_TEMPERATURE", "")
                ),
            },
        }

        primary_cfg = config["providers"].get(config["primary_provider"], {})
        if not primary_cfg.get("enabled", False):
            fallback_primary = self._select_fallback_provider_from_config(
                config, excluded_provider=config["primary_provider"]
            )
            if fallback_primary:
                _log.warning(
                    "Primary provider %s is disabled, using %s",
                    config["primary_provider"],
                    fallback_primary,
                )
                config["primary_provider"] = fallback_primary

        return config

    def _parse_temperature(self, value: str) -> Optional[float]:
        """Parse a temperature string to float, returning None if empty or invalid."""
        if not value or not value.strip():
            return None
        try:
            temp = float(value.strip())
            return max(0.0, min(2.0, temp))  # Clamp to valid range
        except (ValueError, TypeError):
            return None

    def get_agent_temperature(self, agent_name: Optional[str] = None) -> float:
        """
        Get the temperature for a specific agent.
        Returns the agent-specific temperature if set, otherwise the global temperature.

        Args:
            agent_name: Agent name (Browser, Music, Meeting, System, Productivity, Notes, Email, Supervisor)

        Returns:
            Temperature float in range [0.0, 2.0]
        """
        if agent_name:
            agent_temp = self.config.get("agent_temperatures", {}).get(agent_name)
            if agent_temp is not None:
                return agent_temp
        return self.config["temperature"]

    def _normalize_provider(self, provider: Optional[str]) -> Optional[str]:
        """Normalize provider name to a supported key or return None."""
        if not provider:
            return None
        normalized = str(provider).strip().lower()
        return normalized if normalized in self.PROVIDERS else None

    def _select_fallback_provider(self, excluded_provider: Optional[str] = None) -> Optional[str]:
        """Get the first enabled provider, optionally excluding one."""
        for fallback_provider in ["azure", "ollama", "openai", "zhipu"]:
            if fallback_provider == excluded_provider:
                continue
            fallback_config = self.config["providers"].get(fallback_provider)
            if fallback_config and fallback_config.get("enabled", False):
                return fallback_provider
        return None

    def _select_fallback_provider_from_config(
        self, config: Dict[str, Any], excluded_provider: Optional[str] = None
    ) -> Optional[str]:
        """Get the first enabled provider from a provided config."""
        for fallback_provider in ["azure", "ollama", "openai", "zhipu"]:
            if fallback_provider == excluded_provider:
                continue
            fallback_config = config["providers"].get(fallback_provider)
            if fallback_config and fallback_config.get("enabled", False):
                return fallback_provider
        return None

    def _create_azure_llm(
        self, azure_config: Dict[str, Any], temperature: Optional[float] = None
    ) -> Any:
        """Create Azure OpenAI LLM instance."""
        from langchain_openai import AzureChatOpenAI

        temp = temperature if temperature is not None else self.config["temperature"]
        return AzureChatOpenAI(
            azure_endpoint=azure_config["endpoint"],
            openai_api_version=azure_config["api_version"],
            deployment_name=azure_config["deployment_name"],
            openai_api_key=azure_config["api_key"],
            temperature=temp,
        )

    def _create_ollama_llm(
        self, ollama_config: Dict[str, Any], temperature: Optional[float] = None
    ) -> Any:
        """Create Ollama LLM instance."""
        from langchain_ollama import ChatOllama

        temp = temperature if temperature is not None else self.config["temperature"]
        return ChatOllama(
            model=ollama_config["model"],
            temperature=temp,
            base_url=ollama_config["base_url"],
            timeout=ollama_config["timeout"],
        )

    def _create_openai_llm(
        self, openai_config: Dict[str, Any], temperature: Optional[float] = None
    ) -> Any:
        """Create OpenAI LLM instance."""
        from langchain_openai import ChatOpenAI

        temp = temperature if temperature is not None else self.config["temperature"]
        return ChatOpenAI(
            api_key=openai_config["api_key"],
            model=openai_config["model"],
            temperature=temp,
        )

    def _create_zhipu_llm(
        self, zhipu_config: Dict[str, Any], temperature: Optional[float] = None
    ) -> Any:
        """Create Zhipu AI (GLM) LLM instance via OpenAI-compatible API."""
        from langchain_openai import ChatOpenAI

        temp = temperature if temperature is not None else self.config["temperature"]
        return ChatOpenAI(
            api_key=zhipu_config["api_key"],
            model=zhipu_config["model"],
            base_url=zhipu_config["base_url"],
            temperature=temp,
        )

    def get_llm(self, provider: Optional[str] = None, agent: Optional[str] = None) -> Any:
        """
        Create and return LLM instance based on configuration.

        Args:
            provider: Specific provider to use (azure, ollama, openai). If None, uses primary or agent assignment.
            agent: Agent name to get agent-specific provider assignment and temperature.

        Returns:
            LLM instance configured with the agent-specific (or global) temperature.
        """
        # Determine which provider to use
        if agent and agent in self.config["agent_assignments"]:
            assigned_provider = self.config["agent_assignments"][agent]
            if assigned_provider:
                provider = assigned_provider

        provider = self._normalize_provider(provider)
        if provider is None:
            provider = self.config["primary_provider"]

        # Check if provider is enabled
        provider_config = self.config["providers"].get(provider)
        if not provider_config or not provider_config.get("enabled", False):
            # Try fallback if enabled
            if self.config["fallback_enabled"]:
                fallback_provider = self._select_fallback_provider(excluded_provider=provider)
                if not fallback_provider:
                    raise ValueError("No enabled LLM provider found")
                _log.warning(
                    "Provider %s not enabled, falling back to %s", provider, fallback_provider
                )
                provider = fallback_provider
                provider_config = self.config["providers"][fallback_provider]
            else:
                raise ValueError(f"LLM provider {provider} is not enabled")

        # Resolve the effective temperature for this agent
        temperature = self.get_agent_temperature(agent)

        # Cache key includes temperature so different-temperature instances are separate
        cache_key = f"{provider}_{temperature}_{agent or 'default'}"
        if cache_key in self._llm_instances:
            return self._llm_instances[cache_key]

        # Create new LLM instance with the resolved temperature
        if provider == "azure":
            llm = self._create_azure_llm(provider_config, temperature=temperature)
        elif provider == "ollama":
            llm = self._create_ollama_llm(provider_config, temperature=temperature)
        elif provider == "openai":
            llm = self._create_openai_llm(provider_config, temperature=temperature)
        elif provider == "zhipu":
            llm = self._create_zhipu_llm(provider_config, temperature=temperature)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        # Cache the instance
        self._llm_instances[cache_key] = llm
        return llm

    def get_llm_for_agent(self, agent_name: str) -> Any:
        """
        Get LLM instance for a specific agent.

        Args:
            agent_name: Name of the agent (Browser, Music, Meeting, System, Productivity, Supervisor).

        Returns:
            LLM instance for the agent.
        """
        return self.get_llm(agent=agent_name)

    def get_primary_llm(self) -> Any:
        """Get the primary LLM instance."""
        return self.get_llm(provider=self.config["primary_provider"])

    def get_provider_name(self, provider: Optional[str] = None) -> str:
        """Get human-readable provider name."""
        if provider is None:
            provider = self.config["primary_provider"]
        return self.PROVIDERS.get(provider, "Unknown")

    def get_config_summary(self) -> str:
        """Get configuration summary for logging."""
        primary = self.config["primary_provider"]
        providers = self.config["providers"]

        enabled_providers = [p for p, cfg in providers.items() if cfg.get("enabled", False)]

        summary = f"Primary: {self.get_provider_name(primary)}"
        summary += (
            f" | Enabled: {', '.join([self.get_provider_name(p) for p in enabled_providers])}"
        )
        summary += f" | Global temp: {self.config['temperature']}"

        agent_assignments = self.config["agent_assignments"]
        assigned_agents = {k: v for k, v in agent_assignments.items() if v}
        if assigned_agents:
            summary += f" | Agent Providers: {assigned_agents}"

        agent_temps = self.config.get("agent_temperatures", {})
        custom_temps = {k: v for k, v in agent_temps.items() if v is not None}
        if custom_temps:
            summary += f" | Agent Temps: {custom_temps}"

        return summary

    def get_enabled_providers(self) -> list:
        """Get list of enabled provider names."""
        return [p for p, cfg in self.config["providers"].items() if cfg.get("enabled", False)]


def get_llm_config() -> LLMConfig:
    """Get or create global LLM configuration instance (delegates to ServiceContainer)."""
    from src.utils.container import get_container

    return get_container().llm_config


def reload_llm_config() -> LLMConfig:
    """Reload LLM configuration from environment."""
    load_dotenv(override=True)  # Reload .env file
    container = __import__("src.utils.container", fromlist=["get_container"]).get_container()
    container._llm_config = LLMConfig()
    return container._llm_config
