"""Local English speech recognition using Faster-Whisper."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from xd_ai.voice.audio import AudioRecording, EmptyRecordingError

logger = logging.getLogger(__name__)
DiagnosticCallback = Callable[[str], None]


class TranscriptionError(RuntimeError):
    """Raised when the local speech recognition engine fails."""


class SpeechNotRecognizedError(TranscriptionError):
    """Raised when recorded audio contains no recognizable English speech."""


class FasterWhisperTranscriber:
    """Lazily load Faster-Whisper and transcribe recordings entirely locally."""

    def __init__(
        self,
        model_name: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
        model: Any | None = None,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._compute_type = compute_type
        self._model = model

    def transcribe(
        self,
        recording: AudioRecording,
        on_diagnostic: DiagnosticCallback | None = None,
    ) -> str:
        """Transcribe an in-memory recording without uploading or saving it."""
        if not recording.pcm_data:
            raise EmptyRecordingError("No audio was captured for transcription.")

        started_at = time.perf_counter()
        self._emit(
            on_diagnostic,
            "Transcription started "
            f"({recording.duration_seconds:.2f}s, {recording.sample_rate} Hz, "
            f"{recording.channels} channel, {recording.sample_width * 8}-bit PCM).",
        )

        if self._model is None:
            model = self._load_model(on_diagnostic)
        else:
            model = self._model
            self._emit(
                on_diagnostic,
                f"Whisper model ready: {self._model_name} (already loaded).",
            )

        try:
            segments, _info = model.transcribe(
                recording.as_wav_buffer(),
                language="en",
                beam_size=5,
                vad_filter=True,
            )
            self._emit(on_diagnostic, "Audio decoded; consuming transcription segments.")
            segment_texts: list[str] = []
            segment_count = 0
            for segment in segments:
                segment_count += 1
                segment_text = segment.text.strip()
                if segment_text:
                    segment_texts.append(segment_text)
            text = " ".join(segment_texts).strip()
        except (EmptyRecordingError, SpeechNotRecognizedError):
            raise
        except Exception as error:
            self._emit(
                on_diagnostic,
                f"Transcription failed during audio decoding ({type(error).__name__}).",
            )
            if isinstance(error, TypeError) and "metadata_errors" in str(error):
                raise TranscriptionError(
                    "Faster-Whisper cannot decode audio because the installed PyAV "
                    "version is incompatible. Reinstall project dependencies to use "
                    "the supported PyAV version."
                ) from error
            raise TranscriptionError(
                "Local speech recognition failed. Check the Whisper model settings "
                "and try again."
            ) from error

        self._emit(
            on_diagnostic,
            f"Transcription completed in {time.perf_counter() - started_at:.2f}s; "
            f"segments={segment_count}.",
        )

        if not text:
            raise SpeechNotRecognizedError(
                "No English speech was recognized. Speak clearly and try again."
            )
        return text

    def _load_model(self, on_diagnostic: DiagnosticCallback | None = None) -> Any:
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise TranscriptionError(
                "Faster-Whisper is not installed. Run: pip install -e '.[dev]'"
            ) from error

        started_at = time.perf_counter()
        self._emit(
            on_diagnostic,
            f"Whisper model loading started: {self._model_name} "
            f"({self._device}/{self._compute_type}).",
        )
        try:
            self._model = WhisperModel(
                self._model_name,
                device=self._device,
                compute_type=self._compute_type,
            )
        except Exception as error:
            self._emit(
                on_diagnostic,
                f"Whisper model loading failed ({type(error).__name__}).",
            )
            raise TranscriptionError(
                f"The local Whisper model '{self._model_name}' could not be loaded. "
                "The first use requires an internet connection to download the model."
            ) from error
        self._emit(
            on_diagnostic,
            f"Whisper model loading completed in "
            f"{time.perf_counter() - started_at:.2f}s.",
        )
        return self._model

    @staticmethod
    def _emit(callback: DiagnosticCallback | None, message: str) -> None:
        logger.info(message)
        if callback is not None:
            callback(message)

