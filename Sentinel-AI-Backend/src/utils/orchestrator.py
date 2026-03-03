from src.utils.speech_recognizer import SpeechRecognitionAgent
from src.utils.wake_word_listener import WakeWordListener
from src.utils.langgraph_router import route_to_langgraph
from src.utils.text_to_speech import get_tts_instance
from src.utils.agent_memory import get_agent_memory, MemoryType
from src.utils.log_config import get_logger
from dotenv import load_dotenv
import os
import sys
import re
import threading

logger = get_logger("orchestrator")

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
            logger.warning("Event emission failed: %s", e)


def normalize_dictation(text: str) -> str:
    """
    Normalize common voice dictation patterns so spoken technical content
    (email addresses, URLs) is converted to its written form.

    Examples:
        "asim dot dev at gmail dot com"  → "asim.dev@gmail.com"
        "Asim dot Dev dot cs@giftsonair.com" → "Asim.Dev.cs@giftsonair.com"
        "go to google dot com slash search" → "go to google.com/search"
    """
    if not text:
        return text

    # --- Email normalization ---
    # Case 1: Full dictated email — "local dot part at domain dot com"
    # Pattern: word( dot word)* at word( dot word)*
    full_email_re = re.compile(
        r"\b(\w+(?:\s+dot\s+\w+)*)\s+at\s+(\w+(?:\s+dot\s+\w+)+)\b",
        re.IGNORECASE,
    )

    def _replace_full_email(m):
        local = re.sub(r"\s+dot\s+", ".", m.group(1), flags=re.IGNORECASE)
        domain = re.sub(r"\s+dot\s+", ".", m.group(2), flags=re.IGNORECASE)
        return f"{local}@{domain}"

    text = full_email_re.sub(_replace_full_email, text)

    # Case 2: Partial — STT already produced "@" but left "dot" literal
    # e.g. "Asim dot Dev dot cs@giftsonair.com"
    # Replace " dot " with "." when adjacent to an @ somewhere in the text
    if "@" in text:
        text = re.sub(r"\b(\w+)\s+dot\s+(?=\w)", r"\1.", text, flags=re.IGNORECASE)

    # --- URL normalization ---
    # "google dot com" → "google.com"  (only when followed by a TLD-like word)
    tlds = r"(?:com|org|net|io|dev|ai|co|edu|gov|app|xyz)"
    text = re.sub(
        rf"\b(\w+)\s+dot\s+({tlds})\b", r"\1.\2", text, flags=re.IGNORECASE
    )
    # "slash" → "/" after a domain (e.g. "google.com slash search")
    text = re.sub(
        rf"(\.\w{{2,6}})\s+slash\s+", r"\1/", text, flags=re.IGNORECASE
    )

    # --- Common symbol dictation ---
    # "dash" / "hyphen" between words (only in technical-looking sequences)
    # "underscore" between words
    # These are left alone for now to avoid false positives in normal speech.

    return text


def is_follow_up_question(response: str) -> bool:
    """
    Detects if the AI response is asking a follow-up question.
    Returns True if conversation should continue.

    Uses two heuristics:
    1. If the response ends with '?', it is asking something.
    2. If the last sentence starts with a direct-question phrase aimed at the user,
       it is prompting for more input.

    Single-word matches like "what", "how", "where" are intentionally excluded
    to avoid false positives on statements like "Here's what I found".
    """
    if not response:
        return False

    stripped = response.strip()

    # If the response ends with a question mark, treat as follow-up
    if stripped.endswith("?"):
        return True

    # Extract the last sentence.
    # Split on sentence-ending punctuation followed by whitespace, markdown, or
    # closing parentheses/brackets (handles "**bold?** (hint)\n\nPlease provide...")
    last_sentence = re.split(r"[.!?][*_)\]]*\s+", stripped)[-1].strip().lower()

    # Strip leading "please " so "please let me know" matches "let me know", etc.
    check_sentence = last_sentence
    if check_sentence.startswith("please "):
        check_sentence = check_sentence[7:]

    # Direct-question starters that indicate the agent wants user input
    direct_question_starters = [
        "could you",
        "can you",
        "would you",
        "would you like",
        "do you want",
        "do you need",
        "provide",
        "specify",
        "tell me",
        "let me know",
        "share",
        "confirm",
    ]

    for starter in direct_question_starters:
        if check_sentence.startswith(starter):
            return True

    return False


def build_conversation_context(history: list[str]) -> str:
    """
    Build context for the next turn.

    Rule: the latest user instruction is authoritative. Earlier requests are
    context only and may be superseded if they conflict.
    """
    if not history:
        return ""

    if len(history) == 1:
        return history[0]

    previous_requests = "\n".join([f"- {item}" for item in history[:-1]])
    latest_request = history[-1]

    return (
        "The user is continuing the same conversation.\n"
        "Use prior requests as context only.\n"
        "If the latest request conflicts with earlier ones, follow the latest request.\n\n"
        f"Earlier requests:\n{previous_requests}\n\n"
        f"Latest request (authoritative):\n{latest_request}"
    )


def run_sentinel_agent(shutdown_event=None, container=None):
    load_dotenv()
    access_key = os.getenv("PORCUPINE_KEY")

    # Wake word configuration
    wake_word_sensitivity = float(os.getenv("WAKE_WORD_SENSITIVITY", "0.7"))
    wake_word_paths_raw = os.getenv(
        "WAKE_WORD_PATHS", "src/wakeword/Sentinel_en_windows_v3_0_0.ppn"
    )
    wake_word_paths = [p.strip() for p in wake_word_paths_raw.split(",") if p.strip()]

    # Speech recognition configuration
    stt_language = os.getenv("STT_LANGUAGE", "en-US")
    stt_energy_threshold = os.getenv("STT_ENERGY_THRESHOLD")
    stt_pause_threshold = os.getenv("STT_PAUSE_THRESHOLD")
    continuous_listening = os.getenv("CONTINUOUS_LISTENING", "false").lower() == "true"

    # Use container services if provided, otherwise fall back to singletons
    if container is not None:
        tts = container.tts
        memory = container.agent_memory
        if shutdown_event is None:
            shutdown_event = container.shutdown_event
    else:
        tts = get_tts_instance()
        memory = get_agent_memory()

    wake_listener = WakeWordListener(
        keyword_paths=wake_word_paths,
        access_key=access_key,
        sensitivities=wake_word_sensitivity,
    )

    # Build recognizer kwargs from env config
    recognizer_kwargs = {}
    if stt_energy_threshold:
        recognizer_kwargs["energy_threshold"] = int(stt_energy_threshold)
    if stt_pause_threshold:
        recognizer_kwargs["pause_threshold"] = float(stt_pause_threshold)
    recognizer = SpeechRecognitionAgent(**recognizer_kwargs)

    wake_listener.start()
    if continuous_listening:
        logger.info("Continuous listening mode enabled (wake word skipped)")
    else:
        logger.info("Waiting for wake word... (Press Ctrl+C to exit)")
    logger.info("Agent memory initialized")

    # Conversation state
    conversation_history = []
    max_turns = 5  # Maximum conversation turns

    def _should_run():
        return not (shutdown_event and shutdown_event.is_set())

    try:
        while _should_run():
            if continuous_listening:
                # Skip wake word, go directly to listening for command
                _emit_event(EventType.LISTENING_FOR_COMMAND, status=BackendStatus.PROCESSING)
                logger.info("Listening for command (continuous mode)...")
            else:
                # Emit: Listening for wake word
                _emit_event(EventType.LISTENING_FOR_WAKE_WORD, status=BackendStatus.LISTENING)

                detected = wake_listener.wait_for_wake_word(timeout=1.0)
                if not detected:
                    continue

                # Emit: Wake word detected
                _emit_event(EventType.WAKE_WORD_DETECTED, status=BackendStatus.WAKE_WORD_DETECTED)

                logger.info("Listening for command...")

                # Emit: Listening for command
                _emit_event(EventType.LISTENING_FOR_COMMAND, status=BackendStatus.PROCESSING)

            command = recognizer.listen_command(
                timeout=5, phrase_time_limit=10, language=stt_language
            )

            if command:
                # Normalize dictated emails/URLs ("dot" → ".", "at" → "@", etc.)
                command = normalize_dictation(command)
                logger.info("Recognized: %s", command)

                # Emit: Command received
                _emit_event(EventType.COMMAND_RECEIVED, data=command)

                # Start new memory session for this conversation
                session_id = memory.start_session()
                logger.info("Memory session started: %s...", session_id[:8])

                # Store the initial command in memory
                memory.store_command(command, session_id=session_id)

                # Start conversation loop — always clean up session in finally
                conversation_history = [command]
                turn_count = 0

                try:
                    while turn_count < max_turns:
                        # Emit: Processing command
                        _emit_event(EventType.PROCESSING_COMMAND, status=BackendStatus.PROCESSING)

                        # Build context so latest follow-up overrides conflicting earlier intents
                        full_context = build_conversation_context(conversation_history)
                        response = route_to_langgraph(full_context)
                        logger.info("LangGraph response: %s", response)

                        # Emit: Response generated
                        _emit_event(EventType.RESPONSE_GENERATED, data=response)

                        # Speak the response in a background thread so events can still be emitted.
                        # We still wait for speech to finish before listening again.
                        if response:
                            _emit_event(EventType.TTS_SPEAKING, status=BackendStatus.SPEAKING)
                            tts_done = threading.Event()

                            def _speak_and_signal():
                                tts.speak(response, blocking=True)
                                tts_done.set()

                            tts_thread = threading.Thread(target=_speak_and_signal, daemon=True)
                            tts_thread.start()
                            tts_done.wait()  # Block until speech is complete
                            _emit_event(EventType.TTS_FINISHED)

                        # Check if agent is asking for more information
                        if is_follow_up_question(response):
                            logger.info("Waiting for follow-up...")

                            # Emit: Waiting for follow-up
                            _emit_event(EventType.FOLLOW_UP_DETECTED)

                            # Listen for follow-up without wake word
                            follow_up = recognizer.listen_command(
                                timeout=10, phrase_time_limit=15, language=stt_language
                            )

                            if not follow_up:
                                logger.warning("No follow-up detected. Ending conversation.")
                                _emit_event(EventType.CONVERSATION_ENDED)
                                break

                            # Check for exit phrases
                            exit_phrases = [
                                "cancel",
                                "nevermind",
                                "never mind",
                                "stop",
                                "quit",
                                "exit",
                            ]
                            if any(phrase in follow_up.lower() for phrase in exit_phrases):
                                logger.info("Conversation cancelled by user.")
                                tts.speak("Okay, cancelled.", blocking=False)
                                _emit_event(EventType.CONVERSATION_ENDED)
                                break

                            follow_up = normalize_dictation(follow_up)
                            logger.info("Follow-up: %s", follow_up)
                            _emit_event(EventType.COMMAND_RECEIVED, data=follow_up)

                            # Store follow-up in memory
                            memory.store_command(follow_up, session_id=session_id)

                            conversation_history.append(follow_up)
                            turn_count += 1
                        else:
                            # Agent provided final answer, end conversation
                            logger.info("Conversation complete.")
                            _emit_event(EventType.CONVERSATION_ENDED)
                            break
                finally:
                    # Always end session — prevents orphaned MongoDB docs on crash
                    memory.end_session()

                # Clear conversation history
                conversation_history = []

            else:
                logger.warning("No command detected.")

    except KeyboardInterrupt:
        logger.info("Shutting down Sentinel agent.")
    finally:
        memory.end_session()
        wake_listener.stop()
