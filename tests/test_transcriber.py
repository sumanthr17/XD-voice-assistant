import wave
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from xd_ai.voice.audio import AudioRecording, EmptyRecordingError
from xd_ai.voice.transcriber import (
    FasterWhisperTranscriber,
    SpeechNotRecognizedError,
    TranscriptionError,
)


class FakeWhisperModel:
    def __init__(self, texts: list[str]) -> None:
        self.texts = texts
        self.calls: list[tuple[object, dict[str, object]]] = []

    def transcribe(self, audio, **kwargs):
        self.calls.append((audio, kwargs))
        return ([SimpleNamespace(text=text) for text in self.texts], SimpleNamespace())


class FailingWhisperModel(FakeWhisperModel):
    def transcribe(self, audio, **kwargs):
        raise RuntimeError("decoder failure")


class LazyWhisperModel(FakeWhisperModel):
    def __init__(self, texts: list[str]) -> None:
        super().__init__(texts)
        self.consumed = 0

    def transcribe(self, audio, **kwargs):
        self.calls.append((audio, kwargs))

        def generate_segments():
            for text in self.texts:
                self.consumed += 1
                yield SimpleNamespace(text=text)

        return generate_segments(), SimpleNamespace()


class IncompatiblePyAvModel(FakeWhisperModel):
    def transcribe(self, audio, **kwargs):
        raise TypeError("open() got an unexpected keyword argument 'metadata_errors'")


def test_transcriber_uses_english_and_in_memory_wav() -> None:
    model = FakeWhisperModel([" Hello", "world. "])
    transcriber = FasterWhisperTranscriber(model=model)
    recording = AudioRecording(b"\x01\x00" * 32, sample_rate=16_000)

    text = transcriber.transcribe(recording)

    audio, options = model.calls[0]
    assert text == "Hello world."
    audio.seek(0)
    assert audio.read(4) == b"RIFF"
    audio.seek(0)
    with wave.open(audio, "rb") as wav_file:
        assert wav_file.getframerate() == 16_000
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getnframes() == 32
    assert options["language"] == "en"
    assert options["vad_filter"] is True


def test_transcriber_rejects_empty_audio() -> None:
    transcriber = FasterWhisperTranscriber(model=FakeWhisperModel(["unused"]))

    with pytest.raises(EmptyRecordingError):
        transcriber.transcribe(AudioRecording(b"", sample_rate=16_000))


def test_transcriber_reports_unrecognized_speech() -> None:
    transcriber = FasterWhisperTranscriber(model=FakeWhisperModel(["  "]))

    with pytest.raises(SpeechNotRecognizedError, match="No English speech"):
        transcriber.transcribe(AudioRecording(b"\x00\x00" * 32, sample_rate=16_000))


def test_transcriber_wraps_local_engine_failure() -> None:
    transcriber = FasterWhisperTranscriber(model=FailingWhisperModel([]))

    with pytest.raises(TranscriptionError, match="Local speech recognition failed"):
        transcriber.transcribe(AudioRecording(b"\x00\x00" * 32, sample_rate=16_000))


def test_transcriber_consumes_lazy_segments_and_reports_diagnostics() -> None:
    model = LazyWhisperModel(["first", "second"])
    diagnostics: list[str] = []
    transcriber = FasterWhisperTranscriber(model=model)

    result = transcriber.transcribe(
        AudioRecording(b"\x00\x00" * 32, sample_rate=16_000),
        on_diagnostic=diagnostics.append,
    )

    assert result == "first second"
    assert model.consumed == 2
    assert any("Transcription started" in message for message in diagnostics)
    assert any("consuming transcription segments" in message for message in diagnostics)
    assert any("Transcription completed" in message for message in diagnostics)
    assert any("segments=2" in message for message in diagnostics)


def test_transcriber_reports_model_loading_started_and_completed() -> None:
    model = FakeWhisperModel(["ready"])
    diagnostics: list[str] = []
    transcriber = FasterWhisperTranscriber()

    with patch("faster_whisper.WhisperModel", return_value=model):
        transcriber.transcribe(
            AudioRecording(b"\x00\x00" * 32, sample_rate=16_000),
            on_diagnostic=diagnostics.append,
        )

    assert any("model loading started" in message for message in diagnostics)
    assert any("model loading completed" in message for message in diagnostics)


def test_transcriber_explains_incompatible_pyav() -> None:
    transcriber = FasterWhisperTranscriber(model=IncompatiblePyAvModel([]))

    with pytest.raises(TranscriptionError, match="PyAV version is incompatible"):
        transcriber.transcribe(AudioRecording(b"\x00\x00" * 32, sample_rate=16_000))

