"""Gemini API client boundary and in-memory conversation context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from xd_ai.core.config import Settings


class GeminiConfigurationError(RuntimeError):
    """Raised when Gemini is used without the required configuration."""


class GeminiServiceError(RuntimeError):
    """Raised when the Gemini service cannot produce a usable response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GenerateContentClient(Protocol):
    """Small SDK surface used by this application, enabling straightforward tests."""

    models: Any


@dataclass(frozen=True, slots=True)
class Message:
    role: str
    text: str


class Conversation:
    """A bounded, in-memory list of completed user/assistant turns."""

    def __init__(self, max_turns: int) -> None:
        self._max_turns = max_turns
        self._messages: list[Message] = []

    def contents_for(self, user_text: str) -> list[dict[str, object]]:
        """Build SDK-compatible content including history and the next user message."""
        messages = [*self._messages, Message(role="user", text=user_text)]
        return [
            {"role": message.role, "parts": [{"text": message.text}]}
            for message in messages
        ]

    def add_turn(self, user_text: str, assistant_text: str) -> None:
        self._messages.extend(
            [Message(role="user", text=user_text), Message(role="model", text=assistant_text)]
        )
        self._messages = self._messages[-(self._max_turns * 2) :]

    def clear(self) -> None:
        self._messages.clear()

    @property
    def message_count(self) -> int:
        return len(self._messages)


class GeminiService:
    """Send text prompts to Gemini and retain successful local conversation turns."""

    def __init__(self, settings: Settings, client: GenerateContentClient | None = None) -> None:
        self._settings = settings
        self._conversation = Conversation(settings.max_history_turns)
        self._client = client

    def ask(self, user_text: str) -> str:
        """Return Gemini's answer or a meaningful, safe exception."""
        if not self._settings.has_gemini_credentials:
            raise GeminiConfigurationError(
                "Gemini is not configured. Add GEMINI_API_KEY to your local .env file."
            )

        client = self._client or self._create_client()
        try:
            response = client.models.generate_content(
                model=self._settings.gemini_model,
                contents=self._conversation.contents_for(user_text),
            )
        except Exception as error:  # The SDK exposes several transport/API exception types.
            raise self._service_error(error) from error

        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise GeminiServiceError("Gemini returned no text response for this request.")

        answer = text.strip()
        self._conversation.add_turn(user_text, answer)
        return answer

    def clear_conversation(self) -> None:
        self._conversation.clear()

    def list_available_models(self) -> list[str]:
        """List models available to this API key that can generate content."""
        if not self._settings.has_gemini_credentials:
            raise GeminiConfigurationError(
                "Gemini is not configured. Add GEMINI_API_KEY to your local .env file."
            )

        client = self._client or self._create_client()
        try:
            models = client.models.list()
            names = {
                self._model_id(model.name)
                for model in models
                if model.name
                and "generateContent" in (model.supported_actions or [])
            }
        except Exception as error:
            raise self._service_error(error) from error
        return sorted(names)

    def _create_client(self) -> GenerateContentClient:
        try:
            from google import genai
            from google.genai import types
        except ImportError as error:
            raise GeminiConfigurationError(
                "The Google Gen AI SDK is not installed. Run: pip install -e '.[dev]'"
            ) from error
        return genai.Client(
            api_key=self._settings.gemini_api_key,
            http_options=types.HttpOptions(
                # Use the SDK's built-in retry policy. Do not add another retry loop here.
                retry_options=types.HttpRetryOptions()
            ),
        )

    def _service_error(self, error: Exception) -> GeminiServiceError:
        status_code = self._status_code(error)
        messages = {
            503: (
                "Gemini is temporarily unavailable after automatic retries. "
                "Please wait a moment and try again."
            ),
            429: (
                "Gemini's rate limit was reached after automatic retries. "
                "Please wait before trying again or check your API quota."
            ),
            404: (
                f"The configured model '{self._settings.gemini_model}' is unavailable. "
                "Use /models to list compatible models, then update GEMINI_MODEL in .env."
            ),
            401: (
                "Gemini authentication failed. Check GEMINI_API_KEY and its permissions; "
                "the key has not been displayed."
            ),
            403: (
                "Gemini denied this request. Check GEMINI_API_KEY, API access, and project "
                "permissions; the key has not been displayed."
            ),
        }
        message = messages.get(
            status_code,
            "Gemini could not complete the request. Check your connection and try again.",
        )
        return GeminiServiceError(message, status_code=status_code)

    @staticmethod
    def _status_code(error: Exception) -> int | None:
        for candidate in (
            getattr(error, "code", None),
            getattr(error, "status_code", None),
            getattr(getattr(error, "response", None), "status_code", None),
        ):
            if isinstance(candidate, int):
                return candidate
        return None

    @staticmethod
    def _model_id(name: str) -> str:
        """Return the model ID users can place directly in GEMINI_MODEL."""
        return name.removeprefix("models/")

