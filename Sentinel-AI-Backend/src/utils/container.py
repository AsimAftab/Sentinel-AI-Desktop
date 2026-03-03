"""
Lightweight dependency injection container for Sentinel AI Backend.

Provides lazy-initialized, thread-safe access to shared services.
Existing singleton functions (get_llm_config, get_agent_memory, get_tts_instance)
delegate to this container so all services share one lifecycle.
"""

import threading
from src.utils.log_config import get_logger

logger = get_logger("container")

_container = None
_container_lock = threading.Lock()


class ServiceContainer:
    """Central owner of all shared backend services."""

    def __init__(self):
        self._lock = threading.Lock()
        self._llm_config = None
        self._agent_memory = None
        self._tts = None

        # Set externally by integration layer (None in standalone mode)
        self.event_bus = None

        # Shutdown coordination
        self.shutdown_event = threading.Event()

    # --- Lazy properties ------------------------------------------------

    @property
    def llm_config(self):
        if self._llm_config is None:
            with self._lock:
                if self._llm_config is None:
                    from src.utils.llm_config import LLMConfig

                    self._llm_config = LLMConfig()
                    logger.info("LLMConfig initialized")
        return self._llm_config

    @property
    def agent_memory(self):
        if self._agent_memory is None:
            with self._lock:
                if self._agent_memory is None:
                    from src.utils.agent_memory import AgentMemory

                    self._agent_memory = AgentMemory()
                    logger.info("AgentMemory initialized")
        return self._agent_memory

    @property
    def tts(self):
        if self._tts is None:
            with self._lock:
                if self._tts is None:
                    from src.utils.text_to_speech import TextToSpeech

                    self._tts = TextToSpeech()
                    logger.info("TextToSpeech initialized")
        return self._tts

    # --- Lifecycle ------------------------------------------------------

    def close(self):
        """Release all resources."""
        self.shutdown_event.set()
        if self._agent_memory is not None:
            self._agent_memory.close()
        if self._tts is not None:
            self._tts.stop()
        if self._llm_config is not None:
            self._llm_config = None
        logger.info("ServiceContainer closed")


def get_container() -> ServiceContainer:
    """Get or create the global ServiceContainer singleton."""
    global _container
    if _container is None:
        with _container_lock:
            if _container is None:
                _container = ServiceContainer()
    return _container
