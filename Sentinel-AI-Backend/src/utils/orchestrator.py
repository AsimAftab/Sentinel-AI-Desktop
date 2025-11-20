
from src.utils.speech_recognizer import SpeechRecognitionAgent
from src.utils.wake_word_listener import WakeWordListener
from src.utils.langgraph_router import route_to_langgraph
from src.utils.text_to_speech import get_tts_instance
from dotenv import load_dotenv
import os
import sys
import re


def is_follow_up_question(response: str) -> bool:
    """
    Detects if the AI response is asking a follow-up question.
    Returns True if conversation should continue.
    """
    if not response:
        return False

    response_lower = response.lower()

    # Question indicators
    question_keywords = [
        "could you",
        "can you",
        "would you",
        "what",
        "when",
        "where",
        "which",
        "who",
        "how",
        "do you want",
        "would you like",
        "please provide",
        "please tell",
        "let me know",
        "tell me",
        "specify",
        "?",  # Contains question mark
    ]

    # Check for question indicators
    for keyword in question_keywords:
        if keyword in response_lower:
            return True

    return False


def run_sentinel_agent():
    load_dotenv()
    access_key = os.getenv("PORCUPINE_KEY")
    keyword_path = "src/wakeword/Sentinel_en_windows_v3_0_0.ppn"

    wake_listener = WakeWordListener(keyword_path=keyword_path, access_key=access_key)
    recognizer = SpeechRecognitionAgent()
    tts = get_tts_instance()  # Initialize text-to-speech

    wake_listener.start()
    print("🟢 Waiting for wake word... (Press Ctrl+C to exit)")

    # Conversation state
    conversation_history = []
    max_turns = 5  # Maximum conversation turns

    try:
        while True:
            wake_listener.wait_for_wake_word()
            print("🎙️ Listening for command...")
            command = recognizer.listen_command(timeout=5, phrase_time_limit=10)

            if command:
                print(f"🧠 Recognized: {command}")

                # Start conversation loop
                conversation_history = [command]
                turn_count = 0

                while turn_count < max_turns:
                    # Get response from LangGraph with conversation context
                    full_context = " ".join(conversation_history)
                    response = route_to_langgraph(full_context)
                    print(f"🤖 LangGraph response: {response}")

                    # Speak the response
                    if response:
                        tts.speak(response, blocking=True)

                    # Check if agent is asking for more information
                    if is_follow_up_question(response):
                        print("💬 Waiting for follow-up... (or say 'cancel' to stop)")

                        # Listen for follow-up without wake word
                        follow_up = recognizer.listen_command(timeout=10, phrase_time_limit=15)

                        if not follow_up:
                            print("⏱️ No follow-up detected. Ending conversation.")
                            break

                        # Check for exit phrases
                        exit_phrases = ["cancel", "nevermind", "never mind", "stop", "quit", "exit"]
                        if any(phrase in follow_up.lower() for phrase in exit_phrases):
                            print("🛑 Conversation cancelled by user.")
                            tts.speak("Okay, cancelled.", blocking=True)
                            break

                        print(f"🧠 Follow-up: {follow_up}")
                        conversation_history.append(follow_up)
                        turn_count += 1
                    else:
                        # Agent provided final answer, end conversation
                        print("✅ Conversation complete.")
                        break

                # Clear conversation history
                conversation_history = []

            else:
                print("⚠️ No command detected.")

    except KeyboardInterrupt:
        print("\n🛑 Shutting down Sentinel agent.")
        wake_listener.stop()
        sys.exit(0)