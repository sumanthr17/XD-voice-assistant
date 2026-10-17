from types import SimpleNamespace

import pytest

from xd_ai.voice.audio import EmptyRecordingError, MicrophoneError, MicrophoneRecorder


class FakeStream:
    def __init__(self, callback, emit_audio: bool = True) -> None:
        self.callback = callback
        self.emit_audio = emit_audio
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self) -> None:
        self.started = True
        if self.emit_audio:
            self.emit()

    def emit(self) -> None:
        self.callback(b"\x01\x00" * 16, 16, None, None)

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True


class FakeSoundDevice:
    def __init__(self, emit_audio: bool = True) -> None:
        self.default = SimpleNamespace(device=(1, 0))
        self.devices = [
            {
                "name": "Speakers",
                "max_input_channels": 0,
                "default_samplerate": 48_000,
            },
            {
                "name": "Test Microphone",
                "max_input_channels": 2,
                "default_samplerate": 48_000,
            },
        ]
        self.emit_audio = emit_audio
        self.last_stream: FakeStream | None = None
        self.last_stream_options: dict[str, object] = {}
        self.checked_input_settings: dict[str, object] = {}

    def query_devices(self, device=None, kind=None):
        if device is None and kind == "input":
            return self.devices[1]
        if device is None:
            return self.devices
        if isinstance(device, int):
            return self.devices[device]
        return next(item for item in self.devices if device.casefold() in item["name"].casefold())

    def RawInputStream(self, **kwargs):
        self.last_stream_options = kwargs
        self.last_stream = FakeStream(kwargs["callback"], emit_audio=self.emit_audio)
        return self.last_stream

    def check_input_settings(self, **kwargs) -> None:
        self.checked_input_settings = kwargs


class MissingSoundDevice(FakeSoundDevice):
    def query_devices(self, device=None, kind=None):
        raise RuntimeError("No audio hardware")


def test_recorder_uses_default_device_and_keeps_audio_in_memory() -> None:
    sounddevice = FakeSoundDevice()
    recorder = MicrophoneRecorder(sounddevice_module=sounddevice)

    device = recorder.start()
    recording = recorder.stop()

    assert device.index == 1
    assert device.name == "Test Microphone"
    assert recording.pcm_data == b"\x01\x00" * 16
    assert recording.sample_rate == 48_000
    assert sounddevice.last_stream_options["dtype"] == "int16"
    assert sounddevice.last_stream_options["device"] == 1
    assert sounddevice.checked_input_settings["device"] == 1
    assert sounddevice.last_stream is not None
    assert sounddevice.last_stream.closed
    assert recorder.last_diagnostics is not None
    assert recorder.last_diagnostics.callback_count == 1
    assert recorder.last_diagnostics.audio_frame_count == 16


def test_recorder_detects_empty_recording() -> None:
    recorder = MicrophoneRecorder(sounddevice_module=FakeSoundDevice(emit_audio=False))
    recorder.start()

    assert not recorder.wait_for_first_frame(timeout=0)

    with pytest.raises(EmptyRecordingError, match="audio callback received no samples"):
        recorder.stop()

    assert recorder.last_diagnostics is not None
    assert recorder.last_diagnostics.callback_count == 0
    assert recorder.last_diagnostics.audio_frame_count == 0


def test_recorder_waits_for_asynchronous_callback() -> None:
    sounddevice = FakeSoundDevice(emit_audio=False)
    recorder = MicrophoneRecorder(sounddevice_module=sounddevice)
    recorder.start()

    assert not recorder.wait_for_first_frame(timeout=0)
    assert sounddevice.last_stream is not None
    sounddevice.last_stream.emit()

    assert recorder.wait_for_first_frame(timeout=0)
    recording = recorder.stop()
    assert recording.duration_seconds > 0


def test_recorder_lists_and_selects_input_devices() -> None:
    recorder = MicrophoneRecorder(sounddevice_module=FakeSoundDevice())

    devices = recorder.list_input_devices()
    selected = recorder.select_device(1)

    assert [device.name for device in devices] == ["Test Microphone"]
    assert selected.index == 1


def test_recorder_reports_unavailable_microphone() -> None:
    recorder = MicrophoneRecorder(sounddevice_module=MissingSoundDevice())

    with pytest.raises(MicrophoneError, match="No usable microphone"):
        recorder.validate_device()

