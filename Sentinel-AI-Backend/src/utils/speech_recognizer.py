import speech_recognition as sr
from src.utils.log_config import get_logger

logger = get_logger("speech")


class SpeechRecognitionAgent:
    def __init__(self, energy_threshold=300, pause_threshold=0.8):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = energy_threshold
        self.recognizer.pause_threshold = pause_threshold
        self.microphone = sr.Microphone()

    def adjust_for_ambient_noise(self, duration=1):
        try:
            with self.microphone as source:
                logger.info("Calibrating microphone for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=duration)
                logger.info("Energy threshold set to: %s", self.recognizer.energy_threshold)
                return True
        except Exception as e:
            logger.error("Failed to calibrate mic: %s", e)
            return False

    def listen_command(self, timeout=5, phrase_time_limit=10, language="en-US"):
        try:
            with self.microphone as source:
                logger.info("Listening for a command...")
                audio = self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )
            command = self.recognizer.recognize_google(audio, language=language)
            return command
        except sr.WaitTimeoutError:
            logger.warning("Listening timed out.")
        except sr.UnknownValueError:
            logger.warning("Could not understand audio.")
        except sr.RequestError as e:
            logger.warning("Could not request results from Google API: %s", e)
        return None

    def listen_in_background(self, callback):
        logger.info("Background listener started.")
        return self.recognizer.listen_in_background(self.microphone, callback)


def default_callback(recognizer, audio):
    try:
        command = recognizer.recognize_google(audio)
        logger.info("Heard (background): %s", command)
    except sr.UnknownValueError:
        logger.warning("Background: Could not understand audio.")
    except sr.RequestError as e:
        logger.warning("Background API error: %s", e)
