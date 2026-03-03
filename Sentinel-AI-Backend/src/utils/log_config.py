"""Centralized logging configuration for Sentinel AI Backend."""

import logging

_configured = False


def configure_logging(level=logging.INFO):
    """Configure root logger with console handler. Idempotent."""
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(level)

    # Only add handler if none exist (avoids duplicates)
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)


def get_logger(name):
    """Return a named logger, configuring logging on first call."""
    configure_logging()
    return logging.getLogger(name)
