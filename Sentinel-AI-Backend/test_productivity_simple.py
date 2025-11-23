# test_productivity_simple.py
# Simple direct test for productivity tools (timers and alarms)

import os
import sys
import time

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.tools.productivity_tools import (
    set_timer,
    set_alarm,
    list_active_timers,
    cancel_timer,
    cancel_alarm
)

def test_productivity_tools():
    """Direct test of productivity tools without the full agent system."""

    print("\n" + "="*60)
    print("PRODUCTIVITY TOOLS - DIRECT TEST")
    print("="*60 + "\n")

    # Test 1: Set a short timer (1 minute)
    print("TEST 1: Setting a 1-minute timer...")
    print("-" * 40)
    result = set_timer.invoke({"duration_minutes": 1, "name": "Test Timer"})
    print(result)
    print()

    # Wait a moment
    time.sleep(1)

    # Test 2: Set another timer
    print("TEST 2: Setting a 2-minute timer...")
    print("-" * 40)
    result = set_timer.invoke({"duration_minutes": 2, "name": "Coffee Break"})
    print(result)
    print()

    # Test 3: Set an alarm
    print("TEST 3: Setting an alarm for 1 minute from now...")
    print("-" * 40)
    from datetime import datetime, timedelta
    alarm_time = (datetime.now() + timedelta(minutes=1)).strftime("%I:%M %p")
    result = set_alarm.invoke({"time_str": alarm_time, "name": "Test Alarm"})
    print(result)
    print()

    # Test 4: List active timers and alarms
    print("TEST 4: Listing all active timers and alarms...")
    print("-" * 40)
    result = list_active_timers.invoke({})
    print(result)
    print()

    # Test 5: Cancel timer 1
    print("TEST 5: Cancelling timer ID 1...")
    print("-" * 40)
    result = cancel_timer.invoke({"timer_id": 1})
    print(result)
    print()

    # Test 6: List again to verify
    print("TEST 6: Listing active timers after cancellation...")
    print("-" * 40)
    result = list_active_timers.invoke({})
    print(result)
    print()

    print("\n" + "="*60)
    print("TESTS COMPLETED!")
    print("="*60)
    print("\nNote: Remaining timers/alarms will complete in the background.")
    print("You should hear notification sounds when they go off.")
    print("\nWaiting 10 seconds to demonstrate timer completion...")

    # Wait for a bit to let timer 2 tick down
    for i in range(10, 0, -1):
        print(f"  {i} seconds remaining...")
        time.sleep(1)

    # Show final status
    print("\nFinal Status:")
    print("-" * 40)
    result = list_active_timers.invoke({})
    print(result)


if __name__ == "__main__":
    test_productivity_tools()
