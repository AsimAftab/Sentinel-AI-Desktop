"""Multi-provider LLM manager.

Port of the legacy ``llm_config.py`` with a factory registry instead of
string branching, plus Groq and Cerebras (both OpenAI-compatible with tool
calling). Per-agent provider/temperature assignment, instance caching,
ordered fallback, and hot reload.
"""

from __future__ import annotations

import logging
from typing import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable

from .config import PROVIDER_KEY_ENV, ProviderConfig, Settings, get_secret

logger = logging.getLogger(__name__)

# Fallback preference: fast OpenAI-compatible clouds first, local last.
FALLBACK_ORDER = ["groq", "cerebras", "azure", "openai", "zhipu", "ollama"]

# Same-provider alternate models tried on a rate limit (429) BEFORE switching
# provider. Groq rate-limits per model, so a sibling model recovers a 429
# instantly. Only models verified to exist + support tool calling belong here.
PROVIDER_FALLBACK_MODELS = {
    "groq": (
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-20b",
        "llama-3.1-8b-instant",
    ),
}

# The Responder only rephrases — it can ride the provider's fast tier. The
# Supervisor stays on the primary model: routing quality (context resolution,
# disambiguation) measurably degrades on the small tier for barely any latency.
FAST_AGENTS = ("Responder",)
FAST_MODELS = {"groq": "openai/gpt-oss-20b"}


def _make_openai_compatible(name: str, cfg: ProviderConfig, temperature: float) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    api_key = get_secret(PROVIDER_KEY_ENV[name])
    if not api_key:
        raise ValueError(f"{PROVIDER_KEY_ENV[name]} is not set (env or keyring)")
    return ChatOpenAI(
        model=cfg.resolve_model(name),
        api_key=api_key,
        base_url=cfg.base_url,
        temperature=temperature,
        timeout=60,
        max_retries=2,
    )


def _make_azure(name: str, cfg: ProviderConfig, temperature: float) -> BaseChatModel:
    from langchain_openai import AzureChatOpenAI

    api_key = get_secret(PROVIDER_KEY_ENV["azure"])
    if not (api_key and cfg.endpoint and cfg.deployment):
        raise ValueError("Azure OpenAI needs AZURE_OPENAI_API_KEY, _ENDPOINT and _DEPLOYMENT_NAME")
    return AzureChatOpenAI(
        azure_endpoint=cfg.endpoint,
        azure_deployment=cfg.deployment,
        api_version=cfg.api_version,
        api_key=api_key,
        temperature=temperature,
        timeout=60,
        max_retries=2,
    )


def _make_ollama(name: str, cfg: ProviderConfig, temperature: float) -> BaseChatModel:
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=cfg.resolve_model(name),
        base_url=cfg.base_url,
        temperature=temperature,
    )


FACTORIES: dict[str, Callable[[str, ProviderConfig, float], BaseChatModel]] = {
    "groq": _make_openai_compatible,
    "cerebras": _make_openai_compatible,
    "openai": _make_openai_compatible,
    "zhipu": _make_openai_compatible,
    "azure": _make_azure,
    "ollama": _make_ollama,
}


class LLMManager:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._cache: dict[tuple[str, float], BaseChatModel] = {}

    @property
    def settings(self) -> Settings:
        return self._settings

    def reload(self, settings: Settings) -> None:
        self._settings = settings
        self._cache.clear()
        logger.info("LLM config reloaded (primary=%s)", settings.primary_provider)

    def _provider_for_agent(self, agent: str | None) -> str:
        if agent and agent in self._settings.agent_providers:
            return self._settings.agent_providers[agent]
        return self._settings.primary_provider

    def _temperature_for_agent(self, agent: str | None, override: float | None) -> float:
        if override is not None:
            return override
        if agent and agent in self._settings.agent_temperatures:
            return self._settings.agent_temperatures[agent]
        return self._settings.temperature

    def _create(self, provider: str, temperature: float, model: str | None = None) -> BaseChatModel:
        cfg = self._settings.providers.get(provider)
        if cfg is None or not cfg.enabled:
            raise ValueError(f"Provider '{provider}' is not enabled")
        if model:
            cfg = cfg.model_copy(update={"model": model})
        key = (provider, cfg.resolve_model(provider), temperature)
        if key not in self._cache:
            self._cache[key] = FACTORIES[provider](provider, cfg, temperature)
            logger.info(
                "Created LLM %s (model=%s, temp=%s)",
                provider,
                cfg.resolve_model(provider),
                temperature,
            )
        return self._cache[key]

    def _model_for_agent(self, agent: str | None, provider: str) -> str | None:
        # Explicit per-provider model config wins; otherwise fast tier for routing agents.
        cfg = self._settings.providers.get(provider)
        if agent in FAST_AGENTS and cfg is not None and not cfg.model:
            return FAST_MODELS.get(provider)
        return None

    def get(self, agent: str | None = None, temperature: float | None = None) -> BaseChatModel:
        """LLM for an agent, honoring per-agent assignment; falls back in order."""
        temp = self._temperature_for_agent(agent, temperature)
        preferred = self._provider_for_agent(agent)
        candidates = [preferred]
        if self._settings.fallback_enabled:
            candidates += [p for p in FALLBACK_ORDER if p != preferred]

        errors: list[str] = []
        for provider in candidates:
            try:
                return self._create(provider, temp, self._model_for_agent(agent, provider))
            except Exception as exc:  # noqa: BLE001 — collect and try the next provider
                errors.append(f"{provider}: {exc}")
        raise RuntimeError("No usable LLM provider. Tried: " + "; ".join(errors))

    def candidates(
        self, agent: str | None = None, temperature: float | None = None
    ) -> list[BaseChatModel]:
        """Ordered models to try for an agent at RUNTIME (rate-limit fallback).

        Unlike ``get()`` (which only guards against *construction* failures like
        a missing key), this returns every buildable model so callers can chain
        them with ``.with_fallbacks``/retry and survive a 429 mid-turn: primary
        model first, then alternate models on the same provider (a 429 is
        per-model on Groq), then other enabled providers. Unbuildable candidates
        are skipped; the primary is always first.
        """
        temp = self._temperature_for_agent(agent, temperature)
        preferred = self._provider_for_agent(agent)
        out: list[BaseChatModel] = []
        seen: set[tuple[str, str]] = set()

        def add(provider: str, model: str | None) -> None:
            cfg = self._settings.providers.get(provider)
            if cfg is None or not cfg.enabled:
                return
            resolved = model or cfg.resolve_model(provider)
            if (provider, resolved) in seen:
                return
            try:
                built = self._create(provider, temp, model)
            except Exception as exc:  # noqa: BLE001 — skip an unusable candidate
                logger.debug("Fallback candidate %s/%s unusable: %s", provider, resolved, exc)
                return
            seen.add((provider, resolved))
            out.append(built)

        add(preferred, self._model_for_agent(agent, preferred))
        if self._settings.fallback_enabled:
            for alt in PROVIDER_FALLBACK_MODELS.get(preferred, ()):
                add(preferred, alt)
            for provider in FALLBACK_ORDER:
                if provider != preferred:
                    add(provider, None)
        # Nothing built (e.g. fallback disabled and primary unusable): defer to
        # get(), which raises the same informative error it always has.
        return out or [self.get(agent, temperature)]

    def bound(
        self,
        agent: str | None,
        transform: Callable[[BaseChatModel], Runnable],
        temperature: float | None = None,
    ) -> Runnable:
        """Apply ``transform`` (bind tools / structured output / config) to each
        candidate and chain them with runtime fallbacks, so a rate-limit or
        transient error on one model transparently retries the next."""
        runnables = [transform(m) for m in self.candidates(agent, temperature)]
        head, *tail = runnables
        return head.with_fallbacks(tail) if tail else head

    def validate(self) -> dict[str, str]:
        """Best-effort constructability check per enabled provider (no API calls)."""
        report: dict[str, str] = {}
        for name, cfg in self._settings.providers.items():
            if not cfg.enabled:
                report[name] = "disabled"
                continue
            try:
                FACTORIES[name](name, cfg, self._settings.temperature)
                report[name] = "ok"
            except Exception as exc:  # noqa: BLE001
                report[name] = f"error: {exc}"
        return report
