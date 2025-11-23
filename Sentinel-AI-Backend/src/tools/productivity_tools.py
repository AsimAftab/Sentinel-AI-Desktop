# src/tools/productivity_tools.py

import threading
import time
from datetime import datetime, timedelta
from langchain_core.tools import tool
import winsound
import sys

# Global storage for active timers and alarms
active_timers = {}
active_alarms = {}
timer_id_counter = 0
alarm_id_counter = 0


def play_notification_sound():
    """Play a notification sound on Windows."""
    try:
        if sys.platform == 'win32':
            # Play Windows default beep
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            time.sleep(0.3)
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            time.sleep(0.3)
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception as e:
        print(f"Could not play sound: {e}")


def timer_callback(timer_id, name, duration_minutes):
    """Callback function when timer completes."""
    if timer_id in active_timers:
        print(f"\n{'='*60}")
        print(f"⏰ TIMER COMPLETED!")
        print(f"Timer: {name}")
        print(f"Duration: {duration_minutes} minute(s)")
        print(f"{'='*60}\n")

        # Play notification sound
        play_notification_sound()

        # Remove from active timers
        del active_timers[timer_id]


def alarm_callback(alarm_id, name, alarm_time):
    """Callback function when alarm goes off."""
    if alarm_id in active_alarms:
        print(f"\n{'='*60}")
        print(f"⏰ ALARM!")
        print(f"Alarm: {name}")
        print(f"Time: {alarm_time}")
        print(f"{'='*60}\n")

        # Play notification sound
        play_notification_sound()

        # Remove from active alarms
        del active_alarms[alarm_id]


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

        # Generate unique timer ID
        timer_id_counter += 1
        timer_id = timer_id_counter

        # Calculate end time
        end_time = datetime.now() + timedelta(minutes=duration_minutes)

        # Create timer thread
        timer_thread = threading.Timer(
            duration_minutes * 60,
            timer_callback,
            args=(timer_id, name, duration_minutes)
        )
        timer_thread.daemon = True
        timer_thread.start()

        # Store timer info
        active_timers[timer_id] = {
            'name': name,
            'duration_minutes': duration_minutes,
            'end_time': end_time,
            'thread': timer_thread
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
                duration_str = f"{hours} hour{'s' if hours > 1 else ''} {mins} minute{'s' if mins > 1 else ''}"

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
            "%I:%M%p",   # 3:30PM
            "%I%p",      # 3PM
            "%H:%M",     # 15:30
            "%H",        # 15
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

        # Generate unique alarm ID
        alarm_id_counter += 1
        alarm_id = alarm_id_counter

        # Create alarm thread
        alarm_thread = threading.Timer(
            seconds_until_alarm,
            alarm_callback,
            args=(alarm_id, name, alarm_time.strftime("%I:%M %p"))
        )
        alarm_thread.daemon = True
        alarm_thread.start()

        # Store alarm info
        active_alarms[alarm_id] = {
            'name': name,
            'alarm_time': alarm_time,
            'thread': alarm_thread
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

        # List active timers
        if active_timers:
            result += "⏱️ **Active Timers:**\n\n"
            for timer_id, timer_info in active_timers.items():
                name = timer_info['name']
                end_time = timer_info['end_time']
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
        if active_alarms:
            result += "⏰ **Active Alarms:**\n\n"
            for alarm_id, alarm_info in active_alarms.items():
                name = alarm_info['name']
                alarm_time = alarm_info['alarm_time']
                alarm_time_str = alarm_time.strftime("%I:%M %p")

                remaining = alarm_time - datetime.now()
                if remaining.total_seconds() > 0:
                    hours_left = int(remaining.total_seconds() // 3600)
                    minutes_left = int((remaining.total_seconds() % 3600) // 60)

                    if hours_left > 0:
                        time_left = f"{hours_left}h {minutes_left}m"
                    else:
                        time_left = f"{minutes_left}m"

                    result += f"🆔 {alarm_id}: '{name}' at {alarm_time_str} ({time_left} remaining)\n"
            result += "\n"

        if not active_timers and not active_alarms:
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
        if timer_id in active_timers:
            timer_info = active_timers[timer_id]
            timer_info['thread'].cancel()
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
        if alarm_id in active_alarms:
            alarm_info = active_alarms[alarm_id]
            alarm_info['thread'].cancel()
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

        # Cancel all timers
        for timer_id in list(active_timers.keys()):
            active_timers[timer_id]['thread'].cancel()
            del active_timers[timer_id]
            cancelled_count += 1

        # Cancel all alarms
        for alarm_id in list(active_alarms.keys()):
            active_alarms[alarm_id]['thread'].cancel()
            del active_alarms[alarm_id]
            cancelled_count += 1

        if cancelled_count == 0:
            return "ℹ️ No active timers or alarms to cancel."

        return f"✅ Cancelled {cancelled_count} timer(s) and alarm(s)."

    except Exception as e:
        return f"Error cancelling all timers: {e}"


# Productivity tools list
productivity_tools = [
    set_timer,
    set_alarm,
    list_active_timers,
    cancel_timer,
    cancel_alarm,
    cancel_all_timers_and_alarms,
]
