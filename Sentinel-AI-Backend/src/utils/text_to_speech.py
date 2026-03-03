# src/utils/text_to_speech.py

import os
import threading
from elevenlabs import ElevenLabs, VoiceSettings
from dotenv import load_dotenv
import tempfile
import pygame
import time
from src.utils.log_config import get_logger

# Load environment variables
load_dotenv()

logger = get_logger("tts")


class TextToSpeech:
    """
    Text-to-Speech handler using ElevenLabs API with pyttsx3 fallback.
    ElevenLabs is the primary engine; pyttsx3 (offline, free) kicks in
    automatically when ElevenLabs fails.
    """

    def __init__(self):
        """Initialize the TTS engine with ElevenLabs API."""
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = os.getenv(
            "ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL"
        )  # Default: Sarah (Female)
        self.enabled = os.getenv("TTS_ENABLED", "true").lower() == "true"

        # Fallback configuration
        self.fallback_enabled = (
            os.getenv("TTS_FALLBACK_ENABLED", "true").lower() == "true"
        )
        self.fallback_rate = int(os.getenv("TTS_FALLBACK_RATE", "175"))
        self._fallback_lock = threading.Lock()
        self._fallback_engine_active = False

        # Track whether ElevenLabs is available
        self._elevenlabs_available = False

        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY not found.")
            if self.fallback_enabled:
                logger.info("TTS fallback (pyttsx3) available when needed.")
            else:
                self.enabled = False
            return

        try:
            # Initialize ElevenLabs client
            self.client = ElevenLabs(api_key=self.api_key)

            # Initialize pygame mixer for audio playback
            pygame.mixer.init()

            self._elevenlabs_available = True
            logger.info("TTS initialized with voice ID: %s", self.voice_id)

        except Exception as e:
            logger.error("Error initializing ElevenLabs TTS: %s", e)
            if not self.fallback_enabled:
                self.enabled = False

    def speak(self, text: str, blocking: bool = True) -> bool:
        """
        Convert text to speech and play it.

        Args:
            text: The text to speak
            blocking: If True, wait for speech to complete before returning

        Returns:
            bool: True if speech was successful, False otherwise
        """
        if not self.enabled:
            logger.info("TTS disabled. Would have spoken: %s", text)
            return False

        if not text or not text.strip():
            return False

        # Clean the text (remove markdown formatting, emojis, etc.)
        clean_text = self._clean_text(text)

        if not clean_text:
            return False

        logger.info("Speaking: %s", clean_text[:100])

        # Try ElevenLabs first
        if self._elevenlabs_available:
            try:
                return self._speak_elevenlabs(clean_text, blocking)
            except Exception as e:
                logger.warning("ElevenLabs TTS failed: %s — trying fallback", e)

        # Fall back to pyttsx3
        if self.fallback_enabled:
            return self._speak_fallback(clean_text, blocking)

        return False

    def _speak_elevenlabs(self, clean_text: str, blocking: bool) -> bool:
        """Speak using ElevenLabs API."""
        audio_generator = self.client.text_to_speech.convert(
            voice_id=self.voice_id,
            optimize_streaming_latency="0",
            output_format="mp3_44100_128",
            text=clean_text,
            model_id="eleven_turbo_v2",
            voice_settings=VoiceSettings(
                stability=0.5,
                similarity_boost=0.75,
                style=0.0,
                use_speaker_boost=True,
            ),
        )

        # Save audio to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
            for chunk in audio_generator:
                if chunk:
                    temp_audio.write(chunk)
            temp_path = temp_audio.name

        # Play the audio
        self._play_audio(temp_path, blocking=blocking)

        # Clean up temporary file
        try:
            os.remove(temp_path)
        except OSError:
            pass

        return True

    def _speak_fallback(self, clean_text: str, blocking: bool) -> bool:
        """Speak using pyttsx3 (offline fallback). Thread-safe: creates engine per call."""
        try:
            import pyttsx3
        except ImportError:
            logger.error("pyttsx3 not installed. Run: pip install pyttsx3")
            return False

        def _do_speak():
            engine = None
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", self.fallback_rate)
                engine.setProperty("volume", 1.0)
                engine.say(clean_text)
                with self._fallback_lock:
                    self._fallback_engine_active = True
                engine.runAndWait()
            except Exception as e:
                logger.error("pyttsx3 fallback error: %s", e)
            finally:
                with self._fallback_lock:
                    self._fallback_engine_active = False
                if engine:
                    try:
                        engine.stop()
                    except Exception:
                        pass

        if blocking:
            _do_speak()
        else:
            thread = threading.Thread(target=_do_speak, daemon=True)
            thread.start()

        logger.info("Spoke via pyttsx3 fallback")
        return True

    def _play_audio(self, audio_path: str, blocking: bool = True):
        """
        Play audio file using pygame.

        Args:
            audio_path: Path to the audio file
            blocking: If True, wait for playback to complete
        """
        try:
            # Load and play the audio
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()

            if blocking:
                # Wait for playback to complete
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)

        except Exception as e:
            logger.error("Error playing audio: %s", e)

    def _clean_text(self, text: str) -> str:
        """
        Clean text for TTS by removing markdown, emojis, and special formatting.

        Args:
            text: Raw text to clean

        Returns:
            str: Cleaned text suitable for TTS
        """
        import re

        # Remove markdown formatting
        # Remove bold/italic markers
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # **bold**
        text = re.sub(r"\*([^*]+)\*", r"\1", text)  # *italic*
        text = re.sub(r"__([^_]+)__", r"\1", text)  # __bold__
        text = re.sub(r"_([^_]+)_", r"\1", text)  # _italic_

        # Remove markdown headers
        text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)

        # Remove links [text](url)
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

        # Remove emojis (most common ones)
        emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"  # emoticons
            "\U0001f300-\U0001f5ff"  # symbols & pictographs
            "\U0001f680-\U0001f6ff"  # transport & map symbols
            "\U0001f1e0-\U0001f1ff"  # flags
            "\U00002500-\U00002bef"  # chinese characters
            "\U00002702-\U000027b0"
            "\U000024c2-\U0001f251"
            "\U0001f926-\U0001f937"
            "\U00010000-\U0010ffff"
            "\u2640-\u2642"
            "\u2600-\u2b55"
            "\u200d"
            "\u23cf"
            "\u23e9"
            "\u231a"
            "\ufe0f"  # dingbats
            "\u3030"
            "]+",
            flags=re.UNICODE,
        )
        text = emoji_pattern.sub("", text)

        # Remove URLs
        text = re.sub(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            "",
            text,
        )

        # Remove special characters used for formatting
        text = re.sub(r"[▶️⏸️⏭️⏮️👍👎🔗📎✂️]", "", text)

        # Clean up extra whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Remove agent prefix if present (e.g., "(Music agent): ")
        text = re.sub(r"^\([^)]+\):\s*", "", text)

        return text

    def get_available_voices(self) -> list:
        """
        Get list of available voices from ElevenLabs.

        Returns:
            list: List of voice dictionaries with id, name, and description
        """
        if not self.enabled:
            return []

        try:
            voices = self.client.voices.get_all()

            voice_list = []
            for voice in voices.voices:
                voice_list.append(
                    {
                        "id": voice.voice_id,
                        "name": voice.name,
                        "category": voice.category if hasattr(voice, "category") else "Unknown",
                        "description": voice.description if hasattr(voice, "description") else "",
                    }
                )

            return voice_list

        except Exception as e:
            logger.error("Error getting voices: %s", e)
            return []

    def set_voice(self, voice_id: str):
        """
        Change the voice used for TTS.

        Args:
            voice_id: ElevenLabs voice ID
        """
        self.voice_id = voice_id
        logger.info("Voice changed to: %s", voice_id)

    def stop(self):
        """Stop current audio playback (ElevenLabs/pygame and pyttsx3)."""
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass


def get_tts_instance() -> TextToSpeech:
    """Get or create TTS singleton instance (delegates to ServiceContainer)."""
    from src.utils.container import get_container

    return get_container().tts


def speak(text: str, blocking: bool = True) -> bool:
    """
    Convenience function to speak text.

    Args:
        text: Text to speak
        blocking: If True, wait for speech to complete

    Returns:
        bool: True if successful
    """
    tts = get_tts_instance()
    return tts.speak(text, blocking=blocking)


# Example usage and voice listing
if __name__ == "__main__":
    tts = TextToSpeech()

    # List available voices
    print("\n📋 Available voices:")
    voices = tts.get_available_voices()
    for i, voice in enumerate(voices[:10], 1):  # Show first 10
        print(
            f"{i}. {voice['name']} (ID: {voice['id']}) - {voice.get('description', 'No description')}"
        )

    # Test TTS
    print("\n🔊 Testing TTS...")
    tts.speak("Hello! I am Sentinel, your AI assistant. How can I help you today?")
