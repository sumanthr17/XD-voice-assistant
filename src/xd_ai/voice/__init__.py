"""Local voice input and output components for XD AI."""

from xd_ai.voice.audio import (
    AudioDevice,
    AudioRecording,
    EmptyRecordingError,
    MicrophoneError,
    MicrophoneRecorder,
    RecordingDiagnostics,
)
from xd_ai.voice.transcriber import (
    FasterWhisperTranscriber,
    SpeechNotRecognizedError,
    TranscriptionError,
)
from xd_ai.voice.tts import (
    Pyttsx3Speaker,
    SpeechInterruptedError,
    TextToSpeechError,
)

__all__ = [
    "AudioDevice",
    "AudioRecording",
    "EmptyRecordingError",
    "FasterWhisperTranscriber",
    "MicrophoneError",
    "MicrophoneRecorder",
    "Pyttsx3Speaker",
    "RecordingDiagnostics",
    "SpeechInterruptedError",
    "SpeechNotRecognizedError",
    "TextToSpeechError",
    "TranscriptionError",
]

