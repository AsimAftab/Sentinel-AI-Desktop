
from src.utils.speech_recognizer import SpeechRecognitionAgent
from src.utils.wake_word_listener import WakeWordListener
from src.utils.langgraph_router import route_to_langgraph
from src.utils.text_to_speech import get_tts_instance
from dotenv import load_dotenv
import os
import sys
import re

# Event system for frontend integration (optional - only if integration layer is present)
try:
    # Try importing from integration package (when run via launcher)
    from integration.event_bus import EventBus, EventType, BackendStatus
    _event_bus = EventBus()
    _has_event_bus = True
except ImportError:
    try:
        # Fallback: try importing directly (when integration is in sys.path)
        from event_bus import EventBus, EventType, BackendStatus  # type: ignore
        _event_bus = EventBus()
        _has_event_bus = True
    except ImportError:
        # No integration layer available - backend runs standalone
        _event_bus = None
        _has_event_bus = False


def _emit_event(event_type, status=None, data=None):
    """Helper to emit events if event bus is available."""
    if _has_event_bus and _event_bus:
        try:
            _event_bus.emit(event_type, status=status, data=data)
        except Exception as e:
            # Don't crash backend if event emission fails
            print(f"⚠️ Event emission failed: {e}")


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
            # Emit: Listening for wake word
            _emit_event(EventType.LISTENING_FOR_WAKE_WORD, status=BackendStatus.LISTENING)

            wake_listener.wait_for_wake_word()

            # Emit: Wake word detected
            _emit_event(EventType.WAKE_WORD_DETECTED, status=BackendStatus.WAKE_WORD_DETECTED)

            print("🎙️ Listening for command...")

            # Emit: Listening for command
            _emit_event(EventType.LISTENING_FOR_COMMAND, status=BackendStatus.PROCESSING)

            command = recognizer.listen_command(timeout=5, phrase_time_limit=10)

            if command:
                print(f"🧠 Recognized: {command}")

                # Emit: Command received
                _emit_event(EventType.COMMAND_RECEIVED, data=command)

                # Start conversation loop
                conversation_history = [command]
                turn_count = 0

                while turn_count < max_turns:
                    # Emit: Processing command
                    _emit_event(EventType.PROCESSING_COMMAND, status=BackendStatus.PROCESSING)

                    # Get response from LangGraph with conversation context
                    full_context = " ".join(conversation_history)
                    response = route_to_langgraph(full_context)
                    print(f"🤖 LangGraph response: {response}")

                    # Emit: Response generated
                    _emit_event(EventType.RESPONSE_GENERATED, data=response)

                    # Speak the response
                    if response:
                        _emit_event(EventType.TTS_SPEAKING, status=BackendStatus.SPEAKING)
                        tts.speak(response, blocking=True)
                        _emit_event(EventType.TTS_FINISHED)

                    # Check if agent is asking for more information
                    if is_follow_up_question(response):
                        print("💬 Waiting for follow-up... (or say 'cancel' to stop)")

                        # Emit: Waiting for follow-up
                        _emit_event(EventType.FOLLOW_UP_DETECTED)

                        # Listen for follow-up without wake word
                        follow_up = recognizer.listen_command(timeout=10, phrase_time_limit=15)

                        if not follow_up:
                            print("⏱️ No follow-up detected. Ending conversation.")
                            _emit_event(EventType.CONVERSATION_ENDED)
                            break

                        # Check for exit phrases
                        exit_phrases = ["cancel", "nevermind", "never mind", "stop", "quit", "exit"]
                        if any(phrase in follow_up.lower() for phrase in exit_phrases):
                            print("🛑 Conversation cancelled by user.")
                            tts.speak("Okay, cancelled.", blocking=True)
                            _emit_event(EventType.CONVERSATION_ENDED)
                            break

                        print(f"🧠 Follow-up: {follow_up}")
                        _emit_event(EventType.COMMAND_RECEIVED, data=follow_up)
                        conversation_history.append(follow_up)
                        turn_count += 1
                    else:
                        # Agent provided final answer, end conversation
                        print("✅ Conversation complete.")
                        _emit_event(EventType.CONVERSATION_ENDED)
                        break

                # Clear conversation history
                conversation_history = []

            else:
                print("⚠️ No command detected.")

    except KeyboardInterrupt:
        print("\n🛑 Shutting down Sentinel agent.")
        wake_listener.stop()
        sys.exit(0)