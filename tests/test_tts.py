from types import SimpleNamespace

import pytest

from xd_ai.voice.tts import Pyttsx3Speaker, SpeechInterruptedError, TextToSpeechError


class FakeEngine:
    def __init__(self, *, voices=None, playback_error: BaseException | None = None) -> None:
        self.voices = voices if voices is not None else [
            SimpleNamespace(id="voice-one", name="Calm Voice"),
            SimpleNamespace(id="voice-two", name="Clear Voice"),
        ]
        self.properties: dict[str, object] = {}
        self.spoken: list[str] = []
        self.run_count = 0
        self.stop_count = 0
        self.playback_error = playback_error

    def getProperty(self, name: str):
        assert name == "voices"
        return self.voices

    def setProperty(self, name: str, value: object) -> None:
        self.properties[name] = value

    def say(self, text: str) -> None:
        self.spoken.append(text)

    def runAndWait(self) -> None:
        self.run_count += 1
        if self.playback_error:
            raise self.playback_error

    def stop(self) -> None:
        self.stop_count += 1


def test_speaker_configures_rate_voice_and_plays_text() -> None:
    engine = FakeEngine()
    speaker = Pyttsx3Speaker(rate=165, voice="Calm", engine=engine)

    speaker.speak("System online.")

    assert engine.properties == {"rate": 165, "voice": "voice-one"}
    assert engine.spoken == ["System online."]
    assert engine.run_count == 1


def test_speaker_exposes_stop() -> None:
    engine = FakeEngine()
    speaker = Pyttsx3Speaker(engine=engine)

    speaker.stop()

    assert engine.stop_count == 1


def test_speaker_reports_missing_configured_voice() -> None:
    speaker = Pyttsx3Speaker(voice="Not Installed", engine=FakeEngine())

    with pytest.raises(TextToSpeechError, match="not installed"):
        speaker.speak("Hello")


def test_speaker_can_list_voices_when_configured_voice_is_invalid() -> None:
    speaker = Pyttsx3Speaker(voice="Not Installed", engine=FakeEngine())

    assert [voice.name for voice in speaker.list_voices()] == ["Calm Voice", "Clear Voice"]


def test_speaker_stops_playback_on_user_interruption() -> None:
    engine = FakeEngine(playback_error=KeyboardInterrupt())
    speaker = Pyttsx3Speaker(engine=engine)

    with pytest.raises(SpeechInterruptedError):
        speaker.speak("Long response")

    assert engine.stop_count == 1

