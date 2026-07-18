"""File navigation tools (read-only + open). No delete/move/write tools.

All tool names start with fs_. Paths are expanded (~, %VARS%) before use.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import stat
import subprocess
import time
from datetime import datetime
from pathlib import Path

from .server import mcp

logger = logging.getLogger("sentinel-mcp-windows.files")

_LIST_CAP = 100
_TREE_CAP = 200
_FIND_BUDGET_S = 10.0
_READ_MAX_BYTES = 5 * 1024 * 1024

FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4
FILE_ATTRIBUTE_REPARSE_POINT = 0x400

# Directory names pruned during fs_find (noise / huge trees).
_PRUNE_DIRS = {
    "appdata",
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".env",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    "site-packages",
    "$recycle.bin",
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
}

_DOWNLOADS_GUID = "{374DE290-123F-4565-9164-39C4925E467B}"


def _expand(path: str) -> Path:
    """Expand ~ and environment variables and return an absolute Path."""
    return Path(os.path.expandvars(os.path.expanduser(path.strip()))).absolute()


def _fmt_size(size: int) -> str:
    """Human-readable file size."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{int(size)} B"


def _fmt_mtime(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _attrs(entry_stat: os.stat_result) -> int:
    return getattr(entry_stat, "st_file_attributes", 0)


def _is_hidden_or_system(entry: os.DirEntry) -> bool:
    """True for hidden/system entries and reparse points (junctions/symlinks)."""
    try:
        st = entry.stat(follow_symlinks=False)
    except OSError:
        return True
    a = _attrs(st)
    if a & (FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM | FILE_ATTRIBUTE_REPARSE_POINT):
        return True
    return entry.name.startswith(".")


def _downloads_dir() -> Path:
    """Resolve the real Downloads folder via the registry; fall back to ~/Downloads."""
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, _DOWNLOADS_GUID)
        return Path(os.path.expandvars(value))
    except OSError:
        return Path.home() / "Downloads"


# --- Tools ---


@mcp.tool()
def fs_known_folders() -> str:
    """List the user's known folders (Desktop, Documents, Downloads, etc.) with real paths."""
    try:
        home = Path.home()
        folders = {
            "Desktop": home / "Desktop",
            "Documents": home / "Documents",
            "Downloads": _downloads_dir(),
            "Pictures": home / "Pictures",
            "Music": home / "Music",
            "Videos": home / "Videos",
        }
        lines = [f"Home: {home}"]
        for name, path in folders.items():
            marker = "" if path.is_dir() else " (missing)"
            lines.append(f"{name}: {path}{marker}")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("fs_known_folders failed")
        return f"Error resolving known folders: {e}"


@mcp.tool()
def fs_list(path: str) -> str:
    """List a directory's entries with type, size, and modified date (directories first)."""
    try:
        target = _expand(path)
        if not target.exists():
            return f"Error: path does not exist: {target}"
        if not target.is_dir():
            return f"Error: not a directory: {target} (use fs_info for files)"

        dirs: list[str] = []
        fils: list[str] = []
        total = 0
        for entry in sorted(os.scandir(target), key=lambda e: e.name.lower()):
            total += 1
            try:
                st = entry.stat(follow_symlinks=False)
                mtime = _fmt_mtime(st.st_mtime)
                if entry.is_dir(follow_symlinks=False):
                    dirs.append(f"[dir]  {entry.name}  (modified {mtime})")
                else:
                    fils.append(f"[file] {entry.name}  {_fmt_size(st.st_size)}  "
                                f"(modified {mtime})")
            except OSError:
                fils.append(f"[?]    {entry.name}  (inaccessible)")

        entries = dirs + fils
        if not entries:
            return f"{target} is empty."
        shown = entries[:_LIST_CAP]
        lines = [f"{target} ({total} entries):"] + shown
        if total > _LIST_CAP:
            lines.append(f"…and {total - _LIST_CAP} more")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("fs_list failed")
        return f"Error listing directory: {e}"


@mcp.tool()
def fs_tree(path: str, max_depth: int = 3) -> str:
    """Show an ASCII directory tree (like the tree command), skipping hidden/system dirs.

    Capped at 200 entries total; notes what was truncated.
    """
    try:
        root = _expand(path)
        if not root.is_dir():
            return f"Error: not an existing directory: {root}"
        max_depth = max(1, min(max_depth, 10))

        lines = [str(root)]
        count = 0
        truncated_dirs: list[str] = []
        capped = False

        def walk(directory: Path, prefix: str, depth: int) -> None:
            nonlocal count, capped
            if capped:
                return
            try:
                entries = sorted(
                    (e for e in os.scandir(directory) if not _is_hidden_or_system(e)),
                    key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()),
                )
            except OSError:
                lines.append(f"{prefix}└── [access denied]")
                return
            for i, entry in enumerate(entries):
                if count >= _TREE_CAP:
                    capped = True
                    lines.append(f"{prefix}└── …(capped at {_TREE_CAP} entries)")
                    return
                last = i == len(entries) - 1
                branch = "└── " if last else "├── "
                is_dir = entry.is_dir(follow_symlinks=False)
                suffix = "\\" if is_dir else ""
                lines.append(f"{prefix}{branch}{entry.name}{suffix}")
                count += 1
                if is_dir:
                    if depth < max_depth:
                        walk(Path(entry.path), prefix + ("    " if last else "│   "), depth + 1)
                    else:
                        truncated_dirs.append(entry.name)

        walk(root, "", 1)
        if truncated_dirs and not capped:
            shown = ", ".join(truncated_dirs[:5])
            more = f" (+{len(truncated_dirs) - 5} more)" if len(truncated_dirs) > 5 else ""
            lines.append(f"[depth limit {max_depth} reached; not expanded: {shown}{more}]")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("fs_tree failed")
        return f"Error building tree: {e}"


@mcp.tool()
def fs_find(name_pattern: str, root: str = "", max_results: int = 25) -> str:
    """Find files/folders by name under root (default: user home).

    Case-insensitive substring match, or glob if the pattern contains * ? [ ].
    Prunes noise directories (AppData, node_modules, .git, venvs). ~10s time budget.
    """
    try:
        pattern = name_pattern.strip().lower()
        if not pattern:
            return "Error: empty search pattern."
        base = _expand(root) if root.strip() else Path.home()
        if not base.is_dir():
            return f"Error: root is not an existing directory: {base}"
        max_results = max(1, min(max_results, 100))
        is_glob = any(c in pattern for c in "*?[]")

        def matches(name: str) -> bool:
            low = name.lower()
            return fnmatch.fnmatch(low, pattern) if is_glob else pattern in low

        deadline = time.monotonic() + _FIND_BUDGET_S
        results: list[str] = []
        budget_hit = False
        for dirpath, dirnames, filenames in os.walk(base):
            if time.monotonic() > deadline:
                budget_hit = True
                break
            dirnames[:] = [
                d for d in dirnames
                if d.lower() not in _PRUNE_DIRS and not d.startswith(".")
            ]
            for name in dirnames + filenames:
                if matches(name):
                    results.append(os.path.join(dirpath, name))
                    if len(results) >= max_results:
                        break
            if len(results) >= max_results:
                break

        if not results:
            note = " (stopped early: 10s time budget hit)" if budget_hit else ""
            return f"No matches for '{name_pattern}' under {base}.{note}"
        lines = [f"Found {len(results)} match(es) for '{name_pattern}' under {base}:"]
        lines += results
        if len(results) >= max_results:
            lines.append(f"[stopped at max_results={max_results}]")
        if budget_hit:
            lines.append("[search stopped early: 10s time budget hit — results may be partial]")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("fs_find failed")
        return f"Error searching files: {e}"


@mcp.tool()
def fs_open(path: str) -> str:
    """Open a file with its default application."""
    try:
        target = _expand(path)
        if not target.exists():
            return f"Error: path does not exist: {target}"
        os.startfile(str(target))  # noqa: S606 - intended default-app open
        return f"Opened {target} with its default application."
    except Exception as e:
        logger.exception("fs_open failed")
        return f"Error opening file: {e}"


@mcp.tool()
def fs_open_folder(path: str) -> str:
    """Open a folder in Windows Explorer."""
    try:
        target = _expand(path)
        if not target.is_dir():
            return f"Error: not an existing folder: {target}"
        subprocess.Popen(["explorer.exe", str(target)])
        return f"Opened {target} in Explorer."
    except Exception as e:
        logger.exception("fs_open_folder failed")
        return f"Error opening folder: {e}"


@mcp.tool()
def fs_info(path: str) -> str:
    """Get size, dates, and type for a file or directory."""
    try:
        target = _expand(path)
        if not target.exists():
            return f"Error: path does not exist: {target}"
        st = target.stat()
        if target.is_dir():
            kind = "directory"
            try:
                n = sum(1 for _ in os.scandir(target))
                size_line = f"Entries: {n}"
            except OSError:
                size_line = "Entries: (access denied)"
        else:
            kind = f"file ({target.suffix.lstrip('.') or 'no extension'})"
            size_line = f"Size: {_fmt_size(st.st_size)} ({st.st_size} bytes)"
        readonly = " read-only" if not (st.st_mode & stat.S_IWRITE) else ""
        return "\n".join([
            f"Path: {target}",
            f"Type: {kind}{readonly}",
            size_line,
            f"Modified: {_fmt_mtime(st.st_mtime)}",
            f"Created: {_fmt_mtime(st.st_ctime)}",
        ])
    except Exception as e:
        logger.exception("fs_info failed")
        return f"Error getting file info: {e}"


@mcp.tool()
def fs_read_text(path: str, max_chars: int = 4000) -> str:
    """Read a text-file preview (up to max_chars). Refuses binary files and files over 5 MB."""
    try:
        target = _expand(path)
        if not target.is_file():
            return f"Error: not an existing file: {target}"
        size = target.stat().st_size
        if size > _READ_MAX_BYTES:
            return f"Error: file is too large ({_fmt_size(size)}); limit is 5 MB."
        max_chars = max(100, min(max_chars, 100_000))

        with open(target, "rb") as f:
            head = f.read(1024)
        if b"\x00" in head:
            return f"Error: {target.name} looks like a binary file; refusing to read as text."

        text = target.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            return (f"{text[:max_chars]}\n"
                    f"…[truncated: showing {max_chars} of {len(text)} characters]")
        return text if text else f"{target.name} is empty."
    except Exception as e:
        logger.exception("fs_read_text failed")
        return f"Error reading file: {e}"
