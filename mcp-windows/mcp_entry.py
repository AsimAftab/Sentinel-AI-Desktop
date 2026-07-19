"""PyInstaller entry point for the frozen Sentinel Windows MCP server.

Freezing ``server.py`` directly collapses the package, so its
``from . import files, radios, workspaces`` fails with "attempted relative
import with no known parent package". Pointing PyInstaller at this wrapper
keeps ``sentinel_mcp_windows`` a real package in the bundle, so the relative
imports (and @mcp.tool registrations) resolve.
"""

from sentinel_mcp_windows.server import main

if __name__ == "__main__":
    main()
