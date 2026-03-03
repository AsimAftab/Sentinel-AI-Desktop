"""
Dev task entry points for uv run shortcuts.

Usage:
    uv run lint        → ruff check .
    uv run format      → ruff format .
    uv run typecheck   → pyright
"""

import subprocess
import sys


def lint() -> None:
    sys.exit(subprocess.call(["ruff", "check", "."]))


def format() -> None:
    sys.exit(subprocess.call(["ruff", "format", "."]))


def typecheck() -> None:
    sys.exit(subprocess.call(["pyright"]))
