"""Windows UI automation via UIA (pywinauto): inspect, click, and type into
applications by accessible element name — never by coordinates or blind keys.
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

INTERACTIVE_TYPES = {
    "Button",
    "Hyperlink",
    "MenuItem",
    "TabItem",
    "Edit",
    "ComboBox",
    "CheckBox",
    "RadioButton",
    "ListItem",
    "TreeItem",
}
MAX_ELEMENTS = 60
CONNECT_TIMEOUT_S = 10

_SPECIAL_KEYS = set("{}+^%~()")


def _escape_keys(text: str) -> str:
    """Escape pywinauto type_keys special characters by brace-wrapping them."""
    return "".join(f"{{{ch}}}" if ch in _SPECIAL_KEYS else ch for ch in text)


def _open_window_titles():
    from pywinauto import Desktop

    windows = Desktop(backend="uia").windows()
    return [(w, w.window_text()) for w in windows if w.window_text().strip()]


def _find_window(window_title: str):
    """Return (window, None) for the best title match, or (None, error string)."""
    needle = window_title.strip().lower()
    if not needle:
        return None, "Empty window title. Provide part of the window's title bar text."
    candidates = _open_window_titles()
    matches = [(w, t) for w, t in candidates if needle in t.lower()]
    if not matches:
        titles = ", ".join(f"'{t}'" for _, t in candidates[:20]) or "(none)"
        return None, f"Window '{window_title}' not found. Open windows: {titles}"
    # Best match: exact title beats shorter titles beats the rest.
    matches.sort(key=lambda m: (m[1].lower() != needle, len(m[1])))
    return matches[0][0], None


def _interactive_descendants(window, element_type: str = "any"):
    wanted = INTERACTIVE_TYPES if element_type == "any" else {element_type}
    found = []
    for elem in window.descendants():
        try:
            info = elem.element_info
            if info.control_type in wanted and (info.name or "").strip():
                found.append(elem)
        except Exception:  # noqa: BLE001 — stale elements are expected during enumeration
            continue
    return found


def _match_elements(elements, element_name: str):
    """Exact-name matches first; fall back to case-insensitive substring."""
    exact = [e for e in elements if e.element_info.name == element_name]
    if exact:
        return exact
    needle = element_name.lower()
    return [e for e in elements if needle in e.element_info.name.lower()]


def _describe(elem) -> str:
    info = elem.element_info
    return f"{info.control_type}: '{info.name}'"


@tool
def ui_elements(window_title: str) -> str:
    """List the interactive UI elements (buttons, links, menus, text fields...)
    of an open window, so they can be clicked or typed into by name.

    Args:
        window_title: part of the window's title bar text, e.g. "Notepad".
    """
    import pythoncom

    pythoncom.CoInitialize()
    try:
        window, error = _find_window(window_title)
        if error:
            return error
        elements = _interactive_descendants(window)
        if not elements:
            return f"No named interactive elements found in '{window.window_text()}'."
        lines = [_describe(e) for e in elements[:MAX_ELEMENTS]]
        header = f"Interactive elements in '{window.window_text()}':\n"
        note = (
            f"\n...(truncated, {len(elements) - MAX_ELEMENTS} more)"
            if len(elements) > MAX_ELEMENTS
            else ""
        )
        return header + "\n".join(lines) + note
    except Exception as exc:  # noqa: BLE001
        logger.exception("ui_elements failed")
        return f"Could not inspect window '{window_title}': {exc}"
    finally:
        pythoncom.CoUninitialize()


@tool
def ui_click(window_title: str, element_name: str, element_type: str = "any") -> str:
    """Click a UI element in an open window by its accessible name.

    Args:
        window_title: part of the window's title bar text.
        element_name: the element's name as shown by ui_elements, e.g. "Save".
        element_type: optional filter — Button, Hyperlink, MenuItem, TabItem,
            Edit, ComboBox, CheckBox, RadioButton, ListItem, TreeItem, or "any".
    """
    import pythoncom

    pythoncom.CoInitialize()
    try:
        window, error = _find_window(window_title)
        if error:
            return error
        elements = _interactive_descendants(window, element_type)
        matches = _match_elements(elements, element_name)
        if not matches:
            near = ", ".join(_describe(e) for e in elements[:15]) or "(none)"
            return (
                f"No element named '{element_name}' in '{window.window_text()}'. "
                f"Did you mean one of: {near}"
            )
        if len(matches) > 1:
            listing = "; ".join(_describe(e) for e in matches[:10])
            return (
                f"Ambiguous: {len(matches)} elements match '{element_name}': {listing}. "
                "Narrow it with element_type or a more specific name."
            )
        target = matches[0]
        window.set_focus()
        try:
            target.invoke()
            action = "Invoked"
        except Exception:  # noqa: BLE001 — no InvokePattern; fall back to a real click
            target.click_input()
            action = "Clicked"
        return f"{action} {_describe(target)} in '{window.window_text()}'."
    except Exception as exc:  # noqa: BLE001
        logger.exception("ui_click failed")
        return f"Could not click '{element_name}' in '{window_title}': {exc}"
    finally:
        pythoncom.CoUninitialize()


@tool
def ui_type_text(window_title: str, text: str, element_name: str = "") -> str:
    """Type text into an open window — into a named text field, or into the
    currently focused control if no element name is given. Enter is only
    pressed if the text ends with a newline.

    Args:
        window_title: part of the window's title bar text.
        text: the text to type; end with "\\n" to press Enter afterwards.
        element_name: optional name of the Edit/ComboBox field to fill.
    """
    import pythoncom

    pythoncom.CoInitialize()
    try:
        window, error = _find_window(window_title)
        if error:
            return error
        press_enter = text.endswith("\n")
        text = text.rstrip("\n")
        window.set_focus()
        target = None
        if element_name:
            edits = [
                e
                for e in _interactive_descendants(window)
                if e.element_info.control_type in ("Edit", "ComboBox")
            ]
            matches = _match_elements(edits, element_name)
            if not matches:
                near = ", ".join(_describe(e) for e in edits[:15]) or "(none)"
                return (
                    f"No text field named '{element_name}' in '{window.window_text()}'. "
                    f"Text fields found: {near}"
                )
            if len(matches) > 1:
                listing = "; ".join(_describe(e) for e in matches[:10])
                return f"Ambiguous: {len(matches)} fields match '{element_name}': {listing}."
            target = matches[0]
            try:
                target.set_edit_text(text)
                if press_enter:
                    target.type_keys("{ENTER}")
                return f"Set {_describe(target)} to the given text in '{window.window_text()}'."
            except Exception:  # noqa: BLE001 — no ValuePattern; click and type instead
                target.click_input()
        keys = _escape_keys(text) + ("{ENTER}" if press_enter else "")
        (target or window).type_keys(keys, with_spaces=True)
        where = _describe(target) if target else "the focused control"
        return f"Typed text into {where} in '{window.window_text()}'."
    except Exception as exc:  # noqa: BLE001
        logger.exception("ui_type_text failed")
        return f"Could not type into '{window_title}': {exc}"
    finally:
        pythoncom.CoUninitialize()


@tool
def ui_window_action(window_title: str, action: str) -> str:
    """Minimize, maximize, restore, or close an open window.

    Args:
        window_title: part of the window's title bar text.
        action: one of "minimize", "maximize", "restore", "close".
    """
    import pythoncom

    pythoncom.CoInitialize()
    try:
        action = action.strip().lower()
        if action not in ("minimize", "maximize", "restore", "close"):
            return f"Unknown action '{action}'. Use minimize, maximize, restore, or close."
        window, error = _find_window(window_title)
        if error:
            return error
        title = window.window_text()
        if action == "minimize":
            window.minimize()
        elif action == "maximize":
            window.maximize()
        elif action == "restore":
            window.restore()
        else:
            window.close()  # graceful close request, never a kill
        return f"Window '{title}': {action} done."
    except Exception as exc:  # noqa: BLE001
        logger.exception("ui_window_action failed")
        return f"Could not {action} window '{window_title}': {exc}"
    finally:
        pythoncom.CoUninitialize()


TOOLS = [ui_elements, ui_click, ui_type_text, ui_window_action]
