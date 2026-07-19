"""Coding agent: delegates software tasks to the Claude Code CLI, headless.

code_question runs read-only; coding_task may edit files but only inside the
given project folder (acceptEdits permission mode — no shell execution).
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

TASK_TIMEOUT_S = 300


def _claude() -> str | None:
    return shutil.which("claude")


async def _run_claude(project: Path, prompt: str, extra_args: list[str]) -> str:
    exe = _claude()
    if exe is None:
        return "Claude Code CLI is not installed (https://claude.com/claude-code)."
    if not project.is_dir():
        return f"Not a folder: {project}"
    try:
        proc = await asyncio.create_subprocess_exec(
            exe,
            "-p",
            prompt,
            "--output-format",
            "text",
            *extra_args,
            cwd=str(project),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TASK_TIMEOUT_S)
    except TimeoutError:
        proc.kill()
        return f"The coding task ran past {TASK_TIMEOUT_S // 60} minutes and was stopped."
    except Exception as exc:  # noqa: BLE001
        logger.exception("claude CLI failed")
        return f"Could not run the coding task: {exc}"
    text = stdout.decode("utf-8", errors="replace").strip()
    if not text:
        err = stderr.decode("utf-8", errors="replace").strip()
        return f"No output from Claude Code.{(' Error: ' + err[:300]) if err else ''}"
    return text[-4000:]


@tool
async def code_question(project_folder: str, question: str) -> str:
    """Answer a question about a local code project (read-only analysis).

    Args:
        project_folder: path to the project, e.g. "C:/Users/me/myapp".
        question: e.g. "what does the auth flow do?" or "where is X defined?".
    """
    path = Path(os.path.expandvars(os.path.expanduser(project_folder.strip())))
    return await _run_claude(path, question, [])


@tool
async def coding_task(project_folder: str, instruction: str) -> str:
    """Make a code change in a local project. File edits are allowed within
    the project; shell commands are not. Takes up to a few minutes.

    Args:
        project_folder: path to the project.
        instruction: precise change to make, e.g. "fix the off-by-one in
            utils.parse_range and add a docstring".
    """
    path = Path(os.path.expandvars(os.path.expanduser(project_folder.strip())))
    return await _run_claude(path, instruction, ["--permission-mode", "acceptEdits"])


TOOLS = [code_question, coding_task]
