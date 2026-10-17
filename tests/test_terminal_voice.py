from io import StringIO
from unittest.mock import patch

from rich.console import Console

from xd_ai.core.config import Settings
from xd_ai.interface.terminal import TerminalApp
from xd_ai.voice.audio import AudioDevice, AudioRecording, RecordingDiagnostics


class FakeRecorder:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.closed = 0
        self.is_recording = False
        self.last_diagnostics: RecordingDiagnostics | None = None

    def validate_device(self) -> AudioDevice:
        return AudioDevice(1, "Mock Microphone", 1, 16_000)

    def start(self) -> AudioDevice:
        self.started += 1
        self.is_recording = True
        return self.validate_device()

    def wait_for_first_frame(self, timeout: float = 1.0) -> bool:
        return True

    def stop(self) -> AudioRecording:
        self.stopped += 1
        self.is_recording = False
        self.last_diagnostics = RecordingDiagnostics(
            device=self.validate_device(),
            elapsed_seconds=0.25,
            audio_duration_seconds=0.002,
            audio_frame_count=32,
            callback_count=1,
        )
        return AudioRecording(b"\x01\x00" * 32, 16_000)

    def cancel(self) -> RecordingDiagnostics | None:
        self.is_recording = False
        return self.last_diagnostics

    def close(self) -> None:
        self.closed += 1


class NoCallbackRecorder(FakeRecorder):
    def wait_for_first_frame(self, timeout: float = 1.0) -> bool:
        return False

    def cancel(self) -> RecordingDiagnostics:
        self.is_recording = False
        self.last_diagnostics = RecordingDiagnostics(
            device=self.validate_device(),
            elapsed_seconds=1.0,
            audio_duration_seconds=0.0,
            audio_frame_count=0,
            callback_count=0,
        )
        return self.last_diagnostics


class FakeTranscriber:
    def __init__(self) -> None:
        self.recordings: list[AudioRecording] = []

    def transcribe(self, recording: AudioRecording, on_diagnostic=None) -> str:
        self.recordings.append(recording)
        if on_diagnostic is not None:
            on_diagnostic("Transcription completed; segments=1.")
        return "How are you?"


class FakeSpeaker:
    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.closed = 0

    def speak(self, text: str) -> None:
        self.spoken.append(text)

    def close(self) -> None:
        self.closed += 1


class FakeGeminiService:
    def __init__(self) -> None:
        self.questions: list[str] = []

    def ask(self, question: str) -> str:
        self.questions.append(question)
        return "All systems are operating normally."


def test_voice_turn_runs_record_transcribe_ai_and_speech_pipeline() -> None:
    recorder = FakeRecorder()
    transcriber = FakeTranscriber()
    speaker = FakeSpeaker()
    service = FakeGeminiService()
    output = StringIO()
    app = TerminalApp(
        Settings("test-key"),
        service=service,  # type: ignore[arg-type]
        console=Console(file=output, force_terminal=False),
        recorder=recorder,  # type: ignore[arg-type]
        transcriber=transcriber,  # type: ignore[arg-type]
        speaker=speaker,  # type: ignore[arg-type]
    )

    with patch("xd_ai.interface.terminal.Prompt.ask", return_value=""):
        app._run_voice_turn()

    assert recorder.started == 1
    assert recorder.stopped == 1
    assert service.questions == ["How are you?"]
    assert speaker.spoken == ["All systems are operating normally."]
    assert "[LISTENING]" in output.getvalue()
    assert "Recording completed" in output.getvalue()
    assert "frames=32" in output.getvalue()
    assert "segments=1" in output.getvalue()
    assert "[SPEAKING]" in output.getvalue()


def test_app_exit_releases_voice_resources() -> None:
    recorder = FakeRecorder()
    speaker = FakeSpeaker()
    app = TerminalApp(
        Settings("test-key"),
        service=FakeGeminiService(),  # type: ignore[arg-type]
        console=Console(file=StringIO(), force_terminal=False),
        recorder=recorder,  # type: ignore[arg-type]
        transcriber=FakeTranscriber(),  # type: ignore[arg-type]
        speaker=speaker,  # type: ignore[arg-type]
    )

    with patch("xd_ai.interface.terminal.Prompt.ask", return_value="exit"):
        app.run()

    assert recorder.closed == 1
    assert speaker.closed == 1


def test_missing_audio_callback_reports_once_without_retrying() -> None:
    recorder = NoCallbackRecorder()
    output = StringIO()
    app = TerminalApp(
        Settings("test-key"),
        service=FakeGeminiService(),  # type: ignore[arg-type]
        console=Console(file=output, force_terminal=False),
        recorder=recorder,  # type: ignore[arg-type]
        transcriber=FakeTranscriber(),  # type: ignore[arg-type]
        speaker=FakeSpeaker(),  # type: ignore[arg-type]
    )

    app._run_voice_turn()

    assert recorder.started == 1
    assert recorder.stopped == 0
    assert "callbacks=0" in output.getvalue()
    assert "audio callbacks within 1 second" in output.getvalue()


def test_microphone_diagnostic_requires_confirmation() -> None:
    recorder = FakeRecorder()
    output = StringIO()
    app = TerminalApp(
        Settings("test-key"),
        service=FakeGeminiService(),  # type: ignore[arg-type]
        console=Console(file=output, force_terminal=False),
        recorder=recorder,  # type: ignore[arg-type]
        transcriber=FakeTranscriber(),  # type: ignore[arg-type]
        speaker=FakeSpeaker(),  # type: ignore[arg-type]
    )

    with patch("xd_ai.interface.terminal.Confirm.ask", return_value=False):
        app._run_microphone_diagnostic()

    assert recorder.started == 0
    assert "diagnostic cancelled" in output.getvalue()


def test_microphone_diagnostic_records_once_and_discards_audio() -> None:
    recorder = FakeRecorder()
    service = FakeGeminiService()
    output = StringIO()
    app = TerminalApp(
        Settings("test-key"),
        service=service,  # type: ignore[arg-type]
        console=Console(file=output, force_terminal=False),
        recorder=recorder,  # type: ignore[arg-type]
        transcriber=FakeTranscriber(),  # type: ignore[arg-type]
        speaker=FakeSpeaker(),  # type: ignore[arg-type]
    )

    with (
        patch("xd_ai.interface.terminal.Confirm.ask", return_value=True),
        patch("xd_ai.interface.terminal.time.sleep") as sleep,
    ):
        app._run_microphone_diagnostic()

    sleep.assert_called_once_with(3.0)
    assert recorder.started == 1
    assert recorder.stopped == 1
    assert service.questions == []
    assert "audio was discarded" in output.getvalue()
