"""PyInstaller entry point for the frozen Sentinel Core service.

Imports the app object directly (no uvicorn import-string, which is fragile
under freezing) and runs it.
"""

import logging
import multiprocessing


def main() -> None:
    multiprocessing.freeze_support()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    import uvicorn

    from sentinel_core.app import app
    from sentinel_core.config import Settings

    settings = Settings.from_env()
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
