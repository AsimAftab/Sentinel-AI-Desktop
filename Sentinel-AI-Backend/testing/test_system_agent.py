# test_system_agent.py
# Quick test script for the System Control Agent

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.graph.graph_builder import graph

def test_system_agent(command: str):
    """Test the system agent with a voice command."""
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
            print(f"\n✅ Response: {final_message[1]}")
        else:
            print(f"\n✅ Response: {final_message.content if hasattr(final_message, 'content') else final_message}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n🤖 SENTINEL AI - SYSTEM CONTROL AGENT TEST\n")

    # Test commands
    test_commands = [
        # Volume tests
        "What's my current volume?",
        "Increase volume by 5 percent",
        "Set volume to 50",

        # Brightness tests
        "What's my current brightness?",

        # Application tests
        "Open notepad",
        "List running applications",
        "Close notepad",

        # Screenshot tests
        "Take a screenshot",
        "What's my screen size?",
        "Take a screenshot named test_image",
    ]

    print("Available test commands:")
    for i, cmd in enumerate(test_commands, 1):
        print(f"{i}. {cmd}")

    print("\n" + "="*60)
    print("INTERACTIVE MODE")
    print("="*60)
    print("Type a command or enter a number (1-{}) to test.".format(len(test_commands)))
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
                    print("❌ Invalid number. Please enter 1-{}".format(len(test_commands)))
                    continue
            else:
                command = user_input

            test_system_agent(command)

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
