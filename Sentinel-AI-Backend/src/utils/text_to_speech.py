# src/utils/text_to_speech.py

import os
from elevenlabs import ElevenLabs, VoiceSettings
from dotenv import load_dotenv
import tempfile
import pygame
import time

# Load environment variables
load_dotenv()


class TextToSpeech:
    """
    Text-to-Speech handler using ElevenLabs API.
    Converts text responses to natural-sounding speech.
    """

    def __init__(self):
        """Initialize the TTS engine with ElevenLabs API."""
        self.api_key = os.getenv('ELEVENLABS_API_KEY')
        self.voice_id = os.getenv('ELEVENLABS_VOICE_ID', 'EXAVITQu4vr4xnSDxMaL')  # Default: Sarah (Female)
        self.enabled = os.getenv('TTS_ENABLED', 'true').lower() == 'true'

        if not self.api_key:
            print("⚠️ ELEVENLABS_API_KEY not found in .env file. Text-to-speech will be disabled.")
            self.enabled = False
            return

        try:
            # Initialize ElevenLabs client
            self.client = ElevenLabs(api_key=self.api_key)

            # Initialize pygame mixer for audio playback
            pygame.mixer.init()

            print(f"✅ Text-to-Speech initialized with voice ID: {self.voice_id}")

        except Exception as e:
            print(f"❌ Error initializing Text-to-Speech: {e}")
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
            print(f"🔇 TTS disabled. Would have spoken: {text}")
            return False

        if not text or not text.strip():
            return False

        try:
            # Clean the text (remove markdown formatting, emojis, etc.)
            clean_text = self._clean_text(text)

            if not clean_text:
                return False

            print(f"🔊 Speaking: {clean_text[:100]}..." if len(clean_text) > 100 else f"🔊 Speaking: {clean_text}")

            # Generate speech using ElevenLabs
            # Using eleven_turbo_v2 - available on free tier, fast and high quality
            audio_generator = self.client.text_to_speech.convert(
                voice_id=self.voice_id,
                optimize_streaming_latency="0",
                output_format="mp3_44100_128",
                text=clean_text,
                model_id="eleven_turbo_v2",  # Free tier compatible model
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.75,
                    style=0.0,
                    use_speaker_boost=True,
                ),
            )

            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_audio:
                # Write all chunks to file
                for chunk in audio_generator:
                    if chunk:
                        temp_audio.write(chunk)

                temp_path = temp_audio.name

            # Play the audio
            self._play_audio(temp_path, blocking=blocking)

            # Clean up temporary file
            try:
                os.remove(temp_path)
            except:
                pass

            return True

        except Exception as e:
            print(f"❌ Error in text-to-speech: {e}")
            return False

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
            print(f"❌ Error playing audio: {e}")

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
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold**
        text = re.sub(r'\*([^*]+)\*', r'\1', text)      # *italic*
        text = re.sub(r'__([^_]+)__', r'\1', text)      # __bold__
        text = re.sub(r'_([^_]+)_', r'\1', text)        # _italic_

        # Remove markdown headers
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)

        # Remove links [text](url)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

        # Remove emojis (most common ones)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002500-\U00002BEF"  # chinese characters
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F926-\U0001F937"
            "\U00010000-\U0010FFFF"
            "\u2640-\u2642"
            "\u2600-\u2B55"
            "\u200d"
            "\u23cf"
            "\u23e9"
            "\u231a"
            "\ufe0f"  # dingbats
            "\u3030"
            "]+",
            flags=re.UNICODE
        )
        text = emoji_pattern.sub('', text)

        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

        # Remove special characters used for formatting
        text = re.sub(r'[▶️⏸️⏭️⏮️👍👎🔗📎✂️]', '', text)

        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Remove agent prefix if present (e.g., "(Music agent): ")
        text = re.sub(r'^\([^)]+\):\s*', '', text)

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
                voice_list.append({
                    'id': voice.voice_id,
                    'name': voice.name,
                    'category': voice.category if hasattr(voice, 'category') else 'Unknown',
                    'description': voice.description if hasattr(voice, 'description') else ''
                })

            return voice_list

        except Exception as e:
            print(f"❌ Error getting voices: {e}")
            return []

    def set_voice(self, voice_id: str):
        """
        Change the voice used for TTS.

        Args:
            voice_id: ElevenLabs voice ID
        """
        self.voice_id = voice_id
        print(f"✅ Voice changed to: {voice_id}")

    def stop(self):
        """Stop current audio playback."""
        try:
            pygame.mixer.music.stop()
        except:
            pass


# Singleton instance
_tts_instance = None


def get_tts_instance() -> TextToSpeech:
    """Get or create TTS singleton instance."""
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TextToSpeech()
    return _tts_instance


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
        print(f"{i}. {voice['name']} (ID: {voice['id']}) - {voice.get('description', 'No description')}")

    # Test TTS
    print("\n🔊 Testing TTS...")
    tts.speak("Hello! I am Sentinel, your AI assistant. How can I help you today?")
