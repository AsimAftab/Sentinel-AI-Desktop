"""Voice pipeline v2: wake word → Groq Whisper STT → agent graph → streaming TTS.

Import lazily — modules here require audio hardware and native deps
(PyAudio, Porcupine); the core service must boot without them.
"""
