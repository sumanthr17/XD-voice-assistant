"""Configuration loading for XD AI."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_MODEL = "gemini-3.1-flash-lite"
DEFAULT_HISTORY_TURNS = 10


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration sourced from the local environment."""

    gemini_api_key: str | None
    gemini_model: str = DEFAULT_MODEL
    max_history_turns: int = DEFAULT_HISTORY_TURNS

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

