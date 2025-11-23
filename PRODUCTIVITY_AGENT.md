# Productivity Agent

## Overview

The Productivity Agent is a voice-activated time management assistant that helps you stay on track with timers and alarms. Perfect for Pomodoro technique, reminders, and time-based workflows.

## Features

### ⏱️ Timer Management (3 tools)
- **Set Timer**: Create countdown timers from 1 minute to 8 hours
- **List Timers**: View all active timers with remaining time
- **Cancel Timer**: Stop a timer before it completes

### ⏰ Alarm Management (3 tools)
- **Set Alarm**: Create time-based alarms for specific times
- **List Alarms**: View all scheduled alarms
- **Cancel Alarm**: Remove a scheduled alarm

### 🎯 Quick Actions (1 tool)
- **Cancel All**: Clear all active timers and alarms at once

## Voice Command Examples

### Timers
```
"Sentinel, set a timer for 5 minutes"
"Sentinel, set a 25 minute timer named Pomodoro"
"Sentinel, set a timer for 1 hour"
"Sentinel, set a 30 minute timer for cooking"
"Sentinel, list my timers"
"Sentinel, cancel timer 1"
```

### Alarms
```
"Sentinel, set an alarm for 3:30 PM"
"Sentinel, set an alarm for 2pm named Meeting"
"Sentinel, set alarm for 15:00"
"Sentinel, list my alarms"
"Sentinel, cancel alarm 1"
```

### Quick Actions
```
"Sentinel, cancel all timers"
"Sentinel, list all timers and alarms"
```

## Supported Time Formats

### For Timers (Duration)
- Minutes only: "5 minutes", "30 minutes"
- Hours: "1 hour", "2 hours"
- Hours and minutes: "1 hour 30 minutes"
- Range: 1 minute to 480 minutes (8 hours)

### For Alarms (Specific Time)
- 12-hour format: "3:30 PM", "2:15 AM"
- 24-hour format: "15:30", "14:00"
- Short format: "3pm", "2am"
- Auto-detection: If time has passed today, sets for tomorrow

## Use Cases

### 🍅 Pomodoro Technique
```
"Sentinel, set a 25 minute timer named Work session"
# Work for 25 minutes
# When timer goes off...
"Sentinel, set a 5 minute timer named Break"
```

### 💼 Meeting Reminders
```
"Sentinel, set an alarm for 2pm named Team meeting"
"Sentinel, set an alarm for 3:30 PM named Client call"
```

### 🍳 Cooking & Tasks
```
"Sentinel, set a 12 minute timer named Pasta"
"Sentinel, set a 45 minute timer named Laundry"
```

### 📚 Study Sessions
```
"Sentinel, set a 50 minute timer named Study"
"Sentinel, set a 10 minute timer named Break"
```

## Testing

### Quick Test (Direct tool test)
```bash
cd Sentinel-AI-Backend
python test_productivity_simple.py
```

This runs a 30-second demo showing:
- Setting multiple timers
- Setting alarms
- Listing active timers/alarms
- Cancelling timers
- Countdown functionality

### Full Test (With voice)
```bash
python launcher.py
# Say: "Sentinel" → "set a timer for 5 minutes"
```

### Interactive Test Menu
```bash
cd Sentinel-AI-Backend
python test_productivity_agent.py
# Choose from preset commands or type your own
```

## Technical Details

### Implementation

**File:** `src/tools/productivity_tools.py`

**Tools:**
1. `set_timer(duration_minutes, name)` - Creates countdown timer
2. `set_alarm(time_str, name)` - Creates time-based alarm
3. `list_active_timers()` - Shows all active timers/alarms
4. `cancel_timer(timer_id)` - Cancels specific timer
5. `cancel_alarm(alarm_id)` - Cancels specific alarm
6. `cancel_all_timers_and_alarms()` - Cancels everything

**Technology:**
- Uses Python's `threading.Timer` for non-blocking timers
- `datetime` for time parsing and calculations
- `winsound` for Windows notification beeps (built-in)

### Dependencies

**No additional dependencies required!**

All functionality uses Python standard library:
- `threading` - For timer threads
- `datetime` - For time handling
- `winsound` - For notification sounds (Windows built-in)

### Notification System

When a timer completes or alarm goes off:
1. **Visual notification**: Console message with details
2. **Audio notification**: Triple beep sound (Windows)
3. **Auto-cleanup**: Timer/alarm removed from active list

Example notification:
```
============================================================
⏰ TIMER COMPLETED!
Timer: Coffee Break
Duration: 5 minute(s)
============================================================
```

### Thread Safety

- Each timer/alarm runs in its own daemon thread
- Global dictionaries track active timers/alarms
- Thread-safe operations for add/remove/list
- Daemon threads automatically terminate with main program

### File Changes

**New Files:**
- `src/tools/productivity_tools.py` - Timer and alarm tools
- `test_productivity_agent.py` - Interactive test script
- `test_productivity_simple.py` - Quick verification test

**Modified Files:**
- `src/graph/graph_builder.py` - Added Productivity agent to graph
- No requirements.txt changes needed (uses stdlib only)

### Architecture

```
User Voice Command → Wake Word Detection → Speech Recognition
    → Supervisor Agent → Productivity Agent (with 6 tools)
    → Set Timer/Alarm → Background Thread
    → Notification When Complete
```

**Agent Routing:**
- Supervisor detects timer/alarm keywords
- Routes to Productivity agent
- Agent selects appropriate tool
- Returns confirmation with ID and details
- Timer/alarm runs in background

### Platform Support

**Currently Supported:**
- ✅ Windows 10/11 (notification sounds via winsound)

**Future Support:**
- ⏳ macOS (requires different notification system)
- ⏳ Linux (requires different notification system)

## Troubleshooting

### Timer/Alarm Not Completing

**Possible causes:**
1. Program terminated before timer completed
2. Daemon threads end when main program exits

**Solution:**
- Keep Sentinel AI running for timers to complete
- Timers persist as long as the program is running

### No Notification Sound

**Possible causes:**
1. System volume muted
2. Running on non-Windows platform

**Solution:**
- Check system volume
- On macOS/Linux, sound notifications not yet implemented

### Can't Cancel Timer/Alarm

**Issue:** "No active timer found with ID: X"

**Solution:**
- Use `list_active_timers` to see current IDs
- Timer may have already completed
- Check if you're using the correct ID number

### Time Format Not Recognized

**Issue:** "Could not parse time"

**Solution:**
Use supported formats:
- ✅ "3:30 PM"
- ✅ "15:30"
- ✅ "3pm"
- ❌ "3:30" (ambiguous - AM or PM?)
- ❌ "half past three" (not supported)

## Example Session

```
User: "Sentinel"
[Wake word detected]

User: "Set a timer for 5 minutes named Tea"
Productivity: "⏱️ Timer set: 'Tea'
⏰ Duration: 5 minutes
🕐 Will complete at: 04:47 PM
🆔 Timer ID: 1"

User: "Sentinel"
User: "Set an alarm for 3pm"
Productivity: "⏰ Alarm set: 'Alarm'
🕐 Time: 03:00 PM (today)
⏱️ Time until alarm: 2 hours 13 minutes
🆔 Alarm ID: 1"

User: "Sentinel"
User: "List my timers"
Productivity: "⏱️ **Active Timers:**
🆔 1: 'Tea' - 4m 32s remaining

⏰ **Active Alarms:**
🆔 1: 'Alarm' at 03:00 PM (2h 13m remaining)"

[5 minutes later...]
============================================================
⏰ TIMER COMPLETED!
Timer: Tea
Duration: 5 minute(s)
============================================================
[Triple beep sound plays]
```

## Future Enhancements

Potential additions:
- **Recurring alarms**: Daily/weekly repeating alarms
- **Snooze functionality**: Delay alarm for X minutes
- **Custom sounds**: Upload custom notification sounds
- **Timer presets**: Save frequently-used timer durations
- **Pause/resume**: Pause and resume timers
- **Timer history**: Log of completed timers
- **Desktop notifications**: System tray notifications (Windows 10+)
- **Mobile sync**: Sync timers across devices

## Integration with Other Agents

The Productivity Agent works seamlessly with other agents:

**Example workflows:**
```
# Meeting workflow
"Sentinel, create a meeting at 3pm" → Meeting Agent
"Sentinel, set an alarm for 2:55 PM named Meeting reminder" → Productivity Agent

# Study music workflow
"Sentinel, play focus music" → Music Agent
"Sentinel, set a 50 minute timer named Study session" → Productivity Agent

# Cooking workflow
"Sentinel, search for pasta recipe" → Browser Agent
"Sentinel, set a 12 minute timer named Pasta" → Productivity Agent
```

## Security & Privacy

✅ **No cloud dependencies**: All timers/alarms run locally
✅ **No data collection**: Timer data never leaves your machine
✅ **No network access**: Works completely offline
✅ **Lightweight**: Minimal CPU/memory usage per timer

---

**Total Tools:** 6
**Dependencies:** 0 (uses Python stdlib)
**Platform:** Windows (macOS/Linux support planned)
**Status:** ✅ Fully Implemented and Tested
