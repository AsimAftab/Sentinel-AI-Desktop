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


# --- Bluetooth Control Tools (Human-like UI Automation) ---

@tool
def open_bluetooth_settings() -> str:
    """
    Opens Windows Bluetooth settings panel and reports current Bluetooth status.
    Use this to access Bluetooth device management, pairing, and settings.

    NOTE: If user wants to turn Bluetooth ON or OFF, use enable_bluetooth or disable_bluetooth instead!
    This tool only OPENS the settings panel.
    """
    if sys.platform != 'win32':
        return "Bluetooth settings control is currently only supported on Windows."

    try:
        # Check current state first
        current_state = _get_bluetooth_state()

        # Open Bluetooth settings via ms-settings URI
        subprocess.Popen(['start', 'ms-settings:bluetooth'], shell=True)

        if current_state == "On":
            return "📶 Opened Bluetooth settings. Bluetooth is currently ON. You can pair devices or manage connections."
        elif current_state == "Off":
            return "📴 Opened Bluetooth settings. Bluetooth is currently OFF. Toggle the switch at the top to turn it on."
        else:
            return "📶 Opened Bluetooth settings. You can now pair devices, view connected devices, or toggle Bluetooth."

    except Exception as e:
        return f"Error opening Bluetooth settings: {e}"


def _get_bluetooth_state() -> str:
    """Helper function to get current Bluetooth state (On/Off/NotFound)."""
    try:
        ps_command = '''
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
        Function Await($WinRtTask, $ResultType) {
            $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
            $netTask = $asTask.Invoke($null, @($WinRtTask))
            $netTask.Wait(-1) | Out-Null
            $netTask.Result
        }
        [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
        [Windows.Devices.Radios.RadioState,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
        $radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
        $bluetooth = $radios | Where-Object { $_.Kind -eq 'Bluetooth' }
        if ($bluetooth) {
            Write-Output $bluetooth.State
        } else {
            Write-Output "NotFound"
        }
        '''
        result = subprocess.run(
            ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_command],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip()
    except:
        return "Unknown"


@tool
def toggle_bluetooth(action: str = "on") -> str:
    """
    Toggles Bluetooth on or off. First checks current state, then toggles if needed.
    Uses human-like UI automation to click the toggle in Settings.

    Args:
        action: "on" to enable Bluetooth, "off" to disable Bluetooth
    """
    if sys.platform != 'win32':
        return "Bluetooth control is currently only supported on Windows."

    if not SCREENSHOT_AVAILABLE:
        return "UI automation requires pyautogui. Run: pip install pyautogui"

    try:
        import time

        action_lower = action.lower().strip()
        if action_lower not in ["on", "off", "enable", "disable"]:
            return "Invalid action. Use 'on' to enable or 'off' to disable Bluetooth."

        want_enabled = action_lower in ["on", "enable"]

        # First, check current Bluetooth state
        current_state = _get_bluetooth_state()

        if current_state == "NotFound":
            return "❌ No Bluetooth adapter found on this device."

        is_currently_on = current_state == "On"

        # Check if already in desired state
        if want_enabled and is_currently_on:
            return "📶 Bluetooth is already ON. No action needed."
        elif not want_enabled and not is_currently_on:
            return "📴 Bluetooth is already OFF. No action needed."

        # Need to toggle - open Bluetooth settings
        subprocess.Popen(['start', 'ms-settings:bluetooth'], shell=True)
        time.sleep(2.0)  # Wait for settings to fully open

        # Navigate to the Bluetooth toggle switch
        # Tab through the settings page to reach the toggle
        for _ in range(3):  # Tab a few times to reach the toggle
            pyautogui.press('tab')
            time.sleep(0.15)

        # Press Space to toggle the switch
        pyautogui.press('space')
        time.sleep(1.0)  # Wait for toggle to take effect

        # Verify the change happened
        new_state = _get_bluetooth_state()
        is_now_on = new_state == "On"

        # Close settings window
        pyautogui.hotkey('alt', 'F4')
        time.sleep(0.3)

        # Report result
        if want_enabled:
            if is_now_on:
                return "📶 Bluetooth is now ON! Successfully enabled."
            else:
                return "⚠️ Tried to enable Bluetooth but it's still OFF. Please try manually in Settings."
        else:
            if not is_now_on:
                return "📴 Bluetooth is now OFF! Successfully disabled."
            else:
                return "⚠️ Tried to disable Bluetooth but it's still ON. Please try manually in Settings."

    except Exception as e:
        # Fall back to opening settings
        try:
            subprocess.Popen(['start', 'ms-settings:bluetooth'], shell=True)
            return f"⚠️ Could not automate toggle ({e}). Opened Bluetooth settings - please toggle manually."
        except:
            return f"Error toggling Bluetooth: {e}"


@tool
def toggle_bluetooth_quick() -> str:
    """
    Quick toggle Bluetooth using Windows Action Center (Win + A).
    Simulates human clicking on the Bluetooth quick action button.
    """
    if sys.platform != 'win32':
        return "Bluetooth control is currently only supported on Windows."

    if not SCREENSHOT_AVAILABLE:
        return "UI automation requires pyautogui. Run: pip install pyautogui"

    try:
        import time

        # Open Windows Action Center with Win + A
        pyautogui.hotkey('win', 'a')
        time.sleep(1.2)  # Wait for Action Center to fully open

        # The quick actions panel has Bluetooth as one of the buttons
        # We can try to click it by approximate position or use keyboard
        # Press Tab multiple times to reach Bluetooth, or click directly

        # Get screen size to calculate approximate button positions
        screen_width, screen_height = pyautogui.size()

        # Action Center quick actions are typically on the right side
        # Bluetooth button is usually in the quick actions grid
        # Approximate position (may need adjustment based on Windows version)
        # Quick actions are at bottom-right of Action Center panel

        # Try clicking in the area where Bluetooth quick action typically is
        # This is an approximation - Windows 10/11 layout
        action_center_x = screen_width - 200  # Right side
        action_center_y = screen_height - 300  # Lower portion

        # Click on approximate Bluetooth button location
        pyautogui.click(action_center_x, action_center_y)
        time.sleep(0.5)

        # Close Action Center
        pyautogui.press('escape')

        return "📶 Clicked Bluetooth quick action in Action Center. Please check if Bluetooth status changed."

    except Exception as e:
        try:
            pyautogui.press('escape')  # Close Action Center if open
        except:
            pass
        return f"Error with quick toggle: {e}. Try using 'open bluetooth settings' instead."


@tool
def get_bluetooth_status() -> str:
    """
    Gets the current Bluetooth status (enabled/disabled) and lists paired devices.
    """
    if sys.platform != 'win32':
        return "Bluetooth status check is currently only supported on Windows."

    try:
        # Use PowerShell to check status (read-only, doesn't need UI)
        ps_command = '''
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
        Function Await($WinRtTask, $ResultType) {
            $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
            $netTask = $asTask.Invoke($null, @($WinRtTask))
            $netTask.Wait(-1) | Out-Null
            $netTask.Result
        }
        [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
        [Windows.Devices.Radios.RadioState,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
        $radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
        $bluetooth = $radios | Where-Object { $_.Kind -eq 'Bluetooth' }
        if ($bluetooth) {
            Write-Output "Status:$($bluetooth.State)"
        } else {
            Write-Output "Status:NotFound"
        }
        '''

        result = subprocess.run(
            ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_command],
            capture_output=True,
            text=True,
            timeout=15
        )

        output = result.stdout.strip()

        if "Status:NotFound" in output:
            return "❌ No Bluetooth adapter found on this device."

        if "Status:On" in output:
            status = "📶 Bluetooth is **ON** (enabled)"
        elif "Status:Off" in output:
            status = "📴 Bluetooth is **OFF** (disabled)"
        else:
            status = f"Bluetooth status: {output}"

        # Try to get paired devices
        try:
            devices_cmd = 'Get-PnpDevice -Class Bluetooth | Where-Object { $_.Status -eq "OK" } | Select-Object -ExpandProperty FriendlyName'
            devices_result = subprocess.run(
                ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', devices_cmd],
                capture_output=True,
                text=True,
                timeout=10
            )

            devices = [d.strip() for d in devices_result.stdout.strip().split('\n') if d.strip()]

            if devices:
                status += f"\n\n🔗 **Connected/Paired Devices ({len(devices)}):**\n"
                for device in devices[:10]:
                    status += f"  • {device}\n"
            else:
                status += "\n\nNo paired Bluetooth devices found."

        except:
            pass

        return status

    except subprocess.TimeoutExpired:
        return "⚠️ Bluetooth status check timed out."
    except Exception as e:
        return f"Error checking Bluetooth status: {e}"


@tool
def enable_bluetooth() -> str:
    """
    Enables (turns on) Bluetooth. Checks current state first - if already on, confirms it.
    If off, opens settings and toggles it on.
    """
    if sys.platform != 'win32':
        return "Bluetooth control is currently only supported on Windows."

    # Check current state first
    current_state = _get_bluetooth_state()

    if current_state == "NotFound":
        return "❌ No Bluetooth adapter found on this device."

    if current_state == "On":
        return "📶 Bluetooth is already ON and ready to use!"

    # Need to turn it on - use toggle function
    return toggle_bluetooth.invoke({"action": "on"})


@tool
def disable_bluetooth() -> str:
    """
    Disables (turns off) Bluetooth. Checks current state first - if already off, confirms it.
    If on, opens settings and toggles it off.
    """
    if sys.platform != 'win32':
        return "Bluetooth control is currently only supported on Windows."

    # Check current state first
    current_state = _get_bluetooth_state()

    if current_state == "NotFound":
        return "❌ No Bluetooth adapter found on this device."

    if current_state == "Off":
        return "📴 Bluetooth is already OFF."

    # Need to turn it off - use toggle function
    return toggle_bluetooth.invoke({"action": "off"})


@tool
def open_bluetooth_pairing() -> str:
    """
    Opens Bluetooth pairing mode - opens the 'Add a device' dialog.
    Simulates a human clicking 'Add Bluetooth or other device'.
    """
    if sys.platform != 'win32':
        return "Bluetooth pairing is currently only supported on Windows."

    if not SCREENSHOT_AVAILABLE:
        return "UI automation requires pyautogui. Run: pip install pyautogui"

    try:
        import time

        # Open Bluetooth settings
        subprocess.Popen(['start', 'ms-settings:bluetooth'], shell=True)
        time.sleep(1.5)

        # Press Tab to navigate to "Add Bluetooth or other device" button
        pyautogui.press('tab')
        time.sleep(0.2)

        # Press Enter to open Add Device dialog
        pyautogui.press('enter')
        time.sleep(1.0)

        return "📶 Opened 'Add a device' dialog. Select the type of device you want to pair."

    except Exception as e:
        return f"Error opening Bluetooth pairing: {e}"


# --- WiFi Control Tools (Human-like UI Automation) ---

@tool
def open_wifi_settings() -> str:
    """
    Opens Windows WiFi settings panel.
    Use this to manage WiFi connections, view available networks, or toggle WiFi.
    """
    if sys.platform != 'win32':
        return "WiFi settings control is currently only supported on Windows."

    try:
        subprocess.Popen(['start', 'ms-settings:network-wifi'], shell=True)
        return "📡 Opened WiFi settings. You can now connect to networks or toggle WiFi."

    except Exception as e:
        return f"Error opening WiFi settings: {e}"


@tool
def toggle_wifi(action: str = "on") -> str:
    """
    Toggles WiFi on or off using human-like UI automation.
    Opens WiFi settings and clicks the toggle switch.

    Args:
        action: "on" to enable WiFi, "off" to disable WiFi
    """
    if sys.platform != 'win32':
        return "WiFi control is currently only supported on Windows."

    if not SCREENSHOT_AVAILABLE:
        return "UI automation requires pyautogui. Run: pip install pyautogui"

    try:
        import time

        action_lower = action.lower().strip()
        if action_lower not in ["on", "off", "enable", "disable"]:
            return "Invalid action. Use 'on' to enable or 'off' to disable WiFi."

        enable = action_lower in ["on", "enable"]

        # Open WiFi settings
        subprocess.Popen(['start', 'ms-settings:network-wifi'], shell=True)
        time.sleep(1.5)

        # Navigate to WiFi toggle using Tab
        pyautogui.press('tab')
        time.sleep(0.2)
        pyautogui.press('tab')
        time.sleep(0.2)

        # Press Space to toggle
        pyautogui.press('space')
        time.sleep(0.5)

        # Close settings
        pyautogui.hotkey('alt', 'F4')

        status_emoji = "📡" if enable else "📴"
        status_text = "enabled" if enable else "disabled"

        return f"{status_emoji} WiFi toggle attempted. Please verify WiFi is now {status_text}."

    except Exception as e:
        try:
            subprocess.Popen(['start', 'ms-settings:network-wifi'], shell=True)
            return f"⚠️ Could not automate toggle ({e}). Opened WiFi settings - please toggle manually."
        except:
            return f"Error toggling WiFi: {e}"


@tool
def toggle_wifi_quick() -> str:
    """
    Quick toggle WiFi using Windows Action Center (Win + A).
    Simulates human clicking on the WiFi quick action button.
    """
    if sys.platform != 'win32':
        return "WiFi control is currently only supported on Windows."

    if not SCREENSHOT_AVAILABLE:
        return "UI automation requires pyautogui. Run: pip install pyautogui"

    try:
        import time

        # Open Windows Action Center
        pyautogui.hotkey('win', 'a')
        time.sleep(1.2)

        # Get screen size
        screen_width, screen_height = pyautogui.size()

        # WiFi button is typically near Bluetooth in quick actions
        # Approximate position
        action_center_x = screen_width - 280
        action_center_y = screen_height - 300

        pyautogui.click(action_center_x, action_center_y)
        time.sleep(0.5)

        # Close Action Center
        pyautogui.press('escape')

        return "📡 Clicked WiFi quick action in Action Center. Please check if WiFi status changed."

    except Exception as e:
        try:
            pyautogui.press('escape')
        except:
            pass
        return f"Error with quick toggle: {e}. Try using 'open wifi settings' instead."


@tool
def get_wifi_status() -> str:
    """
    Gets the current WiFi status and connected network name.
    """
    if sys.platform != 'win32':
        return "WiFi status check is currently only supported on Windows."

    try:
        result = subprocess.run(
            'netsh wlan show interfaces',
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )

        output = result.stdout

        if "There is no wireless interface" in output or not output.strip():
            return "❌ No WiFi adapter found or WiFi is disabled."

        status_info = {}
        for line in output.split('\n'):
            if ':' in line:
                key, _, value = line.partition(':')
                status_info[key.strip().lower()] = value.strip()

        state = status_info.get('state', 'Unknown')
        ssid = status_info.get('ssid', 'Not connected')
        signal = status_info.get('signal', 'N/A')

        if state.lower() == 'connected':
            return f"📡 WiFi is **ON** and connected\n🌐 Network: {ssid}\n📶 Signal: {signal}"
        elif state.lower() == 'disconnected':
            return "📡 WiFi is **ON** but not connected to any network."
        else:
            return f"📴 WiFi status: {state}"

    except subprocess.TimeoutExpired:
        return "⚠️ WiFi status check timed out."
    except Exception as e:
        return f"Error checking WiFi status: {e}"


@tool
def show_available_wifi_networks() -> str:
    """
    Shows available WiFi networks by opening the network flyout.
    Simulates clicking on the WiFi icon in the taskbar.
    """
    if sys.platform != 'win32':
        return "WiFi control is currently only supported on Windows."

    if not SCREENSHOT_AVAILABLE:
        return "UI automation requires pyautogui. Run: pip install pyautogui"

    try:
        import time

        # Method 1: Use keyboard shortcut to open network flyout
        # Win + A opens Action Center, then we can access WiFi
        pyautogui.hotkey('win', 'a')
        time.sleep(1.0)

        # Click on the WiFi section to expand available networks
        screen_width, screen_height = pyautogui.size()

        # Click on WiFi area (right side, lower portion of action center)
        pyautogui.click(screen_width - 200, screen_height - 350)
        time.sleep(0.5)

        return "📡 Opened WiFi network list. Available networks should now be visible."

    except Exception as e:
        # Fallback: open settings
        subprocess.Popen(['start', 'ms-settings:network-wifi'], shell=True)
        return f"Opened WiFi settings instead. You can see available networks there."


@tool
def connect_to_wifi(network_name: str) -> str:
    """
    Attempts to connect to a known WiFi network by name.
    Uses netsh command (works for previously connected networks).

    Args:
        network_name: Name (SSID) of the WiFi network to connect to
    """
    if sys.platform != 'win32':
        return "WiFi control is currently only supported on Windows."

    try:
        # Try to connect using netsh (works for saved networks)
        cmd = f'netsh wlan connect name="{network_name}"'
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            return f"📡 Connecting to '{network_name}'... Connection request sent successfully."
        else:
            error = result.stderr or result.stdout
            if "is not found" in error.lower() or "not found" in error.lower():
                return f"❌ Network '{network_name}' not found in saved networks. Please connect manually through WiFi settings."
            else:
                # Open WiFi settings as fallback
                subprocess.Popen(['start', 'ms-settings:network-wifi'], shell=True)
                return f"⚠️ Could not connect to '{network_name}' automatically. Opened WiFi settings - please connect manually."

    except Exception as e:
        return f"Error connecting to WiFi: {e}"


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
    # Bluetooth controls (human-like UI automation)
    open_bluetooth_settings,
    toggle_bluetooth,
    toggle_bluetooth_quick,
    get_bluetooth_status,
    enable_bluetooth,
    disable_bluetooth,
    open_bluetooth_pairing,
    # WiFi controls (human-like UI automation)
    open_wifi_settings,
    toggle_wifi,
    toggle_wifi_quick,
    get_wifi_status,
    show_available_wifi_networks,
    connect_to_wifi,
]
