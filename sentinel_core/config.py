"""Configuration for Sentinel Core.

Layered: environment variables (+ .env files) form the base; user overrides
persisted in the SQLite settings table are merged on top at load time via
``apply_overrides``. Secrets prefer the OS keyring over plaintext env when
available.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

KEYRING_SERVICE = "sentinel-ai"

# Providers that speak the OpenAI chat-completions protocol via a base_url.
OPENAI_COMPATIBLE_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
}

DEFAULT_MODELS = {
    "groq": "openai/gpt-oss-120b",
    "cerebras": "gpt-oss-120b",
    "zhipu": "glm-4.5",
    "openai": "gpt-4o-mini",
    "ollama": "llama3.1",
}

PROVIDER_KEY_ENV = {
    "groq": "GROQ_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "zhipu": "ZHIPU_API_KEY",
    "openai": "OPENAI_API_KEY",
    "azure": "AZURE_OPENAI_API_KEY",
}

ALL_PROVIDERS = ("groq", "cerebras", "azure", "openai", "ollama", "zhipu")


def data_dir() -> Path:
    base = os.environ.get("SENTINEL_DATA_DIR")
    if base:
        path = Path(base)
    elif os.name == "nt":
        path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SentinelAI"
    else:
        path = Path.home() / ".sentinel-ai"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_env_files() -> None:
    root = Path(__file__).resolve().parent.parent
    for candidate in (root / ".env", root / "Sentinel-AI-Backend" / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)


def get_secret(name: str) -> str | None:
    """Env first (explicit wins), then OS keyring."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        import keyring

        return keyring.get_password(KEYRING_SERVICE, name)
    except Exception:
        return None


def set_secret(name: str, value: str) -> None:
    import keyring

    keyring.set_password(KEYRING_SERVICE, name, value)


class ProviderConfig(BaseModel):
    enabled: bool = False
    model: str | None = None
    base_url: str | None = None
    # Azure-only extras
    endpoint: str | None = None
    deployment: str | None = None
    api_version: str | None = None
    # Ollama-only
    timeout: int = 120

    def resolve_model(self, provider: str) -> str:
        return self.model or DEFAULT_MODELS.get(provider, "")


class Settings(BaseModel):
    primary_provider: str = "groq"
    fallback_enabled: bool = True
    temperature: float = 0.3
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    # agent name -> provider override, e.g. {"Supervisor": "cerebras"}
    agent_providers: dict[str, str] = Field(default_factory=dict)
    agent_temperatures: dict[str, float] = Field(default_factory=dict)

    host: str = "127.0.0.1"
    port: int = 8721
    tavily_api_key: str | None = None
    memory_ttl_hours: int = 24

    @classmethod
    def from_env(cls) -> "Settings":
        _load_env_files()
        providers: dict[str, ProviderConfig] = {}

        for name in ALL_PROVIDERS:
            enabled_env = os.environ.get(f"{name.upper()}_ENABLED")
            has_key = bool(get_secret(PROVIDER_KEY_ENV.get(name, ""))) if name != "ollama" else True
            providers[name] = ProviderConfig(
                # Providers with a key present are on unless explicitly disabled.
                enabled=(enabled_env or str(has_key)).strip().lower() in ("true", "1", "yes"),
                model=os.environ.get(f"{name.upper()}_MODEL"),
                base_url=os.environ.get(
                    f"{name.upper()}_BASE_URL", OPENAI_COMPATIBLE_BASE_URLS.get(name)
                ),
            )

        azure = providers["azure"]
        azure.endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        azure.deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
        azure.api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
        azure.enabled = azure.enabled and bool(azure.endpoint and azure.deployment)

        ollama = providers["ollama"]
        ollama.base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        ollama.enabled = os.environ.get("OLLAMA_ENABLED", "false").strip().lower() in (
            "true",
            "1",
            "yes",
        )

        primary = os.environ.get("LLM_PROVIDER")
        if not primary:
            primary = next(
                (
                    p
                    for p in ("groq", "cerebras", "azure", "openai", "zhipu", "ollama")
                    if providers[p].enabled
                ),
                "groq",
            )

        return cls(
            primary_provider=primary,
            fallback_enabled=os.environ.get("LLM_FALLBACK_ENABLED", "true").strip().lower()
            in ("true", "1", "yes"),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.3")),
            providers=providers,
            host=os.environ.get("SENTINEL_HOST", "127.0.0.1"),
            port=int(os.environ.get("SENTINEL_PORT", "8721")),
            tavily_api_key=get_secret("TAVILY_API_KEY"),
            memory_ttl_hours=int(os.environ.get("MEMORY_TTL_HOURS", "24")),
        )

    def apply_overrides(self, overrides: dict) -> "Settings":
        """Merge a user-settings dict (from SQLite) over env-derived config."""
        data = self.model_dump()
        for key in (
            "primary_provider",
            "fallback_enabled",
            "temperature",
            "agent_providers",
            "agent_temperatures",
        ):
            if key in overrides and overrides[key] is not None:
                data[key] = overrides[key]
        for name, cfg in (overrides.get("providers") or {}).items():
            if name in data["providers"]:
                data["providers"][name].update({k: v for k, v in cfg.items() if v is not None})
        return Settings(**data)
