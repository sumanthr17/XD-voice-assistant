"""Explicit, in-memory microphone recording through PortAudio."""

from __future__ import annotations

import io
import logging
import threading
import time
import wave
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class MicrophoneError(RuntimeError):
    """Raised when the microphone cannot be queried or recorded."""


class EmptyRecordingError(MicrophoneError):
    """Raised when recording produced no audio frames."""


@dataclass(frozen=True, slots=True)
class AudioDevice:
    """A microphone that can be selected by its PortAudio index."""

    index: int
    name: str
    channels: int
    default_sample_rate: int


@dataclass(frozen=True, slots=True)
class AudioRecording:
    """PCM microphone data retained only in memory."""

    pcm_data: bytes
    sample_rate: int
    channels: int = 1
    sample_width: int = 2

    @property
    def duration_seconds(self) -> float:
        bytes_per_second = self.sample_rate * self.channels * self.sample_width
        return len(self.pcm_data) / bytes_per_second if bytes_per_second else 0.0

    def as_wav_buffer(self) -> io.BytesIO:
        """Create an in-memory WAV stream for the local transcription engine."""
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.sample_width)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(self.pcm_data)
        buffer.seek(0)
        return buffer


@dataclass(frozen=True, slots=True)
class RecordingDiagnostics:
    """Privacy-safe recording statistics; no microphone samples are included."""

    device: AudioDevice
    elapsed_seconds: float
    audio_duration_seconds: float
    audio_frame_count: int
    callback_count: int


class MicrophoneRecorder:
    """Capture one user-initiated utterance without persisting it to disk."""

    def __init__(
        self,
        device: int | str | None = None,
        sample_rate: int | None = None,
        channels: int = 1,
        sounddevice_module: Any | None = None,
    ) -> None:
        self._device = device
        self._requested_sample_rate = sample_rate
        self._channels = channels
        self._sounddevice = sounddevice_module
        self._stream: Any | None = None
        self._frames: list[bytes] = []
        self._stream_status: list[str] = []
        self._active_sample_rate: int | None = None
        self._active_device: AudioDevice | None = None
        self._started_at: float | None = None
        self._callback_count = 0
        self._audio_frame_count = 0
        self._first_frame_received = threading.Event()
        self._callback_lock = threading.Lock()
        self._last_diagnostics: RecordingDiagnostics | None = None

    @property
    def device(self) -> int | str | None:
        return self._device

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    @property
    def last_diagnostics(self) -> RecordingDiagnostics | None:
        """Return statistics for the most recently stopped/cancelled recording."""
        return self._last_diagnostics

    def validate_device(self) -> AudioDevice:
        """Return the selected/default microphone after checking its capabilities."""
        sd = self._get_sounddevice()
        try:
            details = sd.query_devices(self._device, "input")
            index = self._device_index(details, sd)
            channels = int(details["max_input_channels"])
            if channels < self._channels:
                raise MicrophoneError(
                    f"The selected microphone does not support {self._channels} input channel."
                )
            return AudioDevice(
                index=index,
                name=str(details["name"]),
                channels=channels,
                default_sample_rate=int(details["default_samplerate"]),
            )
        except MicrophoneError:
            raise
        except Exception as error:
            raise MicrophoneError(
                "No usable microphone was found. Check Windows microphone permissions "
                "and the selected device."
            ) from error

    def list_input_devices(self) -> list[AudioDevice]:
        """Return all input-capable devices without opening a recording stream."""
        sd = self._get_sounddevice()
        try:
            devices = []
            for index, details in enumerate(sd.query_devices()):
                channels = int(details["max_input_channels"])
                if channels > 0:
                    devices.append(
                        AudioDevice(
                            index=index,
                            name=str(details["name"]),
                            channels=channels,
                            default_sample_rate=int(details["default_samplerate"]),
                        )
                    )
            return devices
        except Exception as error:
            raise MicrophoneError("Microphone devices could not be enumerated.") from error

    def select_device(self, device: int | str | None) -> AudioDevice:
        """Select and validate a microphone for subsequent recordings."""
        if self.is_recording:
            raise MicrophoneError("Stop the current recording before changing microphones.")
        previous = self._device
        self._device = device
        try:
            return self.validate_device()
        except MicrophoneError:
            self._device = previous
            raise

    def start(self) -> AudioDevice:
        """Open the selected microphone. Recording starts only after this call."""
        if self.is_recording:
            raise MicrophoneError("The microphone is already recording.")

        device = self.validate_device()
        sample_rate = self._requested_sample_rate or device.default_sample_rate
        with self._callback_lock:
            self._frames = []
            self._stream_status = []
            self._callback_count = 0
            self._audio_frame_count = 0
        self._active_sample_rate = sample_rate
        self._active_device = device
        self._started_at = None
        self._first_frame_received.clear()
        self._last_diagnostics = None

        def callback(
            input_data: Any,
            frame_count: int,
            _time_info: Any,
            status: Any,
        ) -> None:
            chunk = bytes(input_data)
            with self._callback_lock:
                self._callback_count += 1
                if status:
                    self._stream_status.append(str(status))
                if chunk:
                    self._frames.append(chunk)
                    self._audio_frame_count += int(frame_count)
                    self._first_frame_received.set()

        stream = None
        try:
            sounddevice = self._get_sounddevice()
            check_input_settings = getattr(sounddevice, "check_input_settings", None)
            if check_input_settings is not None:
                check_input_settings(
                    device=device.index,
                    channels=self._channels,
                    dtype="int16",
                    samplerate=sample_rate,
                )
            stream = sounddevice.RawInputStream(
                samplerate=sample_rate,
                blocksize=0,
                # Open the exact endpoint that validate_device() resolved. This avoids
                # a default-device change or an ambiguous Windows device name.
                device=device.index,
                channels=self._channels,
                dtype="int16",
                callback=callback,
            )
            self._started_at = time.monotonic()
            stream.start()
            self._stream = stream
            logger.info(
                "Recording started: device=%s index=%d sample_rate=%d channels=%d",
                device.name,
                device.index,
                sample_rate,
                self._channels,
            )
            return device
        except Exception as error:
            self._stream = None
            if stream is not None:
                stream.close()
            raise MicrophoneError(
                "The microphone could not start recording. Check the selected device "
                "and Windows microphone permissions."
            ) from error

    def wait_for_first_frame(self, timeout: float = 1.0) -> bool:
        """Wait briefly for PortAudio to prove that its callback is receiving data."""
        if self._stream is None:
            raise MicrophoneError("The microphone is not currently recording.")
        return self._first_frame_received.wait(timeout=max(0.0, timeout))

    def stop(self) -> AudioRecording:
        """Stop recording, close the stream, and return in-memory PCM audio."""
        if self._stream is None:
            raise MicrophoneError("The microphone is not currently recording.")

        stream = self._stream
        try:
            stream.stop()
        except Exception as error:
            raise MicrophoneError("The microphone recording could not be completed.") from error
        finally:
            try:
                stream.close()
            finally:
                self._stream = None

        diagnostics = self._capture_diagnostics()
        self._last_diagnostics = diagnostics
        logger.info(
            "Recording stopped: device=%s elapsed=%.2fs audio_duration=%.2fs "
            "audio_frames=%d callbacks=%d",
            diagnostics.device.name,
            diagnostics.elapsed_seconds,
            diagnostics.audio_duration_seconds,
            diagnostics.audio_frame_count,
            diagnostics.callback_count,
        )

        with self._callback_lock:
            stream_status = list(self._stream_status)
            pcm_data = b"".join(self._frames)

        if stream_status:
            raise MicrophoneError(
                "Audio input was interrupted or overflowed. Please record the message again."
            )

        if not pcm_data:
            raise EmptyRecordingError(
                "The microphone stream opened, but its audio callback received no samples. "
                "Check the selected input device and Windows microphone permissions."
            )
        recording = AudioRecording(
            pcm_data=pcm_data,
            sample_rate=self._active_sample_rate or 16_000,
            channels=self._channels,
        )
        logger.info(
            "Recording completed: duration=%.2fs sample_rate=%d channels=%d bit_depth=%d",
            recording.duration_seconds,
            recording.sample_rate,
            recording.channels,
            recording.sample_width * 8,
        )
        return recording

    def cancel(self) -> RecordingDiagnostics | None:
        """Close an active stream and discard all captured audio."""
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
        diagnostics = self._capture_diagnostics() if self._active_device is not None else None
        self._last_diagnostics = diagnostics
        with self._callback_lock:
            self._frames = []
            self._stream_status = []
        if diagnostics is not None:
            logger.info(
                "Recording cancelled: device=%s elapsed=%.2fs audio_frames=%d callbacks=%d",
                diagnostics.device.name,
                diagnostics.elapsed_seconds,
                diagnostics.audio_frame_count,
                diagnostics.callback_count,
            )
        return diagnostics

    def close(self) -> None:
        """Release the microphone if the application exits during capture."""
        try:
            self.cancel()
        except Exception:
            # Shutdown must continue even if PortAudio is already unavailable.
            self._stream = None

    def _get_sounddevice(self) -> Any:
        if self._sounddevice is not None:
            return self._sounddevice
        try:
            import sounddevice
        except ImportError as error:
            raise MicrophoneError(
                "Microphone support is not installed. Run: pip install -e '.[dev]'"
            ) from error
        self._sounddevice = sounddevice
        return sounddevice

    def _device_index(self, details: Any, sounddevice: Any) -> int:
        if isinstance(self._device, int):
            return self._device
        if self._device is None:
            default_device = sounddevice.default.device
            return int(default_device[0])
        for index, candidate in enumerate(sounddevice.query_devices()):
            if candidate["name"] == details["name"]:
                return index
        return -1

    def _capture_diagnostics(self) -> RecordingDiagnostics:
        device = self._active_device
        if device is None:
            raise MicrophoneError("No microphone recording diagnostics are available.")
        sample_rate = self._active_sample_rate or device.default_sample_rate
        with self._callback_lock:
            byte_count = sum(len(frame) for frame in self._frames)
            callback_count = self._callback_count
            audio_frame_count = self._audio_frame_count
        bytes_per_second = sample_rate * self._channels * 2
        audio_duration = byte_count / bytes_per_second if bytes_per_second else 0.0
        elapsed = max(0.0, time.monotonic() - (self._started_at or time.monotonic()))
        return RecordingDiagnostics(
            device=device,
            elapsed_seconds=elapsed,
            audio_duration_seconds=audio_duration,
            audio_frame_count=audio_frame_count,
            callback_count=callback_count,
        )

