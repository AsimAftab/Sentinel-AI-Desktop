# test_productivity_agent.py
# Test script for the Productivity Agent (Timers and Alarms)

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

from src.graph.graph_builder import graph

def test_productivity_agent(command: str):
    """Test the productivity agent with a command."""
    print(f"\n{'='*60}")
    print(f"Testing command: '{command}'")
    print('='*60)

    try:
        result = graph.invoke({
            "messages": [("user", command)]
        })

        # Print the response
        final_message = result["messages"][-1]
        if isinstance(final_message, tuple):
            print(f"\n✅ Response:\n{final_message[1]}")
        else:
            print(f"\n✅ Response:\n{final_message.content if hasattr(final_message, 'content') else final_message}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n🤖 SENTINEL AI - PRODUCTIVITY AGENT TEST\n")

    # Test commands
    test_commands = [
        # Timer tests
        "Set a timer for 1 minute",
        "Set a timer for 5 minutes named Coffee break",
        "Set a 2 minute timer",
        "List all timers",

        # Alarm tests
        "Set an alarm for 3:30 PM",
        "Set an alarm for 2pm named Meeting",
        "List all alarms",

        # Cancel tests
        "Cancel timer 1",
        "Cancel alarm 1",
        "Cancel all timers and alarms",
    ]

    print("Available test commands:")
    for i, cmd in enumerate(test_commands, 1):
        print(f"{i}. {cmd}")

    print("\n" + "="*60)
    print("INTERACTIVE MODE")
    print("="*60)
    print(f"Type a command or enter a number (1-{len(test_commands)}) to test.")
    print("Type 'quit' or 'exit' to stop.\n")

    while True:
        try:
            user_input = input("🎤 Command: ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break

            if not user_input:
                continue

            # Check if user entered a number
            if user_input.isdigit():
                idx = int(user_input) - 1
                if 0 <= idx < len(test_commands):
                    command = test_commands[idx]
                else:
                    print(f"❌ Invalid number. Please enter 1-{len(test_commands)}")
                    continue
            else:
                command = user_input

            test_productivity_agent(command)

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
