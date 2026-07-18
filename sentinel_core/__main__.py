"""Entry point:  uv run --group core python -m sentinel_core"""

from __future__ import annotations

import logging

import uvicorn

from .config import Settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    uvicorn.run("sentinel_core.app:app", host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
