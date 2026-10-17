"""Configuration loading for XD AI."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_MODEL = "gemini-3.1-flash-lite"
DEFAULT_HISTORY_TURNS = 10
DEFAULT_WHISPER_MODEL = "base.en"
DEFAULT_TTS_RATE = 175


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration sourced from the local environment."""

    gemini_api_key: str | None
    gemini_model: str = DEFAULT_MODEL
    max_history_turns: int = DEFAULT_HISTORY_TURNS
    microphone_device: int | str | None = None
    audio_sample_rate: int | None = None
    whisper_model: str = DEFAULT_WHISPER_MODEL
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    tts_rate: int = DEFAULT_TTS_RATE
    tts_voice: str | None = None

    @property
    def has_gemini_credentials(self) -> bool:
        """Return whether a non-empty Gemini API key is configured."""
        return bool(self.gemini_api_key)


def load_settings() -> Settings:
    """Load local `.env` values without replacing existing environment variables."""
    load_dotenv(override=False)
    return Settings(
        gemini_api_key=_optional_value("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        max_history_turns=_positive_int(
            os.getenv("XD_AI_MAX_HISTORY_TURNS"), DEFAULT_HISTORY_TURNS
        ),
        microphone_device=_device_selector(os.getenv("XD_AI_MICROPHONE")),
        audio_sample_rate=_optional_positive_int(os.getenv("XD_AI_SAMPLE_RATE")),
        whisper_model=(
            os.getenv("XD_AI_WHISPER_MODEL", DEFAULT_WHISPER_MODEL).strip()
            or DEFAULT_WHISPER_MODEL
        ),
        whisper_device=os.getenv("XD_AI_WHISPER_DEVICE", "cpu").strip() or "cpu",
        whisper_compute_type=(
            os.getenv("XD_AI_WHISPER_COMPUTE_TYPE", "int8").strip() or "int8"
        ),
        tts_rate=_positive_int(os.getenv("XD_AI_TTS_RATE"), DEFAULT_TTS_RATE),
        tts_voice=_optional_value("XD_AI_TTS_VOICE"),
    )


def _optional_value(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _positive_int(value: str | None, default: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _optional_positive_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _device_selector(value: str | None) -> int | str | None:
    if value is None or not value.strip():
        return None
    selector = value.strip()
    try:
        return int(selector)
    except ValueError:
        return selector

