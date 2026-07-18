# System Control Agent

## Overview

The System Control Agent is a new agent added to Sentinel AI that enables voice-controlled system operations on your Windows computer.

## Features

### 🔊 Volume Control (6 tools)
- **Increase Volume**: Increase system volume by percentage
- **Decrease Volume**: Decrease system volume by percentage
- **Set Volume**: Set volume to specific level (0-100%)
- **Get Current Volume**: Check current volume level
- **Mute Volume**: Mute system audio
- **Unmute Volume**: Unmute system audio

### 💡 Brightness Control (4 tools)
- **Increase Brightness**: Increase screen brightness by percentage
- **Decrease Brightness**: Decrease screen brightness by percentage
- **Set Brightness**: Set brightness to specific level (0-100%)
- **Get Current Brightness**: Check current brightness level

### 💻 Application Control (3 tools)
- **Open Application**: Open apps by name (notepad, calculator, chrome, spotify, etc.)
- **Close Application**: Close running applications
- **List Running Applications**: See all currently running apps

### 📸 Screenshot Control (2 tools)
- **Take Screenshot**: Capture entire screen and save with timestamp
- **Get Screen Size**: Check current screen resolution

## Voice Command Examples

### Volume Control
```
"Sentinel, increase volume by 10"
"Sentinel, set volume to 50 percent"
"Sentinel, what's my current volume?"
"Sentinel, mute the volume"
"Sentinel, unmute"
```

### Brightness Control
```
"Sentinel, increase brightness"
"Sentinel, decrease brightness by 20"
"Sentinel, set brightness to 75"
"Sentinel, what's my current brightness?"
```

### Application Control
```
"Sentinel, open notepad"
"Sentinel, open calculator"
"Sentinel, open chrome"
"Sentinel, open spotify"
"Sentinel, list running applications"
"Sentinel, close notepad"
"Sentinel, close spotify"
```

### Screenshot Control
```
"Sentinel, take a screenshot"
"Sentinel, take a screenshot named my_image"
"Sentinel, what's my screen size?"
"Sentinel, capture my screen"
```

## Supported Applications

The agent supports common Windows applications including:

**Productivity:**
- Notepad
- Calculator
- Paint
- File Explorer
- Command Prompt
- PowerShell
- Task Manager
- Control Panel
- Windows Settings

**Browsers:**
- Chrome
- Firefox
- Edge

**Microsoft Office:**
- Word
- Excel
- PowerPoint
- Outlook

**Other Apps:**
- Spotify
- Discord
- VS Code
- And any .exe application by name

## Testing

### Quick Test (Without Voice)

Run the test script to verify functionality:

```bash
cd Sentinel-AI-Backend
python test_system_agent.py
```

This opens an interactive test mode where you can type commands or select from preset test commands.

### Test with Voice

Run the full Sentinel AI system:

```bash
python launcher.py
```

Then say:
1. "Sentinel" (wake word)
2. Say your command (e.g., "increase volume by 10")

## Technical Details

### Dependencies Added

```txt
pycaw==20240210          # Windows audio control
comtypes==1.4.8          # COM interface for pycaw
screen-brightness-control==0.23.0  # Display brightness control
psutil==6.1.1            # Process and system utilities
pyautogui==0.9.54        # Screenshot and screen automation
Pillow==11.0.0           # Image processing for screenshots
```

### File Changes

**New Files:**
- `Sentinel-AI-Backend/src/tools/system_tools.py` - System control tool implementations
- `Sentinel-AI-Backend/test_system_agent.py` - Test script

**Modified Files:**
- `Sentinel-AI-Backend/requirements.txt` - Added system control dependencies
- `Sentinel-AI-Backend/src/graph/graph_builder.py` - Added System agent to multi-agent graph

### Architecture

The System agent follows the same pattern as other agents:

```
User Voice Command → Wake Word Detection → Speech Recognition
    → Supervisor Agent → System Agent (with 15 tools)
    → Execute Action → TTS Response
```

**Agent Routing:**
- Supervisor determines if command requires system control
- Routes to System agent if volume/brightness/app-related
- System agent uses ReAct pattern to select and execute appropriate tool
- Returns result to user via voice

### Platform Support

**Currently Supported:**
- ✅ Windows 10/11 (fully tested)

**Future Support:**
- ⏳ macOS (requires different libraries)
- ⏳ Linux (requires different libraries)

## Troubleshooting

### "Required libraries not installed" Error

If you see this error, install dependencies:

```bash
cd Sentinel-AI-Backend
pip install pycaw comtypes screen-brightness-control psutil
```

### Brightness Control Not Working

Some systems may not support brightness control via software. This depends on:
- Display type (external monitors may not support it)
- Graphics drivers
- Laptop vs Desktop (laptops have better support)

### Application Won't Open

1. Try using the full application name
2. Check if the application is installed
3. Try opening it manually first to verify it works
4. Some apps may require administrator privileges

### Permission Errors

Some system operations may require administrator privileges. Run Sentinel AI as administrator:

1. Right-click `launcher.py`
2. Select "Run as administrator"

### Screenshot Issues

**Where are screenshots saved?**
- Screenshots are saved to `Sentinel-AI-Backend/screenshots/` folder
- Files are named with timestamp: `screenshot_20250123_143052.png`
- You can specify custom names: "take a screenshot named my_image"

**Screenshot on multi-monitor setup:**
- The tool captures all connected displays as one large screenshot
- The entire virtual screen is captured (spanning all monitors)

## Example Session

```
User: "Sentinel"
[Wake word detected]

User: "What's my current volume?"
System: "🔊 Current volume: 45%"

User: "Sentinel"
User: "Increase it by 10"
System: "🔊 Volume increased by 10% → Now at 55%"

User: "Sentinel"
User: "Open notepad"
System: "✅ Opened notepad"

User: "Sentinel"
User: "List running applications"
System: "💻 Running Applications:
1. Chrome
2. Notepad
3. Spotify
..."

User: "Sentinel"
User: "Close notepad"
System: "✅ Closed 1 instance(s) of notepad"
```

## Future Enhancements

Potential additions to System agent:

- **File Operations**: Create/delete/move files and folders
- **Lock Screen**: Lock computer with voice
- **Shutdown/Restart**: System power controls
- **Window Management**: Minimize/maximize/switch windows
- **System Info**: Battery status, CPU usage, RAM usage
- **Clipboard**: Copy/paste operations
- **Network**: WiFi controls, network info
- **Screenshot Enhancements**: Delayed screenshot, screenshot with timer

## Security Considerations

⚠️ **Important Security Notes:**

1. **Admin Rights**: Some operations may require administrator privileges
2. **App Closing**: Can close any running application - use with caution
3. **Volume Control**: Can unmute or increase volume unexpectedly
4. **Voice Activation**: Ensure wake word detection is reliable to prevent accidental commands

## Integration with Frontend

The System agent works seamlessly with the existing Sentinel AI frontend:

- Backend status widget shows System agent activity
- Communication bus transmits system control events
- Real-time feedback appears in dashboard activity log

No changes needed to frontend code - integration layer handles everything!
