# src/tools/system_tools.py

import os
import sys
import subprocess
import psutil
from datetime import datetime
from langchain_core.tools import tool

# Platform-specific imports
if sys.platform == 'win32':
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        import screen_brightness_control as sbc
        WINDOWS_LIBS_AVAILABLE = True
    except ImportError:
        WINDOWS_LIBS_AVAILABLE = False
        print("⚠️ System control libraries not installed. Install with: pip install pycaw screen-brightness-control psutil comtypes")
else:
    WINDOWS_LIBS_AVAILABLE = False

# Screenshot imports
try:
    import pyautogui
    SCREENSHOT_AVAILABLE = True
except ImportError:
    SCREENSHOT_AVAILABLE = False
    print("⚠️ Screenshot library not installed. Install with: pip install pyautogui pillow")


# --- Volume Control Tools ---

@tool
def increase_volume(amount: int = 10) -> str:
    """
    Increases system volume by a specified percentage.

    Args:
        amount: Percentage to increase (1-100), default is 10
    """
    if sys.platform != 'win32':
        return "Volume control is currently only supported on Windows."

    if not WINDOWS_LIBS_AVAILABLE:
        return "Required libraries not installed. Run: pip install pycaw comtypes"

    try:
        # Clamp amount between 1 and 100
        amount = max(1, min(100, amount))

        # Get the default audio device
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        # Get current volume (0.0 to 1.0)
        current_volume = volume.GetMasterVolumeLevelScalar()

        # Calculate new volume
        new_volume = min(1.0, current_volume + (amount / 100.0))

        # Set new volume
        volume.SetMasterVolumeLevelScalar(new_volume, None)

        # Unmute if muted
        volume.SetMute(0, None)

        percentage = int(new_volume * 100)
        return f"🔊 Volume increased by {amount}% → Now at {percentage}%"

    except Exception as e:
        return f"Error increasing volume: {e}"


@tool
def decrease_volume(amount: int = 10) -> str:
    """
    Decreases system volume by a specified percentage.

    Args:
        amount: Percentage to decrease (1-100), default is 10
    """
    if sys.platform != 'win32':
        return "Volume control is currently only supported on Windows."

    if not WINDOWS_LIBS_AVAILABLE:
        return "Required libraries not installed. Run: pip install pycaw comtypes"

    try:
        # Clamp amount between 1 and 100
        amount = max(1, min(100, amount))

        # Get the default audio device
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        # Get current volume (0.0 to 1.0)
        current_volume = volume.GetMasterVolumeLevelScalar()

        # Calculate new volume
        new_volume = max(0.0, current_volume - (amount / 100.0))

        # Set new volume
        volume.SetMasterVolumeLevelScalar(new_volume, None)

        percentage = int(new_volume * 100)
        return f"🔉 Volume decreased by {amount}% → Now at {percentage}%"

    except Exception as e:
        return f"Error decreasing volume: {e}"


@tool
def set_volume(level: int) -> str:
    """
    Sets system volume to a specific percentage.

    Args:
        level: Volume level (0-100)
    """
    if sys.platform != 'win32':
        return "Volume control is currently only supported on Windows."

    if not WINDOWS_LIBS_AVAILABLE:
        return "Required libraries not installed. Run: pip install pycaw comtypes"

    try:
        # Clamp level between 0 and 100
        level = max(0, min(100, level))

        # Get the default audio device
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        # Set volume (convert percentage to 0.0-1.0 scale)
        volume.SetMasterVolumeLevelScalar(level / 100.0, None)

        # Unmute if setting to non-zero
        if level > 0:
            volume.SetMute(0, None)

        return f"🔊 Volume set to {level}%"

    except Exception as e:
        return f"Error setting volume: {e}"


@tool
def get_current_volume() -> str:
    """
    Gets the current system volume level.
    """
    if sys.platform != 'win32':
        return "Volume control is currently only supported on Windows."

    if not WINDOWS_LIBS_AVAILABLE:
        return "Required libraries not installed. Run: pip install pycaw comtypes"

    try:
        # Get the default audio device
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        # Get current volume
        current_volume = volume.GetMasterVolumeLevelScalar()
        is_muted = volume.GetMute()

        percentage = int(current_volume * 100)

        if is_muted:
            return f"🔇 Volume: {percentage}% (MUTED)"
        else:
            return f"🔊 Current volume: {percentage}%"

    except Exception as e:
        return f"Error getting volume: {e}"


@tool
def mute_volume() -> str:
    """
    Mutes the system volume.
    """
    if sys.platform != 'win32':
        return "Volume control is currently only supported on Windows."

    if not WINDOWS_LIBS_AVAILABLE:
        return "Required libraries not installed. Run: pip install pycaw comtypes"

    try:
        # Get the default audio device
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        # Mute
        volume.SetMute(1, None)

        return "🔇 Volume muted"

    except Exception as e:
        return f"Error muting volume: {e}"


@tool
def unmute_volume() -> str:
    """
    Unmutes the system volume.
    """
    if sys.platform != 'win32':
        return "Volume control is currently only supported on Windows."

    if not WINDOWS_LIBS_AVAILABLE:
        return "Required libraries not installed. Run: pip install pycaw comtypes"

    try:
        # Get the default audio device
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        # Unmute
        volume.SetMute(0, None)

        # Get current volume to display
        current_volume = volume.GetMasterVolumeLevelScalar()
        percentage = int(current_volume * 100)

        return f"🔊 Volume unmuted → {percentage}%"

    except Exception as e:
        return f"Error unmuting volume: {e}"


# --- Brightness Control Tools ---

@tool
def increase_brightness(amount: int = 10) -> str:
    """
    Increases screen brightness by a specified percentage.

    Args:
        amount: Percentage to increase (1-100), default is 10
    """
    if sys.platform != 'win32':
        return "Brightness control is currently only supported on Windows."

    if not WINDOWS_LIBS_AVAILABLE:
        return "Required libraries not installed. Run: pip install screen-brightness-control"

    try:
        # Clamp amount
        amount = max(1, min(100, amount))

        # Get current brightness
        current = sbc.get_brightness()[0] if isinstance(sbc.get_brightness(), list) else sbc.get_brightness()

        # Calculate new brightness
        new_brightness = min(100, current + amount)

        # Set brightness
        sbc.set_brightness(new_brightness)

        return f"☀️ Brightness increased by {amount}% → Now at {new_brightness}%"

    except Exception as e:
        return f"Error increasing brightness: {e}"


@tool
def decrease_brightness(amount: int = 10) -> str:
    """
    Decreases screen brightness by a specified percentage.

    Args:
        amount: Percentage to decrease (1-100), default is 10
    """
    if sys.platform != 'win32':
        return "Brightness control is currently only supported on Windows."

    if not WINDOWS_LIBS_AVAILABLE:
        return "Required libraries not installed. Run: pip install screen-brightness-control"

    try:
        # Clamp amount
        amount = max(1, min(100, amount))

        # Get current brightness
        current = sbc.get_brightness()[0] if isinstance(sbc.get_brightness(), list) else sbc.get_brightness()

        # Calculate new brightness
        new_brightness = max(0, current - amount)

        # Set brightness
        sbc.set_brightness(new_brightness)

        return f"🌙 Brightness decreased by {amount}% → Now at {new_brightness}%"

    except Exception as e:
        return f"Error decreasing brightness: {e}"


@tool
def set_brightness(level: int) -> str:
    """
    Sets screen brightness to a specific percentage.

    Args:
        level: Brightness level (0-100)
    """
    if sys.platform != 'win32':
        return "Brightness control is currently only supported on Windows."

    if not WINDOWS_LIBS_AVAILABLE:
        return "Required libraries not installed. Run: pip install screen-brightness-control"

    try:
        # Clamp level
        level = max(0, min(100, level))

        # Set brightness
        sbc.set_brightness(level)

        return f"💡 Brightness set to {level}%"

    except Exception as e:
        return f"Error setting brightness: {e}"


@tool
def get_current_brightness() -> str:
    """
    Gets the current screen brightness level.
    """
    if sys.platform != 'win32':
        return "Brightness control is currently only supported on Windows."

    if not WINDOWS_LIBS_AVAILABLE:
        return "Required libraries not installed. Run: pip install screen-brightness-control"

    try:
        # Get brightness
        brightness = sbc.get_brightness()[0] if isinstance(sbc.get_brightness(), list) else sbc.get_brightness()

        return f"💡 Current brightness: {brightness}%"

    except Exception as e:
        return f"Error getting brightness: {e}"


# --- Application Control Tools ---

@tool
def open_application(app_name: str) -> str:
    """
    Opens an application by name. Supports common Windows applications.

    Args:
        app_name: Name of the application (e.g., "notepad", "calculator", "chrome", "spotify")
    """
    try:
        app_name_lower = app_name.lower().strip()

        # Common Windows applications mapping
        app_mappings = {
            'notepad': 'notepad.exe',
            'calculator': 'calc.exe',
            'paint': 'mspaint.exe',
            'chrome': 'chrome.exe',
            'firefox': 'firefox.exe',
            'edge': 'msedge.exe',
            'explorer': 'explorer.exe',
            'file explorer': 'explorer.exe',
            'word': 'winword.exe',
            'excel': 'excel.exe',
            'powerpoint': 'powerpnt.exe',
            'outlook': 'outlook.exe',
            'spotify': 'spotify.exe',
            'discord': 'discord.exe',
            'vscode': 'code.exe',
            'visual studio code': 'code.exe',
            'cmd': 'cmd.exe',
            'command prompt': 'cmd.exe',
            'powershell': 'powershell.exe',
            'task manager': 'taskmgr.exe',
            'control panel': 'control.exe',
            'settings': 'ms-settings:',
        }

        # Get executable name
        executable = app_mappings.get(app_name_lower, f"{app_name_lower}.exe")

        # Special handling for Windows Settings
        if executable == 'ms-settings:':
            subprocess.Popen(['start', 'ms-settings:'], shell=True)
            return f"✅ Opened Windows Settings"

        # Try to open the application
        if sys.platform == 'win32':
            # Use start command on Windows
            subprocess.Popen(['start', '', executable], shell=True)
        else:
            # On other platforms, try direct execution
            subprocess.Popen([executable])

        return f"✅ Opened {app_name}"

    except Exception as e:
        return f"❌ Could not open '{app_name}'. Error: {e}\n\nTry opening it manually or check the application name."


@tool
def close_application(app_name: str) -> str:
    """
    Closes a running application by name.

    Args:
        app_name: Name of the application to close (e.g., "notepad", "chrome", "spotify")
    """
    try:
        app_name_lower = app_name.lower().strip()

        # Common application process names
        process_mappings = {
            'notepad': 'notepad.exe',
            'calculator': 'Calculator.exe',
            'paint': 'mspaint.exe',
            'chrome': 'chrome.exe',
            'firefox': 'firefox.exe',
            'edge': 'msedge.exe',
            'word': 'WINWORD.EXE',
            'excel': 'EXCEL.EXE',
            'powerpoint': 'POWERPNT.EXE',
            'outlook': 'OUTLOOK.EXE',
            'spotify': 'Spotify.exe',
            'discord': 'Discord.exe',
            'vscode': 'Code.exe',
            'visual studio code': 'Code.exe',
        }

        # Get process name
        process_name = process_mappings.get(app_name_lower, app_name_lower)

        # Add .exe if not present
        if not process_name.endswith('.exe'):
            process_name += '.exe'

        # Find and close the process
        closed_count = 0
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'].lower() == process_name.lower():
                    proc.terminate()
                    closed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        if closed_count > 0:
            return f"✅ Closed {closed_count} instance(s) of {app_name}"
        else:
            return f"❌ No running instances of '{app_name}' found"

    except Exception as e:
        return f"Error closing application: {e}"


@tool
def list_running_applications() -> str:
    """
    Lists all currently running applications (excluding system processes).
    """
    try:
        # Get all running processes
        processes = []

        # Common system processes to exclude
        system_processes = {
            'svchost.exe', 'system', 'registry', 'smss.exe', 'csrss.exe',
            'wininit.exe', 'services.exe', 'lsass.exe', 'winlogon.exe',
            'dwm.exe', 'taskeng.exe', 'taskmgr.exe', 'explorer.exe',
            'runtime broker', 'system idle process', 'audiodg.exe',
            'conhost.exe', 'fontdrvhost.exe', 'sihost.exe', 'ctfmon.exe'
        }

        for proc in psutil.process_iter(['name', 'pid']):
            try:
                proc_name = proc.info['name']
                if proc_name and proc_name.lower() not in system_processes:
                    # Filter out duplicates and background processes
                    if proc_name not in [p['name'] for p in processes]:
                        processes.append({
                            'name': proc_name,
                            'pid': proc.info['pid']
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Sort by name
        processes.sort(key=lambda x: x['name'].lower())

        # Take top 20 most relevant
        processes = processes[:20]

        if not processes:
            return "No user applications currently running."

        result = "💻 **Running Applications:**\n\n"
        for i, proc in enumerate(processes, 1):
            # Clean up .exe extension for display
            display_name = proc['name'].replace('.exe', '')
            result += f"{i}. {display_name}\n"

        return result

    except Exception as e:
        return f"Error listing applications: {e}"


# --- Screenshot Tools ---

@tool
def take_screenshot(filename: str = None) -> str:
    """
    Takes a screenshot of the entire screen and saves it to the screenshots folder.

    Args:
        filename: Optional custom filename (without extension). If not provided, uses timestamp.
    """
    if not SCREENSHOT_AVAILABLE:
        return "Screenshot library not installed. Run: pip install pyautogui pillow"

    try:
        # Create screenshots directory if it doesn't exist
        screenshots_dir = "screenshots"
        os.makedirs(screenshots_dir, exist_ok=True)

        # Generate filename with timestamp if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}"

        # Remove .png extension if user added it
        if filename.endswith('.png'):
            filename = filename[:-4]

        # Full file path
        filepath = os.path.join(screenshots_dir, f"{filename}.png")

        # Take screenshot
        screenshot = pyautogui.screenshot()

        # Save screenshot
        screenshot.save(filepath)

        # Get absolute path for better clarity
        abs_path = os.path.abspath(filepath)

        return f"📸 Screenshot saved successfully!\n📁 Location: {abs_path}"

    except Exception as e:
        return f"Error taking screenshot: {e}"


@tool
def get_screen_size() -> str:
    """
    Gets the current screen resolution (width x height).
    """
    if not SCREENSHOT_AVAILABLE:
        return "Screenshot library not installed. Run: pip install pyautogui pillow"

    try:
        screen_width, screen_height = pyautogui.size()
        return f"🖥️ Screen resolution: {screen_width} x {screen_height} pixels"

    except Exception as e:
        return f"Error getting screen size: {e}"


# System tools list
system_tools = [
    # Volume controls
    increase_volume,
    decrease_volume,
    set_volume,
    get_current_volume,
    mute_volume,
    unmute_volume,
    # Brightness controls
    increase_brightness,
    decrease_brightness,
    set_brightness,
    get_current_brightness,
    # Application controls
    open_application,
    close_application,
    list_running_applications,
    # Screenshot controls
    take_screenshot,
    get_screen_size,
]
