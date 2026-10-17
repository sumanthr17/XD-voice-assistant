"""Command-line entry point for XD AI."""

from xd_ai.ai.gemini import GeminiService
from xd_ai.core.config import load_settings
from xd_ai.interface.terminal import TerminalApp
from xd_ai.voice import FasterWhisperTranscriber, MicrophoneRecorder, Pyttsx3Speaker


def main() -> None:
    """Launch the terminal assistant."""
    settings = load_settings()
    recorder = MicrophoneRecorder(
        device=settings.microphone_device,
        sample_rate=settings.audio_sample_rate,
    )
    transcriber = FasterWhisperTranscriber(
        model_name=settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )
    speaker = Pyttsx3Speaker(rate=settings.tts_rate, voice=settings.tts_voice)
    TerminalApp(
        settings=settings,
        service=GeminiService(settings),
        recorder=recorder,
        transcriber=transcriber,
        speaker=speaker,
    ).run()


if __name__ == "__main__":
    main()

