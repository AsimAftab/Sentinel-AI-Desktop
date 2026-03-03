# src/tools/productivity_tools.py

import subprocess
import threading
import time
from datetime import datetime, timedelta
from langchain_core.tools import tool
import sys

try:
    import winsound

    _WINSOUND_AVAILABLE = True
except ImportError:
    _WINSOUND_AVAILABLE = False

from src.utils.log_config import get_logger

logger = get_logger("productivity")

# Global storage for active timers and alarms
active_timers = {}
active_alarms = {}
timer_id_counter = 0
alarm_id_counter = 0
_counter_lock = threading.Lock()  # Protects both ID counters from race conditions
_timers_lock = threading.Lock()  # Protects active_timers and active_alarms dicts


def play_notification_sound():
    """Play a notification sound on Windows."""
    try:
        if sys.platform == "win32" and _WINSOUND_AVAILABLE:
            # Play Windows default beep
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            time.sleep(0.3)
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            time.sleep(0.3)
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception as e:
        logger.debug("Could not play sound: %s", e)


def timer_callback(timer_id, name, duration_minutes):
    """Callback function when timer completes."""
    with _timers_lock:
        if timer_id in active_timers:
            logger.info("Timer completed: '%s' (%d minute(s))", name, duration_minutes)
            del active_timers[timer_id]
        else:
            return

    # Play notification sound outside the lock
    play_notification_sound()


def alarm_callback(alarm_id, name, alarm_time):
    """Callback function when alarm goes off."""
    with _timers_lock:
        if alarm_id in active_alarms:
            logger.info("Alarm triggered: '%s' at %s", name, alarm_time)
            del active_alarms[alarm_id]
        else:
            return

    # Play notification sound outside the lock
    play_notification_sound()


# --- Timer Tools ---


@tool
def set_timer(duration_minutes: int, name: str = "Timer") -> str:
    """
    Sets a countdown timer for a specified duration in minutes.
    When the timer completes, a notification sound will play.

    Args:
        duration_minutes: Duration in minutes (1-480, max 8 hours)
        name: Optional name for the timer (e.g., "Coffee break", "Meeting")
    """
    global timer_id_counter, active_timers

    try:
        # Validate duration
        if duration_minutes < 1:
            return "❌ Timer duration must be at least 1 minute."
        if duration_minutes > 480:
            return "❌ Timer duration cannot exceed 8 hours (480 minutes)."

        # Generate unique timer ID (thread-safe)
        with _counter_lock:
            timer_id_counter += 1
            timer_id = timer_id_counter

        # Calculate end time
        end_time = datetime.now() + timedelta(minutes=duration_minutes)

        # Create timer thread
        timer_thread = threading.Timer(
            duration_minutes * 60, timer_callback, args=(timer_id, name, duration_minutes)
        )
        timer_thread.daemon = True
        timer_thread.start()

        # Store timer info
        with _timers_lock:
            active_timers[timer_id] = {
                "name": name,
                "duration_minutes": duration_minutes,
                "end_time": end_time,
                "thread": timer_thread,
            }

        # Format response
        end_time_str = end_time.strftime("%I:%M %p")

        if duration_minutes == 1:
            duration_str = "1 minute"
        elif duration_minutes < 60:
            duration_str = f"{duration_minutes} minutes"
        elif duration_minutes == 60:
            duration_str = "1 hour"
        else:
            hours = duration_minutes // 60
            mins = duration_minutes % 60
            if mins == 0:
                duration_str = f"{hours} hour{'s' if hours > 1 else ''}"
            else:
                duration_str = (
                    f"{hours} hour{'s' if hours > 1 else ''} {mins} minute{'s' if mins > 1 else ''}"
                )

        return f"⏱️ Timer set: '{name}'\n⏰ Duration: {duration_str}\n🕐 Will complete at: {end_time_str}\n🆔 Timer ID: {timer_id}"

    except Exception as e:
        return f"Error setting timer: {e}"


@tool
def set_alarm(time_str: str, name: str = "Alarm") -> str:
    """
    Sets an alarm for a specific time today or tomorrow.
    Supports formats like "3:30 PM", "15:30", "3pm", "15:00".

    Args:
        time_str: Time for the alarm (e.g., "3:30 PM", "15:30", "3pm")
        name: Optional name for the alarm (e.g., "Meeting", "Lunch break")
    """
    global alarm_id_counter, active_alarms

    try:
        # Parse time string
        time_str = time_str.strip().upper()

        # Try different time formats
        alarm_time = None
        formats_to_try = [
            "%I:%M %p",  # 3:30 PM
            "%I:%M%p",  # 3:30PM
            "%I%p",  # 3PM
            "%H:%M",  # 15:30
            "%H",  # 15
        ]

        for fmt in formats_to_try:
            try:
                parsed_time = datetime.strptime(time_str, fmt).time()
                # Combine with today's date
                alarm_time = datetime.combine(datetime.now().date(), parsed_time)
                break
            except ValueError:
                continue

        if alarm_time is None:
            return "❌ Could not parse time. Use formats like '3:30 PM', '15:30', or '3pm'."

        # If time has already passed today, set for tomorrow
        if alarm_time <= datetime.now():
            alarm_time += timedelta(days=1)
            day_info = "tomorrow"
        else:
            day_info = "today"

        # Calculate seconds until alarm
        seconds_until_alarm = (alarm_time - datetime.now()).total_seconds()

        # Generate unique alarm ID (thread-safe)
        with _counter_lock:
            alarm_id_counter += 1
            alarm_id = alarm_id_counter

        # Create alarm thread
        alarm_thread = threading.Timer(
            seconds_until_alarm,
            alarm_callback,
            args=(alarm_id, name, alarm_time.strftime("%I:%M %p")),
        )
        alarm_thread.daemon = True
        alarm_thread.start()

        # Store alarm info
        with _timers_lock:
            active_alarms[alarm_id] = {
                "name": name,
                "alarm_time": alarm_time,
                "thread": alarm_thread,
            }

        # Format response
        alarm_time_str = alarm_time.strftime("%I:%M %p")
        time_until = alarm_time - datetime.now()
        hours = int(time_until.total_seconds() // 3600)
        minutes = int((time_until.total_seconds() % 3600) // 60)

        if hours > 0:
            time_until_str = f"{hours} hour{'s' if hours > 1 else ''} {minutes} minute{'s' if minutes > 1 else ''}"
        else:
            time_until_str = f"{minutes} minute{'s' if minutes > 1 else ''}"

        return f"⏰ Alarm set: '{name}'\n🕐 Time: {alarm_time_str} ({day_info})\n⏱️ Time until alarm: {time_until_str}\n🆔 Alarm ID: {alarm_id}"

    except Exception as e:
        return f"Error setting alarm: {e}"


@tool
def list_active_timers() -> str:
    """
    Lists all currently active timers and alarms.
    Shows remaining time for each.
    """
    try:
        result = ""

        with _timers_lock:
            timers_snapshot = dict(active_timers)
            alarms_snapshot = dict(active_alarms)

        # List active timers
        if timers_snapshot:
            result += "⏱️ **Active Timers:**\n\n"
            for timer_id, timer_info in timers_snapshot.items():
                name = timer_info["name"]
                end_time = timer_info["end_time"]
                remaining = end_time - datetime.now()

                if remaining.total_seconds() > 0:
                    minutes_left = int(remaining.total_seconds() // 60)
                    seconds_left = int(remaining.total_seconds() % 60)

                    if minutes_left > 0:
                        time_left = f"{minutes_left}m {seconds_left}s"
                    else:
                        time_left = f"{seconds_left}s"

                    result += f"🆔 {timer_id}: '{name}' - {time_left} remaining\n"
            result += "\n"

        # List active alarms
        if alarms_snapshot:
            result += "⏰ **Active Alarms:**\n\n"
            for alarm_id, alarm_info in alarms_snapshot.items():
                name = alarm_info["name"]
                alarm_time = alarm_info["alarm_time"]
                alarm_time_str = alarm_time.strftime("%I:%M %p")

                remaining = alarm_time - datetime.now()
                if remaining.total_seconds() > 0:
                    hours_left = int(remaining.total_seconds() // 3600)
                    minutes_left = int((remaining.total_seconds() % 3600) // 60)

                    if hours_left > 0:
                        time_left = f"{hours_left}h {minutes_left}m"
                    else:
                        time_left = f"{minutes_left}m"

                    result += (
                        f"🆔 {alarm_id}: '{name}' at {alarm_time_str} ({time_left} remaining)\n"
                    )
            result += "\n"

        if not timers_snapshot and not alarms_snapshot:
            return "ℹ️ No active timers or alarms."

        return result.strip()

    except Exception as e:
        return f"Error listing timers: {e}"


@tool
def cancel_timer(timer_id: int) -> str:
    """
    Cancels an active timer by its ID.

    Args:
        timer_id: The ID of the timer to cancel (shown when timer was created)
    """
    try:
        with _timers_lock:
            if timer_id in active_timers:
                timer_info = active_timers[timer_id]
                timer_info["thread"].cancel()
                del active_timers[timer_id]
                return f"✅ Timer '{timer_info['name']}' (ID: {timer_id}) cancelled."
            else:
                return f"❌ No active timer found with ID: {timer_id}"

    except Exception as e:
        return f"Error cancelling timer: {e}"


@tool
def cancel_alarm(alarm_id: int) -> str:
    """
    Cancels an active alarm by its ID.

    Args:
        alarm_id: The ID of the alarm to cancel (shown when alarm was created)
    """
    try:
        with _timers_lock:
            if alarm_id in active_alarms:
                alarm_info = active_alarms[alarm_id]
                alarm_info["thread"].cancel()
                del active_alarms[alarm_id]
                return f"✅ Alarm '{alarm_info['name']}' (ID: {alarm_id}) cancelled."
            else:
                return f"❌ No active alarm found with ID: {alarm_id}"

    except Exception as e:
        return f"Error cancelling alarm: {e}"


@tool
def cancel_all_timers_and_alarms() -> str:
    """
    Cancels all active timers and alarms.
    """
    try:
        cancelled_count = 0

        with _timers_lock:
            # Cancel all timers
            for timer_id in list(active_timers.keys()):
                active_timers[timer_id]["thread"].cancel()
                del active_timers[timer_id]
                cancelled_count += 1

            # Cancel all alarms
            for alarm_id in list(active_alarms.keys()):
                active_alarms[alarm_id]["thread"].cancel()
                del active_alarms[alarm_id]
                cancelled_count += 1

        if cancelled_count == 0:
            return "ℹ️ No active timers or alarms to cancel."

        return f"✅ Cancelled {cancelled_count} timer(s) and alarm(s)."

    except Exception as e:
        return f"Error cancelling all timers: {e}"


# --- Pomodoro & Focus Tools ---

# Track Pomodoro sessions for daily summary
_pomodoro_sessions = []  # list of {"started": datetime, "work_min": int, "break_min": int, "cycles": int}
_focus_mode_active = {"active": False, "until": None}

# Cancellation events for long-running background tasks
_pomodoro_cancel_event: threading.Event | None = None
_focus_cancel_event: threading.Event | None = None


def _pomodoro_runner(
    work_minutes: int, break_minutes: int, cycles: int, cancel_event: threading.Event
):
    """Background function that runs the full Pomodoro cycle sequence."""
    for cycle in range(1, cycles + 1):
        logger.info("Pomodoro %d/%d — Work phase (%dm) started", cycle, cycles, work_minutes)
        play_notification_sound()

        # Wait for work phase (cancellable)
        if cancel_event.wait(timeout=work_minutes * 60):
            logger.info("Pomodoro cancelled during work phase %d/%d", cycle, cycles)
            return

        if cycle < cycles:
            logger.info("Pomodoro %d/%d — Break time (%dm)", cycle, cycles, break_minutes)
            play_notification_sound()

            # Wait for break phase (cancellable)
            if cancel_event.wait(timeout=break_minutes * 60):
                logger.info("Pomodoro cancelled during break phase %d/%d", cycle, cycles)
                return
        else:
            logger.info("Pomodoro session complete! %d cycles finished", cycles)
            play_notification_sound()


@tool
def start_pomodoro(work_minutes: int = 25, break_minutes: int = 5, cycles: int = 4) -> str:
    """
    Starts a Pomodoro productivity session with alternating work and break intervals.
    Plays a notification sound at each phase transition.

    Args:
        work_minutes: Duration of each work interval in minutes (default: 25)
        break_minutes: Duration of each short break in minutes (default: 5)
        cycles: Number of work/break cycles to complete (default: 4)
    """
    global _pomodoro_cancel_event

    try:
        if not (1 <= work_minutes <= 120):
            return "❌ Work interval must be between 1 and 120 minutes."
        if not (1 <= break_minutes <= 60):
            return "❌ Break interval must be between 1 and 60 minutes."
        if not (1 <= cycles <= 10):
            return "❌ Cycles must be between 1 and 10."

        # Cancel any existing Pomodoro session
        if _pomodoro_cancel_event is not None:
            _pomodoro_cancel_event.set()

        session = {
            "started": datetime.now(),
            "work_min": work_minutes,
            "break_min": break_minutes,
            "cycles": cycles,
        }
        _pomodoro_sessions.append(session)

        _pomodoro_cancel_event = threading.Event()

        thread = threading.Thread(
            target=_pomodoro_runner,
            args=(work_minutes, break_minutes, cycles, _pomodoro_cancel_event),
            daemon=True,
        )
        thread.start()

        total_min = cycles * work_minutes + (cycles - 1) * break_minutes
        end_time = (datetime.now() + timedelta(minutes=total_min)).strftime("%I:%M %p")

        return (
            f"🍅 **Pomodoro Session Started!**\n\n"
            f"⏱️  Work:  {work_minutes} min × {cycles} cycles\n"
            f"☕  Break: {break_minutes} min between cycles\n"
            f"⏳  Total: ~{total_min} minutes\n"
            f"🕐  Finishes around: {end_time}\n\n"
            f"A notification sound will play at each phase transition. Stay focused!"
        )
    except Exception as e:
        return f"Error starting Pomodoro: {e}"


@tool
def cancel_pomodoro() -> str:
    """
    Cancels the currently running Pomodoro session immediately.
    """
    global _pomodoro_cancel_event

    try:
        if _pomodoro_cancel_event is not None and not _pomodoro_cancel_event.is_set():
            _pomodoro_cancel_event.set()
            _pomodoro_cancel_event = None
            return "✅ Pomodoro session cancelled."
        else:
            return "ℹ️ No active Pomodoro session to cancel."
    except Exception as e:
        return f"Error cancelling Pomodoro: {e}"


@tool
def enable_focus_mode(duration_minutes: int = 60) -> str:
    """
    Enables Focus Mode for a set duration. Suppresses Windows notifications using
    Focus Assist via PowerShell and sets a reminder when the session ends.

    Args:
        duration_minutes: How long to stay in focus mode in minutes (default: 60)
    """
    global _focus_cancel_event

    try:
        if not (1 <= duration_minutes <= 480):
            return "❌ Duration must be between 1 and 480 minutes."

        # Cancel any existing focus mode session
        if _focus_cancel_event is not None:
            _focus_cancel_event.set()

        # Best-effort: enable Windows Focus Assist via PowerShell
        if sys.platform == "win32":
            try:
                subprocess.run(
                    [
                        "powershell",
                        "-Command",
                        "Set-ItemProperty -Path "
                        "'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\Store"
                        "\\DefaultAccount\\Current\\default$windows.data.notifications.quiethourssettings"
                        "\\windows.data.notifications.quiethourssettings' "
                        "-Name 'Data' -Type Binary -Value ([byte[]](0x02,0x00,0x00,0x00)) "
                        "-ErrorAction SilentlyContinue",
                    ],
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                pass  # Non-critical

        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        _focus_mode_active["active"] = True
        _focus_mode_active["until"] = end_time

        _focus_cancel_event = threading.Event()
        cancel_evt = _focus_cancel_event

        def _disable_focus():
            cancelled = cancel_evt.wait(timeout=duration_minutes * 60)
            _focus_mode_active["active"] = False
            _focus_mode_active["until"] = None
            if cancelled:
                logger.info("Focus Mode cancelled early.")
            else:
                logger.info("Focus Mode ended. Notifications restored.")
            play_notification_sound()

        threading.Thread(target=_disable_focus, daemon=True).start()

        end_str = end_time.strftime("%I:%M %p")
        return (
            f"🎯 **Focus Mode Enabled**\n\n"
            f"⏱️  Duration: {duration_minutes} minutes\n"
            f"🕐  Ends at: {end_str}\n"
            f"🔕  Windows Focus Assist activation attempted.\n"
            f"💡  Tip: Close distracting apps and stay in the zone!"
        )
    except Exception as e:
        return f"Error enabling focus mode: {e}"


@tool
def cancel_focus_mode() -> str:
    """
    Cancels the currently active Focus Mode session immediately.
    Restores normal notification behavior.
    """
    global _focus_cancel_event

    try:
        if _focus_cancel_event is not None and not _focus_cancel_event.is_set():
            _focus_cancel_event.set()
            _focus_cancel_event = None
            return "✅ Focus Mode cancelled. Notifications restored."
        else:
            return "ℹ️ No active Focus Mode session to cancel."
    except Exception as e:
        return f"Error cancelling Focus Mode: {e}"


@tool
def get_daily_summary() -> str:
    """
    Returns a summary of today's productivity: active timers, alarms,
    Pomodoro sessions completed, and focus mode status.
    """
    try:
        today = datetime.now().date()
        result = f"📋 **Daily Summary — {today.strftime('%B %d, %Y')}**\n\n"

        # Focus mode
        if _focus_mode_active["active"] and _focus_mode_active["until"]:
            until_str = _focus_mode_active["until"].strftime("%I:%M %p")
            result += f"🎯 Focus Mode: ACTIVE until {until_str}\n\n"
        else:
            result += "🎯 Focus Mode: Off\n\n"

        # Pomodoro sessions today
        today_sessions = [s for s in _pomodoro_sessions if s["started"].date() == today]
        if today_sessions:
            total_work = sum(s["work_min"] * s["cycles"] for s in today_sessions)
            result += f"🍅 Pomodoro Sessions: {len(today_sessions)} session(s) started\n"
            result += f"   ~{total_work} min of focused work scheduled today\n\n"
        else:
            result += "🍅 Pomodoro Sessions: None today\n\n"

        # Snapshot under lock
        with _timers_lock:
            timers_snapshot = dict(active_timers)
            alarms_snapshot = dict(active_alarms)

        # Active timers
        if timers_snapshot:
            result += f"⏱️ Active Timers: {len(timers_snapshot)}\n"
            for tid, info in timers_snapshot.items():
                mins = max(0, int((info["end_time"] - datetime.now()).total_seconds() // 60))
                result += f"   [{tid}] {info['name']} — {mins}m remaining\n"
            result += "\n"
        else:
            result += "⏱️ Active Timers: None\n\n"

        # Active alarms
        if alarms_snapshot:
            result += f"⏰ Active Alarms: {len(alarms_snapshot)}\n"
            for aid, info in alarms_snapshot.items():
                result += (
                    f"   [{aid}] {info['name']} at {info['alarm_time'].strftime('%I:%M %p')}\n"
                )
        else:
            result += "⏰ Active Alarms: None"

        return result.strip()
    except Exception as e:
        return f"Error generating daily summary: {e}"


# Productivity tools list
productivity_tools = [
    set_timer,
    set_alarm,
    list_active_timers,
    cancel_timer,
    cancel_alarm,
    cancel_all_timers_and_alarms,
    start_pomodoro,
    cancel_pomodoro,
    enable_focus_mode,
    cancel_focus_mode,
    get_daily_summary,
]
