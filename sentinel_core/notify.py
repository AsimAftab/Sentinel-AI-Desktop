"""Windows toast notifications via WinRT (PowerShell 5.1, no dependencies).

The script is passed with -EncodedCommand (UTF-16LE base64) so user text is
never interpolated into a command line.
"""

# ruff: noqa: E501 — the PowerShell template lines cannot be wrapped

from __future__ import annotations

import base64
import logging
import subprocess
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)

POWERSHELL_51 = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

_TEMPLATE = """
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml(@'
<toast><visual><binding template="ToastGeneric"><text>{title}</text><text>{body}</text></binding></visual></toast>
'@)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Sentinel AI').Show($toast)
"""


def toast(title: str, body: str) -> bool:
    """Show a Windows toast. Returns False on failure (never raises)."""
    try:
        script = _TEMPLATE.format(title=escape(title[:80]), body=escape(body[:200]))
        encoded = base64.b64encode(script.encode("utf-16-le")).decode()
        subprocess.run(
            [POWERSHELL_51, "-NoProfile", "-EncodedCommand", encoded],
            capture_output=True,
            timeout=15,
        )
        return True
    except Exception:  # noqa: BLE001 — notifications are best-effort
        logger.exception("Toast notification failed")
        return False
