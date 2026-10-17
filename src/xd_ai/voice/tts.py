"""Local text-to-speech adapter using the operating system voice engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class TextToSpeechError(RuntimeError):
    """Raised when local speech synthesis cannot play audio."""


class SpeechInterruptedError(TextToSpeechError):
    """Raised after the user stops active speech playback."""


@dataclass(frozen=True, slots=True)
class VoiceInfo:
    id: str
    name: str


class Pyttsx3Speaker:
    """Speak through pyttsx3 while keeping the engine replaceable."""

    def __init__(
        self,
        rate: int = 175,
        voice: str | None = None,
        engine: Any | None = None,
    ) -> None:
        self._rate = rate
        self._voice = voice
        self._engine = engine
        self._configured = False

    def list_voices(self) -> list[VoiceInfo]:
        """Return installed operating-system voices without speaking."""
        engine = self._get_engine(configure=False)
        try:
            voices = engine.getProperty("voices") or []
            return [
                VoiceInfo(id=str(item.id), name=str(getattr(item, "name", item.id)))
                for item in voices
            ]
        except Exception as error:
            raise TextToSpeechError("Installed speech voices could not be listed.") from error

    def speak(self, text: str) -> None:
        """Speak text synchronously; Ctrl+C stops the current utterance."""
        if not text.strip():
            return
        engine = self._get_engine()
        try:
            engine.say(text)
            engine.runAndWait()
        except KeyboardInterrupt as error:
            self._stop_safely()
            raise SpeechInterruptedError("Speech playback was stopped.") from error
        except Exception as error:
            self._stop_safely()
            raise TextToSpeechError(
                "XD could not play speech. Check the Windows audio output device."
            ) from error

    def stop(self) -> None:
        """Stop the current utterance and clear queued speech."""
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception as error:
                raise TextToSpeechError("Speech playback could not be stopped cleanly.") from error

    def close(self) -> None:
        self._stop_safely()
        self._engine = None

    def _get_engine(self, *, configure: bool = True) -> Any:
        if self._engine is None:
            try:
                import pyttsx3
            except ImportError as error:
                raise TextToSpeechError(
                    "Text-to-speech support is not installed. Run: pip install -e '.[dev]'"
                ) from error
            try:
                self._engine = pyttsx3.init()
            except Exception as error:
                raise TextToSpeechError(
                    "The local text-to-speech engine could not start."
                ) from error

        if configure and not self._configured:
            self._configure(self._engine)
        return self._engine

    def _configure(self, engine: Any) -> None:
        try:
            engine.setProperty("rate", self._rate)
            voices = engine.getProperty("voices") or []
            if not voices:
                raise TextToSpeechError("No local text-to-speech voices are installed.")
            if self._voice:
                selected = self._find_voice(voices, self._voice)
                if selected is None:
                    raise TextToSpeechError(
                        f"The configured TTS voice '{self._voice}' is not installed."
                    )
                engine.setProperty("voice", selected.id)
            self._configured = True
        except TextToSpeechError:
            raise
        except Exception as error:
            raise TextToSpeechError("The local speech voice could not be configured.") from error

    @staticmethod
    def _find_voice(voices: list[Any], selector: str) -> Any | None:
        selector_lower = selector.casefold()
        for voice in voices:
            voice_id = str(voice.id)
            voice_name = str(getattr(voice, "name", ""))
            if selector_lower in {voice_id.casefold(), voice_name.casefold()}:
                return voice
        for voice in voices:
            if selector_lower in str(getattr(voice, "name", "")).casefold():
                return voice
        return None

    def _stop_safely(self) -> None:
        try:
            self.stop()
        except TextToSpeechError:
            pass

