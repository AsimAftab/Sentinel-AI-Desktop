# test_screenshot_simple.py
# Simple direct test for screenshot functionality

import os
import sys

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.tools.system_tools import take_screenshot, get_screen_size, SCREENSHOT_AVAILABLE

def test_screenshot_tools():
    """Direct test of screenshot tools without the full agent system."""

    print("\n" + "="*60)
    print("SCREENSHOT TOOLS - DIRECT TEST")
    print("="*60 + "\n")

    # Check if libraries are available
    if not SCREENSHOT_AVAILABLE:
        print("[ERROR] Screenshot library not available!")
        print("Install with: pip install pyautogui pillow")
        return

    print("[OK] Screenshot library is available!\n")

    # Test 1: Get screen size
    print("TEST 1: Getting screen size...")
    print("-" * 40)
    result = get_screen_size.invoke({})
    print(result)
    print()

    # Test 2: Take a simple screenshot
    print("TEST 2: Taking screenshot with auto-generated filename...")
    print("-" * 40)
    result = take_screenshot.invoke({})
    print(result)
    print()

    # Test 3: Take screenshot with custom name
    print("TEST 3: Taking screenshot with custom filename...")
    print("-" * 40)
    result = take_screenshot.invoke({"filename": "test_screenshot"})
    print(result)
    print()

    # Check if screenshots directory was created
    screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots")
    if os.path.exists(screenshots_dir):
        files = os.listdir(screenshots_dir)
        print(f"[OK] Screenshots folder contains {len(files)} file(s):")
        for f in files:
            filepath = os.path.join(screenshots_dir, f)
            size_kb = os.path.getsize(filepath) / 1024
            print(f"   - {f} ({size_kb:.1f} KB)")
    else:
        print("[WARNING] Screenshots directory not found")

    print("\n" + "="*60)
    print("TESTS COMPLETED!")
    print("="*60)


if __name__ == "__main__":
    test_screenshot_tools()
